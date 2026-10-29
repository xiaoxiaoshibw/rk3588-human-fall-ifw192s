"""Localhost GET-only viewer for a completed skeleton-calibration run."""
import argparse
import importlib.util
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
R01 = ROOT / 'sidequests/hfus_tcms_02/realdev/r01'
R04 = ROOT / 'sidequests/hfus_tcms_02/realdev/r04'
S3 = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Run:
    def __init__(self, run_dir):
        self.dir = Path(run_dir).resolve()
        self.meta = json.loads((self.dir / 'RUN_META.json').read_text(encoding='utf8'))
        self.summary = json.loads((self.dir / 'FRAME_SUMMARY.json').read_text(encoding='utf8'))
        self.artifact = json.loads((S3 / 'TRANSFORM/TRANSFORM_S3.json').read_text(encoding='utf8'))
        sys.path.insert(0, str(R04))
        try:
            X = module('skeleton02_view_transform', R04 / 'transform.py')
        finally:
            sys.path.remove(str(R04))
        self.T = X.Transform(self.artifact)
        contracts = module('skeleton02_view_contracts', R01 / 'contracts.py')
        source = Path(ROOT / 'data/sessions/cap_20261017_113516')
        self.source = contracts.Source(dict(
            kind='REAL_DEVELOPMENT', role='B', independent_test=False,
            path=str(source), sid='cap_20261017_113516', coordinate_version='RAW/innolidar',
            source_sha256=dict(meta=self.meta['source']['meta_sha256'],
                               points=self.meta['source']['points_sha256'])))
        self.records = {}
        with (self.dir / 'frames.jsonl').open(encoding='utf8') as f:
            for line in f:
                rec = json.loads(line)
                self.records[rec['fi']] = rec
        self.calibration = json.loads((self.dir / 'CALIBRATION.json').read_text(encoding='utf8'))

    def points(self, fi):
        f = self.source.frame(fi)
        local = self.T.points(f['xyz'], self.T.tag(fi, False), fi, source_validity=True)
        valid = np.isfinite(local).all(axis=1) & np.any(local != 0, axis=1)
        labels = np.load(self.dir / 'frames' / ('%04d.npz' % fi))['candidate']
        rows = np.flatnonzero(valid)
        points = []
        for row in rows:
            x, y, z = (float(v) for v in local[row])
            points.append([round(x, 4), round(y, 4), round(z, 4), int(row), int(labels[row])])
        invalid = np.flatnonzero(~valid)
        return dict(fi=fi, time_ns=int(f['time_ns']), relative_s=float(f['relative_s']),
                    rows=int(len(local)), valid_rows=int(len(rows)),
                    invalid_row_examples=[int(r) for r in invalid[:12]],
                    points=points,
                    source_sha256=dict(meta=self.meta['source']['meta_sha256'],
                                       points=self.meta['source']['points_sha256']),
                    transform_id=self.T.id, coordinate_version=self.T.version,
                    camera_projection_note='Projection is display-only; returned point coordinates are S3_LOCAL world coordinates.')

    def frame(self, fi):
        rec = self.records[int(fi)]
        data = self.points(int(fi))
        tracks = rec.get('track_results', [])
        best = max(tracks, key=lambda t: (t.get('valid_nodes', 0), t.get('edge_count', 0)),
                   default=None)
        data.update(record=rec, best_track=best,
                    calibration_rows=([] if best is None else best.get('edges', [])))
        return data

    def point(self, fi, row):
        f = self.source.frame(int(fi))
        raw = self.source.raw_row(int(fi), int(row))
        labels = np.load(self.dir / 'frames' / ('%04d.npz' % int(fi)))['candidate']
        xyz = raw['xyz']
        valid = bool(all(v is not None and np.isfinite(v) for v in xyz)
                     and any(abs(v) > 0 for v in xyz))
        local = None
        if valid:
            local = self.T.points(np.asarray([xyz], dtype=float),
                                  self.T.tag(int(fi), False), int(fi)).tolist()[0]
        return dict(fi=int(fi), source_row=int(row), raw28_hex=raw['raw_bytes_hex'],
                    source_xyz=xyz,
                    local_xyz=local,
                    valid=valid,
                    candidate_id=int(labels[int(row)]),
                    source_sha256=raw['source_sha256'],
                    coordinate_version=self.T.version,
                    transform_id=self.T.id,
                    opaque_bytes_12_27='NOT_INTERPRETED')

    def meta_payload(self):
        return dict(meta=self.meta, summary=self.summary,
                    calibration_gate=self.calibration.get('gate'),
                    primary_track=self.calibration.get('primary_track'),
                    protocol_sha=self.meta.get('protocol_sha'),
                    frames=sorted(self.records),
                    warning='POINT-SUPPORTED REGIONS ONLY; ANATOMY/LEFT-RIGHT/PHYSICAL HEIGHT/HUMAN IDENTITY = UNKNOWN.')


class Handler(BaseHTTPRequestHandler):
    run = None

    def log_message(self, fmt, *args):
        return

    def send_json(self, value, status=200):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':')).encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == '/':
                return self.send_file(HERE / 'index.html', 'text/html; charset=utf-8')
            if u.path == '/app.js':
                return self.send_file(HERE / 'app.js', 'application/javascript; charset=utf-8')
            if u.path == '/api/meta':
                return self.send_json(self.run.meta_payload())
            if u.path == '/api/frame':
                return self.send_json(self.run.frame(int(q['fi'][0])))
            if u.path == '/api/point':
                return self.send_json(self.run.point(int(q['fi'][0]), int(q['row'][0])))
            if u.path == '/api/health':
                return self.send_json(dict(ok=True, pid=__import__('os').getpid()))
            self.send_error(404)
        except Exception as exc:
            self.send_json(dict(error=str(exc)), status=500)

    def send_file(self, path, content_type):
        body = Path(path).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--port', type=int, default=0)
    args = ap.parse_args()
    Handler.run = Run(args.run)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    host, port = server.server_address
    print(json.dumps(dict(address=[host, port], url='http://%s:%d/' % (host, port),
                          pid=__import__('os').getpid())), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
