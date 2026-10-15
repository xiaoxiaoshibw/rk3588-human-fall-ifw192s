"""视觉自查（运动期全形态）：瞬态前景并集 + 相对稳健中心的对齐投影。

用法：
    python -B -W error look_union.py --out <evidence_dir>
输出：
  22_UNION_MOVING.png   运动期(帧8-17)每帧瞬态前景并集，三视图按帧着色 + 轨迹
  22_UNION_ALIGNED.png  同批点相对各自帧稳健中心，投影到(沿轨, 垂直轴1/2)，看横向展布
背景=10-13 空场(131958) 经既有 registration.js PASS 变换；前景=0.08 m 网格 ±1 格内无空场点。
"""
import argparse
import json
from pathlib import Path

import numpy as np


def perpendicular_basis(direction):
    reference = np.array([0.0, 0.0, 1.0]) if abs(direction[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    p1 = np.cross(direction, reference)
    p1 /= np.linalg.norm(p1)
    return p1, np.cross(direction, p1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--track", default="20_TRACK_V2.json")
    parser.add_argument("--registration", default="03_REGISTRATION_131958_to_164522")
    parser.add_argument("--frames", default="8,17")
    parser.add_argument("--radius-m", type=float, default=1.4)
    args = parser.parse_args()
    low, high = (int(v) for v in args.frames.split(","))
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt

    from background import apply_transform, background_keys, collect_points, foreground_mask, load_points

    out = Path(args.out)
    registration = json.loads((out / args.registration / "registration.json").read_text(encoding="utf8"))
    payload = json.loads((out / args.track).read_text(encoding="utf8"))
    track = {row["frame"]: row for row in payload["track"] if row["detected"]}
    directions = {}
    for row in payload["frames"]:
        for candidate in row["candidates"]:
            if candidate.get("desmear") and candidate["point_count"] >= 8 \
                    and candidate.get("free_space") and not candidate.get("near_known_leak"):
                directions[row["frame"]] = np.asarray(candidate["desmear"]["motion_direction"])
                break

    target_frames, _tmeta = load_points("363473a9e2e64649994dca11b2b26929", "tls")
    empty_frames, _emeta = load_points("61cb6976b0f8479394641850d9a7c6ca", "tls")
    empty_registered = apply_transform(empty_frames, registration["rotation_row_major"],
                                       registration["translation_m"])
    keys, origin, base = background_keys(collect_points(empty_registered, stride=2), 0.08)

    union, frame_of, centred, along, perp1_all, perp2_all = [], [], [], [], [], []
    for index, _stamp, xyz, _values in target_frames:
        if index < low or index > high or index not in track:
            continue
        finite = np.isfinite(xyz).all(axis=1)
        points = xyz[finite]
        mask = foreground_mask(points, keys, origin, base, 0.08)
        center = np.asarray(track[index]["center"])
        near = points[mask][np.linalg.norm(points[mask] - center, axis=1) <= args.radius_m]
        if not len(near):
            continue
        direction = directions.get(index, np.array([1.0, 0.0, 0.0]))
        p1, p2 = perpendicular_basis(direction)
        offset = near - center
        union.append(near)
        frame_of.append(np.full(len(near), index))
        centred.append(offset)
        along.append(offset @ direction)
        perp1_all.append(offset @ p1)
        perp2_all.append(offset @ p2)

    union = np.concatenate(union); frame_of = np.concatenate(frame_of)
    centred = np.concatenate(centred)
    along = np.concatenate(along); perp1_all = np.concatenate(perp1_all)
    perp2_all = np.concatenate(perp2_all)
    centers = sorted(track)
    center_points = np.array([track[f]["center"] for f in centers])

    figure, axes = plt.subplots(1, 3, figsize=(19, 6))
    pairs = [(0, 1, "x", "y"), (0, 2, "x", "z"), (1, 2, "y", "z")]
    for axis, (i, j, ni, nj) in zip(axes, pairs):
        scatter = axis.scatter(union[:, i], union[:, j], c=frame_of, cmap="viridis", s=55,
                               edgecolors="#222")
        axis.plot(center_points[:, i], center_points[:, j], "-", color="#f2c14e", lw=1.2)
        axis.plot(center_points[:, i], center_points[:, j], "x", color="#f2c14e", ms=9)
        axis.set_xlabel(ni + " [m]"); axis.set_ylabel(nj + " [m]"); axis.grid(alpha=0.3)
        axis.set_aspect("equal")
        figure.colorbar(scatter, ax=axis, label="帧号", shrink=0.85)
    figure.suptitle("运动期(帧 %d–%d)每帧中心 %.1f m 内全部瞬态前景点并集（每个点只出现在 1–2 帧）"
                    % (low, high, args.radius_m), fontsize=13)
    figure.tight_layout(rect=[0, 0, 1, 0.95])
    figure.savefig(out / "22_UNION_MOVING.png", dpi=110)
    plt.close(figure)

    figure, axes = plt.subplots(1, 3, figsize=(18, 6))
    panels = [(along, perp1_all, "沿轨 [m]", "垂直轴 1 [m]"), (along, perp2_all, "沿轨 [m]", "垂直轴 2 [m]"),
              (perp1_all, perp2_all, "垂直轴 1 [m]", "垂直轴 2 [m]")]
    for axis, (a, b, la, lb) in zip(axes, panels):
        scatter = axis.scatter(a, b, c=frame_of, cmap="viridis", s=45, edgecolors="#222")
        axis.axhline(0, color="#888", lw=0.6); axis.axvline(0, color="#888", lw=0.6)
        axis.set_xlabel(la); axis.set_ylabel(lb); axis.grid(alpha=0.3); axis.set_aspect("equal")
        figure.colorbar(scatter, ax=axis, label="帧号", shrink=0.85)
    figure.suptitle("同批点相对各自帧稳健中心的投影：沿轨方向=帧内拖影方向；垂直向=目标真实横向展布", fontsize=13)
    figure.tight_layout(rect=[0, 0, 1, 0.95])
    figure.savefig(out / "22_UNION_ALIGNED.png", dpi=110)
    plt.close(figure)

    stats = {
        "points": int(len(union)),
        "along_range_m": [round(float(along.min()), 3), round(float(along.max()), 3)],
        "perp1_range_m": [round(float(perp1_all.min()), 3), round(float(perp1_all.max()), 3)],
        "perp2_range_m": [round(float(perp2_all.min()), 3), round(float(perp2_all.max()), 3)],
        "center_distance_max_m": round(float(np.linalg.norm(centred, axis=1).max()), 3),
    }
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
