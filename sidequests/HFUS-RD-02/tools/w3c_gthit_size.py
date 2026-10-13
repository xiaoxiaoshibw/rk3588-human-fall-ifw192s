# -*- coding: utf-8 -*-
"""W3 补：C4 系列"GT 命中簇"的尺寸分布——检验 100% 召回是否可用于生产。

逻辑：生产 ledger 事实（W1）：n>=2000 候选 258 个，接受率 0%；即房间级
大团会被 RF 拒（prob≈0.0029）。若 C4 对某 GT 对象的最佳簇是 n>=2000 的
大团，则该 GT 在生产打分下仍会被拒 → 纸面召回，不是可救召回。

对每个 reviewed GT 对象（7 有效会话），在 GT 帧上跑 C4/C4A/C4C，取
"覆盖该 GT 最多点的簇"，记录其点数与覆盖率。输出分桶统计：
  rescue_ready : 60 <= n <= 1999（生产可打分的人形尺度）
  big_blob     : n >= 2000（生产必拒）
  too_small    : n < 60（进不了生产 n>=60 门）

输出 evidence/W3C_GTHIT_SIZE.json。
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..",
    "HFUS-RD-01", "tools")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
from w3_c4_opt import c4_core, v_roi  # noqa: E402
from d2_cluster_ablation import xy_voxel_clusters  # noqa: E402

EVID = os.path.join(C.REPO, "docs", "sidequests", "evidence",
                    "2026-10-12_HFUS_RD_02_r1")


def gt_hit_sizes(sid, variants_out):
    gt = C.load_gt(sid)
    objs_by_frame = defaultdict(list)
    if not gt:
        return
    for o in gt["objects"]:
        if (o["class_name"] == "PERSON"
                and o["review_status"] == "reviewed"
                and o["source"] == "human"):
            objs_by_frame[o["frame_idx"]].append(o)
    mm = None
    for fi in sorted(objs_by_frame.keys()):
        xyz, _i, mm = C.read_frame_xyz(sid, fi, mm=mm)
        lev = C.level(xyz)
        mask = np.isfinite(lev).all(axis=1) & (lev != 0).any(axis=1)
        vid = np.nonzero(mask)[0]
        pts = lev[vid]
        rol = np.nonzero(np.isfinite(xyz).all(axis=1)
                         & (xyz != 0).any(axis=1))[0]
        gt_sets = [set(C.gt_raw_indices(o, rol).tolist())
                   for o in objs_by_frame[fi]]
        # C4
        cl_c4 = c4_core(pts)
        # C4A
        cl_roi = v_roi(pts)
        for name, cl in (("C4_FROZEN", cl_c4), ("C4A_ROI", cl_roi)):
            cl_raw = [set(vid[np.asarray(g, dtype=np.int64)].tolist())
                      for g in cl]
            for gi, gs in enumerate(gt_sets):
                best_n, best_cov = 0, 0.0
                for cs in cl_raw:
                    inter = len(cs & gs)
                    cov = inter / max(1, len(gs))
                    if cov > best_cov:
                        best_cov, best_n = cov, len(cs)
                variants_out[name].append(
                    {"sid": sid, "frame": fi, "gi": gi,
                     "best_cov": round(best_cov, 3), "best_n": best_n})


def bucket(n):
    if n >= 2000:
        return "big_blob_ge2000"
    if n >= 60:
        return "rescue_ready_60_1999"
    if n >= 15:
        return "thin_15_59"
    return "too_small_lt15"


def main():
    out = defaultdict(list)
    for sid in C.SIDS:
        if sid == "cap_20261010_180751":
            continue   # S9 INVALID_BINDING
        gt_hit_sizes(sid, out)
        print("[w3c] %s done" % C.SID_SHORT[sid])
    report = {"date": "2026-10-12",
              "definition": ("每 GT 对象取覆盖它最多的簇；n>=2000 → 生产 "
                             "RF 必拒（ledger 实测 0/258 接受）；60-1999 → "
                             "可进生产打分；<60 → 被 n>=60 门拒。"),
              "variants": {}}
    for name, rows in out.items():
        cov50 = [r for r in rows if r["best_cov"] >= 0.5]
        buckets = defaultdict(int)
        for r in cov50:
            buckets[bucket(r["best_n"])] += 1
        report["variants"][name] = {
            "gt_objects": len(rows),
            "cov50_objects": len(cov50),
            "cov50_by_best_cluster_size": dict(buckets),
            "rescue_ready_frac_of_cov50": round(
                buckets.get("rescue_ready_60_1999", 0) / max(len(cov50), 1), 3),
            "per_session": {
                b: {
                    "cov50": sum(1 for r in cov50 if r["sid"] == b),
                    "rescue_ready": sum(1 for r in cov50 if r["sid"] == b
                                        and bucket(r["best_n"])
                                        == "rescue_ready_60_1999"),
                    "big_blob": sum(1 for r in cov50 if r["sid"] == b
                                    and bucket(r["best_n"])
                                    == "big_blob_ge2000")}
                for b in sorted(set(r["sid"] for r in rows))},
        }
        v = report["variants"][name]
        print("[w3c] %s: gt=%d cov50=%d rescue_ready=%d (%.0f%%) big_blob=%d"
              % (name, v["gt_objects"], v["cov50_objects"],
                 buckets.get("rescue_ready_60_1999", 0),
                 100 * v["rescue_ready_frac_of_cov50"],
                 buckets.get("big_blob_ge2000", 0)))
    op = os.path.join(EVID, "W3C_GTHIT_SIZE.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("[w3c] written", op)


if __name__ == "__main__":
    main()
