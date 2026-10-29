"""Episode continuity + posture-layer regressions (single-person geometry chain).

These cases pin the measured behaviour of 2026-10-28: a short unmeasured gap
must not erase the fall episode, the posture layer (not the visible-surface
median height) decides low/lying, a slow fall is a posture transition, and the
single-person lock has a release/switch debounce. All fixtures are synthetic
geometry, not human or fall ground truth.
"""

import unittest

import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.fall_state import FallStateMachine
from core.range_posture import PostureObserver
from core.range_tracker import RangeTracker


def feature(stamp, height=0.3, top=None, p10=None, p90=None, extent=1.2,
            verticality=0.05, points=200, descent_rate=None, **changes):
    block = {'median': height, 'max': height if top is None else top,
             'min': 0.0 if p10 is None else max(0.0, p10 - 0.2)}
    if p10 is not None:
        block['p10'] = p10
    if p90 is not None:
        block['p90'] = p90
    value = dict(source_stamp_s=stamp, observable=True, ground_relative=True,
                 height_median_m=height, height_m=block, horizontal_extent_m=extent,
                 axis_verticality=verticality, axis_ambiguous=False, point_count=points,
                 descent_rate_m_s=descent_rate, observation_gap=False, reset_now=False)
    value.update(changes)
    return value


def observation(track_id='t0001', status='locked', epoch=0):
    return dict(track_id=track_id, track_status=status, time_epoch=epoch,
                action_generation=epoch, selection_version=epoch,
                session_id='s', calibration_version='g')


LYING = dict(state='lying_candidate', durationSec=2.0)
STANDING = dict(state='standing', durationSec=2.0)
SITTING = dict(state='sitting', durationSec=2.0)


class EpisodeContinuity(unittest.TestCase):
    def test_short_gap_keeps_descent_evidence_and_fires_suspected(self):
        state = FallStateMachine('s')
        # stand, then a measured descent
        for index in range(4):
            state.update(feature(index*0.1, height=1.5, top=1.7, extent=0.5,
                                 verticality=1.0), observation(), posture=STANDING)
        state.update(feature(0.4, height=0.9, top=1.6, extent=0.5, verticality=1.0,
                             descent_rate=0.6),
                     observation(), posture=dict(state='sitting'))
        self.assertTrue(state._descent_seen)
        # 3-frame measurement gap with no track id at all
        for index, stamp in enumerate((0.5, 0.6, 0.7)):
            out = state.update(feature(stamp, height=None, top=None, extent=None,
                                       verticality=None, points=0, observable=False),
                               observation(track_id=None, status='unselected'),
                               posture=dict(state='unknown'))
            self.assertEqual(out['state'], 'unknown')
            self.assertIn('target_held_gap', out['reason_codes'])
        self.assertTrue(state._descent_seen)
        # lying body returns; sustained low posture now upgrades to suspected
        out = None
        for stamp in (0.8, 1.0, 1.4, 2.2, 2.4):
            out = state.update(feature(stamp, height=0.25, top=0.35, extent=1.2,
                                       verticality=0.03), observation(), posture=LYING)
        self.assertEqual(out['state'], 'suspected')

    def test_gap_beyond_tolerance_clears_the_episode(self):
        state = FallStateMachine('s')
        for index in range(4):
            state.update(feature(index*0.1, height=1.5, top=1.7, extent=0.5,
                                 verticality=1.0), observation(), posture=STANDING)
        state.update(feature(0.4, height=0.9, top=1.6, extent=0.5, verticality=1.0,
                             descent_rate=0.6),
                     observation(), posture=dict(state='sitting'))
        self.assertTrue(state._descent_seen)
        out = state.update(feature(3.0, height=None, top=None, extent=None,
                                   verticality=None, points=0, observable=False),
                           observation(track_id=None, status='unselected'),
                           posture=dict(state='unknown'))
        self.assertEqual(out['state'], 'unknown')
        self.assertNotIn('target_held_gap', out['reason_codes'])
        self.assertFalse(state._descent_seen)
        out = None
        for stamp in (3.1, 3.4, 3.9, 4.9, 5.1):
            out = state.update(feature(stamp, height=0.25, top=0.35, extent=1.2,
                                       verticality=0.03), observation(), posture=LYING)
        self.assertNotEqual(out['state'], 'suspected')

    def test_missing_id_feature_reset_is_a_gap_not_a_target_change(self):
        state = FallStateMachine('s')
        state.update(feature(0.0, height=1.5), observation(), posture=STANDING)
        state.update(feature(0.1, height=0.9, descent_rate=0.6), observation(), posture=SITTING)
        out = state.update(feature(0.2, observable=False, reset_now=True,
                                   history_reset_reason='target_changed'),
                           observation(track_id=None, status='unselected'))
        self.assertIn('target_held_gap', out['reason_codes'])
        self.assertTrue(state._descent_seen)
        out = state.update(feature(0.3), observation(track_id='other'), posture=LYING)
        self.assertIn('target_changed', out['reason_codes'])
        self.assertFalse(state._descent_seen)

    def test_target_change_still_clears_the_episode(self):
        state = FallStateMachine('s')
        for index in range(4):
            state.update(feature(index*0.1, height=1.5, top=1.7, extent=0.5,
                                 verticality=1.0), observation('t1'), posture=STANDING)
        state.update(feature(0.4, height=0.9, top=1.6, extent=0.5, verticality=1.0,
                             descent_rate=0.6),
                     observation('t1'), posture=dict(state='sitting'))
        out = state.update(feature(0.5, height=0.4, top=0.5, extent=1.0, verticality=0.1),
                           observation('t2'), posture=LYING)
        self.assertEqual(out['state'], 'unknown')
        self.assertIn('target_changed', out['reason_codes'])
        self.assertFalse(state._descent_seen)

    def test_held_track_beyond_tolerance_clears_the_episode(self):
        state = FallStateMachine('s')
        state.update(feature(0.0, height=1.5), observation(), posture=STANDING)
        state.update(feature(0.1, height=0.9, descent_rate=0.6), observation(), posture=SITTING)
        self.assertTrue(state._descent_seen)
        out = state.update(feature(1.61, observable=False), observation(status='held'))
        self.assertNotIn('target_held_gap', out['reason_codes'])
        self.assertFalse(state._descent_seen)

    def test_posture_transition_alone_never_confirms(self):
        state = FallStateMachine('s', dict(mode_verified=True, allow_confirmed=True))
        baseline = dict(observation(), status='ready', height_m={'median': 1.5})
        state.update(feature(0.0, height=1.5), observation(), baseline, STANDING)
        for stamp in (0.1, 1.0, 2.0, 3.0, 4.0):
            out = state.update(feature(stamp), observation(), baseline, LYING)
        self.assertEqual(out['state'], 'suspected')
        self.assertIsNone(out['new_event'])
        self.assertIn('posture_transition_supported', out['reason_codes'])


