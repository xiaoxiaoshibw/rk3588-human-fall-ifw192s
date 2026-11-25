"""阶段 1 纯雷达物理人体识别单测与合成反例回归（仅 stdlib + NumPy）。

覆盖：
- core/range_normals.py（有序 2D 网格法向、方位角法向熵、单/双平面占比、深度断边、近地法向）
- core/human_prior.py::describe_physical_v1（10 层归一化剖面、三姿态兼容、窄门板/双面盒体/悬挂鸟粘连拒识）
- core/human_kinematics_filter.py（刚体平移柜/箱、非刚体行走人、静止人免误罚、周期振荡/悬空摆动、缺口重置）
- core/full_body_recovery.py（贴地脚/小腿局部回收 + 地面法向剥离、人椅平面截断、竞争轨迹/膨胀拒绝）
- core/human_belief.py + RangeRuntime 接入（Log-Odds 迟滞状态机、默认零回归等价、Python 3.8 AST 检查）

语义诚实：合成反例仅验证软件与物理几何契约，不代表真实人体准确率或误报率。
"""

import ast
import math
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.full_body_recovery import recover_full_body
from core.human_belief import (
    HumanBeliefTracker,
    HumanPhysicalEvaluator,
    STATE_CANDIDATE,
    STATE_CONFIRMED,
    STATE_UNKNOWN,
    resolve_belief_settings,
)
from core.human_kinematics_filter import HumanKinematicsFilter
from core.human_prior import (
    CLASS_HANGING_ADHESION,
    CLASS_LYING,
    CLASS_PLANAR,
    CLASS_SITTING,
    CLASS_STANDING,
    describe,
    describe_physical_v1,
)
from core.range_contract import binding_tuple
from core.range_normals import cluster_normal_features, estimate_grid_normals
from core.range_runtime import RangeRuntime
from test_range_frontend import scene


IDENTITY = dict(
    session="phys_v1_test",
    meta_sha256="m",
    points_sha256="p",
    coordinate="RAW/innolidar",
    units="m",
    coordinate_transform="identity",
    grid_sha256="grid_sha",
    epoch="source_header_epoch",
)
BINDING = binding_tuple(IDENTITY)
GROUND = dict(
    status="valid",
    normal=[0.0, 0.0, 1.0],
    offset_m=0.0,
    frame="innolidar",
    binding=IDENTITY,
)


class DummyGrid:
    def __init__(self, shape, sha="grid_sha"):
        self.shape = tuple(shape)
        self.sha256 = sha


class SyntheticGridFrame:
    """带完整 2D 有序网格拓扑的 RangeFrame 替身（无相机，纯 3D 雷达点）。"""

    def __init__(self, grid_xyz, binding=BINDING, grid_sha="grid_sha"):
        arr = np.asarray(grid_xyz, dtype=np.float64)
        assert arr.ndim == 3 and arr.shape[2] == 3
        h, w, _ = arr.shape
        self.grid = DummyGrid((h, w), sha=grid_sha)
        self.binding = binding
        self.valid = np.all(np.isfinite(arr), axis=2)
        valid_cells = np.flatnonzero(self.valid.ravel())
        self.xyz = arr.reshape(-1, 3)[valid_cells].copy()
        self.source_rows = np.full((h, w), -1, dtype=np.int64)
        self.source_rows.ravel()[valid_cells] = np.arange(len(valid_cells), dtype=np.int64)
        self.range_m = np.full((h, w), np.nan, dtype=np.float64)
        if valid_cells.size:
            self.range_m.ravel()[valid_cells] = np.linalg.norm(self.xyz, axis=1)


class SimpleBackground:
    """测试用显式背景模型（含 known / mean_m）。"""

    def __init__(self, mean_m):
        self.mean_m = np.asarray(mean_m, dtype=np.float64)
        self.known = np.isfinite(self.mean_m)


def _blank_grid(h=48, w=48, bg_x=5.0):
    grid = np.full((h, w, 3), np.nan, dtype=np.float64)
    ys = np.linspace(-1.4, 1.4, w)
    zs = np.linspace(2.2, 0.0, h)
    yy, zz = np.meshgrid(ys, zs)
    grid[:, :, 0] = bg_x
    grid[:, :, 1] = yy
    grid[:, :, 2] = zz
    return grid


def _paint_cylinder(grid, *, cx=2.6, cy=0.0, radius=0.22, z_bot=0.04, z_top=1.70,
                    r0=8, r1=42, c0=16, c1=32, phase=0.0, articulate=False):
    """在 2D 有序网格上绘制弯曲人体正面圆柱（支持可选四肢非刚体摆动）。"""
    rows = []
    nr = max(1, r1 - r0)
    nc = max(1, c1 - c0)
    for r in range(r0, r1 + 1):
        fz = 1.0 - (r - r0) / float(nr)  # 1 at top, 0 at bottom
        z = z_bot + fz * (z_top - z_bot)
        # 略带头-肩-腰-腿剖面调制
        if fz > 0.85:
            local_r = radius * 0.62
        elif fz > 0.55:
            local_r = radius * 1.05
        elif fz > 0.35:
            local_r = radius * 0.85
        else:
            local_r = radius * 0.90
        if articulate:
            # 模拟真实行走：下肢前后交替错动 + 手臂层宽调制
            leg_shift = (0.14 * math.sin(phase)) if fz < 0.35 else 0.0
            arm_widen = (1.0 + 0.30 * math.sin(phase + 0.8)) if (0.45 <= fz <= 0.78) else 1.0
            torso_sway = 0.05 * math.cos(phase) if fz > 0.65 else 0.0
        else:
            leg_shift = 0.0
            arm_widen = 1.0
            torso_sway = 0.0
        local_r *= arm_widen
        for c in range(c0, c1 + 1):
            frac_a = (c - c0) / float(nc) * 2.0 - 1.0
            ang = frac_a * math.radians(82.0)
            # 朝向原点 (x=0)：正面壳 x = cx - r*cos(ang)
            x = cx - local_r * math.cos(ang) + (leg_shift if frac_a >= 0 else -leg_shift)
            y = cy + local_r * math.sin(ang) + torso_sway
            grid[r, c] = (x, y, z)
            rows.append((r, c))
    return rows


def _paint_flat_panel(grid, *, cx=2.6, cy=0.0, width=0.55, z_bot=0.05, z_top=1.70,
                      r0=8, r1=42, c0=18, c1=30, yaw_deg=0.0):
    """在 2D 网格上绘制窄平门板/柜面（旧版宽门 0.90m 会漏检的典型平面反例）。"""
    rows = []
    nr = max(1, r1 - r0)
    nc = max(1, c1 - c0)
    yaw = math.radians(yaw_deg)
    ca, sa = math.cos(yaw), math.sin(yaw)
    for r in range(r0, r1 + 1):
        fz = 1.0 - (r - r0) / float(nr)
        z = z_bot + fz * (z_top - z_bot)
        for c in range(c0, c1 + 1):
            ly = ((c - c0) / float(nc) - 0.5) * width
            x = cx - sa * ly
            y = cy + ca * ly
            grid[r, c] = (x, y, z)
            rows.append((r, c))
    return rows


def _paint_box_corner(grid, *, cx=2.6, cy=0.0, side=0.50, z_bot=0.05, z_top=1.60,
                      r0=10, r1=42, c0=16, c1=32):
    """在 2D 网格上绘制双正交平面柜体拐角。"""
    rows = []
    nr = max(1, r1 - r0)
    cm = (c0 + c1) // 2
    for r in range(r0, r1 + 1):
        fz = 1.0 - (r - r0) / float(nr)
        z = z_bot + fz * (z_top - z_bot)
        for c in range(c0, cm + 1):
            t = (cm - c) / float(max(1, cm - c0))
            # 左面法向 (-1/sqrt2, -1/sqrt2, 0)
            x = cx + t * side * 0.7071
            y = cy - t * side * 0.7071
            grid[r, c] = (x, y, z)
            rows.append((r, c))
        for c in range(cm + 1, c1 + 1):
            t = (c - cm) / float(max(1, c1 - cm))
            # 右面法向 (-1/sqrt2, +1/sqrt2, 0)
            x = cx + t * side * 0.7071
            y = cy + t * side * 0.7071
            grid[r, c] = (x, y, z)
            rows.append((r, c))
    return rows


