#!/usr/bin/env python3
"""Publish read-only human-like target state from calibrated ROS1 point clouds."""

import argparse
import json
import math
import threading
import time

from calibrate_human_follow import (CalibrationError, background_from_frames,
                                    candidates_in_frame, capture_frames,
                                    xyz_from_cloud)


def load_calibration(path):
    with open(path, encoding="utf-8") as source:
        data = json.load(source)
    try:
        if data["schema_version"] != 1 or not data["sensor_frame"]:
            raise CalibrationError("unsupported calibration file")
        distance = float(data["preferred_follow_distance_m"])
        offset = float(data["bearing_offset_rad"])
        if not (math.isfinite(distance) and distance > 0 and math.isfinite(offset)):
            raise CalibrationError("invalid follow distance or bearing offset")
        settings, roi = data["thresholds"], data["roi"]
        for name in ("min_range_m", "background_cell_m", "background_z_cell_m",
                     "cluster_cell_m", "min_height_m", "max_height_m",
                     "max_depth_m", "max_width_m"):
            value = float(settings[name])
            if not math.isfinite(value) or value <= 0:
                raise CalibrationError("invalid threshold: " + name)
        if int(settings["min_cluster_points"]) < 1:
            raise CalibrationError("invalid cluster size")
        for low, high in (("x_min_m", "x_max_m"), ("y_min_m", "y_max_m"),
                          ("z_min_m", "z_max_m")):
            lower, upper = float(roi[low]), float(roi[high])
            if not (math.isfinite(lower) and math.isfinite(upper) and lower < upper):
                raise CalibrationError("invalid ROI: " + low + "/" + high)
    except (KeyError, TypeError, ValueError) as exc:
        raise CalibrationError("invalid calibration file: " + str(exc)) from exc
    return data


def target_state(points, background, calibration):
    candidates = candidates_in_frame(points, background, calibration["roi"],
                                     calibration["thresholds"])
    state = {"status": "absent", "person_present": False,
             "distance_m": None, "bearing_rad": None, "follow_error_m": None}
    if len(candidates) > 1:
        state.update(status="ambiguous", person_present=None)
    elif candidates:
        target = candidates[0]
        distance = target["surface_distance_m"]
        state.update(status="present", person_present=True, distance_m=distance,
                     bearing_rad=math.atan2(target["y_m"], target["x_m"])
                     - calibration["bearing_offset_rad"],
                     follow_error_m=distance - calibration["preferred_follow_distance_m"])
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", required=True, help="saved stationary calibration JSON")
    parser.add_argument("--topic", default=None, help="PointCloud2 input; defaults to calibration topic")
    parser.add_argument("--output-topic", default="/human_follow/state")
    parser.add_argument("--samples", type=int, default=15, help="empty-scene frames (>= 5)")
    parser.add_argument("--timeout", type=float, default=2.0, help="point-cloud timeout in seconds")
    args = parser.parse_args(argv)
    if args.samples < 5 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("samples must be at least five and timeout must be positive")
    try:
        calibration = load_calibration(args.calibration)
    except (OSError, ValueError) as exc:
        parser.exit(2, "Cannot load calibration: {}\n".format(exc))
    try:
        import rospy
        from sensor_msgs.msg import PointCloud2
        from std_msgs.msg import String
    except ImportError as exc:
        parser.exit(2, "ROS1 rospy/sensor_msgs/std_msgs is required: {}\n".format(exc))

    topic = args.topic or calibration.get("topic", "/innolidar_points")
    frame = calibration["sensor_frame"]
    roi, settings = calibration["roi"], calibration["thresholds"]
    rospy.init_node("human_follow_monitor", anonymous=True)
    try:
        input("Keep the sensor still and clear the ROI. Press Enter to capture the empty scene... ")
        empty, previous_stamp = capture_frames(
            rospy, PointCloud2, topic, frame, args.samples, args.timeout,
            settings["min_range_m"], roi)
        baseline_count = args.samples * 2 // 3
        background = background_from_frames(empty[:baseline_count], roi,
                                            settings["background_cell_m"],
                                            settings["background_z_cell_m"])
        if any(candidates_in_frame(points, background, roi, settings)
               for points in empty[baseline_count:]):
            raise CalibrationError("empty scene changed during capture; retry")
    except (CalibrationError, EOFError) as exc:
        parser.exit(2, "Cannot capture empty scene: {}\n".format(exc))

    publisher = rospy.Publisher(args.output_topic, String, queue_size=1)
    guard = threading.Lock()
    last_received = time.monotonic()
    stale_sent = False

    def publish(state, stamp=None):
        state["sensor_stamp_s"] = stamp
        publisher.publish(String(data=json.dumps(state, allow_nan=False)))

    def on_cloud(msg):
        nonlocal previous_stamp, last_received, stale_sent
        stamp = (int(msg.header.stamp.secs), int(msg.header.stamp.nsecs))
        with guard:
            fresh = stamp > previous_stamp and stamp != (0, 0) and 0 <= stamp[1] < 1_000_000_000
            if fresh and msg.header.frame_id == frame:
                previous_stamp = stamp
                last_received = time.monotonic()
                stale_sent = False
        if not fresh or msg.header.frame_id != frame:
            publish({"status": "invalid", "person_present": None,
                     "distance_m": None, "bearing_rad": None, "follow_error_m": None})
            return
        try:
            points = xyz_from_cloud(msg, settings["min_range_m"])
            state = target_state(points, background, calibration)
        except CalibrationError as exc:
            rospy.logwarn("Human follow point cloud rejected: %s", exc)
            state = {"status": "invalid", "person_present": None,
                     "distance_m": None, "bearing_rad": None, "follow_error_m": None}
        publish(state, stamp[0] + stamp[1] / 1e9)

    rospy.Subscriber(topic, PointCloud2, on_cloud, queue_size=1, buff_size=2 ** 24)
    rospy.loginfo("Human follow state: %s -> %s", topic, args.output_topic)
    while not rospy.is_shutdown():
        with guard:
            send_stale = time.monotonic() - last_received > args.timeout and not stale_sent
            if send_stale:
                stale_sent = True
        if send_stale:
            publish({"status": "stale", "person_present": None,
                     "distance_m": None, "bearing_rad": None, "follow_error_m": None})
        time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
