import copy
import json
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PACKAGE_DIR.parent
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))
sys.path.insert(0, str(SRC_DIR / "human_follow_calibration" / "scripts"))

import record_session
from sensor_health import (HealthMonitor, _load_xyz_from_cloud, check_stamp, dumps_strict,
                           orientation_covariance_flags, point_value_summary,
                           pointcloud_layout, quaternion_report, read_point_timestamps)
from record_session import build_manifest


def cloud_message(rows, timestamps, point_step=26, row_step=None, bigendian=False):
    height = len(rows)
    width = len(rows[0])
    if row_step is None:
        row_step = width * point_step
    byteorder = ">" if bigendian else "<"
    data = bytearray(row_step * height)
    for row, points in enumerate(rows):
        for column, point in enumerate(points):
            base = row * row_step + column * point_step
            struct.pack_into(byteorder + "fff", data, base, *point)
            struct.pack_into(byteorder + "d", data, base + 18, timestamps[row][column])
    fields = [SimpleNamespace(name="x", offset=0, datatype=7, count=1),
              SimpleNamespace(name="y", offset=4, datatype=7, count=1),
              SimpleNamespace(name="z", offset=8, datatype=7, count=1),
              SimpleNamespace(name="intensity", offset=12, datatype=7, count=1),
              SimpleNamespace(name="ring", offset=16, datatype=2, count=1),
              SimpleNamespace(name="timestamp", offset=18, datatype=8, count=1)]
    return SimpleNamespace(width=width, height=height, point_step=point_step, row_step=row_step,
                           data=bytes(data), fields=fields, is_bigendian=bigendian)


def valid_layout():
    return pointcloud_layout(cloud_message([[(1.0, 0.0, 0.0)]], [[10.0]]))


def make_monitor(**overrides):
    settings = dict(session_id="test", cloud_topic="/cloud", imu_topic="/imu",
                    device_topic="/device", cloud_timeout_s=0.5, imu_timeout_s=0.3,
                    device_timeout_s=0.5, max_forward_jump_s=30.0)
    settings.update(overrides)
    return HealthMonitor(**settings)


