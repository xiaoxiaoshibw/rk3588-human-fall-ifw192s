"""B：准实时演示服务（10 Hz，P1 在线段：低门槛候选 → KF/M-N 跟踪 → TBD 声明）。

用法：
    python -B -W error rt_server.py --port 8971 [--start-delay 6]

诚实口径：
- 启动时做一次 **离线上游**（前景/自由空间候选提取，逐帧实测 ms 写入 manifest），
  然后按源帧真实间隔（≈10 Hz）喂帧，**只测在线段**（候选→关联→KF 更新→TBD 计分→发布）。
- 页面/客户端接口与 `replay_server.py` 保持一致，`replay_client.py` 可直接复用测量。
端点：
- GET /            可视化页（rt.html）
- GET /api/state   当前帧/统计/轨迹状态/TBD 声明
- GET /api/points?i=<frame>  二进制：uint32 数 + float32 中心 + uint8 标记(1=确认运动轨迹)
"""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

from background import apply_transform, background_keys, collect_points, foreground_mask, load_points
from inspect_target import clusters_local
from plane_shape import robust_core
from tbd_track import (CELL_M, FREE_SPACE_MIN_M, GRID_M, Track, frame_candidates, tbd_declared_frame,
                       batch_tbd)

HERE = Path(__file__).resolve().parent
LOCK = threading.Lock()
STATE = {"started": False, "frames_total": 0, "current": -1, "rows": [], "published": [],
         "client_reports": [], "upstream_ms_per_frame": None, "tbd": None}


DEFAULT_REGISTRATION = (r"D:\Code\ldiar\docs\sidequests\evidence\2026-10-14_plane_track_r1"
                        r"\03_REGISTRATION_131958_to_164522")


def _pack_cells(cells, base):
    return (cells[:, 0] * base + cells[:, 1]) * base + cells[:, 2]


def _dedup_keys(points, cell):
    """去重后的占用格键（排序数组）+ origin/base；查表用 np.searchsorted。"""
    cells = np.floor(points / cell).astype(np.int64)
    origin = cells.min(axis=0)
    span = cells.max(axis=0) - origin + 2
    base = int(span.max()) + 2
    keys = np.unique(_pack_cells(cells - origin, base))
    return keys, origin, base


class EmptyIndex:
    """把空场点按 0.5 m 格排序，查询时只取邻域点做精确最近距离（毫秒级）。"""

    def __init__(self, points, cell=0.5):
        self.cell = cell
        self.origin = np.floor(points.min(axis=0) / cell).astype(np.int64)
        cells = np.floor(points / cell).astype(np.int64) - self.origin
        span = cells.max(axis=0) + 2
        self.base = int(span.max()) + 2
        keys = _pack_cells(cells, self.base)
        order = np.argsort(keys)
        self.points = points[order]
        self.keys = keys[order]

    def nearest_distance(self, center, cap=1.5):
        i, j, k = np.floor(center / self.cell).astype(np.int64) - self.origin
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    key = (i + dx) * (self.base * self.base) + (j + dy) * self.base + (k + dz)
                    lo = int(np.searchsorted(self.keys, key, "left"))
                    hi = int(np.searchsorted(self.keys, key, "right"))
                    if hi > lo:
                        distance = float(np.linalg.norm(self.points[lo:hi] - center, axis=1).min())
                        best = distance if best is None else min(best, distance)
        if best is None:
            return cap   # 邻域内没有空场点：返回下界 cap
        return best


def _cell_foreground(points, keys, origin, base, cell):
    """单次查表的快速前景：同格无空场点即算前景（格 0.15 m，等价于"最近空场点 ≳0.15 m"）。"""
    cells = np.floor(points / cell).astype(np.int64) - origin
    packed = (cells[:, 0] * base + cells[:, 1]) * base + cells[:, 2]
    index = np.searchsorted(keys, packed)
    index = np.minimum(index, len(keys) - 1)
    return keys[index] != packed


def _foreground_mask_fast(points, keys, origin, base, cell_m=CELL_M, ring=1):
    """与 background.foreground_mask 同语义，但已命中的点不再参与后续偏移查询（约 2–6× 提速）。"""
    cells = np.floor(points / cell_m).astype(np.int64) - origin
    hit = np.zeros(len(points), dtype=bool)
    stride_y, stride_x = base, base * base
    pending = np.arange(len(points))
    for dx in range(-ring, ring + 1):
        for dy in range(-ring, ring + 1):
            for dz in range(-ring, ring + 1):
                if not len(pending):
                    return ~hit
                shifted = ((cells[pending, 0] + dx) * stride_x + (cells[pending, 1] + dy) * stride_y
                           + (cells[pending, 2] + dz))
                index = np.searchsorted(keys, shifted)
                index = np.minimum(index, len(keys) - 1)
                found = keys[index] == shifted
                hit[pending[found]] = True
                pending = pending[~found]
    return ~hit


