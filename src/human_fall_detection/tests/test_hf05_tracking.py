import sys
import unittest
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))

from core.association import associate_tracks
from core.baseline import StanceBaselineCollector
from core.selection import (REASON_CONFLICT, REASON_EPOCH_MISMATCH,
                            REASON_INSUFFICIENT_QUALITY, REASON_NOT_LOCKED,
                            REASON_STALE_SNAPSHOT, REASON_STALE_VERSION,
                            REASON_UNKNOWN_CANDIDATE, SelectionBackend)
from core.tracking import TargetTracker
from sensor_health import dumps_strict


def candidate(candidate_id, position, size=0.5, points=200, sufficient=True):
    return {
        "candidate_id": candidate_id,
        "semantic": "unknown",
        "center_source_m": list(position),
        "center_reference_m": list(position),
        "position_m": list(position),
        "bbox_source_min_m": [position[0] - 0.2, position[1] - 0.2, position[2] - 0.2],
        "bbox_source_max_m": [position[0] + 0.2, position[1] + 0.2, position[2] + 0.2],
        "horizontal_extent_m": {"u": size, "v": size, "max": size},
        "point_count": points,
        "quality": {"sufficient_points": sufficient, "reasons": []},
    }


def snapshot(time_epoch=0, snapshot_id="s1", candidates=None, source_stamp_s=10.0):
    return {"kind": "candidate_snapshot", "schema_version": 1, "session_id": "hf05",
            "time_epoch": time_epoch, "snapshot_id": snapshot_id,
            "source": {"source_stamp_s": source_stamp_s},
            "calibration": {"calibration_id": "cal1"},
            "candidates": candidates or [], "quality": {}}


def select_request(request_id="r1", version=0, **overrides):
    request = {"schema_version": 1, "request_id": request_id, "action": "select",
               "session_id": "hf05", "time_epoch": 0, "snapshot_id": "s1",
               "candidate_id": "c0000", "selection_version": version,
               "calibration_version": "cal1"}
    request.update(overrides)
    return request


class AssociationTest(unittest.TestCase):
    def test_two_close_candidates_are_ambiguous_not_resolved(self):
        result = associate_tracks(
            [{"track_id": "t1", "position_m": [0.0, 0.0, 0.0], "size_m": None}],
            [candidate("c0", [0.05, 0.0, 0.0]), candidate("c1", [0.15, 0.0, 0.0])],
            settings={"ambiguity_margin_m": 0.2})
        self.assertEqual(result["matches"], [])
        self.assertIn("t1", result["ambiguous_track_ids"])
        self.assertEqual(result["ambiguous_candidate_ids"], ["c0", "c1"])

    def test_two_tracks_competing_for_one_candidate_are_both_ambiguous(self):
        result = associate_tracks(
            [{"track_id": "t1", "position_m": [0.0, 0.0, 0.0], "size_m": None},
             {"track_id": "t2", "position_m": [0.1, 0.0, 0.0], "size_m": None}],
            [candidate("c0", [0.05, 0.0, 0.0])])
        self.assertEqual(result["matches"], [])
        self.assertEqual(sorted(result["ambiguous_track_ids"]), ["t1", "t2"])

    def test_out_of_gate_candidate_is_unmatched(self):
        result = associate_tracks(
            [{"track_id": "t1", "position_m": [0.0, 0.0, 0.0], "size_m": None}],
            [candidate("c0", [3.0, 0.0, 0.0])])
        self.assertEqual(result["unmatched_track_ids"], ["t1"])
        self.assertEqual(result["unmatched_candidate_ids"], ["c0"])


