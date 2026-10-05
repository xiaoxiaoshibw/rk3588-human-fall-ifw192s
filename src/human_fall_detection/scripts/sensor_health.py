#!/usr/bin/env python3
"""Publish strict-JSON health for the point cloud, auxiliary IMU and device status. Read-only."""

import argparse
import json
import math
import os
import sys
import tempfile
import threading
import time

import numpy as np

SCHEMA_VERSION = 1
HEALTH_KIND = "health"
SOURCE_TIME_DOMAIN = "device_stamp_s_unanchored"
QUATERNION_UNIT_TOLERANCE = 1e-3
FLOAT32_DATATYPE = 7
FLOAT64_DATATYPE = 8
STAMP_STATUSES = ("none", "first", "ok", "repeated", "regressed", "forward_jump", "invalid")


def finite_or_none(value):
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def dumps_strict(payload):
    return json.dumps(payload, allow_nan=False)


def save_json(path, data):
    directory = os.path.abspath(os.path.dirname(path) or ".")
    os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory,
                                         prefix=".human-fall-", suffix=".json",
                                         delete=False) as output:
            temporary = output.name
            json.dump(data, output, indent=2, ensure_ascii=False, allow_nan=False)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def stamp_pair(header):
    return (int(header.secs), int(header.nsecs))


def valid_stamp(stamp):
    if stamp is None or len(stamp) != 2:
        return False
    secs, nsecs = int(stamp[0]), int(stamp[1])
    if secs < 0 or nsecs < 0 or nsecs >= 1000000000:
        return False
    return (secs, nsecs) != (0, 0)


def stamp_seconds(stamp):
    if not valid_stamp(stamp):
        return None
    return int(stamp[0]) + int(stamp[1]) / 1e9


def raw_stamp(stamp):
    """Raw integer sec/nsec of the current frame, kept even when the stamp is invalid."""
    if stamp is None or len(stamp) != 2:
        return None, None
    try:
        return int(stamp[0]), int(stamp[1])
    except (TypeError, ValueError):
        return None, None


def check_stamp(prefix, previous, current, max_forward_jump_s):
    """Classify a new source stamp. Returns (status, reason, discontinuity)."""
    if not valid_stamp(current):
        return "invalid", prefix + "_stamp_invalid", False
    if previous is None:
        return "first", None, False
    current_s = stamp_seconds(current)
    previous_s = stamp_seconds(previous)
    if current_s < previous_s:
        return "regressed", prefix + "_stamp_regressed", True
    if current_s == previous_s:
        return "repeated", prefix + "_stamp_repeated", True
    if current_s - previous_s > float(max_forward_jump_s):
        return "forward_jump", prefix + "_stamp_forward_jump", True
    return "ok", None, False


def orientation_covariance_flags(covariance):
    """Return (all_zero, not_provided) for the ROS Imu 9-element covariance array.

    All nine entries zero only mark the covariance as unknown; a first entry of -1
    means the orientation estimate is not provided and must be ignored.
    """
    values = [float(value) for value in covariance] if covariance is not None else []
    all_zero = len(values) == 9 and all(value == 0.0 for value in values)
    not_provided = bool(values) and values[0] == -1.0
    return all_zero, not_provided


def quaternion_report(quaternion):
    """Return (usable, reason). All-zero, non-finite and non-unit quaternions are unusable."""
    values = [float(value) for value in quaternion]
    if len(values) != 4 or not all(math.isfinite(value) for value in values):
        return False, "orientation_nonfinite"
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        return False, "orientation_all_zero"
    if abs(norm - 1.0) > QUATERNION_UNIT_TOLERANCE:
        return False, "orientation_non_unit"
    return True, None


