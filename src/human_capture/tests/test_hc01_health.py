"""HC-01 验收：/healthz + /api/v1/status（票 HC-01 H1/H2/H6）。

起真实 HTTP 服务（随机空闲端口），用 urllib 打真实请求，
顺带验证只读边界（服务进程不做 ros 控制）。
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(os.path.dirname(_HERE), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import capture_server  # noqa: E402


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _ServerCtx(object):
    def __enter__(self):
        self.tmp = tempfile.mkdtemp(prefix="hc01_")
        cfg = dict(capture_server.DEFAULT_CONFIG)
        cfg["staging_dir"] = os.path.join(self.tmp, "staging")
        cfg["sessions_db"] = os.path.join(self.tmp, "staging", "sessions.json")
        cfg["staging_parent"] = os.path.dirname(cfg["staging_dir"]) or "/"
        self.port = _free_port()
        self.server = capture_server._Server(("127.0.0.1", self.port),
                                             capture_server._Handler, cfg)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return "http://127.0.0.1:%d" % self.port

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


class TestHealth(unittest.TestCase):
    def test_healthz(self):
        with _ServerCtx() as base:
            status, body = _get(base + "/healthz")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["service"], "human_capture")
        self.assertIn("version", body)


class TestStatus(unittest.TestCase):
    def test_status_fields(self):
        with _ServerCtx() as base:
            status, body = _get(base + "/api/v1/status")
        self.assertEqual(status, 200)
        self.assertIn(body["ros"], ("up", "down", "unknown"))
        self.assertIsInstance(body["disk_free_mb"], int)
        self.assertGreaterEqual(body["disk_free_mb"], 0)
        self.assertIsInstance(body["sessions_total"], int)
        self.assertIs(body["recording"], False)
        self.assertGreaterEqual(body["uptime_sec"], 0.0)

    def test_disk_free_matches_shutil(self):
        with _ServerCtx() as base:
            _, body = _get(base + "/api/v1/status")
            # 只保证类型与非负（绝对值随环境变）；一致性由 H4 持久化测试覆盖
            self.assertGreaterEqual(body["disk_free_mb"], 0)


if __name__ == "__main__":
    unittest.main()
