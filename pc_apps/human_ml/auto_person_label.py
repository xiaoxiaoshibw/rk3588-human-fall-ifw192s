# -*- coding: utf-8 -*-
"""auto_person_label.py — 自动 AI 判读占位器： 生成每帧 ai_labels.json。

思路:
  1. 用空场模板建 5cm 网格背景 z95 包络 (person_probe.empty_envelope 逻辑)
  2. 每帧 leveled → 找「高于同位背景 + 0.25m 且 z∈[0.6..2.3]」的热点
  3. 在热点 xy 上做 2D 网格连通分量, 取最大 => 人簇 (中位 xy + p90 半径)
  4. 一致化: 该会话所有帧的簇心滚动中位; 若某帧最大簇心漂移 > 0.5m 或簇点 < 30 → posture="none"
  5. 写 captures/remote/<sid>/ai_labels.json

posture 一律 "stand" (本次采集全部是站立/举手静止); 这就是标签, 不是姿态分类。
"""
import json
import os
import sys

import numpy as np

from person_probe import EMPTY_SID, load_frames, level_frame

R_GRID = 0.05


def background_envelope(root, z_band=(-1.0, 2.6), empty_sid=None):
    meta, raw = load_frames(root, empty_sid or EMPTY_SID)
    cells = {}
    for fi in range(0, len(meta["frames"]), 4):
        lv = level_frame(raw[meta["frames"][fi]["offset_points"]:
                             meta["frames"][fi]["offset_points"] + meta["frames"][fi]["count_points"]])
        lv = lv[(lv[:, 2] > z_band[0]) & (lv[:, 2] < z_band[1])]
        if not len(lv):
            continue
        gx = np.floor(lv[:, 0] / R_GRID).astype(np.int32)
        gy = np.floor(lv[:, 1] / R_GRID).astype(np.int32)
        key = gx * 4096 + gy
        z = lv[:, 2]
        o = np.argsort(key, kind="stable")
        k, z = key[o], z[o]
        b = np.flatnonzero(np.r_[True, k[1:] != k[:-1], True])
        for a, bb in zip(b[:-1], b[1:]):
            if bb - a < 2:
                continue
            p = float(np.percentile(z[a:bb], 95))
            kk = int(k[a])
            if kk not in cells or p > cells[kk]:
                cells[kk] = p
    return cells


def components(hx, hy):
    """粗 2D 连通分量: 量化到 5cm 网格做洪水填充, 返回 [(members_mask, size)...]。"""
    gx = np.floor(hx / R_GRID).astype(np.int32)
    gy = np.floor(hy / R_GRID).astype(np.int32)
    key = gx * 4096 + gy
    grid = {}
    for i, k in enumerate(key):
        grid.setdefault(int(k), []).append(i)
    seen = set()
    comps = []
    for k, members in grid.items():
        if k in seen:
            continue
        stack, acc = [k], []
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            acc.extend(grid[cur])
            cx, cy = cur // 4096, cur % 4096
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nk = (cx + dx) * 4096 + (cy + dy)
                    if nk in grid and nk not in seen:
                        stack.append(nk)
        comps.append(acc)
    comps.sort(key=len, reverse=True)
    return comps


# 姿态热区 z 带 (leveled, 地面=0): 背景差分热点必须落在这里面才算身体点
POSTURE_BANDS = {
    "stand": (0.6, 2.3, 0.5),    # z_lo, z_hi, 时序跳变门限 m
    "walk": (0.6, 2.3, 0.9),     # 同站立, 但人每帧移动 ~0.1m, 放宽跳变
    "sit": (0.15, 1.2, 0.5),     # 坐姿头顶 ~1.2m 以下
    "squat": (0.15, 0.9, 0.5),   # 蹲姿更低
    "lying": (0.15, 0.8, 0.5),   # 躺姿几乎贴地
    "fall": (0.15, 2.3, 0.9),    # 跌倒过程跨全带, 别卡窄
}


