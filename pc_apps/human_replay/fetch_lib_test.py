# -*- coding: utf-8 -*-
"""HR-01 fetch.py 纯逻辑单测（stdlib unittest；Windows 可跑，不触 ssh/板）。

覆盖：
  pick_sessions 的过滤契约（ready && download_requested && !transferred && 路径齐）
  _validate_meta 接受板上真实 28B meta、拒绝旧 16B 契约（README 文档滞后，代码以板为准）
  _sha256_of_points 按 frame 点区实际字节算（允许 bin 尾部额外填充）
  select_job 稳定顺序（created_iso 升序）
"""

import hashlib
import json
import os
import struct
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fetch  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
