#!/usr/bin/env python3
"""Static file server for the field page, with explicit no-cache headers.

Why not ``python -m http.server``: it sends no ``Cache-Control``, so a browser
may keep the previous release's ``index.html`` after the ``current`` symlink is
switched. The page then honestly reports "页面版本与运行版本不一致" and has to
reload itself -- a fix that cannot work for a page older than the fix itself.

This server is the same stdlib handler with two differences:

* every response carries ``Cache-Control: no-cache, must-revalidate`` so the
  browser always revalidates against ``Last-Modified``;
* the directory is fixed on the command line, so the page can only ever be the
  one under ``$BASE/www`` (which follows ``current``).

It serves only regular files under that root; the symlink layout is resolved by
the OS, which is exactly the release binding we want.
"""

import argparse
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class NoCacheHandler(SimpleHTTPRequestHandler):
    server_version = "hf_page/1"

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):  # keep the log line short and timestamped
        sys.stderr.write("[webui] %s %s\n" % (self.log_date_time_string(), fmt % args))


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, directory):
        self.directory = os.path.abspath(directory)
        handler = lambda *a, **kw: NoCacheHandler(*a, directory=self.directory, **kw)
        super().__init__(address, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8936)
    parser.add_argument("--directory", required=True)
    args = parser.parse_args(argv)
    if not os.path.isdir(args.directory):
        sys.stderr.write("directory not found: %s\n" % args.directory)
        return 2
    server = Server((args.bind, args.port), args.directory)
    print("[webui] serving %s on http://%s:%d/ (no-cache)"
          % (os.path.abspath(args.directory), args.bind, args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())