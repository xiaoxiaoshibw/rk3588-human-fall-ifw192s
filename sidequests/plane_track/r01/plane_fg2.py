"""T4c 算法 v2：单链接聚类 + 稳健核中心 + 去拖影体形框估计。

相对 v1（plane_fg.py）的改动：
  1) 聚类：0.3 m 网格 26 邻域链式连通 → 单链接最大距离 0.12 m（网格 0.0693 m × 26 邻域，
     两点最大跨度 ≈ 0.12 m），拖影内部仍连通，跨段离群点被分开；
  2) 簇心：全体中位数 → 稳健核（0.18 m 半径内迭代中位数），离群点不再拉偏中心；
  3) 体形：新增去拖影估计——沿轨迹方向长度 = 实测沿轨迹范围 − 帧间位移（帧内滚动 s ≈ v×0.103 s），
     垂直两向尺寸不受拖影影响；两者都输出并标注可分辨下限。

用法：
    python -B -W error plane_fg2.py --out <evidence_dir> --registration <dir>
输出：20_TRACK_V2.json + 20_TRACK_V2.png（v1/v2 中心与体形对照）。
"""
import argparse
import json
from pathlib import Path

import numpy as np

from background import apply_transform, background_keys, collect_points, foreground_mask, load_points
from common import LEVELED
from inspect_target import clusters_local

CELL_M = 0.08
LINK_M = 0.12
GRID_M = LINK_M / np.sqrt(3.0)
MIN_POINTS = 8
CORE_RADIUS_M = 0.18
FREE_SPACE_MIN_M = 0.20
GATE_BASE_M = 0.5
STATIC_LEAKS = [[3.9, 2.6, 0.2], [0.78, 1.93, 0.28], [9.45, 5.4, 0.8]]
FRAME_PERIOD_S = 0.103


def load_intensity(job_id, method):
    directory = LEVELED / job_id / method
    meta = json.loads((directory / "meta.json").read_text(encoding="utf8"))
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    return np.ndarray((int(meta["total_points"]),), dtype="<f4", buffer=raw, offset=12, strides=(28,))


def robust_core(group):
    """迭代中位数：0.18 m 半径内的点反复求中位数（对拖影尾部和离群点稳健）。"""
    center = np.median(group, axis=0)
    core = group
    for _ in range(4):
        distance = np.linalg.norm(group - center, axis=1)
        core = group[distance <= CORE_RADIUS_M]
        if len(core) < 3:
            break
        updated = np.median(core, axis=0)
        if np.allclose(updated, center, atol=1e-6):
            center = updated
            break
        center = updated
    return center, core


