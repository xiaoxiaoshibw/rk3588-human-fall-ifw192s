"""HC-01 验收 H4：持久化——杀进程重起、损坏文件拒绝启动、HTTP PATCH 409/404。"""

import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
_SCRIPTS = os.path.join(_PKG, "scripts")
for p in (_PKG, _SCRIPTS):
    if p not in sys.path:
        sys.path.insert(0, p)

from core.session_store import SessionStore, StoreError  # noqa: E402
import capture_server  # noqa: E402
from test_hc01_health import _ServerCtx, _get  # noqa: E402


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hc01_p_")
        self.db = os.path.join(self.tmp, "sessions.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_reopen_keeps_sessions(self):
        s1 = SessionStore(self.db)
        s1.upsert({"session_id": "cap_a", "state": "ready",
                   "created_iso": "2026-10-02T10:00:00+08:00"})
        del s1  # 模拟进程退出
        s2 = SessionStore(self.db)
        self.assertEqual(s2.get("cap_a")["state"], "ready")

    def test_corrupt_refuses_start(self):
        with open(self.db, "w", encoding="utf-8") as fh:
            fh.write("{not json at all")
        with self.assertRaises(StoreError):
            SessionStore(self.db)

    def test_wrong_shape_refuses_start(self):
        with open(self.db, "w", encoding="utf-8") as fh:
            json.dump({"sessions": "not-a-list"}, fh)
        with self.assertRaises(StoreError):
            SessionStore(self.db)


def _http(method, url, body=None):
    req = urllib.request.Request(url, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class TestHttpContract(unittest.TestCase):
    def test_patch_illegal_transition_409(self):
        with _ServerCtx() as base:
            _http("POST", base + "/api/v1/sessions",
                  {"session_id": "cap_x", "state": "recording",
                   "created_iso": "2026-10-02T11:00:00+08:00"})
            code, body = _http("PATCH", base + "/api/v1/sessions/cap_x",
                               {"state": "ready"})
        self.assertEqual(code, 409)
        self.assertEqual(body["error"]["code"], "bad_transition")

    def test_patch_missing_session_404(self):
        with _ServerCtx() as base:
            code, _ = _http("PATCH", base + "/api/v1/sessions/cap_ghost",
                            {"state": "ready"})
        self.assertEqual(code, 404)

    def test_extra_whitelist_blocks_unknown_keys(self):
        with _ServerCtx() as base:
            _http("POST", base + "/api/v1/sessions",
                  {"session_id": "cap_y", "state": "extracting",
                   "created_iso": "2026-10-02T11:05:00+08:00"})
            _http("PATCH", base + "/api/v1/sessions/cap_y",
                  {"state": "failed",
                   "extra": {"error": "boom", "injected_key": "nope"}})
            _, s = _get(base + "/api/v1/sessions/cap_y")
        self.assertEqual(s["error"], "boom")
        self.assertNotIn("injected_key", s)

    def test_patch_extra_only_keeps_state(self):
        with _ServerCtx() as base:
            _http("POST", base + "/api/v1/sessions",
                  {"session_id": "cap_z", "state": "ready",
                   "created_iso": "2026-10-02T11:06:00+08:00"})
            code, body = _http("PATCH", base + "/api/v1/sessions/cap_z",
                               {"extra": {"download_requested": True}})
            _, s = _get(base + "/api/v1/sessions/cap_z")
        self.assertEqual(code, 200)
        self.assertEqual(body["state"], "ready")
        self.assertTrue(s["download_requested"])


if __name__ == "__main__":
    unittest.main()
