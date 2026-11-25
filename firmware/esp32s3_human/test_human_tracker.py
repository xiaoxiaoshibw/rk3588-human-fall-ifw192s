"""Unit tests for ESP32-S3 C++ background-free kinematic human tracker.

Run with:
    python -B -W error -m unittest discover -s firmware/esp32s3_human -p "test_*.py" -v
"""

import json
import math
import os
import struct
import subprocess
import unittest
from pathlib import Path

HOST_EXE = Path(os.environ.get("HUMAN_S3_HOST_EXE", Path(__file__).resolve().parent / "build" / "human_host.exe"))


def _make_scene_frame(
    wall_dist_m: float = 5.0,
    person: dict | None = None,
    pitch_deg: float = 26.0,
) -> list[tuple[int, float, float, float]]:
    """Generate a synthetic 192x256 grid in tilted sensor coordinates.

    World frame: +X forward, +Y left, +Z up.
    Sensor frame is pitched downward by pitch_deg around +Y.
    """
    p = math.radians(pitch_deg)
    cp, sp = math.cos(p), math.sin(p)

    def world_to_sensor(wx: float, wy: float, wz: float) -> tuple[float, float, float]:
        # Inverse of gravity_up = (-sin(p), 0, cos(p)):
        # sx = cp*wx - sp*wz, sy = wy, sz = sp*wx + cp*wz
        return (cp * wx - sp * wz, wy, sp * wx + cp * wz)

    recs: list[tuple[int, float, float, float]] = []
    # Background wall on a 40x60 patch in grid center
    for r in range(60, 140, 2):
        for c in range(90, 170, 2):
            wy = (c - 130) * 0.03
            wz = (100 - r) * 0.03 + 0.5
            sx, sy, sz = world_to_sensor(wall_dist_m, wy, wz)
            recs.append(((r << 8) | c, sx, sy, sz))

    if person is not None:
        # Render a rectangular human body patch on the grid
        wx = person["x"]
        cy = person["y"]
        z0 = person["z_bottom"]
        z1 = person["z_top"]
        half_w = person["half_w"]
        r0 = int(person.get("r0", 72))
        r1 = int(person.get("r1", 122))
        c0 = int(person.get("c0", 118))
        c1 = int(person.get("c1", 142))
        # Overwrite cells with person points (closer than wall -> nearest return wins)
        nr = max(1, r1 - r0)
        nc = max(1, c1 - c0)
        for r in range(r0, r1 + 1):
            frac_z = 1.0 - (r - r0) / nr
            wz = z0 + frac_z * (z1 - z0)
            for c in range(c0, c1 + 1):
                frac_y = ((c - c0) / nc) * 2.0 - 1.0
                wy = cy + frac_y * half_w
                sx, sy, sz = world_to_sensor(wx, wy, wz)
                recs.append(((r << 8) | c, sx, sy, sz))

    return recs


def _run_host(frames: list[tuple[float, list[tuple[int, float, float, float]]]], pitch_deg: float = 26.0):
    chunks = []
    for idx, (dt, recs) in enumerate(frames):
        chunks.append(struct.pack("<IfI", idx, float(dt), len(recs)))
        for cell, x, y, z in recs:
            chunks.append(struct.pack("<HHfff", cell, 0, x, y, z))
    chunks.append(struct.pack("<IfI", 0, 0.0, 0xFFFFFFFF))

    res = subprocess.run(
        [str(HOST_EXE), "--pitch-deg", f"{pitch_deg:.3f}", "--roll-deg", "0.0"],
        input=b"".join(chunks),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr.decode("utf-8", errors="replace"))
    lines = [json.loads(ln) for ln in res.stdout.decode("utf-8").splitlines() if ln.strip()]
    return lines[0], lines[1:]


def _walking_frame(i):
    return _make_scene_frame(person={
        "x": 2.6, "y": -0.25 + 0.045 * i, "z_bottom": 0.0, "z_top": 1.70,
        "half_w": 0.24, "r0": 72, "r1": 122, "c0": 112 + i, "c1": 128 + i,
    })


def _measured_locks(frames):
    return [tr for frame in frames for tr in frame["tracks"] if tr["locked"] and tr["measured"]]


