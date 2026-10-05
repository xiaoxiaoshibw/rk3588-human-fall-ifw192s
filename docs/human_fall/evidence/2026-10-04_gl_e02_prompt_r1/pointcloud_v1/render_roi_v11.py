# -*- coding: utf-8 -*-
"""
GL-E02 ROI 标注 v11 / 用户确认变换后的静态渲染
================================================
变换 (2026-10-04 浏览器内用户确认):
  A 方向: R_y(+26°)   [user: "A是对的"]
  高度:   tz = +1.340 m  [user: "+1.340 m 最合适记录一下"]

  X_w = c*x + s*z
  Y_w = y
  Z_w = -s*x + c*z + tz
  (c=cos(26°), s=sin(26°))

输出:
  annotated_pointcloud_v11.png   俯视图, 全点按 Z 着色 + 4 ROI + 玄矢条
  annotated_pointcloud_v11.meta.json
"""
import json
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_BIN  = os.path.join(HERE, "points.bin")
OUT_PNG  = os.path.join(HERE, "annotated_pointcloud_v11.png")
OUT_META = os.path.join(HERE, "annotated_pointcloud_v11.meta.json")

STRIDE = 28
PITCH_DEG = 26.0
TZ = 1.340                     # 用户对格校准值 (annotator v11 滑杆)

ROIS = [
    {"id":"#1 FIT_near",     "color":(46,204,113),  "X":(0.6,1.2), "Y":(-0.4,0.4)},
    {"id":"#2 VAL_mid_near", "color":(241,196,15),  "X":(1.3,1.8), "Y":(-0.5,0.5)},
    {"id":"#3 VAL_mid_far",  "color":(230,126,34),  "X":(1.9,2.4), "Y":(-0.5,0.5)},
    {"id":"#4 VAL_far",      "color":(155,89,182),  "X":(2.7,3.4), "Y":(-0.5,0.5)},
]
POWER_STRIP = (2.50, 2.55)

def load_points(path):
    raw = open(path, "rb").read()
    n = len(raw) // STRIDE
    buf = np.frombuffer(raw, dtype=np.uint8)[: n * STRIDE].reshape(n, STRIDE)
    xyzi = buf[:, :16].copy().view(np.float32)
    return xyzi[:, 0], xyzi[:, 1], xyzi[:, 2], xyzi[:, 3]

def main():
    xs, ys, zs, ig = load_points(SRC_BIN)
    print(f"loaded {len(xs)} points")

    a = np.deg2rad(PITCH_DEG)
    c, s = np.cos(a), np.sin(a)
    Xw = c * xs + s * zs
    Yw = ys
    Zw = -s * xs + c * zs + TZ

    print(f"world bbox: X[{Xw.min():.2f},{Xw.max():.2f}] "
          f"Y[{Yw.min():.2f},{Yw.max():.2f}] Z[{Zw.min():.2f},{Zw.max():.2f}]")

    # 地板带: |Z| < 0.15m
    floor = np.abs(Zw) < 0.15
    Xf, Yf, Zf = Xw[floor], Yw[floor], Zw[floor]
    print(f"floor band points: {len(Xf)} / {len(Xw)}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    fig, ax = plt.subplots(figsize=(12, 12), dpi=110)
    sc = ax.scatter(Yf, Xf, c=Zf, cmap="RdYlGn", vmin=-0.15, vmax=0.15,
                    s=0.6, alpha=0.6, linewidths=0, marker='.', rasterized=True)
    plt.colorbar(sc, ax=ax, label="Z_world (m) — floor should be 0")

    ax.set_xlabel("Y_world (m, lateral)")
    ax.set_ylabel("X_world (m, forward)")
    ax.set_title(f"GL-E02 v11 | user-confirmed: R_y(+26deg), tz=+1.340m | "
                 f"floor band {len(Xf)} pts (of {len(Xw)})")
    ax.grid(True, alpha=0.25, linestyle=":")
    ax.set_aspect("equal", adjustable="box")

    # 雷达原点
    ax.plot(0, 0, marker="^", markersize=18, color="deepskyblue",
            markeredgecolor="white", markeredgewidth=1.5)
    ax.text(0.08, 0.05, "lidar origin", fontsize=11, color="deepskyblue", weight="bold")

    # 玄矢条
    ax.axhspan(POWER_STRIP[0], POWER_STRIP[1], color=(1,0,1), alpha=0.22,
               label=f"power strip {POWER_STRIP[0]}-{POWER_STRIP[1]}m")
    for xv in POWER_STRIP:
        ax.axhline(xv, color=(1,0,1), linewidth=1.5, alpha=0.95)

    # ROI
    for r in ROIS:
        X0, X1 = r["X"]; Y0, Y1 = r["Y"]
        rect = mpatches.Rectangle((Y0, X0), Y1-Y0, X1-X0, linewidth=2.0,
                                  edgecolor=np.array(r["color"])/255,
                                  facecolor=np.array(r["color"])/255, alpha=0.30)
        ax.add_patch(rect)
        cy, cx = (Y0+Y1)/2, (X0+X1)/2
        ax.text(cy, cx, r["id"], fontsize=13, weight="bold",
                color=np.array(r["color"])/255, ha="center", va="center",
                bbox=dict(facecolor='black', alpha=0.6, pad=4,
                          edgecolor=np.array(r["color"])/255))
        mask = (Xf>=X0)&(Xf<=X1)&(Yf>=Y0)&(Yf<=Y1)
        r["points_inside"] = int(mask.sum())

    ax.legend(loc="upper right", fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=110)
    print(f"OUT: {OUT_PNG}")

    meta = {
        "schema_version": "1.0",
        "kind": "gle02_roi_pointcloud_annotation",
        "version": "v11",
        "transform_user_confirmed": {
            "rotation": "A: R_y(+26deg)",
            "tz_m": TZ,
            "confirmed_at": "2026-10-04T17:5x+08:00 (annotator.html v11 slider)",
            "confirmed_by": "user on-site visual alignment",
            "physical_verified": False,
            "note": "tz for flat floor ≈ mount height; cross-check at FIELD_CHECKLIST §2"
        },
        "source": {
            "session_id": "cap_20261002_233210",
            "points_sha256": "d946b80b51258e4e0452fc3a40f9ebd7b47c9b3edac25df7aeb1c6ea9f322664",
            "frames_merged": 99, "total_points": int(len(xs)),
            "floor_band_points": int(len(Xf)), "floor_band_tol_m": 0.15,
        },
        "roi_definitions": [
            {"roi_id": r["id"], "X_range_m": list(r["X"]), "Y_range_m": list(r["Y"]),
             "points_inside_floor_band": r["points_inside"],
             "color_rgb": list(r["color"])} for r in ROIS
        ],
        "power_strip": {"X_range_m": list(POWER_STRIP)},
        "version_history": [
            {"v":"v7","issue":"histogram-mode floor z; lidar x treated as world x"},
            {"v":"v8","issue":"wrong rotation sign/tz; points off floor"},
            {"v":"v10","issue":"identity transform experiment wrongly concluded SDK-leveled"},
            {"v":"v11","fix":"user-confirmed A=R_y(+26), tz=+1.340 on annotator.html"}
        ]
    }
    with open(OUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"META: {OUT_META}")

if __name__ == "__main__":
    main()
