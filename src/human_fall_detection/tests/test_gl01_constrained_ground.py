"""GL-01 constrained ground-path regressions (software synthetic only).

These exercise the opt-in constrained path in ``core/ground.py``: the explicit
up-axis and sensor-height priors, spatial balanced sampling, candidate
dedup/ambiguity, SVD degeneracy and the per-region untruncated validation gate.
Everything here is synthetic; no physical ground claim is made.
"""

import copy
import math
import sys
import unittest
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))

from core.ground import (DEFAULT_SETTINGS, REASON_COMPETITION, REASON_DEGENERATE,
                         REASON_GROUP_LEAKAGE, REASON_METADATA, REASON_NOT_FOUND,
                         REASON_ORIENTATION, REASON_OVERLAP,
                         REASON_VALIDATION_FAILED, STATUS_INVALID,
                         STATUS_ORIENTATION_UNVERIFIED, STATUS_VALID,
                         check_ground_stability, fit_ground_plane,
                         fit_ground_plane_constrained, ground_is_valid,
                         region_indices, resolve_constrained_settings,
                         validate_constrained_ground)


def tangent_basis(up):
    up = np.asarray(up, dtype=np.float64)
    up = up / np.linalg.norm(up)
    reference = np.array([1.0, 0.0, 0.0])
    if abs(float(up @ reference)) > 0.9:
        reference = np.array([0.0, 1.0, 0.0])
    first = np.cross(up, reference)
    first = first / np.linalg.norm(first)
    return first, np.cross(up, first)


def plane_points(up, height, count, extent=12.0, noise=0.02, seed=5):
    up = np.asarray(up, dtype=np.float64)
    up = up / np.linalg.norm(up)
    first, second = tangent_basis(up)
    rng = np.random.RandomState(seed)
    spread = (rng.rand(count, 2) - 0.5) * extent
    points = spread[:, :1] * first + spread[:, 1:] * second - float(height) * up
    return points + rng.randn(count, 3) * noise


def up_axis_from_tilt(tilt_deg):
    tilt = math.radians(tilt_deg)
    return np.array([math.sin(tilt), 0.0, math.cos(tilt)])


def tilt_of(normal, up):
    value = float(np.clip(float(np.asarray(normal) @ np.asarray(up)), -1.0, 1.0))
    return math.degrees(math.acos(value))


def split_regions(indices, groups=3):
    chunks = np.array_split(np.asarray(indices), groups)
    return [{"region_id": "region_%d" % i, "indices": chunk.tolist(),
             "frame_group": "g%d" % (i + 1)} for i, chunk in enumerate(chunks)
            if len(chunk)]


def clean_scene(tilt_deg=0.0, height=1.2, seed=5):
    up = up_axis_from_tilt(tilt_deg)
    fit_points = plane_points(up, height, 3000, seed=seed)
    val_points = plane_points(up, height, 900, seed=seed + 100)
    points = np.vstack([fit_points, val_points])
    fit = np.arange(0, len(fit_points))
    regions = split_regions(np.arange(len(fit_points), len(points)))
    return points, up, fit, regions


def run(points, up, fit, regions, interval=(0.5, 1.6), **kwargs):
    return fit_ground_plane_constrained(
        points, settings=None, frame="innolidar", up_axis=up,
        sensor_height_interval_m=list(interval), fit_indices=fit,
        fit_frame_group="fit", validation_regions=regions, **kwargs)


