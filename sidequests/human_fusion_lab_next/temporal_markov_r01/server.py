"""Loopback-only research replay; no routes to devices or production services."""
import argparse
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import numpy as np
from experiment import HERE, ROOT, OLD, EVIDENCE, read, sha
from temporal import sequence


def serve(run, port):
    catalog = read(run/'catalog.json')
    sessions = {s['sid']:read(run/s['sid']/'features.json') for s in catalog}
    cfg = read(run/'FROZEN_CONFIG.json')
    bindings = read(run/'INPUT_MANIFEST.json')['bindings']
    allowed = {'ema_tau_s':(.05, 2), 'low_hold_s':(.1, 3), 'event_probability':(.1, .99)}
    assets = {'/':HERE/'index.html', '/app.js':HERE/'app.js', '/three.min.js':ROOT/'webui/three.min.js', '/OrbitControls.js':ROOT/'webui/OrbitControls.js'}

    class Handler(BaseHTTPRequestHandler):
        def reply(self, value, status=200):
            body=json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf8')
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

        def do_GET(self):
            u=urlparse(self.path)
            try:
                if u.path in assets:
                    p=assets[u.path];body=p.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(p))[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
                if u.path=='/api/catalog':
                    self.reply(dict(sessions=catalog, config=cfg, mode='RULE_INITIALIZED_NO_GT'));return
                q=parse_qs(u.query);sid=q.get('sid',[''])[0]
                if sid not in sessions:
                    self.reply({'error':'Unknown session'},404);return
                if u.path=='/api/session':
                    rows=sessions[sid]
                    self.reply(dict(rows=rows,predictions=read(run/sid/'predictions.json')));return
                if u.path=='/api/cloud':
                    fi=int(q['fi'][0]);r=next(r for r in sessions[sid] if r['fi']==fi)
                    p=OLD/'primary/common'/sid/('{:04d}.npz'.format(fi))
                    if sha(p)!=bindings[p.relative_to(ROOT).as_posix()]:
                        raise ValueError('Cloud SHA drift')
                    with np.load(p) as a:
                        cloud=a['corrected'];valid=np.isfinite(cloud).all(1)&(np.linalg.norm(cloud,axis=1)<15)
                        ids=np.flatnonzero(valid);ids=ids[np.linspace(0,len(ids)-1,min(len(ids),7000),dtype=int)] if len(ids) else ids
                        self.reply(dict(fi=fi,sid=sid,points=cloud[ids].tolist(),candidate=r['points'],source_sha256=r['source_sha256']))
                    return
                self.reply({'error':'Not found'},404)
            except (ValueError,KeyError,StopIteration,IndexError) as e:
                self.reply({'error':str(e)},400)

        def do_POST(self):
            try:
                if self.headers.get('Origin') and self.headers['Origin']!='http://127.0.0.1:'+str(self.server.server_port):
                    self.reply({'error':'Origin rejected'},403);return
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<10000:raise ValueError('Invalid request size')
                r=json.loads(self.rfile.read(size));sid=r['sid']
                if sid not in sessions:raise ValueError('Unknown session')
                if self.path=='/api/infer':
                    c=json.loads(json.dumps(cfg));params=r.get('params',{})
                    for k,v in params.items():
                        if k not in allowed or not isinstance(v,(int,float)) or not np.isfinite(v) or not allowed[k][0]<=v<=allowed[k][1]:raise ValueError('Invalid parameter')
                        c[k]=v
                    start=r.get('start',0)
                    if type(start)!=int or not 0<=start<len(sessions[sid]):raise ValueError('Invalid start')
                    self.reply(dict(predictions=sequence(sessions[sid],c,start),start=start,params=params,mode='EXPLORATORY_NOT_FROZEN_RESULT'));return
                if self.path=='/api/review':
                    fi=r['fi'];row=next(x for x in sessions[sid] if x['fi']==fi)
                    if type(fi)!=int or type(r.get('reviewer'))!=str or not r['reviewer'].strip() or r.get('posture') not in ['STANDING','SITTING','CROUCHING','LYING','TRANSITION','UNKNOWN'] or r.get('event') not in ['NONE','CONTROLLED_LOW','POSSIBLE_REAL_FALL','UNKNOWN']:raise ValueError('Review needs named human, posture and event')
                    from uuid import uuid4
                    directory=EVIDENCE/'human_reviews';directory.mkdir(exist_ok=True)
                    record=dict(sid=sid,fi=fi,source_sha256=row['source_sha256'],reviewer=r['reviewer'][:120],posture=r['posture'],event=r['event'],source='human',status='SINGLE_REVIEW_NOT_TRAINING_GATE',selected_indices_sha256=row['selected_indices_sha256'])
                    with (directory/(uuid4().hex+'.json')).open('x',encoding='utf8') as f:json.dump(record,f,ensure_ascii=False,allow_nan=False)
                    self.reply(record);return
                self.reply({'error':'Not found'},404)
            except (ValueError,KeyError,StopIteration,TypeError) as e:self.reply({'error':str(e)},400)

    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print('HFUS Markov Demo http://127.0.0.1:'+str(server.server_port),flush=True)
    server.serve_forever()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8947);p.add_argument('--run',type=Path,default=EVIDENCE/'run_r3');args=p.parse_args();serve(args.run,args.port)
