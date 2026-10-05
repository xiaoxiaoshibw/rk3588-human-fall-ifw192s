#!/usr/bin/env python3
"""Finite, read-only profiling of the HF-07 node on live ROS.

The node publishes an optional ``performance`` block inside its state JSON
(``output.performance: true``) with node-side monotonic receive/start/finish
timestamps, ``frame_count`` and ``LatestFrameQueue.dropped``. This observer
reads those node-reported numbers, so processing latency is the node's own
decode+compute time, not a difference between two independent subscriptions.

Measured: real input message rate; effective processed rate and per-category
counts from *deduplicated* frames keyed by (session_id, time_epoch, source
seq/sec/nsec); node-reported processing / queue / receive->finish percentiles;
node-reported queue drops; node CPU/RSS/temperature (null when absent).

Not measured: device-source, network, browser, or end-to-end latency. An
observer arrival->state gap is reported separately and clearly named as such.

Bounded duration, stats only -- no raw bag is ever recorded.
"""

import argparse
import json
import os
import sys
import time
from collections import deque

SCHEMA_VERSION = 1
KIND = "pipeline_profile"
NODE_STATE_KIND = "target_state"
PERF_KIND = "performance"
MAX_SAMPLES = 200000
MAX_PENDING = 20000


def _percentile(sorted_values, fraction):
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = fraction * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _is_int(value):
    """Strict integer: JSON booleans are ints in Python, so reject them here."""
    return type(value) is int


def _finite_positive(value, name):
    if isinstance(value, bool):
        raise ValueError("{} must be a finite positive number, got {!r}".format(name, value))
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("{} must be a finite positive number, got {!r}".format(name, value))
    if number != number or number in (float("inf"), float("-inf")) or number <= 0:
        raise ValueError("{} must be a finite positive number, got {!r}".format(name, value))
    return number


def _read_proc_cpu(pid):
    try:
        with open("/proc/{}/stat".format(pid), encoding="utf-8") as handle:
            fields = handle.read().split()
        ticks = os.sysconf("SC_CLK_TCK")
        return (int(fields[13]) + int(fields[14])) / float(ticks)
    except (OSError, ValueError, IndexError):
        return None


