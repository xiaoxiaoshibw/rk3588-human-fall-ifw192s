# -*- coding: utf-8 -*-
"""
GL-E02 真 P2 跨框验证 / fit->val extrapolation
================================================
真 P2 口径 (FIELD_CHECKLIST P2 / GL-E02 E 项):
  在 FIT 区拟合一个平面, 用**同一个平面**去预测 3 个 VAL 区的 Z,
  预测残差的 |P95| 必须 <= 0.05 m.
  这是"跨框外推", 不是"每框自拟平面".

用法:
  python p2_cross_validation.py                    # FIT=pick_03 (默认)
  python p2_cross_validation.py --fit pick_01      # 指定 FIT

输出:
  p2_cross_validation_<fitid>.png / .meta.json
"""
import argparse
import json
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_BIN = os.path.join(HERE, "points.bin")
STRIDE = 28
PITCH_DEG = 26.0   # 可被 --pitch 覆盖
ROLL_DEG  = 0.0    # 可被 --roll 覆盖
TZ        = 1.340  # 可被 --tz 覆盖

PICKS = {
    "pick_01": {"en": "flat #1 first pick",  "X": (1.022, 1.773), "Y": (-0.952, -0.432)},
    "pick_02": {"en": "far past power strip","X": (2.623, 3.333), "Y": (-0.585,  0.213)},
    "pick_03": {"en": "mid before strip",    "X": (1.918, 2.415), "Y": (-0.964,  0.087)},
    "pick_04": {"en": "near/lateral FIXED",  "X": (1.296, 1.776), "Y": (-0.400,  0.220)},
}
P2_GATE_M = 0.05

def load_points(path):
    raw = open(path, "rb").read()
    n = len(raw) // STRIDE
    buf = np.frombuffer(raw, dtype=np.uint8)[: n * STRIDE].reshape(n, STRIDE)
    xyzi = buf[:, :16].copy().view(np.float32)
    return xyzi[:, 0], xyzi[:, 1], xyzi[:, 2]

