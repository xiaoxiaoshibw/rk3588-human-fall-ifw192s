import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))

from core.fall_state import (STATE_CONFIRMED, STATE_DESCENDING, STATE_LOW,
                             STATE_RECOVERING, STATE_SUSPECTED, STATE_UNKNOWN,
                             STATE_UPRIGHT, FallStateMachine)
from core.features import FeatureExtractor, baseline_applies
from core.ground import fit_ground_plane
from core.lidar_candidates import build_background
from core.pipeline import ReplayPipeline
from sensor_health import dumps_strict, load_config


def candidate(height, ground=True, axis_ambiguous=False, verticality=1.0,
              points=200, extent=0.4, spread=0.05):
    return {
        "ground_relative_available": ground,
        "height_m": {"median": height, "p10": height - spread, "p90": height + spread},
        "horizontal_extent_m": {"u": extent, "v": extent, "max": extent},
        "axis": {"ambiguous": axis_ambiguous, "verticality": None if axis_ambiguous else verticality},
        "point_count": points,
    }


def observation(source_stamp_s, candidate_value=None, predicted=False, epoch=0,
                generation=1, track_id="t0001", track_status="locked",
                calibration_version="cal1"):
    return {"candidate": candidate_value, "position_predicted": predicted,
            "source_stamp_s": source_stamp_s, "time_epoch": epoch,
            "action_generation": generation, "selection_version": generation,
            "track_id": track_id, "track_status": track_status,
            "calibration_version": calibration_version}


def features(height, rate=None, drop=None, observable=True, reason=None,
             reset_reason=None, epoch=0, track_id="t0001"):
    return {"observable": observable, "reason": reason, "height_median_m": height,
            "height_drop_m": drop, "descent_rate_m_s": rate,
            "history_reset_reason": reset_reason, "time_epoch": epoch,
            "track_id": track_id}


def baseline(height=1.65, version=1, track_id="t0001", generation=1, epoch=0):
    return {"status": "ready", "session_id": "hf06", "track_id": track_id,
            "time_epoch": epoch, "selection_version": generation,
            "action_generation": generation, "calibration_version": "cal1",
            "baseline_version": version, "height_m": {"median": height}}


def fall_observation(source_stamp_s, epoch=0, generation=1, track_id="t0001",
                     track_status="locked", calibration_version="cal1"):
    return {"source_stamp_s": source_stamp_s, "time_epoch": epoch,
            "action_generation": generation, "selection_version": generation,
            "track_id": track_id, "track_status": track_status,
            "calibration_version": calibration_version}


class FeatureExtractorTest(unittest.TestCase):
    def test_prediction_does_not_advance_history(self):
        extractor = FeatureExtractor("hf06")
        extractor.update(observation(1.0, candidate(1.6)), baseline())
        self.assertEqual(len(extractor.history), 1)
        predicted = extractor.update(observation(1.2, candidate(1.6), predicted=True))
        self.assertFalse(predicted["observable"])
        self.assertEqual(predicted["reason"], "prediction_not_observation")
        self.assertEqual(len(extractor.history), 1)

    def test_descent_rate_and_near_ground_duration(self):
        extractor = FeatureExtractor("hf06")
        heights = [1.6, 1.3, 1.0, 0.7, 0.45, 0.4]
        result = None
        for step, height in enumerate(heights):
            result = extractor.update(observation(step * 0.2, candidate(height)), baseline())
        self.assertGreater(result["descent_rate_m_s"], 0.0)
        self.assertGreater(result["height_drop_m"], 0.0)
        self.assertGreater(result["near_ground_duration_s"], 0.0)

    def test_degenerate_axis_stays_unknown(self):
        extractor = FeatureExtractor("hf06")
        result = extractor.update(observation(1.0, candidate(0.4, axis_ambiguous=True)),
                                  baseline())
        self.assertTrue(result["axis_ambiguous"])
        self.assertIsNone(result["axis_verticality"])

    def test_ready_baseline_missing_binding_is_not_valid(self):
        context = {"session_id": "hf06", "track_id": "t0001", "time_epoch": 0,
                   "selection_version": 1, "action_generation": 1,
                   "calibration_version": "cal1"}
        self.assertFalse(baseline_applies({"status": "ready",
                                           "height_m": {"median": 1.5}}, context))
        self.assertTrue(baseline_applies(baseline(), context))

    def test_context_reset_clears_history(self):
        extractor = FeatureExtractor("hf06")
        extractor.update(observation(1.0, candidate(1.6)), baseline())
        result = extractor.update(observation(1.2, candidate(1.6), generation=2),
                                  baseline())
        self.assertEqual(result["history_reset_reason"], "action_history_reset")
        self.assertEqual(result["history_samples"], 1)


