"""T3 去背景：空场配准 + 泄漏带定量。

用法：
    python -B -W error background.py --out <evidence_dir> --registration <dir with registration.json>

泄漏定义（距离判据，避免体素网格相位假象）：
    目标帧的点若在冻结空场的 cell_m 网格 ±1 格（切比雪夫 ≤ cell_m）内不存在空场点，
    即判定为泄漏（前景）。空场取 131958（10-13），经既有 registration.js PASS 变换
    （fit p50 9.1mm / p90 31.6mm，diagnostics.json）进入 164522 显示系。
对照：131958 不套用配准变换；175227（10-10，既有 registration 管线拒绝）不套用变换。
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from inspect_target import clusters_local
from plane_track import load_leveled_frames

CELL_M = 0.05                 # 泄漏判据网格
CLUSTER_CELL_M = 0.25
MIN_CLUSTER_POINTS = 5


def load_points(job_id, method):
    frames, _transform, meta = load_leveled_frames(job_id, method, "")
    return frames, meta


def apply_transform(frames, R, t):
    R = np.asarray(R, dtype=np.float64).reshape(3, 3)
    t = np.asarray(t, dtype=np.float64)
    return [(index, stamp, xyz @ R.T + t, values) for index, stamp, xyz, values in frames]


def collect_points(frames, stride=1):
    chunks = []
    for _index, _stamp, xyz, _values in frames:
        finite = np.isfinite(xyz).all(axis=1)
        if finite.any():
            chunks.append(xyz[finite][::stride])
    return np.concatenate(chunks) if chunks else np.zeros((0, 3))


def background_keys(points, cell_m=CELL_M):
    """Packed int64 keys of the frozen empty scene (one lookup structure)."""
    origin = np.floor(points.min(axis=0) / cell_m).astype(np.int64)
    cells = np.floor(points / cell_m).astype(np.int64) - origin
    span = cells.max(axis=0) + 2
    base = int(span.max()) + 2
    keys = (cells[:, 0] * base + cells[:, 1]) * base + cells[:, 2]
    keys.sort()
    return keys, origin, base


def foreground_mask(points, keys, origin, base, cell_m=CELL_M, ring=1):
    """True where no empty-scene cell exists within ±ring cells along each axis."""
    cells = np.floor(points / cell_m).astype(np.int64) - origin
    hit = np.zeros(len(points), dtype=bool)
    for dx in range(-ring, ring + 1):
        for dy in range(-ring, ring + 1):
            for dz in range(-ring, ring + 1):
                if hit.all():
                    break
                shifted = (cells[:, 0] + dx) * (base * base) + (cells[:, 1] + dy) * base + (cells[:, 2] + dz)
                index = np.searchsorted(keys, shifted)
                index = np.minimum(index, len(keys) - 1)
                hit |= keys[index] == shifted
    return ~hit


def leak_clusters(points, mask):
    if not mask.any():
        return []
    groups = clusters_local(points[mask], CLUSTER_CELL_M, MIN_CLUSTER_POINTS)
    rows = []
    for members in groups:
        group = points[mask][members]
        rows.append({"point_count": int(len(members)),
                     "center": np.median(group, axis=0).round(4).tolist(),
                     "bbox_size_m": np.round(group.max(axis=0) - group.min(axis=0), 4).tolist()})
    rows.sort(key=lambda row: -row["point_count"])
    return rows


def leak_report(target_frames, empty_points, tag, cell_m=CELL_M):
    keys, origin, base = background_keys(empty_points, cell_m)
    per_frame, persistent = [], Counter()
    for index, stamp, xyz, _values in target_frames:
        finite = np.isfinite(xyz).all(axis=1)
        points = xyz[finite]
        mask = foreground_mask(points, keys, origin, base, cell_m)
        cells = np.floor(points[mask] / CLUSTER_CELL_M).astype(np.int64)
        persistent.update(map(tuple, cells.tolist()))
        groups = leak_clusters(points, mask)
        per_frame.append({
            "frame": index, "stamp_s": stamp,
            "points": int(len(points)), "leak_points": int(mask.sum()),
            "leak_fraction": float(mask.mean()) if len(points) else None,
            "clusters_ge5": len(groups),
            "largest_cluster_points": groups[0]["point_count"] if groups else 0,
            "largest_cluster_center": groups[0]["center"] if groups else None,
            "largest_cluster_bbox_m": groups[0]["bbox_size_m"] if groups else None,
        })
    counts = [row["leak_points"] for row in per_frame]
    frames_n = len(per_frame)
    return {
        "tag": tag, "cell_m": cell_m,
        "empty_cells": int(len(keys)),
        "leak_points_median": float(np.median(counts)),
        "leak_points_p10_p90": [float(np.percentile(counts, 10)), float(np.percentile(counts, 90))],
        "leak_fraction_median": float(np.median([row["leak_fraction"] for row in per_frame])),
        "largest_cluster_median": float(np.median([row["largest_cluster_points"] for row in per_frame])),
        "largest_cluster_max": int(max(row["largest_cluster_points"] for row in per_frame)),
        "persistent_cells_ge80pct_frames": int(sum(1 for count in persistent.values()
                                                   if count >= frames_n * 0.8)),
        "frames": per_frame,
    }


def render(target_frame, leak_points, path, title, cell_m=CELL_M):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _index, _stamp, xyz, _values = target_frame
    finite = np.isfinite(xyz).all(axis=1)
    room = xyz[finite]
    room = room[(room[:, 0] > -1) & (room[:, 0] < 10) & (np.abs(room[:, 1]) < 5)
                & (room[:, 2] > -0.2) & (room[:, 2] < 3.6)]
    figure, axes = plt.subplots(1, 2, figsize=(16, 6))
    axes[0].scatter(room[::2, 0], room[::2, 1], s=1, c="lightgray", label="room (1/2)")
    axes[0].scatter(leak_points[:, 0], leak_points[:, 1], s=6, c="crimson",
                    label="leak (frame %d, %d pts)" % (target_frame[0], len(leak_points)))
    axes[0].set_xlabel("x display [m]"); axes[0].set_ylabel("y display [m]")
    axes[0].set_title(title + " top view"); axes[0].set_aspect("equal")
    axes[0].grid(alpha=0.3); axes[0].legend(loc="upper right")
    axes[1].scatter(room[::2, 0], room[::2, 2], s=1, c="lightgray")
    axes[1].scatter(leak_points[:, 0], leak_points[:, 2], s=6, c="crimson")
    axes[1].set_xlabel("x display [m]"); axes[1].set_ylabel("z display [m]")
    axes[1].set_title(title + " side view"); axes[1].grid(alpha=0.3)
    figure.tight_layout(); figure.savefig(path, dpi=110); plt.close(figure)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--target-job", default="363473a9e2e64649994dca11b2b26929")
    parser.add_argument("--empty-job", default="61cb6976b0f8479394641850d9a7c6ca")
    parser.add_argument("--older-empty-job", default="6d5809d5a87b462cad4023520868b9e6")
    parser.add_argument("--target-sid", default="cap_20261014_164522")
    parser.add_argument("--empty-sid", default="cap_20261013_131958")
    parser.add_argument("--older-empty-sid", default="cap_20261010_175227")
    args = parser.parse_args()
    out = Path(args.out)
    registration = json.loads((Path(args.registration) / "registration.json").read_text(encoding="utf8"))
    assert registration["quality"]["status"] == "PASS", "registration not PASS"
    assert registration["source_session"] == args.empty_sid
    assert registration["reference_session"] == args.target_sid

    target_frames, _tmeta = load_points(args.target_job, "tls")
    empty_frames, _emeta = load_points(args.empty_job, "tls")
    empty_registered = apply_transform(empty_frames, registration["rotation_row_major"],
                                      registration["translation_m"])
    older_frames, _ometa = load_points(args.older_empty_job, "tls")

    empty_points = collect_points(empty_frames)
    empty_registered_points = collect_points(empty_registered)
    older_points = collect_points(older_frames, stride=4)      # 14.9M -> 3.7M, bounded runtime

    reports = {
        "registered_131958_to_164522": leak_report(target_frames, empty_registered_points, "registered"),
        "unregistered_131958": leak_report(target_frames, empty_points, "unregistered"),
        "unregistered_175227": leak_report(target_frames, older_points, "unregistered_older"),
    }
    payload = {
        "target": {"sid": args.target_sid, "job_id": args.target_job, "frames": len(target_frames)},
        "empty": {"sid": args.empty_sid, "job_id": args.empty_job, "frames": len(empty_frames),
                  "registration": {"artifact_id": registration.get("artifact_id"),
                                   "quality": registration["quality"],
                                   "transform_R": registration["rotation_row_major"],
                                   "transform_t": registration["translation_m"]}},
        "older_empty": {"sid": args.older_empty_sid, "job_id": args.older_empty_job,
                        "frames": len(older_frames), "points_subsampled_stride": 4,
                        "gate_refusal": "registration.js exit 1 LEVELING_SHA_MISMATCH at line 104 "
                                        "(report.recommended!=='tls'): 10-10 配平跨方法 offset 差 "
                                        "0.033 m > 0.03 m 门 → 既有配准管线拒绝该空场"},
        "criterion": "leak = no empty-scene cell within +/-1 cell (Chebyshev <= cell_m)",
        "cluster_cell_m": CLUSTER_CELL_M, "min_cluster_points": MIN_CLUSTER_POINTS,
        "reports": reports,
    }
    with (out / "04_BACKGROUND.json").open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)

    keys, origin, base = background_keys(empty_registered_points, CELL_M)
    finite = np.isfinite(target_frames[0][2]).all(axis=1)
    mask = foreground_mask(target_frames[0][2][finite], keys, origin, base, CELL_M)
    render(target_frames[0], target_frames[0][2][finite][mask],
           out / "04_BACKGROUND.png", "registered 10-13 empty vs 10-14 frame 0")
    summary = {key: {k: report[k] for k in
                     ("empty_cells", "leak_points_median", "leak_points_p10_p90", "leak_fraction_median",
                      "largest_cluster_median", "largest_cluster_max",
                      "persistent_cells_ge80pct_frames")}
               for key, report in reports.items()}
    print(json.dumps(summary, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