def pointcloud_layout(msg):
    """Validate PointCloud2 fields/offsets/datatypes/strides/endianness/data length."""
    errors = []
    try:
        width, height = int(msg.width), int(msg.height)
        point_step, row_step = int(msg.point_step), int(msg.row_step)
        bigendian = bool(msg.is_bigendian)
        raw_fields = list(msg.fields)
    except (AttributeError, TypeError, ValueError) as exc:
        return {"valid": False, "errors": ["unreadable_message:" + str(exc)],
                "width": None, "height": None, "point_step": None, "row_step": None,
                "data_bytes": 0, "required_bytes": None, "is_bigendian": None,
                "field_names": []}
    if width <= 0 or height <= 0:
        errors.append("invalid_dimensions")
    if point_step <= 0:
        errors.append("invalid_point_step")
    if row_step < width * point_step:
        errors.append("row_step_smaller_than_points")
    try:
        data = memoryview(msg.data)
        data_bytes = data.nbytes
    except (TypeError, ValueError):
        data = None
        data_bytes = 0
        errors.append("data_not_a_byte_buffer")
    required_bytes = max(0, row_step) * max(0, height)
    if data is not None and data_bytes < required_bytes:
        errors.append("truncated_data")
    fields = {}
    for field in raw_fields:
        name = str(field.name)
        if name in fields:
            errors.append("duplicate_field_" + name)
            continue
        fields[name] = field
    for name in ("x", "y", "z"):
        field = fields.get(name)
        if field is None:
            errors.append("missing_field_" + name)
            continue
        size = 4 if int(field.datatype) == FLOAT32_DATATYPE else 8
        if int(field.datatype) not in (FLOAT32_DATATYPE, FLOAT64_DATATYPE) or int(field.count) != 1:
            errors.append("bad_field_" + name)
        elif int(field.offset) < 0 or int(field.offset) + size > point_step:
            errors.append("field_outside_point_step_" + name)
    timestamp_field = fields.get("timestamp")
    if timestamp_field is None:
        errors.append("missing_field_timestamp")
    elif int(timestamp_field.datatype) != FLOAT64_DATATYPE or int(timestamp_field.count) != 1:
        errors.append("bad_field_timestamp")
    elif int(timestamp_field.offset) < 0 or int(timestamp_field.offset) + 8 > point_step:
        errors.append("field_outside_point_step_timestamp")
    return {"valid": not errors, "errors": errors,
            "width": width, "height": height,
            "point_step": point_step, "row_step": row_step,
            "data_bytes": data_bytes, "required_bytes": required_bytes,
            "is_bigendian": bigendian, "field_names": list(fields)}


def read_point_timestamps(msg):
    """Read the per-point float64 timestamp field at its declared (possibly unaligned) offset."""
    layout = pointcloud_layout(msg)
    if not layout["valid"]:
        raise ValueError("invalid PointCloud2 layout: " + ",".join(layout["errors"]))
    field = next(field for field in msg.fields if str(field.name) == "timestamp")
    try:
        data = memoryview(msg.data)
        dtype = np.dtype(">f8" if layout["is_bigendian"] else "<f8")
        array = np.ndarray((layout["height"], layout["width"]), dtype=dtype, buffer=data,
                           strides=(layout["row_step"], layout["point_step"]),
                           offset=int(field.offset))
        return np.asarray(array, dtype=np.float64).ravel()
    except (TypeError, ValueError) as exc:
        raise ValueError("cannot decode PointCloud2 timestamps: " + str(exc)) from exc


def point_value_summary(total_points, xyz):
    """Summarise decoded xyz points: finite/non-finite and all-zero (invalid-return) counts."""
    total = int(total_points)
    finite = int(len(xyz))
    zero = int(np.count_nonzero(np.all(np.asarray(xyz) == 0.0, axis=1))) if xyz.size else 0
    return {"total_points": total, "nonfinite_points": total - finite,
            "zero_points": zero, "finite_nonzero_points": finite - zero}


def _load_xyz_from_cloud():
    """Reuse human_follow_calibration.xyz_from_cloud instead of copying the decoder."""
    try:
        from calibrate_human_follow import CalibrationError, xyz_from_cloud
        return xyz_from_cloud, CalibrationError
    except ImportError:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = (os.path.join(here, "..", "human_follow_calibration"),
                  os.path.join(here, "..", "..", "human_follow_calibration", "scripts"))
    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        if os.path.isfile(os.path.join(candidate, "calibrate_human_follow.py")):
            if candidate not in sys.path:
                sys.path.append(candidate)
    try:
        from calibrate_human_follow import CalibrationError, xyz_from_cloud
        return xyz_from_cloud, CalibrationError
    except ImportError:
        return None, None


