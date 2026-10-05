"""cap_20261002_223757 automatic floor-region failure diagnosis.

Read-only: replicates floor_detector.detect_floor_regions constants, order and
FIT-frame selection, but records per-cell rejection reasons instead of raising.
Uses the same pitch/roll as the GL-V01 r2 run (26 / 0). No gate is changed and
no production file is touched.
"""
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

SID = "cap_20261002_223757"
PITCH_DEG, ROLL_DEG = 26.0, 0.0
OUT = Path(__file__).resolve().parent


def plane_angles(normal):
    n = np.asarray(normal, dtype="f8")
    return (math.degrees(math.atan2(-n[0], n[2])),
            math.degrees(math.asin(float(np.clip(n[1], -1, 1)))))


def main():
    began = time.monotonic()
    directory = ROOT / "captures" / "remote" / SID
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
    work, frame_ids = points[inside], frame_ids[inside]
    del points

    initial = rotation(PITCH_DEG, ROLL_DEG)
    anchor = initial[2]

    # --- plane discovery, identical to floor_detector.detect_floor_regions ---
    voxel = np.floor(work / PROFILE["voxel_m"]).astype("i4")
    _, inverse = np.unique(voxel, axis=0, return_inverse=True)
    count = np.bincount(inverse)
    representatives = np.column_stack(
        [np.bincount(inverse, weights=work[:, i]) / count for i in range(3)])
    remaining = representatives
    planes = []
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
            pitch, roll = plane_angles(normal)
            planes.append({"order": len(planes), "normal": normal.tolist(),
                           "offset_m": float(offset), "pitch_deg": pitch, "roll_deg": roll,
                           "discovery_voxels": int(inliers.sum())})
        if not inliers.any():
            break
        remaining = remaining[~inliers]

    # --- per-cell accounting, same checks and order as the detector ---
    display = work @ initial.T
    keys = np.floor(display[:, :2] / PROFILE["cell_m"]).astype("i4")
    unique, inverse = np.unique(keys, axis=0, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    splits = np.r_[0, np.cumsum(np.bincount(inverse))]
    frame_uniques = np.unique(frame_ids)
    frame_index = np.searchsorted(frame_uniques, frame_ids)

    cells = []
    for i, key in enumerate(unique):
        index = order[splits[i]:splits[i + 1]]
        counts = np.bincount(frame_index[index], minlength=len(frame_uniques))
        cell = display[index]
        height_span = float(np.ptp(cell[:, 2]))
        # Detector skips cells below min_points_per_fit_frame / height_span
        # before eigh; keep accounting for those without crashing on n<2.
        if len(index) >= 2:
            values, vectors = np.linalg.eigh(np.cov(cell.T))
            local_normal = vectors[:, 0]
            local_rms = math.sqrt(max(0., float(values[0])))
            local_nz = float(abs(local_normal[2]))
        else:
            local_rms, local_nz = float("inf"), 0.
        reasons = []
        if counts.min() < PROFILE["min_points_per_fit_frame"]:
            reasons.append("min_frame_count")
        if height_span > PROFILE["cell_height_span_max_m"]:
            reasons.append("height_span")
        if local_nz < PROFILE["normal_alignment_min"]:
            reasons.append("normal_z")
        if local_rms > PROFILE["cell_local_rms_max_m"]:
            reasons.append("local_rms")
        cells.append({
            "key": [int(key[0]), int(key[1])],
            "count": int(len(index)), "min_frame_count": int(counts.min()),
            "median_frame_count": int(np.median(counts)), "max_frame_count": int(counts.max()),
            "frames_below_min": int((counts < PROFILE["min_points_per_fit_frame"]).sum()),
            "height_span_m": height_span,
            "local_normal_z": local_nz, "local_rms_m": local_rms,
            "center": [float(v) for v in cell.mean(axis=0)],
            "z_min": float(cell[:, 2].min()), "z_max": float(cell[:, 2].max()),
            "reasons": reasons})

    clean = [c for c in cells if not c["reasons"]]

    # --- plane matching / components, same conditions as the detector ---
    matches = []
    for p in planes:
        normal = np.asarray(p["normal"])
        offset = p["offset_m"]
        nd = initial @ normal
        matched, gap_failures = [], []
        for c in clean:
            center = c["center"]
            predicted = -(nd[0] * center[0] + nd[1] * center[1] + offset) / nd[2]
            gap_center = abs(center[2] - predicted)
            gap_zmin = abs(c["z_min"] - predicted)
            if (gap_center <= PROFILE["cell_floor_gap_max_m"]
                    and gap_zmin <= PROFILE["cell_height_span_max_m"]):
                matched.append(c)
            else:
                gap_failures.append({"key": c["key"], "gap_center_m": gap_center,
                                     "gap_zmin_m": gap_zmin, "min_frame_count": c["min_frame_count"]})
        groups = sorted(components({tuple(c["key"]) for c in matched}),
                        key=lambda g: (-len(g), min(g)))
        groups_info = []
        would_qualify = False
        for g in groups:
            xy = np.array(g)
            span = ((np.ptp(xy, axis=0) + 1) * PROFILE["cell_m"]).tolist()
            ok = (len(g) >= PROFILE["min_component_cells"]
                  and min(span) >= PROFILE["min_component_axis_m"])
            would_qualify = would_qualify or ok
            groups_info.append({"cells": len(g), "span_m": span, "would_qualify": bool(ok),
                                "member_keys": [list(k) for k in sorted(g)]})
        matches.append({"offset_m": p["offset_m"], "pitch_deg": p["pitch_deg"],
                        "roll_deg": p["roll_deg"], "clean_cells": len(matched),
                        "components": groups_info, "would_qualify": bool(would_qualify),
                        "clean_gap_failures": len(gap_failures),
                        "gap_failures": sorted(gap_failures, key=lambda r: r["gap_center_m"])[:40],
                        "matched_cells": [{"key": c["key"], "count": c["count"],
                                           "min_frame_count": c["min_frame_count"],
                                           "height_span_m": c["height_span_m"],
                                           "local_rms_m": c["local_rms_m"],
                                           "local_normal_z": c["local_normal_z"]} for c in matched]})

    reason_counts = Counter(r for c in cells for r in c["reasons"])
    first_reason = Counter(c["reasons"][0] if c["reasons"] else "clean" for c in cells)
    combo = Counter("+".join(sorted(c["reasons"])) if c["reasons"] else "clean" for c in cells)
    single = Counter()
    for c in cells:
        if len(c["reasons"]) == 1:
            single[c["reasons"][0]] += 1

    floor_band = [c for c in cells if -1.5 <= c["center"][2] <= -1.05]
    floor_band_reasons = Counter(c["reasons"][0] if c["reasons"] else "clean" for c in floor_band)
    clean_keys = {tuple(c["key"]) for c in clean}
    neighbors = []
    for c in cells:
        key = tuple(c["key"])
        if key in clean_keys or not c["reasons"]:
            continue
        if any((key[0] + dx, key[1] + dy) in clean_keys
               for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            neighbors.append({"key": c["key"], "reasons": c["reasons"],
                              "count": c["count"], "counts_min": c["min_frame_count"],
                              "counts_med": c["median_frame_count"], "counts_max": c["max_frame_count"],
                              "frames_below_min": c["frames_below_min"],
                              "height_span_m": c["height_span_m"], "local_rms_m": c["local_rms_m"],
                              "local_normal_z": c["local_normal_z"], "center_z": c["center"][2]})

    result = {
        "sid": SID, "pitch_deg": PITCH_DEG, "roll_deg": ROLL_DEG,
        "fit_frame_count": len(fit_ordinals), "total_points": meta["total_points"],
        "points_used": int(len(work)), "points_out_of_bound": int(len(inside) - int(inside.sum())),
        "planes": planes, "cells_total": len(cells),
        "cell_reason_counts": dict(reason_counts), "cell_first_reason": dict(first_reason),
        "cell_reason_combos": dict(combo), "single_reason_cells": dict(single),
        "floor_band_cells": len(floor_band),
        "floor_band_first_reason": dict(floor_band_reasons),
        "clean_neighbors": sorted(neighbors, key=lambda n: (n["key"][0], n["key"][1])),
        "clean_cells": len(clean), "plane_matches": matches,
        "seconds": round(time.monotonic() - began, 3),
    }
    (OUT / "03_diag.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["223757 floor diagnosis (read-only replication of floor_detector)",
             "fit frames %d / total points %d / used (|xyz|<=100) %d / out-of-bound dropped %d"
             % (len(fit_ordinals), meta["total_points"], len(work), result["points_out_of_bound"]),
             "occupied 25cm XY cells: %d; clean cells: %d" % (len(cells), len(clean)),
             "cell reject counts (any reason): %s" % dict(reason_counts),
             "cell first reason: %s" % dict(first_reason),
             "single-reason cells: %s" % dict(single),
             "reason combos: %s" % dict(combo),
             ""]
    for p in planes:
        lines.append("plane off=%.4f pitch=%.3f roll=%.3f discovery_voxels=%d"
                     % (p["offset_m"], p["pitch_deg"], p["roll_deg"], p["discovery_voxels"]))
    lines.append("")
    for m in matches:
        lines.append("plane off=%.4f matched=%d clean_gap_fail=%d would_qualify=%s"
                     % (m["offset_m"], m["clean_cells"], m["clean_gap_failures"], m["would_qualify"]))
        for g in m["components"]:
            lines.append("   component cells=%d span_m=%s qualify=%s"
                         % (g["cells"], g["span_m"], g["would_qualify"]))
        for c in m["matched_cells"]:
            lines.append("   cell key=%s count=%d min_frame=%d span=%.4f rms=%.4f nz=%.4f"
                         % (c["key"], c["count"], c["min_frame_count"], c["height_span_m"],
                            c["local_rms_m"], c["local_normal_z"]))
    lines.append("")
    lines.append("floor-band cells (center_z in [-1.5,-1.05]): %d first-reason %s"
                 % (len(floor_band), dict(floor_band_reasons)))
    for n in sorted(neighbors, key=lambda x: (x["key"][0], x["key"][1])):
        lines.append("   neighbor key=%s reasons=%s count=%d per-frame min/med/max=%d/%d/%d"
                     " below_min_frames=%d span=%.3f rms=%.4f nz=%.3f cz=%.3f"
                     % (n["key"], n["reasons"], n["count"], n["counts_min"], n["counts_med"],
                        n["counts_max"], n["frames_below_min"], n["height_span_m"],
                        n["local_rms_m"], n["local_normal_z"], n["center_z"]))
    lines.append("")
    lines.append("seconds %.3f" % result["seconds"])
    text = "\n".join(lines)
    (OUT / "02_diag.log").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
