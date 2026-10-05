"""GL-I03 R1 phase-1 read-only diagnosis.

Reproduces the single approved real group-fixed draft against the frozen
constrained fitter and decomposes exactly why the two-value variant sample
(0.05 / 8) returns ``ground_degenerate`` while the default sample (0.2 / 4)
returns ``ground_points_insufficient``.

Writes only 00_diag_probe.json next to itself; reads capture/NPZ read-only.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "src/human_fall_detection/scripts"),
                str(ROOT / "src/human_fall_detection")]

from core.capture_input import load_adapted, gate_selection
from core.ground import (CONSTRAINED_DEFAULT_SETTINGS, _balanced_sample,
                         _tangent_basis, fit_ground_plane_constrained,
                         resolve_constrained_settings)
from evaluate_gli02_candidate import _draft_region

OLD = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i02_r1"
draft = json.loads((OLD / "codex_review_01/work/filled_real_draft.json")
                   .read_text(encoding="utf-8"))
manifest, points = load_adapted(str(OLD / "08_real/real_candidate.adapted.npz"))
fit = _draft_region(draft["fit_region"], "fit")
validation = []
for region in draft["validation_regions"]:
    item = _draft_region(region, "validation")
    item["region_id"] = region["region_id"]
    validation.append(item)
fit_rows, regions = gate_selection(points, manifest, fit, None,
                                   fit["frame_group"], validation)

report = {
    "fit_index_count": int(len(fit_rows)),
    "fit_frame_group": fit["frame_group"],
    "validation_counts": [len(r["indices"]) for r in regions],
    "up_axis": draft["up_axis"],
    "height_interval": draft["sensor_height_interval_m"],
    "sweep": {},
    "variant_decomposition": None,
}


def run(label, settings):
    resolved = resolve_constrained_settings(settings)
    result = fit_ground_plane_constrained(
        points, settings=resolved, frame="innolidar", up_axis=draft["up_axis"],
        sensor_height_interval_m=draft["sensor_height_interval_m"],
        fit_indices=fit_rows, fit_frame_group=fit["frame_group"],
        validation_regions=regions)
    report["sweep"][label] = {
        "spatial_cell_m": resolved["spatial_cell_m"],
        "max_points_per_cell": resolved["max_points_per_cell"],
        "status": result["status"], "reason": result["reason"],
        "sampled_fit_count": result["sampled_fit_count"],
        "degenerate_samples": result["degenerate_samples"],
        "raw_candidate_count": len(result["raw_candidates"]),
        "candidate_count": len(result["candidates"]),
        "evaluated_count": result.get("evaluated"),
    }
    return result


run("default", None)
run("variant_005_8", {"spatial_cell_m": 0.05, "max_points_per_cell": 8})
run("mid_010_8", {"spatial_cell_m": 0.10, "max_points_per_cell": 8})
run("mid_005_4", {"spatial_cell_m": 0.05, "max_points_per_cell": 4})
run("coarse_020_8", {"spatial_cell_m": 0.20, "max_points_per_cell": 8})

# Fit-ROI dominant plane: if even the best SVD plane misses the up-axis angle
# or the height interval, no RANSAC triple can produce a candidate.
roi = np.asarray(points, dtype=np.float64)[fit_rows]
centroid = roi.mean(axis=0)
_, _, vt = np.linalg.svd(roi - centroid, full_matrices=False)
up = np.asarray(draft["up_axis"], dtype=np.float64)
up = up / np.linalg.norm(up)
normal = vt[-1]
if float(normal @ up) < 0.0:
    normal = -normal
offset = -float(normal @ centroid)
eigs = np.linalg.svd(roi - centroid, compute_uv=False) ** 2
report["fit_roi_dominant_plane"] = {
    "point_count": int(len(roi)),
    "svd_normal": [float(v) for v in normal],
    "angle_to_up_deg": math.degrees(math.acos(max(-1.0, min(1.0,
                                                             float(normal @ up))))),
    "max_angle_deg": math.degrees(CONSTRAINED_DEFAULT_SETTINGS["max_angle_rad"]),
    "offset_m": offset,
    "height_interval": list(map(float, draft["sensor_height_interval_m"])),
    "eigenvalue_ratio_smallest_to_largest": float(eigs[1] / eigs[0]),
    "aabb_min": [float(v) for v in roi.min(axis=0)],
    "aabb_max": [float(v) for v in roi.max(axis=0)],
}

# Exact variant decomposition: replay the same RNG draw order and count how many
# triples are degenerate, rejected by the up-axis angle or height gate, or
# evaluated (candidate-worthy).
resolved = resolve_constrained_settings({"spatial_cell_m": 0.05,
                                         "max_points_per_cell": 8})
finite = np.all(np.isfinite(np.asarray(points, dtype=np.float64)), axis=1)
norms = np.linalg.norm(np.asarray(points, dtype=np.float64), axis=1)
valid_index = np.nonzero(finite & (norms > 0.0))[0]
fit_index = np.intersect1d(fit_rows, valid_index)
rng = np.random.RandomState(int(resolved["seed"]) % (2 ** 32))
tu, tv = _tangent_basis(up)
sampled = _balanced_sample(np.asarray(points, dtype=np.float64), fit_index, up,
                           tu, tv, resolved["spatial_cell_m"],
                           resolved["max_points_per_cell"],
                           resolved["fit_point_cap"], rng)
fit_points = np.asarray(points, dtype=np.float64)[sampled]
threshold = resolved["inlier_threshold_m"]
min_inliers = resolved["min_inliers"]
min_fraction = resolved["min_fit_inlier_fraction"]
n_fit = len(fit_points)
degenerate = evaluated = angle_reject = height_reject = 0
candidates = []
for _ in range(int(min(resolved["ransac_iterations"],
                       resolved["ransac_iteration_hard_cap"]))):
    draw = rng.choice(n_fit, size=3, replace=False)
    p0, p1, p2 = fit_points[draw]
    if min(float(np.linalg.norm(p1 - p0)), float(np.linalg.norm(p2 - p0)),
           float(np.linalg.norm(p2 - p1))) < resolved["min_sample_separation_m"]:
        degenerate += 1
        continue
    cross = np.cross(p1 - p0, p2 - p0)
    length = float(np.linalg.norm(cross))
    if length <= 0.0 or length / 2.0 < resolved["min_sample_triangle_area_m2"]:
        degenerate += 1
        continue
    normal = cross / length
    if float(normal @ up) < 0.0:
        normal = -normal
    if math.acos(max(-1.0, min(1.0, float(normal @ up)))) > resolved["max_angle_rad"]:
        angle_reject += 1
        continue
    offset = -float(normal @ p0)
    height_lo, height_hi = (float(v) for v in draft["sensor_height_interval_m"])
    if not height_lo <= offset <= height_hi:
        height_reject += 1
        continue
    evaluated += 1
    count = int(np.count_nonzero(np.abs(fit_points @ normal + offset) <= threshold))
    if count < min_inliers or count < min_fraction * n_fit:
        continue
    for candidate in candidates:
        if math.degrees(math.acos(max(-1.0, min(1.0, float(candidate["normal"] @ normal))))) \
                <= resolved["distinct_normal_deg"] \
                and abs(candidate["offset_m"] - offset) <= resolved["distinct_offset_m"]:
            if count > candidate["support_count"]:
                candidate.update({"normal": normal, "offset_m": offset,
                                  "support_count": count})
            break
    else:
        candidates.append({"normal": normal, "offset_m": offset,
                           "support_count": count})
report["variant_decomposition"] = {
    "sampled_fit_count": int(len(sampled)),
    "iterations": int(min(resolved["ransac_iterations"],
                          resolved["ransac_iteration_hard_cap"])),
    "degenerate": degenerate,
    "angle_reject": angle_reject,
    "height_reject": height_reject,
    "evaluated": evaluated,
    "raw_candidates": len(candidates),
    "height_interval_used": [float(v) for v in
                             draft["sensor_height_interval_m"]],
}

# Invalid records still validate; confirm the wrapper's refusal path.
from core.ground import validate_constrained_ground
default_result = fit_ground_plane_constrained(
    points, settings=resolve_constrained_settings(None), frame="innolidar",
    up_axis=draft["up_axis"],
    sensor_height_interval_m=draft["sensor_height_interval_m"],
    fit_indices=fit_rows, fit_frame_group=fit["frame_group"],
    validation_regions=regions)
validate_constrained_ground(default_result, expected_frame="innolidar")
report["default_invalid_record_validates"] = True

with (OUT / "00_diag_probe.json").open("x", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, allow_nan=False)
print(json.dumps({k: v for k, v in report.items()
                  if k not in ("sweep", "fit_roi_dominant_plane",
                               "variant_decomposition")}))
print(json.dumps(report["fit_roi_dominant_plane"]))
print(json.dumps(report["variant_decomposition"]))
