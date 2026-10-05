"""GL-02 ground-local transform, artifact lifecycle and trusted-region monitor.

Software/synthetic only: the PLAN mathematics, the additive artifact contract and
the invalidation/monitoring rules are exercised without any real ground truth.
The physical ground, installation axis and height remain BLOCKED.
"""

import copy
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))

from core.calibration import (GeometryCalibrationError, apply_ground_derived,
                              build_geometry_calibration, build_ground_derived,
                              ground_derived_basis, ground_derived_inverse,
                              ground_derived_status, validate_geometry_calibration,
                              validate_ground_derived)
from core.ground import (MONITOR_DEGRADED, MONITOR_OK, MONITOR_RECALIBRATION,
                         MONITOR_UNKNOWN, GroundMonitor, monitor_ground_residual)
from core.node_runtime import FallNodeCore


def tilted_normal(tilt_deg, azimuth_deg=0.0):
    tilt = math.radians(tilt_deg)
    azimuth = math.radians(azimuth_deg)
    axis = np.array([math.cos(azimuth), math.sin(azimuth), 0.0])
    return math.cos(tilt) * np.array([0.0, 0.0, 1.0]) + math.sin(tilt) * axis


def valid_ground(normal, offset, frame="innolidar", region=None):
    normal = np.asarray(normal, dtype=np.float64)
    normal = normal / np.linalg.norm(normal)
    if region is None:
        region = {"x_min_m": -3.0, "x_max_m": 3.0, "y_min_m": -3.0,
                  "y_max_m": 3.0, "z_min_m": -3.0, "z_max_m": 3.0,
                  "range_min_m": 0.1, "range_max_m": 30.0, "point_count": 100}
    return {
        "kind": "ground_plane", "status": "valid", "valid": True, "reason": None,
        "frame": frame, "normal": [float(v) for v in normal],
        "offset_m": float(offset), "sensor_height_m": float(offset),
        "holdout_residual": {"count": 30, "rms_m": 0.01, "max_m": 0.03},
        "holdout_support": {"count": 30, "rms_m": 0.01, "max_m": 0.03,
                            "fraction": 0.8},
        "valid_region": region,
    }


def flat_ground(offset=1.2, region=None):
    return valid_ground([0.0, 0.0, 1.0], offset, region=region)


class GroundLocalMathTest(unittest.TestCase):
    def test_multi_tilt_direction_height_math_and_inverse(self):
        rng = np.random.RandomState(7)
        for tilt in (0.0, 15.0, 30.0):
            for azimuth in (0.0, 45.0, 120.0):
                for height in (1.0, 1.2, 1.5):
                    with self.subTest(tilt=tilt, azimuth=azimuth, height=height):
                        normal = tilted_normal(tilt, azimuth)
                        ground = valid_ground(normal, height)
                        block = build_ground_derived(ground, [1.0, 0.0, 0.0])
                        validate_ground_derived(block,
                                                expected_from_frame="innolidar")
                        points = (rng.rand(64, 3) - 0.5) * 6.0
                        mapped = apply_ground_derived(points, block)
                        expected_z = points @ normal + height
                        self.assertTrue(np.allclose(mapped[:, 2], expected_z,
                                                    atol=1e-9))
                        # ground Z = 0, sensor origin Z = d, foot maps to origin
                        self.assertTrue(np.allclose(mapped[0, 2], points[0] @ normal
                                                    + height, atol=1e-9))
                        origin_local = apply_ground_derived(
                            np.zeros((1, 3)), block)[0]
                        self.assertTrue(np.allclose(origin_local,
                                                    [0.0, 0.0, height], atol=1e-9))
                        foot = -height * normal
                        self.assertTrue(np.allclose(
                            apply_ground_derived(foot[None, :], block)[0],
                            [0.0, 0.0, 0.0], atol=1e-9))
                        inverse = ground_derived_inverse(block)
                        recovered = mapped @ np.asarray(inverse["R"]).T \
                            + np.asarray(inverse["t"])
                        self.assertTrue(np.allclose(recovered, points, atol=1e-9))

    def test_reference_axis_near_the_normal_is_rejected(self):
        normal = tilted_normal(20.0, 30.0)
        ground = valid_ground(normal, 1.2)
        for axis in (normal, -normal, [0.0, 0.0, 0.0]):
            with self.subTest(axis=list(axis)):
                with self.assertRaises(GeometryCalibrationError):
                    build_ground_derived(ground, axis)

    def test_basis_requires_a_valid_ground(self):
        with self.assertRaises(GeometryCalibrationError):
            ground_derived_basis({"status": "invalid"}, [1.0, 0.0, 0.0])
        with self.assertRaises(GeometryCalibrationError):
            build_ground_derived({"status": "invalid", "frame": "innolidar"},
                                 [1.0, 0.0, 0.0])


