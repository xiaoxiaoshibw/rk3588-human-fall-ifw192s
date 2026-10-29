# -*- coding: utf-8 -*-
"""HR-01 fetch.py 单测（stdlib unittest；Windows 可跑，不依赖 SSH）。

覆盖：
  pick_sessions 的过滤契约（ready && download_requested && !transferred && 路径齐）
  _validate_meta 接受板上真实 28B meta、拒绝旧 16B 契约（README 文档滞后，代码以板为准）
  _sha256_of_points 按 frame 点区实际字节算（允许 bin 尾部额外填充）
  select_job 稳定顺序（created_iso 升序）
  transfer_one 失败必退回 ready（不留 transferring 卡死）
  recover 把卡在 transferring 的会话退回 ready（面板「退回重试」）
  _http_size/_http_download 对真实 HTTP（本机环回）的流式与 Content-Length 校验
  process_session 与真实 capture_server /files 端点端到端对拉
"""

import hashlib
import http.server
import json
import os
import struct
import sys
import tempfile
import threading
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fetch  # noqa: E402

# 端到端测试要用板端 capture_server 本体（同仓 src/，不用部署到板）
_CAPTURE_SCRIPTS = os.path.normpath(
    os.path.join(_HERE, "..", "..", "src", "human_capture", "scripts"))
if _CAPTURE_SCRIPTS not in sys.path:
    sys.path.insert(0, _CAPTURE_SCRIPTS)

import capture_server  # noqa: E402


def _meta(frames, stride=28, fields=None, total_bytes=None):
    fields = fields or ["x", "y", "z", "intensity", "ring", "timestamp"]
    meta = {
        "format": "human_capture_session",
        "format_version": 1,
        "point_file": "points.bin",
        "point_stride_bytes": stride,
        "point_layout": {"endian": "little", "stride_bytes": stride, "fields": fields},
        "frames": frames,
        "total_points": sum(f["count_points"] for f in frames),
    }
    if total_bytes is not None:
        meta["_bin_size"] = total_bytes
    return meta


def _frames(pairs):
    return [{"offset_points": o, "count_points": c, "seq": i + 1,
             "stamp_sec": 0, "stamp_nanosec": 0} for i, (o, c) in enumerate(pairs)]


def _write_bin(path, n_points, stride=28, pad_extra=0):
    payload = b"\x01" * (stride * n_points)
    if pad_extra:
        payload += b"\x00" * pad_extra
    with open(path, "wb") as fh:
        fh.write(payload)
    return payload


class TestPick(unittest.TestCase):

    def _s(self, sid, state="ready", dl=True, tr=False, ts="2026-10-02T00:00:00+08:00", with_paths=True):
        s = {"session_id": sid, "state": state, "created_iso": ts,
             "download_requested": dl, "transferred": tr}
        if with_paths:
            s["meta_json_path"] = "/x/%s/meta.json" % sid
            s["points_bin_path"] = "/x/%s/points.bin" % sid
        return s

    def test_filters(self):
        sessions = {"sessions": [
            self._s("a_ok"),
            self._s("b_state_extracting", state="extracting"),
            self._s("c_no_download", dl=False),
            self._s("d_done", tr=True),
            self._s("e_missing_paths", with_paths=False),
            self._s("f_dl_missing_ok", dl=None),  # None 视为未请求
            self._s("g_transferred_none_ok", tr=None),
        ]}
        got = fetch.pick_sessions(sessions)
        self.assertEqual([s["session_id"] for s in got], ["a_ok", "g_transferred_none_ok"])

    def test_order_stable_oldest_first(self):
        sessions = {"sessions": [
            self._s("z_new", ts="2026-10-02T10:00:00+08:00"),
            self._s("a_old", ts="2026-10-01T10:00:00+08:00"),
        ]}
        got = fetch.pick_sessions(sessions)
        self.assertEqual([s["session_id"] for s in got], ["a_old", "z_new"])


class TestMetaValidate(unittest.TestCase):

    def test_accepts_real_board_layout(self):
        with tempfile.TemporaryDirectory() as d:
            meta = _meta(_frames([(0, 2)]), total_bytes=56)
            bin_path = os.path.join(d, "points.bin")
            _write_bin(bin_path, 2)
            used = fetch._validate_meta(meta, "meta.json", os.path.getsize(bin_path))
            self.assertEqual(used, 56)

    def test_rejects_old_16b_layout(self):
        with tempfile.TemporaryDirectory() as d:
            meta = _meta(_frames([(0, 2)]), stride=16,
                         fields=["x", "y", "z", "intensity"], total_bytes=32)
            bin_path = os.path.join(d, "points.bin")
            _write_bin(bin_path, 2, stride=16)
            with self.assertRaises(ValueError):
                fetch._validate_meta(meta, "meta.json", os.path.getsize(bin_path))

    def test_rejects_frames_beyond_bin(self):
        meta = _meta(_frames([(0, 100)]))
        with self.assertRaises(ValueError):
            fetch._validate_meta(meta, "meta.json", 28 * 10)


