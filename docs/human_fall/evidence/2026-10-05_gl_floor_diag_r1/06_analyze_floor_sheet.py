"""Read-only A/B floor-sheet v2 design probe.

A层: RANSAC plane -> +-eps sheet (source frame) -> 5cm grid occupancy
     (min points / min frames / frame hit ratio) -> connected components
     -> bounded gap explanation by obstacle-contact evidence.
B层: v1 clean 25cm cells (gates unchanged) -> four-ROI distribution check.

No snapshot, no selection change, no pipeline/report writes. Every threshold
used for the provisional pass booleans is printed and marked provisional so
the synthetic regression suite can calibrate them later.
"""
import itertools
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "pc_apps" / "human_replay"))

from floor_detector import PROFILE, components  # noqa: E402
from leveling_estimators import ESTIMATORS  # noqa: E402
from leveling_quality import rotation  # noqa: E402

OUT = Path(__file__).resolve().parent
SIDS = ("cap_20261002_223757", "cap_20261004_203349",
        "cap_20261004_203135", "cap_20261004_202456")
PITCH_DEG, ROLL_DEG = 26.0, 0.0

# --- provisional v2 parameters (calibrate with synthetic regression) ---
EPS_LIST = (0.03, 0.05)
GRID_M = .05
MIN_POINTS_PER_CELL = 10
MIN_FRAMES_SEEN = 20
FRAME_HIT_RATIO = .30
CONTACT_TAU = .05
CONTACT_N_MIN = 5
CONTACT_RATIO_MIN = .5
GAP_CELLS_MAX = 4               # <=0.2 m bridge bound
MIN_COMPONENT_AREA_M2 = .5
ROI_MIN_SEP_M = .5
CONDITION_MIN = .1
TEMPORAL_P05_MIN = .30
LOWEST_MARGIN_MIN = .05
DOMINANCE_SHARE_MIN = .30


