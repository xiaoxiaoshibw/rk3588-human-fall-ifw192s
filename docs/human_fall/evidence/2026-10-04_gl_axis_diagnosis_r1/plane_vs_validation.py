# -*- coding: utf-8 -*-
"""只读分析：拟合平面覆盖范围 + 三个验证区落在什么几何体上。

不修改任何生产文件/config/ROI。只读 NPZ + 人工草稿，输出诊断图。
"""
import json
import math
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

NPZ = "docs/human_fall/evidence/2026-10-03_gl_i01_r1/prepared/cap_20261002_163621.npz"
DRAFT = ("docs/human_fall/evidence/2026-10-03_gl_i02_r1/"
         "codex_review_01/work/filled_real_draft.json")


def fit_plane(pts, up, rng, thresh=0.05, iters=5000):
    """独立 RANSAC + SVD 精修；返回 (normal, offset, support, rms)。"""
    best = None
    for _ in range(iters):
        i = rng.choice(len(pts), 3, replace=False)
        a, b, c = pts[i]
        n = np.cross(b - a, c - a)
        L = np.linalg.norm(n)
        if L < 1e-9:
            continue
        n = n / L
        if n @ up < 0:
            n = -n
        off = -(n @ a)
        if not (1.2 <= off <= 1.7):
            continue
        cnt = int(np.count_nonzero(np.abs(pts @ n + off) <= thresh))
        if best is None or cnt > best[0]:
            best = (cnt, n.copy(), off)
    if best is None:
        return None
    _, n, off = best
    core = pts[np.abs(pts @ n + off) <= thresh]
    centroid = core.mean(axis=0)
    cov = (core - centroid).T @ (core - centroid)
    _, evec = np.linalg.eigh(cov)
    n = evec[:, 0]
    if n @ up < 0:
        n = -n
    off = -(n @ centroid)
    resid = core @ n + off
    rms = float(np.sqrt((resid ** 2).mean()))
    return n, float(off), int(len(core)), rms