def _paint_lying_cylinder(grid, *, cx=2.6, cy=0.0, length=1.40, radius=0.22, z_base=0.04,
                          r0=32, r1=44, c0=10, c1=38):
    """在 2D 网格上绘制贴地躺姿曲面躯干圆柱（含顶面与前侧面，物理纵深 ~0.40 m）。"""
    rows = []
    nr = max(1, r1 - r0)
    nc = max(1, c1 - c0)
    for r in range(r0, r1 + 1):
        frac_a = (r - r0) / float(nr)  # 0 at back-top, 1 at front-bottom
        ang = math.radians(150.0 - 160.0 * frac_a)  # +150 deg (rear-top) -> -10 deg (front)
        x = cx - radius * math.cos(ang)
        z = z_base + radius + radius * math.sin(ang)
        for c in range(c0, c1 + 1):
            ly = ((c - c0) / float(nc) - 0.5) * length
            grid[r, c] = (x, cy + ly, z)
            rows.append((r, c))
    return rows


def _paint_hanging_bird_adhesion(grid, *, cx=2.25, cy=0.0, broken=False):
    """复现现场悬挂鸟 #7 粘连支架（H~1.55m, 3D 曲面顶重团 + 细桥）与断开后（H=0.25m）形态。"""
    rows = []
    if not broken:
        # 顶部 180 点 3D 曲面鸟模型（r=8..17, c=15..32 -> 180 pts, W=0.51m, 饱满半圆柱面）
        for r in range(8, 18):
            fz = 1.0 - (r - 8) / 9.0
            z = 1.40 + fz * 0.25
            for c in range(15, 33):
                ang = ((c - 15) / 17.0 * 2.0 - 1.0) * math.radians(82.0)
                grid[r, c] = (cx - 0.24 * math.cos(ang), cy + 0.255 * math.sin(ang), z)
                rows.append((r, c))
        # 中间 1 列细支架桥（r=18..37, c=24 -> 20 pts, W~0m, z=0.25..1.38m）
        for r in range(18, 38):
            fz = 1.0 - (r - 18) / 19.0
            z = 0.25 + fz * 1.13
            grid[r, 24] = (cx, cy, z)
            rows.append((r, 24))
        # 底部 16 点小底座边（r=38..41, c=22..25 -> 16 pts, z=0.10..0.24m）
        for r in range(38, 42):
            fz = 1.0 - (r - 38) / 3.0
            z = 0.10 + fz * 0.14
            for c in range(22, 26):
                grid[r, c] = (cx, cy + (c - 23.5) * 0.03, z)
                rows.append((r, c))
    else:
        # 断开后仅剩 180 点悬空鸟（H=0.25m, z=0.65..0.90m）
        for r in range(22, 32):
            fz = 1.0 - (r - 22) / 9.0
            z = 0.65 + fz * 0.25
            for c in range(15, 33):
                ang = ((c - 15) / 17.0 * 2.0 - 1.0) * math.radians(82.0)
                grid[r, c] = (cx - 0.24 * math.cos(ang), cy + 0.255 * math.sin(ang), z)
                rows.append((r, c))
    return rows


def _apply_noise(grid, rc_list, rng, range_noise_m, dropout):
    """对绘制好的物体点加径向测距高斯噪声与随机丢点（丢点像素回落为背景墙）。"""
    bg = _blank_grid(grid.shape[0], grid.shape[1])
    kept = []
    for r, c in rc_list:
        if dropout > 0.0 and rng.random() < dropout:
            grid[r, c] = bg[r, c]
            continue
        if range_noise_m > 0.0:
            p = grid[r, c]
            rng_m = float(np.linalg.norm(p))
            grid[r, c] = p * (1.0 + rng.normal(0.0, range_noise_m) / rng_m)
        kept.append((r, c))
    return kept


def _cells_to_rows(frame, rc_list):
    return np.unique(np.array([frame.source_rows[r, c] for r, c in rc_list], dtype=np.int64))


class TestRangeNormals(unittest.TestCase):
    def test_curved_cylinder_vs_flat_door_and_box_corner(self):
        # 1. 弯曲人体圆柱
        g_cyl = _blank_grid()
        rc_cyl = _paint_cylinder(g_cyl)
        f_cyl = SyntheticGridFrame(g_cyl)
        gn_cyl = estimate_grid_normals(f_cyl)
        nf_cyl = cluster_normal_features(f_cyl, _cells_to_rows(f_cyl, rc_cyl), gn_cyl, GROUND)
        self.assertTrue(nf_cyl["available"])
        self.assertGreater(nf_cyl["normal_azimuth_entropy"], 0.45)
        self.assertLess(nf_cyl["single_plane_inlier_ratio"], 0.55)
        # 确认法向朝向传感器原点（dot(n, -p) >= 0 <=> dot(n, p) <= 0）
        cyl_cells = gn_cyl.row_to_cell[_cells_to_rows(f_cyl, rc_cyl)]
        valid_c = cyl_cells[gn_cyl.valid.ravel()[cyl_cells]]
        n_vecs = gn_cyl.normals.reshape(-1, 3)[valid_c]
        p_vecs = gn_cyl.grid_xyz.reshape(-1, 3)[valid_c]
        dots = np.einsum("ij,ij->i", n_vecs, p_vecs)
        self.assertTrue((dots <= 1e-6).all())

        # 2. 窄平面门板（0.55m 宽）
        g_door = _blank_grid()
        rc_door = _paint_flat_panel(g_door, width=0.55)
        f_door = SyntheticGridFrame(g_door)
        gn_door = estimate_grid_normals(f_door)
        nf_door = cluster_normal_features(f_door, _cells_to_rows(f_door, rc_door), gn_door, GROUND)
        self.assertTrue(nf_door["available"])
        self.assertLess(nf_door["normal_azimuth_entropy"], 0.20)
        self.assertGreater(nf_door["single_plane_inlier_ratio"], 0.90)
        self.assertLess(nf_door["median_local_roughness"], 0.005)

        # 3. 双正交平面柜角
        g_box = _blank_grid()
        rc_box = _paint_box_corner(g_box)
        f_box = SyntheticGridFrame(g_box)
        gn_box = estimate_grid_normals(f_box)
        nf_box = cluster_normal_features(f_box, _cells_to_rows(f_box, rc_box), gn_box, GROUND)
        self.assertTrue(nf_box["available"])
        self.assertGreater(nf_box["dual_plane_inlier_ratio"], 0.88)
        self.assertLess(nf_box["normal_azimuth_entropy"], 0.42)

    def test_depth_discontinuity_prevents_background_normal_pollution(self):
        # 2.6m 平面门板紧邻 5.0m 远墙，断边门 0.25m 必须阻止边缘法向被污染
        g = _blank_grid(bg_x=5.0)
        rc = _paint_flat_panel(g, cx=2.6, width=0.55)
        f = SyntheticGridFrame(g)
        gn = estimate_grid_normals(f, max_edge_jump_m=0.25)
        rows = _cells_to_rows(f, rc)
        cells = gn.row_to_cell[rows]
        nvecs = gn.normals.reshape(-1, 3)[cells[gn.valid.ravel()[cells]]]
        # 全部（含最外圈边缘）法向都应近似 (-1, 0, 0)
        self.assertTrue(np.allclose(nvecs[:, 0], -1.0, atol=1e-2))

    def test_ground_normal_alignment_and_1d_fallback(self):
        # 地面水平补丁
        g = np.full((12, 12, 3), np.nan, dtype=np.float64)
        for r in range(12):
            for c in range(12):
                g[r, c] = (2.0 + r * 0.05, -0.3 + c * 0.05, 0.01)
        f = SyntheticGridFrame(g)
        gn = estimate_grid_normals(f)
        nf = cluster_normal_features(f, np.arange(len(f.xyz)), gn, GROUND)
        self.assertTrue(nf["available"])
        # 传感器在原点 z=0 略低或齐平时，检查绝对法向近地对齐（抬高传感器即地面法向 +z）
        ground_elev = dict(GROUND, offset_m=1.2)
        g2 = g.copy()
        g2[:, :, 2] = -1.19  # 在地面 z_ground = 0.01m，传感器位于地面上方 1.2m -> 法向明确朝 +z
        f2 = SyntheticGridFrame(g2)
        gn2 = estimate_grid_normals(f2)
        nf2 = cluster_normal_features(f2, np.arange(len(f2.xyz)), gn2, ground_elev)
        self.assertGreater(nf2["ground_normal_alignment"], 0.95)

        # 1D 退化网格不崩溃、无警告
        g1d = np.array([[[2.0, 0.0, 1.0], [2.0, 0.1, 1.0]]], dtype=np.float64)
        f1d = SyntheticGridFrame(g1d)
        gn1d = estimate_grid_normals(f1d)
        self.assertEqual(gn1d.valid_normal_count, 0)
        nf1d = cluster_normal_features(f1d, np.array([0, 1]), gn1d, GROUND)
        self.assertFalse(nf1d["available"])

    def test_roi_bbox_normals_exact_match_full_grid(self):
        g = _blank_grid()
        rc = _paint_cylinder(g)
        f = SyntheticGridFrame(g)
        gn_full = estimate_grid_normals(f)
        gn_roi = estimate_grid_normals(f, roi_bbox=(8, 43, 16, 33))
        rows = _cells_to_rows(f, rc)
        nf_full = cluster_normal_features(f, rows, gn_full, GROUND)
        nf_roi = cluster_normal_features(f, rows, gn_roi, GROUND)
        self.assertEqual(nf_full, nf_roi)


