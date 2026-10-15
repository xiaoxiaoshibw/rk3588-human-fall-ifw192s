"""把"去背景 + 跟踪"渲成视频（MP4，10 fps，默认循环 3 遍）。

用法：
    python -B -W error make_video.py --out <evidence_dir> [--loops 3]
读取 15_PLANE_FG_TRACK.json（plane_fg.py 产物）；输出 17_PLANE_FG_TRACK.mp4。
"""
import argparse
import json
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--track", default="15_PLANE_FG_TRACK.json")
    parser.add_argument("--name", default="17_PLANE_FG_TRACK.mp4")
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--slow-loops", type=int, default=5)
    args = parser.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter

    out = Path(args.out)
    source = json.loads((out / args.track).read_text(encoding="utf8"))
    track = {row["frame"]: row for row in source["track"]}
    points_by_frame = {}
    for row in source.get("object_points", []):
        for candidate in row["candidates"]:
            if candidate["free_space"] and not candidate["near_known_leak"] and candidate["point_count"] >= 8:
                points_by_frame[row["frame"]] = np.asarray(candidate["points"])
                break
    if not points_by_frame:      # v2 JSON：candidates 在 frames 里（含 points）
        for row in source["frames"]:
            for candidate in row.get("candidates", []):
                if candidate.get("free_space") and not candidate.get("near_known_leak") \
                        and candidate.get("point_count", 0) >= 8 and candidate.get("points"):
                    points_by_frame[row["frame"]] = np.asarray(candidate["points"])
                    break
    frames = source["frames"]
    t0 = frames[0]["stamp_s"]
    detected = [row for row in source["track"] if row["detected"]]
    centers = {row["frame"]: np.asarray(row["center"]) for row in detected}
    speed_by_frame = {}
    for i, row in enumerate(detected):
        frame, center, stamp = row["frame"], np.asarray(row["center"]), row["stamp_s"]
        candidates = []
        if i + 1 < len(detected):
            delta, dt = np.asarray(detected[i + 1]["center"]) - center, detected[i + 1]["stamp_s"] - stamp
            if dt > 0:
                candidates.append(float(np.linalg.norm(delta) / dt))
        if i > 0:
            delta, dt = center - np.asarray(detected[i - 1]["center"]), stamp - detected[i - 1]["stamp_s"]
            if dt > 0:
                candidates.append(float(np.linalg.norm(delta) / dt))
        speed_by_frame[frame] = min(candidates) if candidates else 0.0
    # 视图范围：目标活动范围 + 地面
    lo = np.array([0.9, 0.2, -0.1])
    hi = np.array([2.9, 2.2, 1.9])

    figure, axes = plt.subplots(1, 3, figsize=(13.5, 5.2))
    pairs = [(0, 1, "x [m]", "y [m]", "俯视 x-y"), (0, 2, "x [m]", "z [m]", "侧视 x-z"),
             (1, 2, "y [m]", "z [m]", "前视 y-z")]

    def draw(frame_index, banner):
        for axis, (i, j, ni, nj, title) in zip(axes, pairs):
            axis.clear()
            axis.set_xlim(lo[i], hi[i]); axis.set_ylim(lo[j], hi[j])
            axis.set_xlabel(ni); axis.set_ylabel(nj); axis.set_title(title)
            axis.grid(alpha=0.25)
            if j == 2:      # z 轴视图画一条地面线
                axis.axhline(0.0, color="#3a4a58", lw=1)
            for past in range(0, frame_index):
                if past in points_by_frame:
                    fade = 0.10 + 0.35 * (past / max(1, frame_index))
                    axis.scatter(points_by_frame[past][:, i], points_by_frame[past][:, j],
                                 s=10, color="#ff6b6b", alpha=fade)
            if frame_index in points_by_frame:
                q = points_by_frame[frame_index]
                axis.scatter(q[:, i], q[:, j], s=42, color="#ff2d2d", zorder=5,
                             edgecolors="#ffd7d7", linewidths=0.5)
            if len(centers) > 1:
                ordered = [c for f, c in sorted(centers.items()) if f <= frame_index]
                if len(ordered) > 1:
                    axis.plot([c[i] for c in ordered], [c[j] for c in ordered], "-",
                              color="#f2c14e", lw=1.6, zorder=4)
            if frame_index in centers:
                axis.scatter([centers[frame_index][i]], [centers[frame_index][j]], s=130,
                             facecolors="none", edgecolors="#f2c14e", linewidths=2, zorder=6)
        row = track.get(frame_index, {})
        t = frames[frame_index]["stamp_s"] - t0
        if row.get("detected"):
            text = "帧 %d/27  t=%.2fs   目标#1: %d 点  %.2f m/s  强度 %.0f  离最近静态结构 %.2f m" % (
                frame_index + 1, t, row["point_count"], speed_by_frame.get(frame_index, 0.0),
                row["intensity_median"], row["distance_to_empty_m"])
        else:
            text = "帧 %d/27  t=%.2fs   未检出（该帧自由空间无目标：目标未进入视野或已离场）" % (
                frame_index + 1, t)
        figure.suptitle("PLANE-01 去背景跟踪（房间已减去）cap_20261014_164522 · " + banner
                        + "\n" + text, fontsize=12)
        figure.tight_layout(rect=[0, 0, 1, 0.92])

    target = out / args.name
    writer = FFMpegWriter(fps=args.fps, bitrate=4000, codec="libx264",
                          metadata={"title": "PLANE-01 background-removed tracking"})
    object_frames = sorted(f for f in points_by_frame)
    first_object = object_frames[0] if object_frames else 0
    last_object = object_frames[-1] if object_frames else 0
    schedule = [(frame, "完整 27 帧 · 真速 10 Hz", 1) for frame in range(len(frames))]
    for _loop in range(args.slow_loops):
        for frame in range(max(0, first_object - 1), min(len(frames), last_object + 3)):
            schedule.append((frame, "目标段 0.5 倍慢放（源 10 Hz）", 2))
    with writer.saving(figure, str(target), dpi=110):
        for frame_index, banner, repeat in schedule:
            for _ in range(repeat):
                draw(frame_index, banner)
                writer.grab_frame()
    plt.close(figure)
    print(json.dumps({"video": str(target), "bytes": target.stat().st_size,
                      "written_frames": sum(r for _f, _b, r in schedule), "fps": args.fps,
                      "seconds": round(sum(r for _f, _b, r in schedule) / args.fps, 2)}))


if __name__ == "__main__":
    main()
