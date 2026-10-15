"""T3/T4b 去背景后的移动目标（在自由空间里的高亮点簇）检测与跟踪。

用法：
    python -B -W error plane_fg.py --out <evidence_dir> --registration <dir>

判据（都用现有证据支撑，不是拍脑袋阈值）：
  1) 前景 = 与配准后的 10-13 空场（131958，registration.js PASS）在 0.08 m 网格 ±1 格内无匹配的点；
  2) 移动目标 = 前景簇中「离最近空场点 ≥0.2 m」的自由空间簇 —— 位移家具/新静物泄漏离空场只有 0.17–0.20 m；
  3) 跟踪门 = max(0.5, 1.2 × 划痕 + 0.3)（本段实测目标 2.8 m/s 级、f12 划痕 1.05 m）。
输出：15_PLANE_FG_TRACK.json + 15_PLANE_FG_TRACK.png（三视图按帧着色 + 轨迹）。
"""
import argparse
import json
from pathlib import Path

import numpy as np

from background import apply_transform, background_keys, collect_points, foreground_mask, load_points
from common import LEVELED
from inspect_target import clusters_local

CELL_M = 0.08
CLUSTER_CELL_M = 0.30
MIN_POINTS = 5
FREE_SPACE_MIN_M = 0.20
GATE_BASE_M = 0.5
STATIC_EXCLUDE_M = 0.9          # 与已知静态泄漏带中心太近的簇不算目标
STATIC_LEAKS = [[3.9, 2.6, 0.2], [0.78, 1.93, 0.28], [9.45, 5.4, 0.8]]


def load_intensity(job_id, method):
    directory = LEVELED / job_id / method
    meta = json.loads((directory / "meta.json").read_text(encoding="utf8"))
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    return meta, np.ndarray((int(meta["total_points"]),), dtype="<f4", buffer=raw,
                            offset=12, strides=(28,))


