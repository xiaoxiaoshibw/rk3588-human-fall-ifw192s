# -*- coding: utf-8 -*-
"""crosscheck_diff_frames.py — 从 eval_frames.jsonl 抽出 A/B/C 在人锚命中上的逐帧差异帧.
产出: eval_diff.json  (n_diff, frames[]). 与 FAIL_ATTRIBUTION §1 对照.
"""
import codecs
import json
import os
import sys

EV = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "..", "..",
                                   "docs", "human_capture", "evidence",
                                   "2026-10-10_spike_cluster_r1"))


def hits(cl):
    return any(c.get("d_anchor") is not None and c["d_anchor"] <= 0.55 for c in cl)


def main():
    frames = []
    recs = 0
    with codecs.open(os.path.join(EV, "eval_frames.jsonl"), "r", "utf-8") as f:
        for line in f:
            r = json.loads(line)
            recs += 1
            if r["n_hot"] == 0:
                continue
            hits_v = {v: hits(r[v].get("clusters", [])) for v in ("A", "B", "C")}
            if len(set(hits_v.values())) > 1:
                frames.append(dict(session=r["session"], frame=r["frame"],
                                   gt_type=r["gt_type"], n_hot=r["n_hot"],
                                   hits=hits_v))
    out = dict(purpose="A/B/C 人锚命中 (d_anchor<=0.55) 逐帧差异扫描",
               n_records_scanned=recs, n_frames_with_diff=len(frames),
               diffs=frames[:50])
    with codecs.open(os.path.join(EV, "eval_diff.json"), "w", "utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("n_diff_frames:", len(frames), "of", recs, "records")
    for d in frames[:20]:
        print("  ", d)


if __name__ == "__main__":
    main()
