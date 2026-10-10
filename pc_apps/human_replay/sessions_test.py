"""HR-02 offline: actual local HTTP path must never wait on the board."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

import human_replay_lib as H


class OfflineSessionsTest(unittest.TestCase):
    def test_local_and_failed_board_keep_loadable_files(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(H.C, "DEST_ROOT", tmp):
            sid = "cap_20261005_120000"
            directory = Path(tmp) / sid
            directory.mkdir()
            meta = {"duration_sec": 1, "frames": [{"seq": 1}], "created_iso": "2026-10-05"}
            (directory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            (directory / "points.bin").write_bytes(bytes(28))
            (Path(tmp) / "cap_incomplete").mkdir()
            server = H.ThreadingHTTPServer(("127.0.0.1", 0), H.Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = "http://127.0.0.1:%d" % server.server_address[1]
            def get(path):
                with urllib.request.urlopen(base + path, timeout=2) as response:
                    return response.read()
            try:
                with patch.object(H, "_board_get", side_effect=AssertionError("must not query board")) as board:
                    local = json.loads(get("/api/sessions?scope=local"))
                    board.assert_not_called()
                    self.assertEqual([s["sid"] for s in local["sessions"]], [sid])
                    self.assertTrue(local["sessions"][0]["local"])
                    self.assertEqual(get("/api/file?sid=" + sid + "&name=points.bin"), bytes(28))
                    self.assertEqual(json.loads(get("/api/file?sid=" + sid + "&name=meta.json")), meta)
                with patch.object(H, "_board_get", side_effect=TimeoutError("offline")):
                    offline = json.loads(get("/api/sessions"))
                    self.assertEqual(offline["sessions"], local["sessions"])
                    self.assertIn("offline", offline["board_error"])
                with patch.object(H, "_board_get", return_value={"sessions": [
                        {"session_id": sid, "state": "ready"},
                        {"session_id": "cap_remote", "state": "ready"}]}):
                    merged = json.loads(get("/api/sessions"))
                    self.assertEqual(len(merged["sessions"]), 2)
                    self.assertIsNone(merged["board_error"])
                    self.assertTrue(next(s for s in merged["sessions"] if s["sid"] == sid)["local"])
            finally:
                server.shutdown()
                server.server_close()


class RenameTest(unittest.TestCase):
    """会话改名：只写本地 meta.json 的 name 字段（本地别名），不查板、其它字段原样。"""

    def _request(self, base, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(base + path, data=data,
                                     method="POST" if data is not None else "GET")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=2) as response:
            return json.loads(response.read())

    def test_rename_set_clear_and_guards(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(H.C, "DEST_ROOT", tmp):
            sid = "cap_20261007_220000"
            directory = Path(tmp) / sid
            directory.mkdir()
            meta_path = directory / "meta.json"
            meta_path.write_text(json.dumps(
                {"session_id": sid, "duration_sec": 5.0, "frames": [{"seq": 1}],
                 "created_iso": "2026-10-07T22:00:00+08:00"}), encoding="utf-8")
            (directory / "points.bin").write_bytes(bytes(28))
            server = H.ThreadingHTTPServer(("127.0.0.1", 0), H.Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = "http://127.0.0.1:%d" % server.server_address[1]
            try:
                # 1) 设置：trim 落盘，列表和 meta 都能看到，其它字段不动
                out = self._request(base, "/api/rename", {"sid": sid, "name": " 客厅-张三-下蹲 "})
                self.assertTrue(out["ok"], out)
                self.assertEqual(out["name"], "客厅-张三-下蹲")
                written = json.loads(meta_path.read_text(encoding="utf-8"))
                self.assertEqual(written["name"], "客厅-张三-下蹲")
                self.assertEqual(written["duration_sec"], 5.0)
                listed = self._request(base, "/api/sessions?scope=local")
                self.assertEqual(listed["sessions"][0]["name"], "客厅-张三-下蹲")
                # 2) 标注保存不能吞掉 name（写路径保留未知字段）
                out = self._request(base, "/api/save_annotations", {"sid": sid, "annotations": []})
                self.assertTrue(out["ok"], out)
                self.assertEqual(json.loads(meta_path.read_text(encoding="utf-8"))["name"],
                                 "客厅-张三-下蹲")
                # 3) 空名（含全空格）= 恢复默认显示
                out = self._request(base, "/api/rename", {"sid": sid, "name": "   "})
                self.assertTrue(out["ok"])
                self.assertNotIn("name", json.loads(meta_path.read_text(encoding="utf-8")))
                # 4) 护栏：坏 sid / 超长 / 控制字符 → 400；未下载的 sid → 404
                for body in ({"sid": "cap_x", "name": "a"},
                             {"sid": sid, "name": "x" * 61},
                             {"sid": sid, "name": "a\nb"},
                             {"sid": sid, "name": 7}):
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        self._request(base, "/api/rename", body)
                    self.assertEqual(caught.exception.code, 400)
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._request(base, "/api/rename", {"sid": "cap_99999999_000000", "name": "a"})
                self.assertEqual(caught.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()


class RecoverTest(unittest.TestCase):
    """卡死退回：/api/recover 人工入口 + 失败说明实查板端（不编造 extra.error）。"""

    def _request(self, base, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(base + path, data=data,
                                     method="POST" if data is not None else "GET")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=2) as response:
            return json.loads(response.read())

    def test_recover_route_success_status_and_guards(self):
        server = H.ThreadingHTTPServer(("127.0.0.1", 0), H.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_address[1]
        sid = "cap_20261009_120000"
        self.addCleanup(setattr, H, "_sync_recoverable_sid", None)
        try:
            # sync_status 透出可退回标记
            H._sync_recoverable_sid = sid
            st = self._request(base, "/api/sync_status")
            self.assertTrue(st["recoverable"])
            self.assertEqual(st["recover_sid"], sid)
            # 成功退回：调 fetch.recover + 清标记
            with patch("fetch.recover", return_value=(True, "")) as rec:
                out = self._request(base, "/api/recover", {"sid": sid})
                self.assertTrue(out["ok"], out)
                rec.assert_called_once_with(sid)
            self.assertIsNone(H._sync_recoverable_sid)
            # 板端非 transferring：409 + 原因
            with patch("fetch.recover", return_value=(False, "板端状态为 ready，无需退回")):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._request(base, "/api/recover", {"sid": sid})
                self.assertEqual(caught.exception.code, 409)
                payload = json.loads(caught.exception.read().decode("utf-8"))
                self.assertIn("无需退回", payload["error"])
            # 非法 sid：400，不触碰 fetch
            with patch("fetch.recover") as rec:
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._request(base, "/api/recover", {"sid": "cap_x"})
                self.assertEqual(caught.exception.code, 400)
                rec.assert_not_called()
        finally:
            server.shutdown()
            server.server_close()

    def test_sync_failure_note_reports_stuck_clean_and_offline(self):
        with patch.object(H, "_board_get", return_value={"state": "transferring"}):
            note, recoverable = H._sync_failure_note("cap_x")
            self.assertTrue(recoverable)
            self.assertIn("退回重试", note)
        with patch.object(H, "_board_get", return_value={
                "state": "ready", "extra": {"error": "hr01: 下载 points.bin 失败"}}):
            note, recoverable = H._sync_failure_note("cap_x")
            self.assertFalse(recoverable)
            self.assertIn("hr01", note)
        with patch.object(H, "_board_get", side_effect=TimeoutError("offline")):
            note, recoverable = H._sync_failure_note("cap_x")
            self.assertFalse(recoverable)
            self.assertIn("状态查询失败", note)


if __name__ == "__main__":
    unittest.main()
