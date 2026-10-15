"""视觉自查：把目标"去拖影"后看它的截面形状（沿运动方向看过去的投影）。

原理：帧内滚动把目标沿运动方向拉成划痕；取垂直运动方向的平面投影，拖影自动塌缩，
剩下的是目标横截面轮廓（同时用颜色标出点在轨迹上的位置=拖影程度）。

用法：
    python -B -W error look_object.py --out <evidence_dir>
读取 20_TRACK_V2.json，输出：
  21_OBJECT_SHAPE.png   逐帧截面（帧 9–15）+ 全帧对齐叠加
  21_OBJECT_SHAPE_ZOOM.png  把核心点单独放大（对齐叠加，看是否有结构）
"""
import argparse
import json
from pathlib import Path

import numpy as np

CORE_RADIUS_M = 0.18


def perpendicular_basis(direction):
    reference = np.array([0.0, 0.0, 1.0]) if abs(direction[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    p1 = np.cross(direction, reference)
    p1 /= np.linalg.norm(p1)
    p2 = np.cross(direction, p1)
    return p1, p2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--track", default="20_TRACK_V2.json")
    args = parser.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt

    out = Path(args.out)
    payload = json.loads((out / args.track).read_text(encoding="utf8"))
    track = {row["frame"]: row for row in payload["track"] if row["detected"]}
    picked = {}
    for row in payload["frames"]:
        for candidate in row["candidates"]:
            if candidate.get("free_space") and not candidate.get("near_known_leak") \
                    and candidate["point_count"] >= 8 and candidate.get("desmear"):
                picked[row["frame"]] = candidate
                break

    figure, axes = plt.subplots(2, 4, figsize=(19, 9))
    all_p1, all_p2, all_frame = [], [], []
    for slot, frame in enumerate(sorted(picked)):
        candidate = picked[frame]
        points = np.asarray(candidate["points"])
        direction = np.asarray(candidate["desmear"]["motion_direction"])
        p1, p2 = perpendicular_basis(direction)
        centered = points - np.asarray(candidate["center"])
        along = centered @ direction
        u = centered @ p1
        v = centered @ p2
        axis = axes.reshape(-1)[slot]
        scatter = axis.scatter(u, v, c=along, s=70, cmap="coolwarm", edgecolors="#333")
        axis.set_aspect("equal"); axis.grid(alpha=0.3)
        axis.set_title("帧 %d  n=%d  截面跨度 %.2f×%.2f m" % (
            frame, len(points), u.max() - u.min(), v.max() - v.min()), fontsize=11)
        axis.set_xlabel("垂直轴 1 [m]"); axis.set_ylabel("垂直轴 2 [m]")
        figure.colorbar(scatter, ax=axis, label="沿轨位置 [m]", shrink=0.85)
        all_p1.append(u); all_p2.append(v); all_frame.append(np.full(len(u), frame))

    axis = axes.reshape(-1)[len(picked)]
    axis.set_aspect("equal"); axis.grid(alpha=0.3)
    flat_p1 = np.concatenate(all_p1); flat_p2 = np.concatenate(all_p2)
    flat_frame = np.concatenate(all_frame)
    scatter = axis.scatter(flat_p1, flat_p2, c=flat_frame, s=45, cmap="viridis", edgecolors="#333")
    axis.set_title("全帧对齐叠加（按稳健中心，颜色=帧号）", fontsize=11)
    axis.set_xlabel("垂直轴 1 [m]"); axis.set_ylabel("垂直轴 2 [m]")
    figure.colorbar(scatter, ax=axis, label="帧号", shrink=0.85)
    for slot in range(len(picked) + 1, 8):
        axes.reshape(-1)[slot].axis("off")
    figure.suptitle("PLANE-01 目标横截面（沿运动方向看，拖影已塌缩；颜色=点在划痕内的位置）", fontsize=14)
    figure.tight_layout(rect=[0, 0, 1, 0.95])
    figure.savefig(out / "21_OBJECT_SHAPE.png", dpi=110)
    plt.close(figure)

    # 放大版：只用稳健核点，对齐叠加 + 单帧并排
    figure, axes = plt.subplots(1, 4, figsize=(19, 5.4))
    for axis, frame in zip(axes, sorted(picked)):
        candidate = picked[frame]
        points = np.asarray(candidate["points"])
        center = np.asarray(candidate["center"])
        direction = np.asarray(candidate["desmear"]["motion_direction"])
        p1, p2 = perpendicular_basis(direction)
        centred = points - center
        core = np.linalg.norm(centred, axis=1) <= CORE_RADIUS_M
        u = centred[core] @ p1
        v = centred[core] @ p2
        axis.scatter(u, v, s=110, color="#ff2d2d", edgecolors="#661111")
        axis.set_aspect("equal"); axis.grid(alpha=0.3)
        axis.set_title("帧 %d 核心截面 %.2f×%.2f m" % (frame, u.max() - u.min(), v.max() - v.min()), fontsize=11)
        axis.set_xlabel("垂直轴 1 [m]"); axis.set_ylabel("垂直轴 2 [m]")
    figure.suptitle("核心点截面放大（0.18 m 稳健核；看是否有翼/尾等结构）", fontsize=13)
    figure.tight_layout(rect=[0, 0, 1, 0.93])
    figure.savefig(out / "21_OBJECT_SHAPE_ZOOM.png", dpi=110)
    plt.close(figure)
    spans = {}
    for frame in sorted(picked):
        candidate = picked[frame]
        points = np.asarray(candidate["points"])
        direction = np.asarray(candidate["desmear"]["motion_direction"])
        p1, p2 = perpendicular_basis(direction)
        centred = points - np.asarray(candidate["center"])
        u = centred @ p1
        v = centred @ p2
        spans[str(frame)] = {"n": int(len(points)),
                             "span_p1_m": round(float(u.max() - u.min()), 3),
                             "span_p2_m": round(float(v.max() - v.min()), 3)}
    print(json.dumps({"frames": sorted(picked), "cross_spans": spans}, ensure_ascii=False))


if __name__ == "__main__":
    main()