def load_session(sid):
    directory = ROOT / "captures" / "remote" / sid
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    xyz = np.ndarray((meta["total_points"], 3), dtype="<f4", buffer=raw, strides=(28, 4))
    frames = meta["frames"]
    nframes = len(frames)
    excluded = {(nframes - 1) // 3, 2 * (nframes - 1) // 3, nframes - 1}
    fit_ordinals = [i for i in range(nframes) if i not in excluded]
    chunks, ids = [], []
    for ordinal in fit_ordinals:
        frame = frames[ordinal]
        lo, count = frame["offset_points"], frame["count_points"]
        segment = xyz[lo:lo + count].astype("f8")
        valid = np.isfinite(segment).all(axis=1) & np.any(segment != 0, axis=1)
        chunks.append(segment[valid])
        ids.append(np.full(int(valid.sum()), ordinal, dtype="i4"))
    points = np.concatenate(chunks)
    frame_ids = np.concatenate(ids)
    del chunks, ids, xyz, raw
    inside = (np.abs(points) <= 100).all(axis=1)
    return points[inside], frame_ids[inside], len(fit_ordinals)


def discover_planes(work, anchor):
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


def v1_cells(work, frame_ids, initial):
    display = work @ initial.T
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
        cell = display[index]
        if counts.min() < PROFILE["min_points_per_fit_frame"]:
            continue
        if float(np.ptp(cell[:, 2])) > PROFILE["cell_height_span_max_m"]:
            continue
        if len(index) < 2:
            continue
        values, vectors = np.linalg.eigh(np.cov(cell.T))
        local_normal = vectors[:, 0]
        if abs(local_normal[2]) < PROFILE["normal_alignment_min"]:
            continue
        if math.sqrt(max(0., float(values[0]))) > PROFILE["cell_local_rms_max_m"]:
            continue
        clean.append([int(key[0]), int(key[1])])
    return clean


def cell_components(cell_keys):
    return sorted(components({tuple(k) for k in cell_keys}),
                  key=lambda g: (-len(g), min(g)))


def four_roi_check(clean_keys):
    keys = np.array(sorted(clean_keys))
    n = len(keys)
    if n < 4:
        return {"ok": False, "reason": "clean_cells<4", "selected": [],
                "min_sep_m": None, "independent_count": 0, "condition": None}
    best, best_sep = None, -1.0
    if n <= 24:
        for combo in itertools.combinations(range(n), 4):
            pts = keys[list(combo)].astype("f8")
            sep = min(float(np.hypot(*(pts[a] - pts[b]))) for a, b in itertools.combinations(range(4), 2))
            if sep > best_sep:
                best_sep, best = sep, combo
    else:  # greedy farthest point sampling
        chosen = [int(np.argmax(np.linalg.norm(keys - keys.mean(axis=0), axis=1)))]
        while len(chosen) < 4:
            dist = np.min(np.linalg.norm(keys[:, None, :] - keys[chosen][None, :, :], axis=2), axis=1)
            chosen.append(int(np.argmax(dist)))
        best, best_sep = tuple(chosen), min(
            float(np.hypot(*(keys[a] - keys[b]))) for a, b in itertools.combinations(chosen, 2))
    sel = keys[list(best)].astype("f8")
    min_sep = best_sep * PROFILE["cell_m"]
    dist = np.hypot(sel[:, None, 0] - sel[None, :, 0], sel[:, None, 1] - sel[None, :, 1])
    np.fill_diagonal(dist, np.inf)
    independent = int(np.all(dist >= ROI_MIN_SEP_M / PROFILE["cell_m"], axis=1).sum())
    centered = sel - sel.mean(axis=0)
    ratio = float(max(0., np.linalg.svd(centered, compute_uv=False)[-1] /
                      max(np.linalg.svd(centered, compute_uv=False)[0], 1e-30)))
    return {"ok": bool(min_sep >= ROI_MIN_SEP_M and independent == 4 and ratio >= CONDITION_MIN),
            "selected": sel.tolist(), "min_sep_m": min_sep, "independent_count": independent,
            "condition": ratio,
            "span_m": [float((sel[:, 0].ptp() + 1) * PROFILE["cell_m"]),
                       float((sel[:, 1].ptp() + 1) * PROFILE["cell_m"])]}


def sheet_metrics(work, frame_ids, initial, plane, eps):
    normal = np.asarray(plane["normal"])
    offset = plane["offset_m"]
    residual = work @ normal + offset
    mask = np.abs(residual) <= eps
    sheet, sheet_frames = work[mask], frame_ids[mask]
    display = sheet @ initial.T
    keys = np.floor(display[:, :2] / GRID_M).astype("i4")
    uniq, inv = np.unique(keys, axis=0, return_inverse=True)
    frame_uniques = np.unique(frame_ids)
    nf = len(frame_uniques)
    findex = np.searchsorted(frame_uniques, sheet_frames)
    pair = inv.astype("i8") * nf + findex
    upair = np.unique(pair)
    frames_seen = np.bincount(upair // nf, minlength=len(uniq))
    points_seen = np.bincount(inv, minlength=len(uniq))
    occupied = (points_seen >= MIN_POINTS_PER_CELL) & (frames_seen >= MIN_FRAMES_SEEN) \
        & (frames_seen / nf >= FRAME_HIT_RATIO)
    occ_keys = [tuple(k) for k, m in zip(uniq, occupied) if m]
    comps = sorted(components(set(occ_keys)), key=lambda g: (-len(g), min(g)))
    total_occ = len(occ_keys)
    largest = len(comps[0]) if comps else 0
    coverage = largest / total_occ if total_occ else 0.

    # all-points index for corridor/contact lookups
    adisplay = work @ initial.T
    akeys = np.floor(adisplay[:, :2] / GRID_M).astype("i4")
    auniq, ainv = np.unique(akeys, axis=0, return_inverse=True)
    aorder = np.argsort(ainv, kind="stable")
    asplits = np.r_[0, np.cumsum(np.bincount(ainv))]
    index = {tuple(k): i for i, k in enumerate(auniq)}

    def corridor_stats(a, b):
        a_cells, b_cells = set(a), set(b)
        A = np.array(sorted(a_cells)); B = np.array(sorted(b_cells))
        if len(A) * len(B) > 20_000_000:
            A = A[::max(1, len(A) // 4000)]; B = B[::max(1, len(B) // 4000)]
        d = np.maximum(np.abs(A[:, None, 0] - B[None, :, 0]),
                       np.abs(A[:, None, 1] - B[None, :, 1]))
        ai, bi = np.unravel_index(int(np.argmin(d)), d.shape)
        (x0, y0), (x1, y1) = A[ai], B[bi]
        steps = int(max(abs(x1 - x0), abs(y1 - y0)))
        line = {}
        for t in np.linspace(0., 1., max(steps, 1) * 2 + 1):
            cx, cy = int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t))
            key = (cx, cy)
            if key in a_cells or key in b_cells:
                continue
            line[key] = None
        n_gap = n_contact = 0
        gap_cells = 0
        for key in line:
            gap_cells += 1
            i = index.get(key)
            if i is None:
                continue
            idx = aorder[asplits[i]:asplits[i + 1]]
            n_gap += len(idx)
            n_contact += int(np.sum(np.abs(residual[idx]) <= CONTACT_TAU))
        contact_ratio = (n_contact / n_gap) if n_gap else 0.
        explained = bool(n_gap >= CONTACT_N_MIN and contact_ratio >= CONTACT_RATIO_MIN
                         and gap_cells <= GAP_CELLS_MAX)
        return {"cells": gap_cells, "width_m": gap_cells * GRID_M, "n_points": n_gap,
                "contact_ratio": contact_ratio, "explained": explained,
                "closest_pair": [[int(x0), int(y0)], [int(x1), int(y1)]]}

    # gaps only matter between significant fragments (<=0.25 m2 satellite
    # patches are reported but cannot invalidate an already-viable sheet);
    # bridging is only *needed* when the largest fragment alone is too small.
    sig = [c for c in comps if len(c) * GRID_M * GRID_M >= .25]
    top = sig[:4]
    pairs = []
    for a, b in itertools.combinations(range(len(top)), 2):
        pairs.append(corridor_stats(top[a], top[b]))
    bridging_needed = (largest * GRID_M * GRID_M) < MIN_COMPONENT_AREA_M2
    effective = largest
    if bridging_needed:
        combos = list(itertools.combinations(range(len(top)), 2))
        for i in range(1, len(top)):
            join = [pairs[k] for k, (a, b) in enumerate(combos) if i in (a, b)]
            if join and all(p["explained"] for p in join):
                effective += len(top[i])
    sig_unexplained = [p for p in pairs if not p["explained"]]
    max_unexplained = max((p["width_m"] for p in sig_unexplained), default=0.)

    # temporal stability of the largest component
    temporal = {"p05": None, "median": None}
    if comps:
        uniq_index = {tuple(k): i for i, k in enumerate(uniq)}
        comp_ids = np.array([uniq_index[tuple(k)] for k in comps[0]], dtype="i8")
        member = np.isin(inv, comp_ids)
        cf = pair[member]
        up = np.unique(cf)
        per_frame = np.bincount(up % nf, minlength=nf) / len(comp_ids)
        temporal = {"p05": float(np.percentile(per_frame, 5)),
                    "median": float(np.median(per_frame))}
    return {"eps_m": eps, "sheet_points": int(len(sheet)), "occupied_cells": total_occ,
            "components": [len(c) for c in comps[:5]], "largest_cells": largest,
            "largest_area_m2": largest * GRID_M * GRID_M, "largest_coverage": coverage,
            "significant_components": [len(c) for c in sig[:5]],
            "bridging_needed": bool(bridging_needed),
            "effective_cells": effective, "effective_area_m2": effective * GRID_M * GRID_M,
            "effective_coverage": (effective / total_occ) if total_occ else 0.,
            "gap_pairs": pairs, "unexplained_gap_count": len(sig_unexplained),
            "max_unexplained_gap_m": max_unexplained, "temporal": temporal,
            "occupancy_params": {"min_points": MIN_POINTS_PER_CELL, "min_frames": MIN_FRAMES_SEEN,
                                 "hit_ratio": FRAME_HIT_RATIO}}


def analyze(sid):
    began = time.monotonic()
    work, frame_ids, fit_frames = load_session(sid)
    initial = rotation(PITCH_DEG, ROLL_DEG)
    anchor = initial[2]
    planes = discover_planes(work, anchor)
    chosen = max(planes, key=lambda p: p["offset_m"])
    others = [p for p in planes if p is not chosen]
    margin = (chosen["offset_m"] - max((p["offset_m"] for p in others), default=-math.inf)) \
        if others else math.inf
    share = chosen["voxels"] / max(sum(p["voxels"] for p in planes), 1)

    clean = v1_cells(work, frame_ids, initial)
    clusters = cell_components(clean)
    roi = four_roi_check(clean)

    sheets = [sheet_metrics(work, frame_ids, initial, chosen, eps) for eps in EPS_LIST]
    main = sheets[0]
    lowest_enough = bool(PROFILE["offset_range_m"][0] <= chosen["offset_m"]
                         <= PROFILE["offset_range_m"][1] and margin >= LOWEST_MARGIN_MIN)
    dominant_enough = bool(share >= DOMINANCE_SHARE_MIN)
    connected_enough = bool(main["effective_area_m2"] >= MIN_COMPONENT_AREA_M2
                            and main["effective_coverage"] >= .5)
    gap_ok = bool((not main["bridging_needed"])
                  or (len(main["gap_pairs"]) > 0
                      and all(p["explained"] for p in main["gap_pairs"])))
    temporal_stable = bool(main["temporal"]["p05"] is not None
                           and main["temporal"]["p05"] >= TEMPORAL_P05_MIN)
    identity_pass = lowest_enough and dominant_enough and connected_enough and gap_ok and temporal_stable
    final = ("IDENTITY_OK_ROI_OK" if identity_pass and roi["ok"] else
             "INSUFFICIENT_CLEAN_ROI_SUPPORT" if identity_pass else
             "FLOOR_IDENTITY_FAIL")
    return {
        "sid": sid, "fit_frames": fit_frames,
        "V1": {"clean_cells": len(clean), "clusters": [len(c) for c in clusters],
               "roi_candidates": roi["selected"]},
        "chosen_plane": {"offset_m": chosen["offset_m"], "voxels": chosen["voxels"],
                         "margin_m": margin, "voxel_share": share,
                         "discovered_offsets": [p["offset_m"] for p in planes]},
        "V2A_gates": {"lowest_enough": lowest_enough, "dominant_enough": dominant_enough,
                      "connected_enough": connected_enough, "gap_ok": gap_ok,
                      "temporal_stable": temporal_stable, "identity_pass": identity_pass},
        "V2A_sheets": sheets,
        "V2B": {"clean_roi_count": len(clean), **roi, "roi_pass": roi["ok"]},
        "FINAL": final, "seconds": round(time.monotonic() - began, 2),
    }


def main():
    results = [analyze(sid) for sid in SIDS]
    (OUT / "08_sheet_v2.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = []
    for r in results:
        a = r["V2A_sheets"][0]
        lines.append("== %s  final=%s  (%.1fs)" % (r["sid"], r["FINAL"], r["seconds"]))
        lines.append("  [V1] clean=%d clusters=%s" % (r["V1"]["clean_cells"], r["V1"]["clusters"]))
        lines.append("  [A] plane off=%.4f margin=%.4f share=%.3f gate(lowest=%s dominant=%s)"
                     % (r["chosen_plane"]["offset_m"], r["chosen_plane"]["margin_m"],
                        r["chosen_plane"]["voxel_share"],
                        r["V2A_gates"]["lowest_enough"], r["V2A_gates"]["dominant_enough"]))
        for s in r["V2A_sheets"]:
            lines.append("      eps=%.2f sheet_pts=%d occ_cells=%d comps=%s largest=%d(%.2fm2) "
                         "eff=%.2fm2 cov=%.2f bridge=%s gaps=%d unexp=%d max_unexp=%.2fm p05=%.2f"
                         % (s["eps_m"], s["sheet_points"], s["occupied_cells"], s["components"],
                            s["largest_cells"], s["largest_area_m2"], s["effective_area_m2"],
                            s["effective_coverage"], s["bridging_needed"], len(s["gap_pairs"]),
                            s["unexplained_gap_count"], s["max_unexplained_gap_m"],
                            s["temporal"]["p05"] if s["temporal"]["p05"] is not None else -1))
        lines.append("  [B] clean_roi=%d independent=%d min_sep=%.2fm cond=%.3f roi_pass=%s"
                     % (r["V2B"]["clean_roi_count"], r["V2B"]["independent_count"],
                        r["V2B"]["min_sep_m"] or 0., r["V2B"]["condition"] or 0.,
                        r["V2B"]["roi_pass"]))
        lines.append("  gates: connected=%s gap_ok=%s temporal=%s -> A=%s"
                     % (r["V2A_gates"]["connected_enough"], r["V2A_gates"]["gap_ok"],
                        r["V2A_gates"]["temporal_stable"], r["V2A_gates"]["identity_pass"]))
    text = "\n".join(lines)
    (OUT / "07_sheet_v2.log").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
