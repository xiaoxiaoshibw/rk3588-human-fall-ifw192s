#!/usr/bin/env python3
"""Calibrate one stationary LiDAR target. This program never commands a robot."""

import argparse
import json
import math
import os
import tempfile
import time
from datetime import datetime, timezone

import numpy as np


class CalibrationError(ValueError):
    pass


def positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return number


def xyz_from_cloud(msg, min_range_m):
    """Read x/y/z from organized or flat PointCloud2, including padded rows."""
    width, height = int(msg.width), int(msg.height)
    point_step, row_step = int(msg.point_step), int(msg.row_step)
    if width <= 0 or height <= 0 or point_step <= 0 or row_step < width * point_step:
        raise CalibrationError("invalid PointCloud2 dimensions or strides")
    try:
        data = memoryview(msg.data)
    except TypeError as exc:
        raise CalibrationError("PointCloud2 data is not a byte buffer") from exc
    if data.nbytes < row_step * height:
        raise CalibrationError("truncated PointCloud2 data")

    fields = {}
    for field in msg.fields:
        if field.name in ("x", "y", "z"):
            if field.name in fields:
                raise CalibrationError("duplicate PointCloud2 coordinate field: " + field.name)
            fields[field.name] = field
    if set(fields) != {"x", "y", "z"}:
        raise CalibrationError("PointCloud2 needs x, y and z fields")

    formats, offsets = [], []
    for name in ("x", "y", "z"):
        field = fields[name]
        if field.count != 1 or field.datatype not in (7, 8):  # PointField FLOAT32/FLOAT64
            raise CalibrationError("unsupported PointCloud2 field: " + name)
        size = 4 if field.datatype == 7 else 8
        if field.offset < 0 or field.offset + size > point_step:
            raise CalibrationError("PointCloud2 field exceeds point_step: " + name)
        formats.append(np.dtype((">" if msg.is_bigendian else "<") + ("f4" if size == 4 else "f8")))
        offsets.append(field.offset)
    try:
        dtype = np.dtype({"names": ["x", "y", "z"], "formats": formats,
                          "offsets": offsets, "itemsize": point_step})
        cloud = np.ndarray((height, width), dtype=dtype, buffer=data,
                           strides=(row_step, point_step))
        xyz = np.column_stack((cloud["x"].ravel(), cloud["y"].ravel(),
                               cloud["z"].ravel())).astype(np.float64, copy=False)
    except (ValueError, TypeError) as exc:
        raise CalibrationError("cannot decode PointCloud2 xyz: " + str(exc)) from exc
    xyz = xyz[np.isfinite(xyz).all(axis=1)]
    distance = np.hypot(np.hypot(xyz[:, 0], xyz[:, 1]), xyz[:, 2])
    return xyz[distance >= min_range_m]


def crop_roi(points, roi):
    return points[(points[:, 0] >= roi["x_min_m"]) & (points[:, 0] <= roi["x_max_m"])
                  & (points[:, 1] >= roi["y_min_m"]) & (points[:, 1] <= roi["y_max_m"])
                  & (points[:, 2] >= roi["z_min_m"]) & (points[:, 2] <= roi["z_max_m"])]


def voxel_keys(points, cell_xy_m, cell_z_m):
    grid = np.floor(points / (cell_xy_m, cell_xy_m, cell_z_m)).astype(np.int32)
    return np.ascontiguousarray(grid).view(np.dtype((np.void, 12))).ravel()


def background_from_frames(frames, roi, cell_xy_m, cell_z_m):
    points = np.concatenate([crop_roi(frame, roi) for frame in frames])
    if len(points) == 0:
        raise CalibrationError("empty-scene capture has no points inside ROI")
    return np.unique(voxel_keys(points, cell_xy_m, cell_z_m))


def candidates_in_frame(frame, background, roi, settings):
    points = crop_roi(frame, roi)
    if len(points) == 0:
        return []
    foreground = points[~np.isin(voxel_keys(points, settings["background_cell_m"],
                                            settings["background_z_cell_m"]),
                                  background)]
    if len(foreground) < settings["min_cluster_points"]:
        return []

    cells, inverse = np.unique(np.floor(foreground[:, :2] / settings["cluster_cell_m"])
                               .astype(np.int32), axis=0, return_inverse=True)
    cell_index = {tuple(cell): index for index, cell in enumerate(cells)}
    cell_counts = np.bincount(inverse, minlength=len(cells))
    seen = set()
    candidates = []
    for start in range(len(cells)):
        if start in seen:
            continue
        seen.add(start)
        stack = [start]
        component = []
        while stack:
            current = stack.pop()
            component.append(current)
            x, y = cells[current]
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    neighbor = cell_index.get((x + dx, y + dy))
                    if neighbor is not None and neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
        count = int(cell_counts[component].sum())
        if count < settings["min_cluster_points"]:
            continue
        cluster = foreground[np.isin(inverse, component)]
        low, high = np.percentile(cluster, (5, 95), axis=0)
        span = high - low
        if not (settings["min_height_m"] <= span[2] <= settings["max_height_m"]
                and span[0] <= settings["max_depth_m"]
                and span[1] <= settings["max_width_m"]):
            continue
        center = np.median(cluster[:, :2], axis=0)
        candidates.append({"x_m": float(center[0]), "y_m": float(center[1]),
                           "points": count, "height_m": float(span[2])})
    return candidates


