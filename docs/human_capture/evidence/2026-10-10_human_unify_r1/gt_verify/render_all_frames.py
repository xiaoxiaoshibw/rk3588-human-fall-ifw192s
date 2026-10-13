# -*- coding: utf-8 -*-
"""渲染两段全部帧的带框标注版 PNG.
用法: python render_all_frames.py
输出: frames/<sid>_f<NNNN>_box.png
"""
import json, os, sys, io
import render_with_gt_box as R

SESSIONS = ["cap_20261007_154007", "cap_20261007_143945"]
OUT_DIR = "frames"

os.makedirs(OUT_DIR, exist_ok=True)
n_total = 0
for sid in SESSIONS:
    meta = json.load(io.open("D:/Code/ldiar/captures/remote/%s/meta.json" % sid, encoding="utf-8"))
    n = len(meta["frames"])
    print("== %s (%d frames) ==" % (sid, n))
    for fi in range(n):
        out = os.path.join(OUT_DIR, "%s_f%04d_box.png" % (sid, fi))
        R.render_with_gt(sid, fi, out)
        n_total += 1
        if fi % 20 == 0 or fi == n - 1:
            print("  f%d -> %s" % (fi, out))
print("TOTAL %d frames rendered" % n_total)
