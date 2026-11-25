"""有序 2D 距离图局部表面法向与平面度分析（仅 stdlib + NumPy，纯雷达）。

利用 IFW192S 192x256 原生有序网格直接做邻域 3D 叉乘估计表面法向（深度跳变处断边），
为人体物理相容性校验与局部完整肢体回收提供：
- 水平方位角法向熵（normal_azimuth_entropy）
- 确定性单平面 / 双平面内点占比（single_plane_inlier_ratio / dual_plane_inlier_ratio）
- 近地表面法向朝上一致性（ground_normal_alignment）
- 局部法向粗糙度（local_roughness）

严格语义：本模块只输出几何/表面物理统计，不输出人体身份或准确率。
"""

import numpy as np

try:  # pragma: no cover - import shim
    from .lidar_candidates import ground_plane_basis
    from .range_features import bound_ground
except ImportError:  # pragma: no cover
    from lidar_candidates import ground_plane_basis
    from range_features import bound_ground


DEFAULT_NORMAL_SETTINGS = {
    "max_edge_jump_m": 0.25,
    "min_normal_points": 15,
    "azimuth_bins": 12,
    "elevation_bins": 6,
    "non_horiz_min_mag": 0.25,
    "plane_dist_tol_m": 0.035,
    "plane_normal_cos_min": 0.927,  # cos(22 deg)
    "dual_plane_max_abs_dot": 0.75,  # >= ~41 deg separation
    "ground_band_m": 0.10,
    "ground_up_cos_min": 0.90,
}


