import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))

from core.calibration import (GeometryCalibrationError, apply_rotation,
                              apply_transform, build_geometry_calibration,
                              invert_transform, length_to_meters, make_rotation,
                              make_transform, make_unknown_rotation,
                              make_unknown_transform, sensor_height_from_ground,
                              transform_matrix, validate_geometry_calibration,
                              validate_rotation, validate_translation)
from core.ground import (REASON_INSUFFICIENT, REASON_NOT_FOUND, REASON_ORIENTATION,
                         STATUS_INVALID, STATUS_ORIENTATION_UNVERIFIED,
                         STATUS_VALID, fit_ground_plane, ground_is_valid,
                         resolve_settings)
from sensor_health import dumps_strict


def rot_z(angle):
    c, s = math.cos(angle), math.sin(angle)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def plane_points(normal, height, count=6000, extent=8.0, noise=0.004, seed=3,
                 min_range=0.0):
    """Points on ``n . p + height = 0`` (normal points up, ground below sensor)."""
    normal = np.asarray(normal, dtype=np.float64)
    normal = normal / np.linalg.norm(normal)
    axis = np.array([1.0, 0.0, 0.0])
    if abs(float(normal @ axis)) > 0.9:
        axis = np.array([0.0, 1.0, 0.0])
    u = np.cross(normal, axis)
    u = u / np.linalg.norm(u)
    v = np.cross(normal, u)
    rng = np.random.RandomState(seed)
    spread = (rng.rand(count, 2) - 0.5) * extent
    points = spread[:, :1] * u + spread[:, 1:] * v - float(height) * normal
    points = points + rng.randn(count, 3) * noise
    ranges = np.linalg.norm(points, axis=1)
    return points[ranges >= min_range]


