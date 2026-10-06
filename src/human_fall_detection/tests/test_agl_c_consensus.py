"""GL-C（AGL-C-01..05）：三估计器一致性仲裁不变量与真实 P02 场景。"""
import copy
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.adaptive_ground.consensus import (build_consensus, consensus_config_id,
                                            quality_summary,
                                            resolve_consensus_config,
                                            validate_consensus_report)
from core.adaptive_ground.contracts import (canonical_plane, display_rotation,
                                            validate_plane_estimate)
from core.adaptive_ground.estimators import ESTIMATORS
from core.adaptive_ground.quality import evaluate_quality
from core.ground_evidence import digest
from test_agl_a_estimators import base_config, ground_points
from test_agl_b_quality import (P02_FIXTURE, P02_UP, build_domain, quality_config)

ORDER = ("tls", "svd", "ransac")


def consensus_config(**overrides):
    config = {"good_angle_deg": 0.5, "degraded_angle_deg": 1.5,
              "good_offset_m": 0.02, "degraded_offset_m": 0.05,
              "tls_svd_numeric_angle_deg": 0.001,
              "tls_svd_numeric_offset_m": 0.00001,
              "degraded_confidence_cap": 0.7, "min_good_confidence": 0.8,
              "min_degraded_confidence": 0.55, "degraded_updates_enabled": False,
              "ls_only_updates_enabled": False}
    config.update(overrides)
    return config


def craft(base, pitch_delta=0.0, roll_delta=0.0, offset_delta=0.0, flip=False,
          reference=None):
    estimate = copy.deepcopy(base)
    ref = base if reference is None else reference
    pitch = ref["pitch_deg"] + pitch_delta
    roll = ref["roll_deg"] + roll_delta
    normal = np.array(display_rotation(pitch, roll))[2]
    offset = ref["offset_source_m"] + offset_delta
    if flip:
        normal, offset = -normal, -offset
    estimate["pitch_deg"] = pitch
    estimate["roll_deg"] = roll
    estimate["normal_source"] = [float(v) for v in normal]
    estimate["offset_source_m"] = float(offset)
    return estimate


def q_all(confidence=0.9):
    return {name: {"valid": True, "confidence": confidence, "reasons": []}
            for name in ORDER}


