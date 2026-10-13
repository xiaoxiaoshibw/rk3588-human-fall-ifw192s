"""Read-only local evidence viewer. No inference on seek; all rows are saved sequential runs."""
import argparse
import hashlib
import json
import re
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent
R02=ROOT/'docs/human_capture/evidence/2026-10-11_hfus_d05_r2'
R03=ROOT/'docs/human_capture/evidence/2026-10-12_hfus_d05_r3'
OUT=ROOT/'docs/human_capture/evidence/2026-10-12_hfus_d05_r4'

def reportpath(v):return OUT/'runs/fast/R04_fast_SUMMARY.json' if v=='fast' else R03/'runs/gate/R03_gate_SUMMARY.json' if v=='gate' else R02/'runs/full'/v/f'R02_{v}_SUMMARY.json'
def ledgerpath(v,sid):return OUT/'runs/fast'/f'R04_fast_{sid}.jsonl' if v=='fast' else R03/'runs/gate'/f'R03_gate_{sid}.jsonl' if v=='gate' else R02/'runs/full'/v/f'R02_{v}_{sid}.jsonl'
FROZEN=ROOT/'docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/base'

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

@lru_cache(maxsize=40)
def index(p):
    offsets=[]
    with p.open('rb') as f:
        while True:
            offset=f.tell();line=f.readline()
            if not line:break
            offsets.append((offset,len(line)))
    return offsets

@lru_cache(maxsize=9)
def verified(sid, stamp):
    records={}
    tooling_path=sorted(OUT.glob('TOOLING_SOURCES_V*.json'))[-1]
    tooling=load(tooling_path)
    for item in tooling['files']:assert sha(ROOT/item['path'])==item['sha256'],'tooling SHA mismatch'
    for v in ('base','a06','split','gate','fast'):
        p=reportpath(v); report=load(p); s=next(s for s in report['sessions'] if s['sid']==sid)
        for source in report['sources']:assert sha(ROOT/source['path'])==source['sha256'],'source SHA mismatch'
        ledger=Path(s['ledger']['path']);assert sha(ledger)==s['ledger']['sha256'],'ledger SHA mismatch'
        for name in ('meta','points'):assert sha(ROOT/'captures/remote'/sid/('meta.json' if name=='meta' else 'points.bin'))==s['input_sha256'][name],'input SHA mismatch'
        records[v]={'ledger_sha256':s['ledger']['sha256'],'input_sha256':s['input_sha256'],'model_sha256':s['model_sha256'],'frames':s['frames']}
    audit=load(ROOT/'sidequests/human_fusion_lab/results/AUDIT.json');rec=next(r for r in audit['sessions'] if r['sid']==sid)
    assert sha(Path(rec['gt_path']))==rec['gt_sha256'],'GT SHA mismatch'
    assert sha(Path(rec['gt_path']).parent/'manifest.json')==rec['manifest_sha256'],'GT manifest SHA mismatch'
    records['gt']={'sha256':rec['gt_sha256'],'manifest_sha256':rec['manifest_sha256'],'qualification':'INVALID_BINDING' if sid.endswith('180751') else 'PARTIAL_REVIEWED_BOUND'}
    old=next(s for s in load(FROZEN/'D04_base_SUMMARY.json')['sessions'] if s['sid']==sid)
    assert sha(Path(old['ledger']['path']))==old['ledger']['sha256']
    records['frozen']={'ledger_sha256':old['ledger']['sha256']}
    return {'sid':sid,'status':'SHA_VERIFIED','records':records,'tooling_manifest_sha256':sha(tooling_path),'tooling_files':len(tooling['files']),'qualification':'INVALID_BINDING' if sid.endswith('180751') else 'PARTIAL; unannotated UNKNOWN'}

