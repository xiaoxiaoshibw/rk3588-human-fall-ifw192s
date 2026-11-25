"""Tests for instant-start (zero empty-room, zero blocking fit) + silent background ground refinement."""
import ast
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import numpy as np

HF_DIR = Path(__file__).resolve().parents[1]
if str(HF_DIR) not in sys.path:
    sys.path.insert(0, str(HF_DIR))

from core.capture_input import ROW_DTYPE
from core.range_contract import binding_tuple
from core.range_engine import RangeEngine
from core.range_features import bound_ground
from core.range_image import ScanGrid
from core.range_service import RangeService
from core.range_wire import parse_cloud
from core.instant_tracker import (
    FALL_DESCENDING,
    FALL_SUSPECTED,
    FALL_UNKNOWN,
    FALL_UPRIGHT,
    InstantHumanTracker,
    REASON_FAST_KINEMATIC,
    REASON_SLOW_DESCENT,
)
from core.silent_ground_refiner import (
    GravityUpEstimator,
    STAGE_FOOT_ANCHORED,
    STAGE_GRAVITY_ONLY,
    STAGE_REFINED_PLANE,
    SilentGroundRefiner,
    fit_low_plane_candidate,
    gravity_up_from_pitch_roll,
    horizontal_basis,
)

ROOT = Path(__file__).resolve().parents[3]
AZ_CSV = ROOT / "src" / "inno_lidar_ros" / "config" / "ifw192s" / "ifw192s_azimuth_192x256.csv"
EL_CSV = ROOT / "src" / "inno_lidar_ros" / "config" / "ifw192s" / "ifw192s_elevation_192x256.csv"


def _make_grid():
    if AZ_CSV.is_file() and EL_CSV.is_file():
        return ScanGrid.from_csv(AZ_CSV, EL_CSV)
    az = np.tile(np.linspace(-60.0, 60.0, 256), (192, 1))
    el = np.tile(np.linspace(-35.0, 35.0, 192)[:, None], (1, 256))
    return ScanGrid(az, el)


def _ray_dirs(grid):
    az = np.radians(grid.azimuth_deg)
    el = np.radians(grid.elevation_deg)
    ce = np.cos(el)
    return np.stack([ce * np.cos(az), ce * np.sin(az), np.sin(el)], axis=-1)


def _world_basis(pitch_deg, roll_deg):
    up = gravity_up_from_pitch_roll(pitch_deg, roll_deg)
    u_ax, v_ax, g_up = horizontal_basis(up)
    # Forward = projection of sensor +X onto ground
    fwd = np.array([1.0, 0.0, 0.0], dtype=np.float64) - g_up * float(g_up[0])
    fwd = fwd / np.linalg.norm(fwd)
    left = np.cross(g_up, fwd)
    return fwd, left, g_up


