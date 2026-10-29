"""Exclusive localhost GET-only indexed replay. Single frame cost O(frame rows)."""
import argparse
import json
import os
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs,urlparse
import numpy as np
from contracts import HERE, ITEM, Source, sha, write_new, guarded
from pipeline import LABELS


class Replay:
    def __init__(self,path,cases=None):
        self.path=guarded(path);self.hashes=json.loads((self.path/'OUTPUT_INDEX.json').read_text(encoding='utf8'))
        for name,h in self.hashes.items():
            p=(self.path/name).resolve()
            if not p.is_relative_to(self.path) or sha(p)!=h:raise ValueError('Replay artifact drift: '+name)
        self.index=json.loads((self.path/'INDEX.json').read_text(encoding='utf8'))
        self.frames={f['fi']:f for f in self.index['frames']}
        if len(self.frames)!=len(self.index['frames']):raise ValueError('Duplicate frame')
        self.source=Source(self.index['entries'][0]);self.stats=self.source_stats()
        self.map={};self.map_meta=None
        if (self.path/'map/MAP.json').exists():
            self.map_meta=json.loads((self.path/'map/MAP.json').read_text(encoding='utf8'))
            with np.load(self.path/'map/surfaces.npz') as z:self.map={k:z[k] for k in z.files}
        self.cases=json.loads(Path(cases).read_text(encoding='utf8')) if cases else []

    def source_stats(self):
        return [(p.stat().st_size,p.stat().st_mtime_ns) for p in [self.source.folder/'meta.json',self.source.folder/'points.bin']]

    def verify(self):
        if self.source_stats()!=self.stats:raise ValueError('Source drift since full SHA verification; restart requires revalidation')
        if sha(self.source.folder/'meta.json')!=self.source.binding['meta']:raise ValueError('Source meta byte drift')
        if sha(self.path/'INDEX.json')!=self.hashes['INDEX.json']:raise ValueError('Index drift')

    def record(self,fi,variant):
        self.verify()
        if type(fi) is not int or fi not in self.frames or variant not in self.index['variants']:raise ValueError('Unknown frame/variant')
        meta=self.frames[fi]['variants'][variant]
        loaded=[]
        for key in ['record','ledger']:
            name=meta[key]
            if sha(self.path/name)!=self.hashes[name]:raise ValueError('Frame drift')
            loaded.append(self.path/name)
        r=json.loads(loaded[0].read_text(encoding='utf8'))
        with np.load(loaded[1]) as z:rows=z['current'];hits=z['map_hits']
        f=self.source.frames[fi]
        import hashlib
        raw28=self.source.buffer[f['offset_points']*28:(f['offset_points']+f['count_points'])*28] if self.source.buffer is not None else b''
        if hashlib.sha256(raw28).hexdigest()!=self.frames[fi].get('raw28_sha256'):raise ValueError('Raw28 frame byte drift (including opaque tail)')
        expected=dict(sid=self.source.sid,fi=fi,time_ns=self.source.stamps[fi],coordinate_version=self.source.entry['coordinate_version'])
        if (any(r.get(k)!=v for k,v in expected.items()) or len(rows)!=f['count_points'] or
            r['offset']!=f['offset_points'] or r['source_sha256']!=self.source.binding):raise ValueError('Frame/ledger/source mismatch')
        return r,rows,hits

    def row(self,fi,i,row):
        raw=self.source.raw_row(fi,int(i));flags=int(row['flags'])
        return dict(raw,label=LABELS[int(row['label'])],valid=bool(flags&1),background_compatible=bool(flags&2),
                    discovery_seed=bool(flags&4),continuation_support=bool(flags&8),target_member=bool(flags&16),
                    historical_ground_candidate_compatible=bool(flags&32),
                    candidate_id=int(row['candidate']),surface_id=int(row['surface']))

    def frame(self,fi,variant,limit=9000):
        r,rows,hits=self.record(fi,variant);p=self.source.frame(fi)['xyz'];n=len(rows)
        # Deterministic DISPLAY selection only. Candidate members get visibility priority.
        cand=np.flatnonzero(rows['candidate']>=0)
        uniform=np.linspace(0,max(n-1,0),min(n,max(0,limit-min(len(cand),3000))),dtype=int) if n else np.array([],dtype=int)
        chosen=np.unique(np.r_[uniform,cand[np.linspace(0,max(len(cand)-1,0),min(len(cand),3000),dtype=int)] if len(cand) else uniform])
        current=[]
        for i in chosen:
            flags=int(rows['flags'][i])
            current.append(dict(source_row=int(i),xyz=[float(x) if np.isfinite(x) else None for x in p[i]],label=LABELS[int(rows['label'][i])],
                         background_compatible=bool(flags&2),target_member=bool(flags&16),ground_candidate_compatible=bool(flags&32),candidate_id=int(rows['candidate'][i])))
        map_rows=[]
        # A finished map is never displayed as available on an earlier build frame.
        if r['candidate_map_exists']:
            ids=np.linspace(0,len(self.map['centers'])-1,min(3000,len(self.map['centers'])),dtype=int)
            visible=set(map(int,hits))
            for i in ids:map_rows.append(dict(surface_id=int(i),map_id=r['map_id'],xyz=self.map['centers'][i].tolist(),visibility='visible' if int(i) in visible else 'unobserved',current_member=False))
        return dict(r,current_rows=current,map_ledger=map_rows,display=dict(sample_rows=len(chosen),full_current_rows=n,sampling='deterministic display only',
                    map_sample=len(map_rows),map_total=len(self.map.get('centers',[])),full_ledger_url=f'/api/source-members?fi={fi}&variant={variant}&start=0&count=1000'))

    def surface(self,fi,variant,i,start=0,count=100):
        r,rows,hits=self.record(fi,variant)
        if not r['candidate_map_exists'] or not 0<=i<len(self.map['centers']):raise ValueError('Surface unavailable at this causal frame')
        if not 0<=start or not 1<=count<=1000:raise ValueError('Invalid support page')
        a,b=self.map['indptr'][i:i+2];support=self.map['support_global'][a:b];page=support[start:start+count]
        offsets=np.asarray([x['offset_points'] for x in self.source.frames]);out=[]
        for global_row in page:
            source_fi=int(np.searchsorted(offsets,global_row,side='right')-1)
            out.append(self.source.mapping(source_fi,global_row=int(global_row)))
        match=np.flatnonzero(((rows['flags']&2)!=0)&(rows['surface']==i))
        return dict(surface_id=i,map_id=r['map_id'],coordinate_version=r['coordinate_version'],source_sha256=self.source.binding,
               xyz=self.map['centers'][i].tolist(),finite_min=self.map['minimum'][i].tolist(),finite_max=self.map['maximum'][i].tolist(),
               observation_count=int(self.map['count'][i]),distinct_frames=int(self.map['frame_count'][i]),noise_std_xyz=self.map['noise'][i].tolist(),
               all_support_count=len(support),support_page_start=start,support=out,next_start=start+len(page) if start+len(page)<len(support) else None,
               visibility='visible' if i in hits else 'unobserved',strong_free=False,strong_occlusion=False,current_member=False,current_match_evidence_rows=match.tolist())


