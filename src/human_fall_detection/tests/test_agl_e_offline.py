"""GL-E（AGL-E-01..05）：transform GT/gauge/inverse、来源绑定与只读、资格分层、
physical 只读、逐帧报告与历史 FAIL 引用。"""
import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.adaptive_ground.transform import (PHYSICAL_HEIGHT_M, TRANSFORM_FIELDS,
                                            apply_display_transform,
                                            build_display_transform,
                                            build_frame_report, display_sample,
                                            invert_display_transform, run_offline,
                                            signed_residuals,
                                            validate_display_transform)
from core.calibration import validate_geometry_calibration, validate_known_transform
from test_agl_a_estimators import frame_key, ground_points


def decision(applied=True, state="STABLE", fresh=True, eligible=True, revision=1):
    return {"state": state, "applied": applied, "fresh": fresh,
            "eligible_for_geometry": eligible, "accept_revision": revision}


class AglEOfflineTest(unittest.TestCase):
    def test_gt_transform_gauge_inverse_invariance_AGL_E_01(self):
        for pitch, roll, offset in ((10.0, 0.0, 1.2), (26.623261, -1.394671, 1.3219),
                                    (45.0, -10.0, 0.8)):
            fk = frame_key(1)
            transform = build_display_transform(pitch, roll, offset, fk,
                                                "agl-domain:test", "agl-config:test")
            rotation = np.array(transform["rotation"])
            normal = rotation[2]
            self.assertLessEqual(float(np.linalg.norm(rotation @ normal - [0, 0, 1])), 1e-12)
            self.assertAlmostEqual(float(np.linalg.det(rotation)), 1.0, places=12)
            self.assertLessEqual(float(np.abs(rotation.T @ rotation - np.eye(3)).max()), 1e-12)
            self.assertEqual(float(rotation[0][1]), 0.0)
            self.assertEqual(transform["translation_m"][:2], [0.0, 0.0])
            self.assertEqual(transform["translation_m"][2], offset)
            self.assertFalse(transform["physical_verified"])
            points, _ = ground_points(pitch, roll, height_m=offset)
            mapped = apply_display_transform(points, transform)["points"]
            self.assertLessEqual(float(np.max(np.abs(mapped[:, 2]))), 1e-9)
            residuals = signed_residuals(points, transform)
            self.assertLessEqual(float(np.max(np.abs(residuals - mapped[:, 2]))), 1e-12)
            inverse = invert_display_transform(transform)
            self.assertLessEqual(float(np.max(np.abs(
                np.array(inverse["rotation"]) - rotation.T))), 1e-15)
            back = (mapped - np.array(transform["translation_m"])) @ rotation
            self.assertLessEqual(float(np.max(np.abs(back - points))), 1e-12)
        transform = build_display_transform(26.0, 0.0, 1.32, frame_key(1),
                                            "agl-domain:test", "agl-config:test")
        with self.assertRaises(ValueError):
            validate_known_transform(transform)
        with self.assertRaises(ValueError):
            validate_geometry_calibration(transform)

    def test_source_binding_invalid_rows_and_sampling_AGL_E_02(self):
        points, _ = ground_points(20.0, 0.0, height_m=1.32)
        points = points.copy()
        points[3] = np.nan
        points[7] = np.nan
        points[9] = 0.0
        points[10] = 0.0
        fk = frame_key(2)
        transform = build_display_transform(20.0, 0.0, 1.32, fk,
                                            "agl-domain:test", "agl-config:test")
        rows = np.arange(len(points), dtype=np.int64)
        snapshot = points.tobytes()
        result = run_offline(points, rows, fk, decision(), transform)
        self.assertEqual(points.tobytes(), snapshot)
        self.assertEqual(result["invalid_row_count"], 4)
        self.assertEqual(result["mode"], "accepted")
        self.assertEqual(result["valid_row_count"], len(points) - 4)
        self.assertEqual(result["source_rows"], rows.tolist())
        self.assertTrue(result["result_id"].startswith("agl-offline:"))
        self.assertTrue(result["mapped_sha256"].startswith("sha256:"))
        self.assertEqual(result["frame_key"], fk)
        mapped = result["mapped_points"]
        finite = np.all(np.isfinite(mapped), axis=1)
        self.assertLessEqual(float(np.max(np.abs(mapped[finite][:, 2]))), 1e-9)
        sample = display_sample(mapped, 50)
        self.assertLessEqual(len(sample), 50)
        self.assertEqual(display_sample(mapped, 50).tobytes(), sample.tobytes())
        repeat = run_offline(points, rows, fk, decision(), transform)
        self.assertEqual(repeat["mapped_points"].tobytes(), mapped.tobytes())
        self.assertEqual(repeat["mapped_sha256"], result["mapped_sha256"])

    def test_reference_fallback_hold_and_bad_model_AGL_E_03(self):
        fk = frame_key(3)
        points, _ = ground_points(10.0, 0.0)
        rows = np.arange(len(points), dtype=np.int64)
        none_result = run_offline(points, rows, fk,
                                  decision(applied=False, fresh=False, eligible=False,
                                           state="HOLD"), None)
        self.assertEqual(none_result["mode"], "reference_only")
        self.assertIsNone(none_result["transform"])
        self.assertIsNone(none_result["mapped_points"])
        self.assertFalse(none_result["fresh"])
        self.assertFalse(none_result["eligible_for_geometry"])
        hold_transform = build_display_transform(10.0, 0.0, 1.32, fk,
                                                 "agl-domain:test", "agl-config:test")
        held = run_offline(points, rows, fk,
                           decision(applied=False, fresh=False, eligible=False,
                                    state="HOLD"), hold_transform)
        self.assertEqual(held["mode"], "hold_numeric")
        self.assertIsNotNone(held["mapped_points"])
        self.assertFalse(held["eligible_for_geometry"])
        bad = build_display_transform(10.0, 0.0, 1.32, fk,
                                      "agl-domain:test", "agl-config:test")
        bad["kind"] = "geometry_calibration"
        snapshot = points.tobytes()
        with self.assertRaises(ValueError):
            run_offline(points, rows, fk, decision(), bad)
        self.assertEqual(points.tobytes(), snapshot)

    def test_physical_reference_readonly_AGL_E_04(self):
        fk = frame_key(4)
        transform = build_display_transform(26.0, 0.0, 1.3219, fk,
                                            "agl-domain:test", "agl-config:test")
        self.assertEqual(transform["physical_height_m"], 1.14)
        self.assertEqual(transform["measurement_reference"]["physical_height_m"],
                         PHYSICAL_HEIGHT_M)
        self.assertEqual(transform["observed_tz_m"], 1.3219)
        self.assertEqual(set(transform), set(TRANSFORM_FIELDS))
        for forbidden in ("d_over_nz", "refit_rms", "optimizer", "physical_extrinsics",
                          "rotation_optimized"):
            self.assertNotIn(forbidden, transform)
        mutated = copy.deepcopy(transform)
        mutated["physical_height_m"] = 1.2
        with self.assertRaises(ValueError):
            validate_display_transform(mutated)
        mutated = copy.deepcopy(transform)
        mutated["physical_verified"] = True
        with self.assertRaises(ValueError):
            validate_display_transform(mutated)
        other = build_display_transform(26.0, 0.0, 1.40, fk,
                                        "agl-domain:test", "agl-config:test")
        self.assertEqual(other["physical_height_m"], 1.14)
        self.assertEqual(other["observed_tz_m"], 1.40)

    def test_frame_report_and_historical_failures_AGL_E_05(self):
        rows = []
        for index, (accepted_pitch, rms, p95) in enumerate(
                ((26.00, 0.019, 0.038), (26.02, 0.019, 0.039), (26.01, 0.020, 0.040))):
            fk = frame_key(10 + index)
            rows.append({"frame_key": fk,
                         "raw": {"pitch_deg": accepted_pitch + 0.01, "roll_deg": 0.0,
                                 "offset_m": 1.32},
                         "filtered": {"pitch_deg": accepted_pitch + 0.002, "roll_deg": 0.0,
                                      "offset_m": 1.32},
                         "accepted": {"pitch_deg": accepted_pitch, "roll_deg": 0.0,
                                      "offset_m": 1.32},
                         "rms_m": rms, "p95_m": p95})
        historical = {"source": "P02 published (not recomputed)",
                      "regions": {"1": "FAIL", "2": "PASS", "3": "FAIL", "4": "FAIL"}}
        report = build_frame_report(rows, historical)
        self.assertEqual(len(report["per_frame"]), 3)
        expected_std = float(np.std([26.00, 26.02, 26.01]))
        self.assertAlmostEqual(report["pose_spread"]["pitch_std_deg"], expected_std,
                               places=12)
        self.assertEqual(report["per_frame"][0]["rms_m"], 0.019)
        self.assertEqual(report["per_frame"][0]["accepted_pitch_deg"], 26.00)
        self.assertEqual(report["historical_leave_one_out_failures"], historical)
        self.assertTrue(report["report_id"].startswith("agl-frame-report:"))
        json.dumps(report, allow_nan=False)
        historical["regions"]["1"] = "PASS"
        self.assertEqual(report["historical_leave_one_out_failures"]["regions"]["1"],
                         "FAIL")


if __name__ == '__main__':
    unittest.main()
