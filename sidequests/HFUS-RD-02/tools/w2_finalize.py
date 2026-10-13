# -*- coding: utf-8 -*-
"""W2 收口：把 append-only 标签 + 冻结队列 → reviewed 负例集 + 状态 JSON。

- labels 末条胜（同 qid 重复标注保留历史，取最后一次）
- 负例性标签 {FURNITURE, WALL_OR_FLOOR, OTHER_OBJECT} → reviewed_negatives.jsonl
- PERSON 标签单独登记（本轮队列未含正例池，正常为 0）
- 只读队列和标签，不改、不覆盖历史

用法：python -B tools/w2_finalize.py
输出：work/reviewed_negatives.jsonl / evidence/W2_REVIEW_STATUS.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WORK = os.path.join(ROOT, "sidequests", "HFUS-RD-02", "work")
EVID = os.path.join(ROOT, "docs", "sidequests", "evidence",
                    "2026-10-12_HFUS_RD_02_r1")
QUEUE = os.path.join(WORK, "review_queue.json")
LABELS = os.path.join(WORK, "review_labels.jsonl")

NEG_LABELS = {"FURNITURE", "WALL_OR_FLOOR", "OTHER_OBJECT"}
ALL_LABELS = NEG_LABELS | {"PERSON", "UNKNOWN"}


def main():
    if not os.path.exists(QUEUE):
        print("queue missing:", QUEUE)
        return 1
    with open(QUEUE, encoding="utf-8") as f:
        q = json.load(f)
    by_qid = {c["qid"]: c for c in q["items"]}

    last = {}
    order = []
    if os.path.exists(LABELS):
        with open(LABELS, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r["qid"] not in last:
                    order.append(r["qid"])
                last[r["qid"]] = r   # 末条胜

    counts = {k: 0 for k in ALL_LABELS}
    counts["unlabeled"] = 0
    neg_rows = []
    person_rows = []
    for qid in order:
        r = last[qid]
        c = by_qid.get(qid)
        if c is None:
            print("[w2f] WARN qid not in queue:", qid)
            continue
        counts[r["label"]] = counts.get(r["label"], 0) + 1
        row = {"qid": qid, "label": r["label"], "note": r.get("note", ""),
               "reviewer": r.get("reviewer"), "ts": r.get("ts"),
               "sid": c["sid"], "frame": c["frame"], "cand_id": c["cand_id"],
               "pointset_sha256": c["pointset_sha256"], "n": c["n"],
               "prob": c["prob"], "bucket": c["bucket"],
               "size_z": c.get("size_z")}
        if r["label"] in NEG_LABELS:
            neg_rows.append(row)
        elif r["label"] == "PERSON":
            person_rows.append(row)
    n_items = len(q["items"])
    counts["unlabeled"] = n_items - sum(
        counts.get(k, 0) for k in ALL_LABELS)

    with open(os.path.join(WORK, "reviewed_negatives.jsonl"), "w",
              encoding="utf-8") as f:
        for row in neg_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(os.path.join(EVID, "W2_REVIEW_STATUS.json"), "w",
              encoding="utf-8") as f:
        json.dump({
            "date": "2026-10-12",
            "queue_n": n_items,
            "labeled_n": sum(counts.get(k, 0) for k in ALL_LABELS),
            "counts": counts,
            "reviewed_negatives_n": len(neg_rows),
            "reviewed_person_n": len(person_rows),
            "blocked_note": (
                "reviewed 负例不足 → 分类器正式收益结论阻断（见 "
                "HARD_NEGATIVE_STUDY.md §7）。未审核条目保持 UNKNOWN。"),
            "sha_binding": "每条 pointset_sha256 取自 ledger 原值",
        }, f, ensure_ascii=False, indent=2)
    print("[w2f] queue=%d labeled=%d neg=%d person=%d unlabeled=%d"
          % (n_items, sum(counts.get(k, 0) for k in ALL_LABELS),
             len(neg_rows), len(person_rows), counts["unlabeled"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
