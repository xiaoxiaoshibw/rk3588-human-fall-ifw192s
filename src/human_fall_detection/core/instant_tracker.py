"""免空场、免阻塞地面拟合的即时人体跟踪与运动学跌倒候选核心（stdlib + NumPy，Python 3.8 兼容）。

设计来源与对齐：
- 完整继承 `firmware/esp32s3_human/human_tracker.cpp`（v3 同轨续期/起身恢复 + 2026-11-22 悬挂鸟粘连
  修复：垂向连续性/IQR/三段占比门、水平 (u,v) 位移窗口、上下半区协同运动门）的核心逻辑；
- 面向 RK3588 的 NumPy 向量化加速：2D 距离图前景差分、背景自愈与 8 邻域深度连通全部向量化执行，
  并完整保留每簇/每轨的真实解码 `source_rows`；
- 与 `SilentGroundRefiner` 深度协同：
  1. 第 0 帧直接初始化最远背景包络并运行，无需 50 帧空场或阻塞拟合；
  2. 后台精修收敛切换 `gravity_up` 时，按各活跃轨迹中心平滑重投影基线与滤波状态，
     实现真正的“无感切换”（零 ID 跳变、零速度尖峰、零跌倒史清空）；
  3. 后台获得地面零点 `offset_m` 后，自动输出绝对离地高度、启用额外悬空物物理拒识，
     并暴露 `background_adapter` 供 `human_physical_v1` 局部肢体回收使用。
- 严格语义诚实：输出上限为 `suspected`（`confirmed_enabled=False`），`semantic='unknown'`。
"""

from collections import deque
import math
import time

import numpy as np

try:  # pragma: no cover - import shim
    from .silent_ground_refiner import horizontal_basis
except ImportError:  # pragma: no cover
    from silent_ground_refiner import horizontal_basis


FALL_UNKNOWN = "unknown"
FALL_UPRIGHT = "upright"
FALL_DESCENDING = "descending"
FALL_SUSPECTED = "suspected"

REASON_NONE = "NONE"
REASON_FAST_KINEMATIC = "FAST_KINEMATIC"
REASON_SLOW_DESCENT = "SLOW_DESCENT"

DEFAULT_INSTANT_SETTINGS = {
    "min_range_mm": 350,
    "max_range_mm": 8000,
    "fg_margin_mm": 220,
    "bg_grow_margin_mm": 140,
    "bfs_step_mm": 200,
    "retain_margin_mm": 450,
    "retain_extra_mm": 350,
    "retain_tight_mm": 300,
    "min_cluster_points": 80,
    "max_cluster_span_m": 2.35,
    "max_horiz_radius_m": 1.15,
    "max_candidates": 16,
    "max_tracks": 8,
    "kinematic_window": 20,
    # 人体初锁与防粘连门（对齐 ESP32-S3 v3 + 2026-11-22 悬挂鸟修复）
    "lock_min_frames": 3,
    "human_min_lock_points": 260,
    "human_max_bottom_row": 98,
    "human_min_upright_h_m": 0.90,
    "human_max_upright_h_m": 2.15,
    "human_min_horiz_m": 0.15,
    "human_max_horiz_m": 1.15,
    "human_min_aspect": 1.05,
    "human_min_vertical_fill": 0.72,
    "human_max_vertical_gap_m": 0.14,
    "human_min_iqr_ratio": 0.28,
    "human_min_third_ratio": 0.10,
    # 地面零点收敛后的额外物理悬空拦截（保留书桌遮挡站立人余量）
    "ground_hanging_bottom_max_m": 0.95,
    "motion_depth_mm": 120,
    "motion_window_sec": 1.30,
    "motion_lock_disp_m": 0.11,
    "motion_renew_disp_m": 0.075,
    "human_max_speed_mps": 3.50,
    "still_hold_sec": 25.0,
    "suspected_hold_sec": 12.0,
    # 运动学 + 体态三联跌倒门
    "fast_down_vel_mps": 0.70,
    "fast_acc_mps2": 2.00,
    "fast_drop_m": 0.75,
    "slow_down_vel_mps": 0.25,
    "slow_drop_m": 0.80,
    "collapsed_min_height_m": 0.14,
    "collapsed_height_m": 0.55,
    "collapsed_aspect_max": 0.55,
    "very_low_height_m": 0.45,
    "fall_hold_sec": 1.20,
    "recover_height_m": 1.02,
    "recover_drop_m": 0.35,
    # 轨迹关联与短缺测
    "assoc_horiz_m": 0.85,
    "assoc_3d_m": 1.15,
    "max_miss_frames": 8,
    "short_miss_frames": 2,
    "max_gap_sec": 0.35,
}


def resolve_instant_settings(settings=None):
    resolved = dict(DEFAULT_INSTANT_SETTINGS)
    for k, v in (settings or {}).items():
        if k not in resolved:
            raise ValueError("unknown instant tracker setting: " + str(k))
        resolved[k] = v
    int_keys = (
        "min_range_mm", "max_range_mm", "fg_margin_mm", "bg_grow_margin_mm",
        "bfs_step_mm", "retain_margin_mm", "retain_extra_mm", "retain_tight_mm",
        "min_cluster_points", "max_candidates", "max_tracks", "kinematic_window",
        "lock_min_frames", "human_min_lock_points", "human_max_bottom_row",
        "motion_depth_mm", "max_miss_frames", "short_miss_frames",
    )
    for k in int_keys:
        val = resolved[k]
        if isinstance(val, bool) or int(val) != val or int(val) < 0:
            raise ValueError(k + " must be a non-negative integer")
        resolved[k] = int(val)
    for k in resolved:
        if k in int_keys:
            continue
        val = float(resolved[k])
        if not math.isfinite(val) or val < 0.0:
            raise ValueError(k + " must be finite non-negative")
        resolved[k] = val
    return resolved


