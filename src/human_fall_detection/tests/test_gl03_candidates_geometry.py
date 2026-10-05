"""GL-03 candidate geometry tests (G01-G05, G07): reference AABB, ground geometry,
entry/binding rejection, node coordinate labelling and lifecycle masking.

Software/synthetic only. The physical ground, installation axis, real identity and
full-frame replay stay BLOCKED; nothing here is a human-fall acceptance.
"""

import copy
import math
import sys
import unittest
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))
sys.path.insert(0, str(TEST_DIR))

from core.calibration import (apply_ground_derived, apply_transform,
                              build_geometry_calibration, build_ground_derived,
                              make_transform, make_unknown_transform)
from core.ground import MONITOR_OK
from core.lidar_candidates import build_snapshot, validate_snapshot
from core.node_runtime import FallNodeCore

from test_gl02_ground_frame import _standing_column, flat_ground, trusted_block

FROM_FRAME = "innolidar"
TO_FRAME = "map"


def rotation_z(degrees):
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def reference_transform(degrees=35.0, translation=(0.4, -0.3, 0.2)):
    return make_transform(rotation_z(degrees), list(translation),
                          FROM_FRAME, TO_FRAME, evidence="synthetic")


def tilted_ground(offset=1.4, normal=(0.0, 0.0, 1.0)):
    """A ground record with a non-axis normal, for axis-mixing ground tests."""
    normal = np.asarray(normal, dtype=np.float64)
    normal = normal / np.linalg.norm(normal)
    return {
        "kind": "ground_plane", "status": "valid", "valid": True, "reason": None,
        "frame": FROM_FRAME, "normal": [float(v) for v in normal],
        "offset_m": float(offset), "sensor_height_m": float(offset),
        "holdout_residual": {"count": 30, "rms_m": 0.01, "max_m": 0.03},
        "holdout_support": {"count": 30, "rms_m": 0.01, "max_m": 0.03,
                            "fraction": 0.8},
        "valid_region": {"x_min_m": -5.0, "x_max_m": 5.0, "y_min_m": -5.0,
                         "y_max_m": 5.0, "z_min_m": -3.0, "z_max_m": 3.0,
                         "range_min_m": 0.1, "range_max_m": 30.0,
                         "point_count": 100},
    }


def calibration_with(ground, block=None):
    return build_geometry_calibration(
        "cal1", "2026-10-02T00:00:00Z", FROM_FRAME, ground=ground,
        ground_derived=block)


def reference_calibration(transform, ground=None, block=None,
                          calibration_id="ref-cal"):
    return build_geometry_calibration(
        calibration_id, "2026-10-02T00:00:00Z", FROM_FRAME, ground=ground,
        ground_derived=block, reference_frame=TO_FRAME,
        transforms={"T_reference_lidar": transform})


def blob(center=(3.0, 0.5, -0.6), spread=(0.25, 0.25, 0.4), count=300, seed=5):
    rng = np.random.RandomState(seed)
    return rng.normal(center, spread, (count, 3))


def ground_plane(offset=1.5, count=4000, extent=8.0, seed=2):
    rng = np.random.RandomState(seed)
    xy = (rng.rand(count, 2) - 0.5) * extent
    return np.column_stack((xy, np.full(count, -offset)))


def target_frame(target=None, ground_offset=1.5):
    return np.vstack((ground_plane(ground_offset),
                      blob() if target is None else target))


def snapshot(points, **context):
    context.setdefault("session_id", "gl03")
    context.setdefault("time_epoch", 0)
    context.setdefault("snapshot_id", "snap-1")
    context.setdefault("seq", 7)
    context.setdefault("stamp_secs", 100)
    context.setdefault("stamp_nsecs", 0)
    context.setdefault("source_stamp_s", 100.0)
    return build_snapshot(points, context.pop("settings", None), **context)


class ReferenceGeometryTest(unittest.TestCase):
    """G01: reference AABB over all points; centre keeps source-centre semantics."""

    def test_reference_block_survives_nonzero_rotation_and_translation(self):
        # Regression: the old builder packed a 3-vector centre next to two
        # 3-vectors and np.minimum over a ragged/object array, which raised for
        # any legal non-identity transform.
        transform = reference_transform()
        points = blob()
        snap = snapshot(points, transform=transform)
        candidate = snap["candidates"][0]
        evidence = points[np.asarray(candidate["evidence_indices"])]
        mapped = apply_transform(evidence, transform)
        expected_min = mapped.min(axis=0)
        expected_max = mapped.max(axis=0)
        self.assertTrue(np.allclose(candidate["bbox_reference_min_m"],
                                    expected_min, atol=1e-9))
        self.assertTrue(np.allclose(candidate["bbox_reference_max_m"],
                                    expected_max, atol=1e-9))
        # The AABB covers every actual transformed point, not just two corners.
        inside = np.all(mapped >= expected_min - 1e-9) and \
            np.all(mapped <= expected_max + 1e-9)
        self.assertTrue(bool(inside))

    def test_reference_bbox_is_not_the_two_corner_shortcut(self):
        # The old builder only mapped the two source AABB corners. Over a rotated
        # cluster that shortcut under-covers: there exist actual mapped points
        # outside the corner box while the reported reference AABB contains all.
        transform = reference_transform(degrees=35.0)
        points = blob(center=(3.0, 0.5, -0.6), spread=(0.7, 0.7, 0.4), seed=31)
        snap = snapshot(points, transform=transform)
        candidate = snap["candidates"][0]
        evidence = points[np.asarray(candidate["evidence_indices"])]
        mapped = apply_transform(evidence, transform)
        corners = np.asarray([candidate["bbox_source_min_m"],
                              candidate["bbox_source_max_m"]], dtype=float)
        corner_box = apply_transform(corners, transform)
        corner_min, corner_max = corner_box.min(axis=0), corner_box.max(axis=0)
        # Some actual mapped point escapes the two-corner box ...
        escaped = np.any(mapped < corner_min - 1e-9, axis=1) \
            | np.any(mapped > corner_max + 1e-9, axis=1)
        self.assertTrue(bool(np.any(escaped)))
        # ... while the reported AABB still contains every mapped point.
        self.assertTrue(np.all(np.asarray(candidate["bbox_reference_min_m"])
                               <= mapped.min(axis=0) + 1e-9))
        self.assertTrue(np.all(np.asarray(candidate["bbox_reference_max_m"])
                               >= mapped.max(axis=0) - 1e-9))

    def test_center_reference_is_source_center_mapped_not_point_median(self):
        transform = reference_transform()
        points = blob(center=(3.0, 0.5, -0.6), spread=(0.7, 0.1, 0.4), seed=9)
        snap = snapshot(points, transform=transform)
        candidate = snap["candidates"][0]
        expected = apply_transform(
            np.asarray(candidate["center_source_m"], dtype=float)[None, :],
            transform)[0]
        self.assertTrue(np.allclose(candidate["center_reference_m"], expected,
                                    atol=1e-9))

    def test_unknown_transform_keeps_reference_fields_null(self):
        snap = snapshot(blob(), transform={"status": "unknown"})
        candidate = snap["candidates"][0]
        self.assertIsNone(candidate["center_reference_m"])
        self.assertIsNone(candidate["bbox_reference_min_m"])
        self.assertIsNone(candidate["bbox_reference_max_m"])

    def test_reference_binding_requires_actual_frame_and_known_label(self):
        # Regression (G03): an artifact-owned T alone must project, but a
        # producing frame/label that disagrees with the record, or a standalone
        # transform conflicting with the known artifact record, must never
        # publish reference coordinates.
        transform = reference_transform()
        record = reference_calibration(transform)
        snap = snapshot(blob(), calibration=record)
        candidate = snap["candidates"][0]
        mapped = apply_transform(
            blob()[np.asarray(candidate["evidence_indices"])], transform)
        self.assertTrue(np.allclose(candidate["bbox_reference_min_m"],
                                    mapped.min(axis=0), atol=1e-9))
        foreign = snapshot(blob(), calibration=record, frame_id="other_lidar")
        self.assertTrue(all(c["center_reference_m"] is None
                            for c in foreign["candidates"]))
        self.assertEqual(foreign["coordinate"]["transform_status"], "unknown")
        wrong_label = reference_calibration(
            make_transform(np.eye(3).tolist(), [0.1, 0.2, 0.3], FROM_FRAME,
                           "other_reference", evidence="synthetic"))
        labelled = snapshot(blob(), calibration=wrong_label)
        self.assertTrue(all(c["center_reference_m"] is None
                            for c in labelled["candidates"]))
        conflicted = snapshot(blob(), calibration=record,
                              transform=reference_transform(
                                  translation=(9.0, 9.0, 9.0)))
        self.assertTrue(all(c["center_reference_m"] is None
                            for c in conflicted["candidates"]))
        self.assertTrue(all(c["bbox_reference_min_m"] is None
                            for c in conflicted["candidates"]))


