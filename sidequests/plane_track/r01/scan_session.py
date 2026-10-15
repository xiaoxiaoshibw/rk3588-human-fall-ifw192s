"""在任意会话上跑 P1 管线（背景=空场经 1 或 2 段注册变换到该会话显示系）。

用法：
    python -B -W error scan_session.py --out <evidence> --sid cap_20261014_221808 \
        --job ce77481751a9421b8e0f7cd77886cb05 \
        --registration 36_REGISTRATION_164522_to_221808 \
        [--bridge 03_REGISTRATION_131958_to_164522] [--empty-job 61cb6976b0f8479394641850d9a7c6ca]

说明：`--registration` 是"上一段→本段"的变换；`--bridge` 是"空场→上一段"的变换（可选）。
两段都在 registration.js PASS 的前提下由本脚本合成：p_本段 = R1(R0 p_空场 + t0) + t1。
输出：37_SCAN_<sid>.json（轨迹/时间线/负对照）+ 37_SCAN_<sid>.png
"""
import argparse
import json
from pathlib import Path

import numpy as np

from common import LEVELED
from inspect_target import clusters_local
from plane_shape import robust_core
from rt_server import EmptyIndex, _dedup_keys, _foreground_mask_fast
from tbd_track import (CELL_M, FREE_SPACE_MIN_M, GRID_M, Track)


def compose(registration, bridge=None):
    R1 = np.asarray(registration["rotation_row_major"], dtype=float).reshape(3, 3)
    t1 = np.asarray(registration["translation_m"], dtype=float)
    if bridge is None:
        return R1, t1
    R0 = np.asarray(bridge["rotation_row_major"], dtype=float).reshape(3, 3)
    t0 = np.asarray(bridge["translation_m"], dtype=float)
    return R1 @ R0, R1 @ t0 + t1


