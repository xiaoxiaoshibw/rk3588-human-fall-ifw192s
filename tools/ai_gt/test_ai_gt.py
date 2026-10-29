"""HFUS-AI-GT-TOOL-01 单元测试。

运行（仓库根目录）：python -B -W error tools/ai_gt/test_ai_gt.py
"""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_gt


class TestGeometry(unittest.TestCase):
    def setUp(self):
        self.cam = ai_gt.default_camera()

    def test_roundtrip_angle(self):
        rng = np.random.default_rng(7)
        pts = rng.uniform([1.0, -2.0, -1.0], [9.0, 2.0, 2.0], (64, 3))
        u, v, ok = ai_gt.project(pts, self.cam)
        self.assertTrue(ok.all())
        for i in range(len(pts)):
            d_ray = ai_gt.ray_dir(self.cam, u[i], v[i])
            d_true = pts[i] - np.asarray(self.cam["C"], float)
            d_true = d_true / np.linalg.norm(d_true)
            ang = math.degrees(math.atan2(float(np.linalg.norm(np.cross(d_ray, d_true))),
                                          float(np.dot(d_ray, d_true))))
            self.assertLess(ang, 1e-9)

    def test_optical_axis_to_center(self):
        p = np.asarray(self.cam["C"], float) + np.asarray(self.cam["f"], float) * 5.0
        u, v, _ = ai_gt.project(np.asarray([p]), self.cam)
        self.assertAlmostEqual(float(u[0]), self.cam["W"] / 2.0, places=6)
        self.assertAlmostEqual(float(v[0]), self.cam["H"] / 2.0, places=6)

    def test_nearest_point_and_rows(self):
        pts = np.asarray([[3.0, 0.5, 0.8], [5.0, -0.5, 1.0], [7.0, 0.0, 0.2]])
        rows = np.asarray([101, 202, 303])
        u, v, _ = ai_gt.project(np.asarray([pts[1]]), self.cam)
        i, dist = ai_gt.nearest_point(pts, self.cam, float(u[0]), float(v[0]))
        self.assertEqual(i, 1)
        self.assertLess(dist, 1e-9)
        self.assertEqual(int(rows[i]), 202)


class TestDeterminism(unittest.TestCase):
    def test_render_bytes_identical(self):
        cam = ai_gt.default_camera()
        case = ai_gt.make_case(np.random.default_rng(3), has_person=True)
        with tempfile.TemporaryDirectory() as d:
            p1, p2 = Path(d) / "a.png", Path(d) / "b.png"
            ai_gt.render(case["points"], cam, p1)
            ai_gt.render(case["points"], cam, p2)
            self.assertEqual(ai_gt.sha256_file(p1), ai_gt.sha256_file(p2))

    def test_suite_counts_and_seed(self):
        s1, s2 = ai_gt.build_suite(20261018), ai_gt.build_suite(20261018)
        self.assertEqual(len(s1), 12)
        self.assertEqual(sum(c["truth"] is not None for c in s1), 10)
        for a, b in zip(s1, s2):
            self.assertTrue(np.array_equal(a["points"], b["points"]))


