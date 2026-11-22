"""Serve ESP32-S3 human kinematic & fall-detection JSON output over HTTP/SSE on RK3588.

Python 3.8+ compatible. Live mode uses pyserial and accepts an explicit serial
port and IFW192S calibration file.
"""

import argparse
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from queue import Empty, Full, Queue
import struct
import sys
from threading import Event, Lock, Thread
from time import monotonic, sleep, time as wall_time
import zlib

VENDOR_DIR = Path.home() / ".local/opt/lidar-bird-s3/runtime/vendor"
if VENDOR_DIR.is_dir() and str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

HTML_PATH = Path(__file__).with_name("human_s3_live.html")

HEADER = struct.Struct("<4sIII")
RUN = struct.Struct("<4sI")
CALIBRATION_BYTES = 16 + 49152 * 16
FIRST_FRAME_TIMEOUT = 18.0
FRAME_TIMEOUT = 3.0
MAX_TRAIL_POINTS = 120
MAX_KIN_SAMPLES = 120
MAX_EVENTS = 40
HISTORY_TTL_SEC = 20.0


class HumanFrameAssembler:
    """Group ESP32-S3 Protocol 2 frame and track lines into atomic snapshots."""

    def __init__(self):
        self._pending = None
        self._expected_tracks = 0

    def _finalize(self):
        frame = self._pending
        self._pending = None
        self._expected_tracks = 0
        return frame

    def push_message(self, msg):
        if not isinstance(msg, dict):
            return []
        msg_type = msg.get("type")
        completed = []

        if msg_type == "frame":
            if self._pending is not None:
                completed.append(self._finalize())
            state = str(msg.get("state", "UNKNOWN"))
            locked = int(msg.get("locked", 0)) if state == "active" else 0
            tail_us = msg.get("tail_read_us")
            grid_us = msg.get("grid_ready_us")
            start_us = msg.get("tracker_start_us")
            ready_us = msg.get("result_ready_us")

            latency_ms = None
            materialize_ms = None
            tracker_ms = None
            if isinstance(tail_us, (int, float)) and isinstance(ready_us, (int, float)):
                latency_ms = round((ready_us - tail_us) / 1000.0, 3)
            if isinstance(tail_us, (int, float)) and isinstance(grid_us, (int, float)):
                materialize_ms = round((grid_us - tail_us) / 1000.0, 3)
            if isinstance(start_us, (int, float)) and isinstance(ready_us, (int, float)):
                tracker_ms = round((ready_us - start_us) / 1000.0, 3)

            snapshot = {
                "seq": msg.get("seq"),
                "state": state,
                "warmup": int(msg.get("warmup", 0)),
                "locked": locked,
                "candidates": int(msg.get("candidates", 0)),
                "tentative": int(msg.get("tentative", 0)),
                "valid_cells": int(msg.get("valid_cells", 0)),
                "fg_seeds": int(msg.get("fg_seeds", 0)),
                "fall_suspected": int(msg.get("fall_suspected", 0)),
                "records": msg.get("records"),
                "latency_ms": latency_ms,
                "materialize_ms": materialize_ms,
                "tracker_ms": tracker_ms,
                "tracks": [],
            }
            if "host_wall_ms" in msg:
                snapshot["host_wall_ms"] = msg["host_wall_ms"]
            if "host_mono_ms" in msg:
                snapshot["host_mono_ms"] = msg["host_mono_ms"]

            if state == "active" and locked > 0:
                self._pending = snapshot
                self._expected_tracks = locked
            else:
                completed.append(snapshot)
            return completed

        if msg_type == "track" and self._pending is not None:
            if msg.get("seq") == self._pending.get("seq"):
                self._pending["tracks"].append({
                    "id": int(msg.get("id", 0)),
                    "box": msg.get("box", [0, 0, 0, 0]),
                    "xyz_m": msg.get("xyz_m", [0.0, 0.0, 0.0]),
                    "points": int(msg.get("points", 0)),
                    "range_m": float(msg.get("range_m", 0.0)),
                    "height_m": float(msg.get("height_m", 0.0)),
                    "h_p95": float(msg.get("h_p95", 0.0)),
                    "horiz_m": float(msg.get("horiz_m", 0.0)),
                    "aspect": float(msg.get("aspect", 0.0)),
                    "drop_m": float(msg.get("drop_m", 0.0)),
                    "vel_mps": float(msg.get("vel_mps", 0.0)),
                    "acc_mps2": float(msg.get("acc_mps2", 0.0)),
                    "peak_down_vel": float(msg.get("peak_down_vel", 0.0)),
                    "peak_down_acc": float(msg.get("peak_down_acc", 0.0)),
                    "low_sec": float(msg.get("low_sec", 0.0)),
                    "still_sec": None if msg.get("still_sec") is None else float(msg["still_sec"]),
                    "baseline_ready": bool(msg.get("baseline_ready", False)),
                    "fall_state": str(msg.get("fall_state", "UNKNOWN")),
                    "fall_reason": str(msg.get("fall_reason", "NONE")),
                })
                if len(self._pending["tracks"]) >= self._expected_tracks:
                    completed.append(self._finalize())
            return completed

        if msg_type in ("summary", "ethernet_done", "error") and self._pending is not None:
            completed.append(self._finalize())
        return completed

    def flush(self):
        return [self._finalize()] if self._pending is not None else []


