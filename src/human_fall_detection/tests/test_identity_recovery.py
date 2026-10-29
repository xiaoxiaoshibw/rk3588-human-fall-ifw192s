"""Falsifiable recovery contracts, synthetic geometry, no human GT."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.target_acquisition import TargetAcquisition
from core.tracking import TargetTracker
from test_human_entry_gate import candidate


class IdentityRecovery(unittest.TestCase):
    def start(self, **settings):
        a = TargetAcquisition(TargetTracker('synthetic_recovery'), settings)
        for i in range(25):
            a.step([candidate(x=2+.06*i), candidate('other', x=6., height=.45)], 0, i*.1)
        self.assertEqual(a.tracker.track_status, 'locked')
        # Stationary anchor removes velocity prediction as a confounder.
        for i in range(25,35):
            a.step([candidate(x=3.44), candidate('other', x=6., height=.45)], 0, i*.1)
        return a

    def test_long_gap_single_new_history_never_inherits_measurement(self):
        a = self.start()
        track, generation = a.tracker.track_id, a.tracker.action_generation
        a.step([], 0, 3.5)
        c = candidate('new31', x=3.44, height=1.865)
        c['point_count'] = 31
        state, acq, measured = a.step([c], 0, 5.68)
        self.assertIsNone(measured)
        self.assertTrue(state['position_predicted'])
        self.assertEqual(state['track_id'], track)
        self.assertEqual(state['action_generation'], generation)
        self.assertEqual(acq['rejected']['new31'], 'recovery_verification_pending')

    def test_repeated_unbacked_recovery_gets_new_binding_and_action_history(self):
        a = self.start()
        old, gen = a.tracker.track_id, a.tracker.action_generation
        a.step([], 0, 3.5)
        for t in (4.4,4.5,4.6):
            state, _, measured = a.step([candidate('new', x=3.44)], 0, t)
        self.assertIsNotNone(measured)
        self.assertNotEqual(state['track_id'], old)
        self.assertGreater(state['action_generation'], gen)
        self.assertEqual(len(a.tracker.action_history), 1)

    def test_known_non_target_survives_missing_frame_but_memory_expires(self):
        a = self.start()
        a.step([], 0, 3.5)
        _, acq, measured = a.step([candidate('return', x=6., height=.45)], 0, 4.7)
        self.assertIsNone(measured)
        self.assertEqual(acq['rejected']['return'], 'known_non_target_spatial_memory')
        # A new acquisition clears memory; it is not a permanent location ban.
        for i in range(48,80):
            a.step([], 0, i*.1)
        for i in range(80,110):
            state, _, measured = a.step([candidate('return', x=6.+.06*(i-80))], 0, i*.1)
        self.assertIsNotNone(measured)
        self.assertEqual(state['track_status'], 'locked')

    def test_short_gap_stationary_low_and_partial_support_stay_measured(self):
        a = self.start()
        old = a.tracker.track_id
        a.step([], 0, 3.5)
        for i in range(37,60):
            c = candidate(x=3.44, height=.45 if i>40 else 1.7)
            c['point_count'] = 31
            c['horizontal_extent_m']['max'] = .1
            state, _, measured = a.step([c], 0, i*.1)
            self.assertIsNotNone(measured)
            self.assertEqual(state['track_id'], old)


if __name__ == '__main__':
    unittest.main()
