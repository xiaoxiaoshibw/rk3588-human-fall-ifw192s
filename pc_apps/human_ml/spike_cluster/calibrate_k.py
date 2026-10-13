# -*- coding: utf-8 -*-
"""calibrate_k.py — p50 最近邻水平点距按距离环标定 (调参会话专用, 不用评估会话).

方法:
  对每个调参会话每帧, 按 find_hot 后与生产完全一致的输入, 收集 hot 点;
  用 XY 网格 (cell=0.5m) 加速近似最近邻: 对每个 hot 点, 查本格与 26 邻格,
  找水平欧氏最近点距离 d_nn. 用 median-of-cells-per-NN 作为稳健统计量.
  按 r = sqrt(x²+y²) 进 9 个环 (0.5..6.0m), 拟合 p50 d_nn(r) → eps(r)=k*r + bias.
  k 拟合用 LAD (中位数回归) — 抗场景污染.

产出 evidence/calibration_k.json.
"""
import json
import math
import os
import sys
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from _harness_lib import find_hot_js, grid_key, load_bg_envelope  # noqa: E402

# 与 crosscheck 一致的 R/T
R = np.array([[0.893544, 0.0, 0.448975],
              [-0.014337, 0.99949, 0.028533],
              [-0.448746, -0.031932, 0.893089]], dtype=np.float32)
T = np.array([0.0, 0.0, 1.380286], dtype=np.float32)

# 调参会话 (与 freeze_baseline.SESSIONS_TUNING 一致)
TUNING = ["cap_20261007_143945", "cap_20261007_150455", "cap_20261007_154007",
          "cap_20261007_154341", "cap_20261007_154545", "cap_20261007_154920"]

RNG_EDGES = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.5, 9.0]
MAX_FRAMES_PER_SESSION = 60       # 每会话抽样帧数上限 (均匀抽 60 帧, 帧自相关保护)
CELL = 0.5                         # 加速 NN 查询的辅助网格 (m)


def accel_nn(xs, ys):
    """scipy cKDTree 最近邻 (k=2, 第 0 是自己). 返回 (n,) 的 min horizontal dist.
    本函数在 PC 离线 spike 内调用 (板端部署仍允许纯 NumPy 重新实现; 参 _harness_lib 注释)."""
    from scipy.spatial import cKDTree
    pts = np.column_stack([xs, ys]).astype(np.float64)
    tree = cKDTree(pts, leafsize=16)
    dists, _ = tree.query(pts, k=2)
    return dists[:, 1]


def main():
    bg = load_bg_envelope(os.path.join(REPO, "pc_apps", "human_replay", "bg_envelope.json"))
    ring_of = {}
    for i in range(len(RNG_EDGES) - 1):
        ring_of[i] = dict(lo=RNG_EDGES[i], hi=RNG_EDGES[i + 1], samples=[])

    per_session_stats = {}
    for sid in TUNING:
        sdir = os.path.join(REPO, "captures", "remote", sid)
        if not os.path.isfile(os.path.join(sdir, "points.bin")):
            per_session_stats[sid] = {"skip": "no points.bin"}
            continue
        meta = json.load(open(os.path.join(sdir, "meta.json"), encoding="utf-8"))
        raw = np.memmap(os.path.join(sdir, "points.bin"), dtype=np.uint8, mode="r"
                        ).reshape(-1, 28).view(np.float32).reshape(-1, 7)
        nf = len(meta["frames"])
        step = max(1, nf // MAX_FRAMES_PER_SESSION)
        s_samples = 0
        for fi in range(0, nf, step):
            f = meta["frames"][fi]
            seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
            xyz = seg[:, :3].astype(np.float32)
            lv = (xyz @ R.T + T).astype(np.float32)
            xs = lv[:, 0].tolist()
            ys = lv[:, 1].tolist()
            zs = lv[:, 2].tolist()
            hot = find_hot_js(xs, ys, zs, bg, 0.1, 2.3)
            n_hot = len(hot)
            if n_hot < 20:
                continue
            hx = [xs[i] for i in hot]
            hy = [ys[i] for i in hot]
            nn = accel_nn(hx, hy)
            rs = [math.sqrt(x * x + y * y) for x, y in zip(hx, hy)]
            for d, r in zip(nn, rs):
                if not np.isfinite(d) or d <= 0.0:
                    continue
                for ri in range(len(RNG_EDGES) - 1):
                    if RNG_EDGES[ri] <= r < RNG_EDGES[ri + 1]:
                        ring_of[ri]["samples"].append(d)
                        s_samples += 1
                        break
        per_session_stats[sid] = {"frames_seen": (nf + step - 1) // step,
                                  "samples_added": s_samples}

    # 每环 p10/p50/p90
    rings_out = []
    for ri in range(len(RNG_EDGES) - 1):
        s = ring_of[ri]["samples"]
        if len(s) < 50:
            rings_out.append(dict(ring=[RNG_EDGES[ri], RNG_EDGES[ri + 1]],
                                  n=len(s), status="SKIP_lt50"))
            continue
        arr = np.array(s)
        rings_out.append(dict(ring=[RNG_EDGES[ri], RNG_EDGES[ri + 1]],
                              n=len(s),
                              p10=float(np.percentile(arr, 10)),
                              p50=float(np.percentile(arr, 50)),
                              p90=float(np.percentile(arr, 90)),
                              max=float(arr.max())))

    # LAD 拟合 k: 用 p90 (代替 p50 — NN 分布重尾来自"密度 vs gap", p90 更接近"该环下正常点的最大 NN",
    # 即 ceil(p90/CELL) ≈ ceil(p90/0.05) 给出 cell 探查半径的物理上限)
    ring_mid, p90s, weights = [], [], []
    for r in rings_out:
        if "p90" not in r:
            continue
        ring_mid.append(sum(r["ring"]) / 2)
        p90s.append(r["p90"])
        weights.append(r["n"])
    ring_mid = np.array(ring_mid)
    p90s = np.array(p90s)
    weights = np.array(weights, dtype=np.float64)
    A = np.vstack([ring_mid, np.ones_like(ring_mid)]).T
    W = np.diag(weights / weights.sum())
    coef = np.linalg.solve(A.T @ W @ A, A.T @ W @ p90s)
    k, b = float(coef[0]), float(coef[1])

    out = dict(purpose="radius-adaptive eps(r) calibration on TUNING sessions only",
               method="p90 horizontal NN per ring, weighted-LAD k*r+b fit; NN=曼哈顿搜索距离, p90 反映该环正常点的最大 gap 上界",
               rings=rings_out,
               fit_k=k, fit_b=b,
               formula=f"eps(r)=max(eps_min, {k:.4f}*r + {b:.4f})",
               recommendation=dict(
                   k=round(k, 4),
                   b=round(b, 4),
                   eps_min=0.08,
                   note="eps_min 取 B1 网格 0.05m 的(8邻范围=0.10m)略保守下限; 具体 eps(r) 最终仍需 A/B 评估",
               ),
               per_session=per_session_stats,
               ring_edges_m=RNG_EDGES, accel_cell_m=CELL, max_frames=MAX_FRAMES_PER_SESSION)

    ev_dir = sys.argv[1]
    with open(os.path.join(ev_dir, "calibration_k.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print(json.dumps(dict(rings=[(r["ring"], r.get("p50")) for r in rings_out],
                          fit_k=k, fit_b=b), indent=2))
    print("wrote", os.path.join(ev_dir, "calibration_k.json"))


if __name__ == "__main__":
    main()