def main():
    d = np.load(NPZ)
    points = d["points"]
    manifest = json.loads(str(d["input_manifest"]))
    groups = manifest["frame_groups"]
    draft = json.load(open(DRAFT, encoding="utf-8"))

    up = np.array([-0.438371, 0.0, 0.898794])   # 反证用的翻转 up
    rng = np.random.RandomState(20261004)

    fit_group = draft["fit_region"]["frame_group"]
    lo, hi = groups[fit_group]["rows"]
    fit_frame = points[lo:hi].astype(np.float64)
    fit_frame = fit_frame[np.any(fit_frame != 0.0, axis=1)]

    # fit ROI 需要放大才能过 min_inliers（第2步结论）
    fit_box = (2.0, 2.99, -2.0, 0.0, -1.5, 0.5)
    m = (fit_frame[:, 0] >= fit_box[0]) & (fit_frame[:, 0] <= fit_box[1])
    m &= (fit_frame[:, 1] >= fit_box[2]) & (fit_frame[:, 1] <= fit_box[3])
    m &= (fit_frame[:, 2] >= fit_box[4]) & (fit_frame[:, 2] <= fit_box[5])
    roi = fit_frame[m]

    n, off, support, rms = fit_plane(roi, up, rng)
    print("独立拟合平面:")
    print("  normal  =", [round(float(v), 4) for v in n])
    print("  offset  = %.4f m" % off)
    print("  support = %d / %d (%.1f%%)" % (support, len(roi), 100 * support / len(roi)))
    print("  本层RMS = %.5f m" % rms)
    ang = math.degrees(math.acos(np.clip(n @ up, -1, 1)))
    print("  与翻转up夹角 = %.3f deg" % ang)

    # ---- 平面在整个 fit 帧上的覆盖 ----
    d_frame = fit_frame @ n + off
    inl_frame = np.abs(d_frame) <= 0.05
    print()
    print("平面在整帧的覆盖: %d / %d = %.1f%%"
          % (inl_frame.sum(), len(fit_frame), 100 * inl_frame.mean()))

    # ---- 三个验证区 ----
    print()
    print("=== 三个验证区各自相对拟合平面的位置 ===")
    val_pts = []
    for src in draft["validation_regions"]:
        b = src["bounds"]
        g = src["frame_group"]
        a0, a1 = groups[g]["rows"]
        fp = points[a0:a1].astype(np.float64)
        mm = (fp[:, 0] >= b["x_min_m"]) & (fp[:, 0] <= b["x_max_m"])
        mm &= (fp[:, 1] >= b["y_min_m"]) & (fp[:, 1] <= b["y_max_m"])
        mm &= (fp[:, 2] >= b["z_min_m"]) & (fp[:, 2] <= b["z_max_m"])
        pv = fp[mm]
        val_pts.append(pv)
        dv = pv @ n + off
        near = np.abs(dv) <= 0.05
        print()
        print("  %s  frame=%s  n=%d" % (src["region_id"], g[6:14], len(pv)))
        print("     z 范围   : %.3f .. %.3f" % (b["z_min_m"], b["z_max_m"]))
        print("     平面穿过此区? %s  支持率 %.3f"
              % ("是" if near.sum() else "否", near.mean()))
        print("     有符号距离: p5=%+.4f  p50=%+.4f  p95=%+.4f"
              % (np.percentile(dv, 5), np.median(dv), np.percentile(dv, 95)))
        print("     |距离| p95 = %.4f  (门槛 0.05)" % np.percentile(np.abs(dv), 95))

    # ---- 传感器是否静止：跨帧拟合稳定性 ----
    print()
    print("=== 跨帧平面稳定性 (采样10帧) ===")
    keys = list(groups.keys())
    picks = keys[::max(1, len(keys) // 10)][:10]
    print("  frame        support   offset    normal_z   angle_up")
    offs = []
    for k in picks:
        a0, a1 = groups[k]["rows"]
        fr = points[a0:a1].astype(np.float64)
        fr = fr[np.any(fr != 0.0, axis=1)]
        mm = (fr[:, 0] >= fit_box[0]) & (fr[:, 0] <= fit_box[1])
        mm &= (fr[:, 1] >= fit_box[2]) & (fr[:, 1] <= fit_box[3])
        mm &= (fr[:, 2] >= fit_box[4]) & (fr[:, 2] <= fit_box[5])
        r = fit_plane(fr[mm], up, np.random.RandomState(7))
        if r is None:
            print("  %s  (无平面)" % k[6:14])
            continue
        nn, oo, sp, _ = r
        aa = math.degrees(math.acos(np.clip(nn @ up, -1, 1)))
        offs.append(oo)
        print("  %s  %6d  %7.4f  %8.4f  %7.3f" % (k[6:14], sp, oo, nn[2], aa))
    if offs:
        print("  offset 跨帧极差 = %.4f m" % (max(offs) - min(offs)))

    # ======================= 绘图 =======================
    fig = plt.figure(figsize=(18, 12), dpi=105)

    # ---- (1) 顶视：平面覆盖 ----
    ax = fig.add_subplot(2, 2, 1)
    sub = fit_frame[::10]
    ax.scatter(sub[:, 0], sub[:, 1], c="lightgray", s=1.0, alpha=0.5, linewidths=0)
    cov = fit_frame[inl_frame][::5]
    ax.scatter(cov[:, 0], cov[:, 1], c="crimson", s=1.0, alpha=0.55, linewidths=0)
    ax.add_patch(Rectangle((fit_box[0], fit_box[2]), fit_box[1] - fit_box[0],
                           fit_box[3] - fit_box[2], fill=False, edgecolor="blue",
                           linewidth=2.0))
    ax.text(fit_box[0], fit_box[3] + 0.15, "fit ROI (widened)", color="blue",
            fontsize=10, weight="bold")
    ax.plot(0, 0, "ko", ms=8)
    ax.text(0.12, -0.35, "sensor", fontsize=9)
    ax.set_xlim(-1, 8)
    ax.set_ylim(-4, 4)
    ax.set_xlabel("X forward (m)")
    ax.set_ylabel("Y left (m)")
    ax.set_title("(1) where the fitted plane lives  [gray=all points, red=%d plane inliers]"
                 % int(inl_frame.sum()), fontsize=10)
    ax.grid(alpha=0.3)
    ax.set_aspect("equal")

    # ---- (2) 顶视：验证区叠加 ----
    ax = fig.add_subplot(2, 2, 2)
    ax.scatter(cov[:, 0], cov[:, 1], c="crimson", s=1.2, alpha=0.35, linewidths=0)
    ax.add_patch(Rectangle((fit_box[0], fit_box[2]), fit_box[1] - fit_box[0],
                           fit_box[3] - fit_box[2], fill=False, edgecolor="blue",
                           linewidth=2.0))
    colors = ["orange", "deepskyblue", "magenta"]
    for src, pv, col in zip(draft["validation_regions"], val_pts, colors):
        b = src["bounds"]
        ax.add_patch(Rectangle((b["x_min_m"], b["y_min_m"]),
                               b["x_max_m"] - b["x_min_m"],
                               b["y_max_m"] - b["y_min_m"], fill=False,
                               edgecolor=col, linewidth=2.2))
        ax.text(b["x_min_m"], b["y_max_m"] + 0.12,
                "%s (n=%d)" % (src["region_id"], len(pv)), color=col,
                fontsize=10, weight="bold")
        if len(pv):
            ax.scatter(pv[::3, 0], pv[::3, 1], c=col, s=1.4, alpha=0.5, linewidths=0)
    ax.plot(0, 0, "ko", ms=8)
    ax.set_xlim(-0.5, 6)
    ax.set_ylim(-3, 3)
    ax.set_xlabel("X forward (m)")
    ax.set_ylabel("Y left (m)")
    ax.set_title("(2) validation regions vs plane inliers (red)", fontsize=10)
    ax.grid(alpha=0.3)
    ax.set_aspect("equal")

    # ---- (3) 侧视 X-Z ----
    ax = fig.add_subplot(2, 2, 3)
    ax.scatter(sub[:, 0], sub[:, 2], c="lightgray", s=1.0, alpha=0.45, linewidths=0)
    ax.scatter(cov[:, 0], cov[:, 2], c="crimson", s=1.2, alpha=0.5, linewidths=0)
    xs = np.linspace(-1, 8, 2)
    zs = (-off - n[0] * xs) / n[2]
    ax.plot(xs, zs, "r-", lw=2.2, label="fitted plane")
    for src, pv, col in zip(draft["validation_regions"], val_pts, colors):
        b = src["bounds"]
        ax.add_patch(Rectangle((b["x_min_m"], b["z_min_m"]),
                               b["x_max_m"] - b["x_min_m"],
                               b["z_max_m"] - b["z_min_m"], fill=False,
                               edgecolor=col, linewidth=2.2))
        ax.text(b["x_min_m"], b["z_max_m"] + 0.1, src["region_id"], color=col,
                fontsize=10, weight="bold")
        if len(pv):
            ax.scatter(pv[::3, 0], pv[::3, 2], c=col, s=1.4, alpha=0.5, linewidths=0)
    ax.add_patch(Rectangle((fit_box[0], fit_box[4]), fit_box[1] - fit_box[0],
                           fit_box[5] - fit_box[4], fill=False, edgecolor="blue",
                           linewidth=2.0))
    ax.plot(0, 0, "ko", ms=8)
    ax.set_xlim(-0.5, 6)
    ax.set_ylim(-1.5, 1.5)
    ax.set_xlabel("X forward (m)")
    ax.set_ylabel("Z (m)")
    ax.set_title("(3) side view: plane (red line) vs boxes", fontsize=10)
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(alpha=0.3)

    # ---- (4) 各验证区到平面距离直方图 ----
    ax = fig.add_subplot(2, 2, 4)
    bins = np.linspace(-0.4, 0.4, 61)
    for src, pv, col in zip(draft["validation_regions"], val_pts, colors):
        if not len(pv):
            continue
        dv = pv @ n + off
        ax.hist(dv, bins=bins, histtype="step", color=col, linewidth=2.0,
                label="%s  n=%d  support|d|<5cm = %.2f"
                      % (src["region_id"], len(pv), (np.abs(dv) <= 0.05).mean()))
    ax.axvspan(-0.05, 0.05, color="green", alpha=0.14,
               label="inlier band (+/-5cm)")
    ax.set_xlabel("signed distance to fitted plane (m)")
    ax.set_ylabel("points")
    ax.set_title("(4) each validation region's residual to the plane", fontsize=10)
    ax.legend(fontsize=8.5, loc="upper right")
    ax.grid(alpha=0.3)

    fig.suptitle("GL ground fit: plane coverage vs the 3 human-drawn validation regions "
                 "(READ-ONLY diagnosis, flipped up_axis)",
                 fontsize=12, weight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.965])
    out = "tmp_gl_diag/plane_vs_validation.png"
    fig.savefig(out, bbox_inches="tight")
    print()
    print("saved", out)


if __name__ == "__main__":
    main()
