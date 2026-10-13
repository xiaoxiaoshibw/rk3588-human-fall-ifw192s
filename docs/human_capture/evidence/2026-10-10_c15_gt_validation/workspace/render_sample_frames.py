# -*- coding: utf-8 -*-
"""render_sample_frames.py — C1.5 人工判读渲染 (只读, 不写会话目录)。

复用 pc_apps/human_ml/render_person_label.py 的渲染逻辑 (顶层 import 不触发 main),
把 motion 候选 + 对照 session 的若干帧渲染到本会话 evidence 的 renders/ 目录,
供 C1.5 GT 裁定 (真人动态 vs 家具/合并-分裂) 人工看图。
"""
import importlib.util
import io
import json
import os
import sys

import numpy as np

HR_ML = "D:/Code/ldiar/pc_apps/human_ml/render_person_label.py"
SESSION_ROOT = "D:/Code/ldiar/captures/remote"

spec = importlib.util.spec_from_file_location("rpl", HR_ML)
rpl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpl)  # 顶层仅定义函数/常量, __main__ 不执行

R = rpl.R
T = rpl.T


def load_frames(session_dir):
    meta = json.load(io.open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(session_dir, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, 28).view(np.float32).reshape(-1, 7)
    return meta, raw


def render(session_dir, frame_idx, out_path):
    meta, raw = load_frames(session_dir)
    f = meta["frames"][frame_idx]
    seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
    xyz = seg[:, :3].astype(np.float64)
    v = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
    lv = (xyz[v] @ R.T) + T
    rpl.render_frame(lv, out_path)
    return meta["frames"][frame_idx]


def main():
    out_root = sys.argv[1]
    # (session, [frames]) — motion 候选全程 sampling + 已确认近场 stand 对照
    picks = [
        ("cap_20261007_143945", [0, 18, 36, 54, 72, 90, 99]),
        ("cap_20261007_154007", [0, 24, 42, 48, 54, 60, 78]),
        ("cap_20261008_114340", [0, 69, 92, 161, 230, 253, 276]),
        ("cap_20261008_114254", [0, 88, 176]),
        ("cap_20261009_121622", [50]),      # 近场 stand 对照 (confirmed person)
        ("cap_20261009_113611", [50]),      # 空场对照 (present=0)
    ]
    idx = []
    for sid, frames in picks:
        sdir = os.path.join(SESSION_ROOT, sid)
        if not os.path.exists(os.path.join(sdir, "meta.json")):
            print("skip (no meta)", sid); continue
        od = os.path.join(out_root, sid)
        os.makedirs(od, exist_ok=True)
        meta = json.load(io.open(os.path.join(sdir, "meta.json"), encoding="utf-8"))
        nf = len(meta["frames"])
        for fi in frames:
            if fi >= nf:
                continue
            outp = os.path.join(od, "f%04d.png" % fi)
            try:
                render(sdir, fi, outp)
                idx.append({"session": sid, "frame": fi, "png": outp})
                print("rendered %s f%04d" % (sid, fi))
            except Exception as e:
                print("ERR %s f%04d: %s" % (sid, fi, e))
    with io.open(os.path.join(out_root, "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"note": "C1.5 人工判读 rendering sampling", "items": idx}, fh, ensure_ascii=False, indent=1)
    print("wrote index.json n=%d" % len(idx))


if __name__ == "__main__":
    main()
