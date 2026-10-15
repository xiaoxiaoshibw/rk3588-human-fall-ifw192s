"""T4 小目标检测 + 跟踪：复用 core/lidar_candidates.py 候选层（只有设置是新的）。

用法：
    python -B -W error plane_track.py --out <evidence_dir> --job <job_id> --method tls
    python -B -W error plane_track.py --out <evidence_dir> --synthetic
跟踪门限不用 perception.yaml 的 max_speed_m_s=2.5 / gate_m=0.8：
    gate = 0.35 m（实测目标 2.7 s 漂移 ±0.15 m 的最大帧间位移 + 余量，见 06_TRACK_REAL.json）。
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

from common import LEVELED, ROOT, intensity_view

sys.path.insert(0, str(ROOT / "src/human_fall_detection"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.ground import STATUS_VALID  # noqa: E402
from core import lidar_candidates as LC  # noqa: E402

GROUND = {"status": STATUS_VALID, "normal": [0.0, 0.0, 1.0], "offset_m": 0.0,
          "frame": "ground_offline_display", "sensor_height_m": 1.14}
BASE_SETTINGS = {
    "range_min_m": 1.0, "range_max_m": 10.0,
    "height_min_m": -0.5, "height_max_m": 4.5,
    "cluster_cell_m": 0.3, "min_cluster_points": 5, "preferred_cluster_points": 8,
    "pca_min_points": 5, "pca_axis_ratio": 2.5,
    "denoise_enabled": False, "denoise_radius_m": 0.12, "denoise_min_neighbors": 2,
    "max_points": 200000,
}
FRAME_PERIOD_S = 0.103          # 帧内滚动窗口（本工单已核实值）
GATE_M = 0.35                   # 见模块 docstring
DEFAULT_AREA_M2 = 0.0117        # 玩具飞机展翅级轮廓（工单提供），用于可达距离模型


def snapshot_settings(**overrides):
    settings = dict(BASE_SETTINGS)
    settings.update(overrides)
    return settings


def frame_candidates(points_xyz, settings, session_id, frame_index, stamp, evidence_offset=0):
    """One frame through the shared candidate layer; returns compact candidate dicts."""
    snapshot = LC.build_snapshot(
        points_xyz, settings, session_id=session_id, time_epoch=0,
        snapshot_id="f%04d" % frame_index, seq=frame_index, ground=GROUND,
        frame_id="ground_offline_display")
    rows = []
    for candidate in snapshot["candidates"]:
        rows.append({
            "candidate_id": candidate["candidate_id"],
            "point_count": candidate["point_count"],
            "center": candidate["center_source_m"],
            "evidence_indices": [int(i) for i in candidate["evidence_indices"]],
            "height_median_m": None if candidate["height_m"] is None else candidate["height_m"]["median"],
            "horizontal_extent_max_m": None if candidate["horizontal_extent_m"] is None
            else candidate["horizontal_extent_m"]["max"],
            "axis_ambiguous": candidate["axis"]["ambiguous"],
            "range_median_m": candidate["range_m"]["median"],
        })
    return rows


def streak_m(candidate_points):
    """Max pairwise extent along the dominant horizontal direction ("scratch" length)."""
    if len(candidate_points) < 2:
        return 0.0, (0.0, 0.0)
    xy = candidate_points[:, :2]
    centred = xy - xy.mean(axis=0)
    values, vectors = np.linalg.eigh(centred.T @ centred / len(centred))
    axis = vectors[:, -1]
    project = centred @ axis
    return float(project.max() - project.min()), (float(axis[0]), float(axis[1]))


def run_frames(frames, settings, session_id="cap_20261014_164522"):
    """frames: list of (index, stamp, xyz(N,3), intensity(N,) or None) -> per-frame candidates+seeds."""
    rows = []
    for index, stamp, xyz, values in frames:
        candidates = frame_candidates(xyz, settings, session_id, index, stamp)
        for candidate in candidates:
            local = xyz[candidate["evidence_indices"]]
            candidate["streak_m"], candidate["streak_direction"] = streak_m(local)
            if values is not None:
                candidate["intensity_median"] = float(np.median(values[candidate["evidence_indices"]]))
        rows.append({"frame": index, "stamp_s": stamp, "candidate_count": len(candidates),
                     "logical_points": int(len(xyz)), "candidates": candidates})
    return rows


def track(rows, seed_center, gate_m=GATE_M, max_gap_frames=3, adaptive_gate=True):
    """Greedy nearest-center association with an explicit loss state (no re-assign after loss).

    Gate rule (evidence-based, deliberately not perception.yaml's 2.5 m/s / 0.8 m):
    base gate 0.35 m covers the measured ±0.15 m drift target. The within-frame
    "scratch" length bounds the inter-frame displacement (streak = v×0.103 s), so
    the gate grows to 1.2×streak + 0.15 m of the last detected candidate; a slow
    target keeps the 0.35 m gate, a fast one is not dropped by it.
    """
    track_rows, events = [], []
    center = np.asarray(seed_center, dtype=np.float64)
    lost = False
    last_seen = None
    track_id = 1
    last_streak = None
    missing_since = None
    for row in rows:
        gate = gate_m
        if adaptive_gate and last_streak is not None:
            gate = max(gate_m, 1.2 * last_streak + 0.15)
        picked = None
        if not lost:
            best = None
            for candidate in row["candidates"]:
                distance = float(np.linalg.norm(np.asarray(candidate["center"]) - center))
                if best is None or distance < best[0]:
                    best = (distance, candidate)
            if best is not None and best[0] <= gate:
                picked = best[1]
        if picked is None:
            track_rows.append({**{k: row[k] for k in ("frame", "stamp_s", "candidate_count")},
                               "detected": False, "track_id": None, "association_distance_m": None,
                               "gate_m": gate, "point_count": None, "range_median_m": None,
                               "streak_m": None, "center": None})
            if missing_since is None:
                missing_since = row["frame"]
            if last_seen is not None and row["frame"] - last_seen >= max_gap_frames:
                lost = True
            continue
        new_center = np.asarray(picked["center"], dtype=np.float64)
        step = float(np.linalg.norm(new_center - center))
        last_streak = picked["streak_m"]
        center = new_center
        last_seen = row["frame"]
        missing_since = None
        track_rows.append({**{k: row[k] for k in ("frame", "stamp_s", "candidate_count")},
                           "detected": True, "track_id": track_id,
                           "association_distance_m": step,
                           "gate_m": gate,
                           "point_count": picked["point_count"],
                           "range_median_m": picked["range_median_m"],
                           "streak_m": picked["streak_m"],
                           "streak_direction": picked["streak_direction"],
                           "intensity_median": picked.get("intensity_median"),
                           "center": picked["center"]})
    detected = [row for row in track_rows if row["detected"]]
    speeds = []
    for previous, current in zip(detected, detected[1:]):
        dt = current["stamp_s"] - previous["stamp_s"]
        if dt > 0:
            distance = float(np.linalg.norm(np.asarray(current["center"]) - np.asarray(previous["center"])))
            speeds.append({"frame": current["frame"], "speed_m_s": distance / dt, "step_m": distance})
    summary = {
        "frames": len(track_rows),
        "detected_frames": len(detected),
        "lost_frames": len(track_rows) - len(detected),
        "lost_runs": sum(1 for row in track_rows if not row["detected"] and
                         (row["frame"] == 0 or track_rows[row["frame"] - 1]["detected"] is False)),
        "id_switches": 0,          # single greedy track; any re-init would show as a new run
        "reinit_count": sum(1 for row in track_rows if row["detected"] and
                            (row["frame"] == 0 or track_rows[row["frame"] - 1]["detected"] is False)),
        "max_step_speed_m_s": max((item["speed_m_s"] for item in speeds), default=None),
        "max_step_m": max((item["step_m"] for item in speeds), default=None),
        "gate_m": gate_m,
        "adaptive_gate": adaptive_gate,
        "detection_rate": len(detected) / len(track_rows) if track_rows else None,
    }
    return track_rows, speeds, summary, events


def frame_threshold_sweep(frames, seed_center, thresholds=(3, 5, 8, 25)):
    """Per-threshold detection rate near the seed (hit = a candidate center within GATE_M)."""
    result = {}
    for threshold in thresholds:
        rows = run_frames(frames, snapshot_settings(min_cluster_points=threshold,
                                                    preferred_cluster_points=max(threshold, 8)))
        hits, points = 0, []
        for row in rows:
            near = [candidate for candidate in row["candidates"]
                    if float(np.linalg.norm(np.asarray(candidate["center"]) - np.asarray(seed_center))) <= GATE_M]
            if near:
                hits += 1
                points.append(max(candidate["point_count"] for candidate in near))
        result[str(threshold)] = {"frames": len(rows), "hit_frames": hits,
                                  "detection_rate": hits / len(rows) if rows else None,
                                  "point_counts": {"min": min(points) if points else None,
                                                   "median": float(np.median(points)) if points else None,
                                                   "max": max(points) if points else None}}
    return result


def reachable_distance_m(area_m2=DEFAULT_AREA_M2, threshold=5, density=14282.0):
    """工单模型 N ≈ A×14282/R² → R_max = sqrt(A×14282/N)。"""
    return float(np.sqrt(area_m2 * density / threshold))


def load_leveled_frames(job_id, method, sid):
    directory = LEVELED / job_id / method
    meta = json.loads((directory / "meta.json").read_text(encoding="utf8"))
    transform = json.loads((directory / "transform.json").read_text(encoding="utf8"))
    stride = int(meta["point_stride_bytes"])
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    xyz = np.ndarray((int(meta["total_points"]), 3), dtype="<f4", buffer=raw, strides=(stride, 4))
    values = intensity_view(directory, meta)
    frames = []
    for index, frame in enumerate(meta["frames"]):
        lo = int(frame["offset_points"])
        hi = lo + int(frame["count_points"])
        stamp = float(frame["bag_time_sec"]) if "bag_time_sec" in frame else float(frame["stamp_sec"])
        frames.append((index, stamp, np.asarray(xyz[lo:hi], dtype=np.float64),
                       np.asarray(values[lo:hi], dtype=np.float64)))
    return frames, transform, meta


def real_run(args):
    frames, transform, meta = load_leveled_frames(args.job, args.method, args.sid)
    seed = np.asarray(transform["R"], dtype=np.float64) @ np.array([4.3, -0.55, 4.17]) \
        + np.asarray(transform["t"], dtype=np.float64)
    rows = run_frames(frames, snapshot_settings())
    track_rows, speeds, summary, _ = track(rows, seed)
    sweep = frame_threshold_sweep(frames, seed)
    denoised_rows = run_frames(frames, snapshot_settings(denoise_enabled=True))
    denoise_ablation = {
        "denoise_on_candidate_frames": sum(1 for row in denoised_rows
                                           if any(float(np.linalg.norm(np.asarray(c["center"]) - seed)) <= GATE_M
                                                  for c in row["candidates"])),
        "denoise_on_candidates_total": sum(row["candidate_count"] for row in denoised_rows),
        "denoise_off_candidate_frames": sum(1 for row in rows
                                            if any(float(np.linalg.norm(np.asarray(c["center"]) - seed)) <= GATE_M
                                                   for c in row["candidates"])),
        "denoise_off_candidates_total": sum(row["candidate_count"] for row in rows),
    }
    detected = [row for row in track_rows if row["detected"]]
    points = [row["point_count"] for row in detected]
    area_samples = [row["point_count"] * row["range_median_m"] ** 2 / 14282.0 for row in detected]
    payload = {
        "sid": args.sid, "job_id": args.job, "method": args.method,
        "settings": snapshot_settings(), "gate_m": GATE_M, "frame_period_s": FRAME_PERIOD_S,
        "seed_display": seed.tolist(),
        "track": track_rows, "speeds": speeds, "summary": summary,
        "threshold_sweep": sweep,
        "denoise_ablation": denoise_ablation,
        "implied_area_m2": {"median": float(np.median(area_samples)) if area_samples else None,
                            "min": float(np.min(area_samples)) if area_samples else None,
                            "max": float(np.max(area_samples)) if area_samples else None},
        "points_per_hit": {"count": len(points), "min": min(points) if points else None,
                           "median": float(np.median(points)) if points else None,
                           "max": max(points) if points else None},
        "reachable_distance_m": {str(t): reachable_distance_m(threshold=t)
                                 for t in (3, 5, 8, 25)},
        "reachable_distance_from_measured_area": {
            str(t): reachable_distance_m(
                area_m2=float(np.median(area_samples)) if area_samples else DEFAULT_AREA_M2, threshold=t)
            for t in (3, 5, 8, 25)},
    }
    with (args.out / "06_TRACK_REAL.json").open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    render_track(payload, args.out / "06_TRACK_REAL.png")
    print(json.dumps({k: payload["summary"][k] for k in
                      ("frames", "detected_frames", "lost_frames", "max_step_speed_m_s")},
                     default=float))


def render_track(payload, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = payload["track"]
    figure, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    times = [row["stamp_s"] - rows[0]["stamp_s"] for row in rows]
    detected = [row for row in rows if row["detected"]]
    det_times = [row["stamp_s"] - rows[0]["stamp_s"] for row in detected]
    axes[0].plot([row["center"][0] for row in detected], [row["center"][1] for row in detected], "-o", ms=3)
    axes[0].set_xlabel("x display [m]"); axes[0].set_ylabel("y display [m]")
    axes[0].set_title("target track (display frame)"); axes[0].grid(alpha=0.3)
    axes[1].plot(det_times, [row["point_count"] for row in detected], "-o", ms=3)
    axes[1].set_xlabel("t [s]"); axes[1].set_ylabel("points"); axes[1].set_title("points per frame")
    axes[1].grid(alpha=0.3)
    axes[2].plot(times, [1 if row["detected"] else 0 for row in rows], "o", ms=4)
    axes[2].set_yticks([0, 1]); axes[2].set_xlabel("t [s]"); axes[2].set_title("detected per frame")
    axes[2].grid(alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=110)
    plt.close(figure)


def synthetic_frames(speed_m_s, area_m2, range_m, frames=30, period=FRAME_PERIOD_S,
                     start_azimuth_deg=10.0, elevation_deg=32.0):
    """Synthetic single small target on a constant-range horizontal arc (range stays 6 m so
    every frame is inside the range gate; horizontal arc length per frame = v×0.103 s).
    speed_m_s is the target's true horizontal speed. Points cover the within-frame swept
    arc (frame integration); count from N≈A×14282/R²."""
    count = max(1, int(round(area_m2 * 14282.0 / range_m ** 2)))
    out = []
    elevation = np.radians(elevation_deg)
    horizontal_radius = range_m * np.cos(elevation)
    for index in range(frames):
        t = index * period
        azimuth = np.radians(start_azimuth_deg) + (speed_m_s * t) / horizontal_radius
        if count == 1:
            offsets = [0.0]
        else:
            offsets = np.linspace(-1.0, 0.0, count) * (speed_m_s * period) / horizontal_radius
        points = []
        for offset in offsets:
            theta = azimuth + offset
            points.append([horizontal_radius * np.cos(theta),
                           horizontal_radius * np.sin(theta),
                           range_m * np.sin(elevation)])
        out.append((index, t, np.asarray(points, dtype=np.float64), np.full(count, 100.0)))
    return out


def synthetic_run(args):
    results = {}
    for cell_m in (0.3, 0.5):
        for speed in (0.0, 3.0, 5.0, 10.0):
            frames = synthetic_frames(speed, DEFAULT_AREA_M2, 6.0)
            rows = run_frames(frames, snapshot_settings(cluster_cell_m=cell_m), session_id="synthetic")
            seed = np.asarray(frames[0][2].mean(axis=0))
            track_rows, speeds, summary, _ = track(rows, seed)
            detected = [row for row in track_rows if row["detected"]]
            streak = [row["streak_m"] for row in detected]
            near_seed = sum(1 for row in rows if any(
                float(np.linalg.norm(np.asarray(c["center"]) - np.asarray(frames[row["frame"]][2].mean(axis=0))))
                <= max(GATE_M, speed * FRAME_PERIOD_S + 0.05) for c in row["candidates"]))
            results["cell_%g_speed_%g_m_s" % (cell_m, speed)] = {
                "cluster_cell_m": cell_m,
                "true_speed_m_s": speed, "expected_streak_m": speed * FRAME_PERIOD_S,
                "summary": summary,
                "cluster_frames_near_target": near_seed,
                "streak_m_median": float(np.median(streak)) if streak else None,
                "measured_max_step_speed_m_s": summary["max_step_speed_m_s"],
            }
    payload = {"sid": "synthetic", "settings": snapshot_settings(),
               "area_m2": DEFAULT_AREA_M2, "range_m": 6.0, "frame_period_s": FRAME_PERIOD_S,
               "motion": "constant-range arc, arc length per frame = v*0.103s",
               "cases": results}
    name = getattr(args, "name", None) or "07_TRACK_SYNTHETIC.json"
    with (args.out / name).open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({k: {"detected": v["summary"]["detected_frames"],
                          "streak": v["streak_m_median"],
                          "meas_speed": v["measured_max_step_speed_m_s"]}
                      for k, v in results.items()}, default=float))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--job")
    parser.add_argument("--method", default="tls")
    parser.add_argument("--sid", default="cap_20261014_164522")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--name", default=None)
    args = parser.parse_args()
    args.out = Path(args.out)
    if args.synthetic:
        synthetic_run(args)
    else:
        if not args.job:
            parser.error("--job is required unless --synthetic")
        real_run(args)


if __name__ == "__main__":
    main()