class TestSha256PointsRegion(unittest.TestCase):

    def test_region_ignores_trailing_pad(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "points.bin")
            payload = _write_bin(path, 3, pad_extra=128)
            got = fetch._sha256_of_points(path, 28 * 3, 3)
            want = hashlib.sha256(payload[:28 * 3]).hexdigest()
            self.assertEqual(got, want)


class _FakeHTTP(object):
    def __init__(self):
        self.calls = []

    def __call__(self, method, path, body=None, timeout=None):
        self.calls.append((method, path, body))
        return {}


class TestTransferOneReverts(unittest.TestCase):
    """失败路径必须 PATCH 回 ready+hr01（旧实现异常时把会话卡死在 transferring）。"""

    def test_unexpected_exception_reverts(self):
        def boom(*a, **kw):
            raise RuntimeError("boom")

        http = _FakeHTTP()
        with tempfile.TemporaryDirectory() as d:
            ok = fetch.transfer_one({"session_id": "cap_x", "state": "ready"},
                                    http, boom, boom, d, log=lambda m: None)
        self.assertFalse(ok)
        self.assertEqual(http.calls[0],
                         ("PATCH", "/api/v1/sessions/cap_x", {"state": "transferring"}))
        method, path, body = http.calls[-1]
        self.assertEqual((method, path), ("PATCH", "/api/v1/sessions/cap_x"))
        self.assertEqual(body["state"], "ready")
        self.assertIn("hr01", body["extra"]["error"])


class _LoopbackHandler(http.server.BaseHTTPRequestHandler):
    files = {}
    lie_extra = 0
    status = 200

    def _respond(self, head_only):
        if self.status == 204:
            self.send_response(204)
            self.end_headers()
            return
        data = self.files.get(self.path.rsplit("/", 1)[-1])
        if data is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(data) + self.lie_extra))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def do_GET(self):
        self._respond(False)

    def do_HEAD(self):
        self._respond(True)

    def log_message(self, *a):
        pass


class TestHttpDataPlaneLoopback(unittest.TestCase):
    """_http_size/_http_download 对真实 HTTP（本机环回）：流式 + 长度校验。"""

    def _serve(self, files, lie_extra=0):
        handler = type("H", (_LoopbackHandler,),
                       {"files": files, "lie_extra": lie_extra})
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)   # 注意 LIFO：先注册 close，后注册 shutdown
        self.addCleanup(srv.shutdown)
        old = fetch.C.BOARD_URL
        fetch.C.BOARD_URL = "http://127.0.0.1:%d" % srv.server_address[1]
        self.addCleanup(setattr, fetch.C, "BOARD_URL", old)

    def test_download_ok_and_size(self):
        self._serve({"points.bin": b"\x01\x02\x03"})
        self.assertEqual(fetch._http_size("cap_x", "points.bin"), 3)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "points.bin.part")
            self.assertTrue(fetch._http_download("cap_x", "points.bin", p))
            with open(p, "rb") as fh:
                self.assertEqual(fh.read(), b"\x01\x02\x03")

    def test_truncated_body_rejected(self):
        # Content-Length 谎报（比实际多）：连接关闭后字节数对不上 → 拒收
        self._serve({"points.bin": b"\x01\x02"}, lie_extra=16)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "points.bin.part")
            self.assertFalse(fetch._http_download("cap_x", "points.bin", p))

    def test_empty_204_is_diagnosed_without_creating_file(self):
        self._serve({"points.bin": b"unused"})
        with mock.patch.object(_LoopbackHandler, 'status', 204), tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'points.bin.part')
            logs = []
            self.assertFalse(fetch._http_download('cap_x', 'points.bin', path, log=logs.append))
            self.assertFalse(os.path.exists(path))
            self.assertIn('status=204', logs[0])


