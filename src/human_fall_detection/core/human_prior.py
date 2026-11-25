"""单人人体几何相容性描述子（体素/柱状特征），不判定人体身份。

用途：给定"同一帧内一个候选目标的实测点"，回答三个可验证的问题：

1. 它的尺度/形状能不能是**一个人**（站、坐蹲、躺三种姿态之一）？
2. 它是不是**碎片**（两个方向都远小于人体最小可分辨尺寸）或**平面结构**
   （墙、柜门、桌面这类细长面）？
3. 在单人场景下，当前帧所有候选中**应当锁定哪一个**（含迟滞与歧义标记）？

严格语义：

* 输出是几何相容性，不是身份、不是概率。``semantic`` 与 ``identity`` 恒为
  ``UNKNOWN``，``class`` 里只出现 ``standing_geometry`` /
  ``sitting_geometry`` / ``lying_geometry`` / ``fragment`` /
  ``planar_structure`` / ``not_compatible`` / ``unknown``，绝不写 "person"。
* 缺地面 → 不判相容（``available=False``），而不是猜。
* ``unknown`` 表示"本次无法评估"（点太少、缺时间/地面），它**不能**被当成
  不相容：下游选择策略允许它继续占用目标，只是优先级更低。
* 阈值是宽区间初值，均出现在输出的 ``thresholds`` 块里，便于逐条复核；
  它们尚未在带人体真值的独立数据上验证，准确率/召回率 UNKNOWN。

坐标系：所有高度、水平跨度、体素都在重力对齐的地面系里算（法向为 +z，
地面为 z=0）；距离补偿用本目标点的中位斜距。
"""

import numpy as np

try:  # pragma: no cover - import shim
    from .lidar_candidates import ground_plane_basis, rebuild_candidate
    from .range_features import bound_ground, valid_source_row_mask
    from .range_normals import cluster_normal_features
except ImportError:  # pragma: no cover
    from lidar_candidates import ground_plane_basis, rebuild_candidate
    from range_features import bound_ground, valid_source_row_mask
    from range_normals import cluster_normal_features

KIND = "human_prior"
SCHEMA_VERSION = 1

CLASS_STANDING = "standing_geometry"
CLASS_SITTING = "sitting_geometry"
CLASS_LYING = "lying_geometry"
CLASS_FRAGMENT = "fragment"
CLASS_PLANAR = "planar_structure"
CLASS_HANGING_ADHESION = "hanging_or_adhesion"
CLASS_OTHER = "not_compatible"
CLASS_UNKNOWN = "unknown"
CLASSES = (CLASS_STANDING, CLASS_SITTING, CLASS_LYING, CLASS_FRAGMENT,
           CLASS_PLANAR, CLASS_OTHER, CLASS_UNKNOWN)
PHYSICAL_V1_CLASSES = CLASSES + (CLASS_HANGING_ADHESION,)
COMPATIBLE_CLASSES = (CLASS_STANDING, CLASS_SITTING, CLASS_LYING)

POSTURE = {
    CLASS_STANDING: "standing",
    CLASS_SITTING: "sitting_or_squatting",
    CLASS_LYING: "lying_horizontal",
    CLASS_FRAGMENT: "not_evaluable_fragment",
    CLASS_PLANAR: "not_evaluable_planar",
    CLASS_HANGING_ADHESION: "not_evaluable_hanging_adhesion",
    CLASS_OTHER: "not_evaluable_shape",
    CLASS_UNKNOWN: "not_evaluable",
}

