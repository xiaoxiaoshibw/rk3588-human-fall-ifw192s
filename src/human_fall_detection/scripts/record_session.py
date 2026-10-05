#!/usr/bin/env python3
"""Record the HF point-cloud/IMU/device-status/health topics with rosbag and write manifest.json."""

import argparse
import hashlib
import math
import os
import re
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sensor_health import finite_or_none, save_json

MANIFEST_SCHEMA_VERSION = 1
PACKAGE_VERSION = "0.1.0"
SOURCE_TIME_DOMAIN = "device_stamp_s_unanchored"
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_TOPICS = ("/innolidar_points", "/inno_imu", "/device_status", "/human_fall/health")
SYNC_KEYS = ("cross_stream_same_clock_verified", "host_anchor_verified")
UNITS_KEYS = ("imu_units_verified", "imu_alignment_verified")
CALIBRATION_STATUSES = ("pending", "verified")


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_bool_map(entry, field, keys):
    if not isinstance(entry, dict):
        raise ValueError("manifest missing field: " + field)
    for key in keys:
        if not isinstance(entry.get(key), bool):
            raise ValueError("manifest invalid field: {}.{}".format(field, key))


def check_file_reference(entry, field):
    if not isinstance(entry, dict) or "path" not in entry or "sha256" not in entry:
        raise ValueError("manifest missing field: " + field)
    path = entry.get("path")
    if path is not None and (not isinstance(path, str) or not path):
        raise ValueError("manifest invalid field: {}.path".format(field))
    sha256 = entry.get("sha256")
    if sha256 is not None and (not isinstance(sha256, str) or not HASH_PATTERN.match(sha256)):
        raise ValueError("manifest invalid field: {}.sha256".format(field))


def check_calibration(entry):
    check_file_reference(entry, "calibration")
    if entry.get("status") not in CALIBRATION_STATUSES:
        raise ValueError("manifest invalid field: calibration.status")
    if not isinstance(entry.get("tf_available"), bool):
        raise ValueError("manifest invalid field: calibration.tf_available")


def check_software(software):
    if not isinstance(software, dict):
        raise ValueError("manifest missing field: software")
    for key in ("package", "version"):
        value = software.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError("manifest invalid field: software." + key)
    if software.get("python") is not None and not isinstance(software["python"], str):
        raise ValueError("manifest invalid field: software.python")


def check_finite_or_none(value, field):
    if value is not None and (isinstance(value, bool)
                              or not isinstance(value, (int, float))
                              or not math.isfinite(float(value))):
        raise ValueError("manifest invalid field: " + field)


def check_bag_summary(summary):
    if not isinstance(summary, dict):
        raise ValueError("manifest missing field: bag.summary")
    count = summary.get("message_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("manifest invalid field: bag.summary.message_count")
    topics = summary.get("topics")
    if not isinstance(topics, dict) or not topics:
        raise ValueError("manifest invalid field: bag.summary.topics")
    for name, topic in topics.items():
        if not isinstance(name, str) or not name.startswith("/") or not isinstance(topic, dict):
            raise ValueError("manifest invalid field: bag.summary.topics")
        if not isinstance(topic.get("type"), str) or not topic["type"]:
            raise ValueError("manifest invalid field: bag.summary.topics.{}.type".format(name))
        messages = topic.get("messages")
        if not isinstance(messages, int) or isinstance(messages, bool) or messages < 0:
            raise ValueError("manifest invalid field: bag.summary.topics.{}.messages".format(name))
        check_finite_or_none(topic.get("frequency"),
                             "bag.summary.topics.{}.frequency".format(name))
    for key in ("duration_s", "start_time_s", "end_time_s"):
        check_finite_or_none(summary.get(key), "bag.summary." + key)


def check_bag(bag):
    if not isinstance(bag, dict):
        raise ValueError("manifest missing field: bag")
    for key in ("path", "size_bytes", "readable"):
        if key not in bag:
            raise ValueError("manifest missing field: bag." + key)
    if not isinstance(bag.get("path"), str) or not bag["path"]:
        raise ValueError("manifest missing field: bag.path")
    size = bag.get("size_bytes")
    if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size < 0):
        raise ValueError("manifest invalid field: bag.size_bytes")
    if not isinstance(bag.get("readable"), bool):
        raise ValueError("manifest missing field: bag.readable")
    sha256 = bag.get("sha256")
    if sha256 is not None and (not isinstance(sha256, str) or not HASH_PATTERN.match(sha256)):
        raise ValueError("manifest invalid field: bag.sha256")
    if bag["readable"]:
        if not isinstance(sha256, str) or not HASH_PATTERN.match(sha256):
            raise ValueError("manifest missing field: bag.sha256")
        if bag.get("summary") is None:
            raise ValueError("manifest missing field: bag.summary")


