# -*- coding: utf-8 -*-
"""0.85+半径滤波+z门 组合下 223757 残留簇的形态分析"""
import collections
import json

rows = json.load(open(r"docs/human_capture/evidence/2026-10-06_hrw03_r1/cap_20261002_223757_fix_0.85_0.1_z.json", encoding="utf-8"))
cells = collections.defaultdict(list)
for r in rows:
    cells[(round(r["cx"]), round(r["cy"]))].append(r)

print("total drawn:", len(rows), " frames:", len({r["f"] for r in rows}))
for cell, sub in sorted(cells.items(), key=lambda kv: -len(kv[1]))[:8]:
    hs = sorted(r["h"] for r in sub)
    ns = sorted(r["n"] for r in sub)
    fs = sorted(r["f"] for r in sub)
    tags = collections.Counter(r["tag"] for r in sub).most_common(3)
    span = "%d..%d" % (fs[0], fs[-1])
    print("%s obs=%3d frames=%s h=%.2f..%.2f n=%d..%d tags=%s"
          % (cell, len(sub), span, hs[0], hs[-1], ns[0], ns[-1], tags))

# 每帧最大簇的轨迹（判断有没有移动的人）
by_frame = collections.defaultdict(list)
for r in rows:
    by_frame[r["f"]].append(r)
seq = []
for f in sorted(by_frame):
    big = max(by_frame[f], key=lambda r: r["n"])
    seq.append((f, round(big["cx"], 1), round(big["cy"], 1), big["n"], big["h"], big["tag"]))
print("\n每帧最大簇（每 10 帧采样）:")
for s in seq[::10]:
    print(s)