class TopicTracker:
    def __init__(self, label, topic, timeout_s, max_forward_jump_s, required):
        self.label = label
        self.topic = topic
        self.timeout_s = float(timeout_s)
        self.max_forward_jump_s = float(max_forward_jump_s)
        self.required = bool(required)
        self.messages = 0
        self.first_receive_s = None
        self.last_receive_s = None
        self.last_stamp = None
        self.stamp_status = "none"
        self.stamp_reason = None
        self.stamp_secs = None
        self.stamp_nsecs = None
        self.last_source_stamp_s = None
        self.frame_id = None

    def note(self, now, stamp, frame_id=None):
        self.messages += 1
        if self.first_receive_s is None:
            self.first_receive_s = float(now)
        self.last_receive_s = float(now)
        if frame_id is not None:
            self.frame_id = frame_id
        status, reason, discontinuity = check_stamp(self.label, self.last_stamp, stamp,
                                                    self.max_forward_jump_s)
        self.stamp_status = status
        self.stamp_reason = reason
        self.stamp_secs, self.stamp_nsecs = raw_stamp(stamp)
        if status == "invalid":
            self.last_source_stamp_s = None
        else:
            self.last_stamp = stamp
            self.last_source_stamp_s = stamp_seconds(stamp)
        return discontinuity

    def block(self, now):
        age = None if self.last_receive_s is None else max(0.0, float(now) - self.last_receive_s)
        if self.messages == 0:
            status = "no_data"
        elif age > self.timeout_s:
            status = "stale"
        else:
            status = "fresh"
        rate = None
        if self.messages >= 2 and self.last_receive_s > self.first_receive_s:
            rate = (self.messages - 1) / (self.last_receive_s - self.first_receive_s)
        return {"topic": self.topic, "required": self.required, "status": status,
                "messages": self.messages, "receive_hz": finite_or_none(rate),
                "last_age_s": finite_or_none(age), "frame_id": self.frame_id,
                "stamp_status": self.stamp_status if self.messages else "none",
                "stamp_reason": self.stamp_reason,
                "stamp_secs": self.stamp_secs,
                "stamp_nsecs": self.stamp_nsecs,
                "source_stamp_s": finite_or_none(self.last_source_stamp_s)}