class HumanLiveHub:
    """Thread-safe hub storing latest frame, trails, kinematics history, events, and SSE clients."""

    def __init__(self, source_label):
        self.source_label = source_label
        self._lock = Lock()
        self._input_status = "waiting"
        self._device_info = {}
        self._latest = None
        self._trails = {}
        self._kinematics = {}
        self._last_seen = {}
        self._history_epoch = 0
        self._prev_states = {}
        self._events = deque(maxlen=MAX_EVENTS)
        self._frame_times = deque(maxlen=30)
        self._subscribers = set()

    def set_device_info(self, info):
        with self._lock:
            self._device_info = dict(info)
            self._broadcast_locked("status", {"status": self._input_status, "device": self._device_info})

    def _broadcast_locked(self, event_name, payload):
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        msg = "event: {}\ndata: {}\n\n".format(event_name, encoded) if event_name else "data: {}\n\n".format(encoded)
        for q in list(self._subscribers):
            try:
                q.put_nowait(msg)
            except Full:
                try:
                    q.get_nowait()
                except Empty:
                    pass
                try:
                    q.put_nowait(msg)
                except Full:
                    pass

    def reset_input(self, status, detail=""):
        with self._lock:
            self._input_status = status
            self._reset_histories_locked()
            self._prev_states.clear()
            self._frame_times.clear()
            self._latest = {
                "seq": None,
                "state": "UNKNOWN",
                "locked": 0,
                "candidates": 0,
                "tentative": 0,
                "valid_cells": 0,
                "fg_seeds": 0,
                "fall_suspected": 0,
                "tracks": [],
                "source": self.source_label,
                "fps": 0.0,
            }
            if detail:
                self._events.appendleft({
                    "wall_ms": round(wall_time() * 1000.0, 1),
                    "kind": "status",
                    "text": detail,
                })
            self._broadcast_locked("init", self._snapshot_locked())

    def input_status(self, status, detail=""):
        with self._lock:
            self._input_status = status
            if detail:
                self._events.appendleft({
                    "wall_ms": round(wall_time() * 1000.0, 1),
                    "kind": "status",
                    "text": detail,
                })
            self._broadcast_locked("status", {"status": status, "device": self._device_info, "detail": detail})

    def clear_history(self):
        with self._lock:
            self._reset_histories_locked()
            self._events.clear()
            self._broadcast_locked("init", self._snapshot_locked())

    def _reset_histories_locked(self):
        self._trails.clear()
        self._kinematics.clear()
        self._last_seen.clear()
        self._history_epoch += 1

    def _prune_history_locked(self, now):
        for tid, last_seen in list(self._last_seen.items()):
            if now - last_seen >= HISTORY_TTL_SEC:
                del self._last_seen[tid]
                self._trails.pop(tid, None)
                self._kinematics.pop(tid, None)
                self._prev_states.pop(tid, None)

    def publish(self, frame):
        now_wall = round(wall_time() * 1000.0, 1)
        with self._lock:
            now = monotonic()
            self._prune_history_locked(now)
            self._frame_times.append(now)
            fps = 0.0
            if len(self._frame_times) >= 2:
                span = self._frame_times[-1] - self._frame_times[0]
                if span > 0:
                    fps = round((len(self._frame_times) - 1) / span, 2)

            payload = dict(frame)
            payload["fps"] = fps
            payload["source"] = self.source_label
            payload["device"] = self._device_info

            active_ids = set()
            if payload.get("state") == "active":
                for tr in payload.get("tracks", []):
                    tid = str(tr["id"])
                    active_ids.add(tid)
                    self._last_seen[tid] = now
                    xyz = tr.get("xyz_m")
                    if isinstance(xyz, list) and len(xyz) == 3:
                        trail = self._trails.setdefault(tid, deque(maxlen=MAX_TRAIL_POINTS))
                        trail.append({
                            "seq": payload.get("seq"),
                            "xyz_m": xyz,
                            "fall_state": tr.get("fall_state", "UNKNOWN"),
                        })
                    kin = self._kinematics.setdefault(tid, deque(maxlen=MAX_KIN_SAMPLES))
                    kin.append({
                        "t_ms": now_wall,
                        "h": tr.get("height_m", 0.0),
                        "drop": tr.get("drop_m", 0.0),
                        "v": tr.get("vel_mps", 0.0),
                        "a": tr.get("acc_mps2", 0.0),
                        "state": tr.get("fall_state", "UNKNOWN"),
                    })
                    prev_st = self._prev_states.get(tid)
                    cur_st = tr.get("fall_state", "UNKNOWN")
                    if prev_st is None:
                        self._events.appendleft({
                            "wall_ms": now_wall,
                            "kind": "lock",
                            "text": "锁定目标 ID #{} (距离 {:.2f}m, 高度 {:.2f}m)".format(
                                tid, tr.get("range_m", 0.0), tr.get("height_m", 0.0)
                            ),
                        })
                    elif prev_st != cur_st:
                        kind = "fall" if cur_st == "FALL_SUSPECTED" else ("warn" if cur_st == "FALLING" else "info")
                        self._events.appendleft({
                            "wall_ms": now_wall,
                            "kind": kind,
                            "text": "ID #{} 状态 {} -> {} (原因: {}, H={:.2f}m, 落差={:.2f}m)".format(
                                tid, prev_st, cur_st, tr.get("fall_reason", "NONE"),
                                tr.get("height_m", 0.0), tr.get("drop_m", 0.0),
                            ),
                        })
                    self._prev_states[tid] = cur_st

            for gone in list(self._prev_states.keys()):
                if gone not in active_ids:
                    self._prev_states.pop(gone, None)

            payload["history_ids"] = list(self._last_seen)
            payload["history_epoch"] = self._history_epoch
            payload["events_head"] = list(self._events)[:8]
            self._latest = payload
            self._broadcast_locked(None, payload)

    def _snapshot_locked(self):
        self._prune_history_locked(monotonic())
        return {
            "source": self.source_label,
            "input_status": self._input_status,
            "device": self._device_info,
            "latest": self._latest,
            "history_epoch": self._history_epoch,
            "trails": {tid: list(pts) for tid, pts in self._trails.items()},
            "kinematics": {tid: list(pts) for tid, pts in self._kinematics.items()},
            "events": list(self._events),
        }

    def snapshot(self):
        with self._lock:
            return self._snapshot_locked()

    def subscribe(self):
        q = Queue(maxsize=32)
        with self._lock:
            self._subscribers.add(q)
            return q, self._snapshot_locked()

    def unsubscribe(self, q):
        with self._lock:
            self._subscribers.discard(q)