class PointCloudTest(unittest.TestCase):
    def test_timestamp_at_18_with_point_step_26_is_read_unaligned(self):
        message = cloud_message([[(1.0, 2.0, 3.0), (-1.0, 0.5, 0.25)]],
                                [[409.391589, 409.494682]])
        layout = pointcloud_layout(message)
        self.assertTrue(layout["valid"], layout["errors"])
        self.assertEqual(layout["point_step"], 26)
        stamps = read_point_timestamps(message)
        np.testing.assert_allclose(stamps, [409.391589, 409.494682], rtol=0, atol=1e-9)
        self.assertAlmostEqual(float(stamps[-1] - stamps[0]), 0.103093, places=6)

    def test_xyz_decoder_reuse_and_padded_big_endian_rows(self):
        xyz_from_cloud, _ = _load_xyz_from_cloud()
        self.assertIsNotNone(xyz_from_cloud, "human_follow_calibration.xyz_from_cloud missing")
        little = cloud_message([[(1.0, 0.0, 0.0)], [(2.0, 0.0, 0.0)]],
                               [[10.0], [10.1]], row_step=26 + 4)
        xyz = xyz_from_cloud(little, 0.0)
        np.testing.assert_allclose(xyz[:, 0], [1.0, 2.0])
        big = cloud_message([[(1.5, -1.0, 2.0)], [(3.0, 0.0, 4.5)]],
                            [[20.0], [20.2]], row_step=26 + 4, bigendian=True)
        layout = pointcloud_layout(big)
        self.assertTrue(layout["valid"], layout["errors"])
        self.assertTrue(layout["is_bigendian"])
        np.testing.assert_allclose(read_point_timestamps(big), [20.0, 20.2])
        np.testing.assert_allclose(xyz_from_cloud(big, 0.0), [[1.5, -1.0, 2.0],
                                                              [3.0, 0.0, 4.5]])

    def test_truncated_and_invalid_fields_are_rejected(self):
        message = cloud_message([[(1.0, 0.0, 0.0)]], [[1.0]])
        message.data = message.data[:-1]
        layout = pointcloud_layout(message)
        self.assertFalse(layout["valid"])
        self.assertIn("truncated_data", layout["errors"])

        no_timestamp = cloud_message([[(1.0, 0.0, 0.0)]], [[1.0]])
        no_timestamp.fields = [field for field in no_timestamp.fields
                               if field.name != "timestamp"]
        self.assertIn("missing_field_timestamp", pointcloud_layout(no_timestamp)["errors"])

        bad_type = cloud_message([[(1.0, 0.0, 0.0)]], [[1.0]])
        bad_type.fields[0].datatype = 3
        self.assertIn("bad_field_x", pointcloud_layout(bad_type)["errors"])

        bad_offset = cloud_message([[(1.0, 0.0, 0.0)]], [[1.0]])
        bad_offset.fields[5].offset = 20
        self.assertIn("field_outside_point_step_timestamp",
                      pointcloud_layout(bad_offset)["errors"])

        duplicated = cloud_message([[(1.0, 0.0, 0.0)]], [[1.0]])
        duplicated.fields[1].name = "x"
        self.assertIn("duplicate_field_x", pointcloud_layout(duplicated)["errors"])
        with self.assertRaises(ValueError):
            read_point_timestamps(message)

    def test_zero_and_nonfinite_points_are_counted(self):
        xyz_from_cloud, _ = _load_xyz_from_cloud()
        coordinates = [[(0.0, 0.0, 0.0), (float("nan"), 0.0, 0.0), (1.0, 2.0, 3.0)],
                       [(float("inf"), 0.0, 0.0), (0.0, 0.0, 0.0), (4.0, 0.0, 0.0)]]
        message = cloud_message(coordinates, [[9.0, 9.0, 9.0], [9.0, 9.0, 9.0]])
        xyz = xyz_from_cloud(message, 0.0)
        summary = point_value_summary(6, xyz)
        self.assertEqual(summary, {"total_points": 6, "nonfinite_points": 2, "zero_points": 2,
                                   "finite_nonzero_points": 2})