class TestHumanPriorPhysicalV1(unittest.TestCase):
    def test_three_postures_compatible_and_default_describe_unchanged(self):
        # 站姿
        g_st = _blank_grid()
        rc_st = _paint_cylinder(g_st, z_bot=0.04, z_top=1.70)
        f_st = SyntheticGridFrame(g_st)
        rows_st = _cells_to_rows(f_st, rc_st)
        base_st = describe(f_st, rows_st, GROUND)
        v1_st = describe_physical_v1(f_st, rows_st, GROUND, normals=estimate_grid_normals(f_st))
        self.assertEqual(base_st["class"], CLASS_STANDING)
        self.assertEqual(v1_st["class"], CLASS_STANDING)
        self.assertTrue(v1_st["compatible"])
        self.assertEqual(v1_st["semantic"], "UNKNOWN")
        self.assertEqual(v1_st["normalized_profile"]["num_tiers"], 10)
        self.assertGreaterEqual(v1_st["normalized_profile"]["vertical_fill"], 0.8)

        # 坐/蹲姿（不把直立身高当入口硬门）
        g_sit = _blank_grid()
        rc_sit = _paint_cylinder(g_sit, z_bot=0.04, z_top=0.92, r0=20, r1=42)
        f_sit = SyntheticGridFrame(g_sit)
        v1_sit = describe_physical_v1(f_sit, _cells_to_rows(f_sit, rc_sit), GROUND,
                                      normals=estimate_grid_normals(f_sit))
        self.assertEqual(v1_sit["class"], CLASS_SITTING)
        self.assertTrue(v1_sit["compatible"])

        # 躺姿
        g_lie = _blank_grid()
        rc_lie = _paint_lying_cylinder(g_lie)
        f_lie = SyntheticGridFrame(g_lie)
        v1_lie = describe_physical_v1(f_lie, _cells_to_rows(f_lie, rc_lie), GROUND,
                                      normals=estimate_grid_normals(f_lie))
        self.assertEqual(v1_lie["class"], CLASS_LYING)
        self.assertTrue(v1_lie["compatible"])

    def test_rejects_narrow_planar_door_box_corner_and_hanging_bird_adhesion(self):
        # 1. 0.55m 窄门板：原 describe() 会判 standing_geometry，physical_v1 必须拒绝为 planar_structure
        g_door = _blank_grid()
        rc_door = _paint_flat_panel(g_door, width=0.55)
        f_door = SyntheticGridFrame(g_door)
        rows_door = _cells_to_rows(f_door, rc_door)
        self.assertEqual(describe(f_door, rows_door, GROUND)["class"], CLASS_STANDING)
        v1_door = describe_physical_v1(f_door, rows_door, GROUND, normals=estimate_grid_normals(f_door))
        self.assertEqual(v1_door["class"], CLASS_PLANAR)
        self.assertFalse(v1_door["compatible"])
        self.assertIn("surface_normal_single_plane", v1_door["rejection_reasons"])

        # 2. 双面直角柜角
        g_box = _blank_grid()
        rc_box = _paint_box_corner(g_box)
        f_box = SyntheticGridFrame(g_box)
        v1_box = describe_physical_v1(f_box, _cells_to_rows(f_box, rc_box), GROUND,
                                      normals=estimate_grid_normals(f_box))
        self.assertEqual(v1_box["class"], CLASS_PLANAR)
        self.assertFalse(v1_box["compatible"])

        # 3. 悬挂鸟 #7 粘连支架（顶重细桥）
        g_bird = _blank_grid()
        rc_bird = _paint_hanging_bird_adhesion(g_bird, broken=False)
        f_bird = SyntheticGridFrame(g_bird)
        v1_bird = describe_physical_v1(f_bird, _cells_to_rows(f_bird, rc_bird), GROUND,
                                       normals=estimate_grid_normals(f_bird))
        self.assertEqual(v1_bird["class"], CLASS_HANGING_ADHESION)
        self.assertFalse(v1_bird["compatible"])

        # 4. 垂向大空洞且底部离地（上下分离两块，下块悬空 0.45 m 以上）-> 断层判据生效
        g_gap = _blank_grid()
        rc_top = _paint_cylinder(g_gap, z_bot=1.25, z_top=1.70, r0=8, r1=18, c0=18, c1=30)
        rc_bot = _paint_cylinder(g_gap, z_bot=0.45, z_top=0.80, r0=30, r1=38, c0=18, c1=30)
        f_gap = SyntheticGridFrame(g_gap)
        v1_gap = describe_physical_v1(f_gap, _cells_to_rows(f_gap, rc_top + rc_bot), GROUND,
                                      normals=estimate_grid_normals(f_gap))
        self.assertFalse(v1_gap["compatible"])
        self.assertEqual(v1_gap["class"], CLASS_HANGING_ADHESION)
        self.assertTrue(v1_gap["normalized_profile"]["bottom_detached"])
        self.assertIn("vertical_profile_gap_discontinuity", v1_gap["rejection_reasons"])

        # 5. r2：同样的上下分离两块但底部贴地 -> 不得单凭断层判悬空粘连
        g_gnd = _blank_grid()
        rc_top2 = _paint_cylinder(g_gnd, z_bot=1.25, z_top=1.70, r0=8, r1=18, c0=18, c1=30)
        rc_bot2 = _paint_cylinder(g_gnd, z_bot=0.05, z_top=0.45, r0=32, r1=42, c0=18, c1=30)
        f_gnd = SyntheticGridFrame(g_gnd)
        v1_gnd = describe_physical_v1(f_gnd, _cells_to_rows(f_gnd, rc_top2 + rc_bot2), GROUND,
                                      normals=estimate_grid_normals(f_gnd))
        self.assertNotIn("vertical_profile_gap_discontinuity", v1_gnd["rejection_reasons"])
        self.assertNotIn("low_normalized_vertical_fill", v1_gnd["rejection_reasons"])
        self.assertFalse(v1_gnd["normalized_profile"]["bottom_detached"])

    def test_desk_occluded_standing_human_not_rejected_as_hanging(self):
        """r2：书桌遮挡 0.40–0.95 m 中段、双脚贴地的站立人体不能被判为悬空粘连。"""
        g = _blank_grid()
        bg = _blank_grid()
        rc = _paint_cylinder(g)
        keep = []
        for r, c in rc:
            if 0.40 <= g[r, c, 2] <= 0.95:
                g[r, c] = bg[r, c]
            else:
                keep.append((r, c))
        f = SyntheticGridFrame(g)
        rows = _cells_to_rows(f, keep)
        v1 = describe_physical_v1(f, rows, GROUND, normals=estimate_grid_normals(f))
        self.assertEqual(describe(f, rows, GROUND)["class"], CLASS_STANDING)
        self.assertEqual(v1["class"], CLASS_STANDING)
        self.assertTrue(v1["compatible"])
        self.assertGreaterEqual(v1["normalized_profile"]["max_empty_tier_run"], 2)
        self.assertIn("gap_ignored_bottom_ground_supported", v1["physical_notes"])