class TrackerTest(unittest.TestCase):
    def _locked(self, **settings):
        tracker = TargetTracker("hf05", settings)
        tracker.select("t0001", 0, candidate=candidate("c0000", [3.0, 0.0, 0.0]),
                       calibration_version="cal1", selection_version=1,
                       source_stamp_s=1.0, receive_s=1.0)
        return tracker

    def test_pose_size_jump_does_not_swap_the_person(self):
        tracker = self._locked()
        same_person = candidate("c0100", [3.05, 0.0, 0.0], size=1.8)
        other_person = candidate("c0101", [6.0, 0.0, 0.0], size=0.5)
        state = tracker.update([same_person, other_person], 0,
                               source_stamp_s=1.2, receive_s=1.2)
        self.assertEqual(tracker.track_id, "t0001")
        self.assertEqual(state["track_status"], "locked")
        self.assertEqual(state["candidate_id"], "c0100")
        self.assertFalse(state["position_predicted"])

    def test_ambiguous_pair_requires_reselection_and_resets_history(self):
        tracker = self._locked()
        generation = tracker.action_generation
        state = tracker.update([candidate("c0200", [3.05, 0.0, 0.0]),
                                candidate("c0201", [3.15, 0.0, 0.0])], 0,
                               source_stamp_s=1.2, receive_s=1.2)
        self.assertEqual(state["track_status"], "ambiguous")
        self.assertTrue(state["requires_reselection"])
        self.assertGreater(tracker.action_generation, generation)
        self.assertEqual(state["history_reset_reason"], "ambiguous")

    def test_prediction_is_flagged_and_adds_no_action_history(self):
        tracker = self._locked()
        history = list(tracker.action_history)
        state = tracker.update([], 0, receive_s=1.2)
        self.assertEqual(state["track_status"], "occluded")
        self.assertTrue(state["position_predicted"])
        self.assertEqual(list(tracker.action_history), history)

    def test_long_occlusion_becomes_lost_and_resets(self):
        tracker = self._locked()
        tracker.update([], 0, receive_s=1.2)
        generation = tracker.action_generation
        state = tracker.update([], 0, receive_s=5.0)
        self.assertEqual(state["track_status"], "lost")
        self.assertTrue(state["requires_reselection"])
        self.assertGreater(tracker.action_generation, generation)
        self.assertEqual(state["history_reset_reason"], "lost_timeout")

    def test_epoch_change_resets_to_lost(self):
        tracker = self._locked()
        generation = tracker.action_generation
        state = tracker.note_epoch(1) or tracker.snapshot()
        self.assertEqual(state["track_status"], "lost")
        self.assertGreater(tracker.action_generation, generation)
        self.assertEqual(state["history_reset_reason"], "time_epoch_changed")

    def test_reselecting_a_new_target_increments_history_generation(self):
        tracker = self._locked()
        generation = tracker.action_generation
        tracker.select("t0002", 0, candidate=candidate("c0300", [5.0, 0.0, 0.0]),
                       selection_version=2)
        self.assertGreater(tracker.action_generation, generation)
        self.assertEqual(tracker.track_id, "t0002")
        self.assertEqual(tracker.history_reset_reason, "operator_select")

    def test_prediction_is_anchored_at_last_measurement(self):
        tracker = self._locked()
        tracker.update([candidate("c0100", [3.5, 0.0, 0.0])], 0,
                       source_stamp_s=2.0, receive_s=2.0)
        tracker.update([], 0, source_stamp_s=2.5, receive_s=2.5)
        state = tracker.update([], 0, source_stamp_s=3.0, receive_s=3.0)
        self.assertAlmostEqual(state["position_m"][0], 4.0, places=6)
        self.assertTrue(state["position_predicted"])

    def test_lost_timeout_is_checked_before_association(self):
        tracker = self._locked()
        state = tracker.update([candidate("c0200", [3.05, 0.0, 0.0])], 0,
                               source_stamp_s=10.0, receive_s=10.0)
        self.assertNotEqual(state["track_status"], "locked")
        self.assertTrue(state["requires_reselection"])
        self.assertEqual(state["history_reset_reason"], "lost_timeout")

    def test_invalid_current_receive_does_not_switch_clock_domain(self):
        for bad in (float("nan"), float("inf")):
            with self.subTest(bad=bad):
                tracker = TargetTracker("hf05")
                tracker.select("t0001", 0, candidate=candidate("c0000", [3.0, 0.0, 0.0]),
                               source_stamp_s=100.0, receive_s=10.0)
                state = tracker.update([candidate("c0100", [3.2, 0.0, 0.0])], 0,
                                       source_stamp_s=100.1, receive_s=bad)
                self.assertTrue(state["position_predicted"]
                                or state["track_status"] != "locked")
                self.assertEqual(state["last_measured_source_s"], 100.0)
                self.assertEqual(state["clock_reason"], "current_invalid")

    def test_clock_regression_is_not_treated_as_zero_dt(self):
        tracker = self._locked()
        state = tracker.update([candidate("c0300", [3.05, 0.0, 0.0])], 0,
                               source_stamp_s=0.5, receive_s=0.5)
        self.assertEqual(state["track_status"], "lost")
        self.assertEqual(state["history_reset_reason"], "clock_regressed")

    def test_state_is_strict_json(self):
        state = self._locked().snapshot()
        text = dumps_strict(state)
        self.assertNotIn("NaN", text)


