"""T3 补充：泄漏带分布（簇大小分布 / 空间分布 / 目标区泄漏）。

用法：
    python -B -W error background_probe.py --out <evidence_dir> --registration <dir>
在 04_BACKGROUND.json 的基础上补充：全部泄漏簇（>=2 点）的大小分布、高度/XY 分布、
以及 6.5 m 小目标邻域内的泄漏点数（目标是否被空场吃掉）。
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from background import (CELL_M, CLUSTER_CELL_M, MIN_CLUSTER_POINTS, apply_transform, background_keys,
                        collect_points, foreground_mask, load_points)
from inspect_target import clusters_local

TARGET_DISPLAY = np.array([5.75, -0.52, 3.0])   # 05_TARGET_IDENTITY.json 27 帧中心中位数附近


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--target-job", default="363473a9e2e64649994dca11b2b26929")
    parser.add_argument("--empty-job", default="61cb6976b0f8479394641850d9a7c6ca")
    args = parser.parse_args()
    out = Path(args.out)
    registration = json.loads((Path(args.registration) / "registration.json").read_text(encoding="utf8"))
    target_frames, _tmeta = load_points(args.target_job, "tls")
    empty_frames, _emeta = load_points(args.empty_job, "tls")
    empty_registered = apply_transform(empty_frames, registration["rotation_row_major"],
                                      registration["translation_m"])
    keys, origin, base = background_keys(collect_points(empty_registered), CELL_M)

    buckets = [(2, 4), (5, 9), (10, 49), (50, 199), (200, 10 ** 9)]
    cluster_hist = Counter()
    height_hist = Counter()
    xy_cells = Counter()
    target_rows = []
    for index, stamp, xyz, _values in target_frames:
        finite = np.isfinite(xyz).all(axis=1)
        points = xyz[finite]
        mask = foreground_mask(points, keys, origin, base, CELL_M)
        leaked = points[mask]
        if mask.any():
            for members in clusters_local(leaked, CLUSTER_CELL_M, 2):
                size = len(members)
                for low, high in buckets:
                    if low <= size <= high:
                        cluster_hist["%d-%d" % (low, high)] += 1
                        break
                center = np.median(leaked[members], axis=0)
                height_hist["%.1f" % (round(float(center[2]), 1))] += 1
                xy_cells[(int(center[0] * 2), int(center[1] * 2))] += 1
        near = leaked[np.linalg.norm(leaked - TARGET_DISPLAY, axis=1) <= 0.5]
        target_rows.append({"frame": index, "stamp_s": stamp, "leak_total": int(mask.sum()),
                            "leak_near_target_0p5m": int(len(near)),
                            "clusters_ge5": sum(1 for m in
                                                clusters_local(leaked, CLUSTER_CELL_M, MIN_CLUSTER_POINTS))})
    top_cells = [{"center_xy_m": [cell[0] / 2 + 0.25, cell[1] / 2 + 0.25], "frames": count}
                 for cell, count in xy_cells.most_common(10)]
    payload = {"cell_m": CELL_M, "cluster_min_points": 2,
               "cluster_size_histogram": dict(cluster_hist),
               "cluster_height_histogram_z_m": dict(height_hist),
               "top_leak_xy_cells": top_cells,
               "target_region": {"center_display_m": TARGET_DISPLAY.tolist(), "radius_m": 0.5,
                                 "per_frame": target_rows,
                                 "leak_near_target_median": float(np.median(
                                     [row["leak_near_target_0p5m"] for row in target_rows]))}}
    with (out / "04_BACKGROUND_DISTRIBUTION.json").open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"cluster_size_histogram": dict(cluster_hist),
                      "target_leak_median": payload["target_region"]["leak_near_target_median"],
                      "top_cells": top_cells[:3]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