def make_handler(hub):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            return

        def _send_bytes(self, status, content_type, body):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path == "/api/clear":
                hub.clear_history()
                self._send_bytes(HTTPStatus.OK, "application/json; charset=utf-8", b'{"ok":true}\n')
                return
            self._send_bytes(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", b'{"error":"not_found"}\n')

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                body = HTML_PATH.read_bytes()
                self._send_bytes(HTTPStatus.OK, "text/html; charset=utf-8", body)
                return
            if path == "/api/snapshot":
                body = (json.dumps(hub.snapshot(), ensure_ascii=False) + "\n").encode("utf-8")
                self._send_bytes(HTTPStatus.OK, "application/json; charset=utf-8", body)
                return
            if path == "/events":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()
                q, initial = hub.subscribe()
                try:
                    init_payload = json.dumps(initial, separators=(",", ":"), ensure_ascii=False)
                    self.wfile.write("event: init\ndata: {}\n\n".format(init_payload).encode("utf-8"))
                    self.wfile.flush()
                    while True:
                        try:
                            msg = q.get(timeout=5.0)
                            self.wfile.write(msg.encode("utf-8"))
                        except Empty:
                            self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    hub.unsubscribe(q)
                return
            self._send_bytes(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"Not Found\n")

    return Handler


def _receive_serial_lines(link, messages, stopped):
    pending = bytearray()
    while not stopped.is_set():
        line = link.readline()
        if not line:
            continue
        pending.extend(line)
        if not line.endswith(b"\n"):
            continue
        if pending.lstrip().startswith(b"{"):
            try:
                messages.put(json.loads(pending.decode("utf-8", errors="replace")))
            except json.JSONDecodeError:
                pass
        pending.clear()


def _wait_reply(messages, expected_type, timeout_s):
    deadline = monotonic() + timeout_s
    while monotonic() < deadline:
        try:
            row = messages.get(timeout=min(0.25, max(0.01, deadline - monotonic())))
        except Empty:
            continue
        if row.get("type") == "error":
            raise RuntimeError("ESP32-S3 error: {}".format(row))
        if row.get("type") == expected_type:
            return row
    raise TimeoutError("Timed out waiting for '{}' from ESP32-S3".format(expected_type))


def _device_identity(device_path):
    st = device_path.stat()
    return (st.st_dev, st.st_ino, st.st_ctime_ns)


def stream_serial_connection(device_path, calibration_bytes, spi_mhz, hub, stop):
    import serial  # noqa: E402

    orig_id = _device_identity(device_path)
    link = serial.Serial(baudrate=2_000_000, timeout=0.25, write_timeout=8, exclusive=True)
    link.port = str(device_path)
    link.dtr = False
    link.rts = False
    link.open()
    messages = Queue()
    stopped = Event()
    reader = Thread(target=_receive_serial_lines, args=(link, messages, stopped), daemon=True)
    try:
        link.reset_input_buffer()
        link.rts = True
        sleep(0.1)
        link.rts = False
        reader.start()

        ready = _wait_reply(messages, "ready", 10.0)
        if ready.get("protocol") != 2:
            raise RuntimeError("Protocol 2 required, got {}".format(ready))

        link.write(HEADER.pack(b"CAL2", 0, len(calibration_bytes), zlib.crc32(calibration_bytes) & 0xFFFFFFFF))
        for off in range(0, len(calibration_bytes), 8192):
            if stop.is_set():
                return
            link.write(calibration_bytes[off : off + 8192])

        cal = _wait_reply(messages, "calibrated", 20.0)
        hub.set_device_info({
            "profile": ready.get("profile", "UNKNOWN"),
            "internal_free": cal.get("internal_free"),
            "psram_free": cal.get("psram_free"),
            "workspace_bytes": cal.get("workspace_bytes"),
            "tracker_bytes": cal.get("tracker_bytes"),
            "mount_pitch_deg": cal.get("mount_pitch_deg", 26.0),
            "spi_mhz": spi_mhz,
        })
        link.write(RUN.pack(b"UDP2", spi_mhz * 1_000_000))

        assembler = HumanFrameAssembler()
        streaming = False
        deadline = monotonic() + FIRST_FRAME_TIMEOUT
        while not stop.is_set():
            if _device_identity(device_path) != orig_id:
                raise ConnectionError("Serial device replaced")
            rem = deadline - monotonic()
            if rem <= 0:
                raise TimeoutError("ESP32-S3 stopped producing frames")
            try:
                row = messages.get(timeout=min(rem, 0.25))
            except Empty:
                continue
            if row.get("type") in ("ready", "error", "ethernet_done", "summary"):
                raise ConnectionError("ESP32-S3 stream ended ({})".format(row.get("type")))
            row["host_wall_ms"] = round(wall_time() * 1000.0, 3)
            row["host_mono_ms"] = round(monotonic() * 1000.0, 3)
            for frame in assembler.push_message(row):
                if frame["locked"] != len(frame["tracks"]):
                    continue
                if not streaming:
                    hub.input_status("streaming", "ESP32-S3 已连接并开始实时推流 (W5500 {} MHz)".format(spi_mhz))
                    streaming = True
                hub.publish(frame)
                deadline = monotonic() + FRAME_TIMEOUT
    finally:
        stopped.set()
        reader.join(timeout=2.0)
        link.close()


def follow_serial_device(device_path, calibration_bytes, spi_mhz, hub, stop):
    hub.reset_input("waiting", "等待 ESP32-S3 串口设备就绪...")
    while not stop.is_set():
        if device_path.exists():
            try:
                stream_serial_connection(device_path, calibration_bytes, spi_mhz, hub, stop)
            except Exception as exc:
                print("ESP32-S3 link error: {}".format(exc), flush=True)
                hub.reset_input("closed", "ESP32-S3 连接断开: {}".format(exc))
        stop.wait(1.0)


def feed_jsonl_replay(path, hub, fps, loop, stop):
    interval = 1.0 / max(fps, 0.5)
    hub.input_status("streaming", "离线回放模式: {}".format(path.name))
    while not stop.is_set():
        assembler = HumanFrameAssembler()
        profile = "UNKNOWN"
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if stop.is_set():
                    return
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") == "ready":
                    profile = msg.get("profile", "UNKNOWN")
                    hub.set_device_info({"profile": profile})
                    continue
                if msg.get("type") == "calibrated":
                    hub.set_device_info({
                        "profile": msg.get("profile", profile),
                        "internal_free": msg.get("internal_free"),
                        "psram_free": msg.get("psram_free"),
                        "workspace_bytes": msg.get("workspace_bytes"),
                        "tracker_bytes": msg.get("tracker_bytes"),
                        "mount_pitch_deg": msg.get("mount_pitch_deg", 26.0),
                    })
                    continue
                for frame in assembler.push_message(msg):
                    hub.publish(frame)
                    if stop.wait(interval):
                        return
        if not loop:
            hub.reset_input("closed", "离线回放已结束")
            return
        hub.reset_input("streaming", "离线回放重新开始")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=Path, help="ESP32-S3 serial device for live mode")
    parser.add_argument("--calibration", type=Path, help="IFW192S SDK geometry binary for live mode")
    parser.add_argument("--spi-mhz", type=int, default=80, choices=(40, 80))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--http-port", default=8896, type=int)
    parser.add_argument("--replay", type=Path, default=None, help="Replay JSONL instead of live serial")
    parser.add_argument("--replay-fps", type=float, default=10.0)
    args = parser.parse_args()

    label = "回放 · {}".format(args.replay.name) if args.replay else "实时 · ESP32-S3 人体跌倒"
    hub = HumanLiveHub(label)
    stop = Event()

    if args.replay:
        worker = Thread(target=feed_jsonl_replay, args=(args.replay, hub, args.replay_fps, True, stop), daemon=True)
    else:
        if args.port is None or args.calibration is None:
            parser.error("live mode requires --port and --calibration")
        cal_bytes = args.calibration.read_bytes()
        if len(cal_bytes) != CALIBRATION_BYTES:
            raise ValueError("Wrong calibration size: {}".format(len(cal_bytes)))
        worker = Thread(
            target=follow_serial_device,
            args=(args.port, cal_bytes, args.spi_mhz, hub, stop),
            daemon=True,
        )

    with ThreadingHTTPServer((args.host, args.http_port), make_handler(hub)) as server:
        worker.start()
        print("ESP32-S3 Human Fall Web listening on http://{}:{}".format(args.host, args.http_port), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()


if __name__ == "__main__":
    main()
