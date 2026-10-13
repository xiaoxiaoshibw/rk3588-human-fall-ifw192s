# -*- coding: utf-8 -*-
"""W4 补：把 ledger 真分（生产引擎 RF prob）接进同一测试划分。

d3_dataset.jsonl 的 rf_prob 来自 RD-01 的 JS 复刻（已被 W1B 证明与生产
不一致，接受率 100% vs 生产 58-80%）。本脚本用 (sid, frame, cand) 键把
ledger 的**真实 prob** 接回，在同一 train/test 奇偶划分上给出生产 RF 的
首个 out-of-sample 数字，与复刻线并列对比。

输出追加到 W4_MODEL_COMPARE.json 的 models + calibration_on_test：
  M0_TRUE_PROD_LEDGER
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "HFUS-RD-01", "tools"))
import common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
D3 = os.path.join(C.REPO, "sidequests", "HFUS-RD-01", "work",
                  "d3_dataset.jsonl")
EVID = os.path.join(C.REPO, "docs", "sidequests", "evidence",
                    "2026-10-12_HFUS_RD_02_r1")


def main():
    rows = [json.loads(l) for l in open(D3, encoding="utf-8")]
    need = defaultdict(set)
    for r in rows:
        need[r["sid"]].add((r["frame"], r["cand"]))
    led = {}
    for sid, keys in need.items():
        print("[w4b] scan ledger", C.SID_SHORT[sid], "keys", len(keys))
        for rec in C.iter_ledger(sid, fields=["frame_index", "candidates"]):
            fi = rec["frame_index"]
            for c in (rec.get("candidates") or []):
                k = (fi, c["id"])
                if k in keys:
                    led[(sid, fi, c["id"])] = (c["prob"], c["decision"])
        print("[w4b]   got %d / %d" % (
            sum(1 for k in led if k[0] == sid), len(keys)))
    prob = np.array([led.get((r["sid"], r["frame"], r["cand"]),
                             (np.nan, None))[0] for r in rows],
                    dtype=np.float64)
    missing = int(np.isnan(prob).sum())
    y = np.array([r["y"] for r in rows], dtype=np.int64)
    sid = np.array([r["sid"][-6:] for r in rows])
    fr = np.array([r["frame"] for r in rows])
    tr = ((sid == "175227") & (fr % 2 == 0)) | \
         ((sid == "175429") & (fr % 2 == 0))
    te = ((sid == "175227") & (fr % 2 == 1)) | \
         ((sid == "175429") & (fr % 2 == 1)) | (sid == "175553")
    ok = ~np.isnan(prob)
    print("[w4b] joined %d/%d rows (missing %d)" % (ok.sum(), len(rows),
                                                    missing))
    # 仅用有真分的行评估；训练阈值同样只用有真分行
    from sklearn.metrics import average_precision_score, \
        precision_recall_curve
    tr_ok = tr & ok
    te_ok = te & ok
    pr, rc, t = precision_recall_curve(y[tr_ok], prob[tr_ok])
    f1 = 2 * pr * rc / np.clip(pr + rc, 1e-9, None)
    i = int(np.nanargmax(f1))
    thr = float(t[i - 1]) if i > 0 and len(t) else 0.5
    yt, pt = y[te_ok], prob[te_ok]
    pred = (pt >= thr).astype(int)
    tp = int((pred & (yt == 1)).sum())
    fp = int((pred & (yt == 0)).sum())
    fn = int(((pred == 0) & (yt == 1)).sum())
    res = {
        "model": "M0_TRUE_PROD_LEDGER",
        "n": int(len(yt)), "pos": int(yt.sum()), "neg": int(len(yt) - yt.sum()),
        "auprc": round(float(average_precision_score(yt, pt)), 4),
        "thr": round(thr, 4),
        "precision": round(tp / max(tp + fp, 1), 4),
        "recall": round(tp / max(tp + fn, 1), 4),
        "f1": round(2 * tp / max(2 * tp + fp + fn, 1), 4),
        "fp_at_thr": fp,
        "brier": round(float(np.mean((pt - yt) ** 2)), 4),
        "mean_pred": round(float(pt.mean()), 4),
        "base_rate": round(float(yt.mean()), 4),
        "caveat": ("ledger 真分；负例= S1 奇数帧家具（本划分 OOS 帧）。"
                   "S3-far 正例行无 ledger 覆盖时计入 missing。"),
    }
    print("[w4b] M0_TRUE_PROD:", json.dumps(res, ensure_ascii=False))
    op = os.path.join(EVID, "W4_MODEL_COMPARE.json")
    with open(op, encoding="utf-8") as f:
        d = json.load(f)
    d["models"]["M0_TRUE_PROD_LEDGER"] = res
    d["models"]["M0_RF51_FROZEN"]["contaminated_note"] = (
        "该行 rf_prob 来自 RD-01 JS 复刻（W1B 已证与生产不一致：复刻对 "
        "S1/S3-near/S8 接受率 100% vs 生产 58.2/79.0/79.5%），只能作为"
        "复刻线对照，不是生产 RF 行为。")
    d["join_note"] = {"rows_with_true_prob": int(ok.sum()),
                      "missing": missing,
                      "missing_breakdown": {
                          s: int(((sid == s[-6:]) & ~ok).sum())
                          for s in ("175227", "175429", "175553")}}
    with open(op, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print("[w4b] updated", op)


if __name__ == "__main__":
    main()