class GroundDerivedValidationTest(unittest.TestCase):
    def setUp(self):
        self.ground = flat_ground()
        self.block = build_ground_derived(self.ground, [1.0, 0.0, 0.0])

    def rejected(self, mutate):
        damaged = copy.deepcopy(self.block)
        mutate(damaged)
        with self.assertRaises(GeometryCalibrationError):
            validate_ground_derived(damaged)

    def test_valid_block_and_id_round_trip(self):
        validate_ground_derived(self.block, expected_from_frame="innolidar")
        self.assertTrue(self.block["ground_derived_id"])

    def test_non_rigid_reflection_and_bad_wiring_are_rejected(self):
        self.rejected(lambda b: b["R"][0].__setitem__(0, 2.0))
        self.rejected(lambda b: b["n"].__setitem__(2, 0.5))
        self.rejected(lambda b: b.update(d=-1.0))
        self.rejected(lambda b: b["t"].__setitem__(2, 99.0))

    def test_damaged_id_and_unknown_version_and_bad_frames_units(self):
        self.rejected(lambda b: b.update(ground_derived_id="gd_deadbeef"))
        self.rejected(lambda b: b["valid_region_ground_local"]
                      .__setitem__("point_count", 999))
        self.rejected(lambda b: b.update(schema_version=2))
        self.rejected(lambda b: b.update(units="mm"))
        self.rejected(lambda b: b.update(to_frame="world_local"))
        self.rejected(lambda b: b.update(from_frame=""))

    def test_physical_and_identity_flags_cannot_be_pre_set(self):
        self.rejected(lambda b: b.update(physical_verified=True))
        self.rejected(lambda b: b["applicability"]
                      .__setitem__("single_plane_confirmed", True))
        self.rejected(lambda b: b["applicability"]
                      .__setitem__("single_plane_assumed", False))

    def test_status_separates_geometry_identity_and_physics(self):
        status = ground_derived_status(self.block)
        self.assertTrue(status["geometric_usable"])
        self.assertFalse(status["ground_identity_confirmed"])
        self.assertFalse(status["physical_height_verified"])
        self.assertFalse(ground_derived_status(None)["geometric_usable"])


class ArtifactCompatibilityTest(unittest.TestCase):
    def test_old_artifact_without_block_still_loads(self):
        old = build_geometry_calibration("cal-old", "2026-10-01T00:00:00Z",
                                         "innolidar", ground=flat_ground())
        self.assertNotIn("ground_derived", old)
        validate_geometry_calibration(old)

    def test_block_is_additive_and_never_sets_verification(self):
        ground = flat_ground()
        block = build_ground_derived(ground, [1.0, 0.0, 0.0])
        artifact = build_geometry_calibration(
            "cal-new", "2026-10-01T00:00:00Z", "innolidar", ground=ground,
            ground_derived=block)
        self.assertEqual(artifact["ground_derived"]["ground_derived_id"],
                         block["ground_derived_id"])
        self.assertFalse(artifact["verification"]["extrinsics_verified"])
        self.assertFalse(artifact["verification"]["imu_alignment_verified"])
        self.assertFalse(artifact["verification"]["ground_physical_verified"])
        self.assertNotIn("T_reference_lidar", artifact["transforms"])

    def test_unknown_nested_version_or_damage_is_rejected_on_load(self):
        ground = flat_ground()
        block = build_ground_derived(ground, [1.0, 0.0, 0.0])
        artifact = build_geometry_calibration(
            "cal", "2026-10-01T00:00:00Z", "innolidar", ground=ground,
            ground_derived=block)
        damaged = copy.deepcopy(artifact)
        damaged["ground_derived"]["schema_version"] = 2
        with self.assertRaises(GeometryCalibrationError):
            validate_geometry_calibration(damaged)
        missing = copy.deepcopy(artifact)
        missing["ground_derived"].pop("schema_version")
        with self.assertRaises(GeometryCalibrationError):
            validate_geometry_calibration(missing)


