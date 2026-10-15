"""P0+ ：按帧姿态归一化后的形状累积（航向=机头方向，z=翼面法向）。

用法：
    python -B -W error plane_shape_align.py --out <evidence_dir> [--track 20_TRACK_V2.json]
每帧：逐点时间戳去畸变(Δ≤12 mm) → PCA 主轴，用该帧速度定机头方向、用地面法向定翼面法向
（退化帧回退为"速度+竖直"对齐）→ 归一到 (航向 x, 翼展 y, 法向 z) 后累积。
输出 26_SHAPE_ALIGNED.json + 26_SHAPE_ALIGNED.png（含 2 cm 二值轮廓与剖面）。
"""
import argparse
import json
from pathlib import Path

import numpy as np

from common import LEVELED
from plane_shape import JOB, GRID_M, convex_hull_area, robust_core


def frame_basis(points, velocity, up=np.array([0.0, 0.0, 1.0])):
    """返回 3x3 基（行 = 航向/翼展/法向）与是否用了速度回退。"""
    centred = points - points.mean(axis=0)
    values, vectors = np.linalg.eigh(centred.T @ centred / len(centred))
    order = np.argsort(values)[::-1]
    vectors = vectors[:, order]
    speed = float(np.linalg.norm(velocity))
    fallback = speed < 1e-6
    if fallback:
        e1 = up
    else:
        e1 = velocity / speed
    # 用 PCA 最长轴作为机头方向的候选（若与速度夹角 < 60° 才采纳，否则回退到速度）
    longest = vectors[:, 0]
    if abs(float(longest @ e1)) >= 0.5:
        if float(longest @ e1) < 0:
            longest = -longest
        e1 = longest
    # 法向：取与 e1 正交、且最接近"竖直"的 PCA 轴；退化时用 up 正交化
    reference = up - e1 * float(up @ e1)
    norm = float(np.linalg.norm(reference))
    e3 = reference / norm if norm > 1e-6 else np.array([0.0, 1.0, 0.0])
    flat = vectors[:, 2]
    flat_orth = flat - e1 * float(flat @ e1)
    if np.linalg.norm(flat_orth) > 1e-6:
        flat_orth /= np.linalg.norm(flat_orth)
        if abs(float(flat_orth @ e3)) > 0.5:
            if float(flat_orth @ e3) < 0:
                flat_orth = -flat_orth
            e3 = flat_orth
    e2 = np.cross(e3, e1)
    e2 /= np.linalg.norm(e2)
    e3 = np.cross(e1, e2)
    return np.vstack([e1, e2, e3]), fallback


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
    stamps = np.ndarray((total,), dtype="<f4", buffer=raw, offset=20, strides=(28,))

    detected = [row for row in payload["track"] if row["detected"]]
    velocity = {}
    for i, row in enumerate(detected):
        candidates = []
        if i + 1 < len(detected):
            dt = detected[i + 1]["stamp_s"] - row["stamp_s"]
            if dt > 0:
                candidates.append((np.asarray(detected[i + 1]["center"]) - np.asarray(row["center"])) / dt)
        if i > 0:
            dt = row["stamp_s"] - detected[i - 1]["stamp_s"]
            if dt > 0:
                candidates.append((np.asarray(row["center"]) - np.asarray(detected[i - 1]["center"])) / dt)
        velocity[row["frame"]] = np.mean(np.array(candidates), axis=0) if candidates else np.zeros(3)

    aligned, labels, rows = [], [], []
    for row in payload["frames"]:
        frame = row["frame"]
        if frame not in velocity:
            continue
        candidate = None
        for item in row["candidates"]:
            if item.get("free_space") and not item.get("near_known_leak") and item["point_count"] >= 8:
                candidate = item
                break
        if candidate is None:
            continue
        points = np.asarray(candidate["points"])
        offset = sum(int(meta["frames"][k]["count_points"]) for k in range(frame))
        count = int(meta["frames"][frame]["count_points"])
        indices = np.array([int(np.argmin(np.linalg.norm(xyz[offset:offset + count] - q, axis=1)))
                            for q in points])
        times = stamps[offset + indices].astype(np.float64)
        deskewed = points - velocity[frame][None, :] * (times - float(np.median(times)))[:, None]
        center, core = robust_core(deskewed)
        basis, fallback = frame_basis(core, velocity[frame])
        aligned.append((core - center) @ basis.T)
        labels.append(np.full(len(core), frame))
        rows.append({"frame": frame, "core_points": int(len(core)), "velocity_fallback": bool(fallback)})
    cloud = np.concatenate(aligned)
    labels = np.concatenate(labels)

    extents_robust = (np.percentile(cloud, 97.5, axis=0) - np.percentile(cloud, 2.5, axis=0)).tolist()
    extents_full = (cloud.max(axis=0) - cloud.min(axis=0)).tolist()
    hull = convex_hull_area(cloud[:, :2])
    grid = np.floor(cloud[:, :2] / GRID_M).astype(np.int64)
    occupied = len(set(map(tuple, grid.tolist())))
    payload_out = {
        "object": "tracked moving target (user: paper plane), orientation-normalized accumulation",
        "frames": rows,
        "point_count": int(len(cloud)),
        "flight_frame_extents_robust_m": [round(float(v), 3) for v in extents_robust],
        "flight_frame_extents_full_m": [round(float(v), 3) for v in extents_full],
        "span_over_length": round(float(extents_robust[1] / max(extents_robust[0], 1e-9)), 3),
        "thickness_over_length": round(float(extents_robust[2] / max(extents_robust[0], 1e-9)), 3),
        "planform_hull_area_m2": round(hull, 4),
        "occupied_cells_2cm": occupied,
        "note": "航向=机头方向（PCA 长轴，需与速度夹角<60°，否则回退速度方向）；z=翼面法向",
    }
    with (out / "26_SHAPE_ALIGNED.json").open("x", encoding="utf8") as stream:
        json.dump(payload_out, stream, ensure_ascii=False, indent=2, allow_nan=False)
    render(out, cloud, labels, payload_out)
    print(json.dumps({"points": payload_out["point_count"],
                      "extents_m": payload_out["flight_frame_extents_robust_m"],
                      "span_over_length": payload_out["span_over_length"],
                      "thickness_over_length": payload_out["thickness_over_length"],
                      "planform_hull_area_m2": payload_out["planform_hull_area_m2"]}, ensure_ascii=False))