class TestEsp32S3HumanTracker(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HOST_EXE.exists(), f"missing compiled binary: {HOST_EXE}")

    def test_memory_budget_fits_esp32s3(self):
        init_msg, _ = _run_host([(0.1, _make_scene_frame())])
        # Must stay well below 2 MB (ESP32-S3 has 8 MB PSRAM + 512 KB SRAM)
        self.assertLess(init_msg["workspace_bytes"], 1_200_000)
        self.assertLess(init_msg["tracker_object_bytes"], 32_768)

    def test_fast_fall_triggers_kinematic_without_empty_room_or_ground_fit(self):
        frames = []
        # Frame 0: person ALREADY standing in scene (no empty room!)
        frames.append((0.1, _make_scene_frame(person={
            "x": 2.6, "y": -0.3, "z_bottom": 0.0, "z_top": 1.70, "half_w": 0.24,
            "r0": 72, "r1": 122, "c0": 112, "c1": 128,
        })))
        # Frames 1..14: person walks slightly in +Y and stands upright
        for i in range(1, 15):
            y = -0.3 + min(0.35, i * 0.04)
            c_shift = int(min(10, i))
            frames.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": y, "z_bottom": 0.0, "z_top": 1.70, "half_w": 0.24,
                "r0": 72, "r1": 122, "c0": 112 + c_shift, "c1": 128 + c_shift,
            })))
        # Frames 15..20: rapid fall (0.5 s drop from 1.70 m to 0.35 m, widening horizontally)
        drop_tops = [1.55, 1.25, 0.85, 0.50, 0.36, 0.35]
        for step_i, top in enumerate(drop_tops):
            half_w = 0.24 + step_i * 0.09
            r0 = 72 + step_i * 7
            c_half = 8 + step_i * 3
            frames.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": 0.05, "z_bottom": 0.0, "z_top": top, "half_w": half_w,
                "r0": r0, "r1": 122, "c0": 130 - c_half, "c1": 130 + c_half,
            })))
        # Remains collapsed long enough to check the alert's finite hold.
        for _ in range(160):
            frames.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": 0.05, "z_bottom": 0.0, "z_top": 0.35, "half_w": 0.72,
                "r0": 107, "r1": 122, "c0": 107, "c1": 153,
            })))

        _, out = _run_host(frames, pitch_deg=26.0)
        suspected = [
            (m["frame"], tr)
            for m in out
            for tr in m["tracks"]
            if tr["locked"] and tr["measured"] and tr["state"] == "FALL_SUSPECTED"
        ]
        self.assertGreater(len(suspected), 0, "expected FALL_SUSPECTED on synthetic fast fall")
        first_tr = suspected[0][1]
        self.assertEqual(first_tr["reason"], "FAST_KINEMATIC")
        self.assertGreaterEqual(first_tr["pk_dv"], 0.70)
        self.assertGreaterEqual(first_tr["drop_m"], 0.45)
        self.assertLessEqual(suspected[-1][0] - suspected[0][0], 120)
        self.assertEqual(len(_measured_locks(out[-20:])), 0)

        # Skip two real measurements during low-posture accumulation, then rise on the same ID.
        interrupted = frames[:26] + [(0.1, [])] * 2 + frames[26:51]
        for top, bottom, half_w, row0, row1 in [
            (0.88, 0.39, 0.32, 91, 112), (1.14, 0.24, 0.32, 84, 116),
            (1.70, 0.0, 0.24, 72, 122),
        ]:
            interrupted.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": 0.05, "z_bottom": bottom, "z_top": top, "half_w": half_w,
                "r0": row0, "r1": row1, "c0": 118, "c1": 142,
            })))
        _, out = _run_host(interrupted)
        def track_at(frame):
            return next(tr for tr in out[frame]["tracks"] if tr["id"] == first_tr["id"])

        before = track_at(25)
        self.assertEqual(before["state"], "FALLING")
        for frame in (26, 27):
            missed = track_at(frame)
            self.assertFalse(missed["measured"])
            self.assertEqual(missed["pts"], 0)
            self.assertEqual(missed["low_s"], before["low_s"])
            self.assertEqual(missed["state"], before["state"])
            self.assertEqual(missed["pk_dv"], before["pk_dv"])
        self.assertTrue(track_at(28)["measured"])
        self.assertEqual(track_at(28)["low_s"], before["low_s"])
        self.assertEqual(track_at(len(out) - 4)["state"], "FALL_SUSPECTED")
        self.assertEqual(track_at(len(out) - 3)["state"], "FALL_SUSPECTED")
        self.assertTrue(track_at(len(out) - 1)["measured"])
        self.assertEqual(track_at(len(out) - 1)["state"], "UPRIGHT")

    def test_bend_and_recover_does_not_trigger_fall(self):
        frames = []
        # Walk in & stand upright
        for i in range(14):
            c_shift = min(10, i)
            frames.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": -0.2 + min(0.3, i * 0.03), "z_bottom": 0.0, "z_top": 1.70, "half_w": 0.24,
                "r0": 72, "r1": 122, "c0": 112 + c_shift, "c1": 128 + c_shift,
            })))
        # Bend down briefly (0.6 s) to 0.95 m, then stand back up
        bend_tops = [1.50, 1.25, 1.00, 0.95, 0.98, 1.20, 1.50, 1.70]
        for top in bend_tops:
            r0 = int(122 - (top / 1.70) * 50)
            frames.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": 0.1, "z_bottom": 0.0, "z_top": top, "half_w": 0.28,
                "r0": r0, "r1": 122, "c0": 120, "c1": 140,
            })))
        for _ in range(15):
            frames.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": 0.1, "z_bottom": 0.0, "z_top": 1.70, "half_w": 0.24,
                "r0": 72, "r1": 122, "c0": 122, "c1": 138,
            })))

        _, out = _run_host(frames, pitch_deg=26.0)
        self.assertTrue(_measured_locks(out[:14]))
        suspected = [
            m["frame"]
            for m in out
            for tr in m["tracks"]
            if tr["locked"] and tr["state"] == "FALL_SUSPECTED"
        ]
        self.assertEqual(suspected, [], "brief bend and recovery must not trigger FALL_SUSPECTED")

    def test_sustained_squat_tying_shoes_does_not_trigger_fall(self):
        frames = []
        # Walk in & stand upright
        for i in range(14):
            c_shift = min(10, i)
            frames.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": -0.2 + min(0.3, i * 0.03), "z_bottom": 0.0, "z_top": 1.70, "half_w": 0.24,
                "r0": 72, "r1": 122, "c0": 112 + c_shift, "c1": 128 + c_shift,
            })))
        # Squat down to 0.72 m height (aspect ~0.75) and stay for 15 s.
        for top in [1.45, 1.15, 0.90, 0.75]:
            r0 = int(122 - (top / 1.70) * 50)
            frames.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": 0.1, "z_bottom": 0.0, "z_top": top, "half_w": 0.38,
                "r0": r0, "r1": 122, "c0": 118, "c1": 142,
            })))
        for _ in range(150):
            frames.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": 0.1, "z_bottom": 0.0, "z_top": 0.72, "half_w": 0.42,
                "r0": 100, "r1": 122, "c0": 116, "c1": 144,
            })))

        _, out = _run_host(frames, pitch_deg=26.0)
        self.assertTrue(_measured_locks(out[:14]))
        self.assertEqual({tr["id"] for tr in _measured_locks(out[-1:])},
                         {tr["id"] for tr in _measured_locks(out[:14])})
        suspected = [
            m["frame"]
            for m in out
            for tr in m["tracks"]
            if tr["locked"] and tr["state"] == "FALL_SUSPECTED"
        ]
        self.assertEqual(suspected, [], "squatting (height~0.72m) must not trigger FALL_SUSPECTED")

    def test_slow_descent_fall_triggers_suspected(self):
        frames = []
        for i in range(14):
            c_shift = min(10, i)
            frames.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": -0.2 + min(0.3, i * 0.03), "z_bottom": 0.0, "z_top": 1.70, "half_w": 0.24,
                "r0": 72, "r1": 122, "c0": 112 + c_shift, "c1": 128 + c_shift,
            })))
        # Slow descent over 3.0 s (30 frames) from 1.70 m down to 0.34 m
        for i in range(30):
            frac = (i + 1) / 30.0
            top = 1.70 - frac * 1.36
            half_w = 0.24 + frac * 0.48
            r0 = int(72 + frac * 35)
            c_half = int(8 + frac * 15)
            frames.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": 0.1, "z_bottom": 0.0, "z_top": top, "half_w": half_w,
                "r0": r0, "r1": 122, "c0": 130 - c_half, "c1": 130 + c_half,
            })))
        for _ in range(20):
            frames.append((0.1, _make_scene_frame(person={
                "x": 2.6, "y": 0.1, "z_bottom": 0.0, "z_top": 0.34, "half_w": 0.72,
                "r0": 107, "r1": 122, "c0": 107, "c1": 153,
            })))

        _, out = _run_host(frames, pitch_deg=26.0)
        suspected = [
            (m["frame"], tr)
            for m in out
            for tr in m["tracks"]
            if tr["locked"] and tr["state"] == "FALL_SUSPECTED"
        ]
        self.assertGreater(len(suspected), 0, "expected FALL_SUSPECTED on synthetic slow fall")

    def test_static_scene_spawns_zero_locked_humans(self):
        frames = [(0.1, _make_scene_frame(person=None)) for _ in range(25)]
        _, out = _run_host(frames, pitch_deg=26.0)
        locked = [tr for m in out for tr in m["tracks"] if tr["locked"]]
        self.assertEqual(locked, [], "static background only must not lock any human")

    def test_new_tall_static_surface_stays_unlocked_and_becomes_background(self):
        wall = _make_scene_frame()
        _, static = _run_host([(0.1, wall)] * 4 + [(0.1, _walking_frame(10))] * 140)
        self.assertGreater(max(frame["candidates"] for frame in static), 0)
        self.assertEqual(len(_measured_locks(static)), 0)
        self.assertEqual(static[-1]["fg_seeds"], 0)

    def test_moving_small_top_edge_stays_unlocked(self):
        backdrop = _make_scene_frame(person={
            "x": 5.0, "y": 0.1, "z_bottom": 1.55, "z_top": 2.40, "half_w": 1.2,
            "r0": 170, "r1": 191, "c0": 90, "c1": 170,
        })
        def bird(i):
            return _make_scene_frame(person={
                "x": 2.6, "y": -0.45 + 0.08 * i, "z_bottom": 1.7, "z_top": 2.3, "half_w": 0.4,
                "r0": 173, "r1": 191, "c0": 112 + i, "c1": 133 + i,
            })

        _, small = _run_host([(0.1, backdrop)] * 4 + [
            (0.1, backdrop + bird(min(i, 12))) for i in range(116)
        ])
        self.assertGreater(max(frame["candidates"] for frame in small), 0)
        self.assertEqual(len(_measured_locks(small)), 0)

    def test_pause_keeps_lock_briefly_then_expires_and_walking_reacquires(self):
        walking = [(0.1, _walking_frame(i)) for i in range(13)]
        _, out = _run_host([(0.1, _make_scene_frame())] * 4 + walking +
                           [(0.1, _walking_frame(12))] * 280 + walking[::-1])
        first = _measured_locks(out[:17])
        later = _measured_locks(out[297:])
        self.assertTrue(first)
        self.assertEqual({tr["id"] for tr in _measured_locks(out[170:175])}, {first[0]["id"]})
        self.assertGreater(_measured_locks(out[170:175])[-1]["still_sec"], 15.0)
        self.assertEqual(len(_measured_locks(out[270:297])), 0)
        self.assertTrue(later)
        self.assertNotEqual(first[0]["id"], later[0]["id"])

    def test_source_gap_breaks_lock_and_motion_history(self):
        walking = [(0.1, _walking_frame(i)) for i in range(13)]
        _, out = _run_host([(0.1, _make_scene_frame())] * 4 + walking +
                           [(2.5, _walking_frame(12))] + [(0.1, _walking_frame(12))] * 8)
        self.assertTrue(_measured_locks(out[:17]))
        self.assertEqual(len(_measured_locks(out[17:])), 0)

    def test_slow_radial_motion_can_lock(self):
        frames = [(0.1, _make_scene_frame())] * 4
        for i in range(14):
            frames.append((0.1, _make_scene_frame(person={
                "x": 3.1 - 0.032 * i, "y": 0.1, "z_bottom": 0.0, "z_top": 1.70,
                "half_w": 0.24, "r0": 72, "r1": 122, "c0": 116, "c1": 140,
            })))
        _, out = _run_host(frames)
        self.assertTrue(_measured_locks(out))

    def test_locked_track_does_not_transfer_to_small_top_fragment(self):
        walking = [(0.1, _walking_frame(i)) for i in range(13)]
        fragment = _make_scene_frame(person={
            "x": 2.6, "y": 0.29, "z_bottom": 1.40, "z_top": 1.70,
            "half_w": 0.24, "r0": 72, "r1": 82, "c0": 124, "c1": 140,
        })
        _, out = _run_host([(0.1, _make_scene_frame())] * 4 + walking + [(0.1, fragment)] * 60)
        self.assertTrue(_measured_locks(out[:17]))
        self.assertEqual(len(_measured_locks(out[17:])), 0)

    def test_suspended_bird_adhered_to_stand_stays_unlocked_and_never_falls(self):
        p = math.radians(26.0)
        cp, sp = math.cos(p), math.sin(p)

        def w2s(wx: float, wy: float, wz: float) -> tuple[float, float, float]:
            return (cp * wx - sp * wz, wy, sp * wx + cp * wz)

        base_wall = _make_scene_frame(wall_dist_m=5.0)
        frames = [(0.1, base_wall)] * 3
        for i in range(8):
            recs = list(base_wall)
            c0 = 112 + min(i, 4)
            swing_y = 0.045 * min(i, 4)
            bird_x = 2.25 - 0.03 * min(i, 4)
            # 180-pt swinging bird at top (H=0.25m, W=0.51m)
            for r in range(80, 92):
                wz = 0.65 + ((91 - r) / 11.0) * 0.25
                for c in range(c0, c0 + 15):
                    wy = swing_y + (((c - c0) / 14.0) * 2.0 - 1.0) * 0.255
                    recs.append(((r << 8) | c, *w2s(bird_x, wy, wz)))
            # Thin 1-col vertical bridge + 16-pt stand edge at bottom (40 pts -> 220 pts total, H~1.52m)
            c_mid = c0 + 7
            for r in range(92, 116):
                wz = -0.55 + ((115 - r) / 23.0) * 1.20
                recs.append(((r << 8) | c_mid, *w2s(bird_x, swing_y, wz)))
            for r in range(116, 120):
                wz = -0.73 + ((119 - r) / 3.0) * 0.15
                for c in range(c_mid - 1, c_mid + 3):
                    recs.append(((r << 8) | c, *w2s(bird_x, swing_y + (c - c_mid) * 0.04, wz)))
            frames.append((0.1, recs))
        # Adhesion disconnects: only 180-pt bird remains (H=0.25m)
        for _ in range(20):
            recs = list(base_wall)
            for r in range(112, 124):
                wz = -0.41 + ((123 - r) / 11.0) * 0.25
                for c in range(116, 131):
                    wy = 0.18 + (((c - 116) / 14.0) * 2.0 - 1.0) * 0.255
                    recs.append(((r << 8) | c, *w2s(2.13, wy, wz)))
            frames.append((0.1, recs))

        _, out = _run_host(frames, pitch_deg=26.0)
        self.assertGreater(max(frame["candidates"] for frame in out), 0)
        self.assertEqual(len(_measured_locks(out)), 0)

    def test_top_only_motion_adhered_to_static_lower_stand_stays_unlocked(self):
        p = math.radians(26.0)
        cp, sp = math.cos(p), math.sin(p)

        def w2s(wx: float, wy: float, wz: float) -> tuple[float, float, float]:
            return (cp * wx - sp * wz, wy, sp * wx + cp * wz)

        base_wall = _make_scene_frame(wall_dist_m=5.0)
        frames = [(0.1, base_wall)] * 3
        for i in range(12):
            recs = list(base_wall)
            # Static lower half (r=98..122, 25 rows x 10 cols = 250 pts, completely fixed)
            for r in range(98, 123):
                wz = -0.60 + ((122 - r) / 24.0) * 0.80
                for c in range(116, 126):
                    wy = ((c - 116) / 9.0 * 2.0 - 1.0) * 0.20
                    recs.append(((r << 8) | c, *w2s(2.30, wy, wz)))
            # Moving upper half (r=72..97, 26 rows x 10 cols = 260 pts) shifting horizontally/in-depth
            shift_c = min(i, 6)
            for r in range(72, 98):
                wz = 0.22 + ((97 - r) / 25.0) * 0.80
                for c in range(116 + shift_c, 126 + shift_c):
                    wy = 0.04 * shift_c + ((c - (116 + shift_c)) / 9.0 * 2.0 - 1.0) * 0.20
                    recs.append(((r << 8) | c, *w2s(2.30 - 0.03 * shift_c, wy, wz)))
            frames.append((0.1, recs))

        _, out = _run_host(frames, pitch_deg=26.0)
        self.assertGreater(max(frame["candidates"] for frame in out), 0)
        self.assertEqual(len(_measured_locks(out)), 0)

    def test_elevated_mid_upper_row_object_stays_unlocked(self):
        backdrop = _make_scene_frame(person={
            "x": 5.0, "y": 0.0, "z_bottom": 0.2, "z_top": 2.2, "half_w": 1.2,
            "r0": 100, "r1": 165, "c0": 95, "c1": 165,
        })
        frames = [(0.1, backdrop)] * 3
        for i in range(12):
            obj = _make_scene_frame(person={
                "x": 2.4, "y": -0.25 + 0.05 * i, "z_bottom": 0.3, "z_top": 1.8, "half_w": 0.24,
                "r0": 105, "r1": 155, "c0": 112 + i, "c1": 128 + i,
            })
            frames.append((0.1, backdrop + obj))

        _, out = _run_host(frames, pitch_deg=26.0)
        self.assertGreater(max(frame["candidates"] for frame in out), 0)
        self.assertEqual(len(_measured_locks(out)), 0)


if __name__ == "__main__":
    unittest.main()
