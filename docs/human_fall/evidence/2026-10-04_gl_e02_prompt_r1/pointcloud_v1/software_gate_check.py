# -*- coding: utf-8 -*-
"""
GL-E02 软件门自检 (PLAN §5 口径) / software_gate_check.py
============================================================
门 (GROUND_LEVELING_NEXT_STAGE_PLAN.md §5, 既有软件工程门):
  1. 至少 3 独立验证区域
  2. 每区 >= 20 点
  3. untruncated RMS <= 0.03 m  (每区对自己拟合平面, 不修剪)
  4. |残差| P95 <= 0.05 m       (同上口径)
  5. 支持率 >= 0.8              (|Z_residual| < 阈值 的点占比; 阈值取 0.05m)
  6. 法向稳定 <= 2 度            (跨帧平面法向角变化; 帧间对比)
  7. offset 稳定 <= 0.03 m       (跨帧平面 offset 变化)

本脚本:
  - 对 4 个框, 分别在"单帧"与"全叠加"两种模式算 1-5 门
  - 用第 0 帧 vs 第 50 帧 (或滚动多帧) 算 6-7 门
  - 输出表格 + meta
"""
import json
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_BIN = os.path.join(HERE, "points.bin")
SRC_META = os.path.join(HERE, "meta.json")
OUT_PNG = os.path.join(HERE, "software_gate_check.png")
OUT_META = os.path.join(HERE, "software_gate_check.meta.json")

STRIDE = 28
PITCH_DEG = 26.2338
ROLL_DEG  = -1.3221
TZ        = 1.3222
SUPPORT_THRESH_M = 0.05
GROUND_Z_GATE_M = 0.15   # 地面提取 Z 门限: 只保留 |Z|<0.15m 的地板候选点
                          # (生产管线等价; 排除 AOI 内立式物体如机器人机身的点)

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
    return (xyzi[:, 0].astype(np.float64), xyzi[:, 1].astype(np.float64),
            xyzi[:, 2].astype(np.float64))


def apply_transform(x, y, z, pitch, roll, tz):
    a = np.radians(pitch); b = np.radians(roll)
    ca, sa = np.cos(a), np.sin(a)
    cb, sb = np.cos(b), np.sin(b)
    rx0 = ca * x + sa * z
    rx1 = y
    rx2 = -sa * x + ca * z
    return rx0, cb * rx1 - sb * rx2, sb * rx1 + cb * rx2 + tz


def plane_fit(X, Y, Z):
    A = np.column_stack([np.ones_like(X), X, Y])
    coef, *_ = np.linalg.lstsq(A, Z, rcond=None)
    return coef, Z - A @ coef


def normal_from_coef(coef):
    """平面 Z = a + bX + cY 的法向 (未归一): (-b, -c, 1)."""
    n = np.array([-coef[1], -coef[2], 1.0])
    return n / np.linalg.norm(n)


def eval_box(X, Y, Z, box, truncate_clean=False):
    """对指定点集+框, 算门 2-5. truncate_clean=False 为 untruncated RMS."""
    X0, X1 = box["X"]; Y0, Y1 = box["Y"]
    m = (X >= X0) & (X <= X1) & (Y >= Y0) & (Y <= Y1) & (np.abs(Z) < GROUND_Z_GATE_M)
    px, py, pz = X[m], Y[m], Z[m]
    n = len(px)
    if n < 20:
        return {"n": n, "error": "too few"}
    coef, res = plane_fit(px, py, pz)
    rms = float(np.sqrt((res ** 2).mean()))
    p95 = float(np.percentile(np.abs(res), 95))
    support = float((np.abs(res) < SUPPORT_THRESH_M).mean())
    return {"n": n, "coef": [float(v) for v in coef],
            "rms_m": rms, "absres_p95_m": p95, "support": support,
            "normal": [float(v) for v in normal_from_coef(coef)]}