class Handler(BaseHTTPRequestHandler):
    def send(self,code,data,kind='application/json; charset=utf-8'):
        if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf8')
        self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)

    def do_GET(self):
        u=urlparse(self.path);q=parse_qs(u.query);replay=self.server.replay
        try:
            if u.path in ('/','/app.js'):
                name='index.html' if u.path=='/' else 'app.js'
                return self.send(200,(HERE/name).read_bytes(),'text/html; charset=utf-8' if u.path=='/' else 'text/javascript; charset=utf-8')
            if u.path=='/api/catalog':
                return self.send(200,dict(sessions=[dict(sid=replay.source.sid,kind='REAL_DEVELOPMENT',frames=list(replay.frames),times=[f['relative_s'] for f in replay.index['frames']],variants=replay.index['variants'],cases=replay.cases)],effectiveness='BLOCKED',stage='REAL_DIAGNOSTIC'))
            fi=int(q.get('fi',['-1'])[0]);variant=q.get('variant',['main'])[0]
            if q.get('sid',[replay.source.sid])[0]!=replay.source.sid:raise ValueError('Wrong sid')
            if u.path=='/api/frame':return self.send(200,replay.frame(fi,variant))
            if u.path=='/api/source':
                r,rows,_=replay.record(fi,variant);i=int(q['row'][0])
                if not 0<=i<len(rows):raise ValueError('Row outside frame')
                return self.send(200,replay.row(fi,i,rows[i]))
            if u.path=='/api/source-members':
                r,rows,_=replay.record(fi,variant);start=int(q.get('start',['0'])[0]);count=int(q.get('count',['1000'])[0])
                if not 0<=start<=len(rows) or not 1<=count<=2000:raise ValueError('Invalid row page')
                return self.send(200,dict(full_rows=len(rows),start=start,rows=[replay.row(fi,i,rows[i]) for i in range(start,min(len(rows),start+count))]))
            if u.path=='/api/surface':return self.send(200,replay.surface(fi,variant,int(q['surface_id'][0]),int(q.get('start',['0'])[0]),int(q.get('count',['100'])[0])))
            if u.path=='/api/candidate':
                r,rows,_=replay.record(fi,variant);i=int(q['id'][0]);c=next(c for c in r['candidates'] if c['id']==i)
                return self.send(200,dict(candidate=c,confirmation_template=dict(sid=r['sid'],fi=fi,time_ns=r['time_ns'],source_sha256=r['source_sha256'],coordinate_version=r['coordinate_version'],
                    candidate_version=c['version'],run_version=r['run_version'],protocol_sha=r['protocol_sha'],provenance='PENDING_ACTUAL_HUMAN',reviewer=None),human_confirmation=False))
            return self.send(404,dict(error='Unknown endpoint'))
        except (ValueError,KeyError,OSError,IndexError,StopIteration) as e:return self.send(400,dict(error=str(e)))

    def do_POST(self):self.send(405,dict(error='Read-only replay; actual user confirmation captured separately'))
    def log_message(self,*a):pass


class Server(ThreadingHTTPServer):allow_reuse_address=False


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--cases');p.add_argument('--port',type=int,default=0);p.add_argument('--process-record',required=True);a=p.parse_args()
    service=Server(('127.0.0.1',a.port),Handler);service.replay=Replay(a.run,a.cases)
    write_new(a.process_record,dict(pid=os.getpid(),address=service.server_address,run=a.run,cases=a.cases,command=sys.argv,scope='localhost-read-only'))
    print('http://127.0.0.1:%d/'%service.server_port,flush=True);service.serve_forever()