def _render_synthetic_frame(grid, rays, binding, *, pitch_deg=26.0, roll_deg=0.0, sensor_height_m=1.36,
                            room_back_x=5.5, boxes=(), extra_floor_occ=False):
    """Render an exact ScanGrid-compatible packed point cloud of floor + back wall + world-space 3D boxes."""
    fwd, left, up = _world_basis(pitch_deg, roll_deg)
    # Transform rays into ground frame: R_wg = [fwd; left; up]
    # Point at range r has world coords: p_w = r * (rays @ R_wg.T) + [0, 0, sensor_height_m]
    R_wg = np.stack([fwd, left, up], axis=0)
    ray_w = rays @ R_wg.T  # (H, W, 3)

    h, w, _ = rays.shape
    best_r = np.full((h, w), np.inf, dtype=np.float64)

    # Back wall at world x = room_back_x
    dx = ray_w[:, :, 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        r_wall = np.where(dx > 0.05, room_back_x / dx, np.inf)
    best_r = np.minimum(best_r, np.where((r_wall >= 0.4) & (r_wall <= 7.8), r_wall, np.inf))

    # Floor at world z = 0 -> sensor_height_m + r * ray_w_z = 0
    if not extra_floor_occ:
        dz = ray_w[:, :, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            r_floor = np.where(dz < -0.05, -sensor_height_m / dz, np.inf)
        best_r = np.minimum(best_r, np.where((r_floor >= 0.4) & (r_floor <= 7.8), r_floor, np.inf))

    # World-space AABB boxes: (x0, x1, y0, y1, z0, z1)
    origin_w = np.array([0.0, 0.0, sensor_height_m], dtype=np.float64)
    for (x0, x1, y0, y1, z0, z1) in boxes:
        tmin = np.full((h, w), -np.inf, dtype=np.float64)
        tmax = np.full((h, w), np.inf, dtype=np.float64)
        b_lo = (x0, y0, z0)
        b_hi = (x1, y1, z1)
        valid_box = np.ones((h, w), dtype=bool)
        for ax in range(3):
            d = ray_w[:, :, ax]
            o = origin_w[ax]
            with np.errstate(divide="ignore", invalid="ignore"):
                inv = np.where(np.abs(d) > 1e-8, 1.0 / d, np.nan)
                t1 = (b_lo[ax] - o) * inv
                t2 = (b_hi[ax] - o) * inv
            parallel = np.abs(d) <= 1e-8
            inside_par = (o >= b_lo[ax]) & (o <= b_hi[ax])
            valid_box &= (~parallel) | inside_par
            t_lo = np.where(parallel, -np.inf, np.minimum(t1, t2))
            t_hi = np.where(parallel, np.inf, np.maximum(t1, t2))
            tmin = np.maximum(tmin, t_lo)
            tmax = np.minimum(tmax, t_hi)
        hit = valid_box & (tmax >= np.maximum(tmin, 0.4)) & (tmin <= 7.8)
        r_hit = np.where(hit, np.maximum(tmin, 0.4), np.inf)
        best_r = np.minimum(best_r, r_hit)

    valid = np.isfinite(best_r) & (best_r >= 0.4) & (best_r <= 7.8)
    rs, cs = np.nonzero(valid)
    r_vals = best_r[rs, cs]
    pts = rays[rs, cs] * r_vals[:, None]

    packed = np.zeros(len(rs), dtype=ROW_DTYPE)
    packed["x"] = pts[:, 0].astype(np.float32)
    packed["y"] = pts[:, 1].astype(np.float32)
    packed["z"] = pts[:, 2].astype(np.float32)
    packed["intensity"] = 100.0
    packed["ring"] = rs.astype(np.uint16)
    return grid.decode(packed, binding), packed


def _pack_ros_cloud(packed, seq, stamp_s, frame_id="innolidar"):
    secs = int(stamp_s)
    nsecs = int(round((stamp_s - secs) * 1e9))
    # Build minimal PointCloud2 wire payload compatible with core.range_wire.parse_cloud
    n = len(packed)
    row_bytes = np.zeros(n, dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                                   ("intensity", "<f4"), ("ring", "<u2"), ("timestamp", "<f4")])
    row_bytes["x"] = packed["x"]
    row_bytes["y"] = packed["y"]
    row_bytes["z"] = packed["z"]
    row_bytes["intensity"] = packed["intensity"]
    row_bytes["ring"] = packed["ring"]
    row_bytes["timestamp"] = float(stamp_s)
    data = row_bytes.tobytes()
    point_step = row_bytes.dtype.itemsize
    fields = [
        ("x", 0, 7, 1),
        ("y", 4, 7, 1),
        ("z", 8, 7, 1),
        ("intensity", 12, 7, 1),
        ("ring", 16, 4, 1),
        ("timestamp", 18, 7, 1),
    ]

    def enc_str(s):
        b = s.encode("utf-8")
        return struct.pack("<I", len(b)) + b

    raw = (
        struct.pack("<III", seq, secs, nsecs)
        + enc_str(frame_id)
        + struct.pack("<III", 1, n, len(fields))
        + b"".join(enc_str(name) + struct.pack("<IBI", off, dt, cnt) for name, off, dt, cnt in fields)
        + struct.pack("<?III", False, point_step, point_step * n, len(data))
        + data
        + struct.pack("<?", True)
    )
    msg = parse_cloud(raw)
    msg.serialize = lambda stream: stream.write(raw)
    return raw, msg


class GravityUpEstimatorTests(unittest.TestCase):
    def test_nominal_and_stationary_imu_convergence_with_discrete_commit(self):
        est = GravityUpEstimator({"mount_pitch_deg": 26.0, "mount_roll_deg": 0.0})
        snap0 = est.snapshot()
        self.assertEqual(snap0["source"], "nominal_mount")
        self.assertEqual(snap0["revision"], 0)
        self.assertFalse(snap0["imu_extrinsics_verified"])
        self.assertAlmostEqual(snap0["up"][0], -math.sin(math.radians(26.0)), places=6)
        self.assertAlmostEqual(snap0["up"][2], math.cos(math.radians(26.0)), places=6)

        # Reject invalid / moving / wrong-norm / upside-down IMU samples
        self.assertFalse(est.feed_imu(float("nan"), 0.0, 9.8, 0.0, 0.0, 0.0))
        self.assertFalse(est.feed_imu(0.0, 0.0, 2.0, 0.0, 0.0, 0.0))  # norm too low
        self.assertFalse(est.feed_imu(-4.2, 0.14, 8.7, 0.5, 0.0, 0.0))  # spinning fast
        self.assertFalse(est.feed_imu(0.0, 0.0, -9.8, 0.0, 0.0, 0.0))  # upside down
        self.assertEqual(est.snapshot()["source"], "nominal_mount")
        self.assertEqual(est.snapshot()["imu_rejected"], 4)

        # Feed 9 stationary samples -> not committed yet
        for i in range(9):
            self.assertTrue(est.feed_imu(-4.23, 0.14, 8.72, 0.003, -0.01, 0.005, stamp_s=100.0 + i * 0.005))
        self.assertEqual(est.snapshot()["source"], "nominal_mount")

        # 10th stationary sample commits IMU gravity
        self.assertTrue(est.feed_imu(-4.23, 0.14, 8.72, 0.003, -0.01, 0.005, stamp_s=100.05))
        snap1 = est.snapshot()
        self.assertEqual(snap1["source"], "imu_static_gravity")
        self.assertEqual(snap1["revision"], 1)
        expected = np.array([-4.23, 0.14, 8.72])
        expected = expected / np.linalg.norm(expected)
        self.assertTrue(np.allclose(snap1["up"], expected, atol=1e-3))

        # Tiny jitter (< 1.5 deg) must NOT bump revision (prevents downstream belief reset)
        for i in range(5):
            self.assertTrue(est.feed_imu(-4.25, 0.15, 8.71, 0.001, 0.001, 0.001))
        self.assertEqual(est.snapshot()["revision"], 1)


class SilentGroundRefinerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid = _make_grid()
        cls.rays = _ray_dirs(cls.grid)
        cls.identity = {
            "session": "test_silent_refiner",
            "coordinate": "RAW/innolidar",
            "units": "m",
            "coordinate_transform": "identity",
            "grid_sha256": cls.grid.sha256,
        }
        cls.binding = binding_tuple(cls.identity)

    def test_converges_in_cluttered_room_without_empty_prefix_and_freezes_on_occlusion(self):
        # True sensor tilted 28.0 deg pitch, -1.8 deg roll, height 1.42 m; nominal starts at 26.0 / 0.0
        est = GravityUpEstimator({"mount_pitch_deg": 26.0, "mount_roll_deg": 0.0})
        refiner = SilentGroundRefiner(est, frame_id="innolidar")

        # Frame 0 status: immediately has gravity_only displayPlane
        st0 = refiner.status_dict("s1")
        self.assertEqual(st0["refinementStage"], STAGE_GRAVITY_ONLY)
        self.assertFalse(st0["available"])
        self.assertIsNotNone(st0["displayPlane"])
        self.assertEqual(st0["physicalGroundTruth"], "UNKNOWN")

        true_n = gravity_up_from_pitch_roll(28.0, -1.8)
        # Render cluttered room WITH a person + table (no empty room!)
        for fidx in range(15):
            person_y = -0.6 + 0.08 * fidx
            boxes = [
                (2.4, 2.75, person_y - 0.22, person_y + 0.22, 0.0, 1.72),  # walking person
                (3.6, 4.4, 0.8, 1.6, 0.72, 0.78),  # elevated table top at z=0.75 m
            ]
            frame, _ = _render_synthetic_frame(
                self.grid, self.rays, self.binding,
                pitch_deg=28.0, roll_deg=-1.8, sensor_height_m=1.42, boxes=boxes,
            )
            static_xyz = frame.xyz[frame.source_rows[frame.valid]]
            refiner.observe_frame(static_xyz)

        self.assertEqual(refiner.stage, STAGE_REFINED_PLANE)
        ang_err = math.degrees(math.acos(float(np.clip(np.dot(refiner.normal, true_n), -1.0, 1.0))))
        self.assertLess(ang_err, 0.8)
        self.assertAlmostEqual(refiner.offset_m, 1.42, delta=0.025)

        # Must pass core.range_features.bound_ground strictly
        plane = refiner.bound_plane(frame)
        self.assertIsNotNone(bound_ground(frame, plane))

        # Feed total floor occlusion -> refined plane must stay frozen, never degrade
        sha_before = refiner.sha256
        for _ in range(30):
            refiner.observe_frame(np.zeros((10, 3), dtype=np.float64))
        self.assertEqual(refiner.stage, STAGE_REFINED_PLANE)
        self.assertEqual(refiner.sha256, sha_before)

    def test_elevated_tabletop_rejected_when_floor_points_exist_below(self):
        rng = np.random.RandomState(42)
        g_up = gravity_up_from_pitch_roll(26.0, 0.0)
        fwd, left, up = _world_basis(26.0, 0.0)
        R_gw = np.stack([fwd, left, up], axis=1)  # columns = world axes in sensor frame

        # Dense tabletop at z = 0.75 m (1200 pts) + sparser real floor at z = 0.0 m (260 pts)
        n_tbl, n_flr = 1200, 260
        tbl_w = np.column_stack([rng.uniform(1.8, 3.2, n_tbl), rng.uniform(-0.8, 0.8, n_tbl), np.full(n_tbl, 0.75 - 1.36)])
        flr_w = np.column_stack([rng.uniform(1.5, 4.0, n_flr), rng.uniform(-1.2, 1.2, n_flr), np.full(n_flr, 0.0 - 1.36)])
        pts_s = np.vstack([tbl_w, flr_w]) @ R_gw.T

        cand, reason = fit_low_plane_candidate(pts_s, g_up, SilentGroundRefiner().settings, 12.0)
        self.assertIsNotNone(cand, msg=f"expected real floor, got {reason}")
        # Must fit real floor (~1.36 m below sensor), NEVER the tabletop (~0.61 m below sensor)!
        self.assertAlmostEqual(cand["offset_m"], 1.36, delta=0.04)

    def test_foot_anchored_fallback_and_cross_check(self):
        est = GravityUpEstimator({"mount_pitch_deg": 26.0, "mount_roll_deg": 0.0})
        refiner = SilentGroundRefiner(est, frame_id="innolidar")

        # No floor plane available; walking upright person feeds foot heights around -1.38 m
        for i in range(12):
            refiner.observe_upright_foot(-1.38 + 0.005 * ((i % 3) - 1), 2.5 + 0.04 * i, 0.1)
        self.assertEqual(refiner.stage, STAGE_FOOT_ANCHORED)
        self.assertAlmostEqual(refiner.offset_m, 1.38, delta=0.02)
        st = refiner.status_dict("s_foot")
        self.assertTrue(st["available"])
        self.assertTrue(st["footConsistent"])


class InstantHumanTrackerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid = _make_grid()
        cls.rays = _ray_dirs(cls.grid)
        cls.identity = {
            "session": "test_instant_tracker",
            "coordinate": "RAW/innolidar",
            "units": "m",
            "coordinate_transform": "identity",
            "grid_sha256": cls.grid.sha256,
        }
        cls.binding = binding_tuple(cls.identity)

    def _run_sequence(self, box_fn, n_frames, *, pitch_deg=26.0, sensor_height_m=1.36,
                      ground_offset_fn=None, gravity_shift_at=None):
        g_up = gravity_up_from_pitch_roll(pitch_deg, 0.0)
        tracker = InstantHumanTracker(shape=self.grid.shape, gravity_up=g_up)
        outs = []
        for i in range(n_frames):
            boxes = box_fn(i)
            frame, _ = _render_synthetic_frame(
                self.grid, self.rays, self.binding,
                pitch_deg=pitch_deg, sensor_height_m=sensor_height_m, boxes=boxes,
            )
            cur_g = g_up
            if gravity_shift_at is not None and i >= gravity_shift_at[0]:
                cur_g = gravity_shift_at[1]
            off = ground_offset_fn(i) if ground_offset_fn else None
            outs.append(tracker.step(frame, 1000.0 + i * 0.104, i, gravity_up=cur_g, ground_offset_m=off))
        return outs

    def test_zero_empty_room_fast_fall_and_upright_recovery(self):
        # Frame 0 already has person standing in scene (ZERO empty room!)
        # f0..24: walks laterally -> locks; f25..31: falls fast to floor; f32..50: stays collapsed; f51..64: stands up
        def boxes(i):
            if i < 25:
                y = -0.8 + 0.06 * i
                return [(2.3, 2.65, y - 0.22, y + 0.22, 0.0, 1.72)]
            if i < 32:
                frac = (i - 24) / 7.0
                top = 1.72 * (1.0 - frac) + 0.34 * frac
                w_half = 0.22 * (1.0 - frac) + 0.72 * frac
                return [(2.3, 2.65, 0.64 - w_half, 0.64 + w_half, 0.0, top)]
            if i < 51:
                return [(2.3, 2.65, -0.08, 1.36, 0.0, 0.34)]
            frac = min(1.0, (i - 50) / 8.0)
            top = 0.34 * (1.0 - frac) + 1.70 * frac
            w_half = 0.72 * (1.0 - frac) + 0.22 * frac
            return [(2.3, 2.65, 0.64 - w_half, 0.64 + w_half, 0.0, top)]

        outs = self._run_sequence(boxes, 65)
        self.assertTrue(outs[0]["bootstrap_frame"])
        locked_ids = [o["tracking"]["target_track_id"] for o in outs if o["tracking"]["target_track_id"]]
        self.assertTrue(locked_ids, "must lock human without any empty-room prefix")
        self.assertEqual(len(set(locked_ids)), 1, "must keep same track ID across fall and recovery")

        suspected_frames = [i for i, o in enumerate(outs) if o["fall_status"] == FALL_SUSPECTED]
        self.assertTrue(suspected_frames, "fast fall must trigger suspected")
        self.assertEqual(outs[suspected_frames[0]]["fall_evidence"]["fall_reason"], REASON_FAST_KINEMATIC)
        self.assertFalse(outs[suspected_frames[0]]["fall_evidence"]["confirmed_enabled"])
        self.assertEqual(outs[-1]["fall_status"], FALL_UPRIGHT, "standing up must clear suspected back to upright")

    def test_bend_and_squat_do_not_false_trigger_suspected(self):
        # Walks, then squats (height 0.80 m, aspect ~1.25) for 3.5 seconds, then rises
        def boxes(i):
            if i < 20:
                y = -0.7 + 0.06 * i
                return [(2.3, 2.65, y - 0.22, y + 0.22, 0.0, 1.72)]
            if i < 55:
                return [(2.3, 2.65, 0.20, 0.72, 0.0, 0.80)]
            return [(2.3, 2.65, 0.24, 0.68, 0.0, 1.72)]

        outs = self._run_sequence(boxes, 65)
        self.assertTrue(any(o["tracking"]["target_track_id"] for o in outs))
        self.assertEqual([i for i, o in enumerate(outs) if o["fall_status"] == FALL_SUSPECTED], [])

    def test_hanging_bird_adhesion_and_disconnect_zero_false_lock(self):
        # Hanging bird at z=1.10..1.55 m hovering above a static stand at z=0.0..0.60 m (0.50 m vertical gap!)
        def boxes(i):
            y = -0.3 + 0.05 * math.sin(i * 0.4)
            if i < 25:
                return [
                    (2.3, 2.60, y - 0.20, y + 0.20, 1.15, 1.55),  # hanging bird
                    (2.3, 2.60, -0.18, 0.18, 0.0, 0.55),  # static stand below with gap
                ]
            return [(2.3, 2.60, -0.18, 0.18, 0.0, 0.55)]

        outs = self._run_sequence(boxes, 40, ground_offset_fn=lambda _: 1.36)
        self.assertEqual([i for i, o in enumerate(outs) if o["tracking"]["target_track_id"]], [])
        self.assertEqual([i for i, o in enumerate(outs) if o["fall_status"] == FALL_SUSPECTED], [])

    def test_seamless_gravity_refinement_causes_no_id_switch_or_false_fall(self):
        # Person walks steadily; at frame 20 gravity_up refines from pitch=26 -> pitch=29 deg (+3 deg shift)
        refined_g = gravity_up_from_pitch_roll(29.0, -1.5)

        def boxes(i):
            y = -0.9 + 0.05 * i
            return [(2.5, 2.85, y - 0.22, y + 0.22, 0.0, 1.72)]

        outs = self._run_sequence(boxes, 36, pitch_deg=28.0, gravity_shift_at=(20, refined_g))
        locked_before = [o["tracking"]["target_track_id"] for o in outs[:20] if o["tracking"]["target_track_id"]]
        locked_after = [o["tracking"]["target_track_id"] for o in outs[20:] if o["tracking"]["target_track_id"]]
        self.assertTrue(locked_before and locked_after)
        self.assertEqual(set(locked_before), set(locked_after), "gravity refinement must not switch track ID")
        for o in outs[20:]:
            self.assertNotIn(o["fall_status"], (FALL_DESCENDING, FALL_SUSPECTED))


class InstantEngineServiceNodeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid = _make_grid()
        cls.rays = _ray_dirs(cls.grid)
        cls.identity = {
            "session": "test_instant_engine",
            "coordinate": "RAW/innolidar",
            "units": "m",
            "coordinate_transform": "identity",
            "grid_sha256": cls.grid.sha256,
            "epoch": "live_source_header",
        }
        cls.binding = binding_tuple(cls.identity)

    def test_engine_and_service_instant_start_with_silent_ground_and_physical_v1(self):
        now = [1000.0]
        engine = RangeEngine(
            self.grid, "innolidar", identity=self.identity,
            clock=lambda: now[0],
            instant_start=True, mount_pitch_deg=26.0, mount_roll_deg=0.0,
            human_physical_v1=True,
        )
        service = RangeService(engine, release_id="instant-test", preview=False, clock=lambda: now[0])

        # Feed stationary IMU messages before/during cloud stream
        imu_msg = NS(
            header=NS(stamp=NS(secs=1000, nsecs=0)),
            linear_acceleration=NS(x=-4.55, y=-0.12, z=8.68),
            angular_velocity=NS(x=0.002, y=-0.001, z=0.001),
        )
        for _ in range(12):
            self.assertTrue(service.submit_imu(imu_msg))

        stages_seen = []
        phys_statuses = []
        locked_ids = set()

        for i in range(25):
            now[0] += 0.104
            y = -0.8 + 0.06 * i
            boxes = [(2.4, 2.75, y - 0.22, y + 0.22, 0.0, 1.72)]
            _, packed = _render_synthetic_frame(
                self.grid, self.rays, self.binding,
                pitch_deg=27.5, roll_deg=-0.8, sensor_height_m=1.38, boxes=boxes,
            )
            _, msg = _pack_ros_cloud(packed, seq=i + 1, stamp_s=now[0])
            service.submit(msg)
            res = service.process_latest()
            snap = service.snapshot()
            self.assertEqual(res["observability"], "valid")
            self.assertFalse(res["confirmed_enabled"])
            self.assertIn("instant_start", snap["service"]["capabilities"])
            self.assertIn("silent_ground_refinement", snap["service"]["capabilities"])
            # Frame 0 already has leveled displayPlane and groundBinding!
            self.assertIsNotNone(res["local_range"]["ground"]["displayPlane"])
            self.assertIsNotNone(snap["groundBinding"])
            self.assertEqual(res["local_range"]["background"]["status"], "adaptive_ready")
            stages_seen.append(res["local_range"]["ground"]["refinementStage"])
            phys_statuses.append(res["human_physical_v1"]["status"])
            if res["track_id"]:
                locked_ids.add(res["track_id"])

        self.assertIn(STAGE_GRAVITY_ONLY, stages_seen[:5])
        self.assertEqual(stages_seen[-1], STAGE_REFINED_PLANE)
        self.assertIn("awaiting_ground_offset", phys_statuses[:5])
        self.assertEqual(phys_statuses[-1], "ok")
        self.assertEqual(len(locked_ids), 1, "silent ground refinement must not split active track")

    def test_range_service_node_instant_start_cli_and_imu_subscription(self):
        spec = importlib.util.spec_from_file_location(
            "range_service_node_instant_test",
            ROOT / "src" / "human_fall_detection" / "scripts" / "range_service_node.py",
        )
        node = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(node)

        states, subs, closed = [], [], []
        started = time.monotonic()

        def publisher(topic, typ, **kwargs):
            return NS(publish=lambda msg: states.append(json.loads(msg.data)))

        def subscriber(topic, typ, callback, **kwargs):
            subs.append(topic)
            if topic == "/inno_imu":
                for _ in range(12):
                    callback(NS(
                        header=NS(stamp=NS(secs=100, nsecs=0)),
                        linear_acceleration=NS(x=-4.23, y=0.14, z=8.72),
                        angular_velocity=NS(x=0.001, y=0.001, z=0.001),
                    ))
            return NS(get_num_connections=lambda: 1, unregister=lambda: closed.append(topic))

        rospy = NS(
            init_node=lambda *a, **k: None,
            get_name=lambda: "/range_recognition_service",
            Publisher=publisher,
            Subscriber=subscriber,
            is_shutdown=lambda: time.monotonic() - started > 0.20,
        )
        rosgraph = NS(Master=lambda name: NS(getSystemState=lambda: ([], [], [])))
        modules = {
            "rospy": rospy,
            "rosgraph": rosgraph,
            "sensor_msgs": NS(),
            "sensor_msgs.msg": NS(PointCloud2=object, Imu=object),
            "std_msgs": NS(),
            "std_msgs.msg": NS(String=lambda data: NS(data=data)),
        }
        with patch.dict(sys.modules, modules):
            rc = node.main([
                "--config", str(ROOT / "src" / "human_fall_detection" / "config" / "range_service_v1.json"),
                "--release-id", "node-instant",
                "--instant-start", "--mount-pitch-deg", "26.0", "--human-physical-v1",
            ])
        self.assertEqual(rc, 0)
        self.assertIn("/inno_imu", subs)
        self.assertIn("/inno_imu", closed)
        self.assertTrue(states)
        self.assertTrue(all("instant_start" in s["service"]["capabilities"] for s in states))
        self.assertTrue(all(s["service"]["effectiveConfig"]["instant_start"] is True for s in states[:-1]))

        # Combining --instant-start with --declare-empty-prefix must fail argument parsing
        import io
        from contextlib import redirect_stderr
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            node.main([
                "--config", str(ROOT / "src" / "human_fall_detection" / "config" / "range_service_v1.json"),
                "--instant-start", "--declare-empty-prefix",
            ])

    def test_python38_ast_compatibility(self):
        for rel in (
            "src/human_fall_detection/core/silent_ground_refiner.py",
            "src/human_fall_detection/core/instant_tracker.py",
            "src/human_fall_detection/core/range_engine.py",
            "src/human_fall_detection/core/range_service.py",
            "src/human_fall_detection/scripts/range_service_node.py",
        ):
            src = (ROOT / rel).read_text(encoding="utf-8")
            ast.parse(src, filename=rel, feature_version=(3, 8))


if __name__ == "__main__":
    unittest.main()
