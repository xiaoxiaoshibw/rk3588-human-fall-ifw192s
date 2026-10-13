"""DET-06 fix round regression: sub-voxel and reduced-cap pillar sampling. Synthetic only."""
import unittest

import numpy as np
import torch

from cpu_pointpillars import Voxelization
from det06_fix_probe import FixProbe, subvox_select, zrank_cap_select


def make_cloud():
    rng = np.random.default_rng(0)
    pts = np.zeros((103, 4), dtype='f4')
    pts[:100, 0] = 0.1 + 0.05 * rng.random(100)
    pts[:100, 1] = 0.1 + 0.05 * rng.random(100)
    pts[:100, 2] = 0.1 + 1.8 * rng.random(100)
    pts[:100, 3] = 0.5
    pts[100:, 0] = 5.0
    pts[100:, 1] = 5.0
    pts[100:, 2] = 0.3
    pts[100:, 3] = 0.5
    return pts


class TestSelectors(unittest.TestCase):
    def test_subvox_cap_coverage_determinism(self):
        pts = make_cloud()
        ids = np.arange(100, dtype='i8')
        bounds = np.array([0, -39.68, -3, 69.12, 39.68, 1], dtype='f4')
        sel = subvox_select(pts, ids, bounds, np.array([.04, .04, .08], 'f4'), 32)
        self.assertLessEqual(len(sel), 32)
        self.assertTrue(len(set(sel.tolist())) == len(sel))
        self.assertLess(pts[sel, 2].min(), 0.3)   # endpoints kept: low
        self.assertGreater(pts[sel, 2].max(), 1.7)  # endpoints kept: high
        np.testing.assert_array_equal(sel, subvox_select(pts, ids, bounds, np.array([.04, .04, .08], 'f4'), 32))

    def test_zrank11(self):
        pts = make_cloud()
        ids = np.arange(100, dtype='i8')
        sel = zrank_cap_select(pts, ids, 11)
        self.assertEqual(len(sel), 11)
        self.assertLess(pts[sel, 2].min(), 0.3)
        self.assertGreater(pts[sel, 2].max(), 1.7)


class TestProbe(unittest.TestCase):
    def probe(self, mode):
        base = Voxelization([.16, .16, 4], [0, -39.68, -3, 69.12, 39.68, 1], 32, (16000, 40000))
        probe = FixProbe(base)
        probe.mode = mode
        return probe, base

    def test_subvox32_full_pipeline(self):
        pts = make_cloud()
        probe, base = self.probe('subvox32')
        vox, coords, counts = probe(torch.from_numpy(pts))
        c = counts.numpy()
        self.assertLessEqual(int(c.max()), 32)
        self.assertEqual(int(c.sum()), 32 + 3)
        for j, n in enumerate(c):
            if n < 32:
                np.testing.assert_array_equal(vox[j, n:].numpy(), np.zeros((32 - n, 4), 'f4'))

    def test_zrank11_pipeline(self):
        pts = make_cloud()
        probe, base = self.probe('zrank11')
        vox, coords, counts = probe(torch.from_numpy(pts))
        c = counts.numpy()
        self.assertLessEqual(int(c.max()), 11)
        self.assertEqual(int(c.sum()), 11 + 3)


if __name__ == '__main__':
    unittest.main()
