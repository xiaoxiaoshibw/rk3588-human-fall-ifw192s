"""段内移动目标扫描（不需要空场）：自背景 + 单链接分簇 + KF/M-N 跟踪。

用法：
    python -B -W error self_bg_scan.py --out <evidence_dir> --sid cap_20261014_221808 [--stride 1]

原理（对应 24 号调研的"时空背景减除 + 飞行物提取 + 轨迹"路线，2 类方法）：
  1) 自背景：把整段所有帧的体素占用统计一遍，被 ≥`--static-frac` 比例帧占据的格视为静态；
  2) 前景 = 不在静态格里的点；单链接 0.12 m 分簇（≥2 点），稳健核中心 + 到静态格的近似距离；
  3) 复用 `tbd_track.Track`（KF + M/N 确认 + coast）做段内跟踪；
  4) 输出：轨迹表（帧区间/位移/平均速度/点数）+ 逐帧时间线 + PNG。
  备注：自背景会把长时间静止的物体当背景（这是它的设计取舍，与空场法的差异要一起看）。
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from common import REMOTE, load_session, xyz_view
from inspect_target import clusters_local
from plane_shape import robust_core
from tbd_track import (COAST_FRAMES, CONFIRM_HITS, CONFIRM_WINDOW, GATE_BASE_M, GRID_M, Track)

STATIC_CELL_M = 0.15
MIN_POINTS = 2


def build_static_cells(meta, xyz, static_frac=0.3, frame_stride=1):
    """整段体素占用统计 → 静态格键集合（+ origin/base 供查询）。

    先对每帧的格键去重，再用 (key, frame) 的唯一对统计"每格出现在多少帧里"，
    出现帧数 ≥ static_frac × 采样帧数 的格视为静态。
    """
    per_frame_keys = []
    origin = base = None
    for frame in meta["frames"][::frame_stride]:
        lo = int(frame["offset_points"]); hi = lo + int(frame["count_points"])
        points = np.asarray(xyz[lo:hi], dtype=np.float64)
        points = points[np.isfinite(points).all(axis=1)]
        if not len(points):
            per_frame_keys.append(np.zeros(0, dtype=np.int64))
            continue
        cells = np.floor(points / STATIC_CELL_M).astype(np.int64)
        if origin is None:
            origin = cells.min(axis=0)
            span = cells.max(axis=0) - origin + 2
            base = int(span.max()) + 2
        shifted = cells - origin
        keys = (shifted[:, 0] * base + shifted[:, 1]) * base + shifted[:, 2]
        per_frame_keys.append(np.unique(keys))
    sampled = len(per_frame_keys)
    keys_all = np.concatenate(per_frame_keys) if sampled else np.zeros(0, dtype=np.int64)
    frame_ids = np.concatenate([np.full(len(k), i, dtype=np.int64)
                                for i, k in enumerate(per_frame_keys)]) if sampled \
        else np.zeros(0, dtype=np.int64)
    combined = np.unique(keys_all.astype(np.int64) * sampled + frame_ids)
    keys = combined // sampled
    unique_keys, counts = np.unique(keys, return_counts=True)
    static_keys = unique_keys[counts >= static_frac * sampled]
    return static_keys, origin, base, sampled


def frame_candidates_selfbg(points, static_keys, origin, base):
    """前景 = 0.15 m 格不在静态集合里（1 次查表）；单链接 0.12 m 分簇（≥2 点）。"""
    cells = np.floor(points / STATIC_CELL_M).astype(np.int64) - origin
    packed = (cells[:, 0] * base + cells[:, 1]) * base + cells[:, 2]
    index = np.searchsorted(static_keys, packed)
    index = np.minimum(index, len(static_keys) - 1)
    foreground = static_keys[index] != packed
    candidates = []
    fg_points = points[foreground]
    if not len(fg_points):
        return candidates, 0
    for members in clusters_local(fg_points, GRID_M, MIN_POINTS):
        group = fg_points[members]
        center, core = robust_core(group)
        candidates.append({"center": center, "points": int(len(group)), "core_points": int(len(core)),
                           "weight": float(min(len(group), 32))})
    return candidates, int(foreground.sum())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--sid", default="cap_20261014_221808")
    parser.add_argument("--static-frac", type=float, default=0.3)
    parser.add_argument("--frame-stride", type=int, default=2)
    parser.add_argument("--name", default=None)
    args = parser.parse_args()
    out = Path(args.out)
    directory, meta = load_session(args.sid)
    xyz = xyz_view(directory, meta)
    static_keys, origin, base, frames_used = build_static_cells(meta, xyz, args.static_frac,
                                                               args.frame_stride)

    tracks, finished, next_id = [], [], 1
    rows = []
    for index, frame in enumerate(meta["frames"]):
        stamp = float(frame.get("bag_time_sec", frame["stamp_sec"]))
        lo = int(frame["offset_points"]); hi = lo + int(frame["count_points"])
        points = np.asarray(xyz[lo:hi], dtype=np.float64)
        points = points[np.isfinite(points).all(axis=1)]
        candidates, foreground = frame_candidates_selfbg(points, static_keys, origin, base)
        for track in tracks:
            track.predict(stamp)
        used = set()
        for track in tracks:
            gate = max(GATE_BASE_M, 1.5 * float(np.linalg.norm(track.x[3:])) * 0.103 + 0.2)
            best = None
            for order, candidate in enumerate(candidates):
                if order in used:
                    continue
                distance = float(np.linalg.norm(candidate["center"] - track.x[:3]))
                if distance <= gate and (best is None or distance < best[0]):
                    best = (distance, order, candidate)
            if best is not None:
                _, order, candidate = best
                used.add(order)
                track.update(candidate["center"], stamp, candidate["weight"], index)
            else:
                track.missed()
        for order, candidate in enumerate(candidates):
            if order in used or candidate["points"] < 3:
                continue
            tracks.append(Track(next_id, candidate["center"], stamp, candidate["weight"], index))
            next_id += 1
        tracks = [t for t in tracks if t.alive]
        rows.append({"frame": index, "stamp_s": stamp, "candidates": len(candidates),
                     "foreground_points": foreground,
                     "confirmed": sum(1 for t in tracks if t.confirmed)})
    finished.extend(tracks)
    summaries = [t.summary() for t in finished]
    moving = sorted([s for s in summaries if s["moving"]], key=lambda s: -s["score"])
    payload = {
        "sid": args.sid, "frames": len(meta["frames"]), "duration_s": meta["duration_sec"],
        "static_cells": int(len(static_keys)), "static_frac": args.static_frac,
        "frames_used_for_background": frames_used,
        "note": "自背景法（无需空场）；长期静止物体会被视为背景，与空场法互补",
        "tracks_finished": len(summaries), "tracks_confirmed": sum(1 for s in summaries if s["confirmed"]),
        "moving_tracks": moving, "all_tracks": summaries, "timeline": rows,
    }
    name = args.name or ("35_SELF_BG_%s.json" % args.sid)
    with (out / name).open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"sid": args.sid, "duration_s": payload["duration_s"],
                      "static_cells": payload["static_cells"],
                      "tracks_confirmed": payload["tracks_confirmed"],
                      "moving_tracks": moving[:5]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