def build_upstream(job="363473a9e2e64649994dca11b2b26929",
                   empty_job="61cb6976b0f8479394641850d9a7c6ca",
                   registration_dir=DEFAULT_REGISTRATION,
                   fast=True, fast_cell=0.15):
    """离线上游：逐帧自由空间候选（含逐帧耗时）。

    fast=True 用 0.15 m 单格查表（1 次 searchsorted/点）先粗筛，再对存活点簇心做精确
    自由空间距离（≥0.22 m）；fast=False 保留原 0.08 m 网格 ±1 格（27 次查表）作对照。
    """
    registration = json.loads((Path(registration_dir) / "registration.json").read_text(encoding="utf8"))
    target_frames, _tmeta = load_points(job, "tls")
    empty_frames, _emeta = load_points(empty_job, "tls")
    empty_registered = apply_transform(empty_frames, registration["rotation_row_major"],
                                       registration["translation_m"])
    empty_points = collect_points(empty_registered, stride=2)
    empty_index = EmptyIndex(empty_points)
    keys, origin, base = _dedup_keys(empty_points, CELL_M)
    frames, costs, raw = [], [], []
    for index, stamp, xyz, _values in target_frames:
        began = time.perf_counter()
        finite = np.isfinite(xyz).all(axis=1)
        points = xyz[finite]
        mask = _foreground_mask_fast(points, keys, origin, base, CELL_M)
        candidates = _candidates_from_mask(points, mask, empty_index)
        costs.append((time.perf_counter() - began) * 1000.0)
        frames.append((index, stamp, candidates))
        raw.append((index, stamp, points))
    return frames, costs, raw


def _candidates_from_mask(points, mask, empty_index):
    candidates = []
    for members in clusters_local(points[mask], GRID_M, 1):
        group = points[mask][members]
        center, core = robust_core(group)
        distance = empty_index.nearest_distance(center)
        if distance < FREE_SPACE_MIN_M:
            continue
        candidates.append({"center": center, "points": int(len(group)),
                           "core_points": int(len(core)),
                           "distance_to_empty_m": round(float(distance), 3),
                           "weight": float(min(len(group), 32))})
    return candidates


def _live_front_end(points, keys, origin, base, empty_index):
    """在线段的检测前端（与离线路径同语义）：前景 → 分簇 → 自由空间门。"""
    mask = _foreground_mask_fast(points, keys, origin, base, CELL_M)
    return _candidates_from_mask(points, mask, empty_index)


def replay_worker(raw_frames, front_end, start_delay):
    time.sleep(start_delay)
    t0 = time.perf_counter()
    tracks, next_id = [], 1
    for index, stamp, points in raw_frames:
        scheduled = t0 + (stamp - raw_frames[0][1])
        now = time.perf_counter()
        if now < scheduled:
            time.sleep(scheduled - now)
        began = time.perf_counter()
        late = began > scheduled + 0.005
        candidates = front_end(points)
        for track in tracks:
            track.predict(stamp)
        used = set()
        for track in tracks:
            prediction = track.x[:3]
            gate = max(0.5, 1.5 * float(np.linalg.norm(track.x[3:])) * 0.103 + 0.2)
            best = None
            for order, candidate in enumerate(candidates):
                if order in used:
                    continue
                distance = float(np.linalg.norm(candidate["center"] - prediction))
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
        moving = [t for t in tracks if t.confirmed and float(np.linalg.norm(t.x[3:])) > 0.5]
        target = max(moving, key=lambda t: t.score) if moving else None
        flags = []
        for candidate in candidates:
            hit = target is not None and float(np.linalg.norm(candidate["center"] - target.x[:3])) < 0.5
            flags.append(1 if hit else 0)
        done = time.perf_counter()
        with LOCK:
            STATE["current"] = index
            STATE["rows"].append({"frame": index, "stamp_s": stamp, "candidates": len(candidates),
                                  "confirmed_tracks": sum(1 for t in tracks if t.confirmed),
                                  "target_id": None if target is None else target.id,
                                  "target_speed_m_s": None if target is None else round(float(np.linalg.norm(target.x[3:])), 3),
                                  "target_position": None if target is None else [round(float(v), 3) for v in target.x[:3]],
                                  "compute_ms": (done - began) * 1000.0,
                                  "publish_delay_ms": (done - scheduled) * 1000.0,
                                  "late_start": bool(late),
                                  "flags": flags,
                                  "centers": [[round(float(v), 3) for v in c["center"]] for c in candidates]})
            STATE["published"].append(done)
    with LOCK:
        STATE["finished"] = time.perf_counter()


