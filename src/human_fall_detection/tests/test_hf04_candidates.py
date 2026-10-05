import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))

from core.ground import STATUS_VALID, fit_ground_plane
from core.lidar_candidates import (build_background, build_snapshot,
                                   candidates_from_cloud, foreground_mask,
                                   ground_coverage, ground_plane_basis,
                                   resolve_settings, scene_change_fraction,
                                   validate_snapshot)
from sensor_health import dumps_strict


def plane_points(normal, height, count=6000, extent=9.0, noise=0.003, seed=5):
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
    return points[ranges >= 0.9]


def valid_ground(normal=(0.0, 0.0, 1.0), height=1.5):
    points = plane_points(normal, height)
    return fit_ground_plane(points, settings={"range_min_m": 0.0}, frame="innolidar")


def on_ground(normal, offset, a, b, h):
    normal = np.asarray(normal, dtype=np.float64)
    normal = normal / np.linalg.norm(normal)
    axis = np.array([1.0, 0.0, 0.0]) if abs(normal[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(normal, axis)
    u = u / np.linalg.norm(u)
    v = np.cross(normal, u)
    offset = np.reshape(np.asarray(offset, dtype=np.float64), (-1, 1))
    return np.outer(a, u) + np.outer(b, v) + (np.reshape(h, (-1, 1)) - offset) * normal


def person_lying(normal, offset, center=(3.0, 0.0), seed=11):
    rng = np.random.RandomState(seed)
    along = rng.uniform(-0.9, 0.9, 260)
    across = rng.uniform(-0.22, 0.22, 260)
    heights = np.clip(np.abs(along) * 0.12 + rng.uniform(0.02, 0.22, 260), 0.02, 0.45)
    points = np.vstack([
        on_ground(normal, offset, center[0] + along, center[1] + across, height)
        for height in heights])
    return points


def frame(normal, offset, extra_ground=True):
    ground = plane_points(normal, offset)
    if not extra_ground:
        return ground
    return ground


def snapshot(points, ground, background=None, settings=None, **context):
    context.setdefault("session_id", "hf04")
    context.setdefault("time_epoch", 0)
    context.setdefault("snapshot_id", "snap-1")
    context.setdefault("seq", 42)
    context.setdefault("stamp_secs", 100)
    context.setdefault("stamp_nsecs", 500)
    context.setdefault("source_stamp_s", 100.0000005)
    return build_snapshot(points, settings, ground=ground, background=background, **context)


class GroundHugTest(unittest.TestCase):
    def test_lying_low_posture_survives_without_a_standing_size_gate(self):
        ground = valid_ground()
        normal = [0.0, 0.0, 1.0]
        empty = plane_points(normal, 1.5)
        background = build_background([empty], frame_id="innolidar")
        person = person_lying(normal, 1.5)
        snap = snapshot(np.vstack((empty, person)), ground, background)
        self.assertEqual(snap["kind"], "candidate_snapshot")
        self.assertEqual(len(snap["candidates"]), 1)
        candidate = snap["candidates"][0]
        self.assertTrue(candidate["ground_relative_available"])
        self.assertLess(candidate["height_m"]["median"], 0.5)
        self.assertGreater(candidate["horizontal_extent_m"]["max"], 1.0)
        self.assertEqual(candidate["semantic"], "unknown")
        self.assertEqual(candidate["axis"]["ambiguous"], False)

    def test_tilted_ground_uses_normal_height_and_tangent_basis(self):
        tilt = 0.3
        normal = [math.sin(tilt), 0.0, math.cos(tilt)]
        ground = valid_ground(normal, 1.4)
        self.assertEqual(ground["status"], STATUS_VALID)
        empty = plane_points(normal, 1.4)
        background = build_background([empty])
        person = person_lying(normal, ground["offset_m"], center=(3.0, 1.0))
        snap = snapshot(np.vstack((empty, person)), ground, background)
        basis = ground_plane_basis(ground)
        self.assertIsNotNone(basis)
        candidate = snap["candidates"][0]
        self.assertTrue(candidate["ground_relative_available"])
        heights = np.asarray(candidate["height_m"]["max"], dtype=float)
        self.assertLess(heights, 1.0)
        self.assertEqual(snap["coordinate"]["horizontal_basis"], "ground_tangent")

    def test_no_ground_is_uncalibrated_without_height_or_fall_claim(self):
        rng = np.random.RandomState(3)
        blob = rng.normal((3.0, 0.0, 0.0), (0.25, 0.25, 0.4), (300, 3))
        snap = snapshot(blob, None)
        self.assertFalse(snap["coordinate"]["ground_relative_available"])
        self.assertEqual(snap["coordinate"]["horizontal_basis"], "raw_xy_uncalibrated")
        self.assertEqual(snap["quality"]["ground_valid"], False)
        self.assertIn("ground_unavailable", snap["quality"]["reasons"])
        candidate = snap["candidates"][0]
        self.assertFalse(candidate["ground_relative_available"])
        self.assertIsNone(candidate["height_m"])
        self.assertIsNone(candidate["axis"]["verticality"])


class DegeneracyTest(unittest.TestCase):
    def test_compact_blob_has_no_confident_axis(self):
        rng = np.random.RandomState(8)
        blob = rng.normal((3.0, 0.0, 0.0), (0.3, 0.3, 0.3), (600, 3))
        snap = snapshot(blob, None, settings={"pca_axis_ratio": 2.5})
        candidate = snap["candidates"][0]
        self.assertTrue(candidate["axis"]["ambiguous"])
        self.assertIsNone(candidate["axis"]["axis"])
        self.assertIn("axis_ambiguous", candidate["quality"]["reasons"])

    def test_too_few_points_for_pca_is_explicit(self):
        rng = np.random.RandomState(9)
        few = rng.normal((3.0, 0.0, 0.0), 0.1, (10, 3))
        snap = snapshot(few, None, settings={"min_cluster_points": 5, "pca_min_points": 100})
        candidate = snap["candidates"][0]
        self.assertEqual(candidate["axis"]["reason"], "insufficient_points")
        self.assertTrue(candidate["axis"]["ambiguous"])

    def test_low_point_cluster_is_kept_and_flagged(self):
        rng = np.random.RandomState(10)
        points = rng.normal((3.0, 0.0, 0.0), (0.2, 0.2, 0.2), (40, 3))
        snap = snapshot(points, None, settings={"min_cluster_points": 10,
                                                "preferred_cluster_points": 200})
        candidate = snap["candidates"][0]
        self.assertTrue(candidate["quality"]["low_points"])
        self.assertIn("low_points", candidate["quality"]["reasons"])


class MultiTargetAndMergeTest(unittest.TestCase):
    def test_two_separated_targets_stay_two_candidates(self):
        rng = np.random.RandomState(21)
        left = rng.normal((3.0, -1.5, 0.0), (0.25, 0.25, 0.5), (300, 3))
        right = rng.normal((3.5, 1.5, 0.0), (0.25, 0.25, 0.5), (300, 3))
        snap = snapshot(np.vstack((left, right)), None)
        self.assertEqual(len(snap["candidates"]), 2)

    def test_person_touching_furniture_merges_and_is_reported_as_one_cluster(self):
        rng = np.random.RandomState(22)
        person = rng.normal((3.0, 0.0, 0.0), (0.25, 0.25, 0.5), (300, 3))
        furniture = np.zeros((400, 3))
        furniture[:, 0] = rng.uniform(2.7, 3.3, 400)
        furniture[:, 1] = rng.uniform(-0.05, 0.05, 400)
        furniture[:, 2] = rng.uniform(-0.4, 0.4, 400)
        snap = snapshot(np.vstack((person, furniture)), None,
                        settings={"cluster_cell_m": 0.3})
        self.assertEqual(len(snap["candidates"]), 1)
        candidate = snap["candidates"][0]
        self.assertGreater(candidate["point_count"], 600)


class BackgroundTest(unittest.TestCase):
    def test_frozen_background_never_learns_a_still_person(self):
        rng = np.random.RandomState(31)
        empty = rng.normal((3.0, 0.0, 0.0), (0.5, 0.5, 0.05), (2000, 3))
        background = build_background([empty])
        person = rng.normal((3.0, 3.0, 0.0), (0.2, 0.2, 0.5), (300, 3))
        later = np.vstack((empty, person))
        mask = foreground_mask(later, background)
        self.assertEqual(int(np.count_nonzero(mask)), 300)
        self.assertTrue(mask[len(empty):].all())
        self.assertGreater(scene_change_fraction(later, background), 0.05)

    def test_no_background_means_everything_is_foreground(self):
        rng = np.random.RandomState(32)
        points = rng.normal(0.0, 1.0, (100, 3))
        self.assertTrue(foreground_mask(points, None).all())
        self.assertIsNone(scene_change_fraction(points, None))

    def test_background_requires_frames_and_validates_settings(self):
        with self.assertRaises(ValueError):
            build_background([])
        with self.assertRaises(ValueError):
            resolve_settings({"not_a_setting": 1})
        with self.assertRaises(ValueError):
            resolve_settings({"range_min_m": 9.0, "range_max_m": 1.0})


class CoverageTest(unittest.TestCase):
    def test_tall_standing_person_is_covered_via_projection(self):
        ground = valid_ground(height=1.5)
        rng = np.random.RandomState(41)
        standing = np.zeros((400, 3))
        standing[:, 0] = rng.normal(3.0, 0.2, 400)
        standing[:, 1] = rng.normal(0.0, 0.2, 400)
        standing[:, 2] = rng.uniform(-1.5, 0.2, 400)
        coverage = ground_coverage(standing, ground)
        self.assertTrue(coverage["available"])
        self.assertGreater(coverage["projected_inside_fraction"], 0.95)
        self.assertIsNone(ground_coverage(standing, None)["projected_inside_fraction"])


class SnapshotContractTest(unittest.TestCase):
    def test_snapshot_is_deterministic_and_strict_json(self):
        ground = valid_ground()
        empty = plane_points([0.0, 0.0, 1.0], 1.5)
        background = build_background([empty])
        person = person_lying([0.0, 0.0, 1.0], 1.5)
        points = np.vstack((empty, person))
        first = snapshot(points, ground, background)
        second = snapshot(points, ground, background)
        self.assertEqual(dumps_strict(first), dumps_strict(second))
        text = dumps_strict(first)
        self.assertNotIn("NaN", text)
        self.assertNotIn("Infinity", text)
        validate_snapshot(first)
        self.assertEqual(first["source"]["seq"], 42)
        self.assertEqual(first["source"]["stamp_secs"], 100)
        self.assertEqual(first["coordinate"]["source_frame"], "innolidar")

    def test_evidence_indices_reconstruct_the_candidate(self):
        rng = np.random.RandomState(51)
        points = rng.normal((3.0, 0.0, 0.0), (0.2, 0.2, 0.4), (300, 3))
        snap = snapshot(points, None)
        candidate = snap["candidates"][0]
        evidence = points[np.asarray(candidate["evidence_indices"])]
        self.assertEqual(len(evidence), candidate["point_count"])
        self.assertTrue(np.allclose(np.median(evidence, axis=0),
                                    candidate["center_source_m"]))

    def test_validate_rejects_semantic_human_claim(self):
        rng = np.random.RandomState(52)
        points = rng.normal((3.0, 0.0, 0.0), 0.2, (300, 3))
        snap = snapshot(points, None)
        snap["candidates"][0]["semantic"] = "human_like"
        with self.assertRaises(ValueError):
            validate_snapshot(snap)


class DecodeHelperTest(unittest.TestCase):
    def test_decode_cloud_is_available_without_ros_objects(self):
        from core.lidar_candidates import decode_cloud
        self.assertTrue(callable(decode_cloud))
        self.assertTrue(callable(candidates_from_cloud))


if __name__ == "__main__":
    unittest.main()
