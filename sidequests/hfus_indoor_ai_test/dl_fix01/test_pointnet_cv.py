"""HFUS-DL-OPT-01 合成自验：python -B -W error -m unittest discover -s sidequests/hfus_indoor_ai_test/dl_fix01"""
import unittest

import numpy as np

import pointnet_cv as pc


class TestProtocol(unittest.TestCase):
    def test_pos_weight_uses_sampled_fold_distribution(self):
        y = np.array([1] * 4 + [0] * 96)
        sub = pc.sample_subset(y, cap=16, seed=1)  # 全 4 正 + 负采样 12
        self.assertEqual(len(sub), 16)
        self.assertAlmostEqual(pc.pos_weight_from(y[sub]), 3.0)   # 采样口径
        self.assertNotAlmostEqual(pc.pos_weight_from(y[sub]), 24.0)  # 全局口径（缺陷 2）不得使用
        with self.assertRaises(ValueError):
            pc.pos_weight_from(np.zeros(5, dtype=int))

    def test_fresh_model_and_optimizer_per_fold(self):
        x, y = pc.synthetic_clouds(8, 24, points_per=16, seed=3)
        folds = [np.arange(0, 16), np.arange(16, 32)]
        res = pc.run_cv(x, y, folds, steps=3, seed=43)
        self.assertTrue(all(not f["model_reused"] for f in res["folds"]))       # 缺陷 1
        self.assertEqual(len({f["init_hash"] for f in res["folds"]}), 1)        # 同 seed 全新初始化
        self.assertNotEqual(res["folds"][0]["final_hash"], res["folds"][1]["final_hash"])
        leaky = pc.run_cv(x, y, folds, steps=3, seed=43, carry_state=True)      # 旧缺陷对照
        self.assertTrue(leaky["folds"][1]["model_reused"])

    def test_oof_unseen_and_full_cover(self):
        x, y = pc.synthetic_clouds(12, 20, points_per=16, seed=4)
        folds = pc._folds(len(y))
        res = pc.run_cv(x, y, folds, steps=3, seed=43)
        self.assertFalse(np.isnan(res["oof"]).any())                            # 缺陷 3：1:1 覆盖
        self.assertEqual(len(res["oof"]), len(y))
        self.assertEqual([f["prev_seen_in_val"] for f in res["folds"]], [0, 0, 0, 0])
        leaky = pc.run_cv(x, y, folds, steps=3, seed=43, carry_state=True)
        self.assertGreater(leaky["folds"][1]["prev_seen_in_val"], 0)            # 复现跨折污染

    def test_separable_learn_and_determinism(self):
        x, y = pc.synthetic_clouds(24, 56, points_per=32, seed=5)
        folds = pc._folds(len(y))
        r1 = pc.run_cv(x, y, folds, steps=200, lr=2e-2, seed=43)
        m = pc.oof_metrics(y, r1["oof"])
        self.assertGreaterEqual(m["precision"], 0.9)
        self.assertGreaterEqual(m["recall"], 0.9)
        r2 = pc.run_cv(x, y, folds, steps=200, lr=2e-2, seed=43)
        np.testing.assert_array_equal(r1["oof"], r2["oof"])                     # 同 seed 逐值一致


if __name__ == "__main__":
    unittest.main()
