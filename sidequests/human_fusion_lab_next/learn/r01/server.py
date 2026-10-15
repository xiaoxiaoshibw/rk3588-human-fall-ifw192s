"""Versioned routes on the ORIGINAL replay application. Its old bytes stay untouched."""
import argparse
import copy
import importlib.util
import json
import os
import socket
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import numpy as np
from contracts import ROOT, OLD, read, sha, write, Revisions, trusted_labels, universe

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(OLD))
spec = importlib.util.spec_from_file_location('hfus_original_server', OLD/'server.py')
legacy = importlib.util.module_from_spec(spec); spec.loader.exec_module(legacy)
validate_source_binding = legacy.validate_source_binding
LOCK = threading.Lock()


class View:
    def __init__(self, evidence, expected_manifest=None, expected_index=None):
        self.e = Path(evidence).resolve(); self.m = read(self.e/'RUN_MANIFEST.json')
        self.manifest_sha = sha(self.e/'RUN_MANIFEST.json')
        self.index = read(self.e/'primary/INDEX.json'); self.index_sha = sha(self.e/'primary/INDEX.json')
        if self.m.get('schema') != 'hfus-learn/1' or self.m.get('run_id') != self.e.name: raise ValueError('Unknown run schema/ID')
        if expected_manifest is not None and expected_manifest != self.manifest_sha: raise ValueError('Expected manifest drift')
        if expected_index is not None and expected_index != self.index_sha: raise ValueError('Expected output index drift')
        if self.index['run_manifest_sha256'] != self.manifest_sha: raise ValueError('Run/index mismatch')
        self.tasks = read(self.e/'ANNOTATION_TASKS.json'); self.labels = Revisions(self.e/'labels')

    def verified(self, relative):
        relative = relative.replace('\\', '/')
        if relative.startswith('/') or '..' in relative.split('/'): raise ValueError('Invalid output path')
        if sha(self.e/'RUN_MANIFEST.json') != self.manifest_sha or sha(self.e/'primary/INDEX.json') != self.index_sha:
            raise ValueError('Live same-ID content drift')
        path = self.e/'primary'/relative
        if relative not in self.index['files'] or sha(path) != self.index['files'][relative]: raise ValueError('Frozen output drift')
        return path

    def frame(self, sid, fi, group='G0', height=128):
        if sid not in self.m['sources'] or group not in self.index['geometry_streams'] or type(fi) is not int or height not in [128, 256]: raise ValueError('Unknown source/variant/grid')
        if sid == self.m['split']['empty_sid'] and fi not in self.m['split']['empty_report']: raise ValueError('FIT/CAL excluded')
        if not 0 <= fi < self.m['sources'][sid]['frames']: raise ValueError('Unknown frame')
        row = read(self.verified(f'runs/{group}/{sid}/{fi:04d}.json'))
        with np.load(self.verified(f'common/{sid}/{fi:04d}.npz')) as d: common = {k:d[k] for k in d.files}
        with np.load(self.verified(f'runs/{group}/{sid}/{fi:04d}.npz')) as d: members = {k:d[k] for k in d.files}
        with np.load(self.verified(f'projection/{sid}/{fi:04d}_{height}.npz')) as d: projection = {k:d[k] for k in d.files}
        return row, common, members, projection

    def original(self, sid, fi, index):
        row, common, members, _ = self.frame(sid, fi)
        if type(index) is not int or not 0 <= index < len(common['raw']): raise ValueError('Invalid source row')
        directory = ROOT/'captures/remote'/sid
        if not (directory/'meta.json').exists() or not (directory/'points.bin').exists():
            return dict(status='BLOCKED_MISSING_ORIGINAL', raw_bytes=None, identity='UNKNOWN')
        legacy.validate_source_binding(directory, self.m['sources'][sid]['sha256'])
        from next_contract import validate_meta
        meta = read(directory/'meta.json'); validate_meta(meta, (directory/'points.bin').stat().st_size)
        if meta['frames'][fi] != row['source_frame']: raise ValueError('Source frame drift')
        offset = (row['source_frame']['offset_points']+index)*28
        with (directory/'points.bin').open('rb') as f: f.seek(offset); data = f.read(28)
        if len(data) != 28: raise ValueError('Truncated source query')
        finite = lambda x: [float(v) if np.isfinite(v) else None for v in x]
        return dict(status='ORIGINAL_BYTES_SHA_VERIFIED', sid=sid, fi=fi, row=index,
                    global_row=row['source_frame']['offset_points']+index, offset_bytes=offset, device_time=row['time'],
                    raw_bytes_hex=data.hex(), opaque_12_27=data[12:].hex(), raw=finite(common['raw'][index]),
                    nominal=finite(common['nominal'][index]), corrected=finite(common['corrected'][index]),
                    source_sha256=self.m['sources'][sid]['sha256'], identity='UNKNOWN')


