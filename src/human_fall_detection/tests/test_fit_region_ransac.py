"""Fit-domain candidate selection must preserve independent holdout rejection."""
import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.ground_fit.leveling_estimators.ransac import estimate
from core.ground_fit.leveling_quality import compare, FIT_REGION_RANSAC_VARIANT


class FitRegionRansacTests(unittest.TestCase):
    @staticmethod
    def domain():
        rng = np.random.RandomState(0)
        parts, labels = [], []
        for k, (count, center, offset, noise) in enumerate(zip(
                [300, 120, 250, 75], [[0, 0], [1, 0], [0, 1], [1, 1]],
                [-.01, .016, .004, -.020], [.018, .012, .012, .006]), 1):
            parts.append(np.column_stack((np.asarray(center)+rng.uniform(-.12, .12, (count, 2)),
                -1.3+offset+rng.normal(0, noise, count))))
            labels.extend([k]*count)
        return np.concatenate(parts), np.asarray(labels)

    def test_global_support_winner_cannot_sacrifice_a_fit_region(self):
        p, c = self.domain()
        held = [dict(ordinal=i, points=p.copy(), regions=c.copy()) for i in (25, 26, 27)]
        raw = compare(p, c, held, np.array([0, 0, 1]))
        result = compare(p, c, held, np.array([0, 0, 1]), fit_region_ransac=True)
        self.assertEqual(raw['consensus'], 'NO_RECOMMENDATION')
        self.assertGreater(raw['estimators']['ransac']['regions']['4']['rms_m'], .03)
        self.assertEqual(result['consensus'], 'GOOD')
        estimate_result = result['estimators']['ransac']
        self.assertEqual(estimate_result['estimator_variant'], FIT_REGION_RANSAC_VARIANT)
        self.assertTrue(estimate_result['fit_selection']['fit_feasible_found'])
        self.assertLess(estimate_result['fit_selection']['selected_support_count'],
                        estimate_result['fit_selection']['raw_support_count'])
        self.assertEqual(estimate_result['fit_selection']['policy'], 'fit_region_support_then_median')
        n, d = np.asarray(estimate_result['normal_source']), estimate_result['offset_source_m']
        self.assertGreaterEqual(int((np.abs(p@n+d) < 1e-10).sum()), 3)

    def test_holdouts_do_not_change_candidate_and_still_reject_shift(self):
        p, c = self.domain()
        def run(z):
            return compare(p, c, [dict(ordinal=25, points=p+[0, 0, z], regions=c)],
                           np.array([0, 0, 1]), fit_region_ransac=True)
        good, bad = run(0), run(.4)
        a, b = good['estimators']['ransac'], bad['estimators']['ransac']
        self.assertEqual(a['normal_source'], b['normal_source'])
        self.assertEqual(a['offset_source_m'], b['offset_source_m'])
        self.assertEqual(bad['consensus'], 'NO_RECOMMENDATION')
        self.assertIn('GL_HOLDOUT_QUALITY', b['reject_reasons'])

    def test_no_fit_candidate_returns_raw_for_explicit_rejection(self):
        p, _ = self.domain()
        raw = estimate(p)
        report = {}
        result = estimate(p, candidate_valid=lambda n, d: False, selection_report=report)
        np.testing.assert_array_equal(result[0], raw[0])
        self.assertEqual(result[1], raw[1])
        self.assertFalse(report['fit_feasible_found'])

    def test_raw_feasible_candidate_stays_identical(self):
        p, _ = self.domain()
        raw = estimate(p)
        result = estimate(p, candidate_valid=lambda n, d: True)
        np.testing.assert_array_equal(result[0], raw[0])
        self.assertEqual(result[1], raw[1])

    def test_non_coplanar_fit_regions_remain_rejected(self):
        p, c = self.domain()
        p[c == 4, 2] += .4
        result = compare(p, c, [dict(ordinal=25, points=p, regions=c)],
                         np.array([0, 0, 1]), fit_region_ransac=True)
        self.assertEqual(result['consensus'], 'NO_RECOMMENDATION')
        self.assertFalse(result['estimators']['ransac']['fit_selection']['fit_feasible_found'])

    def test_fit_frame_quality_uses_fit_ids_and_reports_each_region_group(self):
        p, c = self.domain()
        points = np.concatenate([p]*3)
        codes = np.tile(c, 3)
        frame_ids = np.repeat(np.arange(3), len(p))
        result = compare(points, codes, [dict(ordinal=25, points=p, regions=c)],
            np.array([0, 0, 1]), fit_region_ransac=True, fit_frame_ids=frame_ids)
        self.assertEqual(result['consensus'], 'GOOD')
        report = result['estimators']['ransac']['fit_selection']
        self.assertEqual(report['fit_frame_region_groups'], 12)
        self.assertLessEqual(report['worst_fit_frame_region_rms_m'], .03)


if __name__ == '__main__':
    unittest.main()
