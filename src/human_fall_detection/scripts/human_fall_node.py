#!/usr/bin/env python3
"""ROS1 node for the HF-04..06 geometry/fall chain (HF-07). Read-only output.

Message plumbing only: the point-cloud callback records the real receive clock
and drops the frame into a bounded latest-frame queue, a single worker thread
decodes and runs the pure :class:`core.node_runtime.FallNodeCore`, and requests
are answered through the same locked core. Nothing here publishes vehicle
commands; the only input topic is operator selection/baseline requests.

Runtime contract exercised by this file:

- bounded queue + single writer, so a slow frame computation never blocks the
  sensor callbacks;
- illegal stamps / undecodable clouds keep an explicit invalid/unknown state
  instead of a fabricated normal scene;
- selection requests are validated by the board-side backend (schema/epoch/
  snapshot/quality/version) and only its ack is authoritative;
- fall events are de-duplicated and appended to a local JSONL log; a write
  failure is surfaced, never reported as a successful save.
"""

import argparse
import json
import os
import threading
import time

SCHEMA_VERSION = 1


def performance_block(frame_count, queue_dropped, input_valid, suppressed, receive_s,
                      process_start_s, process_finish_s, process_s,
                      receive_to_finish_s, ground_valid, fall_status):
    """Optional node-side diagnostic block added to the state JSON.

    Pure and additive: the node's own monotonic timestamps and counters only, so
    a separate observer can measure real decode+compute latency and queue drops
    without relying on cross-subscription timing. It never changes the algorithm
    or the frozen health/manifest.
    """
    queue_age_s = None
    if process_start_s is not None and receive_s is not None:
        queue_age_s = process_start_s - receive_s
    return {"kind": "performance", "schema_version": 1, "enabled": True,
            "clock_domain": "monotonic", "frame_count": int(frame_count),
            "queue_dropped": int(queue_dropped), "input_valid": bool(input_valid),
            "suppressed": bool(suppressed), "receive_s": receive_s,
            "process_start_s": process_start_s,
            "process_finish_s": process_finish_s, "process_s": process_s,
            "queue_age_s": queue_age_s, "receive_to_finish_s": receive_to_finish_s,
            "ground_valid": bool(ground_valid), "fall_status": fall_status,
            "mode": "live_monotonic"}


def load_yaml(path):
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("PyYAML is required: " + str(exc))
    with open(path, encoding="utf-8") as source:
        return yaml.safe_load(source) or {}


def _resolve_relative(base_dir, path):
    if path is None:
        return None
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(base_dir, path))


def load_ground_context(config, config_dir):
    """Return (ground, calibration, background) from config paths.

    A configured path that is present but unreadable/invalid raises, so a
    mis-declared calibration never silently degrades to "no ground". No path
    configured is a legitimate waiting state (``ground=None``).
    """
    ground = None
    calibration = None
    background = None
    calibration_path = _resolve_relative(config_dir, config.get("calibration_path"))
    ground_path = _resolve_relative(config_dir, config.get("ground_path"))
    background_path = _resolve_relative(config_dir, config.get("background_path"))
    if calibration_path:
        from core.calibration import validate_geometry_calibration
        with open(calibration_path, encoding="utf-8") as handle:
            artifact = validate_geometry_calibration(json.load(handle))
        calibration = artifact
        ground = artifact.get("ground")
    elif ground_path:
        from core.ground import validate_ground_plane
        with open(ground_path, encoding="utf-8") as handle:
            record = json.load(handle)
        if isinstance(record, dict) and "ground" in record:
            record = record["ground"]
        ground = validate_ground_plane(record) if record is not None else None
    if background_path:
        with open(background_path, encoding="utf-8") as handle:
            background = json.load(handle)
    return ground, calibration, background


