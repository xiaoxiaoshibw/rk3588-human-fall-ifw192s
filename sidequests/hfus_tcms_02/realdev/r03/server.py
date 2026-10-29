"""Read-only S2 review server: range image + 3D same frame, point/bin reverse lookup."""
import argparse
import base64
import json
import math
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s2core import OUT, ROOT, load, sha, load_source, validity, RAW
import distance

LABEL = 'full_r1'
HERE = Path(__file__).resolve().parent


def b64(a, dtype):
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode()


class Data:
    def __init__(self):
        self.protocol = load(OUT / 'PROTOCOL_V4.json')
        self.cand = load(OUT / LABEL / 'CANDIDATES.json')
        self.dom = load(OUT / 'audit/AUDIT_DOMAINS_V4.json')
        self.hist_path = ROOT / self.protocol['view_frame']['path']
        self.hist = load(self.hist_path)
        self.R = np.asarray(self.hist['R'], dtype=float)
        self.t = np.asarray(self.hist['t'], dtype=float)
        self.src, self.times = load_source()
        self.best = next((c for c in self.cand if c['status'] == 'S2_CANDIDATE_VAL_CONSISTENT'), None)
        if self.best is None:
            self.best = next((c for c in self.cand if c['id'] == 'OLD_TLS'), self.cand[0])
        self.old = next((c for c in self.cand if c['id'] == 'OLD_TLS'), None)
        self.lock = threading.Lock()
        self.cache = {}

    def local(self, p):
        return p @ self.R.T + self.t

    def frame(self, fi):
        if not 0 <= fi < len(self.times):
            raise ValueError('fi range')
        with self.lock:
            if fi in self.cache:
                return self.cache[fi]
        f = self.src.frame(fi)
        p = f['xyz']
        ok = validity(p)[1]
        rows = np.flatnonzero(ok)
        patch = np.zeros(len(p), dtype=np.uint8)
        loc = p @ self.R.T + self.t
        for i, pt in enumerate(self.dom['patches']):
            u0, u1, v0, v1 = pt['rect_uv']
            m = ok & (loc[:, 0] >= u0) & (loc[:, 0] < u1) & (loc[:, 1] >= v0) & (loc[:, 1] < v1) & (np.abs(loc[:, 2]) <= 0.15)
            patch[m] = i + 1
        keep = np.unique(np.r_[rows[::max(1, len(rows) // 7000)], np.flatnonzero(patch > 0)])
        keep = keep[:12000]
        r, az, el = distance.angles(p[keep])
        b = distance.bins(az, el, 1024, 512)
        out = dict(fi=fi, time_s=float(self.times[fi]), rows=len(p), valid=int(len(rows)),
                   raw=b64(p[keep], '<f4'), local=b64(self.local(p[keep]), '<f4'),
                   rows_b64=b64(keep, '<i4'), patch=b64(patch[keep], 'u1'),
                   pic=dict(nearest=b64(image_for(p, ok), '<f4')))
        with self.lock:
            if len(self.cache) > 3:
                self.cache.clear()
            self.cache[fi] = out
        return out

    def point(self, fi, row):
        f = self.src.frame(fi)
        p = f['xyz']
        if not 0 <= row < len(p):
            raise ValueError('row range')
        raw = self.src.buffer[(f['offset'] + row) * 28:(f['offset'] + row + 1) * 28].tobytes()
        loc = self.local(p[row:row + 1])[0]
        rec = dict(fi=fi, source_row=row, global_row=int(f['offset'] + row),
                   byte_offset=int((f['offset'] + row) * 28), raw28_hex=raw.hex(),
                   raw_xyz=[float(x) for x in p[row]], local_xyz=[float(x) for x in loc],
                   source_sha256=self.src.binding, coordinate_version=RAW,
                   local_version='HISTORICAL_CANDIDATE/' + sha(self.hist_path)[:16],
                   transform_id=self.hist['transform_id'], protocol_sha=sha(OUT / 'PROTOCOL_V4.json'))
        rec['residual_m'] = float(loc @ np.asarray(self.best['n']) + self.best['d'])
        return rec

    def binrows(self, fi, ia, ie):
        f = self.src.frame(fi)
        p = f['xyz']
        ok = validity(p)[1]
        r, az, el = distance.angles(p[ok])
        b = distance.bins(az, el, 1024, 512)
        cnt = np.bincount(b, minlength=1024 * 512)
        want = ie * 1024 + ia
        req = (ia, ie)
        if cnt[want] == 0:
            bestn, bestp = 0, None
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    a2, e2 = ia + dx, ie + dy
                    if 0 <= a2 < 1024 and 0 <= e2 < 512:
                        n2 = int(cnt[e2 * 1024 + a2])
                        if n2 > bestn:
                            bestn, bestp = n2, (a2, e2)
            if bestp is not None:
                ia, ie = bestp
                want = ie * 1024 + ia
        idx = np.flatnonzero(b == want)
        rows = np.flatnonzero(ok)[idx]
        order = np.argsort(r[idx])
        rows = rows[order]
        return dict(fi=fi, ia=ia, ie=ie, requested_ia=req[0], requested_ie=req[1],
                    snapped=(ia, ie) != req, count=int(len(rows)),
                    az_deg=float(-180 + (ia + 0.5) * 360 / 1024), el_deg=float(-90 + (ie + 0.5) * 180 / 512),
                    rows=[int(x) for x in rows[:96]], rows_total=int(len(rows)),
                    nearest_m=float(r[idx][order][0]) if len(rows) else None)


def image_for(p, ok):
    r, az, el = distance.angles(p[ok])
    b = distance.bins(az, el, 1024, 512)
    near = np.full(524288, np.inf, dtype=np.float64)
    np.minimum.at(near, b, r)
    img = near.reshape(512, 1024)
    # min-pool to 256x512; holes stay NaN
    img = img.reshape(256, 2, 512, 2).min(axis=(1, 3))
    img[~np.isfinite(img)] = np.nan
    return img.astype('<f4')


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
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ('/', '/index.html'):
                return self.send(200, (HERE / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            if u.path == '/app.js':
                return self.send(200, (HERE / 'app.js').read_bytes(), 'application/javascript; charset=utf-8')
            if u.path == '/api/meta':
                d = DATA
                return self.json(dict(item='HFUS-TCMS-02-REALDEV-02-S02', state='CANDIDATE_PLANE_PREVIEW', mode='OFFLINE_REVIEW',
                    warning='候选配平预览，地面身份与本段几何尚未验证；S2 审计域为先验条件选择，非独立地面真值',
                    source=d.src.binding, frames=len(d.times), hist_sha=sha(d.hist_path), protocol_sha=sha(OUT / 'PROTOCOL_V4.json'),
                    best=d.best, old=d.old, patches=d.dom['patches'], R=d.R.tolist(), t=d.t.tolist(),
                    candidate_status=d.best['status']))
            if u.path == '/api/frame':
                return self.json(DATA.frame(int(q['fi'])))
            if u.path == '/api/point':
                return self.json(DATA.point(int(q['fi']), int(q['row'])))
            if u.path == '/api/firstbin':
                fi = int(q['fi']); f = DATA.src.frame(fi); p = f['xyz']; ok = validity(p)[1]
                r, az, el = distance.angles(p[ok]); b = distance.bins(az, el, 1024, 512)
                cnt = np.bincount(b, minlength=1024 * 512)
                best = int(np.argmax(cnt))
                return self.json(dict(fi=fi, ia=best % 1024, ie=best // 1024, count=int(cnt[best])))
            if u.path == '/api/bin':
                return self.json(DATA.binrows(int(q['fi']), int(q['ia']), int(q['ie'])))
            if u.path == '/api/health':
                return self.json(dict(ok=True, frames=len(DATA.times)))
            self.send(404, b'not found', 'text/plain')
        except Exception as e:
            self.json(dict(error=type(e).__name__, message=str(e)), 400)


def main():
    global DATA
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=0)
    ap.add_argument('--label', default='full_r1')
    a = ap.parse_args()
    global LABEL
    LABEL = a.label
    DATA = Data()
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    print(json.dumps(dict(url='http://127.0.0.1:%d/' % srv.server_address[1], pid=__import__('os').getpid(),
                          best=DATA.best['id'])), flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
