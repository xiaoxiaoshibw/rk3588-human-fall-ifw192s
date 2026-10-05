"""Read-only GL-I04 geometry observations; never a calibration producer.

Replay is an independently computed account of the frozen finite sequence,
not native fitter trace. Source XYZ and residual along an oriented model normal
are distinct quantities. A model is not proof of world up or ground identity.
"""
import math

import numpy as np

from . import ground as g
from .capture_input import select_group_region


def residual_stats(points, normal, offset, threshold=0.05):
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must be Nx3")
    normal = g._unit_vector(normal, "normal")
    offset = g._finite_number(offset, "offset")
    threshold = g._finite_number(threshold, "threshold")
    if threshold <= 0:
        raise ValueError("threshold must be positive")
    finite = np.all(np.isfinite(array), axis=1)
    usable = array[finite]
    result = {"count": int(len(array)), "finite_count": int(len(usable)),
              "nonfinite_count": int(len(array) - len(usable)),
              "zero_count": int(np.count_nonzero(np.all(usable == 0, axis=1))),
              "reason": None if len(usable) else "no_finite_selected_points",
              "rms_m": None, "p95_m": None, "signed_median_m": None,
              "signed_min_m": None, "signed_max_m": None,
              "support_count": 0, "support_fraction": None,
              "high_tail_count": 0, "low_tail_count": 0}
    if len(usable):
        signed = usable @ normal + offset
        result.update(rms_m=float(np.sqrt(np.mean(signed ** 2))),
                      p95_m=float(np.percentile(np.abs(signed), 95)),
                      signed_median_m=float(np.median(signed)),
                      signed_min_m=float(signed.min()), signed_max_m=float(signed.max()),
                      support_count=int(np.count_nonzero(np.abs(signed) <= threshold)),
                      support_fraction=float(np.mean(np.abs(signed) <= threshold)),
                      high_tail_count=int(np.count_nonzero(signed > threshold)),
                      low_tail_count=int(np.count_nonzero(signed < -threshold)))
    return result


def pca_plane(points, up):
    array = np.asarray(points, dtype=np.float64)
    up = g._unit_vector(up, "up")
    array = array[np.all(np.isfinite(array), axis=1)]
    if len(array) < 3:
        raise ValueError("reference FIT needs three finite points")
    center = array.mean(axis=0)
    values, vectors = np.linalg.eigh((array - center).T @ (array - center))
    if values[1] <= 0 or values[2] <= 0:
        raise ValueError("reference FIT is collinear or identical")
    normal = vectors[:, 0]
    if normal @ up < 0:
        normal = -normal
    return {"normal": normal.tolist(), "offset_m": -float(normal @ center),
            "eigenvalue_ratio": float(values[1] / values[2]),
            "origin": "posthoc_PCA_all_approved_FIT_rows_not_physical"}


def rotation_conditions(angle_deg=90.0):
    angle = math.radians(g._finite_number(angle_deg, "angle_deg"))
    c, s = math.cos(angle), math.sin(angle)
    rotation = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    z = np.array([0., 0., 1.])
    return {"status": "conditional_not_measured",
            "convention": "right-handed column vectors; active +Ry source->world",
            "from": "source", "to": "world", "R_source_to_world": rotation.tolist(),
            "angle_deg": angle_deg, "R_times_source_z_in_world": (rotation @ z).tolist(),
            "world_up_expressed_in_source_R_transpose": (rotation.T @ z).tolist(),
            "passive": "coordinate change world->source is inverse R = R.T",
            "condition": "only if this R is the actual source-to-world rotation",
            "recording_extrinsic": "unknown; frame string does not identify extrinsic"}


