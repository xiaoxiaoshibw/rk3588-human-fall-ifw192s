# -*- coding: utf-8 -*-
"""汇总 work/d2_per_session_*.json → evidence/D2_CLUSTER_ABLATION.json。"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

res = {}
for p in glob.glob(os.path.join(C.WORK, "d2_per_session_*.json")):
    j = json.load(open(p, encoding="utf-8"))
    res.update(j["results"])
    variants = j["variants"]
out = {"variants": variants, "results": res}
dst = os.path.join(C.EVIDENCE, "D2_CLUSTER_ABLATION.json")
with open(dst, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("[D2-FINISH] sessions=%d written %s" % (len(res), dst))
