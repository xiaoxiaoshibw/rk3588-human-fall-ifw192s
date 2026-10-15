"""T5 本机 10 Hz 准实时回放（不做板端部署；只读 captures）。

用法：
    python -B -W error replay_server.py --job <job_id> --port 8941 [--period-scale 1.0]
- 按源帧真实 bag 时间间隔（≈10 Hz）喂帧；每帧跑 core/lidar_candidates 候选层 + 关联跟踪。
- GET /            可视化页面（顶视+侧视，灰色=房间，红色=目标簇，HUD 显示延迟/掉帧）
- GET /api/state   当前帧/统计 JSON（含每帧处理耗时、发布延迟、掉帧计数）
- GET /api/points?i=<frame>  该帧渲染点（二进制 float32 xyz + 目标掩码字节）
- GET /api/client  POST 客户端回传的渲染延迟（页面用 performance.now() 记录）
"""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

from plane_track import GATE_M, frame_candidates, load_leveled_frames, snapshot_settings

HERE = Path(__file__).resolve().parent
STATE_LOCK = threading.Lock()
STATE = {
    "job_id": None, "sid": None, "frames": 0, "period_s": [], "current": -1,
    "published": [], "track_rows": [], "events": [],
    "client_reports": [], "started": None, "finished": None, "dropped_schedule": 0,
}


def render_payload(xyz, mask_target, stride=4):
    """Binary: uint32 count + float32 xyz (room subsample) + uint8 target flags."""
    room = xyz[::stride]
    flags = mask_target[::stride].astype(np.uint8)
    header = np.array([len(room)], dtype="<u4").tobytes()
    return header + np.float32(room).tobytes() + flags.tobytes()


def replay_worker(frames, settings, step_scale, start_delay=0.0):
    from plane_track import streak_m
    time.sleep(start_delay)
    t0 = time.perf_counter()
    previous = None
    last_streak = None
    next_scheduled = None
    for index, stamp, xyz, _values in frames:
        scheduled = t0 + (stamp - frames[0][1]) * step_scale
        now = time.perf_counter()
        if now < scheduled:
            time.sleep(scheduled - now)
        compute_start = time.perf_counter()
        late_start = compute_start > scheduled + 0.005
        candidates = frame_candidates(xyz, settings, STATE["sid"], index, stamp)
        for candidate in candidates:
            local = xyz[candidate["evidence_indices"]]
            candidate["streak_m"], candidate["streak_direction"] = streak_m(local)
        gate = GATE_M
        if last_streak is not None:
            gate = max(GATE_M, 1.2 * last_streak + 0.15)
        picked = None
        if previous is not None:
            for candidate in candidates:
                distance = float(np.linalg.norm(np.asarray(candidate["center"]) - previous))
                if distance <= gate and (picked is None or distance < picked[0]):
                    picked = (distance, candidate)
        else:
            for candidate in candidates:
                distance = float(np.linalg.norm(np.asarray(candidate["center"])
                                                - np.array([5.75, -0.52, 3.0])))
                if distance <= 1.2 and (picked is None or distance < picked[0]):
                    picked = (distance, candidate)
        compute_done = time.perf_counter()
        row = {"frame": index, "stamp_s": stamp, "candidates": len(candidates),
               "detected": picked is not None, "compute_ms": (compute_done - compute_start) * 1000.0,
               "schedule_delay_ms": (compute_start - scheduled) * 1000.0,
               "publish_delay_ms": (compute_done - scheduled) * 1000.0,
               "late_start": bool(late_start),
               "point_count": None if picked is None else picked[1]["point_count"],
               "range_median_m": None if picked is None else picked[1]["range_median_m"],
               "streak_m": None if picked is None else picked[1]["streak_m"],
               "gate_m": gate,
               "center": None if picked is None else picked[1]["center"]}
        if picked is not None:
            previous = np.asarray(picked[1]["center"])
            last_streak = picked[1]["streak_m"]
        mask = np.zeros(len(xyz), dtype=bool)
        if picked is not None:
            mask[picked[1]["evidence_indices"]] = True
        with STATE_LOCK:
            STATE["current"] = index
            STATE["track_rows"].append(row)
            STATE["last_xyz"] = xyz
            STATE["last_mask"] = mask
            STATE["published"].append({"frame": index, "t_publish": compute_done, "t_scheduled": scheduled})
        next_scheduled = scheduled
    with STATE_LOCK:
        STATE["finished"] = time.perf_counter()


def stats_payload():
    with STATE_LOCK:
        rows = list(STATE["track_rows"])
        published = list(STATE["published"])
        payload = {
            "sid": STATE["sid"], "job_id": STATE["job_id"], "frames_total": STATE["frames"],
            "frames_published": len(rows), "current": STATE["current"],
            "detected_frames": sum(1 for row in rows if row["detected"]),
            "compute_ms": {"median": float(np.median([row["compute_ms"] for row in rows])) if rows else None,
                           "p95": float(np.percentile([row["compute_ms"] for row in rows], 95)) if rows else None,
                           "max": max((row["compute_ms"] for row in rows), default=None)},
            "publish_delay_ms": {"median": float(np.median([row["publish_delay_ms"] for row in rows])) if rows else None,
                                 "p95": float(np.percentile([row["publish_delay_ms"] for row in rows], 95)) if rows else None,
                                 "max": max((row["publish_delay_ms"] for row in rows), default=None)},
            "dropped_schedule": sum(1 for row in rows if row["late_start"]),
            "late_start_frames": [row["frame"] for row in rows if row["late_start"]],
            "client_reports": list(STATE["client_reports"]),
            "rows": rows,
        }
    return payload


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
            return self.send((HERE / "replay.html").read_bytes(), "text/html; charset=utf-8")
        if url.path == "/api/state":
            return self.send(stats_payload())
        if url.path == "/api/points":
            try:
                index = int(parse_qs(url.query)["i"][0])
            except (KeyError, ValueError):
                return self.send({"error": "i required"}, code=400)
            with STATE_LOCK:
                if STATE["current"] < 0:
                    return self.send({"error": "not started"}, code=409)
                xyz = STATE["last_xyz"]
                mask = STATE["last_mask"]
                stamp = STATE["published"][-1]["t_publish"]
                seq = STATE["current"]
            payload = render_payload(xyz, mask)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("X-Frame-Index", str(seq))
            self.send_header("X-Frame-T-Publish", "%.6f" % stamp)
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
        with STATE_LOCK:
            STATE["client_reports"].append(report)
        return self.send({"ok": True})

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", default="363473a9e2e64649994dca11b2b26929")
    parser.add_argument("--sid", default="cap_20261014_164522")
    parser.add_argument("--port", type=int, default=8941)
    parser.add_argument("--method", default="tls")
    parser.add_argument("--period-scale", type=float, default=1.0)
    parser.add_argument("--start-delay", type=float, default=0.0,
                        help="seconds to wait before the replay starts (client/browser can attach)")
    args = parser.parse_args()
    frames, _transform, _meta = load_leveled_frames(args.job, args.method, args.sid)
    with STATE_LOCK:
        STATE["job_id"] = args.job
        STATE["sid"] = args.sid
        STATE["frames"] = len(frames)
        STATE["started"] = time.perf_counter()
    worker = threading.Thread(target=replay_worker,
                              args=(frames, snapshot_settings(), args.period_scale, args.start_delay),
                              daemon=True)
    worker.start()
    print("replay http://127.0.0.1:%d/ (%d frames @real cadence)" % (args.port, len(frames)), flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
