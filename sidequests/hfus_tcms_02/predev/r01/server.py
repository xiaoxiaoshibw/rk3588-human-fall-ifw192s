"""Read-only, exclusive localhost replay. Adapted from pointset/r01 Handler.send.

No old Handler, label writers, output constants, fallback cache or source discovery.
"""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from contracts import HERE, EVIDENCE_ROOT, Source, sha, write_new


class Replay:
    def __init__(self, paths):
        self.runs = []
        self.sources = {}
        self.source_stats = {}
        self.run_bindings = {}
        for path in paths:
            path = Path(path).resolve()
            index = json.loads((path / 'OUTPUT_INDEX.json').read_text(encoding='utf8'))
            for name, h in index.items():
                if not (path/name).resolve().is_relative_to(path) or sha(path / name) != h:
                    raise ValueError('Replay artifact drift')
            data = json.loads((path / 'REPLAY.json').read_text(encoding='utf8'))
            self.runs.append((path, data))
            self.run_bindings[str(path)] = dict(index=sha(path/'OUTPUT_INDEX.json'), replay=index['REPLAY.json'])
            for e in data['entries']:
                s = Source(e)
                s.close()
                self.sources[e['sid']] = e
                self.source_stats[e['sid']] = self.stats(e)

    def stats(self, entry):
        return [(p.stat().st_size,p.stat().st_mtime_ns) for p in
                [Path(entry['path'])/'meta.json',Path(entry['path'])/'points.bin']]

    def verify_source(self, sid):
        if self.stats(self.sources[sid]) != self.source_stats[sid]:
            s = Source(self.sources[sid])
            s.close()
            self.source_stats[sid] = self.stats(self.sources[sid])

    def record(self, sid, fi, variant):
        self.verify_source(sid)
        for p,_ in self.runs:
            expected = self.run_bindings[str(p)]
            if sha(p/'OUTPUT_INDEX.json') != expected['index'] or sha(p/'REPLAY.json') != expected['replay']:
                raise ValueError('Live replay/index drift')
        matches = [r for _, d in self.runs for r in d['records']
                   if r['sid'] == sid and r['fi'] == fi and r['variant'] == variant]
        if len(matches) != 1:
            raise ValueError('Unknown/nonunique frame binding')
        return matches[0]


class Handler(BaseHTTPRequestHandler):
    def send(self, code, data, kind='application/json; charset=utf-8'):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf8')
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path in ('/', '/app.js'):
                name = 'index.html' if u.path == '/' else 'app.js'
                return self.send(200, (HERE / name).read_bytes(),
                                 'text/html; charset=utf-8' if name.endswith('html') else 'text/javascript; charset=utf-8')
            replay = self.server.replay
            if u.path == '/api/catalog':
                sessions = []
                for _, d in replay.runs:
                    for e in d['entries']:
                        rows = [r for r in d['records'] if r['sid'] == e['sid']]
                        if rows:
                            sessions.append(dict(sid=e['sid'], kind=e['kind'],
                                                 frames=sorted({r['fi'] for r in rows}),
                                                 variants=sorted({r['variant'] for r in rows}),
                                                 cases=[c for c in d['cases'] if c.get('sid', e['sid']) == e['sid']]))
                return self.send(200, dict(sessions=sessions, real_status='BLOCKED', contract_only=True))
            sid, fi = q.get('sid', [''])[0], int(q.get('fi', ['-1'])[0])
            r = replay.record(sid, fi, q.get('variant', ['full'])[0])
            if u.path in ('/api/frame', '/api/source-members'):
                return self.send(200, r if u.path == '/api/frame' else r['current_rows'])
            if u.path == '/api/source':
                row = int(q['row'][0])
                s = Source(replay.sources[sid])
                try:
                    binding = s.mapping(fi, source_row=row)
                    f = s.frame(fi)
                    if f['source_sha256'] != r['source_sha256'] or f['offset'] != r['offset']:
                        raise ValueError('Source/frame drift')
                    with (s.folder / 'points.bin').open('rb') as stream:
                        stream.seek(binding['byte_offset'])
                        raw = stream.read(28)
                    return self.send(200, dict(binding, source_sha256=s.binding,
                                               row_record=r['current_rows'][row], raw_bytes_hex=raw.hex(),
                                               opaque_bytes_12_27='NOT_INTERPRETED', original_source_sha_verified=True))
                finally:
                    s.close()
            if u.path == '/api/surface':
                i = int(q['surface_id'][0])
                if not 0 <= i < len(r['map_ledger']):
                    raise ValueError('Invalid surface ID')
                replay.verify_source(r['map_ledger'][i]['mapping_source']['mapping_sid'])
                return self.send(200, r['map_ledger'][i])
            return self.send(404, dict(error='Unknown endpoint'))
        except (ValueError, KeyError, OSError, IndexError) as exc:
            return self.send(400, dict(error=str(exc)))

    def do_POST(self):
        self.send(405, dict(error='Read-only replay; explicit CLI confirmation file required'))

    def log_message(self, fmt, *args):
        pass


class LocalReplayServer(ThreadingHTTPServer):
    allow_reuse_address = False


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run', action='append', required=True)
    p.add_argument('--port', type=int, default=0)
    p.add_argument('--process-record', required=True)
    args = p.parse_args()
    process_path = Path(args.process_record).resolve()
    if (not process_path.is_relative_to(EVIDENCE_ROOT) or
            not process_path.relative_to(EVIDENCE_ROOT).parts[0].startswith('2026-10-17_hfus_tcms_02_predev_r')):
        raise ValueError('Process record must be in this PREDEV evidence item')
    service = LocalReplayServer(('127.0.0.1', args.port), Handler)
    service.replay = Replay(args.run)
    write_new(process_path, dict(pid=os.getpid(), address=service.server_address,
                                       runs=args.run, command=__import__('sys').argv, scope='localhost-read-only'))
    print('http://127.0.0.1:%d/' % service.server_port, flush=True)
    service.serve_forever()
