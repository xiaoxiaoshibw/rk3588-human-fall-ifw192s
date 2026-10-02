#!/usr/bin/env python3
"""GL-00 read-only bag analyser (independent, no production imports).

Reads an existing rosbag read-only and reports, for /innolidar_points:
frame/layout/units sanity, zero/non-finite counts, spatial extent, and the
competing planes (iterative RANSAC) with support counts and orientations.
Writes nothing except stdout JSON + an optional downsample CSV given as argv.

usage: python3 gl00_readonly_analyze.py BAG OUT_JSON [DOWNSAMPLE_CSV]
No writes to the source tree, the bag, or any service.
"""
import hashlib
import json
import sys

import numpy as np
import rosbag

TOPIC = "/innolidar_points"
# x/y/z float32 at offsets 0/4/8, packed point_step=26 (observed).
DTYPE = np.dtype({"names": ["x", "y", "z"],
                  "formats": ["<f4", "<f4", "<f4"],
                  "offsets": [0, 4, 8], "itemsize": 26})
POOL_STRIDE = 20
RANSAC_ITERS = 400
RANSAC_THRESH_M = 0.05
MAX_PLANES = 6
SEED = 20261001


def plane_fit(points, rng):
    n = len(points)
    best = None
    best_count = -1
    for _ in range(RANSAC_ITERS):
        idx = rng.randint(0, n, 3)
        a, b, c = points[idx[0]], points[idx[1]], points[idx[2]]
        normal = np.cross(b - a, c - a)
        norm = float(np.linalg.norm(normal))
        if norm < 1e-9:
            continue
        normal = normal / norm
        offset = -float(normal @ a)
        count = int(np.count_nonzero(np.abs(points @ normal + offset) <= RANSAC_THRESH_M))
        if count > best_count:
            best_count, best = count, (normal, offset)
    if best is None:
        return None, 0
    normal, offset = best
    inliers = points[np.abs(points @ normal + offset) <= RANSAC_THRESH_M]
    centroid = inliers.mean(axis=0)
    _, _, vt = np.linalg.svd(inliers - centroid, full_matrices=False)
    normal = vt[-1]
    offset = -float(normal @ centroid)
    count = int(np.count_nonzero(np.abs(points @ normal + offset) <= RANSAC_THRESH_M))
    return (normal, offset), count


def describe(points, normal, offset, total):
    dist = np.abs(points @ normal + offset)
    inliers = points[dist <= RANSAC_THRESH_M]
    resid = dist[dist <= RANSAC_THRESH_M]
    tilt = float(np.arccos(np.clip(abs(normal[2]), -1.0, 1.0)))
    ranges = np.linalg.norm(inliers, axis=1)
    return {
        "normal": [float(v) for v in normal],
        "offset_m": float(offset),
        "tilt_from_z_rad": tilt,
        "horizontal_candidate": bool(abs(normal[2]) > 0.94),
        "support_count": int(len(inliers)),
        "support_fraction_of_pool": float(len(inliers) / total) if total else None,
        "residual_rms_m": float(np.sqrt(np.mean(resid ** 2))) if len(resid) else None,
        "aabb_min_m": [float(v) for v in inliers.min(axis=0)],
        "aabb_max_m": [float(v) for v in inliers.max(axis=0)],
        "range_min_m": float(ranges.min()), "range_max_m": float(ranges.max()),
        "range_median_m": float(np.median(ranges)),
    }