class CleanFloorTest(unittest.TestCase):
    def test_clean_floor_tilts_are_valid_candidates(self):
        for tilt_deg in (0.0, 15.0, 25.0):
            with self.subTest(tilt=tilt_deg):
                points, up, fit, regions = clean_scene(tilt_deg)
                result = run(points, up, fit, regions)
                self.assertEqual(result["status"], STATUS_VALID)
                self.assertTrue(result["constrained"])
                self.assertLess(tilt_of(result["normal"], up), 2.0)
                self.assertAlmostEqual(result["sensor_height_m"], 1.2, places=1)
                self.assertEqual(result["iterations"], 861)
                self.assertGreater(result["sampled_fit_count"], 0)
                self.assertGreater(len(result["fit_support_indices"]), 0)
                self.assertEqual(result["ambiguous"], False)
                validate_constrained_ground(result, expected_frame=None)

    def test_tilted_floor_needs_its_own_up_axis(self):
        points, up, fit, regions = clean_scene(30.0)
        admitted = run(points, up, fit, regions)
        self.assertEqual(admitted["status"], STATUS_VALID)
        rejected = run(points, [0.0, 0.0, 1.0], fit, regions,
                       interval=(1.0, 1.4))
        self.assertNotEqual(rejected["status"], STATUS_VALID)


class WallAndDeskCompetitionTest(unittest.TestCase):
    def test_dense_wall_does_not_win_over_floor(self):
        up = np.array([0.0, 0.0, 1.0])
        floor_fit = plane_points(up, 1.2, 3000, seed=7)
        floor_val = plane_points(up, 1.2, 600, seed=8)
        rng = np.random.RandomState(9)
        wall = np.column_stack([np.full(6000, 3.0), rng.uniform(-4, 4, 6000),
                                rng.uniform(-2.5, 0.5, 6000)])
        points = np.vstack([floor_fit, floor_val, wall])
        fit = np.concatenate([np.arange(0, 3000), np.arange(3600, 9600)])
        regions = split_regions(np.arange(3000, 3600))
        result = run(points, up, fit, regions)
        self.assertEqual(result["status"], STATUS_VALID)
        self.assertLess(tilt_of(result["normal"], up), 3.0)
        self.assertAlmostEqual(result["sensor_height_m"], 1.2, places=1)

    def test_desk_competition_is_ambiguous_without_roi(self):
        up = np.array([0.0, 0.0, 1.0])
        floor_fit = plane_points(up, 1.2, 3000, seed=11)
        floor_val = plane_points(up, 1.2, 300, seed=13)
        desk = plane_points(up, 0.45, 2500, extent=8.0, noise=0.01, seed=12)
        points = np.vstack([floor_fit, floor_val, desk])
        fit = np.concatenate([np.arange(0, 3000), np.arange(3300, 5800)])
        regions = split_regions(np.arange(3000, 3300))
        result = run(points, up, fit, regions, interval=(0.4, 1.4))
        self.assertEqual(result["status"], STATUS_ORIENTATION_UNVERIFIED)
        self.assertTrue(result["ambiguous"])
        self.assertEqual(result["reason"], REASON_ORIENTATION)

    def test_desk_competition_resolves_with_floor_roi(self):
        up = np.array([0.0, 0.0, 1.0])
        floor_fit = plane_points(up, 1.2, 3000, seed=11)
        floor_val = plane_points(up, 1.2, 300, seed=13)
        desk = plane_points(up, 0.45, 2500, extent=8.0, noise=0.01, seed=12)
        points = np.vstack([floor_fit, floor_val, desk])
        fit = np.arange(0, 3000)
        regions = split_regions(np.arange(3000, 3300))
        result = run(points, up, fit, regions, interval=(0.4, 1.4))
        self.assertEqual(result["status"], STATUS_VALID)
        self.assertAlmostEqual(result["sensor_height_m"], 1.2, places=1)


