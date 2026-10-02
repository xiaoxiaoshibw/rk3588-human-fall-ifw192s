"""Independent tracking and request freshness contracts; synthetic only."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/human_fall_detection"))
from core.tracking import TargetTracker
from core.selection import SelectionBackend
from core.features import FeatureExtractor, baseline_applies
from core.fall_state import FallStateMachine
from core.pipeline import ReplayPipeline
import numpy as np


def candidate(name="c1", x=0.0):
    return {"candidate_id": name, "center_source_m": [x, 0.0, 1.0],
            "horizontal_extent_m": {"max": 0.5},
            "quality": {"sufficient_points": True}}


def backend(received=10.0):
    tracker = TargetTracker("review")
    value = SelectionBackend("review", tracker)
    value.register_snapshot({"snapshot_id": "s1", "time_epoch": 0,
                             "source": {"source_stamp_s": 100.0},
                             "calibration": {"calibration_id": "geo"},
                             "candidates": [candidate()]}, received)
    return value, tracker


def request(version=1):
    return {"schema_version": version, "request_id": "r1", "action": "select",
            "session_id": "review", "time_epoch": 0, "snapshot_id": "s1",
            "candidate_id": "c1", "selection_version": 0,
            "calibration_version": "geo"}


def stance(target="target", version=1):
    return {"kind": "target_stance_baseline", "schema_version": 1,
            "status": "ready", "session_id": "review", "track_id": target,
            "time_epoch": 0, "baseline_version": version,
            "selection_version": version, "action_generation": version,
            "calibration_version": "geo", "unit": "m", "source": "measured",
            "sample_count": 30, "duration_s": 3.0, "point_count_median": 200,
            "position_m": [0, 0, 1], "position_spread_m": 0.05,
            "height_m": {"median": 1.5, "p10": 1.45, "p90": 1.55, "std": 0.01}}


def observation(stamp, height, target="target", generation=1, predicted=False):
    geometry = {"ground_relative_available": True,
                "height_m": {"min": max(0, height - 0.1), "p10": height - 0.05,
                             "median": height, "p90": height + 0.05,
                             "max": height + 0.1}, "point_count": 200,
                "horizontal_extent_m": {"max": 1.5 if height < 0.7 else 0.5},
                "axis": {"ambiguous": False, "verticality": 0.1 if height < 0.7 else 1.0}}
    return {"candidate": None if predicted else geometry,
            "source_stamp_s": stamp, "position_predicted": predicted,
            "track_status": "occluded" if predicted else "locked",
            "track_id": target, "time_epoch": 0,
            "action_generation": generation, "selection_version": generation,
            "calibration_version": "geo"}


class ContinuityContracts(unittest.TestCase):
    def test_first_frame_after_long_gap_does_not_auto_bind_another_candidate(self):
        tracker = TargetTracker("review")
        tracker.select("target", 0, candidate=candidate(), source_stamp_s=100.0,
                       receive_s=10.0)
        result = tracker.update([candidate("other", 5.0)], 0,
                                source_stamp_s=110.0, receive_s=20.0)
        self.assertNotEqual(result["track_status"], "locked", result)
        self.assertTrue(result["requires_reselection"], result)

    def test_late_match_cannot_bypass_occlusion_timeout(self):
        tracker = TargetTracker("review")
        tracker.select("target", 0, candidate=candidate(), source_stamp_s=100.0,
                       receive_s=10.0)
        tracker.update([], 0, source_stamp_s=100.1, receive_s=10.1)
        result = tracker.update([candidate("other", 0.1)], 0,
                                source_stamp_s=110.0, receive_s=20.0)
        self.assertNotEqual(result["track_status"], "locked", result)
        self.assertTrue(result["requires_reselection"], result)

    def test_prediction_is_anchored_at_last_measurement(self):
        tracker = TargetTracker("review")
        tracker.select("target", 0, candidate=candidate(), source_stamp_s=100.0,
                       receive_s=10.0)
        tracker.update([candidate(x=1.0)], 0, source_stamp_s=101.0, receive_s=11.0)
        tracker.update([], 0, source_stamp_s=101.5, receive_s=11.5)
        result = tracker.update([], 0, source_stamp_s=102.0, receive_s=12.0)
        self.assertAlmostEqual(result["position_m"][0], 2.0, places=6, msg=str(result))
        self.assertTrue(result["position_predicted"])

    def test_future_snapshot_has_negative_age_and_is_rejected(self):
        value, tracker = backend(received=12.0)
        ack = value.handle(request(), receive_s=10.0)
        self.assertFalse(ack["accepted"], ack)
        self.assertEqual(tracker.track_status, "unselected")

    def test_invalid_snapshot_receive_time_cannot_enable_selection(self):
        for received in (float("nan"), float("inf")):
            with self.subTest(received=received):
                try:
                    value, tracker = backend(received)
                except ValueError:
                    continue
                ack = value.handle(request(), receive_s=10.0)
                self.assertFalse(ack["accepted"], ack)
                self.assertEqual(tracker.track_status, "unselected")

    def test_unknown_request_schema_does_not_execute_selection(self):
        value, tracker = backend()
        ack = value.handle(request(version=999), receive_s=10.1)
        self.assertFalse(ack["accepted"], ack)
        self.assertEqual(tracker.track_status, "unselected")

    def test_new_selection_does_not_reuse_previous_targets_ready_baseline(self):
        value, tracker = backend()
        value.baseline.start("previous", "geo", start_source_s=0.0)
        observation = {"track_id": "previous", "calibration_version": "geo",
                       "ground_relative": True, "point_count": 200,
                       "height_m": {"median": 1.3}, "position_m": [0, 0, 1]}
        for index in range(15):
            value.baseline.feed(observation, source_stamp_s=index * 0.25)
        self.assertEqual(value.baseline.snapshot()["status"], "ready")
        ack = value.handle(request(), receive_s=10.1)
        self.assertTrue(ack["accepted"], ack)
        self.assertNotEqual(value.baseline.snapshot()["status"], "ready")

    def test_capture_baseline_rejects_wrong_epoch(self):
        value, tracker = backend()
        selected = value.handle(request(), receive_s=10.1)
        self.assertTrue(selected["accepted"], selected)
        command = request()
        command.update({"request_id": "r2", "action": "capture_baseline",
                        "time_epoch": 99, "selection_version": 1,
                        "track_id": tracker.track_id})
        ack = value.handle(command, receive_s=10.2)
        self.assertFalse(ack["accepted"], ack)

    def test_initial_low_posture_with_stored_baseline_is_not_a_descent(self):
        extractor = FeatureExtractor("review")
        machine = FallStateMachine("review", {"mode_verified": True,
                                    "allow_confirmed": True,
                                    "low_min_duration_s": 0.2,
                                    "confirmed_min_low_duration_s": 0.4})
        for stamp in (100.0, 100.2, 100.8, 101.0):
            obs = observation(stamp, 0.2)
            result = machine.update(extractor.update(obs, stance()), obs, stance())
        self.assertEqual(result["fall_status"], "low_posture_unclassified", result)
        self.assertEqual(result["event_count"], 0)

    def test_prediction_gap_does_not_duplicate_an_existing_event(self):
        extractor = FeatureExtractor("review")
        machine = FallStateMachine("review", {"mode_verified": True,
                                    "allow_confirmed": True,
                                    "low_min_duration_s": 0.2,
                                    "confirmed_min_low_duration_s": 0.4})
        for stamp, height in ((100, 1.5), (100.2, 0.9), (100.4, 0.2),
                              (100.8, 0.2), (101, 0.2)):
            obs = observation(stamp, height)
            result = machine.update(extractor.update(obs, stance()), obs, stance())
        self.assertEqual(result["event_count"], 1, result)
        predicted = observation(101.1, 0.2, predicted=True)
        machine.update(extractor.update(predicted, stance()), predicted, stance())
        measured = observation(101.2, 0.2)
        result = machine.update(extractor.update(measured, stance()), measured, stance())
        self.assertEqual(result["event_count"], 1, result)

    def test_context_reset_is_consumed_once_and_new_observations_recover(self):
        extractor = FeatureExtractor("review")
        machine = FallStateMachine("review")
        first = observation(100, 1.5)
        machine.update(extractor.update(first, stance()), first, stance())
        for stamp in (101, 101.2, 101.4):
            obs = observation(stamp, 1.5, target="second", generation=2)
            baseline = stance("second", version=2)
            result = machine.update(extractor.update(obs, baseline), obs, baseline)
        self.assertEqual(result["fall_status"], "upright", result)

    def test_small_motion_while_initially_low_does_not_use_static_baseline_drop(self):
        extractor = FeatureExtractor("review")
        machine = FallStateMachine("review", {"mode_verified": True,
                                    "allow_confirmed": True,
                                    "descending_min_drop_m": 0.4,
                                    "low_min_duration_s": 0.2,
                                    "confirmed_min_low_duration_s": 0.4})
        for stamp, height in ((100, 0.35), (100.2, 0.15), (100.8, 0.15),
                              (101, 0.15)):
            obs = observation(stamp, height)
            result = machine.update(extractor.update(obs, stance()), obs, stance())
        self.assertEqual(result["fall_status"], "low_posture_unclassified", result)
        self.assertEqual(result["event_count"], 0)

    def test_operator_confirmation_does_not_turn_a_flat_low_pose_into_stance(self):
        value, _ = backend()
        value.baseline.start("target", "geo", start_source_s=0.0,
                             operator_confirmed=True)
        low = {"track_id": "target", "calibration_version": "geo",
               "ground_relative": True, "point_count": 200,
               "height_m": {"median": 0.2, "p10": 0.15, "p90": 0.25,
                            "min": 0.1, "max": 0.3}, "position_m": [0, 0, 0.2]}
        for index in range(15):
            value.baseline.feed(low, source_stamp_s=index * 0.25)
        self.assertNotEqual(value.baseline.snapshot()["status"], "ready")

    def test_replay_does_not_choose_a_target_without_explicit_initial_selection(self):
        rng = np.random.RandomState(12)
        cloud = rng.normal(size=(500, 3)) * [0.05, 0.05, 0.1] + [3, 0, 1]
        result = ReplayPipeline("review").step(cloud, 100.0, 0, seq=1)
        self.assertEqual(result["track"]["track_status"], "unselected", result)

    def test_ready_baseline_without_binding_is_not_valid_for_any_target(self):
        unknown_baseline = {"status": "ready", "height_m": {"median": 1.5}}
        context = {"session_id": "review", "track_id": "target", "time_epoch": 0,
                   "selection_version": 1, "action_generation": 1,
                   "calibration_version": "geo"}
        self.assertFalse(baseline_applies(unknown_baseline, context))

    def test_invalid_current_receive_does_not_fall_back_to_another_clock(self):
        for received in (float("nan"), float("inf")):
            with self.subTest(received=received):
                tracker = TargetTracker("review")
                tracker.select("target", 0, candidate=candidate(), source_stamp_s=100.0,
                               receive_s=10.0)
                result = tracker.update([candidate(x=0.2)], 0,
                                        source_stamp_s=100.1, receive_s=received)
                self.assertTrue(result["position_predicted"] or
                                result["track_status"] != "locked", result)
                self.assertEqual(result["last_measured_source_s"], 100.0, result)

    def test_prediction_age_counts_from_last_measurement(self):
        tracker = TargetTracker("review")
        tracker.select("target", 0, candidate=candidate(), source_stamp_s=100,
                       receive_s=10)
        tracker.update([], 0, source_stamp_s=100.5, receive_s=10.5)
        result = tracker.update([], 0, source_stamp_s=101, receive_s=11)
        self.assertAlmostEqual(result["prediction_age_s"], 1.0)

    def test_delayed_first_missing_frame_already_has_stale_prediction(self):
        tracker = TargetTracker("review")
        tracker.select("target", 0, candidate=candidate(), source_stamp_s=100,
                       receive_s=10)
        result = tracker.update([], 0, source_stamp_s=101.7, receive_s=11.7)
        self.assertTrue(result["prediction_stale"], result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
