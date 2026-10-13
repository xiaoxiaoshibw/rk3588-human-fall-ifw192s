"""P03 R1 — 算法自动地面域（detect_ground_domain）单测。

架构：board 端 100% stdlib+NumPy。不依赖 leveling_test 的 28B bin/fixture（detect 是纯函数）。
happy path 用真实 session（cap_20261004_*）保证排水证据；R2 锚点对照写日志不断言。
负路径用轻量 synthetic：构造点云直接喂 detect，不诚实就 fail。
"""
import json
import math
import unittest
from pathlib import Path

import numpy as np

import leveling_quality as Q
from leveling_lib import detect_ground_domain

ROOT = Path(__file__).resolve().parent / "remote_for_auto_test"  # 不被生成
REMOTE = Path(__file__).resolve().parents[2] / "captures" / "remote"


def _session_points(sid):
    directory = REMOTE / sid
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    xyz = np.ndarray((meta["total_points"], 3), dtype="<f4", buffer=raw, strides=(28, 4))
    pts = []
    for frame in meta["frames"]:
        seg = xyz[frame["offset_points"]:frame["offset_points"] + frame["count_points"]].astype(np.float64)
        valid = np.isfinite(seg).all(axis=1) & np.any(seg != 0, axis=1)
        pts.append(seg[valid])
    return np.concatenate(pts)


def _synthetic_points(rng, rects, pitch_deg=26, roll_deg=-1, sensor_z=1.3, per_region=80):
    R, t = Q.rotation(pitch_deg, roll_deg), np.array([0, 0, sensor_z])
    chunks = []
    for xl, xh, yl, yh in rects:
        display = np.column_stack([
            rng.uniform(xl + .05, xh - .05, per_region),
            rng.uniform(yl + .05, yh - .05, per_region),
            rng.normal(0, .002, per_region)])
        chunks.append((display - t) @ R)
    return np.vstack(chunks)


class DetectTest(unittest.TestCase):
    def test_synthetic_favorite_four_regions(self):
        rng = np.random.RandomState(7)
        rects = [[.5, 1.3, -1, -.2], [1.7, 2.5, -1, -.2], [.5, 1.3, .2, 1], [1.7, 2.5, .2, 1]]
        pts = _synthetic_points(rng, rects)
        # detect 的 anchor = nominal rotation.z
        anchor = Q.rotation(26, -1)[2]
        result = detect_ground_domain(pts, 26, -1, anchor)
        self.assertEqual(len(result["regions"]), 4)
        # 算法 ROI 必须互不重叠（与下游 freeze 断言同因）
        rs = result["regions"]
        for i in range(4):
            for j in range(i + 1, 4):
                overlap_x = min(rs[i][1], rs[j][1]) > max(rs[i][0], rs[j][0])
                overlap_y = min(rs[i][3], rs[j][3]) > max(rs[i][2], rs[j][2])
                self.assertFalse(overlap_x and overlap_y, "ROI %d 与 %d 重叠" % (i, j))
        # 候选平面已经靠近平面真值（5° 容差，不绑死 R2）
        cand = result["candidate"]
        self.assertAlmostEqual(cand["pitch_deg"], 26, delta=5)
        self.assertAlmostEqual(cand["roll_deg"], -1, delta=5)
        self.assertAlmostEqual(cand["offset_source_m"], 1.3, delta=.05)

    def test_wall_like_scene_rejects_with_reason(self):
        rng = np.random.RandomState(11)
        # 唯一的"地面"实际是 x=1.3 竖直墙 → normal[2]≈0 < .85
        display_wall = np.column_stack([
            np.full(600, 1.3),
            rng.uniform(-1, 1, 600),
            rng.normal(0, .002, 600)])
        pts = display_wall  # z 已经 0
        anchor = Q.rotation(26, -1)[2]
        with self.assertRaisesRegex(ValueError, "ground_auto_candidate_invalid: 主面法向不朝上"):
            detect_ground_domain(pts, 26, -1, anchor)

    def test_plane_below_sensor_floor_rejects(self):
        rng = np.random.RandomState(13)
        # 平面在 d=2.5（>=1.8 出界）。
        rects = [[.5, 1.3, -1, -.2], [1.7, 2.5, -1, -.2], [.5, 1.3, .2, 1], [1.7, 2.5, .2, 1]]
        pts = _synthetic_points(rng, rects, sensor_z=2.5)
        anchor = Q.rotation(26, -1)[2]
        with self.assertRaisesRegex(ValueError, "ground_auto_candidate_invalid: 平面偏移超出门范围"):
            detect_ground_domain(pts, 26, -1, anchor)

    def test_two_connected_components_rejects(self):
        rng = np.random.RandomState(17)
        rects = [[.5, 1.3, -1, -.2], [1.7, 2.5, -1, -.2]]  # 只 2 个
        pts = _synthetic_points(rng, rects)
        anchor = Q.rotation(26, -1)[2]
        with self.assertRaisesRegex(ValueError, "ground_auto_regions_invalid: 连通域不足 4 个"):
            detect_ground_domain(pts, 26, -1, anchor)


class RealSessionAnchorTest(unittest.TestCase):
    """真实 session：detect 必须工作；与 R2 联合值只报告不断言（P03-D 报告义务）。"""

    R2_TLS_PITCH = 26.623261360650194
    R2_TLS_ROLL = -1.3946707174625859
    R2_TLS_D = 1.32190083447894

    def _anchor(self):
        return Q.rotation(26, -1)[2]

    for_sid = ("cap_20261004_202456", "cap_20261004_203349")

    def test_real_sessions_detect_four_regions(self):
        for sid in self.for_sid:
            pts = _session_points(sid)
            result = detect_ground_domain(pts, 26, -1, self._anchor())
            self.assertEqual(len(result["regions"]), 4)
            cand = result["candidate"]
            delta_pitch = abs(cand["pitch_deg"] - self.R2_TLS_PITCH)
            delta_roll = abs(cand["roll_deg"] - self.R2_TLS_ROLL)
            delta_d = abs(cand["offset_source_m"] - self.R2_TLS_D)
            # P03-D：如实报告差值；门是 <1.5°pitch（P03-A 工单）。
            self.assertLess(delta_pitch, 1.5,
                            "sid=%s Δpitch=%.4f Δroll=%.4f Δd=%.5f" % (sid, delta_pitch, delta_roll, delta_d))
            print("AUTO_ANCHOR sid=%s pitch=%.4f roll=%.4f d=%.5f support=%.4f Δpitch=%.4f Δroll=%.4f Δd=%.5f" % (
                sid, cand["pitch_deg"], cand["roll_deg"], cand["offset_source_m"], cand["support_ratio"],
                delta_pitch, delta_roll, delta_d))


if __name__ == "__main__":
    unittest.main()