def handler(evidence, expected_manifest=None, expected_index=None, expected_viewer=None):
    view = View(evidence, expected_manifest, expected_index)
    viewer = {n:sha(HERE/n) for n in ['server.py', 'view.js', 'view.html']}
    if expected_viewer is not None and viewer != expected_viewer: raise ValueError('Expected viewer source drift')
    def check_viewer():
        if viewer != {n:sha(HERE/n) for n in viewer}: raise ValueError('Live viewer code drift')
    class Handler(legacy.Handler):
        def do_GET(self):
            req = urlparse(self.path)
            if req.path == '/console.html':
                self.send(200, (ROOT/'pc_apps/console/console.html').read_bytes(), 'text/html; charset=utf-8')
                return
            if not req.path.startswith('/learn/'):
                return super().do_GET()
            prefix = '/learn/'+view.e.name+'/'
            try:
                check_viewer()
                if not req.path.startswith(prefix): raise ValueError('Unknown version gate')
                route = req.path[len(prefix):]; q = parse_qs(req.query)
                if route in ['', 'app.js']:
                    self.send(200, (HERE/('view.html' if not route else 'view.js')).read_bytes(),
                              'text/html; charset=utf-8' if not route else 'text/javascript; charset=utf-8'); return
                if route == 'catalog':
                    self.send(200, dict(run_id=view.e.name, manifest_sha256=view.manifest_sha,
                                        code_sha256=view.m['source_sha256'], viewer_sha256=viewer, tasks=view.tasks, sources=view.m['sources'],
                                        groups=view.index['geometry_streams'], models=read(view.e/'EXPERIMENT_MATRIX.json'),
                                        label_manifest=read(view.e/'LABEL_MANIFEST.json'))); return
                sid = q['sid'][0]; fi = int(q['fi'][0]); group = q.get('group', ['G0'])[0]; h = int(q.get('h', ['128'])[0])
                if route == 'source':
                    self.send(200, view.original(sid, fi, int(q['row'][0]))); return
                row, common, members, projection = view.frame(sid, fi, group, h)
                if route == 'frame':
                    u = np.flatnonzero(common['U']); labels = view.labels.records(sid, fi)
                    task = next((t for t in view.tasks if t['sid'] == sid and t['fi'] == fi), None)
                    gt = trusted_labels(labels, u, bool(task and task['secondary_required']),
                                        .7 if sid != view.m['split']['empty_sid'] else 0)
                    with np.load(view.verified(f'runs/G0/{sid}/{fi:04d}.npz')) as d:
                        baseline = d['selected'][u].astype(bool)
                    current = members['selected'][u].astype(bool)
                    # Full U view, never only old selected points; invalid raw not made drawable.
                    self.send(200, dict(metadata=row, rows=u.tolist(), raw=common['raw'][u].tolist(),
                                        nominal=common['nominal'][u].tolist(), corrected=common['corrected'][u].tolist(),
                                        selected=members['selected'][u].tolist(), cluster=members['cluster'][u].tolist(),
                                        added=(current & ~baseline).tolist(), removed=(baseline & ~current).tolist(),
                                        GT=gt.tolist(), projection={k:v.tolist() for k, v in projection.items()},
                                        reviews=labels, task=task, manifest_sha256=view.manifest_sha)); return
                raise ValueError('Unknown learn route')
            except (ValueError, KeyError, IndexError, OSError, TypeError) as exc:
                self.send(400, dict(error=str(exc), status='FAIL_OR_MISSING_SOURCE_NO_FALLBACK'))

        def do_POST(self):
            if not self.path.startswith('/learn/'):
                return super().do_POST()
            try:
                check_viewer()
                if self.path != '/learn/'+view.e.name+'/labels': raise ValueError('Unknown label route')
                if self.headers.get('Origin') != 'http://'+self.headers.get('Host', ''): raise ValueError('Same-origin review required')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16*1024*1024 or 'application/json' not in self.headers.get('Content-Type', ''): raise ValueError('Label body')
                rec = json.loads(self.rfile.read(size)); sid, fi = rec['sid'], rec['fi']
                task = next((t for t in view.tasks if t['sid'] == sid and t['fi'] == fi), None)
                if task is None or task['kind'] != 'CORE': raise ValueError('Proposal tasks cannot become gold in this frozen run')
                if rec.get('layer') == 'SECONDARY' and not task['secondary_required']: raise ValueError('Not in frozen second review list')
                row, common, _, _ = view.frame(sid, fi)
                legacy.validate_source_binding(ROOT/'captures/remote'/sid, view.m['sources'][sid]['sha256'])
                with LOCK:
                    saved = view.labels.append(rec, row['source'], np.flatnonzero(common['U']))
                self.send(201, dict(saved=saved, note='Human evidence recorded; gates must be recomputed before any training'))
            except (ValueError, KeyError, TypeError, OSError) as exc: self.send(400, dict(error=str(exc)))
    return Handler


def serve(evidence, port=0):
    return legacy.LocalReplayServer(('127.0.0.1', port), handler(evidence))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--evidence', type=Path, required=True); p.add_argument('--port', type=int, default=0)
    a = p.parse_args(); s = serve(a.evidence, a.port)
    write(a.evidence/'SERVER_START.json', dict(pid=os.getpid(), port=s.server_address[1], host='127.0.0.1',
                                               code_sha256=sha(__file__), legacy_handler_sha256=sha(OLD/'server.py')))
    print('http://127.0.0.1:'+str(s.server_address[1])+'/learn/'+a.evidence.name+'/', flush=True)
    s.serve_forever()
