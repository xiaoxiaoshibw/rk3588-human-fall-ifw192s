"""GL-S01 lowest_floor_sheet_v2: floor identity layer for auto leveling.

Primary path stays frozen v1 (`floor_detector.detect_floor_regions`): on v1
success this module returns the v1 result verbatim. It only takes over when
v1 rejects with `floor_regions_invalid`, to certify:

A-layer identity: RANSAC plane -> +-eps sheet -> 5cm multi-frame occupancy
    -> connected components -> bounded contact-gap bridging.
B-layer support: v1 clean-25cm-cell gates (unchanged) + four-ROI spread
    (min separation / independence / conditioning).

Failure semantics: A fails -> `floor_regions_invalid: floor identity failed`;
A passes / B fails -> `INSUFFICIENT_CLEAN_ROI_SUPPORT`; both pass -> regions
plus candidate kind `lowest_floor_sheet_v2`.
"""
import itertools
import math

import numpy as np

from floor_detector import PROFILE, components, detect_floor_regions
from leveling_estimators import ESTIMATORS
from leveling_quality import rotation

SHEET_PROFILE = {
    "id": "lowest_floor_sheet_v2", "eps_m": .03, "grid_m": .05,
    "min_points_per_cell": 10, "min_frames_seen": 20, "frame_hit_ratio": .30,
    "contact_tau_m": .05, "contact_points_min": 5,
    "contact_cell_ratio_min": .50, "gap_cells_max": 4,
    "significant_fragment_m2": .25, "min_effective_area_m2": .50,
    "min_effective_coverage": .50,
    "roi_min_separation_m": .50, "condition_min": .10,
    "temporal_p05_min": .30, "lowest_margin_min_m": .05,
    "dominance_share_min": .30,
}


def _discover_planes(work, anchor):
    """Identical discovery loop to v1 (same seed/band/range), kept local so v1 stays frozen."""
    voxel = np.floor(work / PROFILE["voxel_m"]).astype("i4")
    _, inverse = np.unique(voxel, axis=0, return_inverse=True)
    count = np.bincount(inverse)
    representatives = np.column_stack(
        [np.bincount(inverse, weights=work[:, i]) / count for i in range(3)])
    remaining, planes = representatives, []
    for _ in range(PROFILE["max_discovery_planes"]):
        if len(remaining) < 80:
            break
        normal, offset = ESTIMATORS["ransac"](remaining)
        if normal @ anchor < 0:
            normal, offset = -normal, -offset
        distances = np.abs(remaining @ normal + offset)
        inliers = distances <= PROFILE["discovery_band_m"]
        if (normal @ anchor >= PROFILE["normal_alignment_min"]
                and PROFILE["offset_range_m"][0] <= offset <= PROFILE["offset_range_m"][1]):
            planes.append({"normal": normal.tolist(), "offset_m": float(offset),
                           "voxels": int(inliers.sum())})
        if not inliers.any():
            break
        remaining = remaining[~inliers]
    return planes


