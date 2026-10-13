"""Local read-only player for the new real-session artifacts."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import numpy as np
from prepare import ROOT, OUT, frame_xyz, sha

HERE=Path(__file__).resolve().parent
SID='cap_20261013_094333'
TRACK=json.loads((OUT/'tracking_v1.json').read_text(encoding='utf8'))
MANIFEST=json.loads((OUT/(SID+'_foreground.json')).read_text(encoding='utf8'))
DIRECTORY=ROOT/'captures/remote'/SID
META=json.loads((DIRECTORY/'meta.json').read_text(encoding='utf8'))
FG=np.memmap(OUT/(SID+'_foreground.bin'),dtype='<f4',mode='r').reshape(-1,4)
for file,key in [('meta.json','meta_sha256'),('points.bin','bin_sha256')]:
    if sha(DIRECTORY/file)!=MANIFEST['source'][key]:raise ValueError('source SHA mismatch')
for file,key in [(SID+'_foreground.bin','data_sha256'),(SID+'_source_rows.bin','rows_sha256')]:
    if sha(OUT/file)!=MANIFEST[key]:raise ValueError('derived SHA mismatch')


class Handler(BaseHTTPRequestHandler):
    def send(self,data,mime='application/json; charset=utf-8',code=200):
        if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf8')
        self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)

    def do_GET(self):
        u=urlsplit(self.path)
        if u.path=='/favicon.ico':return self.send(b'', 'image/x-icon', code=204)
        if u.path=='/':return self.send((HERE/'index.html').read_bytes(),'text/html; charset=utf-8')
        if u.path=='/app.js':return self.send((HERE/'app.js').read_bytes(),'application/javascript')
        if u.path in ('/three.min.js','/OrbitControls.js'):
            return self.send((ROOT/'pc_apps/human_replay/vendor'/u.path[1:]).read_bytes(),'application/javascript')
        if u.path=='/api/info':return self.send({'sid':SID,'frames':len(TRACK['rows']),'events':TRACK['events'],
                                                'limits':TRACK['limits'],'config':TRACK['config'],'background':MANIFEST['background'],
                                                'source':MANIFEST['source'],'initialization':TRACK['initialization']})
        if u.path=='/api/frame':
            try:
                args=parse_qs(u.query,strict_parsing=True)
                if set(args)!={'i'} or len(args['i'])!=1:raise ValueError('frame query required')
                i=int(args['i'][0])
                if not 0<=i<len(TRACK['rows']):raise ValueError('frame out of range')
                row=TRACK['rows'][i];f=MANIFEST['frames'][i]
                fg=FG[f['offset']:f['offset']+f['count'],:3]
                target=fg[row['source_fg_indices']]
                raw=frame_xyz(DIRECTORY,META,i)
                lv=raw@np.array(MANIFEST['transform']['R']).T+np.array(MANIFEST['transform']['t'])
                keep=(lv[:,0]>-.5)&(lv[:,0]<6)&(abs(lv[:,1])<3)&(lv[:,2]>-.1)&(lv[:,2]<2.6)
                room=lv[keep][::3]  # display-only decimation; target and analysis remain complete
                return self.send({'row':{k:v for k,v in row.items() if k!='source_fg_indices'},
                                  'room':np.round(room,4).tolist(),'fg':np.round(fg,4).tolist(),
                                  'target':np.round(target,4).tolist()})
            except (ValueError,KeyError) as e:return self.send({'error':str(e)},code=400)
        return self.send({'error':'not found'},code=404)

    def log_message(self,*args):pass


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8929);args=parser.parse_args()
    print('REAL FALL offline http://127.0.0.1:%d/'%args.port,flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
