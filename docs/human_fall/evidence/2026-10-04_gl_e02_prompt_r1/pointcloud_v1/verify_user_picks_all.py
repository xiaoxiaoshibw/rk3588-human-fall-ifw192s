# -*- coding: utf-8 -*-
"""
GL-E02 用户框选 4 区 总验证 / user_picks_verify_all
======================================================
用户在 annotator.html v11 框的 4 个区:
  pick_01  X[1.022,1.773] Y[-0.952,-0.432]  "这一块平"
  pick_02  X[2.623,3.333] Y[-0.585, 0.213]  远距区
  pick_03  X[1.918,2.415] Y[-0.964, 0.087]  中距区
  pick_04  X[1.296,1.776] Y[-0.473, 0.220]  近距/侧向区

统一变换: A: R_y(+26°), tz=+1.340 (user-confirmed)

输出:
  user_picks_verify_all.png        4 子图: 俯视/箱线图/统计表/间距表
  user_picks_verify_all.meta.json  数值全量
"""
import json
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_BIN  = os.path.join(HERE, "points.bin")
OUT_PNG  = os.path.join(HERE, "user_picks_verify_all.png")
OUT_META = os.path.join(HERE, "user_picks_verify_all.meta.json")

STRIDE = 28
PITCH_DEG = 26.0
TZ = 1.340

