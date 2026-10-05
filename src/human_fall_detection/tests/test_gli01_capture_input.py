"""GL-I01 capture-input adaptation regressions (synthetic only).

These exercise ``core/capture_input.py``: the strict source export format,
same-snapshot meta/bin hashing, canonical per-frame content-based groups, the
three-way XYZ byte equality, group-first selection and the atomic exclusive
NPZ publish. Everything here is synthetic; the real capture is only touched
read-only by the evidence runner, never by these tests.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

import hashlib
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))

from core.capture_input import (CaptureInputError, check_declared_frame,
                                classify_npz, frame_group_id, frame_of_row,
                                gate_selection, load_adapted, prepare_npz,
                                read_source_meta, read_snapshot,
                                select_group_region, source_identity,
                                validate_frames)

ROW_DTYPE = np.dtype([
    ("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("intensity", "<f4"),
    ("ring", "<u2"), ("_pad1", "<u2"), ("timestamp", "<f4"), ("_pad2", "<f4"),
])


def make_frame(seq, count, offset, sec=100, nsec=0):
    return {"seq": seq, "stamp_sec": sec, "stamp_nanosec": nsec,
            "bag_time_sec": 1.0 + seq, "offset_points": offset,
            "count_points": count, "dropped_points": 0}


def write_export(directory, counts=(4, 3, 0, 2, 1), frame_id="innolidar"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    total = int(sum(counts))
    rows = np.zeros(total, dtype=ROW_DTYPE)
    for row in range(total):
        rows["x"][row] = float(row * 3)
        rows["y"][row] = float(row * 3 + 1)
        rows["z"][row] = float(row * 3 + 2)
    (directory / "points.bin").write_bytes(rows.tobytes())
    frames = []
    offset = 0
    for index, count in enumerate(counts):
        frames.append(make_frame(1979000 + index, count, offset,
                                 sec=100 + index, nsec=1000 + index))
        offset += count
    meta = {
        "format": "human_capture_session",
        "format_version": 1,
        "session_id": "cap_synthetic",
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


class TempCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="gli01-"))
        self.src = self.root / "cap"
        self.meta = write_export(self.src)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def prepared(self, name="adapted.npz"):
        out = self.root / name
        prepare_npz(str(self.src), "innolidar", "m", str(out))
        return str(out)


class PrepareAndReloadTest(TempCase):
    def test_prepare_then_reload_round_trip(self):
        meta = self.meta
        out = self.prepared()
        manifest, points = load_adapted(out)
        self.assertEqual(points.shape, (meta["total_points"], 3))
        self.assertEqual(points.dtype, np.dtype("<f4"))
        self.assertEqual(manifest["kind"], "capture_input_adaptation")
        self.assertEqual(len(manifest["frame_groups"]), 5)
        self.assertEqual(manifest["provenance"]["point_index_domain"],
                         "capture_export_row")
        self.assertFalse(manifest["provenance"]["physical_verified"])
        self.assertFalse(manifest["provenance"]["source_bag_hash_verified"])
        self.assertFalse(manifest["source"]["source_bag_hash_verified"])

    def test_deterministic_groups_are_content_based(self):
        manifest, _ = load_adapted(self.prepared())
        meta_raw, meta_sha = read_snapshot(str(self.src / "meta.json"), "meta")
        bin_raw, bin_sha = read_snapshot(str(self.src / "points.bin"), "bin")
        identity = source_identity(meta_sha, bin_sha)
        frames = validate_frames(self.meta)
        for ordinal, fr in enumerate(frames):
            gid = frame_group_id(identity, ordinal, fr)
            self.assertIn(gid, manifest["frame_groups"])
            rows = manifest["frame_groups"][gid]["rows"]
            self.assertEqual(rows, [fr["offset_points"],
                                    fr["offset_points"] + fr["count_points"]])

    def test_manifest_is_scalar_unicode(self):
        out = self.prepared()
        loaded = np.load(out, allow_pickle=False)
        try:
            raw = loaded["input_manifest"]
            self.assertEqual(raw.ndim, 0)
            self.assertEqual(raw.dtype.kind, "U")
        finally:
            loaded.close()

    def test_zero_returns_and_empty_frames_preserved(self):
        manifest, points = load_adapted(self.prepared())
        self.assertEqual(int(manifest["points"]["shape"][0]), 10)
        empty = [g for g in manifest["frame_groups"].values()
                 if g["rows"][0] == g["rows"][1]]
        self.assertEqual(len(empty), 1)


class SourceEqualityTest(TempCase):
    def test_tampered_points_bytes_rejected(self):
        out = self.prepared()
        with np.load(out, allow_pickle=False) as loaded:
            points = loaded["points"].copy()
            manifest = str(loaded["input_manifest"])
        points[0, 0] = 123.0
        with open(out, "wb") as handle:
            np.savez(handle, points=points, input_manifest=np.array(manifest))
        with self.assertRaises(CaptureInputError):
            load_adapted(out)

    def test_tampered_source_bin_rejected(self):
        out = self.prepared()
        with open(self.src / "points.bin", "ab") as handle:
            handle.write(b"\x00" * 28)
        with self.assertRaises(CaptureInputError):
            load_adapted(out)

    def test_tampered_manifest_frame_group_rejected(self):
        out = self.prepared()
        with np.load(out, allow_pickle=False) as loaded:
            points = loaded["points"]
            manifest = json.loads(str(loaded["input_manifest"]))
        first = next(iter(manifest["frame_groups"]))
        manifest["frame_groups"]["frame:" + "0" * 24] = \
            manifest["frame_groups"][first]
        with open(out, "wb") as handle:
            np.savez(handle, points=points,
                     input_manifest=np.array(json.dumps(manifest)))
        with self.assertRaises(CaptureInputError):
            load_adapted(out)

    def test_missing_source_rejected(self):
        out = self.prepared()
        shutil.rmtree(self.src)
        with self.assertRaises(CaptureInputError):
            load_adapted(out)


class ClassificationTest(TempCase):
    def test_legacy_npz_and_npy_are_legacy(self):
        legacy = self.root / "legacy.npz"
        with open(legacy, "wb") as handle:
            np.savez(handle, points=np.zeros((3, 3), dtype="<f4"))
        self.assertEqual(classify_npz(str(legacy)), "legacy")

    def test_adapted_marker_detected(self):
        self.assertEqual(classify_npz(self.prepared()), "adapted")

    def test_damaged_marker_never_falls_back(self):
        out = self.prepared()
        with open(out, "wb") as handle:
            np.savez(handle, points=np.zeros((1, 3), dtype="<f4"),
                     input_manifest=np.array("{not json"))
        self.assertEqual(classify_npz(out), "adapted")
        with self.assertRaises(CaptureInputError):
            load_adapted(out)


class SelectionTest(TempCase):
    def _loaded(self):
        return load_adapted(self.prepared())

    def test_group_first_bounds_stay_inside_members(self):
        manifest, points = self._loaded()
        gids = list(manifest["frame_groups"])
        rows = select_group_region(points, manifest, {
            "x_min_m": -1e9, "x_max_m": 1e9, "y_min_m": -1e9, "y_max_m": 1e9,
            "z_min_m": -1e9, "z_max_m": 1e9, "frame_group": gids[1]})
        start, end = manifest["frame_groups"][gids[1]]["rows"]
        self.assertTrue(np.all(rows >= start) and np.all(rows < end))

    def test_explicit_indices_outside_group_rejected(self):
        manifest, points = self._loaded()
        gid = next(iter(manifest["frame_groups"]))
        with self.assertRaises(CaptureInputError):
            select_group_region(points, manifest,
                                {"frame_group": gid, "indices": [8]})

    def test_unknown_group_rejected(self):
        manifest, points = self._loaded()
        with self.assertRaises(CaptureInputError):
            select_group_region(points, manifest,
                                {"frame_group": "g1", "indices": [0]})

    def test_gate_requires_three_validation_regions(self):
        manifest, points = self._loaded()
        gids = list(manifest["frame_groups"])
        fit = {"x_min_m": -1e9, "x_max_m": 1e9, "y_min_m": -1e9,
               "y_max_m": 1e9, "z_min_m": -1e9, "z_max_m": 1e9,
               "frame_group": gids[0]}
        regions = [{"region_id": "r1", "frame_group": gids[1]}]
        with self.assertRaises(CaptureInputError):
            gate_selection(points, manifest, fit, None, gids[0], regions)

    def test_gate_rejects_fit_validation_frame_overlap(self):
        manifest, points = self._loaded()
        gids = list(manifest["frame_groups"])
        full = lambda g: {"x_min_m": -1e9, "x_max_m": 1e9, "y_min_m": -1e9,
                          "y_max_m": 1e9, "z_min_m": -1e9, "z_max_m": 1e9,
                          "frame_group": g}
        regions = [dict(full(gids[1]), region_id="r1"),
                   dict(full(gids[2]), region_id="r2"),
                   dict(full(gids[4]), region_id="r3")]
        with self.assertRaises(CaptureInputError):
            gate_selection(points, manifest, full(gids[0]), None, gids[0], regions)
        with self.assertRaises(CaptureInputError):
            gate_selection(points, manifest, full(gids[0]), None, gids[1], regions)

    def test_gate_rejects_real_frame_overlap_with_valid_selectors(self):
        # Otherwise-valid explicit selectors whose two validation regions sit on
        # the same source frame: only the frame-set overlap check can catch this.
        manifest, points = self._loaded()
        gids = list(manifest["frame_groups"])
        full = lambda g: {"x_min_m": -1e9, "x_max_m": 1e9, "y_min_m": -1e9,
                          "y_max_m": 1e9, "z_min_m": -1e9, "z_max_m": 1e9,
                          "frame_group": g}
        regions = [
            dict(full(gids[1]), region_id="r1"),
            dict(full(gids[1]), region_id="r2"),
            dict(full(gids[4]), region_id="r3"),
        ]
        with self.assertRaises(CaptureInputError):
            gate_selection(points, manifest, full(gids[0]), None, gids[0], regions)

    def test_gate_rejects_region_group_mismatch(self):
        # A validation region targeting the fit group would share the fit frame.
        manifest, points = self._loaded()
        gids = list(manifest["frame_groups"])
        full = lambda g: {"x_min_m": -1e9, "x_max_m": 1e9, "y_min_m": -1e9,
                          "y_max_m": 1e9, "z_min_m": -1e9, "z_max_m": 1e9,
                          "frame_group": g}
        regions = [dict(full(gids[0]), region_id="r1"),
                   dict(full(gids[1]), region_id="r2"),
                   dict(full(gids[4]), region_id="r3")]
        with self.assertRaises(CaptureInputError):
            gate_selection(points, manifest, full(gids[0]), None, gids[0], regions)

    def test_gate_positive_three_disjoint_groups(self):
        manifest, points = self._loaded()
        gids = list(manifest["frame_groups"])
        full = lambda g: {"x_min_m": -1e9, "x_max_m": 1e9, "y_min_m": -1e9,
                          "y_max_m": 1e9, "z_min_m": -1e9, "z_max_m": 1e9,
                          "frame_group": g}
        regions = [dict(full(gids[1]), region_id="r1"),
                   dict(full(gids[3]), region_id="r2"),
                   dict(full(gids[4]), region_id="r3")]
        fit_rows, resolved = gate_selection(points, manifest, full(gids[0]),
                                            None, gids[0], regions)
        start, end = manifest["frame_groups"][gids[0]]["rows"]
        self.assertTrue(np.all(fit_rows >= start) and np.all(fit_rows < end))
        self.assertEqual(len(resolved), 3)

    def test_region_without_selector_rejected(self):
        manifest, points = self._loaded()
        gid = list(manifest["frame_groups"])[0]
        with self.assertRaises(CaptureInputError):
            select_group_region(points, manifest, {"frame_group": gid})

    def test_select_bounds_must_be_finite(self):
        manifest, points = self._loaded()
        gid = list(manifest["frame_groups"])[0]
        for bad in (float("inf"), float("nan")):
            with self.assertRaises(CaptureInputError):
                select_group_region(points, manifest, {
                    "x_min_m": bad, "x_max_m": 1e9, "y_min_m": -1e9,
                    "y_max_m": 1e9, "z_min_m": -1e9, "z_max_m": 1e9,
                    "frame_group": gid})

    def test_select_bounds_reject_bool(self):
        manifest, points = self._loaded()
        gid = list(manifest["frame_groups"])[0]
        with self.assertRaises(CaptureInputError):
            select_group_region(points, manifest, {
                "x_min_m": True, "x_max_m": 1e9, "y_min_m": -1e9,
                "y_max_m": 1e9, "z_min_m": -1e9, "z_max_m": 1e9,
                "frame_group": gid})

    def test_select_bounds_reject_string(self):
        manifest, points = self._loaded()
        gid = list(manifest["frame_groups"])[0]
        with self.assertRaises(CaptureInputError):
            select_group_region(points, manifest, {
                "x_min_m": "0", "x_max_m": 1e9, "y_min_m": -1e9,
                "y_max_m": 1e9, "z_min_m": -1e9, "z_max_m": 1e9,
                "frame_group": gid})

    def test_empty_group_does_not_skip_malformed_bound(self):
        manifest, points = self._loaded()
        gids = list(manifest["frame_groups"])
        empty = next(g for g in gids
                     if manifest["frame_groups"][g]["rows"][0]
                     == manifest["frame_groups"][g]["rows"][1])
        with self.assertRaises(CaptureInputError):
            select_group_region(points, manifest, {
                "x_min_m": float("inf"), "x_max_m": 1e9, "y_min_m": -1e9,
                "y_max_m": 1e9, "z_min_m": -1e9, "z_max_m": 1e9,
                "frame_group": empty})

    def test_empty_group_returns_empty_for_valid_bounds(self):
        manifest, points = self._loaded()
        gids = list(manifest["frame_groups"])
        empty = next(g for g in gids
                     if manifest["frame_groups"][g]["rows"][0]
                     == manifest["frame_groups"][g]["rows"][1])
        rows = select_group_region(points, manifest, {
            "x_min_m": -1e9, "x_max_m": 1e9, "y_min_m": -1e9, "y_max_m": 1e9,
            "z_min_m": -1e9, "z_max_m": 1e9, "frame_group": empty})
        self.assertEqual(len(rows), 0)

    def test_mixed_indices_and_bounds_rejected(self):
        manifest, points = self._loaded()
        gid = list(manifest["frame_groups"])[0]
        with self.assertRaises(CaptureInputError):
            select_group_region(points, manifest, {
                "indices": [0], "x_min_m": -1e9, "x_max_m": 1e9,
                "y_min_m": -1e9, "y_max_m": 1e9, "z_min_m": -1e9,
                "z_max_m": 1e9, "frame_group": gid})


class FrameOfRowGuardTest(TempCase):
    def test_negative_row_rejected_not_wrapped(self):
        manifest, _ = load_adapted(self.prepared())
        with self.assertRaises(CaptureInputError):
            frame_of_row(manifest, [-1])

    def test_out_of_range_row_rejected(self):
        manifest, _ = load_adapted(self.prepared())
        total = int(manifest["points"]["shape"][0])
        with self.assertRaises(CaptureInputError):
            frame_of_row(manifest, [total])

    def test_bool_row_rejected(self):
        manifest, _ = load_adapted(self.prepared())
        with self.assertRaises(CaptureInputError):
            frame_of_row(manifest, [True, 0])

    def test_float_row_rejected(self):
        manifest, _ = load_adapted(self.prepared())
        with self.assertRaises(CaptureInputError):
            frame_of_row(manifest, [0.0, 1.0])

    def test_order_and_duplicates_preserved(self):
        manifest, _ = load_adapted(self.prepared())
        total = int(manifest["points"]["shape"][0])
        rows = [total - 1, 0, 0, total - 1]
        mapped = frame_of_row(manifest, rows)
        self.assertEqual(len(mapped), 4)
        self.assertEqual(mapped[0], mapped[3])
        self.assertEqual(mapped[1], mapped[2])
        self.assertNotEqual(mapped[0], mapped[1])


class StrictTypeTest(TempCase):
    def test_bool_mixed_indices_rejected(self):
        manifest, points = self._loaded_pair()
        gid = next(iter(manifest["frame_groups"]))
        with self.assertRaises(CaptureInputError):
            select_group_region(points, manifest,
                                {"frame_group": gid, "indices": [True, 0, 1]})

    def _loaded_pair(self):
        return load_adapted(self.prepared())

    def test_bool_count_and_float_stamp_rejected(self):
        self.meta["frames"][0]["count_points"] = True
        (self.src / "meta.json").write_text(json.dumps(self.meta),
                                            encoding="utf-8")
        with self.assertRaises(CaptureInputError):
            prepare_npz(str(self.src), "innolidar", "m",
                        str(self.root / "x.npz"))

    def test_string_stamp_rejected(self):
        self.meta["frames"][0]["stamp_sec"] = "100"
        (self.src / "meta.json").write_text(json.dumps(self.meta),
                                            encoding="utf-8")
        with self.assertRaises(CaptureInputError):
            prepare_npz(str(self.src), "innolidar", "m",
                        str(self.root / "x.npz"))

    def test_bad_nanosec_rejected(self):
        self.meta["frames"][0]["stamp_nanosec"] = 1000000000
        (self.src / "meta.json").write_text(json.dumps(self.meta),
                                            encoding="utf-8")
        with self.assertRaises(CaptureInputError):
            prepare_npz(str(self.src), "innolidar", "m",
                        str(self.root / "x.npz"))


class DeclarationTest(TempCase):
    def _reject(self, mutate, **kwargs):
        mutate(self.meta)
        (self.src / "meta.json").write_text(json.dumps(self.meta),
                                            encoding="utf-8")
        args = {"frame": "innolidar", "units": "m"}
        args.update(kwargs)
        with self.assertRaises(CaptureInputError):
            prepare_npz(str(self.src), args["frame"], args["units"],
                        str(self.root / "x.npz"))

    def test_frame_mismatch_rejected(self):
        self._reject(lambda m: None, frame="other")

    def test_units_must_be_m(self):
        self._reject(lambda m: None, units="mm")

    def test_top_level_units_are_checked(self):
        self._reject(lambda m: m.update({"units": "mm"}))

    def test_sensor_units_are_checked(self):
        self._reject(lambda m: m["sensor"].update({"units": "cm"}))

    def test_wrong_format_version_rejected(self):
        self._reject(lambda m: m.update({"format_version": 2}))

    def test_dropped_frames_must_be_zero(self):
        self._reject(lambda m: m["extraction"].update({"dropped_frames": 1}))

    def test_dropped_frames_rejects_bool(self):
        self._reject(lambda m: m["extraction"].update({"dropped_frames": True}))

    def test_incomplete_offset_rejected(self):
        self._reject(lambda m: m["frames"][1].update({"offset_points": 99}))

    def test_total_points_mismatch_rejected(self):
        self._reject(lambda m: m.update({"total_points": 99}))

    def test_endian_layout_mismatch_rejected(self):
        self._reject(lambda m: m["point_layout"].update({"endian": "big"}))


class AtomicPublishTest(TempCase):
    def test_existing_target_refused(self):
        out = str(self.root / "taken.npz")
        with open(out, "wb") as handle:
            handle.write(b"keep")
        with self.assertRaises(CaptureInputError):
            prepare_npz(str(self.src), "innolidar", "m", out)
        with open(out, "rb") as handle:
            self.assertEqual(handle.read(), b"keep")

    def test_failure_leaves_no_temp_files(self):
        self.meta["frames"][0]["count_points"] = 999
        (self.src / "meta.json").write_text(json.dumps(self.meta),
                                            encoding="utf-8")
        with self.assertRaises(CaptureInputError):
            prepare_npz(str(self.src), "innolidar", "m",
                        str(self.root / "x.npz"))
        leftovers = [name for name in os.listdir(self.root)
                     if name.startswith(".gli01-")]
        self.assertEqual(leftovers, [])

    def test_output_path_is_npy_free_npz(self):
        out = self.prepared()
        with open(out, "rb") as handle:
            self.assertEqual(handle.read(2), b"PK")


class ContentDetectionTest(TempCase):
    def test_renamed_extension_still_detected(self):
        out = self.root / "renamed.dat"
        prepare_npz(str(self.src), "innolidar", "m", str(out))
        self.assertEqual(classify_npz(str(out)), "adapted")
        load_adapted(str(out))

    def test_pathlike_accepted(self):
        prepare_npz(str(self.src), "innolidar", "m", str(self.root / "p.npz"))
        self.assertEqual(classify_npz(self.root / "p.npz"), "adapted")

    def test_extra_archive_key_rejected(self):
        out = self.prepared()
        with np.load(out, allow_pickle=False) as loaded:
            points = loaded["points"]
            manifest = str(loaded["input_manifest"])
        with open(out, "wb") as handle:
            np.savez(handle, points=points, input_manifest=np.array(manifest),
                     extra=np.zeros(3))
        with self.assertRaises(CaptureInputError):
            load_adapted(out)

    def test_manifest_must_be_scalar_not_1d(self):
        out = self.prepared()
        with np.load(out, allow_pickle=False) as loaded:
            points = loaded["points"]
            manifest = str(loaded["input_manifest"])
        with open(out, "wb") as handle:
            np.savez(handle, points=points,
                     input_manifest=np.array([manifest]))
        with self.assertRaises(CaptureInputError):
            load_adapted(out)

    def test_nonfinite_source_refused_whole(self):
        with open(self.src / "points.bin", "r+b") as handle:
            handle.seek(0)
            handle.write(np.float32("nan").tobytes())
        with self.assertRaises(CaptureInputError):
            prepare_npz(str(self.src), "innolidar", "m",
                        str(self.root / "x.npz"))


class ManifestCanonicalTest(TempCase):
    def _rewrite(self, mutate):
        out = self.prepared()
        with np.load(out, allow_pickle=False) as loaded:
            points = loaded["points"]
            manifest = str(loaded["input_manifest"])
        data = json.loads(manifest)
        mutate(data)
        with open(out, "wb") as handle:
            np.savez(handle, points=points,
                     input_manifest=np.array(json.dumps(data)))
        return out

    def test_bool_for_int_flag_rejected(self):
        out = self._rewrite(lambda m: m["provenance"].__setitem__(
            "physical_verified", 0))
        with self.assertRaises(CaptureInputError):
            load_adapted(out)

    def test_contradictory_verification_flag_rejected(self):
        out = self._rewrite(lambda m: m.__setitem__("verify", {"ok": True}))
        with self.assertRaises(CaptureInputError):
            load_adapted(out)

    def test_float_schema_rejected(self):
        out = self._rewrite(lambda m: m.__setitem__("schema", 1.0))
        with self.assertRaises(CaptureInputError):
            load_adapted(out)

    def test_declared_units_tamper_rejected(self):
        out = self._rewrite(lambda m: m["declared"].__setitem__("units", "mm"))
        with self.assertRaises(CaptureInputError):
            load_adapted(out)

    def test_source_bag_verified_tamper_rejected(self):
        out = self._rewrite(lambda m: m["provenance"].__setitem__(
            "source_bag_hash_verified", True))
        with self.assertRaises(CaptureInputError):
            load_adapted(out)

    def test_frame_group_members_tamper_rejected(self):
        out = self._rewrite(lambda m: next(
            iter(m["frame_groups"].values())).__setitem__("rows", [0, 0]))
        with self.assertRaises(CaptureInputError):
            load_adapted(out)

    def test_self_rehash_tamper_still_rejected(self):
        # Tamper the source *and* rewrite a digest that matches it: the canonical
        # recompute must still disagree on the honest fields.
        out = self.prepared()
        with np.load(out, allow_pickle=False) as loaded:
            points = loaded["points"].copy()
            manifest = json.loads(str(loaded["input_manifest"]))
        points[0, 0] = 42.0
        manifest["points"]["sha256"] = hashlib.sha256(
            points.tobytes()).hexdigest()
        with open(out, "wb") as handle:
            np.savez(handle, points=points,
                     input_manifest=np.array(json.dumps(manifest)))
        with self.assertRaises(CaptureInputError):
            load_adapted(out)


class DeclaredFrameConsistencyTest(TempCase):
    def test_cli_frame_must_match_manifest(self):
        manifest, _ = load_adapted(self.prepared())
        check_declared_frame(manifest, "innolidar")
        with self.assertRaises(CaptureInputError):
            check_declared_frame(manifest, "other")

    def test_fit_region_group_must_agree_with_fitter_group(self):
        manifest, points = load_adapted(self.prepared())
        gids = list(manifest["frame_groups"])
        fit = {"x_min_m": -1e9, "x_max_m": 1e9, "y_min_m": -1e9,
               "y_max_m": 1e9, "z_min_m": -1e9, "z_max_m": 1e9,
               "frame_group": gids[0]}
        with self.assertRaises(CaptureInputError):
            gate_selection(points, manifest, fit, None, gids[1], [])


if __name__ == "__main__":
    unittest.main()