class StampAndTopicTest(unittest.TestCase):
    def test_stamp_repeat_regress_and_forward_jump_bump_epoch(self):
        monitor = make_monitor()
        layout = valid_layout()
        monitor.note_cloud(0.0, (10, 0), "innolidar", layout=layout)
        self.assertEqual(monitor.time_epoch, 0)
        monitor.note_cloud(0.1, (10, 100000000), "innolidar", layout=layout)
        monitor.note_cloud(0.2, (10, 100000000), "innolidar", layout=layout)
        self.assertEqual(monitor.time_epoch, 1)
        snapshot = monitor.snapshot(0.3)
        self.assertEqual(snapshot["topics"]["cloud"]["stamp_status"], "repeated")
        self.assertIn("cloud_stamp_repeated", snapshot["reason_codes"])
        monitor.note_cloud(0.4, (9, 900000000), "innolidar", layout=layout)
        self.assertEqual(monitor.time_epoch, 2)
        monitor.note_cloud(0.5, (9, 910000000), "innolidar", layout=layout)
        self.assertEqual(monitor.time_epoch, 2)
        monitor.note_cloud(0.6, (100, 0), "innolidar", layout=layout)
        self.assertEqual(monitor.time_epoch, 3)
        self.assertIn("cloud_stamp_forward_jump", monitor.snapshot(0.7)["reason_codes"])
        monitor.note_cloud(0.8, (5, 2000000000), "innolidar", layout=layout)
        self.assertEqual(monitor.time_epoch, 3)
        self.assertEqual(monitor.snapshot(0.9)["topics"]["cloud"]["stamp_status"], "invalid")
        status, reason, discontinuity = check_stamp("imu", (1, 0), (1, 0), 30.0)
        self.assertEqual((status, reason, discontinuity), ("repeated", "imu_stamp_repeated", True))

    def test_invalid_current_stamp_is_null_and_previous_valid_baseline_survives(self):
        monitor = make_monitor()
        layout = valid_layout()
        monitor.note_cloud(0.0, (10, 0), "innolidar", layout=layout)
        monitor.note_cloud(0.1, (0, 0), "innolidar", layout=layout)
        monitor.note_cloud(0.2, (10, 2000000000), "innolidar", layout=layout)
        cloud = monitor.snapshot(0.3)["topics"]["cloud"]
        self.assertEqual(cloud["stamp_status"], "invalid")
        self.assertIsNone(cloud["source_stamp_s"])
        self.assertEqual((cloud["stamp_secs"], cloud["stamp_nsecs"]), (10, 2000000000))
        self.assertEqual(monitor.time_epoch, 0)
        monitor.note_cloud(0.4, (9, 900000000), "innolidar", layout=layout)
        cloud = monitor.snapshot(0.5)["topics"]["cloud"]
        self.assertEqual(cloud["stamp_status"], "regressed")
        self.assertEqual(cloud["source_stamp_s"], 9.9)
        self.assertEqual(monitor.time_epoch, 1)

    def test_invalid_stamp_path_is_shared_by_every_topic(self):
        monitor = make_monitor()
        monitor.note_imu(0.0, (7, 0), "innolidar", (0.0, 0.0, 9.8), (0.0, 0.0, 0.0),
                         (0.0, 0.0, 0.0, 1.0), True)
        monitor.note_imu(0.1, (0, 0), "innolidar", (0.0, 0.0, 9.8), (0.0, 0.0, 0.0),
                         (0.0, 0.0, 0.0, 1.0), True)
        monitor.note_device(0.0, (7, 0), "innolidar", {"abnormal_flag": 0})
        monitor.note_device(0.1, (0, 2000000000), "innolidar", {"abnormal_flag": 0})
        snapshot = monitor.snapshot(0.2)
        for label in ("imu", "device_status"):
            self.assertEqual(snapshot["topics"][label]["stamp_status"], "invalid", label)
            self.assertIsNone(snapshot["topics"][label]["source_stamp_s"], label)
        self.assertEqual(monitor.time_epoch, 0)

    def test_cloud_stall_invalid_but_imu_stall_only_degrades(self):
        monitor = make_monitor()
        layout = valid_layout()
        monitor.note_cloud(0.0, (10, 0), "innolidar", layout=layout)
        monitor.note_imu(0.0, (10, 0), "innolidar", (0.0, 0.0, 9.8), (0.0, 0.0, 0.0),
                         (0.0, 0.0, 0.0, 1.0), True)
        monitor.note_device(0.0, (10, 0), "innolidar",
                            {"device_number": 71, "trx_temperature": 44.0,
                             "main_temperature": 40.0, "abnormal_flag": 0})
        self.assertEqual(monitor.snapshot(0.1)["observability"], "valid")
        monitor.note_cloud(0.40, (10, 103000000), "innolidar", layout=layout)
        snapshot = monitor.snapshot(0.45)
        self.assertEqual(snapshot["topics"]["cloud"]["status"], "fresh")
        self.assertEqual(snapshot["topics"]["imu"]["status"], "stale")
        self.assertEqual(snapshot["observability"], "degraded")
        self.assertIn("imu_stale", snapshot["reason_codes"])
        snapshot = monitor.snapshot(1.1)
        self.assertEqual(snapshot["topics"]["cloud"]["status"], "stale")
        self.assertEqual(snapshot["observability"], "invalid")
        self.assertIn("cloud_stale", snapshot["reason_codes"])

    def test_missing_required_input_is_invalid_not_degraded(self):
        monitor = make_monitor()
        snapshot = monitor.snapshot(0.0)
        self.assertEqual(snapshot["topics"]["cloud"]["status"], "no_data")
        self.assertEqual(snapshot["observability"], "invalid")
        self.assertIn("cloud_no_data", snapshot["reason_codes"])
        self.assertIn("imu_no_data", snapshot["reason_codes"])

    def test_unexpected_frame_degrades_cloud(self):
        monitor = make_monitor(expected_cloud_frame="innolidar")
        monitor.note_cloud(0.0, (10, 0), "other", layout=valid_layout())
        monitor.note_imu(0.0, (10, 0), "innolidar", (0.0, 0.0, 9.8), (0.0, 0.0, 0.0),
                         (0.0, 0.0, 0.0, 1.0), True)
        monitor.note_device(0.0, (10, 0), "innolidar",
                            {"device_number": 71, "trx_temperature": 44.0,
                             "main_temperature": 40.0, "abnormal_flag": 0})
        snapshot = monitor.snapshot(0.1)
        self.assertEqual(snapshot["observability"], "degraded")
        self.assertIn("cloud_frame_unexpected", snapshot["reason_codes"])


