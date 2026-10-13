# -*- coding: utf-8 -*-
"""D3 数据集构建 + 会话级折叠 + 分层采样。

标签三态严格化：
  P     = reviewed PERSON GT 命中的候选（oracle 正样本，cov>0）
  P_FP  = S1 空场家具会话中被 GT 误关联的候选（优先做负例）
  N     = S1 会话中无 GT 交集的候选（空场负例）
  UNK   = 非 S1 会话中无 GT 交集候选（不冒充负例，但 S8-still 除外）
  N_S8  = S8（180557）"静保"会话中、且时间戳在 GT 人标注同帧窗口外的
          无交集候选 —— 历史 qualification 登记 S8 静止段 GT 覆盖良好，
          该段无交集候选可信度较高,仍标记独立来源、单独统计。
策略（预登记）：
  - 正例：全部 P（559 个）。
  - 负例 池 = P_FP + N + N_S8；对每个 fold，从池里按"每会话等权 + 距
    离/点数分层"抽 3× 正例数，避免家具某一会话压垮。
  - UNK 不参与训练/阈值选择；报告时只作参考行。
  - 折叠：train=[175429,175804,175943,175227(S1)] val=[175553]
          test=[180337,180557] stress=[180235]；S9 只探索。
输出 work/d3_dataset.jsonl（行=f51,x18,y,src,sid,fold,cand_n,cov,pur,prob）
"""
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

NEG_PER_POS = 3
REBUILD_T = time.time()


def fold_of(sid):
    for f, sids in C.FOLDS.items():
        if sid in sids:
            return f
    return "explore"


def main():
    pos, neg_pool, unk = [], [], []
    for line in open(os.path.join(C.WORK, "candidates_stage2.jsonl"),
                     encoding="utf-8"):
        r = json.loads(line)
        lab = r["label"]
        fold = fold_of(r["sid"])
        row = {"f51": r["f51"], "x18": r["x18"],
               "y": None, "src": lab, "sid": r["sid"], "fold": fold,
               "frame": r["frame"], "cand": r["cand"], "n": r["n"],
               "cov": r["cov"], "pur": r["pur"], "rf_prob": r["rf_prob"]}
        if lab == "P":
            row["y"] = 1
            pos.append(row)
        elif lab in ("P_FP_S1", "N"):
            row["y"] = 0
            neg_pool.append(row)
        elif lab == "UNK" and r["sid"] == "cap_20261010_180557":
            row["src"] = "N_S8"
            unk.append(row)  # 注册但默认不进负例池; 资格提升须人工 S8 审计
        else:
            unk.append(row)
    print("[D3] pos=%d negpool=%d unk=%d" % (len(pos), len(neg_pool),
                                              len(unk)))

    # 分层采样：每 fold 内按 (点数桶 × 距离桶) 分层抽 3× 正例
    rng = np.random.default_rng(20261012)
    chosen = []
    for fold in ("train", "val", "test", "stress", "explore"):
        fpos = [p for p in pos if p["fold"] == fold]
        fneg = [n for n in neg_pool if n["fold"] == fold]
        need = min(len(fneg), NEG_PER_POS * max(1, len(fpos)))
        if not fneg:
            continue
        # 分层键：点数桶 × 距离粗桶
        def key(r):
            nb = 0 if r["n"] < 30 else (1 if r["n"] < 60 else 2)
            return (nb, 0)
        strata = defaultdict(list)
        for r in fneg:
            strata[key(r)].append(r)
        per = {k: max(1, round(need * len(v) / len(fneg)))
               for k, v in strata.items()}
        picked = []
        for k, v in strata.items():
            v = v[:]
            rng.shuffle(v)
            picked.extend(v[:per[k]])
        # 会话上限（避免 S1 会话独占）
        cap = max(1, int(0.6 * need))
        by_sid = defaultdict(list)
        for r in picked:
            by_sid[r["sid"]].append(r)
        final = []
        for sid, rs in by_sid.items():
            final.extend(rs[:cap])
        chosen.extend(final)
        print("  fold=%-7s pos=%d negpool=%d chosen=%d (need=%d)" % (
            fold, len(fpos), len(fneg), len(final), need))

    rows = pos + chosen
    with open(os.path.join(C.WORK, "d3_dataset.jsonl"), "w",
              encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("[D3] dataset=%d written" % len(rows))


if __name__ == "__main__":
    main()
