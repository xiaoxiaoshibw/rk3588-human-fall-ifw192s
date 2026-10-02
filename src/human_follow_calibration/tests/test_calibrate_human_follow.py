import math
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from calibrate_human_follow import (CalibrationError, background_from_frames,
                                    calibrate_frames, xyz_from_cloud)
from monitor_human_follow import target_state


ROI = {"x_min_m": 0.6, "x_max_m": 6.0, "y_min_m": -2.0, "y_max_m": 2.0,
       "z_min_m": -0.2, "z_max_m": 2.2}
SETTINGS = {"background_cell_m": 0.1, "background_z_cell_m": 0.1,
            "cluster_cell_m": 0.2,
            "min_cluster_points": 60, "min_height_m": 0.45,
            "max_height_m": 2.4, "max_depth_m": 1.2,
            "max_width_m": 1.2, "stand_tolerance_m": 0.8,
            "min_valid_fraction": 0.6, "max_stationary_spread_m": 0.35}


class CalibrationTest(unittest.TestCase):
    def test_padded_pointcloud_filters_zero_and_nan(self):
        coordinates = [[(0, 0, 0), (2.0, 0.1, 1.0), (float("nan"), 0, 0)],
                       [(3.0, -0.2, 0.8), (0.1, 0, 0), (4.0, 0, 1.2)]]
        width, height, step = 3, 2, 26
        row_step = width * step + 4
        data = bytearray(height * row_step)
        for row, items in enumerate(coordinates):
            for column, point in enumerate(items):
                struct.pack_into("<fff", data, row * row_step + column * step, *point)
        fields = [SimpleNamespace(name=name, offset=i * 4, datatype=7, count=1)
                  for i, name in enumerate(("x", "y", "z"))]
        msg = SimpleNamespace(width=width, height=height, point_step=step,
                              row_step=row_step, data=data, fields=fields,
                              is_bigendian=False)
        points = xyz_from_cloud(msg, 0.3)
        self.assertEqual(points.shape, (3, 3))
        np.testing.assert_allclose(points[:, 0], [2, 3, 4])
        msg.fields = fields[:-1]
        with self.assertRaises(CalibrationError):
            xyz_from_cloud(msg, 0.3)

    def test_stationary_target_and_ambiguous_scene(self):
        rng = np.random.default_rng(7)
        wall = np.column_stack((np.full(500, 5.5), rng.uniform(-1.5, 1.5, 500),
                                rng.uniform(0, 2, 500)))
        floor = np.column_stack((rng.uniform(1.7, 2.3, 300),
                                 rng.uniform(-0.4, 0.4, 300),
                                 np.full(300, -0.1)))
        scene = np.vstack((wall, floor))
        empty = [scene.copy() for _ in range(12)]

        def person(y):
            return np.column_stack((rng.normal(2.0, 0.09, 320),
                                    rng.normal(y, 0.10, 320),
                                    rng.uniform(0, 1.8, 320)))

        occupied = [np.vstack((scene, person(0.18))) for _ in range(12)]
        result = calibrate_frames(empty, occupied, 2.0, 1.5, ROI, SETTINGS)
        background = background_from_frames(empty[:8], ROI, 0.1, 0.1)
        calibration = {"roi": ROI, "thresholds": SETTINGS,
                       "bearing_offset_rad": result["bearing_offset_rad"],
                       "preferred_follow_distance_m": 1.5}
        self.assertEqual(target_state(empty[8], background, calibration)["status"], "absent")
        state = target_state(occupied[0], background, calibration)
        self.assertEqual(state["status"], "present")
        self.assertAlmostEqual(state["follow_error_m"], state["distance_m"] - 1.5)
        self.assertLess(abs(state["bearing_rad"]), 0.05)
        self.assertEqual(result["valid_person_frames"], 12)
        self.assertAlmostEqual(result["preferred_follow_distance_m"], 1.5)
        self.assertLess(abs(result["measured_distance_m"] - 2.0), 0.12)
        self.assertLess(abs(result["bearing_offset_rad"] - math.atan2(0.18, 2.0)), 0.05)
        distant = person(1.2)
        distant[:, 0] += 2.0
        bridge = np.column_stack((np.linspace(2.2, 3.8, 80),
                                  np.linspace(0.2, 1.1, 80), np.full(80, 0.25)))
        with_distant_change = [np.vstack((frame, distant, bridge)) for frame in occupied]
        self.assertEqual(calibrate_frames(empty, with_distant_change, 2.0, 1.5,
                                          ROI, SETTINGS)["valid_person_frames"], 12)
        with self.assertRaisesRegex(CalibrationError, "target absent"):
            calibrate_frames(empty, empty, 2.0, 1.5, ROI, SETTINGS)
        ambiguous = [np.vstack((scene, person(-0.7), person(0.7))) for _ in range(12)]
        self.assertEqual(target_state(ambiguous[0], background, calibration)["status"],
                         "ambiguous")
        with self.assertRaisesRegex(CalibrationError, "multiple"):
            calibrate_frames(empty, ambiguous, 2.0, 1.5, ROI, SETTINGS)
        moved = [np.vstack((scene + (0.4, 0, 0), person(0.18))) for _ in range(12)]
        with self.assertRaisesRegex(CalibrationError, "scene changed"):
            calibrate_frames(empty, moved, 2.0, 1.5, ROI, SETTINGS)


if __name__ == "__main__":
    unittest.main()