class HealthMonitor:
    """Pure bookkeeping for the health payload; ROS callbacks only feed this object."""

    def __init__(self, session_id, cloud_topic, imu_topic, device_topic,
                 cloud_timeout_s, imu_timeout_s, device_timeout_s, max_forward_jump_s,
                 expected_cloud_frame=None, units_verified=False, alignment_verified=False,
                 tf_available=False, calibration_status="pending"):
        self._lock = threading.Lock()
        self.session_id = session_id
        self.time_epoch = 0
        self.expected_cloud_frame = expected_cloud_frame
        self.units_verified = bool(units_verified)
        self.alignment_verified = bool(alignment_verified)
        self.tf_available = bool(tf_available)
        self.calibration_status = calibration_status
        self.cloud = TopicTracker("cloud", cloud_topic, cloud_timeout_s,
                                  max_forward_jump_s, required=True)
        self.imu = TopicTracker("imu", imu_topic, imu_timeout_s,
                                max_forward_jump_s, required=False)
        self.device = TopicTracker("device", device_topic, device_timeout_s,
                                   max_forward_jump_s, required=False)
        self.cloud_layout = None
        self.cloud_points = None
        self.cloud_point_stamp = None
        self.cloud_header_equals_first = None
        self.cloud_decode_error = None
        self.imu_measurements_finite = None
        self.imu_acceleration = None
        self.imu_angular_velocity = None
        self.imu_orientation_usable = None
        self.imu_orientation_reason = None
        self.imu_orientation_not_provided = None
        self.imu_covariance_zero = None
        self.device_fields = None

    def note_cloud(self, now, stamp, frame_id=None, layout=None, points=None,
                   point_stamp=None, header_equals_first=None, decode_error=None):
        with self._lock:
            if self.cloud.note(now, stamp, frame_id):
                self.time_epoch += 1
            self.cloud_layout = layout
            self.cloud_points = points
            self.cloud_point_stamp = point_stamp
            self.cloud_header_equals_first = header_equals_first
            self.cloud_decode_error = decode_error

    def note_imu(self, now, stamp, frame_id=None, acceleration=None, angular_velocity=None,
                 orientation=None, orientation_covariance_zero=None,
                 orientation_not_provided=False):
        with self._lock:
            if self.imu.note(now, stamp, frame_id):
                self.time_epoch += 1
            self.imu_acceleration = acceleration
            self.imu_angular_velocity = angular_velocity
            if acceleration is None or angular_velocity is None:
                self.imu_measurements_finite = None
            else:
                values = [float(v) for v in list(acceleration) + list(angular_velocity)]
                self.imu_measurements_finite = all(math.isfinite(v) for v in values)
            if orientation is None:
                self.imu_orientation_usable = None
                self.imu_orientation_reason = None
            elif orientation_not_provided:
                self.imu_orientation_usable = False
                self.imu_orientation_reason = "orientation_not_provided"
            else:
                self.imu_orientation_usable, self.imu_orientation_reason = \
                    quaternion_report(orientation)
            self.imu_orientation_not_provided = bool(orientation_not_provided)
            self.imu_covariance_zero = orientation_covariance_zero

    def note_device(self, now, stamp, frame_id=None, fields=None):
        with self._lock:
            if self.device.note(now, stamp, frame_id):
                self.time_epoch += 1
            self.device_fields = fields

    def _reason_codes(self, cloud_block, imu_block, device_block):
        codes = []

        def add(code):
            if code and code not in codes:
                codes.append(code)

        for tracker, block in ((self.cloud, cloud_block), (self.imu, imu_block),
                               (self.device, device_block)):
            if block["status"] == "no_data":
                add(tracker.label + "_no_data")
            elif block["status"] == "stale":
                add(tracker.label + "_stale")
            add(block["stamp_reason"])
        if self.cloud_layout is not None and not self.cloud_layout["valid"]:
            add("cloud_layout_invalid")
        if self.cloud_decode_error is not None:
            add("cloud_decode_failed")
        if self.cloud_layout is None and self.cloud.messages and self.cloud.stamp_status != "invalid":
            add("cloud_layout_missing")
        if self.cloud_points is not None and self.cloud_points["nonfinite_points"] > 0:
            add("cloud_nonfinite_points")
        if (self.expected_cloud_frame and self.cloud.frame_id
                and self.cloud.frame_id != self.expected_cloud_frame):
            add("cloud_frame_unexpected")
        if self.imu_measurements_finite is False:
            add("imu_measurement_nonfinite")
        if self.imu_orientation_usable is False:
            add("orientation_unusable")
        if not self.units_verified:
            add("imu_units_unverified")
        if not self.alignment_verified:
            add("imu_alignment_unverified")
        if not self.tf_available:
            add("tf_absent")
        if self.calibration_status != "verified":
            add("calibration_pending")
        add("clock_cross_stream_unverified")
        add("host_anchor_unverified")
        if self.device_fields and self.device_fields.get("abnormal_flag") not in (None, 0):
            add("device_abnormal_flag_uninterpreted")
        return codes

    def _observability(self, cloud_block, imu_block, device_block):
        if cloud_block["status"] != "fresh" or cloud_block["stamp_status"] == "invalid":
            return "invalid"
        if self.cloud_layout is None or not self.cloud_layout["valid"]:
            return "invalid"
        if self.cloud_decode_error is not None:
            return "invalid"
        if (self.expected_cloud_frame and self.cloud.frame_id
                and self.cloud.frame_id != self.expected_cloud_frame):
            return "degraded"
        if imu_block["status"] != "fresh" or device_block["status"] != "fresh":
            return "degraded"
        if self.imu_measurements_finite is False:
            return "degraded"
        return "valid"

    def snapshot(self, now):
        with self._lock:
            cloud_block = self.cloud.block(now)
            cloud_block["layout"] = self.cloud_layout
            cloud_block["points"] = self.cloud_points
            cloud_block["point_stamp"] = self.cloud_point_stamp
            cloud_block["header_equals_first_point_stamp"] = self.cloud_header_equals_first
            cloud_block["decode_error"] = self.cloud_decode_error

            imu_block = self.imu.block(now)
            if self.imu_acceleration is None:
                imu_block["raw_acceleration"] = None
            else:
                imu_block["raw_acceleration"] = {
                    "x": finite_or_none(self.imu_acceleration[0]),
                    "y": finite_or_none(self.imu_acceleration[1]),
                    "z": finite_or_none(self.imu_acceleration[2]),
                    "units": "unknown"}
            if self.imu_angular_velocity is None:
                imu_block["raw_angular_velocity"] = None
            else:
                imu_block["raw_angular_velocity"] = {
                    "x": finite_or_none(self.imu_angular_velocity[0]),
                    "y": finite_or_none(self.imu_angular_velocity[1]),
                    "z": finite_or_none(self.imu_angular_velocity[2]),
                    "units": "unknown"}
            imu_block["measurements_finite"] = self.imu_measurements_finite
            imu_block["units_verified"] = self.units_verified
            imu_block["alignment_verified"] = self.alignment_verified
            imu_block["orientation_usable"] = self.imu_orientation_usable
            imu_block["orientation_reason"] = self.imu_orientation_reason
            imu_block["orientation_not_provided"] = self.imu_orientation_not_provided
            imu_block["orientation_covariance_zero"] = self.imu_covariance_zero

            device_block = self.device.block(now)
            fields = self.device_fields or {}
            device_block["device_number"] = fields.get("device_number")
            device_block["trx_temperature"] = finite_or_none(fields.get("trx_temperature"))
            device_block["main_temperature"] = finite_or_none(fields.get("main_temperature"))
            device_block["abnormal_flag"] = fields.get("abnormal_flag")
            device_block["abnormal_flag_semantics"] = "unknown"

            return {
                "schema_version": SCHEMA_VERSION,
                "kind": HEALTH_KIND,
                "session_id": self.session_id,
                "time_epoch": self.time_epoch,
                "time_received_s": finite_or_none(now),
                "source_time_domain": SOURCE_TIME_DOMAIN,
                "normalized_stamp_s": None,
                "observability": self._observability(cloud_block, imu_block, device_block),
                "reason_codes": self._reason_codes(cloud_block, imu_block, device_block),
                "sync": {"cross_stream_same_clock_verified": False,
                         "host_anchor_verified": False},
                "units": {"imu_units_verified": self.units_verified,
                          "imu_alignment_verified": self.alignment_verified},
                "calibration": {"tf_available": self.tf_available, "extrinsics": "unknown",
                                "ground": "unknown", "imu_alignment": "unknown",
                                "geometry_params": self.calibration_status},
                "topics": {"cloud": cloud_block, "imu": imu_block,
                           "device_status": device_block},
            }


