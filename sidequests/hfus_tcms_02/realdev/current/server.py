"""Existing replay API backed by the active, source-bound development pipeline."""
import argparse
import importlib.util
import json
import sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import numpy as np
from coordinates import GroundCoordinates

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('active_project_runner',HERE/'run.py')
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
ROOT=P.ROOT
sys.path.insert(0,str(ROOT/'ML/src'))
from fall_geometry import FallGeometryRuntime,DEFAULTS as EVENT_SETTINGS

class Store:
    def __init__(self,pointer_path=None):
        pointer=json.loads(Path(pointer_path or HERE/'LATEST.json').read_text(encoding='utf8'))
        self.out=(ROOT/pointer['output']).resolve()
        allowed=(ROOT/'docs/evidence',ROOT/'docs/human_fall/evidence')
        if not any(self.out.is_relative_to(root.resolve()) for root in allowed):raise ValueError('invalid project output')
        for n in ('RUN.json','FINISHED.json','orientation_frames.jsonl','partition_frames.jsonl'):
            if P.sha(self.out/n)!=pointer['files'][n]:raise ValueError('project output changed: '+n)
        if not (self.out/'FINISHED.json').is_file():raise ValueError('incomplete project run')
        binding=json.loads((self.out/'RUN.json').read_text(encoding='utf8'))
        for n in ('run.py','project_regions.py','project_dependencies.py','project_fall.py','target_points.py','coordinates.py','region_runtime.py'):
            if P.sha(HERE/n)!=binding['source_sha'][n]:raise ValueError('algorithm changed; rerun project pipeline: '+n)
        for n,h in binding['fall']['core_sha'].items():
            if P.sha(ROOT/'src/human_fall_detection/core'/n)!=h:raise ValueError('core changed; rerun: '+n)
        self.binding=binding
        transform=pointer['ground_transform']
        path=(ROOT/transform['path']).resolve()
        if P.sha(path)!=transform['sha256'] or transform['sha256']!=binding['ground']['sha256']:
            raise ValueError('ground transform differs from completed run')
        self.src=P.source(binding['session']);self.sid=self.src.sid
        try:
            if self.src.binding!=binding['input_sha']:raise ValueError('session input changed')
            self.coordinates=GroundCoordinates(path,self.sid,self.src.binding)
            self.data={k:[json.loads(l) for l in path.read_text(encoding='utf8').splitlines()]
                for k,path in dict(orientation=self.out/'orientation_frames.jsonl',partition=self.out/'partition_frames.jsonl').items()}
            if any(r['binding']['ground_version']!=self.coordinates.artifact['transform_id']
                   for records in self.data.values() for r in records):
                raise ValueError('frame ground version differs from display transform')
            self.default=pointer['default_variant']
            if self.default not in self.data:raise ValueError('invalid project default')
            # Precompute strictly in source order, independent of HTTP seek order.
            # The frozen target rows and the original fall state stay untouched.
            self.event_geometry={}
            for variant,records in self.data.items():
                runtime=FallGeometryRuntime(self.coordinates.R[2],float(self.coordinates.t[2]))
                values=[]
                for row in records:
                    frame=self.src.frame(row['fi']);rows=np.asarray(row['target_rows'],dtype=np.int64)
                    local=rows-frame['offset'];raw=frame['xyz'];track=row['track'];binding=row['binding']
                    if (local<0).any() or (local>=len(raw)).any() or len(np.unique(rows))!=len(rows):
                        raise ValueError('event preview target provenance invalid')
                    observed=bool(len(rows)>=EVENT_SETTINGS['minimum_points'] and track['status']=='locked' and not track['predicted'])
                    values.append(runtime.push(raw[local],row['t'],(self.sid,track['track_id']),
                        (binding['time_epoch'],track['generation'],track['selection_version']),
                        (self.binding['ground']['sha256'],binding['ground_version']),observed=observed))
                self.event_geometry[variant]=values
            self.event_binding=dict(algorithm='seconds_geometry_v1',mode='PC_OFFLINE_SHADOW',
                geometry_source_sha256=P.sha(ROOT/'ML/src/fall_geometry.py'),
                binding_source_sha256=P.sha(ROOT/'ML/src/human_pointset.py'),
                adapter_sha256=P.sha(HERE/'server.py'),settings=dict(EVENT_SETTINGS),
                ground_transform_sha256=self.binding['ground']['sha256'],
                source=self.src.binding,temporal_model='NOT_TRAINED_NOT_LOADED',
                confirmed_enabled=False,physical_validity='UNKNOWN',
                summary={key:dict(frames=len(values),candidate_events=sum(v['new_event'] is not None for v in values),
                    unknown_frames=sum(v['state']=='unknown' for v in values)) for key,values in self.event_geometry.items()})
            # Session-level calibration picture: an edge that never reaches CALIBRATED
            # because it is short/sparse is reported explicitly instead of looking broken.
            self.calibration_stats={}
            for variant,rows in self.data.items():
                stats={}
                for a,b in P.SK.EDGES:
                    key=a+'|'+b;states=[];lengths=[];supports=[]
                    for r in rows:
                        snap=r['calibration']['edges'][key];states.append(snap['state'])
                        na,nb=r['nodes'][a],r['nodes'][b]
                        if na['xyz'] is not None and nb['xyz'] is not None:
                            lengths.append(float(np.linalg.norm(np.asarray(na['xyz'])-np.asarray(nb['xyz']))))
                        if na['valid'] and nb['valid']:supports.append(min(na['support_n'],nb['support_n']))
                    stats[key]=dict(ever_calibrated='CALIBRATED' in states,
                        median_length_m=float(np.median(lengths)) if lengths else None,
                        median_min_support=float(np.median(supports)) if supports else None)
                stats['__short_sparse__']=[k for k,v in stats.items() if isinstance(v,dict) and not v['ever_calibrated']
                    and v['median_length_m'] is not None and (v['median_length_m']<.15 or (v['median_min_support'] or 0)<20)]
                self.calibration_stats[variant]=stats
        except BaseException:
            self.src.close()
            raise

    def info(self):
        return dict(sessions={self.sid:dict(frames=len(self.src.frames),times=self.src.times,events=[],source=self.src.binding)},
            variants=dict(partition='当前开发：自动目标与支撑分区',orientation='对照：自动目标只修方向'),
            default_variant=self.default,skeleton_slots=P.SK.SLOTS,coordinate=self.coordinates.frame,
            analysis_coordinate='RAW/innolidar',default_coordinate='ground',
            region_contract=self.binding.get('region_contract','legacy_raw_roi'),
            ground_normal_raw=self.coordinates.R[2].tolist(),
            ground_transform_id=self.coordinates.artifact['transform_id'],
            ground_transform_sha256=self.binding['ground']['sha256'],
            event_geometry=self.event_binding,
            input_scope=self.binding.get('input_scope',dict(kind=self.binding['pipeline'])),
            view_centers={k:self.coordinates.points([1.575,1.275,.725],k).tolist() for k in ('ground','raw')},
            leveling=dict(pitch_deg=self.coordinates.artifact['plane']['pitch_deg'],roll_deg=self.coordinates.artifact['plane']['roll_deg'],ground_z_m=0),
            background=dict(explicit=self.binding['background'],warmup_frames=self.binding['empty_prefix_frames']),
            candidate_history=dict(policy=self.binding.get('candidate_history',{}).get('policy','unavailable'),semantic='unknown',
                ledger='candidate_history in completed frame records; actual rows, structure and support deltas'),
            output=self.out.relative_to(ROOT).as_posix(),pipeline=self.binding['pipeline'],
            limits=['reused development session','semantic UNKNOWN','human precision/recall UNKNOWN',
                    'confirmed disabled','predictions are not observations'])

    def frame(self,sid,fi,variant,mode='fg',key=None,coordinate='ground'):
        if sid!=self.sid or variant not in self.data or not 0<=fi<len(self.src.frames):raise ValueError('invalid session/frame/variant')
        if mode not in ('fg','room'):raise ValueError('invalid point mode')
        if coordinate not in ('ground','raw'):raise ValueError('invalid coordinate space')
        frame_id=self.coordinates.frame if coordinate=='ground' else 'RAW/innolidar'
        f=self.src.frame(fi);raw=f['xyz'];r=self.data[variant][fi]
        rows=np.asarray(r['foreground_rows'],dtype=np.int64)
        target_rows=np.asarray(r['target_rows'],dtype=np.int64)
        sources=dict(candidate_rows=sum(c['point_count'] for c in r['clusters']),
            foreground_rows=int(len(rows)),background_removed=None,
            reference_build=r['acquisition']['reason']=='declared_background_warmup')
        target=self.coordinates.points(raw[rows-f['offset']],coordinate)
        body=self.coordinates.points(raw[target_rows-f['offset']],coordinate)
        if key is not None:
            if key not in P.SK.SLOTS:raise ValueError('invalid region')
            n=r['nodes'][key];sup=np.array(n['support_rows'],dtype=int)
            return dict(key=key,points=self.coordinates.points(raw[sup-f['offset']],coordinate).tolist(),global_rows=sup.tolist(),
                local_rows=(sup-f['offset']).tolist(),measured=n['valid'],coordinate=frame_id,variant=variant)
        nodes={}
        for k,n in r['nodes'].items():
            nodes[k]={x:v for x,v in n.items() if x not in ('support_rows','xyz_local')}
            if n['xyz'] is not None:nodes[k]['xyz']=self.coordinates.points(n['xyz'],coordinate).tolist()
        sk=dict(nodes=nodes,
            edges=[[a,b] for a,b in P.SK.EDGES if r['nodes'][a]['valid'] and r['nodes'][b]['valid']],
            diagnostics={k:r.get('diagnostics',{}).get(k) for k in ['orientation_sign_flipped','orientation_reference_used','branch_partition','region_contract','ground_up_raw']},reason=r['reason'])
        track=r.get('track') or dict(track_id=None,status='unselected',predicted=False,requires_reselection=False,generation=0)
        fall=r.get('fall') or dict(status='unknown',reasons=['no_fall_state'],height_m=None,descent_rate_m_s=None,near_ground_duration_s=None,event_count=0,confirmed_enabled=False,baseline_ready=False,limitations=[])
        measured=r.get('candidate')
        # Per-edge calibration diagnostics: length and support explain edges that
        # cannot reach the frozen 5%/2 cm gate (short, sparse branch edges).
        edges={}
        for a,b in P.SK.EDGES:
            key=a+'|'+b;snap=r['calibration']['edges'][key]
            na,nb=r['nodes'][a],r['nodes'][b]
            length=None
            if na['xyz'] is not None and nb['xyz'] is not None:
                length=float(np.linalg.norm(np.asarray(na['xyz'])-np.asarray(nb['xyz'])))
            edges[key]=dict(state=snap['state'],n=snap['n'],mean=snap['mean'],std=snap['std'],
                measurement=snap['measurement'],length_m=length,
                support_n=[na['support_n'],nb['support_n']],
                ever_calibrated=self.calibration_stats[variant][key]['ever_calibrated'],
                session_length_m=self.calibration_stats[variant][key]['median_length_m'])
        short=list(self.calibration_stats[variant]['__short_sparse__'])
        row=dict(frame=fi,t=r['t'],skeleton=sk,calibration=r['calibration'],
            event_geometry=self.event_geometry[variant][fi],
            calibration_edges=dict(edges=edges,short_sparse=short),
            track_id=track['track_id'] if track['status'] in ('locked','occluded') else None,track=track,fall=fall,
            acquisition=r['acquisition'],target_source_rows=r['target_rows'],
            target_candidate_id=r['target_candidate_id'],binding=r['binding'],semantic='unknown',
            sources=sources,
            state=dict(state=fall['status'],reason_codes=fall['reasons']),alert_active=False,prototype_alert=False,
            observed=bool(len(body)) and track['status']=='locked' and not track['predicted'],
            bbox=None if not len(body) else dict(min=body.min(0).tolist(),max=body.max(0).tolist()),
            bbox_foreground=None if not len(target) else dict(min=target.min(0).tolist(),max=target.max(0).tolist()),
            foreground=dict(points=int(len(target)),body_points=int(len(body)),
                outlier_points=int(len(target)-len(body)),components=len(r['clusters'])),
            candidate=dict(height_m=measured['height_m'],point_count=measured['point_count'],
                horizontal_extent_m=measured['horizontal_extent_m']) if measured else None,
            features=dict(height_drop_m=None,descent_rate_m_s=fall.get('descent_rate_m_s'),
                near_ground_duration_s=fall.get('near_ground_duration_s')))
        valid=np.isfinite(raw).all(1)&np.any(raw!=0,1)
        return dict(sid=sid,row=row,fg=target.tolist(),target=body.tolist(),
            room=self.coordinates.points(raw[valid],coordinate).tolist() if mode=='room' else [],coordinate=frame_id,variant=variant)

