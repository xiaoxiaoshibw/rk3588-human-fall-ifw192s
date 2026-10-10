"""会话文件 HTTP 直下端点（网页直下扩展，HC-04 的免 SSH 下载路）。

GET/HEAD /api/v1/sessions/<sid>/files/<meta.json|points.bin>：浏览器直接另存
文件本体，供没配 SSH key 的普通 PC 手工放进 Console 的 captures/remote/<sid>/。

起真实 HTTP 服务 + 真实文件（随机空闲端口），覆盖：
- meta/points 200、HEAD 无 body、Content-Disposition/长度
- 未登记/缺文件 404、非法文件名 400、`..` 穿越不出 staging
- download_limit_kbit 限速仍保证内容完整
"""

import http.client
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(os.path.dirname(_HERE), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import capture_server  # noqa: E402


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _ServerCtx(object):
    """与 test_hc01_health 同款 harness，额外暴露 staging 与 seed 助手。"""

    def __init__(self, cfg_overrides=None):
        self.cfg_overrides = cfg_overrides or {}

    def __enter__(self):
        self.tmp = tempfile.mkdtemp(prefix="hc04dl_")
        cfg = dict(capture_server.DEFAULT_CONFIG)
        cfg["staging_dir"] = os.path.join(self.tmp, "staging")
        cfg["sessions_db"] = os.path.join(self.tmp, "staging", "sessions.json")
        cfg["staging_parent"] = os.path.dirname(cfg["staging_dir"]) or "/"
        cfg.update(self.cfg_overrides)
        self.port = _free_port()
        self.server = capture_server._Server(("127.0.0.1", self.port),
                                             capture_server._Handler, cfg)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.staging = cfg["staging_dir"]
        return self

    def seed(self, sid, meta_bytes, bin_bytes):
        d = os.path.join(self.staging, sid)
        os.makedirs(d, exist_ok=True)
        if meta_bytes is not None:
            with open(os.path.join(d, "meta.json"), "wb") as fh:
                fh.write(meta_bytes)
        if bin_bytes is not None:
            with open(os.path.join(d, "points.bin"), "wb") as fh:
                fh.write(bin_bytes)
        self.server.store.upsert({
            "session_id": sid,
            "state": "ready",
            "created_iso": "2026-10-07T00:00:00+08:00",
            "meta_json_path": os.path.join(d, "meta.json"),
            "points_bin_path": os.path.join(d, "points.bin"),
        })

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False


def _req(port, method, path, timeout=10):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request(method, path)
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


class TestSessionFileDownload(unittest.TestCase):
    def test_meta_points_head(self):
        with _ServerCtx() as ctx:
            meta = b'{"format": "human_capture_session"}\n'
            points = bytes(range(256)) * 4
            ctx.seed("cap_20261007_000001", meta, points)

            status, headers, body = _req(
                ctx.port, "GET", "/api/v1/sessions/cap_20261007_000001/files/meta.json")
            self.assertEqual(status, 200)
            self.assertEqual(body, meta)
            self.assertIn("attachment", headers.get("Content-Disposition", ""))
            self.assertIn("application/json", headers.get("Content-Type", ""))
            self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")

            status, headers, body = _req(
                ctx.port, "GET", "/api/v1/sessions/cap_20261007_000001/files/points.bin")
            self.assertEqual(status, 200)
            self.assertEqual(body, points)
            self.assertEqual(int(headers["Content-Length"]), len(points))
            self.assertIn("application/octet-stream", headers.get("Content-Type", ""))

            status, headers, body = _req(
                ctx.port, "HEAD", "/api/v1/sessions/cap_20261007_000001/files/points.bin")
            self.assertEqual(status, 200)
            self.assertEqual(int(headers["Content-Length"]), len(points))
            self.assertEqual(body, b"")

    def test_missing_and_bad_requests(self):
        with _ServerCtx() as ctx:
            ctx.seed("cap_20261007_000002", b"{}", None)  # 只有 meta，没有 bin

            status, _, body = _req(
                ctx.port, "GET", "/api/v1/sessions/cap_20261007_000002/files/points.bin")
            self.assertEqual(status, 404)
            self.assertIn(b"file_missing", body)

            status, _, _ = _req(
                ctx.port, "GET", "/api/v1/sessions/cap_20261007_000003/files/meta.json")
            self.assertEqual(status, 404)  # 目录/文件都不存在

            status, _, body = _req(
                ctx.port, "GET", "/api/v1/sessions/cap_20261007_000002/files/sessions.json")
            self.assertEqual(status, 400)
            self.assertIn(b"bad_name", body)

            # `..` 组合被 realpath 拦截，绝不越过 staging
            status, _, _ = _req(ctx.port, "GET", "/api/v1/sessions/../files/meta.json")
            self.assertEqual(status, 404)

    def test_throttle_keeps_content(self):
        with _ServerCtx({"download_limit_kbit": 1600}) as ctx:  # 200 KB/s
            payload = os.urandom(100 * 1024)
            ctx.seed("cap_20261007_000004", b"{}", payload)
            t0 = time.monotonic()
            status, _, body = _req(
                ctx.port, "GET", "/api/v1/sessions/cap_20261007_000004/files/points.bin")
            elapsed = time.monotonic() - t0
            self.assertEqual(status, 200)
            self.assertEqual(body, payload)
            # 100KB @ 200KB/s ≈ 0.5s；下限放宽防计时抖动
            self.assertGreaterEqual(elapsed, 0.25)


if __name__ == "__main__":
    unittest.main()
