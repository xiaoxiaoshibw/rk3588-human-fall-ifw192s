"""Local sequential replay of four sessions; offline background and ground are precomputed."""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'pc_apps/range_fall'), str(ROOT/'src/human_fall_detection')]
import human_prior_probe as probe
import session_compare as sc
from core.capture_input import ROW_DTYPE, sha256_file
from core.range_demo_alert import DemoAlert
from core.range_features import bound_ground
from core.range_png import png
from target_expansion import supplemental

NAMES = ('houdao','qiandao','huanmandiedao','jixiedaiwanyao')


def target_geometry(xyz, rows, basis, offset):
    """All measured target rows, in the same ground-aligned frame as the 3D view."""
    if not rows:
        return None
    points = sc.to_display(xyz[np.asarray(rows, dtype=np.int64)], basis, offset)
    if not np.isfinite(points).all():
        return None
    return dict(center_m=np.median(points, axis=0).tolist(),
                min_m=np.min(points, axis=0).tolist(), max_m=np.max(points, axis=0).tolist())


def target_rectangle(valid, source_rows, rows):
    """Inclusive bounds in the 180-degree-rotated displayed depth image."""
    mask = (valid & np.isin(source_rows, np.asarray(rows, dtype=np.int64)))[::-1, ::-1]
    yy, xx = np.nonzero(mask)
    return None if not len(xx) else [int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())]


class Activity:
    """Combine causal geometric observations without turning low posture into a fall event."""
    def __init__(self):
        self.alert = DemoAlert()
    def update(self, rule, record, binding):
        f = rule['features']; h = f.get('height_m') or {}
        measured = bool(record['target_source_rows']) and f.get('observable') and f.get('ground_relative')
        row = dict(i=record['frame'], t=record['time_s'], tid=record['target_track_id'],
                   n=len(record['target_source_rows']) if measured else 0,
                   hm=f.get('height_median_m') if measured else None,
                   ht=h.get('max') if measured else None,
                   sp=f.get('horizontal_extent_m') if measured else None,
                   generation=record['generation'], binding=binding, reset=f.get('reset_now') or f.get('observation_gap'))
        level = self.alert.update(row)
        state = rule['state']['state'] if measured else 'unknown'
        posture = rule['posture']['state'] if measured else 'unknown'
        # Low-horizontal measurements supplement posture when PCA is unavailable;
        # the output stays a geometric candidate and never creates confirmed events.
        if not measured:
            label = 'unknown'
        elif state == 'suspected':
            label = 'fall_suspected'
        elif level:
            label = 'low_horizontal_sustained' if level == 2 else 'low_horizontal_candidate'
        elif state in ('descending','recovering'):
            label = state
        elif self.alert.eligible:
            label = 'low_horizontal_pending'
        else:
            label = posture
        return dict(label=label, posture=posture, state=state, level=level,
                    low_duration_s=self.alert.duration, measured=bool(measured),
                    low_eligible=self.alert.eligible,
                    reason_codes=rule['state'].get('reason_codes') or [],
                    posture_reason=rule['posture'].get('reason'),
                    human_semantic='UNKNOWN', confirmed=False)

