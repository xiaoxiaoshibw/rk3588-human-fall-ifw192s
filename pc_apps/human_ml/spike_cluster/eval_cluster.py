# -*- coding: utf-8 -*-
"""eval_cluster.py — A/B/C 在 E0 评估会话上全量逐帧对比, 产出 per-frame JSONL + 汇总.

跑法: python -B eval_cluster.py <evidence_dir> <params_frozen.json>
产出:
  eval_frames.jsonl  — 每帧 × 每算法 (A/B/C) × 会话: 簇统计 + GT 命中 + 指标
  eval_summary.json  — 分层汇总 (Wilson CI by track-run, 距离带, 动静)
不做: 不写生产、不训 RF、不上板.
"""
import json
import math
import os
import sys
import time
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from _harness_lib import (find_clusters_A, find_clusters_BC, find_hot_js,  # noqa: E402
                          load_bg_envelope, make_eps_fn, cluster_summary)
from _harness_lib_v2 import find_clusters_C_pointband  # noqa: E402

R_MAT = np.array([[0.893544, 0.0, 0.448975],
                  [-0.014337, 0.99949, 0.028533],
                  [-0.448746, -0.031932, 0.893089]], dtype=np.float32)
T_MAT = np.array([0.0, 0.0, 1.380286], dtype=np.float32)

# GT 锚点 (来自 evidence GT 勘查回报; unit: 米, leveled 系)
GT_ANCHORS = {
    # 12 段站立 (11 段有 ai_labels + 215540 README)
    "cap_20261009_114709": {"type": "stand", "xy": (1.767, 1.127), "r": 0.55},
    "cap_20261009_114734": {"type": "stand_side", "xy": (1.70, 1.08), "r": 0.55},
    "cap_20261009_114754": {"type": "stand", "xy": (1.13, 0.50), "r": 0.55},
    "cap_20261009_114817": {"type": "stand", "xy": (2.15, 1.12), "r": 0.55},
    "cap_20261009_121622": {"type": "stand", "xy": (1.75, 0.85), "r": 0.55},
    "cap_20261009_121647": {"type": "stand", "xy": (1.18, 0.51), "r": 0.55},
    "cap_20261009_121723": {"type": "stand", "xy": (2.41, 1.22), "r": 0.55},
    "cap_20261009_122616": {"type": "stand", "xy": (1.68, 1.02), "r": 0.55},
    "cap_20261009_122637": {"type": "stand", "xy": (1.17, 0.47), "r": 0.55},
    "cap_20261009_122700": {"type": "stand", "xy": (2.48, 1.50), "r": 0.55},
    "cap_20261009_114641": {"type": "stand", "xy": (1.76, 1.15), "r": 0.55},
    "cap_20261007_215540": {"type": "still", "xy": (2.10, -0.57), "r": 0.55},
    # 空场 (无人): hot 期望 0
    "cap_20261009_113611": {"type": "empty", "xy": None, "r": None},
    # 参考 (描述性)
    "cap_20261008_114205": {"type": "still", "xy": (1.80, 0.85), "r": 0.55},   # 配准_C1 中央空处静立 (估)
    "cap_20261008_114254": {"type": "still", "xy": (1.80, 0.85), "r": 0.55},
    "cap_20261008_114340": {"type": "still", "xy": (1.80, 0.85), "r": 0.55},
    "cap_20261008_114422": {"type": "still", "xy": (1.80, 0.85), "r": 0.55},
}

# 柜位锚点 (来自 b2a_shadow_r1 flicker_analysis.json, unit: 米 leveled)
CABINET_ANCHORS = {
    "cap_20261009_121622": (3.00, 1.14),
    "cap_20261009_121647": (3.63, 0.78),
    "cap_20261009_122616": (2.89, 1.25),
    "cap_20261009_122637": (3.66, 0.74),
}


