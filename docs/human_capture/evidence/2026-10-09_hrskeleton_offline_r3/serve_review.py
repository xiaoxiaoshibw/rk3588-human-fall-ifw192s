"""Read-only guided review server. R1 frozen assets are explicitly allowlisted."""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

OUT = Path(__file__).resolve().parent
R1 = OUT.parent/'2026-10-09_hrskeleton_offline_r1'

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        name = unquote(urlsplit(path).path).lstrip('/')
        if name in ['input_manifest.json','pass5/nodes_raw.jsonl','pass5/nodes_filtered.jsonl'] or (name.startswith('frames/f') and name.endswith('.json')):
            base, relative = R1, name
        elif name in ['r1/review.js','r1/review_config_final.js']:
            base, relative = R1, name[3:]
        else:
            base, relative = OUT, name or 'review.html'
        resolved = (base/relative).resolve()
        if resolved != base and base not in resolved.parents:
            return str(OUT/'__denied__')
        return str(resolved)

if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1',8884),functools.partial(Handler,directory=str(OUT)))
    try:
        print('GUIDED_REVIEW http://127.0.0.1:8884/review.html',flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
