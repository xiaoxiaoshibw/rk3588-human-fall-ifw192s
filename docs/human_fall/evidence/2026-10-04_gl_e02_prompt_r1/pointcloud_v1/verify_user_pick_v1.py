# -*- coding: utf-8 -*-
"""
GL-E02 用户框选区 #1 验证 / user_pick_fit_v1
================================================
用户在 annotator v11 中框选:
  X_range_m: [1.022, 1.773]
  Y_range_m: [-0.952, -0.432]
  user 判断: "这一块平"

本脚本:
  1. 载入 4863787 点, 施加已确认变换 (A: R_y(+26°), tz=+1.340)
  2. 取框内点, 算 Z 分布 / 平面拟合残差 (给"平"一个数)
  3. 2x2 图: 俯视(带框) / Z直方图 / Z-X 散点 / Z-Y 散点
  4. 存 meta json 记录本次框选为证据
"""
import json
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_BIN  = os.path.join(HERE, "points.bin")
OUT_PNG  = os.path.join(HERE, "user_pick_fit_v1.png")
OUT_META = os.path.join(HERE, "user_pick_fit_v1.meta.json")

STRIDE = 28
PITCH_DEG = 26.0
TZ = 1.340

PICK = {"X": (1.022, 1.773), "Y": (-0.952, -0.432)}

def load_points(path):
    raw = open(path, "rb").read()
    n = len(raw) // STRIDE
    buf = np.frombuffer(raw, dtype=np.uint8)[: n * STRIDE].reshape(n, STRIDE)
    xyzi = buf[:, :16].copy().view(np.float32)
    return xyzi[:, 0], xyzi[:, 1], xyzi[:, 2]

