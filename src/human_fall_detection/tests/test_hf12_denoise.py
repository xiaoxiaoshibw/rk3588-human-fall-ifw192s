"""HF-12 point-denoise tests: isolated-point drops, order, settings, snapshot.

Synthetic geometry only; no real-human/device claim. The stage is disabled in
core defaults, so only enable it explicitly here (or through perception.yaml).
"""

import sys
import unittest
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))

from core.lidar_candidates import (build_background, build_snapshot,
                                   denoise_mask, resolve_settings,
                                   validate_snapshot)
from sensor_health import dumps_strict, load_config

VALID_GROUND = {"kind": "ground_plane", "status": "valid", "frame": "innolidar",
                "normal": [0.0, 0.0, 1.0], "offset_m": 1.5, "sensor_height_m": 1.5}


def blob(center=(3.0, 0.0, -1.5), spread=0.15, count=300, seed=7):
    return np.random.RandomState(seed).normal(center, spread, (count, 3))


def isolated_points(count=20):
    """Evenly spaced singles: >0.3 m apart, 5 m from the blob, inside range."""
    x = np.linspace(-4.0, 4.0, count)
    return np.column_stack((x, np.full(count, 5.0), np.full(count, -1.5)))


def enabled(radius=0.15, min_neighbors=2):
    return {"denoise_enabled": True, "denoise_radius_m": radius,
            "denoise_min_neighbors": min_neighbors}


def snapshot(points, settings=None, ground=None, background=None):
    return build_snapshot(points, settings, session_id="hf12", time_epoch=0,
                          snapshot_id="s1", ground=ground, background=background)


class DefaultsTest(unittest.TestCase):
    def test_core_defaults_keep_denoise_disabled(self):
        resolved = resolve_settings(None)
        self.assertIs(resolved["denoise_enabled"], False)
        self.assertEqual(resolved["denoise_radius_m"], 0.1)
        self.assertEqual(resolved["denoise_min_neighbors"], 2)

    def test_default_matches_explicit_off(self):
        points = np.vstack((blob(), isolated_points()))
        default = snapshot(points)
        off = snapshot(points, {"denoise_enabled": False})
        self.assertEqual(dumps_strict(default), dumps_strict(off))
        stage = default["quality"]["denoise"]
        self.assertFalse(stage["enabled"])
        self.assertEqual(stage["input_point_count"], len(points))
        self.assertEqual(stage["kept_point_count"], len(points))
        self.assertEqual(stage["dropped_point_count"], 0)

    def test_perception_config_enables_denoise(self):
        config = load_config(str(PACKAGE_DIR / "config" / "perception.yaml"))
        resolved = resolve_settings(config["candidates"])
        self.assertIs(resolved["denoise_enabled"], True)
        self.assertEqual(resolved["denoise_radius_m"], 0.1)
        self.assertEqual(resolved["denoise_min_neighbors"], 2)


class MaskSemanticsTest(unittest.TestCase):
    def test_empty_single_and_min_neighbors_one(self):
        empty = denoise_mask(np.zeros((0, 3)), 0.1, 2)
        self.assertEqual(len(empty), 0)
        single = np.array([[3.0, 0.0, 0.0]])
        self.assertFalse(denoise_mask(single, 0.1, 2)[0])
        self.assertTrue(denoise_mask(single, 0.1, 1)[0])

    def test_neighbouring_cells_support_each_other(self):
        pair = np.array([[2.999, 0.0, 0.0], [3.002, 0.0, 0.0],
                         [5.0, 5.0, 0.0]])
        self.assertEqual(denoise_mask(pair, 0.1, 2).tolist(),
                         [True, True, False])

    def test_mask_validates_parameters(self):
        pair = np.zeros((2, 3))
        with self.assertRaises(ValueError):
            denoise_mask(pair, 0.0, 2)
        with self.assertRaises(ValueError):
            denoise_mask(pair, float("nan"), 2)
        with self.assertRaises(ValueError):
            denoise_mask(pair, 0.1, 0)
        with self.assertRaises(ValueError):
            denoise_mask(pair, 0.1, True)

    def test_small_radius_fallback_keeps_counting(self):
        # 0.005 m over an 8 m spread exceeds the dense-grid cap -> packed-key
        # fallback must return the same neighbourhood semantics.
        points = np.array([[0.0, 0.0, 0.0], [0.004, 0.0, 0.0], [8.0, 8.0, 8.0]])
        self.assertEqual(denoise_mask(points, 0.005, 2).tolist(),
                         [True, True, False])