class ReferenceQualificationTest(unittest.TestCase):
    """R4 G03/G04/G05: strict reference qualification and fixed version binding.

    Reproduces the R3 independent findings: a malformed standalone or damaged
    parent used to project with bare R/t, a same-id reference change used to
    keep old eligibility, a node startup conflict was silently dropped, and a
    standalone binding stayed live to caller mutation.
    """

    def test_malformed_standalone_reference_never_projects(self):
        for key, value in (("from_frame", None), ("to_frame", None),
                           ("status", "broken"), ("units", "mm"),
                           ("evidence", None)):
            with self.subTest(key=key):
                transform = reference_transform()
                transform[key] = value
                snap = snapshot(blob(), transform=transform)
                self.assertTrue(all(c["center_reference_m"] is None
                                    for c in snap["candidates"]), key)
                self.assertEqual(snap["coordinate"]["transform_status"], "unknown")

    def test_damaged_full_artifact_cannot_supply_reference(self):
        for key, value in (("schema_version", 99), ("calibration_id", None)):
            with self.subTest(key=key):
                artifact = reference_calibration(reference_transform())
                artifact[key] = value
                snap = snapshot(blob(), calibration=artifact)
                self.assertTrue(all(c["center_reference_m"] is None
                                    for c in snap["candidates"]), key)
                self.assertEqual(snap["coordinate"]["transform_status"], "unknown")

    def test_legacy_minimal_summary_and_standalone_stay_supported(self):
        # A non-artifact legacy summary (no kind) keeps the old reference
        # support: only the record itself must now be fully qualified.
        transform = reference_transform()
        summary = {"calibration_id": "legacy", "frames": {"lidar": FROM_FRAME,
                                                          "reference": TO_FRAME},
                   "transforms": {"T_reference_lidar": transform}}
        candidate = snapshot(blob(), calibration=summary)["candidates"][0]
        mapped = apply_transform(
            blob()[np.asarray(candidate["evidence_indices"])], transform)
        self.assertTrue(np.allclose(candidate["bbox_reference_min_m"],
                                    mapped.min(axis=0), atol=1e-9))
        standalone = snapshot(blob(), transform=reference_transform())
        self.assertIsNotNone(standalone["candidates"][0]["center_reference_m"])

    def test_node_startup_conflict_is_refused(self):
        record = reference_calibration(reference_transform())
        with self.assertRaises(ValueError):
            FallNodeCore("s1", {}, expected_frame=FROM_FRAME,
                         calibration=record,
                         transform=reference_transform(translation=(9.0, -2.0, 0.7)))

    def test_node_startup_matching_explicit_reference_is_adopted(self):
        transform = reference_transform()
        core = FallNodeCore("s1", {}, expected_frame=FROM_FRAME,
                            calibration=reference_calibration(transform),
                            transform=copy.deepcopy(transform))
        result = core.process(blob(), 1.0, seq=1, stamp_secs=100,
                              stamp_nsecs=0, frame_id=FROM_FRAME, now=1.0)
        candidate = result["snapshot"]["candidates"][0]
        expected = apply_transform(
            np.asarray(candidate["center_source_m"], dtype=float)[None, :],
            transform)[0]
        self.assertTrue(np.allclose(candidate["center_reference_m"], expected,
                                    atol=1e-9))

    def test_same_id_changed_reference_reload_is_refused_without_side_effects(self):
        record = reference_calibration(reference_transform())
        core = FallNodeCore("s1", {}, expected_frame=FROM_FRAME,
                            calibration=record)
        core.process(blob(), 1.0, seq=1, stamp_secs=100, stamp_nsecs=0,
                     frame_id=FROM_FRAME, now=1.0)
        snapshot_before = core._latest_valid_snapshot
        bound_before = copy.deepcopy(core._reference_transform)
        with self.assertRaises(ValueError):
            core.apply_ground_context(calibration=reference_calibration(
                reference_transform(translation=(9.0, -2.0, 0.7))))
        self.assertIs(core._latest_valid_snapshot, snapshot_before)
        self.assertEqual(core._reference_transform, bound_before)
        self.assertEqual(core.calibration["calibration_id"],
                         record["calibration_id"])

    def test_same_id_same_reference_reload_keeps_eligibility(self):
        core = FallNodeCore("s1", {}, expected_frame=FROM_FRAME,
                            calibration=reference_calibration(
                                reference_transform()))
        core.process(blob(), 1.0, seq=1, stamp_secs=100, stamp_nsecs=0,
                     frame_id=FROM_FRAME, now=1.0)
        lifecycle = core.apply_ground_context(calibration=reference_calibration(
            reference_transform()))
        self.assertFalse(lifecycle["changed"])
        self.assertIsNotNone(core._latest_valid_snapshot)

    def test_standalone_caller_mutation_cannot_change_live_binding(self):
        transform = reference_transform()
        core = FallNodeCore("s1", {}, expected_frame=FROM_FRAME,
                            transform=transform)
        before = core.process(blob(), 1.0, seq=1, stamp_secs=100, stamp_nsecs=0,
                              frame_id=FROM_FRAME,
                              now=1.0)["snapshot"]["candidates"][0]
        transform["translation_m"][0] = 9.0
        after = core.process(blob(), 1.3, seq=2, stamp_secs=100,
                             stamp_nsecs=300000000, frame_id=FROM_FRAME,
                             now=1.3)["snapshot"]["candidates"][0]
        np.testing.assert_allclose(before["center_reference_m"],
                                   after["center_reference_m"], atol=1e-12)

    def test_wrong_kind_full_artifact_is_not_legacy_summary(self):
        # R5 (G03): a record that explicitly declares a non-artifact kind is a
        # damaged/foreign record, not an old no-kind minimal summary: its
        # internal R/t must not bypass the supported-parent validation.
        artifact = reference_calibration(reference_transform())
        artifact["kind"] = "unsupported_geometry_calibration"
        snap = snapshot(blob(), calibration=artifact)
        self.assertTrue(all(c["center_reference_m"] is None
                            for c in snap["candidates"]))
        self.assertEqual(snap["coordinate"]["transform_status"], "unknown")

    def test_parent_lidar_frame_must_match_reference_record(self):
        # R5 (G03): parent frames.lidar and the producing T.from are one
        # cross-record binding; legal internal R/t is not enough.
        artifact = reference_calibration(reference_transform())
        artifact["frames"]["lidar"] = "other_lidar"
        snap = snapshot(blob(), calibration=artifact)
        self.assertTrue(all(c["center_reference_m"] is None
                            for c in snap["candidates"]))
        self.assertEqual(snap["coordinate"]["transform_status"], "unknown")

    def test_standalone_same_id_reload_cannot_reread_mutated_caller(self):
        # R5 (G04/G05): the standalone input is frozen at the node boundary. A
        # caller edit after startup is not a reload authorization: a same-id
        # reload keeps the fixed binding (or refuses before side effects), and
        # the occluded prediction uses the same fixed inverse.
        transform = reference_transform()
        record = reference_calibration(
            make_unknown_transform(FROM_FRAME, TO_FRAME),
            calibration_id="standalone-ref")
        core = FallNodeCore("s1", {}, expected_frame=FROM_FRAME,
                            calibration=record, transform=transform)
        first = core.process(blob(), 1.0, seq=1, stamp_secs=100,
                             stamp_nsecs=0, frame_id=FROM_FRAME, now=1.0)
        request = {"schema_version": 1, "request_id": "r5-standalone-select",
                   "action": "select", "session_id": "s1",
                   "time_epoch": first["state"]["time_epoch"],
                   "snapshot_id": first["snapshot"]["snapshot_id"],
                   "candidate_id": first["snapshot"]["candidates"][0]["candidate_id"],
                   "selection_version": 0}
        self.assertTrue(core.handle_request(request, 1.01)["accepted"])
        core.process(blob(), 1.1, seq=2, stamp_secs=100,
                     stamp_nsecs=100000000, frame_id=FROM_FRAME, now=1.1)
        source_before = np.asarray(core._last_candidate["center_source_m"])
        bound_before = copy.deepcopy(core._reference_transform)
        transform["translation_m"][0] = 9.0
        try:
            result = core.apply_ground_context(calibration=copy.deepcopy(record))
        except ValueError:
            self.assertEqual(core._reference_transform, bound_before)
        else:
            self.assertFalse(result["changed"])
            self.assertEqual(core._reference_transform, bound_before)
        state = core.process(np.empty((0, 3)), 1.2, seq=3, stamp_secs=100,
                             stamp_nsecs=200000000, frame_id=FROM_FRAME,
                             now=1.2)["state"]
        self.assertIsNotNone(state.get("position_source_m"))
        np.testing.assert_allclose(state["position_source_m"], source_before,
                                   atol=1e-8)

    def test_new_id_known_to_unknown_fallback_uses_frozen_standalone(self):
        # R5 (G05): when the new artifact no longer owns a known T, the
        # fallback is the fixed startup standalone copy, never the caller's
        # later in-place edit.
        artifact_tf = reference_transform()
        caller_tf = copy.deepcopy(artifact_tf)
        core = FallNodeCore("s1", {}, expected_frame=FROM_FRAME,
                            calibration=reference_calibration(artifact_tf),
                            transform=caller_tf)
        new_record = reference_calibration(
            make_unknown_transform(FROM_FRAME, TO_FRAME),
            calibration_id="ref-cal-c")
        caller_tf["translation_m"][0] = 9.0
        lifecycle = core.apply_ground_context(calibration=new_record)
        self.assertTrue(lifecycle["changed"])
        snap = core.process(blob(), 1.2, seq=2, stamp_secs=100,
                            stamp_nsecs=200000000, frame_id=FROM_FRAME,
                            now=1.2)["snapshot"]
        self.assertEqual(snap["calibration"]["calibration_id"], "ref-cal-c")
        for candidate in snap["candidates"]:
            expected = apply_transform(
                np.asarray(candidate["center_source_m"], dtype=float)[None, :],
                artifact_tf)[0]
            np.testing.assert_allclose(candidate["center_reference_m"],
                                       expected, atol=1e-9)

    def test_same_id_rejection_leaves_pending_status_and_request_untouched(self):
        # R5 (G04/G05): a rejected same-id reload has no side effect on a
        # pending baseline, the cached measurement status or the request gate;
        # an ordinary release still works on the unchanged fixed binding.
        core = FallNodeCore("s1", {}, expected_frame=FROM_FRAME,
                            calibration=reference_calibration(
                                reference_transform()))
        first = core.process(blob(), 1.0, seq=1, stamp_secs=100,
                             stamp_nsecs=0, frame_id=FROM_FRAME, now=1.0)
        request = {"schema_version": 1, "request_id": "r5-pending-select",
                   "action": "select", "session_id": "s1",
                   "time_epoch": first["state"]["time_epoch"],
                   "snapshot_id": first["snapshot"]["snapshot_id"],
                   "candidate_id": first["snapshot"]["candidates"][0]["candidate_id"],
                   "selection_version": 0}
        self.assertTrue(core.handle_request(request, 1.01)["accepted"])
        core.baseline.start(core.tracker.track_id,
                            core.calibration["calibration_id"])
        self.assertEqual(core.baseline.status, "pending")
        tracker_before = core.tracker.snapshot()
        state_before = core.status_state(1.11)
        with self.assertRaises(ValueError):
            core.apply_ground_context(calibration=reference_calibration(
                reference_transform(translation=(9.0, -2.0, 0.7))))
        self.assertEqual(core.baseline.status, "pending")
        self.assertEqual(core.tracker.snapshot(), tracker_before)
        self.assertEqual(core.status_state(1.11), state_before)
        release = dict(request, request_id="r5-release", action="release",
                       selection_version=1)
        self.assertTrue(core.handle_request(release, 1.12)["accepted"])

    def test_full_artifact_missing_kind_cannot_hide_behind_legacy_path(self):
        # R6 (G03): a complete product (constructor-exclusive full-product
        # blocks present) whose kind is removed/nulled is damage, not a legacy
        # minimal summary; its unsupported schema can never ride the legacy
        # path, and even a supported version cannot be downgraded by deleting
        # the kind.
        for mode, version in (("removed", 99), ("null", 99),
                              ("removed", 1)):
            with self.subTest(mode=mode, version=version):
                artifact = reference_calibration(reference_transform())
                artifact["schema_version"] = version
                if mode == "removed":
                    artifact.pop("kind")
                else:
                    artifact["kind"] = None
                snap = snapshot(blob(), calibration=artifact)
                self.assertTrue(all(c["center_reference_m"] is None
                                    for c in snap["candidates"]))
                self.assertEqual(snap["coordinate"]["transform_status"],
                                 "unknown")

    def test_legacy_summary_schema_version_is_classified(self):
        # R6 (G03/G07): a true minimal summary (no full-product block, no
        # kind) keeps the legacy path when the version is absent or the
        # supported v1; an explicitly present unsupported/bool/float/null
        # version is refused instead of being mistaken for v1.
        transform = reference_transform()
        base = {"calibration_id": "legacy",
                "frames": {"lidar": FROM_FRAME, "reference": TO_FRAME},
                "transforms": {"T_reference_lidar": transform}}
        absent = snapshot(blob(), calibration=dict(base))
        self.assertIsNotNone(absent["candidates"][0]["center_reference_m"])
        supported = snapshot(blob(), calibration=dict(base, schema_version=1))
        self.assertIsNotNone(supported["candidates"][0]["center_reference_m"])
        for version in (99, True, 1.0, None):
            with self.subTest(version=version):
                summary = dict(base, schema_version=version)
                snap = snapshot(blob(), calibration=summary)
                self.assertTrue(all(c["center_reference_m"] is None
                                    for c in snap["candidates"]), version)
                self.assertEqual(snap["coordinate"]["transform_status"],
                                 "unknown")

    def test_full_parent_labels_must_be_frame_names(self):
        # R7 (G03): a full artifact's frames.lidar is a required non-empty
        # name and frames.reference is null or a non-empty name; truthiness,
        # containers and non-strings are not names and cannot skip the binding.
        for value in (42, True, ["innolidar"], ""):
            with self.subTest(label="lidar", value=value):
                artifact = reference_calibration(reference_transform())
                artifact["frames"]["lidar"] = value
                snap = snapshot(blob(), calibration=artifact)
                self.assertTrue(all(c["center_reference_m"] is None
                                    for c in snap["candidates"]), value)
                self.assertEqual(snap["coordinate"]["transform_status"],
                                 "unknown")
        for value in ([], {}, 42, True, ""):
            with self.subTest(label="reference", value=value):
                artifact = reference_calibration(reference_transform())
                artifact["frames"]["reference"] = value
                snap = snapshot(blob(), calibration=artifact)
                self.assertTrue(all(c["center_reference_m"] is None
                                    for c in snap["candidates"]), value)

    def test_full_parent_bad_containers_and_child_are_refused(self):
        # R7 (G03): a non-object transforms/rotations container or a non-object
        # canonical child of a full artifact is damage, never "absent".
        for container in ("transforms", "rotations"):
            with self.subTest(container=container):
                artifact = reference_calibration(reference_transform())
                artifact[container] = "damaged"
                snap = snapshot(blob(), calibration=artifact)
                self.assertTrue(all(c["center_reference_m"] is None
                                    for c in snap["candidates"]))
        artifact = reference_calibration(reference_transform())
        artifact["transforms"]["T_reference_lidar"] = "damaged"
        snap = snapshot(blob(), calibration=artifact)
        self.assertTrue(all(c["center_reference_m"] is None
                            for c in snap["candidates"]))

    def test_damaged_summary_containers_are_refused_without_raw_error(self):
        # R7 (G03): a true summary with a non-object frames/transforms container
        # is refused as unavailable instead of raising AttributeError.
        base = {"calibration_id": "legacy",
                "frames": {"lidar": FROM_FRAME, "reference": TO_FRAME},
                "transforms": {"T_reference_lidar": reference_transform()}}
        for key in ("frames", "transforms"):
            for value in ("damaged", 42, []):
                with self.subTest(key=key, value=value):
                    summary = dict(base)
                    summary[key] = value
                    snap = snapshot(blob(), calibration=summary)
                    self.assertTrue(all(c["center_reference_m"] is None
                                        for c in snap["candidates"]))

    def test_bad_canonical_child_cannot_enable_standalone_fallback(self):
        # R7 (G03): a declared but damaged canonical child is refused; it is
        # not "no record", so the legal standalone must not be adopted.
        summary = {"calibration_id": "legacy",
                   "frames": {"lidar": FROM_FRAME, "reference": TO_FRAME},
                   "transforms": {"T_reference_lidar": "damaged"}}
        snap = snapshot(blob(), calibration=summary,
                        transform=reference_transform())
        self.assertTrue(all(c["center_reference_m"] is None
                            for c in snap["candidates"]))
        self.assertEqual(snap["coordinate"]["transform_status"], "unknown")

    def test_undeclared_summary_fields_keep_legacy_compatibility(self):
        # R7 (G07): absent/None containers and labels stay undeclared, an
        # absent/None/legal-unknown canonical child keeps the standalone
        # fallback, and a valid summary keeps projecting.
        transform = reference_transform()
        cases = (
            {"calibration_id": "legacy"},
            {"calibration_id": "legacy", "frames": None, "transforms": None},
            {"calibration_id": "legacy", "frames": {},
             "transforms": {"T_reference_lidar": transform}},
            {"calibration_id": "legacy",
             "frames": {"lidar": None, "reference": None},
             "transforms": {"T_reference_lidar": transform}},
            {"calibration_id": "legacy",
             "frames": {"lidar": FROM_FRAME, "reference": TO_FRAME},
             "transforms": {"T_reference_lidar":
                            make_unknown_transform(FROM_FRAME, TO_FRAME)}},
        )
        for index, record in enumerate(cases):
            with self.subTest(case=index):
                snap = snapshot(blob(), calibration=record,
                                transform=reference_transform())
                self.assertIsNotNone(snap["candidates"][0]["center_reference_m"])


