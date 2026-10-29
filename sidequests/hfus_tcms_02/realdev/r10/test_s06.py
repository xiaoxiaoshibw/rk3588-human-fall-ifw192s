"""Focused regression of the single S06 semantic change and ledger contract."""
import copy
import unittest

import numpy as np
from scipy.spatial import cKDTree

import s06 as S


class ForegroundTest(unittest.TestCase):
    def setUp(self):
        self.pipe = S.setup()
        self.cls = S.envelope_class(self.pipe)

    def fake_map(self, cls):
        m = object.__new__(cls)
        m.centers = np.array([[1., 0., .02], [2., 0., .02]])
        m.minimum = m.centers - [.02, .02, .02]
        m.maximum = m.centers + [.02, .02, .02]
        m.noise = np.full((2, 3), .01)
        m.protocol = {'map': {'tau': .08}}
        m.tree_ids = np.arange(2)
        m.tree = cKDTree(m.centers)
        return m

    def test_strict_contact_envelope_and_same_nearest_surface(self):
        main = self.fake_map(self.pipe.FrozenMap)
        variant = self.fake_map(self.cls)
        points = np.array([[1., 0., .05], [1., 0., np.nextafter(.05, np.inf)],
                           [1., 0., .10], [1., 0., .10001], [1., 0., -.04],
                           [1., 0., np.nan], [0., 0., 0.], [2., 0., .06], [3., 0., .06]])
        valid = self.pipe.validity(points)[1]
        b0, d0, s0 = main.match(points, valid)
        b1, d1, s1 = variant.match(points, valid)
        self.assertEqual(b0.tolist(), [True, True, True, False, True, False, False, True, False])
        self.assertEqual(b1.tolist(), [True, False, False, False, True, False, False, False, False])
        np.testing.assert_array_equal(d0, d1)
        np.testing.assert_array_equal(s0, s1)
        for name in ('maximum', 'minimum', 'noise', 'tree_ids'):
            np.testing.assert_array_equal(getattr(main, name), getattr(variant, name))

    def test_no_eligible_surface_and_noncontact_main_equivalence(self):
        for cls in (self.cls, self.pipe.FrozenMap):
            m = self.fake_map(cls); m.tree = None
            bg, _, surface = m.match(np.array([[1., 0., .06]]), np.array([True]))
            self.assertFalse(bg.any()); self.assertEqual(surface[0], -1)
        rng = np.random.default_rng(17)
        points = rng.normal(size=(100, 3)); points[:, 2] += 1
        valid = self.pipe.validity(points)[1]
        a = self.fake_map(self.cls).match(points, valid)
        b = self.fake_map(self.pipe.FrozenMap).match(points, valid)
        for x,y in zip(a,b): np.testing.assert_array_equal(x,y)

    def test_envelope_does_not_expand_tau_or_aabb(self):
        main = self.fake_map(self.pipe.FrozenMap); variant = self.fake_map(self.cls)
        points = np.array([[1.2,0.,.02], [1.,0.,-.10], [1.,0.,.04]])
        a = main.match(points, np.ones(3,bool)); b = variant.match(points,np.ones(3,bool))
        for x,y in zip(a,b): np.testing.assert_array_equal(x,y)
        self.assertEqual(b[0].tolist(), [False,False,True])

    def test_ledger_single_candidate_threshold_and_overlap(self):
        ids = np.r_[np.zeros(29,int), np.ones(29,int), -1, -1]
        flags = np.r_[np.full(58,5,dtype='u1'),3,0]
        result = S.candidate_stats(ids,flags)
        self.assertEqual(result['candidate_rows'],58)
        self.assertEqual(result['measurable_candidate_count'],0)
        ids[29] = 0
        self.assertEqual(S.candidate_stats(ids,flags)['measurable_candidate_count'],1)
        flags[0] = 1
        with self.assertRaises(ValueError): S.candidate_stats(ids,flags)


if __name__ == '__main__': unittest.main()
