"""GL-I02 candidate-evaluation regressions (synthetic only).

These exercise ``scripts/evaluate_gli02_candidate.py`` through its public CLI
``main``: a synthetic planar 7-frame adapted NPZ plus a human-reviewed selection
draft must yield a *candidate* geometry-calibration artifact
(``status.ground == "candidate"``, ``ground.status == "valid"``, physical flags
false, no ``ground_derived``). Every missing prior, legacy input, existing
target and exclusive draft is refused with a non-zero exit and no artifact. The
real capture is only touched read-only by the evidence runner, never here.
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PACKAGE_DIR / "scripts"
for _path in (str(PACKAGE_DIR), str(SCRIPTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from core.capture_input import load_adapted, prepare_npz
from evaluate_gli02_candidate import main as gli02_main

ROW_DTYPE = np.dtype([
    ("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("intensity", "<f4"),
    ("ring", "<u2"), ("_pad1", "<u2"), ("timestamp", "<f4"), ("_pad2", "<f4"),
])

BOUNDS = {"x_min_m": -1e9, "x_max_m": 1e9, "y_min_m": -1e9, "y_max_m": 1e9,
          "z_min_m": -1e9, "z_max_m": 1e9}


def make_frame(seq, count, offset, sec=100, nsec=0):
    return {"seq": seq, "stamp_sec": sec, "stamp_nanosec": nsec,
            "bag_time_sec": 1.0 + seq, "offset_points": offset,
            "count_points": count, "dropped_points": 0}


def write_planar_export(directory, counts=(400, 100, 100, 100, 10, 10, 10),
                        frame_id="innolidar"):
    """A 7-frame synthetic export whose points lie on one ground plane at z=-1."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    total = int(sum(counts))
    rows = np.zeros(total, dtype=ROW_DTYPE)
    rng = np.random.RandomState(7)
    offset = 0
    frames = []
    for index, count in enumerate(counts):
        rows["x"][offset:offset + count] = rng.uniform(-4.0, 4.0, count)
        rows["y"][offset:offset + count] = rng.uniform(-4.0, 4.0, count)
        rows["z"][offset:offset + count] = -1.0 + rng.uniform(-0.005, 0.005,
                                                              count)
        frames.append(make_frame(1979000 + index, count, offset,
                                 sec=100 + index, nsec=1000 + index))
        offset += count
    (directory / "points.bin").write_bytes(rows.tobytes())
    meta = {
        "format": "human_capture_session",
        "format_version": 1,
        "session_id": "cap_synthetic_gli02",
        "created_iso": "2026-10-03T00:00:00+08:00",
        "sensor": {"model": "IFW192S", "frame_id": frame_id},
        "time_domain": "device_stamp_s_unanchored",
        "point_layout": {
            "fields": ["x", "y", "z", "intensity", "ring", "timestamp"],
            "dtypes": ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
            "stride_bytes": 28, "endian": "little",
            "pad_offsets_bytes": [18, 24],
        },
        "point_file": "points.bin",
        "point_stride_bytes": 28,
        "total_points": total,
        "total_dropped_points": 0,
        "frames": frames,
        "extraction": {"tool": "bag2session/0.1.0",
                       "source_bag": "/x/y.bag",
                       "source_bag_sha256": "ab" * 32,
                       "point_step_bytes_src": 26, "dropped_frames": 0},
    }
    (directory / "meta.json").write_text(json.dumps(meta, indent=1),
                                         encoding="utf-8")
    return meta


def make_draft(gids, **overrides):
    draft = {
        "schema": 1,
        "kind": "gli02_capture_selection_draft",
        "status": "pending_human_review",
        "source_kind": "synthetic_fixture",
        "up_axis": [0.0, 0.0, 1.0],
        "sensor_height_interval_m": [0.5, 1.5],
        "fit_region": {"frame_group": gids[0], "bounds": dict(BOUNDS)},
        "validation_regions": [
            {"region_id": "v1", "frame_group": gids[1], "bounds": dict(BOUNDS)},
            {"region_id": "v2", "frame_group": gids[2], "bounds": dict(BOUNDS)},
            {"region_id": "v3", "frame_group": gids[3], "bounds": dict(BOUNDS)},
        ],
        "default_refusal": "no_auto_ground_selection",
    }
    draft.update(overrides)
    return draft


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="gli02-"))
        self.src = self.root / "cap"
        write_planar_export(self.src)
        self.adapted = self.root / "adapted.npz"
        prepare_npz(str(self.src), "innolidar", "m", str(self.adapted))
        manifest, _ = load_adapted(str(self.adapted))
        self.manifest = manifest
        self.gids = list(manifest["frame_groups"])

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def draft_path(self, **overrides):
        path = self.root / "draft.json"
        path.write_text(json.dumps(make_draft(self.gids, **overrides)),
                        encoding="utf-8")
        return str(path)

    def candidate_args(self, output, draft):
        return ["--prepared-npz", str(self.adapted), "--draft", draft,
                "--output", str(output), "--source-kind", "synthetic_fixture"]


