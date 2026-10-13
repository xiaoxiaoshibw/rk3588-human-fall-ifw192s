# -*- coding: utf-8 -*-
"""汇总 work/evidence JSON → 唯一 METRICS.json（任务交付 6）。"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C


def j(path):
    return json.load(open(path, encoding="utf-8"))


def main():
    evd = C.EVIDENCE
    out = {
        "task": "HFUS-RD-01", "date": "2026-10-12",
        "repo_head": "026e06303f60ed1bbe4ddc4d037836db68da6d27",
        "sids_order": C.SIDS,
        "sid_short": C.SID_SHORT,
        "layer_attribution": j(os.path.join(evd, "D1_LAYER_SUMMARY.json")),
        "fusion_ablation": j(os.path.join(evd, "D1_FUSION_ABLATION.json")),
        "track_events": j(os.path.join(evd, "D1_TRACK_EVENTS.json")),
        "d4_feasibility": j(os.path.join(evd, "D4_RANDLANET_FEAS.json"))}
    # D2 per-session
    d2 = {}
    for p in glob.glob(os.path.join(C.WORK, "d2_per_session_*.json")):
        r = j(p)["results"]
        d2.update(r)
    out["cluster_ablation"] = {"variants": j(p)["variants"],
                               "results": d2}
    # D3
    d3 = {}
    for f in ("rf", "xgb", "m3_pointnet", "m4_pointnetpp"):
        p = os.path.join(C.WORK, "d3_%s.json" % f)
        if os.path.exists(p):
            d3[f] = j(p)
    d3["dataset_notes"] = {
        "pos": 350, "neg_pool": 644, "unk": 1594,
        "train_rows": 645, "val_rows": 91,
        "val_all_positive": True,
        "limitation": "val fold 缺负例（S1 全压 train），AUPRC 不上 val/test"}
    out["classifier_ablation"] = d3
    dst = os.path.join(evd, "METRICS.json")
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("[METRICS] written %s" % dst)


if __name__ == "__main__":
    main()
