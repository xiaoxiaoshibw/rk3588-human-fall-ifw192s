import unittest
from pathlib import Path

import numpy as np
import yaml
from core import cluster, decode_indices, roi_mask, sample_points, skeleton


class PointSetChecks(unittest.TestCase):
    def setUp(self):
        self.cfg = yaml.safe_load((Path(__file__).parent/'config.yaml').read_text(encoding='utf-8'))

    def test_3d_separates_xy_overlap(self):
        grid = np.array([[x, y, z] for x in np.arange(0, .35, .05) for y in np.arange(0, .35, .05)
                         for z in np.arange(0, .2, .05)])
        cloud = np.r_[grid, grid+[0, 0, 1]]
        a, _ = cluster(cloud, self.cfg, 3)
        b, _ = cluster(cloud, self.cfg, 2)
        self.assertEqual(len(a), 2)
        self.assertEqual(len(b), 1)
        self.assertEqual(len(np.unique(np.concatenate(a))), len(cloud))

    def test_compact_gt_indices_and_invalid(self):
        np.testing.assert_array_equal(decode_indices(['m', [2, 3, 3], [15]]), [2, 5, 8, 15])
        with self.assertRaises(ValueError):
            decode_indices(['s', 2, 2])
        with self.assertRaises(ValueError):
            decode_indices(['x', 2])

    def test_roi_and_centered_sample(self):
        p = np.array([[.5, .5, 0], [2, 2, 0], [.2, .5, .1]])
        np.testing.assert_array_equal(roi_mask(p, [[0, 0], [1, 0], [1, 1], [0, 1]]), [True, False, True])
        sampled = sample_points(p)
        self.assertEqual(sampled.shape, (256, 3))
        np.testing.assert_allclose(sampled.mean(axis=0), 0, atol=1e-6)

    def test_lying_support_and_no_fake_anatomy(self):
        rng = np.random.default_rng(3)
        p = np.column_stack([rng.uniform(0, 1.8, 600), rng.uniform(-.2, .2, 600), rng.uniform(.01, .12, 600)])
        ids = np.arange(1000, 1600)
        result = skeleton(p, ids, self.cfg)
        self.assertEqual(result['head_identity'], 'UNKNOWN')
        self.assertTrue(any(n['valid'] for n in result['nodes'].values()))
        for n in result['nodes'].values():
            self.assertTrue(set(n['support_source_indices']).issubset(ids))
        ambiguous = rng.uniform(-.3, .3, (600, 3))
        self.assertFalse(any(n['valid'] for n in skeleton(ambiguous, ids, self.cfg)['nodes'].values()))


if __name__ == '__main__':
    unittest.main()
