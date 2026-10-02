#!/usr/bin/env python3
"""GL-00 provisional ground ROI + fit/validation zones (read-only).

Fits the dominant plane with the same bounded RANSAC as
gl00_readonly_analyze.py, orients its normal upward, builds the ground-local
tangent basis, and partitions a forward channel into a fitting zone and a
spatially disjoint validation zone. Emits physical (ground-local) bounds, the
source-frame plane used, per-zone height statistics, and a bounded CSV of ROI
points carrying their original (frame seq, in-frame point index).

This is exploratory evidence for the historical bring-up bag only; it does NOT
confirm that the scene matches the operator's screenshots and does not create a
verified calibration. usage:
  python3 gl00_roi_zones.py BAG OUT_JSON OUT_ROI_CSV
"""
import json
import sys

import numpy as np
import rosbag

TOPIC = "/innolidar_points"
DTYPE = np.dtype({"names": ["x", "y", "z"],
                  "formats": ["<f4", "<f4", "<f4"],
                  "offsets": [0, 4, 8], "itemsize": 26})
POOL_STRIDE = 20
RANSAC_ITERS = 400
THRESH_M = 0.05
SEED = 20261001
ROI_MAX_EXPORT = 6000


def ransac_plane(points, rng):
    best = None
    best_count = -1
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
    return normal, offset


def height_stats(points, normal, offset):
    if len(points) == 0:
        return {"count": 0}
    h = points @ normal + offset
    return {"count": int(len(h)),
            "min_m": float(h.min()), "p10_m": float(np.percentile(h, 10)),
            "median_m": float(np.median(h)), "p90_m": float(np.percentile(h, 90)),
            "max_m": float(h.max()),
            "rms_abs_m": float(np.sqrt(np.mean(h ** 2)))}


def main():
    bag_path, out_json, out_csv = sys.argv[1], sys.argv[2], sys.argv[3]
    pool = []
    frames = []
    with rosbag.Bag(bag_path, "r") as bag:
        for _, msg, _ in bag.read_messages(topics=[TOPIC]):
            arr = np.frombuffer(msg.data, dtype=DTYPE)
            xyz = np.column_stack((arr["x"], arr["y"], arr["z"]))
            frame = {"seq": int(msg.header.seq), "xyz": xyz}
            frames.append(frame)
            finite = np.isfinite(xyz).all(axis=1)
            valid = xyz[finite & (np.abs(xyz).sum(axis=1) > 0.0)]
            if len(valid):
                pool.append(valid[::POOL_STRIDE])
    points = np.vstack(pool)

    normal, offset = ransac_plane(points, np.random.RandomState(SEED))
    if normal[2] < 0.0:
        normal = -normal
        offset = -offset
    height = float(offset)
    tilt = float(np.arccos(np.clip(normal[2], -1.0, 1.0)))

    x_axis = np.array([1.0, 0.0, 0.0])
    u = x_axis - (x_axis @ normal) * normal
    u = u / np.linalg.norm(u)
    v = np.cross(normal, u)

    # ground-local coordinates for pooled points
    s = points @ u
    t = points @ v
    h = points @ normal + offset
    ground = np.abs(h) <= THRESH_M

    fits = {"forward_min_m": 1.5, "forward_max_m": 3.0,
            "lateral_abs_m": 1.0, "height_abs_m": THRESH_M}
    validation = {"forward_min_m": 3.0, "forward_max_m": 5.0,
                  "lateral_abs_m": 1.0, "height_abs_m": THRESH_M}

    def zone(spec):
        mask = ground & (s >= spec["forward_min_m"]) & (s <= spec["forward_max_m"]) \
            & (np.abs(t) <= spec["lateral_abs_m"])
        return points[mask], s[mask], t[mask]

    fit_pts, fit_s, fit_t = zone(fits)
    val_pts, val_s, val_t = zone(validation)

    result = {
        "bag": bag_path,
        "note": "provisional/unconfirmed scene; not a verified calibration",
        "plane_source_frame": {"normal_up": [float(x) for x in normal],
                               "offset_m": float(offset),
                               "sensor_height_m": height,
                               "tilt_from_source_z_rad": tilt},
        "ground_axes": {"u_source": [float(x) for x in u],
                        "v_source": [float(x) for x in v]},
        "fit_zone_spec_ground_local": fits,
        "validation_zone_spec_ground_local": validation,
        "fit_zone": {"point_count": int(len(fit_pts)),
                     "forward_p50_m": float(np.median(fit_s)) if len(fit_s) else None,
                     "height": height_stats(fit_pts, normal, offset)},
        "validation_zone": {"point_count": int(len(val_pts)),
                            "forward_p50_m": float(np.median(val_s)) if len(val_s) else None,
                            "height": height_stats(val_pts, normal, offset)},
        "ground_fraction_of_pool": float(ground.sum() / len(points)),
    }

    # export bounded ROI points with original frame/index for replay
    export = []
    with rosbag.Bag(bag_path, "r") as bag:
        for _, msg, _ in bag.read_messages(topics=[TOPIC]):
            arr = np.frombuffer(msg.data, dtype=DTYPE)
            xyz = np.column_stack((arr["x"], arr["y"], arr["z"]))
            ss = xyz @ u
            tt = xyz @ v
            hh = xyz @ normal + offset
            mask = (np.abs(hh) <= THRESH_M) & (ss >= fits["forward_min_m"]) & \
                (ss <= validation["forward_max_m"]) & (np.abs(tt) <= fits["lateral_abs_m"])
            idx = np.nonzero(mask)[0]
            for i in idx:
                if len(export) >= ROI_MAX_EXPORT:
                    break
                export.append((int(msg.header.seq), int(i),
                               float(xyz[i, 0]), float(xyz[i, 1]), float(xyz[i, 2])))
            if len(export) >= ROI_MAX_EXPORT:
                break
    with open(out_csv, "w") as handle:
        handle.write("frame_seq,point_index,x_m,y_m,z_m\n")
        for row in export:
            handle.write("%d,%d,%.4f,%.4f,%.4f\n" % row)
    result["roi_export_count"] = len(export)
    result["roi_export_capped"] = len(export) >= ROI_MAX_EXPORT

    with open(out_json, "w") as handle:
        json.dump(result, handle, indent=1, sort_keys=True)
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