class CandidateArtifactTest(BaseCase):
    def test_t1_synthetic_candidate_artifact(self):
        out = self.root / "candidate.json"
        rc = gli02_main(self.candidate_args(out, self.draft_path()))
        self.assertEqual(rc, 0)
        artifact = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(artifact["status"]["ground"], "candidate")
        self.assertEqual(artifact["ground"]["status"], "valid")
        self.assertIs(artifact["verification"]["ground_physical_verified"], False)
        self.assertNotIn("ground_derived", artifact)
        provenance = artifact["input"]["input_manifest"]["provenance"]
        self.assertIs(provenance["physical_verified"], False)
        self.assertIs(provenance["source_bag_hash_verified"], False)

    def test_t2_missing_prior_refused_without_artifact(self):
        out = self.root / "t2.json"
        rc = gli02_main(self.candidate_args(out, self.draft_path(up_axis=None)))
        self.assertEqual(rc, 2)
        self.assertFalse(out.exists())
        out2 = self.root / "t2b.json"
        rc2 = gli02_main(self.candidate_args(
            out2, self.draft_path(validation_regions=[])))
        self.assertEqual(rc2, 2)
        self.assertFalse(out2.exists())

    def test_t3_existing_artifact_refused(self):
        out = self.root / "t3.json"
        draft = self.draft_path()
        self.assertEqual(gli02_main(self.candidate_args(out, draft)), 0)
        before = out.read_bytes()
        self.assertEqual(gli02_main(self.candidate_args(out, draft)), 2)
        self.assertEqual(out.read_bytes(), before)

    def test_t4_source_kind_strictly_labeled(self):
        synthetic = self.root / "synthetic.json"
        self.assertEqual(
            gli02_main(self.candidate_args(synthetic, self.draft_path())), 0)
        artifact = json.loads(synthetic.read_text(encoding="utf-8"))
        self.assertEqual(artifact["input"]["source"], "synthetic_fixture")
        self.assertIs(artifact["input"]["synthetic"], True)

        real = self.root / "capture_export.json"
        args = ["--prepared-npz", str(self.adapted), "--draft",
                self.draft_path(), "--output", str(real),
                "--source-kind", "capture_export"]
        self.assertEqual(gli02_main(args), 0)
        export = json.loads(real.read_text(encoding="utf-8"))
        self.assertEqual(export["input"]["source"], "capture_export")
        self.assertIs(export["input"]["synthetic"], False)

    def test_t5_legacy_and_damaged_adapted_refused(self):
        draft = self.draft_path()
        legacy = self.root / "legacy.npz"
        with open(legacy, "wb") as handle:
            np.savez(handle, points=np.zeros((3, 3), dtype="<f4"))
        out = self.root / "t5.json"
        rc = gli02_main(["--prepared-npz", str(legacy), "--draft", draft,
                         "--output", str(out)])
        self.assertEqual(rc, 2)
        self.assertFalse(out.exists())

        with np.load(str(self.adapted), allow_pickle=False) as loaded:
            points = loaded["points"]
            manifest = str(loaded["input_manifest"])
        damaged = self.root / "damaged.npz"
        with open(damaged, "wb") as handle:
            np.savez(handle, points=points, input_manifest=np.array(manifest),
                     extra=np.zeros(3))
        out2 = self.root / "t5b.json"
        rc2 = gli02_main(["--prepared-npz", str(damaged), "--draft", draft,
                          "--output", str(out2)])
        self.assertEqual(rc2, 2)
        self.assertFalse(out2.exists())

    def test_t6_emit_draft_template_exclusive(self):
        out = self.root / "template.json"
        args = ["--prepared-npz", str(self.adapted), "--emit-draft",
                "--draft-out", str(out), "--output", str(self.root / "unused.json")]
        self.assertEqual(gli02_main(args), 0)
        draft = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(draft["status"], "pending_human_review")
        self.assertEqual(draft["default_refusal"], "no_auto_ground_selection")
        for key in ("up_axis", "sensor_height_interval_m", "fit_region",
                    "validation_regions"):
            self.assertIn(key, draft)
        self.assertIsNone(draft["up_axis"])
        self.assertEqual(gli02_main(args), 2)

    def test_t7_capture_dir_read_only(self):
        digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        meta_before = digest(self.src / "meta.json")
        bin_before = digest(self.src / "points.bin")
        listing_before = sorted(os.listdir(self.src))
        out = self.root / "t7.json"
        args = ["--capture-dir", str(self.src), "--frame", "innolidar",
                "--draft", self.draft_path(), "--output", str(out),
                "--source-kind", "synthetic_fixture"]
        self.assertEqual(gli02_main(args), 0)
        self.assertTrue(out.exists())
        self.assertEqual(digest(self.src / "meta.json"), meta_before)
        self.assertEqual(digest(self.src / "points.bin"), bin_before)
        self.assertEqual(sorted(os.listdir(self.src)), listing_before)

    def test_t8_wrapper_uses_public_api_only(self):
        source = (SCRIPTS_DIR / "evaluate_gli02_candidate.py").read_text(
            encoding="utf-8")
        for call in ("load_adapted(", "gate_selection(",
                     "fit_ground_plane_constrained(",
                     "validate_constrained_ground(", "build_input_info(",
                     "build_geometry_calibration(", "save_exclusive_json("):
            self.assertIn(call, source)
        for forbidden in ("region_indices", "select_group_region", "np.cross",
                          "fit_ground_plane("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
