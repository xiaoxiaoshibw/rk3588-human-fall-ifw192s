"""Loopback viewer; inputs read-only, human reviews append only under this item."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import argparse
import hashlib
import json
from pathlib import Path
import threading
import uuid
import numpy as np
from prototype import HERE, ROOT, E, read, sha, write, mapped, paths, transform, check_hashes, validate_meta

class Store:
    def __init__(self, target):
        self.target = target.resolve(); self.manifest_sha = sha(E/'RUN_MANIFEST.json'); self.m = read(E/'RUN_MANIFEST.json')
        self.index_sha = sha(target/'INDEX.json'); self.index = read(target/'INDEX.json')
        if self.m.get('schema') != 'local-indoor/1' or self.index['manifest_sha256'] != self.manifest_sha:
            raise ValueError('Invalid run/index/schema')
        # Numeric prepare snapshot stays immutable. Later viewer revisions bind separately.
        self.delivery_path = E/'DELIVERY_V4.json'
        self.delivery_sha = sha(self.delivery_path)
        delivery = read(self.delivery_path)
        if delivery['manifest_sha256'] != self.manifest_sha or delivery['index_sha256'] != self.index_sha:
            raise ValueError('Viewer/numeric delivery binding drift')
        check_hashes(delivery['source_sha256']); check_hashes(self.m['assets'])
        self.delivery_sources = delivery['source_sha256']
        self.runtime_signatures = {p:self.signature(Path(p)) for p in self.delivery_sources}
        frozen = read(E/'BASELINE_BEFORE.json')['assets']
        self.served_hashes = {**frozen, **self.delivery_sources}
        if sha(HERE/'prototype.py') != self.m['code'][str(HERE/'prototype.py')]:
            raise ValueError('Numeric execution source drift')
        self.source_signatures = {}; self.raw = {}; self.lock = threading.Lock()
        for sid, s in self.m['sources'].items():
            meta, q, intensity = mapped(sid, s['sha256']); self.raw[sid] = (meta, q)
            for p in paths(sid): self.source_signatures[str(p)] = self.signature(p)
        self.asset_signatures = {p:self.signature(Path(p)) for p in self.m['assets']}

    @staticmethod
    def signature(p):
        stat = p.stat(); return (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)

    def check(self, sid, fi):
        if sid not in self.m['sources'] or type(fi) is not int or fi not in self.m['sources'][sid]['available']:
            raise ValueError('Unapproved session/frame (FIT/CAL excluded)')
        if sha(E/'RUN_MANIFEST.json') != self.manifest_sha or sha(self.target/'INDEX.json') != self.index_sha:
            raise ValueError('Same-ID run/index drift')
        if sha(self.delivery_path) != self.delivery_sha:
            raise ValueError('Viewer delivery content drift')
        for p, sig in self.runtime_signatures.items():
            if self.signature(Path(p)) != sig:
                raise ValueError('Viewer/runtime source changed: '+p)
        for p in paths(sid):
            if self.signature(p) != self.source_signatures[str(p)]:
                raise ValueError('Source changed/missing: restart with a new verified run')
        for p, sig in self.asset_signatures.items():
            if self.signature(Path(p)) != sig: raise ValueError('Background/transform changed')
        return self.m['sources'][sid]

    def check_served(self, path):
        expected = self.served_hashes.get(str(path))
        if expected is None or sha(path) != expected:
            raise ValueError('Served source SHA drift')

    def catalog(self):
        records = self.review_records()
        queue = read(E/'REVIEW_QUEUE.json')
        queue['creation_snapshot_reviews'] = queue.pop('real_human_reviews', 0)
        queue['real_human_reviews'] = len({(r['sid'], r['fi']) for r in records})
        queue['human_candidate_assertions'] = len(records)
        return dict(manifest=self.m, manifest_sha256=self.manifest_sha, queue=queue,
            ledger=read(self.target/'FRAME_LEDGER.json'), human_reviews=records, viewer_delivery_sha256=self.delivery_sha)

    def artifact(self, relative):
        if relative not in self.index['artifacts']: raise ValueError('Unbound artifact')
        p = self.target/relative
        if sha(p) != self.index['artifacts'][relative]: raise ValueError('Same-ID artifact drift')
        return p

    def frame(self, sid, fi):
        source = self.check(sid, fi)
        row = read(self.artifact(sid+'/'+str(fi)+'.json'))
        if row['sid'] != sid or row['fi'] != fi or row['source_sha256'] != source['sha256'] or row['run'] != self.m['run_id']:
            raise ValueError('Frame binding drift')
        with np.load(self.artifact(sid+'/'+str(fi)+'.npz')) as d:
            code, labels = d['terminal'].copy(), d['cluster'].copy()
        meta, raw = self.raw[sid]; f = meta['frames'][fi]
        q = raw[f['offset_points']:f['offset_points']+f['count_points']].copy()
        with paths(sid)[1].open('rb') as stream:
            stream.seek(f['offset_points']*28); digest=hashlib.sha256(stream.read(f['count_points']*28)).hexdigest()
        if digest != row['frame_bytes_sha256']: raise ValueError('Frame source bytes drift')
        reg = None if sid == self.m['empty_sid'] else read(Path(self.m['cfg']['background_experiment'])/(sid+'_registration.json'))
        p = transform(q, reg)
        if len(code) != len(q) or len(labels) != len(q): raise ValueError('Source row mismatch')
        self.check(sid, fi)
        return row, q, p, code, labels

    def review_records(self):
        records = [read(p) for p in sorted((E/'human_reviews').glob('*.json'))]
        return records

    def append_review(self, record):
        # This endpoint records the named user's explicit UI submission. Never called by AI tests on real data.
        if record.get('human_attestation') is not True or record.get('schema') != 'local-human-review/1':
            raise ValueError('Explicit real human attestation/schema required')
        for k in ['reviewer', 'date', 'basis', 'label_version', 'scope']:
            if not isinstance(record.get(k), str) or not record[k].strip(): raise ValueError('Missing '+k)
        datetime.fromisoformat(record['date'])
        for k in ['occlusion', 'ambiguity', 'missing_labels', 'frame_complete']:
            if k not in record or (record[k] is not None and type(record[k]) is not bool):
                raise ValueError('Explicit bool or null=UNKNOWN flags required')
        sid, fi = record.get('sid'), record.get('fi')
        row, _, _, _, _ = self.frame(sid, fi)
        if record.get('source_sha256') != row['source_sha256']: raise ValueError('Review source drift')
        if record.get('granularity') != 'CANDIDATE_LEVEL' or record.get('class') not in ['HUMAN_PRESENT', 'HUMAN_ONLY', 'NONHUMAN', 'MIXED', 'FRAGMENT', 'UNKNOWN']:
            raise ValueError('Unsupported label granularity/class')
        if type(record.get('candidate_id')) is not int or record['candidate_id'] not in [c['id'] for c in row['candidates']]:
            raise ValueError('Candidate missing')
        candidate = next(c for c in row['candidates'] if c['id'] == record['candidate_id'])
        record = dict(record, candidate_member_sha256=candidate['member_sha256'], run=self.m['run_id'],
            manifest_sha256=self.manifest_sha, saved_at=datetime.now().astimezone().isoformat(),
            qualification='PENDING_QUALITY_AUDIT_NOT_POINT_GT', revision_id=uuid.uuid4().hex)
        with self.lock: write(E/'human_reviews'/(record['revision_id']+'.json'), record)
        return record

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def send(self, value, status=200, mime='application/json; charset=utf-8'):
        data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status); self.send_header('Content-Type', mime); self.send_header('Content-Length', str(len(data)))
        try:
            self.send_header('Cache-Control', 'no-store'); self.send_header('X-Content-Type-Options', 'nosniff'); self.end_headers(); self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass  # A superseded browser request is intentionally aborted.

    def do_GET(self):
        try:
            uri=urlparse(self.path); args=parse_qs(uri.query); store=self.server.store
            if uri.path in ['/', '/app.js', '/state.js', '/three.min.js', '/OrbitControls.js']:
                name={'/':'index.html'}.get(uri.path, uri.path[1:]); p=(ROOT/'webui'/name) if name in ['three.min.js','OrbitControls.js'] else HERE/name
                store.check_served(p)
                return self.send(p.read_bytes(), mime='text/html; charset=utf-8' if name.endswith('.html') else 'application/javascript; charset=utf-8')
            if uri.path == '/api/catalog':
                return self.send(store.catalog())
            if uri.path in ['/api/frame', '/api/members']:
                if set(args) - {'sid', 'fi', 'candidate'}: raise ValueError('Unknown query')
                sid=args['sid'][0]; text=args['fi'][0]
                if not text.isdecimal(): raise ValueError('Non-integer frame')
                fi=int(text); row,q,p,code,labels=store.frame(sid, fi)
                if uri.path == '/api/members':
                    cid=int(args['candidate'][0])
                    if cid not in [c['id'] for c in row['candidates']]: raise ValueError('Unknown candidate')
                    ids=np.flatnonzero(labels == cid)
                    return self.send(dict(sid=sid, fi=fi, candidate=cid, source_rows=ids.tolist(),
                        session_rows=(ids+row['source_frame']['offset_points']).tolist(), raw_xyz=q[ids].tolist(), xyz=p[ids].tolist(), source_sha256=row['source_sha256']))
                finite=np.flatnonzero(np.isfinite(p).all(1))
                return self.send(dict(row=row, source_rows=finite.tolist(), xyz=p[finite].tolist(), terminal=code[finite].tolist(), cluster=labels[finite].tolist(),
                    nonfinite_display_excluded=len(q)-len(finite), manifest_sha256=store.manifest_sha,
                    reviews=[r for r in store.review_records() if r['sid']==sid and r['fi']==fi]))
            return self.send(dict(error='NOT_FOUND', clear_results=True), 404)
        except (ValueError, KeyError, FileNotFoundError, IndexError, OSError) as exc:
            self.send(dict(error=str(exc), clear_results=True), 409)

    def do_POST(self):
        try:
            if self.path != '/api/human-review': raise ValueError('Unknown endpoint')
            origin=self.headers.get('Origin')
            if origin != 'http://'+self.headers.get('Host',''): raise ValueError('Local UI origin required')
            length=int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 32768: raise ValueError('Invalid body size')
            record=json.loads(self.rfile.read(length)); self.send(self.server.store.append_review(record))
        except (ValueError, KeyError, FileNotFoundError, TypeError) as exc:
            self.send(dict(error=str(exc), clear_results=True), 409)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--target',type=Path,default=E/'baseline_r1'); parser.add_argument('--port',type=int,default=0)
    args=parser.parse_args(); store=Store(args.target)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler); server.store=store
    url='http://127.0.0.1:'+str(server.server_port)+'/'
    print('LOCAL_INDOOR_URL='+url,flush=True)
    server.serve_forever()