class TestSelfcheckPipeline(unittest.TestCase):
    def _render(self, d):
        args = SimpleNamespace(out=d, seed=20261018,
                               _argv=["ai_gt", "selfcheck", "render", "--out", d, "--seed", "20261018"])
        self.assertEqual(ai_gt.cmd_selfcheck_render(args), 0)

    def _score(self, d, picks):
        args = SimpleNamespace(out=d, picks=picks, _argv=["ai_gt", "selfcheck", "score", "--out", d])
        self.assertEqual(ai_gt.cmd_selfcheck_score(args), 0)
        return json.loads((Path(d) / "SELFCHECK.json").read_text(encoding="utf-8"))

    def test_oracle_zero_error(self):
        with tempfile.TemporaryDirectory() as d:
            self._render(d)
            truth = json.loads((Path(d) / "truth" / "truth.json").read_text(encoding="utf-8"))
            picks = {"annotator": {"model_id": "oracle"},
                     "picks": [{"case": c["case"],
                                "u": c["truth_px"][0] if c["has_person"] else None,
                                "v": c["truth_px"][1] if c["has_person"] else None}
                               for c in truth["cases"]]}
            pf = Path(d) / "picks_oracle.json"
            pf.write_text(json.dumps(picks), encoding="utf-8")
            sc = self._score(d, str(pf))
            self.assertEqual((sc["tp"], sc["fn"], sc["fp"], sc["tn"]), (10, 0, 0, 2))
            self.assertLessEqual(sc["px_err"]["max"], 1e-9)
            self.assertLessEqual(sc["lateral_m"]["max"], 1e-9)

    def test_injected_noise_readback(self):
        with tempfile.TemporaryDirectory() as d:
            self._render(d)
            truth = json.loads((Path(d) / "truth" / "truth.json").read_text(encoding="utf-8"))
            picks = {"annotator": {"model_id": "noisy"},
                     "picks": [{"case": c["case"],
                                "u": (c["truth_px"][0] + 5.0) if c["has_person"] else None,
                                "v": c["truth_px"][1] if c["has_person"] else None}
                               for c in truth["cases"]]}
            pf = Path(d) / "picks_noisy.json"
            pf.write_text(json.dumps(picks), encoding="utf-8")
            sc = self._score(d, str(pf))
            self.assertAlmostEqual(sc["px_err"]["min"], 5.0, places=9)
            self.assertAlmostEqual(sc["px_err"]["max"], 5.0, places=9)
            self.assertEqual(sc["tp"], 10)
            env = json.loads((Path(d) / "ENVELOPE.json").read_text(encoding="utf-8"))
            self.assertTrue(env["small_sample"])
            self.assertEqual(env["render_spec"]["W"], 1280)


class TestLabelBlind(unittest.TestCase):
    def _args(self, d):
        return SimpleNamespace(points=str(Path(d) / "pts.npy"), rows=str(Path(d) / "rows.npy"),
                               picks=str(Path(d) / "picks.json"), meta=str(Path(d) / "meta.json"),
                               out=str(Path(d) / "labels.json"), camera=None,
                               model_id="test-model", model_version="v0", prompt_sha="p0",
                               render_sha="r0")

    def test_blind_guard_rejects_pipeline_fields(self):
        with tempfile.TemporaryDirectory() as d:
            np.save(Path(d) / "pts.npy", np.zeros((3, 3)))
            np.save(Path(d) / "rows.npy", np.arange(3))
            (Path(d) / "picks.json").write_text(json.dumps({"picks": [{"case": "c0", "u": 1.0, "v": 1.0}]}),
                                                encoding="utf-8")
            (Path(d) / "meta.json").write_text(json.dumps({"sid": "s", "meta_sha256": "m",
                                                           "points_sha256": "p", "candidates": []}),
                                               encoding="utf-8")
            with self.assertRaises(SystemExit):
                ai_gt.cmd_label(self._args(d))

    def test_label_schema_and_rows(self):
        cam = ai_gt.default_camera()
        with tempfile.TemporaryDirectory() as d:
            pts = np.asarray([[5.0, 0.0, 0.9], [6.0, 0.5, 0.4], [7.0, -0.5, 1.2]])
            np.save(Path(d) / "pts.npy", pts)
            np.save(Path(d) / "rows.npy", np.asarray([11, 22, 33]))
            u, v, _ = ai_gt.project(np.asarray([pts[0]]), cam)
            (Path(d) / "picks.json").write_text(json.dumps(
                {"picks": [{"case": "c0", "u": float(u[0]), "v": float(v[0])}]}), encoding="utf-8")
            (Path(d) / "meta.json").write_text(json.dumps(
                {"sid": "s", "meta_sha256": "m", "points_sha256": "p"}), encoding="utf-8")
            self.assertEqual(ai_gt.cmd_label(self._args(d)), 0)
            doc = json.loads((Path(d) / "labels.json").read_text(encoding="utf-8"))
            self.assertEqual(doc["schema"], "ai_gt_labels_v1")
            self.assertTrue(doc["blind"])
            self.assertEqual(doc["annotator"]["model_id"], "test-model")
            self.assertEqual(doc["render_sha256"], "r0")
            lbl = doc["labels"][0]
            self.assertEqual(lbl["source_row"], 11)
            self.assertAlmostEqual(lbl["xyz"][0], pts[0][0], places=6)