class SelectionBackendTest(unittest.TestCase):
    def _backend(self, **settings):
        tracker = TargetTracker("hf05")
        backend = SelectionBackend("hf05", tracker, settings=settings)
        backend.register_snapshot(snapshot(candidates=[candidate("c0000", [3.0, 0.0, 0.0])]),
                                  receive_s=10.0)
        return backend, tracker

    def test_select_ack_is_authoritative_and_idempotent(self):
        backend, tracker = self._backend()
        first = backend.handle(select_request(), receive_s=10.0)
        self.assertTrue(first["accepted"])
        self.assertEqual(first["track_id"], "t0001")
        self.assertEqual(first["selection_version"], 1)
        replay = backend.handle(select_request(), receive_s=10.0)
        self.assertTrue(replay["accepted"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["track_id"], "t0001")
        self.assertEqual(tracker.track_id, "t0001")

    def test_same_request_id_different_content_is_conflict(self):
        backend, tracker = self._backend()
        backend.handle(select_request(), receive_s=10.0)
        conflict = backend.handle(select_request(candidate_id="c9999"), receive_s=10.0)
        self.assertFalse(conflict["accepted"])
        self.assertEqual(conflict["reason"], REASON_CONFLICT)
        self.assertEqual(tracker.track_id, "t0001")

    def test_stale_snapshot_rejected(self):
        backend, tracker = self._backend()
        stale = backend.handle(select_request(request_id="r2"), receive_s=13.0)
        self.assertEqual(stale["reason"], REASON_STALE_SNAPSHOT)

    def test_cross_epoch_and_old_version_rejected(self):
        backend, tracker = self._backend(snapshot_ttl_s=100.0)
        first = backend.handle(select_request(request_id="r3"), receive_s=10.0)
        self.assertTrue(first["accepted"])
        old = backend.handle({"schema_version": 1, "request_id": "r5",
                              "action": "release", "session_id": "hf05",
                              "time_epoch": 0, "selection_version": 0},
                             receive_s=10.1)
        self.assertEqual(old["reason"], REASON_STALE_VERSION)
        epoch = backend.handle(select_request(request_id="r6", time_epoch=1, version=1),
                               receive_s=10.2)
        self.assertEqual(epoch["reason"], REASON_EPOCH_MISMATCH)

    def test_unknown_candidate_and_poor_quality_rejected(self):
        backend, tracker = self._backend()
        unknown = backend.handle(select_request(request_id="r6", candidate_id="nope"),
                                 receive_s=10.0)
        self.assertEqual(unknown["reason"], REASON_UNKNOWN_CANDIDATE)
        backend.register_snapshot(
            snapshot(snapshot_id="s2",
                     candidates=[candidate("c0000", [3.0, 0.0, 0.0], sufficient=False)]),
            receive_s=10.0)
        poor = backend.handle(select_request(request_id="r7", snapshot_id="s2"),
                              receive_s=10.0)
        self.assertEqual(poor["reason"], REASON_INSUFFICIENT_QUALITY)

    def test_capture_baseline_requires_a_lock(self):
        backend, tracker = self._backend()
        request = {"schema_version": 1, "request_id": "r8", "action": "capture_baseline",
                   "session_id": "hf05", "time_epoch": 0, "selection_version": 0,
                   "track_id": "t0001"}
        ack = backend.handle(request, receive_s=10.0)
        self.assertEqual(ack["reason"], REASON_NOT_LOCKED)
        backend.handle(select_request(request_id="r9"), receive_s=10.1)
        request["request_id"] = "r10"
        request["selection_version"] = 1
        ack = backend.handle(request, receive_s=10.2)
        self.assertTrue(ack["accepted"])
        self.assertEqual(ack["baseline"]["status"], "pending")

    def test_nonmonotonic_receive_time_is_rejected(self):
        backend, tracker = self._backend()
        backend.handle(select_request(request_id="r11"), receive_s=10.0)
        backward = backend.handle(select_request(request_id="r12"), receive_s=9.0)
        self.assertEqual(backward["reason"], "nonmonotonic_time")

    def test_future_snapshot_and_bad_schema_are_rejected(self):
        backend, tracker = self._backend()
        future = backend.handle(select_request(request_id="r13"), receive_s=9.0)
        self.assertEqual(future["reason"], "snapshot_in_future")
        bad_schema = backend.handle(select_request(request_id="r14", schema_version=999),
                                    receive_s=10.0)
        self.assertEqual(bad_schema["reason"], "unsupported_schema_version")
        self.assertEqual(tracker.track_status, "unselected")

    def test_register_snapshot_rejects_nonfinite_receive_time(self):
        tracker = TargetTracker("hf05")
        backend = SelectionBackend("hf05", tracker)
        for received in (float("nan"), float("inf")):
            with self.subTest(received=received), self.assertRaises(ValueError):
                backend.register_snapshot(snapshot(candidates=[candidate("c0000", [3.0, 0.0, 0.0])]),
                                          receive_s=received)

    def test_new_selection_invalidates_previous_ready_baseline(self):
        backend, tracker = self._backend()
        backend.baseline.start("previous", "cal1", start_source_s=0.0)
        for step in range(15):
            backend.baseline.feed(observation(height=1.5, track_id="previous"),
                                  source_stamp_s=step * 0.25)
        self.assertEqual(backend.baseline.snapshot()["status"], "ready")
        ack = backend.handle(select_request(request_id="r15"), receive_s=10.0)
        self.assertTrue(ack["accepted"])
        self.assertNotEqual(backend.baseline.snapshot()["status"], "ready")


def observation(height=1.65, position=(3.0, 0.0, 0.0), points=200,
                track_id="t0001", calibration_version="cal1", ground=True):
    return {"track_id": track_id, "calibration_version": calibration_version,
            "ground_relative": ground, "point_count": points,
            "height_m": {"median": height, "p10": height - 0.5, "p90": height + 0.15,
                         "min": height - 0.6, "max": height + 0.2},
            "position_m": list(position)}


class BaselineTest(unittest.TestCase):
    def test_initial_lying_fails_without_a_baseline(self):
        collector = StanceBaselineCollector("hf05")
        collector.start("t0001", "cal1", start_source_s=0.0)
        state = collector.feed(observation(height=0.2), source_stamp_s=0.1)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["reason"], "initial_low_posture")
        self.assertIsNone(state["baseline"])

    def test_stable_observations_become_a_versioned_baseline(self):
        collector = StanceBaselineCollector("hf05")
        collector.start("t0001", "cal1", start_source_s=0.0)
        state = None
        for step in range(20):
            state = collector.feed(observation(), source_stamp_s=step * 0.2)
        self.assertEqual(state["status"], "ready")
        baseline = state["baseline"]
        self.assertEqual(baseline["baseline_version"], 1)
        self.assertEqual(baseline["calibration_version"], "cal1")
        self.assertEqual(baseline["source"], "measured")
        self.assertAlmostEqual(baseline["height_m"]["median"], 1.65, places=3)
        self.assertEqual(baseline["units"], {"length": "m", "time": "s"})
        dumps_strict(baseline)

    def test_predicted_occluded_and_calibration_change_are_refused(self):
        collector = StanceBaselineCollector("hf05")
        collector.start("t0001", "cal1", start_source_s=0.0)
        state = collector.feed(observation(), source_stamp_s=0.1, predicted=True)
        self.assertEqual(state["status"], "pending")
        self.assertEqual(state["sample_count"], 0)
        state = collector.feed(observation(), source_stamp_s=0.2, occluded=True)
        self.assertEqual(state["sample_count"], 0)
        state = collector.feed(observation(calibration_version="cal2"),
                               source_stamp_s=0.3)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["reason"], "calibration_version_changed")

    def test_unstable_position_fails(self):
        collector = StanceBaselineCollector("hf05")
        collector.start("t0001", "cal1", start_source_s=0.0)
        state = None
        for step in range(20):
            offset = 0.5 if step % 2 else -0.5
            state = collector.feed(observation(position=(3.0 + offset, 0.0, 0.0)),
                                   source_stamp_s=step * 0.2)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["reason"], "position_unstable")

    def test_low_point_count_fails(self):
        collector = StanceBaselineCollector("hf05")
        collector.start("t0001", "cal1", start_source_s=0.0)
        state = collector.feed(observation(points=3), source_stamp_s=0.1)
        self.assertEqual(state["reason"], "low_point_count")

    def test_operator_confirmation_cannot_accept_a_flat_low_pose(self):
        collector = StanceBaselineCollector("hf05")
        collector.start("t0001", "cal1", start_source_s=0.0, operator_confirmed=True)
        low = {"track_id": "t0001", "calibration_version": "cal1",
               "ground_relative": True, "point_count": 200,
               "height_m": {"median": 0.2, "p10": 0.15, "p90": 0.25,
                            "min": 0.1, "max": 0.3}, "position_m": [0.0, 0.0, 0.2]}
        state = None
        for step in range(15):
            state = collector.feed(low, source_stamp_s=step * 0.25)
        self.assertNotEqual(state["status"], "ready")
        self.assertIsNone(state["baseline"])


if __name__ == "__main__":
    unittest.main()