def plane_fit(X, Y, Z):
    A = np.column_stack([np.ones_like(X), X, Y])
    coef, *_ = np.linalg.lstsq(A, Z, rcond=None)
    res = Z - A @ coef
    return coef, res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", default="pick_03", choices=list(PICKS.keys()))
    ap.add_argument("--pitch", type=float, default=PITCH_DEG)
    ap.add_argument("--roll",  type=float, default=ROLL_DEG)
    ap.add_argument("--tz",    type=float, default=TZ)
    args = ap.parse_args()

    xs, ys, zs = load_points(SRC_BIN)
    a = np.deg2rad(args.pitch)
    b = np.deg2rad(args.roll)
    ca, sa = np.cos(a), np.sin(a)
    cb, sb = np.cos(b), np.sin(b)
    # R = Rx(roll) @ Ry(pitch)
    # Ry 行: [ca*x + sa*z, y, -sa*x + ca*z]
    # Rx 作用其上: X=rx0, Y=cb*rx1 - sb*rx2, Z=sb*rx1 + cb*rx2
    rx0 = ca * xs + sa * zs
    rx1 = ys
    rx2 = -sa * xs + ca * zs
    Xw = rx0
    Yw = cb * rx1 - sb * rx2
    Zw = sb * rx1 + cb * rx2 + args.tz

    # 分框取点
    box_pts = {}
    for pid, p in PICKS.items():
        X0, X1 = p["X"]; Y0, Y1 = p["Y"]
        m = (Xw >= X0) & (Xw <= X1) & (Yw >= Y0) & (Yw <= Y1)
        box_pts[pid] = (Xw[m], Yw[m], Zw[m])
        print(f"{pid}: n={m.sum()}")

    # FIT 平面
    fx, fy, fz = box_pts[args.fit]
    coef, res_fit = plane_fit(fx, fy, fz)
    rms_fit = float(np.sqrt((res_fit ** 2).mean()))
    print(f"\nFIT = {args.fit}: plane Z = {coef[0]:.5f} + {coef[1]:.5f}*X + {coef[2]:.5f}*Y")
    print(f"  FIT residual RMS = {rms_fit:.4f} m, |res|P95 = {np.percentile(np.abs(res_fit),95):.4f} m")

    # 用 FIT 的平面外推到所有框 (含 FIT 自身作基准)
    results = []
    for pid, (px, py, pz) in box_pts.items():
        pred = coef[0] + coef[1] * px + coef[2] * py
        res = pz - pred
        absres = np.abs(res)
        p95 = float(np.percentile(absres, 95))
        r = {
            "roi": pid,
            "role": "FIT" if pid == args.fit else "VAL",
            "n": int(len(px)),
            "res_mean_m": float(res.mean()),
            "res_std_m": float(res.std()),
            "absres_p95_m": p95,
            "absres_max_m": float(absres.max()),
            "p2_gate_pass": bool(p95 <= P2_GATE_M),
        }
        results.append(r)
        tag = "FIT" if pid == args.fit else "VAL"
        flag = "PASS" if r["p2_gate_pass"] else "FAIL"
        print(f"  [{tag}] {pid}: n={r['n']:6d}  mean={r['res_mean_m']:+.4f}  "
              f"std={r['res_std_m']:.4f}  |P95|={p95:.4f}  -> {flag}")

    overall = all(r["p2_gate_pass"] for r in results if r["role"] == "VAL")
    print(f"\nOVERALL P2 (all VALs under FIT plane): {'PASS' if overall else 'FAIL'}")

    # ── 可视化 ─────────────────────────────────────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    colors = {"pick_01": "cyan", "pick_02": "magenta", "pick_03": "orange", "pick_04": "lime"}
    fig, axes = plt.subplots(1, 2, figsize=(15, 7), dpi=100)

    # A) 俯视: 所有点按"以 FIT 平面为基准的残差"着色
    ax = axes[0]
    near = (Xw >= -0.2) & (Xw <= 4.0) & (Yw >= -1.4) & (Yw <= 1.0)
    Xn, Yn, Zn = Xw[near], Yw[near], Zw[near]
    resid = Zn - (coef[0] + coef[1] * Xn + coef[2] * Yn)
    sc = ax.scatter(Yn, Xn, c=resid, cmap="RdBu_r", vmin=-0.10, vmax=0.10,
                    s=0.5, alpha=0.5, linewidths=0, marker='.', rasterized=True)
    plt.colorbar(sc, ax=ax, label="Z - FIT_plane(X,Y)  [m]")
    for pid, p in PICKS.items():
        X0, X1 = p["X"]; Y0, Y1 = p["Y"]
        lw = 3.0 if pid == args.fit else 1.8
        style = "-" if pid == args.fit else "--"
        ax.add_patch(mpatches.Rectangle((Y0, X0), Y1-Y0, X1-X0, linewidth=lw,
                     edgecolor=colors[pid], facecolor='none', linestyle=style))
        ax.text((Y0+Y1)/2, (X0+X1)/2, f"{pid}\n{'FIT' if pid==args.fit else 'VAL'}",
                color=colors[pid], fontsize=10, weight='bold',
                ha='center', va='center', bbox=dict(facecolor='black', alpha=0.5, pad=2))
    ax.plot(0, 0, marker="^", markersize=14, color="deepskyblue")
    ax.axhspan(2.50, 2.55, color='magenta', alpha=0.3)
    ax.set_xlabel("Y (m)"); ax.set_ylabel("X (m)")
    ax.set_title(f"Residual to FIT plane ({args.fit})  |  "
                 f"red/blue tints show systematic offset per VAL")
    ax.grid(True, alpha=0.25, linestyle=":"); ax.set_aspect("equal")

    # B) 残差箱线图
    ax = axes[1]
    data = []
    labels = []
    for r in results:
        pid = r["roi"]
        px, py, pz = box_pts[pid]
        pred = coef[0] + coef[1] * px + coef[2] * py
        data.append(pz - pred)
        labels.append(f"{pid}\n{r['role']}")
    bp = ax.boxplot(data, tick_labels=labels, showfliers=False, whis=(5, 95),
                    patch_artist=True)
    for patch, r in zip(bp['boxes'], results):
        patch.set_facecolor(colors[r["roi"]]); patch.set_alpha(0.55)
    ax.axhline(0, color='k', linewidth=1)
    ax.axhline(+P2_GATE_M, color='r', linestyle='--', linewidth=1, label="P2 gate +/-0.05m")
    ax.axhline(-P2_GATE_M, color='r', linestyle='--', linewidth=1)
    ax.set_ylabel("residual to FIT plane (m)")
    ax.set_ylim(-0.08, 0.08)
    ax.set_title("Cross-box residual (FIT plane -> all boxes), whis=5-95%")
    ax.grid(True, alpha=0.25, linestyle=":")
    ax.legend()

    plt.tight_layout()
    tag = f"{args.fit}_p{args.pitch:.3f}_r{args.roll:.3f}_t{args.tz:.3f}"
    out_png = os.path.join(HERE, f"p2_cross_validation_{tag}.png")
    plt.savefig(out_png, dpi=100)
    print("OUT:", out_png)

    meta = {
        "schema_version": "1.0",
        "kind": "gle02_p2_cross_validation",
        "fit_id": args.fit,
        "transform": {"rotation": "Rx(roll) @ Ry(pitch)", "pitch_deg": args.pitch, "roll_deg": args.roll, "tz_m": args.tz},
        "fit_plane": {"a": float(coef[0]), "b_X": float(coef[1]), "c_Y": float(coef[2]),
                       "rms_m": rms_fit},
        "results": results,
        "p2_gate_m": P2_GATE_M,
        "overall_pass": bool(overall),
        "notes": [
            "This is the real P2 protocol: single plane from FIT, extrapolated to VALs.",
            "Per-box self-fit numbers (from verify_user_picks_all.py) are health checks only.",
        ],
    }
    out_meta = os.path.join(HERE, f"p2_cross_validation_{tag}.meta.json")
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("META:", out_meta)

if __name__ == "__main__":
    main()