DEFAULT_SETTINGS = {
    "voxel_m": 0.1,
    "contact_m": 0.1,
    "min_points": 40,
    "min_height_span_m": 0.30,
    "top_min_m": 0.05,
    "top_max_m": 2.15,
    "footprint_area_max_m2": 0.90,
    "footprint_elongation_max": 3.5,
    "standing_top_min_m": 1.05,
    "standing_span_min_m": 0.60,
    # 接地门只用来挡悬空结构（衣架/吊柜），必须留出"腿被矮家具挡住"的余地。
    "standing_bottom_max_m": 1.00,
    "sitting_top_min_m": 0.55,
    "sitting_span_min_m": 0.35,
    "sitting_horizontal_max_m": 1.10,
    "sitting_bottom_max_m": 0.70,
    "lying_top_max_m": 0.85,
    "lying_bottom_max_m": 0.40,
    "lying_horizontal_min_m": 0.55,
    "lying_verticality_max": 0.55,
    "lying_span_max_m": 0.95,
    "fragment_span_max_m": 0.30,
    "fragment_height_max_m": 0.35,
    "planar_horizontal_min_m": 0.90,
    "planar_thickness_max_m": 0.25,
    "keep_previous_score_ratio": 0.85,
    "competing_score_ratio": 0.90,
}


def resolve_settings(settings=None):
    resolved = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown human prior setting: " + str(key))
        resolved[key] = value
    for key in DEFAULT_SETTINGS:
        if key == "min_points":
            continue
        resolved[key] = float(resolved[key])
        if not np.isfinite(resolved[key]) or resolved[key] < 0.0:
            raise ValueError(key + " must be a finite non-negative number")
    resolved["min_points"] = int(resolved["min_points"])
    if resolved["min_points"] < 3:
        raise ValueError("min_points must be at least 3")
    if resolved["top_max_m"] <= resolved["top_min_m"]:
        raise ValueError("top_max_m must exceed top_min_m")
    return resolved


def _require_rows(frame, rows):
    rows = np.asarray(rows)
    if (rows.ndim != 1 or not rows.size or rows.dtype.kind not in "iu"
            or len(np.unique(rows)) != len(rows) or rows.min() < 0
            or rows.max() >= len(frame.xyz)
            or not valid_source_row_mask(frame)[rows].all()):
        raise ValueError("human prior requires unique current decoded measurement rows")
    return rows


def _height_stats(heights):
    return {
        "min": float(heights.min()),
        "p10": float(np.percentile(heights, 10.0)),
        "median": float(np.median(heights)),
        "p90": float(np.percentile(heights, 90.0)),
        "max": float(heights.max()),
    }


def _horizontal_spans(u, v):
    """Robust (p5..p95) horizontal spans in the ground tangent plane."""
    low_u, high_u = np.percentile(u, [5.0, 95.0])
    low_v, high_v = np.percentile(v, [5.0, 95.0])
    span_u, span_v = float(high_u - low_u), float(high_v - low_v)
    return span_u, span_v


def _voxel_profile(u, v, heights, cell_m, contact_m):
    """0.1 m 体素描述子的廉价部分：占用、填充、分层宽度、接地占比。"""
    origin_u, origin_v = float(u.min()), float(v.min())
    cells_u = np.floor((u - origin_u) / cell_m).astype(np.int64)
    cells_v = np.floor((v - origin_v) / cell_m).astype(np.int64)
    cells_z = np.floor((heights - float(heights.min())) / cell_m).astype(np.int64)
    flat = (cells_u * (int(cells_v.max()) + 1) + cells_v)
    occupied_2d = int(len(np.unique(flat)))
    occupied_3d = int(len(np.unique(flat * (int(cells_z.max()) + 1) + cells_z)))
    area_m2 = occupied_2d * cell_m * cell_m
    bbox_u = (int(cells_u.max()) + 1) * cell_m
    bbox_v = (int(cells_v.max()) + 1) * cell_m
    bbox_cells_2d = max(1, (int(cells_u.max()) + 1) * (int(cells_v.max()) + 1))
    bbox_cells_3d = bbox_cells_2d * max(1, int(cells_z.max()) + 1)
    # 分层：高度直方图 + 每层水平宽度（肩/腰/腿的剖面）
    bins = int(cells_z.max()) + 1
    counts = np.bincount(cells_z, minlength=bins).astype(np.float64)
    histogram = counts / max(1.0, float(counts.sum()))
    widths = []
    for index in range(bins):
        member = cells_z == index
        if not member.any():
            widths.append(0.0)
            continue
        low_u, high_u = float(u[member].min()), float(u[member].max())
        low_v, high_v = float(v[member].min()), float(v[member].max())
        widths.append(round(max(high_u - low_u, high_v - low_v), 4))
    return {
        "voxel_m": float(cell_m),
        "occupied_voxels_2d": occupied_2d,
        "occupied_voxels_3d": occupied_3d,
        "footprint_area_m2": round(area_m2, 4),
        "footprint_bbox_m": [round(bbox_u, 3), round(bbox_v, 3)],
        "footprint_bbox_area_m2": round(bbox_u * bbox_v, 4),
        "occupancy_2d": round(occupied_2d / float(bbox_cells_2d), 4),
        "occupancy_3d": round(occupied_3d / float(bbox_cells_3d), 4),
        "vertical_fill": round(int(len(np.unique(cells_z))) / float(max(bins, 1)), 4),
        "height_histogram": [round(float(value), 4) for value in histogram],
        "tier_width_m": widths,
        "ground_contact_fraction": round(float((heights - float(heights.min())
                                                <= contact_m).mean()), 4),
    }