class FallStateMachineTest(unittest.TestCase):
    def _machine(self, **settings):
        return FallStateMachine("hf06", settings)

    def _feed(self, machine, source_s, height, rate=None, drop=None, epoch=0,
              generation=1, track_id="t0001", data=None, baseline_value=None):
        result = machine.update(
            data if data is not None else features(height, rate=rate, drop=drop,
                                                    epoch=epoch, track_id=track_id),
            fall_observation(source_s, epoch=epoch, generation=generation,
                             track_id=track_id),
            baseline_value if baseline_value is not None else baseline())
        return result

    def test_initial_lying_is_low_posture_unclassified(self):
        machine = self._machine()
        result = self._feed(machine, 0.0, 0.2)
        self.assertEqual(result["fall_status"], STATE_LOW)
        self.assertEqual(result["event_count"], 0)

    def test_crouch_without_descent_is_not_suspected(self):
        machine = self._machine()
        for step in range(10):
            result = self._feed(machine, step * 0.5, 0.5)
        self.assertEqual(result["fall_status"], STATE_LOW)
        self.assertNotIn(STATE_SUSPECTED, result["fall_status"])

    def test_default_mode_tops_out_at_suspected(self):
        machine = self._machine()
        states = []
        for source_s, height, rate, drop in ((0.0, 1.65, 0.0, 0.0),
                                             (0.2, 1.2, 1.5, 0.45),
                                             (0.4, 0.4, 1.5, 1.25),
                                             (1.5, 0.4, 0.0, 1.25),
                                             (2.5, 0.4, 0.0, 1.25)):
            states.append(self._feed(machine, source_s, height, rate=rate, drop=drop))
        self.assertFalse(states[-1]["confirmed_enabled"])
        self.assertEqual(states[-1]["fall_status"], STATE_SUSPECTED)
        self.assertEqual(states[-1]["event_count"], 0)

    def test_confirmed_requires_mode_gate_and_emits_once(self):
        machine = self._machine(mode_verified=True, allow_confirmed=True)
        sequence = ((0.0, 1.65, 0.0, 0.0), (0.2, 1.2, 1.5, 0.45),
                    (0.4, 0.4, 2.0, 1.25), (1.5, 0.4, 0.0, 1.25),
                    (2.5, 0.4, 0.0, 1.25), (3.6, 0.4, 0.0, 1.25),
                    (4.0, 0.4, 0.0, 1.25))
        result = None
        emitted = []
        for source_s, height, rate, drop in sequence:
            result = self._feed(machine, source_s, height, rate=rate, drop=drop)
            if result["new_event"] is not None:
                emitted.append(result["new_event"])
        self.assertEqual(result["fall_status"], STATE_CONFIRMED)
        self.assertEqual(len(emitted), 1)
        self.assertEqual(result["event_count"], 1)
        text = dumps_strict(result)
        self.assertNotIn("NaN", text)

    def test_recovery_then_new_fall_is_a_new_event(self):
        machine = self._machine(mode_verified=True, allow_confirmed=True)
        for source_s, height, rate, drop in ((0.0, 1.65, 0.0, 0.0),
                                             (0.2, 1.2, 1.5, 0.45),
                                             (0.4, 0.4, 2.0, 1.25),
                                             (1.5, 0.4, 0.0, 1.25),
                                             (2.5, 0.4, 0.0, 1.25),
                                             (3.6, 0.4, 0.0, 1.25)):
            self._feed(machine, source_s, height, rate=rate, drop=drop)
        self.assertEqual(machine.fall_status, STATE_CONFIRMED)
        first_event = machine.events[0]["event_id"]
        recovering = self._feed(machine, 5.0, 1.6, rate=-0.2, drop=0.05)
        self.assertEqual(recovering["fall_status"], STATE_RECOVERING)
        upright = self._feed(machine, 6.5, 1.62, rate=0.0, drop=0.03)
        self.assertEqual(upright["fall_status"], STATE_UPRIGHT)
        for source_s, height, rate, drop in ((7.0, 1.2, 1.5, 0.45),
                                             (7.2, 0.4, 2.0, 1.25),
                                             (8.5, 0.4, 0.0, 1.25),
                                             (10.5, 0.4, 0.0, 1.25)):
            result = self._feed(machine, source_s, height, rate=rate, drop=drop)
        self.assertEqual(result["fall_status"], STATE_CONFIRMED)
        self.assertEqual(result["event_count"], 2)
        self.assertNotEqual(machine.events[1]["event_id"], first_event)

    def test_epoch_change_returns_unknown_and_keeps_events(self):
        machine = self._machine(mode_verified=True, allow_confirmed=True)
        for source_s, height, rate, drop in ((0.0, 1.65, 0.0, 0.0),
                                             (0.2, 1.2, 1.5, 0.45),
                                             (0.4, 0.4, 2.0, 1.25),
                                             (1.5, 0.4, 0.0, 1.25),
                                             (2.5, 0.4, 0.0, 1.25),
                                             (3.6, 0.4, 0.0, 1.25)):
            self._feed(machine, source_s, height, rate=rate, drop=drop)
        result = machine.update(features(0.4, epoch=1, reset_reason="time_epoch_changed"),
                                fall_observation(3.7, epoch=1))
        self.assertEqual(result["fall_status"], STATE_UNKNOWN)
        self.assertEqual(result["event_count"], 1)
        self.assertIn("time_epoch_changed", result["reason_codes"])

    def test_target_switch_clears_action_history(self):
        machine = self._machine(mode_verified=True, allow_confirmed=True)
        for source_s, height, rate, drop in ((0.0, 1.65, 0.0, 0.0),
                                             (0.2, 1.2, 1.5, 0.45),
                                             (0.4, 0.4, 2.0, 1.25)):
            self._feed(machine, source_s, height, rate=rate, drop=drop)
        self.assertTrue(machine._descent_seen)
        result = machine.update(features(0.5, track_id="t0002",
                                         reset_reason="target_changed"),
                                fall_observation(0.5, track_id="t0002"))
        self.assertEqual(result["fall_status"], STATE_UNKNOWN)
        self.assertFalse(machine._descent_seen)

    def test_prediction_yields_unknown_without_clearing_events(self):
        machine = self._machine(mode_verified=True, allow_confirmed=True)
        for source_s, height, rate, drop in ((0.0, 1.65, 0.0, 0.0),
                                             (0.2, 1.2, 1.5, 0.45),
                                             (0.4, 0.4, 2.0, 1.25),
                                             (1.5, 0.4, 0.0, 1.25),
                                             (2.5, 0.4, 0.0, 1.25),
                                             (3.6, 0.4, 0.0, 1.25)):
            self._feed(machine, source_s, height, rate=rate, drop=drop)
        result = machine.update(features(0.4, observable=False,
                                         reason="prediction_not_observation"),
                                fall_observation(3.7))
        self.assertEqual(result["fall_status"], STATE_UNKNOWN)
        self.assertEqual(result["event_count"], 1)

    def test_initial_low_with_stored_baseline_is_not_a_descent(self):
        machine = self._machine(mode_verified=True, allow_confirmed=True,
                                low_min_duration_s=0.2, confirmed_min_low_duration_s=0.4)
        result = None
        for source_s in (100.0, 100.2, 100.8, 101.0):
            result = self._feed(machine, source_s, 0.2)
        self.assertEqual(result["fall_status"], STATE_LOW)
        self.assertEqual(result["event_count"], 0)

    def test_prediction_gap_does_not_duplicate_an_existing_event(self):
        machine = self._machine(mode_verified=True, allow_confirmed=True,
                                low_min_duration_s=0.2, confirmed_min_low_duration_s=0.4)
        for source_s, height, rate, drop in ((100.0, 1.5, 0.0, 0.0),
                                             (100.2, 0.9, 3.0, 0.6),
                                             (100.4, 0.2, 3.0, 1.3),
                                             (100.8, 0.2, 0.0, 1.3),
                                             (101.0, 0.2, 0.0, 1.3)):
            result = self._feed(machine, source_s, height, rate=rate, drop=drop)
        self.assertEqual(result["event_count"], 1)
        gap = machine.update(features(0.2, observable=False,
                                      reason="prediction_not_observation"),
                             fall_observation(101.1))
        self.assertEqual(gap["event_count"], 1)
        resumed = machine.update(features(0.2), fall_observation(101.2))
        self.assertEqual(resumed["event_count"], 1)

    def test_reset_is_consumed_once_and_valid_observations_recover(self):
        extractor = FeatureExtractor("hf06")
        machine = FallStateMachine("hf06")
        first = observation(100.0, candidate(1.6))
        machine.update(extractor.update(first, baseline()), fall_observation(100.0),
                       baseline())
        result = None
        bound = baseline(track_id="t0002", generation=2)
        for stamp in (101.0, 101.2, 101.4):
            obs = observation(stamp, candidate(1.6), generation=2, track_id="t0002")
            result = machine.update(extractor.update(obs, bound),
                                    fall_observation(stamp, generation=2,
                                                     track_id="t0002"), bound)
        self.assertEqual(result["fall_status"], STATE_UPRIGHT)

    def test_unknown_state_does_not_revoke_events(self):
        machine = self._machine(mode_verified=True, allow_confirmed=True)
        for source_s, height, rate, drop in ((0.0, 1.65, 0.0, 0.0),
                                             (0.2, 1.2, 1.5, 0.45),
                                             (0.4, 0.4, 2.0, 1.25),
                                             (1.5, 0.4, 0.0, 1.25),
                                             (2.5, 0.4, 0.0, 1.25),
                                             (3.6, 0.4, 0.0, 1.25)):
            self._feed(machine, source_s, height, rate=rate, drop=drop)
        result = machine.update(features(0.0, observable=False, reason="no_ground_or_candidate"),
                                fall_observation(3.8))
        self.assertEqual(result["fall_status"], STATE_UNKNOWN)
        self.assertEqual(len(machine.events), 1)


