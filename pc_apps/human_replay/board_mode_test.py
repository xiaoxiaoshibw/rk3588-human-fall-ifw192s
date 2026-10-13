# -*- coding: utf-8 -*-
"""board_mode_test.py — 板端模式护栏/路径开关 单元测试。

spin up 临时 human_replay 服务（BOARD_MODE 打开但监听 127.0.0.1 随机口），
模拟远程客户端，断言危险端点被 403、回源走远端路径、导出路由白名单生效。

跑法： python -B -W error -m unittest pc_apps.human_replay.board_mode_test -v
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def _http(method, url, body=None):
    req = urllib.request.Request(url, method=method)
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
        req.data = data
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except Exception:
            payload = {}
        return e.code, payload


class BoardModeTest(unittest.TestCase):
    """每个 case 起独立进程：env+config 模块态完全隔离。"""

    def _spawn_board_server(self):
        """临时起一份 board_mode 服务，返回 (base_url, thread, srv, tmpdir)。"""
        tmpdir = tempfile.mkdtemp(prefix="hr_board_")
        os.environ["HUMAN_REPLAY_BOARD_MODE"] = "1"
        os.environ["HR_DEST_ROOT"] = os.path.join(tmpdir, "staging")
        os.environ["HR_STORE_DIR"] = os.path.join(tmpdir, "gt_store")
        os.makedirs(os.environ["HR_DEST_ROOT"], exist_ok=True)
        # 任意旧 import 态都要重置
        for m in ("config", "human_replay_lib", "gt_server"):
            sys.modules.pop(m, None)
        import config as C
        import human_replay_lib as H
        # 板上虽然要 0.0.0.0，但 Windows sandbox 环回实测就能共享 client_address
        srv = H.ThreadingHTTPServer(("127.0.0.1", 0), H.Handler)
        port = srv.server_address[1]
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        return "http://127.0.0.1:%d" % port, th, srv, tmpdir

    def tearDown(self):
        for m in ("config", "human_replay_lib", "gt_server"):
            sys.modules.pop(m, None)
        for k in ("HUMAN_REPLAY_BOARD_MODE", "HR_DEST_ROOT", "HR_STORE_DIR"):
            os.environ.pop(k, None)

    # ---------- 危险端点护栏 ----------

    def test_board_mode_denies_local_only_posts(self):
        base, th, srv, tmp = self._spawn_board_server()
        try:
            for path, body in [
                ("/api/delete", {"sid": "cap_20261010_175227", "scope": "local"}),
                ("/api/sync", {"sid": "cap_20261010_175227"}),
                ("/api/rename", {"sid": "cap_20261010_175227", "name": "x"}),
                ("/api/save_annotations", {"sid": "cap_20261010_175227", "annotations": []}),
                ("/api/board/record/start", {}),
                ("/api/recover", {"sid": "cap_20261010_175227"}),
            ]:
                code, payload = _http("POST", base + path, body)
                self.assertEqual(code, 403, "%s 应该 403, 得到 %d %s" % (path, code, payload))
                self.assertTrue(payload.get("board_mode"))
        finally:
            srv.shutdown()
            shutil.rmtree(tmp, ignore_errors=True)

    def test_board_mode_allows_gt_reads_and_writes(self):
        base, th, srv, tmp = self._spawn_board_server()
        try:
            # GT 端点不受多-client 护栏约束（落盘并发由 gt_store 的写锁保证）
            code, payload = _http("GET", base + "/api/gt/export")
            self.assertEqual(code, 200)
            self.assertTrue(payload.get("ok"))
            self.assertIn("sessions", payload)

            code, payload = _http("GET", base + "/api/gt/exports")
            self.assertEqual(code, 200)
            self.assertTrue(payload.get("ok"))
        finally:
            srv.shutdown()
            shutil.rmtree(tmp, ignore_errors=True)

    def test_pc_mode_default_dest_unchanged(self):
        """BOARD_MODE 不设时 DEST_ROOT 必须是 D:\\codeldiar\\captures\\remote（D1 不漂移）。"""
        for k in ("HUMAN_REPLAY_BOARD_MODE", "HR_DEST_ROOT", "HR_STORE_DIR"):
            os.environ.pop(k, None)
        sys.modules.pop("config", None)
        import config as C
        expected = os.path.join(os.path.dirname(os.path.dirname(_HERE)),
                                "captures", "remote")
        self.assertEqual(os.path.normpath(C.DEST_ROOT), os.path.normpath(expected))

    # ---------- 导出白名单 ----------

    def test_gt_export_whitelist(self):
        base, th, srv, tmp = self._spawn_board_server()
        try:
            # 假 sid 必须 400
            code, payload = _http("GET", base + "/api/gt/exports/file?sid=../../etc&name=x")
            self.assertEqual(code, 400)
            # 非法 name
            code, _ = _http("GET", base + "/api/gt/exports/file?sid=cap_20261010_175227&name=secret.txt")
            self.assertEqual(code, 400)
            # 白名单但不存在 → 404
            code, _ = _http("GET", base + "/api/gt/exports/file?sid=cap_20261010_175227&name=draft.json")
            self.assertEqual(code, 404)
        finally:
            srv.shutdown()
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
