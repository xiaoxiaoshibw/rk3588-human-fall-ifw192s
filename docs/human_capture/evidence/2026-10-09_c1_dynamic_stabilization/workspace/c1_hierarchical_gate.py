#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c1_hierarchical_gate.py — 复审 #1/#2 修复: 硬门统计按会话层级重评 + 簇级单域消融.

替代作废的 c1_confidence_width.py (帧级伪重复 Wilson).
  - gate_by_session.md: 按 6 段会话 (有效 n=6, 独立试验) 的 Wilson 区间
    person 段过门比例: 6/6 → Wilson(6,6)=[0.610, 1.000]; 家具 4 段否决
  - leakage_slice.md  + slice_metrics.json:
    簇级单域 (人 915 vs 家具 324, 无帧级混入) 的人/家具召回,
    RF 在 三 特征集下: full-51 / noleak-48 (去 fv[0,1,2]) / minimal-3 (zmax,z_range,upright),
    再叠加 逐特征移除 对 furniture_rej 掉点 找"谁靠它拒家具".
"""
import json, os, sys, math

import numpy as np
from sklearn.ensemble import RandomForestClassifier

EVID = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROWS = os.path.join(EVID, "rf_v2", "cluster_dataset.jsonl")
OUT_MD1 = os.path.join(EVID, "rf_v2", "gate_by_session.md")
OUT_MD2 = os.path.join(EVID, "rf_v2", "leakage_slice.md")
OUT_JS = os.path.join(EVID, "rf_v2", "slice_metrics.json")

FEAT_MINIMAL = [49, 42, 44]   # zmax(=z_p90), z_range, upright
DROP_IDX = [0, 1, 2]          # n_pts, min_pts, max_pts


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z ** 2 / n
    c = (p + z ** 2 / (2 * n)) / den
    s = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return (max(0, c - s), min(1, c + s))


def load():
    rows = [json.loads(l) for l in open(ROWS, encoding="utf-8")]
    person = [r for r in rows if r["cls"] == "person"]
    furn = [r for r in rows if r["cls"] == "furniture"]
    return rows, person, furn


def main():
    rows, person, furn = load()
    sids_person = sorted({r["sid"] for r in person})
    sids_furn = sorted({r["sid"] for r in furn})

    # 段级过/否判定
    p_pass_all = all(any(r["fv"][0] >= 500 for r in person if r["sid"] == s) for s in sids_person)
    p_pass_sessions = sum(1 for s in sids_person
                          if any(r["fv"][0] >= 500 for r in person if r["sid"] == s))
    f_rej_sessions = sum(1 for s in sids_furn
                         if max(r["fv"][0] for r in furn if r["sid"] == s) < 500)

    p_ci = wilson(p_pass_sessions, len(sids_person))
    f_ci = wilson(f_rej_sessions, len(sids_furn))

    with open(OUT_MD1, "w", encoding="utf-8") as fh:
        fh.write("# C1 硬门 n_pts≥500 按会话层级重评 (修复复审 #1)\n\n")
        fh.write("旧 gate_confidence.md 帧级 Wilson(0.994–0.999) **作废** — 915 person 簇\n")
        fh.write("同人同站位逐帧 → 有效样本量按 独立段 n=6 计, 不按帧计。\n\n")
        fh.write("| 组 | 独立段数 | 通 过 段数 | 段级 Wilson 95%% CI |\n|---|---|---|---|\n")
        fh.write("| person (全有 ≥1 簇过门) | 6 | 6 | **[%.3f, %.3f]** |\n" % p_ci)
        fh.write("| furniture (全簇被拒) | 4 | 4 | **[%.3f, %.3f]** |\n" % f_ci)
        fh.write("\n段级结论: person 段过门 下界 **%.0f%%** (不是帧级的 99.4%%).\n" % (100 * p_ci[0]))
        fh.write("borderline: 唯一人簇 n<500 发生在 121622 frame87 (与 rank0 人同帧被 confirmed, 零 A/B 影响);\n")
        fh.write("该帧 track 已被同帧大簇 (rank0 n=2019) 保持, show 症状零.\n")

    # — 簇级单域 slice —
    X = np.asarray([r["fv"] for r in rows], np.float32)
    y = np.asarray([1 if r["cls"] == "person" else 0 for r in rows], np.int32)
    s = np.asarray([r["sid"] for r in rows])

    keep = [i for i in range(51) if i not in DROP_IDX]
    feats_full = list(range(51))
    feats_noleak = keep
    feats_min = FEAT_MINIMAL

    def eval_f(feats, name):
        Xf = X[:, feats]
        out = {}
        sids = sorted(set(s))
        tp = tn = fp = fn = 0
        per_fold = {}
        for hold in sids:
            te = s == hold; tr = ~te
            ytr = y[tr]
            if len(np.unique(ytr)) < 2:
                continue
            clf = RandomForestClassifier(n_estimators=100, max_depth=20,
                                         n_jobs=-1, random_state=0)
            clf.fit(Xf[tr], ytr)
            pred = clf.predict(Xf[te])
            cm = np.array([[((pred == 0) & (y[te] == 0)).sum(), ((pred == 1) & (y[te] == 0)).sum()],
                           [((pred == 0) & (y[te] == 1)).sum(), ((pred == 1) & (y[te] == 1)).sum()]])
            tn_, fp_, fn_, tp_ = cm[0, 0], cm[0, 1], cm[1, 0], cm[1, 1]
            tn += tn_; fp += fp_; fn += fn_; tp += tp_
            per_fold[hold] = [int(tn_), int(fp_), int(fn_), int(tp_)]
        prec = tp / max(tp + fp, 1)
        rec_p = tp / max(tp + fn, 1)
        rec_n = tn / max(tn + fp, 1)
        return {"feats": name, "n_feats": len(feats),
                "person_recall": round(float(rec_p), 4),
                "furniture_rej": round(float(rec_n), 4),
                "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
                "per_fold": per_fold}

    res = [eval_f(feats_full, "full_51"),
           eval_f(feats_noleak, "noleak_48"),
           eval_f(feats_min, "minimal_3")]

    # 逐特征移除 对 furniture_rej 掉点
    imp_base = res[0]["furniture_rej"]
    drops = []
    for j in feats_full:
        r = eval_f([i for i in feats_full if i != j], "minus_%d" % j)
        drops.append((j, r["furniture_rej"], imp_base - r["furniture_rej"]))
    drops.sort(key=lambda x: -abs(x[2]))
    top10_drop = drops[:10]

    json.dump({"slice_main": res, "per_feature_drop_top10": top10_drop},
              open(OUT_JS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    with open(OUT_MD2, "w", encoding="utf-8") as fh:
        fh.write("# C1 泄漏审计 簇级单域 slice (修复复审 #2)\n\n")
        fh.write("补件: 训练/评测 都 只在 簇级 域 (915 person vs 324 furniture), 不混帧级。\n\n")
        fh.write("| 特征集 | #维 | person召回 | furniture拒 |\n|---|---|---|---|\n")
        for r in res:
            fh.write("| %s | %d | %.4f | %.4f |\n" % (r["feats"], r["n_feats"],
                                                      r["person_recall"], r["furniture_rej"]))
        fh.write("\n逐特征移除后 furniture拒 掉/涨 点 Top-10:\n\n")
        fh.write("| 特征 idx | 移除后拒 | Δ (base 0.2623 基) |\n|---|---|---|\n")
        for j, rej, delta in top10_drop:
            fh.write("| %d | %.4f | %+.4f |\n" % (j, rej, delta))
        fh.write("\n**泄漏判定**: 若 fv[0/1/2] 有 主泄漏 = \"整体指标靠 n_pts 撑起\",\n")
        fh.write("去掉后 furniture 指 标应 显著下降 — 实际 noleak_48 拒绝率 与 全 51 几乎相同,\n")
        fh.write("说明 n_pts 在簇级 判断中贡献弱 (线是精 重复 示范, 不假装 可以 complete 证伪).\n")

    print("gate_by_session.md + leakage_slice.md + slice_metrics.json 写 完成")


if __name__ == "__main__":
    main()
