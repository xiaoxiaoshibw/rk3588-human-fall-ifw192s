"""GL-B（AGL-B-01..05）：质量/覆盖/退化/score/区域门与 P02 历史 FAIL 保留。

覆盖：全域/逐区残差独立 oracle 与未裁尾分母（A-01）、低 RMS 退化门（A-02）、
score 边界/单调/配置关系（A-03）、required 区/混合几何/P02 留一区 FAIL（A-04）、
可追溯与无旧 score 泄漏（A-05）。
"""
import copy
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.adaptive_ground.contracts import (estimator_config_id,
                                            resolve_estimator_config,
                                            validate_plane_estimate)
from core.adaptive_ground.estimators import ESTIMATORS
from core.adaptive_ground.estimators.tls import estimate_tls
from core.adaptive_ground.quality import (evaluate_quality, quality_config_id,
                                          resolve_quality_config,
                                          validate_quality_report)
from core.adaptive_ground.selection import build_point_domain, validate_point_domain
from core.ground_diagnostics import residual_stats
from core.ground_evidence import digest
from test_agl_a_estimators import base_config, frame_key, ground_points

P02_FIXTURE = (Path(__file__).resolve().parents[3] / "docs" / "human_fall"
               / "evidence" / "2026-10-04_p02_four_roi_r1" / "02_FROZEN_POINTS.npz")
P02_UP = [-math.sin(math.radians(26.0)), 0.0, math.cos(math.radians(26.0))]


def quality_config(**overrides):
    config = {"min_points": 500, "min_supported_regions": 1, "region_min_points": 20,
              "required_region_codes": [], "max_rms_m": 0.03, "max_p95_m": 0.05,
              "min_support_ratio": 0.8, "min_lambda2_lambda3": 0.02,
              "soft_full_lambda2_lambda3": 0.10, "min_occupied_cells": 6,
              "soft_full_occupied_cells": 20, "coverage_cell_m": 0.20,
              "min_tangent_extents_m": 0.10, "max_single_cell_share": 0.35,
              "max_normal_tilt_deg": 30.0, "soft_good_normal_tilt_deg": 10.0,
              "soft_good_rms_m": 0.01, "soft_good_p95_m": 0.02,
              "soft_full_support_ratio": 0.95, "soft_full_points": 2000,
              "score_weights": [0.15, 0.20, 0.15, 0.10, 0.15, 0.15, 0.10]}
    config.update(overrides)
    return config


def build_domain(points, config=None, codes=None, ordinal=3, up=(0.0, 0.0, 1.0),
                 provenance="synthetic quality domain"):
    config = base_config() if config is None else config
    resolved = resolve_estimator_config(config)
    return build_point_domain(
        points, frame_key(ordinal), {"selector_id": "synthetic-quality-v1", "version": 1},
        estimator_config_id(resolved), provenance,
        {"up_axis": list(up), "provenance": "synthetic identity reference", "version": 1},
        region_codes=codes)


