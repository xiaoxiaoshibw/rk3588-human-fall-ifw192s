"""新版UI单独入口；既有v2源码/失败记录保持。"""
import argparse
from urllib.parse import urlsplit

from server import Handler, HERE, ThreadingHTTPServer


class PreviewHandler(Handler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ('/', '/app_v3.js'):
            return self.send((HERE / ('index_v3.html' if path == '/' else 'app_v3.js')).read_bytes(),
                             'text/html; charset=utf-8' if path == '/' else 'application/javascript; charset=utf-8')
        return super().do_GET()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8927)
    args = parser.parse_args()
    print('真实点云粗骨架 UI v3 http://127.0.0.1:%d/' % args.port, flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), PreviewHandler).serve_forever()
