"""GL-S02 lowest_floor_sheet_v3_fine_roi: fine-grained ROI selection.

v1/v2 stay frozen. This entry first defers to v2 (v1 success -> verbatim; v2
success -> verbatim). It only takes over when v2 reports
`INSUFFICIENT_CLEAN_ROI_SUPPORT` (A-layer identity already passed, 25cm ROI
support failed): it selects 15cm boxes with the same purity gates (thickness /
normal / RMS / plane gap unchanged; per-frame points scaled 30 -> >=20, which
is also the downstream per-region holdout minimum) and the same spread /
independence / conditioning contract.
"""
import math

import numpy as np

from floor_detector import PROFILE, detect_floor_regions
from floor_sheet import (SHEET_PROFILE, _discover_planes, _sheet_metrics,
                         detect_floor_regions_v2)
from leveling_quality import rotation

FINE_PROFILE = {
    "id": "lowest_floor_sheet_v3_fine_roi",
    "grid_m": .15,
    "min_points_per_frame": 20,  # >= leveling_quality.PROFILE["min_points_per_region"] per frame
    "roi_min_separation_m": .50,
    "condition_min": .10,
}


def _identity_gates(sheet, margin, share):
    """Same five booleans as floor_sheet.detect_floor_regions_v2 (kept local, v2 frozen)."""
    p = SHEET_PROFILE
    return {
        "lowest": margin >= p["lowest_margin_min_m"],
        "dominant": share >= p["dominance_share_min"],
        "connected": (sheet["effective_area_m2"] >= p["min_effective_area_m2"]
                      and sheet["effective_coverage"] >= p["min_effective_coverage"]),
        "gap": (not sheet["bridging_needed"]) or (bool(sheet["gap_pairs"])
               and all(pair["explained"] for pair in sheet["gap_pairs"])),
        "temporal": (sheet["temporal_p05"] is not None
                     and sheet["temporal_p05"] >= p["temporal_p05_min"]),
    }


