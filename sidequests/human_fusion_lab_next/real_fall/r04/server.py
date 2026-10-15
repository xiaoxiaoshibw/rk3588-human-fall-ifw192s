"""Local full-process evidence player; source and derivatives remain read-only."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import sys
from urllib.parse import urlsplit,parse_qs
import numpy as np
from paths import ROOT,OUT
sys.path.insert(0,str(ROOT/'sidequests/human_fusion_lab_next/real_fall/r01'))
from prepare import frame_xyz,sha

HERE=ROOT/'sidequests/human_fusion_lab_next/real_fall/r04'
SID='cap_20261013_094333';REF='cap_20261013_131958'
DATA={}
for sid in (SID,REF):
    manifest=json.loads((OUT/(sid+'_foreground.json')).read_text(encoding='utf8'))
    trackfile=OUT/('process.json' if sid==SID else sid+'_tracking.json')
    track=json.loads(trackfile.read_text(encoding='utf8'))
    directory=ROOT/'captures/remote'/sid
    for file,key in [('meta.json','meta_sha256'),('points.bin','bin_sha256')]:
        if sha(directory/file)!=manifest['source'][key]:raise ValueError('source SHA mismatch')
    for suffix,key in [('_foreground.bin','data_sha256'),('_source_rows.bin','rows_sha256')]:
        if sha(OUT/(sid+suffix))!=manifest[key]:raise ValueError('derived SHA mismatch')
    DATA[sid]={'manifest':manifest,'track':track,'directory':directory,
               'meta':json.loads((directory/'meta.json').read_text(encoding='utf8')),
               'source_rows':np.memmap(OUT/(sid+'_source_rows.bin'),dtype='<u4',mode='r'),
               'fg':np.memmap(OUT/(sid+'_foreground.bin'),dtype='<f4',mode='r').reshape(-1,4)}


class Handler(BaseHTTPRequestHandler):
    def send(self,data,mime='application/json; charset=utf-8',code=200):
        if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf8')
        self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)

    def do_GET(self):
        u=urlsplit(self.path)
        if u.path=='/favicon.ico':return self.send(b'','image/x-icon',204)
        if u.path=='/':return self.send((HERE/'index.html').read_bytes(),'text/html; charset=utf-8')
        if u.path=='/app.js':return self.send((HERE/'app.js').read_bytes(),'application/javascript')
        if u.path in ('/three.min.js','/OrbitControls.js'):
            return self.send((ROOT/'pc_apps/human_replay/vendor'/u.path[1:]).read_bytes(),'application/javascript')
        if u.path=='/api/info':
            return self.send({'sessions':{sid:{'frames':len(d['track']['rows']),'times':[r['t'] for r in d['track']['rows']],'events':d['track']['events'],'source':d['manifest']['source']} for sid,d in DATA.items()},
                              'background':DATA[SID]['manifest']['background'],'skeleton_slots':DATA[SID]['track']['skeleton_slots'],
                              'limits':['visual initialization; frames 0..4 are offline warmup','point-supported regions, anatomical joints unverified','active lying indistinguishable','startup residual outside protected .55m seed may absorb unreviewed human points','empty result is self-reference limited']})
        if u.path in ('/api/frame','/api/support'):
            try:
                q=parse_qs(u.query,strict_parsing=True)
                if not {'sid','i'}.issubset(q) or set(q)-{'sid','i','mode','key'} or any(len(v)!=1 for v in q.values()):raise ValueError('query invalid')
                sid=q['sid'][0];i=int(q['i'][0]);d=DATA[sid]
                if not 0<=i<len(d['track']['rows']):raise ValueError('frame out of range')
                row=d['track']['rows'][i];f=d['manifest']['frames'][i]
                fg=d['fg'][f['offset']:f['offset']+f['count'],:3];target=fg[row['source_fg_indices']]
                if u.path=='/api/support':
                    key=q.get('key',[''])[0];node=row.get('skeleton',{}).get('nodes',{}).get(key)
                    if node is None:raise ValueError('node invalid')
                    source_ids=d['source_rows'][f['offset']:f['offset']+f['count']][row['source_fg_indices']]
                    support_map={int(source):point for source,point in zip(source_ids,target)}
                    return self.send({'key':key,'points':[support_map[source].tolist() for source in node['support_rows'] if source in support_map],'measured':node['valid']})
                display_row={k:v for k,v in row.items() if k!='source_fg_indices'}
                if row.get('skeleton'):
                    display_row['skeleton']={**row['skeleton'],'nodes':{
                        key:{k:v for k,v in node.items() if k not in ('support_rows','xyz_local')}
                        for key,node in row['skeleton']['nodes'].items()}}
                mode=q.get('mode',['fg'])[0]
                if mode not in ('fg','room'):raise ValueError('mode invalid')
                if mode=='fg':
                    return self.send({'sid':sid,'row':display_row,'room':[],'fg':np.round(fg.astype('f8'),4).tolist(),'target':np.round(target.astype('f8'),4).tolist()})
                raw=frame_xyz(d['directory'],d['meta'],i);rt=d['manifest']['transform']
                lv=raw@np.array(rt['R']).T+np.array(rt['t'])
                if rt.get('reference_alignment'):
                    a=rt['reference_alignment'];lv=lv@np.array(a['R']).reshape(3,3).T+np.array(a['t'])
                keep=(lv[:,0]>-.5)&(lv[:,0]<6)&(abs(lv[:,1])<3)&(lv[:,2]>-.1)&(lv[:,2]<2.6)
                return self.send({'sid':sid,'row':display_row,
                                  'room':np.round(lv[keep][::3],4).tolist(),'fg':np.round(fg.astype('f8'),4).tolist(),'target':np.round(target.astype('f8'),4).tolist()})
            except (ValueError,KeyError) as e:return self.send({'error':str(e)},code=400)
        return self.send({'error':'not found'},code=404)

    def log_message(self,*args):pass


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8934);args=parser.parse_args()
    print('Full process http://127.0.0.1:%d/'%args.port,flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
