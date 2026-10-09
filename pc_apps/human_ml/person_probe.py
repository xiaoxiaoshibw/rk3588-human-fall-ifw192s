# -*- coding: utf-8 -*-
"""person_probe.py — 批量渲染 + 背景差分/z 带占位数值探针，辅助 AI 逐帧判读人体 ROI。

用法:
    python person_probe.py <sid> [<sid>...]     # 渲染全部给定会话 + 输出 probe.json

每会话:
  1. render_person_label.main(session) -> film_person/f%04d.png
  2. 对每帧算 leveled 点云 -> 背景差分参考 (取空场模板 113611 的多帧 90% 高度包络,
     再在每帧上找「显著高于同位背景」的点集) 输出候选 xy 占位+峰值高度.

探针只做候选给 AI 看, 不参与判定; 判定由 AI 读图得出。
"""
import json
import os
import sys

import numpy as np

from render_person_label import R, T, ground_peak

EMPTY_SID = "cap_20261009_113611"


def load_frames(root, sid):
    meta = json.load(open(os.path.join(root, sid, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(root, sid, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, 28).view(np.float32).reshape(-1, 7)
    return meta, raw


def level_frame(seg):
    xyz = seg[:, :3].astype(np.float64)
    v = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
    return xyz[v] @ R.T + T


def empty_envelope(root, step=4, sid=None):
    """空场模板: 每隔 step 帧抽一帧, 在 5cm XY 网格上取 z 的 95 分位作背景上界。"""
    meta, raw = load_frames(root, sid or EMPTY_SID)
    cells = {}
    for fi in range(0, len(meta["frames"]), step):
        lv = level_frame(raw[meta["frames"][fi]["offset_points"]:
                             meta["frames"][fi]["offset_points"] + meta["frames"][fi]["count_points"]])
        lv = lv[(lv[:, 2] - ground_peak(lv[:, 2])) > -0.05]
        if not len(lv):
            continue
        gx = np.floor(lv[:, 0] / 0.05).astype(np.int32)
        gy = np.floor(lv[:, 1] / 0.05).astype(np.int32)
        key = gx * 4096 + gy
        # 聚合每格 z 的 95 分位
        z = lv[:, 2]
        order = np.argsort(key, kind="stable")
        k, z = key[order], z[order]
        bounds = np.flatnonzero(np.r_[True, k[1:] != k[:-1], True])
        for a, b in zip(bounds[:-1], bounds[1:]):
            if b - a < 2:
                continue
            p95 = float(np.percentile(z[a:b], 95))
            kk = int(k[a])
            if kk not in cells or p95 > cells[kk]:
                cells[kk] = p95
    return cells


def probe_session(root, sid, cells, out_root):
    meta, raw = load_frames(root, sid)
    out = {"session_id": sid, "n_frames": len(meta["frames"]), "frames": []}
    film_dir = os.path.join(out_root, sid, "film_person")
    os.makedirs(film_dir, exist_ok=True)
    for fi, f in enumerate(meta["frames"]):
        lv = level_frame(raw[f["offset_points"]: f["offset_points"] + f["count_points"]])
        z0 = ground_peak(lv[:, 2])
        z = lv[:, 2] - z0
        gx = np.floor(lv[:, 0] / 0.05).astype(np.int32)
        gy = np.floor(lv[:, 1] / 0.05).astype(np.int32)
        key = gx * 4096 + gy
        # 高度明显高于同位背景 95 分位 + 0.20m
        bg = np.array([cells.get(int(k), -10.0) for k in key], dtype=np.float64)
        excess = z - (bg + 0.20)
        hot = (excess > 0) & (lv[:, 0] > 0.4) & (lv[:, 0] < 6.0)
        if hot.sum() < 5:
            out["frames"].append({"frame": fi, "candidate": None})
            continue
        hx, hy, hz = lv[hot, 0], lv[hot, 1], z[hot]
        # 单簇假设: 90 分位法找主团
        cx, cy = float(np.median(hx)), float(np.median(hy))
        r = np.sqrt((hx - cx) ** 2 + (hy - cy) ** 2)
        rr = float(np.percentile(r, 90))
        keep = r <= rr
        out["frames"].append({
            "frame": fi,
            "candidate": {
                "x": round(cx, 3), "y": round(cy, 3), "r90": round(rr, 3),
                "n_hot": int(keep.sum()), "z_p90": round(float(np.percentile(hz[keep], 90)), 3),
            }})
    with open(os.path.join(out_root, sid, "probe.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    return out


def main():
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "captures", "remote")
    out_root = root  # probe.json + film_person 落回会话目录
    sids = [s for s in sys.argv[1:] if s != EMPTY_SID]
    if not sids:
        print("usage: person_probe.py <sid> [<sid>...]  (empty template %s is auto-excluded)" % EMPTY_SID)
        return
    print("building empty-room envelope from %s ..." % EMPTY_SID)
    cells = empty_envelope(root)
    print("envelope cells:", len(cells))
    for sid in sids:
        from render_person_label import main as render
        render(os.path.join(root, sid))
        probe = probe_session(root, sid, cells, out_root)
        hot = sum(1 for f in probe["frames"] if f["candidate"])
        print("  %s: %d/%d frames have candidate" % (sid, hot, probe["n_frames"]))


if __name__ == "__main__":
    main()
