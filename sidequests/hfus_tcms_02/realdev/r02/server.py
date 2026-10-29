"""Loopback GET-only candidate preview, persisted full numeric outputs."""
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
import numpy as np
from bootstrap import ROOT,OUT,write,sha
from preview import Frozen,load,sampled_ids,make_transform,validate_output_binding,validate_record_binding,source_payload
from coordinates import Transform,valid_xyz

HERE=__import__('pathlib').Path(__file__).resolve().parent


def finite(x):
    return [float(v) if np.isfinite(v) else None for v in x]


class Preview:
    def __init__(self,run='full_final'):
        self.protocol=load(OUT/'PROTOCOL_V1.json');self.T=Transform(load(OUT/'TRANSFORM_V1.json'))
        if self.T.artifact!=make_transform(self.protocol):raise ValueError('Candidate artifact changed; new run required')
        if not run.replace('_','').isalnum():raise ValueError('Unsafe output run')
        self.frozen=Frozen(self.protocol);self.path=OUT/run
        self.hashes=load(self.path/'OUTPUT_INDEX.json')
        for name,h in self.hashes.items():
            if sha(self.path/name)!=h:raise ValueError('Persisted output drift '+name)
        validate_output_binding(self.T,load(self.path/'INDEX.json'),sha(OUT/'TRANSFORM_V1.json'),self.frozen.source.binding)
        self.map_local=np.load(self.path/'map/centers.npy',allow_pickle=False)
        self.map_obb=np.load(self.path/'map/obb_corners.npy',allow_pickle=False)
        self.support_local=np.memmap(self.path/'map/support_local_xyz.bin',mode='r',dtype='<f8',shape=(len(self.frozen.map['support_global']),3))
        self.map_meta=load(self.path/'map/MAP.json')
        if self.map_meta['tag']!=self.T.tag(-1):raise ValueError('Stale map coordinate version')
        self.trajectory=load(self.path/'TRAJECTORY.json')

    def request_version(self,q):
        for key,expected in [('transform_id',self.T.id),('coordinate_version',self.T.version)]:
            if key in q and q[key]!=[expected]:raise ValueError('Mixed/stale transform version')

    def frame(self,fi):
        f,r,rows,hits,p=self.frozen.frame(fi)
        for suffix in ['npy','json']:
            name='%04d.%s'%(fi,suffix)
            if sha(self.path/name)!=self.hashes[name]:raise ValueError('Output frame drift')
        q=np.load(self.path/('%04d.npy'%fi),allow_pickle=False)
        record=load(self.path/('%04d.json'%fi));selected=sampled_ids(rows)
        validate_record_binding(self.T,record,fi,self.frozen.source.binding)
        current=[]
        for i in selected:
            current.append(dict(source_row=int(i),global_row=int(f['offset_points']+i),raw_xyz=finite(p[i]),local_xyz=finite(q[i]),
                raw_tag=self.T.tag(fi,False),tag=self.T.tag(fi),valid=bool(rows['flags'][i]&1),
                flags=int(rows['flags'][i]),label=int(rows['label'][i]),candidate_id=int(rows['candidate'][i])))
        map_rows=[];support=[]
        if record['candidate_map_exists']:
            chosen=np.linspace(0,len(self.map_local)-1,min(3000,len(self.map_local)),dtype=int)
            visible=set(map(int,hits))
            for i in chosen:
                map_rows.append(dict(surface_id=int(i),raw_xyz=self.frozen.map['centers'][i].tolist(),local_xyz=self.map_local[i].tolist(),
                    local_obb=self.map_obb[i].tolist(),tag=self.T.tag(fi),raw_tag=self.T.tag(fi,False),visible=int(i) in visible))
            ix=np.linspace(0,len(self.support_local)-1,min(600,len(self.support_local)),dtype=int)
            global_rows=self.frozen.map['support_global'][ix]
            for at,g in zip(ix,global_rows):
                support.append(dict(global_row=int(g),raw_xyz=self.frozen.source.xyz[g].tolist(),local_xyz=self.support_local[at].tolist(),
                    tag=self.T.tag(fi),raw_tag=self.T.tag(fi,False),source_role='FROZEN_M0_SUPPORT'))
        history=[v for v in self.trajectory if v['fi']<=fi]
        return dict(record,current=current,map=map_rows,map_support=support,trajectory=history,
            transform=self.T.artifact,display=dict(sample_rows=len(selected),full_rows=len(p),
                map_surfaces=len(map_rows),full_map_surfaces=len(self.map_local),support_sample=len(support),
                full_support_rows=len(self.support_local),sampling='DISPLAY_ONLY; complete computation persisted for all 780 frames'),
            map_available_after_fi=self.map_meta['available_after_fi'],map_first_display_fi=self.map_meta['first_display_fi'])

    def row(self,fi,row):
        _,_,rows,_,p=self.frozen.frame(fi)
        if not 0<=row<len(p):raise ValueError('Row outside frame')
        if sha(self.path/('%04d.npy'%fi))!=self.hashes['%04d.npy'%fi]:raise ValueError('Output frame drift')
        validate_record_binding(self.T,load(self.path/('%04d.json'%fi)),fi,self.frozen.source.binding)
        q=np.load(self.path/('%04d.npy'%fi),mmap_mode='r',allow_pickle=False)
        raw=self.frozen.source.raw_row(fi,row)
        return dict(source_payload(self.T,raw,q[row]),valid=bool(rows['flags'][row]&1),candidate_id=int(rows['candidate'][row]),
            plane_signed_distance_m=float(q[row,2]) if rows['flags'][row]&1 else None,
            opaque_tail='bytes 12..27 NOT_INTERPRETED',source_sha256=self.frozen.source.binding,
            state='CANDIDATE_PLANE_PREVIEW',mode='OFFLINE_REVIEW')

    def surface(self,fi,surface,start,count):
        _,r,_,_,_=self.frozen.frame(fi)
        if not r['candidate_map_exists']:raise ValueError('Map unavailable at this frame')
        m=self.frozen.map
        if not 0<=surface<len(self.map_local) or not 0<=start or not 1<=count<=100:raise ValueError('Invalid surface/page')
        a,b=map(int,m['indptr'][surface:surface+2]);end=min(a+start+count,b);begin=min(a+start,b)
        offsets=np.array([f['offset_points'] for f in self.frozen.source.frames]);support=[]
        for at in range(begin,end):
            g=int(m['support_global'][at]);srcfi=int(np.searchsorted(offsets,g,side='right')-1)
            raw=self.frozen.source.raw_row(srcfi,g-int(offsets[srcfi]))
            support.append(source_payload(self.T,raw,self.support_local[at]))
        return dict(surface_id=surface,tag=self.T.tag(fi),raw_tag=self.T.tag(fi,False),
            raw_xyz=m['centers'][surface].tolist(),local_xyz=self.map_local[surface].tolist(),
            obb_corners=self.map_obb[surface].tolist(),support_count=b-a,support=support,
            next_start=start+len(support) if end<b else None,
            source_sha256=self.frozen.source.binding,map_id=load(self.path/('%04d.json'%fi))['map_id'],
            historical_map_id=r['map_id'],
            operation='FROZEN_M0_TRANSFORM; not rebuilt in local coordinates')