def build_core(config, perception, *, session_id, config_dir, event_path):
    from core.node_runtime import FallNodeCore
    topics = config.get("topics", {})
    timeouts = config.get("timeouts_s", {})
    stamps = config.get("stamps", {})
    checks = config.get("checks", {})
    ground, calibration, background = load_ground_context(config.get("geometry", {}),
                                                          config_dir)
    # This live ROS node always samples time.monotonic() in its callbacks and
    # worker; it never drives the core with message/source time. Offline
    # message-time replay lives in scripts/fall_replay.py, so do not fake a
    # message clock here (see the mode.replay guard in main()).
    clock_domain = "monotonic"
    return FallNodeCore(
        session_id, perception, ground=ground, calibration=calibration,
        background=background, event_path=event_path,
        recent_events=int(config.get("output", {}).get("recent_events", 64)),
        expected_frame=checks.get("expected_cloud_frame") or "innolidar",
        cloud_timeout_s=float(timeouts.get("cloud_stale", 0.6)),
        imu_timeout_s=float(timeouts.get("imu_stale", 0.3)),
        device_timeout_s=float(timeouts.get("device_stale", 0.6)),
        max_forward_jump_s=float(stamps.get("max_forward_jump_s", 30.0)),
        clock_domain=clock_domain)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None,
                        help="node YAML; defaults to the package config/human_fall.yaml")
    parser.add_argument("--perception", default=None,
                        help="perception sections YAML; defaults to config/perception.yaml")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--output-dir", default=None)
    # Unknown args are ROS remaps/params (e.g. ``_config:=...``); they must not
    # make a standalone or roslaunch invocation fail argument parsing.
    args, _unknown = parser.parse_known_args(argv)
    try:
        import rospy
        import rospkg
        from sensor_msgs.msg import Imu, PointCloud2
        from std_msgs.msg import String
        from inno_lidar_msg.msg import DeviceStatus
    except ImportError as exc:
        parser.exit(2, "ROS1 rospy/rospkg/sensor_msgs/std_msgs/inno_lidar_msg required: {}\n"
                    .format(exc))

    rospy.init_node("human_fall_node", disable_signals=False)
    package_dir = rospkg.RosPack().get_path("human_fall_detection")
    config_path = (rospy.get_param("~config", None) or args.config
                   or os.path.join(package_dir, "config", "human_fall.yaml"))
    config_dir = os.path.dirname(os.path.abspath(config_path))
    config = load_yaml(config_path)
    perception_path = (rospy.get_param("~perception", None) or args.perception
                       or os.path.join(config_dir, "perception.yaml"))
    perception = load_yaml(perception_path)

    session_id = (args.session_id or rospy.get_param("~session_id", "")
                  or config.get("session_id") or "")
    if not session_id:
        session_id = "hfd_" + time.strftime("%Y%m%d_%H%M%S", time.gmtime())

    output = config.get("output", {})
    output_dir = (args.output_dir or rospy.get_param("~output_dir", "")
                  or output.get("session_dir") or "/root/catkin_ws/human_fall_sessions")
    event_path = os.path.join(output_dir, str(output.get("event_file", "events.jsonl")))

    mode = config.get("mode", {})
    if mode.get("replay"):
        parser.exit(2, "human_fall_node is a live ROS node and always uses the monotonic "
                       "clock; use scripts/fall_replay.py for offline message-time replay\n")
    require_ground = bool(mode.get("require_ground", False))
    core = build_core(config, perception, session_id=session_id,
                      config_dir=config_dir, event_path=event_path)
    if require_ground and not core._ground_valid():
        parser.exit(3, "no valid ground configured and mode.require_ground is true\n")

    from sensor_health import _load_xyz_from_cloud, dumps_strict, stamp_pair
    xyz_from_cloud, calibration_error = _load_xyz_from_cloud()
    if xyz_from_cloud is None:
        parser.exit(2, "human_follow_calibration.xyz_from_cloud is unavailable; "
                       "the required point-cloud decoder could not be loaded\n")

    topics = config.get("topics", {})
    cloud_topic = topics.get("cloud", "/innolidar_points")
    imu_topic = topics.get("imu", "/inno_imu")
    device_topic = topics.get("device_status", "/device_status")
    publish_period = float(config.get("publish_period_s", 0.5))
    cloud_stale_s = float(config.get("timeouts_s", {}).get("cloud_stale", 0.6))
    # Optional, off-by-default diagnostic extension of the state JSON. It adds
    # only node-side monotonic counters/timestamps (no algorithm change, no
    # frozen health/manifest change), so an observer can measure real processing
    # latency instead of inferring it from independent subscriptions.
    performance_enabled = bool(output.get("performance", False)
                               or rospy.get_param("~performance", False))
    perf_holder = {"last": {"kind": "performance", "schema_version": 1,
                            "enabled": True, "clock_domain": "monotonic",
                            "frame_count": 0, "queue_dropped": 0,
                            "input_valid": False, "suppressed": False,
                            "receive_s": None, "process_start_s": None,
                            "process_finish_s": None, "process_s": None,
                            "queue_age_s": None, "receive_to_finish_s": None,
                            "ground_valid": False, "fall_status": None,
                            "mode": "live_monotonic"}}

    publishers = {
        "candidates": rospy.Publisher(topics.get("candidates", "/human_fall/candidates"),
                                      String, queue_size=1),
        "state": rospy.Publisher(topics.get("state", "/human_fall/state"),
                                 String, queue_size=1),
        "event": rospy.Publisher(topics.get("event", "/human_fall/event"),
                                 String, queue_size=4),
        "ack": rospy.Publisher(topics.get("selection_ack", "/human_fall/selection_ack"),
                               String, queue_size=4),
    }

    from core.node_runtime import (LatestFrameQueue, frame_age_exceeded,
                                   project_snapshot_for_ros, sample_point_data)
    queue = LatestFrameQueue(1)

    # Read-only visualization stream: the algorithm keeps using the full cloud;
    # only the browser-facing display topic is stride-sampled and never touches
    # the source message. Disabled unless configured.
    vis_cfg = config.get("visualization", {})
    display_topic = topics.get("display_points") if vis_cfg.get("enabled") else None
    vis_stride = int(vis_cfg.get("stride", 4))
    vis_max = int(vis_cfg.get("max_points", 12000))
    display_pub = rospy.Publisher(display_topic, PointCloud2, queue_size=1) \
        if display_topic else None
    viz_holder = {"last": None}
    stop = threading.Event()

    def on_cloud(msg):
        queue.put((time.monotonic(), msg))

    def on_imu(msg):
        from core.sensor_quality import six_axis_report
        report = six_axis_report(
            (msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z),
            (msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z))
        try:
            core.note_imu(time.monotonic(), stamp_pair(msg.header.stamp),
                          msg.header.frame_id, report["finite"])
        except Exception as exc:  # noqa: BLE001 - auxiliary stream never fatal
            rospy.logwarn_throttle(10.0, "human_fall_node IMU note failed: %s", exc)

    def on_device(msg):
        try:
            core.note_device(time.monotonic(), stamp_pair(msg.header.stamp),
                             msg.header.frame_id)
        except Exception as exc:  # noqa: BLE001
            rospy.logwarn_throttle(10.0, "human_fall_node device note failed: %s", exc)

    def on_request(msg):
        try:
            request = json.loads(msg.data)
        except (TypeError, ValueError):
            request = None
        # Now is sampled inside handle_request *after* it acquires the core lock,
        # so a request that waited behind a long frame computation is gated with
        # the actual handling time (``time.monotonic``) rather than arrival time.
        ack = core.handle_request(request, None, now_fn=time.monotonic)
        _publish(publishers["ack"], ack)

    def _publish(publisher, payload):
        try:
            publisher.publish(String(data=dumps_strict(payload)))
        except ValueError as exc:
            rospy.logerr("Refusing non-finite payload on %s: %s", publisher.name, exc)

    def _publish_state(payload, performance=None):
        if performance_enabled or display_pub is not None:
            payload = dict(payload)
        # A watchdog-settled capture rides the state payload as an additive field
        # (existing consumers may ignore it), but the authoritative terminal
        # receipt must also reach the existing selection_ack topic the WebUI
        # reads. The normal frame path sends result["baseline_ack"] itself, so
        # only a status_state receipt is forwarded here -- exactly one publish
        # per terminal receipt, never a duplicate.
        baseline_ack = payload.get("baseline_ack") \
            if isinstance(payload, dict) else None
        if performance_enabled:
            payload["performance"] = performance if performance is not None \
                else perf_holder["last"]
        if display_pub is not None:
            payload["visualization"] = viz_holder["last"]
        _publish(publishers["state"], payload)
        if baseline_ack is not None:
            _publish(publishers["ack"], baseline_ack)

    def _publish_display(orig, snapshot):
        """Publish a stride-sampled copy of one cloud for display only.

        Returns the wire mapping (topic, actual wire seq read back after publish,
        original source header, stride, counts) or None when the layout is
        unusable -- a bad frame never produces a fabricated display cloud.
        """
        names = {field.name for field in orig.fields}
        if not {"x", "y", "z"}.issubset(names):
            return None
        sampled, count, total = sample_point_data(
            orig.data, orig.point_step, orig.row_step, orig.height, orig.width,
            vis_stride, vis_max)
        if sampled is None:
            return None
        out = PointCloud2()
        out.header.frame_id = orig.header.frame_id
        out.header.stamp = orig.header.stamp          # preserve the source stamp
        out.header.seq = orig.header.seq              # source seq (rospy rewrites)
        out.height = 1
        out.width = count
        out.point_step = orig.point_step
        out.row_step = count * orig.point_step
        out.is_bigendian = orig.is_bigendian
        out.is_dense = orig.is_dense
        out.fields = list(orig.fields)
        out.data = sampled
        display_pub.publish(out)
        # rospy assigns the real per-topic seq on publish (verified by probe), so
        # read it back from the message instead of claiming the source seq.
        wire_seq = int(out.header.seq)
        source = snapshot.get("source") or {}
        return {"topic": display_topic, "source_topic": cloud_topic,
                "wire_seq": wire_seq,
                "source": {"seq": source.get("seq"),
                           "stamp_secs": source.get("stamp_secs"),
                           "stamp_nsecs": source.get("stamp_nsecs")},
                "stride": vis_stride, "original_points": total,
                "display_points": count}

    rospy.Subscriber(cloud_topic, PointCloud2, on_cloud, queue_size=1,
                     buff_size=2 ** 24)
    rospy.Subscriber(imu_topic, Imu, on_imu, queue_size=64)
    rospy.Subscriber(device_topic, DeviceStatus, on_device, queue_size=8)
    rospy.Subscriber(topics.get("selection_request", "/human_fall/selection_request"),
                     String, on_request, queue_size=16)

    def worker():
        while not stop.is_set():
            got = queue.wait(publish_period)
            item = queue.take() if got else None
            if item is None:
                if stop.is_set():
                    break
                state = core.status_state(time.monotonic())
                _publish_state(state)
                continue
            receive_s, msg = item
            now = time.monotonic()
            # A queued frame that is already older than the required-cloud
            # timeout must not be treated as fresh; drop it and only report the
            # current (stale) status. Processing time, not the frame's arrival
            # time, is the online clock for freshness.
            if frame_age_exceeded(receive_s, now, cloud_stale_s):
                rospy.logwarn_throttle(5.0, "human_fall_node dropping stale queued frame (%.2fs)",
                                       now - receive_s)
                perf_holder["last"] = performance_block(
                    core.frame_count, queue.dropped, False, True, receive_s, None,
                    now, None, now - receive_s, False, None)
                _publish_state(core.status_state(now))
                continue
            points = None
            try:
                points = xyz_from_cloud(msg, 0.0)
            except (ValueError, calibration_error) as exc:  # type: ignore[misc]
                rospy.logwarn_throttle(5.0, "human_fall_node cloud decode failed: %s", exc)
            compute_start = time.monotonic()
            result = core.process(
                points, receive_s, seq=getattr(msg.header, "seq", None),
                stamp_secs=stamp_pair(msg.header.stamp)[0],
                stamp_nsecs=stamp_pair(msg.header.stamp)[1],
                frame_id=msg.header.frame_id or None, now=now)
            # Re-read the same-machine clock after the (possibly slow) decode and
            # core computation. If the frame is stale by then, publish only the
            # current stale/unknown status: never a stale candidate, an old
            # "normal" state, or a fresh alarm greened by the pre-compute clock.
            finished = time.monotonic()
            rospy.loginfo_throttle(5.0, "human_fall_node processed frame in %.3fs (age %.3fs)",
                                   finished - compute_start, finished - receive_s)
            input_valid = bool(result["snapshot"] is not None
                               and result["state"].get("observability") != "invalid")
            ground_valid = bool(result["state"].get(
                "sensor_quality", {}).get("ground_valid"))
            suppressed = frame_age_exceeded(receive_s, finished, cloud_stale_s)
            perf = performance_block(
                core.frame_count, queue.dropped, input_valid, suppressed, receive_s,
                compute_start, finished, finished - compute_start,
                finished - receive_s, ground_valid, result["state"].get("fall_status"))
            perf_holder["last"] = perf
            if suppressed:
                rospy.logwarn_throttle(5.0, "human_fall_node frame stale after compute "
                                            "(%.2fs); suppressing outputs", finished - receive_s)
                _publish_state(core.status_state(finished), perf)
                # A capture terminal already produced by this frame must still
                # reach the ack topic even though the stale candidate/event/
                # position outputs are suppressed. status_state cannot also emit
                # it: once the collector is ready/failed it is no longer pending.
                if result["baseline_ack"] is not None:
                    _publish(publishers["ack"], result["baseline_ack"])
                continue
            if display_pub is not None and result["snapshot"] is not None:
                viz = _publish_display(msg, result["snapshot"])
                if viz is not None:
                    viz_holder["last"] = viz
            if result["snapshot"] is not None:
                # Strip the large offline evidence arrays from the browser copy
                # without mutating the cached/selection snapshot.
                projected = project_snapshot_for_ros(result["snapshot"])
                if display_pub is not None and viz_holder["last"] is not None:
                    projected["visualization"] = viz_holder["last"]
                _publish(publishers["candidates"], projected)
            _publish_state(result["state"], perf)
            if result["event"] is not None:
                _publish(publishers["event"], result["event"])
            if result["baseline_ack"] is not None:
                _publish(publishers["ack"], result["baseline_ack"])

    def shutdown():
        stop.set()
        queue.put(None)
        queue.wake()

    rospy.on_shutdown(shutdown)
    thread = threading.Thread(target=worker, name="human_fall_worker", daemon=True)
    thread.start()
    rospy.loginfo("human_fall_node: %s + %s + %s -> %s (session %s, ground=%s, events=%s)",
                  cloud_topic, imu_topic, device_topic, publishers["state"].name,
                  session_id, "valid" if core._ground_valid() else "unavailable",
                  event_path)
    rate = rospy.Rate(10.0)
    while not rospy.is_shutdown():
        rate.sleep()
    stop.set()
    queue.put(None)
    queue.wake()
    thread.join(timeout=5.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
