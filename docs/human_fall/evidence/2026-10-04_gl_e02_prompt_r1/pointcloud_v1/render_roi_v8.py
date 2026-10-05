# -*- coding: utf-8 -*-
"""
GL-E02 ROI 标注 v8 / 真配平 + 4 ROI + 玄矢条
=============================================
v8 纠正 v7 的两个错误:
  1) v7 用直方图众数当地板 z → 错;v8 用真实安装几何 (h=1.1m, α=26°)
  2) v7 把"lidar x"当"世界 x" → 错;v8 先做 R_y(−26°) 旋转再平移 −(0,0,1.1)

物理几何(user-provided ground truth):
  - 雷达原点位于世界坐标 (0, 0, +1.1) m — 地板上方 1.1 m
  - 安装时下俯角约 26°,即雷达 +x 沿"略向下的视线"指向正前
  - 世界系地板 = {z_world = 0} 平面

雷达系 (x, y, z) → 世界系 (X, Y, Z) 的转换:
  p_world = R_y(−α) · p_lidar − (0, 0, 1.1)
  其中 R_y(−α) 表示"把 +x 由向下斜指的视线旋回到水平"

手续:
  1) 加载全部 4863787 点
  2) 旋转 + 平移到世界系
  3) 取 z_world ∈ [−0.10, +0.10] m 的点 = 地板薄板
  4) 在 (X, Y) 平面画 4 ROI + 电源走线槽条带
  5) 输出 meta + annotated_pointcloud_v8.png
"""
import json
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_BIN  = os.path.join(HERE, "points.bin")
OUT_PNG  = os.path.join(HERE, "annotated_pointcloud_v8.png")
OUT_META = os.path.join(HERE, "annotated_pointcloud_v8.meta.json")

# ── 用户提供的安装几何 (GROUND TRUTH) ─────────────────────────
MOUNT_HEIGHT_M = 1.1        # 雷达原点距地板
MOUNT_PITCH_DEG = 26.0      # 安装下俯角(+x 朝前下方)

# ── 用户提供的玄矢条位置(世界系 X) ───────────────────────────
POWER_STRIP_X = (2.50, 2.55)

# ── 4 ROI 定义 (现在都是"世界系"下的米) ─────────────────────
ROIS = [
    # 矩形 x_range × y_range,全部在世界地板坐标中
    {"id":"#1 FIT_near",     "color":(46,204,113),
     "X":(0.6, 1.2),   "Y":(-0.4, 0.4),
     "note":"FIT, closest to lidar"},
    {"id":"#2 VAL_mid_near", "color":(241,196,15),
     "X":(1.3, 1.8),   "Y":(-0.5, 0.5),
     "note":"VAL mid-near"},
    {"id":"#3 VAL_mid_far",  "color":(230,126,34),
     "X":(1.9, 2.4),   "Y":(-0.5, 0.5),
     "note":"VAL mid-far, before power strip"},
    {"id":"#4 VAL_far",      "color":(155,89,182),
     "X":(2.7, 3.4),   "Y":(-0.5, 0.5),
     "note":"VAL far, past power strip"},
]

STRIDE = 28

def load_points(path):
    raw = open(path, "rb").read()
    n = len(raw) // STRIDE
    buf = np.frombuffer(raw, dtype=np.uint8)
    buf = buf[: n * STRIDE].reshape(n, STRIDE)
    xyzi = buf[:, :16].copy().view(np.float32)
    return xyzi[:, 0], xyzi[:, 1], xyzi[:, 2], xyzi[:, 3]

def lidar_to_world(x, y, z):
    """雷达系点 → 世界系点.世界系: +X=沿雷达视向水平, +Y=左, +Z=上.
    雷达安装: 原点 (0,0,1.1), 下俯 α=26°.
    p_world = R_y(−α) · p_lidar − (0, 0, 1.1)
    """
    a = np.deg2rad(MOUNT_PITCH_DEG)
    ca, sa = np.cos(a), np.sin(a)
    # R_y(−α) 作用在 (x, z) 平面
    X = ca * x + sa * z
    Y = y
    Z = -sa * x + ca * z
    # 平移:雷达原点在世界上 z=+1.1
    Z = Z + MOUNT_HEIGHT_M
    return X, Y, Z