def calibrate_frames(empty_frames, person_frames, known_distance_m,
                     preferred_distance_m, roi, settings):
    if len(empty_frames) < 5 or not person_frames:
        raise CalibrationError("need at least five empty frames and one person frame")
    baseline_count = max(1, len(empty_frames) * 2 // 3)
    background = background_from_frames(empty_frames[:baseline_count], roi,
                                        settings["background_cell_m"],
                                        settings["background_z_cell_m"])
    for frame in empty_frames[baseline_count:]:
        if candidates_in_frame(frame, background, roi, settings):
            raise CalibrationError("empty-scene holdout contains a person-sized foreground cluster")

    stand_roi = dict(roi)
    stand_roi["x_min_m"] = max(roi["x_min_m"], known_distance_m - settings["stand_tolerance_m"])
    stand_roi["x_max_m"] = min(roi["x_max_m"], known_distance_m + settings["stand_tolerance_m"])
    stand_roi["y_min_m"] = max(roi["y_min_m"], -settings["stand_tolerance_m"])
    stand_roi["y_max_m"] = min(roi["y_max_m"], settings["stand_tolerance_m"])
    outside_change = []
    for frame in person_frames:
        points = crop_roi(frame, roi)
        outside = points[(points[:, 0] < stand_roi["x_min_m"])
                         | (points[:, 0] > stand_roi["x_max_m"])
                         | (points[:, 1] < stand_roi["y_min_m"])
                         | (points[:, 1] > stand_roi["y_max_m"])]
        if len(outside) >= 100:
            outside_change.append(float(np.mean(~np.isin(
                voxel_keys(outside, settings["background_cell_m"],
                           settings["background_z_cell_m"]), background))))
    if outside_change and np.median(outside_change) > 0.5:
        raise CalibrationError("scene changed outside the stand area; recapture the empty scene")
    selected = []
    for frame in person_frames:
        candidates = candidates_in_frame(frame, background, stand_roi, settings)
        nearby = [candidate for candidate in candidates
                  if math.hypot(candidate["x_m"] - known_distance_m,
                                candidate["y_m"]) <= settings["stand_tolerance_m"]]
        if len(nearby) > 1:
            raise CalibrationError("multiple foreground clusters near the known stand position")
        if nearby:
            selected.append(nearby[0])
    needed = math.ceil(len(person_frames) * settings["min_valid_fraction"])
    if len(selected) < needed:
        raise CalibrationError("target absent or outside the known stand position in too many frames")

    centers = np.array([[item["x_m"], item["y_m"]] for item in selected])
    center = np.median(centers, axis=0)
    spread = np.max(np.linalg.norm(centers - center, axis=1))
    if spread > settings["max_stationary_spread_m"]:
        raise CalibrationError("target moved during calibration; stand still and retry")
    measured_distance = float(np.hypot(center[0], center[1]))
    measured_bearing = float(math.atan2(center[1], center[0]))
    return {
        "measured_target_x_m": float(center[0]),
        "measured_target_y_m": float(center[1]),
        "measured_distance_m": measured_distance,
        "measured_bearing_rad": measured_bearing,
        "known_forward_distance_m": known_distance_m,
        "distance_residual_m": measured_distance - known_distance_m,
        "bearing_offset_rad": measured_bearing,
        "preferred_follow_distance_m": preferred_distance_m,
        "valid_person_frames": len(selected),
        "person_frames": len(person_frames),
        "empty_frames": len(empty_frames),
        "stationary_spread_m": float(spread),
        "outside_scene_change_fraction": float(np.median(outside_change)) if outside_change else None,
    }


def capture_frames(rospy, cloud_type, topic, expected_frame, count, timeout_s,
                   min_range_m, roi, previous_stamp=None):
    frames = []
    for number in range(count):
        started = time.monotonic()
        try:
            msg = rospy.wait_for_message(topic, cloud_type, timeout=timeout_s)
        except rospy.ROSException as exc:
            raise CalibrationError("no fresh point cloud within timeout: " + str(exc)) from exc
        if time.monotonic() - started > timeout_s:
            raise CalibrationError("point cloud reception exceeded timeout")
        if msg.header.frame_id != expected_frame:
            raise CalibrationError("unexpected frame_id: " + repr(msg.header.frame_id))
        stamp = (int(msg.header.stamp.secs), int(msg.header.stamp.nsecs))
        if (stamp == (0, 0) or stamp[1] < 0 or stamp[1] >= 1_000_000_000
                or (previous_stamp is not None and stamp <= previous_stamp)):
            raise CalibrationError("stale or repeated device frame timestamp")
        previous_stamp = stamp
        points = xyz_from_cloud(msg, min_range_m)
        frames.append(points)
        print("\r  captured {}/{} frames ({} ROI points)".format(
            number + 1, count, len(crop_roi(points, roi))), end="", flush=True)
    print()
    return frames, previous_stamp


def save_json(path, data):
    directory = os.path.abspath(os.path.dirname(path) or ".")
    os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory,
                                         prefix=".follow-cal-", suffix=".json",
                                         delete=False) as output:
            temporary = output.name
            json.dump(data, output, indent=2, ensure_ascii=False, allow_nan=False)
            output.write("\n")
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--known-distance", type=positive_float, required=True,
                        help="tape-measured sensor-to-person forward distance in metres")
    parser.add_argument("--follow-distance", type=positive_float, required=True,
                        help="desired sensor-to-visible-person-surface distance in metres")
    parser.add_argument("--output", default="human_follow_calibration.json")
    parser.add_argument("--topic", default="/innolidar_points")
    parser.add_argument("--frame", default="innolidar")
    parser.add_argument("--samples", type=int, default=15, help="frames in each phase (>= 5)")
    parser.add_argument("--timeout", type=positive_float, default=2.0)
    parser.add_argument("--min-range", type=positive_float, default=0.3)
    parser.add_argument("--x-min", type=float, default=0.6)
    parser.add_argument("--x-max", type=float, default=6.0)
    parser.add_argument("--y-half-width", type=positive_float, default=2.0)
    parser.add_argument("--z-min", type=float, default=-0.2)
    parser.add_argument("--z-max", type=float, default=2.2)
    parser.add_argument("--background-cell", type=positive_float, default=0.1)
    parser.add_argument("--background-z-cell", type=positive_float, default=0.1)
    parser.add_argument("--cluster-cell", type=positive_float, default=0.2)
    parser.add_argument("--min-cluster-points", type=int, default=60)
    parser.add_argument("--stand-tolerance", type=positive_float, default=0.8)
    args = parser.parse_args(argv)
    if (args.samples < 5 or args.min_cluster_points < 1 or args.x_min >= args.x_max
            or args.z_min >= args.z_max or not all(map(math.isfinite,
                  (args.x_min, args.x_max, args.z_min, args.z_max)))
            or not args.x_min <= args.known_distance <= args.x_max):
        parser.error("invalid ROI, sample count, cluster size or known stand distance")

    roi = {"x_min_m": args.x_min, "x_max_m": args.x_max,
           "y_min_m": -args.y_half_width, "y_max_m": args.y_half_width,
           "z_min_m": args.z_min, "z_max_m": args.z_max}
    settings = {"background_cell_m": args.background_cell,
                "background_z_cell_m": args.background_z_cell,
                "cluster_cell_m": args.cluster_cell,
                "min_cluster_points": args.min_cluster_points,
                "min_height_m": 0.45, "max_height_m": 2.4,
                "max_depth_m": 1.2, "max_width_m": 1.2,
                "stand_tolerance_m": args.stand_tolerance,
                "min_valid_fraction": 0.6,
                "max_stationary_spread_m": 0.35}
    try:
        import rospy
        from sensor_msgs.msg import PointCloud2
    except ImportError as exc:
        parser.exit(2, "ROS1 rospy/sensor_msgs is required: {}\n".format(exc))
    rospy.init_node("human_follow_calibration", anonymous=True)
    try:
        print("Keep the robot stationary. Remove all people from the ROI.")
        input("Press Enter to capture the empty scene... ")
        empty_frames, stamp = capture_frames(rospy, PointCloud2, args.topic, args.frame,
                                             args.samples, args.timeout, args.min_range,
                                             roi)
        print("One person: stand still {:.2f} m directly forward from the sensor.".format(
            args.known_distance))
        input("Press Enter when the person is in place... ")
        person_frames, _ = capture_frames(rospy, PointCloud2, args.topic, args.frame,
                                          args.samples, args.timeout, args.min_range,
                                          roi, stamp)
        result = calibrate_frames(empty_frames, person_frames, args.known_distance,
                                  args.follow_distance, roi, settings)
        result.update({"schema_version": 1,
                       "created_at_utc": datetime.now(timezone.utc).isoformat(),
                       "topic": args.topic, "sensor_frame": args.frame,
                       "known_distance_reference": "feet_center",
                       "preferred_follow_distance_reference": "visible_surface",
                       "roi": roi, "thresholds": {"min_range_m": args.min_range, **settings},
                       "notes": "One forward station estimates local bearing offset, not full sensor extrinsics or range scale."})
        save_json(args.output, result)
        print("Saved {}".format(os.path.abspath(args.output)))
        print("Measured {:.3f} m at {:.2f} deg; known {:.3f} m; residual {:+.3f} m".format(
            result["measured_distance_m"], math.degrees(result["measured_bearing_rad"]),
            args.known_distance, result["distance_residual_m"]))
        return 0
    except (CalibrationError, EOFError) as exc:
        print("Calibration failed: {}".format(exc))
        return 2
    except KeyboardInterrupt:
        print("\nCalibration cancelled")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
