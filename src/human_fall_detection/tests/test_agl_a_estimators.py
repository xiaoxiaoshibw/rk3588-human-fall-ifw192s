"""GL-A（AGL-A-01..05）：统一 PointDomain/PlaneEstimate 与三薄适配器不变量。

覆盖：同域绑定/JSON 安全（A-01）、已知 GT 角度与法向翻转/显示旋转（A-02）、
严格拒收与 invalid 不造 identity（A-03）、TLS/SVD 数值交叉与 RANSAC 分母/预算
（A-04）、所有权/重载/配置 epoch/顺序无关（A-05）。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.adaptive_ground.contracts import (assemble_estimate, canonical_plane,
                                            display_rotation, estimator_config_id,
                                            resolve_estimator_config,
                                            validate_plane_estimate)
from core.adaptive_ground.estimators import ESTIMATORS
from core.adaptive_ground.selection import (build_point_domain, point_domain_reference,
                                            validate_point_domain)


def frame_key(ordinal=3):
    return {"stream_instance_id": "stream:agl-a-test", "session_id": "session:agl-a",
            "reference_epoch": 0, "ordinal": ordinal, "seq": ordinal,
            "source_frame": "innolidar", "source_stamp": 12.5 + ordinal,
            "time_domain": "device_seconds"}


def base_config(**overrides):
    config = {"inlier_threshold_m": 0.05, "min_inliers": 100, "min_inlier_fraction": 0.2,
              "ransac_iterations": 861, "ransac_iteration_hard_cap": 2000,
              "seed": 20261001}
    config.update(overrides)
    return config


def ground_points(pitch_deg, roll_deg, height_m=1.32, span=1.0, step=0.05,
                  noise=0.0, seed=7):
    rotation = np.array(display_rotation(pitch_deg, roll_deg))
    axis = np.arange(-span, span + step / 2.0, step)
    grid_x, grid_y = np.meshgrid(axis, axis)
    display = np.column_stack([grid_x.ravel(), grid_y.ravel(),
                               np.zeros(grid_x.size)])
    if noise:
        display[:, 2] = np.random.RandomState(seed).normal(0.0, noise, grid_x.size)
    source = (rotation.T @ (display - np.array([0.0, 0.0, height_m])).T).T
    return source, rotation


def domain_for(points, config=None, ordinal=3, selector_version=1,
               provenance="synthetic ground grid"):
    config = base_config() if config is None else config
    resolved = resolve_estimator_config(config)
    return build_point_domain(
        points, frame_key(ordinal),
        {"selector_id": "synthetic-grid-v1", "version": selector_version},
        estimator_config_id(resolved), provenance,
        {"up_axis": [0.0, 0.0, 1.0], "provenance": "synthetic identity reference",
         "version": 1})


class AglAEstimatorInterfaceTest(unittest.TestCase):
    def test_shared_domain_binding_and_json_safe_outputs_AGL_A_01(self):
        points, _ = ground_points(26.0, 5.0)
        domain = domain_for(points)
        names = ("source_points", "source_indices", "weights", "region_codes")
        snapshots = {name: domain[name].tobytes() for name in names}
        config = base_config()
        estimates = {name: ESTIMATORS[name](domain, config)
                     for name in ("tls", "svd", "ransac")}
        for name, estimate in estimates.items():
            self.assertEqual(estimate["domain_id"], domain["domain_id"], name)
            self.assertEqual(estimate["point_sha256"], domain["point_sha256"], name)
            self.assertEqual(estimate["rows_sha256"], domain["rows_sha256"], name)
            self.assertEqual(estimate["weights_sha256"], domain["weights_sha256"], name)
            self.assertEqual(estimate["frame_key"], domain["frame_key"], name)
            self.assertEqual(estimate["full_domain_residuals"]["point_count"],
                             domain["point_count"], name)
            self.assertEqual(estimate["full_domain_residuals"]["point_count"], len(points))
            validate_plane_estimate(estimate, domain)
            json.dumps(estimate, allow_nan=False)
        self.assertEqual(set(estimates["tls"]), set(estimates["svd"]))
        self.assertEqual(set(estimates["tls"]), set(estimates["ransac"]))
        for name in names:
            self.assertEqual(domain[name].tobytes(), snapshots[name],
                             name + " was modified by estimators")
        self.assertEqual(estimates["ransac"]["hypothesis_count"], 861)
        self.assertEqual(set(ESTIMATORS), {"tls", "svd", "ransac"})
        json.dumps(point_domain_reference(domain), allow_nan=False)
        same = domain_for(points.copy(), base_config())
        self.assertEqual(same["domain_id"], domain["domain_id"])

    def test_known_gt_angles_flip_and_display_rotation_AGL_A_02(self):
        for pitch, roll in ((10.0, 0.0), (26.0, 10.0), (45.0, -10.0),
                            (26.623261, -1.394671)):
            points, rotation = ground_points(pitch, roll)
            domain = domain_for(points)
            for name in ("tls", "svd", "ransac"):
                estimate = ESTIMATORS[name](domain, base_config())
                self.assertTrue(estimate["numerical_valid"], (name, pitch, roll))
                self.assertAlmostEqual(estimate["pitch_deg"], pitch, places=6)
                self.assertAlmostEqual(estimate["roll_deg"], roll, places=6)
                self.assertAlmostEqual(estimate["offset_source_m"], 1.32, places=9)
                normal = np.array(estimate["normal_source"])
                check = np.array(display_rotation(estimate["pitch_deg"],
                                                 estimate["roll_deg"]))
                error = float(np.linalg.norm(check @ normal - np.array([0.0, 0.0, 1.0])))
                self.assertLessEqual(error, 1e-12, name)
                self.assertGreater(float(normal @ rotation[2]), 1.0 - 1e-12)
                self.assertLessEqual(float(np.max(np.abs(check[2] - normal))), 1e-12)
                self.assertAlmostEqual(float(np.linalg.det(check)), 1.0, places=12)
                self.assertAlmostEqual(float(check[0][1]), 0.0, places=15)
                mapped = points @ check.T
                mapped[:, 2] += estimate["offset_source_m"]
                self.assertLessEqual(float(np.max(np.abs(mapped[:, 2]))), 1e-9)
        normal = np.array(display_rotation(26.0, 10.0))[2]
        self.assertEqual(canonical_plane(normal, 1.32, (0.0, 0.0, 1.0)),
                         canonical_plane(-normal, -1.32, (0.0, 0.0, 1.0)))
        with self.assertRaises(ValueError):
            canonical_plane([1.0, 0.0, 0.0], -0.5, (0.0, 0.0, 1.0))
        with self.assertRaises(ValueError):
            canonical_plane([0.0, 0.0, 0.0], 1.0, (0.0, 0.0, 1.0))

    def test_scaled_normal_offset_normalization_regression_AGL_A_02(self):
        """独审反例：|n|≠1 时 d 必须同除 ‖n‖（修复前 d 停在 -2.64，平面放大 ‖n‖ 倍）。"""
        up = (0.0, 0.0, 1.0)
        self.assertEqual(canonical_plane([0.0, 0.0, 2.0], -2.64, up),
                         canonical_plane([0.0, 0.0, 1.0], -1.32, up))
        self.assertEqual(canonical_plane([0.0, 0.0, -2.0], 2.64, up),
                         canonical_plane([0.0, 0.0, 1.0], -1.32, up))

    def test_scaled_normal_offset_assemble_regression_AGL_A_02(self):
        """缩放输入过公有装配：地面网格 z=-1.32（2z+2.64=0）；修复前 offset=2.64/RMS=1.32。"""
        points, _ = ground_points(0.0, 0.0)
        domain = domain_for(points)
        resolved = resolve_estimator_config(base_config())
        for normal, offset in (([0.0, 0.0, 2.0], 2.64), ([0.0, 0.0, -2.0], -2.64)):
            estimate = assemble_estimate("tls", domain, resolved,
                                         normal=normal, offset=offset)
            self.assertTrue(estimate["numerical_valid"])
            self.assertAlmostEqual(estimate["offset_source_m"], 1.32, places=12)
            self.assertAlmostEqual(estimate["pitch_deg"], 0.0, places=12)
            self.assertLessEqual(estimate["full_domain_residuals"]["rms_m"], 1e-9)
            validate_plane_estimate(estimate, domain)

    def test_strict_refusals_and_invalid_no_identity_AGL_A_03(self):
        points, _ = ground_points(10.0, 0.0, span=0.2, step=0.1)
        config = base_config()
        builder = lambda **extra: build_point_domain(
            points, frame_key(),
            {"selector_id": "synthetic-grid-v1", "version": 1},
            estimator_config_id(resolve_estimator_config(config)),
            "synthetic test source",
            {"up_axis": [0.0, 0.0, 1.0],
             "provenance": "synthetic identity reference", "version": 1}, **extra)
        for bad in (points.tolist() + [[True, 0.0, 0.0]], "not points",
                    np.full((4, 2), 1.0), []):
            with self.assertRaises(ValueError):
                domain_for(bad, config)
        nan_points = points.copy()
        nan_points[0, 0] = float("nan")
        with self.assertRaises(ValueError):
            domain_for(nan_points, config)
        index_count = len(points)
        for extra in ({"source_indices": [0, 1, 1] + list(range(3, index_count))},
                      {"source_indices": [-1] + list(range(1, index_count))},
                      {"source_indices": [0, 1]},
                      {"weights": np.ones(index_count - 1)},
                      {"weights": np.zeros(index_count)},
                      {"region_codes": np.zeros(index_count + 1, dtype=np.int64)}):
            with self.assertRaises(ValueError):
                builder(**extra)
        bad = domain_for(points, config)
        bad["frame_key"]["ordinal"] = True
        with self.assertRaises(ValueError):
            validate_point_domain(bad)
        bad = domain_for(points, config)
        bad["frame_key"]["source_stamp"] = float("nan")
        with self.assertRaises(ValueError):
            validate_point_domain(bad)
        bad = domain_for(points, config)
        bad["source_points"][0, 0] += 0.25
        with self.assertRaises(ValueError):
            validate_point_domain(bad)
        with self.assertRaises(ValueError):
            ESTIMATORS["tls"](bad, config)
        bad = domain_for(points, config)
        bad["point_count"] += 1
        with self.assertRaises(ValueError):
            validate_point_domain(bad)
        bad = domain_for(points, config)
        bad["units"] = "mm"
        with self.assertRaises(ValueError):
            validate_point_domain(bad)
        bad = domain_for(points, config)
        bad["schema"] = True
        with self.assertRaises(ValueError):
            validate_point_domain(bad)
        for override in ({"min_inliers": True}, {"min_inliers": 2},
                         {"min_inliers": 100.5}, {"min_inlier_fraction": 0.0},
                         {"min_inlier_fraction": 1.5},
                         {"inlier_threshold_m": float("nan")},
                         {"inlier_threshold_m": "0.05"},
                         {"ransac_iterations": 2001}, {"ransac_iterations": 0},
                         {"ransac_iteration_hard_cap": 2001}, {"seed": -1},
                         {"unknown": 1}):
            with self.assertRaises(ValueError):
                resolve_estimator_config(base_config(**override))
        domain = domain_for(points, config)
        with self.assertRaises(ValueError):
            ESTIMATORS["tls"](domain, base_config(seed=20261002))
        estimate = ESTIMATORS["tls"](domain, config)
        with self.assertRaises(ValueError):
            validate_plane_estimate(estimate, domain_for(points, config, ordinal=4))
        two = np.array([[0.10, 0.00, -1.20], [0.20, 0.10, -1.20]])
        invalid = ESTIMATORS["tls"](domain_for(two, config), config)
        self.assertFalse(invalid["numerical_valid"])
        self.assertFalse(invalid["valid"])
        self.assertIsNone(invalid["normal_source"])
        self.assertIsNone(invalid["offset_source_m"])
        self.assertIsNone(invalid["pitch_deg"])
        self.assertIsNone(invalid["full_domain_residuals"])
        self.assertEqual(invalid["confidence"], 0.0)
        self.assertEqual(invalid["quality_status"], "NOT_EVALUATED")
        self.assertIn("GL_LOW_POINT_COUNT", invalid["reject_reasons"])
        for forbidden in ("physical_verified", "extrinsics_verified",
                          "runtime_eligible", "transform_id", "rotation"):
            self.assertNotIn(forbidden, invalid)
        validate_plane_estimate(invalid, domain_for(two, config))
        line = np.column_stack([np.linspace(0.0, 1.0, 50), np.zeros(50),
                                np.full(50, -1.20)])
        line_domain = domain_for(line, config)
        for name in ("tls", "svd", "ransac"):
            estimate = ESTIMATORS[name](line_domain, config)
            self.assertFalse(estimate["numerical_valid"], name)
            self.assertIn("GL_DEGENERATE_GEOMETRY", estimate["reject_reasons"], name)
        axis = np.linspace(-0.5, 0.5, 41)
        narrow = np.linspace(-0.005, 0.005, 5)
        grid_x, grid_y = np.meshgrid(axis, narrow)
        strip_display = np.column_stack([grid_x.ravel(), grid_y.ravel(),
                                         np.zeros(grid_x.size)])
        strip = (np.array(display_rotation(5.0, 2.0)).T
                 @ (strip_display - np.array([0.0, 0.0, 1.20])).T).T
        strip_estimate = ESTIMATORS["tls"](domain_for(strip, config), config)
        self.assertTrue(strip_estimate["numerical_valid"])
        self.assertLess(strip_estimate["eigenvalue_ratio"], 0.01)
        self.assertEqual(strip_estimate["quality_status"], "NOT_EVALUATED")
        self.assertFalse(strip_estimate["valid"])

    def test_numeric_cross_check_and_ransac_denominators_AGL_A_04(self):
        for noise in (0.0, 0.008):
            points, _ = ground_points(26.0, 3.0, noise=noise)
            domain = domain_for(points)
            tls = ESTIMATORS["tls"](domain, base_config())
            svd = ESTIMATORS["svd"](domain, base_config())
            self.assertTrue(tls["numerical_valid"] and svd["numerical_valid"])
            dot = float(np.clip(np.dot(tls["normal_source"], svd["normal_source"]),
                                -1.0, 1.0))
            self.assertLessEqual(float(np.degrees(np.arccos(dot))), 1e-3)
            self.assertLessEqual(abs(tls["offset_source_m"] - svd["offset_source_m"]),
                                 1e-5)
        points, _ = ground_points(26.0, 3.0, noise=0.004)
        domain = domain_for(points)
        ransac = ESTIMATORS["ransac"](domain, base_config())
        self.assertTrue(ransac["numerical_valid"])
        normal = np.array(ransac["normal_source"])
        offset = ransac["offset_source_m"]
        manual = int(np.count_nonzero(np.abs(points @ normal + offset) <= 0.05))
        full = ransac["full_domain_residuals"]
        self.assertEqual(full["point_count"], len(points))
        self.assertEqual(full["support_count"], manual)
        self.assertAlmostEqual(full["support_fraction"], manual / len(points))
        self.assertEqual(full["basis"], "full_domain_untruncated")
        self.assertEqual(ransac["hypothesis_count"], 861)
        self.assertEqual(ransac["iterations_requested"], 861)
        self.assertTrue(ransac["resource_complete"])
        with self.assertRaises(ValueError):
            resolve_estimator_config(base_config(ransac_iterations=2001))
        rng = np.random.RandomState(9)
        cloud = rng.uniform(-2.0, 2.0, size=(600, 3))
        strict = base_config(min_inliers=580, min_inlier_fraction=0.99)
        cloud_domain = domain_for(cloud, strict)
        result = ESTIMATORS["ransac"](cloud_domain, strict)
        self.assertFalse(result["numerical_valid"])
        self.assertFalse(result["valid"])
        self.assertIn("GL_RANSAC_INVALID", result["reject_reasons"])
        self.assertIsNotNone(result["diagnostic_hypothesis"])
        self.assertEqual(result["hypothesis_count"], 861)
        self.assertTrue(ESTIMATORS["tls"](cloud_domain, strict)["numerical_valid"])

    def test_ownership_reload_and_config_epoch_AGL_A_05(self):
        points, _ = ground_points(12.0, -4.0)
        content = points.copy()
        config = base_config()
        domain = domain_for(points, config)
        names = ("source_points", "source_indices", "weights", "region_codes")
        snapshots = {name: domain[name].tobytes() for name in names}
        first = {name: ESTIMATORS[name](domain, config)
                 for name in ("tls", "svd", "ransac")}
        original = copy.deepcopy(first)
        points[:] = 0.0
        first["tls"]["normal_source"][0] = 123.0
        first["tls"]["frame_key"]["ordinal"] = 999
        first["tls"]["reject_reasons"].append("MUTATED")
        for name in ("tls", "svd", "ransac"):
            self.assertEqual(ESTIMATORS[name](domain, config), original[name], name)
        for name in names:
            self.assertEqual(domain[name].tobytes(), snapshots[name],
                             name + " was modified")
        self.assertEqual(domain["frame_key"]["ordinal"], 3)
        same = domain_for(content.copy(), base_config())
        self.assertEqual(same["domain_id"], domain["domain_id"])
        changed = content.copy()
        changed[0, 0] += 0.01
        other = domain_for(changed, config)
        self.assertNotEqual(other["domain_id"], domain["domain_id"])
        again = {name: ESTIMATORS[name](domain, base_config())
                 for name in ("tls", "svd", "ransac")}
        for name in ("tls", "svd", "ransac"):
            self.assertEqual(again[name], original[name], name)
        other_config = base_config(seed=20261002)
        other_domain = domain_for(content, other_config)
        self.assertNotEqual(other_domain["config_id"], domain["config_id"])
        with self.assertRaises(ValueError):
            ESTIMATORS["tls"](domain, other_config)
        with self.assertRaises(ValueError):
            ESTIMATORS["tls"](other_domain, config)
        order = {name: ESTIMATORS[name](domain, config)
                 for name in ("ransac", "svd", "tls")}
        for name in ("tls", "svd", "ransac"):
            self.assertEqual(order[name], original[name], name)


if __name__ == '__main__':
    unittest.main()
