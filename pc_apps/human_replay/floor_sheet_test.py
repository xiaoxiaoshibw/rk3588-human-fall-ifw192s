"""GL-S01 lowest_floor_sheet_v2 synthetic regression + two probe-bug regressions.

A-layer / B-layer scenes use known ground truth in the nominal display frame
and are rotated into the source frame exactly like real captures. All gates
are the production ones from floor_sheet.SHEET_PROFILE; no scene-side tuning.
"""
import unittest
from unittest.mock import patch

import numpy as np

from floor_detector import detect_floor_regions
from floor_detector_test import scene as v1_scene
from floor_sheet import SHEET_PROFILE, _clean_cells, _sheet_metrics, detect_floor_regions_v2
from leveling_quality import rotation

R = rotation(26, 0)
T = np.array([0., 0., 1.3])
FRAMES = 24
PLANE = {"normal": (R.T @ np.array([0., 0., 1.])).tolist(), "offset_m": 1.3}


def to_source(display):
    return (display - T) @ R


def slab(rect, rng, density=1200, z=0.0, noise=.002, frames=FRAMES):
    xl, xh, yl, yh = rect
    per = max(1, int(density * (xh - xl) * (yh - yl)))
    pts, ids = [], []
    for frame in range(frames):
        pts.append(np.column_stack([rng.uniform(xl, xh, per), rng.uniform(yl, yh, per),
                                    z + rng.normal(0, noise, per)]))
        ids.append(np.full(per, frame, dtype="i4"))
    return np.vstack(pts), np.concatenate(ids)


def post(cx, cy, rng, radius=.015, height=.8, per=80, frames=FRAMES):
    pts, ids = [], []
    for frame in range(frames):
        angle = rng.uniform(0, 2 * np.pi, per)
        radius = rng.uniform(0, radius, per)
        pts.append(np.column_stack([cx + radius * np.cos(angle), cy + radius * np.sin(angle),
                                    rng.uniform(0, height, per)]))
        ids.append(np.full(per, frame, dtype="i4"))
    return np.vstack(pts), np.concatenate(ids)


def posts_floor(nx, ny, keep, seed, rng=None):
    rng = np.random.RandomState(seed) if rng is None else rng
    frames, ids = [], []
    pts, ident = slab((0, nx * .25, 0, ny * .25), rng)
    frames.append(pts)
    ids.append(ident)
    for i in range(nx):
        for j in range(ny):
            if (i, j) in keep:
                continue
            pts, ident = post((i + .5) * .25, (j + .5) * .25, rng)
            frames.append(pts)
            ids.append(ident)
    display = np.vstack(frames)
    return to_source(display), np.concatenate(ids)


def source_points(chunks):
    pts, ids = [], []
    for points, ident in chunks:
        pts.append(to_source(points))
        ids.append(ident)
    return np.vstack(pts), np.concatenate(ids)


