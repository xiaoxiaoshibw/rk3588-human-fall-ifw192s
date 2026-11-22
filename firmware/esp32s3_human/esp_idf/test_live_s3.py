"""Live Protocol 2 hardware benchmark for ESP32-S3 human tracking on RK3588.

Python 3.8 compatible. Requires pyserial and an explicit serial port and
IFW192S calibration file.
"""

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
from time import monotonic, sleep, time as wall_time

VENDOR_DIR = Path.home() / ".local/opt/lidar-bird-s3/runtime/vendor"
if VENDOR_DIR.is_dir() and str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

import serial  # noqa: E402

HEADER = struct.Struct("<4sIII")
RUN = struct.Struct("<4sI")
CALIBRATION_BYTES = 16 + 49152 * 16


def receive_lines(link, raw_stream, messages, stopped):
    pending = bytearray()
    while not stopped.is_set():
        line = link.readline()
        if not line:
            continue
        raw_stream.write(line)
        raw_stream.flush()
        pending.extend(line)
        if not line.endswith(b"\n"):
            continue
        if pending.lstrip().startswith(b"{"):
            try:
                messages.put(json.loads(pending.decode("utf-8", errors="replace")))
            except json.JSONDecodeError:
                messages.put({"type": "parse_error", "raw": pending.decode("utf-8", errors="replace").strip()})
        pending.clear()


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    idx = (len(ordered) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (idx - lo)


def summarize_ms(us_values):
    if not us_values:
        return None
    ms = [v / 1000.0 for v in us_values]
    return {
        "n": len(ms),
        "min_ms": round(min(ms), 3),
        "p50_ms": round(percentile(ms, 0.50), 3),
        "p95_ms": round(percentile(ms, 0.95), 3),
        "max_ms": round(max(ms), 3),
        "mean_ms": round(sum(ms) / len(ms), 3),
        "over_100ms": sum(v > 100.0 for v in ms),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--spi-mhz", type=int, default=80, choices=(40, 80))
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    cal_bytes = args.calibration.read_bytes()
    if len(cal_bytes) != CALIBRATION_BYTES:
        raise ValueError("Unexpected calibration size: {}".format(len(cal_bytes)))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = args.out_dir / "live_stream.jsonl"
    uart_path = args.out_dir / "live_uart.log"
    summary_path = args.out_dir / "LIVE_SUMMARY.json"

    messages = Queue()
    stopped = Event()
    frames = []
    tracks = []
    errors = []
    ready_msg = None
    cal_msg = None

    with uart_path.open("wb") as raw_stream, jsonl_path.open("w", encoding="utf-8") as jout:
        link = serial.Serial(baudrate=2_000_000, timeout=0.25, write_timeout=8, exclusive=True)
        link.port = args.port
        link.dtr = False
        link.rts = False
        link.open()
        link.reset_input_buffer()
        # Pulse EN (RTS) to reset ESP32-S3 cleanly
        link.rts = True
        sleep(0.1)
        link.rts = False

        reader = Thread(target=receive_lines, args=(link, raw_stream, messages, stopped), daemon=True)
        reader.start()

        def next_msg(timeout):
            return messages.get(timeout=timeout)

        def record(msg):
            msg_out = dict(msg)
            msg_out["host_wall_ms"] = round(wall_time() * 1000.0, 3)
            msg_out["host_mono_ms"] = round(monotonic() * 1000.0, 3)
            jout.write(json.dumps(msg_out, ensure_ascii=False) + "\n")
            jout.flush()
            return msg_out

        try:
            # 1. Wait for ready
            deadline = monotonic() + 10.0
            while monotonic() < deadline:
                try:
                    m = next_msg(max(0.05, deadline - monotonic()))
                except Empty:
                    continue
                record(m)
                if m.get("type") == "error":
                    raise RuntimeError("S3 error before ready: {}".format(m))
                if m.get("type") == "ready":
                    ready_msg = m
                    break
            if not ready_msg:
                raise TimeoutError("Timed out waiting for ready from ESP32-S3")

            # 2. Send calibration
            link.write(HEADER.pack(b"CAL2", 0, len(cal_bytes), zlib.crc32(cal_bytes) & 0xFFFFFFFF))
            for off in range(0, len(cal_bytes), 8192):
                link.write(cal_bytes[off : off + 8192])

            deadline = monotonic() + 20.0
            while monotonic() < deadline:
                try:
                    m = next_msg(max(0.05, deadline - monotonic()))
                except Empty:
                    continue
                record(m)
                if m.get("type") == "error":
                    raise RuntimeError("S3 error during calibration: {}".format(m))
                if m.get("type") == "calibrated":
                    cal_msg = m
                    break
            if not cal_msg:
                raise TimeoutError("Timed out waiting for calibrated from ESP32-S3")

            # 3. Start UDP2 live stream
            link.write(RUN.pack(b"UDP2", args.spi_mhz * 1_000_000))
            stream_start = monotonic()
            stream_end = stream_start + args.seconds

            while monotonic() < stream_end:
                try:
                    m = next_msg(min(0.25, max(0.01, stream_end - monotonic())))
                except Empty:
                    continue
                m_rec = record(m)
                mtype = m.get("type")
                if mtype == "frame":
                    frames.append(m_rec)
                elif mtype == "track":
                    tracks.append(m_rec)
                elif mtype in ("error", "parse_error"):
                    errors.append(m_rec)
                    if mtype == "error":
                        break
        finally:
            stopped.set()
            reader.join(timeout=2.0)
            link.close()

    active = [f for f in frames if f.get("state") == "active"]
    unknown = [f for f in frames if f.get("state") == "UNKNOWN"]
    seq_gaps = 0
    for a, b in zip(active, active[1:]):
        if (b["seq"] - a["seq"]) != 768:
            seq_gaps += 1

    duration_s = 0.0
    if len(active) >= 2:
        duration_s = (active[-1]["host_mono_ms"] - active[0]["host_mono_ms"]) / 1000.0

    track_ids = sorted({t["id"] for t in tracks})
    fall_frames = sum(1 for f in active if f.get("fall_suspected", 0) > 0)
    fall_tracks = [t for t in tracks if t.get("fall_state") == "FALL_SUSPECTED"]

    summary = {
        "ready": ready_msg,
        "calibrated": cal_msg,
        "spi_mhz": args.spi_mhz,
        "requested_seconds": args.seconds,
        "measured_span_s": round(duration_s, 3),
        "total_frames": len(frames),
        "active_frames": len(active),
        "unknown_frames": len(unknown),
        "seq_gaps_in_active": seq_gaps,
        "fps": round((len(active) - 1) / duration_s, 2) if duration_s > 0 else 0.0,
        "errors": errors,
        "timings": {
            "materialize_ms": summarize_ms([f["grid_ready_us"] - f["tail_read_us"] for f in active]),
            "tracker_step_ms": summarize_ms([f["result_ready_us"] - f["tracker_start_us"] for f in active]),
            "tail_to_result_ms": summarize_ms([f["result_ready_us"] - f["tail_read_us"] for f in active]),
        },
        "locked_frames": sum(1 for f in active if f.get("locked", 0) > 0),
        "unique_locked_ids": track_ids,
        "track_records": len(tracks),
        "fall_suspected_frames": fall_frames,
        "fall_suspected_track_records": len(fall_tracks),
        "valid_cells_mean": round(sum(f.get("valid_cells", 0) for f in active) / len(active), 1) if active else 0.0,
        "fg_seeds_mean": round(sum(f.get("fg_seeds", 0) for f in active) / len(active), 1) if active else 0.0,
        "sample_tracks": tracks[:5],
    }

    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