def analyse_cluster(group, intensity_slice, empty_points, motion=None):
    center, core = robust_core(group)
    distance_to_empty = float(np.linalg.norm(empty_points - center, axis=1).min()) if len(empty_points) else 99.0
    report = {
        "point_count": int(len(group)),
        "core_point_count": int(len(core)),
        "center": [round(float(v), 4) for v in center],
        "median_center": [round(float(v), 4) for v in np.median(group, axis=0)],
        "distance_to_empty_m": round(distance_to_empty, 4),
        "intensity_median": round(float(np.median(intensity_slice)), 1),
        "max_radius_m": round(float(np.linalg.norm(group - center, axis=1).max()), 4),
        "points": np.round(group, 4).tolist(),
    }
    if motion is not None and len(core) >= 3:
        direction, step = motion
        projection = (group - center) @ direction
        along = float(projection.max() - projection.min())
        core_projection = (core - center) @ direction
        # 垂直方向=去拖影后仍可量测的两向尺寸
        reference = np.array([0.0, 0.0, 1.0]) if abs(direction[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        perp1 = np.cross(direction, reference); perp1 /= np.linalg.norm(perp1)
        perp2 = np.cross(direction, perp1)
        def span(vector):
            values = (group - center) @ vector
            return float(values.max() - values.min())
        report["desmear"] = {
            "motion_direction": [round(float(v), 4) for v in direction],
            "step_m": round(float(step), 4),
            "along_track_span_m": round(along, 4),
            "along_track_core_span_m": round(float(core_projection.max() - core_projection.min()), 4),
            "body_length_est_m": round(max(along - step, 0.0), 4),
            "body_width_m": round(span(perp1), 4),
            "body_thickness_m": round(span(perp2), 4),
            "note": ("沿轨迹长度 = 实测范围 − 帧内位移；≤ 可分辨下限时不可分辨" if along - step > 0.02
                     else "本体沿轨尺寸小于帧内拖影，不可分辨（只给上限）"),
        }
    return report


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
    target_intensity = load_intensity(args.target_job, "tls")

    offsets, running = [], 0
    for _index, _stamp, xyz, _values in target_frames:
        offsets.append(running)
        running += int(xyz.shape[0])

    # 第一遍：逐帧单链接簇 + 稳健核（先不带运动信息）
    per_frame = []
    for index, (stamp, (frame_index, _fstamp, xyz, _values)) in enumerate(zip([f[1] for f in target_frames], target_frames)):
        finite = np.isfinite(xyz).all(axis=1)
        points = xyz[finite]
        mask = foreground_mask(points, keys, origin, base, CELL_M)
        intensity = target_intensity[offsets[index] + np.flatnonzero(finite)[mask]]
        candidates = []
        for members in clusters_local(points[mask], GRID_M, MIN_POINTS):
            group = points[mask][members]
            report = analyse_cluster(group, intensity[members], empty_points)
            center = np.asarray(report["center"])
            report["free_space"] = bool(report["distance_to_empty_m"] >= FREE_SPACE_MIN_M)
            report["near_known_leak"] = bool(np.min(np.linalg.norm(np.asarray(STATIC_LEAKS) - center, axis=1)) < 0.9)
            candidates.append(report)
        candidates.sort(key=lambda row: -row["point_count"])
        per_frame.append({"frame": frame_index, "stamp_s": stamp, "candidates": candidates,
                          "foreground_points": int(mask.sum())})

    # 跟踪（稳健核中心；门 = max(0.5, 1.2×沿轨跨度+0.3)）
    track_rows, previous, last_span, lost = [], None, None, False
    for row in per_frame:
        pick = None
        if not lost:
            gate = GATE_BASE_M if last_span is None else max(GATE_BASE_M, 1.2 * last_span + 0.3)
            best = None
            for candidate in row["candidates"]:
                if not candidate["free_space"] or candidate["near_known_leak"] or candidate["point_count"] < MIN_POINTS:
                    continue
                distance = 0.0 if previous is None else float(
                    np.linalg.norm(np.asarray(candidate["center"]) - previous))
                if distance <= gate and (best is None or distance < best[0]):
                    best = (distance, candidate)
            pick = None if best is None else best[1]
        if pick is None:
            track_rows.append({"frame": row["frame"], "stamp_s": row["stamp_s"], "detected": False})
            continue
        previous = np.asarray(pick["center"])
        last_span = pick["point_count"] and _along_span(pick)
        track_rows.append({"frame": row["frame"], "stamp_s": row["stamp_s"], "detected": True,
                           "point_count": pick["point_count"], "core_point_count": pick["core_point_count"],
                           "center": pick["center"], "median_center": pick["median_center"],
                           "max_radius_m": pick["max_radius_m"],
                           "distance_to_empty_m": pick["distance_to_empty_m"],
                           "intensity_median": pick["intensity_median"]})

    # 第二遍：用 v2 轨迹给出运动方向/步长，再算去拖影体形
    centers = {row["frame"]: np.asarray(row["center"]) for row in track_rows if row["detected"]}
    detected_frames = sorted(centers)
    enriched = []
    for row in per_frame:
        frame = row["frame"]
        motion = None
        if frame in centers:
            if frame + 1 in centers:
                delta = centers[frame + 1] - centers[frame]
            else:
                delta = centers[frame] - centers[frame - 1]
            norm = float(np.linalg.norm(delta))
            if norm > 1e-6:
                step = norm
                if frame - 1 in centers and frame + 1 in centers:
                    step = float(np.linalg.norm(centers[frame + 1] - centers[frame - 1]) / 2.0)
                motion = (delta / norm, step)
        for candidate in row["candidates"]:
            if motion is not None and np.allclose(np.asarray(candidate["center"]), centers[frame], atol=1e-6):
                candidate.update(analyse_cluster(np.asarray(candidate["points"]),
                                                 np.array([candidate["intensity_median"]]),
                                                 empty_points, motion=motion))
        enriched.append(row)

    detected = [row for row in track_rows if row["detected"]]
    speeds, steps = [], []
    for left, right in zip(detected, detected[1:]):
        dt = right["stamp_s"] - left["stamp_s"]
        if dt > 0:
            step = float(np.linalg.norm(np.asarray(right["center"]) - np.asarray(left["center"])))
            steps.append(step)
            speeds.append(step / dt)
    payload = {
        "target_sid": "cap_20261014_164522",
        "algorithm": {"link_m": LINK_M, "grid_m": round(GRID_M, 4), "core_radius_m": CORE_RADIUS_M,
                      "free_space_min_m": FREE_SPACE_MIN_M, "gate": "max(0.5, 1.2*span+0.3)",
                      "desmear": "body_length = along_track_span - step (step≈v×0.103s)"},
        "frames": enriched,
        "track": track_rows,
        "summary": {"frames": len(track_rows), "detected_frames": len(detected),
                    "lost_frames": len(track_rows) - len(detected),
                    "first_frame": detected[0]["frame"] if detected else None,
                    "last_frame": detected[-1]["frame"] if detected else None,
                    "max_speed_m_s": max(speeds) if speeds else None,
                    "max_step_m": max(steps) if steps else None,
                    "max_radius_m": max(row["max_radius_m"] for row in detected) if detected else None,
                    "max_radius_v1_m": 0.972},
    }
    with (out / "20_TRACK_V2.json").open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    render(payload, out / "20_TRACK_V2.png")
    print(json.dumps({"detected": payload["summary"]["detected_frames"],
                      "max_radius_v2": payload["summary"]["max_radius_m"],
                      "max_speed": None if payload["summary"]["max_speed_m_s"] is None
                      else round(payload["summary"]["max_speed_m_s"], 2)}))


def _along_span(candidate):
    desmear = candidate.get("desmear")
    if desmear:
        return desmear["along_track_span_m"]
    points = np.asarray(candidate["points"])
    return float(np.linalg.norm(points.max(axis=0) - points.min(axis=0)))


def render(payload, path):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt
    track = [row for row in payload["track"] if row["detected"]]
    boxes = {}
    for row in payload["frames"]:
        for candidate in row["candidates"]:
            if candidate["free_space"] and not candidate["near_known_leak"] and candidate.get("desmear"):
                boxes[row["frame"]] = candidate
                break
    figure, axes = plt.subplots(1, 3, figsize=(17, 5.4))
    axes[0].plot([row["median_center"][0] for row in track], [row["median_center"][1] for row in track],
                 "o--", color="#ff6b6b", ms=4, label="v1 中位数中心")
    axes[0].plot([row["center"][0] for row in track], [row["center"][1] for row in track],
                 "o-", color="#1f77b4", ms=4, label="v2 稳健核中心")
    for row in track:
        axes[0].annotate(str(row["frame"]), (row["center"][0], row["center"][1]), fontsize=9, color="#7f8c9b")
    axes[0].set_xlabel("x [m]"); axes[0].set_ylabel("y [m]"); axes[0].legend(fontsize=9)
    axes[0].set_title("A 中心对照（v1 vs v2）"); axes[0].grid(alpha=0.3); axes[0].set_aspect("equal")
    frames = sorted(boxes)
    axes[1].bar([str(f) for f in frames], [boxes[f]["desmear"]["along_track_span_m"] for f in frames],
                label="实测沿轨迹范围")
    axes[1].bar([str(f) for f in frames], [boxes[f]["desmear"]["step_m"] for f in frames],
                label="帧内位移 v×0.103 s", color="#f2c14e")
    axes[1].set_xlabel("帧"); axes[1].set_ylabel("m"); axes[1].legend(fontsize=9)
    axes[1].set_title("B 沿轨迹长度分解"); axes[1].grid(alpha=0.3, axis="y")
    axes[2].plot(frames, [boxes[f]["desmear"]["body_length_est_m"] for f in frames], "o-",
                 label="去拖影后本体长度估计")
    axes[2].plot(frames, [boxes[f]["desmear"]["body_width_m"] for f in frames], "s-", label="宽度(垂直)")
    axes[2].plot(frames, [boxes[f]["desmear"]["body_thickness_m"] for f in frames], "^-", label="厚度(垂直)")
    axes[2].axhline(0.02, color="#888", ls="--", lw=1)
    axes[2].set_xlabel("帧"); axes[2].set_ylabel("m"); axes[2].legend(fontsize=9)
    axes[2].set_title("C 去拖影体形（<0.02 m 视为不可分辨）"); axes[2].grid(alpha=0.3)
    figure.suptitle("PLANE-01 算法 v2：单链接聚类 + 稳健核中心 + 去拖影体形", fontsize=13)
    figure.tight_layout(rect=[0, 0, 1, 0.94])
    figure.savefig(path, dpi=110)
    plt.close(figure)


if __name__ == "__main__":
    main()
