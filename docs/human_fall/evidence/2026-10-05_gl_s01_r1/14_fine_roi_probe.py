"""Read-only probe: can finer ROI granularity make 223757 usable?

Idea (v3): keep every purity gate and the 0.5 m spread gate, but select 10-15cm
ROI boxes inside the A-layer sheet instead of whole 25cm cells. If clean small
boxes exist with enough spread, fragmented floors become usable without
lowering any B-layer threshold.
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "pc_apps" / "human_replay"))

from floor_detector import PROFILE  # noqa: E402
from leveling_estimators import ESTIMATORS  # noqa: E402
from leveling_quality import rotation  # noqa: E402

SID = "cap_20261002_223757"
OUT = Path(__file__).resolve().parent
ROI_MIN_SEP_M = .5
CONDITION_MIN = .1


def load_fit():
    directory = ROOT / "captures" / "remote" / SID
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    xyz = np.ndarray((meta["total_points"], 3), dtype="<f4", buffer=raw, strides=(28, 4))
    frames = meta["frames"]
    nframes = len(frames)
    excluded = {(nframes - 1) // 3, 2 * (nframes - 1) // 3, nframes - 1}
    chunks, ids = [], []
    for ordinal, frame in enumerate(frames):
        if ordinal in excluded:
            continue
        lo, count = frame["offset_points"], frame["count_points"]
        segment = xyz[lo:lo + count].astype("f8")
        valid = np.isfinite(segment).all(axis=1) & np.any(segment != 0, axis=1)
        chunks.append(segment[valid])
        ids.append(np.full(int(valid.sum()), ordinal, dtype="i4"))
    return np.concatenate(chunks), np.concatenate(ids)


def discover_plane(work, anchor):
    voxel = np.floor(work / PROFILE["voxel_m"]).astype("i4")
    _, inverse = np.unique(voxel, axis=0, return_inverse=True)
    count = np.bincount(inverse)
    remaining = np.column_stack(
        [np.bincount(inverse, weights=work[:, i]) / count for i in range(3)])
    planes = []
    for _ in range(PROFILE["max_discovery_planes"]):
        if len(remaining) < 80:
            break
        normal, offset = ESTIMATORS["ransac"](remaining)
        if normal @ anchor < 0:
            normal, offset = -normal, -offset
        inliers = np.abs(remaining @ normal + offset) <= PROFILE["discovery_band_m"]
        if (normal @ anchor >= PROFILE["normal_alignment_min"]
                and PROFILE["offset_range_m"][0] <= offset <= PROFILE["offset_range_m"][1]):
            planes.append({"normal": normal, "offset_m": float(offset)})
        if not inliers.any():
            break
        remaining = remaining[~inliers]
    return max(planes, key=lambda p: p["offset_m"])


def clean_boxes(work, frame_ids, initial, plane, grid_m, min_pts_per_frame):
    normal, offset = plane["normal"], plane["offset_m"]
    nd = initial @ normal
    display = work @ initial.T
    keys = np.floor(display[:, :2] / grid_m).astype("i4")
    unique, inverse = np.unique(keys, axis=0, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    splits = np.r_[0, np.cumsum(np.bincount(inverse))]
    frame_uniques = np.unique(frame_ids)
    frame_index = np.searchsorted(frame_uniques, frame_ids)
    clean = []
    for i, key in enumerate(unique):
        index = order[splits[i]:splits[i + 1]]
        counts = np.bincount(frame_index[index], minlength=len(frame_uniques))
        if counts.min() < min_pts_per_frame or len(index) < 2:
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
        clean.append({"key": [int(key[0]), int(key[1])], "grid_m": grid_m,
                      "center_m": [float(center[0]), float(center[1])],
                      "count": int(len(index)), "min_frame_count": int(counts.min()),
                      "height_span_m": span, "rms_m": rms,
                      "normal_z": float(abs(local_normal[2]))})
    return clean


def select_four(boxes):
    n = len(boxes)
    if n < 4:
        return None
    centers = np.array([b["center_m"] for b in boxes])

    def worst(combo):
        pts = centers[list(combo)]
        return min(float(np.hypot(*(pts[a] - pts[b])))
                   for a in range(4) for b in range(a + 1, 4))

    if n <= 24:
        import itertools
        best, best_sep = None, -1.
        for combo in itertools.combinations(range(n), 4):
            sep = worst(combo)
            if sep > best_sep:
                best_sep, best = sep, combo
    else:
        chosen = [int(np.argmax(np.linalg.norm(centers - centers.mean(axis=0), axis=1)))]
        while len(chosen) < 4:
            dist = np.min(np.linalg.norm(centers[:, None] - centers[chosen][None], axis=2), axis=1)
            chosen.append(int(np.argmax(dist)))
        best, best_sep = tuple(chosen), worst(chosen)
    sel = centers[list(best)]
    dist = np.hypot(sel[:, None, 0] - sel[None, :, 0], sel[:, None, 1] - sel[None, :, 1])
    np.fill_diagonal(dist, np.inf)
    independent = int(np.all(dist >= ROI_MIN_SEP_M, axis=1).sum())
    singular = np.linalg.svd(sel - sel.mean(axis=0), compute_uv=False)
    condition = float(max(0., singular[-1] / max(singular[0], 1e-30)))
    return {"selected": [boxes[i] for i in best], "min_sep_m": best_sep,
            "independent_count": independent, "condition": condition,
            "pass": bool(best_sep >= ROI_MIN_SEP_M and independent == 4
                         and condition >= CONDITION_MIN)}


def main():
    began = time.monotonic()
    work, frame_ids = load_fit()
    initial = rotation(26., 0.)
    plane = discover_plane(work, initial[2])
    results = {"sid": SID, "plane_offset_m": plane["offset_m"], "sizes": []}
    for grid_m, min_pts in ((.20, 20), (.15, 10), (.10, 5)):
        clean = clean_boxes(work, frame_ids, initial, plane, grid_m, min_pts)
        pick = select_four(clean)
        entry = {"grid_m": grid_m, "min_pts_per_frame": min_pts,
                 "clean_boxes": len(clean),
                 "clean_bbox_m": ([min(b["center_m"][0] for b in clean), max(b["center_m"][0] for b in clean),
                                   min(b["center_m"][1] for b in clean), max(b["center_m"][1] for b in clean)]
                                  if clean else None),
                 "selection": pick}
        results["sizes"].append(entry)
        print("grid=%.2f clean=%d bbox=%s pick_min_sep=%s indep=%s cond=%s pass=%s"
              % (grid_m, len(clean), entry["clean_bbox_m"],
                 None if not pick else round(pick["min_sep_m"], 3),
                 None if not pick else pick["independent_count"],
                 None if not pick else round(pick["condition"], 3),
                 None if not pick else pick["pass"]), flush=True)
    results["seconds"] = round(time.monotonic() - began, 2)
    (OUT / "16_fine_roi_probe.json").write_text(json.dumps(results, ensure_ascii=False, indent=1),
                                                encoding="utf-8")


if __name__ == "__main__":
    main()
