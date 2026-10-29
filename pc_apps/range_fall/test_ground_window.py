"""回归：自动配平窗口选择（head 保持旧口径；spread/wide/all 覆盖整段且留出互斥）。"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'exp_2d3d'))

import ablate  # noqa: E402


class GroundWindowTest(unittest.TestCase):
    def test_head_keeps_legacy_window_for_long_sessions(self):
        fit, held = ablate.ground_frame_window(386, 'head')
        self.assertEqual(fit, list(range(0, 50, 2)))
        self.assertEqual(held, [50, 75, 99])
        self.assertFalse(set(fit) & set(held))

    def test_spread_uses_whole_session_and_disjoint_holdouts(self):
        fit, held = ablate.ground_frame_window(126, 'spread')
        self.assertEqual(held, [41, 83, 125])
        self.assertEqual(len(fit), 50)
        self.assertLess(fit[0], 10)
        self.assertGreater(fit[-1], 115)
        self.assertFalse(set(fit) & set(held))

    def test_short_session_holdouts_stay_in_range(self):
        for kind in ('head', 'spread', 'wide'):
            fit, held = ablate.ground_frame_window(48, kind)
            self.assertTrue(all(0 <= i < 48 for i in fit + held), kind)
            self.assertFalse(set(fit) & set(held), kind)
            self.assertTrue(fit, kind)

    def test_wide_uses_every_non_holdout_frame_up_to_cap(self):
        fit, held = ablate.ground_frame_window(1000, 'wide')
        self.assertEqual(len(fit), 120)
        self.assertEqual(len(held), 3)

    def test_too_short_session_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'at least 4 frames'):
            ablate.ground_frame_window(3, 'head')


if __name__ == '__main__':
    unittest.main()