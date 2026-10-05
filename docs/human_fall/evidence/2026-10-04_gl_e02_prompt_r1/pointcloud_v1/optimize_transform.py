# -*- coding: utf-8 -*-
"""
GL-E02 配平参数联合反解 / optimize_transform.py
====================================================
目标: 利用 4 个用户框选地板区(共 ~23 万点), 联合反解最优 (pitch, roll, tz),
      使全部框内地板点的平面残差最小, 替换 "pitch=26°(口头估计)" 的粗糙值.

原理:
  - 真地板是平面; 正确配平后所有框内点 Z 应一致 (Z=0 平面).
  - 对当前变换后的框内点做平面拟合 Z = a + b*X + c*Y,
    斜率 (b, c) 即残余姿态误差: 额外旋转 omega = (-c, b, 0).
  - 迭代: pitch += deg(b), roll += deg(-c), 重建 R = Rx(roll) @ Ry(pitch),
    重算 tz 使框内点中位 Z 为 0. 收敛后输出最优参数.

关键设计: 点集冻结 (frozen indices)
  - 框是在"当前显示系"里框的; 旋转会轻微移动框的物理覆盖.
  - 为保证 before/after 对比用同一批点, 第一次选定后冻结索引,
    后续所有拟合/统计都用这批点.

输出:
  optimized_transform.json    最优参数 + 收敛历史 + 每框残差
  optimize_transform.png      优化后残差图 + 优化前后每框 |P95| 对比
"""
import json
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_BIN = os.path.join(HERE, "points.bin")
OUT_JSON = os.path.join(HERE, "optimized_transform.json")
OUT_PNG = os.path.join(HERE, "optimize_transform.png")

STRIDE = 28

# 初始参数 = 用户此前确认值
PITCH0, ROLL0, TZ0 = 26.0, 0.0, 1.340

# 用户框选 (显示系矩形; pick_04 已按决定 A 修复交叠)
PICKS = {
    "pick_01": {"X": (1.022, 1.773), "Y": (-0.952, -0.432)},
    "pick_02": {"X": (2.623, 3.333), "Y": (-0.585,  0.213)},
    "pick_03": {"X": (1.918, 2.415), "Y": (-0.964,  0.087)},
    "pick_04": {"X": (1.296, 1.776), "Y": (-0.400,  0.220)},
}


def load_points(path):
    raw = open(path, "rb").read()
    n = len(raw) // STRIDE
    buf = np.frombuffer(raw, dtype=np.uint8)[: n * STRIDE].reshape(n, STRIDE)
    xyzi = buf[:, :16].copy().view(np.float32)
    return (xyzi[:, 0].astype(np.float64),
            xyzi[:, 1].astype(np.float64),
            xyzi[:, 2].astype(np.float64))


def rot_x(deg):
    b = np.radians(deg); cb, sb = np.cos(b), np.sin(b)
    return np.array([[1, 0, 0], [0, cb, -sb], [0, sb, cb]])


def rot_y(deg):
    a = np.radians(deg); ca, sa = np.cos(a), np.sin(a)
    return np.array([[ca, 0, sa], [0, 1, 0], [-sa, 0, ca]])


def apply_R(R, x, y, z, tz):
    X = R[0, 0] * x + R[0, 1] * y + R[0, 2] * z
    Y = R[1, 0] * x + R[1, 1] * y + R[1, 2] * z
    Z = R[2, 0] * x + R[2, 1] * y + R[2, 2] * z + tz
    return X, Y, Z


def box_mask(X, Y):
    m = None
    for p in PICKS.values():
        X0, X1 = p["X"]; Y0, Y1 = p["Y"]
        mm = (X >= X0) & (X <= X1) & (Y >= Y0) & (Y <= Y1)
        m = mm if m is None else (m | mm)
    return m


def plane_fit(X, Y, Z):
    A = np.column_stack([np.ones_like(X), X, Y])
    coef, *_ = np.linalg.lstsq(A, Z, rcond=None)
    res = Z - A @ coef
    return coef, res