def fine_boxes(work, frame_ids, initial, plane):
    """15cm boxes on the identified plane; v1-equivalent purity gates."""
    grid = FINE_PROFILE["grid_m"]
    normal, offset = np.asarray(plane["normal"]), plane["offset_m"]
    nd = initial @ normal
    display = work @ initial.T
    keys = np.floor(display[:, :2] / grid).astype("i4")
    unique, inverse = np.unique(keys, axis=0, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    splits = np.r_[0, np.cumsum(np.bincount(inverse))]
    frame_uniques = np.unique(frame_ids)
    frame_index = np.searchsorted(frame_uniques, frame_ids)
    boxes = []
    for i, key in enumerate(unique):
        index = order[splits[i]:splits[i + 1]]
        counts = np.bincount(frame_index[index], minlength=len(frame_uniques))
        if counts.min() < FINE_PROFILE["min_points_per_frame"] or len(index) < 2:
            continue
        cell = display[index]
        span = float(np.ptp(cell[:, 2]))
        if span > PROFILE["cell_height_span_max_m"]:
            continue
        values, vectors = np.linalg.eigh(np.cov(cell.T))
        local_normal = vectors[:, 0]
        if abs(local_normal[2]) < PROFILE["normal_alignment_min"]:
            continue
        rms = math.sqrt(max(0., float(values[0])))
        if rms > PROFILE["cell_local_rms_max_m"]:
            continue
        center = cell.mean(axis=0)
        predicted = -(nd[0] * center[0] + nd[1] * center[1] + offset) / nd[2]
        if (abs(center[2] - predicted) > PROFILE["cell_floor_gap_max_m"]
                or abs(cell[:, 2].min() - predicted) > PROFILE["cell_height_span_max_m"]):
            continue
        boxes.append({"key": [int(key[0]), int(key[1])],
                      "center_m": [float(center[0]), float(center[1])],
                      "count": int(len(index)), "min_frame_count": int(counts.min()),
                      "height_span_m": span, "rms_m": rms,
                      "normal_z": float(abs(local_normal[2]))})
    return boxes


def _select_four(boxes):
    """Pick 4 boxes satisfying spread+conditioning; among feasible sets prefer low per-box RMS.

    All spread / independence / conditioning gates are unchanged (>= gates identical to
    v1/v2). RMS is used ONLY to rank already-feasible combinations, not as an extra gate:
    a box that passed the purity gates can never be rejected for its rms alone.
    """
    import itertools

    p = FINE_PROFILE
    n = len(boxes)
    if n < 4:
        return None
    centers = np.array([box["center_m"] for box in boxes])
    rms = np.array([box["rms_m"] for box in boxes])
    dist = np.hypot(centers[:, None, 0] - centers[None, :, 0],
                    centers[:, None, 1] - centers[None, :, 1])

    def evaluate(index):
        sub = dist[np.ix_(index, index)]
        separation = float(sub[np.triu_indices(4, 1)].min())
        pts = centers[list(index)]
        singular = np.linalg.svd(pts - pts.mean(axis=0), compute_uv=False)
        condition = float(max(0., singular[-1] / max(singular[0], 1e-30)))
        return separation, condition

    def feasible(index):
        separation, condition = evaluate(index)
        if separation < p["roi_min_separation_m"] or condition < p["condition_min"]:
            return None
        return separation, condition

    # Rank: (1) feasible, (2) minimise max box rms, (3) minimise mean rms,
    # (4) maximise conditioning, (5) maximise spread. Gates unchanged; rms only ranks.
    def rank(index, separation, condition):
        sel_rms = rms[list(index)]
        return (-float(sel_rms.max()), -float(sel_rms.mean()), condition, separation)

    best = None
    if n <= 60:  # C(60,4) ~ 487k, exhaustive is cheap and deterministic
        for combo in itertools.combinations(range(n), 4):
            got = feasible(combo)
            if got is None:
                continue
            key = rank(combo, *got)
            if best is None or key > best[0]:
                best = (key, combo, got[0], got[1])
    else:
        for seed in range(n):
            chosen = [seed]
            while len(chosen) < 4:
                d = np.min(dist[np.ix_(chosen, range(n))], axis=0)
                d[chosen] = -1.
                chosen.append(int(np.argmax(d)))
            got = feasible(tuple(chosen))
            if got is not None:
                key = rank(tuple(chosen), *got)
                if best is None or key > best[0]:
                    best = (key, tuple(chosen), got[0], got[1])
    if best is None:
        return None
    return {"index": best[1], "min_sep_m": best[2], "condition": best[3]}


def detect_floor_regions_v3(points, frame_ids, pitch_deg, roll_deg):
    """v1/v2 verbatim; only v2's INSUFFICIENT verdict enables the 15cm ROI layer."""
    try:
        return detect_floor_regions_v2(points, frame_ids, pitch_deg, roll_deg)
    except ValueError as exc:
        if not str(exc).startswith("INSUFFICIENT_CLEAN_ROI_SUPPORT"):
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
    gates = _identity_gates(sheet, margin, share)
    if not all(gates.values()):
        raise ValueError("floor_regions_invalid: floor identity failed (%s)" % gates)

    boxes = fine_boxes(work, frames, initial, chosen)
    pick = _select_four(boxes)
    if pick is None:
        raise ValueError(
            "INSUFFICIENT_CLEAN_ROI_SUPPORT: fine_roi grid=%.2fm clean_boxes=%d "
            "need 4 with sep>=%.2fm cond>=%.2f"
            % (FINE_PROFILE["grid_m"], len(boxes), FINE_PROFILE["roi_min_separation_m"],
               FINE_PROFILE["condition_min"]))
    selected_boxes = sorted((boxes[i] for i in pick["index"]), key=lambda box: tuple(box["key"]))
    grid = FINE_PROFILE["grid_m"]
    regions, selected = [], []
    for box in selected_boxes:
        kx, ky = box["key"]
        regions.append([kx * grid, (kx + 1) * grid, ky * grid, (ky + 1) * grid])
        selected.append({"bounds": regions[-1], "count": box["count"],
                         "min_frame_count": box["min_frame_count"],
                         "height_span_m": box["height_span_m"],
                         "local_rms_m": box["rms_m"], "local_normal_z": box["normal_z"]})
    candidate = {
        "kind": FINE_PROFILE["id"], "profile": dict(FINE_PROFILE),
        "normal_source": chosen["normal"], "offset_source_m": chosen["offset_m"],
        "support_ratio": float(np.mean(np.abs(work @ np.asarray(chosen["normal"])
                                             + chosen["offset_m"]) <= .08)),
        "fit_frame_count": int(len(np.unique(frame_ids))),
        "component_cells": sheet["effective_cells"],
        "component_area_m2": sheet["effective_area_m2"],
        "sheet": {key: sheet[key] for key in
                  ("occupied_cells", "largest_area_m2", "effective_area_m2", "effective_coverage",
                   "bridging_needed", "unexplained_gap_count", "temporal_p05", "gap_pairs")},
        "roi": {"grid_m": grid, "clean_boxes": len(boxes), "min_sep_m": pick["min_sep_m"],
                "independent_count": 4, "condition": pick["condition"]},
        "selected_cells": selected,
        "full_height_preserved": True, "uses_manual_reference": False,
        "basis": ("floor sheet v3 fine ROI: A identity %.2fm2; %d clean %.2fm boxes; "
                  "selected min_sep %.2fm cond %.2f"
                  % (sheet["effective_area_m2"], len(boxes), grid, pick["min_sep_m"],
                     pick["condition"])),
    }
    return {"regions": regions, "candidate": candidate}