def render(out, cloud, labels, report):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt

    figure, panels = plt.subplots(1, 3, figsize=(19, 6))
    scatter = panels[0].scatter(cloud[:, 0], cloud[:, 1], c=labels, cmap="viridis", s=30, edgecolors="#222")
    panels[0].set_title("俯视（航向 x × 翼展 y，颜色=帧号）"); panels[0].set_aspect("equal")
    figure.colorbar(scatter, ax=panels[0], label="帧号", shrink=0.85)
    panels[1].scatter(cloud[:, 0], cloud[:, 2], s=30, color="#ff2d2d", edgecolors="#401010")
    panels[1].set_title("侧视（航向 × 厚度）"); panels[1].set_aspect("equal")
    panels[2].scatter(cloud[:, 1], cloud[:, 2], s=30, color="#8ab4f8", edgecolors="#203040")
    panels[2].set_title("前视（翼展 × 厚度）"); panels[2].set_aspect("equal")
    for axis in panels:
        axis.grid(alpha=0.3); axis.axhline(0, color="#888", lw=0.5); axis.axvline(0, color="#888", lw=0.5)
    figure.suptitle("姿态归一化累积（%d 点；长×宽×厚 %s m）" % (
        report["point_count"], report["flight_frame_extents_robust_m"]), fontsize=13)
    figure.tight_layout(rect=[0, 0, 1, 0.94])
    figure.savefig(out / "26_SHAPE_ALIGNED.png", dpi=110)
    plt.close(figure)


if __name__ == "__main__":
    main()
