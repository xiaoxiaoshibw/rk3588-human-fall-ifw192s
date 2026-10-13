# -*- coding: utf-8 -*-
"""rerun_crosscheck.py — Python A vs JS A 逐帧对拍.

跑法:
  python -B rerun_crosscheck.py <session_dir> <bg_envelope.json> <frame_no>

输出:
  逐帧两者簇数、top1 成员 IoU、平均 |Δcx|/|Δcy| (cm), 及是否等价.
"""
import json
import math
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 复用 human_replay 同一 loader: leveled R/T 与 JS detect_overlay.js:17-21 一致
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _harness_lib import (find_clusters_A, find_hot_js, grid_key,  # noqa: E402
                          load_bg_envelope, cluster_summary)

# 与 detect_overlay.js R/T 一致 (hard code). 读取宁可只用同一个 source-of-truth:
R = np.array([[0.893544, 0.0, 0.448975],
              [-0.014337, 0.99949, 0.028533],
              [-0.448746, -0.031932, 0.893089]], dtype=np.float32)
T = np.array([0.0, 0.0, 1.380286], dtype=np.float32)


def load_frame(session_dir, fn):
    """忠实复现 JS detect_overlay.js level_frame: 不滤 NaN/0, 索引与原始 offset_points 严格对齐.
    NaN 或 ±Inf 的点 R*T 后仍 NaN/Inf, find_hot 的 z filter 会拒其入 hot, 与 JS 行为一致."""
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(session_dir, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, 28).view(np.float32).reshape(-1, 7)
    f = meta["frames"][fn]
    seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
    xyz = seg[:, :3].astype(np.float32)
    # 不滤 —— JS level_frame 对每点直接 R*x+T, 保留索引原样
    lv = (xyz @ R.T + T).astype(np.float32)
    return lv


def iou_sets(a, b):
    A = set(a); B = set(b)
    if not A or not B:
        return 0.0
    return len(A & B) / float(len(A | B))


def main():
    session_dir, bg_path, fn = sys.argv[1], sys.argv[2], int(sys.argv[3])
    bg = load_bg_envelope(bg_path)
    xyz = load_frame(session_dir, fn)
    n = xyz.shape[0]
    xs = xyz[:, 0].tolist()
    ys = xyz[:, 1].tolist()
    zs = xyz[:, 2].tolist()

    # --- Python A ---
    import time
    t0 = time.perf_counter()
    hot_py = find_hot_js(xs, ys, zs, bg, 0.1, 2.3)
    comps_py, st_py = find_clusters_A(xs, ys, hot_py)
    py_ms = (time.perf_counter() - t0) * 1000.0
    # 对 comps 排序不稳定 (find_clusters_A 的 comps.sort(key=len, reverse=True) 同 len 时
    # 顺字典遍历序), 改用 canonical sort: 按 (n desc, sorted(members)[0] asc) 唯一化.
    comps_py = sorted(comps_py, key=lambda m: (-len(m), sorted(m)[0] if m else -1))

    # --- JS A (smoke_crosscheck.js) ---
    jout = subprocess.run(
        ["node", os.path.join(os.path.dirname(os.path.abspath(__file__)), "smoke_crosscheck.js"),
         session_dir, bg_path, str(fn)],
        capture_output=True, text=True, check=True)
    js = json.loads(jout.stdout)

    # --- 比对 (配对: 双向最大 IoU 贪心匹配, 避免遍历序敏感) ---
    print("frame=%d n_pts=%d n_hot py=%d js=%d" % (fn, n, len(hot_py), js["n_hot"]))
    print("comps_py n=%d, comps_js n=%d" % (len(comps_py), len(js["comps_js"])))
    print("ms_py=%.2f ms_js=%d" % (py_ms, js["ms_js"]))
    pys = [set(c) for c in comps_py]
    jss = [set(c) for c in js["comps_members"]]
    pairs = []
    used_j = set()
    for i, A in enumerate(pys):
        best_j, best_iou = -1, 0.0
        for j, B in enumerate(jss):
            if j in used_j:
                continue
            if not A or not B:
                continue
            iou = len(A & B) / float(len(A | B))
            if iou > best_iou:
                best_iou, best_j = iou, j
        pairs.append((i, best_j, best_iou))
        if best_j >= 0:
            used_j.add(best_j)
    for i, j, iou in pairs:
        if j < 0:
            print("  py[%d] no-js-match" % i)
            continue
        cs = cluster_summary(comps_py[i], xs, ys, zs)
        js_m = js["comps_js"][j]
        dcx = abs(cs["cx"] - js_m["cx"]) * 100.0
        dcy = abs(cs["cy"] - js_m["cy"]) * 100.0
        dr90 = abs(cs["r90"] - js_m["r90"]) * 100.0
        print("  py[%d] <-> js[%d]: n=%d/%d IoU=%.3f dcx_cm=%.2f dcy_cm=%.2f dr90_cm=%.2f"
              % (i, j, cs["n"], js_m["n"], iou, dcx, dcy, dr90))
    all_match = (len(pys) == len(jss)
                 and all(j >= 0 and iou > 0.999 for _, j, iou in pairs)
                 and len(pys) == len(pairs)
                 and len(used_j) == len(jss)
                 and len(hot_py) == js["n_hot"])
    print("MATCH:", "PASS" if all_match else "FAIL")
    sys.exit(0 if all_match else 2)


if __name__ == "__main__":
    main()
