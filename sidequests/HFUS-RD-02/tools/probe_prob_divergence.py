# -*- coding: utf-8 -*-
"""定位 ledger.prob 与 stage2.rf_prob 的分歧根因（S1 大候选）。"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "HFUS-RD-01", "tools"))
import common as C  # noqa: E402

NODE = os.path.join(C.REPO, "sidequests", "HFUS-RD-01", "tools",
                    "rf_extract_node.js")
sid = "cap_20261010_175227"

rec = None
for r in C.iter_ledger(sid, fields=["frame_index", "candidates"]):
    cs = [c for c in (r.get("candidates") or []) if c["n"] >= 2000]
    if cs:
        rec = (r["frame_index"], cs[0])
        break
fi, cand = rec
print("frame", fi, "cand", cand["id"], "n", cand["n"],
      "ledger_prob", cand["prob"])

xyz, inten, mm = C.read_frame_xyz(sid, fi)
lev = C.level(xyz)
idx = np.asarray(cand["raw_indices"], dtype=np.int64)
print("idx max", idx.max(), "frame pts", len(xyz), "valid", idx.max() < len(xyz))
b = np.empty((len(idx), 4), dtype=np.float32)
b[:, :3] = lev[idx]
b[:, 3] = inten[idx]

with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as tf:
    np.save(tf, b)
    tp = tf.name
spec = json.dumps({"file": tp.replace("\\", "/"), "counts": [len(b)]})
p = subprocess.run(["node", NODE, spec], capture_output=True, text=True,
                   timeout=180)
print("node rc", p.returncode)
if p.returncode == 0:
    res = json.loads(p.stdout)
    print("rf_extract_node.js prob on LEVELED:", res["probs"][0])
# 再用原始（未 level）坐标算
b2 = np.empty((len(idx), 4), dtype=np.float32)
b2[:, :3] = xyz[idx]
b2[:, 3] = inten[idx]
with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as tf:
    np.save(tf, b2)
    tp2 = tf.name
spec2 = json.dumps({"file": tp2.replace("\\", "/"), "counts": [len(b2)]})
p2 = subprocess.run(["node", NODE, spec2], capture_output=True, text=True,
                    timeout=180)
if p2.returncode == 0:
    print("rf_extract_node.js prob on RAW:",
          json.loads(p2.stdout)["probs"][0])
os.unlink(tp)
os.unlink(tp2)
print("ledger_prob was:", cand["prob"])