class ImuTest(unittest.TestCase):
    def test_quaternion_unusable_cases(self):
        self.assertEqual(quaternion_report((0.0, 0.0, 0.0, 0.0)),
                         (False, "orientation_all_zero"))
        self.assertEqual(quaternion_report((2.0, 0.0, 0.0, 0.0)),
                         (False, "orientation_non_unit"))
        self.assertEqual(quaternion_report((float("nan"), 0.0, 0.0, 1.0)),
                         (False, "orientation_nonfinite"))
        self.assertEqual(quaternion_report((0.0, 0.0, 0.0, 1.0)), (True, None))
        self.assertEqual(quaternion_report((0.5, 0.5, 0.5, 0.5)), (True, None))

    def test_covariance_zero_checks_all_nine_entries(self):
        self.assertEqual(orientation_covariance_flags([0.0] * 9), (True, False))
        partly_nonzero = [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        self.assertEqual(orientation_covariance_flags(partly_nonzero), (False, False))
        self.assertEqual(orientation_covariance_flags([-1.0] + [0.0] * 8), (False, True))
        self.assertEqual(orientation_covariance_flags(None), (False, False))

    def test_orientation_not_provided_minus_one_is_unusable(self):
        monitor = make_monitor()
        monitor.note_imu(0.0, (10, 0), "innolidar", (0.0, 0.0, 9.8), (0.0, 0.0, 0.0),
                         (0.0, 0.0, 0.0, 1.0), False, orientation_not_provided=True)
        imu = monitor.snapshot(0.1)["topics"]["imu"]
        self.assertFalse(imu["orientation_usable"])
        self.assertEqual(imu["orientation_reason"], "orientation_not_provided")
        self.assertTrue(imu["orientation_not_provided"])
        self.assertFalse(imu["orientation_covariance_zero"])
        self.assertTrue(imu["measurements_finite"])
        monitor.note_imu(0.2, (10, 1), "innolidar", (0.0, 0.0, 9.8), (0.0, 0.0, 0.0),
                         (0.0, 0.0, 0.0, 1.0), True)
        imu = monitor.snapshot(0.3)["topics"]["imu"]
        self.assertTrue(imu["orientation_usable"])
        self.assertTrue(imu["orientation_covariance_zero"])

    def test_covariance_zero_and_abnormal_flag_are_not_overinterpreted(self):
        monitor = make_monitor()
        monitor.note_imu(0.0, (10, 0), "innolidar", (0.0, 0.0, 9.7), (0.0, 0.0, 0.0),
                         (0.0, 0.0, 0.0, 0.0), True)
        monitor.note_device(0.0, (10, 0), "innolidar",
                            {"device_number": 71, "trx_temperature": 44.375,
                             "main_temperature": 40.25, "abnormal_flag": 255})
        snapshot = monitor.snapshot(0.1)
        imu = snapshot["topics"]["imu"]
        self.assertTrue(imu["orientation_covariance_zero"])
        self.assertTrue(imu["measurements_finite"])
        self.assertEqual(imu["units_verified"], False)
        self.assertEqual(imu["alignment_verified"], False)
        self.assertEqual(imu["orientation_reason"], "orientation_all_zero")
        device = snapshot["topics"]["device_status"]
        self.assertEqual(device["abnormal_flag"], 255)
        self.assertEqual(device["abnormal_flag_semantics"], "unknown")
        self.assertIn("device_abnormal_flag_uninterpreted", snapshot["reason_codes"])
        self.assertIn("imu_units_unverified", snapshot["reason_codes"])

    def test_nonfinite_measurements_become_null_strict_json(self):
        monitor = make_monitor()
        monitor.note_cloud(0.0, (10, 0), "innolidar", layout=valid_layout(),
                           points={"total_points": 3, "nonfinite_points": 0, "zero_points": 0,
                                   "finite_nonzero_points": 3},
                           point_stamp={"first_s": 10.0, "last_s": 10.0, "span_s": 0.0},
                           header_equals_first=True)
        monitor.note_imu(0.0, (10, 0), "innolidar", (float("nan"), 0.0, float("inf")),
                         (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0), True)
        text = dumps_strict(monitor.snapshot(0.1))
        parsed = json.loads(text)
        self.assertIsNone(parsed["topics"]["imu"]["raw_acceleration"]["x"])
        self.assertIsNone(parsed["topics"]["imu"]["raw_acceleration"]["z"])
        self.assertFalse(parsed["topics"]["imu"]["measurements_finite"])
        self.assertIn("imu_measurement_nonfinite", parsed["reason_codes"])
        self.assertIn("orientation_unusable", parsed["reason_codes"])
        self.assertIsNone(parsed["normalized_stamp_s"])
        with self.assertRaises(ValueError):
            dumps_strict({"bad": float("nan")})


class ManifestTest(unittest.TestCase):
    def make_bag(self):
        return {"path": "/tmp/s.bag", "size_bytes": 1234, "readable": True,
                "sha256": "a" * 64,
                "summary": {"message_count": 5, "duration_s": 8.0, "start_time_s": 1.0,
                            "end_time_s": 9.0,
                            "topics": {"/innolidar_points": {"type": "sensor_msgs/PointCloud2",
                                                             "messages": 5,
                                                             "frequency": 0.6}}}}

    def make_kwargs(self):
        return dict(session_id="hf01_test", created_at_utc="2026-09-30T00:00:00+00:00",
                    requested_topics=["/innolidar_points", "/inno_imu"],
                    termination="duration", duration_requested_s=8.0, bag=self.make_bag(),
                    software={"package": "human_fall_detection", "version": "0.1.0"})

    def test_manifest_round_trip(self):
        manifest = build_manifest(**self.make_kwargs())
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["topics"][0]["name"], "/innolidar_points")
        self.assertEqual(manifest["topics"][0]["type"], "sensor_msgs/PointCloud2")
        self.assertEqual(manifest["source_time_domain"], "device_stamp_s_unanchored")
        self.assertFalse(manifest["sync"]["cross_stream_same_clock_verified"])
        self.assertFalse(manifest["units"]["imu_units_verified"])
        self.assertFalse(manifest["calibration"]["tf_available"])
        self.assertEqual(manifest["calibration"]["status"], "pending")
        self.assertIsNone(manifest["labels"]["path"])
        dumps_strict(manifest)

    def test_manifest_missing_or_invalid_fields_are_rejected(self):
        kwargs = self.make_kwargs()
        kwargs["bag"] = dict(self.make_bag())
        del kwargs["bag"]["sha256"]
        with self.assertRaisesRegex(ValueError, "bag.sha256"):
            build_manifest(**kwargs)
        kwargs = self.make_kwargs()
        kwargs["requested_topics"] = []
        with self.assertRaisesRegex(ValueError, "requested_topics"):
            build_manifest(**kwargs)
        kwargs = self.make_kwargs()
        kwargs["duration_requested_s"] = float("nan")
        with self.assertRaisesRegex(ValueError, "duration"):
            build_manifest(**kwargs)
        kwargs = self.make_kwargs()
        kwargs["software"] = {}
        with self.assertRaisesRegex(ValueError, "software"):
            build_manifest(**kwargs)

    def test_omitted_optional_objects_get_complete_defaults(self):
        manifest = build_manifest(**self.make_kwargs())
        self.assertEqual(set(manifest["sync"]), set(record_session.SYNC_KEYS))
        self.assertEqual(set(manifest["units"]), set(record_session.UNITS_KEYS))
        self.assertEqual(set(manifest["calibration"]),
                         {"tf_available", "status", "path", "sha256"})
        self.assertEqual(set(manifest["config"]), {"path", "sha256"})
        self.assertEqual(set(manifest["labels"]), {"path", "sha256"})
        self.assertEqual(manifest["labels"], {"path": None, "sha256": None})
        self.assertFalse(manifest["calibration"]["tf_available"])
        self.assertEqual(manifest["calibration"]["status"], "pending")
        dumps_strict(manifest)

    def test_nested_schema_incomplete_or_illegal_objects_are_rejected(self):
        cases = {
            "software missing version": {"software": {"package": "human_fall_detection"}},
            "software empty version": {"software": {"package": "human_fall_detection",
                                                     "version": ""}},
            "sync partial": {"sync": {"host_anchor_verified": False}},
            "sync non-bool": {"sync": {"cross_stream_same_clock_verified": 0,
                                       "host_anchor_verified": False}},
            "units partial": {"units": {"imu_units_verified": False}},
            "calibration partial": {"calibration": {"status": "pending"}},
            "calibration bad status": {"calibration": {"tf_available": False,
                                                       "status": "maybe",
                                                       "path": None, "sha256": None}},
            "calibration missing tf flag": {"calibration": {"status": "pending",
                                                            "path": None, "sha256": None}},
            "config partial": {"config": {"path": "/tmp/config.yaml"}},
            "labels partial": {"labels": {"path": "/tmp/labels.json"}},
        }
        for label, overrides in cases.items():
            with self.subTest(label):
                kwargs = self.make_kwargs()
                kwargs.update(overrides)
                with self.assertRaises(ValueError):
                    build_manifest(**kwargs)

    def test_bad_hash_summary_and_nonfinite_values_are_rejected(self):
        kwargs = self.make_kwargs()
        kwargs["bag"]["sha256"] = "ZZ"
        with self.assertRaisesRegex(ValueError, "bag.sha256"):
            build_manifest(**kwargs)
        kwargs = self.make_kwargs()
        kwargs["bag"]["summary"] = {}
        with self.assertRaisesRegex(ValueError, "bag.summary"):
            build_manifest(**kwargs)
        kwargs = self.make_kwargs()
        kwargs["bag"]["summary"]["topics"]["/innolidar_points"]["messages"] = -1
        with self.assertRaisesRegex(ValueError, "messages"):
            build_manifest(**kwargs)
        kwargs = self.make_kwargs()
        kwargs["bag"]["summary"]["topics"]["/innolidar_points"]["type"] = ""
        with self.assertRaisesRegex(ValueError, "type"):
            build_manifest(**kwargs)
        kwargs = self.make_kwargs()
        kwargs["bag"]["size_bytes"] = float("inf")
        with self.assertRaisesRegex(ValueError, "size_bytes"):
            build_manifest(**kwargs)
        kwargs = self.make_kwargs()
        kwargs["labels"] = {"path": "/tmp/labels.json", "sha256": "A" * 64}
        with self.assertRaisesRegex(ValueError, "labels.sha256"):
            build_manifest(**kwargs)
        kwargs = self.make_kwargs()
        kwargs["duration_requested_s"] = float("nan")
        with self.assertRaisesRegex(ValueError, "duration"):
            build_manifest(**kwargs)


