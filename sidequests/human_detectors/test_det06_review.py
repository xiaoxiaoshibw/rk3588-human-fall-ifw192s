"""DET-06 review regression: rotated-box AABB extent, operating-point tie-break. Synthetic only."""
import unittest

import numpy as np

from det06_review_offline import footprint_extent, operating


class TestGeometry(unittest.TestCase):
    def test_extent_follows_yaw(self):
        ex, ey = footprint_extent(np.array([0, 0, 0, .6, .8, 1.7, 0.0]))
        self.assertAlmostEqual(ex, .6)
        self.assertAlmostEqual(ey, .8)
        ex, ey = footprint_extent(np.array([0, 0, 0, .6, .8, 1.7, np.pi / 2]))
        self.assertAlmostEqual(ex, .8)
        self.assertAlmostEqual(ey, .6)
        ex, ey = footprint_extent(np.array([0, 0, 0, .6, .8, 1.7, np.pi / 4]))
        self.assertAlmostEqual(ex, (.6 + .8) / np.sqrt(2))


class TestOperatingPoint(unittest.TestCase):
    def test_budget_and_tie_break(self):
        table = {'0.1': dict(recall_center=.5, fp_per_frame=.05),
                 '0.2': dict(recall_center=.9, fp_per_frame=.4),
                 '0.3': dict(recall_center=.9, fp_per_frame=.3)}
        ops = operating(table)
        self.assertEqual(ops['0.5']['tau'], .3)  # equal recall -> lower FP wins
        self.assertEqual(ops['0.1']['tau'], .1)
        self.assertIsNone(operating({'0.1': dict(recall_center=.9, fp_per_frame=.4)})['0.1'])


if __name__ == '__main__':
    unittest.main()