class GroundLifecycleTest(unittest.TestCase):
    def _core(self, block):
        ground = flat_ground()
        artifact = build_geometry_calibration(
            "cal-a", "2026-10-01T00:00:00Z", "innolidar", ground=ground,
            ground_derived=block)
        return FallNodeCore("s1", {"candidates": {"min_cluster_points": 20}},
                            ground=ground, calibration=artifact)

    def test_bare_ground_derived_without_parent_ground_is_rejected(self):
        # R3 test-contract: a bare derived block is never a complete context;
        # the corresponding incoming parent ground must be supplied (or a
        # full artifact from build_geometry_calibration). A bare block cannot
        # be silently applied and leave old ground/old ID mixed with the new
        # derived transform. The former R1 bare-block test was a stopgap while
        # the old parent would follow later; under R3 it is a refusal.
        ground = flat_ground()
        block = build_ground_derived(ground, [1.0, 0.0, 0.0])
        core = self._core(block)
        with self.assertRaises(ValueError):
            core.apply_ground_context(ground_derived=block)
        # Supplying a mismatched parent ground is equally refused (no mismatch
        # between the consumed ground and the bound derived block).
        with self.assertRaises(ValueError):
            core.apply_ground_context(ground=flat_ground(1.4),
                                      ground_derived=block)
        with self.assertRaises(ValueError):
            core.apply_ground_context(ground=flat_ground(1.4),
                                      ground_derived=trusted_block(1.2))
        # With the *matching* parent ground the bare-block update is a complete
        # context and clears the tracked position as before.
        core.tracker.select("t1", 0, position_m=[1.0, 0.0, 0.5],
                            calibration_version=core.calibration["calibration_id"],
                            receive_s=1.0, source_stamp_s=100.0)
        core.apply_ground_context(ground=flat_ground(1.4),
                                  ground_derived=trusted_block(1.4))
        self.assertIsNone(core.tracker.position_m)

    def test_calibration_switches_ground_and_derived_atomically(self):
        ground = flat_ground()
        block = build_ground_derived(ground, [1.0, 0.0, 0.0])
        core = self._core(block)
        self.assertAlmostEqual(core.ground["offset_m"], 1.2)
        new_ground = flat_ground(1.4)
        new_block = build_ground_derived(new_ground, [1.0, 0.0, 0.0],
                                         source={"kind": "synthetic"},
                                         created_at_utc="2026-10-01T00:00:00Z")
        new_artifact = build_geometry_calibration(
            "cal-b", "2026-10-01T00:00:00Z", "innolidar",
            ground=new_ground, ground_derived=new_block)
        record = core.apply_ground_context(calibration=new_artifact)
        self.assertTrue(record["changed"])
        self.assertAlmostEqual(core.ground["offset_m"], 1.4)
        self.assertAlmostEqual(core.ground_derived["d"], 1.4)
        self.assertEqual(core.ground_derived["ground_derived_id"],
                         new_block["ground_derived_id"])
        # The core is bound to the canonical validated records, never to the
        # caller's dict: later caller edits cannot desynchronise the live
        # ground/derived.
        new_artifact["ground"]["offset_m"] = 9.9
        self.assertAlmostEqual(core.ground["offset_m"], 1.4)
        new_artifact["ground_derived"]["d"] = 9.9
        self.assertAlmostEqual(core.ground_derived["d"], 1.4)

    def test_new_calibration_invalidates_baseline_and_snapshots(self):
        ground = flat_ground()
        first = build_ground_derived(ground, [1.0, 0.0, 0.0])
        core = self._core(first)
        result = core.process(np.array([[3.0, 0.0, -1.4], [3.0, 0.0, 0.1]]),
                              1.0, seq=1, stamp_secs=100, stamp_nsecs=0,
                              frame_id="innolidar", now=1.0)
        self.assertIsNotNone(core._latest_valid_snapshot)
        self.assertEqual(result["snapshot"]["calibration"]["ground_derived_id"],
                         first["ground_derived_id"])
        core.baseline.start("t1", core.calibration["calibration_id"])
        self.assertEqual(core.baseline.status, "pending")

        second = build_ground_derived(ground, [0.0, 1.0, 0.0])
        self.assertNotEqual(first["ground_derived_id"], second["ground_derived_id"])
        record = core.apply_ground_context(
            calibration={**core.calibration, "ground_derived": second})
        self.assertTrue(record["changed"])
        self.assertEqual(core.baseline.status, "idle")
        self.assertEqual(core.baseline.reason, "ground_derived_changed")
        self.assertIsNone(core._latest_valid_snapshot)
        self.assertEqual(core._ground_derived_id, second["ground_derived_id"])

    def test_same_id_is_not_a_change(self):
        ground = flat_ground()
        block = build_ground_derived(ground, [1.0, 0.0, 0.0])
        core = self._core(block)
        record = core.apply_ground_context(calibration=core.calibration)
        self.assertFalse(record["changed"])
        self.assertEqual(len(core.ground_lifecycle), 1)

    def test_paired_update_binds_one_canonical_calibration(self):
        # R4: every entry shape must publish the same canonical records; the
        # paired local update can no longer leave self.calibration behind.
        ground = flat_ground()
        block = build_ground_derived(ground, [1.0, 0.0, 0.0])
        core = self._core(block)
        new_ground, new_block = flat_ground(1.4), trusted_block(1.4)
        record = core.apply_ground_context(ground=new_ground,
                                           ground_derived=new_block)
        self.assertTrue(record["changed"])
        # snapshot/state/monitor GDID all read from the same canonical binding
        self.assertEqual(core.calibration["ground_derived"]["ground_derived_id"],
                         core._ground_derived_id)
        self.assertEqual(core.calibration["ground"]["offset_m"], 1.4)
        xy = np.random.RandomState(3).uniform(-1.0, 1.0, (200, 2))
        points = np.column_stack([xy, np.full(200, -1.4)])
        result = core.process(points, 1.0, seq=1, stamp_secs=100, stamp_nsecs=0)
        self.assertEqual(result["snapshot"]["calibration"]["ground_derived_id"],
                         core._ground_derived_id)
        self.assertEqual(result["snapshot"]["calibration"]["calibration_id"],
                         record["calibration_version"])
        # Caller-side edits cannot desynchronise the bound context.
        new_ground["offset_m"] = 99.0
        new_block["t"][2] = 99.0
        self.assertAlmostEqual(core.ground["offset_m"], 1.4)
        self.assertAlmostEqual(core.ground_derived["t"][2], 1.4)

    def test_new_version_same_gdid_invalidates_eligibility(self):
        # R4: a legal new artifact version with the same derived id still
        # retires the old target/baseline/request/snapshot eligibility.
        ground = flat_ground()
        block = trusted_block()
        core = self._core(block)
        core.tracker.select("t-old", 0, position_m=[1.0, 0.0, 0.2],
                            calibration_version="cal-a",
                            receive_s=1.0, source_stamp_s=100.0)
        new_artifact = build_geometry_calibration(
            "cal-b", "2026-10-01T00:00:00Z", "innolidar",
            ground=flat_ground(), ground_derived=trusted_block())
        self.assertEqual(new_artifact["ground_derived"]["ground_derived_id"],
                         core._ground_derived_id)
        record = core.apply_ground_context(calibration=new_artifact)
        self.assertTrue(record["changed"])
        self.assertIsNone(core.tracker.position_m)
        self.assertIsNone(core.tracker.track_id)
        self.assertEqual(core.baseline.status, "idle")

    def test_capture_baseline_refused_when_ground_monitor_unavailable(self):
        # R4: baseline capture is refused at request level (not accepted into
        # a forever-skipped pending state) when the ground monitor currently
        # cannot back ground-relative measurements.
        ground = flat_ground()
        core = self._core(trusted_block())
        person = _standing_column()
        core.process(person, 1.0, seq=1, stamp_secs=100, stamp_nsecs=0)
        snap = core._latest_valid_snapshot
        select = core.handle_request(
            {"schema_version": 1, "request_id": "sel-r4", "action": "select",
             "session_id": "s1", "time_epoch": 0,
             "snapshot_id": snap["snapshot_id"],
             "candidate_id": snap["candidates"][0]["candidate_id"],
             "selection_version": 0}, 1.01)
        self.assertTrue(select["accepted"])
        capture = core.handle_request(
            {"schema_version": 1, "request_id": "cap-r4",
             "action": "capture_baseline", "session_id": "s1", "time_epoch": 0,
             "selection_version": select["selection_version"]}, 1.02)
        self.assertFalse(capture["accepted"])
        self.assertEqual(capture["reason"], "ground_monitor_unavailable")
        self.assertNotEqual(core.baseline.status, "pending")

    def test_version_switch_settles_pending_capture_with_original_receipt(self):
        # A pending capture accepted under the old context must not be silently
        # erased by a legal version switch: the lifecycle return carries the
        # original request_id's failed terminal receipt, while the new version
        # still resets eligibility/caches.
        core = self._core(trusted_block())
        core.candidate_settings = {"min_cluster_points": 20, "height_min_m": 0.1}
        rng = np.random.RandomState(13)
        floor = np.column_stack([rng.uniform(-1.0, 1.0, (4000, 2)),
                                 np.full(4000, -1.2)])
        scene = np.vstack([floor, _standing_column(x=1.0, bottom=-1.2, top=0.6)])
        core.process(scene, 1.0, seq=1, stamp_secs=100, stamp_nsecs=0)
        snap = core._latest_valid_snapshot
        select = core.handle_request(
            {"schema_version": 1, "request_id": "sel-r7", "action": "select",
             "session_id": "s1", "time_epoch": 0,
             "snapshot_id": snap["snapshot_id"],
             "candidate_id": snap["candidates"][0]["candidate_id"],
             "selection_version": 0}, 1.01)
        self.assertTrue(select["accepted"], select)
        capture = core.handle_request(
            {"schema_version": 1, "request_id": "cap-r7",
             "action": "capture_baseline", "session_id": "s1", "time_epoch": 0,
             "selection_version": select["selection_version"]}, 1.02)
        self.assertTrue(capture["accepted"], capture)
        self.assertEqual(core.baseline.status, "pending")
        new = build_geometry_calibration(
            "cal-b", "2026-10-01T00:00:00Z", "innolidar",
            ground=flat_ground(), ground_derived=trusted_block())
        record = core.apply_ground_context(calibration=new)
        self.assertTrue(record["changed"])
        terminal = record.get("baseline_ack")
        self.assertIsNotNone(terminal)
        self.assertEqual(terminal["kind"], "selection_ack")
        self.assertEqual(terminal["request_id"], "cap-r7")
        self.assertEqual(terminal["track_id"], select["track_id"])
        self.assertFalse(terminal["accepted"])
        self.assertEqual(terminal["reason"], "ground_derived_changed")
        self.assertEqual(terminal["baseline"]["status"], "failed")
        # Not re-emitted on a later status refresh, and the old request binding
        # is cleared for the new version.
        self.assertIsNone(core.status_state(2.0).get("baseline_ack"))
        self.assertIsNone(core._baseline_request_id)