class Replay:
    def __init__(self, name):
        if name not in NAMES: raise ValueError('unknown session')
        self.name=name; self.session=ROOT/'data/sessions'/('cap_20261028_'+name)
        start=time.perf_counter()
        self.meta,self.identity,self.binding,self.count,self.ground,self.runtime=probe.build_inputs(self.session)
        self.prepare_s=time.perf_counter()-start
        self.basis=sc.display_basis(self.ground['normal'])
        self.stream=(self.session/'points.bin').open('rb'); self.index=0; self.activity=Activity()
        self.base=self.meta['frames'][0]['stamp_sec']+self.meta['frames'][0]['stamp_nanosec']/1e9
    def close(self): self.stream.close()
    def next(self, visuals=True, trace=False):
        if self.index>=self.count: return None
        start=time.perf_counter(); i=self.index; info=self.meta['frames'][i]
        raw=self.stream.read(info['count_points']*ROW_DTYPE.itemsize)
        if len(raw)!=info['count_points']*ROW_DTYPE.itemsize: raise ValueError('truncated source frame')
        stamp=info['stamp_sec']+info['stamp_nanosec']/1e9
        result,frame,components=self.runtime.update(raw,stamp,i)
        record=result['tracking']; rule=result['rule']; rows=record['target_source_rows']
        activity=self.activity.update(rule,record,frame.binding)
        features=rule['features']; height=features.get('height_m') or {}
        selected=bool(rows) and record['target_track_id'] is not None
        geometry=(target_geometry(frame.xyz, rows, self.basis, self.ground['offset_m'])
                  if selected and bound_ground(frame, self.ground) else None)
        expanded=supplemental(frame,self.runtime.background,record,self.basis,self.ground['offset_m'])
        extra_rows=expanded.pop('source_rows')
        expanded['rows_sha256']=hashlib.sha256(np.asarray(extra_rows,dtype='<i8').tobytes()).hexdigest()
        expanded['depth_box']=target_rectangle(frame.valid, frame.source_rows, rows+extra_rows) if extra_rows else None
        expanded['geometry']=target_geometry(frame.xyz,rows+extra_rows,self.basis,self.ground['offset_m']) if extra_rows and geometry else None
        exploration=supplemental(frame,self.runtime.background,record,self.basis,self.ground['offset_m'],delta_m=.15)
        exploratory_rows=exploration.pop('source_rows')
        exploratory_only=np.setdiff1d(exploratory_rows,extra_rows).tolist()
        exploration['added_beyond_supplemental']=len(exploratory_only)
        exploration['rows_sha256']=hashlib.sha256(np.asarray(exploratory_rows,dtype='<i8').tobytes()).hexdigest()
        exploration['depth_box']=target_rectangle(frame.valid,frame.source_rows,rows+extra_rows+exploratory_rows) if exploratory_only else None
        exploration['geometry']=target_geometry(frame.xyz,rows+extra_rows+exploratory_rows,self.basis,self.ground['offset_m']) if exploratory_only and geometry else None
        entry=dict(i=i,t=stamp-self.base,tid=record['target_track_id'],n=len(rows),
                   rows_sha256=hashlib.sha256(np.asarray(rows,dtype='<i8').tobytes()).hexdigest(),
                   activity=activity, hm=features.get('height_median_m'), ht=height.get('max'),
                   extent=features.get('horizontal_extent_m'), descent=features.get('descent_rate_m_s'),
                   verticality=features.get('axis_verticality'), geometry=geometry,
                   depth_box=target_rectangle(frame.valid, frame.source_rows, rows) if selected else None,
                   supplemental=expanded, exploration=exploration,
                   runtime_ms=result['timings']['event_chain_ms'])
        if trace:
            from stage_trace import trace_frame
            entry['trace']=trace_frame(frame,self.runtime.background,record,components,
                                       self.basis,self.ground['offset_m'],extra_rows,exploratory_rows)
        if visuals:
            valid=frame.valid; t=np.clip((frame.range_m[valid]-.1)/7.9,0,1)
            rgb=np.zeros(valid.shape+(3,),dtype=np.uint8)
            rgb[valid]=np.column_stack((255*(1-t),255*(1-np.abs(2*t-1)),255*t)).astype(np.uint8)
            target=valid & np.isin(frame.source_rows,np.asarray(rows,dtype=np.int64))
            extra=valid & np.isin(frame.source_rows,np.asarray(extra_rows,dtype=np.int64))
            wider=valid & np.isin(frame.source_rows,np.asarray(exploratory_only,dtype=np.int64))
            # White highlights exactly the measured target pixels in this same frame.
            rgb[wider]=[100,195,255]
            rgb[extra]=[255,185,75]
            rgb[target]=[255,255,255]
            entry['depth']='data:image/png;base64,'+base64.b64encode(png(rgb[::-1,::-1])).decode('ascii')
            scene_rows=frame.source_rows[valid]
            if len(scene_rows)>2200: scene_rows=scene_rows[np.linspace(0,len(scene_rows)-1,2200,dtype=np.int64)]
            target_rows=np.asarray(rows,dtype=np.int64)
            if len(target_rows)>1800: target_rows=target_rows[np.linspace(0,len(target_rows)-1,1800,dtype=np.int64)]
            # Display sampling only; inference and pixel ownership retain every measured row.
            scene_xyz=sc.to_display(frame.xyz[scene_rows],self.basis,self.ground['offset_m'])
            target_xyz=sc.to_display(frame.xyz[target_rows],self.basis,self.ground['offset_m'])
            extra_display=np.asarray(extra_rows,dtype=np.int64)
            if len(extra_display)>1800: extra_display=extra_display[np.linspace(0,len(extra_display)-1,1800,dtype=np.int64)]
            extra_xyz=sc.to_display(frame.xyz[extra_display],self.basis,self.ground['offset_m'])
            wider_display=np.asarray(exploratory_only,dtype=np.int64)
            if len(wider_display)>1800: wider_display=wider_display[np.linspace(0,len(wider_display)-1,1800,dtype=np.int64)]
            wider_xyz=sc.to_display(frame.xyz[wider_display],self.basis,self.ground['offset_m'])
            entry['scene']=sc.quantize(scene_xyz); entry['target']=sc.quantize(target_xyz); entry['extra']=sc.quantize(extra_xyz); entry['wider']=sc.quantize(wider_xyz)
        entry['processing_ms']=(time.perf_counter()-start)*1000
        self.index+=1
        return entry