def replay_sequence(points, fit_rows, up, height, settings):
    """Yield every draw including rejections, with frozen sampling/RNG order."""
    settings = g.resolve_constrained_settings(settings)
    up = g._unit_vector(up, "up")
    low, high = g._height_interval(height)
    array = np.asarray(points, dtype=np.float64)
    rows = g._normalise_indices(fit_rows, "fit_rows", len(array))
    valid = np.all(np.isfinite(array[rows]), axis=1)
    valid &= np.linalg.norm(np.where(np.isfinite(array[rows]), array[rows], 0), axis=1) > 0
    rows = np.unique(rows[valid])
    rng = np.random.RandomState(settings["seed"] % (2 ** 32))
    u, v = g._tangent_basis(up)
    sampled = (g._balanced_sample(array, rows, up, u, v, settings["spatial_cell_m"],
                                  settings["max_points_per_cell"], settings["fit_point_cap"], rng)
               if len(rows) >= settings["min_inliers"] else np.empty(0, dtype=np.int64))

    def generate():
        if len(rows) < settings["min_inliers"] or len(sampled) < settings["min_inliers"]:
            return
        cloud = array[sampled]
        for ordinal in range(settings["ransac_iterations"]):
            draw = rng.choice(len(cloud), size=3, replace=False)
            p0, p1, p2 = cloud[draw]
            event = {"iteration": ordinal, "draw_rows": sampled[draw].tolist(), "stage": None}
            cross = np.cross(p1 - p0, p2 - p0)
            length = float(np.linalg.norm(cross))
            if min(np.linalg.norm(p1 - p0), np.linalg.norm(p2 - p0),
                   np.linalg.norm(p2 - p1)) < settings["min_sample_separation_m"]:
                event["stage"] = "sample_separation"
            elif length <= 0 or length / 2 < settings["min_sample_triangle_area_m2"]:
                event["stage"] = "sample_area"
            else:
                normal = cross / length
                if normal @ up < 0:
                    normal = -normal
                offset = -float(normal @ p0)
                event.update(normal=normal.tolist(), offset_m=offset)
                if math.acos(float(np.clip(normal @ up, -1, 1))) > settings["max_angle_rad"]:
                    event["stage"] = "angle"
                elif not low <= offset <= high:
                    event["stage"] = "height"
                else:
                    count = int(np.count_nonzero(np.abs(cloud @ normal + offset)
                                                 <= settings["inlier_threshold_m"]))
                    event["support_count"] = count
                    event["stage"] = "qualified" if count >= max(
                        settings["min_inliers"], settings["min_fit_inlier_fraction"] * len(cloud)) else "support"
            yield event
    return sampled, rows, generate()


def refine_hypothesis(points, sampled, fit_rows, hypothesis, up, height, settings):
    """Frozen refinement gates, independently replayed, not a physical check."""
    array = np.asarray(points, dtype=np.float64)
    cloud = array[sampled]
    normal = np.asarray(hypothesis["normal"])
    inside = cloud[np.abs(cloud @ normal + hypothesis["offset_m"])
                   <= settings["inlier_threshold_m"]]
    if len(inside) < max(settings["min_inliers"],
                         math.ceil(settings["min_fit_inlier_fraction"] * len(cloud))):
        return None, "refine_support"
    center = inside.mean(axis=0)
    values, vectors = np.linalg.eigh((inside - center).T @ (inside - center))
    ratio = float(values[1] / values[2]) if values[2] > 0 else 0.0
    if ratio < settings["min_planar_eigenvalue_ratio"]:
        return None, "refine_degenerate"
    normal = vectors[:, 0]
    if normal @ up < 0:
        normal = -normal
    offset = -float(normal @ center)
    if math.acos(float(np.clip(normal @ up, -1, 1))) > settings["max_angle_rad"]:
        return None, "refine_angle"
    if not height[0] <= offset <= height[1]:
        return None, "refine_height"
    count = int(np.count_nonzero(np.abs(array[fit_rows] @ normal + offset)
                                 <= settings["inlier_threshold_m"]))
    if count < max(settings["min_inliers"], math.ceil(
            settings["min_fit_inlier_fraction"] * len(fit_rows))):
        return None, "refine_full_support"
    return {"normal": normal.tolist(), "offset_m": offset,
            "support_count": count, "eigenvalue_ratio": ratio}, "refined"


def similar(first, second, settings):
    return (g._angle_deg(first["normal"], second["normal"]) <= settings["distinct_normal_deg"]
            and abs(first["offset_m"] - second["offset_m"]) <= settings["distinct_offset_m"])