class SnapshotDenoiseTest(unittest.TestCase):
    def test_isolated_points_dropped_dense_cluster_kept(self):
        points = np.vstack((blob(), isolated_points()))
        snap = snapshot(points, enabled())
        stage = snap["quality"]["denoise"]
        self.assertTrue(stage["enabled"])
        self.assertEqual(stage["radius_m"], 0.15)
        self.assertEqual(stage["min_neighbors"], 2)
        self.assertEqual(stage["input_point_count"], 320)
        self.assertEqual(stage["kept_point_count"], 300)
        self.assertEqual(stage["dropped_point_count"], 20)
        self.assertEqual(len(snap["candidates"]), 1)
        self.assertEqual(snap["candidates"][0]["point_count"], 300)

    def test_min_neighbors_one_keeps_isolated_points(self):
        points = isolated_points()
        snap = snapshot(points, enabled(min_neighbors=1))
        self.assertEqual(snap["quality"]["denoise"]["dropped_point_count"], 0)

    def test_order_denoise_precedes_height_gate(self):
        # Ground offset 1.5: heights -0.25 (inside band) and -0.35 (below it).
        # The below-band point must still support its neighbour at denoise time.
        points = np.array([[3.0, 0.0, -1.75], [3.0, 0.0, -1.85]])
        settings = enabled(radius=0.15)
        settings.update({"min_cluster_points": 1, "preferred_cluster_points": 1})
        with_ground = snapshot(points, settings, ground=VALID_GROUND)
        stage = with_ground["quality"]["denoise"]
        self.assertEqual((stage["input_point_count"], stage["kept_point_count"],
                          stage["dropped_point_count"]), (2, 2, 0))
        self.assertEqual(len(with_ground["candidates"]), 1)
        self.assertEqual(with_ground["candidates"][0]["point_count"], 1)
        without_ground = snapshot(points, settings)
        self.assertEqual(without_ground["quality"]["denoise"]["dropped_point_count"], 0)
        self.assertEqual(without_ground["candidates"][0]["point_count"], 2)

    def test_order_denoise_precedes_background(self):
        background = build_background([np.array([[3.12, 0.0, 0.0]])],
                                      frame_id="innolidar")
        points = np.array([[3.0, 0.0, 0.0], [3.12, 0.0, 0.0]])
        settings = enabled(radius=0.15)
        settings.update({"min_cluster_points": 1, "preferred_cluster_points": 1})
        snap = snapshot(points, settings, background=background)
        stage = snap["quality"]["denoise"]
        self.assertEqual((stage["input_point_count"], stage["kept_point_count"],
                          stage["dropped_point_count"]), (2, 2, 0))
        self.assertTrue(snap["quality"]["background_applied"])
        self.assertEqual(len(snap["candidates"]), 1)
        self.assertEqual(snap["candidates"][0]["point_count"], 1)

    def test_evidence_indices_map_to_original_points(self):
        points = np.vstack((isolated_points(), blob()))
        snap = snapshot(points, enabled())
        candidate = snap["candidates"][0]
        evidence = points[np.asarray(candidate["evidence_indices"])]
        self.assertEqual(len(evidence), candidate["point_count"])
        self.assertTrue(np.allclose(np.median(evidence, axis=0),
                                    candidate["center_source_m"]))
        self.assertTrue(np.all(np.linalg.norm(
            evidence - np.array([3.0, 0.0, -1.5]), axis=1) < 1.0))

    def test_snapshot_stays_deterministic_and_strict(self):
        points = np.vstack((blob(), isolated_points()))
        first = snapshot(points, enabled())
        second = snapshot(points, enabled())
        self.assertEqual(dumps_strict(first), dumps_strict(second))
        text = dumps_strict(first)
        self.assertNotIn("NaN", text)
        self.assertNotIn("Infinity", text)
        validate_snapshot(first)


class SettingsValidationTest(unittest.TestCase):
    def test_bad_values_rejected(self):
        for bad in ({"denoise_enabled": 1}, {"denoise_enabled": "yes"},
                    {"denoise_radius_m": 0.0}, {"denoise_radius_m": float("nan")},
                    {"denoise_min_neighbors": 0}, {"denoise_min_neighbors": True},
                    {"denoise_min_neighbors": 2.5}):
            with self.assertRaises(ValueError):
                resolve_settings(bad)
        with self.assertRaises(ValueError):
            resolve_settings({"not_a_setting": 1})

    def test_valid_overrides_resolve(self):
        resolved = resolve_settings({"denoise_enabled": True,
                                     "denoise_radius_m": 0.2,
                                     "denoise_min_neighbors": 3})
        self.assertTrue(resolved["denoise_enabled"])
        self.assertEqual(resolved["denoise_radius_m"], 0.2)
        self.assertEqual(resolved["denoise_min_neighbors"], 3)

    def test_old_settings_snapshot_without_denoise_keys_round_trips(self):
        old = {key: value for key, value in resolve_settings(None).items()
               if not key.startswith("denoise_")}
        resolved = resolve_settings(old)
        self.assertIs(resolved["denoise_enabled"], False)
        self.assertEqual(resolved["denoise_radius_m"], 0.1)
        self.assertEqual(resolved["denoise_min_neighbors"], 2)


if __name__ == "__main__":
    unittest.main()
