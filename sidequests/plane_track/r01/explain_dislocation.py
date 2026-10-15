"""解释"脱位"来源：帧内滚动拖影 vs 链式并簇 vs 配准残差（证据图）。

用法：
    python -B -W error explain_dislocation.py --out <evidence_dir>
读取 15_PLANE_FG_TRACK.json，输出 18_DISLOCATION_EXPLAINED.png：
  A) 每帧沿轨迹范围 vs v×0.103 s（帧内滚动模型）
  B) f12 / f14 点云：簇心 0.25 m 内（正常）与 >0.25 m（链式并入的离群点）分色
"""
import argparse
import json
from pathlib import Path

import numpy as np

CORE_RADIUS_M = 0.25
FRAME_PERIOD_S = 0.103


def load_points(payload):
    track = {row["frame"]: row for row in payload["track"] if row["detected"]}
    points = {}
    for row in payload.get("object_points", []):
        for candidate in row["candidates"]:
            if candidate["free_space"] and not candidate["near_known_leak"] and candidate["point_count"] >= 8:
                points[row["frame"]] = np.asarray(candidate["points"])
                break
    return track, points


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--track", default="15_PLANE_FG_TRACK.json")
    args = parser.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt

    out = Path(args.out)
    payload = json.loads((out / args.track).read_text(encoding="utf8"))
    track, points = load_points(payload)
    frames = sorted(points)

    extents, speeds = [], []
    for frame in frames:
        q = points[frame]
        center = np.asarray(track[frame]["center"])
        following = frame + 1 if frame + 1 in track else frame - 1
        direction = np.asarray(track[following]["center"]) - center
        direction = direction / np.linalg.norm(direction)
        projection = (q - center) @ direction
        extents.append(float(projection.max() - projection.min()))
        speed = track[frame]["speed_m_s"]
        speeds.append(float(speed if speed is not None else np.nan))

    figure, axes = plt.subplots(1, 3, figsize=(17, 5.4))
    predicted = np.array(speeds) * FRAME_PERIOD_S
    axes[0].plot([0, 1.2], [0, 1.2], "--", color="#888", lw=1)
    axes[0].scatter(predicted, extents, s=60, c=[plt.cm.viridis(f / 26) for f in frames])
    for frame, x, y in zip(frames, predicted, extents):
        axes[0].annotate(str(frame), (x, y), fontsize=9)
    axes[0].set_xlabel("v × 0.103 s  (帧内滚动模型) [m]")
    axes[0].set_ylabel("实测沿轨迹范围 [m]")
    axes[0].set_title("A 沿轨迹范围 ≈ 帧内滚动拖影\n(点=帧号, 虚线=1:1)")
    axes[0].grid(alpha=0.3)

    for axis, frame in zip(axes[1:], (12, 14)):
        q = points[frame]
        center = np.asarray(track[frame]["center"])
        distance = np.linalg.norm(q - center, axis=1)
        core = distance <= CORE_RADIUS_M
        axis.scatter(q[core, 0], q[core, 1], s=55, color="#ff2d2d", label="簇心 0.25 m 内（目标本体+拖影）")
        if (~core).any():
            axis.scatter(q[~core, 0], q[~core, 1], s=55, color="#ffa500",
                         label=">0.25 m（链式并入的离群点）")
            for point in q[~core]:
                axis.annotate("%.2f m" % float(np.linalg.norm(point - center)),
                              (point[0], point[1]), fontsize=8, color="#cc7a00")
        axis.scatter([center[0]], [center[1]], marker="x", s=90, color="#f2c14e", label="跟踪中心(中位数)")
        axis.set_xlabel("x [m]"); axis.set_ylabel("y [m]")
        axis.set_title("B 帧 %d：簇内 %d 点，其中离群 %d 点" % (frame, len(q), int((~core).sum())))
        axis.grid(alpha=0.3); axis.legend(fontsize=8, loc="lower right"); axis.set_aspect("equal")
    figure.suptitle("PLANE-01 \"脱位\"来源分解：帧内滚动拖影（主因）+ 0.3 m 网格链式并簇（离群点）", fontsize=13)
    figure.tight_layout(rect=[0, 0, 1, 0.94])
    figure.savefig(out / "18_DISLOCATION_EXPLAINED.png", dpi=110)
    plt.close(figure)
    print(json.dumps({"frames": frames, "extents": [round(v, 3) for v in extents],
                      "predicted": [None if not np.isfinite(v) else round(v, 3) for v in predicted],
                      "strays": {str(f): int((np.linalg.norm(points[f] - np.asarray(track[f]["center"]), axis=1)
                                              > CORE_RADIUS_M).sum()) for f in frames}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