class AglCConsensusTest(unittest.TestCase):
    def base_setup(self):
        points, _ = ground_points(20.0, 0.0, noise=0.002)
        domain = build_domain(points)
        estimates = {name: ESTIMATORS[name](domain, base_config()) for name in ORDER}
        return domain, estimates

    def test_pairwise_oracle_flip_and_binding_AGL_C_01(self):
        domain, base = self.base_setup()
        estimates = {"tls": craft(base["tls"]),
                     "svd": craft(base["svd"], pitch_delta=0.7, roll_delta=0.4),
                     "ransac": craft(base["ransac"], pitch_delta=1.2, roll_delta=-0.5,
                                     offset_delta=0.004)}
        quality = q_all()
        report = build_consensus(estimates, domain, quality, consensus_config())
        validate_consensus_report(report, domain)
        planes = {}
        for name in ORDER:
            vector, offset = canonical_plane(estimates[name]["normal_source"],
                                             estimates[name]["offset_source_m"],
                                             domain["spatial_basis"]["up_axis"])
            normal = np.array(vector)
            planes[name] = (normal, float(offset),
                            math.degrees(math.atan2(-float(normal[0]), float(normal[2]))),
                            math.degrees(math.asin(float(np.clip(normal[1], -1, 1)))))
        for entry in report["pairwise"]:
            first, second = entry["a"], entry["b"]
            na, da, pa, ra = planes[first]
            nb, db, pb, rb = planes[second]
            expected_angle = math.degrees(math.acos(
                float(np.clip(float(na @ nb), -1.0, 1.0))))
            self.assertAlmostEqual(entry["angle_deg"], expected_angle, delta=1e-12)
            self.assertAlmostEqual(entry["offset_gap_m"], abs(da - db), delta=1e-12)
            self.assertAlmostEqual(entry["pitch_gap_deg"], abs(pa - pb), delta=1e-12)
            self.assertAlmostEqual(entry["roll_gap_deg"], abs(ra - rb), delta=1e-12)
        flipped = {"tls": estimates["tls"], "svd": estimates["svd"],
                   "ransac": craft(base["ransac"], flip=True)}
        flip_report = build_consensus(flipped, domain, quality, consensus_config())
        entry = [item for item in flip_report["pairwise"]
                 if {item["a"], item["b"]} == {"tls", "ransac"}][0]
        plain = build_consensus({"tls": estimates["tls"], "svd": estimates["svd"],
                                 "ransac": craft(base["ransac"])}, domain, quality,
                                consensus_config())
        plain_entry = [item for item in plain["pairwise"]
                       if {item["a"], item["b"]} == {"tls", "ransac"}][0]
        self.assertEqual(entry["level"], plain_entry["level"])
        self.assertAlmostEqual(entry["angle_deg"], plain_entry["angle_deg"], delta=1e-12)
        self.assertLess(entry["angle_deg"], 1.0)  # n≈-n 不应被当成 180° 反向
        for mutate in ("domain", "units", "frame", "config", "epoch"):
            bad = craft(base["ransac"])
            if mutate == "domain":
                bad["domain_id"] = "agl-domain:" + "0" * 64
            elif mutate == "units":
                bad["units"] = "mm"
            elif mutate == "frame":
                bad["frame_key"]["ordinal"] += 1
            elif mutate == "config":
                bad["config_id"] = "agl-config:" + "0" * 64
            else:
                bad["frame_key"]["reference_epoch"] += 1
            with self.assertRaises(ValueError, msg=mutate):
                build_consensus({"tls": estimates["tls"], "svd": estimates["svd"],
                                 "ransac": bad}, domain, quality, consensus_config())

    def test_status_matrix_and_pair_boundaries_AGL_C_02(self):
        domain, base = self.base_setup()
        quality = q_all()
        reports = {name: evaluate_quality(base[name], domain, base_config(),
                                          quality_config()) for name in ORDER}
        summaries = {name: quality_summary(reports[name]) for name in ORDER}
        good = build_consensus(base, domain, summaries, consensus_config())
        self.assertEqual(good["status"], "GOOD")
        self.assertEqual(good["supporting_estimators"], ["tls", "svd", "ransac"])
        self.assertEqual(good["supporting_families"], ["ls", "robust"])
        self.assertTrue(good["numeric_check_ok"])
        self.assertTrue(good["update_candidate_allowed"])
        self.assertEqual(good["selected_estimator"], "tls")
        self.assertAlmostEqual(good["confidence"],
                               min(summaries[n]["confidence"] for n in ORDER),
                               places=12)
        estimates = {"tls": craft(base["tls"], reference=base["tls"]),
                     "svd": craft(base["svd"], pitch_delta=0.9, reference=base["tls"]),
                     "ransac": craft(base["ransac"], pitch_delta=0.9,
                                     reference=base["tls"])}
        degraded = build_consensus(estimates, domain, quality, consensus_config())
        self.assertEqual(degraded["status"], "DEGRADED")
        self.assertEqual(degraded["supporting_estimators"], ["tls", "svd", "ransac"])
        self.assertFalse(degraded["update_candidate_allowed"])
        for delta, expected_status, expected_level, expected_support in (
                (0.4999, "GOOD", "GOOD", ["tls", "svd", "ransac"]),
                (0.5001, "DEGRADED", "DEGRADED", ["tls", "svd", "ransac"]),
                (1.4999, "DEGRADED", "DEGRADED", ["tls", "svd", "ransac"]),
                (1.5001, "DEGRADED", "CONFLICT", ["tls", "svd"])):
            estimates = {"tls": craft(base["tls"], reference=base["tls"]),
                         "svd": craft(base["svd"], reference=base["tls"]),
                         "ransac": craft(base["ransac"], pitch_delta=delta,
                                         reference=base["tls"])}
            report = build_consensus(estimates, domain, quality, consensus_config())
            entry = [item for item in report["pairwise"]
                     if {item["a"], item["b"]} == {"svd", "ransac"}][0]
            self.assertEqual(entry["level"], expected_level, delta)
            self.assertEqual(report["status"], expected_status, delta)
            self.assertEqual(report["supporting_estimators"], expected_support, delta)

    def test_family_aware_and_numeric_visibility_AGL_C_03(self):
        domain, base = self.base_setup()
        quality = q_all()
        estimates = {"tls": craft(base["tls"], reference=base["tls"]),
                     "svd": craft(base["svd"], reference=base["tls"]),
                     "ransac": craft(base["ransac"], pitch_delta=3.0,
                                     reference=base["tls"])}
        report = build_consensus(estimates, domain, quality, consensus_config())
        self.assertEqual(report["status"], "DEGRADED")
        self.assertEqual(report["supporting_estimators"], ["tls", "svd"])
        self.assertEqual(report["supporting_families"], ["ls"])
        self.assertFalse(report["update_candidate_allowed"])
        self.assertIn("GL_ROBUST_DIVERGENCE", report["reason_codes"])
        estimates = {"tls": craft(base["tls"], reference=base["tls"]),
                     "svd": craft(base["svd"], pitch_delta=0.6, reference=base["tls"]),
                     "ransac": craft(base["ransac"], pitch_delta=0.6,
                                     reference=base["tls"])}
        report = build_consensus(estimates, domain, quality, consensus_config())
        self.assertEqual(report["status"], "DEGRADED")
        self.assertFalse(report["numeric_check_ok"])
        self.assertIn("GL_NUMERICAL_DISAGREEMENT", report["reason_codes"])
        mixed = {"tls": {"valid": True, "confidence": 0.9, "reasons": []},
                 "svd": {"valid": False, "confidence": 0.0,
                         "reasons": ["GL_HIGH_RESIDUAL"]},
                 "ransac": {"valid": True, "confidence": 0.9, "reasons": []}}
        report = build_consensus(base, domain, mixed,
                                 consensus_config(degraded_updates_enabled=True))
        self.assertEqual(report["status"], "DEGRADED")
        self.assertEqual(report["supporting_estimators"], ["tls", "ransac"])
        self.assertTrue(report["update_candidate_allowed"])
        self.assertIn("GL_HIGH_RESIDUAL", report["reason_codes"])
        ls_only = {"tls": {"valid": True, "confidence": 0.9, "reasons": []},
                   "svd": {"valid": True, "confidence": 0.9, "reasons": []},
                   "ransac": {"valid": False, "confidence": 0.0, "reasons": []}}
        default = build_consensus(base, domain, ls_only, consensus_config())
        self.assertEqual(default["supporting_estimators"], ["tls", "svd"])
        self.assertFalse(default["update_candidate_allowed"])
        enabled = build_consensus(base, domain, ls_only,
                                  consensus_config(ls_only_updates_enabled=True))
        self.assertTrue(enabled["update_candidate_allowed"])

    def test_nontransitive_order_and_tie_AGL_C_04(self):
        domain, base = self.base_setup()
        quality = q_all()
        estimates = {"tls": craft(base["tls"], reference=base["tls"]),
                     "svd": craft(base["svd"], pitch_delta=1.2, reference=base["tls"]),
                     "ransac": craft(base["ransac"], pitch_delta=2.4,
                                     reference=base["tls"])}
        report = build_consensus(estimates, domain, quality, consensus_config())
        self.assertEqual(report["status"], "BAD")
        self.assertEqual(report["supporting_estimators"], [])
        self.assertIn("GL_NO_CONSENSUS", report["reason_codes"])
        horizontal = {}
        for name in ORDER:
            bad = copy.deepcopy(base[name])
            bad["normal_source"] = [1.0, 0.0, 0.0]
            bad["offset_source_m"] = -1.32
            horizontal[name] = bad
        report = build_consensus(horizontal, domain, quality, consensus_config())
        self.assertEqual(report["status"], "BAD")
        self.assertIn("GL_NORMAL_INVALID", report["reason_codes"])
        same = {name: craft(base[name]) for name in ORDER}
        first = build_consensus({name: same[name] for name in ORDER},
                                domain, quality, consensus_config())
        second = build_consensus({name: same[name] for name in reversed(ORDER)},
                                 domain, quality, consensus_config())
        self.assertEqual(first, second)
        estimates = {"tls": craft(base["tls"], reference=base["tls"]),
                     "svd": craft(base["svd"], reference=base["tls"]),
                     "ransac": craft(base["ransac"], pitch_delta=3.0,
                                     reference=base["tls"])}
        tie = {"tls": {"valid": True, "confidence": 0.9, "reasons": []},
               "svd": {"valid": True, "confidence": 0.9, "reasons": []},
               "ransac": {"valid": False, "confidence": 0.0, "reasons": []}}
        report = build_consensus(estimates, domain, tie, consensus_config())
        self.assertEqual(report["selected_estimator"], "tls")
        raised = {"tls": {"valid": True, "confidence": 0.8, "reasons": []},
                  "svd": {"valid": True, "confidence": 0.95, "reasons": []},
                  "ransac": {"valid": False, "confidence": 0.0, "reasons": []}}
        report = build_consensus(estimates, domain, raised, consensus_config())
        self.assertEqual(report["selected_estimator"], "svd")

    def test_cap_reasons_and_p02_current_angle_AGL_C_05(self):
        domain, base = self.base_setup()
        estimates = {"tls": craft(base["tls"], reference=base["tls"]),
                     "svd": craft(base["svd"], pitch_delta=0.9, reference=base["tls"]),
                     "ransac": craft(base["ransac"], reference=base["tls"])}
        report = build_consensus(estimates, domain, q_all(0.9), consensus_config())
        self.assertEqual(report["status"], "DEGRADED")
        self.assertAlmostEqual(report["confidence"], 0.7, places=12)
        self.assertEqual(report["confidence_cap"], 0.7)
        validate_consensus_report(report, domain)
        self.assertEqual(report["report_id"],
                         "agl-consensus:" + digest({k: v for k, v in report.items()
                                                    if k != "report_id"}))
        json.dumps(report, allow_nan=False)
        self.assertEqual(report["consensus_config_id"],
                         consensus_config_id(resolve_consensus_config(consensus_config())))
        for override in ({"good_angle_deg": 2.0}, {"tls_svd_numeric_angle_deg": 0.6},
                         {"degraded_confidence_cap": 0.85},
                         {"min_degraded_confidence": 0.8},
                         {"degraded_updates_enabled": 1}, {"unknown": 1}):
            with self.assertRaises(ValueError):
                resolve_consensus_config(consensus_config(**override))
        if not P02_FIXTURE.exists():
            self.skipTest("P02 fixture unavailable")
        data = np.load(P02_FIXTURE, allow_pickle=True)
        points = np.ascontiguousarray(data["source"], dtype=np.float64)
        codes = np.ascontiguousarray(data["region_code"], dtype=np.int64)
        p02_domain = build_domain(points, codes=codes, ordinal=0, up=P02_UP,
                                  provenance="P02 frozen four-ROI fixture (A+C, exposed)")
        config = base_config()
        p02_estimates = {name: ESTIMATORS[name](p02_domain, config)
                         for name in ORDER}
        p02_quality = {name: quality_summary(evaluate_quality(
            p02_estimates[name], p02_domain, config,
            quality_config(required_region_codes=[1, 2, 3, 4],
                            min_supported_regions=4))) for name in ORDER}
        p02_report = build_consensus(p02_estimates, p02_domain, p02_quality,
                                     consensus_config())
        entry = [item for item in p02_report["pairwise"]
                 if {item["a"], item["b"]} == {"tls", "ransac"}][0]
        self.assertAlmostEqual(entry["angle_deg"], 0.74136, delta=0.01)
        self.assertEqual(entry["level"], "DEGRADED")
        self.assertNotEqual(p02_report["status"], "GOOD")


if __name__ == '__main__':
    unittest.main()
