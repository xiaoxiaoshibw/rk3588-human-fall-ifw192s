"""Independent HF03 contracts; synthetic, never allocates a large SVD."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/human_fall_detection"))
from core.calibration import build_geometry_calibration, GeometryCalibrationError
from core.ground import fit_ground_plane


def plane(z=-1.5):
    x, y = np.meshgrid(np.linspace(-2, 2, 20), np.linspace(-2, 2, 20))
    return np.column_stack((x.ravel(), y.ravel(), np.full(x.size, z)))


SETTINGS = {"range_min_m": 0.0, "min_inliers": 60,
            "ransac_iterations": 35, "seed": 7}


class GeometryContracts(unittest.TestCase):
    def test_floor_below_sensor_has_positive_height(self):
        result = fit_ground_plane(plane(), SETTINGS, frame="innolidar")
        self.assertEqual(result["status"], "valid", result)
        self.assertAlmostEqual(result["offset_m"], 1.5, places=6)
        self.assertAlmostEqual(result["sensor_height_m"], 1.5, places=6)

    def test_plane_above_sensor_is_not_valid_ground(self):
        result = fit_ground_plane(plane(1.5), SETTINGS, frame="innolidar")
        self.assertNotEqual(result["status"], "valid", result)

    def test_svd_is_thin_so_point_cap_does_not_allocate_n_squared(self):
        original = np.linalg.svd

        def bounded_svd(array, *args, **kwargs):
            self.assertIs(kwargs.get("full_matrices"), False,
                          "default SVD creates NxN U; use full_matrices=False")
            return original(array, *args, **kwargs)

        with patch("numpy.linalg.svd", side_effect=bounded_svd):
            fit_ground_plane(plane(), SETTINGS)

    def test_disjoint_holdout_plane_cannot_pass_validation(self):
        points = plane()
        order = np.random.RandomState(7).permutation(len(points))
        holdout = order[:int(len(points) * 0.3)]
        points[holdout, 2] = -4.0
        result = fit_ground_plane(points, SETTINGS)
        self.assertNotEqual(result["status"], "valid", result)

    def test_nonunit_ground_normal_is_rejected_in_artifact(self):
        with self.assertRaises(GeometryCalibrationError):
            build_geometry_calibration(
                "bad", "2026-10-01T00:00:00Z", "innolidar",
                ground={"status": "valid", "normal": [0, 0, 2], "offset_m": 1.5})

    def test_dominant_ground_with_other_scene_objects_is_still_valid(self):
        rng = np.random.RandomState(19)
        objects = np.column_stack((rng.uniform(-2, 2, 140),
                                   rng.uniform(-2, 2, 140),
                                   rng.uniform(0.2, 1.5, 140)))
        # 400 floor points + 140 non-floor points: the training and holdout
        # contain a clear dominant floor, as expected in an ordinary room.
        result = fit_ground_plane(np.vstack((plane(), objects)), SETTINGS,
                                  frame="innolidar")
        self.assertEqual(result["status"], "valid", result)
        self.assertAlmostEqual(result["sensor_height_m"], 1.5, places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