def main():
    x, y, z = load_points(SRC_BIN)
    meta_src = json.load(open(SRC_META, encoding="utf-8"))
    frames = meta_src["frames"]
    Xf, Yf, Zf = apply_transform(x, y, z, PITCH_DEG, ROLL_DEG, TZ)
    n_frame = len(frames)

    print(f"frames: {n_frame}")

    # ── 门 2-5: 全叠加 vs 单帧 ──────────────────────────────
    print("\n=== Gate 2-5: per-box (全叠加) ===")
    agg = {}
    for pid, box in PICKS.items():
        r = eval_box(Xf, Yf, Zf, box)
        agg[pid] = {"agg": r}
        print(f"  {pid}: n={r['n']} RMS={r['rms_m']:.4f}m P95={r['absres_p95_m']:.4f}m "
              f"support={r['support']*100:.1f}%")

    # 单帧: 每框取"点最多的一帧"算
    print("\n=== Gate 2-5: per-box (单帧, 每框取点数最多帧) ===")
    for pid, box in PICKS.items():
        X0, X1 = box["X"]; Y0, Y1 = box["Y"]
        best = None
        for fi, f in enumerate(frames):
            s = f["offset_points"]; c = f["count_points"]
            Xs = Xf[s:s + c]; Ys = Yf[s:s + c]; Zs = Zf[s:s + c]
            m = (Xs >= X0) & (Xs <= X1) & (Ys >= Y0) & (Ys <= Y1)
            cnt = int(m.sum())
            if cnt >= 20 and (best is None or cnt > best[1]):
                best = (fi, cnt)
        if best is None:
            print(f"  {pid}: no frame with >=20 pts")
            continue
        fi, cnt = best
        f = frames[fi]
        s = f["offset_points"]; c = f["count_points"]
        Xs = Xf[s:s + c]; Ys = Yf[s:s + c]; Zs = Zf[s:s + c]
        r = eval_box(Xs, Ys, Zs, box)
        agg[pid]["single"] = {"frame_idx": fi, "seq": f["seq"], **r}
        print(f"  {pid}: frame {fi} (seq={f['seq']}) n={r['n']} RMS={r['rms_m']:.4f}m "
              f"P95={r['absres_p95_m']:.4f}m support={r['support']*100:.1f}%")

    # ── 门 6-7: 帧间法向/offset 稳定 ────────────────────────
    # 每个框: 沿帧序列取点够多的帧 (间隔采样 5 帧), 分别拟合平面,
    # 统计法向角变化 (相对首帧) 与 offset (a 系数) 变化.
    print("\n=== Gate 6-7: 帧间稳定 (5帧间隔采样) ===")
    for pid, box in PICKS.items():
        normals = []; offsets = []; used = []
        for fi in range(0, n_frame, 5):
            f = frames[fi]
            s = f["offset_points"]; c = f["count_points"]
            Xs = Xf[s:s + c]; Ys = Yf[s:s + c]; Zs = Zf[s:s + c]
            r = eval_box(Xs, Ys, Zs, box)
            if r.get("error"):
                continue
            normals.append(np.array(r["normal"]))
            offsets.append(r["coef"][0])
            used.append(fi)
        if len(normals) < 3:
            print(f"  {pid}: too few valid frames ({len(normals)})")
            continue
        N = np.array(normals); off = np.array(offsets)
        ref = N.mean(axis=0); ref = ref / np.linalg.norm(ref)
        angs = np.degrees(np.arccos(np.clip(N @ ref, -1, 1)))
        max_ang = float(angs.max())
        off_range = float(off.max() - off.min())
        agg[pid]["stability"] = {
            "frames_used": used,
            "max_normal_angle_deg": max_ang,
            "offset_range_m": off_range,
            "gate6_normal_pass": bool(max_ang <= 2.0),
            "gate7_offset_pass": bool(off_range <= 0.03),
        }
        print(f"  {pid}: frames={len(used)} max|Δnormal|={max_ang:.3f}° "
              f"Δoffset={off_range:.4f}m  "
              f"[normal {'P' if max_ang<=2 else 'F'}] [offset {'P' if off_range<=0.03 else 'F'}]")

    # ── 汇总判定 ────────────────────────────────────────────
    def _pass(r):
        return (r["n"] >= 20 and r["rms_m"] <= 0.03 and r["absres_p95_m"] <= 0.05
                and r["support"] >= 0.8)

    print("\n=== 汇总 (PLAN §5 口径) ===")
    for pid, a in agg.items():
        aa = a["agg"]
        ok = _pass(aa)
        s6 = a.get("stability", {}).get("gate6_normal_pass", None)
        s7 = a.get("stability", {}).get("gate7_offset_pass", None)
        print(f"  {pid}: gates2-5 {'PASS' if ok else 'FAIL'} | "
              f"gate6(normal) {'PASS' if s6 else 'FAIL' if s6 is False else 'N/A'} | "
              f"gate7(offset) {'PASS' if s7 else 'FAIL' if s7 is False else 'N/A'}")

    # ── 图 ─────────────────────────────────────────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(14, 7), dpi=100)
    ax.axis("off")
    lines = ["GL-E02 software gate self-check (PLAN §5) — transform: "
             f"pitch={PITCH_DEG:.3f} roll={ROLL_DEG:.3f} tz={TZ:.4f}",
             "",
             "Gate 2-5 (per-box, aggregate):",
             f"  {'box':9s} {'n':>7s} {'RMS(m)':>8s} {'P95(m)':>8s} {'support':>8s}  result",
             "  " + "-" * 52]
    for pid, a in agg.items():
        aa = a["agg"]
        ok = _pass(aa)
        lines.append(f"  {pid:9s} {aa['n']:>7d} {aa['rms_m']:>8.4f} "
                     f"{aa['absres_p95_m']:>8.4f} {aa['support']*100:>7.1f}%  "
                     f"{'PASS' if ok else 'FAIL'}")
    lines += ["", "Gate 6-7 (frame-to-frame stability):",
              f"  {'box':9s} {'Δnormal(deg)':>13s} {'Δoffset(m)':>12s}  result",
              "  " + "-" * 44]
    for pid, a in agg.items():
        st = a.get("stability")
        if not st:
            lines.append(f"  {pid:9s} {'n/a':>13s} {'n/a':>12s}  (no data)")
            continue
        ok = st["gate6_normal_pass"] and st["gate7_offset_pass"]
        lines.append(f"  {pid:9s} {st['max_normal_angle_deg']:>13.3f} "
                     f"{st['offset_range_m']:>12.4f}  {'PASS' if ok else 'FAIL'}")
    lines += ["",
              "Thresholds: n>=20, RMS<=0.03m, P95<=0.05m, support>=0.8,",
              "            normal<=2deg, offset range<=0.03m"]
    ax.text(0.01, 0.98, "\n".join(lines), va="top", ha="left",
            family="monospace", fontsize=11, transform=ax.transAxes)
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=100)
    print("SAVED:", OUT_PNG)

    meta = {
        "schema_version": "1.0",
        "kind": "gle02_software_gate_check",
        "gate_source": "GROUND_LEVELING_NEXT_STAGE_PLAN.md §5",
        "transform": {"pitch_deg": PITCH_DEG, "roll_deg": ROLL_DEG, "tz_m": TZ,
                       "origin": "optimize_transform.py joint solve"},
        "results": {pid: a for pid, a in agg.items()},
        "ground_z_gate_m": GROUND_Z_GATE_M,
        "gate_input": "ROI box AND |Z|<0.15m (ground extraction equivalent); residuals untruncated",
        "thresholds": {"min_points": 20, "max_rms_m": 0.03, "max_absres_p95_m": 0.05,
                        "min_support": 0.8, "max_normal_deg": 2.0, "max_offset_range_m": 0.03},
        "physical_verified": False,
    }
    with open(OUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("SAVED:", OUT_META)


if __name__ == "__main__":
    main()
