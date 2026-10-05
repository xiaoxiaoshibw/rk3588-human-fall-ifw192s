"""HR-02 offline: actual local HTTP path must never wait on the board."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
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


if __name__ == "__main__":
    unittest.main()