class TestHumanKinematicsFilter(unittest.TestCase):
    def _record(self, fidx, t_s, tid, rows, generation=0):
        return dict(
            frame=fidx,
            time_s=t_s,
            generation=generation,
            tracks=[dict(track_id=tid, observed=True, position_predicted=False,
                         source_rows=rows.tolist(), status="tracked")],
        )

    def _run(self, kf, frames, tid, t0_index=0, clutter=False, noise=None):
        """按帧序列喂入单轨迹；noise=(rng, range_noise_m, dropout) 时对点加测距噪声/随机丢点。"""
        last = None
        history = []
        for k, (t_s, paint_kwargs) in enumerate(frames):
            g = _blank_grid()
            rc = _paint_cylinder(g, **paint_kwargs)
            if noise is not None:
                rc = _apply_noise(g, rc, *noise)
            f = SyntheticGridFrame(g)
            res = kf.update(f, self._record(t0_index + k, t_s, tid, _cells_to_rows(f, rc)), GROUND,
                            clutter_track_ids=[tid] if clutter else None)
            last = res[tid]
            history.append(last)
        return last, history

    def _calibrate_static_clutter(self, kf, noise, t_start=0.0, idx_start=0):
        """两条静止加噪杂物轨迹（各 20 帧）在线标定噪声底。"""
        frames = [(t_start + 0.1 * k, dict(cy=0.0)) for k in range(20)]
        self._run(kf, frames, "clutter_a", idx_start, clutter=True, noise=noise)
        frames_b = [(t_start + 2.0 + 0.1 * k, dict(cy=0.1)) for k in range(20)]
        self._run(kf, frames_b, "clutter_b", idx_start + 20, clutter=True, noise=noise)
        return kf.noise_floor(), t_start + 4.0, idx_start + 40

    def test_uncalibrated_disables_rigid_penalty_and_nonrigid_bonus(self):
        """r2：未标定噪声底前，刚体罚分与非刚体加分都必须关闭（即使是无噪声理想数据）。"""
        moving = [(0.1 * i, dict(cy=-0.4 + 0.035 * i)) for i in range(12)]
        last_rigid, _ = self._run(HumanKinematicsFilter(), moving, "t1")
        walking = [(0.1 * i, dict(cy=-0.4 + 0.035 * i, phase=i * 0.85, articulate=True)) for i in range(12)]
        last_walk, _ = self._run(HumanKinematicsFilter(), walking, "t1")
        for last in (last_rigid, last_walk):
            self.assertTrue(last["articulation_ready"])
            self.assertFalse(last["noise_calibrated"])
            self.assertIsNone(last["noise_floor_ivel_mps"])
            self.assertFalse(last["rigid_moving_object"])
            self.assertFalse(last["articulation_supported"])

    def test_noisy_and_dropout_rigid_never_gets_nonrigid_bonus_after_calibration(self):
        """r2：1 cm 测距噪声 / 10% 随机丢点的刚体平移：标定后不得获得非刚体加分。"""
        for label, range_noise, dropout in (("range_noise_1cm", 0.01, 0.0),
                                            ("dropout_10pct", 0.0, 0.10),
                                            ("noise_and_dropout", 0.01, 0.10)):
            with self.subTest(label):
                rng = np.random.default_rng(7)
                kf = HumanKinematicsFilter()
                floor, t0, i0 = self._calibrate_static_clutter(kf, (rng, range_noise, dropout))
                self.assertTrue(floor["calibrated"])
                self.assertEqual(floor["source"], "online_static_clutter")
                self.assertGreater(floor["ivel_floor_mps"], 0.05)
                moving = [(t0 + 0.1 * k, dict(cy=-0.4 + 0.035 * k)) for k in range(15)]
                _, hist = self._run(kf, moving, "rigid", i0, noise=(rng, range_noise, dropout))
                ready = [h for h in hist if h["articulation_ready"]]
                self.assertTrue(ready)
                self.assertTrue(all(h["noise_calibrated"] for h in ready))
                self.assertFalse(any(h["articulation_supported"] for h in ready))
                self.assertTrue(all(h["internal_vel_noise_ratio"] < 2.0 for h in ready))

    def test_rigid_detected_when_internal_residual_clearly_below_clutter_floor(self):
        """真实数据中大目标的质心抖动低于小碎片杂物（静止目标约 0.5–0.9x 噪声底）。
        这里用 1 cm 噪声 + 10% 丢点的杂物标定，刚体本身 0.2 cm 噪声：内部残差远低于噪声底 -> 刚体平移成立。"""
        rng = np.random.default_rng(5)
        kf = HumanKinematicsFilter()
        floor, t0, i0 = self._calibrate_static_clutter(kf, (rng, 0.01, 0.10))
        self.assertTrue(floor["calibrated"])
        moving = [(t0 + 0.1 * k, dict(cy=-0.4 + 0.035 * k)) for k in range(15)]
        _, hist = self._run(kf, moving, "rigid", i0, noise=(rng, 0.002, 0.0))
        ready = [h for h in hist if h["articulation_ready"]]
        self.assertTrue(all(h["rigid_moving_object"] for h in ready))
        self.assertFalse(any(h["articulation_supported"] for h in ready))

    def test_noisy_walking_human_supported_and_static_human_not_rigid_after_calibration(self):
        rng = np.random.default_rng(11)
        noise = (rng, 0.005, 0.0)
        kf = HumanKinematicsFilter()
        _, t0, i0 = self._calibrate_static_clutter(kf, noise)
        walking = [(t0 + 0.1 * k, dict(cy=-0.4 + 0.035 * k, phase=k * 0.85, articulate=True))
                   for k in range(15)]
        last_walk, hist_walk = self._run(kf, walking, "walker", i0, noise=noise)
        ready = [h for h in hist_walk if h["articulation_ready"]]
        self.assertTrue(all(h["articulation_supported"] for h in ready))
        self.assertFalse(any(h["rigid_moving_object"] for h in ready))
        self.assertGreaterEqual(last_walk["internal_vel_noise_ratio"], 2.5)

        still = [(t0 + 2.0 + 0.1 * k, dict(cy=0.0)) for k in range(15)]
        _, hist_still = self._run(kf, still, "still", i0 + 20, noise=noise)
        self.assertFalse(any(h["rigid_moving_object"] for h in hist_still))
        self.assertFalse(any(h["articulation_supported"] for h in hist_still))

    def test_offline_noise_floor_fallback_and_calibration_scope(self):
        kf = HumanKinematicsFilter({"offline_noise_floor_ivel_mps": 0.13,
                                    "offline_noise_floor_wrate_mps": 0.10})
        floor = kf.noise_floor()
        self.assertTrue(floor["calibrated"])
        self.assertEqual(floor["source"], "offline_tuning_set")
        with self.assertRaises(ValueError):
            HumanKinematicsFilter({"offline_noise_floor_ivel_mps": 0.13})
        with self.assertRaises(ValueError):
            HumanKinematicsFilter({"rigid_ivel_noise_mult": 3.0, "articulation_ivel_noise_mult": 2.0})
        # 非杂物（未声明 clutter）的静止轨迹不得进入标定样本
        kf2 = HumanKinematicsFilter()
        self._run(kf2, [(0.1 * k, dict(cy=0.0)) for k in range(30)], "target_like")
        self.assertEqual(kf2.noise_floor()["samples"], 0)
        # 标定在普通历史重置后保留，在显式清空时清零
        rng = np.random.default_rng(3)
        kf3 = HumanKinematicsFilter()
        self._calibrate_static_clutter(kf3, (rng, 0.01, 0.0))
        kf3.reset()
        self.assertTrue(kf3.noise_floor()["calibrated"])
        kf3.reset(clear_calibration=True)
        self.assertFalse(kf3.noise_floor()["calibrated"])

    def test_periodic_oscillation_and_suspended_prop_flagged_as_soft_evidence(self):
        kf = HumanKinematicsFilter()
        last = None
        for i in range(26):
            t_s = i * 0.1
            cy = 0.12 * math.sin(2.0 * math.pi * 1.1 * t_s)
            g = _blank_grid()
            rc = _paint_cylinder(g, cy=cy, z_bot=0.70, z_top=1.35, r0=12, r1=28)
            f = SyntheticGridFrame(g)
            res = kf.update(f, self._record(i, t_s, "t_osc", _cells_to_rows(f, rc)), GROUND)
            last = res["t_osc"]
        self.assertTrue(last["is_oscillating"])
        self.assertTrue(last["no_ground_contact"])
        self.assertTrue(last["is_suspended_oscillator"])
        self.assertTrue(last["hovering"])
        self.assertIn("soft_suspended_oscillator", last["rejection_reasons"])

        # 真实系鞋带/躺地 1.5–2 cm 级各向同性采样微抖不得误报为振荡
        rng = np.random.default_rng(42)
        kf_jitter = HumanKinematicsFilter()
        for i in range(40):
            t_s = i * 0.1
            jx, jy = rng.normal(0.0, 0.014, size=2)
            g = _blank_grid()
            rc = _paint_cylinder(g, cx=2.6 + jx, cy=jy, z_bot=0.05, z_top=0.85, r0=20, r1=42)
            f = SyntheticGridFrame(g)
            res_j = kf_jitter.update(f, self._record(i, t_s, "t_sq", _cells_to_rows(f, rc)), GROUND)
            self.assertFalse(res_j["t_sq"]["is_oscillating"])
            self.assertFalse(res_j["t_sq"]["is_suspended_oscillator"])

    def test_in_place_sway_standing_and_seated_have_ground_contact(self):
        """r2：原地左右晃（站 / 坐，双脚着地）可能被标记振荡软证据，但绝不能判为悬空振荡。"""
        cases = (
            ("standing_sway_p2p30cm_0p6hz", 0.15, 0.6, dict(z_bot=0.04, z_top=1.70)),
            ("standing_sway_p2p20cm_0p9hz", 0.10, 0.9, dict(z_bot=0.04, z_top=1.70)),
            ("seated_sway_feet_on_floor", 0.08, 0.8, dict(z_bot=0.04, z_top=1.25, r0=16, r1=42)),
        )
        for label, amp, hz, geom in cases:
            with self.subTest(label):
                frames = [(0.1 * i, dict(cy=amp * math.sin(2.0 * math.pi * hz * 0.1 * i),
                                         phase=i * 0.85, articulate=True, **geom))
                          for i in range(45)]
                _, hist = self._run(HumanKinematicsFilter(), frames, "t1")
                self.assertFalse(any(h["is_suspended_oscillator"] for h in hist))
                self.assertFalse(any(h["hovering"] for h in hist))
                self.assertFalse(any(h["no_ground_contact"] for h in hist))

    def test_gap_nan_and_binding_reset_history(self):
        kf = HumanKinematicsFilter()
        g = _blank_grid()
        rc = _paint_cylinder(g)
        f = SyntheticGridFrame(g)
        rows = _cells_to_rows(f, rc)
        for i in range(5):
            kf.update(f, self._record(i, i * 0.1, "t1", rows), GROUND)
        # 超过 reset_gap_s=2.0 -> 历史必须清零
        res = kf.update(f, self._record(6, 3.5, "t1", rows), GROUND)
        self.assertEqual(res["t1"]["reset_reason"], "stream_gap")
        self.assertEqual(res["t1"]["samples"], 1)
        # NaN 时间戳抛 ValueError 且清空历史
        with self.assertRaises(ValueError):
            kf.update(f, self._record(7, float("nan"), "t1", rows), GROUND)
        res_after = kf.update(f, self._record(8, 4.0, "t1", rows), GROUND)
        self.assertEqual(res_after["t1"]["samples"], 1)


