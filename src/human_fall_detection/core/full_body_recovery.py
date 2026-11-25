"""双阈值“核心 -> 肢体”完整人体局部回收（纯雷达，stdlib + NumPy）。

设计原则：
- 绝不降低全局前景差分阈值；只在已确认核心的局部 3D 圆柱包络内放宽差分门限（0.08–0.12 m）。
- 精细地面法向剥离：仅剔除“贴合地面 < 0.04 m 且法向严格朝上 (|nz| > 0.92)”的纯地面点，
  尽可能保留贴地脚背、脚踝、小腿与垂臂。
- 法向平滑与平面截断生长：从核心像素向外 8 邻域生长，遇大面积刚性平面法向跳变立即截断，
  切断与椅背、桌面或墙面的粘连。
- 严格安全护栏：与其他实测轨迹相交、点数膨胀超限、水平包络骤增或平面泄漏时整次拒绝并记录
  `recovery_rejected_reason`，回退到原始核心 `core_rows`。
- 语义诚实：回收结果是几何支撑候选，不声称人体点级完整性真值（`completeness='UNKNOWN'`）。
"""

from collections import deque

import numpy as np

try:  # pragma: no cover - import shim
    from .lidar_candidates import ground_plane_basis
    from .range_features import bound_ground
    from .range_normals import cluster_normal_features, estimate_grid_normals
except ImportError:  # pragma: no cover
    from lidar_candidates import ground_plane_basis
    from range_features import bound_ground
    from range_normals import cluster_normal_features, estimate_grid_normals


DEFAULT_RECOVERY_SETTINGS = {
    "relaxed_delta_m": 0.10,
    "sigma_multiplier": 3.0,
    "min_range_m": 0.10,
    "max_range_m": 8.0,
    "cylinder_pad_m": 0.45,
    "max_cylinder_radius_m": 1.15,
    "min_body_height_m": -0.04,
    "max_body_height_m": 2.25,
    "ground_peel_height_m": 0.04,
    "ground_peel_nz_min": 0.92,
    "edge_depth_base_m": 0.06,
    "edge_depth_slope": 0.015,
    "planar_cut_cos_max": 0.50,          # > 60 deg normal bend into flat sheet
    "hard_crease_cos_max": 0.25,         # > 75 deg sharp 1-pixel normal fold
    "planar_patch_roughness_max": 0.012,
    "max_expansion_ratio": 2.8,
    "max_recovered_horiz_m": 1.95,
    "max_horiz_growth_m": 0.65,
    "max_planar_leak_ratio": 0.80,
    "core_planar_safe_margin": 0.72,
    "added_plane_min_points": 25,
    "added_plane_reject_ratio": 0.85,
    "added_plane_max_entropy": 0.30,
    "added_plane_min_fraction": 0.25,
    "near_ground_band_m": 0.25,
    "low_posture_band_m": 0.60,
}