def build_manifest(session_id, created_at_utc, requested_topics, termination,
                   duration_requested_s, bag, software, config=None, calibration=None,
                   sync=None, units=None, labels=None):
    if not SESSION_ID_PATTERN.match(str(session_id or "")):
        raise ValueError("invalid session_id")
    if not isinstance(created_at_utc, str) or not created_at_utc:
        raise ValueError("manifest missing field: created_at_utc")
    if termination not in ("duration", "sigint"):
        raise ValueError("invalid termination: " + repr(termination))
    if duration_requested_s is not None:
        if (isinstance(duration_requested_s, bool)
                or not isinstance(duration_requested_s, (int, float))
                or not math.isfinite(float(duration_requested_s))
                or float(duration_requested_s) <= 0):
            raise ValueError("duration_requested_s must be a positive finite number or null")
    if termination == "duration" and duration_requested_s is None:
        raise ValueError("duration termination needs a positive finite duration")
    topics = list(requested_topics or [])
    if not topics or not all(isinstance(name, str) and name.startswith("/") for name in topics):
        raise ValueError("manifest missing field: requested_topics")
    check_software(software)
    if sync is None:
        sync = {"cross_stream_same_clock_verified": False, "host_anchor_verified": False}
    check_bool_map(sync, "sync", SYNC_KEYS)
    if units is None:
        units = {"imu_units_verified": False, "imu_alignment_verified": False}
    check_bool_map(units, "units", UNITS_KEYS)
    if calibration is None:
        calibration = {"tf_available": False, "status": "pending", "path": None, "sha256": None}
    check_calibration(calibration)
    if config is None:
        config = {"path": None, "sha256": None}
    check_file_reference(config, "config")
    if labels is None:
        labels = {"path": None, "sha256": None}
    check_file_reference(labels, "labels")
    check_bag(bag)
    if bag["readable"]:
        check_bag_summary(bag["summary"])

    summary = bag.get("summary") or {}
    recorded_topics = []
    for name, topic in sorted((summary.get("topics") or {}).items()):
        recorded_topics.append({"name": name, "type": topic.get("type"),
                                "messages": int(topic.get("messages", 0))})
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "session_id": session_id,
        "created_at_utc": created_at_utc,
        "host": socket.gethostname(),
        "requested_topics": topics,
        "topics": recorded_topics,
        "termination": termination,
        "duration_requested_s": finite_or_none(duration_requested_s),
        "source_time_domain": SOURCE_TIME_DOMAIN,
        "sync": sync,
        "units": units,
        "calibration": calibration,
        "labels": labels,
        "software": dict(software),
        "config": config,
        "bag": {"path": bag["path"],
                "size_bytes": None if bag["size_bytes"] is None else int(bag["size_bytes"]),
                "readable": bag["readable"],
                "sha256": bag.get("sha256"),
                "summary": summary or None},
    }


def read_bag_summary(bag_path):
    """Re-read the finished bag with the ROS1 rosbag module (no format rewriting)."""
    try:
        import rosbag
    except ImportError as exc:
        raise RuntimeError("rosbag python module unavailable: " + str(exc))
    with rosbag.Bag(bag_path) as bag:
        info = bag.get_type_and_topic_info()
        topics = {}
        for name, topic in info.topics.items():
            topics[name] = {"type": topic.msg_type,
                            "messages": int(topic.message_count),
                            "frequency": finite_or_none(topic.frequency)}
        return {"message_count": int(sum(item["messages"] for item in topics.values())),
                "duration_s": finite_or_none(bag.get_end_time() - bag.get_start_time()),
                "start_time_s": finite_or_none(bag.get_start_time()),
                "end_time_s": finite_or_none(bag.get_end_time()),
                "topics": topics}


def run_record(bag_path, topics, duration_s):
    command = ["rosbag", "record", "-O", bag_path]
    if duration_s is not None:
        command.append("--duration={}".format(duration_s))
    command.extend(topics)
    print("recording command: " + " ".join(command), flush=True)
    process = subprocess.Popen(command)
    interrupted = False
    try:
        returncode = process.wait()
    except KeyboardInterrupt:
        interrupted = True
        try:
            process.send_signal(signal.SIGINT)
        except ProcessLookupError:
            pass
        returncode = process.wait()
    return returncode, interrupted


