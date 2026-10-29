"""Read-only S3 review server: same-frame RAW/levelled views, M0 state, point and row lookup."""
import argparse
import base64
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3core as C
import transform as X

HERE = Path(__file__).resolve().parent
PATCH_NAMES = ['S3V_H', 'S3V_I', 'S3V_J']


def b64(a, dtype):
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode()


class Data:
    def __init__(self):
        self.dom = C.load(C.OUT / 'DOMAINS/S3_DOMAINS.json')
        self.art = C.load(C.OUT / 'TRANSFORM/TRANSFORM_S3.json')
        self.qual = C.load(C.OUT / 'TRANSFORM/TRANSFORM_QUALIFICATION.json')
        self.m0 = C.load(C.OUT / 'M0/M0.json')
        self.ver = C.load(C.OUT / 'RUN/VERIFICATION.json')
        self.sum = C.load(C.OUT / 'RUN/SUMMARY.json')
        self.cons = C.load(C.OUT / 'RUN/FRAME_CONSERVATION.json')
        self.cands = C.load(C.S2 / 'full_r1/CANDIDATES.json')
        self.T = X.Transform(self.art)
        self.src, self.times = C.load_source()
        self.recs = [json.loads(l) for l in (C.OUT / 'RUN/frames.jsonl').read_text(encoding='utf8').splitlines()]
        self.z = np.load(C.OUT / 'DOMAINS/domains_s3.npz')
        self.patches = {}
        for name in PATCH_NAMES:
            table = {}
            rows = self.z['%s_val_rows' % name]
            fis = self.z['%s_val_fi' % name]
            for fi in np.unique(fis):
                table[int(fi)] = rows[fis == fi]
            prows = self.z['%s_prefix_rows' % name]
            pfis = self.z['%s_prefix_fi' % name]
            for fi in np.unique(pfis):
                table[int(fi)] = prows[pfis == fi]
            self.patches[name] = table
        self.lock = threading.Lock()
        self.cache = {}

    def state_reason(self, fi):
        rec = self.recs[fi]
        if fi <= 192:
            return ('MAP_BUILDING', 'M0 正在用 FIT [0,20)s 行构建，本帧还没有可用地图；无未来地图泄漏')
        if fi <= 270:
            return ('TEMPORAL_VALIDATION', 'M0 已冻结可用，但地面几何验证尚未结束（[20,28) 窗口未闭合）；271 前不晋级')
        if rec['online_state'] == 'GEOMETRY_VALIDATED_LOCAL':
            return ('GEOMETRY_VALIDATED_LOCAL', '变换数学 + 新域空间/时间 + M0 重建 + 应用链检查全部通过；271 起生效')
        return ('CANDIDATE_PLANE_PREVIEW', '验证门未通过，保持候选预览；见失败包')

    def frame(self, fi):
        if not 0 <= fi < len(self.recs):
            raise ValueError('fi range')
        with self.lock:
            if fi in self.cache:
                return self.cache[fi]
        f = self.src.frame(fi)
        rec = self.recs[fi]
        local = self.T.points(f['xyz'], self.T.tag(fi, False), fi, source_validity=True)
        ok = X.valid_xyz(f['xyz'])
        ledger = np.load(C.OUT / 'RUN/frames' / ('%04d.npz' % fi))['current']
        patch = np.zeros(len(f['xyz']), dtype=np.uint8)
        for i, name in enumerate(PATCH_NAMES):
            rows = self.patches[name].get(fi)
            if rows is not None:
                patch[rows - f['offset']] = i + 1
        rows = np.flatnonzero(ok)
        keep = np.unique(np.r_[rows[::max(1, len(rows) // 8000)],
                               np.flatnonzero(patch > 0)[::max(1, max(1, int((patch > 0).sum())) // 2000)]])
        keep = keep[:12000].astype('i4')
        out = dict(fi=fi, time_s=float(self.times[fi]), rows=len(f['xyz']), valid=int(ok.sum()),
                   invalid=int((~ok).sum()), record=rec,
                   state=rec['online_state'], state_reason=self.state_reason(fi),
                   raw=b64(f['xyz'][keep], '<f4'), local=b64(local[keep], '<f4'),
                   rows_b64=b64(keep, '<i4'), patch=b64(patch[keep], 'u1'),
                   labels={k: int(v) for k, v in rec['labels'].items()},
                   transform_id=self.T.id, coordinate_version=self.T.version)
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
        local = self.T.points(p[row:row + 1], self.T.tag(fi, False), fi, source_validity=True)[0]
        ledger = np.load(C.OUT / 'RUN/frames' / ('%04d.npz' % fi))['current']
        ok = X.valid_xyz(p[row:row + 1])[0]
        return dict(fi=fi, source_row=int(row), global_row=int(f['offset'] + row),
                    byte_offset=int((f['offset'] + row) * 28), raw28_hex=raw.hex(),
                    raw_xyz=[float(x) if np.isfinite(x) else None for x in p[row]],
                    local_xyz=[float(x) for x in local], valid=bool(ok),
                    label=int(ledger['label'][row]), surface=int(ledger['surface'][row]),
                    candidate=int(ledger['candidate'][row]),
                    z_local=float(local[2]) if ok else None,
                    source_sha256=self.src.binding, coordinate_version=self.T.version,
                    transform_id=self.T.id, state=self.recs[fi]['online_state'],
                    note='invalid/zero rows keep their original XYZ values and are not transformed')

    def first_invalid(self, fi):
        f = self.src.frame(fi)
        ok = X.valid_xyz(f['xyz'])
        rows = np.flatnonzero(~ok)
        return dict(fi=fi, row=int(rows[0]) if len(rows) else None, invalid=int(len(rows)))


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
                    item=C.ITEM, state=d.qual['state'], mode='OFFLINE_REVIEW',
                    warning='本段几何配平（S3_LOCAL）：地面身份未确认、无物理高度、非独立 D；271 前不得用于在线资格',
                    source=d.src.binding, frames=len(d.times),
                    transform=dict(transform_id=d.art['transform_id'], coordinate_version=d.art['coordinate_version'],
                                   R=d.art['R'], t=d.art['t'], plane=d.art['plane'],
                                   artifact_sha=C.sha(C.OUT / 'TRANSFORM/TRANSFORM_S3.json')),
                    qualification=d.qual['qualification'], state_from_fi=d.qual['state_from_fi'],
                    candidate=next(c for c in d.cands if c['id'] == 'C3D_03'),
                    controls=[dict(id=c['id'], n=c['n'], d=c['d'], status=c['status']) for c in d.cands],
                    domains=dict(domains_sha=d.dom['domains_sha'], patches=d.dom['patches']),
                    m0=dict(map_id=d.m0['primary']['map_id'], surfaces=d.m0['primary']['surfaces'],
                            eligible_surfaces=d.m0['primary']['eligible_surfaces'],
                            voxel_m=d.m0['primary']['voxel_m'], tau_m=d.m0['primary']['tau_m'],
                            support_rows=d.m0['primary']['support_rows'], build_end_fi=d.m0['build_end_fi'],
                            available_after_fi=d.m0['available_after_fi']),
                    verification=dict(spatial_pass=d.ver['spatial_pass_patches'],
                                      spatial={k: dict(PASS=v['PASS'], rms_m=v['rms_m'], p95_abs_m=v['p95_abs_m'],
                                                       support_rate=v['support_rate'], count=v['count'])
                                               for k, v in d.ver['spatial'].items()},
                                      temporal_pass=d.ver['temporal']['fraction'],
                                      prefix_pass=d.ver['prefix']['all_patch_pass_frames'],
                                      prefix_frames=d.ver['prefix']['frames'],
                                      qualified_M0=d.ver['qualified_M0'], state_from_271=d.ver['state_from_271'],
                                      noise=d.ver['noise_reference'], gates=d.ver['gates']),
                    conservation=dict(rows=d.cons['rows'], valid=d.cons['valid'], invalid=d.cons['invalid'],
                                      PASS=d.cons['PASS']),
                    summary=dict(seconds=d.sum['seconds'], peak_rss_bytes=d.sum['peak_rss_bytes'],
                                 output_bytes=d.sum['output_bytes']),
                    failure=None))
            if u.path == '/api/frame':
                return self.json(DATA.frame(int(q['fi'])))
            if u.path == '/api/point':
                return self.json(DATA.point(int(q['fi']), int(q['row'])))
            if u.path == '/api/firstinvalid':
                return self.json(DATA.first_invalid(int(q['fi'])))
            if u.path == '/api/state':
                fi = int(q['fi'])
                return self.json(dict(fi=fi, state=DATA.recs[fi]['online_state'],
                                      one_liner=DATA.state_reason(fi)[1],
                                      qualified=DATA.recs[fi]['qualified'],
                                      m0_exists=DATA.recs[fi]['m0_exists'],
                                      failure=None))
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
                          pid=__import__('os').getpid(), state=DATA.qual['state'])), flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
