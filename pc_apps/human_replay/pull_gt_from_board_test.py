# -*- coding: utf-8 -*-
"""pull_gt_from_board_test.py — PC 端拉板端 GT 产物的单元测试（本地起 mock 板）。

跑法： python -B -W error -m unittest pc_apps.human_replay.pull_gt_from_board_test -v
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


class _MockBoard(BaseHTTPRequestHandler):
    """模拟板端 /api/gt/export + /api/gt/exports/file。"""
    FILES = {}  # class-level dict: {(sid_or_None, name): bytes}

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):  # noqa: N802
        q = parse_qs(urlparse(self.path).query)
        path = urlparse(self.path).path
        if path == "/api/gt/export":
            sid = (q.get("sid") or [None])[0]
            if sid is None:
                sids = sorted({s for (s, n) in self.FILES if s})
                return self._json({"ok": True, "sessions": sids,
                                    "files": sorted({n for (s, n) in self.FILES if s is None})})
            files = sorted(n for (s, n) in self.FILES if s == sid)
            return self._json({"ok": True, "sid": sid, "files": files})
        if path == "/api/gt/exports/file":
            sid = (q.get("sid") or [None])[0]
            name = q.get("name", [""])[0]
            payload = self.FILES.get((sid, name))
            if payload is None:
                return self.send_error(404)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_error(404)


def _spawn_mock(files):
    _MockBoard.FILES = dict(files)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _MockBoard)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return "http://127.0.0.1:%d" % port, srv, th


class PullGtTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pull_gt_")
        self.srv = None

    def tearDown(self):
        if self.srv:
            self.srv.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pull_writes_new_files_and_skips_identical(self):
        import pull_gt_from_board as P
        sid = "cap_20261010_175227"
        v1 = json.dumps({"version": "V1", "sid": sid}).encode()
        manifest = json.dumps({"versions": [{"version": "V1"}]}).encode()
        base, self.srv, _th = _spawn_mock({
            ("cap_20261010_175227", "manifest.json"): manifest,
            ("cap_20261010_175227", "GT_V1.json"): v1,
            ("cap_20261010_180557", "manifest.json"): manifest,
        })
        logs = []
        res = P.pull(board=base, dest_store=self.tmp, log=lambda m: logs.append(m))
        self.assertEqual(len(res["conflicts"]), 0)
        # 3 个文件（2 会话 manifest + 1 个 GT_V1）
        self.assertEqual(len(res["pulled"]), 3)
        # 再跑一次：全部应 skip 不 pulled
        res2 = P.pull(board=base, dest_store=self.tmp, log=lambda m: None)
        self.assertEqual(len(res2["pulled"]), 0)
        self.assertEqual(len(res2["skipped"]), 3)

    def test_pull_never_overwrites_existing_gtv(self):
        import pull_gt_from_board as P
        sid = "cap_20261010_175227"
        board_v1 = b'{"version":"V1","board":1}'
        pc_diff = b'{"version":"V1","pc_differs":1}'
        base, self.srv, _th = _spawn_mock({(sid, "GT_V1.json"): board_v1})
        # 预置 PC 一份内容不同的 GT_V1
        sess_dir = os.path.join(self.tmp, sid)
        os.makedirs(sess_dir)
        with open(os.path.join(sess_dir, "GT_V1.json"), "wb") as fh:
            fh.write(pc_diff)
        res = P.pull(board=base, dest_store=self.tmp, log=lambda m: None)
        self.assertEqual(len(res["conflicts"]), 1)
        with open(os.path.join(sess_dir, "GT_V1.json"), "rb") as fh:
            self.assertEqual(fh.read(), pc_diff,
                             "GT_V* 不可变：板上版不允许冲掉 PC 已有版")

    def test_pull_handles_empty_board(self):
        import pull_gt_from_board as P
        base, self.srv, _th = _spawn_mock({})
        res = P.pull(board=base, dest_store=self.tmp, log=lambda m: None)
        self.assertEqual(res["pulled"], [])


if __name__ == "__main__":
    unittest.main()