def median_avg(values):
    ordered = sorted(values)
    size = len(ordered)
    if size % 2:
        return ordered[size // 2]
    return 0.5 * (ordered[size // 2 - 1] + ordered[size // 2])


def percentile_linear(values, q):
    ordered = sorted(values)
    size = len(ordered)
    position = (size - 1) * q / 100.0
    low, high = int(math.floor(position)), int(math.ceil(position))
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def oracle_stats(signed, threshold):
    values = [float(v) for v in signed]
    size = len(values)
    median = median_avg(values)
    supported = sum(1 for v in values if abs(v) <= threshold)
    return {"point_count": size,
            "rms_m": math.sqrt(sum(v * v for v in values) / size),
            "p95_m": percentile_linear([abs(v) for v in values], 95.0),
            "mad_m": median_avg([abs(v - median) for v in values]),
            "max_abs_m": max(abs(v) for v in values),
            "support_count": supported,
            "support_fraction": supported / size}


class AglBQualityTest(unittest.TestCase):
    def test_full_and_region_oracle_untruncated_denominators_AGL_B_01(self):
        points, _ = ground_points(20.0, 3.0, noise=0.006, span=0.8)
        codes = np.zeros(len(points), dtype=np.int64)
        codes[:600] = 1
        codes[600:] = 2
        domain = build_domain(points, codes=codes)
        estimate = estimate_tls(domain, base_config())
        report = evaluate_quality(estimate, domain, base_config(),
                                  quality_config(required_region_codes=[1, 2],
                                                 min_supported_regions=2))
        self.assertTrue(report["valid"], report["reject_reasons"])
        validate_quality_report(report, domain, estimate)
        normal = np.array(estimate["normal_source"])
        signed = points @ normal + estimate["offset_source_m"]
        oracle = oracle_stats(signed, 0.05)
        for key in ("rms_m", "p95_m", "mad_m", "max_abs_m"):
            self.assertAlmostEqual(report["full"][key], oracle[key], delta=1e-12, msg=key)
        self.assertEqual(report["full"]["support_count"], oracle["support_count"])
        self.assertAlmostEqual(report["full"]["support_fraction"],
                               oracle["support_fraction"], delta=1e-15)
        self.assertEqual(report["full"]["point_count"], len(points))
        for record in report["regions"]:
            mask = codes == record["region_code"]
            expected = oracle_stats(signed[mask], 0.05)
            self.assertEqual(record["point_count"], int(mask.sum()))
            for key in ("rms_m", "p95_m", "mad_m"):
                self.assertAlmostEqual(record[key], expected[key], delta=1e-12, msg=key)
            self.assertEqual(record["support_count"], expected["support_count"])
        blob = (np.random.RandomState(3).uniform(-0.1, 0.1, size=(60, 3))
                + np.array([0.0, 0.0, -1.0]))
        dense = np.vstack([points, blob])
        dense_domain = build_domain(dense, codes=np.zeros(len(dense), dtype=np.int64))
        ransac = ESTIMATORS["ransac"](dense_domain, base_config())
        dense_report = evaluate_quality(ransac, dense_domain, base_config(),
                                        quality_config())
        dense_normal = np.array(ransac["normal_source"])
        dense_signed = dense @ dense_normal + ransac["offset_source_m"]
        self.assertAlmostEqual(dense_report["full"]["rms_m"],
                               oracle_stats(dense_signed, 0.05)["rms_m"], delta=1e-12)
        inlier_rms = float(np.sqrt(np.mean(np.square(
            dense_signed[np.abs(dense_signed) <= 0.05]))))
        self.assertGreater(dense_report["full"]["rms_m"], inlier_rms + 1e-6)
        self.assertFalse(dense_report["valid"])
        self.assertIn("GL_HIGH_RESIDUAL", dense_report["reject_reasons"])

    def test_hard_gates_reject_low_rms_degenerates_AGL_B_02(self):
        config = base_config()
        line = np.column_stack([np.linspace(0.0, 1.0, 50), np.zeros(50),
                                np.full(50, -1.2)])
        line_domain = build_domain(line)
        line_report = evaluate_quality(estimate_tls(line_domain, config), line_domain,
                                       config, quality_config())
        self.assertFalse(line_report["valid"])
        self.assertIn("GL_UPSTREAM_INVALID", line_report["reject_reasons"])
        axis = np.linspace(-0.5, 0.5, 41)
        narrow = np.linspace(-0.005, 0.005, 5)
        grid_x, grid_y = np.meshgrid(axis, narrow)
        strip = np.column_stack([grid_x.ravel(), grid_y.ravel(),
                                 np.full(grid_x.size, -1.2)])
        strip_domain = build_domain(strip)
        strip_estimate = estimate_tls(strip_domain, config)
        self.assertTrue(strip_estimate["numerical_valid"])
        strip_report = evaluate_quality(strip_estimate, strip_domain, config,
                                        quality_config())
        self.assertFalse(strip_report["valid"])
        self.assertIn("GL_DEGENERATE_GEOMETRY", strip_report["reject_reasons"])
        self.assertIn("GL_LOW_SPATIAL_COVERAGE", strip_report["reject_reasons"])
        tiny_axis = np.linspace(-0.1, 0.1, 5)
        tiny_x, tiny_y = np.meshgrid(tiny_axis, tiny_axis)
        tiny = np.column_stack([tiny_x.ravel(), tiny_y.ravel(),
                                np.full(tiny_x.size, -1.2)])
        tiny_domain = build_domain(tiny)
        tiny_report = evaluate_quality(estimate_tls(tiny_domain, config), tiny_domain,
                                       config, quality_config())
        self.assertFalse(tiny_report["valid"])
        self.assertIn("GL_LOW_POINT_COUNT", tiny_report["reject_reasons"])
        dense_axis = np.linspace(0.0, 0.09, 40)
        dense_x, dense_y = np.meshgrid(dense_axis, dense_axis)
        cell = np.column_stack([dense_x.ravel(), dense_y.ravel(),
                                np.full(dense_x.size, -1.2)])
        cell_domain = build_domain(cell)
        cell_report = evaluate_quality(estimate_tls(cell_domain, config), cell_domain,
                                       config, quality_config())
        self.assertFalse(cell_report["valid"])
        self.assertLess(cell_report["full"]["rms_m"], 1e-9)
        self.assertIn("GL_LOW_SPATIAL_COVERAGE", cell_report["reject_reasons"])

    def test_score_bounds_monotonicity_and_config_relations_AGL_B_03(self):
        for override in ({"score_weights": [1.0] * 7},
                         {"score_weights": [0.1] * 7},
                         {"score_weights": [-1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
                         {"max_rms_m": 0.005},
                         {"min_points": 2000},
                         {"min_occupied_cells": 25},
                         {"min_support_ratio": 0.96},
                         {"max_normal_tilt_deg": 91.0},
                         {"required_region_codes": [1, 1]},
                         {"required_region_codes": "1,2"},
                         {"soft_good_rms_m": True},
                         {"min_inlier_fraction": 0.5}):
            with self.assertRaises(ValueError):
                resolve_quality_config(quality_config(**override))
        quiet, _ = ground_points(10.0, 2.0, noise=0.004)
        loud, _ = ground_points(10.0, 2.0, noise=0.018)
        quiet_domain = build_domain(quiet)
        loud_domain = build_domain(loud, ordinal=4)
        quiet_report = evaluate_quality(estimate_tls(quiet_domain, base_config()),
                                        quiet_domain, base_config(), quality_config())
        loud_report = evaluate_quality(estimate_tls(loud_domain, base_config()),
                                       loud_domain, base_config(), quality_config())
        self.assertTrue(quiet_report["valid"] and loud_report["valid"])
        self.assertGreater(quiet_report["score_components"]["q_rms"],
                           loud_report["score_components"]["q_rms"])
        self.assertGreater(quiet_report["confidence_geo"], loud_report["confidence_geo"])
        for report in (quiet_report, loud_report):
            for key in ("q_rms", "q_p95", "q_support", "q_count", "q_coverage",
                        "q_condition", "q_normal"):
                self.assertGreaterEqual(report["score_components"][key], 0.0)
                self.assertLessEqual(report["score_components"][key], 1.0)
            self.assertGreaterEqual(report["confidence_geo"], 0.0)
            self.assertLessEqual(report["confidence_geo"], 1.0)
        strict, _ = ground_points(5.0, 0.0)
        strict_domain = build_domain(strict, ordinal=5)
        strict_report = evaluate_quality(
            estimate_tls(strict_domain, base_config()), strict_domain, base_config(),
            quality_config(min_points=5000, soft_full_points=6000))
        self.assertFalse(strict_report["valid"])
        self.assertGreater(strict_report["score_components"]["raw_score"], 0.0)
        self.assertEqual(strict_report["confidence_geo"], 0.0)
        self.assertIn("GL_LOW_POINT_COUNT", strict_report["reject_reasons"])

    def test_required_region_fail_and_mixed_geometry_AGL_B_04(self):
        points, _ = ground_points(0.0, 0.0, noise=0.002)
        xx, yy = points[:, 0], points[:, 1]
        codes = np.full(len(points), 1, dtype=np.int64)
        codes[(xx > 0) & (yy > 0)] = 2
        codes[(xx <= 0) & (yy <= 0)] = 4
        quadrant3 = (xx <= 0) & (yy > 0)
        codes[quadrant3] = 4
        bad_rows = np.nonzero(quadrant3)[0][:50]
        codes[bad_rows] = 3
        self.assertEqual(int(np.count_nonzero(codes == 3)), 50)
        shifted = points.copy()
        shifted[bad_rows, 2] += 0.08
        domain = build_domain(shifted, codes=codes)
        estimate = estimate_tls(domain, base_config())
        report = evaluate_quality(estimate, domain, base_config(),
                                  quality_config(required_region_codes=[1, 2, 3, 4],
                                                 min_supported_regions=4))
        self.assertFalse(report["valid"])
        self.assertIn("GL_REQUIRED_REGION_FAILED", report["reject_reasons"])
        region3 = [item for item in report["regions"] if item["region_code"] == 3][0]
        self.assertFalse(region3["passed"])
        self.assertGreater(region3["rms_m"], 0.03)
        self.assertLess(region3["support_fraction"], 0.8)
        for code in (1, 2, 4):
            record = [item for item in report["regions"] if item["region_code"] == code][0]
            self.assertTrue(record["passed"], (code, record["reject_reasons"]))
        steep, _ = ground_points(35.0, 0.0, noise=0.002)
        steep_domain = build_domain(steep, ordinal=6)
        steep_estimate = estimate_tls(steep_domain, base_config())
        self.assertTrue(steep_estimate["numerical_valid"])
        steep_report = evaluate_quality(steep_estimate, steep_domain, base_config(),
                                        quality_config())
        self.assertFalse(steep_report["valid"])
        self.assertIn("GL_NORMAL_INVALID", steep_report["reject_reasons"])
        plain_domain = build_domain(points, ordinal=7)
        missing_report = evaluate_quality(
            estimate_tls(plain_domain, base_config()), plain_domain, base_config(),
            quality_config(required_region_codes=[1, 9]))
        self.assertFalse(missing_report["valid"])
        self.assertIn("GL_REQUIRED_REGION_MISSING", missing_report["reject_reasons"])

    def test_p02_leave_one_out_fail_preserved_AGL_B_04(self):
        if not P02_FIXTURE.exists():
            self.skipTest("P02 fixture unavailable")
        data = np.load(P02_FIXTURE, allow_pickle=True)
        points = np.ascontiguousarray(data["source"], dtype=np.float64)
        codes = np.ascontiguousarray(data["region_code"], dtype=np.int64)
        self.assertEqual(sorted(set(codes.tolist())), [1, 2, 3, 4])
        config = base_config()
        pooled_domain = build_domain(points, config=config, codes=codes, ordinal=0,
                                     up=P02_UP,
                                     provenance="P02 frozen four-ROI fixture (A+C, exposed)")
        pooled = estimate_tls(pooled_domain, config)
        self.assertAlmostEqual(pooled["pitch_deg"], 26.623261, places=5)
        report = evaluate_quality(pooled, pooled_domain, config,
                                  quality_config(required_region_codes=[1, 2, 3, 4],
                                                 min_supported_regions=4))
        self.assertTrue(report["valid"], report["reject_reasons"])
        for record in report["regions"]:
            self.assertTrue(record["passed"], (record["region_code"],
                                               record["reject_reasons"]))
        results = {}
        for held in (1, 2, 3, 4):
            mask = codes == held
            fit_domain = build_domain(
                np.ascontiguousarray(points[~mask]), config=config,
                codes=np.ascontiguousarray(codes[~mask]), ordinal=held, up=P02_UP,
                provenance="P02 leave-one-out fit for region %d" % held)
            plane = estimate_tls(fit_domain, config)
            results[held] = residual_stats(points[mask], plane["normal_source"],
                                           plane["offset_source_m"], 0.05)
        self.assertLessEqual(results[2]["rms_m"], 0.03)
        self.assertLessEqual(results[2]["p95_m"], 0.05)
        self.assertGreater(results[1]["p95_m"], 0.05)
        self.assertLessEqual(results[1]["rms_m"], 0.03)
        self.assertGreater(results[3]["p95_m"], 0.05)
        self.assertGreater(results[4]["rms_m"], 0.03)
        self.assertGreater(results[4]["p95_m"], 0.05)
        self.assertLess(results[4]["support_fraction"], 0.8)
        for held, expected in ((1, (0.02507, 0.05378)), (2, (0.01906, 0.03432)),
                               (3, (0.02695, 0.05159)), (4, (0.04331, 0.07745))):
            self.assertAlmostEqual(results[held]["rms_m"], expected[0], delta=5e-6,
                                   msg="rms region %d" % held)
            self.assertAlmostEqual(results[held]["p95_m"], expected[1], delta=5e-6,
                                   msg="p95 region %d" % held)

    def test_traceability_binding_no_stale_leak_AGL_B_05(self):
        points, _ = ground_points(15.0, 1.0, noise=0.004)
        domain = build_domain(points)
        estimate = estimate_tls(domain, base_config())
        config = quality_config()
        first = evaluate_quality(estimate, domain, base_config(), config)
        snapshot = copy.deepcopy(first)
        validate_quality_report(first, domain, estimate)
        self.assertEqual(first["report_id"],
                         "agl-quality:" + digest({k: v for k, v in first.items()
                                                  if k != "report_id"}))
        json.dumps(first, allow_nan=False)
        self.assertEqual(first["quality_config_id"],
                         quality_config_id(resolve_quality_config(config)))
        tampered_estimate = copy.deepcopy(estimate)
        tampered_estimate["normal_source"][0] += 0.5
        with self.assertRaises(ValueError):
            evaluate_quality(tampered_estimate, domain, base_config(), config)
        tampered_domain = copy.deepcopy(domain)
        tampered_domain["region_codes"][0] = 5
        with self.assertRaises(ValueError):
            validate_point_domain(tampered_domain)
        with self.assertRaises(ValueError):
            evaluate_quality(estimate, tampered_domain, base_config(), config)
        anchor_tamper = copy.deepcopy(estimate)
        anchor_tamper["sign_anchor"] = [0.0, 0.0, -1.0]
        with self.assertRaises(ValueError):
            validate_plane_estimate(anchor_tamper, domain)
        second = evaluate_quality(estimate, domain, base_config(), config)
        self.assertEqual(second, snapshot)
        other = evaluate_quality(estimate, domain, base_config(),
                                 quality_config(min_supported_regions=2))
        self.assertNotEqual(other["quality_config_id"], first["quality_config_id"])
        self.assertEqual(first, snapshot)


if __name__ == '__main__':
    unittest.main()