class PostureDrivenClassification(unittest.TestCase):
    def test_standing_posture_is_upright_without_a_baseline(self):
        state = FallStateMachine('s')
        out = state.update(feature(0.0, height=1.2, top=1.7, extent=0.5, verticality=1.0),
                           observation(), posture=STANDING)
        self.assertEqual(out['state'], 'upright')
        self.assertIn('standing_posture', out['reason_codes'])

    def test_slow_fall_upgrades_by_posture_transition_without_descent_rate(self):
        state = FallStateMachine('s')
        for index in range(10):
            state.update(feature(index*0.1, height=1.2, top=1.7, extent=0.5,
                                 verticality=1.0), observation(), posture=STANDING)
        self.assertFalse(state._descent_seen)
        out = None
        for stamp in (1.0, 1.5, 2.0, 2.6, 2.7):
            out = state.update(feature(stamp, height=0.28, top=0.36, extent=1.2,
                                       verticality=0.04), observation(), posture=LYING)
        self.assertEqual(out['state'], 'suspected')
        self.assertIn('posture_transition_supported', out['reason_codes'])

    def test_sitting_posture_is_low_but_never_suspected(self):
        state = FallStateMachine('s')
        for index in range(10):
            state.update(feature(index*0.1, height=1.2, top=1.7, extent=0.5,
                                 verticality=1.0), observation(), posture=STANDING)
        out = None
        for stamp in (1.0, 1.6, 2.2, 2.8):
            out = state.update(feature(stamp, height=0.6, top=0.85, extent=0.6,
                                       verticality=0.8), observation(), posture=SITTING)
        self.assertEqual(out['state'], 'low_posture_unclassified')
        self.assertNotEqual(out['state'], 'suspected')

    def test_standing_after_descent_recovers_without_a_baseline(self):
        state = FallStateMachine('s')
        for index in range(4):
            state.update(feature(index*0.1, height=1.5, top=1.7, extent=0.5,
                                 verticality=1.0), observation(), posture=STANDING)
        state.update(feature(0.4, height=0.9, top=1.6, extent=0.5, verticality=1.0,
                             descent_rate=0.6),
                     observation(), posture=dict(state='sitting'))
        recovered = False
        for index in range(15):
            out = state.update(feature(0.6+index*0.1, height=1.2, top=1.7, extent=0.5,
                                       verticality=1.0), observation(), posture=STANDING)
            recovered = recovered or 'recovered' in out['reason_codes']
        self.assertEqual(out['state'], 'upright')
        self.assertTrue(recovered)