def main():
    xs, ys, zs = load_points(SRC_BIN)
    a = np.deg2rad(PITCH_DEG)
    c, s = np.cos(a), np.sin(a)
    Xw = c * xs + s * zs
    Yw = ys
    Zw = -s * xs + c * zs + TZ

    # 框内选择 (世界系)
    X0, X1 = PICK["X"]; Y0, Y1 = PICK["Y"]
    inbox = (Xw >= X0) & (Xw <= X1) & (Yw >= Y0) & (Yw <= Y1)
    Xi, Yi, Zi = Xw[inbox], Yw[inbox], Zw[inbox]
    n_in = len(Xi)
    print(f"points in box: {n_in}")

    # ── Z 统计 ────────────────────────────────────────────────
    if n_in == 0:
        print("EMPTY BOX — nothing to report")
        return
    p5, p25, p50, p75, p95 = np.percentile(Zi, [5, 25, 50, 75, 95])
    # 主簇: |Z-p50| < 0.2
    core = np.abs(Zi - p50) < 0.2
    n_core = int(core.sum())
    z_std_core = float(Zi[core].std()) if n_core > 10 else float("nan")

    # 平面拟合: Z = a + bX + cY (全点 + 去离群再拟合)
    def plane_fit_rms(X, Y, Z, label):
        A = np.column_stack([np.ones_like(X), X, Y])
        coef, *_ = np.linalg.lstsq(A, Z, rcond=None)
        res = Z - A @ coef
        rms = float(np.sqrt((res ** 2).mean()))
        print(f"  plane fit [{label}]: Z = {coef[0]:.4f} + {coef[1]:.4f}*X + {coef[2]:.4f}*Y, RMS={rms:.4f} m, n={len(X)}")
        return coef, res, rms

    print("Z stats (m): P5 %.3f P25 %.3f P50 %.3f P75 %.3f P95 %.3f" % (p5, p25, p50, p75, p95))
    print(f"core cluster (|Z-P50|<0.2): n={n_core}, std={z_std_core:.4f}")
    coef_all, res_all, rms_all = plane_fit_rms(Xi, Yi, Zi, "all")
    keep = np.abs(res_all) < 0.15
    if keep.sum() > 10:
        coef_k, res_k, rms_k = plane_fit_rms(Xi[keep], Yi[keep], Zi[keep], "trim15cm")
    else:
        coef_k, rms_k = coef_all, rms_all
        print("  (trim insufficient, using all)")

    # ── 渲染 2x2 ──────────────────────────────────────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    # 俯视近邻区域
    near = (Xw >= -0.5) & (Xw <= 3.5) & (Yw >= -2.0) & (Yw <= 1.5)
    Xn, Yn, Zn = Xw[near], Yw[near], Zw[near]

    fig, axes = plt.subplots(2, 2, figsize=(14, 12), dpi=100)

    # A) 俯视
    ax = axes[0][0]
    sc = ax.scatter(Yn, Xn, c=Zn, cmap="RdYlGn", vmin=-0.15, vmax=0.15,
                    s=0.6, alpha=0.5, linewidths=0, marker='.', rasterized=True)
    plt.colorbar(sc, ax=ax, label="Z (m)")
    rect = mpatches.Rectangle((Y0, X0), Y1-Y0, X1-X0, linewidth=2.5,
                              edgecolor='cyan', facecolor='cyan', alpha=0.25)
    ax.add_patch(rect)
    ax.text((Y0+Y1)/2, (X0+X1)/2, "YOUR PICK", color='cyan', fontsize=12,
            weight='bold', ha='center', va='center')
    ax.plot(0, 0, marker="^", markersize=14, color="deepskyblue")
    ax.set_xlabel("Y (m, lateral)"); ax.set_ylabel("X (m, forward)")
    ax.set_title("Top view (near field)")
    ax.grid(True, alpha=0.25, linestyle=":"); ax.set_aspect("equal")

    # B) Z 直方图
    ax = axes[0][1]
    ax.hist(Zi, bins=80, range=(-1.0, 1.0), color='steelblue', alpha=0.8)
    ax.axvline(0, color='r', linewidth=1.5, label="Z=0 (floor plane)")
    ax.axvline(p50, color='orange', linewidth=1.5, linestyle="--", label=f"median {p50:.3f}")
    ax.set_xlabel("Z (m)"); ax.set_ylabel("count")
    ax.set_title(f"Z histogram in box (n={n_in})")
    ax.legend()

    # C) Z vs X
    ax = axes[1][0]
    ax.scatter(Xi, Zi, s=1.0, alpha=0.4, marker='.', rasterized=True)
    ax.axhline(0, color='r', linewidth=1)
    ax.axhline(p50, color='orange', linestyle="--", linewidth=1)
    ax.set_xlabel("X (m)"); ax.set_ylabel("Z (m)")
    ax.set_ylim(-0.6, 0.6)
    ax.set_title("Z vs X within box (tilt check)")
    ax.grid(True, alpha=0.25, linestyle=":")

    # D) Z vs Y
    ax = axes[1][1]
    ax.scatter(Yi, Zi, s=1.0, alpha=0.4, marker='.', rasterized=True)
    ax.axhline(0, color='r', linewidth=1)
    ax.axhline(p50, color='orange', linestyle="--", linewidth=1)
    ax.set_xlabel("Y (m)"); ax.set_ylabel("Z (m)")
    ax.set_ylim(-0.6, 0.6)
    ax.set_title("Z vs Y within box (tilt check)")
    ax.grid(True, alpha=0.25, linestyle=":")

    fig.suptitle(f"User pick #1 — X[1.022,1.773] Y[-0.952,-0.432] — "
                 f"plane RMS(all)={rms_all:.4f} m, RMS(trim)={rms_k:.4f} m", fontsize=12)
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=100)
    print("OUT:", OUT_PNG)

    # ── meta ─────────────────────────────────────────────────
    meta = {
        "schema_version": "1.0",
        "kind": "gle02_user_roi_pick",
        "pick_id": "user_pick_fit_v1",
        "status": "USER_PICKED_FLATNESS_MEASURED",
        "picked_via": "annotator.html v11 picker (2-point box)",
        "picked_at_local": None,   # 由调用方补
        "transform": {"rotation": "A: R_y(+26deg)", "tz_m": TZ,
                       "source": "user-confirmed 2026-10-04"},
        "source": {"session_id": "cap_20261002_233210",
                    "points_sha256": "d946b80b51258e4e0452fc3a40f9ebd7b47c9b3edac25df7aeb1c6ea9f322664",
                    "frames_merged": 99},
        "box_world_m": {"X_range": list(PICK["X"]), "Y_range": list(PICK["Y"])},
        "user_statement": "这一块平 (this block is flat) — chosen as ROI",
        "measurements": {
            "n_points_in_box": n_in,
            "Z_p5_p25_p50_p75_p95": [float(p5), float(p25), float(p50), float(p75), float(p95)],
            "core_cluster_n": n_core,
            "core_cluster_Z_std_m": z_std_core,
            "plane_fit_all": {"coef_a_bX_cY": [float(v) for v in coef_all],
                               "rms_m": rms_all},
            "plane_fit_trim15cm": {"coef_a_bX_cY": [float(v) for v in coef_k],
                                    "rms_m": rms_k},
        },
        "interpretation": "z_std_core is the empirical flatness of the user's pick "
                           "under the user-confirmed transform; compare with "
                           "GL-E02 P2 gate |residual|P95 <= 0.05m",
        "physical_verified": False,
    }
    with open(OUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("META:", OUT_META)

if __name__ == "__main__":
    main()