def label_session(root, sid, cells, out_root, posture="stand", empty_sid=None):
    z_lo, z_hi, jump_gate = POSTURE_BANDS[posture]
    meta, raw = load_frames(root, sid)
    recs = {}
    track_xy = None           # 滚动簇心
    roi_r = 0.8               # 初始
    alpha = 0.15              # 跟踪低通
    for fi, f in enumerate(meta["frames"]):
        lv = level_frame(raw[f["offset_points"]: f["offset_points"] + f["count_points"]])
        gx = np.floor(lv[:, 0] / R_GRID).astype(np.int32)
        gy = np.floor(lv[:, 1] / R_GRID).astype(np.int32)
        key = gx * 4096 + gy
        bg = np.array([cells.get(int(k), -10.0) for k in key], dtype=np.float64)
        ex = lv[:, 2] - (bg + 0.25)
        hot = (ex > 0) & (lv[:, 2] > z_lo) & (lv[:, 2] < z_hi) & (lv[:, 0] > 0.4) & (lv[:, 0] < 8.0)
        if track_xy is not None:
            d = np.hypot(lv[:, 0] - track_xy[0], lv[:, 1] - track_xy[1])
            hot &= d < 1.8                     # 时序窗口
        if int(hot.sum()) < 30:
            recs[str(fi)] = {"posture": "none"}
            continue
        comps = components(lv[hot, 0], lv[hot, 1])
        if not comps or len(comps[0]) < 30:
            recs[str(fi)] = {"posture": "none"}
            continue
        # walk 时人可能分裂成前后两簇； 取最大两簇的并集再求质心, 单簇则不变
        if posture in ("walk", "fall") and len(comps) > 1 and len(comps[1]) >= 0.4 * len(comps[0]):
            acc = np.asarray(comps[0] + comps[1], dtype=np.int32)
        else:
            acc = np.asarray(comps[0], dtype=np.int32)
        hx, hy = lv[hot][acc, 0], lv[hot][acc, 1]
        cx, cy = float(np.median(hx)), float(np.median(hy))
        r90 = float(np.percentile(np.hypot(hx - cx, hy - cy), 90))
        if track_xy is not None and np.hypot(cx - track_xy[0], cy - track_xy[1]) > jump_gate:
            recs[str(fi)] = {"posture": "none"}       # 跳变, 保守丢弃
            continue
        track_xy = (cx, cy) if track_xy is None else (
            (1 - alpha) * track_xy[0] + alpha * cx,
            (1 - alpha) * track_xy[1] + alpha * cy)
        roi_r = max(0.6, min(1.4, 2.0 * r90))
        recs[str(fi)] = {"posture": posture, "x": round(cx, 3), "y": round(cy, 3),
                         "r_xy": round(roi_r, 3), "n_hot": int(len(acc)),
                         "z_max": round(float(lv[hot][acc, 2].max()), 3),
                         "confidence": "auto"}
    out = {"session_id": sid,
           "labelled_by": "auto_person_label.py+%s-bgdiff" % (empty_sid or EMPTY_SID),
           "posture_set": [posture, "none"], "frames": recs}
    os.makedirs(os.path.join(out_root, sid), exist_ok=True)
    with open(os.path.join(out_root, sid, "ai_labels.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    n = sum(1 for r in recs.values() if r["posture"] != "none")
    return n, len(recs)


def main():
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "captures", "remote")
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--posture", default="stand", choices=sorted(POSTURE_BANDS),
                    help="本会话已知姿态 (z 带 + 跟踪门限)")
    ap.add_argument("--empty", default=None, help="空场模板 sid (默认 %s)" % EMPTY_SID)
    ap.add_argument("sids", nargs="+")
    args = ap.parse_args()
    empty_sid = args.empty or EMPTY_SID
    sids = [s for s in args.sids if s != empty_sid]
    print("building background envelope from %s ..." % empty_sid)
    cells = background_envelope(root, empty_sid=empty_sid)
    print("envelope cells:", len(cells))
    for sid in sids:
        n, tot = label_session(root, sid, cells, root, args.posture)
        print("  %s: %d/%d frames posture=%s" % (sid, n, tot, args.posture))


if __name__ == "__main__":
    main()