class FloorSheetTest(unittest.TestCase):
    def test_scattered_coplanar_patches_identity_rejected(self):
        rng = np.random.RandomState(11)
        rects = [(0, .5, 0, .5), (2, 2.5, 0, .5), (0, .5, 2, 2.5), (2, 2.5, 2, 2.5)]
        points, ids = source_points([slab(rect, rng) for rect in rects])
        with self.assertRaisesRegex(ValueError, "floor identity failed"):
            detect_floor_regions_v2(points, ids, 26, 0)

    def test_adjacent_clean_cells_insufficient_support(self):
        points, ids = posts_floor(3, 3, {(0, 0), (1, 0), (0, 1), (1, 1)}, seed=12)
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_CLEAN_ROI_SUPPORT"):
            detect_floor_regions_v2(points, ids, 26, 0)

    def test_scattered_clean_cells_on_one_sheet_succeed(self):
        keep = {(0, 0), (2, 0), (0, 2), (2, 2)}
        points, ids = posts_floor(6, 6, keep, seed=13)
        result = detect_floor_regions_v2(points, ids, 26, 0)
        candidate = result["candidate"]
        self.assertEqual(candidate["kind"], "lowest_floor_sheet_v2")
        self.assertTrue(candidate["full_height_preserved"])
        self.assertFalse(candidate["uses_manual_reference"])
        self.assertEqual(candidate["fit_frame_count"], FRAMES)
        regions = result["regions"]
        self.assertEqual(len(regions), 4)
        keys = sorted((int(region[0] / .25), int(region[2] / .25)) for region in regions)
        self.assertEqual(keys, sorted(keep))
        for a in range(4):
            for b in range(a + 1, 4):
                r1, r2 = regions[a], regions[b]
                self.assertFalse(min(r1[1], r2[1]) > max(r1[0], r2[0])
                                 and min(r1[3], r2[3]) > max(r1[2], r2[2]))

    def test_low_platforms_with_empty_gaps_identity_rejected(self):
        rng = np.random.RandomState(14)
        rects = [(0, .6, 0, .6), (1, 1.6, 0, .6), (0, .6, 1, 1.6)]
        points, ids = source_points([slab(rect, rng, z=-.45) for rect in rects])
        with self.assertRaisesRegex(ValueError, "floor_regions_invalid"):
            detect_floor_regions_v2(points, ids, 26, 0)

    def test_out_of_band_surface_not_floor(self):
        rng = np.random.RandomState(15)
        points, ids = source_points([slab((0, 1.5, 0, 1.5), rng, z=-.75)])
        with self.assertRaisesRegex(ValueError, "floor_not_found"):
            detect_floor_regions_v2(points, ids, 26, 0)

    def test_contact_bridge_merges_fragmented_sheet(self):
        rng = np.random.RandomState(16)
        left, idl = slab((-0.9, -0.1, -0.3, 0.3), rng)
        right, idr = slab((0.1, 0.9, -0.3, 0.3), rng)
        per = 4000
        wall, wall_ids = [], []
        for frame in range(FRAMES):
            wall.append(np.column_stack([rng.uniform(-.1, .1, per), rng.uniform(-.3, .3, per),
                                         rng.uniform(.035, .5, per)]))
            wall_ids.append(np.full(per, frame, dtype="i4"))
        points, ids = source_points([(left, idl), (right, idr),
                                     (np.vstack(wall), np.concatenate(wall_ids))])
        metrics = _sheet_metrics(points, ids, R, PLANE)
        self.assertTrue(metrics["bridging_needed"])
        self.assertTrue(metrics["gap_pairs"])
        self.assertTrue(all(pair["explained"] for pair in metrics["gap_pairs"]))
        self.assertGreaterEqual(metrics["effective_area_m2"], .5)

    def test_leg_on_continuous_floor_identity_ok(self):
        rng = np.random.RandomState(21)
        floor, idf = slab((0, 2, 0, 2), rng)
        leg, idl = post(1, 1, rng, radius=.02, height=.7, per=120)
        metrics = _sheet_metrics(*source_points([(floor, idf), (leg, idl)]), R, PLANE)
        self.assertGreaterEqual(metrics["largest_area_m2"], .5)
        self.assertFalse(metrics["bridging_needed"])
        self.assertEqual(metrics["unexplained_gap_count"], 0)

    def test_bridge_requires_contact_and_bounded_gap(self):
        rng = np.random.RandomState(17)
        left, idl = slab((-0.9, -0.1, -0.3, 0.3), rng)
        right, idr = slab((0.1, 0.9, -0.3, 0.3), rng)
        empty = _sheet_metrics(*source_points([(left, idl), (right, idr)]), R, PLANE)
        self.assertTrue(empty["bridging_needed"])
        self.assertLess(empty["effective_area_m2"], .5)
        self.assertEqual(empty["unexplained_gap_count"], len(empty["gap_pairs"]))
        far_left, idfl = slab((-0.9, -0.1, -0.3, 0.3), rng)
        far_right, idfr = slab((0.3, 1.1, -0.3, 0.3), rng)
        noise = np.column_stack([rng.uniform(-0.1, 0.3, 60), rng.uniform(-0.3, 0.3, 60),
                                 rng.normal(0, .01, 60)])
        noise_ids = np.full(60, 0, dtype="i4")
        noisy = _sheet_metrics(*source_points([(far_left, idfl), (far_right, idfr), (noise, noise_ids)]),
                               R, PLANE)
        self.assertTrue(noisy["bridging_needed"])
        self.assertLess(noisy["effective_area_m2"], .5)
        self.assertGreaterEqual(noisy["unexplained_gap_count"], 1)

    def test_undulating_floor_stays_connected(self):
        rng = np.random.RandomState(18)
        per = 6000
        chunks, ids = [], []
        for frame in range(FRAMES):
            x = rng.uniform(-1, 1, per)
            y = rng.uniform(-1, 1, per)
            z = rng.normal(0, .003, per)
            for cx, cy, amp in ((-.5, .2, .03), (.4, -.4, .04), (.1, .6, .02)):
                z = z + amp * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * .05 ** 2))
            chunks.append(to_source(np.column_stack([x, y, z])))
            ids.append(np.full(per, frame, dtype="i4"))
        points, ids = np.vstack(chunks), np.concatenate(ids)
        for eps in (.03, .05):
            with patch.dict(SHEET_PROFILE, {"eps_m": eps}):
                metrics = _sheet_metrics(points, ids, R, PLANE)
            self.assertGreaterEqual(metrics["largest_area_m2"], .5, metrics)
            self.assertGreaterEqual(metrics["effective_coverage"], .5, metrics)
            self.assertEqual(metrics["unexplained_gap_count"], 0, metrics)

    def test_small_satellite_fragment_ignored(self):
        rng = np.random.RandomState(19)
        floor, idf = slab((0, 2, 0, 2), rng)
        satellite, ids = slab((2.6, 2.75, 0.6, 0.75), rng)
        metrics = _sheet_metrics(*source_points([(floor, idf), (satellite, ids)]), R, PLANE)
        self.assertGreaterEqual(metrics["largest_area_m2"], .5)
        self.assertFalse(metrics["bridging_needed"])
        self.assertEqual(metrics["unexplained_gap_count"], 0)
        self.assertNotIn(1, metrics["significant_components"])

    def test_clean_cell_normal_direction_regression(self):
        points, ids = posts_floor(6, 6, {(0, 0), (2, 0), (0, 2), (2, 2)}, seed=20)
        clean = _clean_cells(points, ids, R, PLANE)
        keys = sorted(tuple(cell["key"]) for cell in clean)
        self.assertEqual(keys, [(0, 0), (0, 2), (2, 0), (2, 2)])
        for cell in clean:
            self.assertGreaterEqual(cell["local_normal_z"], .94)

    def test_v1_success_passthrough(self):
        points, ids, _ = v1_scene()
        expected = detect_floor_regions(points, ids, 26, 0)
        actual = detect_floor_regions_v2(points, ids, 26, 0)
        self.assertEqual(actual["regions"], expected["regions"])
        self.assertEqual(actual["candidate"], expected["candidate"])


if __name__ == "__main__":
    unittest.main()