class GroundGeometryTest(unittest.TestCase):
    """G02: ground geometry from ACTUAL points under the validated R/t."""

    def setUp(self):
        self.ground = flat_ground()
        self.block = build_ground_derived(self.ground, [1.0, 0.0, 0.0])
        self.calibration = calibration_with(self.ground, self.block)

    def test_ground_box_is_per_axis_minmax_of_mapped_actual_points(self):
        points = blob(center=(3.0, 0.5, -0.6), spread=(0.4, 0.35, 0.5), seed=13)
        snap = snapshot(points, ground=self.ground,
                        calibration=self.calibration)
        candidate = snap["candidates"][0]
        evidence = points[np.asarray(candidate["evidence_indices"])]
        mapped = apply_ground_derived(evidence, self.block)
        self.assertEqual(candidate["bbox_ground_from"], "actual_points")
        self.assertTrue(np.allclose(candidate["bbox_ground_min_m"],
                                    mapped.min(axis=0), atol=1e-9))
        self.assertTrue(np.allclose(candidate["bbox_ground_max_m"],
                                    mapped.max(axis=0), atol=1e-9))
        self.assertTrue(np.allclose(candidate["center_ground_m"],
                                    np.median(mapped, axis=0), atol=1e-9))

    def test_ground_median_differs_from_rotated_source_median(self):
        # An asymmetric single cluster under a tilted ground whose basis mixes
        # axes: the source median maps to a point that is NOT the per-axis
        # median of the mapped points (the key GL-03 distinction).
        tilt, azimuth = 0.35, 0.6
        normal = np.array([math.sin(tilt) * math.cos(azimuth),
                           math.sin(tilt) * math.sin(azimuth), math.cos(tilt)])
        ground = tilted_ground(offset=1.4, normal=normal)
        block = build_ground_derived(ground, [1.0, 0.0, 0.0])
        calibration = calibration_with(ground, block)
        rng = np.random.RandomState(3)
        arm_x = np.column_stack([np.linspace(-0.5, 0.5, 200),
                                 np.zeros(200), np.full(200, -0.5)])
        arm_y = np.column_stack([np.zeros(120), np.linspace(-0.5, 0.9, 120),
                                 np.full(120, -0.5)])
        points = np.vstack((arm_x, arm_y)) + np.array([3.0, 0.3, 0.0]) \
            + rng.normal(0.0, 0.02, (320, 3))
        snap = snapshot(points, ground=ground, calibration=calibration,
                        settings={"cluster_cell_m": 0.5})
        self.assertEqual(len(snap["candidates"]), 1)
        candidate = snap["candidates"][0]
        evidence = points[np.asarray(candidate["evidence_indices"])]
        mapped_median = np.median(apply_ground_derived(evidence, block), axis=0)
        source_median_mapped = apply_ground_derived(
            np.asarray(candidate["center_source_m"], dtype=float)[None, :],
            block)[0]
        self.assertFalse(np.allclose(mapped_median, source_median_mapped,
                                     atol=1e-6))
        self.assertTrue(np.allclose(candidate["center_ground_m"], mapped_median,
                                    atol=1e-9))

    def test_no_valid_derived_yields_unavailable_and_no_id(self):
        snap = snapshot(blob(), ground=self.ground,
                        calibration=calibration_with(self.ground))
        candidate = snap["candidates"][0]
        self.assertEqual(candidate["bbox_ground_from"], "unavailable")
        self.assertIsNone(candidate["center_ground_m"])
        self.assertIsNone(candidate["bbox_ground_min_m"])
        self.assertIsNone(candidate["bbox_ground_max_m"])
        self.assertIsNone(snap["coordinate"]["ground_derived_id"])

    def test_source_center_bbox_and_indices_unchanged_by_ground_geometry(self):
        # Adding the derived ground artifact must not move the source geometry or
        # re-index the evidence; only the new ground fields appear.
        points = blob()
        no_derived = snapshot(points, ground=self.ground,
                              calibration=calibration_with(self.ground))
        with_derived = snapshot(points, ground=self.ground,
                                calibration=self.calibration)
        a = no_derived["candidates"][0]
        b = with_derived["candidates"][0]
        self.assertEqual(a["center_source_m"], b["center_source_m"])
        self.assertEqual(a["bbox_source_min_m"], b["bbox_source_min_m"])
        self.assertEqual(a["bbox_source_max_m"], b["bbox_source_max_m"])
        self.assertEqual(a["evidence_indices"], b["evidence_indices"])
        self.assertEqual(a["bbox_ground_from"], "unavailable")
        self.assertEqual(b["bbox_ground_from"], "actual_points")


