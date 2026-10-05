"""Explicit GL-I03 config variants; all fixtures here are synthetic."""
import json
from unittest import mock

from test_gli02_candidate import BaseCase, PACKAGE_DIR
from core.ground import resolve_constrained_settings
from evaluate_gli02_candidate import _load_constrained_settings, main
from sensor_health import load_config

FROZEN = PACKAGE_DIR / "config/geometry_constrained.yaml"
VARIANT = PACKAGE_DIR / "config/geometry_constrained_gli03_r1.yaml"


class CandidateConfigOverrideTest(BaseCase):
    def run_candidate(self, name, config=None, **draft_values):
        out = self.root / (name + ".json")
        args = self.candidate_args(out, self.draft_path(**draft_values))
        if config is not None:
            args += ["--constrained-config", str(config)]
        return main(args), out

    def test_only_two_variant_values_change(self):
        old = load_config(str(FROZEN))["ground_constrained"]
        new = load_config(str(VARIANT))["ground_constrained"]
        self.assertEqual(set(old), set(new))
        self.assertEqual({key for key in old if old[key] != new[key]},
                         {"spatial_cell_m", "max_points_per_cell"})
        self.assertEqual(new["spatial_cell_m"], 0.05)
        self.assertEqual(new["max_points_per_cell"], 8)
        self.assertEqual(_load_constrained_settings(None),
                         _load_constrained_settings(str(FROZEN)))

    def test_default_and_explicit_frozen_ground_are_identical(self):
        default_rc, default = self.run_candidate("default")
        frozen_rc, frozen = self.run_candidate("frozen", FROZEN)
        self.assertEqual((default_rc, frozen_rc), (0, 0))
        a = json.loads(default.read_text(encoding="utf-8"))
        b = json.loads(frozen.read_text(encoding="utf-8"))
        self.assertEqual(a["ground"], b["ground"])
        self.assertEqual(a["status"], b["status"])
        self.assertEqual(a["verification"], b["verification"])

    def test_variant_candidate_is_labeled_and_exclusive(self):
        rc, path = self.run_candidate("variant", VARIANT)
        self.assertEqual(rc, 0)
        artifact = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(artifact["ground"]["settings"],
                         _load_constrained_settings(str(VARIANT)))
        self.assertEqual(artifact["status"]["ground"], "candidate")
        self.assertEqual(artifact["ground"]["status"], "valid")
        self.assertEqual(artifact["input"]["source"], "synthetic_fixture")
        self.assertIs(artifact["input"]["synthetic"], True)
        self.assertIs(artifact["verification"]["ground_physical_verified"], False)
        self.assertIs(artifact["input"]["input_manifest"]["provenance"]["physical_verified"], False)
        self.assertNotIn("ground_derived", artifact)
        before = path.read_bytes()
        rc2, _ = self.run_candidate("variant", VARIANT)
        self.assertEqual(rc2, 2)
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_configs_refuse_without_candidate(self):
        cases = {
            "empty": "",
            "syntax": "ground_constrained: [",
            "top_list": "[1, 2]",
            "missing_section": "other: {}",
            "null_section": "ground_constrained: null",
            "list_section": "ground_constrained: [1]",
            "bool_section": "ground_constrained: true",
            "unknown": "ground_constrained: {unknown: 1}",
            "bool": "ground_constrained: {spatial_cell_m: true}",
            "nan": "ground_constrained: {spatial_cell_m: .nan}",
            "inf": "ground_constrained: {spatial_cell_m: .inf}",
            "negative": "ground_constrained: {spatial_cell_m: -0.1}",
            "float_integer": "ground_constrained: {max_points_per_cell: 8.0}",
            "floor": "ground_constrained: {min_inliers: 99}",
            "overflow": "ground_constrained: {spatial_cell_m: " + "9" * 400 + "}",
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                config = self.root / (name + ".yaml")
                config.write_text(text, encoding="utf-8")
                rc, out = self.run_candidate("refused_" + name, config)
                self.assertEqual(rc, 2)
                self.assertFalse(out.exists())
        for name, path in (("missing", self.root / "absent.yaml"),
                           ("empty_path", ""), ("directory", self.root)):
            with self.subTest(name=name):
                rc, out = self.run_candidate("refused_" + name, path)
                self.assertEqual(rc, 2)
                self.assertFalse(out.exists())
        bad_utf8 = self.root / "invalid_utf8.yaml"
        bad_utf8.write_bytes(b"\xff\xfe\xfd")
        rc, out = self.run_candidate("refused_utf8", bad_utf8)
        self.assertEqual(rc, 2)
        self.assertFalse(out.exists())

    def test_same_path_reload_and_defaults_are_isolated(self):
        config = self.root / "reload.yaml"
        config.write_bytes(VARIANT.read_bytes())
        rc, path = self.run_candidate("first", config)
        self.assertEqual(rc, 0)
        first = json.loads(path.read_text(encoding="utf-8"))["ground"]["settings"]
        self.assertEqual(first["spatial_cell_m"], 0.05)
        config.write_bytes(FROZEN.read_bytes())
        rc2, path2 = self.run_candidate("reloaded", config)
        self.assertEqual(rc2, 0)
        self.assertEqual(json.loads(path2.read_text(encoding="utf-8"))["ground"]["settings"],
                         resolve_constrained_settings(None))
        changed = _load_constrained_settings(str(VARIANT))
        changed["spatial_cell_m"] = 99
        self.assertEqual(_load_constrained_settings(str(VARIANT))["spatial_cell_m"], 0.05)
        self.assertEqual(_load_constrained_settings(None)["spatial_cell_m"], 0.2)

    def test_emit_draft_does_not_consume_config(self):
        out = self.root / "blank.json"
        unused = self.root / "unused.json"
        args = ["--prepared-npz", str(self.adapted), "--emit-draft",
                "--draft-out", str(out), "--output", str(unused),
                "--constrained-config", str(self.root / "absent.yaml")]
        with mock.patch("evaluate_gli02_candidate.load_config",
                        side_effect=AssertionError("config must not be read")):
            self.assertEqual(main(args), 0)
        draft = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(draft["status"], "pending_human_review")
        self.assertIsNone(draft["up_axis"])
        self.assertFalse(unused.exists())

    def test_optional_yaml_dependency_and_loader_error(self):
        with mock.patch.dict("sys.modules", {"yaml": None}):
            rc, _ = self.run_candidate("without_yaml_default")
            self.assertEqual(rc, 0)
            rc2, out = self.run_candidate("without_yaml_explicit", VARIANT)
            self.assertEqual(rc2, 2)
            self.assertFalse(out.exists())
        with mock.patch("evaluate_gli02_candidate.load_config",
                        side_effect=RuntimeError("PyYAML is required")):
            rc, out = self.run_candidate("loader_error", VARIANT)
            self.assertEqual(rc, 2)
            self.assertFalse(out.exists())

    def test_variant_keeps_prior_and_frame_gate(self):
        rc, out = self.run_candidate("no_prior", VARIANT, up_axis=None)
        self.assertEqual(rc, 2)
        self.assertFalse(out.exists())
        out2 = self.root / "wrong_frame.json"
        args = self.candidate_args(out2, self.draft_path()) + [
            "--constrained-config", str(VARIANT), "--frame", "other"]
        self.assertEqual(main(args), 2)
        self.assertFalse(out2.exists())
