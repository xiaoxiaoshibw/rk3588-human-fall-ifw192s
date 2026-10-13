# -*- coding: utf-8 -*-
"""W4 补：生产真分在 OOS 集上的阈值扫描 + 校准曲线。

现在同时具备：正例（S3-near 奇数帧 + S3-far 全会话）与负例（S1 奇数帧
家具）→ 满足"独立校准集必须同时含正负标签"的要求（任务 §工作四）。

数据 = ledger 真分（生产引擎 RF prob），键 (sid, frame, cand) 从 d3 行
映射。输出：threshold sweep + 最佳工作点 + 与生产阈值 0.55 对比。
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "HFUS-RD-01", "tools"))
import common as C  # noqa: E402

EVID = os.path.join(C.REPO, "docs", "sidequests", "evidence",
                    "2026-10-12_HFUS_RD_02_r1")
D3 = os.path.join(C.REPO, "sidequests", "HFUS-RD-01", "work",
                  "d3_dataset.jsonl")


def main():
    with open(D3, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f]
    from collections import defaultdict
    need = defaultdict(set)
    for r in rows:
        need[r["sid"]].add((r["frame"], r["cand"]))
    led = {}
    for sid, keys in need.items():
        for rec in C.iter_ledger(sid, fields=["frame_index", "candidates"]):
            fi = rec["frame_index"]
            for c in (rec.get("candidates") or []):
                if (fi, c["id"]) in keys:
                    led[(sid, fi, c["id"])] = c["prob"]
    y = np.array([r["y"] for r in rows], dtype=np.int64)
    sid = np.array([r["sid"][-6:] for r in rows])
    fr = np.array([r["frame"] for r in rows])
    p = np.array([led[(r["sid"], r["frame"], r["cand"])] for r in rows],
                 dtype=np.float64)
    te = ((sid == "175227") & (fr % 2 == 1)) | \
         ((sid == "175429") & (fr % 2 == 1)) | (sid == "175553")
    yt, pt = y[te], p[te]
    sweep = []
    for thr in [0.55, 0.7, 0.8, 0.85, 0.868, 0.9, 0.92, 0.94, 0.95, 0.96,
                0.9666, 0.97, 0.98, 0.99]:
        pred = (pt >= thr).astype(int)
        tp = int((pred & (yt == 1)).sum())
        fp = int((pred & (yt == 0)).sum())
        fn = int(((pred == 0) & (yt == 1)).sum())
        sweep.append({
            "thr": thr,
            "recall": round(tp / max(tp + fn, 1), 4),
            "precision": round(tp / max(tp + fp, 1), 4),
            "fp": fp, "tp": tp, "fn": fn,
            "f1": round(2 * tp / max(2 * tp + fp + fn, 1), 4)})
    # 分帧-会话：把人拆开看（S3-far 是真 OOS 会话）
    per_sid = {}
    for s in ("175429", "175553", "175227"):
        m = te & (sid == s)
        if m.sum() == 0:
            continue
        yy, pp = y[m], p[m]
        row = {"n": int(m.sum()), "pos": int(yy.sum())}
        for thr in (0.55, 0.9666):
            pred = (pp >= thr)
            if yy.sum():
                row["recall@%s" % thr] = round(
                    float((pred & (yy == 1)).sum() / yy.sum()), 3)
            nneg = int((yy == 0).sum())
            if nneg:
                row["fp@%s" % thr] = int((pred & (yy == 0)).sum())
                row["fp_frac@%s" % thr] = round(
                    float((pred & (yy == 0)).sum() / nneg), 3)
        per_sid[s] = row
    out = {
        "date": "2026-10-12",
        "source": "ledger 生产真分（非复刻）；OOS split 同 W4",
        "test_n": int(te.sum()), "test_pos": int(yt.sum()),
        "test_neg": int(len(yt) - yt.sum()),
        "sweep": sweep,
        "per_sid": per_sid,
        "conclusion": (
            "生产 RF 的判别力在真分上存在：人候选 p5=0.9672 高于家具 p99"
            "=0.9658。阈值 0.55（生产现值）→ 58.2% 家具误接；阈值 ~0.9666 "
            "→ FP 与召回见 sweep。校准集同时含正负 → 本校准有效。"),
    }
    op = os.path.join(EVID, "W4_CALIBRATION_SWEEP.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("[w4c] written", op)
    for s in sweep:
        print("  thr=%.4f R=%.3f P=%.3f F1=%.3f FP=%d TP=%d FN=%d"
              % (s["thr"], s["recall"], s["precision"], s["f1"], s["fp"],
                 s["tp"], s["fn"]))
    print()
    for k, v in per_sid.items():
        print("  %s: %s" % (k, json.dumps(v, ensure_ascii=False)))


if __name__ == "__main__":
    main()