class BindingAndEntryTest(unittest.TestCase):
    """G03/G07: strict derived binding; damaged records never fake success."""

    def setUp(self):
        self.ground = flat_ground()
        self.block = build_ground_derived(self.ground, [1.0, 0.0, 0.0])

    def _snapshot_with_block(self, block):
        return snapshot(blob(), ground=self.ground,
                        calibration=calibration_with(self.ground, block))

    def test_valid_derived_publishes_id_and_actual_points(self):
        snap = self._snapshot_with_block(self.block)
        self.assertEqual(snap["coordinate"]["ground_derived_id"],
                         self.block["ground_derived_id"])
        candidate = snap["candidates"][0]
        self.assertEqual(candidate["bbox_ground_from"], "actual_points")

    def _built_artifact(self, block):
        return calibration_with(self.ground, block)

    def test_damaged_derived_is_refused_not_silently_used(self):
        artifact = copy.deepcopy(self._built_artifact(self.block))
        artifact["ground_derived"]["R"][0][0] = 2.0
        snap = snapshot(blob(), ground=self.ground, calibration=artifact)
        self.assertIsNone(snap["coordinate"]["ground_derived_id"])
        self.assertEqual(snap["candidates"][0]["bbox_ground_from"], "unavailable")

    def test_bare_derived_without_parent_ground_is_refused(self):
        calibration = {"calibration_id": "c", "schema_version": 1,
                       "frames": {"lidar": FROM_FRAME, "reference": TO_FRAME},
                       "ground_derived": self.block}
        snap = snapshot(blob(), ground=self.ground, calibration=calibration)
        self.assertIsNone(snap["coordinate"]["ground_derived_id"])
        self.assertEqual(snap["candidates"][0]["bbox_ground_from"], "unavailable")

    def test_derived_frame_mismatch_is_refused(self):
        artifact = copy.deepcopy(self._built_artifact(self.block))
        artifact["ground_derived"]["from_frame"] = "other_frame"
        snap = snapshot(blob(), ground=self.ground, calibration=artifact)
        self.assertIsNone(snap["coordinate"]["ground_derived_id"])
        self.assertEqual(snap["candidates"][0]["bbox_ground_from"], "unavailable")

    def test_legacy_and_source_only_stay_working(self):
        # No calibration at all: old minimal behaviour, null new fields.
        snap = snapshot(blob())
        self.assertIsNone(snap["coordinate"]["ground_derived_id"])
        candidate = snap["candidates"][0]
        self.assertEqual(candidate["semantic"], "unknown")
        self.assertEqual(candidate["bbox_ground_from"], "unavailable")
        # Ground present but no derived artifact: no ground box, no ID.
        snap2 = snapshot(blob(), ground=self.ground,
                         calibration=calibration_with(self.ground))
        self.assertIsNone(snap2["coordinate"]["ground_derived_id"])

    def test_damaged_parent_artifact_never_enables_ground_geometry(self):
        # Regression (G03): a nested-only derived validation used to pass while
        # the parent identity/version or a verification flag was corrupt. The
        # whole artifact must be validated before any GDID/ground box is emitted.
        for change in ("schema_bool", "missing_id", "invalid_verification"):
            with self.subTest(change=change):
                artifact = copy.deepcopy(self._built_artifact(self.block))
                if change == "schema_bool":
                    artifact["schema_version"] = True
                elif change == "missing_id":
                    artifact["calibration_id"] = None
                else:
                    artifact["verification"]["extrinsics_verified"] = True
                snap = snapshot(blob(), ground=self.ground, calibration=artifact)
                self.assertIsNone(snap["coordinate"]["ground_derived_id"])
                self.assertEqual(snap["candidates"][0]["bbox_ground_from"],
                                 "unavailable")

    def test_snapshot_binds_actual_frame_and_supplied_ground(self):
        # Regression (G03): the derived block belongs to its producing frame and
        # parent plane; a snapshot from another frame, or an explicit ground that
        # differs from the artifact parent, must not inherit it.
        artifact = self._built_artifact(self.block)
        with self.subTest(case="actual source frame differs"):
            snap = snapshot(blob(), ground=self.ground, calibration=artifact,
                            frame_id="other_lidar")
            self.assertIsNone(snap["coordinate"]["ground_derived_id"])
            self.assertEqual(snap["candidates"][0]["bbox_ground_from"],
                             "unavailable")
        with self.subTest(case="explicit ground differs"):
            snap = snapshot(blob(), ground=flat_ground(offset=1.4),
                            calibration=artifact)
            self.assertIsNone(snap["coordinate"]["ground_derived_id"])
            self.assertEqual(snap["candidates"][0]["bbox_ground_from"],
                             "unavailable")

    def test_legacy_snapshot_without_optional_ground_extension_validates(self):
        # Regression (G07): the ground extension is additive. An old candidate
        # that predates it (none of the four keys) must stay valid; only a
        # present-but-inconsistent extension is refused.
        snap = snapshot(blob())
        for candidate in snap["candidates"]:
            for key in ("bbox_ground_from", "bbox_ground_min_m",
                        "bbox_ground_max_m", "center_ground_m"):
                candidate.pop(key, None)
        validate_snapshot(snap)

    def test_validate_snapshot_enforces_ground_contract(self):
        snap = self._snapshot_with_block(self.block)
        validate_snapshot(snap)
        broken = copy.deepcopy(snap)
        broken["candidates"][0]["bbox_ground_from"] = "unavailable"
        # unavailable must null the ground fields, not keep actual values.
        with self.assertRaises(ValueError):
            validate_snapshot(broken)
        broken2 = copy.deepcopy(snap)
        broken2["candidates"][0]["center_ground_m"] = None
        with self.assertRaises(ValueError):
            validate_snapshot(broken2)

    def test_evidence_indices_reconstruct_same_points_used_for_geometry(self):
        points = blob(seed=17)
        snap = snapshot(points, ground=self.ground,
                        calibration=calibration_with(self.ground, self.block))
        candidate = snap["candidates"][0]
        evidence = points[np.asarray(candidate["evidence_indices"])]
        mapped = apply_ground_derived(evidence, self.block)
        self.assertTrue(np.allclose(candidate["bbox_ground_min_m"],
                                    mapped.min(axis=0), atol=1e-9))
        self.assertEqual(len(evidence), candidate["point_count"])


