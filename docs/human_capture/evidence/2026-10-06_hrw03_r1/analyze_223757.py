# -*- coding: utf-8 -*-
"""223757 静态残留簇分析：低矮簇的位置/占用率/标签 + 全簇距离分布"""
import collections
import json
import math

d = json.load(open(r"docs/human_capture/evidence/2026-10-06_hrw03_r1/cap_20261002_223757_diag.json", encoding="utf-8"))
cl = d["clusters"]
NF = d["frames"]

low = [c for c in cl if c["zmin"] < 0.2]
cells = collections.Counter((round(c["cx"]), round(c["cy"])) for c in low)
print("zmin<0.2 簇的 (1m 格) 频次 top10:", cells.most_common(10))

for (cx, cy), _ in cells.most_common(4):
    sub = [c for c in low if round(c["cx"]) == cx and round(c["cy"]) == cy]
    occs = sorted(c["occ_med"] for c in sub)
    hs = sorted(c["h"] for c in sub)
    tags = collections.Counter(c["tag"] for c in sub).most_common(2)
    q = lambda a, p: a[min(len(a) - 1, max(0, round(p * (len(a) - 1))))]
    print("(%d,%d) n_obs=%d occ_med p10/p50/p90=%d/%d/%d h=(%.2f..%.2f) tags=%s"
          % (cx, cy, len(sub), q(occs, .1), q(occs, .5), q(occs, .9),
             hs[0], hs[-1], tags))

r = sorted(math.hypot(c["cx"], c["cy"]) for c in cl)
q = lambda a, p: a[min(len(a) - 1, max(0, round(p * (len(a) - 1))))]
print("簇距离 m: p10/p50/p90=%0.1f/%0.1f/%0.1f max=%0.1f"
      % (q(r, .1), q(r, .5), q(r, .9), r[-1]))
