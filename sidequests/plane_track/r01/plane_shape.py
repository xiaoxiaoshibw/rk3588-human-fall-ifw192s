"""P0 落地：逐点时间戳去畸变 + 运动补偿累积 + 形状特征（纸飞机口径）。

用法：
    python -B -W error plane_shape.py --out <evidence_dir> [--track 20_TRACK_V2.json]

输入：captures/leveled/<job>/tls（只读；28B 布局：intensity@12, ring@16, u16; timestamp@20, f4）
      20_TRACK_V2.json（稳健核中心/运动方向）
流程：
  1) 去畸变：每点按自身 timestamp 相对帧内参考时刻，用该帧速度把点平移回同一时刻
     （p' = p − v·(t − t_ref)）；本段拖影实测 ≤5.5 cm，这一步主要是把跨帧形状对齐做干净。
  2) 运动补偿累积：把每帧目标点减去该帧稳健中心 → 叠到"物体坐标系"。
  3) 形状特征：PCA 轴长（2.5–97.5 分位与全量）、厚长比、平面形/凸包面积、2 cm 栅格占有率；
     运动学：滑翔比、速度/加速度、俯仰角。
输出：25_SHAPE_FEATURES.json + 25_SHAPE_ACCUM.png + 25_SHAPE_SILHOUETTE.png
"""
import argparse
import json
from pathlib import Path

import numpy as np

from common import LEVELED

JOB = "363473a9e2e64649994dca11b2b26929"
FRAME_PERIOD_S = 0.103
CORE_RADIUS_M = 0.18
GRID_M = 0.02


