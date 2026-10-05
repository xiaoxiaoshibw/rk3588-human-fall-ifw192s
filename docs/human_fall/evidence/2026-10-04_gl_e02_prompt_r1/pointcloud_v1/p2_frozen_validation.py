# -*- coding: utf-8 -*-
"""
GL-E02 真 P2 验证 (冻结点集版) / p2_frozen_validation.py
==========================================================
修正 p2_cross_validation.py 的方法论问题:
  框矩形是在"初始显示系(26.0,0,1.340)"里画的 → 物理点集应冻结.
  换变换后**不得**用矩形重选; 必须用同一批 index.

流程:
  1. 初始变换选点 (4 框并集, |Z-med|<0.12 修剪) → 冻结 index
  2. 对候选变换 (pitch, roll, tz) 组:
       冻结点的 fit 组 → 拟合平面
       冻结点的 val 组 → 外推残差 |P95| 对 P2 门 (0.05m)
  3. 对比: 初始变换 vs 优化变换, 对全部 4 种 FIT 选择

输出:
  p2_frozen_validation.png / .meta.json
"""
import json
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_BIN = os.path.join(HERE, "points.bin")

STRIDE = 28

PICKS = {
    "pick_01": {"X": (1.022, 1.773), "Y": (-0.952, -0.432)},
    "pick_02": {"X": (2.623, 3.333), "Y": (-0.585,  0.213)},
    "pick_03": {"X": (1.918, 2.415), "Y": (-0.964,  0.087)},
    "pick_04": {"X": (1.296, 1.776), "Y": (-0.400,  0.220)},
}

TRANSFORMS = {
    "initial":   {"pitch": 26.0000, "roll":  0.0000, "tz": 1.3400,
                   "source": "user visual alignment 2026-10-04"},
    "optimized": {"pitch": 26.2338, "roll": -1.3221, "tz": 1.3222,
                   "source": "joint solve on frozen floor points (optimize_transform.py)"},
}

P2_GATE_M = 0.05


def load_points(path):
    raw = open(path, "rb").read()
    n = len(raw) // STRIDE
    buf = np.frombuffer(raw, dtype=np.uint8)[: n * STRIDE].reshape(n, STRIDE)
    xyzi = buf[:, :16].copy().view(np.float32)
    return (xyzi[:, 0].astype(np.float64),
            xyzi[:, 1].astype(np.float64),
            xyzi[:, 2].astype(np.float64))


def apply_transform(x, y, z, pitch, roll, tz):
    a = np.radians(pitch); b = np.radians(roll)
    ca, sa = np.cos(a), np.sin(a)
    cb, sb = np.cos(b), np.sin(b)
    rx0 = ca * x + sa * z
    rx1 = y
    rx2 = -sa * x + ca * z
    X = rx0
    Y = cb * rx1 - sb * rx2
    Z = sb * rx1 + cb * rx2 + tz
    return X, Y, Z


def plane_fit(X, Y, Z):
    A = np.column_stack([np.ones_like(X), X, Y])
    coef, *_ = np.linalg.lstsq(A, Z, rcond=None)
    res = Z - A @ coef
    return coef, res


