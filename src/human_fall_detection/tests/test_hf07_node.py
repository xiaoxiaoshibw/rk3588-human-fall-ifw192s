"""HF-07 node runtime tests: queue, event log, merged state, selection, baseline.

No ROS here: the pure ``core.node_runtime`` layer is exercised directly, which is
the same object the ROS node drives. Synthetic point clouds are explicitly
synthetic geometry, never a real human-fall acceptance.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))

from core.node_runtime import (EventLog, FallNodeCore, LatestFrameQueue,
                               dumps_strict, frame_age_exceeded)
from human_fall_node import build_core

VALID_GROUND = {
    "kind": "ground_plane", "status": "valid", "valid": True, "reason": None,
    "frame": "innolidar", "normal": [0.0, 0.0, 1.0], "offset_m": 1.5,
    "sensor_height_m": 1.5,
    "holdout_residual": {"count": 30, "rms_m": 0.01, "max_m": 0.03},
    "holdout_support": {"count": 30, "rms_m": 0.01, "max_m": 0.03, "fraction": 0.8},
    "valid_region": {"x_min_m": 0.0, "x_max_m": 6.0, "y_min_m": -2.0,
                     "y_max_m": 2.0, "z_min_m": -1.6, "z_max_m": 0.6,
                     "range_min_m": 0.8, "range_max_m": 8.0, "point_count": 100},
}


def standing_person(x=3.0, y=0.0, count=80, bottom=-1.4, top=0.1):
    z = np.linspace(bottom, top, count)
    x += np.zeros(count)
    y += np.zeros(count)
    return np.column_stack((x, y, z))


def settings():
    return {
        "candidates": {"min_cluster_points": 20, "preferred_cluster_points": 30},
        "tracking": {"occlusion_timeout_s": 1.5, "lost_timeout_s": 3.0},
        "fall": {"mode_verified": False, "allow_confirmed": False},
    }


def stamp_for(index, base=100.0, step=0.2):
    value = base + step * index
    secs = int(value)
    nsecs = int(round((value - secs) * 1e9))
    return secs, nsecs


def _strict_json(payload):
    text = dumps_strict(payload)

    def _no_constant(value):  # pragma: no cover - only on failure
        raise AssertionError("non-finite JSON constant: " + value)

    return json.loads(text, parse_constant=_no_constant)


class LatestFrameQueueTest(unittest.TestCase):
    def test_keeps_only_latest(self):
        queue = LatestFrameQueue(1)
        queue.put("a")
        queue.put("b")
        self.assertGreaterEqual(queue.dropped, 1)
        self.assertEqual(queue.take(), "b")
        self.assertIsNone(queue.take())

    def test_wake_without_item(self):
        queue = LatestFrameQueue(1)
        queue.wake()
        self.assertTrue(queue.wait(0.01))
        self.assertIsNone(queue.take())


class EventLogTest(unittest.TestCase):
    def test_deduplicate_and_no_replay_after_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "events.jsonl")
            event = {"event_id": "fall:s:1", "kind": "fall_event"}
            log = EventLog(path)
            persisted, reason = log.append(event)
            self.assertTrue(persisted)
            self.assertIsNone(reason)
            persisted, reason = log.append(event)
            self.assertFalse(persisted)
            self.assertEqual(reason, "duplicate")
            reloaded = EventLog(path)
            self.assertTrue(reloaded.has("fall:s:1"))
            self.assertEqual(len(reloaded.recent), 1)
            # A reloaded event is history, never reported as new.
            self.assertEqual(reloaded.report()["persisted_count"], 1)

    def test_disk_failure_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            blocker = os.path.join(directory, "blocker")
            with open(blocker, "w", encoding="utf-8") as handle:
                handle.write("x")
            log = EventLog(os.path.join(blocker, "sub", "events.jsonl"))
            persisted, reason = log.append({"event_id": "fall:s:1"})
            self.assertFalse(persisted)
            self.assertIsNotNone(reason)
            self.assertTrue(log.degraded)
            self.assertIsNotNone(log.report()["reason"])


class FallNodeCoreTest(unittest.TestCase):
    def _core(self, ground=VALID_GROUND, event_path=None):
        return FallNodeCore("s1", settings(), ground=ground, event_path=event_path,
                            expected_frame="innolidar")

    def _frame(self, core, receive, seq, stamp, points=None):
        return core.process(points if points is not None else standing_person(),
                            receive, seq=seq, stamp_secs=stamp[0],
                            stamp_nsecs=stamp[1], frame_id="innolidar", now=receive)

    def test_process_publishes_candidates_and_merged_state(self):
        core = self._core()
        result = self._frame(core, 1.0, 1, (100, 0))
        self.assertEqual(result["snapshot"]["kind"], "candidate_snapshot")
        self.assertGreaterEqual(len(result["snapshot"]["candidates"]), 1)
        state = result["state"]
        self.assertEqual(state["kind"], "target_state")
        self.assertIn(state["fall_status"], ("unknown", "low_posture_unclassified"))
        self.assertEqual(state["method"], "lidar_geometry")
        self.assertEqual(state["observability"], "valid")
        _strict_json(state)
        _strict_json(result["snapshot"])

    def test_no_ground_degrades_and_stays_unknown(self):
        core = self._core(ground=None)
        result = self._frame(core, 1.0, 1, (100, 0))
        self.assertEqual(result["state"]["observability"], "degraded")
        self.assertIn("ground_unavailable", result["state"]["reason_codes"])
        self.assertNotEqual(result["state"]["fall_status"], "confirmed")

    def test_illegal_stamp_changes_epoch(self):
        core = self._core()
        first = self._frame(core, 1.0, 1, (100, 0))
        self.assertEqual(first["state"]["time_epoch"], 0)
        second = self._frame(core, 1.2, 2, (99, 0))  # source time regressed
        self.assertEqual(second["state"]["time_epoch"], 1)

    def test_undecodable_frame_is_invalid_not_normal(self):
        core = self._core()
        result = core.process(None, 1.0, seq=1, stamp_secs=100, stamp_nsecs=0,
                              frame_id="innolidar")
        self.assertIsNone(result["snapshot"])
        self.assertEqual(result["state"]["observability"], "invalid")

    def _select(self, core, result, version=0):
        snapshot = result["snapshot"]
        candidate_id = snapshot["candidates"][0]["candidate_id"]
        request = {"schema_version": 1, "request_id": "r1", "action": "select",
                   "session_id": "s1", "time_epoch": result["state"]["time_epoch"],
                   "snapshot_id": snapshot["snapshot_id"],
                   "candidate_id": candidate_id, "selection_version": version}
        latest = core._last_state or result["state"]
        receive = (latest.get("time_received_s") or 1.0) + 0.01
        return core.handle_request(request, receive)

    def test_selection_ack_and_idempotent_replay(self):
        core = self._core()
        result = self._frame(core, 1.0, 1, (100, 0))
        ack = self._select(core, result)
        self.assertTrue(ack["accepted"])
        self.assertEqual(ack["kind"], "selection_ack")
        self.assertIsNotNone(ack["track_id"])
        replay = self._select(core, result)
        self.assertTrue(replay["accepted"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["request_id"], ack["request_id"])

    def test_stale_snapshot_rejected(self):
        core = self._core()
        result = self._frame(core, 1.0, 1, (100, 0))
        snapshot = result["snapshot"]
        request = {"schema_version": 1, "request_id": "r2", "action": "select",
                   "session_id": "s1", "time_epoch": 0,
                   "snapshot_id": snapshot["snapshot_id"],
                   "candidate_id": snapshot["candidates"][0]["candidate_id"],
                   "selection_version": 0}
        ack = core.handle_request(request, 10.0)  # required input also long stale
        self.assertFalse(ack["accepted"])
        # The required-cloud gate fires before the snapshot TTL; both are valid
        # rejections of a request against an old frame.
        self.assertIn(ack["reason"], ("stale_snapshot", "cloud_stale"))

    def test_epoch_mismatch_rejected(self):
        core = self._core()
        result = self._frame(core, 1.0, 1, (100, 0))
        snapshot = result["snapshot"]
        request = {"schema_version": 1, "request_id": "r3", "action": "select",
                   "session_id": "s1", "time_epoch": 5,
                   "snapshot_id": snapshot["snapshot_id"],
                   "candidate_id": snapshot["candidates"][0]["candidate_id"],
                   "selection_version": 0}
        ack = core.handle_request(request, 1.05)
        self.assertFalse(ack["accepted"])
        self.assertEqual(ack["reason"], "epoch_mismatch")

    def test_malformed_request_is_explicit(self):
        core = self._core()
        ack = core.handle_request(None, 1.0)
        self.assertFalse(ack["accepted"])
        self.assertEqual(ack["reason"], "malformed_request")

    def test_release_allowed_after_required_cloud_stalls(self):
        core = self._core()
        result = self._frame(core, 1.0, 0, stamp_for(0))
        ack = self._select(core, result)
        self.assertTrue(ack["accepted"])
        release = {"schema_version": 1, "request_id": "rel1", "action": "release",
                   "session_id": "s1", "time_epoch": 0,
                   "track_id": ack["track_id"], "selection_version": 1}
        got = core.handle_request(release, 30.0)  # far past cloud_stale
        self.assertTrue(got["accepted"], got)

    def test_auxiliary_device_repeat_keeps_cloud_epoch(self):
        core = self._core()
        self._frame(core, 1.0, 0, stamp_for(0))
        core.note_device(1.05, (50, 0), "innolidar")
        core.note_device(1.06, (50, 0), "innolidar")  # repeated aux stamp
        result = self._frame(core, 1.1, 1, stamp_for(1))
        self.assertEqual(result["state"]["time_epoch"], 0)
        ack = self._select(core, result)
        self.assertTrue(ack["accepted"], ack)

    def test_candidate_unique_continuity_accepted(self):
        core = self._core()
        first = self._frame(core, 1.0, 0, stamp_for(0))
        # Same person shifted slightly (< tracking gate) in the next frame.
        self._frame(core, 1.1, 1, stamp_for(1), points=standing_person(x=3.05))
        ack = self._select(core, first)  # references the older snapshot
        self.assertTrue(ack["accepted"], ack)

    def test_event_log_rejects_nonserializable_event(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "events.jsonl")
            log = EventLog(path)
            persisted, reason = log.append({"event_id": "e1", "bad": float("nan")})
            self.assertFalse(persisted)
            self.assertIsNotNone(reason)
            self.assertTrue(log.degraded)
            self.assertEqual(log.report()["recent_count"], 0)  # not queued
            persisted, reason = log.append({"event_id": "e2", "kind": "fall_event"})
            self.assertTrue(persisted, reason)

    def test_release_clears_current_geometry(self):
        core = self._core()
        result = self._frame(core, 1.0, 0, stamp_for(0))
        ack = self._select(core, result)
        self.assertTrue(ack["accepted"])
        release = {"schema_version": 1, "request_id": "rel", "action": "release",
                   "session_id": "s1", "time_epoch": 0,
                   "track_id": ack["track_id"], "selection_version": 1}
        got = core.handle_request(release, 1.05)
        self.assertTrue(got["accepted"], got)
        after = self._frame(core, 1.1, 1, stamp_for(1))
        state = after["state"]
        self.assertIsNone(state["track_id"])
        self.assertEqual(state["track_status"], "unselected")
        self.assertIsNone(state["position_source_m"])
        self.assertIsNone(state["bbox_source_min_m"])
        self.assertIsNone(state["bbox_source_max_m"])
        self.assertIsNone(state["range_m"])
        self.assertFalse(state["position_predicted"])

    def test_ground_only_derives_version_and_reaches_upright(self):
        sections = dict(settings())
        sections["baseline"] = {"require_seconds": 0.2, "max_duration_s": 1.0,
                                "min_samples": 3}
        core = FallNodeCore("s1", sections, ground=VALID_GROUND,
                            expected_frame="innolidar")
        self.assertTrue(str(core.calibration.get("calibration_id", "")).startswith("ground-only-"))
        first = self._frame(core, 1.0, 0, stamp_for(0))
        selected = self._select(core, first)
        self.assertTrue(selected["accepted"], selected)
        self._frame(core, 1.1, 1, stamp_for(1))
        capture = {"schema_version": 1, "request_id": "b1",
                   "action": "capture_baseline", "session_id": "s1",
                   "time_epoch": 0, "track_id": selected["track_id"],
                   "selection_version": 1, "operator_confirmed": False}
        ack = core.handle_request(capture, 1.15)
        self.assertTrue(ack["accepted"], ack)
        result = None
        for index in range(2, 9):
            result = self._frame(core, 1.0 + 0.1 * index, index, stamp_for(index))
        self.assertEqual(core.baseline.status, "ready", core.baseline.snapshot())
        self.assertEqual(result["state"]["fall_status"], "upright", result["state"])

    def test_baseline_completion_ack(self):
        core = self._core()
        result = self._frame(core, 1.0, 0, stamp_for(0))
        select_ack = self._select(core, result)
        self.assertTrue(select_ack["accepted"])
        self._frame(core, 1.1, 1, stamp_for(1))  # lock to the candidate
        capture = {"schema_version": 1, "request_id": "b1",
                   "action": "capture_baseline", "session_id": "s1",
                   "time_epoch": result["state"]["time_epoch"],
                   "track_id": select_ack["track_id"], "selection_version": 1,
                   "operator_confirmed": True}
        ack = core.handle_request(capture, 1.15)
        self.assertTrue(ack["accepted"])
        self.assertEqual(ack["baseline"]["status"], "pending")
        completion = None
        for index in range(2, 30):
            receive = 1.0 + 0.2 * index
            step = self._frame(core, receive, index, stamp_for(index))
            if step["baseline_ack"] is not None:
                completion = step["baseline_ack"]
                break
        self.assertIsNotNone(completion, "baseline never completed")
        self.assertTrue(completion["accepted"])
        self.assertEqual(completion["baseline"]["status"], "ready")
        self.assertEqual(completion["request_id"], "b1")


class RosProjectionTest(unittest.TestCase):
    def test_projection_drops_evidence_without_mutating_algorithm_snapshot(self):
        from core.node_runtime import project_snapshot_for_ros
        core = FallNodeCore("s1", settings(), ground=VALID_GROUND,
                            expected_frame="innolidar")
        result = core.process(standing_person(), 1.0, seq=1, stamp_secs=100,
                              stamp_nsecs=0, frame_id="innolidar", now=1.0)
        snap = result["snapshot"]
        self.assertTrue(snap["candidates"])
        self.assertIn("evidence_indices", snap["candidates"][0])
        original_json = dumps_strict(snap)
        projected = project_snapshot_for_ros(snap)
        self.assertIsNot(projected, snap)
        self.assertIn("evidence_indices", snap["candidates"][0])   # not mutated
        self.assertNotIn("evidence_indices", projected["candidates"][0])
        for field in ("candidate_id", "center_source_m", "bbox_source_min_m",
                      "bbox_source_max_m", "point_count", "quality"):
            self.assertEqual(projected["candidates"][0][field],
                             snap["candidates"][0][field])
        for field in ("session_id", "time_epoch", "snapshot_id", "source",
                      "coordinate", "calibration"):
            self.assertEqual(projected[field], snap[field])
        self.assertEqual(dumps_strict(snap), original_json)        # unchanged
        self.assertLess(len(dumps_strict(projected)), len(original_json))


class StalledStreamWatchdogTest(unittest.TestCase):
    """HF09: a stale/absent required stream must not publish a green last state."""

    def _core(self):
        return FallNodeCore("s1", settings(), ground=VALID_GROUND,
                            expected_frame="innolidar")

    def test_before_first_frame_fall_state_is_unknown(self):
        state = self._core().status_state(10.0)
        self.assertEqual(state["observability"], "invalid")
        self.assertEqual(state["fall_status"], "unknown")

    def test_stale_stream_hides_last_measured_geometry(self):
        core = self._core()
        result = core.process(standing_person(), 1.0, seq=0, stamp_secs=100,
                              stamp_nsecs=0, frame_id="innolidar", now=1.0)
        candidate_id = result["snapshot"]["candidates"][0]["candidate_id"]
        select = {"schema_version": 1, "request_id": "r1", "action": "select",
                  "session_id": "s1", "time_epoch": 0,
                  "snapshot_id": result["snapshot"]["snapshot_id"],
                  "candidate_id": candidate_id, "selection_version": 0}
        self.assertTrue(core.handle_request(select, 1.01)["accepted"])
        result = core.process(standing_person(), 1.1, seq=1, stamp_secs=100,
                              stamp_nsecs=100000000, frame_id="innolidar", now=1.1)
        self.assertIsNotNone(result["state"]["position_source_m"])
        # No further frame; the required stream is now stale.
        state = core.status_state(5.0)
        self.assertEqual(state["observability"], "invalid")
        self.assertEqual(state["fall_status"], "unknown")
        self.assertIsNone(state["position_source_m"])
        self.assertIsNone(state["range_m"])
        self.assertIsNone(state["bbox_source_min_m"])
        self.assertFalse(state["target_features"]["observable"])
        self.assertEqual(state["fall_state"]["fall_status"], "unknown")


class NodeClockBoundaryTest(unittest.TestCase):
    """HF09: injectable-clock boundaries for the ROS adapter (no ROS needed)."""

    def test_build_core_always_monotonic_even_with_replay_flag(self):
        config = {"mode": {"replay": True}, "topics": {}, "timeouts_s": {},
                  "stamps": {}, "checks": {}, "geometry": {}, "output": {}}
        core = build_core(config, settings(), session_id="s1",
                          config_dir=tempfile.gettempdir(), event_path=None)
        self.assertEqual(core.clock_domain, "monotonic")

    def test_frame_age_exceeded_is_injectable(self):
        self.assertFalse(frame_age_exceeded(10.0, 10.5, 0.6))
        self.assertTrue(frame_age_exceeded(10.0, 10.7, 0.6))
        self.assertTrue(frame_age_exceeded(None, 10.0, 0.6))

    def test_request_uses_post_lock_clock(self):
        core = FallNodeCore("s1", settings(), ground=VALID_GROUND)
        core.process(standing_person(), 1.0, seq=1, stamp_secs=100,
                     stamp_nsecs=0, frame_id="innolidar", now=1.0)
        snapshot = core._latest_valid_snapshot
        request = {"schema_version": 1, "request_id": "r", "action": "select",
                   "session_id": "s1", "time_epoch": 0,
                   "snapshot_id": snapshot["snapshot_id"],
                   "candidate_id": snapshot["candidates"][0]["candidate_id"],
                   "selection_version": 0}
        # Pre-wait arrival looks fresh, but the real post-lock handling time is stale.
        stale = core.handle_request(request, 1.05, now_fn=lambda: 100.0)
        self.assertFalse(stale["accepted"])
        self.assertEqual(stale["reason"], "cloud_stale")
        # And a stale arrival time must not reject a genuinely fresh handling time.
        fresh = core.handle_request(request, 100.0, now_fn=lambda: 1.05)
        self.assertTrue(fresh["accepted"], fresh)


if __name__ == "__main__":
    unittest.main()
