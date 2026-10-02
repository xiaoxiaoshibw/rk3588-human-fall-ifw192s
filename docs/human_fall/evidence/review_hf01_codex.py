"""HF-01 independent review checks; failures document required rework.

Run from the repository root: python -B -W error docs/human_fall/evidence/review_hf01_codex.py
Synthetic checks only. No ROS processes, hardware changes, or real bags are used.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/human_fall_detection/scripts"))
sys.path.insert(0, str(ROOT / "src/human_fall_detection/tests"))
import record_session
import test_hf01_health as fixtures


class IndependentReview(unittest.TestCase):
    def test_invalid_current_stamp_does_not_reuse_previous_source_stamp(self):
        monitor = fixtures.make_monitor()
        monitor.note_cloud(0.0, (10, 0), "innolidar", layout=fixtures.valid_layout())
        monitor.note_cloud(0.1, (0, 0), "innolidar", layout=fixtures.valid_layout())
        topic = monitor.snapshot(0.2)["topics"]["cloud"]
        self.assertEqual(topic["stamp_status"], "invalid")
        self.assertIsNone(topic["source_stamp_s"], "current invalid stamp silently became 10.0")

    def test_snapshot_cannot_publish_new_stamp_with_previous_valid_layout(self):
        monitor = fixtures.make_monitor()
        monitor.note_cloud(0.0, (10, 0), "innolidar", layout=fixtures.valid_layout())
        monitor.note_imu(0.0, (10, 0), "innolidar", (0, 0, 9.8), (0, 0, 0), (0, 0, 0, 1), True)
        monitor.note_device(0.0, (10, 0), "innolidar", {})
        updated = threading.Event()
        resume = threading.Event()
        original_note = monitor.cloud.note

        def paused_note(*args, **kwargs):
            result = original_note(*args, **kwargs)
            updated.set()
            if not resume.wait(3):
                raise RuntimeError("review barrier timeout")
            return result

        monitor.cloud.note = paused_note
        invalid = copy.deepcopy(fixtures.valid_layout())
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
            self.assertTrue(updated.wait(3))
            reader.start()
            snapshot_done.wait(0.1)
        finally:
            resume.set()
            writer.join(3)
            if reader.ident is not None:
                reader.join(3)
        self.assertTrue(snapshot_done.is_set())
        cloud = payloads[0]["topics"]["cloud"]
        self.assertFalse(cloud["source_stamp_s"] == 11.0 and cloud["layout"]["valid"],
                         "new stamp and previous frame's valid layout were published together")

    def test_manifest_rejects_missing_software_version(self):
        kwargs = fixtures.ManifestTest().make_kwargs()
        kwargs["software"] = {"package": "human_fall_detection"}
        with self.assertRaises(ValueError):
            record_session.build_manifest(**kwargs)

    def test_manifest_rejects_incomplete_sync_and_calibration(self):
        for key, value in (("sync", {"host_anchor_verified": False}),
                           ("calibration", {"status": "pending"}),
                           ("config", {"path": "/tmp/config.yaml"})):
            with self.subTest(key=key):
                kwargs = fixtures.ManifestTest().make_kwargs()
                kwargs[key] = value
                with self.assertRaises(ValueError):
                    record_session.build_manifest(**kwargs)

    def test_existing_session_is_rejected_before_starting_recorder(self):
        with tempfile.TemporaryDirectory() as directory:
            bag = Path(directory) / "existing.bag"
            manifest = Path(directory) / "existing.manifest.json"
            bag.write_bytes(b"old bag sentinel")
            manifest.write_text('{"old": true}', encoding="utf-8")
            summary = fixtures.ManifestTest().make_bag()["summary"]

            def fake_record(path, topics, duration):
                # Model rosbag's write path on task-owned temporary data only.
                Path(path).write_bytes(b"replacement bag")
                return 0, False

            with patch.object(record_session, "run_record", side_effect=fake_record) as recorder:
                with patch.object(record_session, "read_bag_summary", return_value=summary):
                    try:
                        record_session.main(["--output-dir", directory, "--session-id", "existing",
                                             "--duration", "1"])
                    except (SystemExit, ValueError, FileExistsError):
                        pass
            self.assertEqual(recorder.call_count, 0, "existing bag/manifest were not protected")
            self.assertEqual(bag.read_bytes(), b"old bag sentinel")
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8")), {"old": True})

    def test_ctrl_c_reports_actual_sigint_termination(self):
        with tempfile.TemporaryDirectory() as directory:
            def fake_record(path, topics, duration):
                Path(path).write_bytes(b"synthetic bag")
                return 0, True

            with patch.object(record_session, "run_record", side_effect=fake_record):
                with patch.object(record_session, "read_bag_summary",
                                  return_value=fixtures.ManifestTest().make_bag()["summary"]):
                    result = record_session.main(["--output-dir", directory, "--session-id", "interrupted",
                                                  "--duration", "10"])
            self.assertEqual(result, 130)
            manifest = json.loads((Path(directory) / "interrupted.manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["termination"], "sigint", "early Ctrl-C was recorded as duration")


if __name__ == "__main__":
    unittest.main(verbosity=2)
