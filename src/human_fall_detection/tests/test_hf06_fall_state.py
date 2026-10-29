import os
import sys
import tempfile
import unittest
from unittest.mock import patch
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
             reset_reason=None, epoch=0, track_id="t0001", extent=None, top=None):
    # Posture geometry travels with every real feature block: the low measured
    # surface top and the horizontal extent. A plain falling fixture defaults to
    # a low top (a body ending on the ground); pass ``extent``/``top`` to model a
    # crouch or a missing geometry instead.
    return {"observable": observable, "reason": reason, "height_median_m": height,
            "height_m": {"median": height, "max": height + 0.1 if top is None else top},
            "horizontal_extent_m": extent,
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
    def test_invalid_height_breaks_continuity_without_poisoning_history(self):
        for height in (np.nan, np.inf, -np.inf, 'invalid', [0.4]):
            with self.subTest(height=height):
                extractor = FeatureExtractor('hf06')
                extractor.update(observation(0., candidate(.4)))
                bad_candidate = candidate(.4)
                bad_candidate['height_m']['median'] = height
                invalid = extractor.update(observation(.1, bad_candidate))
                self.assertFalse(invalid['observable'])
                self.assertEqual(invalid['reason'], 'invalid_height')
                self.assertEqual(len(extractor.history), 1)
                dumps_strict(invalid)
                resumed = extractor.update(observation(.2, candidate(.4)))
                self.assertTrue(resumed['observation_gap'])
                self.assertIsNone(resumed['descent_rate_m_s'])
                self.assertEqual(resumed['near_ground_duration_s'], 0.)

    def test_unobserved_frames_break_temporal_segment_without_deleting_history(self):
        for kind in ('prediction', 'candidate', 'ground', 'height'):
            with self.subTest(kind=kind):
                extractor = FeatureExtractor('hf06')
                extractor.update(observation(0, candidate(.4)))
                extractor.update(observation(.1, candidate(.4)))
                missing = observation(.2, candidate(.4), predicted=kind == 'prediction')
                if kind == 'candidate':missing['candidate'] = None
                if kind == 'ground':missing['candidate']['ground_relative_available'] = False
                if kind == 'height':missing['candidate']['height_m']['median'] = None
                self.assertFalse(extractor.update(missing)['observable'])
                self.assertEqual(len(extractor.history), 2)
                resumed = extractor.update(observation(.3, candidate(.4)))
                self.assertTrue(resumed['observation_gap'])
                self.assertFalse(resumed['reset_now'])
                self.assertEqual(resumed['near_ground_duration_s'], 0.)
                self.assertIsNone(resumed['descent_rate_m_s'])

    def test_gap_boundary_and_bounded_history(self):
        for dt, gap in ((.3, False), (.3 + .5e-9, False), (.3 + 2e-9, True)):
            extractor = FeatureExtractor('hf06')
            extractor.update(observation(.1, candidate(.4)))
            result = extractor.update(observation(.1 + dt, candidate(.4)))
            self.assertEqual(result.get('observation_gap', False), gap)
        extractor = FeatureExtractor('hf06', dict(max_history=2))
        for t in (0, .1, 2., 2.1):result = extractor.update(observation(t, candidate(.4)))
        self.assertEqual(len(extractor.history), 2)
        self.assertAlmostEqual(result['near_ground_duration_s'], .1)
        for value in (0, -1, np.nan, np.inf):
            with self.assertRaises(ValueError):FeatureExtractor('hf06', dict(max_gap_s=value))

    def test_invalid_or_reverse_time_never_appends_temporal_evidence(self):
        for stamp in (None, np.nan, np.inf, 'invalid', .1, 0.):
            extractor = FeatureExtractor('hf06')
            initial = observation(.1, candidate(.4))
            machine = FallStateMachine('hf06')
            machine.update(extractor.update(initial), initial)
            bad_observation = observation(stamp, candidate(.4))
            invalid = extractor.update(bad_observation)
            self.assertFalse(invalid['observable'])
            self.assertEqual(len(extractor.history), 1)
            dumps_strict(invalid)
            refused = machine.update(invalid, bad_observation)
            self.assertEqual(refused['fall_status'], STATE_UNKNOWN)
            self.assertIsNone(refused['new_event'])
            dumps_strict(refused)
            result = extractor.update(observation(.2, candidate(.4)))
            self.assertTrue(result['observation_gap'])
            self.assertEqual(result['near_ground_duration_s'], 0.)

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
    def test_nonfinite_geometry_cannot_supply_lying_support(self):
        for extent, top in ((np.inf, .95), (.2, -np.inf), (np.nan, np.nan)):
            with self.subTest(extent=extent, top=top):
                result = self._descent(self._machine(), dict(extent=extent, top=top))
                self.assertEqual(result['fall_status'], STATE_LOW)
                self.assertEqual(result['event_count'], 0)

    def test_lying_support_checks_each_alternative_independently(self):
        for extent in ('invalid', np.inf, np.nan):
            with self.subTest(extent=extent):
                result = self._descent(self._machine(), dict(extent=extent, top=.45))
                self.assertEqual(result['fall_status'], STATE_SUSPECTED)

    def test_implicit_gap_cannot_manufacture_sustained_low_evidence(self):
        extractor = FeatureExtractor('hf06');machine = FallStateMachine('hf06')
        for t,h in ((0,1.6),(.1,1.2),(.2,.4),(2.,.4)):
            obs = observation(t,candidate(h))
            f = extractor.update(obs,baseline())
            result = machine.update(f,obs,baseline())
        self.assertEqual(result['fall_status'], STATE_LOW)
        self.assertEqual(f['near_ground_duration_s'], 0.)
        self.assertIsNone(f['descent_rate_m_s'])
        for i in range(1,18):
            obs = observation(2. + i*.1,candidate(.4))
            result = machine.update(extractor.update(obs,baseline()),obs,baseline())
        self.assertEqual(result['fall_status'], STATE_LOW)
        self.assertNotIn('measured_descent', result['reason_codes'])

    def test_real_feature_gaps_keep_confirmed_episode_deduplicated(self):
        for kind in ('prediction', 'implicit', 'no_time'):
            with self.subTest(kind=kind):
                extractor = FeatureExtractor('hf06')
                machine = FallStateMachine('hf06', dict(mode_verified=True,allow_confirmed=True,
                    low_min_duration_s=.2,confirmed_min_low_duration_s=.4))
                sequence = [(0,1.6),(.1,1.2)] + [(i*.1,.4) for i in range(2,11)]
                for t,h in sequence:
                    obs = observation(t,candidate(h))
                    result = machine.update(extractor.update(obs,baseline()),obs,baseline())
                self.assertEqual(result['event_count'], 1)
                if kind != 'implicit':
                    obs = observation(None if kind == 'no_time' else 1.1,candidate(.4),
                                      predicted=kind == 'prediction')
                    result = machine.update(extractor.update(obs,baseline()),obs,baseline())
                    dumps_strict(result)
                start = 2. if kind == 'implicit' else 1.2
                for i in range(8):
                    obs = observation(start+i*.1,candidate(.4))
                    result = machine.update(extractor.update(obs,baseline()),obs,baseline())
                    self.assertEqual(result['event_count'], 1)
                    self.assertIsNone(result['new_event'])
                self.assertEqual(result['fall_status'], STATE_CONFIRMED)

    def test_recovery_duration_restarts_after_dipping_below_recovery_height(self):
        machine = self._machine()
        for t,h,rate in ((0,1.65,0),(.1,1.2,4),(.2,.4,5)):
            self._feed(machine,t,h,rate=rate)
        for i in range(3,19):self._feed(machine,i*.1,.4,rate=0)
        self._feed(machine,2.,1.1,rate=0)
        for i in range(21,30):self._feed(machine,i*.1,.8,rate=0)
        self.assertEqual(self._feed(machine,3.,1.1,rate=0)['fall_status'],STATE_RECOVERING)
        self.assertEqual(self._feed(machine,3.9,1.1,rate=0)['fall_status'],STATE_RECOVERING)
        self.assertEqual(self._feed(machine,4.1,1.1,rate=0)['fall_status'],STATE_UPRIGHT)

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

    def _descent(self, machine, geometry, start=0.0, hold_s=3.2):
        """Sustained low posture after a measured descent, with given geometry."""
        result = None
        for source_s, height, rate, drop in ((start, 1.65, 0.0, 0.0),
                                             (start + 0.2, 1.2, 1.5, 0.45),
                                             (start + 0.4, 0.55, 1.5, 1.1)):
            result = machine.update(features(height, rate=rate, drop=drop, **geometry),
                                    fall_observation(source_s))
        step = 0
        while source_s + 0.8 * (step + 1) <= start + hold_s:
            step += 1
            result = machine.update(features(0.55, rate=0.0, drop=1.1, **geometry),
                                    fall_observation(source_s + 0.8 * step))
        return result

    def test_sustained_crouch_geometry_is_not_suspected(self):
        # Measured descent into a deep crouch: low height but neither long on
        # the ground nor low-topped, so it is not called a fall.
        result = self._descent(self._machine(), dict(extent=0.2, top=0.95))
        self.assertEqual(result["fall_status"], STATE_LOW)
        self.assertIn("low_posture_without_lying_pose", result["reason_codes"])
        self.assertNotIn(STATE_SUSPECTED, result["fall_status"])
        self.assertEqual(result["event_count"], 0)

    def test_lying_geometry_is_required_and_sufficient_for_suspected(self):
        for geometry in (dict(extent=0.9, top=1.1),   # long on the ground
                         dict(extent=0.2, top=0.45),  # flat and low-topped
                         dict(extent=None, top=0.45)):
            with self.subTest(geometry=geometry):
                result = self._descent(self._machine(), geometry)
                self.assertEqual(result["fall_status"], STATE_SUSPECTED)

    def test_missing_posture_geometry_never_counts_as_lying(self):
        machine = self._machine()
        result = None
        for source_s, height, rate, drop in ((0.0, 1.65, 0.0, 0.0),
                                             (0.2, 1.2, 1.5, 0.45),
                                             (0.4, 0.55, 1.5, 1.1),
                                             (1.6, 0.55, 0.0, 1.1),
                                             (3.0, 0.55, 0.0, 1.1)):
            data = features(height, rate=rate, drop=drop)
            data.pop("height_m")
            result = machine.update(data, fall_observation(source_s))
        self.assertEqual(result["fall_status"], STATE_LOW)
        self.assertIn("low_posture_without_lying_pose", result["reason_codes"])

    def test_confirmed_without_lying_pose_is_not_emitted(self):
        machine = self._machine(mode_verified=True, allow_confirmed=True)
        crouch = dict(extent=0.2, top=0.95)
        result = self._descent(machine, crouch, hold_s=4.0)
        self.assertEqual(result["fall_status"], STATE_LOW)
        self.assertEqual(result["event_count"], 0)
        result = machine.update(features(0.55, rate=0.0, drop=1.1, extent=0.9, top=1.1),
                                fall_observation(4.4), baseline())
        self.assertEqual(result["fall_status"], STATE_CONFIRMED)
        self.assertEqual(result["event_count"], 1)
        self.assertIn("lying_pose_supported", result["new_event"]["reason_codes"])

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
    def test_ready_baseline_binding_is_passed_to_both_consumers(self):
        c = candidate(1.6)
        c.update(candidate_id='c0000',center_source_m=[0,0,1.6],evidence_indices=[0])
        for wrong in (None, 'selection_version', 'calibration_version'):
            bound = baseline()
            if wrong is not None:bound[wrong] = 'other'
            pipeline = ReplayPipeline('hf06',baseline=bound)
            pipeline.tracker.select('t0001',0,candidate=c,calibration_version='cal1',
                selection_version=1,source_stamp_s=0,receive_s=0)
            with patch('core.pipeline.build_snapshot',return_value=dict(snapshot_id='one',candidates=[c])):
                result = pipeline.step([[0,0,1.6]],.1,0,seq=1)
            self.assertEqual(result['features']['baseline_bound'],wrong is None)
            self.assertEqual(result['fall']['baseline_version'],1 if wrong is None else None)
            if wrong is None:self.assertEqual(result['fall']['fall_status'],STATE_UPRIGHT)

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