def main():
    x, y, z = load_points(SRC_BIN)
    print("loaded", len(x))

    # ── 1) 冻结 index (用初始变换选) ────────────────────────
    t0 = TRANSFORMS["initial"]
    X0, Y0, Z0 = apply_transform(x, y, z, t0["pitch"], t0["roll"], t0["tz"])
    frozen = {}
    for pid, p in PICKS.items():
        X0m, X1m = p["X"]; Y0m, Y1m = p["Y"]
        m = (X0 >= X0m) & (X0 <= X1m) & (Y0 >= Y0m) & (Y0 <= Y1m)
        idx = np.where(m)[0]
        med = np.median(Z0[idx])
        keep = np.abs(Z0[idx] - med) < 0.12
        frozen[pid] = idx[keep]
        print(f"frozen {pid}: {len(frozen[pid])} pts")

    # ── 2) 对每个变换 + 每个 FIT 选择, 跑跨框验证 ────────────
    report = {}
    for tname, t in TRANSFORMS.items():
        Xw, Yw, Zw = apply_transform(x, y, z, t["pitch"], t["roll"], t["tz"])
        fz = {pid: (Xw[ix], Yw[ix], Zw[ix]) for pid, ix in frozen.items()}
        report[tname] = {}
        for fit_id in PICKS:
            fx, fy, fzz = fz[fit_id]
            coef, res = plane_fit(fx, fy, fzz)
            rms_fit = float(np.sqrt((res ** 2).mean()))
            entry = {"fit": fit_id, "fit_plane": {"a": float(coef[0]),
                                                   "b": float(coef[1]),
                                                   "c": float(coef[2]),
                                                   "rms_m": rms_fit},
                     "val": {}}
            for val_id in PICKS:
                if val_id == fit_id:
                    continue
                vx, vy, vzz = fz[val_id]
                pred = coef[0] + coef[1] * vx + coef[2] * vy
                r = vzz - pred
                keep = np.abs(r) < 0.12   # 同口径轻修剪
                r = r[keep]
                p95 = float(np.percentile(np.abs(r), 95))
                entry["val"][val_id] = {
                    "n": int(len(r)),
                    "mean_m": float(r.mean()),
                    "std_m": float(r.std()),
                    "absres_p95_m": p95,
                    "pass": bool(p95 <= P2_GATE_M),
                }
            entry["overall_pass"] = all(v["pass"] for v in entry["val"].values())
            report[tname][fit_id] = entry
            vals = " ".join(f"{vid}:{v['absres_p95_m']:.4f}{'P' if v['pass'] else 'F'}"
                            for vid, v in entry["val"].items())
            print(f"[{tname:9s}] FIT={fit_id}: rms={rms_fit:.4f} | {vals} | "
                  f"{'PASS' if entry['overall_pass'] else 'FAIL'}")

    # ── 汇总 ───────────────────────────────────────────────
    print()
    n_pass_init = sum(1 for e in report["initial"].values() if e["overall_pass"])
    n_pass_opt = sum(1 for e in report["optimized"].values() if e["overall_pass"])
    print(f"initial transform:   {n_pass_init}/4 FIT choices fully pass")
    print(f"optimized transform: {n_pass_opt}/4 FIT choices fully pass")
    best_opt = min(report["optimized"].items(),
                   key=lambda kv: max(v["absres_p95_m"] for v in kv[1]["val"].values()))
    worst_p95 = max(v["absres_p95_m"] for v in best_opt[1]["val"].values())
    print(f"best under optimized: FIT={best_opt[0]}, worst VAL |P95|={worst_p95:.4f}m "
          f"(gate {P2_GATE_M})")

    # ── 可视化: 表格图 ─────────────────────────────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(16, 6.5), dpi=100)
    for ax, tname in zip(axes, ["initial", "optimized"]):
        ax.axis("off")
        t = TRANSFORMS[tname]
        lines = [f"{tname}: pitch={t['pitch']:.3f} roll={t['roll']:.3f} tz={t['tz']:.4f}",
                  "", f"{'FIT':10s} {'VAL_1':>10s} {'VAL_2':>10s} {'VAL_3':>10s}   {'ALL':>5s}",
                  "-" * 54]
        for fit_id, e in report[tname].items():
            row = [f"{fit_id:10s}"]
            for vid, v in e["val"].items():
                s = f"{v['absres_p95_m']:.4f}{'P' if v['pass'] else 'F'}"
                row.append(f"{s:>10s}")
            row.append("  PASS" if e["overall_pass"] else "  FAIL")
            lines.append(" ".join(row))
        lines.append("")
        lines.append("P2 gate: |res|P95 <= 0.05m  (P=PASS, F=FAIL)")
        n_pass = sum(1 for e in report[tname].values() if e["overall_pass"])
        lines.append(f"fully-passing FIT choices: {n_pass}/4")
        ax.text(0.02, 0.95, "\n".join(lines), va="top", ha="left",
                family="monospace", fontsize=11, transform=ax.transAxes)
        ax.set_title(f"{tname} transform — frozen-point cross validation")

    plt.tight_layout()
    out_png = os.path.join(HERE, "p2_frozen_validation.png")
    plt.savefig(out_png, dpi=100)
    print("SAVED:", out_png)

    meta = {
        "schema_version": "1.0",
        "kind": "gle02_p2_frozen_cross_validation",
        "method": "frozen point sets (selected under initial transform, union of boxes, "
                  "trimmed |Z-med|<0.12); cross-validated under both transforms",
        "frozen_counts": {pid: int(len(ix)) for pid, ix in frozen.items()},
        "transforms": TRANSFORMS,
        "report": report,
        "p2_gate_m": P2_GATE_M,
        "summary": {
            "initial_pass_fit_choices": int(n_pass_init),
            "optimized_pass_fit_choices": int(n_pass_opt),
            "best_optimized_fit": best_opt[0],
            "best_optimized_worst_val_p95_m": float(worst_p95),
        },
        "physical_verified": False,
        "notes": [
            "frozen sets avoid the selection-change artifact of rectangle re-selection",
            "optimized transform is model-based (assumes planar floor); instrument "
            "measurement (FIELD_CHECKLIST §2/§3) still required",
        ],
    }
    with open(os.path.join(HERE, "p2_frozen_validation.meta.json"), "w",
              encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("SAVED: p2_frozen_validation.meta.json")


if __name__ == "__main__":
    main()