def resolve_recovery_settings(settings=None):
    resolved = dict(DEFAULT_RECOVERY_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown full_body_recovery setting: " + str(key))
        resolved[key] = value
    if (isinstance(resolved["added_plane_min_points"], bool)
            or int(resolved["added_plane_min_points"]) != resolved["added_plane_min_points"]
            or int(resolved["added_plane_min_points"]) < 5):
        raise ValueError("added_plane_min_points must be an integer >= 5")
    resolved["added_plane_min_points"] = int(resolved["added_plane_min_points"])
    for key in resolved:
        if key == "added_plane_min_points":
            continue
        val = float(resolved[key])
        if not np.isfinite(val):
            raise ValueError(key + " must be finite")
        resolved[key] = val
    if not (0.04 <= resolved["relaxed_delta_m"] <= 0.25):
        raise ValueError("relaxed_delta_m must be within [0.04, 0.25]")
    if resolved["max_expansion_ratio"] < 1.0:
        raise ValueError("max_expansion_ratio must be >= 1.0")
    return resolved


def _horiz_span(u, v):
    if len(u) <= 1:
        return 0.0
    if len(u) >= 10:
        su = float(np.percentile(u, 95.0) - np.percentile(u, 5.0))
        sv = float(np.percentile(v, 95.0) - np.percentile(v, 5.0))
        return max(su, sv)
    return max(float(u.max() - u.min()), float(v.max() - v.min()))


def recover_full_body(frame, background, core_rows, ground, grid_normals=None,
                      other_tracks_rows=None, settings=None):
    """在已确认目标核心的局部 3D 圆柱内执行法向引导低阈值完整人体点集回收。"""
    cfg = resolve_recovery_settings(settings)
    rows_arr = np.asarray(core_rows, dtype=np.int64)
    base_result = {
        "status": "unavailable",
        "recovery_rejected_reason": None,
        "core_count": int(len(rows_arr)),
        "recovered_count": int(len(rows_arr)),
        "added_count": 0,
        "core_rows": rows_arr.tolist(),
        "added_rows": [],
        "recovered_rows": rows_arr.tolist(),
        "breakdown": {
            "added_near_ground_count": 0,
            "added_low_posture_count": 0,
            "added_boundary_count": 0,
            "peeled_ground_pixels": 0,
            "cut_planar_edges": 0,
            "core_horiz_span_m": None,
            "recovered_horiz_span_m": None,
            "core_single_plane_ratio": None,
            "recovered_single_plane_ratio": None,
        },
        "completeness": "UNKNOWN",
        "semantic": "UNKNOWN",
    }

    if rows_arr.ndim != 1 or not rows_arr.size:
        base_result["recovery_rejected_reason"] = "empty_core_rows"
        return base_result
    if (len(np.unique(rows_arr)) != len(rows_arr)
            or rows_arr.min() < 0 or rows_arr.max() >= len(frame.xyz)):
        raise ValueError("core_rows must be unique valid current measurement rows")

    plane = bound_ground(frame, ground)
    basis = ground_plane_basis(plane) if plane is not None else None
    if basis is None:
        base_result["recovery_rejected_reason"] = "ground_unavailable_or_unbound"
        return base_result
    if background is None or not hasattr(background, "known") or not hasattr(background, "mean_m"):
        base_result["recovery_rejected_reason"] = "background_unavailable"
        return base_result

    if grid_normals is None:
        grid_normals = estimate_grid_normals(frame)

    core_cells = grid_normals.row_to_cell[rows_arr]
    if (core_cells < 0).any():
        raise ValueError("core_rows must map to current valid grid cells")

    g_norm, axis_u, axis_v = basis
    offset_m = float(plane["offset_m"])
    h, w = frame.grid.shape

    core_xyz = frame.xyz[rows_arr].astype(np.float64)
    core_u = core_xyz @ axis_u
    core_v = core_xyz @ axis_v
    core_h = core_xyz @ g_norm + offset_m
    cu = float(np.median(core_u))
    cv = float(np.median(core_v))
    core_radii = np.hypot(core_u - cu, core_v - cv)
    r_core = float(np.percentile(core_radii, 95.0)) if len(core_radii) >= 5 else float(core_radii.max())
    cyl_radius = min(cfg["max_cylinder_radius_m"], r_core + cfg["cylinder_pad_m"])
    core_span = _horiz_span(core_u, core_v)
    base_result["breakdown"]["core_horiz_span_m"] = round(core_span, 4)

    core_y = core_cells // w
    core_x = core_cells % w
    # 局部 2D 网格搜索窗（包含向下延伸到底部的脚/小腿与周边肢体）
    pad_r = max(24, int(0.45 * (int(core_y.max() - core_y.min()) + 1)))
    pad_c = max(20, int(0.45 * (int(core_x.max() - core_x.min()) + 1)))
    y0 = max(0, int(core_y.min()) - pad_r)
    y1 = min(h, int(core_y.max()) + pad_r + 1)
    x0 = max(0, int(core_x.min()) - pad_c)
    x1 = min(w, int(core_x.max()) + pad_c + 1)

    roi_valid = frame.valid[y0:y1, x0:x1]
    roi_known = background.known[y0:y1, x0:x1]
    roi_r = frame.range_m[y0:y1, x0:x1]
    roi_bg = background.mean_m[y0:y1, x0:x1]
    roi_xyz = grid_normals.grid_xyz[y0:y1, x0:x1, :]
    roi_normals = grid_normals.normals[y0:y1, x0:x1, :]
    roi_nvalid = grid_normals.valid[y0:y1, x0:x1]
    roi_rough = grid_normals.local_roughness[y0:y1, x0:x1]

    seed_roi = np.zeros((y1 - y0, x1 - x0), dtype=bool)
    seed_roi[core_y - y0, core_x - x0] = True

    with np.errstate(invalid="ignore"):
        delta = roi_bg - roi_r
        delta_thresh = np.full(delta.shape, cfg["relaxed_delta_m"], dtype=np.float64)
        if hasattr(background, "sigma_m") and background.sigma_m is not None:
            sig = background.sigma_m[y0:y1, x0:x1]
            delta_thresh = np.maximum(delta_thresh, cfg["sigma_multiplier"] * sig)
        relaxed = (roi_valid & roi_known & (delta > delta_thresh)
                   & (roi_r >= cfg["min_range_m"]) & (roi_r <= cfg["max_range_m"]))

        # 局部 3D 圆柱包络约束（高度 + 水平半径）
        roi_h = np.einsum("ijk,k->ij", roi_xyz, g_norm) + offset_m
        roi_u = np.einsum("ijk,k->ij", roi_xyz, axis_u)
        roi_v = np.einsum("ijk,k->ij", roi_xyz, axis_v)
        in_cyl = (np.hypot(roi_u - cu, roi_v - cv) <= cyl_radius) & (
            roi_h >= cfg["min_body_height_m"]) & (roi_h <= cfg["max_body_height_m"])

        # 地面法向精细剥离：仅剔除贴合地面 (<4 cm) 且法向严格朝上 (|nz| > 0.92) 的平坦地面点
        roi_nz = np.einsum("ijk,k->ij", roi_normals, g_norm)
        flat_ground = (roi_h < cfg["ground_peel_height_m"]) & (
            (roi_nvalid & (np.abs(roi_nz) > cfg["ground_peel_nz_min"]))
            | (~roi_nvalid)
        )

    peeled_mask = relaxed & in_cyl & ~seed_roi & flat_ground
    peeled_ground_pixels = int(peeled_mask.sum())
    eligible = seed_roi | (relaxed & in_cyl & ~flat_ground)

    # 向量化预计算 8 邻域允许扩展位掩码与刚性平面截断位掩码，消除 BFS 内层 NumPy 标量索引开销
    rh, rw = eligible.shape
    dirs = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
    cos_max = cfg["planar_cut_cos_max"]
    hard_cos_max = cfg["hard_crease_cos_max"]
    rough_max = cfg["planar_patch_roughness_max"]
    d_base = cfg["edge_depth_base_m"]
    d_slope = cfg["edge_depth_slope"]

    allow_bits = np.zeros((rh, rw), dtype=np.uint8)
    cut_bits = np.zeros((rh, rw), dtype=np.uint8)
    with np.errstate(invalid="ignore"):
        flat_cell = np.isfinite(roi_rough) & (roi_rough <= rough_max)
        for bit_idx, (dy, dx) in enumerate(dirs):
            sy0 = max(0, -dy)
            sy1 = rh - max(0, dy)
            sx0 = max(0, -dx)
            sx1 = rw - max(0, dx)
            if sy0 >= sy1 or sx0 >= sx1:
                continue
            ty0, ty1 = sy0 + dy, sy1 + dy
            tx0, tx1 = sx0 + dx, sx1 + dx

            src_ok = eligible[sy0:sy1, sx0:sx1]
            dst_ok = eligible[ty0:ty1, tx0:tx1]
            r_src = roi_r[sy0:sy1, sx0:sx1]
            r_dst = roi_r[ty0:ty1, tx0:tx1]
            lim = np.maximum(d_base, d_slope * np.minimum(r_src, r_dst))
            depth_ok = src_ok & dst_ok & (np.abs(r_dst - r_src) <= lim)
            if not depth_ok.any():
                continue

            both_n = depth_ok & roi_nvalid[sy0:sy1, sx0:sx1] & roi_nvalid[ty0:ty1, tx0:tx1]
            planar_cut = np.zeros(depth_ok.shape, dtype=bool)
            if both_n.any():
                dots = np.einsum(
                    "ijk,ijk->ij",
                    roi_normals[sy0:sy1, sx0:sx1, :],
                    roi_normals[ty0:ty1, tx0:tx1, :],
                )
                hard_cut = both_n & (dots < hard_cos_max)
                soft_cand = both_n & (dots < cos_max) & ~hard_cut
                if soft_cand.any():
                    nb_flat = flat_cell[ty0:ty1, tx0:tx1].copy()
                    # 前进 1 步延续点检查，避免缝隙像素粗糙度污染导致漏切刚性平面
                    ay0, ay1 = ty0 + dy, ty1 + dy
                    ax0, ax1 = tx0 + dx, tx1 + dx
                    my0 = max(0, -ay0)
                    my1 = (ay1 - ay0) - max(0, ay1 - rh)
                    mx0 = max(0, -ax0)
                    mx1 = (ax1 - ax0) - max(0, ax1 - rw)
                    if my0 < my1 and mx0 < mx1:
                        nb_flat[my0:my1, mx0:mx1] |= flat_cell[
                            ay0 + my0:ay0 + my1, ax0 + mx0:ax0 + mx1
                        ]
                    planar_cut = hard_cut | (soft_cand & nb_flat)
                else:
                    planar_cut = hard_cut

            bit = np.uint8(1 << bit_idx)
            allow_bits[sy0:sy1, sx0:sx1] |= np.where(depth_ok & ~planar_cut, bit, np.uint8(0))
            cut_bits[sy0:sy1, sx0:sx1] |= np.where(planar_cut, bit, np.uint8(0))

    # 纯 Python 扁平索引 BFS（零 NumPy 逐元素开销）
    allow_flat = allow_bits.ravel().tolist()
    cut_flat = cut_bits.ravel().tolist()
    visited_flat = seed_roi.ravel().tolist()
    offsets = tuple(dy * rw + dx for dy, dx in dirs)
    bits = (1, 2, 4, 8, 16, 32, 64, 128)
    queue = deque(np.flatnonzero(seed_roi.ravel()).tolist())
    cut_planar_edges = 0

    while queue:
        idx = queue.popleft()
        ab = allow_flat[idx]
        cb = cut_flat[idx]
        if cb:
            for bit, off in zip(bits, offsets):
                if (cb & bit) and not visited_flat[idx + off]:
                    cut_planar_edges += 1
        if ab:
            for bit, off in zip(bits, offsets):
                if ab & bit:
                    nxt = idx + off
                    if not visited_flat[nxt]:
                        visited_flat[nxt] = True
                        queue.append(nxt)

    visited = np.asarray(visited_flat, dtype=bool).reshape((rh, rw))

    base_result["breakdown"]["peeled_ground_pixels"] = peeled_ground_pixels
    base_result["breakdown"]["cut_planar_edges"] = cut_planar_edges

    rec_y, rec_x = np.nonzero(visited)
    rec_rows = np.unique(frame.source_rows[rec_y + y0, rec_x + x0].astype(np.int64))
    added_rows = np.setdiff1d(rec_rows, rows_arr, assume_unique=True)

    if not added_rows.size:
        base_result["status"] = "no_addition"
        base_result["breakdown"]["recovered_horiz_span_m"] = round(core_span, 4)
        return base_result

    # 安全护栏 1：与其他实测轨迹冲突则整次拒绝
    for other in (other_tracks_rows or []):
        other_arr = np.asarray(other, dtype=np.int64)
        if other_arr.size and np.intersect1d(rec_rows, other_arr, assume_unique=False).size:
            base_result["status"] = "rejected"
            base_result["recovery_rejected_reason"] = "competing_observed_track"
            return base_result

    # 安全护栏 2：点数膨胀超限
    if len(rec_rows) > cfg["max_expansion_ratio"] * len(rows_arr):
        base_result["status"] = "rejected"
        base_result["recovery_rejected_reason"] = "expansion_ratio_exceeded"
        return base_result

    # 安全护栏 3：物理包络骤增检查
    rec_xyz = frame.xyz[rec_rows].astype(np.float64)
    rec_u = rec_xyz @ axis_u
    rec_v = rec_xyz @ axis_v
    rec_h = rec_xyz @ g_norm + offset_m
    rec_span = _horiz_span(rec_u, rec_v)
    base_result["breakdown"]["recovered_horiz_span_m"] = round(rec_span, 4)
    if (rec_span > min(cfg["max_recovered_horiz_m"], core_span + cfg["max_horiz_growth_m"])
            or float(rec_h.max()) > cfg["max_body_height_m"]):
        base_result["status"] = "rejected"
        base_result["recovery_rejected_reason"] = "envelope_surge_exceeded"
        return base_result

    # 安全护栏 4：平面泄漏检查（避免生长吞入大面积墙面/椅背/桌面）
    core_nf = cluster_normal_features(frame, rows_arr, grid_normals=grid_normals, ground=plane)
    rec_nf = cluster_normal_features(frame, rec_rows, grid_normals=grid_normals, ground=plane)
    core_sp = core_nf.get("single_plane_inlier_ratio") if core_nf.get("available") else None
    rec_sp = rec_nf.get("single_plane_inlier_ratio") if rec_nf.get("available") else None
    base_result["breakdown"]["core_single_plane_ratio"] = core_sp
    base_result["breakdown"]["recovered_single_plane_ratio"] = rec_sp

    if (core_sp is not None and rec_sp is not None
            and core_sp < cfg["core_planar_safe_margin"]
            and rec_sp >= cfg["max_planar_leak_ratio"]):
        base_result["status"] = "rejected"
        base_result["recovery_rejected_reason"] = "planar_leakage_detected"
        return base_result

    if len(added_rows) >= cfg["added_plane_min_points"]:
        added_nf = cluster_normal_features(frame, added_rows, grid_normals=grid_normals, ground=plane)
        added_sp = added_nf.get("single_plane_inlier_ratio") if added_nf.get("available") else None
        added_ent = added_nf.get("normal_azimuth_entropy") if added_nf.get("available") else None
        if (added_sp is not None and added_ent is not None
                and added_sp >= cfg["added_plane_reject_ratio"]
                and added_ent <= cfg["added_plane_max_entropy"]
                and len(added_rows) >= cfg["added_plane_min_fraction"] * len(rows_arr)):
            base_result["status"] = "rejected"
            base_result["recovery_rejected_reason"] = "added_planar_surface_leakage"
            return base_result

    # 新增点分解账本（近地/低姿/边界）
    added_xyz = frame.xyz[added_rows].astype(np.float64)
    added_h = added_xyz @ g_norm + offset_m
    added_near_ground = int((added_h <= cfg["near_ground_band_m"]).sum())
    added_low_posture = int((added_h <= cfg["low_posture_band_m"]).sum())
    added_boundary = int(len(added_rows) - added_low_posture)

    base_result.update({
        "status": "recovered",
        "recovery_rejected_reason": None,
        "recovered_count": int(len(rec_rows)),
        "added_count": int(len(added_rows)),
        "added_rows": added_rows.tolist(),
        "recovered_rows": rec_rows.tolist(),
    })
    base_result["breakdown"].update({
        "added_near_ground_count": added_near_ground,
        "added_low_posture_count": added_low_posture,
        "added_boundary_count": added_boundary,
    })
    return base_result
