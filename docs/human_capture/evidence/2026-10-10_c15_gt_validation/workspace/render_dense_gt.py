# -*- coding: utf-8 -*-
"""render_dense_gt.py — C1.5 逐帧渲染 + 加密 sampling, 生成人工 GT 待确认帧集。

把 2 段动态会话 (143945/154007) 全部帧渲成 top/side PNG, 支撑逐帧人工判定;
渲染动作 GT 负责视觉比对。本脚本只产出 PNG + 待确认清单, 不写 GT。
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
spec.loader.exec_module(rpl)
R, T = rpl.R, rpl.T

DENSE_SESSIONS = ["cap_20261007_143945", "cap_20261007_154007"]


def render_all(sid, out_root):
    sdir = os.path.join(SESSION_ROOT, sid)
    meta = json.load(io.open(os.path.join(sdir, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(sdir, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, 28).view(np.float32).reshape(-1, 7)
    od = os.path.join(out_root, sid)
    os.makedirs(od, exist_ok=True)
    n = len(meta["frames"])
    for fi in range(n):
        f = meta["frames"][fi]
        seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
        xyz = seg[:, :3].astype(np.float64)
        v = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
        lv = (xyz[v] @ R.T) + T
        rpl.render_frame(lv, os.path.join(od, "f%04d.png" % fi))
    return n


def main():
    out_root = sys.argv[1]
    manifest = []
    for sid in DENSE_SESSIONS:
        n = render_all(sid, out_root)
        manifest.append({"session": sid, "n_frames": n, "dir": os.path.join(out_root, sid)})
        print("rendered %s ALL %d frames" % (sid, n))
    with io.open(os.path.join(out_root, "dense_index.json"), "w", encoding="utf-8") as fh:
        json.dump({"note": "C1.5 dense render for human GT", "sessions": manifest}, fh, ensure_ascii=False, indent=1)
    print("done")


if __name__ == "__main__":
    main()
