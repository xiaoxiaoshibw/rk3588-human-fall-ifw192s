# -*- coding: utf-8 -*-
"""
GL-E02 ROI 标注 v7 / 全录制叠加 + 4 ROI + 用户手绘紫框
============================================================
数据源 : cap_20261002_233210 (99 帧, 4863787 点)
         已从板端 sha256 校验拉取,源 sha256 = d946b80b51258e4e...

GL-E01 A05 部分解除: user 已声明 "雷达位置 = 今日拍摄紫框位置",
即 10/2 录制时位姿 = 10/4 现场位姿 → 录制几何可用于今日 sticker placement.

输出:
  annotated_pointcloud_v7.png        2D 点云投影 + 紫框 + 4 ROI 外加 RARING 标记
  annotated_pointcloud_v7.meta.json  数值表 + 每 ROI 内点数 + 范围
"""
import json
import os
import struct
import math

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_BIN  = os.path.join(HERE, "points.bin")
SRC_META = os.path.join(HERE, "meta.json")
OUT_PNG  = os.path.join(HERE, "annotated_pointcloud_v7.png")
OUT_META = os.path.join(HERE, "annotated_pointcloud_v7.meta.json")

# ── 点布局 (来自 meta.json) ────────────────────────────────────
# fields: x, y, z, intensity, ring(u2), timestamp(f4) ; pad 2B at offset 18,22
# stride_bytes = 28
STRIDE = 28

def load_points(path):
    """Read .bin -> N x 4 float32 numpy array (x, y, z, intensity)."""
    raw = open(path, "rb").read()
    n = len(raw) // STRIDE
    print(f"loading {n} points (file {len(raw)} bytes, stride {STRIDE})")
    xs = np.empty(n, dtype=np.float32)
    ys = np.empty(n, dtype=np.float32)
    zs = np.empty(n, dtype=np.float32)
    ints = np.empty(n, dtype=np.float32)
    # 用 struct.unpack 太慢(486 万 * 6) → 用 numpy frombuffer + stride
    buf = np.frombuffer(raw, dtype=np.uint8)
    buf = buf[: n * STRIDE].reshape(n, STRIDE)
    # 各字段字节偏移: x=[0:4], y=[4:8], z=[8:12], intensity=[12:16],
    # ring=[16:18]<u2, ts=[18:22], pad [22:28]=6B? 实际是 stride 28,
    # 文档说 pad_offsets_bytes=[18,24] — reinterpretation.
    # 安全做法:只取前 16 字节为 4 个 float32.
    xyzi = buf[:, :16].copy().view(np.float32)
    xs = xyzi[:, 0]; ys = xyzi[:, 1]; zs = xyzi[:, 2]; ints = xyzi[:, 3]
    return xs, ys, zs, ints

# ── 4 个 ROI 在雷达坐标系中的定义 (单位: 米) ──────────────────
# 你陈述: 雷达正前 = +x ; 左右 = ±y ; 上 = +z
# 玄关条(电源走线 xing) ≈ 2.50-2.55 m (你是 ground truth)
# 雷达高度未知 → 用 z 范围做粗筛 (-0.2 ~ +0.2 是"地面"窗口)
# 实际位置:紫色紫框 = 雷达脚前到机器人脚前
ROIS = [
    # (id,            color,        x_range,        y_range,       note)
    {"id":"#1 FIT_near",
     "color":(46, 204, 113),  # green
     "x":(0.5, 1.2),   "y":(-0.4, 0.4),
     "note":"FIT, nearest sticker"},
    {"id":"#2 VAL_mid_near",
     "color":(241, 196, 15),  # amber
     "x":(1.2, 1.8),   "y":(-0.5, 0.5),
     "note":"VAL near-mid"},
    {"id":"#3 VAL_mid_far",
     "color":(230, 126, 34),  # orange
     "x":(1.8, 2.4),   "y":(-0.5, 0.5),
     "note":"VAL far-mid, stops before power strip"},
    {"id":"#4 VAL_far",
     "color":(155, 89, 182),  # purple
     "x":(2.7, 3.4),   "y":(-0.5, 0.5),
     "note":"VAL far, PAST the 2.55m power-strip line"},
]

# 用户画的紫框(已知):
POWER_STRIP_X_MIN = 2.50
POWER_STRIP_X_MAX = 2.55

# 地板 z 窗口(粗估):相对雷达原点在地面上下的范围
GROUND_Z_RANGE = (-1.4, -0.8)   # 预设雷达约 1.0-1.3m 高
                                # 我们在画图时会先打印实际 z 分布,必要时调整

