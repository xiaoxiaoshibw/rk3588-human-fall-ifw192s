#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""extract_cluster_features.py — 从 b2a_shadow_probe 的 clusters.jsonl 逐簇提 51 维特征.

修复 frame_feature.extract_features 的 bool 求和缺陷, 供 C1 RF v2 训练/A-B 使用.
输入: <raw_dir> (含 <sid>.clusters.jsonl) <sessions_root> <out_dir>
输出: <out_dir>/<sid>.cluster_feats.jsonl
"""
import json, os, sys

import numpy as np

EVID = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO = os.path.abspath(os.path.join(EVID, "..", "..", "..", ".."))
ML_DIR = os.path.join(REPO, "pc_apps", "human_ml")
sys.path.insert(0, ML_DIR)
from frame_feature import extract_features  # noqa: E402

R = np.array([0.893544, 0.0, 0.448975,
              -0.014337, 0.99949, 0.028533,
              -0.448746, -0.031932, 0.893089]).reshape(3, 3)
T = np.array([0.0, 0.0, 1.380286])
Z_LO, Z_HI = 0.1, 2.3
BG_BOOST = 0.25
MIN_PTS = 30
TOP_K = 4


def load_bg(session_root):
    return json.load(open(os.path.join(session_root, "bg_envelope.json"), encoding="utf-8"))


def cell_key(x, y):
    import math
    return int(math.floor(x / 0.05) * 4096 + math.floor(y / 0.05))


def frame_points(mem, meta, fi):
    f = meta["frames"][fi]
    return mem[f["offset_points"]: f["offset_points"] + f["count_points"]]


def extract_cluster_features(session_root, raw_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    bg = load_bg(os.path.join(REPO, "pc_apps", "human_replay"))
    sids = [f.replace(".clusters.jsonl", "") for f in os.listdir(raw_dir) if f.endswith(".clusters.jsonl")]
    for sid in sids:
        sd = os.path.join(session_root, sid)
        meta = json.load(open(os.path.join(sd, "meta.json"), encoding="utf-8"))
        raw = np.memmap(os.path.join(sd, "points.bin"), dtype=np.uint8, mode="r"
                        ).reshape(-1, 28).view(np.float32).reshape(-1, 7)
        lines = open(os.path.join(raw_dir, sid + ".clusters.jsonl"), encoding="utf-8").read().splitlines()
        by_frame = {}
        for ln in lines:
            o = json.loads(ln)
            by_frame.setdefault(o["frame"], []).append(o)
        outp = open(os.path.join(out_dir, sid + ".cluster_feats.jsonl"), "w", encoding="utf-8")
        for fi in sorted(by_frame):
            pts = frame_points(raw, meta, fi)
            xyz = pts[:, :3].astype(np.float64)
            valid = np.isfinite(xyz).all(axis=1)
            xyz = xyz[valid]
            inten = pts[valid, 3]
            lev = xyz @ R.T + T
            z = lev[:, 2]
            mask = (z > Z_LO) & (z < Z_HI)
            lev_m, inten_m = lev[mask], inten[mask]
            z_m = z[mask]
            keys = np.floor(lev_m[:, 0] / 0.05).astype(np.int64) * 4096 \
                + np.floor(lev_m[:, 1] / 0.05).astype(np.int64)
            bgv = np.array([bg.get(str(int(k)), -10.0) for k in keys])
            hot_mask = (bgv > -9) & (z_m > bgv + BG_BOOST)
            hot_idx = np.flatnonzero(hot_mask)
            clusters = []
            if len(hot_idx) >= MIN_PTS:
                grid = {}
                for p in hot_idx:
                    grid.setdefault(int(keys[p]), []).append(p)
                seen = set()
                for k in list(grid):
                    if k in seen:
                        continue
                    stack = [k]; seen.add(k); members = []
                    while stack:
                        cur = stack.pop()
                        members.extend(grid[cur])
                        cx_, cy_ = divmod(cur, 4096)
                        for dx in (-1, 0, 1):
                            for dy in (-1, 0, 1):
                                nk = (cx_ + dx) * 4096 + (cy_ + dy)
                                if nk in grid and nk not in seen:
                                    seen.add(nk); stack.append(nk)
                    if len(members) >= MIN_PTS:
                        clusters.append(members)
                clusters.sort(key=len, reverse=True)
                clusters = clusters[:TOP_K]
            recs = by_frame[fi]
            for rank, rec in enumerate(sorted(recs, key=lambda r: r["rank"])):
                if rec["rank"] < 0:
                    continue
                members = clusters[rec["rank"]]
                pts_c = lev_m[np.array(members)]
                inten_c = inten_m[np.array(members)]
                xyzi = np.column_stack([pts_c, inten_c]).astype(np.float32)
                fv = extract_features(xyzi)
                outp.write(json.dumps({
                    "frame": fi, "rank": rec["rank"], "n": rec["n"],
                    "cx": rec["cx"], "cy": rec["cy"], "zmax": rec["zmax"],
                    "person_prob_probe": rec["person_prob"],
                    "feat": [float(x) for x in fv],
                }) + "\n")
        outp.close()
        print("[extract] %s frames=%d clusters=%d" % (sid, len(by_frame), sum(len(v) for v in by_frame.values())))


if __name__ == "__main__":
    raw_dir = sys.argv[1]
    session_root = sys.argv[2]
    out_dir = sys.argv[3]
    extract_cluster_features(session_root, raw_dir, out_dir)
