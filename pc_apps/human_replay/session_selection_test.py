"""真实本地 HTTP 契约；所有数据写入临时目录，板端请求禁止。"""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request
import human_replay_lib as H


class SessionSelectionTest(unittest.TestCase):
    def test_complete_missing_bin_empty_invalid_and_both_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(H.C, "DEST_ROOT", tmp):
            root = Path(tmp)
            good = ["cap_20261002_223757", "cap_20261009_181716"]
            cases = good + ["cap_20261010_010000", "cap_20261010_020000", "cap_20261010_030000", "cap_20261010_040000", "cap_20261010_050000"]
            for sid in cases:
                d = root / sid
                d.mkdir()
                (d / "meta.json").write_text(json.dumps({"session_id":sid,"frames":[{"seq":1,"offset_points":0,"count_points":1}]}),encoding="utf-8")
                (d / "points.bin").write_bytes(bytes(28))
            (root / cases[2] / "points.bin").unlink()  # meta-only
            (root / cases[3] / "points.bin").write_bytes(b"")
            (root / cases[4] / "meta.json").write_text("{}",encoding="utf-8")
            (root / cases[5] / "meta.json").write_text("invalid",encoding="utf-8")
            (root / cases[6] / "points.bin").write_bytes(bytes(27))
            server = H.ThreadingHTTPServer(("127.0.0.1",0),H.Handler)
            thread = threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                with patch.object(H,"_board_get",side_effect=AssertionError("board forbidden")) as board:
                    for endpoint in ("/api/sessions?scope=local","/api/leveling/sessions"):
                        with opener.open("http://127.0.0.1:%d%s" % (server.server_address[1],endpoint),timeout=2) as response:
                            data=json.load(response)
                        self.assertEqual(sorted(s["sid"] for s in data["sessions"]),good)
                    board.assert_not_called()
                    self.assertEqual(set(H._local_sessions(tmp)),set(good))
                    for sid in good:
                        for name in ("meta.json","points.bin"):
                            with opener.open("http://127.0.0.1:%d/api/file?sid=%s&name=%s" % (server.server_address[1],sid,name),timeout=2) as response:
                                self.assertEqual(response.read(),(root/sid/name).read_bytes())
            finally:
                server.shutdown();server.server_close();thread.join()
            for sid in good:
                (root/sid/"points.bin").unlink()
            self.assertEqual(H._local_sessions(tmp),{})


if __name__ == "__main__": unittest.main()