class SessionReservationTest(unittest.TestCase):
    def test_existing_bag_active_or_manifest_blocks_before_recording(self):
        for suffix in (".bag", ".bag.active", ".manifest.json"):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as directory:
                sentinel = Path(directory) / ("taken" + suffix)
                sentinel.write_bytes(b"old data")
                with patch.object(record_session, "run_record") as recorder:
                    with self.assertRaises(SystemExit):
                        record_session.main(["--output-dir", directory,
                                             "--session-id", "taken", "--duration", "1"])
                recorder.assert_not_called()
                self.assertEqual(sentinel.read_bytes(), b"old data")

    def test_existing_manifest_is_not_rewritten_when_recorder_would_run(self):
        with tempfile.TemporaryDirectory() as directory:
            bag = Path(directory) / "existing.bag"
            manifest = Path(directory) / "existing.manifest.json"
            bag.write_bytes(b"old bag sentinel")
            manifest.write_text('{"old": true}', encoding="utf-8")
            with patch.object(record_session, "run_record") as recorder:
                with self.assertRaises(SystemExit):
                    record_session.main(["--output-dir", directory,
                                         "--session-id", "existing", "--duration", "1"])
            recorder.assert_not_called()
            self.assertEqual(bag.read_bytes(), b"old bag sentinel")
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8")), {"old": True})

    def test_session_reservation_is_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = record_session.reserve_session(directory, "once")
            self.assertTrue(Path(lock).exists())
            with self.assertRaises(FileExistsError):
                record_session.reserve_session(directory, "once")
            with patch.object(record_session, "run_record") as recorder:
                with self.assertRaises(SystemExit):
                    record_session.main(["--output-dir", directory,
                                         "--session-id", "once", "--duration", "1"])
            recorder.assert_not_called()

    def test_interrupted_run_records_sigint_and_keeps_requested_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            def fake_record(path, topics, duration):
                Path(path).write_bytes(b"synthetic bag")
                return 0, True

            summary = ManifestTest().make_bag()["summary"]
            with patch.object(record_session, "run_record", side_effect=fake_record):
                with patch.object(record_session, "read_bag_summary", return_value=summary):
                    result = record_session.main(["--output-dir", directory,
                                                  "--session-id", "interrupted",
                                                  "--duration", "10"])
            self.assertEqual(result, 130)
            manifest = json.loads((Path(directory) / "interrupted.manifest.json")
                                  .read_text(encoding="utf-8"))
            self.assertEqual(manifest["termination"], "sigint")
            self.assertEqual(manifest["duration_requested_s"], 10.0)
            self.assertTrue(manifest["bag"]["readable"])