def _clean_cells(work, frame_ids, initial, plane):
    """v1 clean-25cm-cell gates plus plane match; returns [{key,count,...}]."""
    normal = np.asarray(plane["normal"])
    offset = plane["offset_m"]
    nd = initial @ normal
    display = work @ initial.T
    residual = work @ normal + offset
    keys = np.floor(display[:, :2] / PROFILE["cell_m"]).astype("i4")
    unique, inverse = np.unique(keys, axis=0, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    splits = np.r_[0, np.cumsum(np.bincount(inverse))]
    frame_uniques = np.unique(frame_ids)
    frame_index = np.searchsorted(frame_uniques, frame_ids)
    clean = []
    for i, key in enumerate(unique):
        index = order[splits[i]:splits[i + 1]]
        counts = np.bincount(frame_index[index], minlength=len(frame_uniques))
        if counts.min() < PROFILE["min_points_per_fit_frame"]:
            continue
        cell = display[index]
        height_span = float(np.ptp(cell[:, 2]))
        if height_span > PROFILE["cell_height_span_max_m"] or len(index) < 2:
            continue
        values, vectors = np.linalg.eigh(np.cov(cell.T))
        local_normal = vectors[:, 0]
        local_rms = math.sqrt(max(0., float(values[0])))
        if abs(local_normal[2]) < PROFILE["normal_alignment_min"] or local_rms > PROFILE["cell_local_rms_max_m"]:
            continue
        center = cell.mean(axis=0)
        predicted = -(nd[0] * center[0] + nd[1] * center[1] + offset) / nd[2]
        if (abs(center[2] - predicted) > PROFILE["cell_floor_gap_max_m"]
                or abs(cell[:, 2].min() - predicted) > PROFILE["cell_height_span_max_m"]):
            continue
        clean.append({"key": [int(key[0]), int(key[1])], "count": int(len(index)),
                      "min_frame_count": int(counts.min()), "height_span_m": height_span,
                      "local_rms_m": local_rms, "local_normal_z": float(abs(local_normal[2]))})
    return clean


def _sheet_metrics(work, frame_ids, initial, plane):
    """A-layer identity metrics for one plane (see module docstring)."""
    p = SHEET_PROFILE
    normal = np.asarray(plane["normal"])
    offset = plane["offset_m"]
    residual = work @ normal + offset
    mask = np.abs(residual) <= p["eps_m"]
    sheet, sheet_frames = work[mask], frame_ids[mask]
    display = sheet @ initial.T
    keys = np.floor(display[:, :2] / p["grid_m"]).astype("i4")
    uniq, inv = np.unique(keys, axis=0, return_inverse=True)
    frame_uniques = np.unique(frame_ids)
    nf = len(frame_uniques)
    findex = np.searchsorted(frame_uniques, sheet_frames)
    pair = inv.astype("i8") * nf + findex
    upair = np.unique(pair)
    frames_seen = np.bincount(upair // nf, minlength=len(uniq))
    points_seen = np.bincount(inv, minlength=len(uniq))
    occupied = ((points_seen >= p["min_points_per_cell"])
                & (frames_seen >= p["min_frames_seen"])
                & (frames_seen / nf >= p["frame_hit_ratio"]))
    occ_keys = [tuple(k) for k, m in zip(uniq, occupied) if m]
    comps = sorted(components(set(occ_keys)), key=lambda g: (-len(g), min(g)))
    total_occ = len(occ_keys)
    largest = len(comps[0]) if comps else 0
    cell_area = p["grid_m"] ** 2

    adisplay = work @ initial.T
    akeys = np.floor(adisplay[:, :2] / p["grid_m"]).astype("i4")
    auniq, ainv = np.unique(akeys, axis=0, return_inverse=True)
    aorder = np.argsort(ainv, kind="stable")
    asplits = np.r_[0, np.cumsum(np.bincount(ainv))]
    index = {tuple(k): i for i, k in enumerate(auniq)}

    def corridor_stats(a, b):
        a_cells, b_cells = set(a), set(b)
        A, B = np.array(sorted(a_cells)), np.array(sorted(b_cells))
        if len(A) * len(B) > 20_000_000:
            A = A[::max(1, len(A) // 4000)]
            B = B[::max(1, len(B) // 4000)]
        d = np.maximum(np.abs(A[:, None, 0] - B[None, :, 0]),
                       np.abs(A[:, None, 1] - B[None, :, 1]))
        ai, bi = np.unravel_index(int(np.argmin(d)), d.shape)
        (x0, y0), (x1, y1) = A[ai], B[bi]
        steps = int(max(abs(x1 - x0), abs(y1 - y0)))
        line = {}
        for t in np.linspace(0., 1., max(steps, 1) * 2 + 1):
            cx, cy = int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t))
            key = (cx, cy)
            if key not in a_cells and key not in b_cells:
                line[key] = None
        n_gap = contact_cells = empty_cells = 0
        for key in line:
            i = index.get(key)
            if i is None:
                empty_cells += 1
                continue
            idx = aorder[asplits[i]:asplits[i + 1]]
            n_gap += len(idx)
            if np.any(np.abs(residual[idx]) <= p["contact_tau_m"]):
                contact_cells += 1
        gap_cells = len(line)
        cell_ratio = contact_cells / gap_cells if gap_cells else 0.
        explained = bool(gap_cells >= 1 and empty_cells == 0 and gap_cells <= p["gap_cells_max"]
                         and n_gap >= p["contact_points_min"] and contact_cells >= 1
                         and cell_ratio >= p["contact_cell_ratio_min"])
        return {"cells": gap_cells, "width_m": gap_cells * p["grid_m"], "n_points": n_gap,
                "empty_cells": empty_cells, "contact_cells": contact_cells,
                "contact_cell_ratio": cell_ratio, "explained": explained}

    sig = [c for c in comps if len(c) * cell_area >= p["significant_fragment_m2"]]
    sig = sig[:4]
    pairs = [corridor_stats(sig[a], sig[b]) for a, b in itertools.combinations(range(len(sig)), 2)]
    bridging_needed = largest * cell_area < p["min_effective_area_m2"]
    effective = largest
    if bridging_needed:
        combos = list(itertools.combinations(range(len(sig)), 2))
        for i in range(1, len(sig)):
            join = [pairs[k] for k, (a, b) in enumerate(combos) if i in (a, b)]
            if join and all(c["explained"] for c in join):
                effective += len(sig[i])
    unexplained = [c for c in pairs if not c["explained"]]

    temporal_p05 = temporal_median = None
    if comps:
        uniq_index = {tuple(k): i for i, k in enumerate(uniq)}
        comp_ids = np.array([uniq_index[tuple(k)] for k in comps[0]], dtype="i8")
        member = np.isin(inv, comp_ids)
        up = np.unique(pair[member])
        per_frame = np.bincount(up % nf, minlength=nf) / len(comp_ids)
        temporal_p05, temporal_median = float(np.percentile(per_frame, 5)), float(np.median(per_frame))

    return {"sheet_points": int(len(sheet)), "occupied_cells": total_occ,
            "largest_cells": largest, "largest_area_m2": largest * cell_area,
            "significant_components": [len(c) for c in sig],
            "bridging_needed": bool(bridging_needed), "effective_cells": effective,
            "effective_area_m2": effective * cell_area,
            "effective_coverage": (effective / total_occ) if total_occ else 0.,
            "gap_pairs": pairs, "unexplained_gap_count": len(unexplained),
            "temporal_p05": temporal_p05, "temporal_median": temporal_median}


def _roi_metrics(clean):
    """B-layer support: four clean cells with spread / independence / conditioning."""
    p = SHEET_PROFILE
    keys = np.array(sorted([c["key"] for c in clean]))
    n = len(keys)
    if n < 4:
        return {"ok": False, "reason": "clean_cells<4", "clean_cells": n,
                "selected": [], "min_sep_m": None, "independent_count": 0, "condition": None}
    if n <= 24:
        best, best_sep = None, -1.
        for combo in itertools.combinations(range(n), 4):
            pts = keys[list(combo)].astype("f8")
            sep = min(float(np.hypot(*(pts[a] - pts[b])))
                      for a, b in itertools.combinations(range(4), 2))
            if sep > best_sep:
                best_sep, best = sep, combo
    else:
        chosen = [int(np.argmax(np.linalg.norm(keys - keys.mean(axis=0), axis=1)))]
        while len(chosen) < 4:
            dist = np.min(np.linalg.norm(keys[:, None, :] - keys[chosen][None, :, :], axis=2), axis=1)
            chosen.append(int(np.argmax(dist)))
        best = tuple(chosen)
        best_sep = min(float(np.hypot(*(keys[a] - keys[b])))
                       for a, b in itertools.combinations(chosen, 2))
    sel = keys[list(best)].astype("f8")
    min_sep = best_sep * PROFILE["cell_m"]
    dist = np.hypot(sel[:, None, 0] - sel[None, :, 0], sel[:, None, 1] - sel[None, :, 1])
    np.fill_diagonal(dist, np.inf)
    independent = int(np.all(dist >= p["roi_min_separation_m"] / PROFILE["cell_m"], axis=1).sum())
    singular = np.linalg.svd(sel - sel.mean(axis=0), compute_uv=False)
    condition = float(max(0., singular[-1] / max(singular[0], 1e-30)))
    ok = bool(min_sep >= p["roi_min_separation_m"] and independent == 4
              and condition >= p["condition_min"])
    return {"ok": ok, "clean_cells": n, "selected": sel.tolist(), "min_sep_m": min_sep,
            "independent_count": independent, "condition": condition}


def detect_floor_regions_v2(points, frame_ids, pitch_deg, roll_deg):
    """v1 success returns v1 verbatim; otherwise A/B certification of the reject."""
    try:
        return detect_floor_regions(points, frame_ids, pitch_deg, roll_deg)
    except ValueError as exc:
        if not str(exc).startswith("floor_regions_invalid"):
            raise

    points = np.asarray(points, dtype=np.float64)
    frame_ids = np.asarray(frame_ids)
    if points.ndim != 2 or points.shape[1] != 3 or not len(points) or len(points) != len(frame_ids):
        raise ValueError("floor_auto_candidate_invalid: 空域")
    inside = (np.abs(points) <= 100).all(axis=1)
    work, frames = points[inside], frame_ids[inside]
    initial = rotation(pitch_deg, roll_deg)
    planes = _discover_planes(work, initial[2])
    if not planes:
        raise ValueError("floor_regions_invalid: floor identity failed (no plane hypothesis)")
    chosen = max(planes, key=lambda plane: plane["offset_m"])
    others = [plane for plane in planes if plane is not chosen]
    margin = (chosen["offset_m"] - max(plane["offset_m"] for plane in others)) if others else math.inf
    share = chosen["voxels"] / max(sum(plane["voxels"] for plane in planes), 1)

    sheet = _sheet_metrics(work, frames, initial, chosen)
    p = SHEET_PROFILE
    lowest_enough = margin >= p["lowest_margin_min_m"]
    dominant_enough = share >= p["dominance_share_min"]
    connected_enough = (sheet["effective_area_m2"] >= p["min_effective_area_m2"]
                        and sheet["effective_coverage"] >= p["min_effective_coverage"])
    gap_ok = (not sheet["bridging_needed"]) or (bool(sheet["gap_pairs"])
              and all(c["explained"] for c in sheet["gap_pairs"]))
    temporal_stable = (sheet["temporal_p05"] is not None
                       and sheet["temporal_p05"] >= p["temporal_p05_min"])
    if not (lowest_enough and dominant_enough and connected_enough and gap_ok and temporal_stable):
        raise ValueError(
            "floor_regions_invalid: floor identity failed (lowest=%s dominant=%s connected=%s gap=%s temporal=%s)"
            % (lowest_enough, dominant_enough, connected_enough, gap_ok, temporal_stable))

    clean = _clean_cells(work, frames, initial, chosen)
    roi = _roi_metrics(clean)
    if not roi["ok"]:
        raise ValueError(
            "INSUFFICIENT_CLEAN_ROI_SUPPORT: clean_cells=%d independent=%d min_sep_m=%s condition=%s"
            % (roi["clean_cells"], roi["independent_count"],
               "None" if roi["min_sep_m"] is None else "%.3f" % roi["min_sep_m"],
               "None" if roi["condition"] is None else "%.3f" % roi["condition"]))

    details = {tuple(c["key"]): c for c in clean}
    regions, selected = [], []
    for kx, ky in sorted((int(v[0]), int(v[1])) for v in roi["selected"]):
        regions.append([kx * PROFILE["cell_m"], (kx + 1) * PROFILE["cell_m"],
                        ky * PROFILE["cell_m"], (ky + 1) * PROFILE["cell_m"]])
        cell = details[(kx, ky)]
        selected.append({"bounds": regions[-1], "count": cell["count"],
                         "min_frame_count": cell["min_frame_count"],
                         "height_span_m": cell["height_span_m"],
                         "local_rms_m": cell["local_rms_m"],
                         "local_normal_z": cell["local_normal_z"]})
    candidate = {
        "kind": SHEET_PROFILE["id"], "profile": dict(SHEET_PROFILE),
        "normal_source": chosen["normal"], "offset_source_m": chosen["offset_m"],
        "support_ratio": float(np.mean(np.abs(work @ np.asarray(chosen["normal"])
                                             + chosen["offset_m"]) <= .08)),
        "fit_frame_count": int(len(np.unique(frame_ids))),
        "component_cells": sheet["effective_cells"],
        "component_area_m2": sheet["effective_area_m2"],
        "sheet": {key: sheet[key] for key in
                  ("occupied_cells", "largest_area_m2", "effective_area_m2",
                   "effective_coverage", "bridging_needed", "unexplained_gap_count",
                   "temporal_p05", "gap_pairs")},
        "roi": {key: roi[key] for key in ("clean_cells", "min_sep_m", "independent_count", "condition")},
        "selected_cells": selected,
        "full_height_preserved": True, "uses_manual_reference": False,
        "basis": ("floor sheet v2: A identity %.2fm2 cov %.2f p05 %s; B clean cells %d; bridging=%s"
                  % (sheet["effective_area_m2"], sheet["effective_coverage"],
                     "None" if sheet["temporal_p05"] is None else "%.2f" % sheet["temporal_p05"],
                     roi["clean_cells"], "not_needed" if not sheet["bridging_needed"] else "used")),
    }
    return {"regions": regions, "candidate": candidate}
