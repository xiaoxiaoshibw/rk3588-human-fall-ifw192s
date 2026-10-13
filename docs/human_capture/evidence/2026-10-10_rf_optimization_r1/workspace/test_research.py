import unittest
import numpy as np
from prepare import extra, shape
from experiment import choose_threshold, grouped_splits, no_cross_group_duplicates, probability, make, optional_mean, present_class_score


class ResearchChecks(unittest.TestCase):
    def test_geometry_degenerate_sparse_and_nonfinite(self):
        self.assertTrue(np.array_equal(extra(np.zeros((9,4))),np.zeros(18)))
        self.assertTrue(np.isfinite(extra(np.zeros((20,4)))).all())
        self.assertTrue(np.array_equal(shape(np.zeros((20,3))),np.zeros(3)))
        with self.assertRaises(ValueError): extra(np.full((20,4),np.nan))
        cloud=np.random.default_rng(9).normal(size=(100,4)).astype(np.float32)
        np.testing.assert_allclose(extra(cloud),extra(cloud[::-1]),rtol=1e-6,atol=1e-6)
        self.assertAlmostEqual(float(extra(cloud)[:5].sum()),1.,places=6)

    def test_group_and_duplicate_guards(self):
        X=np.arange(48).reshape(12,4); y=np.tile([0,1],6); g=np.repeat(['a','b','c'],4)
        for tr,va in grouped_splits(X,y,g): self.assertFalse(set(g[tr])&set(g[va]))
        with self.assertRaises(ValueError): grouped_splits(X,np.zeros(12),g)
        X[4]=X[0]
        with self.assertRaises(ValueError): no_cross_group_duplicates(X,g)

    def test_threshold_and_dimension(self):
        t,reached=choose_threshold(np.array([0,0,1,1]),np.array([.1,.4,.8,.9]))
        self.assertTrue(reached)
        self.assertGreater(t,.4)
        self.assertLessEqual(t,.8)
        X=np.arange(69*4).reshape(4,69)
        model=make('rf',dict(max_depth=2)).fit(X,[0,1,0,1])
        self.assertEqual(model.n_features_in_,69)
        with self.assertRaises(ValueError): probability(model,X[:,:51])

    def test_single_class_score_and_missing_recall(self):
        # 复核原文称单类分数恒1不成立；单类召回仍随误判下降。
        self.assertEqual(present_class_score(np.array([1,1]),np.array([0,1])),.5)
        self.assertEqual(optional_mean([None,.5,1]),.75)
        self.assertIsNone(optional_mean([None,None]))


if __name__=='__main__': unittest.main()