def describe(frame, rows, ground, settings=None):
    """描述一个候选目标的几何相容性；输入必须是本帧实测来源行。"""
    resolved = resolve_settings(settings)
    rows = _require_rows(frame, rows)
    plane = bound_ground(frame, ground)
    base = {
        "kind": KIND,
        "schema_version": SCHEMA_VERSION,
        "available": False,
        "reason": None,
        "class": CLASS_UNKNOWN,
        "compatible": False,
        "compatible_with": [],
        "posture": POSTURE[CLASS_UNKNOWN],
        "point_count": int(len(rows)),
        "features": None,
        "thresholds": {key: resolved[key] for key in DEFAULT_SETTINGS if key != "min_points"},
        "min_points": resolved["min_points"],
        "semantic": "UNKNOWN",
        "identity": "UNKNOWN",
        "definition": "anthropometric_geometry_only_not_identity",
    }
    if plane is None:
        base["reason"] = "ground_unavailable_or_unbound"
        return base
    basis = ground_plane_basis(plane)
    if basis is None:
        base["reason"] = "invalid_ground_plane"
        return base
    normal, axis_u, axis_v = basis
    xyz = frame.xyz[rows].astype(np.float64)
    heights = xyz @ normal + float(ground["offset_m"])
    u, v = xyz @ axis_u, xyz @ axis_v
    span_u, span_v = _horizontal_spans(u, v)
    horizontal_span = max(span_u, span_v)
    shorter_span = min(span_u, span_v)
    height_span = float(np.percentile(heights, 90.0) - np.percentile(heights, 10.0))
    top, bottom = float(heights.max()), float(heights.min())
    candidate = rebuild_candidate(xyz, np.arange(len(xyz)), ground=plane,
                                  frame_id=plane["frame"] if plane else "unbound")
    axis = candidate.get("axis") or {}
    ranges = np.linalg.norm(xyz, axis=1)
    range_median = float(np.median(ranges))
    profile = _voxel_profile(u, v, heights, resolved["voxel_m"], resolved["contact_m"])
    footprint_area = profile["footprint_area_m2"]
    elongation = float(horizontal_span / max(shorter_span, 1e-6))
    features = dict(profile)
    features.update({
        "point_count": int(len(rows)),
        "range_median_m": round(range_median, 4),
        "top_m": round(top, 4),
        "bottom_m": round(bottom, 4),
        "height_span_m": round(height_span, 4),
        "height_m": {key: round(value, 4) for key, value in _height_stats(heights).items()},
        "horizontal_span_m": round(horizontal_span, 4),
        "horizontal_span_uv_m": [round(span_u, 4), round(span_v, 4)],
        "footprint_elongation": round(elongation, 4),
        "aspect_height_over_footprint": (None if footprint_area <= 1e-9
                                         else round(height_span / np.sqrt(footprint_area), 4)),
        "verticality": None if axis.get("verticality") is None else round(float(axis["verticality"]), 4),
        "axis_ambiguous": bool(axis.get("ambiguous", True)),
        "eigenvalues_m2": axis.get("eigenvalues"),
        "points_per_m2": round(float(len(rows)) / max(footprint_area, 1e-6), 2),
        "distance_compensated_count": round(float(len(rows)) / max(range_median ** 2, 1e-6), 4),
    })
    base["features"] = features
    if horizontal_span < resolved["fragment_span_max_m"] \
            and height_span < resolved["fragment_height_max_m"]:
        base["available"] = True
        return _classify(base, CLASS_FRAGMENT, "both_spans_below_human_minimum")
    if len(rows) < resolved["min_points"]:
        base["reason"] = "insufficient_points"
        return base
    base["available"] = True
    if horizontal_span >= resolved["planar_horizontal_min_m"] \
            and shorter_span <= resolved["planar_thickness_max_m"] \
            and elongation > resolved["footprint_elongation_max"]:
        return _classify(base, CLASS_PLANAR, "thin_and_long_horizontal_structure")
    if top > resolved["top_max_m"] or top < resolved["top_min_m"]:
        return _classify(base, CLASS_OTHER, "top_outside_human_range")
    if footprint_area > resolved["footprint_area_max_m2"]:
        return _classify(base, CLASS_OTHER, "footprint_too_large")
    if top <= resolved["lying_top_max_m"]:
        # 躺倒相容：贴地（bottom 低）+ 长条（水平跨度）或已平放（垂直度低）。
        verticality = features["verticality"]
        long_body = horizontal_span >= resolved["lying_horizontal_min_m"]
        flat_axis = verticality is not None and verticality <= resolved["lying_verticality_max"]
        if (bottom <= resolved["lying_bottom_max_m"]
                and (long_body or flat_axis)
                and height_span <= resolved["lying_span_max_m"]):
            return _classify(base, CLASS_LYING, "low_and_long_horizontal_body")
        return _classify(base, CLASS_OTHER, "low_but_no_horizontal_body_support")
    if (top >= resolved["standing_top_min_m"]
            and height_span >= resolved["standing_span_min_m"]
            and bottom <= resolved["standing_bottom_max_m"]):
        return _classify(base, CLASS_STANDING, "upright_body_height_and_span")
    if (resolved["sitting_top_min_m"] <= top < resolved["standing_top_min_m"]
            and height_span >= resolved["sitting_span_min_m"]
            and horizontal_span <= resolved["sitting_horizontal_max_m"]
            and bottom <= resolved["sitting_bottom_max_m"]):
        return _classify(base, CLASS_SITTING, "intermediate_height_compact_body")
    return _classify(base, CLASS_OTHER, "does_not_match_a_human_posture")