class PostureObserverStates(unittest.TestCase):
    def _feed(self, observer, count, top, p10, p90, extent, verticality):
        out = None
        first = 0 if observer.last_frame is None else observer.last_frame + 1
        for offset in range(count):
            index = first + offset
            stamp = index*0.1
            frames = dict(frame=index, time_s=stamp, generation=0,
                          target_track_id='T1', target_source_rows=[0, 1])
            out = observer.update(
                feature(stamp, height=(p10+p90)/2, top=top, p10=p10, p90=p90,
                        extent=extent, verticality=verticality),
                frames, ('src',))
        return out

    def test_standing_requires_vertical_span_not_height_alone(self):
        observer = PostureObserver()
        out = self._feed(observer, 10, top=1.7, p10=0.2, p90=1.5, extent=0.5, verticality=0.98)
        self.assertEqual(out['state'], 'standing')
        # a 1.1 m tall narrow strip has height but no body extent
        observer = PostureObserver()
        out = self._feed(observer, 10, top=1.1, p10=1.05, p90=1.15, extent=0.12, verticality=0.97)
        self.assertNotEqual(out['state'], 'standing')

    def test_sitting_and_transition_dwell(self):
        observer = PostureObserver()
        self._feed(observer, 5, top=1.7, p10=0.2, p90=1.5, extent=0.5, verticality=0.98)
        out = self._feed(observer, 1, top=0.8, p10=0.2, p90=0.7, extent=0.5,
                         verticality=0.9)
        self.assertEqual(out['state'], 'transitioning')
        out = self._feed(observer, 4, top=0.8, p10=0.2, p90=0.7, extent=0.5,
                         verticality=0.9)
        self.assertEqual(out['state'], 'sitting')

    def test_lying_still_top_out_at_candidate_and_keeps_duration(self):
        observer = PostureObserver()
        out = self._feed(observer, 20, top=0.4, p10=0.1, p90=0.3, extent=1.3, verticality=0.05)
        self.assertEqual(out['state'], 'lying_candidate')
        self.assertGreaterEqual(out['durationSec'], 1.5)
        self.assertEqual(out['humanSemantic'], 'UNKNOWN')
        self.assertFalse(out['fallEvent'])


class LockDebounce(unittest.TestCase):
    def test_release_debounce_holds_then_releases(self):
        tracker = RangeTracker()
        tracker.selected = 'A'
        available = [dict(track_id='A', selection_score=1.0)]
        policy = dict(chosen_track_id=None, compatible_count=0)
        chosen, reason = tracker._locked_choice(available, policy, 10.0)
        self.assertEqual(chosen['track_id'], 'A')
        self.assertEqual(reason, 'target_held_unverified')
        chosen, reason = tracker._locked_choice(available, policy, 10.2)
        self.assertEqual(chosen['track_id'], 'A')
        chosen, reason = tracker._locked_choice(available, policy, 10.6)
        self.assertIsNone(chosen)
        self.assertEqual(reason, 'target_released_unverified')
        self.assertEqual(tracker.released, 'A')

    def test_switch_debounce_keeps_the_measured_old_target(self):
        tracker = RangeTracker()
        tracker.selected = 'A'
        available = [dict(track_id='A', selection_score=0.9),
                     dict(track_id='B', selection_score=2.0)]
        policy = dict(chosen_track_id='B', compatible_count=1)
        chosen, reason = tracker._locked_choice(available, policy, 20.0)
        self.assertEqual(chosen['track_id'], 'A')
        self.assertEqual(reason, 'previous_target_retained_pending_switch')
        chosen, reason = tracker._locked_choice(available, policy, 20.6)
        self.assertEqual(chosen['track_id'], 'B')
        self.assertIsNone(reason)


if __name__ == '__main__':
    unittest.main()