def resolve_normal_settings(settings=None):
    resolved = dict(DEFAULT_NORMAL_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown range normal setting: " + str(key))
        resolved[key] = value
    for key in ("min_normal_points", "azimuth_bins", "elevation_bins"):
        if isinstance(resolved[key], bool) or int(resolved[key]) != resolved[key] or int(resolved[key]) < 2:
            raise ValueError(key + " must be an integer >= 2")
        resolved[key] = int(resolved[key])
    for key in ("max_edge_jump_m", "non_horiz_min_mag", "plane_dist_tol_m",
                "plane_normal_cos_min", "dual_plane_max_abs_dot",
                "ground_band_m", "ground_up_cos_min"):
        val = float(resolved[key])
        if not np.isfinite(val) or val < 0.0:
            raise ValueError(key + " must be a finite non-negative number")
        resolved[key] = val
    if resolved["max_edge_jump_m"] <= 0.0 or resolved["plane_dist_tol_m"] <= 0.0:
        raise ValueError("jump and plane distance tolerances must be positive")
    return resolved


class GridNormals:
    """单帧有序 2D 网格的表面法向与局部粗糙度缓存（与 RangeFrame 强绑定）。"""

    __slots__ = (
        "shape",
        "max_edge_jump_m",
        "grid_xyz",
        "normals",
        "valid",
        "local_roughness",
        "row_to_cell",
        "valid_normal_count",
    )

    def __init__(self, shape, max_edge_jump_m, grid_xyz, normals, valid,
                 local_roughness, row_to_cell):
        self.shape = tuple(shape)
        self.max_edge_jump_m = float(max_edge_jump_m)
        self.grid_xyz = grid_xyz
        self.normals = normals
        self.valid = valid
        self.local_roughness = local_roughness
        self.row_to_cell = row_to_cell
        self.valid_normal_count = int(valid.sum())


def _compute_normals_window(frame, valid_full, h, w, jump, box,
                            grid_xyz, normals, normal_valid, local_roughness, row_to_cell):
    ry0 = max(0, int(box[0]))
    ry1 = min(h, int(box[1]))
    rx0 = max(0, int(box[2]))
    rx1 = min(w, int(box[3]))
    if ry0 >= ry1 or rx0 >= rx1:
        return
    y0 = max(0, ry0 - 2)
    y1 = min(h, ry1 + 2)
    x0 = max(0, rx0 - 2)
    x1 = min(w, rx1 + 2)
    rh, rw = y1 - y0, x1 - x0
    valid = valid_full[y0:y1, x0:x1]
    src_roi = frame.source_rows[y0:y1, x0:x1]
    local_valid_idx = np.flatnonzero(valid.ravel())
    if not local_valid_idx.size:
        return
    ly = local_valid_idx // rw
    lx = local_valid_idx % rw
    src = np.asarray(src_roi[ly, lx], dtype=np.int64)
    gy = ly + y0
    gx = lx + x0
    grid_xyz[gy, gx, :] = frame.xyz[src].astype(np.float64)
    row_to_cell[src] = (gy * w + gx).astype(np.int32)

    if rh < 2 or rw < 2:
        return

    sub_xyz = grid_xyz[y0:y1, x0:x1, :]
    if hasattr(frame, "range_m") and frame.range_m is not None:
        ranges = np.asarray(frame.range_m[y0:y1, x0:x1], dtype=np.float64)
    else:
        with np.errstate(invalid="ignore"):
            ranges = np.linalg.norm(sub_xyz, axis=2)

    with np.errstate(invalid="ignore"):
        ok_h = valid[:, :-1] & valid[:, 1:] & (np.abs(ranges[:, 1:] - ranges[:, :-1]) <= jump)
        ok_v = valid[:-1, :] & valid[1:, :] & (np.abs(ranges[1:, :] - ranges[:-1, :]) <= jump)

    # 水平切向量：同时有左右连续邻点时等价于中心差分，单侧连续时退化为单侧差分。
    dh = np.where(ok_h[:, :, None], sub_xyz[:, 1:, :] - sub_xyz[:, :-1, :], 0.0)
    tu_sum = np.zeros((rh, rw, 3), dtype=np.float64)
    tu_cnt = np.zeros((rh, rw), dtype=np.uint8)
    tu_sum[:, :-1, :] += dh
    tu_sum[:, 1:, :] += dh
    tu_cnt[:, :-1] += ok_h.astype(np.uint8)
    tu_cnt[:, 1:] += ok_h.astype(np.uint8)

    dv = np.where(ok_v[:, :, None], sub_xyz[1:, :, :] - sub_xyz[:-1, :, :], 0.0)
    tv_sum = np.zeros((rh, rw, 3), dtype=np.float64)
    tv_cnt = np.zeros((rh, rw), dtype=np.uint8)
    tv_sum[:-1, :, :] += dv
    tv_sum[1:, :, :] += dv
    tv_cnt[:-1, :] += ok_v.astype(np.uint8)
    tv_cnt[1:, :] += ok_v.astype(np.uint8)

    sub_normals = np.full((rh, rw, 3), np.nan, dtype=np.float64)
    sub_nvalid = np.zeros((rh, rw), dtype=bool)
    has_both = valid & (tu_cnt > 0) & (tv_cnt > 0)
    if has_both.any():
        tu = tu_sum[has_both] / tu_cnt[has_both, None].astype(np.float64)
        tv = tv_sum[has_both] / tv_cnt[has_both, None].astype(np.float64)
        cross = np.cross(tu, tv)
        norm = np.linalg.norm(cross, axis=1)
        good = np.isfinite(norm) & (norm > 1e-7)
        if good.any():
            unit = cross[good] / norm[good, None]
            pts_good = sub_xyz[has_both][good]
            # 统一法向朝向传感器原点（dot(n, -p) >= 0 <=> dot(n, p) <= 0）。
            dot_view = np.einsum("ij,ij->i", unit, pts_good)
            flip = dot_view > 0.0
            unit[flip] *= -1.0

            both_cells = np.flatnonzero(has_both.ravel())
            good_cells = both_cells[good]
            sub_normals.reshape(-1, 3)[good_cells] = unit
            sub_nvalid.ravel()[good_cells] = True

    # 局部 4 邻域法向粗糙度：1 - mean(dot(n_i, n_nb))，平面接近 0，曲面/边缘更大。
    rough_sum = np.zeros((rh, rw), dtype=np.float64)
    rough_cnt = np.zeros((rh, rw), dtype=np.uint8)
    pair_h = ok_h & sub_nvalid[:, :-1] & sub_nvalid[:, 1:]
    if pair_h.any():
        dots_h = np.einsum("ij,ij->i", sub_normals[:, :-1, :][pair_h], sub_normals[:, 1:, :][pair_h])
        diff_h = 1.0 - np.clip(dots_h, -1.0, 1.0)
        rough_sum[:, :-1][pair_h] += diff_h
        rough_sum[:, 1:][pair_h] += diff_h
        rough_cnt[:, :-1][pair_h] += 1
        rough_cnt[:, 1:][pair_h] += 1

    pair_v = ok_v & sub_nvalid[:-1, :] & sub_nvalid[1:, :]
    if pair_v.any():
        dots_v = np.einsum("ij,ij->i", sub_normals[:-1, :, :][pair_v], sub_normals[1:, :, :][pair_v])
        diff_v = 1.0 - np.clip(dots_v, -1.0, 1.0)
        rough_sum[:-1, :][pair_v] += diff_v
        rough_sum[1:, :][pair_v] += diff_v
        rough_cnt[:-1, :][pair_v] += 1
        rough_cnt[1:, :][pair_v] += 1

    sub_rough = np.full((rh, rw), np.nan, dtype=np.float64)
    has_rough = rough_cnt > 0
    if has_rough.any():
        sub_rough[has_rough] = rough_sum[has_rough] / rough_cnt[has_rough].astype(np.float64)

    iy0, iy1 = ry0 - y0, ry1 - y0
    ix0, ix1 = rx0 - x0, rx1 - x0
    normals[ry0:ry1, rx0:rx1, :] = sub_normals[iy0:iy1, ix0:ix1, :]
    normal_valid[ry0:ry1, rx0:rx1] = sub_nvalid[iy0:iy1, ix0:ix1]
    local_roughness[ry0:ry1, rx0:rx1] = sub_rough[iy0:iy1, ix0:ix1]


def estimate_grid_normals(frame, max_edge_jump_m=0.25, roi_bbox=None, roi_bboxes=None):
    """在有序 2D 距离图上向量化估计逐像素朝向传感器的单位表面法向。

    当提供 ``roi_bbox=(y0, y1, x0, x1)`` 或 ``roi_bboxes=[(y0, y1, x0, x1), ...]`` 时，
    仅在局部窗口（各自自动含 2 像素边距以保证中心差分与 4 邻域粗糙度数值完全等价）计算法向，
    避免散落多轨撑大到全图计算。
    """
    jump = float(max_edge_jump_m)
    if not np.isfinite(jump) or jump <= 0.0:
        raise ValueError("max_edge_jump_m must be positive and finite")
    valid_full = np.asarray(frame.valid, dtype=bool)
    h, w = valid_full.shape
    grid_xyz = np.full((h, w, 3), np.nan, dtype=np.float64)
    normals = np.full((h, w, 3), np.nan, dtype=np.float64)
    normal_valid = np.zeros((h, w), dtype=bool)
    local_roughness = np.full((h, w), np.nan, dtype=np.float64)
    row_to_cell = np.full(len(frame.xyz), -1, dtype=np.int32)

    if roi_bboxes is not None:
        boxes = list(roi_bboxes)
    elif roi_bbox is not None:
        boxes = [roi_bbox]
    else:
        boxes = [(0, h, 0, w)]

    for box in boxes:
        _compute_normals_window(
            frame, valid_full, h, w, jump, box,
            grid_xyz, normals, normal_valid, local_roughness, row_to_cell,
        )

    return GridNormals((h, w), jump, grid_xyz, normals, normal_valid,
                       local_roughness, row_to_cell)


def _candidate_plane_normals(pts, normals, az_bins, el_bins):
    """确定性生成平面法向候选（PCA 最小特征向量 + 均值法向 + 法向直方图 Top 模式）。"""
    candidates = []

    def add_candidate(vec):
        v = np.asarray(vec, dtype=np.float64)
        if v.shape != (3,) or not np.isfinite(v).all():
            return
        nrm = float(np.linalg.norm(v))
        if nrm < 1e-7:
            return
        v = v / nrm
        for existing in candidates:
            if abs(float(v @ existing)) > 0.94:  # ~20 deg deduplication
                return
        candidates.append(v)

    # 1. 整体点云最小方差方向（单平面精确解）
    centered = pts - np.mean(pts, axis=0)
    cov = (centered.T @ centered) / max(1.0, float(len(pts)))
    if np.isfinite(cov).all():
        _, eigvecs = np.linalg.eigh(cov)
        add_candidate(eigvecs[:, 0])

    # 2. 簇法向均值方向
    mean_n = np.mean(normals, axis=0)
    if float(np.linalg.norm(mean_n)) > 0.2:
        add_candidate(mean_n)

    # 3. 球面分箱法向直方图 Top-4 众数（用于捕捉双平面盒体/拐角）
    az = np.arctan2(normals[:, 1], normals[:, 0])
    el = np.arcsin(np.clip(normals[:, 2], -1.0, 1.0))
    a_idx = np.floor(((az + np.pi) / (2.0 * np.pi)) * az_bins).astype(np.int64) % az_bins
    e_idx = np.clip(np.floor(((el + 0.5 * np.pi) / np.pi) * el_bins).astype(np.int64),
                    0, el_bins - 1)
    bin_id = e_idx * az_bins + a_idx
    counts = np.bincount(bin_id, minlength=az_bins * el_bins)
    top_bins = np.argsort(-counts, kind="stable")[:6]
    min_mode_pts = max(5, len(normals) // 20)
    for b in top_bins:
        if counts[b] < min_mode_pts:
            break
        add_candidate(np.mean(normals[bin_id == b], axis=0))
        if len(candidates) >= 6:
            break
    return candidates


def cluster_normal_features(frame, rows, grid_normals=None, ground=None, settings=None):
    """计算单个候选簇的表面法向熵、平面度与近地法向对齐特征。"""
    resolved = resolve_normal_settings(settings)
    rows_arr = np.asarray(rows)
    if (rows_arr.ndim != 1 or not rows_arr.size or rows_arr.dtype.kind not in "iu"
            or len(np.unique(rows_arr)) != len(rows_arr)
            or rows_arr.min() < 0 or rows_arr.max() >= len(frame.xyz)):
        raise ValueError("cluster_normal_features requires unique valid current source rows")

    if grid_normals is None:
        grid_normals = estimate_grid_normals(frame, max_edge_jump_m=resolved["max_edge_jump_m"])

    cells = grid_normals.row_to_cell[rows_arr]
    if (cells < 0).any():
        raise ValueError("cluster rows must belong to current valid grid cells")

    valid_mask = grid_normals.valid.ravel()[cells]
    valid_count = int(valid_mask.sum())
    base = {
        "available": False,
        "reason": None,
        "point_count": int(len(rows_arr)),
        "valid_normal_count": valid_count,
        "valid_normal_fraction": round(valid_count / float(len(rows_arr)), 4),
        "normal_azimuth_entropy": None,
        "normal_azimuth_span_deg": None,
        "normal_sphere_entropy": None,
        "non_horizontal_fraction": None,
        "single_plane_inlier_ratio": None,
        "dual_plane_inlier_ratio": None,
        "dominant_plane_inlier_ratio": None,
        "ground_normal_alignment": None,
        "near_ground_point_count": 0,
        "mean_abs_nz": None,
        "mean_local_roughness": None,
        "median_local_roughness": None,
        "semantic": "UNKNOWN",
    }
    if valid_count < resolved["min_normal_points"]:
        base["reason"] = "insufficient_valid_normals"
        return base

    v_cells = cells[valid_mask]
    v_rows = rows_arr[valid_mask]
    n_raw = grid_normals.normals.reshape(-1, 3)[v_cells]
    p_raw = frame.xyz[v_rows].astype(np.float64)

    plane = bound_ground(frame, ground) if ground is not None else None
    basis = ground_plane_basis(plane) if plane is not None else None
    if basis is not None:
        g_norm, axis_u, axis_v = basis
        nu = n_raw @ axis_u
        nv = n_raw @ axis_v
        nz = n_raw @ g_norm
        heights = p_raw @ g_norm + float(plane["offset_m"])
    else:
        nu = n_raw[:, 0]
        nv = n_raw[:, 1]
        nz = n_raw[:, 2]
        heights = None

    # 1. 水平方位角法向熵（针对非水平表面点，区分平墙/柜门 vs 曲面躯干/四肢）
    horiz_mag = np.hypot(nu, nv)
    non_horiz = horiz_mag >= resolved["non_horiz_min_mag"]
    non_horiz_frac = float(non_horiz.mean())
    az_bins = resolved["azimuth_bins"]
    if int(non_horiz.sum()) >= max(8, resolved["min_normal_points"] // 2):
        az = np.arctan2(nv[non_horiz], nu[non_horiz])
        a_idx = np.floor(((az + np.pi) / (2.0 * np.pi)) * az_bins).astype(np.int64) % az_bins
        counts = np.bincount(a_idx, minlength=az_bins).astype(np.float64)
        probs = counts[counts > 0] / counts.sum()
        az_entropy = float(-np.sum(probs * np.log(probs)) / np.log(float(az_bins)))
        mean_angle = float(np.arctan2(np.mean(np.sin(az)), np.mean(np.cos(az))))
        rel = np.arctan2(np.sin(az - mean_angle), np.cos(az - mean_angle))
        az_span_deg = float(np.degrees(np.percentile(rel, 90.0) - np.percentile(rel, 10.0)))
    else:
        az_entropy = 0.0
        az_span_deg = 0.0

    # 2. 3D 球面法向熵（兼顾水平/倾斜曲面如躺姿躯干 vs 桌面）
    el_bins = resolved["elevation_bins"]
    az_all = np.arctan2(nv, nu)
    el_all = np.arcsin(np.clip(nz, -1.0, 1.0))
    sa = np.floor(((az_all + np.pi) / (2.0 * np.pi)) * az_bins).astype(np.int64) % az_bins
    se = np.clip(np.floor(((el_all + 0.5 * np.pi) / np.pi) * el_bins).astype(np.int64),
                 0, el_bins - 1)
    s_counts = np.bincount(se * az_bins + sa, minlength=az_bins * el_bins).astype(np.float64)
    s_probs = s_counts[s_counts > 0] / s_counts.sum()
    # 传感器单侧可见约占半球，按 log(0.5 * az_bins * el_bins) 归一并截断于 1.0。
    sphere_norm = np.log(max(2.0, 0.5 * az_bins * el_bins))
    sphere_entropy = float(min(1.0, -np.sum(s_probs * np.log(s_probs)) / sphere_norm))

    # 3. 确定性单平面与双平面内点占比（空间距离 + 法向一致性双门）
    candidates = _candidate_plane_normals(p_raw, n_raw, az_bins, el_bins)
    tol = resolved["plane_dist_tol_m"]
    cos_min = resolved["plane_normal_cos_min"]
    inlier_masks = []
    for n_cand in candidates:
        aligned = np.abs(n_raw @ n_cand) >= cos_min
        if not aligned.any():
            inlier_masks.append(np.zeros(len(p_raw), dtype=bool))
            continue
        proj = p_raw @ n_cand
        d0 = float(np.median(proj[aligned]))
        inlier_masks.append(aligned & (np.abs(proj - d0) <= tol))

    single_ratio = max((float(m.mean()) for m in inlier_masks), default=0.0)
    dual_ratio = single_ratio
    max_dot = resolved["dual_plane_max_abs_dot"]
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            if abs(float(candidates[i] @ candidates[j])) <= max_dot:
                ratio = float((inlier_masks[i] | inlier_masks[j]).mean())
                if ratio > dual_ratio:
                    dual_ratio = ratio

    # 4. 近地表面法向朝上一致性
    near_count = 0
    ground_align = None
    if heights is not None:
        near = heights <= resolved["ground_band_m"]
        near_count = int(near.sum())
        if near_count > 0:
            ground_align = round(float((nz[near] >= resolved["ground_up_cos_min"]).mean()), 4)
        else:
            ground_align = 0.0

    # 5. 局部法向粗糙度
    rough_vals = grid_normals.local_roughness.ravel()[v_cells]
    rough_finite = rough_vals[np.isfinite(rough_vals)]
    mean_rough = round(float(np.mean(rough_finite)), 5) if rough_finite.size else None
    median_rough = round(float(np.median(rough_finite)), 5) if rough_finite.size else None

    base.update({
        "available": True,
        "reason": None,
        "normal_azimuth_entropy": round(az_entropy, 4),
        "normal_azimuth_span_deg": round(az_span_deg, 2),
        "normal_sphere_entropy": round(sphere_entropy, 4),
        "non_horizontal_fraction": round(non_horiz_frac, 4),
        "single_plane_inlier_ratio": round(single_ratio, 4),
        "dual_plane_inlier_ratio": round(dual_ratio, 4),
        "dominant_plane_inlier_ratio": round(single_ratio, 4),
        "ground_normal_alignment": ground_align,
        "near_ground_point_count": near_count,
        "mean_abs_nz": round(float(np.mean(np.abs(nz))), 4),
        "mean_local_roughness": mean_rough,
        "median_local_roughness": median_rough,
    })
    return base
