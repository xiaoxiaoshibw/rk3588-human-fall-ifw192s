"""Online lifecycle regressions; synthetic measurements are not human GT."""
import unittest
import numpy as np

from test_episode_continuity import feature, observation, STANDING, SITTING, LYING
from test_range_frontend import scene
from test_range_tracking import step
from core.fall_state import FallStateMachine
from core.range_engine import RangeEngine
from core.range_tracker import RangeTracker, SETTINGS
from core.range_runtime import RangeRuntime
from core.human_prior import DEFAULT_SETTINGS as HUMAN_PRIOR_SETTINGS


class OnlineContinuityTests(unittest.TestCase):
    def falling(self):
        machine = FallStateMachine('s')
        machine.update(feature(0.0, height=1.5), observation(), posture=STANDING)
        machine.update(feature(0.1, height=0.9, descent_rate=0.6), observation(), posture=SITTING)
        self.assertTrue(machine._descent_seen)
        return machine

    def test_long_unobservable_locked_target_drops_old_descent(self):
        machine = self.falling()
        machine.update(feature(2.0, observable=False), observation(), posture=dict(state='unknown'))
        self.assertFalse(machine._descent_seen)
        for stamp in (2.1, 2.6, 3.1, 3.7, 4.0):
            result = machine.update(feature(stamp), observation(), posture=LYING)
        self.assertNotEqual(result['state'], 'suspected')

    def test_long_missing_sequence_without_intermediate_frames_drops_descent(self):
        machine = self.falling()
        result = machine.update(feature(2.0, observation_gap=True), observation(), posture=LYING)
        self.assertFalse(machine._descent_seen)
        self.assertNotIn('measured_descent', result['reason_codes'])

    def test_gap_restarts_standing_recovery_duration(self):
        machine = self.falling()
        machine.update(feature(0.2, height=1.5), observation(), posture=STANDING)
        machine.update(feature(0.3, observable=False), observation())
        result = machine.update(feature(1.4, height=1.5, observation_gap=True), observation(), posture=STANDING)
        self.assertNotIn('recovered', result['reason_codes'])

    def test_missing_track_and_calibration_change_clears_episode(self):
        machine = self.falling()
        obs = dict(observation(track_id=None, status='unselected'), calibration_version='new')
        result = machine.update(feature(0.2, observable=False, reset_now=True,
                                        history_reset_reason='target_changed'), obs)
        self.assertEqual(result['history_reset_reason'], 'calibration_changed')
        self.assertFalse(machine._descent_seen)

    def test_ground_loss_immediately_clears_episode(self):
        machine = self.falling()
        obs = dict(observation(), candidate=dict(ground_relative_available=False))
        machine.update(feature(0.2, observable=False), obs, posture=dict(state='unknown'))
        self.assertFalse(machine._descent_seen)

    def test_short_ambiguity_preserves_same_track_but_restarts_low_duration(self):
        machine = self.falling()
        machine.update(feature(0.15), observation(), posture=LYING)
        result = machine.update(feature(0.2, observable=False),
                                observation(track_id=None, status='ambiguous'))
        self.assertIn('target_ambiguous', result['reason_codes'])
        self.assertTrue(machine._descent_seen)
        result = machine.update(feature(0.3), observation(), posture=LYING)
        self.assertNotEqual(result['state'], 'suspected')
        for stamp in (1.0, 1.6, 2.0):
            result = machine.update(feature(stamp), observation(), posture=LYING)
        self.assertEqual(result['state'], 'suspected')

    def test_long_ambiguity_or_different_track_clears_evidence(self):
        machine = self.falling()
        machine.update(feature(2.0, observable=False), observation(track_id=None, status='ambiguous'))
        self.assertFalse(machine._descent_seen)
        machine = self.falling()
        machine.update(feature(0.2, observable=False), observation(track_id=None, status='ambiguous'))
        result = machine.update(feature(0.3), observation(track_id='different'), posture=LYING)
        self.assertEqual(result['history_reset_reason'], 'target_changed')
        self.assertFalse(machine._descent_seen)

    def test_legacy_path_timeout_and_explicit_ground_loss(self):
        machine = self.falling()
        machine.update(feature(2.0, observable=False), observation())
        self.assertFalse(machine._descent_seen)
        machine = self.falling()
        machine.update(feature(0.2, observable=False), dict(observation(), candidate={}))
        self.assertTrue(machine._descent_seen)
        machine.update(feature(0.3, observable=False), dict(observation(track_id=None, status='held'),
                       ground_relative_available=False))
        self.assertFalse(machine._descent_seen)

    def test_unknown_posture_does_not_mean_standing_or_recovery(self):
        baseline = dict(observation(), status='ready', height_m={'median': 1.5})
        machine = FallStateMachine('s')
        result = machine.update(feature(0.0, height=0.2), observation(), baseline, dict(state='unknown'))
        self.assertEqual(result['state'], 'unknown')
        machine = self.falling()
        result = machine.update(feature(0.2, height=0.2), observation(), baseline, dict(state='unknown'))
        self.assertEqual(result['state'], 'unknown')

    def test_clear_history_retires_ready_baseline_and_posture(self):
        grid, _, _ = scene(np.full((8, 24), 3.))
        engine = RangeEngine(grid, 'lidar', empty_prefix_frames=2)
        runtime = engine.runtime
        runtime.posture.last_frame = 3
        runtime.baseline_collector.status = 'ready'
        runtime.baseline_collector.baseline = {'baseline_version': 1}
        runtime.baseline_collector._baseline_counter = 1
        engine.clear_history()
        self.assertIsNone(runtime.posture.last_frame)
        self.assertEqual(runtime.baseline_collector.status, 'idle')
        self.assertEqual(runtime.baseline_collector.retired[-1]['baseline_version'], 1)
        self.assertEqual(runtime.baseline_collector._baseline_counter, 1)

    def test_short_gap_prefers_unmeasured_old_track_over_switch(self):
        tracker = RangeTracker()
        a, b = (1.4, 0, .5), (3, 1, .5)
        for i in range(4):
            result = step(tracker, [a, b], i * .1, i)
        old = result['target_track_id']
        gap = step(tracker, [b], .4, 4)
        self.assertIsNone(gap['target_track_id'])
        self.assertEqual(gap['target_source_rows'], [])
        self.assertEqual(gap['continuity_track_id'], old)
        result = step(tracker, [a, b], .5, 5)
        self.assertEqual(result['target_track_id'], old)

    def test_lock_rejects_ambiguous_policy(self):
        tracker = RangeTracker()
        tracker.selected = 'A'
        choices = [dict(track_id='A'), dict(track_id='B')]
        policy = dict(chosen_track_id='B', compatible_count=2, ambiguous=True)
        chosen, reason = tracker._locked_choice(choices, policy, 1.)
        self.assertIsNone(chosen)
        self.assertEqual(reason, 'single_person_selection_ambiguous')

    def test_ambiguous_old_track_does_not_block_independent_measurement(self):
        tracker = RangeTracker()
        a, b = (1.4, 0, .5), (3, 1, .5)
        for i in range(4):
            step(tracker, [a, b], i * .1, i)
        result = step(tracker, [(1.4, -.3, .5), (1.4, .3, .5), b], .4, 4)
        self.assertEqual(result['target_track_id'], 'g0_t0002')
        self.assertIsNone(result['continuity_track_id'])

    def test_nonambiguous_old_track_releases_after_short_hold(self):
        tracker = RangeTracker()
        a, b = (1.4, 0, .5), (3, 1, .5)
        for i in range(4):
            result = step(tracker, [a, b], i * .1, i)
        self.assertIsNone(step(tracker, [b], .4, 4)['target_track_id'])
        result = step(tracker, [b], .7, 7)
        self.assertEqual(result['target_track_id'], 'g0_t0002')

    def test_single_predicted_gap_keeps_existing_alert_candidate_contract(self):
        tracker = RangeTracker()
        for i in range(4):
            result = step(tracker, [(2, 0, .5)], i * .1, i)
        gap = step(tracker, [], .4, 4)
        self.assertEqual(gap['target_reason'], 'no_stable_current_measurement')
        self.assertEqual(gap['continuity_track_id'], result['target_track_id'])

    def test_posture_and_baseline_drift_are_rejected_after_history_clear(self):
        from core.range_posture import SETTINGS as posture_settings
        from core.baseline import DEFAULT_SETTINGS as baseline_settings
        grid, packed, _ = scene(np.full((8, 24), 3.))
        for settings, key in ((posture_settings, 'max_gap_s'), (baseline_settings, 'max_gap_s')):
            engine = RangeEngine(grid, 'lidar', empty_prefix_frames=2)
            old = settings[key]
            try:
                settings[key] = old * 2
                engine.clear_history()
                with self.assertRaisesRegex(ValueError, 'settings changed'):
                    engine.runtime.update(packed, 0., 0)
            finally:
                settings[key] = old

    def test_demo_settings_drift_is_named_and_does_not_break_reset(self):
        from core.range_demo_alert import SETTINGS as settings
        grid, packed, _ = scene(np.full((8, 24), 3.))
        engine = RangeEngine(grid, 'lidar', empty_prefix_frames=2)
        old = settings['top_m']
        try:
            settings['top_m'] = old + .1
            engine.clear_history()
            with self.assertRaisesRegex(ValueError, 'demo alert settings changed'):
                engine.runtime.update(packed, 0., 0)
            self.assertEqual(engine.demo_alert.settings['top_m'], old)
        finally:
            settings['top_m'] = old

    def test_runtime_rejects_tracker_settings_drift(self):
        grid, _, _ = scene(np.full((8, 24), 3.))
        identity = dict(session='s', coordinate='RAW/lidar', grid_sha256=grid.sha256)
        runtime = RangeRuntime(grid, identity, empty_prefix_frames=2)
        old = SETTINGS['single_person_lock']
        try:
            SETTINGS['single_person_lock'] = not old
            _, packed, _ = scene(np.full((8, 24), 3.))
            with self.assertRaisesRegex(ValueError, 'tracker settings changed'):
                runtime.update(packed, 0., 0)
        finally:
            SETTINGS['single_person_lock'] = old

    def test_runtime_rejects_human_prior_settings_drift(self):
        grid, packed, _ = scene(np.full((8, 24), 3.))
        identity = dict(session='s', coordinate='RAW/lidar', grid_sha256=grid.sha256)
        runtime = RangeRuntime(grid, identity, empty_prefix_frames=2)
        old = HUMAN_PRIOR_SETTINGS['voxel_m']
        try:
            HUMAN_PRIOR_SETTINGS['voxel_m'] = old * 2
            with self.assertRaisesRegex(ValueError, 'human prior settings changed'):
                runtime.update(packed, 0., 0)
        finally:
            HUMAN_PRIOR_SETTINGS['voxel_m'] = old


if __name__ == '__main__':
    unittest.main()
