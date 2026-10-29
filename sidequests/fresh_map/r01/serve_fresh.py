# -*- coding: utf-8 -*-
"""FRESH-MAP r01 本地小服务：静态=仓库根 + /api/file?sid&name → captures/remote 白名单映射。
仅绑 127.0.0.1；/api/leveling 等其它 /api 一律 404 → replay.js 自动落默认配平兜底。
运行：python serve_fresh.py  （PORT 环境变量可改，缺省 8791）"""
import http.server
import os
import re
import socketserver
import urllib.parse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
NAMES = {"meta.json", "points.bin"}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/file":
            q = urllib.parse.parse_qs(u.query)
            sid = q.get("sid", [""])[0]
            name = q.get("name", [""])[0]
            p = os.path.normpath(os.path.join(ROOT, "captures", "remote", sid, name))
            if SID_RE.match(sid) and name in NAMES and p.startswith(
                    os.path.normpath(os.path.join(ROOT, "captures", "remote")) + os.sep) and os.path.isfile(p):
                self.send_response(200)
                self.send_header("Content-Type", "application/json" if name.endswith(".json") else "application/octet-stream")
                self.send_header("Content-Length", str(os.path.getsize(p)))
                self.end_headers()
                with open(p, "rb") as f:
                    while True:
                        b = f.read(1 << 20)
                        if not b:
                            break
                        self.wfile.write(b)
                return
            self.send_error(404)
            return
        if u.path.startswith("/api/"):
            self.send_error(404)
            return
        return super().do_GET()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8791"))
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler) as srv:
        print("http://127.0.0.1:%d/sidequests/fresh_map/r01/fresh.html" % port, flush=True)
        srv.serve_forever()