class TestCrosscheckAudit(unittest.TestCase):
    def test_crosscheck(self):
        with tempfile.TemporaryDirectory() as d:
            a = {"labels": [{"case": "c0", "u": 100.0, "v": 100.0},
                            {"case": "c1", "u": None},
                            {"case": "c2", "u": 50.0, "v": 60.0}]}
            b = {"labels": [{"case": "c0", "u": 105.0, "v": 100.0},
                            {"case": "c1", "u": None},
                            {"case": "c2", "u": 90.0, "v": 60.0}]}
            (Path(d) / "a.json").write_text(json.dumps(a), encoding="utf-8")
            (Path(d) / "b.json").write_text(json.dumps(b), encoding="utf-8")
            args = SimpleNamespace(a=str(Path(d) / "a.json"), b=str(Path(d) / "b.json"),
                                   out=str(Path(d) / "x.json"), tol_px=12.0)
            self.assertEqual(ai_gt.cmd_crosscheck(args), 0)
            rep = json.loads((Path(d) / "x.json").read_text(encoding="utf-8"))
            self.assertEqual((rep["n_keys"], rep["agree"], rep["disagree"]), (3, 2, 1))

    def test_audit_flags_and_clean(self):
        with tempfile.TemporaryDirectory() as d:
            dirty = {"blind": True, "annotator": {"model_id": "m"}, "render_sha256": "r",
                     "labels": [
                         {"case": "c0", "target_id": "t1", "u": 10.0, "v": 10.0, "xyz": [1, 1, 1.0]},
                         {"case": "c0", "target_id": "t1", "u": 11.0, "v": 11.0, "xyz": [1, 1, 1.0]},
                         {"case": "c1", "target_id": "t2", "u": 2000.0, "v": 300.0, "xyz": [1, 1, 1.0]},
                         {"case": "c2", "target_id": "t3", "u": 5.0, "v": 5.0, "xyz": [1, 1, 9.9]},
                         {"case": "c3", "target_id": "t4", "frame": 1, "u": 5.0, "v": 5.0, "xyz": [0, 0, 1.0]},
                         {"case": "c3", "target_id": "t4", "frame": 2, "u": 6.0, "v": 5.0, "xyz": [0, 0, 1.5]}]}
            clean = {"blind": True, "annotator": {"model_id": "m"}, "render_sha256": "r",
                     "labels": [{"case": "c0", "target_id": "t1", "u": 10.0, "v": 10.0, "xyz": [1, 1, 1.0]},
                                {"case": "c1", "target_id": "t2", "absent": True}]}
            (Path(d) / "dirty.json").write_text(json.dumps(dirty), encoding="utf-8")
            (Path(d) / "clean.json").write_text(json.dumps(clean), encoding="utf-8")
            args = SimpleNamespace(labels=str(Path(d) / "dirty.json"), out=str(Path(d) / "a1.json"),
                                   max_step_m=0.25)
            self.assertEqual(ai_gt.cmd_audit(args), 0)
            rep = json.loads((Path(d) / "a1.json").read_text(encoding="utf-8"))
            types = {f["type"] for f in rep["flags"]}
            self.assertTrue({"duplicate_target", "out_of_bounds", "z_placement", "jitter"} <= types)
            self.assertFalse(rep["pass"])
            args2 = SimpleNamespace(labels=str(Path(d) / "clean.json"), out=str(Path(d) / "a2.json"),
                                    max_step_m=0.25)
            self.assertEqual(ai_gt.cmd_audit(args2), 0)
            rep2 = json.loads((Path(d) / "a2.json").read_text(encoding="utf-8"))
            self.assertTrue(rep2["pass"])
            self.assertEqual(rep2["n_flags"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