def load_config(path):
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required: " + str(exc))
    with open(path, encoding="utf-8") as source:
        return yaml.safe_load(source) or {}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="YAML config; defaults to the package default.yaml")
    parser.add_argument("--session-id", default=None)
    args = parser.parse_args(argv)
    try:
        import rospy
        import rospkg
        from std_msgs.msg import String
        from sensor_msgs.msg import Imu, PointCloud2
        from inno_lidar_msg.msg import DeviceStatus
    except ImportError as exc:
        parser.exit(2, "ROS1 rospy/rospkg/sensor_msgs/std_msgs/inno_lidar_msg required: {}\n".format(exc))
    config_path = args.config
    if config_path is None:
        config_path = os.path.join(rospkg.RosPack().get_path("human_fall_detection"),
                                   "config", "default.yaml")
    config = load_config(config_path)
    topics = config.get("topics", {})
    timeouts = config.get("timeouts_s", {})
    stamp_limits = config.get("stamps", {})
    checks = config.get("checks", {})
    imu_semantics = config.get("imu_semantics", {})
    session_id = args.session_id or "health_" + time.strftime("%Y%m%d_%H%M%S")
    monitor = HealthMonitor(
        session_id=session_id,
        cloud_topic=topics.get("cloud", "/innolidar_points"),
        imu_topic=topics.get("imu", "/inno_imu"),
        device_topic=topics.get("device_status", "/device_status"),
        cloud_timeout_s=float(timeouts.get("cloud_stale", 0.6)),
        imu_timeout_s=float(timeouts.get("imu_stale", 0.3)),
        device_timeout_s=float(timeouts.get("device_stale", 0.6)),
        max_forward_jump_s=float(stamp_limits.get("max_forward_jump_s", 30.0)),
        expected_cloud_frame=checks.get("expected_cloud_frame") or None,
        units_verified=bool(imu_semantics.get("units_verified", False)),
        alignment_verified=bool(imu_semantics.get("alignment_verified", False)))
    xyz_from_cloud, calibration_error = _load_xyz_from_cloud()

    rospy.init_node("human_fall_sensor_health", disable_signals=False)
    publisher = rospy.Publisher(topics.get("health", "/human_fall/health"), String, queue_size=1)

    def on_cloud(msg):
        now = time.monotonic()
        stamp = stamp_pair(msg.header.stamp)
        layout = pointcloud_layout(msg)
        points = None
        point_stamp = None
        header_equals_first = None
        decode_error = None
        if layout["valid"]:
            if xyz_from_cloud is None:
                decode_error = "human_follow_calibration.xyz_from_cloud unavailable"
            else:
                try:
                    timestamps = read_point_timestamps(msg)
                    if timestamps.size:
                        point_stamp = {"first_s": finite_or_none(timestamps[0]),
                                       "last_s": finite_or_none(timestamps[-1]),
                                       "span_s": finite_or_none(timestamps[-1] - timestamps[0])}
                        header_equals_first = (stamp_seconds(stamp) is not None
                                               and stamp_seconds(stamp) == float(timestamps[0]))
                    xyz = xyz_from_cloud(msg, 0.0)
                    points = point_value_summary(layout["width"] * layout["height"], xyz)
                except (ValueError, calibration_error) as exc:
                    decode_error = str(exc)
        monitor.note_cloud(now, stamp, msg.header.frame_id, layout, points,
                           point_stamp, header_equals_first, decode_error)

    def on_imu(msg):
        covariance_zero, not_provided = orientation_covariance_flags(msg.orientation_covariance)
        monitor.note_imu(
            time.monotonic(), stamp_pair(msg.header.stamp), msg.header.frame_id,
            (msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z),
            (msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z),
            (msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w),
            covariance_zero, orientation_not_provided=not_provided)

    def on_device(msg):
        monitor.note_device(time.monotonic(), stamp_pair(msg.header.stamp), msg.header.frame_id,
                            {"device_number": int(msg.device_number),
                             "trx_temperature": float(msg.trx_temperature),
                             "main_temperature": float(msg.main_temperature),
                             "abnormal_flag": int(msg.abnormal_flag)})

    rospy.Subscriber(monitor.cloud.topic, PointCloud2, on_cloud, queue_size=1, buff_size=2 ** 24)
    rospy.Subscriber(monitor.imu.topic, Imu, on_imu, queue_size=64)
    rospy.Subscriber(monitor.device.topic, DeviceStatus, on_device, queue_size=8)
    period = float(config.get("publish_period_s", 0.5))
    rospy.loginfo("Human-fall health: %s + %s + %s -> %s (session %s)",
                  monitor.cloud.topic, monitor.imu.topic, monitor.device.topic,
                  publisher.name, session_id)
    while not rospy.is_shutdown():
        payload = monitor.snapshot(time.monotonic())
        try:
            publisher.publish(String(data=dumps_strict(payload)))
        except ValueError as exc:
            rospy.logerr("Refusing non-finite health payload: %s", exc)
        rospy.sleep(period)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