class SourceFrameGuardTest(unittest.TestCase):
    """G03: a plane from another source frame cannot back this frame's chain.

    The outer ground-geometry gate (R1) only nulls the ground box. The legacy
    height chain, ``ground_relative_available``/``ground_valid`` flags and the
    node's observability/select chain must agree: a foreign frame is a
    measurement invalidation, not a green legacy path.
    """

    def test_foreign_frame_snapshot_cannot_use_foreign_plane_height(self):
        ground = flat_ground()
        for calibration in (None, calibration_with(ground, trusted_block())):
            with self.subTest(source_only=calibration is None):
                snap = snapshot(blob(), ground=ground, calibration=calibration,
                                frame_id="other_lidar")
                self.assertFalse(snap["quality"]["ground_valid"])
                self.assertFalse(snap["coordinate"]["ground_relative_available"])
                self.assertTrue(all(c["height_m"] is None
                                    for c in snap["candidates"]))
                self.assertIsNone(snap["coordinate"]["ground_derived_id"])

    def test_matching_frame_still_applies_plane(self):
        ground = flat_ground()
        snap = snapshot(blob(), ground=ground,
                        calibration=calibration_with(ground, trusted_block()),
                        frame_id=FROM_FRAME)
        self.assertTrue(snap["quality"]["ground_valid"])
        candidate = snap["candidates"][0]
        self.assertTrue(candidate["ground_relative_available"])
        self.assertIsNotNone(candidate["height_m"])