STORE=None

class Handler(BaseHTTPRequestHandler):
    def send(self,value,mime='application/json; charset=utf-8',code=200):
        data=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf8')
        self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)

    def do_GET(self):
        global STORE
        u=urlsplit(self.path)
        assets={'/':'index.html','/app.js':'app.js'}
        if u.path in assets:return self.send((HERE/assets[u.path]).read_bytes(),'text/html; charset=utf-8' if u.path=='/' else 'application/javascript')
        if u.path in ('/three.min.js','/OrbitControls.js'):
            return self.send((ROOT/'pc_apps/human_replay/vendor'/u.path[1:]).read_bytes(),'application/javascript')
        if u.path=='/favicon.ico':return self.send(b'','image/x-icon',204)
        if u.path=='/api/info':return self.send(STORE.info())
        if u.path in ('/api/frame','/api/support'):
            try:
                q=parse_qs(u.query,strict_parsing=True)
                allowed={'sid','i','variant','mode','key','coordinate'}
                if not {'sid','i'}<=set(q) or set(q)-allowed or any(len(v)!=1 for v in q.values()):raise ValueError('invalid query')
                if u.path=='/api/support' and 'key' not in q:raise ValueError('region key required')
                return self.send(STORE.frame(q['sid'][0],int(q['i'][0]),q.get('variant',[STORE.default])[0],
                    q.get('mode',['fg'])[0],q.get('key',[None])[0] if u.path=='/api/support' else None,
                    q.get('coordinate',['ground'])[0]))
            except (ValueError,KeyError,IndexError) as exc:return self.send(dict(error=str(exc)),code=400)
        return self.send(dict(error='not found'),code=404)

    def log_message(self,*args):pass

def create_server(port=0):
    global STORE
    if STORE is None:STORE=Store()
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8934);a=ap.parse_args()
    server=create_server(a.port);print('Project replay http://127.0.0.1:%d/'%server.server_address[1],flush=True)
    server.serve_forever()