def clusters_with_stats(points, intensity_slice, empty_points):
    rows = []
    if not len(points):
        return rows
    for members in clusters_local(points, CLUSTER_CELL_M, MIN_POINTS):
        group = points[members]
        center = np.median(group, axis=0)
        extent = group.max(axis=0) - group.min(axis=0)
        distance = float(np.linalg.norm(empty_points - center, axis=1).min()) if len(empty_points) else 99.0
        rows.append({
            "point_count": int(len(members)),
            "center": [round(float(v), 4) for v in center],
            "extent_m": [round(float(v), 4) for v in extent],
            "streak_m": round(float(max(extent[0], extent[1])), 4),
            "distance_to_empty_m": round(distance, 4),
            "intensity_median": round(float(np.median(intensity_slice[members])), 1),
            "points": np.round(group, 4).tolist(),
        })
    rows.sort(key=lambda row: -row["point_count"])
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--target-job", default="363473a9e2e64649994dca11b2b26929")
    parser.add_argument("--empty-job", default="61cb6976b0f8479394641850d9a7c6ca")
    args = parser.parse_args()
    out = Path(args.out)
    registration = json.loads((Path(args.registration) / "registration.json").read_text(encoding="utf8"))
    assert registration["quality"]["status"] == "PASS"

    target_frames, _tmeta = load_points(args.target_job, "tls")
    empty_frames, _emeta = load_points(args.empty_job, "tls")
    empty_registered = apply_transform(empty_frames, registration["rotation_row_major"],
                                       registration["translation_m"])
    empty_points = collect_points(empty_registered, stride=2)
    keys, origin, base = background_keys(empty_points, CELL_M)
    _tint_meta, target_intensity = load_intensity(args.target_job, "tls")

    rows = []
    frame_offsets, running = [], 0
    for index, _stamp, xyz, _values in target_frames:
        frame_offsets.append(running)
        running += int(xyz.shape[0])
    for index, stamp, xyz, _values in target_frames:
        finite = np.isfinite(xyz).all(axis=1)
        points = xyz[finite]
        mask = foreground_mask(points, keys, origin, base, CELL_M)
        fg_intensity = target_intensity[frame_offsets[index] + np.flatnonzero(finite)[mask]]
        candidates = clusters_with_stats(points[mask], fg_intensity, empty_points)
        for candidate in candidates:
            center = np.asarray(candidate["center"])
            candidate["free_space"] = bool(candidate["distance_to_empty_m"] >= FREE_SPACE_MIN_M)
            candidate["near_known_leak"] = bool(np.min(np.linalg.norm(np.asarray(STATIC_LEAKS)
                                                                      - center, axis=1)) < STATIC_EXCLUDE_M)
        rows.append({"frame": index, "stamp_s": stamp, "foreground_points": int(mask.sum()),
                     "candidates": candidates})

    # 跟踪自由空间簇
    track_rows = []
    previous = None
    last_streak = None
    lost = False
    for row in rows:
        pick = None
        if not lost:
            gate = GATE_BASE_M
            if last_streak is not None:
                gate = max(GATE_BASE_M, 1.2 * last_streak + 0.3)
            best = None
            for candidate in row["candidates"]:
                if not candidate["free_space"] or candidate["near_known_leak"]:
                    continue
                if candidate["point_count"] < 8:
                    continue
                if previous is None:
                    distance = 0.0
                else:
                    distance = float(np.linalg.norm(np.asarray(candidate["center"]) - previous))
                if distance <= gate and (best is None or distance < best[0]):
                    best = (distance, candidate)
            pick = None if best is None else best[1]
        if pick is None:
            track_rows.append({"frame": row["frame"], "stamp_s": row["stamp_s"], "detected": False,
                               "reason": "lost" if lost else "no_free_space_candidate"})
            continue
        center = np.asarray(pick["center"])
        step = None if previous is None else float(np.linalg.norm(center - previous))
        previous = center
        last_streak = pick["streak_m"]
        track_rows.append({"frame": row["frame"], "stamp_s": row["stamp_s"], "detected": True,
                           "point_count": pick["point_count"], "center": pick["center"],
                           "extent_m": pick["extent_m"], "streak_m": pick["streak_m"],
                           "distance_to_empty_m": pick["distance_to_empty_m"],
                           "intensity_median": pick["intensity_median"],
                           "step_m": step,
                           "speed_m_s": None if step is None else step / 0.103})

    detected = [row for row in track_rows if row["detected"]]
    speeds = [row["speed_m_s"] for row in detected if row["speed_m_s"] is not None]
    path = 0.0
    for left, right in zip(detected, detected[1:]):
        path += float(np.linalg.norm(np.asarray(right["center"]) - np.asarray(left["center"])))
    payload = {
        "target_sid": "cap_20261014_164522", "empty_sid": "cap_20261013_131958",
        "registration_artifact": registration.get("artifact_id"),
        "criteria": {"cell_m": CELL_M, "cluster_cell_m": CLUSTER_CELL_M, "min_points": MIN_POINTS,
                     "free_space_min_m": FREE_SPACE_MIN_M, "gate": "max(0.5, 1.2*streak+0.3)",
                     "static_leaks_excluded": STATIC_LEAKS},
        "frames": [{k: v for k, v in row.items() if k != "candidates"} |
                   {"candidates": [{k: v for k, v in c.items() if k != "points"}
                                   for c in row["candidates"]]} for row in rows],
        "track": track_rows,
        "summary": {
            "frames": len(track_rows), "detected_frames": len(detected),
            "lost_frames": len(track_rows) - len(detected),
            "first_frame": detected[0]["frame"] if detected else None,
            "last_frame": detected[-1]["frame"] if detected else None,
            "points_per_hit": {"min": min(row["point_count"] for row in detected) if detected else None,
                               "median": float(np.median([row["point_count"] for row in detected])) if detected else None,
                               "max": max(row["point_count"] for row in detected) if detected else None},
            "max_speed_m_s": max(speeds) if speeds else None,
            "path_length_m": path,
            "duration_s": (detected[-1]["stamp_s"] - detected[0]["stamp_s"]) if len(detected) > 1 else None,
        },
        "object_points": [row for row in rows if any(
            c["free_space"] and not c["near_known_leak"] and c["point_count"] >= 8
            for c in row["candidates"])],
    }
    with (out / "15_PLANE_FG_TRACK.json").open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    render(payload, out / "15_PLANE_FG_TRACK.png")
    print(json.dumps({"detected_frames": payload["summary"]["detected_frames"],
                      "frames": payload["summary"]["frames"],
                      "objects": [(row["frame"], row["point_count"], row["center"],
                                   round(row["speed_m_s"], 2) if row["speed_m_s"] else None)
                                  for row in detected]}, ensure_ascii=False))


def render(payload, path):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt
    colors = plt.cm.viridis
    figure, axes = plt.subplots(1, 3, figsize=(18, 6))
    pairs = [(0, 1, "x", "y", "top (x,y)"), (0, 2, "x", "z", "side (x,z)"), (1, 2, "y", "z", "front (y,z)")]
    for row in payload["object_points"]:
        for candidate in row["candidates"]:
            if not (candidate["free_space"] and not candidate["near_known_leak"]
                    and candidate["point_count"] >= 8):
                continue
            points = np.asarray(candidate["points"])
            color = colors(row["frame"] / 26.0)
            for axis, (i, j, ni, nj, title) in zip(axes, pairs):
                axis.scatter(points[:, i], points[:, j], s=14, color=color)
    centers = np.asarray([row["center"] for row in payload["track"] if row["detected"]])
    for axis, (i, j, ni, nj, title) in zip(axes, pairs):
        if len(centers):
            axis.plot(centers[:, i], centers[:, j], "-", color="#888", lw=1)
            for k, row in enumerate([row for row in payload["track"] if row["detected"]]):
                axis.annotate(str(row["frame"]), (row["center"][i], row["center"][j]),
                              fontsize=9, color="#dddddd")
        axis.set_xlabel(ni); axis.set_ylabel(nj); axis.set_title(title); axis.grid(alpha=0.3)
    figure.suptitle("moving object after background removal (color=frame 9..16, gray line=track)", fontsize=14)
    figure.tight_layout(rect=[0, 0, 1, 0.96])
    figure.savefig(path, dpi=110)
    plt.close(figure)


if __name__ == "__main__":
    main()