def _classify(base, class_name, reason):
    out = dict(base)
    out["class"] = class_name
    out["compatible"] = class_name in COMPATIBLE_CLASSES
    out["compatible_with"] = [class_name] if out["compatible"] else []
    out["posture"] = POSTURE[class_name]
    out["reason"] = reason
    return out


def quick_screen(xyz, ground, settings=None):
    """不建 PCA 的廉价分档，用于逐帧筛掉碎片/平面，避免全量昂贵描述。"""
    resolved = resolve_settings(settings)
    plane = ground_plane_basis(ground)
    out = {"evaluated": False, "reason": "ground_unavailable", "class": CLASS_UNKNOWN,
           "top_m": None, "height_span_m": None, "horizontal_span_m": None,
           "point_count": int(len(xyz))}
    if plane is None:
        return out
    normal, axis_u, axis_v = plane
    points = np.asarray(xyz, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or not len(points):
        out["reason"] = "invalid_points"
        return out
    heights = points @ normal + float(ground["offset_m"])
    u, v = points @ axis_u, points @ axis_v
    span_u, span_v = _horizontal_spans(u, v)
    horizontal_span = max(span_u, span_v)
    height_span = float(np.percentile(heights, 90.0) - np.percentile(heights, 10.0))
    out.update(evaluated=True, reason=None, top_m=round(float(heights.max()), 4),
               height_span_m=round(height_span, 4), horizontal_span_m=round(horizontal_span, 4))
    if horizontal_span < resolved["fragment_span_max_m"] \
            and height_span < resolved["fragment_height_max_m"]:
        out.update({"class": CLASS_FRAGMENT, "reason": "both_spans_below_human_minimum"})
    elif len(points) < resolved["min_points"]:
        out.update({"class": CLASS_UNKNOWN, "reason": "insufficient_points"})
    elif horizontal_span >= resolved["planar_horizontal_min_m"] \
            and min(span_u, span_v) <= resolved["planar_thickness_max_m"] \
            and horizontal_span / max(min(span_u, span_v), 1e-6) > resolved["footprint_elongation_max"]:
        out.update({"class": CLASS_PLANAR, "reason": "thin_and_long_horizontal_structure"})
    else:
        out.update({"class": CLASS_UNKNOWN, "reason": "needs_full_description"})
    return out


def choose_single(entries, previous_track_id=None, settings=None):
    """单人策略：只锁一个目标，带迟滞，宁可无目标也不锁碎片。

    ``entries`` 每项至少含 ``track_id``、``compatible``、``class``、``score``。
    ``unknown``（无法评估）不算不相容，只降优先级；``fragment`` /
    ``planar_structure`` / ``not_compatible`` 直接不参与选择。
    """
    resolved = resolve_settings(settings)
    rejected, eligible = [], []
    for entry in entries or []:
        track_id = entry.get("track_id")
        class_name = entry.get("class")
        if entry.get("compatible"):
            eligible.append(entry)
        elif class_name == CLASS_UNKNOWN:
            eligible.append(dict(entry, compatible=False))
        else:
            rejected.append({"track_id": track_id, "class": class_name,
                             "reason": "not_human_compatible"})
    result = {"policy": "single_person", "schema_version": SCHEMA_VERSION,
              "chosen_track_id": None, "reason": None, "ambiguous": False,
              "compatible_count": sum(1 for entry in eligible if entry.get("compatible")),
              "eligible_count": len(eligible), "rejected": rejected,
              "semantic": "UNKNOWN", "identity": "UNKNOWN"}
    if not eligible:
        result["reason"] = "no_human_compatible_target"
        return result
    ordered = sorted(eligible, key=lambda entry: (0 if entry.get("compatible") else 1,
                                                 -float(entry.get("score") or 0.0),
                                                 -int(entry.get("point_count") or 0),
                                                 str(entry.get("track_id"))))
    best = ordered[0]
    previous = next((entry for entry in ordered
                     if previous_track_id is not None
                     and entry.get("track_id") == previous_track_id), None)
    chosen, reason = best, "best_compatible_target"
    if previous is not None and previous is not best:
        best_score = float(best.get("score") or 0.0)
        previous_score = float(previous.get("score") or 0.0)
        if previous_score >= resolved["keep_previous_score_ratio"] * best_score \
                and previous.get("compatible"):
            chosen, reason = previous, "previous_target_retained"
    chosen_compat = bool(chosen.get("compatible"))
    ranked = [entry for entry in ordered
              if entry is not chosen and bool(entry.get("compatible")) == chosen_compat]
    if ranked and float(ranked[0].get("score") or 0.0) \
            >= resolved["competing_score_ratio"] * float(chosen.get("score") or 0.0):
        result["ambiguous"] = True
    result["chosen_track_id"] = chosen.get("track_id")
    result["reason"] = reason
    return result


PHYSICAL_V1_SETTINGS = {
    "num_tiers": 10,
    "tier_min_point_ratio": 0.01,
    "adhesion_check_min_span_m": 0.70,
    "min_normalized_vertical_fill": 0.60,
    "max_empty_tier_run": 2,
    "detached_bottom_min_m": 0.20,
    "max_top_third_ratio": 0.72,
    "min_third_ratio": 0.08,
    "thin_bridge_width_m": 0.08,
    "thin_bridge_point_ratio": 0.025,
    "max_thin_bridge_tiers": 3,
    "max_top_to_mid_width_ratio": 3.5,
    "single_plane_reject_ratio": 0.80,
    "planar_max_azimuth_entropy": 0.36,
    "planar_non_horiz_floor": 0.20,
    "dual_plane_reject_ratio": 0.90,
    "dual_plane_max_azimuth_entropy": 0.42,
    "dual_plane_max_roughness": 0.015,
    "lying_plane_reject_ratio": 0.88,
    "lying_max_sphere_entropy": 0.28,
}


def resolve_physical_v1_settings(settings=None):
    resolved = dict(PHYSICAL_V1_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown human prior physical_v1 setting: " + str(key))
        resolved[key] = value
    for key in ("num_tiers", "max_empty_tier_run", "max_thin_bridge_tiers"):
        if isinstance(resolved[key], bool) or int(resolved[key]) != resolved[key] or int(resolved[key]) < 1:
            raise ValueError(key + " must be a positive integer")
        resolved[key] = int(resolved[key])
    if resolved["num_tiers"] < 3:
        raise ValueError("num_tiers must be at least 3")
    for key in resolved:
        if key in ("num_tiers", "max_empty_tier_run", "max_thin_bridge_tiers"):
            continue
        val = float(resolved[key])
        if not np.isfinite(val) or val < 0.0:
            raise ValueError(key + " must be a finite non-negative number")
        resolved[key] = val
    return resolved


def _tier_horizontal_spans(u_tier, v_tier):
    """旋转不变的局部水平宽度与厚度（大/小主轴方向跨度）。"""
    count = len(u_tier)
    if count <= 1:
        return 0.0, 0.0
    uv = np.column_stack((u_tier, v_tier))
    centered = uv - np.mean(uv, axis=0)
    if count >= 4:
        cov = (centered.T @ centered) / float(count)
        if np.isfinite(cov).all():
            _, vecs = np.linalg.eigh(cov)
            proj_major = centered @ vecs[:, 1]
            proj_minor = centered @ vecs[:, 0]
            if count >= 10:
                w_maj = float(np.percentile(proj_major, 95.0) - np.percentile(proj_major, 5.0))
                w_min = float(np.percentile(proj_minor, 95.0) - np.percentile(proj_minor, 5.0))
            else:
                w_maj = float(proj_major.max() - proj_major.min())
                w_min = float(proj_minor.max() - proj_minor.min())
            return max(w_maj, w_min), min(w_maj, w_min)
    su = float(u_tier.max() - u_tier.min())
    sv = float(v_tier.max() - v_tier.min())
    return max(su, sv), min(su, sv)


def _normalized_tier_profile(u, v, heights, num_tiers, min_tier_ratio,
                             thin_width_m, thin_ratio, tier_normals=None,
                             tier_normal_valid=None):
    """10 层归一化高度剖面（0%..100% 高度的宽/厚/点数占比/法向离散度）。"""
    total = len(heights)
    h_lo, h_hi = np.percentile(heights, [2.0, 98.0])
    h_span = max(float(h_hi - h_lo), 1e-3)
    norm_h = np.clip((heights - float(h_lo)) / h_span, 0.0, 0.999999)
    tier_idx = np.floor(norm_h * num_tiers).astype(np.int64)

    tiers = []
    occupied_tiers = 0
    cur_empty = 0
    max_empty = 0
    thin_bridge_tiers = 0
    min_pts_occ = max(1, int(np.ceil(total * min_tier_ratio)))

    for k in range(num_tiers):
        mask = tier_idx == k
        cnt = int(mask.sum())
        ratio = cnt / float(max(1, total))
        if cnt > 0:
            width_m, thickness_m = _tier_horizontal_spans(u[mask], v[mask])
        else:
            width_m, thickness_m = 0.0, 0.0

        disp = None
        if tier_normals is not None and tier_normal_valid is not None:
            nm = mask & tier_normal_valid
            if int(nm.sum()) >= 3:
                mean_n = np.mean(tier_normals[nm], axis=0)
                disp = round(float(max(0.0, 1.0 - float(np.linalg.norm(mean_n)))), 4)

        is_occ = cnt >= min_pts_occ
        if is_occ:
            occupied_tiers += 1
            cur_empty = 0
        else:
            cur_empty += 1
            if cur_empty > max_empty:
                max_empty = cur_empty

        if 1 <= k <= num_tiers - 2:
            if width_m < thin_width_m or ratio < thin_ratio:
                thin_bridge_tiers += 1

        tiers.append({
            "tier": k,
            "point_count": cnt,
            "point_ratio": round(ratio, 4),
            "width_m": round(width_m, 4),
            "thickness_m": round(thickness_m, 4),
            "normal_dispersion": disp,
        })

    # 上/中/下三段点数占比（按归一化高度三等分）
    third_idx = np.clip(np.floor(norm_h * 3.0).astype(np.int64), 0, 2)
    third_counts = np.bincount(third_idx, minlength=3).astype(np.float64)
    third_ratios = third_counts / max(1.0, float(third_counts.sum()))

    top_widths = [t["width_m"] for t in tiers[-2:] if t["point_count"] > 0]
    mid_widths = [t["width_m"] for t in tiers[2:-2]]
    top_w = max(top_widths) if top_widths else 0.0
    mid_min_w = min(mid_widths) if mid_widths else 0.0
    top_to_mid_ratio = top_w / max(mid_min_w, 0.02) if top_w > 0.0 else 0.0

    return {
        "num_tiers": num_tiers,
        "height_p02_m": round(float(h_lo), 4),
        "height_p98_m": round(float(h_hi), 4),
        "vertical_fill": round(occupied_tiers / float(num_tiers), 4),
        "max_empty_tier_run": int(max_empty),
        "third_ratios": [round(float(r), 4) for r in third_ratios],
        "bottom_third_ratio": round(float(third_ratios[0]), 4),
        "middle_third_ratio": round(float(third_ratios[1]), 4),
        "top_third_ratio": round(float(third_ratios[2]), 4),
        "min_third_ratio": round(float(third_ratios.min()), 4),
        "thin_bridge_tier_count": int(thin_bridge_tiers),
        "top_to_mid_width_ratio": round(float(top_to_mid_ratio), 3),
        "tiers": tiers,
    }


def describe_physical_v1(frame, rows, ground, normals=None, settings=None,
                         base_settings=None, normal_settings=None):
    """命名变体 physical_v1：10 层归一化剖面 + 表面法向平面度 + 悬空粘连拒识。

    不改动原 describe() 契约；保持 standing/sitting/lying 三姿态物理兼容边界，
    绝不以直立身高作为唯一入口，也不声称人体真值身份（semantic 恒为 UNKNOWN）。
    """
    pcfg = resolve_physical_v1_settings(settings)
    base = describe(frame, rows, ground, settings=base_settings)
    out = dict(base)
    out["variant"] = "physical_v1"
    out["physical_thresholds"] = dict(pcfg)
    out["normalized_profile"] = None
    out["normal_features"] = None
    out["rejection_reasons"] = []
    out["physical_notes"] = []

    if not out["available"]:
        if out["reason"]:
            out["rejection_reasons"] = [out["reason"]]
        return out

    rows_arr = np.asarray(rows, dtype=np.int64)
    plane = bound_ground(frame, ground)
    normal_vec, axis_u, axis_v = ground_plane_basis(plane)
    xyz = frame.xyz[rows_arr].astype(np.float64)
    heights = xyz @ normal_vec + float(plane["offset_m"])
    u = xyz @ axis_u
    v = xyz @ axis_v

    tier_normals = None
    tier_normal_valid = None
    norm_feat = None
    if normals is not None:
        norm_feat = cluster_normal_features(
            frame, rows_arr, grid_normals=normals, ground=plane,
            settings=normal_settings,
        )
        cells = normals.row_to_cell[rows_arr]
        tier_normal_valid = normals.valid.ravel()[cells]
        tier_normals = normals.normals.reshape(-1, 3)[cells]
    else:
        norm_feat = cluster_normal_features(
            frame, rows_arr, grid_normals=None, ground=plane,
            settings=normal_settings,
        )

    profile = _normalized_tier_profile(
        u, v, heights,
        num_tiers=pcfg["num_tiers"],
        min_tier_ratio=pcfg["tier_min_point_ratio"],
        thin_width_m=pcfg["thin_bridge_width_m"],
        thin_ratio=pcfg["thin_bridge_point_ratio"],
        tier_normals=tier_normals,
        tier_normal_valid=tier_normal_valid,
    )
    out["normalized_profile"] = profile
    out["normal_features"] = norm_feat

    if out["class"] in (CLASS_FRAGMENT, CLASS_PLANAR, CLASS_OTHER):
        out["rejection_reasons"] = [out["reason"] or out["class"]]
        return out

    reasons = []
    # 1. 表面法向平面度与盒体拒识（拦截较窄门板、柜面、双面直角箱体）
    if norm_feat is not None and norm_feat.get("available"):
        sp = norm_feat["single_plane_inlier_ratio"]
        dp = norm_feat["dual_plane_inlier_ratio"]
        ent = norm_feat["normal_azimuth_entropy"]
        s_ent = norm_feat["normal_sphere_entropy"]
        non_h = norm_feat["non_horizontal_fraction"]
        med_r = norm_feat["median_local_roughness"]

        if out["class"] == CLASS_LYING:
            if sp >= pcfg["lying_plane_reject_ratio"] and s_ent <= pcfg["lying_max_sphere_entropy"]:
                reasons.append("surface_normal_flat_horizontal_plane")
        else:
            if (sp >= pcfg["single_plane_reject_ratio"]
                    and (ent <= pcfg["planar_max_azimuth_entropy"]
                         or non_h < pcfg["planar_non_horiz_floor"])):
                reasons.append("surface_normal_single_plane")
            elif (dp >= pcfg["dual_plane_reject_ratio"]
                  and ent <= pcfg["dual_plane_max_azimuth_entropy"]
                  and med_r is not None and med_r <= pcfg["dual_plane_max_roughness"]):
                reasons.append("surface_normal_dual_plane_box")

    if reasons:
        rejected = _classify(out, CLASS_PLANAR, reasons[0])
        rejected["rejection_reasons"] = reasons
        return rejected

    # 2. 悬空/细杆粘连/顶重脚轻结构拒识（覆盖悬挂鸟粘连支架、衣帽架、落地灯）
    height_span_m = out["features"]["height_span_m"]
    if height_span_m >= pcfg["adhesion_check_min_span_m"] and out["class"] != CLASS_LYING:
        hang_reasons = []
        # r2：断层/低填充类判据必须同时满足“底部离地”（p02 高度 >= detached_bottom_min_m）。
        # 底部贴地的簇出现中段断层，更常见的是桌面/椅背遮挡人体中段，不能单凭断层判悬空粘连。
        bottom_detached = profile["height_p02_m"] >= pcfg["detached_bottom_min_m"]
        profile["bottom_detached"] = bool(bottom_detached)
        gap_hit = profile["max_empty_tier_run"] >= pcfg["max_empty_tier_run"]
        fill_hit = profile["vertical_fill"] < pcfg["min_normalized_vertical_fill"]
        if gap_hit and bottom_detached:
            hang_reasons.append("vertical_profile_gap_discontinuity")
        if fill_hit and bottom_detached:
            hang_reasons.append("low_normalized_vertical_fill")
        if (gap_hit or fill_hit) and not bottom_detached:
            out["physical_notes"] = ["gap_ignored_bottom_ground_supported"]
        if (profile["top_third_ratio"] >= pcfg["max_top_third_ratio"]
                and profile["min_third_ratio"] < pcfg["min_third_ratio"]):
            hang_reasons.append("top_heavy_hanging_mass_concentration")
        if (profile["thin_bridge_tier_count"] >= pcfg["max_thin_bridge_tiers"]
                and profile["top_to_mid_width_ratio"] >= pcfg["max_top_to_mid_width_ratio"]):
            hang_reasons.append("thin_bridge_lollipop_adhesion")
        if hang_reasons:
            rejected = _classify(out, CLASS_HANGING_ADHESION, hang_reasons[0])
            rejected["rejection_reasons"] = hang_reasons
            return rejected

    return out
