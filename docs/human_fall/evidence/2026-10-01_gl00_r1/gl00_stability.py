#!/usr/bin/env python3
"""GL-00 frame-group stability check (read-only).

Splits the bag into consecutive frame groups, fits the dominant plane
independently in each, orients up, and reports normal/offset/tilt/support so
drift between time-separated groups can be compared. usage:
  python3 gl00_stability.py BAG GROUPS OUT_JSON
"""
import json
import sys

import numpy as np
import rosbag

TOPIC = "/innolidar_points"
DTYPE = np.dtype({"names": ["x", "y", "z"],
                  "formats": ["<f4", "<f4", "<f4"],
                  "offsets": [0, 4, 8], "itemsize": 26})
POOL_STRIDE = 10
RANSAC_ITERS = 500
THRESH_M = 0.05
SEED = 20261001


def fit(points, rng):
    best, best_count = None, -1
    n = len(points)
    for _ in range(RANSAC_ITERS):
        idx = rng.randint(0, n, 3)
        a, b, c = points[idx[0]], points[idx[1]], points[idx[2]]
        normal = np.cross(b - a, c - a)
        norm = float(np.linalg.norm(normal))
        if norm < 1e-9:
            continue
        normal = normal / norm
        offset = -float(normal @ a)
        count = int(np.count_nonzero(np.abs(points @ normal + offset) <= THRESH_M))
        if count > best_count:
            best_count, best = count, (normal, offset)
    normal, offset = best
    inliers = points[np.abs(points @ normal + offset) <= THRESH_M]
    centroid = inliers.mean(axis=0)
    _, _, vt = np.linalg.svd(inliers - centroid, full_matrices=False)
    normal = vt[-1]
    offset = -float(normal @ centroid)
    if normal[2] < 0.0:
        normal, offset = -normal, -offset
    return normal, offset


def main():
    bag_path, groups, out_json = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    per_group = [[] for _ in range(groups)]
    with rosbag.Bag(bag_path, "r") as bag:
        frame_index = 0
        for _, msg, _ in bag.read_messages(topics=[TOPIC]):
            arr = np.frombuffer(msg.data, dtype=DTYPE)
            xyz = np.column_stack((arr["x"], arr["y"], arr["z"]))
            finite = np.isfinite(xyz).all(axis=1)
            valid = xyz[finite & (np.abs(xyz).sum(axis=1) > 0.0)]
            group = min(frame_index * groups // max(1, 47), groups - 1)
            if len(valid):
                per_group[group].append(valid[::POOL_STRIDE])
            frame_index += 1
    results = []
    for g in range(groups):
        pts = np.vstack(per_group[g]) if per_group[g] else np.zeros((0, 3))
        if len(pts) < 500:
            results.append({"group": g, "count": int(len(pts)), "insufficient": True})
            continue
        normal, offset = fit(pts, np.random.RandomState(SEED + g))
        tilt = float(np.arccos(np.clip(normal[2], -1.0, 1.0)))
        support = int(np.count_nonzero(np.abs(pts @ normal + offset) <= THRESH_M))
        results.append({"group": g, "count": int(len(pts)),
                        "normal_up": [float(v) for v in normal],
                        "offset_m": float(offset), "tilt_rad": tilt,
                        "support_fraction": float(support / len(pts))})
    out = {"bag": bag_path, "groups": groups, "results": results}
    norms = [np.array(r["normal_up"]) for r in results if "normal_up" in r]
    if len(norms) >= 2:
        angles = []
        for i in range(len(norms)):
            for j in range(i + 1, len(norms)):
                angles.append(float(np.degrees(np.arccos(
                    np.clip(abs(float(norms[i] @ norms[j])), -1.0, 1.0)))))
        offsets = [r["offset_m"] for r in results if "offset_m" in r]
        out["max_pairwise_normal_angle_deg"] = max(angles)
        out["offset_spread_m"] = max(offsets) - min(offsets)
    with open(out_json, "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
