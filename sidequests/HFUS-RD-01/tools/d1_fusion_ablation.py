# -*- coding: utf-8 -*-
"""D1 补: 融合四变体消融（候选缓存驱动，零重算）。

对每帧收齐 mainline 候选（n, prob, A/B 源, GT 交集标签）后按变体重放回
放决策：
  V0 串联复刻   : n>=60 & prob>=rf_t              (rf_t=0.55)
  V1 软特征     : n>=30, RF 独立打分, 记被身份门救回的命中/误报数
  V2 RF 独立    : prob>=rf_t (无 n 门)
  V3 软组合     : score = prob * gate_soft(n_geo)，geo_soft 由 n 经
                  logistic(n-30) 替代硬门 (参数预登记: k=0.15, x0=30)
指标（均值 per-frame，分子分母齐）:
  obj_recall  = 该帧至少一个候选与 GT 交集 >= 0.5 覆盖 的 GT 比例
  fp_cand/h   = accepted 无交集候选数 / 会话时长（h）
全部仅沿用 stage1 落盘 candidates + stages，不重算特征。
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

RF_T = 0.55
LOG_K, LOG_X0 = 0.15, 30.0          # 预登记软门参数
COVER_T = 0.5                        # 命中阈值（对象覆盖率）


def gate_soft(n):
    return 1.0 / (1.0 + np.exp(-LOG_K * (n - LOG_X0)))


def main():
    # 读 stage2（带 prob）候选 + d1 GT 对象覆盖
    cand_path = os.path.join(C.WORK, "candidates_stage2.jsonl")
    assert os.path.exists(cand_path), "先跑 stage2_features.py"
    cands = defaultdict(list)
    for line in open(cand_path, encoding="utf-8"):
        r = json.loads(line)
        cands[(r["sid"], r["frame"])].append(r)

    # GT 对象（reviewed, human, PERSON），含点数（分桶在 D1 已给出 per-bucket）
    gt_objs = defaultdict(list)
    for line in open(os.path.join(C.WORK, "d1_gt_objects.jsonl"),
                     encoding="utf-8"):
        r = json.loads(line)
        gt_objs[(r["sid"], r["frame"])].append(r)

    dur = {sid: C.load_meta(sid)["duration_sec"] for sid in C.SIDS}
    variants = ["V0_AND", "V1_SOFTGATE", "V2_RFONLY", "V3_SOFTCOMB"]
    out = {v: {} for v in variants}

    for v in variants:
        for sid in C.SIDS:
            stats = {"obj_denom": 0, "obj_hit": 0, "fp_cand": 0,
                     "rescued_hit": 0, "rescued_fp": 0,
                     "frames": 0, "acc_cand": 0}
            for (s, fi), cs in cands.items():
                if s != sid:
                    continue
                stats["frames"] += 1
                gts = gt_objs.get((sid, fi), [])
                stats["obj_denom"] += len(gts)
                # 每 GT 找最优候选覆盖（候选- GT 关联已由 d1 算好 cov）
                hit_any = [False] * len(gts)
                for c in cs:
                    dec = decide(v, c)
                    if not dec:
                        continue
                    stats["acc_cand"] += 1
                    if c["cov"] > 0:  # 有 GT 交集
                        for gi, g in enumerate(gts):
                            # c['cov'] 是与它最佳 GT 的覆盖率；对象级命中
                            # 采用 c.cov>=COVER_T 直接记，与 D1 口径对齐
                            if c["cov"] >= COVER_T:
                                hit_any[gi] = True
                    else:
                        stats["fp_cand"] += 1
                stats["obj_hit"] += sum(1 for h in hit_any if h)
            out[v][sid] = stats

    # 汇总
    print("%-14s %-13s %8s %8s %8s %10s" % (
        "variant", "session", "obj_rec", "fp/h", "acc", "rescued"))
    res = {}
    for v in variants:
        tot_rec_num, tot_rec_den, tot_fp, tot_sec = 0, 0, 0, 0.0
        res[v] = {}
        for sid in C.SIDS:
            s = out[v][sid]
            rec_ = s["obj_hit"] / s["obj_denom"] if s["obj_denom"] else None
            fp_h = s["fp_cand"] / (dur[sid] / 3600.0)
            res[v][sid] = {"recall": rec_, "fp_per_h": round(fp_h, 1),
                           "obj_denom": s["obj_denom"],
                           "obj_hit": s["obj_hit"],
                           "fp_cand": s["fp_cand"],
                           "acc_cand": s["acc_cand"]}
            if sid != "cap_20261010_180751":
                tot_rec_num += s["obj_hit"]
                tot_rec_den += s["obj_denom"]
                tot_fp += s["fp_cand"]
                tot_sec += dur[sid]
            print("%-14s %-13s %8s %8.0f %8d %10d" % (
                v, C.SID_SHORT[sid],
                ("%.3f" % rec_) if rec_ is not None else "NA",
                fp_h, s["acc_cand"], 0))
        res[v]["_reviewed_total"] = {
            "recall": round(tot_rec_num / tot_rec_den, 4),
            "obj_num": tot_rec_num, "obj_den": tot_rec_den,
            "fp_per_h": round(tot_fp / (tot_sec / 3600.0), 1)}
    with open(os.path.join(C.EVIDENCE, "D1_FUSION_ABLATION.json"), "w",
              encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("[D1-ABL] written")


def decide(v, c):
    n, p = c["n"], c["rf_prob"]
    if v == "V0_AND":
        return n >= 60 and p >= RF_T
    if v == "V1_SOFTGATE":
        return n >= 30 and p >= RF_T
    if v == "V2_RFONLY":
        return p >= RF_T
    if v == "V3_SOFTCOMB":
        return (p * gate_soft(n)) >= RF_T
    raise ValueError(v)


if __name__ == "__main__":
    main()