def _read_rss_bytes(pid):
    try:
        with open("/proc/{}/status".format(pid), encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return None


def _read_max_temp_c():
    try:
        zones = [name for name in os.listdir("/sys/class/thermal")
                 if name.startswith("thermal_zone")]
    except OSError:
        return None
    hottest = None
    for zone in zones:
        try:
            with open("/sys/class/thermal/{}/temp".format(zone), encoding="utf-8") as handle:
                value = float(handle.read().strip())
        except (OSError, ValueError):
            continue
        celsius = value / 1000.0 if value > 1000 else value
        hottest = celsius if hottest is None else max(hottest, celsius)
    return hottest


def _write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def parse_state(data):
    """Return a validated state dict, or None for bad JSON / unknown schema."""
    try:
        payload = json.loads(data)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("kind") != NODE_STATE_KIND:
        return None
    if not _is_int(payload.get("schema_version")) \
            or payload["schema_version"] != SCHEMA_VERSION:
        return None
    return payload


def frame_key(payload):
    """(session_id, time_epoch, seq, secs, nsecs), or None for a non-frame state.

    Strict integer header/epoch; malformed metadata returns ``None`` instead of
    raising (a garbage seq must not abort the observer).
    """
    if not isinstance(payload, dict):
        return None
    source = payload.get("source")
    if not isinstance(source, dict):
        return None
    seq = source.get("seq")
    secs = source.get("stamp_secs")
    nsecs = source.get("stamp_nsecs")
    session_id = payload.get("session_id")
    epoch = payload.get("time_epoch")
    if not (_is_int(seq) and _is_int(secs) and _is_int(nsecs)
            and _is_int(epoch) and isinstance(session_id, str)):
        return None
    if seq < 0 or secs < 0 or not (0 <= nsecs < 1000000000):
        return None
    return (session_id, epoch, seq, secs, nsecs)


def _latency_stats(samples, mark, window_start):
    """Overall and windowed (t >= window_start) percentiles from bounded samples.

    ``samples`` is a bounded deque also appended to by a rospy callback thread;
    snapshot it first so a concurrent append/trim cannot raise "deque mutated
    during iteration".
    """
    items = list(samples)
    values = sorted(value for _, value in items)
    recent = sorted(value for when, value in items if when >= window_start)
    return {
        "p50": None if not values else _percentile(values, 0.5),
        "p95": None if not values else _percentile(values, 0.95),
        "window_p50": None if not recent else _percentile(recent, 0.5),
        "window_p95": None if not recent else _percentile(recent, 0.95),
        "count": len(values),
    }


def _ms(value):
    """Convert a seconds latency to milliseconds, or None for a bad value.

    Rejects booleans, non-numbers, NaN/Inf and negative values, so a malformed
    ``performance`` timing is never counted as a latency sample.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")) or number < 0:
        return None
    return number * 1000.0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=1800.0,
                        help="bounded capture seconds (default 1800 = 30 min)")
    parser.add_argument("--cloud-topic", default="/innolidar_points")
    parser.add_argument("--state-topic", default="/human_fall/state")
    parser.add_argument("--note-pid", type=int, default=0,
                        help="PID of the production node to sample (0 = none)")
    parser.add_argument("--window", type=float, default=10.0)
    parser.add_argument("--label", default="live")
    parser.add_argument("--mode", default=None)
    parser.add_argument("--output", required=True, help="windowed JSONL path")
    parser.add_argument("--summary", required=True, help="summary JSON path")
    args = parser.parse_args(argv)

    try:
        args.duration = _finite_positive(args.duration, "--duration")
        args.window = _finite_positive(args.window, "--window")
    except ValueError as exc:
        parser.exit(2, "{}\n".format(exc))

    try:
        import rospy
        from sensor_msgs.msg import PointCloud2
        from std_msgs.msg import String
    except ImportError as exc:
        parser.exit(2, "rospy/sensor_msgs/std_msgs required: {}\n".format(exc))

    now0 = time.monotonic()

    class Store(object):
        pass

    st = Store()
    st.input_messages = 0
    st.state_messages = 0
    st.processed_frames = 0
    st.bad_json = 0
    st.bad_schema = 0
    st.duplicate_outputs = 0
    st.no_performance = 0
    st.input_valid_frames = 0
    st.input_invalid_frames = 0
    st.ground_valid_frames = 0
    st.ground_unavailable_frames = 0
    st.fall_unknown_frames = 0
    st.fall_non_unknown_frames = 0
    st.suppressed_frames = 0
    st.matched_observations = 0
    st.queue_dropped = None
    st.queue_dropped_baseline = None
    st.frame_count = None
    st.first_input_s = None
    st.last_input_s = None
    st.first_state_s = None
    st.last_state_s = None
    st.process = deque(maxlen=MAX_SAMPLES)
    st.receive_to_finish = deque(maxlen=MAX_SAMPLES)
    st.queue_age = deque(maxlen=MAX_SAMPLES)
    st.observer_gap = deque(maxlen=MAX_SAMPLES)
    st.seen_keys = set()
    st.pending_inputs = {}
    st.started_s = now0
    st.window_start = now0
    st.cpu0 = _read_proc_cpu(args.note_pid) if args.note_pid > 0 else None
    st.t0 = now0

    def on_cloud(msg):
        now = time.monotonic()
        st.input_messages += 1
        if st.first_input_s is None:
            st.first_input_s = now
        st.last_input_s = now
        seq = getattr(msg.header, "seq", None)
        if seq is None:
            return
        key = (int(seq), int(msg.header.stamp.secs), int(msg.header.stamp.nsecs))
        st.pending_inputs[key] = now
        if len(st.pending_inputs) > MAX_PENDING:
            for stale in sorted(st.pending_inputs)[:MAX_PENDING // 2]:
                st.pending_inputs.pop(stale, None)

    def on_state(msg):
        now = time.monotonic()
        st.state_messages += 1
        payload = parse_state(msg.data)
        if payload is None:
            try:
                json.loads(msg.data)
                st.bad_schema += 1
            except (TypeError, ValueError):
                st.bad_json += 1
            return
        if st.first_state_s is None:
            st.first_state_s = now
        st.last_state_s = now
        key = frame_key(payload)
        if key is None:
            return
        if key in st.seen_keys:
            st.duplicate_outputs += 1
            return
        st.seen_keys.add(key)
        performance = payload.get("performance")
        if not isinstance(performance, dict) or performance.get("kind") != PERF_KIND \
                or performance.get("schema_version") != SCHEMA_VERSION:
            st.no_performance += 1
            return
        st.processed_frames += 1
        dropped = performance.get("queue_dropped")
        if _is_int(dropped):
            if st.queue_dropped_baseline is None:
                st.queue_dropped_baseline = dropped
            st.queue_dropped = dropped
        frame_count = performance.get("frame_count")
        if _is_int(frame_count):
            st.frame_count = frame_count
        if performance.get("input_valid"):
            st.input_valid_frames += 1
        else:
            st.input_invalid_frames += 1
        if performance.get("ground_valid"):
            st.ground_valid_frames += 1
        else:
            st.ground_unavailable_frames += 1
        if performance.get("fall_status") in (None, "unknown"):
            st.fall_unknown_frames += 1
        else:
            st.fall_non_unknown_frames += 1
        if performance.get("suppressed"):
            st.suppressed_frames += 1
        process_ms = _ms(performance.get("process_s"))
        if process_ms is not None:
            st.process.append((now, process_ms))
        rtf_ms = _ms(performance.get("receive_to_finish_s"))
        if rtf_ms is not None:
            st.receive_to_finish.append((now, rtf_ms))
        queue_ms = _ms(performance.get("queue_age_s"))
        if queue_ms is not None:
            st.queue_age.append((now, queue_ms))
        source = payload["source"]
        ikey = (int(source["seq"]), int(source["stamp_secs"]), int(source["stamp_nsecs"]))
        arrival = st.pending_inputs.pop(ikey, None)
        if arrival is not None:
            st.matched_observations += 1
            st.observer_gap.append((now, (now - arrival) * 1000.0))

    rospy.init_node("hf09_profile_observer", disable_signals=True)
    rospy.Subscriber(args.cloud_topic, PointCloud2, on_cloud, queue_size=1,
                     buff_size=2 ** 24)
    rospy.Subscriber(args.state_topic, String, on_state, queue_size=32)

    rows_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(rows_path), exist_ok=True)
    rows = open(rows_path, "w", encoding="utf-8")

    def emit(now):
        elapsed = now - st.window_start
        if elapsed <= 0:
            return
        cpu1 = _read_proc_cpu(args.note_pid) if args.note_pid > 0 else None
        cpu_pct = None
        if cpu1 is not None and st.cpu0 is not None and now > st.t0:
            cpu_pct = 100.0 * (cpu1 - st.cpu0) / (now - st.t0)
        process_stats = _latency_stats(st.process, None, st.window_start)
        observer_stats = _latency_stats(st.observer_gap, None, st.window_start)
        row = {
            "schema_version": SCHEMA_VERSION,
            "t_rel_s": round(now - st.started_s, 3),
            "window_s": round(elapsed, 3),
            "input_hz": round((st.input_messages - st.window_input) / elapsed, 3),
            "processed_hz": round((st.processed_frames - st.window_processed) / elapsed, 3),
            "process_p50_ms": None if process_stats["window_p50"] is None
            else round(process_stats["window_p50"], 3),
            "process_p95_ms": None if process_stats["window_p95"] is None
            else round(process_stats["window_p95"], 3),
            "queue_dropped_baseline": st.queue_dropped_baseline,
            "queue_dropped_total": st.queue_dropped,
            "queue_dropped_delta_window": (
                None if st.queue_dropped is None or st.window_queue_dropped is None
                else st.queue_dropped - st.window_queue_dropped),
            "observer_arrival_to_state_p50_ms": None
            if observer_stats["window_p50"] is None
            else round(observer_stats["window_p50"], 3),
            "cpu_pct": None if cpu_pct is None else round(cpu_pct, 3),
            "rss_mb": None if args.note_pid <= 0 or _read_rss_bytes(args.note_pid) is None
            else round(_read_rss_bytes(args.note_pid) / 1048576.0, 3),
            "temp_c": _read_max_temp_c(),
        }
        rows.write(json.dumps(row, sort_keys=True) + "\n")
        rows.flush()
        st.window_input = st.input_messages
        st.window_processed = st.processed_frames
        st.window_queue_dropped = st.queue_dropped
        st.window_start = now
        st.cpu0 = cpu1
        st.t0 = now
    st.window_input = 0
    st.window_processed = 0
    st.window_queue_dropped = None

    rospy.loginfo("hf09 profile observer: %s + %s for %.0fs (node pid=%s) -> %s",
                  args.cloud_topic, args.state_topic, args.duration, args.note_pid,
                  rows_path)
    end_s = time.monotonic() + args.duration
    try:
        while not rospy.is_shutdown() and time.monotonic() < end_s:
            time.sleep(min(args.window, max(0.05, end_s - time.monotonic())))
            emit(time.monotonic())
    finally:
        rows.close()

    process_stats = _latency_stats(st.process, None, st.started_s)
    rtf_stats = _latency_stats(st.receive_to_finish, None, st.started_s)
    queue_stats = _latency_stats(st.queue_age, None, st.started_s)
    observer_stats = _latency_stats(st.observer_gap, None, st.started_s)
    input_span = None
    if st.first_input_s is not None and st.last_input_s is not None:
        input_span = st.last_input_s - st.first_input_s
    state_span = None
    if st.first_state_s is not None and st.last_state_s is not None:
        state_span = st.last_state_s - st.first_state_s
    summary = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "label": args.label,
        "mode": args.mode,
        "status": "OK" if st.processed_frames > 0 else "NO_DATA",
        "input_topic": args.cloud_topic,
        "state_topic": args.state_topic,
        "node_pid": args.note_pid if args.note_pid > 0 else None,
        "duration_s": args.duration,
        "window_s": args.window,
        "capture_elapsed_s": round(time.monotonic() - st.started_s, 3),
        "input_messages": st.input_messages,
        "first_input_rel_s": None if st.first_input_s is None
        else round(st.first_input_s - st.started_s, 3),
        "last_input_rel_s": None if st.last_input_s is None
        else round(st.last_input_s - st.started_s, 3),
        "state_messages": st.state_messages,
        "processed_frames": st.processed_frames,
        "duplicate_outputs": st.duplicate_outputs,
        "bad_json": st.bad_json,
        "bad_schema": st.bad_schema,
        "state_without_performance": st.no_performance,
        "input_valid_frames": st.input_valid_frames,
        "input_invalid_frames": st.input_invalid_frames,
        "ground_valid_frames": st.ground_valid_frames,
        "ground_unavailable_frames": st.ground_unavailable_frames,
        "fall_unknown_frames": st.fall_unknown_frames,
        "fall_non_unknown_frames": st.fall_non_unknown_frames,
        "suppressed_frames": st.suppressed_frames,
        "input_hz": None if not input_span else round(st.input_messages / input_span, 3),
        "processed_hz": None if not state_span
        else round(st.processed_frames / state_span, 3),
        "queue_dropped_baseline": st.queue_dropped_baseline,
        "queue_dropped_total": st.queue_dropped,
        "queue_dropped_delta_total": (
            None if st.queue_dropped is None or st.queue_dropped_baseline is None
            else st.queue_dropped - st.queue_dropped_baseline),
        "frame_count_total": st.frame_count,
        "observer_matched_observations": st.matched_observations,
        "observer_unmatched_inputs": len(st.pending_inputs),
        "process_p50_ms": None if process_stats["p50"] is None
        else round(process_stats["p50"], 3),
        "process_p95_ms": None if process_stats["p95"] is None
        else round(process_stats["p95"], 3),
        "receive_to_finish_p50_ms": None if rtf_stats["p50"] is None
        else round(rtf_stats["p50"], 3),
        "receive_to_finish_p95_ms": None if rtf_stats["p95"] is None
        else round(rtf_stats["p95"], 3),
        "queue_age_p50_ms": None if queue_stats["p50"] is None
        else round(queue_stats["p50"], 3),
        "queue_age_p95_ms": None if queue_stats["p95"] is None
        else round(queue_stats["p95"], 3),
        "observer_arrival_to_state_p50_ms": None if observer_stats["p50"] is None
        else round(observer_stats["p50"], 3),
        "observer_arrival_to_state_p95_ms": None if observer_stats["p95"] is None
        else round(observer_stats["p95"], 3),
        "rss_mb": None if args.note_pid <= 0 or _read_rss_bytes(args.note_pid) is None
        else round(_read_rss_bytes(args.note_pid) / 1048576.0, 3),
        "temp_c": _read_max_temp_c(),
        "note": ("processing latency is the NODE's own monotonic decode+compute "
                 "(state.performance.process_s); observer_arrival_to_state is a "
                 "separate secondary observer subscription gap, not processing "
                 "latency, and excludes network/browser/publish serialisation"),
    }
    _write_json(args.summary, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