class TestAgainstCaptureServer(unittest.TestCase):
    """与真实 capture_server（本机环回）对拉：端到端 ready→transferred。"""

    def _start_board(self, tmp):
        cfg = dict(capture_server.DEFAULT_CONFIG)
        cfg["staging_dir"] = os.path.join(tmp, "staging")
        cfg["sessions_db"] = os.path.join(cfg["staging_dir"], "sessions.json")
        cfg["staging_parent"] = tmp
        cfg["download_limit_kbit"] = 0          # 测试不限速
        srv = capture_server._Server(("127.0.0.1", 0), capture_server._Handler, cfg)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)   # 注意 LIFO：先注册 close，后注册 shutdown
        self.addCleanup(srv.shutdown)
        old = fetch.C.BOARD_URL
        fetch.C.BOARD_URL = "http://127.0.0.1:%d" % srv.server_address[1]
        self.addCleanup(setattr, fetch.C, "BOARD_URL", old)
        return srv, cfg

    def test_process_session_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            srv, cfg = self._start_board(tmp)
            sid = "cap_20261007_120000"
            d = os.path.join(cfg["staging_dir"], sid)
            os.makedirs(d)
            with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
                json.dump(_meta(_frames([(0, 3)])), fh)
            _write_bin(os.path.join(d, "points.bin"), 3)
            srv.store.upsert({"session_id": sid, "state": "ready",
                              "created_iso": "2026-10-07T12:00:00+08:00"})
            dest = os.path.join(tmp, "dest")
            os.makedirs(dest)
            ok = fetch.process_session(sid, dest_root=dest, log=lambda m: None)
            self.assertTrue(ok)
            self.assertTrue(os.path.isfile(os.path.join(dest, sid, "meta.json")))
            self.assertTrue(os.path.isfile(os.path.join(dest, sid, "points.bin")))
            st = srv.store.get(sid)
            self.assertEqual(st["state"], "transferred")
            self.assertTrue(st.get("transferred"))

    def test_system_downloader_proxy_cannot_intercept_board_transfer(self):
        """模拟 IDM 全局代理返回 204；控制面/HEAD/文件下载必须全部直连。"""
        handler = type('DownloaderProxy', (_LoopbackHandler,), {'status': 204})
        proxy = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=proxy.serve_forever, daemon=True).start()
        self.addCleanup(proxy.server_close)
        self.addCleanup(proxy.shutdown)
        opener = fetch.urllib.request.build_opener(fetch.urllib.request.ProxyHandler(
            {'http': 'http://127.0.0.1:%d' % proxy.server_port}))
        with mock.patch.object(fetch.urllib.request, '_opener', opener), \
             mock.patch.object(fetch.urllib.request, 'proxy_bypass', return_value=False):
            with fetch.urllib.request.urlopen('http://device.invalid/points.bin') as resp:
                self.assertEqual(resp.status, 204)
            self.test_process_session_end_to_end()

    def test_fail_reverts_to_ready_not_stuck(self):
        # 已登记 ready 但文件不存在：HEAD 拿不到大小 → 退回 ready + hr01 错误
        with tempfile.TemporaryDirectory() as tmp:
            srv, cfg = self._start_board(tmp)
            sid = "cap_20261007_120001"
            srv.store.upsert({"session_id": sid, "state": "ready",
                              "created_iso": "2026-10-07T12:00:01+08:00"})
            dest = os.path.join(tmp, "dest")
            os.makedirs(dest)
            ok = fetch.process_session(sid, dest_root=dest, log=lambda m: None)
            self.assertFalse(ok)
            st = srv.store.get(sid)
            self.assertEqual(st["state"], "ready")
            self.assertIn("hr01", st.get("error", ""))

    def test_process_session_copies_already_transferred(self):
        # 板端已 transferred 但本机没有（别的 PC 拉过/本地删过再要）：只读复制。
        # 旧行为 PATCH transferring 会被状态机 409 拒（transferred 只能转 purged）。
        with tempfile.TemporaryDirectory() as tmp:
            srv, cfg = self._start_board(tmp)
            sid = "cap_20261007_120002"
            d = os.path.join(cfg["staging_dir"], sid)
            os.makedirs(d)
            with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
                json.dump(_meta(_frames([(0, 3)])), fh)
            _write_bin(os.path.join(d, "points.bin"), 3)
            srv.store.upsert({"session_id": sid, "state": "transferred",
                              "created_iso": "2026-10-07T12:00:02+08:00",
                              "transferred": True})
            dest = os.path.join(tmp, "dest")
            os.makedirs(dest)
            ok = fetch.process_session(sid, dest_root=dest, log=lambda m: None)
            self.assertTrue(ok)
            self.assertTrue(os.path.isfile(os.path.join(dest, sid, "meta.json")))
            self.assertTrue(os.path.isfile(os.path.join(dest, sid, "points.bin")))
            st = srv.store.get(sid)
            self.assertEqual(st["state"], "transferred")
            self.assertNotIn("error", st)   # 只读复制没有 hr01 回退痕迹


    def test_recover_unstucks_transferring(self):
        # 客户端中断留下的 transferring 卡死：recover 退回 ready；已非 transferring 拒绝
        with tempfile.TemporaryDirectory() as tmp:
            srv, cfg = self._start_board(tmp)
            sid = "cap_20261007_120003"
            srv.store.upsert({"session_id": sid, "state": "ready",
                              "created_iso": "2026-10-07T12:00:03+08:00"})
            srv.store.transition(sid, "transferring")
            ok, reason = fetch.recover(sid)
            self.assertTrue(ok, reason)
            self.assertEqual(srv.store.get(sid)["state"], "ready")
            ok, reason = fetch.recover(sid)
            self.assertFalse(ok)
            self.assertIn("无需退回", reason)


if __name__ == "__main__":
    unittest.main()
