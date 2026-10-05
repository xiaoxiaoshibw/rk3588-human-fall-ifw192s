# -*- coding: utf-8 -*-
"""limb_lib 单元测试 — 合成点云冒烟 + 真会话抽帧检测"""
import os
import unittest

import numpy as np

from limb_lib import BONES, BODY_KP_ORDER, LimbTracker, detect_frame, fit_ground_ransac


def make_standing_person(n_points=2500, centre=(2.0, 0.5, 0.0), seed=0):
    rng = np.random.default_rng(seed)
    cx, cy, cz = centre
    # 地面 + 人形柱
    g_x = rng.uniform(-8, 10, 3000)
    g_y = rng.uniform(-8, 10, 3000)
    g_z = rng.normal(cz, 0.02, 3000)
    ground = np.column_stack([g_x, g_y, g_z])
    body = rng.normal([cx, cy, cz + 1.0], [0.15, 0.10, 0.45], (n_points // 2, 3))
    head = rng.normal([cx, cy, cz + 1.7], [0.10, 0.10, 0.12], (n_points // 6, 3))
    arm_l = rng.normal([cx + 0.05, cy + 0.55, cz + 1.3], [0.05, 0.10, 0.10],
                        (n_points // 8, 3))
    arm_r = rng.normal([cx + 0.05, cy - 0.55, cz + 1.3], [0.05, 0.10, 0.10],
                        (n_points // 8, 3))
    return np.vstack([ground, body, head, arm_l, arm_r]).astype(np.float32)


class GroundFit(unittest.TestCase):
    def test_flat_ground_normal_up(self):
        pts = make_standing_person()
        n, c = fit_ground_ransac(pts)
        self.assertIsNotNone(n)
        self.assertGreater(n[2], 0.95)
        self.assertAlmostEqual(c[2], 0.0, delta=0.05)


class DetectFrame(unittest.TestCase):
    def test_detect_on_synth(self):
        pts = make_standing_person()
        r = detect_frame(pts)
        self.assertTrue(r["detected"], r)
        # 直立 -> torso_tilt 应小
        self.assertLess(r["torso_tilt_deg"], 30)
        # 左右手腕应都在且一侧 +y 一侧 -y
        self.assertIsNotNone(r["keypoints"]["wrist_l"])
        self.assertIsNotNone(r["keypoints"]["wrist_r"])
        self.assertGreater(r["keypoints"]["wrist_l"][1], 0)
        self.assertLess(r["keypoints"]["wrist_r"][1], 0)
        # 骨架固定
        for a, b in BONES:
            self.assertIn(a, BODY_KP_ORDER)
            self.assertIn(b, BODY_KP_ORDER)


if __name__ == "__main__":
    unittest.main()
