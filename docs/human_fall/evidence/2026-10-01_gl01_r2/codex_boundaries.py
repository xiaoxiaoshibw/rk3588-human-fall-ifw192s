"""Independent GL-01 input, independence and ambiguity regressions."""
import copy
import sys
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src/human_fall_detection'))
sys.path.insert(0, str(ROOT / 'src/human_fall_detection/tests'))
from core.ground import (fit_ground_plane_constrained, resolve_constrained_settings,
                         validate_constrained_ground)
from test_gl01_constrained_ground import clean_scene, plane_points


class IndependentBoundaries(unittest.TestCase):
    def fit(self, points, up, indices, regions, **kwargs):
        return fit_ground_plane_constrained(points, frame='innolidar', up_axis=up,
            sensor_height_interval_m=[0.4, 1.6], fit_indices=indices,
            validation_regions=regions, **kwargs)

    def test_missing_group_provenance_cannot_validate(self):
        points, up, fit, regions = clean_scene()
        for region in regions:
            region.pop('frame_group')
        result = self.fit(points, up, fit, regions)
        self.assertNotEqual(result['status'], 'valid')

    def test_mixed_bool_prior_is_rejected(self):
        points, up, fit, regions = clean_scene()
        with self.assertRaises(ValueError):
            self.fit(points, [True, 0.0, 1.0], fit, regions,
                     fit_frame_group='fit')

    def test_duplicate_region_identity_cannot_validate(self):
        points, up, fit, regions = clean_scene()
        for region in regions:
            region['region_id'] = 'same-region'
        result = self.fit(points, up, fit, regions, fit_frame_group='fit')
        self.assertNotEqual(result['status'], 'valid')

    def test_reduced_candidate_cap_cannot_hide_competition(self):
        up = np.array([0., 0., 1.])
        floor = plane_points(up, 1.2, 3000, noise=.005, seed=400)
        desk = plane_points(up, .45, 3000, noise=.005, seed=401)
        val = plane_points(up, 1.2, 300, noise=.005, seed=402)
        points = np.vstack([floor, desk, val])
        regions = [{'region_id': 'v'+str(i), 'frame_group': 'v'+str(i),
                    'indices': list(range(6000+i*100, 6100+i*100))}
                   for i in range(3)]
        try:
            result = self.fit(points, up, np.arange(6000), regions,
                fit_frame_group='fit', settings={'max_candidates': 1})
        except ValueError:
            return
        self.assertNotEqual(result['status'], 'valid')

    def test_declared_valid_artifact_needs_three_passing_regions(self):
        points, up, fit, regions = clean_scene()
        result = self.fit(points, up, fit, regions, fit_frame_group='fit')
        self.assertEqual(result['status'], 'valid')
        damaged = copy.deepcopy(result)
        damaged['validation_regions'] = [{'passed': False}]
        with self.assertRaises(ValueError):
            validate_constrained_ground(damaged)

    def test_strict_parameter_limits(self):
        for override in ({'seed': -1}, {'max_candidates': 4},
                         {'min_planar_eigenvalue_ratio': 1.1},
                         {'ransac_iteration_hard_cap': 2001}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                resolve_constrained_settings(override)


if __name__ == '__main__':
    unittest.main(verbosity=2)