def _connected_components_mm(mask, cur_mm, step_mm):
    """8 邻域深度连通（水平 run 向量化 + 并查集），仅在 mask 为 True 的有效格上运行。"""
    h, w = mask.shape
    cells = np.flatnonzero(mask.ravel())
    if not len(cells):
        return []
    depth = cur_mm.ravel()
    starts = np.ones(len(cells), dtype=bool)
    if len(cells) > 1:
        same_row_adj = (cells[1:] == cells[:-1] + 1) & ((cells[1:] % w) != 0)
        depth_ok = np.abs(depth[cells[1:]] - depth[cells[:-1]]) <= step_mm
        starts[1:] = ~(same_row_adj & depth_ok)
    runs = np.cumsum(starts, dtype=np.int32) - 1
    n_runs = int(runs[-1]) + 1

    labels_flat = np.full(h * w, -1, dtype=np.int32)
    labels_flat[cells] = runs

    pairs_list = []
    rows = cells // w
    cols = cells % w
    not_last = rows < (h - 1)
    for dc in (-1, 0, 1):
        sel = not_last & ((cols + dc) >= 0) & ((cols + dc) < w)
        if not np.any(sel):
            continue
        a = cells[sel]
        b = a + w + dc
        other = labels_flat[b]
        ok = (other >= 0) & (np.abs(depth[a] - depth[b]) <= step_mm)
        if np.any(ok):
            pairs_list.append(runs[sel][ok].astype(np.int64) * n_runs + other[ok])

    parent = list(range(n_runs))

    def find_root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    if pairs_list:
        for pair in np.unique(np.concatenate(pairs_list)).tolist():
            ra = find_root(pair // n_runs)
            rb = find_root(pair % n_runs)
            if ra != rb:
                if ra < rb:
                    parent[rb] = ra
                else:
                    parent[ra] = rb

    roots = np.array([find_root(i) for i in range(n_runs)], dtype=np.int32)
    comp_ids = roots[runs]
    order = np.argsort(comp_ids, kind="mergesort")
    sorted_ids = comp_ids[order]
    boundaries = np.r_[0, np.flatnonzero(np.diff(sorted_ids)) + 1, len(cells)]
    return [cells[order[b:e]] for b, e in zip(boundaries[:-1], boundaries[1:])]


def _bfs_single_component_mm(growable, cur_mm, seed_r, seed_c, step_mm):
    """在小型 ROI 内从单个种子做精确 8 邻域深度连通（保证只拉出与种子相连的簇）。"""
    rh, rw = growable.shape
    if not (0 <= seed_r < rh and 0 <= seed_c < rw) or not growable[seed_r, seed_c]:
        return np.empty(0, dtype=np.int32), np.empty(0, dtype=np.int32)
    visited = np.zeros((rh, rw), dtype=bool)
    visited[seed_r, seed_c] = True
    q = deque([(seed_r, seed_c)])
    rs = []
    cs = []
    while q:
        r, c = q.popleft()
        rs.append(r)
        cs.append(c)
        c_mm = int(cur_mm[r, c])
        r_lo = 0 if r == 0 else r - 1
        r_hi = rh - 1 if r == rh - 1 else r + 1
        c_lo = 0 if c == 0 else c - 1
        c_hi = rw - 1 if c == rw - 1 else c + 1
        for nr in range(r_lo, r_hi + 1):
            for nc in range(c_lo, c_hi + 1):
                if visited[nr, nc] or not growable[nr, nc]:
                    continue
                if abs(int(cur_mm[nr, nc]) - c_mm) <= step_mm:
                    visited[nr, nc] = True
                    q.append((nr, nc))
    return np.asarray(rs, dtype=np.int32), np.asarray(cs, dtype=np.int32)


class InstantBackgroundAdapter:
    """为 `full_body_recovery` 提供与 `RayBackground` 兼容的只读视图（known / mean_m / sigma_m）。"""

    def __init__(self, shape, binding):
        self.shape = tuple(shape)
        self.binding = binding
        self.known = np.zeros(self.shape, dtype=bool)
        self.mean_m = np.full(self.shape, np.nan, dtype=np.float64)
        self.sigma_m = None
        self.non_causal = False
        self.declaration = "instant_adaptive_far_bg"

    def sync(self, bg_far_mm, binding):
        self.binding = binding
        self.known = bg_far_mm > 0
        self.mean_m = np.where(self.known, bg_far_mm.astype(np.float64) * 0.001, np.nan)


class _MotionWindow:
    __slots__ = ("origin_u", "origin_v", "seconds", "path_m", "moving_steps", "depth_frames")

    def __init__(self, u=0.0, v=0.0):
        self.origin_u = float(u)
        self.origin_v = float(v)
        self.seconds = 0.0
        self.path_m = 0.0
        self.moving_steps = 0
        self.depth_frames = 0


class _Track:
    __slots__ = (
        "slot", "active", "id", "locked_human", "measured_this_frame",
        "age_frames", "miss_frames", "missed_sec", "upright_frames", "point_count",
        "box_r0", "box_c0", "box_r1", "box_c1",
        "center", "cu", "cv", "ch", "start_cu", "start_cv", "vel_u", "vel_v", "range_m",
        "h_p02", "h_p05", "h_p50", "h_p95", "height_m", "horiz_span_m", "aspect",
        "baseline_ready", "baseline_top_h", "baseline_height", "drop_top_m",
        "filter_init", "f_top_h", "f_top_v", "f_top_a",
        "history", "peak_down_vel", "peak_down_acc", "peak_brake_acc",
        "low_posture_sec", "still_sec", "suspected_sec", "renewal_top_h",
        "motion", "fall_state", "fall_reason",
        "source_rows", "cells",
    )

    def __init__(self, slot):
        self.slot = slot
        self.reset()

    def reset(self):
        self.active = False
        self.id = 0
        self.locked_human = False
        self.measured_this_frame = False
        self.age_frames = 0
        self.miss_frames = 0
        self.missed_sec = 0.0
        self.upright_frames = 0
        self.point_count = 0
        self.box_r0 = self.box_c0 = self.box_r1 = self.box_c1 = 0
        self.center = np.zeros(3, dtype=np.float64)
        self.cu = self.cv = self.ch = 0.0
        self.start_cu = self.start_cv = 0.0
        self.vel_u = self.vel_v = 0.0
        self.range_m = 0.0
        self.h_p02 = self.h_p05 = self.h_p50 = self.h_p95 = 0.0
        self.height_m = self.horiz_span_m = self.aspect = 0.0
        self.baseline_ready = False
        self.baseline_top_h = 0.0
        self.baseline_height = 0.0
        self.drop_top_m = 0.0
        self.filter_init = False
        self.f_top_h = self.f_top_v = self.f_top_a = 0.0
        self.history = deque(maxlen=20)
        self.peak_down_vel = self.peak_down_acc = self.peak_brake_acc = 0.0
        self.low_posture_sec = 0.0
        self.still_sec = 0.0
        self.suspected_sec = 0.0
        self.renewal_top_h = 0.0
        self.motion = _MotionWindow()
        self.fall_state = FALL_UNKNOWN
        self.fall_reason = REASON_NONE
        self.source_rows = []
        self.cells = np.empty(0, dtype=np.int32)


class InstantHumanTracker:
    """免空场自适应背景 + 运动学跌倒候选跟踪器（支持重力向量无感更新与地面零点增强）。"""

    def __init__(self, shape=(192, 256), gravity_up=(0.0, 0.0, 1.0), settings=None):
        self.shape = (int(shape[0]), int(shape[1]))
        self.settings = resolve_instant_settings(settings)
        self.u_axis, self.v_axis, self.g_up = horizontal_basis(gravity_up)

        self.bg_far_mm = np.zeros(self.shape, dtype=np.int32)
        self.prev_range_mm = np.zeros(self.shape, dtype=np.int32)
        self.owner_grid = np.zeros(self.shape, dtype=np.uint8)
        self.last_fg_mask = np.zeros(self.shape, dtype=bool)
        self.background_adapter = InstantBackgroundAdapter(self.shape, None)

        self.tracks = [_Track(i) for i in range(self.settings["max_tracks"])]
        self.generation = 0
        self.next_track_id = 1
        self.frame_count = 0
        self.last_stamp_s = None
        self.last_frame_index = None
        self.binding = None
        self.selected_track_id = None

    def reset(self, increment_generation=True):
        if increment_generation:
            self.generation += 1
        self.bg_far_mm.fill(0)
        self.prev_range_mm.fill(0)
        self.owner_grid.fill(0)
        self.last_fg_mask.fill(False)
        for tr in self.tracks:
            tr.reset()
        self.frame_count = 0
        self.last_stamp_s = None
        self.last_frame_index = None
        self.selected_track_id = None

    def set_gravity_up(self, new_gravity_up):
        """无感切换重力方向：按活跃轨迹当前 3D 中心平移基线与滤波状态，不清空跟踪与跌倒史。"""
        new_u, new_v, new_g = horizontal_basis(new_gravity_up)
        if float(np.dot(new_g, self.g_up)) > 1.0 - 1e-12:
            return False
        old_g = self.g_up
        delta_g = new_g - old_g
        for tr in self.tracks:
            if not tr.active:
                continue
            c = tr.center
            dh = float(np.dot(c, delta_g))
            new_cu = float(np.dot(c, new_u))
            new_cv = float(np.dot(c, new_v))
            du = new_cu - tr.cu
            dv = new_cv - tr.cv
            tr.cu = new_cu
            tr.cv = new_cv
            tr.ch += dh
            tr.start_cu += du
            tr.start_cv += dv
            tr.motion.origin_u += du
            tr.motion.origin_v += dv
            tr.h_p02 += dh
            tr.h_p05 += dh
            tr.h_p50 += dh
            tr.h_p95 += dh
            if tr.baseline_ready:
                tr.baseline_top_h += dh
            if tr.filter_init:
                tr.f_top_h += dh
            tr.renewal_top_h += dh
        self.u_axis, self.v_axis, self.g_up = new_u, new_v, new_g
        return True

    def _build_candidate(self, frame, cells, cur_mm, motion_mask, retain_slot):
        cfg = self.settings
        n = len(cells)
        if n < cfg["min_cluster_points"]:
            return None
        w = self.shape[1]
        rs = cells // w
        cs = cells % w
        src_rows = np.sort(frame.source_rows.ravel()[cells].astype(np.int64))
        xyz = frame.xyz[src_rows].astype(np.float64)

        pu = xyz @ self.u_axis
        pv = xyz @ self.v_axis
        ph = xyz @ self.g_up

        u_span = float(pu.max() - pu.min())
        v_span = float(pv.max() - pv.min())
        h_min = float(ph.min())
        h_max = float(ph.max())
        raw_h_span = h_max - h_min
        if (u_span > cfg["max_cluster_span_m"]
                or v_span > cfg["max_cluster_span_m"]
                or raw_h_span > cfg["max_cluster_span_m"]):
            return None

        # 2 cm 垂向直方图（与 ESP32-S3 128 桶完全一致口径）
        bin_size = 0.02
        k_bins = 128
        bins = np.clip(((ph - h_min) / bin_size).astype(np.int32), 0, k_bins - 1)
        hist = np.bincount(bins, minlength=k_bins)
        cumsum = np.cumsum(hist)

        def q_bin(num, den):
            target = max(1, (n * num) // den)
            return int(np.searchsorted(cumsum, target, side="left"))

        b02 = min(k_bins - 1, q_bin(2, 100))
        b05 = min(k_bins - 1, q_bin(5, 100))
        b25 = min(k_bins - 1, q_bin(25, 100))
        b50 = min(k_bins - 1, q_bin(1, 2))
        b75 = min(k_bins - 1, q_bin(75, 100))
        b95 = min(k_bins - 1, q_bin(95, 100))

        hp02 = h_min + (b02 + 0.5) * bin_size
        hp05 = h_min + (b05 + 0.5) * bin_size
        hp25 = h_min + (b25 + 0.5) * bin_size
        hp50 = h_min + (b50 + 0.5) * bin_size
        hp75 = h_min + (b75 + 0.5) * bin_size
        hp95 = h_min + (b95 + 0.5) * bin_size

        span_bins = max(1, b95 - b05 + 1)
        sub_hist = hist[b05:b95 + 1]
        inner_points = int(sub_hist.sum())
        if span_bins >= 3:
            b_idx = np.arange(span_bins, dtype=np.int32)
            t_idx = np.minimum(2, (b_idx * 3) // span_bins)
            third_counts = [int(sub_hist[t_idx == k].sum()) for k in (0, 1, 2)]
        else:
            third_counts = [inner_points, 0, 0]
        min_third = min(third_counts)

        # 4 cm 垂向填充（本桶或相邻桶非空）+ 最大垂向空洞
        filled = sub_hist > 0
        if span_bins > 1:
            covered = filled.copy()
            covered[1:] |= filled[:-1]
            covered[:-1] |= filled[1:]
        else:
            covered = filled
        vertical_fill = float(covered.sum()) / float(span_bins)

        max_empty = 0
        cur_empty = 0
        for cnt in sub_hist.tolist():
            if cnt == 0:
                cur_empty += 1
                if cur_empty > max_empty:
                    max_empty = cur_empty
            else:
                cur_empty = 0

        # 运动点（上下半区统计）
        mot_flags = motion_mask.ravel()[cells]
        motion_points = int(mot_flags.sum())
        h_mid = 0.5 * (h_min + h_max)
        if motion_points:
            # cells 和 src_rows 可能顺序不同，按 cells 直接投影
            mot_rows = frame.source_rows.ravel()[cells[mot_flags]].astype(np.int64)
            mot_h = frame.xyz[mot_rows].astype(np.float64) @ self.g_up
            motion_lower = int((mot_h < h_mid).sum())
            motion_upper = int(motion_points - motion_lower)
        else:
            motion_lower = 0
            motion_upper = 0

        owned_points = 0
        if retain_slot >= 0:
            owned_points = int((self.owner_grid.ravel()[cells] == (retain_slot + 1)).sum())

        height_m = max(0.0, hp95 - hp05)
        horiz_span_m = max(u_span, v_span)
        aspect = height_m / max(horiz_span_m, 0.15)
        return {
            "point_count": n,
            "motion_points": motion_points,
            "motion_lower": motion_lower,
            "motion_upper": motion_upper,
            "owned_points": owned_points,
            "r0": int(rs.min()),
            "c0": int(cs.min()),
            "r1": int(rs.max()),
            "c1": int(cs.max()),
            "center": xyz.mean(axis=0),
            "cu": float(pu.mean()),
            "cv": float(pv.mean()),
            "ch": float(ph.mean()),
            "range_m": float(cur_mm.ravel()[cells].mean()) * 0.001,
            "h_p02": hp02,
            "h_p05": hp05,
            "h_p50": hp50,
            "h_p95": hp95,
            "height_m": height_m,
            "iqr_height_m": max(0.0, hp75 - hp25),
            "vertical_fill": vertical_fill,
            "max_vertical_gap_m": float(max_empty) * bin_size,
            "min_third_ratio": float(min_third) / float(max(1, inner_points)),
            "horiz_span_m": horiz_span_m,
            "aspect": aspect,
            "from_retain": retain_slot >= 0,
            "retain_track_slot": retain_slot,
            "cells": cells.astype(np.int32),
            "source_rows": src_rows.tolist(),
        }

    def _upright_geometry(self, cand, ground_offset_m=None):
        cfg = self.settings
        h_rows = self.shape[0]
        high_edge = (cand["r0"] <= 1 or cand["r1"] >= h_rows - 2) and cand["h_p05"] > 0.0
        if high_edge or cand["r0"] > cfg["human_max_bottom_row"]:
            return False
        if (cand["height_m"] < cfg["human_min_upright_h_m"]
                or cand["height_m"] > cfg["human_max_upright_h_m"]
                or cand["horiz_span_m"] > cfg["human_max_horiz_m"]
                or cand["aspect"] < cfg["human_min_aspect"]):
            return False
        if cand["horiz_span_m"] >= 0.25 and cand["point_count"] < cfg["human_min_lock_points"]:
            return False
        if (cand["vertical_fill"] < cfg["human_min_vertical_fill"]
                or cand["max_vertical_gap_m"] > cfg["human_max_vertical_gap_m"]
                or cand["iqr_height_m"] < cfg["human_min_iqr_ratio"] * cand["height_m"]
                or cand["min_third_ratio"] < cfg["human_min_third_ratio"]):
            return False
        if ground_offset_m is not None:
            bottom_above = cand["h_p05"] + float(ground_offset_m)
            if bottom_above > cfg["ground_hanging_bottom_max_m"]:
                return False
        return True

    def _association_distance_sq(self, tr, cand, dt, ground_offset_m=None):
        cfg = self.settings
        horizon = dt + tr.missed_sec
        du = cand["cu"] - (tr.cu + tr.vel_u * horizon)
        dv = cand["cv"] - (tr.cv + tr.vel_v * horizon)
        dh = cand["ch"] - tr.ch
        horiz_sq = du * du + dv * dv
        horiz_limit = min(cfg["assoc_horiz_m"], 0.22 + cfg["human_max_speed_mps"] * horizon)
        if horiz_sq > horiz_limit * horiz_limit:
            return float("inf")

        postural_match = False
        if tr.locked_human:
            cols_overlap = (cand["c0"] <= tr.box_c1) and (tr.box_c0 <= cand["c1"])
            rising = cand["h_p95"] >= tr.h_p95 + 0.12
            low_track = (tr.drop_top_m >= 0.35
                         or tr.fall_state in (FALL_DESCENDING, FALL_SUSPECTED))
            postural_match = (low_track and cols_overlap and horiz_sq <= 0.45 * 0.45
                              and abs(cand["range_m"] - tr.range_m) <= 0.65)
            covers_body = cand["height_m"] >= 0.60 and cand["horiz_span_m"] >= cfg["human_min_horiz_m"]
            covers_low = (tr.baseline_ready
                          and cand["height_m"] >= cfg["collapsed_min_height_m"]
                          and cand["horiz_span_m"] >= 0.50
                          and cand["h_p95"] <= tr.baseline_top_h - 0.45
                          and cand["h_p05"] <= tr.h_p05 + (0.50 if (postural_match and rising) else 0.30))
            covers_rising = (postural_match and rising and cand["height_m"] >= 0.42
                             and cand["horiz_span_m"] >= 0.28
                             and cand["h_p95"] <= tr.baseline_top_h + 0.20)
            if not (covers_body or covers_low or covers_rising):
                return float("inf")
            if (cand["h_p05"] > tr.h_p05 + 0.42
                    and cand["height_m"] < 0.72 * tr.height_m
                    and cand["h_p95"] > tr.h_p95 - 0.22
                    and not covers_rising):
                return float("inf")
        elif not self._upright_geometry(cand, ground_offset_m):
            return float("inf")

        dist_sq = horiz_sq + (0.25 if postural_match else 1.0) * dh * dh
        limit_3d = min(cfg["assoc_3d_m"], 0.32 + 4.0 * horizon)
        return dist_sq if dist_sq <= limit_3d * limit_3d else float("inf")

    def _update_kinematics_and_fall(self, tr, dt, observed_dt):
        cfg = self.settings
        if not tr.filter_init:
            tr.f_top_h = tr.h_p95
            tr.f_top_v = 0.0
            tr.f_top_a = 0.0
            tr.filter_init = True
        else:
            h_pred = tr.f_top_h + tr.f_top_v * dt + 0.5 * tr.f_top_a * dt * dt
            v_pred = tr.f_top_v + tr.f_top_a * dt
            resid = tr.h_p95 - h_pred
            alpha, beta, gamma = 0.52, 0.22, 0.045
            tr.f_top_h = h_pred + alpha * resid
            tr.f_top_v = max(-6.0, min(6.0, v_pred + (beta / dt) * resid))
            tr.f_top_a = max(-25.0, min(25.0, tr.f_top_a + (2.0 * gamma / (dt * dt)) * resid))

        tr.drop_top_m = max(0.0, tr.baseline_top_h - tr.h_p95) if tr.baseline_ready else 0.0

        tr.history.append((
            dt,
            max(0.0, -tr.f_top_v),
            max(0.0, -tr.f_top_a),
            max(0.0, tr.f_top_a),
            tr.drop_top_m,
        ))
        peak_dv = max(s[1] for s in tr.history)
        peak_da = max(s[2] for s in tr.history)
        peak_ba = max(s[3] for s in tr.history)
        tr.peak_down_vel = peak_dv
        tr.peak_down_acc = peak_da
        tr.peak_brake_acc = peak_ba

        if not tr.locked_human or not tr.baseline_ready:
            tr.low_posture_sec = 0.0
            return

        is_collapsed = (
            (tr.height_m <= cfg["collapsed_height_m"] and tr.aspect <= cfg["collapsed_aspect_max"])
            or (tr.height_m <= cfg["very_low_height_m"])
        )
        fast_kin = (
            peak_dv >= cfg["fast_down_vel_mps"]
            and (peak_da >= cfg["fast_acc_mps2"] or peak_ba >= cfg["fast_acc_mps2"])
            and tr.drop_top_m >= cfg["fast_drop_m"]
        )
        slow_kin = (
            peak_dv >= cfg["slow_down_vel_mps"]
            and tr.drop_top_m >= cfg["slow_drop_m"]
        )

        # 直立恢复清除跌倒状态（过滤弯腰/捡东西）
        if tr.height_m >= cfg["recover_height_m"] and tr.drop_top_m <= cfg["recover_drop_m"]:
            tr.fall_state = FALL_UPRIGHT
            tr.fall_reason = REASON_NONE
            tr.low_posture_sec = 0.0
            return

        if tr.fall_state == FALL_SUSPECTED:
            if is_collapsed:
                tr.low_posture_sec += observed_dt
            return

        if is_collapsed and (fast_kin or slow_kin or tr.low_posture_sec > 0.0):
            tr.low_posture_sec += observed_dt
            if tr.fall_reason == REASON_NONE:
                tr.fall_reason = REASON_FAST_KINEMATIC if fast_kin else REASON_SLOW_DESCENT
            if tr.low_posture_sec >= cfg["fall_hold_sec"]:
                tr.fall_state = FALL_SUSPECTED
            else:
                tr.fall_state = FALL_DESCENDING
        else:
            tr.low_posture_sec = 0.0
            tr.fall_reason = REASON_NONE
            if fast_kin or slow_kin or (tr.drop_top_m >= 0.45 and tr.f_top_v <= -0.35):
                tr.fall_state = FALL_DESCENDING
            else:
                tr.fall_state = FALL_UPRIGHT

    def _update_track(self, tr, cand, dt, ground_offset_m=None):
        cfg = self.settings
        continuous = (tr.age_frames > 0) and (tr.miss_frames == 0)
        elapsed = dt + tr.missed_sec
        upright = self._upright_geometry(cand, ground_offset_m)
        du_step = cand["cu"] - tr.cu
        dv_step = cand["cv"] - tr.cv
        step_m = math.hypot(du_step, dv_step) if continuous else 0.0

        motion = tr.motion
        moving = False
        if (not upright or not continuous
                or (motion.seconds + dt) > cfg["motion_window_sec"]
                or step_m > cfg["human_max_speed_mps"] * dt
                or abs(cand["height_m"] - tr.height_m) > 0.26):
            tr.motion = _MotionWindow(cand["cu"], cand["cv"])
            tr.upright_frames = 0
        elif tr.upright_frames > 0:
            motion.seconds += dt
            motion.path_m += step_m
            if step_m >= 0.012:
                motion.moving_steps += 1
            range_step = abs(cand["range_m"] - tr.range_m)
            radial_motion = (
                range_step >= max(0.025, 0.70 * step_m)
                and abs(cand["height_m"] - tr.height_m) <= 0.10
                and abs(cand["h_p05"] - tr.h_p05) <= 0.12
                and abs(cand["h_p95"] - tr.h_p95) <= 0.12
                and abs(cand["point_count"] - tr.point_count) <= (tr.point_count // 6)
            )
            dual_half = tr.locked_human or (cand["motion_lower"] >= 2 and cand["motion_upper"] >= 2)
            if radial_motion or (dual_half and cand["motion_points"] >= max(4, cand["point_count"] // 100)):
                motion.depth_frames += 1
            disp = math.hypot(cand["cu"] - motion.origin_u, cand["cv"] - motion.origin_v)
            min_disp = cfg["motion_renew_disp_m"] if tr.locked_human else cfg["motion_lock_disp_m"]
            moving = (motion.moving_steps >= 2 and motion.depth_frames >= 2
                      and disp >= min_disp and disp >= 0.60 * motion.path_m)

        if upright:
            if tr.upright_frames < cfg["lock_min_frames"]:
                tr.upright_frames += 1
            if (moving and tr.upright_frames >= cfg["lock_min_frames"]
                    and cand["horiz_span_m"] >= cfg["human_min_horiz_m"]
                    and (tr.locked_human or cand["point_count"] >= cfg["human_min_lock_points"])):
                tr.motion = _MotionWindow(cand["cu"], cand["cv"])
                if not tr.locked_human:
                    tr.locked_human = True
                    tr.fall_state = FALL_UPRIGHT
                tr.still_sec = 0.0
                tr.renewal_top_h = cand["h_p95"]

        if tr.age_frames == 0:
            tr.start_cu = cand["cu"]
            tr.start_cv = cand["cv"]
            tr.vel_u = 0.0
            tr.vel_v = 0.0
        elif continuous:
            tr.vel_u = 0.65 * tr.vel_u + 0.35 * (du_step / dt)
            tr.vel_v = 0.65 * tr.vel_v + 0.35 * (dv_step / dt)

        tr.measured_this_frame = True
        tr.miss_frames = 0
        tr.missed_sec = 0.0
        tr.age_frames += 1
        tr.point_count = cand["point_count"]
        tr.box_r0, tr.box_c0, tr.box_r1, tr.box_c1 = cand["r0"], cand["c0"], cand["r1"], cand["c1"]
        tr.center = cand["center"]
        tr.cu, tr.cv, tr.ch = cand["cu"], cand["cv"], cand["ch"]
        tr.range_m = cand["range_m"]
        tr.h_p02 = cand["h_p02"]
        tr.h_p05 = cand["h_p05"]
        tr.h_p50 = cand["h_p50"]
        tr.h_p95 = cand["h_p95"]
        tr.height_m = cand["height_m"]
        tr.horiz_span_m = cand["horiz_span_m"]
        tr.aspect = cand["aspect"]
        tr.source_rows = cand["source_rows"]
        tr.cells = cand["cells"]

        if upright and tr.fall_state not in (FALL_DESCENDING, FALL_SUSPECTED):
            if not tr.baseline_ready:
                tr.baseline_top_h = cand["h_p95"]
                tr.baseline_height = cand["height_m"]
                tr.baseline_ready = True
            else:
                alpha = 0.12 if cand["h_p95"] >= tr.baseline_top_h - 0.10 else 0.02
                tr.baseline_top_h = (1.0 - alpha) * tr.baseline_top_h + alpha * cand["h_p95"]
                tr.baseline_height = (1.0 - alpha) * tr.baseline_height + alpha * cand["height_m"]

        self._update_kinematics_and_fall(tr, elapsed, dt if continuous else 0.0)
        if (tr.locked_human and continuous
                and abs(tr.f_top_h - tr.renewal_top_h) >= 0.20
                and abs(tr.h_p95 - tr.f_top_h) <= 0.10
                and cand["horiz_span_m"] >= 0.28):
            tr.still_sec = 0.0
            tr.renewal_top_h = tr.f_top_h

    def _update_background(self, cur_mm, new_owner_grid):
        cfg = self.settings
        h, w = self.shape
        prev = self.prev_range_mm
        bg = self.bg_far_mm

        # 保护短缺测已锁轨迹的原覆盖格
        owner = new_owner_grid
        for tr in self.tracks:
            if (tr.active and tr.locked_human and tr.miss_frames > 0
                    and tr.miss_frames <= cfg["short_miss_frames"]
                    and tr.missed_sec <= cfg["max_gap_sec"]):
                old_mask = (self.owner_grid == (tr.slot + 1)) & (owner == 0)
                if np.any(old_mask):
                    near = (cur_mm == 0) | (np.abs(cur_mm - int(round(tr.range_m * 1000.0))) <= 300)
                    owner[old_mask & near] = tr.slot + 1

        # 保护已锁轨迹 1 像素边框免被背景吞噬
        protect = np.zeros(self.shape, dtype=bool)
        for tr in self.tracks:
            if (tr.active and tr.locked_human
                    and tr.miss_frames <= cfg["short_miss_frames"]
                    and tr.missed_sec <= cfg["max_gap_sec"]):
                r0 = max(0, tr.box_r0 - 1)
                r1 = min(h, tr.box_r1 + 2)
                c0 = max(0, tr.box_c0 - 1)
                c1 = min(w, tr.box_c1 + 2)
                tr_mm = int(round(tr.range_m * 1000.0))
                cur_sub = cur_mm[r0:r1, c0:c1]
                prev_sub = prev[r0:r1, c0:c1]
                bg_sub = bg[r0:r1, c0:c1]
                p_sub = (
                    (cur_sub > 0)
                    & ((bg_sub == 0) | (cur_sub < bg_sub))
                    & (prev_sub > 0)
                    & (np.abs(cur_sub - prev_sub) <= 150)
                    & (np.abs(cur_sub - tr_mm) <= 300)
                )
                protect[r0:r1, c0:c1] |= p_sub

        upd = (cur_mm > 0) & (owner == 0) & (~protect)
        if np.any(upd):
            m_init = upd & (bg == 0) & (prev > 0) & (np.abs(cur_mm - prev) <= 100)
            bg[m_init] = cur_mm[m_init]

            has_bg = upd & (bg > 0)
            m_far = has_bg & (cur_mm > bg + 150)
            bg[m_far] = cur_mm[m_far]

            m_near_bg = has_bg & (~m_far) & (np.abs(cur_mm - bg) <= 150)
            bg[m_near_bg] = ((bg[m_near_bg] * 15 + cur_mm[m_near_bg]) >> 4)

            m_closer = has_bg & (~m_far) & (~m_near_bg) & (prev > 0) & (np.abs(cur_mm - prev) <= 35) & (cur_mm < bg)
            if np.any(m_closer):
                step = np.maximum(1, (bg[m_closer] - cur_mm[m_closer]) >> 5)
                bg[m_closer] = bg[m_closer] - step

        self.owner_grid = owner
        self.prev_range_mm = cur_mm.copy()

    def _select_primary_track(self):
        """单人优先选择：优先已锁定且实测的轨迹（含疑似跌倒优先），保留当前选中防抖。"""
        locked_measured = [tr for tr in self.tracks if tr.active and tr.locked_human and tr.measured_this_frame]
        if not locked_measured:
            # 短缺测已锁轨迹维持连续 ID（但不发布目标点行）
            short_held = [
                tr for tr in self.tracks
                if tr.active and tr.locked_human and tr.miss_frames <= self.settings["short_miss_frames"]
            ]
            if self.selected_track_id is not None:
                for tr in short_held:
                    if tr.id == self.selected_track_id:
                        return None, tr, "short_measurement_gap_held"
            self.selected_track_id = None
            return None, None, "no_locked_human_target"

        if self.selected_track_id is not None:
            for tr in locked_measured:
                if tr.id == self.selected_track_id:
                    return tr, tr, None

        # 按跌倒紧迫度 -> 点数 -> 年龄 排序确定性择优
        def rank(tr):
            urg = 2 if tr.fall_state == FALL_SUSPECTED else (1 if tr.fall_state == FALL_DESCENDING else 0)
            return (urg, tr.point_count, tr.age_frames, -tr.id)

        best = max(locked_measured, key=rank)
        self.selected_track_id = best.id
        return best, best, None

    def step(self, frame, stamp_s, frame_index, *, gravity_up=None, ground_offset_m=None):
        """单帧更新，返回兼容 RangeEngine/HumanPhysicalEvaluator 的完整跟踪与运动学结果。"""
        t0 = time.perf_counter()
        if not math.isfinite(float(stamp_s)):
            self.reset(increment_generation=True)
            raise ValueError("finite source header time required")
        stamp_s = float(stamp_s)
        frame_index = int(frame_index)
        cfg = self.settings

        binding = (frame.binding, frame.grid.sha256)
        reset_reason = None
        if self.binding is not None and binding != self.binding:
            reset_reason = "binding_changed"
            self.reset(increment_generation=True)
        self.binding = binding

        if gravity_up is not None:
            self.set_gravity_up(gravity_up)

        dt_raw = (stamp_s - self.last_stamp_s) if self.last_stamp_s is not None else 0.104
        gap = (self.last_stamp_s is not None) and (
            not math.isfinite(dt_raw) or dt_raw <= 0.0 or dt_raw > cfg["max_gap_sec"]
            or (self.last_frame_index is not None and frame_index <= self.last_frame_index)
        )
        dt = 0.104 if (self.last_stamp_s is None or gap) else max(0.04, dt_raw)
        self.last_stamp_s = stamp_s
        self.last_frame_index = frame_index

        # 构造当前帧毫米距离图
        with np.errstate(invalid="ignore"):
            rm_mm = np.where(frame.valid & np.isfinite(frame.range_m), np.rint(frame.range_m * 1000.0), 0.0)
        cur_mm = np.where(
            (rm_mm >= cfg["min_range_mm"]) & (rm_mm <= cfg["max_range_mm"]),
            rm_mm.astype(np.int32),
            0,
        )
        valid_cur = cur_mm > 0

        # 轨迹过期与断流清理
        retain_owner = np.zeros(cfg["max_tracks"] + 1, dtype=bool)
        expired_ids = []
        for tr in self.tracks:
            if not tr.active:
                continue
            tr.still_sec += dt
            if tr.fall_state == FALL_SUSPECTED:
                tr.suspected_sec += dt
            else:
                tr.suspected_sec = 0.0
            hold = cfg["still_hold_sec"] if tr.locked_human else cfg["motion_window_sec"]
            expired = (tr.suspected_sec >= cfg["suspected_hold_sec"]
                       if tr.fall_state == FALL_SUSPECTED else tr.still_sec >= hold)
            if gap or expired:
                expired_ids.append("g%d_t%04d" % (self.generation, tr.id))
                if tr.id == self.selected_track_id:
                    self.selected_track_id = None
                tr.reset()
            else:
                retain_owner[tr.slot + 1] = True
        if gap:
            reset_reason = reset_reason or "stream_gap"
            self.prev_range_mm.fill(0)
            self.owner_grid.fill(0)
        else:
            keep_own = retain_owner[self.owner_grid]
            self.owner_grid = np.where(keep_own, self.owner_grid, np.uint8(0))

        # 第 0 帧：直接用首帧初始化最远背景，免空场等待
        if self.frame_count == 0:
            self.bg_far_mm = cur_mm.copy()
            self.prev_range_mm = cur_mm.copy()
            self.owner_grid.fill(0)
            self.last_fg_mask.fill(False)
            self.background_adapter.sync(self.bg_far_mm, binding)
            self.frame_count += 1
            static_mask = valid_cur
            t_end = time.perf_counter()
            return self._pack_output(
                frame, stamp_s, frame_index, reset_reason, expired_ids,
                static_mask=static_mask, foot_observations=[],
                valid_cells=int(valid_cur.sum()), fg_seed_cells=0,
                candidate_count=0, ground_offset_m=ground_offset_m,
                timings={"instant_tracker_ms": (t_end - t0) * 1000.0},
                bootstrap_frame=True,
            )

        # 前景种子与运动像素
        closer_bg = valid_cur & (self.bg_far_mm > 0) & (cur_mm + cfg["fg_margin_mm"] < self.bg_far_mm)
        closer_prev = valid_cur & (self.prev_range_mm > 0) & (cur_mm + cfg["fg_margin_mm"] < self.prev_range_mm)
        fg_seed = closer_bg | closer_prev
        motion_mask = valid_cur & (self.prev_range_mm > 0) & (np.abs(cur_mm - self.prev_range_mm) >= cfg["motion_depth_mm"])
        self.last_fg_mask = fg_seed

        visited = np.zeros(self.shape, dtype=bool)
        candidates = []
        h_rows, w_cols = self.shape
        max_r2 = cfg["max_horiz_radius_m"] ** 2

        # 阶段 1：在活跃轨迹预测窗口内保留生长
        for tr in self.tracks:
            if not tr.active:
                continue
            tr.measured_this_frame = False
            pred_mm = int(max(100, min(60000, round(tr.range_m * 1000.0))))
            row_pad = 24 if (tr.locked_human and (tr.drop_top_m >= 0.30 or abs(tr.f_top_v) >= 0.35)) else 12
            r0 = max(0, tr.box_r0 - row_pad)
            c0 = max(0, tr.box_c0 - 12)
            r1 = min(h_rows - 1, tr.box_r1 + row_pad)
            c1 = min(w_cols - 1, tr.box_c1 + 12)

            cur_sub = cur_mm[r0:r1 + 1, c0:c1 + 1]
            vis_sub = visited[r0:r1 + 1, c0:c1 + 1]
            fg_sub = fg_seed[r0:r1 + 1, c0:c1 + 1]
            own_sub = (self.owner_grid[r0:r1 + 1, c0:c1 + 1] == (tr.slot + 1))
            dmm_sub = np.abs(cur_sub - pred_mm)
            seed_ok = (cur_sub > 0) & (~vis_sub) & (dmm_sub <= cfg["retain_margin_mm"]) & (fg_sub | own_sub)
            if not np.any(seed_ok):
                continue
            scores = np.where(seed_ok, dmm_sub - np.where(fg_sub, 250, 0), 10000000)
            flat_best = int(np.argmin(scores))
            sr_local = flat_best // scores.shape[1]
            sc_local = flat_best % scores.shape[1]
            sr_glob = r0 + sr_local
            sc_glob = c0 + sc_local

            # 扩展生长窗口（与 ESP grow_cluster 保持一致：row_pad 16/24, col_pad 16）
            g_row_pad = 24 if (tr.locked_human and (tr.drop_top_m >= 0.30 or abs(tr.f_top_v) >= 0.35)) else 16
            gr0 = max(0, tr.box_r0 - g_row_pad)
            gc0 = max(0, tr.box_c0 - 16)
            gr1 = min(h_rows - 1, tr.box_r1 + g_row_pad)
            gc1 = min(w_cols - 1, tr.box_c1 + 16)

            g_cur = cur_mm[gr0:gr1 + 1, gc0:gc1 + 1]
            g_vis = visited[gr0:gr1 + 1, gc0:gc1 + 1]
            g_fg = fg_seed[gr0:gr1 + 1, gc0:gc1 + 1]
            g_bg = self.bg_far_mm[gr0:gr1 + 1, gc0:gc1 + 1]
            g_own = (self.owner_grid[gr0:gr1 + 1, gc0:gc1 + 1] == (tr.slot + 1))
            g_dmm = np.abs(g_cur - pred_mm)
            tight_body = g_own & (g_dmm <= cfg["retain_tight_mm"])
            growable = (
                (g_cur > 0) & (~g_vis)
                & (g_dmm <= (cfg["retain_margin_mm"] + cfg["retain_extra_mm"]))
                & (g_fg | tight_body | (g_bg == 0) | (g_cur + cfg["bg_grow_margin_mm"] < g_bg))
            )
            growable[sr_glob - gr0, sc_glob - gc0] = True

            # 水平半径门预先向量化施加在 ROI 内
            g_rs, g_cs = np.nonzero(growable)
            if len(g_rs) >= cfg["min_cluster_points"]:
                seed_row = int(frame.source_rows[sr_glob, sc_glob])
                seed_xyz = frame.xyz[seed_row].astype(np.float64)
                seed_u = float(np.dot(seed_xyz, self.u_axis))
                seed_v = float(np.dot(seed_xyz, self.v_axis))
                roi_src = frame.source_rows[gr0 + g_rs, gc0 + g_cs].astype(np.int64)
                roi_xyz = frame.xyz[roi_src].astype(np.float64)
                du = (roi_xyz @ self.u_axis) - seed_u
                dv = (roi_xyz @ self.v_axis) - seed_v
                out_rad = (du * du + dv * dv) > max_r2
                if np.any(out_rad):
                    growable[g_rs[out_rad], g_cs[out_rad]] = False
                    growable[sr_glob - gr0, sc_glob - gc0] = True

                cr, cc = _bfs_single_component_mm(
                    growable, g_cur, sr_glob - gr0, sc_glob - gc0, cfg["bfs_step_mm"]
                )
                if len(cr) > 0:
                    glob_r = gr0 + cr
                    glob_c = gc0 + cc
                    visited[glob_r, glob_c] = True
                    if len(candidates) < cfg["max_candidates"]:
                        cells = (glob_r * w_cols + glob_c).astype(np.int32)
                        cand = self._build_candidate(frame, cells, cur_mm, motion_mask, tr.slot)
                        if cand is not None:
                            candidates.append(cand)

        # 阶段 2：全图向量化发现新前景候选
        growable_disc = (
            valid_cur & (~visited)
            & (fg_seed | (self.bg_far_mm == 0) | (cur_mm + cfg["bg_grow_margin_mm"] < self.bg_far_mm))
        )
        if np.any(fg_seed & (~visited)):
            comps = _connected_components_mm(growable_disc, cur_mm, cfg["bfs_step_mm"])
            fg_flat = fg_seed.ravel()
            for comp_cells in comps:
                if len(candidates) >= cfg["max_candidates"]:
                    break
                if len(comp_cells) < cfg["min_cluster_points"]:
                    continue
                seed_in_comp = comp_cells[fg_flat[comp_cells]]
                if not len(seed_in_comp):
                    continue
                cand = self._build_candidate(frame, comp_cells, cur_mm, motion_mask, -1)
                if cand is not None:
                    visited.ravel()[comp_cells] = True
                    candidates.append(cand)
                else:
                    # 若大连通片跨度超 2.35 m（如与墙面轻微粘连），从最密前景种子按 1.15 m 半径裁切提取
                    mid_seed = int(seed_in_comp[len(seed_in_comp) // 2])
                    sr, sc = mid_seed // w_cols, mid_seed % w_cols
                    seed_xyz = frame.xyz[int(frame.source_rows[sr, sc])].astype(np.float64)
                    su = float(np.dot(seed_xyz, self.u_axis))
                    sv = float(np.dot(seed_xyz, self.v_axis))
                    comp_src = frame.source_rows.ravel()[comp_cells].astype(np.int64)
                    comp_xyz = frame.xyz[comp_src].astype(np.float64)
                    in_r = (((comp_xyz @ self.u_axis) - su) ** 2 + ((comp_xyz @ self.v_axis) - sv) ** 2) <= max_r2
                    sub_cells = comp_cells[in_r]
                    if len(sub_cells) >= cfg["min_cluster_points"]:
                        # 保持 8 邻域深度连通，防止半径裁切后留下孤立碎片
                        sub_rs = sub_cells // w_cols
                        sub_cs = sub_cells % w_cols
                        br0, br1 = int(sub_rs.min()), int(sub_rs.max())
                        bc0, bc1 = int(sub_cs.min()), int(sub_cs.max())
                        sub_mask = np.zeros((br1 - br0 + 1, bc1 - bc0 + 1), dtype=bool)
                        sub_mask[sub_rs - br0, sub_cs - bc0] = True
                        cr, cc = _bfs_single_component_mm(
                            sub_mask, cur_mm[br0:br1 + 1, bc0:bc1 + 1],
                            sr - br0, sc - bc0, cfg["bfs_step_mm"],
                        )
                        if len(cr) >= cfg["min_cluster_points"]:
                            conn_cells = ((br0 + cr) * w_cols + (bc0 + cc)).astype(np.int32)
                            sub_cand = self._build_candidate(frame, conn_cells, cur_mm, motion_mask, -1)
                            if sub_cand is not None:
                                visited.ravel()[conn_cells] = True
                                candidates.append(sub_cand)

        # 阶段 3：门控贪心关联（保留源优先 → 已锁轨优先 → 候补轨 → 缺测老化 → 新生）
        cand_slots = [0] * len(candidates)
        for i, cand in enumerate(candidates):
            if not cand["from_retain"]:
                continue
            slot = cand["retain_track_slot"]
            if 0 <= slot < len(self.tracks) and self.tracks[slot].active:
                tr = self.tracks[slot]
                if math.isfinite(self._association_distance_sq(tr, cand, dt, ground_offset_m)):
                    self._update_track(tr, cand, dt, ground_offset_m)
                    cand_slots[i] = slot + 1

        for want_locked in (True, False):
            for tr in self.tracks:
                if not tr.active or tr.measured_this_frame or tr.locked_human != want_locked:
                    continue
                best_i = -1
                best_d = float("inf")
                for i, cand in enumerate(candidates):
                    if cand_slots[i]:
                        continue
                    d = self._association_distance_sq(tr, cand, dt, ground_offset_m)
                    if d < best_d:
                        best_d = d
                        best_i = i
                if best_i >= 0:
                    self._update_track(tr, candidates[best_i], dt, ground_offset_m)
                    cand_slots[best_i] = tr.slot + 1

        # 3c. 未实测轨迹老化（不编造测量点）
        for tr in self.tracks:
            if not tr.active or tr.measured_this_frame:
                continue
            tr.source_rows = []
            tr.cells = np.empty(0, dtype=np.int32)
            tr.miss_frames += 1
            tr.missed_sec += dt
            if tr.locked_human and tr.miss_frames <= cfg["short_miss_frames"] and tr.missed_sec <= cfg["max_gap_sec"]:
                continue
            tr.vel_u = 0.0
            tr.vel_v = 0.0
            tr.filter_init = False
            tr.history.clear()
            tr.peak_down_vel = tr.peak_down_acc = tr.peak_brake_acc = 0.0
            tr.low_posture_sec = 0.0
            tr.fall_reason = REASON_NONE
            tr.fall_state = FALL_UPRIGHT if tr.locked_human else FALL_UNKNOWN
            if tr.miss_frames > cfg["max_miss_frames"]:
                expired_ids.append("g%d_t%04d" % (self.generation, tr.id))
                if tr.id == self.selected_track_id:
                    self.selected_track_id = None
                tr.reset()

        # 3d. 未匹配直立候选新生轨迹
        for i, cand in enumerate(candidates):
            if cand_slots[i] or not self._upright_geometry(cand, ground_offset_m):
                continue
            free_tr = next((tr for tr in self.tracks if not tr.active), None)
            if free_tr is None:
                break
            free_tr.reset()
            free_tr.active = True
            free_tr.id = self.next_track_id
            self.next_track_id += 1
            free_tr.fall_state = FALL_UNKNOWN
            free_tr.fall_reason = REASON_NONE
            self._update_track(free_tr, cand, dt, ground_offset_m)
            cand_slots[i] = free_tr.slot + 1

        # 阶段 4：构造覆盖归属掩码并更新自适应远景背景
        new_owner = np.zeros(self.shape, dtype=np.uint8)
        for i, cand in enumerate(candidates):
            slot = cand_slots[i] - 1
            if slot < 0:
                continue
            tr = self.tracks[slot]
            if not tr.locked_human:
                if cand["motion_points"] < 4 and (cand["retain_track_slot"] != slot or cand["owned_points"] < 4):
                    continue
            new_owner.ravel()[cand["cells"]] = slot + 1
        self._update_background(cur_mm, new_owner)
        self.background_adapter.sync(self.bg_far_mm, binding)
        self.frame_count += 1

        # 收集直立已锁目标的脚底观测供后台精修交叉校验 / 兜底
        foot_observations = []
        for tr in self.tracks:
            if (tr.active and tr.locked_human and tr.measured_this_frame
                    and tr.fall_state == FALL_UPRIGHT
                    and tr.box_r0 > 2
                    and 1.10 <= tr.height_m <= 2.05):
                foot_observations.append((tr.h_p02, tr.cu, tr.cv))

        static_mask = valid_cur & (~fg_seed) & (self.owner_grid == 0)
        t_end = time.perf_counter()
        return self._pack_output(
            frame, stamp_s, frame_index, reset_reason, expired_ids,
            static_mask=static_mask, foot_observations=foot_observations,
            valid_cells=int(valid_cur.sum()), fg_seed_cells=int(fg_seed.sum()),
            candidate_count=len(candidates), ground_offset_m=ground_offset_m,
            timings={"instant_tracker_ms": (t_end - t0) * 1000.0},
            bootstrap_frame=False,
        )

    def _pack_output(self, frame, stamp_s, frame_index, reset_reason, expired_ids, *,
                     static_mask, foot_observations, valid_cells, fg_seed_cells,
                     candidate_count, ground_offset_m, timings, bootstrap_frame):
        primary, continuity_tr, target_reason = self._select_primary_track()
        tracks_out = []
        for tr in self.tracks:
            if not tr.active:
                continue
            tid = "g%d_t%04d" % (self.generation, tr.id)
            h_off = float(ground_offset_m) if ground_offset_m is not None else None
            tracks_out.append({
                "track_id": tid,
                "raw_track_id": tr.id,
                "status": "locked" if (tr.locked_human and tr.measured_this_frame) else (
                    "held" if tr.locked_human else "tentative"
                ),
                "locked_human": tr.locked_human,
                "observed": bool(tr.measured_this_frame and tr.source_rows),
                "source_rows": list(tr.source_rows) if tr.measured_this_frame else [],
                "point_count": int(tr.point_count if tr.measured_this_frame else 0),
                "age_frames": int(tr.age_frames),
                "miss_frames": int(tr.miss_frames),
                "range_m": round(float(tr.range_m), 4),
                "height_span_m": round(float(tr.height_m), 4),
                "horiz_span_m": round(float(tr.horiz_span_m), 4),
                "aspect": round(float(tr.aspect), 3),
                "height_median_m": None if h_off is None else round(float(tr.h_p50 + h_off), 4),
                "height_top_m": None if h_off is None else round(float(tr.h_p95 + h_off), 4),
                "height_bottom_m": None if h_off is None else round(float(tr.h_p05 + h_off), 4),
                "baseline_ready": tr.baseline_ready,
                "drop_top_m": round(float(tr.drop_top_m), 4),
                "vel_top_mps": round(float(tr.f_top_v), 4),
                "acc_top_mps2": round(float(tr.f_top_a), 4),
                "peak_down_vel_mps": round(float(tr.peak_down_vel), 4),
                "peak_down_acc_mps2": round(float(tr.peak_down_acc), 4),
                "peak_brake_acc_mps2": round(float(tr.peak_brake_acc), 4),
                "low_posture_sec": round(float(tr.low_posture_sec), 3),
                "still_sec": round(float(tr.still_sec), 3),
                "fall_state": tr.fall_state,
                "fall_reason": tr.fall_reason,
                "selection_score": float(tr.point_count) if tr.locked_human else 0.0,
                "component_ids": [],
                "reason": "locked_human" if tr.locked_human else "tentative_motion_check",
            })

        target_tid = ("g%d_t%04d" % (self.generation, primary.id)) if primary is not None else None
        cont_tid = ("g%d_t%04d" % (self.generation, continuity_tr.id)) if continuity_tr is not None else None
        target_rows = list(primary.source_rows) if primary is not None else []
        state_tr = primary if primary is not None else continuity_tr

        if bootstrap_frame:
            fall_status = FALL_UNKNOWN
            reason_codes = ["instant_frame0_bootstrap"]
            kinematics = None
        elif state_tr is None:
            fall_status = FALL_UNKNOWN
            reason_codes = [target_reason or "no_locked_human_target"]
            kinematics = None
        else:
            fall_status = state_tr.fall_state
            reason_codes = []
            if state_tr.fall_reason != REASON_NONE:
                reason_codes.append(state_tr.fall_reason)
            if state_tr.baseline_ready:
                reason_codes.append("personal_upright_baseline_ready")
            if state_tr.low_posture_sec > 0.0:
                reason_codes.append("collapsed_low_posture_sustained")
            if not state_tr.measured_this_frame:
                reason_codes.append("short_measurement_gap_held")
            if not reason_codes:
                reason_codes.append("kinematic_" + fall_status)
            kinematics = {
                "method": "instant_gravity_kinematics_v1",
                "track_id": cont_tid,
                "measured_this_frame": state_tr.measured_this_frame,
                "baseline_ready": state_tr.baseline_ready,
                "height_span_m": round(float(state_tr.height_m), 4),
                "horiz_span_m": round(float(state_tr.horiz_span_m), 4),
                "aspect": round(float(state_tr.aspect), 3),
                "drop_top_m": round(float(state_tr.drop_top_m), 4),
                "vel_top_mps": round(float(state_tr.f_top_v), 4),
                "acc_top_mps2": round(float(state_tr.f_top_a), 4),
                "peak_down_vel_mps": round(float(state_tr.peak_down_vel), 4),
                "peak_down_acc_mps2": round(float(state_tr.peak_down_acc), 4),
                "peak_brake_acc_mps2": round(float(state_tr.peak_brake_acc), 4),
                "low_posture_sec": round(float(state_tr.low_posture_sec), 3),
                "still_sec": round(float(state_tr.still_sec), 3),
                "fall_state": fall_status,
                "fall_reason": state_tr.fall_reason,
                "confirmed_enabled": False,
                "semantic": "UNKNOWN",
            }

        h_off = float(ground_offset_m) if ground_offset_m is not None else None
        if primary is not None:
            height_median_m = None if h_off is None else round(float(primary.h_p50 + h_off), 4)
            top_height_m = None if h_off is None else round(float(primary.h_p95 + h_off), 4)
            bottom_height_m = None if h_off is None else round(float(primary.h_p05 + h_off), 4)
            horiz_extent_m = round(float(primary.horiz_span_m), 4)
            descent_rate_mps = round(float(primary.f_top_v), 4)
            axis_vert = round(float(min(1.0, primary.height_m / max(0.15, math.hypot(primary.height_m, primary.horiz_span_m)))), 4)
            # 简易几何姿态摘要（不阻塞运动学跌倒判别）
            if primary.height_m <= self.settings["collapsed_height_m"] and primary.aspect <= self.settings["collapsed_aspect_max"]:
                posture_state = "lying_candidate" if primary.low_posture_sec >= self.settings["fall_hold_sec"] else "lying_pending"
            elif primary.height_m >= 0.90 and primary.aspect >= 1.05:
                posture_state = "standing"
            elif primary.height_m >= 0.45:
                posture_state = "sitting"
            else:
                posture_state = "unknown"
            posture = {
                "state": posture_state,
                "reason": "instant_gravity_posture",
                "durationSec": round(float(primary.low_posture_sec), 3),
                "stable": posture_state,
                "humanSemantic": "UNKNOWN",
                "fallEvent": False,
            }
        else:
            height_median_m = top_height_m = bottom_height_m = None
            horiz_extent_m = descent_rate_mps = axis_vert = None
            posture = {
                "state": "unknown",
                "reason": target_reason or "no_locked_human_target",
                "durationSec": 0.0,
                "stable": None,
                "humanSemantic": "UNKNOWN",
                "fallEvent": False,
            }

        record = {
            "frame": frame_index,
            "time_s": stamp_s,
            "generation": self.generation,
            "reset_reason": reset_reason,
            "tracks": tracks_out,
            "target_track_id": target_tid,
            "continuity_track_id": cont_tid,
            "target_source_rows": target_rows,
            "target_features": None,
            "target_reason": "instant_bootstrap" if bootstrap_frame else target_reason,
            "association_edges": {},
            "compositions": [],
            "ambiguous_component_ids": [],
            "expired_track_ids": expired_ids,
            "semantic": "unknown",
        }

        fall_evidence = {
            "state": fall_status,
            "reason_codes": reason_codes,
            "confirmed_enabled": False,
            "new_event": None,
            "method": "instant_gravity_kinematics_v1",
            "low_duration_s": round(float(state_tr.low_posture_sec), 3) if state_tr is not None else 0.0,
            "drop_top_m": round(float(state_tr.drop_top_m), 4) if state_tr is not None else None,
            "fall_reason": state_tr.fall_reason if state_tr is not None else REASON_NONE,
            "semantic": "UNKNOWN",
        }

        measurement = {
            "topHeightM": top_height_m,
            "bottomHeightM": bottom_height_m,
            "heightSpanM": round(float(primary.height_m), 4) if primary is not None else None,
            "horizontalExtentM": horiz_extent_m,
            "descentRateMps": descent_rate_mps,
            "axisVerticality": axis_vert,
            "dropTopM": round(float(primary.drop_top_m), 4) if primary is not None else None,
            "groundRelativeAvailable": h_off is not None,
        }

        return {
            "tracking": record,
            "fall_status": fall_status,
            "fall_evidence": fall_evidence,
            "kinematics": kinematics,
            "measurement": measurement,
            "height_median_m": height_median_m,
            "posture": posture,
            "static_mask": static_mask,
            "foot_observations": foot_observations,
            "valid_cells": valid_cells,
            "fg_seed_cells": fg_seed_cells,
            "candidate_count": candidate_count,
            "timings": timings,
            "bootstrap_frame": bootstrap_frame,
        }
