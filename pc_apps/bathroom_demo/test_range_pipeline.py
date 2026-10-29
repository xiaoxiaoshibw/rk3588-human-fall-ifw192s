"""Unit tests for the bathroom demo (pure NumPy, Python 3.8)."""
import math
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fall_hmm  # noqa: E402
import range_pipeline as rp  # noqa: E402


def feature(cx=1.5, cy=0.0, count=300, height=1.7, span=1.4, angle=4.0, range_m=2.0):
    return dict(cx=cx, cy=cy, count=count, height_p90=height, height_span=span,
                inclination_deg=angle, range_m=range_m)


class GridTest(unittest.TestCase):
    def test_known_ray_maps_to_ring_and_column(self):
        grid = rp.to_grid([2.0], [0.0], [0.0], [96], [500.0])
        self.assertTrue(grid.valid[96, 120])
        self.assertAlmostEqual(float(grid.range[96, 120]), 2.0, places=5)

    def test_zero_return_is_dropped(self):
        grid = rp.to_grid([0.0, 2.0], [0.0, 0.0], [0.0, 0.0], [96, 96], [0.0, 500.0])
        self.assertFalse(grid.valid[96, 120] and np.isnan(grid.range[96, 120]))
        self.assertEqual(int(grid.valid.sum()), 1)

    def test_nearest_return_wins_duplicate_cell(self):
        grid = rp.to_grid([2.0, 1.5], [0.0, 0.0], [0.0, 0.0], [96, 96], [0.0, 0.0])
        self.assertAlmostEqual(float(grid.range[96, 120]), 1.5, places=5)


class BackgroundTest(unittest.TestCase):
    def _block(self, value):
        xs, ys, rings = [], [], []
        for ring in (95, 96, 97):
            for col in (119, 120, 121):
                az = math.radians(-59.8 + 0.5 * col)
                el = math.radians(-41.6 + 0.469 * ring)
                r = value
                xs.append(r * math.cos(el) * math.cos(az))
                ys.append(r * math.cos(el) * math.sin(az))
                rings.append(ring)
        return rp.to_grid(xs, ys, [0.0] * len(xs), rings, [500.0] * len(xs))

    def test_residual_marks_closer_block(self):
        median = np.full((rp.RINGS, rp.COLS), 2.0, dtype=np.float32)
        sigma = np.full((rp.RINGS, rp.COLS), 0.012, dtype=np.float32)
        bg = rp.Background(median, sigma, 1)
        grid = self._block(1.5)
        ground = rp.Ground(plane=[0.0, 0.0, 0.0])
        mask = rp.foreground_mask(grid, bg, ground, dict(rp.DEFAULTS))
        self.assertTrue(mask[96, 120])

    def test_static_block_is_not_foreground(self):
        median = np.full((rp.RINGS, rp.COLS), 2.0, dtype=np.float32)
        sigma = np.full((rp.RINGS, rp.COLS), 0.012, dtype=np.float32)
        bg = rp.Background(median, sigma, 1)
        grid = self._block(2.0)
        ground = rp.Ground(plane=[0.0, 0.0, 0.0])
        mask = rp.foreground_mask(grid, bg, ground, dict(rp.DEFAULTS))
        self.assertFalse(mask[96, 120])


class ComponentTest(unittest.TestCase):
    def test_depth_discontinuity_splits_components(self):
        mask = np.zeros((rp.RINGS, rp.COLS), dtype=bool)
        rng = np.full((rp.RINGS, rp.COLS), np.nan, dtype=np.float32)
        # two 3x3 blocks at the same rows, 10 columns apart, 0.8 m depth gap
        mask[90:93, 100:103] = True
        rng[90:93, 100:103] = 1.0
        mask[90:93, 113:116] = True
        rng[90:93, 113:116] = 1.8
        comps = rp.components(mask, rng, dict(rp.DEFAULTS, min_component=5))
        self.assertEqual(len(comps), 2)

    def test_continuous_plane_is_one_component(self):
        mask = np.zeros((rp.RINGS, rp.COLS), dtype=bool)
        rng = np.full((rp.RINGS, rp.COLS), np.nan, dtype=np.float32)
        mask[90:95, 100:110] = True
        rng[90:95, 100:110] = 1.0
        comps = rp.components(mask, rng, dict(rp.DEFAULTS, min_component=5))
        self.assertEqual(len(comps), 1)


class TrackerTest(unittest.TestCase):
    def test_constant_velocity_keeps_id(self):
        tracker = rp.Tracker(dict(rp.DEFAULTS, min_track_hits=1))
        ids = []
        for i in range(6):
            tracks = tracker.update([feature(cx=1.0 + 0.1 * i, cy=0.0)], i * 0.1)
            target = tracker.choose()
            ids.append(None if target is None else target.id)
        self.assertTrue(all(v is not None for v in ids))
        self.assertEqual(len(set(ids)), 1)

    def test_gap_drops_track(self):
        tracker = rp.Tracker(dict(rp.DEFAULTS))
        tracker.update([feature()], 0.0)
        tracker.choose()
        tracker.update([], 2.0)
        self.assertEqual(len(tracker.tracks), 0)


class HMMTest(unittest.TestCase):
    def _run(self, heights, spans, dt=0.1):
        hmm = fall_hmm.FallHMM(fall_hold_s=0.3, long_lie_s=1.0)
        out = []
        for i, (h, s) in enumerate(zip(heights, spans)):
            f = feature(height=h, span=s, count=300, angle=10.0)
            out.append(hmm.update(i * dt, f))
        return out

    def test_upright_then_fall_then_long_lie(self):
        heights = [1.8] * 10 + [1.4, 1.0, 0.6, 0.4] + [0.35] * 20
        spans = [1.5] * 10 + [1.2, 0.9, 0.6, 0.4] + [0.35] * 20
        out = self._run(heights, spans)
        self.assertGreaterEqual(sum(1 for r in out if r["fall_suspected"]), 1)
        self.assertGreaterEqual(sum(1 for r in out if r["long_lie_suspected"]), 1)

    def test_low_at_birth_is_not_a_fall(self):
        out = self._run([0.3] * 30, [0.2] * 30)
        self.assertEqual(sum(1 for r in out if r["fall_suspected"]), 0)

    def test_fit_returns_five_state_model(self):
        seq = ([0] * 10 + [2, 3] + [3] * 5,
               [(3, 2, 1, 0)] * 10 + [(2, 1, 0, 1)] * 2 + [(0, 0, 1, 1)] * 5)
        model = fall_hmm.fit_hmm([seq])
        self.assertEqual(model.transition.shape, (5, 5))
        self.assertEqual(model.emission["lying"]["h"].shape, (4,))


class GroundTest(unittest.TestCase):
    def test_transform_height(self):
        ground = rp.Ground(R=np.eye(3), t=np.array([0.0, 0.0, 1.0]))
        h = ground.height(np.array([0.0]), np.array([0.0]), np.array([0.0]))
        self.assertAlmostEqual(float(h[0]), 1.0)

    def test_ground_roundtrip(self):
        ground = rp.Ground(R=np.eye(3), t=np.array([0.1, -0.2, 1.0]))
        p = np.array([[1.0, 2.0, 3.0]])
        g = ground.to_ground(p[:, 0], p[:, 1], p[:, 2])
        back = ground.from_ground(g)
        self.assertTrue(np.allclose(back, p, atol=1e-9))


if __name__ == "__main__":
    unittest.main()