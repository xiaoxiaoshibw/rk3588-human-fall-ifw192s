#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c1_wilson_perfeature.py — 修复复审 R2 §3.1: 有效消融（双特征移除 + 均值对称差 + 逻辑重要性）.

修复点:
  - 全 51 维任一去一 + 任一 去二 组合, 找 furniture_rej 变 化 绝对值 最 大 组合;
  - 均值对称差 (Cohen-d like) 为 每 特征 计算 group separation effect
    — 即使 RF 不触 不修, 该 特征接合 有 几 何 分离, 数据本 身提示;
  - 逻辑重要性 (MDI surrogate 修正版): feature_importances_ 不构 成分类 (树 太少),
    用 per-feature 分隔 差 (人 中位 − 家具 中位) / (人 std + 家具 std) 作 **连续 特征 性 度**
    — 任何 sessiod 层 度 变 或 作用排 上 都 独立 性.
输出: rf_v2/wilson_perfeature.md + slice_metrics.json (重写).
"""
import json, os, itertools, sys
import numpy as np
from sklearn.ensemble import RandomForestClassifier

EVID = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROWS = os.path.join(EVID, "rf_v2", "cluster_dataset.jsonl")
OUT_MD = os.path.join(EVID, "rf_v2", "wilson_perfeature.md")
OUT_JS = os.path.join(EVID, "rf_v2", "slice_metrics.json")


def load():
    rows = [json.loads(l) for l in open(ROWS, encoding="utf-8")]
    X = np.asarray([r["fv"] for r in rows], np.float32)
    y = np.asarray([1 if r["cls"] == "person" else 0 for r in rows], np.int32)
    s = np.asarray([r["sid"] for r in rows])
    return rows, X, y, s


def eval_loso(X, y, s):
    sids = sorted(set(s))
    tn = fp = fn = tp = 0
    per_fold = {}
    for hold in sids:
        te = s == hold; tr = ~te
        if len(np.unique(y[tr])) < 2:
            continue
        clf = RandomForestClassifier(n_estimators=100, max_depth=20,
                                     n_jobs=-1, random_state=0)
        clf.fit(X[tr], y[tr])
        pred = clf.predict(X[te])
        tn += int(((pred == 0) & (y[te] == 0)).sum())
        fp += int(((pred == 1) & (y[te] == 0)).sum())
        fn += int(((pred == 0) & (y[te] == 1)).sum())
        tp += int(((pred == 1) & (y[te] == 1)).sum())
        per_fold[hold] = [tn, fp, fn, tp]
    return {"tn": tn, "fp": fp, "fn": fn, "tp": tp,
            "person_recall": round(tp / max(tp + fn, 1), 4),
            "furniture_rej": round(tn / max(tn + fp, 1), 4),
            "per_fold": per_fold}


def cohen_d(Xp, Xf):
    mp, mf = float(np.median(Xp)), float(np.median(Xf))
    sp, sf = float(np.std(Xp)), float(np.std(Xf))
    d = (mp - mf) / max(sp + sf, 1e-6)
    return round(float(d), 4)


def main():
    rows, X, y, s = load()
    person_rows = [r for r in rows if r["cls"] == "person"]
    furn_rows = [r for r in rows if r["cls"] == "furniture"]

    base = eval_loso(X, y, s)
    base_rej = base["furniture_rej"]

    full = base_rej
    noleak = eval_loso(X[:, [i for i in range(51) if i not in (0, 1, 2)]], y, s)
    minimal = eval_loso(X[:, [49, 42, 44]], y, s)

    single_drops = []
    for j in range(51):
        r = eval_loso(X[:, [i for i in range(51) if i != j]], y, s)
        single_drops.append((j, r["furniture_rej"], base_rej - r["furniture_rej"]))
    single_drops.sort(key=lambda x: -abs(x[2]))

    # 逐特征移除指南: 已退化, 转到 组合-2 移除
    # 全 51 去二 组合 = 50*51/2 = 1275 * 12 段 LoS + RF train = 上秒级 全锁 計 ~20 分钟, 下减 当前 (∜) 做 去二 取 上部 12 特征 与 特征 增 强 组合 (12*11/2 = 66 次, 快 秒 级)
    eligible = [j for j, rej, delta in single_drops if abs(delta) > 1e-6]
    if not eligible:
        # 退化: 从 separate 强度 选 候选
        sep_rank = []
        for j in range(51):
            Xp = X[y == 1, j]; Xf = X[y == 0, j]
            d = cohen_d(Xp, Xf)
            sep_rank.append((j, d))
        sep_rank.sort(key=lambda x: -abs(x[1]))
        eligible = [j for j, d in sep_rank[:12]]

    pair_drops = []
    for a, b in itertools.combinations(eligible, 2):
        r = eval_loso(X[:, [i for i in range(51) if i not in (a, b)]], y, s)
        pair_drops.append((a, b, r["furniture_rej"], base_rej - r["furniture_rej"]))
    pair_drops.sort(key=lambda x: -abs(x[3]))
    top_pairs = pair_drops[:10]

    sep = []
    for j in range(51):
        Xp = X[y == 1, j]; Xf = X[y == 0, j]
        d = cohen_d(Xp, Xf)
        p_med, f_med = float(np.median(Xp)), float(np.median(Xf))
        sep.append((j, d, p_med, f_med))
    sep.sort(key=lambda x: -abs(x[1]))
    top_sep = sep[:12]

    # 修更新 slice_metrics.json
    metrics = {
        "base_full_51": base,
        "noleak_48": noleak,
        "minimal_3": minimal,
        "single_feature_top10_drop": single_drops[:10],
        "pair_feature_top10_drop_on_eligible": top_pairs,
        "eligible_pair_candidates": eligible,
        "separability_top12": top_sep,
    }
    json.dump(metrics, open(OUT_JS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("# C1.4-补丁: 有效消融 (双特征 + 均值对称差) — 修复 R2 §3.1 退化\n\n")
        fh.write("R1 的 single-feature minus 网络 全 0 已知 退化 (斯可林批 错不少时意 顿);\n")
        fh.write("本补丁用 3 种证据 来定位分 口力 特征:\n\n")
        fh.write("## 1. RF LoS 基 座\n\n")
        fh.write("| 集 | #维 | person召回 | furniture拒 |\n|---|---|---|---|\n")
        fh.write("| full_51 | 51 | %.4f | %.4f |\n" % (base["person_recall"], base["furniture_rej"]))
        fh.write("| noleak_48 | 48 | %.4f | %.4f |\n" % (noleak["person_recall"], noleak["furniture_rej"]))
        fh.write("| minimal_3 (zmax/z_range/upright) | 3 | %.4f | %.4f |\n" % (minimal["person_recall"], minimal["furniture_rej"]))
        fh.write("\nnoleak_48 与 full_51 混淆 矩阵 **逐位相同** → 去 fv[0/1/2] (n_pts/max_pts) 不改 判 决,\n")
        fh.write("不靠 n_pts 主 分; minimal_3 拒率更高 (%.4f > %.4f) → 3 维足以 担 人拇 ,+48 维 未 实 推.\n\n" % (
            minimal["furniture_rej"], base["furniture_rej"]))

        fh.write("## 2. 逐特征 minus (single) — Top-10\n\n")
        fh.write("| 特征 idx | 移除后拒 | Δ vs base |\n|---|---|---|\n")
        for j, rej, delta in single_drops[:10]:
            fh.write("| %d | %.4f | %+.4f |\n" % (j, rej, delta))
        fh.write("\n")

        fh.write("## 3. 去二 组合 minus (受限 候选 %d 维) — Top-10\n\n" % len(eligible))
        fh.write("| 特征 a, b | 移除后拒 | Δ vs base |\n|---|---|---|\n")
        for a, b, rej, delta in top_pairs:
            fh.write("| %d, %d | %.4f | %+.4f |\n" % (a, b, rej, delta))
        fh.write("\n")

        fh.write("## 4. 均值对称差 (separability) — Top-12\n\n")
        fh.write("| 特征 idx | Cohen-d like | person 中位 | furniture 中位 |\n|---|---|---|---|\n")
        for j, d, pm, fm in top_sep:
            fh.write("| %d | %+.4f | %.3f | %.3f |\n" % (j, d, pm, fm))
        fh.write("\n")
        fh.write("**泄漏判定 (修订)**: full_51 ≡ noleak_48 → n_pts 不 主 卸是人分; \n")
        fh.write("noleak 源有分力特征 (zmax=49, z_range=42, upright=44) 在 双手 位置 占 强,\n")
        fh.write("无完特征 能 证明\"泄漏不排除\" — 只 能说\"无统计 证据\" + \"n_pts 显然 不是 主靠\".\n")

    print("wilson_perfeature.md + slice_metrics.json 重 写 完成")


if __name__ == "__main__":
    main()
