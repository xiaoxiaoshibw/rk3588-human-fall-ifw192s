"""S4 read-only review server: contact bands, per-frame decomposition, tail reasons, point lookup."""
import argparse
import base64
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s4core as C

HERE = Path(__file__).resolve().parent
CONTACT, NEAR = 0.10, 0.30


def b64(a, dtype):
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode()


class Data:
    def __init__(self):
        self.protocol = C.load(C.OUT / 'PROTOCOL_V1.json')
        self.tail = C.load(C.OUT / 'TAIL_DECOMPOSITION.json')
        self.f430 = C.load(C.OUT / 'F430_DECOMPOSITION.json')
        self.abcd = C.load(C.OUT / 'ABCD.json')
        self.contact = C.load(C.OUT / 'CONTACT_DEFINITION.json')
        self.summary = C.load(C.OUT / 'SUMMARY.json')
        self.art = C.load(C.S3 / 'TRANSFORM/TRANSFORM_S3.json')
        self.qual = C.load(C.S3 / 'TRANSFORM/TRANSFORM_QUALIFICATION.json')
        self.m0 = C.load(C.S3 / 'M0/M0.json')
        X = C.r04_transform()
        self.T = X.Transform(self.art)
        self.src, self.times = C.load_source()
        self.recs = [json.loads(l) for l in (C.OUT / 'RUN/frames.jsonl').read_text(encoding='utf8').splitlines()]
        self.lock = threading.Lock()
        self.cache = {}

    def frame(self, fi):
        if not 0 <= fi < len(self.recs):
            raise ValueError('fi range')
        with self.lock:
            if fi in self.cache:
                return self.cache[fi]
        f = self.src.frame(fi)
        local = self.T.points(f['xyz'], self.T.tag(fi, False), fi, source_validity=True)
        ok = np.isfinite(local).all(axis=1) & np.any(f['xyz'] != 0, axis=1)
        ledger = np.load(C.OUT / 'RUN/frames' / ('%04d.npz' % fi))['current']
        z = np.abs(local[:, 2])
        band = np.zeros(len(z), dtype=np.uint8)
        band[(z <= CONTACT)] = 1
        band[(z > CONTACT) & (z <= NEAR)] = 2
        band[(z > NEAR)] = 3
        band[~ok] = 0
        rows = np.flatnonzero(ok)
        keep = rows[::max(1, len(rows) // 9000)][:9000].astype('i4')
        rec = self.recs[fi]
        return dict(fi=fi, time_s=float(self.times[fi]), rows=int(len(f['xyz'])), valid=int(ok.sum()),
                    invalid=int((~ok).sum()), record=rec,
                    raw=b64(f['xyz'][keep], '<f4'), local=b64(local[keep], '<f4'),
                    band=b64(band[keep], 'u1'), rows_b64=b64(keep, '<i4'),
                    labels=rec['labels'], decomp=rec['decomp'], bands=rec['bands'],
                    transform_id=self.T.id,
                    state='GEOMETRY_VALIDATED_LOCAL' if fi >= 271 else ('RAW' if fi <= 192 else 'CANDIDATE_PLANE_PREVIEW'))

    def point(self, fi, row):
        f = self.src.frame(fi)
        p = f['xyz']
        if not 0 <= row < len(p):
            raise ValueError('row range')
        raw = self.src.buffer[(f['offset'] + row) * 28:(f['offset'] + row + 1) * 28].tobytes()
        local = self.T.points(p[row:row + 1], self.T.tag(fi, False), fi, source_validity=True)[0]
        ledger = np.load(C.OUT / 'RUN/frames' / ('%04d.npz' % fi))['current']
        ok = bool(np.isfinite(p[row]).all() and np.any(p[row] != 0))
        z = abs(float(local[2])) if ok else None
        band = 'INVALID' if not ok else ('CONTACT' if z <= CONTACT else 'NEAR_GROUND' if z <= NEAR else 'CLEAR')
        return dict(fi=fi, source_row=int(row), global_row=int(f['offset'] + row),
                    byte_offset=int((f['offset'] + row) * 28), raw28_hex=raw.hex(),
                    raw_xyz=[float(x) if np.isfinite(x) else None for x in p[row]],
                    local_xyz=[float(x) for x in local], valid=ok, band=band, z_local=z,
                    label=int(ledger['label'][row]), surface=int(ledger['surface'][row]),
                    candidate=int(ledger['candidate'][row]),
                    source_sha256=self.src.binding, transform_id=self.T.id,
                    note='band is an interpretation label only: no deletion, no XYZ change, no physical height')


DATA = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def json(self, obj, code=200):
        self.send(code, json.dumps(obj, ensure_ascii=False, allow_nan=False).encode('utf8'))

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ('/', '/index.html'):
                return self.send(200, (HERE / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            if u.path == '/app.js':
                return self.send(200, (HERE / 'app.js').read_bytes(), 'application/javascript; charset=utf-8')
            if u.path == '/api/meta':
                d = DATA
                return self.json(dict(
                    item=C.ITEM, state='S4 DIAGNOSTIC', warning='S4 只做诊断与接触带标签：不改阈值、不重拟合平面、不是人体效果结论',
                    transform_id=d.T.id, geometry='inherited GEOMETRY_VALIDATED_LOCAL from fi 271',
                    contact=d.contact, tail=d.tail['summary'], tail_zero=d.tail['zero_candidate_frames'],
                    tail_reasons=d.tail['zero_candidate_reasons'],
                    f430=d.f430['summary'], abcd=d.abcd['definition'],
                    m0=dict(map_id=d.m0['primary']['map_id'], surfaces=d.m0['primary']['surfaces'],
                            eligible=d.m0['primary']['eligible_surfaces'], support=d.m0['primary']['support_rows']),
                    summary=dict(totals=d.summary['totals'], seconds=d.summary['seconds'],
                                 tail_zero=d.summary['tail_zero_frames'])))
            if u.path == '/api/frame':
                return self.json(DATA.frame(int(q['fi'])))
            if u.path == '/api/point':
                return self.json(DATA.point(int(q['fi']), int(q['row'])))
            if u.path == '/api/firstinvalid':
                fi = int(q['fi'])
                f = DATA.src.frame(fi)
                ok = np.isfinite(f['xyz']).all(axis=1) & np.any(f['xyz'] != 0, axis=1)
                rows = np.flatnonzero(~ok)
                return self.json(dict(fi=fi, row=int(rows[0]) if len(rows) else None, invalid=int(len(rows))))
            if u.path == '/api/health':
                return self.json(dict(ok=True, frames=len(DATA.times)))
            self.send(404, b'not found', 'text/plain')
        except Exception as e:
            self.json(dict(error=type(e).__name__, message=str(e)), 400)


def main():
    global DATA
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=0)
    a = ap.parse_args()
    DATA = Data()
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    print(json.dumps(dict(url='http://127.0.0.1:%d/' % srv.server_address[1],
                          pid=__import__('os').getpid(), tail_zero=DATA.tail['zero_candidate_frames'])), flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