def batch(out, trace=False, mode='historical'):
    out=Path(out).resolve()
    for protected in (ROOT/'data',ROOT/'captures'):
        protected=protected.resolve()
        if out==protected or protected in out.parents:
            raise ValueError('evidence must be outside data/captures')
    out.mkdir(parents=True,exist_ok=False); summary={}
    for name in (('site_empty',)+NAMES if mode=='service' else NAMES):
        if mode=='service':
            from service_replay import ServiceReplay
            replay=ServiceReplay(name,output=out/name,deterministic=True)
        else:replay=Replay(name)
        rows=[]
        try:
            while True:
                row=replay.next(False, trace=trace)
                if row is None: break
                rows.append(row)
            if mode=='historical':
                assert sha256_file(replay.session/'points.bin')==replay.identity['points_sha256']
                assert sha256_file(replay.session/'meta.json')==replay.identity['meta_sha256']
            (out/(name+'.jsonl')).write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows),encoding='utf8')
            levels=[r['i'] for r in rows if r['activity']['level']>=1]
            hist={s:sum(r['activity']['label']==s for r in rows) for s in sorted(set(r['activity']['label'] for r in rows))}
            costs=[r['runtime_ms'] for r in rows]
            summary[name]=dict(frames=len(rows),histogram=hist,first_low_frame=levels[0] if levels else None,
                               low_frames=len(levels), sustained_frames=sum(r['activity']['level']==2 for r in rows),
                               runtime_p95_ms=float(np.percentile(costs,95)),prepare_s=replay.prepare_s,
                               mode=mode,causal=mode=='service',
                               source_identity=replay.identity,
                               initialization=dict(replay.initializer.status) if mode=='service' else None)
            print(name,json.dumps(summary[name],ensure_ascii=False),flush=True)
        finally: replay.close()
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf8')

class Handler(BaseHTTPRequestHandler):
    replay=None
    def do_GET(self):
        path=urlparse(self.path)
        try:
            if path.path=='/':
                body=(Path(__file__).parent/'pseudo_live.html').read_bytes(); typ='text/html; charset=utf-8'
            elif path.path=='/start':
                query=parse_qs(path.query)
                name=query.get('name',[''])[0]
                mode=query.get('mode',['service'])[0]
                if mode not in ('service','historical'):raise ValueError('unknown replay mode')
                if Handler.replay: Handler.replay.close(); Handler.replay=None
                if mode=='service':
                    from service_replay import ServiceReplay
                    Handler.replay=ServiceReplay(name)
                else:Handler.replay=Replay(name)
                body=json.dumps(dict(frames=Handler.replay.count,prepare_s=Handler.replay.prepare_s,mode=mode)).encode(); typ='application/json'
            elif path.path=='/next':
                if Handler.replay is None: raise ValueError('start a session first')
                body=json.dumps(Handler.replay.next(),allow_nan=False).encode(); typ='application/json'
            else:
                self.send_error(404); return
            self.send_response(200); self.send_header('Content-Type',typ); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        except (ValueError, OSError) as e:
            self.send_error(400,str(e))
    def log_message(self,*args): pass

def main():
    p=argparse.ArgumentParser(); p.add_argument('--batch',type=Path); p.add_argument('--port',type=int,default=8899); p.add_argument('--trace',action='store_true')
    p.add_argument('--mode',choices=('service','historical'),default='service')
    a=p.parse_args()
    if a.batch: batch(a.batch, trace=a.trace, mode=a.mode); return
    server=HTTPServer(('127.0.0.1',a.port),Handler)
    print('http://127.0.0.1:%d/'%a.port,flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        if Handler.replay: Handler.replay.close()
        server.server_close()
if __name__=='__main__': main()