class FailureBranchTest(unittest.TestCase):
    def test_missing_ground_is_not_fabricated(self):
        up = np.array([0.0, 0.0, 1.0])
        rng = np.random.RandomState(41)
        points = (rng.rand(6300, 3) - 0.5) * 10.0
        rng.shuffle(points)  # groundless cloud stays spatially interleaved
        fit = np.arange(0, 6000)
        regions = split_regions(np.arange(6000, 6300))
        self.assertFalse(np.intersect1d(fit, np.arange(6000, 6300)).size)
        result = fit_ground_plane_constrained(
            points, frame="innolidar", up_axis=up,
            sensor_height_interval_m=[0.5, 1.6], fit_indices=fit,
            fit_frame_group="fit", validation_regions=regions)
        self.assertEqual(result["status"], STATUS_INVALID)
        self.assertEqual(result["reason"], REASON_NOT_FOUND)
        self.assertEqual(result["raw_candidates"], [])
        self.assertEqual(result["candidates"], [])
        self.assertIsNone(result["normal"])

    def test_degenerate_collinear_cloud_fails_explicitly(self):
        up = np.array([0.0, 0.0, 1.0])
        rng = np.random.RandomState(43)
        along = np.linspace(0.0, 20.0, 400)
        points = np.column_stack([along, rng.randn(400) * 5e-4,
                                  rng.randn(400) * 5e-4])
        fit = np.arange(0, 300)
        regions = split_regions(np.arange(300, 400))
        result = fit_ground_plane_constrained(
            points, frame="innolidar", up_axis=up,
            sensor_height_interval_m=[0.0, 10.0], fit_indices=fit,
            fit_frame_group="fit", validation_regions=regions)
        self.assertEqual(result["status"], STATUS_INVALID)
        self.assertEqual(result["reason"], REASON_DEGENERATE)

    def test_bad_values_are_filtered_and_zero_returns_are_not_support(self):
        up = np.array([0.0, 0.0, 1.0])
        floor = plane_points(up, 1.2, 3000, seed=31)
        val = plane_points(up, 1.2, 300, seed=32)
        points = np.vstack([floor, [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
                            val, [[np.nan, 0.0, 0.0], [np.inf, 0.0, 0.0]]])
        fit = np.arange(0, 3002)          # includes the two zero returns
        regions = split_regions(np.arange(3002, 3302))
        result = fit_ground_plane_constrained(
            points, frame="innolidar", up_axis=up,
            sensor_height_interval_m=[0.5, 1.6], fit_indices=fit,
            fit_frame_group="fit", validation_regions=regions)
        self.assertEqual(result["status"], STATUS_VALID)
        self.assertEqual(result["valid_point_count"], 3300)
        support = set(result["fit_support_indices"])
        self.assertNotIn(3000, support)
        self.assertNotIn(3001, support)

    def test_height_conflict_rejects_every_candidate(self):
        up = np.array([0.0, 0.0, 1.0])
        floor_fit = plane_points(up, 1.2, 3000, seed=51)
        floor_val = plane_points(up, 1.2, 300, seed=52)
        points = np.vstack([floor_fit, floor_val])
        fit = np.arange(0, 3000)
        regions = split_regions(np.arange(3000, 3300))
        result = run(points, up, fit, regions, interval=(0.5, 0.9))
        self.assertEqual(result["status"], STATUS_INVALID)
        self.assertIn(result["reason"], (REASON_NOT_FOUND, "ground_points_insufficient"))
        self.assertIsNone(result["normal"])

    def test_normal_ambiguity_between_two_tilted_planes(self):
        up = np.array([0.0, 0.0, 1.0])
        a_normal = up_axis_from_tilt(6.0)
        b_normal = up_axis_from_tilt(-6.0)
        a_fit = plane_points(a_normal, 1.0, 3000, seed=61)
        a_val = plane_points(a_normal, 1.0, 300, seed=62)
        b_fit = plane_points(b_normal, 1.4, 2900, seed=63)
        points = np.vstack([a_fit, a_val, b_fit])
        fit = np.concatenate([np.arange(0, 3000), np.arange(3300, 6200)])
        regions = split_regions(np.arange(3000, 3300))
        result = run(points, up, fit, regions, interval=(0.5, 1.6))
        self.assertEqual(result["status"], STATUS_ORIENTATION_UNVERIFIED)
        self.assertTrue(result["ambiguous"])


class IndependenceTest(unittest.TestCase):
    def test_overlapping_fit_and_validation_indices_fail(self):
        points, up, fit, regions = clean_scene()
        regions[0]["indices"] = fit[:50].tolist()
        result = run(points, up, fit, regions)
        self.assertEqual(result["status"], STATUS_INVALID)
        self.assertEqual(result["reason"], REASON_OVERLAP)

    def test_frame_group_leakage_fails(self):
        points, up, fit, regions = clean_scene()
        regions[0]["frame_group"] = "fit"
        result = run(points, up, fit, regions)
        self.assertEqual(result["status"], STATUS_INVALID)
        self.assertEqual(result["reason"], REASON_GROUP_LEAKAGE)

    def test_single_failing_validation_region_fails_the_whole_gate(self):
        up = np.array([0.0, 0.0, 1.0])
        fit_points = plane_points(up, 1.2, 3000, seed=71)
        good = plane_points(up, 1.2, 200, seed=72)
        bad = plane_points(up, 1.5, 200, seed=73)
        points = np.vstack([fit_points, good, bad])
        fit = np.arange(0, 3000)
        regions = [{"region_id": "r1", "frame_group": "g1",
                    "indices": np.arange(3000, 3100).tolist()},
                   {"region_id": "r2", "frame_group": "g2",
                    "indices": np.arange(3100, 3200).tolist()},
                   {"region_id": "r3", "frame_group": "g3",
                    "indices": np.arange(3200, 3400).tolist()}]
        result = fit_ground_plane_constrained(
            points, frame="innolidar", up_axis=up,
            sensor_height_interval_m=[0.5, 1.6], fit_indices=fit,
            fit_frame_group="fit", validation_regions=regions)
        self.assertEqual(result["status"], STATUS_INVALID)
        self.assertEqual(result["reason"], REASON_VALIDATION_FAILED)
        report = {item["region_id"]: item for item in result["validation_regions"]}
        self.assertTrue(report["r1"]["passed"])
        self.assertFalse(report["r3"]["passed"])

    def test_too_few_usable_regions_is_insufficient(self):
        points, up, fit, regions = clean_scene()
        result = run(points, up, fit, regions[:1])
        self.assertEqual(result["status"], STATUS_INVALID)
        self.assertEqual(result["reason"], "ground_validation_insufficient")


class SettingsAndStabilityTest(unittest.TestCase):
    def test_parameters_reject_bool_nan_inf_negative_and_non_integer(self):
        bad = ({"max_points_per_cell": True}, {"max_points_per_cell": 4.0},
               {"seed": "x"}, {"inlier_threshold_m": float("nan")},
               {"inlier_threshold_m": float("inf")},
               {"inlier_threshold_m": -0.05}, {"support_close_ratio": 1.5},
               {"max_angle_rad": 2.0}, {"unknown_setting": 1})
        for settings in bad:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                resolve_constrained_settings(settings)

    def test_missing_priors_raise(self):
        points, _, _, _ = clean_scene()
        with self.assertRaises(ValueError):
            fit_ground_plane_constrained(points, up_axis=None,
                                         sensor_height_interval_m=[1.0, 1.6])
        with self.assertRaises(ValueError):
            fit_ground_plane_constrained(points, up_axis=[0.0, 0.0, 1.0],
                                         sensor_height_interval_m=None)
        with self.assertRaises(ValueError):
            fit_ground_plane_constrained(points, up_axis=[0.0, 0.0, 1.0],
                                         sensor_height_interval_m=[1.6, 1.0])

    def test_region_indices_accepts_bounds_and_indices(self):
        points = np.array([[0.0, 0.0, 1.0], [2.0, 0.0, 1.0], [5.0, 0.0, 1.0]])
        self.assertEqual(region_indices(points, {"x_min_m": -1.0, "x_max_m": 3.0,
                                                 "y_min_m": -1.0, "y_max_m": 1.0,
                                                 "z_min_m": 0.0, "z_max_m": 2.0}).tolist(),
                         [0, 1])
        self.assertEqual(region_indices(points, {"indices": [2]}).tolist(), [2])

    def test_stability_gate_across_frame_groups(self):
        up = np.array([0.0, 0.0, 1.0])
        first = run(*clean_scene(seed=5), interval=(0.5, 1.6))
        second = run(*clean_scene(seed=205), interval=(0.5, 1.6))
        report = check_ground_stability(first, second)
        self.assertTrue(report["stable"])
        shifted = clean_scene(tilt_deg=8.0, seed=5)
        unstable = run(*shifted, interval=(0.5, 1.6))
        self.assertFalse(check_ground_stability(first, unstable)["stable"])

    def test_legacy_path_is_unchanged_and_separate(self):
        self.assertEqual(DEFAULT_SETTINGS["ransac_iterations"], 150)
        points, up, fit, _ = clean_scene()
        legacy = fit_ground_plane(points, settings={"range_min_m": 0.0})
        self.assertNotIn("constrained", legacy)
        constrained = run(points, up, fit, split_regions(np.arange(3000, 3900)))
        self.assertTrue(constrained["constrained"])

    def test_validate_constrained_ground_rejects_tampered_records(self):
        points, up, fit, regions = clean_scene()
        result = run(points, up, fit, regions)
        validate_constrained_ground(result)
        without = dict(result)
        without.pop("constrained")
        with self.assertRaises(ValueError):
            validate_constrained_ground(without)
        tampered = dict(result, up_axis=[2.0, 0.0, 0.0])
        with self.assertRaises(ValueError):
            validate_constrained_ground(tampered)


class MetadataAndBoundaryTest(unittest.TestCase):
    def test_missing_frame_group_provenance_is_invalid(self):
        points, up, fit, regions = clean_scene()
        for region in regions:
            region.pop("frame_group")
        result = fit_ground_plane_constrained(
            points, frame="innolidar", up_axis=up,
            sensor_height_interval_m=[0.5, 1.6], fit_indices=fit,
            validation_regions=regions)
        self.assertEqual(result["status"], STATUS_INVALID)
        self.assertEqual(result["reason"], REASON_METADATA)

    def test_duplicate_region_identity_is_invalid(self):
        points, up, fit, regions = clean_scene()
        for region in regions:
            region["region_id"] = "same-region"
        result = run(points, up, fit, regions)
        self.assertEqual(result["status"], STATUS_INVALID)
        self.assertEqual(result["reason"], REASON_METADATA)

    def test_mixed_bool_indices_and_priors_are_rejected(self):
        points, up, fit, regions = clean_scene()
        def fit_with(fit_indices):
            return fit_ground_plane_constrained(
                points, frame="innolidar", up_axis=up,
                sensor_height_interval_m=[0.5, 1.6], fit_indices=fit_indices,
                fit_frame_group="fit", validation_regions=regions)

        with self.assertRaises(ValueError):
            run(points, [True, 0.0, 1.0], fit, regions)
        with self.assertRaises(ValueError):
            fit_with([True, 1, 2])
        with self.assertRaises(ValueError):
            fit_with([0.0, 1.0, 2.0])
        with self.assertRaises(ValueError):
            run(points, [0.0, 0.0, 2.0], fit, regions)

    def test_reduced_candidate_cap_cannot_hide_competition(self):
        up = np.array([0.0, 0.0, 1.0])
        floor = plane_points(up, 1.2, 3000, noise=0.005, seed=400)
        desk = plane_points(up, 0.45, 3000, noise=0.005, seed=401)
        val = plane_points(up, 1.2, 300, noise=0.005, seed=402)
        points = np.vstack([floor, desk, val])
        regions = [{"region_id": "v%d" % i, "frame_group": "v%d" % i,
                    "indices": list(range(6000 + i * 100, 6100 + i * 100))}
                   for i in range(3)]
        result = fit_ground_plane_constrained(
            points, settings={"max_candidates": 1}, frame="innolidar",
            up_axis=up, sensor_height_interval_m=[0.4, 1.6],
            fit_indices=np.arange(6000), fit_frame_group="fit",
            validation_regions=regions)
        self.assertNotEqual(result["status"], STATUS_VALID)
        self.assertEqual(result["reason"], REASON_ORIENTATION)
        self.assertTrue(result["ambiguous"])

    def test_protocol_floors_and_caps_are_not_relaxable(self):
        for override in ({"min_inliers": 10}, {"points_per_region_min": 5},
                         {"independent_regions_min": 1}, {"seed": -1},
                         {"max_candidates": 4}, {"ransac_iteration_hard_cap": 2001},
                         {"min_planar_eigenvalue_ratio": 1.1}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                resolve_constrained_settings(override)


class ArtifactLoaderValidationTest(unittest.TestCase):
    def setUp(self):
        points, up, fit, regions = clean_scene()
        self.record = run(points, up, fit, regions)
        self.assertEqual(self.record["status"], STATUS_VALID)

    def rejected(self, mutate):
        damaged = copy.deepcopy(self.record)
        mutate(damaged)
        with self.assertRaises(ValueError):
            validate_constrained_ground(damaged)

    def test_valid_record_still_loads(self):
        validate_constrained_ground(self.record, expected_frame="innolidar")

    def test_loaded_group_provenance_must_stay_independent(self):
        self.rejected(lambda g: g.update(
            fit_frame_group=g["validation_regions"][0]["frame_group"]))

    def test_loaded_region_statistics_reject_negative_bool_and_out_of_range(self):
        for key, value in (("rms_m", -0.01), ("p95_m", -0.01),
                           ("support_fraction", 1.2), ("rms_m", False)):
            with self.subTest(key=key, value=value):
                self.rejected(lambda g, k=key, v=value:
                              g["validation_regions"][0].update({k: v}))

    def test_loaded_height_and_normal_must_match_declared_priors(self):
        self.rejected(lambda g: g.update(sensor_height_interval_m=[0.5, 0.9]))
        self.rejected(lambda g: g.update(up_axis=[1.0, 0.0, 0.0]))

    def test_loaded_fit_indices_must_be_unique_in_range_ints(self):
        for index in (True, self.record["input_point_count"]):
            with self.subTest(index=index):
                self.rejected(lambda g, i=index:
                              g["fit_support_indices"].__setitem__(0, i))
        self.rejected(lambda g:
                      g["fit_support_indices"].append(g["fit_support_indices"][0]))

    def test_loaded_budget_cannot_be_zero_or_over_cap(self):
        self.rejected(lambda g: g.update(iterations=0))
        self.rejected(lambda g: g.update(iterations_cap=2001))

    def test_loaded_up_axis_must_already_be_unit(self):
        self.rejected(lambda g: g.update(up_axis=[0.0, 0.0, 2.0]))

    def test_legal_failure_record_is_still_savable(self):
        up = np.array([0.0, 0.0, 1.0])
        floor_fit = plane_points(up, 1.2, 3000, seed=11)
        floor_val = plane_points(up, 1.2, 300, seed=13)
        desk = plane_points(up, 0.45, 2500, extent=8.0, noise=0.01, seed=12)
        points = np.vstack([floor_fit, floor_val, desk])
        fit = np.concatenate([np.arange(0, 3000), np.arange(3300, 5800)])
        regions = split_regions(np.arange(3000, 3300))
        record = run(points, up, fit, regions, interval=(0.4, 1.4))
        self.assertEqual(record["status"], STATUS_ORIENTATION_UNVERIFIED)
        validate_constrained_ground(record, expected_frame="innolidar")


if __name__ == "__main__":
    unittest.main()
