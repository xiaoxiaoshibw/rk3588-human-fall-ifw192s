"""T4 前置：定位并描述 164522 里的唯一紧凑目标（源系或配平显示系）。

用法：
    python -B -W error inspect_target.py --out <evidence_dir> --sid cap_20261014_164522
    python -B -W error inspect_target.py --out <evidence_dir> --sid cap_20261014_164522 --job <job_id> --method tls
- 目标由「已知近似位置 + 最近簇」选定：本轮唯一紧凑目标，不做语义判定。
- 输出逐帧表（点数/中心/bbox/距离/强度）与证据 PNG（三视图，颜色=强度），JSON 落盘。
"""
import argparse
import json
from pathlib import Path

import numpy as np

from common import LEVELED, REMOTE, intensity_view, load_session

SEED_SENSOR = np.array([4.3, -0.55, 4.17])   # 工单给出的传感器系近似中心
SEED_RADIUS_M = 1.2
CLUSTER_CELL_M = 0.25
MIN_POINTS = 3


def clusters_local(points, cell_m, min_points):
    """Grid connected components (8-neighbour) on the three axes; returns index lists."""
    grid = np.floor(points / cell_m).astype(np.int64)
    buckets = {}
    for index, cell in enumerate(grid.tolist()):
        buckets.setdefault((cell[0], cell[1], cell[2]), []).append(index)
    seen, groups = set(), []
    for start in buckets:
        if start in seen:
            continue
        seen.add(start)
        stack, members = [start], []
        while stack:
            key = stack.pop()
            members.extend(buckets[key])
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        neighbour = (key[0] + dx, key[1] + dy, key[2] + dz)
                        if neighbour in buckets and neighbour not in seen:
                            seen.add(neighbour)
                            stack.append(neighbour)
        if len(members) >= min_points:
            groups.append(np.array(sorted(members), dtype=np.int64))
    return groups


def pick_target(points, seed):
    candidates = []
    for members in clusters_local(points, CLUSTER_CELL_M, MIN_POINTS):
        group = points[members]
        center = np.median(group, axis=0)
        candidates.append((float(np.linalg.norm(center - seed)), center, members, group))
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])


def describe(session_meta, points, intensity, frame_index, seed):
    picked = pick_target(points, seed)
    if picked is None:
        return {"frame": frame_index, "seq": session_meta["frames"][frame_index]["seq"],
                "hit": False, "clusters_picked": None}
    distance, center, members, group = picked
    values = intensity[members]
    return {
        "frame": frame_index,
        "seq": session_meta["frames"][frame_index]["seq"],
        "stamp_sec": session_meta["frames"][frame_index]["stamp_sec"],
        "stamp_nanosec": session_meta["frames"][frame_index]["stamp_nanosec"],
        "hit": True,
        "seed_distance_m": distance,
        "point_count": int(len(members)),
        "center": [float(v) for v in center],
        "bbox_min": np.min(group, axis=0).tolist(),
        "bbox_max": np.max(group, axis=0).tolist(),
        "extent_m": (np.max(group, axis=0) - np.min(group, axis=0)).tolist(),
        "range_median_m": float(np.median(np.linalg.norm(group, axis=1))),
        "intensity": {"min": float(values.min()), "median": float(np.median(values)),
                      "max": float(values.max())},
        "local_points": np.round(group, 4).tolist(),
        "local_intensity": [float(v) for v in values],
    }


def render(rows, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    all_points, all_values = [], []
    for row in rows:
        if row["hit"]:
            all_points.append(np.asarray(row["local_points"]))
            all_values.append(np.asarray(row["local_intensity"]))
    if not all_points:
        raise ValueError("no target points to render")
    points = np.concatenate(all_points)
    values = np.concatenate(all_values)
    figure, axes = plt.subplots(1, 3, figsize=(15, 5))
    pairs = [(0, 1, "x", "y"), (0, 2, "x", "z"), (1, 2, "y", "z")]
    for axis, (i, j, ni, nj) in zip(axes, pairs):
        scatter = axis.scatter(points[:, i], points[:, j], c=values, s=6, cmap="viridis")
        axis.set_xlabel(ni + " [m]"); axis.set_ylabel(nj + " [m]"); axis.set_aspect("equal")
        axis.grid(True, alpha=0.3)
        figure.colorbar(scatter, ax=axis, label="intensity")
    axes[0].set_title("target points, all frames (color=intensity)")
    figure.tight_layout()
    figure.savefig(out_png, dpi=110)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--sid", required=True)
    parser.add_argument("--job")
    parser.add_argument("--method", default="tls")
    parser.add_argument("--seed", default="4.3,-0.55,4.17")
    args = parser.parse_args()
    out = Path(args.out)
    seed = np.array([float(v) for v in args.seed.split(",")])
    if args.job:
        directory = LEVELED / args.job / args.method
        meta = json.loads((directory / "meta.json").read_text(encoding="utf8"))
        transform = json.loads((directory / "transform.json").read_text(encoding="utf8"))
        assert transform["source"]["meta_sha256"] == __import__("common").sha256_file(
            REMOTE / args.sid / "meta.json")
        # 目标近似位置随配平变换映射到显示系
        R = np.asarray(transform["R"], dtype=np.float64)
        t = np.asarray(transform["t"], dtype=np.float64)
        seed = R @ seed + t
    else:
        directory, meta = load_session(args.sid)
    points_view = np.ndarray((int(meta["total_points"]), 3), dtype="<f4",
                             buffer=np.memmap(directory / "points.bin", dtype="u1", mode="r"),
                             strides=(28, 4)).astype(np.float64)
    intensity = intensity_view(directory, meta).astype(np.float64)
    rows = []
    for index in range(len(meta["frames"])):
        frame = meta["frames"][index]
        lo = int(frame["offset_points"])
        hi = lo + int(frame["count_points"])
        segment = points_view[lo:hi]
        mask = np.all(np.isfinite(segment), axis=1) \
            & (np.linalg.norm(segment - seed, axis=1) <= SEED_RADIUS_M)
        rows.append(describe(meta, segment[mask], intensity[lo:hi][mask], index, seed))
    payload = {"sid": args.sid, "job_id": args.job, "method": args.method if args.job else "source",
               "seed": seed.tolist(), "seed_radius_m": SEED_RADIUS_M, "cluster_cell_m": CLUSTER_CELL_M,
               "min_points": MIN_POINTS, "frames": rows}
    with (out / "05_TARGET_IDENTITY.json").open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    render(rows, out / "05_TARGET_IDENTITY.png")
    hits = [row for row in rows if row["hit"]]
    print(json.dumps({"frames": len(rows), "hits": len(hits),
                      "points_per_hit": [row["point_count"] for row in hits],
                      "seed_distances": [round(row["seed_distance_m"], 3) for row in hits]}))


if __name__ == "__main__":
    main()
