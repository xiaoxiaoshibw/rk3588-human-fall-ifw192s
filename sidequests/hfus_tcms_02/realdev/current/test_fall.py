"""Regression for the causal track/fall adapter used by the active pipeline."""

# Explicit legacy acquisition keeps these original lifecycle contracts covered.
import unittest

import numpy as np
from project_fall import FallRuntime, body_candidate


def candidate(height, verticality=0.9, points=800):
    return dict(candidate_id='body', ground_relative_available=True,
                center_reference_m=[0.0, 0.0, height],
                height_m=dict(min=max(0.0, height - .2), p10=max(0.0, height - .15),
                              median=height, p90=height + .15, max=height + .2),
                horizontal_extent_m=dict(max=.5), point_count=points,
                axis=dict(ambiguous=False, verticality=verticality))


class FallAdapter(unittest.TestCase):
    def test_suspected_is_the_ceiling_without_human_label(self):
        runtime = FallRuntime('SYNTHETIC_IN_CONTRACT', 'ground:test', acquisition_settings={'human_entry_gate': False})
        t = 0.0
        states = []
        for _ in range(20):
            states.append(runtime.step(t, candidate(1.2))['fall']['status']); t += .1
        # Keep the original narrow-span sample: it cannot prove an upright
        # stance under the shared 0.4m span / 3s policy.
        self.assertIsNone(runtime.baseline)
        for _ in range(45):
            stance = candidate(1.2)
            stance['height_m'].update(p10=.1, p90=1.6, max=1.7)
            states.append(runtime.step(t, stance)['fall']['status']); t += .1
        self.assertIsNotNone(runtime.baseline)
        for height in (1.1, .9, .7, .5):
            states.append(runtime.step(t, candidate(height))['fall']['status']); t += .1
        for _ in range(20):
            states.append(runtime.step(t, candidate(.3))['fall']['status']); t += .1
        self.assertIn('upright', states)
        self.assertIn('suspected', states)
        self.assertNotIn('confirmed', states)
        self.assertEqual(runtime.machine.events, [])
        self.assertFalse(runtime.machine.confirmed_enabled)

    def test_recovery_does_not_inherit_baseline_or_action_history(self):
        runtime = FallRuntime('SYNTHETIC_RECOVERY', 'ground:test')
        t = 0.0
        for i in range(25):
            c = candidate(1.2)
            c['center_reference_m'] = [2.0 + .06*i, 0.0, 1.2]
            runtime.step(t, c); t += .1
        self.assertEqual(runtime.tracker.track_status, 'locked')
        old_track = runtime.tracker.track_id
        old_generation = runtime.tracker.action_generation
        for _ in range(45):
            c = candidate(1.2)
            c['center_reference_m'] = [3.44, 0.0, 1.2]
            c['height_m'].update(p10=.15, p90=1.6, max=1.7)
            runtime.step(t, c); t += .1
        self.assertIsNotNone(runtime.baseline)
        old_baseline = runtime.baseline
        for _ in range(10):
            runtime.step(t, None); t += .1
        self.assertEqual(runtime.tracker.track_status, 'occluded')
        new = None
        for _ in range(3):
            c = candidate(1.2)
            c['center_reference_m'] = [3.44, 0.0, 1.2]
            new = runtime.step(t, c); t += .1
        self.assertNotEqual(new['track']['track_id'], old_track)
        self.assertGreater(new['track']['generation'], old_generation)
        self.assertIsNone(runtime.baseline)
        self.assertIsNot(old_baseline, runtime.baseline)
        self.assertNotEqual(old_baseline['track_id'], new['track']['track_id'])
        # The narrow synthetic stance does not qualify for a new baseline;
        # what matters is that the old one is no longer consumable.
        self.assertIsNone(runtime.baseline_collector.track_id)
        self.assertEqual(len(runtime.tracker.action_history), 1)

    def test_prediction_is_not_an_observation(self):
        runtime = FallRuntime('SYNTHETIC_IN_CONTRACT', 'ground:test', acquisition_settings={'human_entry_gate': False})
        for index in range(20):
            runtime.step(index * .1, candidate(1.2))
        out = runtime.step(2.0, None)
        self.assertEqual(out['track']['status'], 'occluded')
        self.assertTrue(out['track']['predicted'])
        self.assertEqual(out['fall']['status'], 'unknown')
        self.assertIn('prediction_not_observation', out['fall']['reasons'])

    def test_relock_after_timeout_gets_a_new_track(self):
        runtime = FallRuntime('SYNTHETIC_IN_CONTRACT', 'ground:test', acquisition_settings={'human_entry_gate': False})
        for index in range(7):first = runtime.step(index*.1, candidate(1.2))
        self.assertEqual(first['track']['track_id'], 't0001')
        for index in range(45):
            runtime.step(0.7 + index * .1, None)
        self.assertEqual(runtime.acquisition.state['status'], 'searching')
        for index in range(7):again = runtime.step(6.0+index*.1, candidate(1.2))
        self.assertEqual(again['track']['track_id'], 't0002')
        self.assertEqual(again['track']['status'], 'locked')

    def test_body_candidate_floor_and_height(self):
        points = np.zeros((10, 3))
        self.assertIsNone(body_candidate(points))
        grid = np.stack(np.meshgrid(np.linspace(0, .4, 8), np.linspace(0, .4, 8),
                                    np.linspace(0, 1.6, 8)), -1).reshape(-1, 3)
        body = body_candidate(grid)
        self.assertEqual(body['point_count'], len(grid))
        self.assertAlmostEqual(body['height_m']['median'], np.median(grid[:, 2]))
        self.assertGreater(body['axis']['verticality'], .9)


if __name__ == '__main__':
    unittest.main()