class TestFullBodyRecovery(unittest.TestCase):
    def test_recovers_near_ground_calf_and_foot_while_peeling_flat_floor(self):
        # 传感器在 z=1.2m 上方：地面位于 z_raw = -1.20m（ground_h = 0.0m）
        ground_elev = dict(GROUND, offset_m=1.20)
        h, w = 48, 48
        g = np.full((h, w, 3), np.nan, dtype=np.float64)
        bg = np.full((h, w), 5.0, dtype=np.float64)
        for r in range(h):
            for c in range(w):
                g[r, c] = (5.0, (c - 24) * 0.06, 1.0 - r * 0.05)

        # 上半身+大腿核心（距离 2.6m，远小于 5.0m -> 强前景）
        core_rc = []
        for r in range(8, 30):
            gh = 0.35 + (29 - r) / 21.0 * 1.35
            for c in range(18, 30):
                ang = ((c - 18) / 11.0 * 2.0 - 1.0) * math.radians(70.0)
                g[r, c] = (2.6 - 0.20 * math.cos(ang), 0.20 * math.sin(ang), gh - 1.20)
                core_rc.append((r, c))

        # 贴地小腿+竖直脚背（距离背景仅差 0.14m，低于 0.30m 严格门，高于 0.10m 局部宽松门）
        limb_rc = []
        for r in range(30, 38):
            gh = 0.015 + (37 - r) / 7.0 * 0.32
            for c in range(20, 28):
                ang = ((c - 20) / 7.0 * 2.0 - 1.0) * math.radians(65.0)
                px = 2.6 - 0.16 * math.cos(ang)
                py = 0.16 * math.sin(ang)
                pz = gh - 1.20
                g[r, c] = (px, py, pz)
                bg[r, c] = math.sqrt(px * px + py * py + pz * pz) + 0.14
                limb_rc.append((r, c))

        # 紧邻脚下的平坦地面补丁（gh = 0.01m，法向严格朝 +z，距离也故意设为前景 -0.14m 考验地面剥离）
        floor_rc = []
        for r in range(38, 45):
            for c in range(16, 32):
                px = 2.55 - (r - 38) * 0.06
                py = (c - 24) * 0.05
                pz = 0.01 - 1.20
                g[r, c] = (px, py, pz)
                bg[r, c] = math.sqrt(px * px + py * py + pz * pz) + 0.14
                floor_rc.append((r, c))

        f = SyntheticGridFrame(g)
        gn = estimate_grid_normals(f)
        core_rows = _cells_to_rows(f, core_rc)
        limb_rows = _cells_to_rows(f, limb_rc)
        floor_rows = _cells_to_rows(f, floor_rc)

        res = recover_full_body(f, SimpleBackground(bg), core_rows, ground_elev, grid_normals=gn)
        self.assertEqual(res["status"], "recovered")
        self.assertGreater(res["added_count"], 20)
        self.assertGreater(res["breakdown"]["added_near_ground_count"], 10)
        self.assertGreater(res["breakdown"]["peeled_ground_pixels"], 20)
        # 地面内部像素被剥离（允许极少脚-地交界像素不构成地面吞噬），且核心行完整保留
        rec_set = set(res["recovered_rows"])
        self.assertTrue(set(core_rows.tolist()).issubset(rec_set))
        self.assertGreater(len(set(limb_rows.tolist()) & rec_set) / float(len(limb_rows)), 0.75)
        self.assertLess(len(set(floor_rows.tolist()) & rec_set) / float(len(floor_rows)), 0.15)

    def test_cuts_human_chair_contact_and_rejects_competing_track(self):
        h, w = 48, 48
        g = _blank_grid(h, w, bg_x=5.0)
        bg = np.full((h, w), 5.0, dtype=np.float64)
        core_rc = _paint_cylinder(g, cx=2.6, cy=-0.10, radius=0.20, r0=10, r1=38, c0=12, c1=24)

        # 紧邻人体右侧的刚性垂直大墙/椅背（法向沿 -y，与人体边缘成大夹角且极其平坦）
        wall_rc = []
        for r in range(10, 38):
            fz = 1.0 - (r - 10) / 27.0
            z = 0.05 + fz * 1.60
            for c in range(25, 42):
                px = 2.6 + (c - 25) * 0.055
                py = 0.12
                g[r, c] = (px, py, z)
                bg[r, c] = math.sqrt(px * px + py * py + z * z) + 0.14
                wall_rc.append((r, c))

        f = SyntheticGridFrame(g)
        gn = estimate_grid_normals(f)
        core_rows = _cells_to_rows(f, core_rc)
        wall_rows = _cells_to_rows(f, wall_rc)

        # 1. 法向平面截断必须把 476 点刚性墙体阻断在 1 列接触缝以内（绝不泛洪吞墙）
        res = recover_full_body(f, SimpleBackground(bg), core_rows, GROUND, grid_normals=gn)
        rec_set = set(res["recovered_rows"])
        wall_swallowed = len(rec_set & set(wall_rows.tolist()))
        self.assertGreaterEqual(res["breakdown"]["cut_planar_edges"], 20)
        self.assertLessEqual(wall_swallowed, 30)
        self.assertLess(wall_swallowed / float(len(wall_rows)), 0.08)

        # 2. 若与另一实测轨迹连续相交，必须整次拒绝并记录 competing_observed_track
        g2 = _blank_grid(h, w, bg_x=5.0)
        bg2 = np.full((h, w), 5.0, dtype=np.float64)
        c1_rc = _paint_cylinder(g2, cx=2.6, cy=-0.05, z_bot=0.88, z_top=1.70, r0=10, r1=26, c0=16, c1=28)
        c2_rc = _paint_cylinder(g2, cx=2.6, cy=-0.05, z_bot=0.05, z_top=0.85, r0=27, r1=38, c0=16, c1=28)
        for r, c in c2_rc:
            p = g2[r, c]
            bg2[r, c] = math.sqrt(float(p @ p)) + 0.14
        f2 = SyntheticGridFrame(g2)
        c1_rows = _cells_to_rows(f2, c1_rc)
        c2_rows = _cells_to_rows(f2, c2_rc)
        res_conflict = recover_full_body(
            f2, SimpleBackground(bg2), c1_rows, GROUND,
            grid_normals=estimate_grid_normals(f2),
            other_tracks_rows=[c2_rows],
        )
        self.assertEqual(res_conflict["status"], "rejected")
        self.assertEqual(res_conflict["recovery_rejected_reason"], "competing_observed_track")
        self.assertEqual(res_conflict["recovered_rows"], c1_rows.tolist())

        # 3. 膨胀倍数超限时必须拒绝（expansion_ratio_exceeded）
        res_over = recover_full_body(
            f2, SimpleBackground(bg2), c1_rows, GROUND,
            grid_normals=estimate_grid_normals(f2),
            settings={"max_expansion_ratio": 1.10},
        )
        self.assertEqual(res_over["status"], "rejected")
        self.assertEqual(res_over["recovery_rejected_reason"], "expansion_ratio_exceeded")
        self.assertEqual(res_over["recovered_rows"], c1_rows.tolist())


