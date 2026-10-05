"""GL-I04 independent hand fixtures and offline boundary checks."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

import numpy as np

from test_gli02_candidate import BaseCase, BOUNDS, make_draft, write_planar_export
from core.capture_input import load_adapted, prepare_npz, sha256_file
from core.calibration import validate_geometry_calibration
from core.ground_diagnostics import (observe_boxes, replay_frozen_search,
                                     residual_stats, rotation_conditions)
from diagnose_gli04_geometry import main, verify_draft
from evaluate_gli02_candidate import _blank_draft
from core import ground as g


class HandFixtures(unittest.TestCase):
    def test_actual_replay_early_returns_and_degeneracy(self):
        rng = np.random.RandomState(8)
        fit = np.column_stack([rng.uniform(-2, 2, (400, 2)), np.full(400, -1.)])
        hold = np.column_stack([rng.uniform(-2, 2, (90, 2)), np.full(90, -1.)])
        points = np.vstack([fit, hold, hold, hold])
        regions = [{"region_id": str(i), "frame_group": "h%d" % i,
                    "indices": list(range(400 + i * 90, 400 + (i + 1) * 90))} for i in range(3)]
        settings = g.resolve_constrained_settings({"spatial_cell_m": .05, "max_points_per_cell": 8})
        cases = [("positive", points, np.arange(400), [0, 0, 1], [.5, 1.5]),
                 ("insufficient", points, np.arange(50), [0, 0, 1], [.5, 1.5]),
                 ("angle", points, np.arange(400), [1, 0, 0], [.5, 1.5]),
                 ("height", points, np.arange(400), [0, 0, 1], [2, 3])]
        line = points.copy()
        line[:400, 0] = np.linspace(-2, 2, 400)
        line[:400, 1] = 0
        cases.append(("collinear", line, np.arange(400), [0, 0, 1], [.5, 1.5]))
        for label, cloud, rows, up, height in cases:
            up = np.asarray(up, dtype=float)
            actual = g.fit_ground_plane_constrained(cloud, settings, "fixture", up, height, rows, "fit", regions)
            replay = replay_frozen_search(cloud, rows, up, height, settings)
            for key in ("sampled_fit_count", "raw_candidates", "candidates"):
                self.assertEqual(actual[key], replay[key], label)
            if label == "positive":
                self.assertEqual(actual["status"], "valid")
                self.assertEqual(len(actual["validation_regions"]), 3)
            else:
                self.assertFalse(actual["validation_regions"])
            if label == "angle":
                self.assertGreater(replay["counters"].get("angle", 0), 0)
            if label == "height":
                self.assertGreater(replay["counters"].get("height", 0), 0)
            if label == "collinear":
                self.assertEqual(actual["reason"], g.REASON_DEGENERATE)

    def test_signed_stats_zero_nonfinite_empty(self):
        stats = residual_stats([[0, 0, -.1], [0, 0, 0], [0, 0, .1],
                                [float("nan"), 0, 0]], [0, 0, 1], 0)
        self.assertEqual((stats["count"], stats["finite_count"], stats["nonfinite_count"],
                          stats["zero_count"]), (4, 3, 1, 1))
        self.assertAlmostEqual(stats["rms_m"], np.sqrt(.02 / 3))
        self.assertAlmostEqual(stats["p95_m"], .1)
        self.assertEqual(stats["signed_median_m"], 0)
        self.assertEqual((stats["low_tail_count"], stats["high_tail_count"], stats["support_count"]), (1, 1, 1))
        self.assertIsNone(residual_stats(np.empty((0, 3)), [0, 0, 1], 1)["rms_m"])
        for points, normal, offset in [([[1, 2]], [0, 0, 1], 0), ([[0, 0, 0]], [0, 0, 2], 0),
                                       ([[0, 0, 0]], [0, 0, 1], float("nan"))]:
            with self.assertRaises(ValueError):
                residual_stats(points, normal, offset)

    def test_rotation_hand_inverse(self):
        result = rotation_conditions(90)
        np.testing.assert_allclose(result["R_times_source_z_in_world"], [1, 0, 0], atol=1e-15)
        np.testing.assert_allclose(result["world_up_expressed_in_source_R_transpose"], [-1, 0, 0], atol=1e-15)
        r = np.asarray(result["R_source_to_world"])
        np.testing.assert_allclose(r @ result["world_up_expressed_in_source_R_transpose"], [0, 0, 1], atol=1e-15)

    def test_frame_mapping_empty_and_fixed_bins_display(self):
        points = np.array([[0, 0, 0], [.25, .25, .1], [-.001, 0, -.1], [1, 1, 0.]])
        manifest = {"points": {"shape": [4, 3]}, "frame_groups": {
            "a": {"rows": [0, 3], "ordinal": 0, "seq": 10},
            "empty": {"rows": [3, 3], "ordinal": 1, "seq": 11},
            "b": {"rows": [3, 4], "ordinal": 2, "seq": 12}}}
        plane = {"normal": [0., 0., 1.], "offset_m": 0.}
        records, sidecar, _ = observe_boxes(points, manifest, [("FIT", BOUNDS)], plane, 1)
        all_records, _, _ = observe_boxes(points, manifest, [("FIT", BOUNDS)], plane, 99)
        self.assertEqual([record["stats"] for record in records], [record["stats"] for record in all_records])
        self.assertEqual(records[0]["display_rows"], [0])
        self.assertEqual(records[1]["stats"]["count"], 0)
        self.assertIsNone(records[1]["stats"]["rms_m"])
        self.assertEqual([(row["pooled_row"], row["frame_ordinal"], row["frame_row"], row["seq"]) for row in sidecar],
                         [(0, 0, 0, 10), (1, 0, 1, 10), (2, 0, 2, 10), (3, 2, 0, 12)])
        self.assertEqual([cell["cell"] for cell in records[0]["source_xyz_bins"]], [[-1, 0, -1], [0, 0, 0], [1, 1, 0]])
        for budget in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                observe_boxes(points, manifest, [("FIT", BOUNDS)], plane, budget)


class DiagnosticCLI(BaseCase):
    def approved(self):
        draft = _blank_draft(self.manifest, "synthetic_fixture")
        draft.update(make_draft(self.gids))
        draft["review"] = {"by": "fixture", "at_utc": "2026-10-03T00:00:00Z"}
        return draft

    def invoke(self, name, draft=None, extra=()):
        path = self.root / (name + ".draft.json")
        path.write_text(json.dumps(draft if draft is not None else self.approved()), encoding="utf-8")
        output = self.root / name
        rc = main(["--prepared-npz", str(self.adapted), "--draft", str(path),
                   "--output-dir", str(output), "--display-budget", "2"] + list(extra))
        return rc, output

    def test_positive_repeat_exclusive_not_calibration(self):
        frozen = sha256_file(str(self.adapted))
        rc, output = self.invoke("one")
        self.assertEqual(rc, 0)
        report = json.loads((output / "diagnostic.json").read_text(encoding="utf-8"))
        self.assertEqual(report["kind"], "gli04_geometry_diagnostic")
        self.assertIs(report["physical_verified"], False)
        self.assertEqual(len(report["box_frame_records"]), 4 * 7)
        self.assertTrue((output / "local_source.svg").exists())
        with self.assertRaises(ValueError):
            validate_geometry_calibration(report)
        rc2, second = self.invoke("two")
        self.assertEqual(rc2, 0)
        other = json.loads((second / "diagnostic.json").read_text(encoding="utf-8"))
        for key in ("experiments", "temporal", "box_frame_records"):
            self.assertEqual(report[key], other[key])
        report["settings"]["seed"] = 0
        self.assertNotEqual(report["settings"], other["settings"])
        old = (output / "diagnostic.json").read_bytes()
        self.assertEqual(self.invoke("one")[0], 2)
        self.assertEqual((output / "diagnostic.json").read_bytes(), old)
        self.assertEqual(sha256_file(str(self.adapted)), frozen)

    def test_rejected_drafts_no_output(self):
        mutations = [("schema", True), ("schema", 2), ("kind", "geometry_calibration"),
                     ("review", None), ("up_axis", [0, 0, 2]), ("sensor_height_interval_m", [2, 1])]
        for i, (key, value) in enumerate(mutations):
            draft = self.approved()
            draft[key] = value
            self.assertEqual(self.invoke("reject" + str(i), draft)[0], 2)
            self.assertFalse((self.root / ("reject" + str(i))).exists())
        for key in ("frame", "units", "meta_sha256", "bin_sha256", "manifest_points_sha256", "time_domain"):
            draft = self.approved()
            draft["source"][key] = "wrong"
            rc, output = self.invoke(key, draft)
            self.assertEqual(rc, 2)
            self.assertFalse(output.exists())
        for name in ("alias", "bounds", "indices", "duplicate"):
            draft = self.approved()
            if name == "alias":
                draft["validation_regions"][0]["frame_group"] = self.gids[0]
            elif name == "bounds":
                draft["fit_region"]["bounds"]["x_min_m"] = True
            elif name == "indices":
                draft["fit_region"]["indices"] = [0]
            else:
                draft["validation_regions"][0]["region_id"] = "FIT"
            rc, output = self.invoke(name, draft)
            self.assertEqual(rc, 2)
            self.assertFalse(output.exists())

    def test_config_legacy_tampered_source_and_compute_failure(self):
        bad = self.root / "bad.yaml"
        bad.write_text("ground_constrained: {seed: true}", encoding="utf-8")
        rc, output = self.invoke("config", extra=["--constrained-config", str(bad)])
        self.assertEqual(rc, 2)
        self.assertFalse(output.exists())

    def test_output_inside_capture_refused_and_frame_mismatch(self):
        draft_path = self.root / "approved.json"
        draft_path.write_text(json.dumps(self.approved()), encoding="utf-8")
        output = self.src / "forbidden"
        self.assertEqual(main(["--prepared-npz", str(self.adapted), "--draft", str(draft_path),
                               "--output-dir", str(output)]), 2)
        self.assertFalse(output.exists())
        rc, output = self.invoke("wrong_frame", extra=["--frame", "wrong"])
        self.assertEqual(rc, 2)
        self.assertFalse(output.exists())
        with mock.patch("diagnose_gli04_geometry.pca_plane", side_effect=ValueError("failed calculation")):
            rc, output = self.invoke("compute")
        self.assertEqual(rc, 2)
        self.assertFalse(output.exists())
        np.savez(str(self.root / "legacy.npz"), points=np.zeros((2, 3)))
        rc, output = self.invoke("legacy", extra=["--prepared-npz", str(self.root / "legacy.npz")])
        self.assertEqual(rc, 2)
        self.assertFalse(output.exists())
        source = self.src / "points.bin"
        source.write_bytes(source.read_bytes() + b"x")
        rc, output = self.invoke("tampered")
        self.assertEqual(rc, 2)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