def _standing_column(x=1.0, bottom=-1.2, top=0.3, count=80):
    z = np.linspace(bottom, top, count)
    return np.column_stack([np.full(count, x), np.zeros(count), z])


# Fixture helper: a synthetic *trusted* ground ROI. A test that wants the
# monitor to report a real ok/supprt verdict must mark the region trusted and
# name its evidence source; the auto-derived AABB is intentionally NOT enough.
def trusted_block(height=1.2):
    region = {"available": True, "x_min_m": -2.0, "x_max_m": 2.0,
              "y_min_m": -2.0, "y_max_m": 2.0, "z_min_m": -0.05,
              "z_max_m": 0.05, "point_count": 400, "trusted": True,
              "evidence": "synthetic known floor", "source": "synthetic_fixture"}
    return build_ground_derived(flat_ground(height), [1.0, 0.0, 0.0],
                                valid_region_ground_local=region)


class GroundMonitorTest(unittest.TestCase):
    def setUp(self):
        self.block = trusted_block()
        self.inverse = ground_derived_inverse(self.block)
        self.rng = np.random.RandomState(11)

    def _source(self, local):
        return local @ np.asarray(self.inverse["R"]).T \
            + np.asarray(self.inverse["t"])

    def _local(self, count=200, z=0.0, noise=0.005):
        xy = self.rng.uniform(-1.5, 1.5, size=(count, 2))
        return np.column_stack([xy, z + self.rng.randn(count) * noise])

    def test_trusted_region_ok_and_support_insufficient(self):
        report = monitor_ground_residual(self._source(self._local()), self.block)
        self.assertEqual(report["status"], MONITOR_OK)
        self.assertGreater(report["support_fraction"], 0.8)
        sparse = self._source(self._local(count=5))
        report = monitor_ground_residual(sparse, self.block)
        self.assertIn(report["status"], (MONITOR_UNKNOWN, MONITOR_DEGRADED))

    def test_region_absent_is_unknown(self):
        block = copy.deepcopy(self.block)
        block["valid_region_ground_local"]["available"] = False
        report = monitor_ground_residual(self._source(self._local()), block)
        self.assertEqual(report["status"], MONITOR_UNKNOWN)
        self.assertEqual(report["reason"], "no_trusted_region")

    def test_sustained_whole_plane_shift_requires_recalibration(self):
        # The whole trusted plane moving +0.1 m kills the old plane's support
        # (old residual gate fails); a coherent single-direction shift on top
        # of a *failed* old fit is what the latch is for.
        monitor = GroundMonitor({"sustained_frames": 3, "history_frames": 5})
        shifted = self._source(self._local(z=0.1, count=400))
        report = None
        for _ in range(3):
            report = monitor.feed(shifted, self.block)
        self.assertTrue(report["sustained"])
        self.assertEqual(report["status"], MONITOR_RECALIBRATION)

    def test_one_sided_obstacle_is_not_treated_as_plane_shift(self):
        # 90% of the old ground still on the plane + 10% of it hidden by a
        # flat one-sided object: the old plane's support gate still passes, so
        # this can only be a local obstacle, never whole-shift evidence.
        monitor = GroundMonitor({"sustained_frames": 3, "history_frames": 5})
        local = self._local(count=400)
        local[:40, 2] = 0.3
        shifted = self._source(local)
        report = None
        for _ in range(10):
            report = monitor.feed(shifted, self.block)
        self.assertNotEqual(report["status"], MONITOR_RECALIBRATION)
        self.assertFalse(report["sustained"])
        self.assertEqual(report["reason"], "local_obstacle_suspected")

    def test_transient_change_is_not_recalibration(self):
        monitor = GroundMonitor({"sustained_frames": 3, "history_frames": 5})
        report = monitor.feed(self._source(self._local(z=0.1)), self.block)
        self.assertEqual(report["status"], MONITOR_DEGRADED)
        self.assertFalse(report["sustained"])

    def test_coherent_ground_shift_requires_recalibration(self):
        monitor = GroundMonitor()
        for _ in range(10):
            report = monitor.feed(self._source(self._local(z=-0.1)), self.block)
        self.assertEqual(report["status"], MONITOR_RECALIBRATION)

    def test_two_sided_scatter_is_not_shift_evidence(self):
        # 50% up / 50% down around the old plane: a bidirectional scatter has
        # no dominant direction to call "the plane moved by ..."; it must not
        # count as recalibration evidence (it is a degraded/unknown breaking
        # frame), unlike the single +0.1 m coherent-shift positive case.
        monitor = GroundMonitor()
        local = self._local(count=200)
        local[:, 2] = 0.1
        local[100:, 2] = -0.1
        for _ in range(10):
            report = monitor.feed(self._source(local), self.block)
        self.assertNotEqual(report["status"], MONITOR_RECALIBRATION)

    def test_recalibration_requirement_latches_until_new_context(self):
        monitor = GroundMonitor()
        for _ in range(5):
            report = monitor.feed(self._source(self._local(z=0.1)), self.block)
        self.assertEqual(report["status"], MONITOR_RECALIBRATION)
        # Restoring the original plane does not silently undo an established
        # recalibration requirement; only an explicit new valid context does.
        report = monitor.feed(self._source(self._local()), self.block)
        self.assertEqual(report["status"], MONITOR_RECALIBRATION)
        monitor.note_valid_ground_context()
        report = monitor.feed(self._source(self._local()), self.block)
        self.assertEqual(report["status"], MONITOR_OK)
        # And the latched state survives a stream gap (note_invalid only
        # clears the current continuous run, not the already-invalidated
        # calibration).
        monitor = GroundMonitor()
        for _ in range(5):
            monitor.feed(self._source(self._local(z=0.1)), self.block)
        monitor.note_invalid()
        report = monitor.feed(self._source(self._local()), self.block)
        self.assertEqual(report["status"], MONITOR_RECALIBRATION)


