# -*- coding: utf-8 -*-
"""量化 ledger(生产 RF) prob vs stage2(RD-01 JS 复刻) rf_prob 的一致性。

发现（probe_prob_divergence.py）：同一 S1 大候选，ledger=0.0029，
复刻=0.89。若普遍存在，则 RD-01 D3 分类器实验（M0-M4）在不一致特征上，
结论失去与生产行为的关联。

对齐键：(sid, frame, cand_id)。输出 evidence/W1B_PROB_CONSISTENCY.json。
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "HFUS-RD-01", "tools"))
import common as C  # noqa: E402

EVID = os.path.join(C.REPO, "docs", "sidequests", "evidence",
                    "2026-10-12_HFUS_RD_02_r1")
S2 = os.path.join(C.REPO, "sidequests", "HFUS-RD-01", "work",
                  "candidates_stage2.jsonl")
SIDS_CHECK = ["cap_20261010_175227", "cap_20261010_175429",
              "cap_20261010_180557"]


def main():
    # stage2 分数
    s2 = defaultdict(dict)
    with open(S2, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            s2[r["sid"]][(r["frame"], r["cand"])] = (r["rf_prob"], r["n"])
    out = {}
    for sid in SIDS_CHECK:
        # ledger 分数（只取需要的字段省内存）
        pairs = []
        for rec in C.iter_ledger(sid, fields=["frame_index", "candidates"]):
            fi = rec["frame_index"]
            for c in (rec.get("candidates") or []):
                key = (fi, c["id"])
                if key in s2[sid]:
                    pairs.append((c["prob"], s2[sid][key][0], c["n"]))
        if not pairs:
            out[sid] = {"status": "no overlap"}
            continue
        led = np.array([p[0] for p in pairs])
        rep = np.array([p[1] for p in pairs])
        n = np.array([p[2] for p in pairs])
        diff = np.abs(led - rep)
        acc = np.mean((led >= 0.55) == (rep >= 0.55))
        out[sid] = {
            "n": len(pairs),
            "mean_abs_diff": round(float(diff.mean()), 4),
            "median_abs_diff": round(float(np.median(diff)), 4),
            "frac_diff_lt_0.05": round(float((diff < 0.05).mean()), 4),
            "frac_diff_gt_0.3": round(float((diff > 0.3).mean()), 4),
            "accept_agreement_at_0.55": round(float(acc), 4),
            "ledger_accept_frac": round(float((led >= 0.55).mean()), 4),
            "replica_accept_frac": round(float((rep >= 0.55).mean()), 4),
            "by_bucket": {},
        }
        for bname, lo, hi in [("lt100", 0, 99), ("mid_100_999", 100, 999),
                              ("ge1000", 1000, 1999),
                              ("ge2000", 2000, 10 ** 9)]:
            m = (n >= lo) & (n <= hi)
            if m.sum() == 0:
                continue
            out[sid]["by_bucket"][bname] = {
                "n": int(m.sum()),
                "ledger_accept_frac": round(float((led[m] >= 0.55).mean()), 3),
                "replica_accept_frac": round(float((rep[m] >= 0.55).mean()), 3),
                "mean_abs_diff": round(float(diff[m].mean()), 3),
            }
        print("[w1b] %s n=%d agree=%.3f led_acc=%.3f rep_acc=%.3f"
              % (C.SID_SHORT[sid], len(pairs), acc,
                 (led >= 0.55).mean(), (rep >= 0.55).mean()))
    report = {
        "date": "2026-10-12",
        "probe": ("single S1 candidate a_6_0 (n=5018): ledger prob=0.00292 "
                  "vs rf_extract_node.js replica=0.89 (leveled) / 0.88 (raw)"),
        "conclusion_draft": ("若普遍：RD-01 D3 的 f51/rf_prob 全部来自复刻, "
                             "与生产 ledger 打分不一致 → M0-M4 的机会均被"
                             "复刻缺陷污染, 不能代表生产行为。"),
        "per_sid": out,
    }
    op = os.path.join(EVID, "W1B_PROB_CONSISTENCY.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("[w1b] written", op)


if __name__ == "__main__":
    main()