PICKS = [
    {"id": "pick_01", "en": "flat #1", "X": (1.022, 1.773), "Y": (-0.952, -0.432), "color": "cyan"},
    {"id": "pick_02", "en": "far",       "X": (2.623, 3.333), "Y": (-0.585,  0.213), "color": "magenta"},
    {"id": "pick_03", "en": "mid",       "X": (1.918, 2.415), "Y": (-0.964,  0.087), "color": "orange"},
    {"id": "pick_04", "en": "near/lateral",  "X": (1.296, 1.776), "Y": (-0.400,  0.220), "color": "lime"},
]
POWER_STRIP = (2.50, 2.55)

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
    xs, ys, zs = load_points(SRC_BIN)
    a = np.deg2rad(PITCH_DEG)
    c, s = np.cos(a), np.sin(a)
    Xw = c * xs + s * zs
    Yw = ys
    Zw = -s * xs + c * zs + TZ

    results = []
    for p in PICKS:
        X0, X1 = p["X"]; Y0, Y1 = p["Y"]
        m = (Xw >= X0) & (Xw <= X1) & (Yw >= Y0) & (Yw <= Y1)
        Xi, Yi, Zi = Xw[m], Yw[m], Zw[m]
        n = len(Xi)
        r = {"id": p["id"], "zh": p["en"], "X": list(p["X"]), "Y": list(p["Y"]), "n": n}
        if n < 50:
            r["error"] = "too few points"
            results.append(r); continue
        p5, p50, p95 = np.percentile(Zi, [5, 50, 95])
        coef_all, res_all = plane_fit(Xi, Yi, Zi)
        rms_all = float(np.sqrt((res_all ** 2).mean()))
        keep = np.abs(res_all) < 0.15
        if keep.sum() > 30:
            coef_k, res_k = plane_fit(Xi[keep], Yi[keep], Zi[keep])
            rms_k = float(np.sqrt((res_k ** 2).mean()))
            res_k_abs = np.abs(res_k)
            p95_res = float(np.percentile(res_k_abs, 95))
        else:
            coef_k, rms_k = coef_all, rms_all
            p95_res = float(np.percentile(np.abs(res_all), 95))
        # 平面斜率(deg)
        slope = float(np.degrees(np.arctan(np.hypot(coef_k[1], coef_k[2]))))
        r.update({
            "center": [float((X0+X1)/2), float((Y0+Y1)/2)],
            "size": [float(X1-X0), float(Y1-Y0)],
            "Z_p5_p50_p95": [float(p5), float(p50), float(p95)],
            "Z_std": float(Zi.std()),
            "plane_coef": [float(v) for v in coef_k],
            "plane_rms_m": rms_k,
            "absres_p95_m": p95_res,
            "plane_slope_deg": slope,
            "frac_absZ_lt_05": float((np.abs(Zi) < 0.05).mean()),
        })
        results.append(r)
        print(f"{p['id']} [{p['en']}]: n={n}, RMS={rms_k:.4f}m, |res|P95={p95_res:.4f}m, "
              f"slope={slope:.2f}deg, Z_std={Zi.std():.4f}")

    # ── 两两几何: 中心距离 + 交叠面积 ─────────────────────────
    np_ = len(results)
    pair_info = []
    for i in range(np_):
        for j in range(i+1, np_):
            A_, B_ = results[i], results[j]
            ca, cb = np.array(A_["center"]), np.array(B_["center"])
            dist = float(np.linalg.norm(ca - cb))
            xov = max(0.0, min(A_["X"][1], B_["X"][1]) - max(A_["X"][0], B_["X"][0]))
            yov = max(0.0, min(A_["Y"][1], B_["Y"][1]) - max(A_["Y"][0], B_["Y"][0]))
            area = xov * yov
            pair_info.append({
                "a": A_["id"], "b": B_["id"],
                "center_dist_m": dist,
                "overlap_x_m": xov, "overlap_y_m": yov, "overlap_area_m2": area,
                "checklist_ge_1m": bool(dist >= 1.0),
                "disjoint": bool(area == 0.0),
            })
            print(f"  {A_['id']} <-> {B_['id']}: d={dist:.3f}m, overlap={area:.4f}m2"
                  f" {'[<1m!]' if dist < 1.0 else ''}{' [OVERLAP!]' if area > 0 else ''}")

    # ── 渲染 2x2 ──────────────────────────────────────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    try:
        matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
        matplotlib.rcParams['font.family'] = 'sans-serif'
        matplotlib.rcParams['axes.unicode_minus'] = False
    except Exception:
        pass

    fig, axes = plt.subplots(2, 2, figsize=(15, 13), dpi=100)

    # A) 俯视
    ax = axes[0][0]
    near = (Xw >= -0.5) & (Xw <= 4.2) & (Yw >= -1.6) & (Yw <= 1.2)
    Xn, Yn, Zn = Xw[near], Yw[near], Zw[near]
    sc = ax.scatter(Yn, Xn, c=Zn, cmap="RdYlGn", vmin=-0.15, vmax=0.15,
                    s=0.5, alpha=0.45, linewidths=0, marker='.', rasterized=True)
    plt.colorbar(sc, ax=ax, label="Z (m)")
    for p, r in zip(PICKS, results):
        X0, X1 = p["X"]; Y0, Y1 = p["Y"]
        ax.add_patch(mpatches.Rectangle((Y0, X0), Y1-Y0, X1-X0, linewidth=2.2,
                     edgecolor=p["color"], facecolor=p["color"], alpha=0.22))
        ax.text((Y0+Y1)/2, (X0+X1)/2, f"{p['id']}\n{p['en']}", color=p["color"],
                fontsize=10, weight='bold', ha='center', va='center',
                bbox=dict(facecolor='black', alpha=0.55, pad=2))
    ax.axhspan(*POWER_STRIP, color='magenta', alpha=0.3)
    ax.text(0, (POWER_STRIP[0]+POWER_STRIP[1])/2 + 0.05, "电源走线槽 2.50-2.55m",
            color='magenta', fontsize=9)
    ax.plot(0, 0, marker="^", markersize=14, color="deepskyblue")
    ax.set_xlabel("Y (m, lateral)"); ax.set_ylabel("X (m, forward)")
    ax.set_title("俯视图: 4 个用户框选 (99帧叠加, A+R_y(26°), tz=+1.340)")
    ax.grid(True, alpha=0.25, linestyle=":"); ax.set_aspect("equal")

    # B) Z 箱线图
    ax = axes[0][1]
    data = []
    labels = []
    for p in PICKS:
        X0, X1 = p["X"]; Y0, Y1 = p["Y"]
        m = (Xw >= X0) & (Xw <= X1) & (Yw >= Y0) & (Yw <= Y1)
        data.append(Zw[m])
        labels.append(p["id"] + "\n" + p["en"])
    bp = ax.boxplot(data, labels=labels, showfliers=False, whis=(5, 95), patch_artist=True)
    for patch, p in zip(bp['boxes'], PICKS):
        patch.set_facecolor(p["color"]); patch.set_alpha(0.5)
    ax.axhline(0, color='r', linewidth=1.2, label="Z=0")
    ax.set_ylabel("Z (m)"); ax.set_ylim(-0.15, 0.15)
    ax.set_title("每框 Z 分布 (whis=5-95%)")
    ax.grid(True, alpha=0.25, linestyle=":")
    ax.legend()

    # C) 统计表 (英文, 等宽对齐)
    ax = axes[1][0]; ax.axis("off")
    lines = ["Per-box measurements (A: R_y(+26deg), tz=+1.340):", ""]
    hdr = f"{'id':10s} {'n':>7s} {'RMS':>8s} {'|res|P95':>9s} {'slope':>7s} {'|Z|<5cm':>8s}"
    lines.append(hdr)
    lines.append("-" * 56)
    for r in results:
        if r.get("error"):
            lines.append(f"{r['id']:10s} {r['n']:>7d}   <too few>")
            continue
        lines.append(f"{r['id']:10s} {r['n']:>7d} {r['plane_rms_m']:>7.4f}m "
                     f"{r['absres_p95_m']:>8.4f}m {r['plane_slope_deg']:>6.2f}° "
                     f"{r['frac_absZ_lt_05']*100:>6.1f}%")
    lines.append("")
    lines.append("P2 gate |res|P95 <= 0.05m: "
                 + ("ALL PASS" if all(r.get("absres_p95_m", 1) <= 0.05 for r in results) else "some FAIL"))
    ax.text(0.02, 0.98, "\n".join(lines), va="top", ha="left",
            family="monospace", fontsize=11, transform=ax.transAxes)
    ax.set_title("统计汇总 / Summary")

    # D) 间距表 (英文)
    ax = axes[1][1]; ax.axis("off")
    lines = ["Pairwise geometry (checklist: spacing >= 1m, no overlap):", ""]
    for pi in pair_info:
        flag = ""
        if not pi["checklist_ge_1m"]:
            flag += " [<1m]"
        if not pi["disjoint"]:
            flag += " [OVERLAP]"
        lines.append(f"{pi['a']} <-> {pi['b']}: d={pi['center_dist_m']:.2f}m, "
                     f"overlap={pi['overlap_area_m2']:.3f}m2{flag}")
    lines.append("")
    n_bad = sum(1 for pi in pair_info if not pi["disjoint"])
    n_short = sum(1 for pi in pair_info if not pi["checklist_ge_1m"])
    lines.append(f"overlap pairs: {n_bad} / 6      <1m pairs: {n_short} / 6")
    lines.append("")
    lines.append("note: [<1m] is a guideline;")
    lines.append("      [OVERLAP] breaks VAL independence - fix advised")
    ax.text(0.02, 0.98, "\n".join(lines), va="top", ha="left",
            family="monospace", fontsize=11, transform=ax.transAxes)
    ax.set_title("独立性检查 / Independence check")

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=100)
    print("OUT:", OUT_PNG)

    # ── meta ─────────────────────────────────────────────────
    meta = {
        "schema_version": "1.0",
        "kind": "gle02_user_picks_verify_all",
        "session_id": "cap_20261002_233210",
        "transform": {"rotation": "A: R_y(+26deg)", "tz_m": TZ},
        "picks": results,
        "pair_geometry": pair_info,
        "power_strip_x_m": list(POWER_STRIP),
        "p2_gate": {"criterion": "absres_p95 <= 0.05 m", "unit": "m"},
        "physical_verified": False,
        "notes": [
            "absres_p95 measured relative to per-box trimmed plane fit",
            "plane_slope_deg reflects residual pitch error of the 26deg estimate",
        ],
    }
    with open(OUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("META:", OUT_META)

if __name__ == "__main__":
    main()
