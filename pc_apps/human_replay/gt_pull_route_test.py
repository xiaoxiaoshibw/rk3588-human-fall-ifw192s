# -*- coding: utf-8 -*-
"""gt_pull_route_test.py — /api/gt/pull + /api/gt/pull_status 的路由/护栏/板端 403 测试。

不起真板：本地 0 端口 mock 一个 GT 服务 + patch pull 模块的 board URL，跑一遍完整 HTTP 链路。
隔离仿 sessions_test.py（patch.object(C, "DEST_ROOT")）+ gt_server_test.py（patch G.STORE）。
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config as C
import gt_server as G
import human_replay_lib as H
import pull_gt_from_board as P


class _MockGTBoard(BaseHTTPRequestHandler):
    """最小 GT 服务：/api/gt/export 返回空清单。"""
    def log_message(self, *a):  # noqa: N802
        pass

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/gt/export"):
            payload = json.dumps({"ok": True, "sessions": []}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_error(404)


class _Pipe:
    def __init__(self):
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H.Handler)
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self):
        return "http://127.0.0.1:%d" % self.srv.server_address[1]

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()

    def request(self, path, body=None, method=None):
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            method = "POST"
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8"))
            except Exception:
                return e.code, {}


class GtPullRouteTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="gt_pull_route_")
        self._store = os.path.join(self._tmp, "gt_store")
        self._dest = os.path.join(self._tmp, "dest")
        os.makedirs(self._store)
        os.makedirs(self._dest)
        self._store_save = G.STORE
        G.STORE = self._store
        self._dest_save = C.DEST_ROOT
        C.DEST_ROOT = self._dest

        # mock GT board
        self.mock = ThreadingHTTPServer(("127.0.0.1", 0), _MockGTBoard)
        self.mock_thread = threading.Thread(target=self.mock.serve_forever, daemon=True)
        self.mock_thread.start()
        self.mock_url = "http://127.0.0.1:%d" % self.mock.server_address[1]
        self._orig_board = H._GT_PULL_BOARD_DEFAULT
        H._GT_PULL_BOARD_DEFAULT = self.mock_url

        self.pipe = _Pipe()

    def tearDown(self):
        self.pipe.stop()
        self.mock.shutdown()
        self.mock.server_close()
        H._GT_PULL_BOARD_DEFAULT = self._orig_board
        G.STORE = self._store_save
        C.DEST_ROOT = self._dest_save
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_pull_smoke_empty(self):
        code, rj = self.pipe.request("/api/gt/pull", body={})
        self.assertEqual(code, 200)
        self.assertTrue(rj.get("ok"))
        # 轮询直到结束（worker 很快：mock 板返回空清单）
        last = {}
        for _ in range(80):
            _, last = self.pipe.request("/api/gt/pull_status")
            if not last.get("running"):
                break
            time.sleep(0.05)
        self.assertFalse(last.get("running"))
        self.assertEqual(last.get("last_result"), "ok")
        self.assertEqual((last.get("detail") or {}).get("pulled"), [])
        self.assertEqual((last.get("detail") or {}).get("conflicts"), [])

    def test_pull_conflict_guard(self):
        code1, _ = self.pipe.request("/api/gt/pull", body={})
        code2, rj2 = self.pipe.request("/api/gt/pull", body={})
        # 第二次要么 200（若第一次已结束） 要么 409（仍在跑）；不许静默吞掉。
        if code1 == 200 and code2 == 409:
            self.assertIn("已有", rj2.get("error", ""))
        else:
            self.assertEqual(code2, 200)

    def test_pull_unknown_route(self):
        code, rj = self.pipe.request("/api/gt/alias??")
        # 未匹配路由仍走 gt_server.handle 的 unknown-gt-route 分支
        self.assertIn(code, (400, 404))
        self.assertFalse(rj.get("ok", True))

    def test_exports_rejects_traversal(self):
        """FIX-REVIEW-H1: /api/gt/exports?sid=../.. 必 400；former leak。"""
        for bad in ("../..", "..%2f..", "cap_x/../../etc", "cap_/../x", "%2e%2e"):
            code, rj = self.pipe.request("/api/gt/exports?sid=" + bad)
            self.assertEqual(code, 400, "sid %r 应被拒" % bad)
            self.assertFalse(rj.get("ok", True))
        # 合法 sid 仍走正常 listing
        code, rj = self.pipe.request("/api/gt/exports?sid=cap_20261011_120000")
        self.assertEqual(code, 200)


class GtPullBoardModeTest(unittest.TestCase):
    """BOARD_MODE 下 /api/gt/pull 必 403、GET /api/gt/pull_status 仍可读。"""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="gt_pull_boardmode_")
        self._old_env = dict(os.environ)
        os.environ["HUMAN_REPLAY_BOARD_MODE"] = "1"
        os.environ["HR_DEST_ROOT"] = self._tmp
        os.environ["HR_STORE_DIR"] = self._tmp

        for name in ("config", "human_replay_lib", "gt_server"):
            sys.modules.pop(name, None)
        import importlib
        importlib.import_module("config")
        self._H = importlib.import_module("human_replay_lib")

        self._store_save = None

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._old_env)
        for name in ("config", "human_replay_lib", "gt_server"):
            sys.modules.pop(name, None)
        # 拉回原模块，避免污染其它测试
        import importlib
        importlib.import_module("config")
        importlib.import_module("human_replay_lib")
        importlib.import_module("gt_server")
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _request(self, path, body=None):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), self._H.Handler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            data = json.dumps(body or {}).encode() if body is not None else None
            req = urllib.request.Request(
                "http://127.0.0.1:%d%s" % (srv.server_address[1], path),
                data=data, method="POST" if data else None)
            if data:
                req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    return r.status, json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read().decode("utf-8"))
        finally:
            srv.shutdown()
            srv.server_close()

    def test_board_mode_denies_pull(self):
        code, rj = self._request("/api/gt/pull", body={})
        self.assertEqual(code, 403)
        self.assertTrue(rj.get("board_mode"))

    def test_board_mode_pull_status_readonly(self):
        code, rj = self._request("/api/gt/pull_status")
        self.assertEqual(code, 200)
        self.assertFalse(rj.get("running"))


if __name__ == "__main__":
    unittest.main()