def _plane_points(normal=(0.0, 0.0, 1.0), height=1.5, count=4000):
    normal = np.asarray(normal, dtype=np.float64)
    axis = np.array([1.0, 0.0, 0.0])
    u = np.cross(normal, axis)
    u = u / np.linalg.norm(u)
    v = np.cross(normal, u)
    rng = np.random.RandomState(7)
    spread = (rng.rand(count, 2) - 0.5) * 9.0
    points = spread[:, :1] * u + spread[:, 1:] * v - float(height) * normal
    return points + rng.randn(count, 3) * 0.003


def _person(height, seed=13):
    rng = np.random.RandomState(seed)
    points = np.zeros((260, 3))
    points[:, 0] = rng.normal(3.0, 0.2, 260)
    points[:, 1] = rng.normal(0.0, 0.2, 260)
    points[:, 2] = -1.5 + rng.uniform(0.0, max(height, 0.05), 260)
    return points


class ReplayPipelineTest(unittest.TestCase):
    def _scene(self):
        ground_points = _plane_points()
        ground = fit_ground_plane(ground_points, settings={"range_min_m": 0.0},
                                  frame="innolidar")
        background = build_background([ground_points])
        heights = [1.6, 1.4, 1.0, 0.5, 0.3, 0.3, 0.3]
        frames = [np.vstack((ground_points, _person(height))) for height in heights]
        baseline = {"status": "ready", "height_m": {"median": 1.65},
                    "baseline_version": 1, "calibration_version": "synthetic"}
        return frames, ground, background, baseline

    def test_fixed_input_replays_identically(self):
        frames, ground, background, baseline = self._scene()
        times = [step * 0.3 for step in range(len(frames))]
        outputs = []
        for _ in range(2):
            pipeline = ReplayPipeline("hf06_replay", {}, baseline=baseline,
                                      auto_select=True)
            pipeline.ground = ground
            pipeline.background = background
            outputs.append(dumps_strict(pipeline.run(frames, times)))
        self.assertEqual(outputs[0], outputs[1])
        self.assertNotIn("NaN", outputs[0])

    def test_replay_script_entry_is_deterministic(self):
        from fall_replay import main
        frames, ground, background, baseline = self._scene()
        times = [step * 0.3 for step in range(len(frames))]
        with tempfile.TemporaryDirectory() as directory:
            frames_path = os.path.join(directory, "frames.npz")
            ground_path = os.path.join(directory, "ground.json")
            baseline_path = os.path.join(directory, "baseline.json")
            output_a = os.path.join(directory, "a.json")
            output_b = os.path.join(directory, "b.json")
            np.savez(frames_path, frames=np.asarray(frames), times=np.asarray(times))
            import json
            with open(ground_path, "w", encoding="utf-8") as handle:
                json.dump({"kind": "geometry_calibration", "ground": ground}, handle)
            with open(baseline_path, "w", encoding="utf-8") as handle:
                json.dump(baseline, handle)
            for output in (output_a, output_b):
                self.assertEqual(main(["--frames", frames_path, "--ground", ground_path,
                                       "--baseline", baseline_path, "--auto-select",
                                       "--output", output]), 0)
            with open(output_a, encoding="utf-8") as handle:
                first = handle.read()
            with open(output_b, encoding="utf-8") as handle:
                second = handle.read()
            self.assertEqual(first, second)


class PerceptionConfigTest(unittest.TestCase):
    def test_perception_sections_load_into_each_resolver(self):
        from core.association import resolve_settings as resolve_association
        from core.baseline import resolve_settings as resolve_baseline
        from core.fall_state import resolve_settings as resolve_fall
        from core.features import resolve_settings as resolve_features
        from core.lidar_candidates import resolve_settings as resolve_candidates
        from core.selection import resolve_settings as resolve_selection
        from core.tracking import resolve_settings as resolve_tracking
        config = load_config(str(PACKAGE_DIR / "config" / "perception.yaml"))
        resolve_candidates(config["candidates"])
        resolve_association(config["association"])
        resolve_tracking(config["tracking"])
        resolve_selection(config["selection"])
        resolve_baseline(config["baseline"])
        resolve_features(config["features"])
        resolved_fall = resolve_fall(config["fall"])
        self.assertFalse(resolved_fall["mode_verified"])
        self.assertFalse(resolved_fall["allow_confirmed"])


if __name__ == "__main__":
    unittest.main()
