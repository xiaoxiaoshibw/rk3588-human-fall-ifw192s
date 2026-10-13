"""Local read-only review server. No board connection, POST, or write API."""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        resolved = Path(super().translate_path(path)).resolve()
        root = Path(__file__).resolve().parent
        if root not in resolved.parents and resolved != root:
            return str(root/'__outside_denied__')
        return str(resolved)

if __name__ == '__main__':
    folder = str(Path(__file__).resolve().parent)
    server = ThreadingHTTPServer(('127.0.0.1', 8883), functools.partial(Handler, directory=folder))
    try:
        print('REVIEW http://127.0.0.1:8883/review.html', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