class RotationValidationTest(unittest.TestCase):
    def test_proper_rotations_are_accepted(self):
        self.assertTrue(np.allclose(validate_rotation(np.eye(3).tolist()), np.eye(3)))
        self.assertTrue(np.allclose(validate_rotation(rot_z(math.pi / 2)),
                                    rot_z(math.pi / 2)))

    def test_non_rigid_and_axis_flip_matrices_are_rejected(self):
        cases = {
            "non_orthonormal": [[2.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "sheared": [[1.0, 0.5, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "axis_sign_flip_reflection": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]],
            "singular": [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        }
        for name, matrix in cases.items():
            with self.subTest(name=name), self.assertRaises(GeometryCalibrationError):
                validate_rotation(matrix)
        for bad in ([[1.0, 0.0], [0.0, 1.0]], [[1.0, 0.0, 0.0]] * 3,
                    [[float("nan"), 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                    None):
            with self.subTest(bad=bad), self.assertRaises(GeometryCalibrationError):
                validate_rotation(bad)


class TransformDirectionTest(unittest.TestCase):
    def _transform(self, from_frame="innolidar", to_frame="site"):
        return make_transform(rot_z(0.3), [1.0, 0.0, 2.0], from_frame, to_frame,
                              evidence="synthetic")

    def test_apply_then_inverse_recovers_original_points(self):
        transform = self._transform()
        points = np.array([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0], [-2.0, -1.0, 0.5]])
        mapped = apply_transform(points, transform)
        recovered = apply_transform(mapped, invert_transform(transform))
        self.assertTrue(np.allclose(recovered, points, atol=1e-9))
        matrix = transform_matrix(transform)
        self.assertEqual((matrix[3] == np.array([0.0, 0.0, 0.0, 1.0])).all(), True)
        self.assertEqual(transform["direction"], "p_to = R @ p_from + t")
        self.assertEqual(transform["from_frame"], "innolidar")
        self.assertEqual(transform["to_frame"], "site")
        self.assertEqual(invert_transform(transform)["from_frame"], "site")

    def test_same_name_frames_and_missing_evidence_are_refused(self):
        with self.assertRaises(GeometryCalibrationError):
            make_transform(np.eye(3), [0.0, 0.0, 0.0], "innolidar", "innolidar",
                           evidence="synthetic")
        with self.assertRaises(GeometryCalibrationError):
            make_transform(np.eye(3), [0.0, 0.0, 0.0], "innolidar", "site",
                           evidence=None)
        unknown = make_unknown_transform("innolidar", "site")
        self.assertEqual(unknown["status"], "unknown")
        self.assertIsNone(unknown["rotation"])
        self.assertIsNone(unknown["translation_m"])
        with self.assertRaises(GeometryCalibrationError):
            apply_transform([[0.0, 0.0, 0.0]], unknown)

    def test_millimetre_metre_mismatch_is_detected(self):
        with self.assertRaises(GeometryCalibrationError) as raised:
            validate_translation([0.0, 0.0, 1500.0], units="m")
        self.assertIn("unit_mismatch_suspected", str(raised.exception))
        self.assertAlmostEqual(validate_translation([0.0, 0.0, 1500.0], units="mm")[2], 1.5)
        self.assertAlmostEqual(length_to_meters(250.0, "mm"), 0.25)
        with self.assertRaises(GeometryCalibrationError):
            length_to_meters(1.0, "cm")

    def test_rotation_only_record_and_unknown(self):
        record = make_rotation(rot_z(0.2), "imu", "innolidar",
                               evidence="controlled_attitude")
        self.assertEqual(record["status"], "verified")
        self.assertEqual(make_rotation(rot_z(0.2), "imu", "innolidar",
                                       evidence="synthetic")["status"], "synthetic")
        vectors = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        rotated = apply_rotation(vectors, record)
        self.assertTrue(np.allclose(np.linalg.norm(rotated, axis=1), 1.0))
        unknown = make_unknown_rotation("imu", "innolidar")
        self.assertEqual(unknown["status"], "unknown")
        self.assertIsNone(unknown["rotation"])
        with self.assertRaises(GeometryCalibrationError):
            apply_rotation(vectors, unknown)
        with self.assertRaises(GeometryCalibrationError):
            make_rotation(rot_z(0.2), "innolidar", "innolidar",
                          evidence="controlled_attitude")


class GroundFitTest(unittest.TestCase):
    def test_tilted_plane_recovers_normal_height_and_holdout_residual(self):
        tilt = 0.12
        normal = [math.sin(tilt), 0.0, math.cos(tilt)]
        points = plane_points(normal, 1.5, min_range=0.5)
        result = fit_ground_plane(points, settings={"range_min_m": 0.0}, frame="innolidar")
        self.assertEqual(result["status"], STATUS_VALID)
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["normal"][2], math.cos(tilt), places=2)
        self.assertAlmostEqual(result["sensor_height_m"], 1.5, places=2)
        self.assertAlmostEqual(result["tilt_rad"], tilt, places=2)
        self.assertGreater(result["fit_inlier_count"], 3000)
        self.assertLess(result["fit_residual"]["rms_m"], 0.01)
        self.assertLess(result["holdout_residual"]["rms_m"], 0.01)
        self.assertGreater(result["holdout_support"]["fraction"], 0.8)
        self.assertLess(result["holdout_support"]["rms_m"], 0.01)
        self.assertIsNotNone(result["valid_region"])
        dumps_strict(result)

    def test_dominant_floor_with_scene_objects_still_valid(self):
        floor = plane_points([0.0, 0.0, 1.0], 1.5, count=4000, min_range=0.0)
        rng = np.random.RandomState(19)
        objects = np.column_stack((rng.uniform(-4, 4, 1500),
                                   rng.uniform(-4, 4, 1500),
                                   rng.uniform(0.2, 1.5, 1500)))
        result = fit_ground_plane(np.vstack((floor, objects)),
                                  settings={"range_min_m": 0.0})
        self.assertEqual(result["status"], STATUS_VALID)
        self.assertAlmostEqual(result["sensor_height_m"], 1.5, places=2)
        self.assertGreater(result["holdout_support"]["count"], 500)
        self.assertLess(result["holdout_support"]["rms_m"], 0.01)
        self.assertEqual(result["reason"], None)

    def test_missing_ground_is_reported_not_fitted(self):
        rng = np.random.RandomState(7)
        cloud = (rng.rand(8000, 3) - 0.5) * 10.0
        result = fit_ground_plane(cloud, settings={"range_min_m": 0.0})
        self.assertEqual(result["status"], STATUS_INVALID)
        self.assertIn(result["reason"], (REASON_NOT_FOUND, REASON_INSUFFICIENT))
        self.assertFalse(ground_is_valid(result))

    def test_vertical_wall_confusion_fails_explicitly(self):
        wall = plane_points([1.0, 0.0, 0.0], 4.0, min_range=0.5)
        result = fit_ground_plane(wall, settings={"range_min_m": 0.0})
        self.assertEqual(result["status"], STATUS_ORIENTATION_UNVERIFIED)
        self.assertEqual(result["reason"], REASON_ORIENTATION)
        self.assertFalse(result["valid"])
        self.assertIsNone(sensor_height_from_ground(result))
        self.assertLess(abs(result["normal"][2]), 0.5)

    def test_plane_above_the_sensor_is_not_accepted_as_ground(self):
        ceiling = plane_points([0.0, 0.0, 1.0], 1.5, min_range=0.0)
        ceiling = ceiling * np.array([1.0, 1.0, -1.0])
        result = fit_ground_plane(ceiling, settings={"range_min_m": 0.0})
        self.assertEqual(result["status"], STATUS_INVALID)
        self.assertEqual(result["reason"], "ground_above_sensor")
        self.assertFalse(result["valid"])
        self.assertIsNone(sensor_height_from_ground(result))

    def test_insufficient_points_and_range_filter(self):
        few = np.zeros((20, 3))
        result = fit_ground_plane(few)
        self.assertEqual(result["reason"], REASON_INSUFFICIENT)
        far = plane_points([0.0, 0.0, 1.0], 1.0, min_range=0.0) + np.array([0.0, 0.0, 50.0])
        filtered = fit_ground_plane(far, settings={"range_min_m": 1.0, "range_max_m": 5.0})
        self.assertEqual(filtered["reason"], REASON_INSUFFICIENT)

    def test_settings_are_validated_and_seeded_fit_is_reproducible(self):
        with self.assertRaises(ValueError):
            resolve_settings({"not_a_setting": 1})
        with self.assertRaises(ValueError):
            resolve_settings({"range_min_m": 5.0, "range_max_m": 1.0})
        for bad in ({"normal_up_min_z": 1.5}, {"min_holdout_support": 1.5},
                    {"max_holdout_rms_m": 0.0}, {"holdout_fraction": 1.0}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                resolve_settings(bad)
        points = plane_points([0.0, 0.0, 1.0], 1.4, min_range=0.0)
        first = fit_ground_plane(points, settings={"range_min_m": 0.0})
        second = fit_ground_plane(points, settings={"range_min_m": 0.0})
        self.assertEqual(first["fit_inlier_count"], second["fit_inlier_count"])
        self.assertEqual(first["normal"], second["normal"])

    def test_no_holdout_evidence_is_unverified_not_passed(self):
        points = plane_points([0.0, 0.0, 1.0], 1.4, min_range=0.0)
        result = fit_ground_plane(points, settings={"range_min_m": 0.0,
                                                    "holdout_fraction": 0.0})
        self.assertEqual(result["status"], STATUS_INVALID)
        self.assertEqual(result["reason"], "ground_holdout_insufficient")
        self.assertFalse(result["valid"])

    def test_large_cloud_stays_bounded_and_capped(self):
        import time
        points = plane_points([0.0, 0.0, 1.0], 1.6, count=120000, min_range=0.0)
        started = time.monotonic()
        result = fit_ground_plane(points, settings={"range_min_m": 0.0,
                                                    "max_points": 40000,
                                                    "max_fit_points": 20000})
        elapsed = time.monotonic() - started
        self.assertEqual(result["status"], STATUS_VALID)
        self.assertLessEqual(result["point_count"], 40000)
        self.assertLess(elapsed, 20.0)


class CalibrationArtifactTest(unittest.TestCase):
    def _ground(self):
        return fit_ground_plane(plane_points([0.0, 0.0, 1.0], 1.2, min_range=0.0),
                                settings={"range_min_m": 0.0}, frame="innolidar")

    def test_unknown_extrinsics_are_never_filled_with_identity(self):
        artifact = build_geometry_calibration(
            "geo_test", "2026-10-01T00:00:00+00:00", "innolidar",
            reference_frame="site", ground=self._ground())
        self.assertEqual(artifact["transforms"]["T_reference_lidar"]["status"], "unknown")
        self.assertIsNone(artifact["transforms"]["T_reference_lidar"]["rotation"])
        self.assertEqual(artifact["rotations"]["R_lidar_imu"]["status"], "unknown")
        self.assertIsNone(artifact["rotations"]["R_lidar_imu"]["rotation"])
        self.assertEqual(artifact["status"]["extrinsics"], "unknown")
        self.assertEqual(artifact["status"]["imu_alignment"], "unknown")
        self.assertFalse(artifact["verification"]["imu_alignment_verified"])
        self.assertAlmostEqual(artifact["sensor_height_m"], 1.2, places=2)
        text = dumps_strict(artifact)
        self.assertIsNone(json.loads(text)["transforms"]["T_reference_lidar"]["rotation"])

    def test_artifact_validation_rejects_bad_shape_or_units(self):
        ground = self._ground()
        good = build_geometry_calibration("geo", "2026-10-01T00:00:00+00:00",
                                          "innolidar", ground=ground)
        validate_geometry_calibration(dict(good))
        for mutate in ({"kind": "other"}, {"schema_version": 2},
                       {"units": {"length": "mm", "angle": "rad"}}, {"frames": {}}):
            broken = dict(good)
            broken.update(mutate)
            with self.subTest(mutate=mutate), self.assertRaises(GeometryCalibrationError):
                validate_geometry_calibration(broken)
        bad_ground = dict(good, ground=dict(ground, status="valid", offset_m=-1.0))
        with self.assertRaises(GeometryCalibrationError):
            validate_geometry_calibration(bad_ground)

    def test_synthetic_extrinsic_is_marked_synthetic_not_verified(self):
        transform = make_transform(np.eye(3), [0.1, 0.0, 0.2], "innolidar", "site",
                                   evidence="synthetic")
        artifact = build_geometry_calibration(
            "geo", "2026-10-01T00:00:00+00:00", "innolidar", reference_frame="site",
            transforms={"T_reference_lidar": transform}, ground=self._ground())
        self.assertEqual(artifact["transforms"]["T_reference_lidar"]["status"], "synthetic")
        self.assertFalse(artifact["verification"]["extrinsics_verified"])


class CalibrateSensorsToolTest(unittest.TestCase):
    def test_numeric_cloud_produces_valid_artifact_and_strict_json(self):
        from calibrate_sensors import main
        points = plane_points([0.0, 0.0, 1.0], 1.35, min_range=0.0)
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "cloud.npz")
            output = os.path.join(directory, "geometry.json")
            np.savez(source, points=points)
            code = main(["--points", source, "--output", output,
                         "--calibration-id", "geo_tool", "--frame", "innolidar"])
            self.assertEqual(code, 0)
            with open(output, encoding="utf-8") as handle:
                artifact = json.load(handle)
            self.assertEqual(artifact["kind"], "geometry_calibration")
            self.assertAlmostEqual(artifact["sensor_height_m"], 1.35, places=2)
            self.assertEqual(artifact["input"]["source"], "points")
            self.assertEqual(len(artifact["input"]["sha256"]), 64)

    def test_missing_ground_exits_nonzero_with_invalid_artifact(self):
        from calibrate_sensors import main
        rng = np.random.RandomState(11)
        cloud = (rng.rand(4000, 3) - 0.5) * 8.0
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "noise.npy")
            output = os.path.join(directory, "geometry.json")
            np.save(source, cloud)
            code = main(["--points", source, "--output", output])
            self.assertEqual(code, 2)
            with open(output, encoding="utf-8") as handle:
                artifact = json.load(handle)
            self.assertEqual(artifact["ground"]["status"], STATUS_INVALID)
            self.assertIsNone(artifact["sensor_height_m"])
            self.assertEqual(artifact["status"]["ground"], "unknown")


if __name__ == "__main__":
    unittest.main()