def load_frames(job, method="tls"):
    directory = LEVELED / job / method
    meta = json.loads((directory / "meta.json").read_text(encoding="utf8"))
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    total = int(meta["total_points"])
    xyz = np.ndarray((total, 3), dtype="<f4", buffer=raw, strides=(28, 4))
    frames = []
    for index, frame in enumerate(meta["frames"]):
        lo = int(frame["offset_points"]); hi = lo + int(frame["count_points"])
        stamp = float(frame.get("bag_time_sec", frame["stamp_sec"]))
        frames.append((index, stamp, np.asarray(xyz[lo:hi], dtype=np.float64)))
    return frames, meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--sid", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--bridge", default=None)
    parser.add_argument("--empty-job", default="61cb6976b0f8479394641850d9a7c6ca")
    parser.add_argument("--empty-stride", type=int, default=2)
    args = parser.parse_args()
    out = Path(args.out)
    registration = json.loads((out / args.registration / "registration.json").read_text(encoding="utf8"))
    bridge = None
    if args.bridge:
        bridge = json.loads((out / args.bridge / "registration.json").read_text(encoding="utf8"))
    R, t = compose(registration, bridge)
    print("composed transform: R diag", np.round(np.diag(R), 3).tolist(), "t", np.round(t, 3).tolist())

    empty_frames, _emeta = load_frames(args.empty_job)
    chunks = []
    for _index, _stamp, points in empty_frames:
        finite = np.isfinite(points).all(axis=1)
        chunks.append(points[finite][::args.empty_stride] @ R.T + t)
    empty_points = np.concatenate(chunks)
    empty_index = EmptyIndex(empty_points)
    keys, origin, base = _dedup_keys(empty_points, CELL_M)
    print("empty points in target frame:", len(empty_points), "unique cells:", len(keys))

    frames, meta = load_frames(args.job)
    tracks, finished, next_id = [], [], 1
    timeline, foreground_counts = [], []
    for index, stamp, points in frames:
        finite = np.isfinite(points).all(axis=1)
        points = points[finite]
        mask = _foreground_mask_fast(points, keys, origin, base, CELL_M)
        foreground_counts.append(int(mask.sum()))
        candidates = []
        for members in clusters_local(points[mask], GRID_M, 1):
            group = points[mask][members]
            center, core = robust_core(group)
            distance = empty_index.nearest_distance(center)
            if distance < FREE_SPACE_MIN_M:
                continue
            candidates.append({"center": center, "points": int(len(group)), "core_points": int(len(core)),
                               "distance_to_empty_m": round(float(distance), 3),
                               "weight": float(min(len(group), 32))})
        for track in tracks:
            track.predict(stamp)
        used = set()
        for track in tracks:
            gate = max(0.5, 1.5 * float(np.linalg.norm(track.x[3:])) * 0.103 + 0.2)
            best = None
            for order, candidate in enumerate(candidates):
                if order in used:
                    continue
                distance = float(np.linalg.norm(candidate["center"] - track.x[:3]))
                if distance <= gate and (best is None or distance < best[0]):
                    best = (distance, order, candidate)
            if best is not None:
                _, order, candidate = best
                used.add(order)
                track.update(candidate["center"], stamp, candidate["weight"], index)
            else:
                track.missed()
        for order, candidate in enumerate(candidates):
            if order in used or candidate["points"] < 3:
                continue
            tracks.append(Track(next_id, candidate["center"], stamp, candidate["weight"], index))
            next_id += 1
        tracks = [track for track in tracks if track.alive]
        timeline.append({"frame": index, "stamp_s": stamp, "candidates": len(candidates),
                         "foreground_points": int(mask.sum()),
                         "confirmed": sum(1 for track in tracks if track.confirmed)})
    finished.extend(tracks)
    summaries = [track.summary() for track in finished]
    moving = sorted([s for s in summaries if s["moving"]], key=lambda s: -s["score"])
    payload = {
        "sid": args.sid, "job_id": args.job, "frames": len(frames),
        "registration": {"artifact_id": registration.get("artifact_id"),
                         "bridge": None if bridge is None else bridge.get("artifact_id"),
                         "quality": registration["quality"]},
        "foreground_points": {"median": int(np.median(foreground_counts)),
                              "max": max(foreground_counts)},
        "tracks_confirmed": sum(1 for s in summaries if s["confirmed"]),
        "moving_tracks": moving, "all_tracks": summaries, "timeline": timeline,
    }
    with (out / ("37_SCAN_%s.json" % args.sid)).open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    render(out, args.sid, timeline, moving)
    print(json.dumps({"sid": args.sid, "frames": len(frames),
                      "foreground_median": payload["foreground_points"]["median"],
                      "tracks_confirmed": payload["tracks_confirmed"],
                      "moving_tracks": moving[:5]}, ensure_ascii=False))


def render(out, sid, timeline, moving):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt

    figure, panels = plt.subplots(1, 2, figsize=(15, 5))
    panels[0].plot([r["frame"] for r in timeline], [r["foreground_points"] for r in timeline], "-",
                   color="#4c9be8")
    panels[0].set_title("逐帧前景点数（背景=空场经注册变换）"); panels[0].set_xlabel("帧")
    panels[0].grid(alpha=0.3)
    panels[1].plot([r["frame"] for r in timeline], [r["candidates"] for r in timeline], "-",
                   color="#f2c14e")
    panels[1].set_title("逐帧自由空间候选数"); panels[1].set_xlabel("帧"); panels[1].grid(alpha=0.3)
    figure.suptitle("%s：段内扫描（%d 帧，确认%d 轨，运动轨 %d）" % (
        sid, len(timeline), sum(1 for r in timeline if r["confirmed"]), len(moving)), fontsize=12)
    figure.tight_layout(rect=[0, 0, 1, 0.94])
    figure.savefig(out / ("37_SCAN_%s.png" % sid), dpi=110)
    plt.close(figure)


if __name__ == "__main__":
    main()