class Handler(BaseHTTPRequestHandler):
    def send(self,code,value,kind='application/json; charset=utf-8'):
        if not isinstance(value,bytes):value=json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf8')
        self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(value)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(value)
    def do_GET(self):
        u=urlparse(self.path);q=parse_qs(u.query);p=self.server.preview
        try:
            if u.path in ['/','/app.js']:
                name='index.html' if u.path=='/' else 'app.js'
                return self.send(200,(HERE/name).read_bytes(),'text/html; charset=utf-8' if name.endswith('html') else 'text/javascript; charset=utf-8')
            p.request_version(q)
            if u.path=='/api/catalog':return self.send(200,dict(frames=780,cases=p.protocol['browser_frames'],transform=p.T.artifact,source=p.protocol['source']))
            fi=int(q.get('fi',['-1'])[0])
            if u.path=='/api/frame':return self.send(200,p.frame(fi))
            if u.path=='/api/source':return self.send(200,p.row(fi,int(q['row'][0])))
            if u.path=='/api/surface':return self.send(200,p.surface(fi,int(q['id'][0]),int(q.get('start',['0'])[0]),int(q.get('count',['10'])[0])))
            return self.send(404,dict(error='Unknown endpoint'))
        except (ValueError,KeyError,IndexError,OSError) as e:return self.send(400,dict(error=str(e)))
    def do_POST(self):self.send(405,dict(error='Read-only offline review'))
    def log_message(self,*args):pass


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=0);ap.add_argument('--service-record',default='SERVICE.json');ap.add_argument('--run',default='full_final');a=ap.parse_args()
    service=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);service.preview=Preview(a.run)
    write(OUT/a.service_record,dict(pid=os.getpid(),address=service.server_address,argv=sys.argv,
        scope='loopback GET-only candidate review',transform_id=service.preview.T.id,run=a.run,
        code_sha256={p.name:sha(p) for p in HERE.iterdir() if p.is_file()}))
    print('http://127.0.0.1:%d/'%service.server_port,flush=True);service.serve_forever()