def state_payload():
    with LOCK:
        rows = list(STATE["rows"])
        compute = [r["compute_ms"] for r in rows]
        delay = [r["publish_delay_ms"] for r in rows]
        return {"sid": "cap_20261014_164522", "frames_total": STATE["frames_total"],
                "frames_published": len(rows), "current": STATE["current"],
                "upstream_ms_per_frame": STATE["upstream_ms_per_frame"],
                "detected_frames": sum(1 for r in rows if r.get("target_id") is not None),
                "dropped_schedule": sum(1 for r in rows if r["late_start"]),
                "late_start_frames": [r["frame"] for r in rows if r["late_start"]],
                "compute_ms": {"median": float(np.median(compute)) if compute else None,
                               "p95": float(np.percentile(compute, 95)) if compute else None,
                               "max": max(compute) if compute else None},
                "publish_delay_ms": {"median": float(np.median(delay)) if delay else None,
                                     "p95": float(np.percentile(delay, 95)) if delay else None,
                                     "max": max(delay) if delay else None},
                "late_start": sum(1 for r in rows if r["late_start"]),
                "tbd": STATE["tbd"], "client_reports": list(STATE["client_reports"]),
                "rows": rows}


class Handler(BaseHTTPRequestHandler):
    def send(self, data, mime="application/json; charset=utf-8", code=200):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf8")
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        from urllib.parse import urlsplit, parse_qs
        url = urlsplit(self.path)
        if url.path == "/":
            return self.send((HERE / "rt.html").read_bytes(), "text/html; charset=utf-8")
        if url.path == "/api/state":
            return self.send(state_payload())
        if url.path == "/api/points":
            try:
                index = int(parse_qs(url.query)["i"][0])
            except (KeyError, ValueError):
                return self.send({"error": "i required"}, code=400)
            with LOCK:
                if STATE["current"] < 0:
                    return self.send({"error": "not started"}, code=409)
                row = STATE["rows"][-1]
            centers = np.asarray(row["centers"], dtype="<f4").reshape(-1, 3) if row["centers"] \
                else np.zeros((0, 3), dtype="<f4")
            flags = np.asarray(row["flags"], dtype=np.uint8)
            payload = np.array([len(centers)], dtype="<u4").tobytes() + centers.tobytes() + flags.tobytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("X-Frame-Index", str(row["frame"]))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        return self.send({"error": "not found"}, code=404)

    def do_POST(self):
        from urllib.parse import urlsplit
        if urlsplit(self.path).path != "/api/client":
            return self.send({"error": "not found"}, code=404)
        length = int(self.headers.get("Content-Length", 0))
        try:
            report = json.loads(self.rfile.read(length).decode("utf8"))
        except (ValueError, UnicodeDecodeError):
            return self.send({"error": "bad json"}, code=400)
        with LOCK:
            STATE["client_reports"].append(report)
        return self.send({"ok": True})

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8971)
    parser.add_argument("--start-delay", type=float, default=6.0)
    parser.add_argument("--registration", default=DEFAULT_REGISTRATION)
    args = parser.parse_args()
    print("warm-up: 离线上游（前景/候选，用于批量 TBD）…", flush=True)
    frames, costs, raw_frames = build_upstream(registration_dir=args.registration)
    ranked, static_count = batch_tbd(frames)
    declared = tbd_declared_frame(ranked)
    with LOCK:
        STATE["frames_total"] = len(frames)
        STATE["upstream_ms_per_frame"] = {"median": float(np.median(costs)), "max": float(max(costs))}
        STATE["tbd"] = {"declared_first_frame": declared, "static_pairs_skipped": static_count,
                        "top": ranked[:3]}
    print("upstream median %.0f ms/frame; TBD declared frame %s" % (STATE["upstream_ms_per_frame"]["median"],
                                                                   declared), flush=True)
    registration = json.loads((Path(args.registration) / "registration.json").read_text(encoding="utf8"))
    empty_frames, _emeta = load_points("61cb6976b0f8479394641850d9a7c6ca", "tls")
    empty_registered = apply_transform(empty_frames, registration["rotation_row_major"],
                                       registration["translation_m"])
    empty_points = collect_points(empty_registered, stride=2)
    empty_index = EmptyIndex(empty_points)
    keys, origin, base = _dedup_keys(empty_points, CELL_M)
    front_end = lambda pts: _live_front_end(pts, keys, origin, base, empty_index)
    worker = threading.Thread(target=replay_worker, args=(raw_frames, front_end, args.start_delay),
                              daemon=True)
    worker.start()
    print("rt demo http://127.0.0.1:%d/ (%d frames @10 Hz, online stage only)" % (args.port, len(frames)),
          flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