def gl02_scene(seed=13):
    """The GL-02 R5/R6 scene: dense trusted floor + a standing person column.

    The floor is a real plane inside the trusted synthetic ROI so the ground
    monitor can report ``ok``; the person is a separate cluster only because
    ``height_min_m`` drops the floor.
    """
    rng = np.random.RandomState(seed)
    floor = np.column_stack([rng.uniform(-1.0, 1.0, (4000, 2)),
                             np.full(4000, -1.2)])
    return np.vstack([floor, _standing_column(x=1.0, bottom=-1.2, top=0.6)])


def pick_target(snapshot, center=(1.0, 0.0, -0.3)):
    best, best_d = None, None
    for candidate in snapshot["candidates"]:
        point = np.asarray(candidate["center_source_m"], dtype=float)
        distance = float(np.linalg.norm(point - np.asarray(center)))
        if best is None or distance < best_d:
            best, best_d = candidate, distance
    return best


class NodeCoordinateTest(unittest.TestCase):
    """G04/G05: state coordinates equal candidate; no mislabelled prediction."""

    def _core(self, **kwargs):
        settings = {
            "candidates": {"min_cluster_points": 20, "preferred_cluster_points": 30,
                           "height_min_m": 0.1},
            "tracking": {"occlusion_timeout_s": 1.5, "lost_timeout_s": 3.0},
            "fall": {"mode_verified": False, "allow_confirmed": False},
        }
        return FallNodeCore("s1", settings, expected_frame=FROM_FRAME, **kwargs)

    def _trusted_core(self, **kwargs):
        ground = flat_ground()
        return self._core(ground=ground,
                          calibration=calibration_with(ground, trusted_block()),
                          **kwargs)

    def _frame(self, core, points, receive, seq=1):
        stamp_secs, stamp_nsecs = 100, int(3e8 * seq)
        return core.process(points, receive, seq=seq, stamp_secs=stamp_secs,
                            stamp_nsecs=stamp_nsecs, frame_id=FROM_FRAME,
                            now=receive)

    @staticmethod
    def _stamp(source_s):
        """Split an absolute source second into (secs, nsecs) with a real carry.

        Avoids the ``int(3e8*seq)`` overflow beyond 1e9 and keeps the source
        clock explicitly monotonic (0.3, 0.6, ...).
        """
        stamp_secs = int(math.floor(source_s))
        return stamp_secs, int(round((source_s - stamp_secs) * 1e9))

    def _process(self, core, points, receive, *, seq, frame_id, source_s):
        secs, nsecs = self._stamp(source_s)
        return core.process(points, receive, seq=seq, stamp_secs=secs,
                            stamp_nsecs=nsecs, frame_id=frame_id, now=receive)

    def _select(self, core, result):
        snapshot = result["snapshot"]
        request = {"schema_version": 1, "request_id": "r1", "action": "select",
                   "session_id": "s1", "time_epoch": result["state"]["time_epoch"],
                   "snapshot_id": snapshot["snapshot_id"],
                   "candidate_id": pick_target(snapshot)["candidate_id"],
                   "selection_version": 0}
        latest = core._last_state or result["state"]
        receive = (latest.get("time_received_s") or 1.0) + 0.01
        return core.handle_request(request, receive)

    def test_observed_state_ground_equals_candidate(self):
        core = self._trusted_core()
        first = self._frame(core, gl02_scene(), 1.0)
        self.assertEqual(first["state"]["observability"], "valid")
        self.assertEqual(core.ground_monitor_report["status"], MONITOR_OK)
        self.assertTrue(self._select(core, first)["accepted"])
        result = self._frame(core, gl02_scene(), 1.3, seq=2)
        state = result["state"]
        self.assertEqual(state["observability"], "valid")
        candidate = pick_target(result["snapshot"])
        self.assertEqual(state["position_source_m"], candidate["center_source_m"])
        self.assertEqual(state["center_ground_m"], candidate["center_ground_m"])
        self.assertEqual(state["bbox_ground_min_m"],
                         candidate["bbox_ground_min_m"])
        self.assertEqual(state["bbox_ground_max_m"],
                         candidate["bbox_ground_max_m"])
        self.assertEqual(state["bbox_ground_from"], "actual_points")
        self.assertEqual(state["ground_derived_id"],
                         result["snapshot"]["coordinate"]["ground_derived_id"])
        self.assertEqual(state["position_source_from"], "actual_points")

    def test_prediction_is_inverse_transformed_into_source(self):
        # Regression: the tracker predicts in the reference domain; the old state
        # wrote that reference value straight into position_source_m. A reference
        # prediction must be inverse-transformed back to source.
        transform = reference_transform()
        core = self._core(ground=flat_ground(), transform=transform)
        reference_point = [3.4, 0.2, -0.6]
        source = core._prediction_in_source(reference_point)
        self.assertIsNotNone(source)
        round_trip = apply_transform(np.asarray(source, dtype=float)[None, :],
                                     transform)[0]
        self.assertTrue(np.allclose(round_trip, reference_point, atol=1e-9))
        # The source value differs from the reference value (non-identity).
        self.assertFalse(np.allclose(source, reference_point, atol=1e-6))

    def test_prediction_without_transform_stays_source_coordinates(self):
        core = self._core(ground=flat_ground())
        point = [3.4, 0.2, -0.6]
        self.assertEqual(core._prediction_in_source(point), point)

    def test_selected_occlusion_never_mislabels_reference_as_source(self):
        core = self._trusted_core(transform=reference_transform())
        first = self._frame(core, gl02_scene(), 1.0)
        self.assertEqual(core.ground_monitor_report["status"], MONITOR_OK)
        self.assertTrue(self._select(core, first)["accepted"])
        # A valid ground-only frame (monitor stays ok) with no target cluster, so
        # the tracker must occlude/predict, never expose a raw reference value.
        result = self._frame(core, gl02_scene()[:4000], 1.3, seq=2)
        state = result["state"]
        self.assertNotEqual(state.get("position_source_from"), "reference")
        self.assertIn(state.get("position_source_from"),
                      ("predicted", "unavailable", "actual_points"))
        if state.get("position_predicted"):
            self.assertIn(state["position_source_from"], ("predicted",
                                                          "unavailable"))
            self.assertEqual(state["bbox_ground_from"], "unavailable")
            self.assertIsNone(state["center_ground_m"])

    def test_lost_status_masks_ground_geometry(self):
        core = self._trusted_core()
        first = self._frame(core, gl02_scene(), 1.0)
        self.assertEqual(core.ground_monitor_report["status"], MONITOR_OK)
        self.assertTrue(self._select(core, first)["accepted"])
        # Fresh ground-only frames with no target, source time advancing ~1 s per
        # frame past lost_timeout: the tracker must age occluded -> lost, and the
        # ground actual-point fields must clear rather than publish a stale box.
        state = None
        floor = gl02_scene()[:4000]
        for index, (receive, secs) in enumerate(
                zip((1.0, 2.0, 3.0, 4.5), (101, 102, 103, 104)), start=1):
            result = core.process(floor, receive, seq=index + 1,
                                  stamp_secs=secs, stamp_nsecs=0,
                                  frame_id=FROM_FRAME, now=receive)
            state = result["state"]
        self.assertIn(state["track_status"], ("lost", "occluded", "ambiguous"))
        if state["track_status"] in ("lost", "ambiguous"):
            self.assertIsNone(state["center_ground_m"])
            self.assertIsNone(state["bbox_ground_min_m"])
            self.assertIsNone(state["bbox_ground_max_m"])
            self.assertEqual(state["bbox_ground_from"], "unavailable")

    def test_predicted_reference_box_follows_prediction_or_is_null(self):
        # Regression (G04): the reference bbox used to stay at the last measured
        # location while the source box moved with the prediction. When the
        # reference frame is active the reference box must translate with the
        # tracker prediction; it must never report the old box at a new position.
        core = self._trusted_core(transform=reference_transform())
        first = self._frame(core, gl02_scene(), 1.0)
        self.assertEqual(core.ground_monitor_report["status"], MONITOR_OK)
        self.assertTrue(self._select(core, first)["accepted"])
        moved = gl02_scene()[:4000].copy()
        person = _standing_column(x=1.0, bottom=-1.2, top=0.6).copy()
        person[:, 0] += 0.1
        measured = self._frame(core, np.vstack((moved, person)), 1.3, seq=2)
        previous = pick_target(measured["snapshot"])
        predicted = self._frame(core, gl02_scene()[:4000], 1.5, seq=3)["state"]
        self.assertEqual(predicted["track_status"], "occluded")
        self.assertTrue(predicted["position_predicted"])
        self.assertEqual(predicted["bbox_ground_from"], "unavailable")
        if predicted.get("bbox_reference_min_m") is not None:
            delta = np.asarray(core.tracker.position_m) \
                - np.asarray(previous["center_reference_m"])
            np.testing.assert_allclose(
                predicted["bbox_reference_min_m"],
                np.asarray(previous["bbox_reference_min_m"]) + delta, atol=1e-9)

    def test_release_without_new_cloud_clears_old_target_geometry(self):
        # Regression (G05): handle_request changed the tracker binding but the
        # state cache kept the previous track/ground measurement. After release,
        # a freshness refresh must report no bound target and no ground box.
        core = self._trusted_core()
        first = self._frame(core, gl02_scene(), 1.0)
        self.assertTrue(self._select(core, first)["accepted"])
        self._frame(core, gl02_scene(), 1.3, seq=2)
        release = {"schema_version": 1, "request_id": "rel-1", "action": "release",
                   "session_id": "s1", "time_epoch": 0,
                   "selection_version": core.tracker.selection_version}
        self.assertTrue(core.handle_request(release, 1.41)["accepted"])
        state = core.status_state(1.42)
        self.assertIsNone(state["track_id"])
        self.assertIsNone(state["center_ground_m"])
        self.assertEqual(state["bbox_ground_from"], "unavailable")
        self.assertEqual(state["selection_version"],
                         core.tracker.selection_version)

    def test_new_selection_without_new_cloud_keeps_binding_without_geometry(self):
        # Regression (G05): a new select bumped tracker t0001->t0002 but the
        # cached state still said t0001 with the old ground box. The refresh must
        # show the current binding and no fabricated measurement.
        core = self._trusted_core()
        first = self._frame(core, gl02_scene(), 1.0)
        self.assertTrue(self._select(core, first)["accepted"])
        selected = self._frame(core, gl02_scene(), 1.3, seq=2)
        snap = selected["snapshot"]
        request = {"schema_version": 1, "request_id": "reselect-1",
                   "action": "select", "session_id": "s1", "time_epoch": 0,
                   "snapshot_id": snap["snapshot_id"],
                   "candidate_id": pick_target(snap)["candidate_id"],
                   "selection_version": core.tracker.selection_version}
        self.assertTrue(core.handle_request(request, 1.41)["accepted"])
        state = core.status_state(1.42)
        self.assertEqual(state["track_id"], core.tracker.track_id)
        self.assertEqual(state["selection_version"],
                         core.tracker.selection_version)
        self.assertIsNone(state["center_ground_m"])

    def test_invalid_frame_masks_ground_and_reference(self):
        ground = flat_ground()
        core = self._core(ground=ground)
        result = core.process(None, 1.0, seq=1, stamp_secs=100, stamp_nsecs=0,
                              frame_id=FROM_FRAME, now=1.0)
        state = result["state"]
        self.assertEqual(state["observability"], "invalid")
        self.assertIsNone(state["center_ground_m"])
        self.assertIsNone(state["bbox_ground_min_m"])
        self.assertIsNone(state["bbox_reference_min_m"])
        self.assertEqual(state["bbox_ground_from"], "unavailable")
        self.assertEqual(state["position_source_from"], "unavailable")

    def test_no_calibration_state_keeps_legacy_nulls(self):
        core = self._core(ground=None)
        result = self._frame(core, blob(), 1.0)
        state = result["state"]
        self.assertIsNone(state["ground_derived_id"])
        self.assertEqual(state["bbox_ground_from"], "unavailable")
        self.assertIsNone(state["center_ground_m"])

    def test_foreign_frame_invalidates_and_refuses_select(self):
        # G03: a plane from another source frame must invalidate the whole
        # ground-dependent chain (height/observability/select), not only null the
        # ground box. Source times are explicitly monotonic: 100.3, 100.6, 100.9.
        core = self._trusted_core()
        first = self._process(core, gl02_scene(), 1.0, seq=1,
                              frame_id=FROM_FRAME, source_s=100.3)
        self.assertNotEqual(core.cloud_timebase.streams["cloud"].stamp_status,
                            "invalid")
        self.assertTrue(self._select(core, first)["accepted"])
        priors = core._latest_valid_snapshot
        epoch = core.cloud_timebase.time_epoch
        stamp_first = core.cloud_timebase.streams["cloud"].source_stamp_s
        foreign = self._process(core, gl02_scene(), 1.3, seq=2,
                                frame_id="other_lidar", source_s=100.6)
        self.assertGreater(core.cloud_timebase.streams["cloud"].source_stamp_s,
                           stamp_first)
        self.assertEqual(foreign["state"]["observability"], "invalid")
        self.assertIsNone(foreign["state"]["position_source_m"])
        self.assertEqual(foreign["state"]["bbox_ground_from"], "unavailable")
        self.assertEqual(core.cloud_timebase.time_epoch, epoch)
        request = {"schema_version": 1, "request_id": "foreign-select",
                   "action": "select", "session_id": "s1", "time_epoch": epoch,
                   "snapshot_id": priors["snapshot_id"],
                   "candidate_id": pick_target(priors)["candidate_id"],
                   "selection_version": core.tracker.selection_version}
        self.assertFalse(core.handle_request(request, 1.31)["accepted"])
        self.assertEqual(core.status_state(1.32)["observability"], "invalid")
        # Recovery on a matching frame at the next monotonic source time.
        restored = self._process(core, gl02_scene(), 1.6, seq=3,
                                 frame_id=FROM_FRAME, source_s=100.9)
        self.assertEqual(restored["state"]["observability"], "valid")

    def test_no_ground_reference_masks_foreign_frame_and_recovers(self):
        # Regression (G03/G04/G05): the reference binding is guarded even with
        # no ground plane, and the shared gate covers process/request/status.
        transform = reference_transform()
        core = self._core(calibration=reference_calibration(transform),
                          transform=transform)
        first = self._process(core, gl02_scene(), 1.0, seq=1,
                              frame_id=FROM_FRAME, source_s=100.3)
        request = {"schema_version": 1, "request_id": "ref-select",
                   "action": "select", "session_id": "s1", "time_epoch": 0,
                   "snapshot_id": first["snapshot"]["snapshot_id"],
                   "candidate_id": pick_target(first["snapshot"])["candidate_id"],
                   "selection_version": 0}
        self.assertTrue(core.handle_request(request, 1.01)["accepted"])
        measured = self._process(core, gl02_scene(), 1.1, seq=2,
                                 frame_id=FROM_FRAME, source_s=100.6)
        self.assertIsNotNone(measured["state"]["position_reference_m"])
        foreign = self._process(core, gl02_scene(), 1.3, seq=3,
                                frame_id="other_lidar", source_s=100.9)
        self.assertEqual(foreign["state"]["observability"], "invalid")
        self.assertIsNone(foreign["state"]["position_reference_m"])
        fresh = dict(request, request_id="ref-foreign-select",
                     selection_version=1)
        self.assertFalse(core.handle_request(fresh, 1.31)["accepted"])
        self.assertEqual(core.status_state(1.32)["observability"], "invalid")
        restored = self._process(core, gl02_scene(), 1.6, seq=4,
                                 frame_id=FROM_FRAME, source_s=101.2)
        self.assertNotEqual(restored["state"]["observability"], "invalid")

    def test_full_reload_adopts_current_artifact_reference_transform(self):
        # Regression (G05): a full new calibration version must publish its id
        # with its own T_reference_lidar, not the previous matrix, and a later
        # caller mutation must not desynchronise the adopted context.
        old_transform = reference_transform()
        core = self._core(calibration=reference_calibration(old_transform),
                          transform=old_transform)
        self._process(core, gl02_scene(), 1.0, seq=1,
                      frame_id=FROM_FRAME, source_s=100.3)
        new_transform = reference_transform(degrees=-20.0,
                                            translation=(2.0, -1.0, 0.2))
        new_record = reference_calibration(new_transform,
                                           calibration_id="ref-cal-b")
        core.apply_ground_context(calibration=new_record)
        current = self._process(core, gl02_scene(), 1.3, seq=2,
                                frame_id=FROM_FRAME, source_s=100.6)
        self.assertEqual(current["snapshot"]["calibration"]["calibration_id"],
                         "ref-cal-b")
        for candidate in current["snapshot"]["candidates"]:
            expected = apply_transform(
                np.asarray(candidate["center_source_m"], dtype=float)[None, :],
                new_transform)[0]
            self.assertTrue(np.allclose(candidate["center_reference_m"],
                                        expected, atol=1e-9))
        new_record["transforms"]["T_reference_lidar"]["translation_m"][0] = 99.0
        after = self._process(core, gl02_scene(), 1.6, seq=3,
                              frame_id=FROM_FRAME, source_s=100.9)
        candidate = after["snapshot"]["candidates"][0]
        expected = apply_transform(
            np.asarray(candidate["center_source_m"], dtype=float)[None, :],
            new_transform)[0]
        self.assertTrue(np.allclose(candidate["center_reference_m"], expected,
                                    atol=1e-9))


if __name__ == "__main__":
    unittest.main()