def per_box_stats(X, Y, Z, coef):
    """每框相对全局平面的残差统计."""
    out = {}
    for pid, p in PICKS.items():
        X0, X1 = p["X"]; Y0, Y1 = p["Y"]
        mm = (X >= X0) & (X <= X1) & (Y >= Y0) & (Y <= Y1)
        px, py, pz = X[mm], Y[mm], Z[mm]
        if len(px) == 0:
            out[pid] = {"n": 0}
            continue
        # 轻修剪防边缘垃圾 (点集已冻结, 这里只做统计稳健化)
        pred = coef[0] + coef[1] * px + coef[2] * py
        r = pz - pred
        keep = np.abs(r) < 0.12
        r = r[keep]
        out[pid] = {
            "n": int(len(r)),
            "mean_m": float(r.mean()),
            "std_m": float(r.std()),
            "absres_p95_m": float(np.percentile(np.abs(r), 95)),
        }
    return out


def main():
    x, y, z = load_points(SRC_BIN)
    print("loaded", len(x), "points")

    # ── 冻结点集: 用初始变换选一次 ─────────────────────────
    R0 = rot_x(ROLL0) @ rot_y(PITCH0)
    X0, Y0, Z0 = apply_R(R0, x, y, z, TZ0)
    m = box_mask(X0, Y0)
    # 一次性粗修剪 (去掉边缘家具污染)
    med = np.median(Z0[m])
    keep = np.abs(Z0[m] - med) < 0.12
    idx = np.where(m)[0][keep]
    print(f"frozen box points: {len(idx)} (from {int(m.sum())})")

    fx, fy, fz = x[idx], y[idx], z[idx]

    # ── 迭代反解 ───────────────────────────────────────────
    pitch, roll, tz = PITCH0, ROLL0, TZ0
    history = []
    for it in range(8):
        R = rot_x(roll) @ rot_y(pitch)
        X, Y, Z = apply_R(R, fx, fy, fz, tz)
        coef, res = plane_fit(X, Y, Z)
        rms = float(np.sqrt((res ** 2).mean()))
        b, c = float(coef[1]), float(coef[2])
        tilt = float(np.degrees(np.hypot(b, c)))
        print(f"iter {it}: pitch={pitch:.4f} roll={roll:.4f} tz={tz:.4f} | "
              f"slopes b={b:.5f} c={c:.5f} | residual tilt={tilt:.4f} deg | rms={rms:.4f}")
        history.append({"iter": it, "pitch_deg": pitch, "roll_deg": roll, "tz_m": tz,
                        "slope_b": b, "slope_c": c, "residual_tilt_deg": tilt,
                        "rms_m": rms, "n": int(len(X))})
        if tilt < 0.01:
            break
        pitch += np.degrees(b)
        roll += np.degrees(-c)
        # 重算 tz
        R = rot_x(roll) @ rot_y(pitch)
        _, _, Z1 = apply_R(R, fx, fy, fz, 0.0)
        tz = -float(np.median(Z1))

    # ── 最终全局平面 + 每框统计 (冻结点集) ───────────────────
    R = rot_x(roll) @ rot_y(pitch)
    X, Y, Z = apply_R(R, fx, fy, fz, tz)
    coef, res = plane_fit(X, Y, Z)
    rms_final = float(np.sqrt((res ** 2).mean()))
    print(f"\nFINAL: pitch={pitch:.4f} roll={roll:.4f} tz={tz:.4f}")
    print(f"FINAL global plane: a={coef[0]:.5f} b={coef[1]:.5f} c={coef[2]:.5f} rms={rms_final:.4f}")

    after_stats = per_box_stats(X, Y, Z, coef)
    for pid, s in after_stats.items():
        print(f"  [after] {pid}: n={s['n']} mean={s['mean_m']:+.4f} "
              f"std={s['std_m']:.4f} |P95|={s['absres_p95_m']:.4f}")

    # before 对照: 同一冻结点集, 初始变换 + 其自身全局平面
    Xb, Yb, Zb = apply_R(R0, fx, fy, fz, TZ0)
    coef_b, res_b = plane_fit(Xb, Yb, Zb)
    before_stats = per_box_stats(Xb, Yb, Zb, coef_b)
    for pid, s in before_stats.items():
        print(f"  [before] {pid}: n={s['n']} mean={s['mean_m']:+.4f} "
              f"std={s['std_m']:.4f} |P95|={s['absres_p95_m']:.4f}")

    # ── 保存 JSON ───────────────────────────────────────────
    out = {
        "schema_version": "1.0",
        "kind": "gle02_optimized_transform",
        "method": "joint (pitch, roll, tz) solve on frozen user-picked floor points "
                  "(~230k pts, 4 boxes); iterative slope-correction to minimize "
                  "global plane residual; tz = -median(Z_frozen)",
        "initial": {"pitch_deg": PITCH0, "roll_deg": ROLL0, "tz_m": TZ0,
                     "source": "user visual alignment 2026-10-04"},
        "optimized": {"pitch_deg": float(pitch), "roll_deg": float(roll), "tz_m": float(tz)},
        "final_global_plane": {"a": float(coef[0]), "b": float(coef[1]),
                                "c": float(coef[2]), "rms_m": rms_final},
        "final_global_plane_before": {"a": float(coef_b[0]), "b": float(coef_b[1]),
                                       "c": float(coef_b[2]),
                                       "rms_m": float(np.sqrt((res_b ** 2).mean()))},
        "history": history,
        "per_box_after": after_stats,
        "per_box_before": before_stats,
        "frozen_points": int(len(idx)),
        "box_definitions": {k: {"X": list(v["X"]), "Y": list(v["Y"])}
                             for k, v in PICKS.items()},
        "convention": "R = Rx(roll) @ Ry(pitch); Z += tz; box rectangles defined in display frame",
        "notes": [
            "This is a MODEL-BASED estimate (assumes floor is planar), not an instrument "
            "measurement; FIELD_CHECKLIST §2/§3 laser measurement still required.",
            "frozen points = union of 4 boxes under initial transform, trimmed |Z-med|<0.12",
            "before/after stats use the SAME frozen points for honest comparison",
        ],
        "physical_verified": False,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("SAVED:", OUT_JSON)

    # ── 渲染 ───────────────────────────────────────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    fig, axes = plt.subplots(1, 2, figsize=(15, 7), dpi=100)

    # 左: 优化后残差图 (全量点变换仅用于画图, 用初始冻结点集不够覆盖视野;
    #     这里改用全部点, 但只画 near 区域)
    ax = axes[0]
    RallX, RallY, RallZ = apply_R(R, x, y, z, tz)
    near = (RallX >= -0.2) & (RallX <= 4.0) & (RallY >= -1.4) & (RallY <= 1.0)
    sc = ax.scatter(RallY[near], RallX[near], c=RallZ[near], cmap="RdBu_r",
                    vmin=-0.08, vmax=0.08, s=0.5, alpha=0.5, linewidths=0,
                    marker='.', rasterized=True)
    plt.colorbar(sc, ax=ax, label="Z after optimized leveling (m)")
    for pid, p in PICKS.items():
        X0, X1 = p["X"]; Y0, Y1 = p["Y"]
        ax.add_patch(mpatches.Rectangle((Y0, X0), Y1 - Y0, X1 - X0,
                     linewidth=2, edgecolor='k', facecolor='none'))
        ax.text((Y0 + Y1) / 2, (X0 + X1) / 2, pid, fontsize=9,
                ha='center', va='center',
                bbox=dict(facecolor='white', alpha=0.6, pad=1))
    ax.plot(0, 0, marker="^", markersize=14, color="deepskyblue")
    ax.set_xlabel("Y (m)"); ax.set_ylabel("X (m)")
    ax.set_title(f"After optimize: pitch={pitch:.3f}deg roll={roll:.3f}deg tz={tz:.3f}m")
    ax.set_aspect("equal"); ax.grid(True, alpha=0.25, linestyle=":")

    # 右: 每框 |P95| before vs after (冻结点集, 各自配置的全局平面)
    ax = axes[1]
    labels = list(PICKS.keys())
    before_v = [before_stats[k]["absres_p95_m"] for k in labels]
    after_v = [after_stats[k]["absres_p95_m"] for k in labels]
    xx = np.arange(len(labels))
    w = 0.35
    ax.bar(xx - w / 2, before_v, w, label="before (26deg, 0, 1.340)", color="salmon")
    ax.bar(xx + w / 2, after_v, w, label="after (optimized)", color="steelblue")
    ax.axhline(0.05, color='r', linestyle='--', linewidth=1.2, label="P2 gate 0.05m")
    ax.set_xticks(xx); ax.set_xticklabels(labels)
    ax.set_ylabel("per-box |residual| P95 (m)")
    ax.set_title("Per-box P95 before vs after (frozen point set)")
    ax.grid(True, alpha=0.25, linestyle=":", axis='y')
    ax.legend()

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=100)
    print("SAVED:", OUT_PNG)


if __name__ == "__main__":
    main()
