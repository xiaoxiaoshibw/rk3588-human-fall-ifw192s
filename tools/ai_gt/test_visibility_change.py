import unittest
import numpy as np
from visibility_change import VisibilityChange


class VisibilityChangeTest(unittest.TestCase):
    def test_past_far_returns_support_new_near_return(self):
        cue = VisibilityChange()
        for t in [0., .1, .2]:
            mask, _ = cue.step([[4., 0, 0]], t, 'same')
            self.assertFalse(mask.any())
        mask, _ = cue.step([[2., 0, 0]], .3, 'same')
        self.assertTrue(mask[0])
        # A stopped object ceases to generate novelty. It must NOT be discarded
        # by a tracker on that basis; this tool deliberately is not a selector.
        mask, _ = cue.step([[2., 0, 0]], .4, 'same')
        self.assertFalse(mask.any())

    def test_missing_old_ray_is_unknown_and_jitter_is_not_motion(self):
        cue = VisibilityChange()
        for t in [0., .1, .2]:
            cue.step([[4., 0, 0]], t, 'same')
        mask, seen = cue.step([[2., 2., 0], [3.95, 0, 0]], .3, 'same')
        self.assertFalse(mask.any())
        self.assertEqual(seen[0], 0)

    def test_gap_binding_or_clock_change_clears_history(self):
        for stamp, binding in [(2., 'same'), (.1, 'same'), (.3, 'other')]:
            cue = VisibilityChange()
            for t in [0., .1, .2]:
                cue.step([[4., 0, 0]], t, 'same')
            mask, seen = cue.step([[2., 0, 0]], stamp, binding)
            self.assertFalse(mask.any())
            self.assertEqual(seen[0], 0)

    def test_future_does_not_change_prefix(self):
        def run(stamps):
            cue = VisibilityChange()
            return [cue.step([[4. if t < .3 else 2., 0, 0]], t, 'same')[0].tolist()
                    for t in stamps]
        self.assertEqual(run([0., .1, .2, .3]), run([0., .1, .2, .3, .4])[:4])

    def test_bad_source_clears_history(self):
        cue = VisibilityChange()
        cue.step([[4., 0, 0]], 0., 'same')
        with self.assertRaises(ValueError):
            cue.step([[np.nan, 0, 0]], .1, 'same')
        self.assertEqual(len(cue.history), 0)


if __name__ == '__main__':
    unittest.main()