class SnapshotConcurrencyTest(unittest.TestCase):
    def test_snapshot_never_mixes_new_stamp_with_old_layout(self):
        monitor = make_monitor()
        monitor.note_cloud(0.0, (10, 0), "innolidar", layout=valid_layout())
        updated = threading.Event()
        resume = threading.Event()
        original_note = monitor.cloud.note

        def paused_note(*args, **kwargs):
            result = original_note(*args, **kwargs)
            updated.set()
            if not resume.wait(3):
                raise RuntimeError("barrier timeout")
            return result

        monitor.cloud.note = paused_note
        invalid = copy.deepcopy(valid_layout())
        invalid.update(valid=False, errors=["truncated_data"])
        writer = threading.Thread(target=monitor.note_cloud,
                                  args=(0.1, (11, 0), "innolidar"), kwargs={"layout": invalid})
        payloads = []
        snapshot_done = threading.Event()

        def take_snapshot():
            payloads.append(monitor.snapshot(0.2))
            snapshot_done.set()

        reader = threading.Thread(target=take_snapshot)
        writer.start()
        try:
            self.assertTrue(updated.wait(3), "writer did not reach the barrier")
            reader.start()
            escaped = snapshot_done.wait(0.1)
        finally:
            resume.set()
            writer.join(3)
            reader.join(3)
        self.assertFalse(escaped, "snapshot escaped while a frame update was in flight")
        self.assertTrue(snapshot_done.is_set())
        cloud = payloads[0]["topics"]["cloud"]
        self.assertFalse(cloud["source_stamp_s"] == 11.0 and cloud["layout"]["valid"],
                         "new stamp and previous frame's valid layout were published together")


if __name__ == "__main__":
    unittest.main()