def main():
    xs, ys, zs, ints = load_points(SRC_BIN)
    print(f"point stats: x [{xs.min():.2f},{xs.max():.2f}] "
          f"y [{ys.min():.2f},{ys.max():.2f}] "
          f"z [{zs.min():.2f},{zs.max():.2f}]")

    # ── 按高度找地板 ─────────────────────────────────────────
    # 简单:与众数 z (地面) 距离 < 0.25m 的算地面点
    hist, edges = np.histogram(zs, bins=100)
    z_floor = edges[np.argmax(hist)]
    print(f"floor z estimate (histogram mode) = {z_floor:.3f}")
    ground_mask = np.abs(zs - z_floor) < 0.18
    xg, yg, zg, ig = xs[ground_mask], ys[ground_mask], zs[ground_mask], ints[ground_mask]
    print(f"ground points kept: {len(xg)} / {len(xs)}")

    # ── 取前方点云 (x > 0) ────────────────────────────────────
    fwd = xg > 0.1
    xg, yg, zg, ig = xg[fwd], yg[fwd], zg[fwd], ig[fwd]
    print(f"forward ground points: {len(xg)}")

    # ── 简单渲染: x vs y 投影, 颜色按 intensity ──────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 12), dpi=110)
    # 背景点云
    sc = ax.scatter(yg, xg, c=zg, s=0.3, cmap="viridis",
                    alpha=0.55, linewidths=0, marker='.', rasterized=True)
    plt.colorbar(sc, ax=ax, label="z (m, height in lidar frame)")

    ax.set_xlabel("y (m)  (lateral, +y = image left)")
    ax.set_ylabel("x (m)  (forward along lidar +x)")
    ax.set_title("cap_20261002_233210 - 99 frames merged - floor points only "
                 f"({len(xg)} pts from {len(xs)})")
    ax.grid(True, alpha=0.25, linestyle=":")
    ax.set_aspect("equal", adjustable="box")

    # 紫框 = 电源走线两条线
    for x_line in (POWER_STRIP_X_MIN, POWER_STRIP_X_MAX):
        ax.axhline(x_line, color=(1.0, 0.0, 1.0), linewidth=1.8, linestyle="-", alpha=0.95)
    ax.axhspan(POWER_STRIP_X_MIN, POWER_STRIP_X_MAX, color=(1.0, 0.0, 1.0), alpha=0.15,
               label=f"power-strip zone (user-measured 2.50-2.55m)")

    # 4 个 ROI
    for r in ROIS:
        # x = forward, y = lateral; 图上 y=横轴, x=纵轴
        x0, x1 = r["x"]; y0, y1 = r["y"]
        # 像素范围 (画面上 y 横, x 纵)
        rect_y = (y0, x0)
        w = y1 - y0; h = x1 - x0
        import matplotlib.patches as mpatches
        rect = mpatches.Rectangle(rect_y, w, h,
                                  linewidth=2.0, edgecolor=np.array(r["color"])/255.0,
                                  facecolor=np.array(r["color"])/255.0, alpha=0.30)
        ax.add_patch(rect)
        # 中心 label
        cy = (y0 + y1) / 2
        cx = (x0 + x1) / 2
        ax.text(cy, cx, r["id"], fontsize=14, weight="bold",
                color=np.array(r["color"])/255.0,
                ha="center", va="center",
                bbox=dict(facecolor='black', alpha=0.6, pad=4,
                          edgecolor=np.array(r["color"])/255.0))
        # 数 ROI 内点数
        mask = (xg >= x0) & (xg <= x1) & (yg >= y0) & (yg <= y1)
        r["points_inside"] = int(mask.sum())

    ax.legend(loc="upper right", fontsize=9)

    # 雷达位置
    ax.plot(0, 0, marker="^", markersize=16, color="deepskyblue",
            markeredgecolor="white", markeredgewidth=1.5)
    ax.text(0.05, 0.02, "lidar", fontsize=11, color="deepskyblue", weight="bold")

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=110)
    print(f"OUT: {OUT_PNG}")

    # ── 元数据 ────────────────────────────────────────────────
    meta = {
        "schema_version": "1.0",
        "kind": "gle02_roi_pointcloud_annotation",
        "version": "v7",
        "source": {
            "bag_session_id": "cap_20261002_233210",
            "points_sha256": "d946b80b51258e4e0452fc3a40f9ebd7b47c9b3edac25df7aeb1c6ea9f322664",
            "meta_sha256":   "246170285a174d3859fbceed0c8b780b4f976d2237adc4b8c11dcbe6ebb4d648",
            "frames_merged": 99,
            "total_points": int(len(xs)),
            "ground_points_kept": int(len(xg)),
            "floor_z_estimate": float(z_floor),
            "ground_z_window": [float(z_floor - 0.18), float(z_floor + 0.18)],
        },
        "binding_to_field_today": {
            "claim": "user stated radar pose @ 10/02 recording == radar pose @ 10/04 today",
            "implication_for_GL_E01_A05": "PARTIALLY_UNBLOCKED",
            "physical_verified": False,
            "note": "lidar has not been moved since 10/02 recording per user statement; "
                    "measurement_record.install_unchanged_since can be 2026-10-02",
        },
        "power_strip_geom_ref": {
            "x_range": [POWER_STRIP_X_MIN, POWER_STRIP_X_MAX],
            "user_description": "电源走线 (power cable conduit), no height step, geometric reference only",
            "user_measured_distance_m": 2.5,
        },
        "roi_definitions": [
            {
                "roi_id": r["id"],
                "x_range_m": list(r["x"]),
                "y_range_m": list(r["y"]),
                "note": r["note"],
                "points_inside": r["points_inside"],
                "color": list(r["color"]),
            } for r in ROIS
        ],
        "rendering": {
            "color_scheme": "z (height) via viridis",
            "projection": "top-down (y lateral, x forward)",
            "alpha": 0.55,
            "size_pt": 0.3,
        },
        "physical_verified": False,
        "next_actions": [
            "User prints annotated_pointcloud_v7.png to field",
            "Place Zone-FIT-01 .. Zone-VAL-03 stickers at field per ROIs",
            "Laser-rangefinder: lidar origin -> each sticker x3",
            "Record actual distances into measurement_record.json",
        ],
    }
    with open(OUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"META: {OUT_META}")


if __name__ == "__main__":
    main()