def convex_hull_area(points_2d):
    """Monotone chain + shoelace（numpy 实现，无 scipy）。"""
    order = np.lexsort((points_2d[:, 1], points_2d[:, 0]))
    unique = points_2d[order]
    if len(unique) < 3:
        return 0.0

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in unique[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    hull = np.array(lower[:-1] + upper[:-1])
    if len(hull) < 3:
        return 0.0
    x, y = hull[:, 0], hull[:, 1]
    return float(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def robust_core(points, radius=CORE_RADIUS_M):
    center = np.median(points, axis=0)
    for _ in range(4):
        distance = np.linalg.norm(points - center, axis=1)
        core = points[distance <= radius]
        if len(core) < 3:
            break
        updated = np.median(core, axis=0)
        if np.allclose(updated, center, atol=1e-6):
            center = updated
            break
        center = updated
    return center, core


def pca_extents(points):
    centred = points - points.mean(axis=0)
    values, vectors = np.linalg.eigh(centred.T @ centred / len(centred))
    basis = vectors[:, np.argsort(values)[::-1]]
    local = centred @ basis
    low, high = np.percentile(local, [2.5, 97.5], axis=0)
    return {
        "axes": basis,
        "extent_robust_m": (high - low).tolist(),
        "extent_full_m": (local.max(axis=0) - local.min(axis=0)).tolist(),
        "local": local,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--track", default="20_TRACK_V2.json")
    parser.add_argument("--job", default=JOB)
    args = parser.parse_args()
    out = Path(args.out)
    directory = LEVELED / args.job / "tls"
    meta = json.loads((directory / "meta.json").read_text(encoding="utf8"))
    payload = json.loads((out / args.track).read_text(encoding="utf8"))
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    total = int(meta["total_points"])
    xyz = np.ndarray((total, 3), dtype="<f4", buffer=raw, strides=(28, 4)).astype(np.float64)
    ring = np.ndarray((total,), dtype="<u2", buffer=raw, offset=16, strides=(28,))
    stamps = np.ndarray((total,), dtype="<f4", buffer=raw, offset=20, strides=(28,))

    track = {row["frame"]: row for row in payload["track"] if row["detected"]}
    detected = [row for row in payload["track"] if row["detected"]]
    velocity = {}
    for i, row in enumerate(detected):
        candidates = []
        if i + 1 < len(detected):
            delta = np.asarray(detected[i + 1]["center"]) - np.asarray(row["center"])
            dt = detected[i + 1]["stamp_s"] - row["stamp_s"]
            if dt > 0:
                candidates.append(delta / dt)
        if i > 0:
            delta = np.asarray(row["center"]) - np.asarray(detected[i - 1]["center"])
            dt = row["stamp_s"] - detected[i - 1]["stamp_s"]
            if dt > 0:
                candidates.append(delta / dt)
        velocity[row["frame"]] = np.mean(np.array(candidates), axis=0) if candidates else np.zeros(3)

    frames_report, stack_core, stack_all, labels = [], [], [], []
    for row in payload["frames"]:
        frame = row["frame"]
        if frame not in track:
            continue
        candidate = None
        for item in row["candidates"]:
            if item.get("free_space") and not item.get("near_known_leak") and item["point_count"] >= 8:
                candidate = item
                break
        if candidate is None:
            continue
        center = np.asarray(candidate["center"])
        points = np.asarray(candidate["points"])
        offset = sum(int(meta["frames"][k]["count_points"]) for k in range(frame))
        count = int(meta["frames"][frame]["count_points"])
        indices = np.array([int(np.argmin(np.linalg.norm(xyz[offset:offset + count] - q, axis=1)))
                            for q in points])
        times = stamps[offset + indices].astype(np.float64)
        reference = float(np.median(times))
        shift = velocity[frame][None, :] * (times - reference)[:, None]
        deskewed = points - shift
        _, core = robust_core(deskewed)
        frames_report.append({
            "frame": frame,
            "points": int(len(points)),
            "time_span_s": round(float(times.max() - times.min()), 5),
            "deskew_max_shift_m": round(float(np.linalg.norm(shift, axis=1).max()), 5),
            "velocity_m_s": [round(float(v), 3) for v in velocity[frame]],
            "core_points": int(len(core)),
            "ring_range": [int(ring[offset + indices].min()), int(ring[offset + indices].max())],
        })
        stack_core.append(core - np.median(core, axis=0))
        free = [item for item in row["candidates"]
                if item.get("free_space") and item["point_count"] >= 5]
        for item in free:
            stack_all.append(np.asarray(item["points"]) - center)
            labels.append(np.full(item["point_count"], frame))
    core_cloud = np.concatenate(stack_core)
    all_cloud = np.concatenate(stack_all)

    core_pca = pca_extents(core_cloud)
    all_pca = pca_extents(all_cloud)
    core_2d = core_pca.pop("local")[:, :2]
    all_2d = all_pca.pop("local")[:, :2]
    grid = np.floor(core_cloud / GRID_M).astype(np.int64)
    occupied = len(set(map(tuple, grid.tolist())))

    trajectory = np.array([track[f]["center"] for f in sorted(track)])
    horizontal = float(np.linalg.norm(trajectory[-1][:2] - trajectory[0][:2]))
    drop = float(trajectory[0][2] - trajectory[-1][2])
    speeds = [float(np.linalg.norm(velocity[f])) for f in sorted(track)]
    acceleration = None
    if len(detected) > 2:
        first = np.linalg.norm(velocity[detected[0]["frame"]])
        last = np.linalg.norm(velocity[detected[-1]["frame"]])
        acceleration = (last - first) / max(detected[-1]["stamp_s"] - detected[0]["stamp_s"], 1e-9)

    report = {
        "object": "tracked moving target (user: paper plane), cap_20261014_164522",
        "de_skew": {"model": "p' = p - v*(t - t_ref), t from per-point timestamp",
                    "note": "时间戳 1 ms 量化；本段拖影 ≤5.5 cm"},
        "frames": frames_report,
        "core_shape": {
            "point_count": int(len(core_cloud)),
            "extent_robust_m": [round(float(v), 3) for v in core_pca["extent_robust_m"]],
            "extent_full_m": [round(float(v), 3) for v in core_pca["extent_full_m"]],
            "thickness_over_length": round(float(core_pca["extent_robust_m"][2] / max(core_pca["extent_robust_m"][0], 1e-9)), 3),
            "width_over_length": round(float(core_pca["extent_robust_m"][1] / max(core_pca["extent_robust_m"][0], 1e-9)), 3),
            "projected_hull_area_m2": round(convex_hull_area(core_2d), 4),
            "occupied_cells_2cm": occupied,
            "occupied_cells_area_m2": round(occupied * GRID_M ** 2, 4),
        },
        "all_points_shape": {
            "point_count": int(len(all_cloud)),
            "extent_robust_m": [round(float(v), 3) for v in all_pca["extent_robust_m"]],
            "extent_full_m": [round(float(v), 3) for v in all_pca["extent_full_m"]],
            "projected_hull_area_m2": round(convex_hull_area(all_2d), 4),
            "note": "含此前被剔的‘同伴点’（同 tick 同 ring、离核心 0.6–0.7 m），归属 UNKNOWN，单列",
        },
        "kinematics": {
            "speed_m_s": [round(v, 3) for v in speeds],
            "acceleration_m_s2": None if acceleration is None else round(float(acceleration), 3),
            "horizontal_travel_m": round(horizontal, 3),
            "vertical_drop_m": round(drop, 3),
            "glide_ratio": None if drop <= 0 else round(float(horizontal / drop), 3),
            "duration_s": round(float(detected[-1]["stamp_s"] - detected[0]["stamp_s"]), 3),
        },
        "paper_plane_checklist": {
            "length_0.15_0.35m": bool(0.15 <= core_pca["extent_robust_m"][0] <= 0.35),
            "thin_0.05_0.15m": bool(0.05 <= core_pca["extent_robust_m"][2] <= 0.15),
            "flat_ratio_below_0.5": bool(core_pca["extent_robust_m"][2] / max(core_pca["extent_robust_m"][0], 1e-9) < 0.5),
            "no_flapping_periodicity": "NOT_RUN（7 帧/0.63 s，不足一个扑翼周期统计）",
            "no_propeller_harmonics": "NOT_RUN（本传感器无微多普勒）",
        },
    }
    with (out / "25_SHAPE_FEATURES.json").open("x", encoding="utf8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    render(out, core_cloud, all_cloud, labels, core_pca["axes"], report)
    print(json.dumps({"core_points": report["core_shape"]["point_count"],
                      "extent_robust_m": report["core_shape"]["extent_robust_m"],
                      "hull_area_m2": report["core_shape"]["projected_hull_area_m2"],
                      "glide_ratio": report["kinematics"]["glide_ratio"],
                      "deskew_max_m": max(f["deskew_max_shift_m"] for f in frames_report)},
                     ensure_ascii=False))


def render(out, core_cloud, all_cloud, labels, axes, report):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt

    figure, panels = plt.subplots(1, 3, figsize=(19, 6))
    local = core_cloud @ axes
    pairs = [(0, 1, "主轴 1(长) [m]", "主轴 2(宽) [m]"), (0, 2, "主轴 1(长) [m]", "主轴 3(厚) [m]"),
             (1, 2, "主轴 2(宽) [m]", "主轴 3(厚) [m]")]
    for axis, (i, j, ni, nj) in zip(panels, pairs):
        axis.scatter(local[:, i], local[:, j], s=28, color="#ff2d2d", edgecolors="#401010")
        axis.set_xlabel(ni); axis.set_ylabel(nj); axis.grid(alpha=0.3); axis.set_aspect("equal")
    figure.suptitle("纸飞机形状（7 帧去畸变后按稳健中心累积到物体坐标系，主轴分解；n=%d）"
                    % report["core_shape"]["point_count"], fontsize=13)
    figure.tight_layout(rect=[0, 0, 1, 0.94])
    figure.savefig(out / "25_SHAPE_ACCUM.png", dpi=110)
    plt.close(figure)

    figure, panels = plt.subplots(1, 3, figsize=(19, 6))
    x, y = local[:, 0], local[:, 1]
    lo_x, hi_x = np.percentile(x, [1, 99]); lo_y, hi_y = np.percentile(y, [1, 99])
    bins_x = max(4, int((hi_x - lo_x) / GRID_M) + 1)
    bins_y = max(4, int((hi_y - lo_y) / GRID_M) + 1)
    counts, _, _ = np.histogram2d(x, y, bins=[bins_x, bins_y], range=[[lo_x, hi_x], [lo_y, hi_y]])
    panels[0].imshow((counts > 0).T, origin="lower", cmap="gray_r",
                     extent=[lo_x, hi_x, lo_y, hi_y], aspect="equal")
    panels[0].set_title("俯视投影二值轮廓（2 cm 栅格）")
    panels[0].set_xlabel("主轴1(长) [m]"); panels[0].set_ylabel("主轴2(宽) [m]")
    panels[1].plot(np.sort(local[:, 0]), "-o", ms=3, label="主轴1 排序投影")
    panels[1].set_title("主轴 1 投影分布"); panels[1].grid(alpha=0.3); panels[1].set_xlabel("点序号")
    panels[1].set_ylabel("沿主轴1 [m]")
    panels[2].hist(local[:, 2], bins=14, color="#8ab4f8")
    panels[2].set_title("厚度方向分布（主轴 3）"); panels[2].set_xlabel("厚度 [m]"); panels[2].grid(alpha=0.3, axis="y")
    figure.suptitle("纸飞机轮廓/分布（核心 %s m；凸包面积 %.3f m²；厚长比 %.2f）" % (
        report["core_shape"]["extent_robust_m"], report["core_shape"]["projected_hull_area_m2"],
        report["core_shape"]["thickness_over_length"]), fontsize=13)
    figure.tight_layout(rect=[0, 0, 1, 0.94])
    figure.savefig(out / "25_SHAPE_SILHOUETTE.png", dpi=110)
    plt.close(figure)


if __name__ == "__main__":
    main()