def load_frame_xyzi(sd, fn):
    meta = json.load(open(os.path.join(sd, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(sd, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, 28).view(np.float32).reshape(-1, 7)
    f = meta["frames"][fn]
    seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
    lv = (seg[:, :3].astype(np.float32) @ R_MAT.T + T_MAT).astype(np.float32)
    return lv, seg[:, 3].astype(np.float32)  # (N,3) leveled, (N,) intensity


def dist_to_anchor(cx, cy, anchor_xy):
    return math.hypot(cx - anchor_xy[0], cy - anchor_xy[1])


def evaluate_frame(lv, fn, sid, bg, gt_anchor, cabinet_xy, params):
    """每帧 × 每算法 (A, B, C) 评估. 返回一行 dict."""
    xs = lv[:, 0].tolist()
    ys = lv[:, 1].tolist()
    zs = lv[:, 2].tolist()
    out = {"session": sid, "frame": fn}

    # ---- find_hot (3 算法共享; 不算入方法耗时分划) ----
    t0 = time.perf_counter()
    hot = find_hot_js(xs, ys, zs, bg, 0.1, 2.3)
    hot_ms = (time.perf_counter() - t0) * 1000.0
    out["n_hot"] = len(hot)
    out["ms_hot"] = round(hot_ms, 2)

    if not hot:
        for v in ("A", "B", "C"):
            out[v] = {"n_comps_top": 0, "attribution": "no_hot_background_absorbed"}
        return out

    # ---- A ----
    t0 = time.perf_counter()
    comps_A, st_A = find_clusters_A(xs, ys, hot)
    a_ms = (time.perf_counter() - t0) * 1000.0
    out["A"] = summarize_variant(comps_A, st_A, xs, ys, zs, gt_anchor, cabinet_xy, cid="A")
    out["A"]["ms_cluster"] = round(a_ms, 3)

    # ---- B ----
    eps_fn, eps_meta = make_eps_fn(params["k"], params["eps_min"])
    t0 = time.perf_counter()
    comps_B, st_B = find_clusters_BC(xs, ys, zs, hot, eps_fn,
                                      bridge_policy=None, symmetric=True)
    b_ms = (time.perf_counter() - t0) * 1000.0
    out["B"] = summarize_variant(comps_B, st_B, xs, ys, zs, gt_anchor, cabinet_xy, cid="B")
    out["B"]["ms_cluster"] = round(b_ms, 3)
    out["B"]["params"] = eps_meta

    # ---- C = B + 点级 z-band 防并簇 (v2 修正: cell mean z → subcell-key) ----
    t0 = time.perf_counter()
    comps_C, st_C = find_clusters_C_pointband(xs, ys, zs, hot, eps_fn,
                                               wall_bands=params["wall_bands"])
    c_ms = (time.perf_counter() - t0) * 1000.0
    out["C"] = summarize_variant(comps_C, st_C, xs, ys, zs, gt_anchor, cabinet_xy, cid="C")
    out["C"]["ms_cluster"] = round(c_ms, 3)
    out["C"]["params"] = dict(eps_meta, wall_bands=params["wall_bands"])
    return out


def summarize_variant(comps, st, xs, ys, zs, gt_anchor, cabinet_xy, cid):
    s = {"n_comps_top": len(comps), "n_cells": st["n_cells"],
         "n_comps_total": st["n_comps"], "clusters": []}
    for i, c in enumerate(comps):
        cs = cluster_summary(c, xs, ys, zs)
        r = math.hypot(cs["cx"], cs["cy"])
        d_anchor = (dist_to_anchor(cs["cx"], cs["cy"], gt_anchor["xy"])
                    if gt_anchor and gt_anchor["xy"] else None)
        d_cab = dist_to_anchor(cs["cx"], cs["cy"], cabinet_xy) if cabinet_xy else None
        # IoU on anchor disk (在 GT r 圆内的成员占比)
        frac_in = None
        if gt_anchor and gt_anchor["xy"] and gt_anchor["r"]:
            ax, ay = gt_anchor["xy"]
            ar2 = gt_anchor["r"] ** 2
            inside = sum(1 for k in c
                         if (xs[k] - ax) ** 2 + (ys[k] - ay) ** 2 <= ar2)
            frac_in = inside / max(1, len(c))
            s["clusters"].append(dict(
                rank=i, n=cs["n"], cx=round(cs["cx"], 3), cy=round(cs["cy"], 3),
                r=round(r, 3), r90=round(cs["r90"], 3), zmax=round(cs["zmax"], 3),
                d_anchor=round(d_anchor, 3) if d_anchor is not None else None,
                d_cabinet=round(d_cab, 3) if d_cab is not None else None,
                frac_in_anchor=round(frac_in, 3) if frac_in is not None else None))
        else:
            s["clusters"].append(dict(
                rank=i, n=cs["n"], cx=round(cs["cx"], 3), cy=round(cs["cy"], 3),
                r=round(r, 3), r90=round(cs["r90"], 3), zmax=round(cs["zmax"], 3),
                d_anchor=None, d_cabinet=None, frac_in_anchor=None))
    return s


def iter_sessions_frames(sids, max_frames_per_session=None, frame_step=1):
    for sid in sids:
        sd = os.path.join(REPO, "captures", "remote", sid)
        if not os.path.isfile(os.path.join(sd, "points.bin")):
            continue
        meta = json.load(open(os.path.join(sd, "meta.json"), encoding="utf-8"))
        nf = len(meta["frames"])
        n_eff = nf if max_frames_per_session is None else min(nf, max_frames_per_session)
        step = max(1, nf // max(1, n_eff)) * frame_step
        for fi in range(0, nf, step):
            yield sid, sd, fi, nf, meta


def main():
    ev_dir = sys.argv[1]
    params_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ev_dir, "params_frozen.json")
    max_frames = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    params = json.load(open(params_path, encoding="utf-8"))

    sids_eval = list(GT_ANCHORS.keys())
    # 121622 等含柜位的会话: 加柜位锚. 121723/122700 无柜位复发则不加.
    frames_out = []
    bg = load_bg_envelope(os.path.join(REPO, "pc_apps", "human_replay", "bg_envelope.json"))

    n_proc = 0
    for sid, sd, fi, nf, meta in iter_sessions_frames(sids_eval, max_frames_per_session=max_frames):
        gt = GT_ANCHORS[sid]
        lv, _ = load_frame_xyzi(sd, fi)
        rec = evaluate_frame(lv, fi, sid, bg, gt, CABINET_ANCHORS.get(sid), params)
        rec["gt_type"] = gt["type"]
        frames_out.append(rec)
        n_proc += 1
        if n_proc % 60 == 0:
            print("...%d frames processed (sid=%s f%d/%d)" % (n_proc, sid, fi, nf))

    fl_path = os.path.join(ev_dir, "eval_frames.jsonl")
    with open(fl_path, "w", encoding="utf-8") as fh:
        for rec in frames_out:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("wrote", fl_path, "n_frames=", len(frames_out))

    # ---- summary (先粗聚合, 详细 Wilson by-track-run 在 summarize 里) ----
    per_variant_ms = defaultdict(list)
    for rec in frames_out:
        for v in ("A", "B", "C"):
            if v in rec and "ms_cluster" in rec[v]:
                per_variant_ms[v].append(rec[v]["ms_cluster"])
    summary_ms = {v: {"n": len(a),
                      "p50": float(np.percentile(a, 50)) if a else None,
                      "p95": float(np.percentile(a, 95)) if a else None,
                      "mean": float(np.mean(a)) if a else None}
                  for v, a in per_variant_ms.items()}
    with open(os.path.join(ev_dir, "eval_timing_ms.json"), "w", encoding="utf-8") as fh:
        json.dump(summary_ms, fh, indent=2)
    print("timing:", json.dumps(summary_ms, indent=2))


if __name__ == "__main__":
    main()