def reserve_session(output_dir, session_id):
    """Reject existing session artifacts and claim the session with an exclusive lock file.

    The O_CREAT|O_EXCL lock is the only synchronisation primitive: two concurrent
    recorders of the same session cannot both pass this point. The lock is kept as
    evidence of the claim; re-using a session needs manual cleanup of the old data.
    """
    for suffix in (".bag", ".bag.active", ".manifest.json"):
        existing = os.path.join(output_dir, session_id + suffix)
        if os.path.exists(existing):
            raise FileExistsError("session output already exists: " + existing)
    lock_path = os.path.join(output_dir, session_id + ".reserve")
    os.close(os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    return lock_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", default=None,
                        help="output name, letters/digits/_/./- only (default session_<timestamp>)")
    parser.add_argument("--duration", type=float, default=None,
                        help="recording length in seconds (default from config or 10)")
    parser.add_argument("--until-interrupt", action="store_true",
                        help="record until Ctrl-C instead of a fixed duration")
    parser.add_argument("--output-dir", default=None,
                        help="bag/manifest directory (default from config or ./human_fall_sessions)")
    parser.add_argument("--config", default=None, help="YAML config with recording defaults")
    parser.add_argument("--calibration", default=None,
                        help="calibration file to reference (status stays pending until HF-03)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    recording = {}
    if args.config:
        try:
            import yaml
            with open(args.config, encoding="utf-8") as source:
                recording = (yaml.safe_load(source) or {}).get("recording", {})
        except (ImportError, OSError, ValueError) as exc:
            raise SystemExit("Cannot load config {}: {}".format(args.config, exc))
    if args.until_interrupt:
        duration = None
    else:
        duration = args.duration if args.duration is not None else float(recording.get("duration_s", 10.0))
        if not (math.isfinite(duration) and duration > 0):
            raise SystemExit("--duration must be a positive finite number")
    topics = list(recording.get("topics", DEFAULT_TOPICS))
    output_dir = args.output_dir or recording.get("output_dir", "human_fall_sessions")
    session_id = args.session_id or "session_" + time.strftime("%Y%m%d_%H%M%S")
    if not SESSION_ID_PATTERN.match(session_id):
        raise SystemExit("invalid session id: " + session_id)
    os.makedirs(output_dir, exist_ok=True)
    bag_path = os.path.abspath(os.path.join(output_dir, session_id + ".bag"))
    manifest_path = os.path.abspath(os.path.join(output_dir, session_id + ".manifest.json"))
    try:
        reserve_session(output_dir, session_id)
    except FileExistsError as exc:
        raise SystemExit("refusing to touch an existing session: {}".format(exc))

    returncode, interrupted = run_record(bag_path, topics, duration)
    bag_exists = os.path.exists(bag_path)
    summary = None
    readable = False
    if bag_exists:
        try:
            summary = read_bag_summary(bag_path)
            readable = True
        except Exception as exc:
            print("bag re-read failed: {}: {}".format(type(exc).__name__, exc))
    else:
        print("bag file missing: " + bag_path)
    calibration = {"path": os.path.abspath(args.calibration) if args.calibration else None,
                   "sha256": file_sha256(args.calibration) if args.calibration else None,
                   "status": "pending", "tf_available": False}
    software = {"package": "human_fall_detection", "version": PACKAGE_VERSION,
                "python": sys.version.split()[0]}
    config_record = {"path": os.path.abspath(args.config) if args.config else None,
                     "sha256": file_sha256(args.config) if args.config else None}
    bag = {"path": bag_path,
           "size_bytes": os.path.getsize(bag_path) if bag_exists else None,
           "readable": readable, "sha256": file_sha256(bag_path) if bag_exists else None,
           "summary": summary}
    termination = "sigint" if (interrupted or duration is None) else "duration"
    manifest = build_manifest(session_id, datetime.now(timezone.utc).isoformat(), topics,
                              termination, duration, bag,
                              software, config=config_record, calibration=calibration)
    save_json(manifest_path, manifest)
    print("wrote " + manifest_path)
    if readable:
        print("bag re-read ok: {} messages, duration {} s".format(
            summary["message_count"], summary["duration_s"]))
        for name in sorted(summary["topics"]):
            print("  {} {} messages".format(name, summary["topics"][name]["messages"]))
    if interrupted:
        return 130
    if not readable:
        return 3
    if returncode in (0, None):
        return 0
    return 128 - returncode if returncode < 0 else returncode


if __name__ == "__main__":
    raise SystemExit(main())