class TestHumanBeliefAndRuntimeIntegration(unittest.TestCase):
    def _eval_sequence(self, frames_rc, tid="t1", evaluator_kwargs=None):
        evaluator = HumanPhysicalEvaluator(**(evaluator_kwargs or {}))
        outputs = []
        for i, (t_s, frame, rows) in enumerate(frames_rc):
            rec = dict(
                frame=i,
                time_s=t_s,
                generation=0,
                target_track_id=tid if len(rows) else None,
                target_source_rows=rows.tolist(),
                tracks=[dict(track_id=tid, observed=bool(len(rows)),
                             position_predicted=False, source_rows=rows.tolist(),
                             status="tracked")] if len(rows) else [],
            )
            outputs.append(evaluator.evaluate(frame, rec, background=None, ground=GROUND))
            self.assertEqual(outputs[-1]["status"], "ok", outputs[-1]["errors"])
        return outputs

    def test_walking_human_confirms_while_all_negative_counterexamples_stay_unknown(self):
        # 1. 行走弯曲人体 -> 晋升 CONFIRMED_HUMAN，且保持 semantic_truth == 'UNKNOWN'
        human_seq = []
        for i in range(12):
            g = _blank_grid()
            rc = _paint_cylinder(g, cy=-0.3 + 0.04 * i, phase=i * 0.8, articulate=True)
            f = SyntheticGridFrame(g)
            human_seq.append((i * 0.1, f, _cells_to_rows(f, rc)))
        out_h = self._eval_sequence(human_seq)
        states_h = [o["target_belief"]["belief_state"] for o in out_h]
        self.assertEqual(states_h[-1], STATE_CONFIRMED)
        self.assertEqual(out_h[-1]["semantic_truth"], "UNKNOWN")
        self.assertEqual(out_h[-1]["target_belief"]["semantic_truth"], "UNKNOWN")

        # 2. 窄平面门板移动 15 帧 -> 0 帧 CONFIRMED_HUMAN
        door_seq = []
        for i in range(15):
            g = _blank_grid()
            rc = _paint_flat_panel(g, cy=-0.2 + 0.03 * i, width=0.55)
            f = SyntheticGridFrame(g)
            door_seq.append((i * 0.1, f, _cells_to_rows(f, rc)))
        out_door = self._eval_sequence(door_seq)
        self.assertTrue(all(o["target_belief"]["belief_state"] == STATE_UNKNOWN for o in out_door))

        # 3. 刚体平移柱/柜 15 帧（非平面曲面但纯刚体快速平移）-> 刚体平移罚分阻止误确认
        # 使用双面直角箱体平移，确保平面 + 刚体双防线均拦截
        box_seq = []
        for i in range(15):
            g = _blank_grid()
            rc = _paint_box_corner(g, cy=-0.3 + 0.04 * i)
            f = SyntheticGridFrame(g)
            box_seq.append((i * 0.1, f, _cells_to_rows(f, rc)))
        out_box = self._eval_sequence(box_seq)
        self.assertTrue(all(o["target_belief"]["belief_state"] == STATE_UNKNOWN for o in out_box))

        # 3b. 弯曲圆柱纯刚体快速平移：噪声底已标定（无噪声合成数据，噪声底取下限 0.02 m/s）时，
        #     刚体平移只做软惩罚（r2：真实直立移动目标也会落入刚体判据，故不否决），不得晋升 CONFIRMED
        rigid_cyl_seq = []
        for i in range(15):
            g = _blank_grid()
            rc = _paint_cylinder(g, cy=-0.4 + 0.035 * i, articulate=False)
            f = SyntheticGridFrame(g)
            rigid_cyl_seq.append((i * 0.1, f, _cells_to_rows(f, rc)))
        calibrated = {"kinematics_settings": {"offline_noise_floor_ivel_mps": 0.02,
                                              "offline_noise_floor_wrate_mps": 0.02}}
        out_rcyl = self._eval_sequence(rigid_cyl_seq, evaluator_kwargs=calibrated)
        self.assertTrue(all(o["target_belief"]["belief_state"] != STATE_CONFIRMED for o in out_rcyl))
        self.assertIn("soft_rigid_moving_object", out_rcyl[-1]["target_belief"]["rejection_reasons"])
        self.assertFalse(out_rcyl[-1]["target_belief"]["veto_active"])

        # 3c. 未标定时同一刚体：运动学通道中性（不加分也不罚分），只记录 uncalibrated 原因码
        out_rcyl_u = self._eval_sequence(rigid_cyl_seq)
        for o in out_rcyl_u:
            self.assertNotIn("nonrigid_articulation_supported", o["target_belief"]["evidence_codes"])
            self.assertEqual(o["target_belief"]["deltas"]["kin"], 0.0)
        self.assertIn("kinematics_uncalibrated_neutral", out_rcyl_u[-1]["target_belief"]["evidence_codes"])

        # 4. 悬挂鸟 #7 粘连支架（10 帧）后断开（12 帧）-> 全程 0 帧 CONFIRMED_HUMAN
        bird_seq = []
        for i in range(22):
            g = _blank_grid()
            rc = _paint_hanging_bird_adhesion(g, cy=0.05 * math.sin(i * 0.6), broken=(i >= 10))
            f = SyntheticGridFrame(g)
            bird_seq.append((i * 0.1, f, _cells_to_rows(f, rc)))
        out_bird = self._eval_sequence(bird_seq)
        self.assertTrue(all(o["target_belief"]["belief_state"] != STATE_CONFIRMED for o in out_bird))

        # 5. 悬空周期摆动物（25 帧）-> 全程 0 帧 CONFIRMED_HUMAN
        osc_seq = []
        for i in range(25):
            t_s = i * 0.1
            g = _blank_grid()
            rc = _paint_cylinder(g, cy=0.12 * math.sin(2.0 * math.pi * 1.1 * t_s),
                                 z_bot=0.70, z_top=1.35, r0=12, r1=28)
            f = SyntheticGridFrame(g)
            osc_seq.append((t_s, f, _cells_to_rows(f, rc)))
        out_osc = self._eval_sequence(osc_seq)
        self.assertEqual(out_osc[-1]["target_belief"]["belief_state"], STATE_UNKNOWN)
        self.assertTrue(all(o["target_belief"]["belief_state"] != STATE_CONFIRMED for o in out_osc))

    def test_belief_hysteresis_freeze_on_miss_and_reset_on_calibration_change(self):
        bt = HumanBeliefTracker()
        good_obs = {
            "t1": {
                "observed": True,
                "source_rows": [1, 2, 3],
                "prior": {
                    "class": CLASS_STANDING,
                    "compatible": True,
                    "normalized_profile": {"vertical_fill": 0.9, "min_third_ratio": 0.25},
                    "normal_features": {
                        "available": True,
                        "single_plane_inlier_ratio": 0.35,
                        "dual_plane_inlier_ratio": 0.55,
                        "normal_azimuth_entropy": 0.70,
                        "normal_sphere_entropy": 0.65,
                    },
                },
                "kinematics": {"available": True, "articulation_supported": True},
            }
        }
        ctx = ("b1", "g1", 0, "ground1")
        for i in range(6):
            res = bt.update_frame(ctx, i * 0.1, i, good_obs)
        self.assertEqual(res["t1"]["belief_state"], STATE_CONFIRMED)
        lo_confirmed = res["t1"]["log_odds"]

        # 短缺测冻结 Log-Odds（不加分也不直接清零）
        res_miss = bt.update_frame(ctx, 0.6, 6, {"t1": {"observed": False}})
        self.assertEqual(res_miss["t1"]["log_odds"], lo_confirmed)
        self.assertEqual(res_miss["t1"]["belief_state"], STATE_CONFIRMED)

        # 更换标定/地面上下文 -> 立即清空历史
        ctx_new = ("b1", "g1", 0, "ground2")
        res_reset = bt.update_frame(ctx_new, 0.7, 7, good_obs)
        self.assertEqual(res_reset["t1"]["reset_reason"], "context_or_calibration_changed")
        self.assertEqual(res_reset["t1"]["observed_frames"], 1)
        self.assertNotEqual(res_reset["t1"]["belief_state"], STATE_CONFIRMED)

    def _good_obs(self, **kin):
        return {
            "t1": {
                "observed": True,
                "source_rows": [1, 2, 3],
                "prior": {
                    "class": CLASS_STANDING,
                    "compatible": True,
                    "normalized_profile": {"vertical_fill": 0.9, "min_third_ratio": 0.25},
                    "normal_features": {
                        "available": True,
                        "single_plane_inlier_ratio": 0.35,
                        "dual_plane_inlier_ratio": 0.55,
                        "normal_azimuth_entropy": 0.70,
                        "normal_sphere_entropy": 0.65,
                    },
                },
                "kinematics": dict({"available": True}, **kin),
            }
        }

    def test_veto_demotes_confirmed_immediately_and_caps_log_odds(self):
        bt = HumanBeliefTracker()
        ctx = ("b1", "g1", 0, "ground1")
        for i in range(20):
            res = bt.update_frame(ctx, i * 0.1, i, self._good_obs())
        self.assertEqual(res["t1"]["belief_state"], STATE_CONFIRMED)
        self.assertLessEqual(res["t1"]["log_odds"], 5.0)
        self.assertEqual(bt.settings["log_odds_max"], 5.0)

        veto_obs = self._good_obs()
        veto_obs["t1"]["prior"] = {"class": CLASS_HANGING_ADHESION, "compatible": False,
                                   "reason": "thin_bridge_lollipop_adhesion"}
        res_v = bt.update_frame(ctx, 2.0, 20, veto_obs)
        self.assertTrue(res_v["t1"]["veto_active"])
        self.assertEqual(res_v["t1"]["belief_state"], STATE_CANDIDATE)
        self.assertLessEqual(res_v["t1"]["log_odds"], bt.settings["veto_log_odds_cap"])
        # 否决后需要重新累积到 confirm_enter 才能再次确认（不会在下一帧立即回到 CONFIRMED）
        res_n = bt.update_frame(ctx, 2.1, 21, self._good_obs())
        self.assertEqual(res_n["t1"]["belief_state"], STATE_CANDIDATE)
        with self.assertRaises(ValueError):
            resolve_belief_settings({"veto_log_odds_cap": 4.0})
        with self.assertRaises(ValueError):
            resolve_belief_settings({"log_odds_max": 3.0})

    def test_oscillation_is_soft_penalty_without_veto(self):
        bt = HumanBeliefTracker()
        ctx = ("b1", "g1", 0, "ground1")
        for i in range(20):
            res = bt.update_frame(ctx, i * 0.1, i, self._good_obs())
        self.assertEqual(res["t1"]["belief_state"], STATE_CONFIRMED)
        for i in range(20, 40):
            res = bt.update_frame(ctx, i * 0.1, i, self._good_obs(is_oscillating=True))
            self.assertFalse(res["t1"]["veto_active"])
            self.assertIn("soft_periodic_oscillation", res["t1"]["rejection_reasons"])
            self.assertEqual(res["t1"]["belief_state"], STATE_CONFIRMED)
        res_s = bt.update_frame(ctx, 4.0, 40, self._good_obs(is_oscillating=True,
                                                             is_suspended_oscillator=True))
        self.assertFalse(res_s["t1"]["veto_active"])
        self.assertIn("soft_suspended_oscillator", res_s["t1"]["rejection_reasons"])
        self.assertAlmostEqual(res_s["t1"]["deltas"]["kin"],
                               bt.settings["delta_suspended_oscillation_penalty"])

    def test_in_place_sway_standing_and_seated_positive_sequences_confirm(self):
        """r2 正例：原地晃动的站姿/坐姿（双脚着地）不被否决，最终仍可确认。"""
        cases = (
            ("standing_sway", 0.15, 0.6, dict(z_bot=0.04, z_top=1.70)),
            ("seated_sway_feet_on_floor", 0.08, 0.8, dict(z_bot=0.04, z_top=1.25, r0=16, r1=42)),
        )
        for label, amp, hz, geom in cases:
            with self.subTest(label):
                seq = []
                for i in range(45):
                    t_s = i * 0.1
                    g = _blank_grid()
                    rc = _paint_cylinder(g, cy=amp * math.sin(2.0 * math.pi * hz * t_s),
                                         phase=i * 0.85, articulate=True, **geom)
                    f = SyntheticGridFrame(g)
                    seq.append((t_s, f, _cells_to_rows(f, rc)))
                out = self._eval_sequence(seq)
                beliefs = [o["target_belief"] for o in out]
                self.assertFalse(any(b["veto_active"] for b in beliefs))
                self.assertFalse(any("soft_suspended_oscillator" in b["rejection_reasons"] for b in beliefs))
                self.assertEqual(beliefs[-1]["belief_state"], STATE_CONFIRMED)

    def test_stage_exceptions_are_isolated_with_reason_codes(self):
        g = _blank_grid()
        rc = _paint_cylinder(g)
        f = SyntheticGridFrame(g)
        rows = _cells_to_rows(f, rc)
        rec = dict(frame=0, time_s=0.0, generation=0, target_track_id="t1",
                   target_source_rows=rows.tolist(),
                   tracks=[dict(track_id="t1", observed=True, position_predicted=False,
                                source_rows=rows.tolist(), status="tracked")])
        ev = HumanPhysicalEvaluator()
        with mock.patch.object(ev.kinematics, "update", side_effect=RuntimeError("boom")):
            out = ev.evaluate(f, rec, background=SimpleBackground(np.full(g.shape[:2], 5.0)),
                              ground=GROUND)
        self.assertEqual(out["status"], "degraded")
        self.assertIn("kinematics_stage_exception", out["error_codes"])
        self.assertIsNotNone(out["target_belief"])
        self.assertIsNone(out["tracks"]["t1"]["kinematics"])

        with mock.patch("core.human_belief.recover_full_body", side_effect=ValueError("bad rows")):
            out2 = ev.evaluate(f, dict(rec, frame=1, time_s=0.1), ground=GROUND,
                               background=SimpleBackground(np.full(g.shape[:2], 5.0)))
        self.assertEqual(out2["status"], "degraded")
        self.assertEqual(out2["error_codes"], ["recovery_stage_exception"])
        self.assertEqual(out2["recovery"]["status"], "error")
        self.assertEqual(out2["recovery"]["recovered_rows"], rows.tolist())

        with mock.patch("core.human_belief.describe_physical_v1", side_effect=FloatingPointError("x")):
            out3 = ev.evaluate(f, dict(rec, frame=2, time_s=0.2), ground=GROUND)
        self.assertIn("prior_stage_exception", out3["error_codes"])
        self.assertEqual(out3["errors"][0]["track_id"], "t1")

    def test_runtime_outer_guard_keeps_main_chain_output(self):
        grid, _, _ = scene(np.full((12, 24), 3.0))
        identity = dict(session="rt_guard", coordinate="RAW/lidar", grid_sha256=grid.sha256)
        plane = dict(status="valid", binding=identity, frame="lidar", normal=[0, 0, 1], offset_m=0.5)
        rt_base = RangeRuntime(grid, identity, empty_prefix_frames=2, ground=plane, ground_sha="gsha")
        rt_v1 = RangeRuntime(grid, identity, empty_prefix_frames=2, ground=plane, ground_sha="gsha",
                             human_physical_v1=True)
        self.assertEqual(rt_v1.config["human_physical_v1"]["revision"], "physical_v1_r2")
        for i in range(6):
            depth = np.full((12, 24), 3.0)
            if i >= 2:
                depth[2:10, 8:16] = 2.0
            _, packed, _ = scene(depth)
            out_b, _, _ = rt_base.update(packed, i * 0.1, i)
            if i == 4:
                with mock.patch.object(rt_v1.human_physical, "evaluate",
                                       side_effect=RuntimeError("evaluator crashed")):
                    out_v, _, _ = rt_v1.update(packed, i * 0.1, i)
                self.assertEqual(out_v["human_physical_v1"]["status"], "error")
                self.assertEqual(out_v["human_physical_v1"]["error_codes"], ["evaluate_exception"])
            else:
                out_v, _, _ = rt_v1.update(packed, i * 0.1, i)
                self.assertNotEqual(out_v["human_physical_v1"]["status"], "error")
            self.assertEqual(out_b["tracking"], out_v["tracking"])
            self.assertEqual(out_b["rule"], out_v["rule"])

    def test_range_runtime_default_parity_and_opt_in_variant(self):
        grid, _, _ = scene(np.full((12, 24), 3.0))
        identity = dict(session="rt_parity", coordinate="RAW/lidar", grid_sha256=grid.sha256)
        plane = dict(status="valid", binding=identity, frame="lidar", normal=[0, 0, 1], offset_m=0.5)
        rt_base = RangeRuntime(grid, identity, empty_prefix_frames=2, ground=plane, ground_sha="gsha")
        rt_v1 = RangeRuntime(grid, identity, empty_prefix_frames=2, ground=plane, ground_sha="gsha",
                             human_physical_v1=True)
        self.assertNotEqual(rt_base.config_sha, rt_v1.config_sha)

        for i in range(10):
            depth = np.full((12, 24), 3.0)
            if i >= 2:
                depth[2:10, 8:16] = 2.0
            _, packed, _ = scene(depth)
            out_b, _, _ = rt_base.update(packed, i * 0.1, i)
            out_v, _, _ = rt_v1.update(packed, i * 0.1, i)
            self.assertNotIn("human_physical_v1", out_b)
            self.assertIn("human_physical_v1", out_v)
            # 原跟踪/规则输出逐字段完全等价
            self.assertEqual(out_b["tracking"], out_v["tracking"])
            self.assertEqual(out_b["rule"], out_v["rule"])
            self.assertIn("physical_total_ms", out_v["timings"])

    def test_python38_ast_syntax_and_pure_lidar_stdlib_numpy_only(self):
        core_dir = Path(__file__).resolve().parents[1] / "core"
        targets = [
            core_dir / "range_normals.py",
            core_dir / "human_prior.py",
            core_dir / "human_kinematics_filter.py",
            core_dir / "full_body_recovery.py",
            core_dir / "human_belief.py",
            core_dir / "range_runtime.py",
        ]
        forbidden = {"cv2", "scipy", "sklearn", "torch", "rospy", "PIL", "ultralytics", "rknn"}
        for path in targets:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(path), feature_version=(3, 8))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        self.assertNotIn(top, forbidden, f"{path.name} imports forbidden {top}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top = node.module.split(".")[0]
                    self.assertNotIn(top, forbidden, f"{path.name} imports forbidden {top}")


if __name__ == "__main__":
    unittest.main()