def main():
    xs, ys, zs, ints = load_points(SRC_BIN)
    print(f"loaded {len(xs)} points")
    print(f"lidar frame bbox: x[{xs.min():.2f},{xs.max():.2f}] "
          f"y[{ys.min():.2f},{ys.max():.2f}] "
          f"z[{zs.min():.2f},{zs.max():.2f}]")

    # ── 配平:雷达系 → 世界系 ────────────────────────────────
    Xs, Ys, Zs = lidar_to_world(xs, ys, zs)
    print(f"world frame bbox: X[{Xs.min():.2f},{Xs.max():.2f}] "
          f"Y[{Ys.min():.2f},{Ys.max():.2f}] "
          f"Z[{Zs.min():.2f},{Zs.max():.2f}]")

    # ── 取地板薄板: z ∈ [-0.10, +0.10] m ─────────────────────
    FLOOR_Z_TOL = 0.10
    floor_mask = (Zs > -FLOOR_Z_TOL) & (Zs < FLOOR_Z_TOL)
    Xf, Yf, Zf = Xs[floor_mask], Ys[floor_mask], Zs[floor_mask]
    print(f"floor points (|Zw| < {FLOOR_Z_TOL}): {len(Xf)} / {len(Xs)}")

    # ── 只取前面 +X > 0.3 m (避开雷达正下盲区) ────────────────
    fwd = Xf > 0.3
    Xf, Yf, Zf = Xf[fwd], Yf[fwd], Zf[fwd]
    print(f"forward floor points: {len(Xf)}")

    # ── 渲染 ────────────────────────────────────────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    fig, ax = plt.subplots(figsize=(11, 11), dpi=110)
    sc = ax.scatter(Yf, Xf, c=Zf, s=0.5, cmap="RdYlGn",
                    vmin=-0.10, vmax=+0.10,
                    alpha=0.55, linewidths=0, marker='.', rasterized=True)
    plt.colorbar(sc, ax=ax, label="Z_world residual (m, floor should be 0)")

    ax.set_xlabel("Y_world (m, lateral)")
    ax.set_ylabel("X_world (m, forward)")
    ax.set_title(f"v8 | balanced to world frame (h={MOUNT_HEIGHT_M}m, pitch={MOUNT_PITCH_DEG}deg) | "
                 f"99 frames, {len(Xf)} floor pts")
    ax.grid(True, alpha=0.25, linestyle=":")
    ax.set_aspect("equal", adjustable="box")

    # 雷达在原点
    ax.plot(0, 0, marker="^", markersize=18, color="deepskyblue",
            markeredgecolor="white", markeredgewidth=1.5)
    ax.text(0.05, 0.1, "lidar (origin)", fontsize=11,
            color="deepskyblue", weight="bold")

    # 玄矢条(电源走线槽)
    ax.axhspan(POWER_STRIP_X[0], POWER_STRIP_X[1],
               color=(1.0, 0.0, 1.0), alpha=0.22,
               label=f"power strip {POWER_STRIP_X[0]}-{POWER_STRIP_X[1]}m (user-measured)")
    for xv in POWER_STRIP_X:
        ax.axhline(xv, color=(1.0, 0.0, 1.0), linewidth=1.6, alpha=0.95)

    # 4 个 ROI
    for r in ROIS:
        X0, X1 = r["X"]; Y0, Y1 = r["Y"]
        rect = mpatches.Rectangle((Y0, X0), Y1 - Y0, X1 - X0,
                                  linewidth=2.0,
                                  edgecolor=np.array(r["color"])/255.0,
                                  facecolor=np.array(r["color"])/255.0,
                                  alpha=0.30)
        ax.add_patch(rect)
        cx, cy = (X0 + X1) / 2, (Y0 + Y1) / 2
        ax.text(cy, cx, r["id"], fontsize=14, weight="bold",
                color=np.array(r["color"])/255.0,
                ha="center", va="center",
                bbox=dict(facecolor='black', alpha=0.6, pad=4,
                          edgecolor=np.array(r["color"])/255.0))
        # 数 ROI 内点数
        mask = (Xf >= X0) & (Xf <= X1) & (Yf >= Y0) & (Yf <= Y1)
        r["points_inside"] = int(mask.sum())

    ax.legend(loc="upper right", fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=110)
    print(f"OUT: {OUT_PNG}")

    # ── 数值表 ──────────────────────────────────────────────
    meta = {
        "schema_version": "1.0",
        "kind": "gle02_roi_pointcloud_annotation",
        "version": "v8",
        "corrections_from_v7": [
            "Use user-provided mount geometry h=1.1m, pitch=26deg (not histogram mode)",
            "Rotate lidar frame to world frame via R_y(-pitch) and translate -1.1m in z",
            "Floor plate = world |Zw| < 0.10 m (not 'z near histogram mode')",
        ],
        "mount_geometry_user_provided": {
            "height_m": MOUNT_HEIGHT_M,
            "pitch_deg": MOUNT_PITCH_DEG,
            "source": "user verbal statement, not yet formal FIELD_CHECKLIST §2/§3 measurement",
            "physical_verified": False,
        },
        "power_strip": {
            "X_range_world_m": list(POWER_STRIP_X),
            "user_measured_distance_m": 2.5,
        },
        "source": {
            "bag_session_id": "cap_20261002_233210",
            "points_sha256": "d946b80b51258e4e0452fc3a40f9ebd7b47c9b3edac25df7aeb1c6ea9f322664",
            "frames_merged": 99,
            "total_points": int(len(xs)),
            "floor_points": int(len(Xf)),
            "floor_z_tol_m": FLOOR_Z_TOL,
        },
        "roi_definitions": [
            {
                "roi_id": r["id"],
                "X_range_world_m": list(r["X"]),
                "Y_range_world_m": list(r["Y"]),
                "note": r["note"],
                "points_inside": r["points_inside"],
                "color_rgb": list(r["color"]),
            } for r in ROIS
        ],
        "rendering": {
            "color_scheme": "Z_world residual via RdYlGn",
            "projection": "top-down (Y lateral, X forward)",
        },
        "next_physical_steps": [
            "User measures mount height/angle formally per FIELD_CHECKLIST §2/§3",
            "Replace h=1.1 deg=26 with measured values when available",
            "Place stickers Zone-FIT-01 .. Zone-VAL-03 at field",
            "Laser-rangefinder distance from origin to each sticker x3",
        ],
        "version_history": [
            {"v": "v7", "issue": "Used histogram mode for floor z, treated lidar x as world x — both wrong"},
            {"v": "v8", "fix": "Proper leveling: R_y(-26) rotation + 1.1m translate, floor plate = |Zw| < 0.10"},
        ],
    }
    with open(OUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"META: {OUT_META}")


if __name__ == "__main__":
    main()