def verification(sid):
    paths=set()
    tooling_path=sorted(OUT.glob('TOOLING_SOURCES_V*.json'))[-1];paths.add(tooling_path)
    paths.update(ROOT/s['path'] for s in load(tooling_path)['files'])
    for v in ('base','a06','split','gate','fast'):
        p=reportpath(v);paths.add(p);report=load(p)
        paths.update(ROOT/s['path'] for s in report['sources'])
        s=next(s for s in report['sessions'] if s['sid']==sid);paths.add(Path(s['ledger']['path']))
    paths.update([ROOT/'captures/remote'/sid/'meta.json',ROOT/'captures/remote'/sid/'points.bin',FROZEN/f'D04_base_{sid}.jsonl',FROZEN/'D04_base_SUMMARY.json'])
    rec=next(r for r in load(ROOT/'sidequests/human_fusion_lab/results/AUDIT.json')['sessions'] if r['sid']==sid);paths.update([Path(rec['gt_path']),Path(rec['gt_path']).parent/'manifest.json'])
    stamp=tuple((str(p),p.stat().st_size,p.stat().st_mtime_ns) for p in sorted(paths))
    return verified(sid,stamp)

def row(p,fi):
    offsets=index(p)
    if not 0<=fi<len(offsets):raise ValueError('frame out of range')
    offset,n=offsets[fi]
    with p.open('rb') as f:f.seek(offset);r=json.loads(f.read(n))
    assert r['frame_index']==fi
    return r

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,body,kind='application/json; charset=utf-8',extra=None,status=200):
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
        for k,v in (extra or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        try:
            u=urlsplit(self.path);q=parse_qs(u.query)
            if u.path=='/':return self.send((HERE/'demo.html').read_bytes(),'text/html; charset=utf-8')
            if u.path=='/three.min.js':return self.send((ROOT/'pc_apps/human_replay/vendor/three.min.js').read_bytes(),'application/javascript')
            if u.path=='/api/sessions':
                j=load(reportpath('base'));return self.send(json.dumps({'sessions':[{'sid':s['sid'],'activity':s['activity'],'frames':s['frames']} for s in j['sessions']],'cases':load(OUT/'CASE_INDEX.json')}).encode())
            sid=q.get('sid',[''])[0]
            if not re.fullmatch(r'cap_20261010_(175227|175429|175553|175804|175943|180235|180337|180557|180751)',sid):raise ValueError('unknown sid')
            if u.path=='/api/verify':return self.send(json.dumps(verification(sid)).encode())
            fi=int(q.get('f',['-1'])[0]);meta=load(ROOT/'captures/remote'/sid/'meta.json')
            if not 0<=fi<len(meta['frames']):raise ValueError('frame out of range')
            if u.path=='/api/frame':
                verification(sid);v=q.get('v',['fast'])[0]
                if v not in ('a06','split','gate','fast'):raise ValueError('variant')
                b=row(FROZEN/f'D04_base_{sid}.jsonl',fi);bs=row(ledgerpath('base',sid),fi);c=row(ledgerpath(v,sid),fi)
                assert b['candidates']==bs['candidates'];b['stages']=bs['stages']
                assert b['timestamp_s']==c['timestamp_s']==meta['frames'][fi]['bag_time_sec']
                body=json.dumps({'base':b,'current':c,'meta':meta['frames'][fi],'reference':load(reportpath('base'))['reference']['coordinate']},separators=(',',':')).encode()
                return self.send(body,extra={'X-Content-SHA256':hashlib.sha256(body).hexdigest()})
            if u.path=='/api/points':
                verification(sid);f=meta['frames'][fi]
                with (ROOT/'captures/remote'/sid/'points.bin').open('rb') as stream:stream.seek(f['offset_points']*28);body=stream.read(f['count_points']*28)
                assert len(body)==f['count_points']*28
                return self.send(body,'application/octet-stream',{'X-Content-SHA256':hashlib.sha256(body).hexdigest()})
            raise ValueError('unknown endpoint')
        except Exception as e:self.send(json.dumps({'error':str(e)}).encode(),status=400)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8915);args=ap.parse_args()
    print(f'R04 Demo http://127.0.0.1:{args.port} read-only saved inference',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
