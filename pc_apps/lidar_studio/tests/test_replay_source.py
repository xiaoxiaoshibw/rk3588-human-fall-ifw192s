import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

STUDIO_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = STUDIO_DIR.parents[1]
if str(STUDIO_DIR) not in sys.path:
    sys.path.insert(0, str(STUDIO_DIR))

from protocol import FLAG_TARGET_CORE, unpack_frame  # noqa: E402
from replay_source import (  # noqa: E402
    ReplayManager,
    assert_safe_cache_dir,
    get_shared_grid,
    validate_session_meta,
    validate_sid,
)


class TestReplaySource(unittest.TestCase):
    def test_cache_dir_never_writes_into_data_or_captures(self):
        for bad in (
            REPO_ROOT / "data",
            REPO_ROOT / "data" / "sessions",
            REPO_ROOT / "captures",
            REPO_ROOT / "captures" / "remote",
        ):
            with self.assertRaises(ValueError):
                assert_safe_cache_dir(bad)

        good = STUDIO_DIR / ".cache"
        self.assertEqual(assert_safe_cache_dir(good), good.resolve())

    def test_reject_bad_session_and_traversal(self):
        sessions_root = REPO_ROOT / "data" / "sessions"
        for bad_sid in ("../etc", ".joint_fetch_staging", "nonexistent_sid_xyz", "a/b"):
            with self.assertRaises(ValueError):
                validate_sid(bad_sid, sessions_root)

        # 缺 meta.json 的真实目录 cap_20261017_141348 应被拒绝
        missing_meta = sessions_root / "cap_20261017_141348"
        if missing_meta.is_dir():
            with self.assertRaises(ValueError):
                validate_session_meta(missing_meta)

        # 构造截断 points.bin 的假会话
        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp) / "bad_sess"
            sdir.mkdir()
            meta = {
                "format": "human_capture_session",
                "format_version": 1,
                "point_file": "points.bin",
                "point_stride_bytes": 28,
                "point_layout": {
                    "fields": ["x", "y", "z", "intensity", "ring", "timestamp"],
                    "dtypes": ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
                    "stride_bytes": 28,
                    "endian": "little",
                    "pad_offsets_bytes": [18, 24],
                },
                "extraction": {"tool": "bag2session/0.1.0", "point_step_bytes_src": 26, "dropped_frames": 0},
                "time_domain": "device_stamp_s_unanchored",
                "sensor": {"frame_id": "innolidar"},
                "total_points": 10,
                "total_dropped_points": 0,
                "frames": [
                    {
                        "seq": 1,
                        "offset_points": 0,
                        "count_points": 10,
                        "stamp_sec": 100,
                        "stamp_nanosec": 0,
                        "dropped_points": 0,
                    }
                ],
            }
            (sdir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            (sdir / "points.bin").write_bytes(b"\x00" * 28)  # 应为 280 字节
            with self.assertRaises(ValueError):
                validate_session_meta(sdir)

    def test_synthetic_session_cache_and_decimation(self):
        grid, _, _ = get_shared_grid()
        az_rad = np.radians(grid.azimuth_deg)
        el_rad = np.radians(grid.elevation_deg)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            s_root = tmp_root / "sessions"
            c_root = tmp_root / "cache"
            s_dir = s_root / "syn_test_01"
            s_dir.mkdir(parents=True)

            # 从标定方向生成 24 帧合法点云（满足 QuantileBackground min_observations=20）
            dtype = np.dtype(
                [
                    ("x", "<f4"),
                    ("y", "<f4"),
                    ("z", "<f4"),
                    ("intensity", "<f4"),
                    ("ring", "<u2"),
                    ("pad0", "<u2"),
                    ("timestamp", "<f4"),
                    ("pad1", "<u4"),
                ]
            )
            rings, cols = np.indices(grid.shape)
            r_base = np.full(grid.shape, 4.5, dtype=np.float64)
            cx = r_base * np.cos(el_rad) * np.cos(az_rad)
            cy = r_base * np.cos(el_rad) * np.sin(az_rad)
            cz = r_base * np.sin(el_rad)

            frames_meta = []
            offset = 0
            bin_chunks = []
            n_pts = r_base.size
            for i in range(24):
                arr = np.zeros(n_pts, dtype=dtype)
                arr["x"] = cx.ravel().astype("<f4")
                arr["y"] = cy.ravel().astype("<f4")
                arr["z"] = cz.ravel().astype("<f4")
                arr["intensity"] = 500.0
                arr["ring"] = rings.ravel().astype("<u2")
                arr["timestamp"] = 100.0 + i * 0.1
                bin_chunks.append(arr.tobytes())
                frames_meta.append(
                    {
                        "seq": i + 1,
                        "offset_points": offset,
                        "count_points": n_pts,
                        "stamp_sec": 100 + i // 10,
                        "stamp_nanosec": (i % 10) * 100_000_000,
                        "dropped_points": 0,
                        "bag_time_sec": 1700000000.0 + i * 0.1,
                    }
                )
                offset += n_pts

            (s_dir / "points.bin").write_bytes(b"".join(bin_chunks))
            meta = {
                "format": "human_capture_session",
                "format_version": 1,
                "point_file": "points.bin",
                "point_stride_bytes": 28,
                "point_layout": {
                    "fields": ["x", "y", "z", "intensity", "ring", "timestamp"],
                    "dtypes": ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
                    "stride_bytes": 28,
                    "endian": "little",
                    "pad_offsets_bytes": [18, 24],
                },
                "extraction": {"tool": "bag2session/0.1.0", "point_step_bytes_src": 26, "dropped_frames": 0},
                "time_domain": "device_stamp_s_unanchored",
                "sensor": {"frame_id": "innolidar"},
                "total_points": offset,
                "total_dropped_points": 0,
                "frames": frames_meta,
            }
            (s_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

            mgr = ReplayManager(sessions_root=s_root, cache_dir=c_root)
            try:
                listed = mgr.list_sessions()
                self.assertEqual(len(listed), 1)
                self.assertFalse(listed[0]["cached"])
                self.assertFalse(listed[0]["has_camera"])

                sess = mgr.open_session("syn_test_01")
                self.assertEqual(sess.frame_count, 24)
                pkt1 = sess.get_packed_frame(0, decimation=1)
                pkt2 = sess.get_packed_frame(0, decimation=2)
                u1 = unpack_frame(pkt1)
                u2 = unpack_frame(pkt2)
                self.assertGreater(len(u1["xyz"]), len(u2["xyz"]))
                self.assertEqual(u2["range_mm"].shape, grid.shape)
                self.assertEqual(u2["state"]["camera"]["available"], False)

                # 确认缓存文件已落地于 c_root，再次打开应直接命中缓存
                mgr.close_all()
                listed2 = mgr.list_sessions()
                self.assertTrue(listed2[0]["cached"])
                stages = []
                sess2 = mgr.open_session("syn_test_01", progress_cb=lambda st, c, t, m: stages.append(st))
                self.assertEqual(stages, ["cache_hit"])
                self.assertEqual(sess2.frame_count, 24)
            finally:
                mgr.close_all()

    def test_houdao_parity_against_r2_ledger(self):
        houdao_dir = REPO_ROOT / "data" / "sessions" / "cap_20261028_houdao"
        ledger_p = (
            REPO_ROOT
            / "docs"
            / "evidence"
            / "2026-11-24_rk3588_human_phys_v1_r2"
            / "frames"
            / "cap_20261028_houdao.jsonl"
        )
        if not houdao_dir.is_dir() or not ledger_p.is_file():
            self.skipTest("houdao session or r2 ledger missing")

        expected_rows = {
            row["frame"]: row
            for row in (json.loads(ln) for ln in ledger_p.read_text(encoding="utf-8").splitlines() if ln.strip())
        }

        mgr = ReplayManager(sessions_root=REPO_ROOT / "data" / "sessions", cache_dir=STUDIO_DIR / ".cache")
        try:
            sess = mgr.open_session("cap_20261028_houdao")
            self.assertEqual(sess.frame_count, 169)
            for fidx, exp in expected_rows.items():
                st = sess.states[fidx]
                phys = st["human_physical_v1"]
                tb = phys["target_belief"]
                rec = phys["recovery"]
                self.assertEqual(st["fall_status"], exp["fall_state"], f"frame {fidx}")
                self.assertEqual(st["track_id"], exp["tid"], f"frame {fidx}")
                self.assertEqual(tb["belief_state"], exp["belief_state"], f"frame {fidx}")
                self.assertAlmostEqual(tb["log_odds"], exp["belief_log_odds"], places=4, msg=f"frame {fidx}")
                self.assertEqual(rec["status"], exp["recovery_status"], f"frame {fidx}")
                self.assertEqual(rec["core_count"], exp["core_points"], f"frame {fidx}")
                self.assertEqual(rec["added_count"], exp["recovery_added"], f"frame {fidx}")

            # 检查跌倒帧 83 打包后完整保留全部目标核心点（不受降采样损失）
            pkt = sess.get_packed_frame(83, decimation=2)
            unpacked = unpack_frame(pkt)
            core_count_in_pkt = int((unpacked["point_flags"] & FLAG_TARGET_CORE).astype(bool).sum())
            self.assertEqual(core_count_in_pkt, expected_rows[83]["core_points"])
            self.assertEqual(unpacked["state"]["camera"]["state"], "ready")
            self.assertLessEqual(abs(unpacked["state"]["camera"]["deltaMs"]), 250.0)
        finally:
            mgr.close_all()


if __name__ == "__main__":
    unittest.main()
