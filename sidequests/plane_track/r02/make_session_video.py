"""R2：给"任意会话"出'去背景跟踪'视频（PLANE-01 `make_video.py` 的参数化变体）。

为什么另开一个文件：`sidequests/plane_track/r01/make_video.py` 把视图范围（[0.9,0.2,-0.1]–[2.9,2.2,1.9]）、
标题（cap_20261014_164522）与"帧 x/27"写死；改它会改掉 PLANE-01 证据里记的 SHA。本文件按纪律
"新变体用新文件"：同一套渲染（三视图 + 去背景点 + 拖影衰减 + 黄色中心轨迹），只是范围/标题/帧数参数化，
并额外叠加 **KF/M-N 运动轨迹**（直接调参考算法的 `tbd_track.run_kf`，不自造平滑）。

用法：
    python -B -W error make_session_video.py --out <会话证据目录> --sid <sid> --job <job> \
        --empty-job <空场 job> --registration <registration 目录> [--name 23_TRACK_VIDEO.mp4] [--slow-loops 3]

输入：<out>/20_TRACK_V2.json（v2 检测/跟踪）、<out>/30_TBD_TRACK.json（取"运动确认"轨迹 id）。
输出：<out>/<name>（MP4，10 fps，目标段插慢放循环）。
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

R01 = Path(__file__).resolve().parents[1] / "r01"
BIRD = Path(__file__).resolve().parents[3] / "Bird识别"
sys.path.insert(0, str(R01))
sys.path.insert(0, str(BIRD))

from background import (apply_transform, background_keys, collect_points,   # noqa: E402
                        foreground_mask, load_points)
import tbd_track                                                            # noqa: E402


def picked_points(source):
    """逐帧取"自由空间（离最近静态点 ≥0.2 m）且非已知泄漏、≥8 点"的最大簇（与页面/PLANE-01 同判据）。"""
    points_by_frame = {}
    for row in source["frames"]:
        for candidate in row["candidates"]:
            if candidate.get("free_space") and not candidate.get("near_known_leak") \
                    and candidate.get("point_count", 0) >= 8 and candidate.get("points"):
                points_by_frame[row["frame"]] = np.asarray(candidate["points"])
                break
    return points_by_frame


def kf_trajectories(job, empty_job, registration, start_frame=0):
    """复用参考算法的 KF/M-N：返回 {track_id: {frame: position}} 与 30 号 JSON 里"运动确认"的 id 集合。

    只记**本帧真的命中**的位置（`misses == 0`），不把纯预测/coasting 的帧画进轨迹；
    `start_frame` 与产物口径一致（142416 用 100），这样轨迹 id 与 `30/31_*.json` 对得上。
    """
    registration_json = json.loads((Path(registration) / "registration.json").read_text(encoding="utf8"))
    target_frames, _ = load_points(job, "tls")
    target_frames = [frame for frame in target_frames if frame[0] >= start_frame]
    empty_frames, _ = load_points(empty_job, "tls")
    empty_registered = apply_transform(empty_frames, registration_json["rotation_row_major"],
                                       registration_json["translation_m"])
    empty_points = collect_points(empty_registered, stride=2)
    keys, origin, base = background_keys(empty_points, tbd_track.CELL_M)
    frames = []
    for index, stamp, xyz, _values in target_frames:
        finite = np.isfinite(xyz).all(axis=1)
        points = xyz[finite]
        mask = foreground_mask(points, keys, origin, base, tbd_track.CELL_M)
        frames.append((index, stamp, tbd_track.frame_candidates(points[mask], empty_points)))
    rows, finished = tbd_track.run_kf(frames)
    positions = {}
    for row in rows:
        for track in row["tracks"]:
            if track["misses"] == 0:          # 本帧命中才算轨迹点
                positions.setdefault(track["id"], {})[row["frame"]] = np.asarray(track["position"])
    moving = {track["id"]: track for track in finished if track["moving"] and track["confirmed"]}
    return positions, moving


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--sid", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--empty-job", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--track", default="20_TRACK_V2.json")
    parser.add_argument("--name", default="23_TRACK_VIDEO.mp4")
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--slow-loops", type=int, default=3)
    parser.add_argument("--start-frame", type=int, default=0,
                        help="KF 轨迹与产物口径对齐用的起始帧（142416 用 100；绘图仍按 --track 里的帧窗口）")
    parser.add_argument("--no-kf", action="store_true", help="不叠加 KF 运动轨迹（只看去背景跟踪）")
    args = parser.parse_args()
    out = Path(args.out)
    source = json.loads((out / args.track).read_text(encoding="utf8"))
    frames = source["frames"]
    track = {row["frame"]: row for row in source["track"]}
    points_by_frame = picked_points(source)

    positions, moving = ({}, {})
    if not args.no_kf:
        positions, moving = kf_trajectories(args.job, args.empty_job, args.registration,
                                            start_frame=args.start_frame)

    detected = [row for row in source["track"] if row["detected"]]
    centers = {row["frame"]: np.asarray(row["center"]) for row in detected}
    speed_by_frame = {}
    for i, row in enumerate(detected):
        speeds = []
        if i + 1 < len(detected):
            delta = np.asarray(detected[i + 1]["center"]) - np.asarray(row["center"])
            dt = detected[i + 1]["stamp_s"] - row["stamp_s"]
            speeds.append(float(np.linalg.norm(delta) / dt) if dt > 0 else 0.0)
        if i > 0:
            delta = np.asarray(row["center"]) - np.asarray(detected[i - 1]["center"])
            dt = row["stamp_s"] - detected[i - 1]["stamp_s"]
            speeds.append(float(np.linalg.norm(delta) / dt) if dt > 0 else 0.0)
        speed_by_frame[row["frame"]] = min(speeds) if speeds else 0.0

    # 视图范围：全部被跟踪到的点 + 中心 + KF 位置，四边留 0.4 m
    cloud = [p for p in points_by_frame.values()]
    cloud += [c.reshape(1, 3) for c in centers.values()]
    for series in positions.values():
        if series:
            cloud += [np.asarray(list(series.values()))]
    stacked = np.vstack(cloud) if cloud else np.zeros((1, 3))
    lo = stacked.min(axis=0) - 0.4
    hi = stacked.max(axis=0) + 0.4
    for axis in range(3):
        if hi[axis] - lo[axis] < 1.2:
            mid = (hi[axis] + lo[axis]) / 2
            lo[axis], hi[axis] = mid - 0.6, mid + 0.6
    if lo[2] < 0.0:            # 让地面 z=0 尽量留在画面里
        lo[2] = max(lo[2], -0.35)

    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter

    figure, axes = plt.subplots(1, 3, figsize=(13.5, 5.2))
    pairs = [(0, 1, "x [m]", "y [m]", "俯视 x-y"), (0, 2, "x [m]", "z [m]", "侧视 x-z"),
             (1, 2, "y [m]", "z [m]", "前视 y-z")]
    first_frame, last_frame = frames[0]["frame"], frames[-1]["frame"]

    def draw(frame_index, banner):
        position = frames[frame_index]["frame"]
        for axis, (i, j, ni, nj, title) in zip(axes, pairs):
            axis.clear()
            axis.set_xlim(lo[i], hi[i]); axis.set_ylim(lo[j], hi[j])
            axis.set_xlabel(ni); axis.set_ylabel(nj); axis.set_title(title)
            axis.grid(alpha=0.25)
            if j == 2:
                axis.axhline(0.0, color="#3a4a58", lw=1)
            for past in range(first_frame, position):
                if past in points_by_frame:
                    fade = 0.10 + 0.35 * ((past - first_frame) / max(1, position - first_frame))
                    axis.scatter(points_by_frame[past][:, i], points_by_frame[past][:, j],
                                 s=10, color="#ff6b6b", alpha=fade)
            if position in points_by_frame:
                q = points_by_frame[position]
                axis.scatter(q[:, i], q[:, j], s=42, color="#ff2d2d", zorder=5,
                             edgecolors="#ffd7d7", linewidths=0.5)
            if len(centers) > 1:
                ordered = [c for f, c in sorted(centers.items()) if f <= position]
                if len(ordered) > 1:
                    axis.plot([c[i] for c in ordered], [c[j] for c in ordered], "-",
                              color="#f2c14e", lw=1.6, zorder=4)
            if position in centers:
                axis.scatter([centers[position][i]], [centers[position][j]], s=130,
                             facecolors="none", edgecolors="#f2c14e", linewidths=2, zorder=6)
            for track_id, series in sorted(positions.items()):
                if track_id not in moving:
                    continue
                seen = [(f, p) for f, p in sorted(series.items()) if f <= position]
                if len(seen) > 1:
                    axis.plot([p[i] for _f, p in seen], [p[j] for _f, p in seen], "-",
                              color="#37d7ff", lw=1.8, zorder=7)
                    axis.scatter([seen[-1][1][i]], [seen[-1][1][j]], s=70, color="#37d7ff", zorder=8,
                                 edgecolors="#0b1a22", linewidths=0.6)
                    if (i, j) == (0, 1):     # 只在俯视图标一次轨迹名/速度，避免三视图重复
                        axis.annotate("#%d %.2f m/s" % (track_id, moving[track_id]["mean_speed_m_s"]),
                                      xy=(seen[-1][1][i], seen[-1][1][j]),
                                      xytext=(6, 4 + 11 * (track_id % 3)),
                                      textcoords="offset points", color="#37d7ff", fontsize=8, zorder=9)
        row = track.get(position, {})
        t = frames[frame_index]["stamp_s"] - frames[0]["stamp_s"]
        label = "帧 %d（第 %d/%d 帧）  t=%.2fs" % (position, frame_index + 1, len(frames), t)
        if row.get("detected"):
            text = "%s   目标: %d 点  %.2f m/s  强度 %.0f  离最近静态结构 %.2f m" % (
                label, row["point_count"], speed_by_frame.get(position, 0.0),
                row["intensity_median"], row["distance_to_empty_m"])
        else:
            text = "%s   未检出（该帧自由空间无 ≥8 点高亮簇）" % label
        moving_now = [tid for tid, series in positions.items()
                      if tid in moving and series and min(series) <= position <= max(series)]
        if moving_now:
            text += "   KF 运动轨迹 " + "、".join(
                "#%d（%.2f m/s）" % (tid, moving[tid]["mean_speed_m_s"]) for tid in sorted(moving_now))
        figure.suptitle("小目标跟踪 · %s · 去背景跟踪（房间已减去） · %s\n%s" % (args.sid, banner, text),
                        fontsize=12)
        figure.tight_layout(rect=[0, 0, 1, 0.92])

    object_frames = sorted(points_by_frame)
    first_object = object_frames[0] if object_frames else first_frame
    last_object = object_frames[-1] if object_frames else last_frame
    schedule = [(index, "完整 %d 帧 · 真速 10 Hz" % len(frames), 1) for index in range(len(frames))]
    for _loop in range(args.slow_loops):
        for index in range(max(0, first_object - first_frame - 1),
                           min(len(frames), last_object - first_frame + 3)):
            schedule.append((index, "目标段 0.5 倍慢放（源 10 Hz）", 2))

    target = out / args.name
    writer = FFMpegWriter(fps=args.fps, bitrate=4000, codec="libx264",
                          metadata={"title": "小目标跟踪 %s" % args.sid})
    with writer.saving(figure, str(target), dpi=110):
        for index, banner, repeat in schedule:
            for _ in range(repeat):
                draw(index, banner)
                writer.grab_frame()
    plt.close(figure)
    print(json.dumps({"video": str(target), "bytes": target.stat().st_size,
                      "written_frames": sum(r for _i, _b, r in schedule), "fps": args.fps,
                      "seconds": round(sum(r for _i, _b, r in schedule) / args.fps, 2),
                      "kf_tracks": {str(k): {"frames": [min(v), max(v)], "speed": round(v2["mean_speed_m_s"], 2)}
                                    for k, v in positions.items() if k in moving for v2 in [moving[k]]}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