def replay_frozen_search(points, fit_rows, up, height, settings):
    sampled, rows, sequence = replay_sequence(points, fit_rows, up, height, settings)
    counters, trace, candidates = {}, [], []
    truncated = False
    for event in sequence:
        trace.append(event)
        stage = event["stage"]
        counters[stage] = counters.get(stage, 0) + 1
        if stage != "qualified":
            continue
        item = {key: event[key] for key in ("normal", "offset_m", "support_count")}
        for old in candidates:
            if similar(old, item, settings):
                if item["support_count"] > old["support_count"]:
                    old.update(item)
                break
        else:
            candidates.append(item)
        if len(candidates) > 8:
            candidates.sort(key=lambda value: value["support_count"], reverse=True)
            del candidates[8:]
            truncated = True
    refined, refine_events = [], []
    for index, item in enumerate(candidates):
        result, reason = refine_hypothesis(points, sampled, rows, item, up, height, settings)
        refine_events.append({"raw_index": index, "reason": reason, "result": result})
        if result is not None:
            refined.append(result)
    refined.sort(key=lambda value: value["support_count"], reverse=True)
    deduped = []
    for item in refined:
        if not any(similar(item, old, settings) for old in deduped):
            deduped.append(item)
    if len(deduped) > 8:
        truncated = True
    summary = lambda item: {key: item[key] for key in ("normal", "offset_m", "support_count")}
    return {"origin": "independent_replay_not_native_trace", "sampled_rows": sampled.tolist(),
            "valid_fit_rows": rows.tolist(), "sampled_fit_count": len(sampled),
            "counters": counters, "draw_trace": trace, "raw_candidates": candidates,
            "refinement": refine_events, "competition_truncated": truncated,
            "competition_candidates": [summary(item) for item in deduped[:8]],
            "candidates": [summary(item) for item in deduped[:settings["max_candidates"]]]}


def observe_boxes(points, manifest, boxes, plane, display_budget=300, bin_size=0.25, threshold=0.05):
    """All fixed source boxes x all frames; sidecar contains all selected rows."""
    if isinstance(display_budget, bool) or not isinstance(display_budget, int) or display_budget < 0:
        raise ValueError("display_budget must be a nonnegative integer")
    if not math.isfinite(bin_size) or bin_size <= 0:
        raise ValueError("bin_size must be positive finite")
    normal, offset = plane["normal"], plane["offset_m"]
    records, sidecar = [], []
    for group_id, group in manifest["frame_groups"].items():
        for label, box in boxes:
            selector = dict(box, frame_group=group_id)
            rows = select_group_region(points, manifest, selector)
            cloud = np.asarray(points[rows], dtype=np.float64)
            stats = residual_stats(cloud, normal, offset, threshold)
            shown = rows[::max(1, int(math.ceil(len(rows) / display_budget)))] if display_budget else rows[:0]
            shown_set = set(shown.tolist())
            finite = np.all(np.isfinite(cloud), axis=1)
            bins = {}
            for row, xyz, valid in zip(rows.tolist(), cloud, finite):
                signed = float(xyz @ normal + offset) if valid else None
                sidecar.append({"box": label, "frame_group": group_id,
                                "pooled_row": row, "frame_ordinal": group["ordinal"],
                                "seq": group["seq"], "frame_row": row - group["rows"][0],
                                "source_xyz_m": xyz.tolist() if valid else None,
                                "signed_residual_m": signed, "displayed": row in shown_set,
                                "reason": None if valid else "nonfinite_source_point"})
                if valid:
                    cell = tuple(np.floor(xyz / bin_size).astype(np.int64).tolist())
                    bins.setdefault(cell, []).append(xyz)
            records.append({"box": label, "frame_group": group_id,
                            "frame_ordinal": group["ordinal"], "seq": group["seq"],
                            "stats": stats, "display_count": len(shown),
                            "display_rule": "source-row stride ceil(count/budget); per box/frame",
                            "display_rows": shown.tolist(),
                            "source_xyz_bins": [{"cell": list(cell), "stats": residual_stats(
                                np.asarray(values), normal, offset, threshold)} for cell, values in sorted(bins.items())]})
    temporal = {}
    for label, _ in boxes:
        medians = [record["stats"]["signed_median_m"] for record in records
                   if record["box"] == label and record["stats"]["signed_median_m"] is not None]
        temporal[label] = {"frames": len(manifest["frame_groups"]),
                           "nonempty_frames": len(medians),
                           "signed_median_std_m": float(np.std(medians)) if medians else None}
    return records, sidecar, temporal
