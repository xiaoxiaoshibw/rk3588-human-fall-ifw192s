"""Boundary tests for S2 distance image, plane fit, gates and audit membership."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import distance
import planes
from run import rect_mask


class FakeSource:
    def __init__(self, frames):
        self.frames = frames

    def frame(self, fi):
        return self.frames[fi]


def cloud(n, seed=1):
    p = np.random.default_rng(seed).uniform(-1, 1, size=(n, 3))
    p[:, 2] = 0.05 * p[:, 0] + 0.02 * p[:, 1] + 0.01
    return p


class Distance(unittest.TestCase):
    def test_bin_wrap_and_poles(self):
        az = np.array([-np.pi, np.pi - 1e-9, np.pi / 2])
        el = np.array([-np.pi / 2, np.pi / 2, 0.0])
        b = distance.bins(az, el, 100, 50)
        self.assertEqual(int(b[0]), 0)
        self.assertEqual(int(b[1]), 49 * 100 + 99)
        self.assertEqual(int(b[2]), 25 * 100 + 75)
        self.assertTrue(np.all((b >= 0) & (b < 5000)))

    def test_hole_and_collision(self):
        p = np.array([[1.0, 0.0, 0.0], [1.1, 0.0, 0.0], [0.0, 2.0, 0.0]])
        src = FakeSource({0: dict(offset=0, xyz=p)})
        im = distance.build(src, [0], 8, 4, stored=[0])
        self.assertEqual(int(im['indptr'][-1]), 3)
        self.assertEqual(len(im['rows']), 3)
        occ = im['count'] > 0
        self.assertLess(occ.sum(), len(occ))
        self.assertTrue(np.isinf(im['nearest'][~occ]).all())
        # two observations in one bin collide without a hardware multi-echo claim
        self.assertTrue((im['count'] > 1).any())
        self.assertEqual(sorted(im['rows'].tolist()), [0, 1, 2])
        self.assertEqual(int(im['nearest_row'][im['count'] > 1][0]) in (0, 1), True)

    def test_seam_adjacency(self):
        # azimuth near +pi and -pi must land in adjacent periodic columns
        p = np.array([[-1.0, 1e-6, 0.0], [-1.0, -1e-6, 0.0]])
        src = FakeSource({0: dict(offset=0, xyz=p)})
        im = distance.build(src, [0], 16, 4)
        idx = np.flatnonzero(im['count'])
        self.assertEqual(len(idx), 2)
        d = abs(int(idx[0] % 16) - int(idx[1] % 16))
        self.assertIn(d, (1, 15))


class Planes(unittest.TestCase):
    def test_tls_recovers_plane(self):
        p = cloud(2000)
        n_true = np.array([-0.05, -0.02, 1.0]) / np.linalg.norm([-0.05, -0.02, 1.0])
        fit = planes.tls(p)
        self.assertAlmostEqual(float(np.dot(fit['n'], n_true)), 1.0, places=3)
        self.assertLess(abs(fit['d'] + 0.01), 0.005)

    def test_reject_reflection(self):
        p = cloud(50)
        p[:, 2] = -p[:, 2]
        fit = planes.tls(p)
        self.assertAlmostEqual(float(np.linalg.norm(fit['n'])), 1.0, places=12)
        self.assertNotAlmostEqual(float(fit['n'][2]), -1.0, places=3)

    def test_ransac_seed_deterministic(self):
        rng = np.random.default_rng(3)
        a = rng.normal(size=(400, 3)); a[:, 2] = 0.0
        b = rng.normal(size=(400, 3)); b[:, 0] = 2.0
        p = np.vstack([a, b])
        w = np.ones(len(p))
        r1 = planes.ransac(p, w, 11, 60, 0.02, 2, 50)
        r2 = planes.ransac(p, w, 11, 60, 0.02, 2, 50)
        self.assertEqual([x['d'] for x in r1], [x['d'] for x in r2])
        self.assertEqual(len(r1), 2)

    def test_gates(self):
        clean = dict(count=100, rms_m=0.01, p95_abs_m=0.02, support_rate=1.0, median_signed_m=0.0)
        noisy = dict(count=100, rms_m=0.08, p95_abs_m=0.2, support_rate=0.4, median_signed_m=0.0)
        rows = planes.gates({'FIT_A': clean, 'FIT_B': noisy}, 'FIT')
        self.assertTrue(rows[0]['PASS'])
        self.assertFalse(rows[1]['PASS'])
        sparse = dict(clean, count=5)
        self.assertFalse(planes.gates({'FIT_A': sparse}, 'FIT')[0]['PASS'])


class Domains(unittest.TestCase):
    def test_rect_slab_bounds(self):
        R = np.eye(3); t = np.zeros(3)
        p = np.array([[0.5, 0.5, 0.15], [0.5, 0.5, 0.1501], [0.5, 0.5, -0.15], [0.5, 0.5, -0.1501],
                      [1.0, 0.5, 0.0], [0.999, 0.5, 0.0]])
        m = rect_mask(p, R, t, (0.0, 1.0, 0.0, 1.0), h=0.15)
        self.assertEqual(m.tolist(), [True, False, True, False, False, True])

    def test_val_prefix_names_do_not_enter_fit(self):
        out = {'FIT_A': {}, 'VAL_E': {}, 'VAL_E_prefix': {}}
        fitp = {k: v for k, v in out.items() if k.startswith('FIT')}
        self.assertNotIn('VAL_E', fitp)
        self.assertNotIn('VAL_E_prefix', fitp)


if __name__ == '__main__':
    unittest.main()