class CliGroundDerivedTest(unittest.TestCase):
    def _write_constrained_inputs(self, directory):
        from core.ground import fit_ground_plane_constrained
        rng = np.random.RandomState(5)

        def plane(count, seed):
            r = np.random.RandomState(seed)
            xy = (r.rand(count, 2) - 0.5) * 8.0
            return np.column_stack([xy, -1.2 + r.randn(count) * 0.02])

        fit = plane(3000, 5)
        val = plane(900, 105)
        points = np.vstack([fit, val])
        points_path = os.path.join(directory, "points.npy")
        fit_path = os.path.join(directory, "fit.npy")
        regions_path = os.path.join(directory, "regions.json")
        np.save(points_path, points)
        np.save(fit_path, np.arange(0, 3000))
        chunks = np.array_split(np.arange(3000, 3900), 3)
        regions = [{"region_id": "r%d" % i, "frame_group": "g%d" % i,
                    "indices": chunk.tolist()}
                   for i, chunk in enumerate(chunks)]
        with open(regions_path, "w", encoding="utf-8") as handle:
            json.dump(regions, handle)
        result = fit_ground_plane_constrained(
            points, frame="innolidar", up_axis=[0.0, 0.0, 1.0],
            sensor_height_interval_m=[0.5, 1.6], fit_indices=np.arange(0, 3000),
            fit_frame_group="fit", validation_regions=regions)
        self.assertEqual(result["status"], "valid")
        return points_path, fit_path, regions_path

    def test_export_writes_block_and_refuses_overwrite(self):
        import calibrate_sensors
        with tempfile.TemporaryDirectory() as directory:
            points, fit, regions = self._write_constrained_inputs(directory)
            output = os.path.join(directory, "geometry.json")
            argv = ["--constrained", "--points", points, "--fit-indices", fit,
                    "--fit-frame-group", "fit", "--validation-regions", regions,
                    "--up-axis", "0", "0", "1", "--sensor-height-interval",
                    "0.5", "1.6", "--output", output, "--ground-derived",
                    "--reference-axis", "1", "0", "0",
                    "--calibration-id", "cal-cli", "--created-at-utc", "t"]
            self.assertEqual(calibrate_sensors.main(argv), 0)
            with open(output, encoding="utf-8") as handle:
                artifact = json.load(handle)
            self.assertIn("ground_derived", artifact)
            validate_geometry_calibration(artifact)
            # A second export must not overwrite an existing calibration version.
            self.assertEqual(calibrate_sensors.main(argv), 2)
            # Missing reference axis is refused before any write.
            other = os.path.join(directory, "other.json")
            argv[argv.index(output)] = other
            del argv[argv.index("--reference-axis"):argv.index("--reference-axis") + 4]
            self.assertEqual(calibrate_sensors.main(argv), 2)


if __name__ == "__main__":
    unittest.main()