def main():
    bag_path = sys.argv[1]
    out_json = sys.argv[2]
    ds_csv = sys.argv[3] if len(sys.argv) > 3 else None

    result = {"bag": bag_path, "topic": TOPIC}
    frame_info = []
    pool = []
    ds = []

    with rosbag.Bag(bag_path, "r") as bag:
        for _, msg, _ in bag.read_messages(topics=[TOPIC]):
            arr = np.frombuffer(msg.data, dtype=DTYPE)
            xyz = np.column_stack((arr["x"], arr["y"], arr["z"]))
            finite = np.isfinite(xyz).all(axis=1)
            nonzero = finite & (np.abs(xyz).sum(axis=1) > 0.0)
            valid = xyz[nonzero]
            if not frame_info:
                result["fields"] = [[f.name, f.offset, f.datatype] for f in msg.fields]
                result["point_step"] = msg.point_step
                result["is_dense"] = bool(msg.is_dense)
                result["frame_id"] = msg.header.frame_id
                result["width"] = msg.width
                result["height"] = msg.height
            frame_info.append({
                "seq": msg.header.seq,
                "stamp": [int(msg.header.stamp.secs), int(msg.header.stamp.nsecs)],
                "point_count": int(len(xyz)),
                "finite_count": int(finite.sum()),
                "nonfinite_count": int((~finite).sum()),
                "zero_count": int((~nonzero).sum()) if len(xyz) else 0,
                "valid_count": int(len(valid)),
            })
            if len(valid):
                pool.append(valid[::POOL_STRIDE])
                if ds_csv is not None:
                    ds.append(valid[::POOL_STRIDE])

    result["frame_count"] = len(frame_info)
    result["first_frame"] = frame_info[0] if frame_info else None
    result["last_frame"] = frame_info[-1] if frame_info else None
    result["total_points"] = sum(f["point_count"] for f in frame_info)
    result["total_finite"] = sum(f["finite_count"] for f in frame_info)
    result["total_nonfinite"] = sum(f["nonfinite_count"] for f in frame_info)
    result["total_zero"] = sum(f["zero_count"] for f in frame_info)
    result["seqs_monotonic"] = all(
        frame_info[i]["seq"] <= frame_info[i + 1]["seq"] for i in range(len(frame_info) - 1))
    result["stamp_secs_monotonic"] = all(
        (frame_info[i]["stamp"][0], frame_info[i]["stamp"][1])
        <= (frame_info[i + 1]["stamp"][0], frame_info[i + 1]["stamp"][1])
        for i in range(len(frame_info) - 1))
    result["stamp_first_s"] = frame_info[0]["stamp"][0] + frame_info[0]["stamp"][1] * 1e-9 if frame_info else None
    result["stamp_last_s"] = frame_info[-1]["stamp"][0] + frame_info[-1]["stamp"][1] * 1e-9 if frame_info else None

    points = np.vstack(pool) if pool else np.zeros((0, 3))
    result["pool_count"] = int(len(points))
    if len(points):
        ranges = np.linalg.norm(points, axis=1)
        result["pool_aabb_min_m"] = [float(v) for v in points.min(axis=0)]
        result["pool_aabb_max_m"] = [float(v) for v in points.max(axis=0)]
        result["pool_range_m"] = {"min": float(ranges.min()), "p50": float(np.median(ranges)),
                                  "max": float(ranges.max())}
        result["pool_z_hist"] = np.histogram(points[:, 2], bins=12)[0].tolist()
        result["pool_z_hist_edges"] = [float(v) for v in np.histogram(points[:, 2], bins=12)[1]]

    rng = np.random.RandomState(SEED)
    remaining = points.copy()
    planes = []
    for _ in range(MAX_PLANES):
        if len(remaining) < 200:
            break
        model, count = plane_fit(remaining, rng)
        if model is None or count < 200:
            break
        normal, offset = model
        desc = describe(remaining, normal, offset, int(len(points)))
        planes.append(desc)
        keep = np.abs(remaining @ normal + offset) > RANSAC_THRESH_M
        remaining = remaining[keep]
    result["competing_planes"] = planes

    if ds_csv is not None and ds:
        csv = np.vstack(ds)
        np.savetxt(ds_csv, csv, delimiter=",", header="x,y,z", comments="", fmt="%.4f")
        result["downsample_csv"] = ds_csv
        result["downsample_count"] = int(len(csv))

    with open(out_json, "w") as handle:
        json.dump(result, handle, indent=1, sort_keys=True)
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
