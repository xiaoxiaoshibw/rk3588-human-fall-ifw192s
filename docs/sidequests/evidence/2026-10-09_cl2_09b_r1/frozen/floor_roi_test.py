"""GL-S02 lowest_floor_sheet_v3_fine_roi synthetic regression.

Reuses the GL-S01 scene builders with known ground truth. All gates are the
production ones; no scene-side tuning.
"""
import unittest

import numpy as np

from floor_detector import detect_floor_regions
from floor_detector_test import scene as v1_scene
from floor_roi import FINE_PROFILE, detect_floor_regions_v3, fine_boxes
from floor_sheet import detect_floor_regions_v2
from floor_sheet_test import R, PLANE, post, posts_floor, slab, source_points


class FineRoiTest(unittest.TestCase):
    def test_fine_roi_succeeds_where_25cm_fails(self):
        points, ids = posts_floor(6, 6, set(), seed=22)
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_CLEAN_ROI_SUPPORT"):
            detect_floor_regions_v2(points, ids, 26, 0)
        result = detect_floor_regions_v3(points, ids, 26, 0)
        candidate = result["candidate"]
        self.assertEqual(candidate["kind"], "lowest_floor_sheet_v3_fine_roi")
        self.assertGreaterEqual(candidate["roi"]["clean_boxes"], 4)
        self.assertGreaterEqual(candidate["roi"]["min_sep_m"], .5)
        self.assertEqual(candidate["roi"]["independent_count"], 4)
        self.assertGreaterEqual(candidate["roi"]["condition"], .1)
        self.assertTrue(candidate["full_height_preserved"])
        self.assertFalse(candidate["uses_manual_reference"])
        regions = result["regions"]
        self.assertEqual(len(regions), 4)
        for xl, xh, yl, yh in regions:
            self.assertAlmostEqual(xh - xl, FINE_PROFILE["grid_m"], places=9)
            self.assertAlmostEqual(yh - yl, FINE_PROFILE["grid_m"], places=9)
        centers = np.array([[(r[0] + r[1]) / 2, (r[2] + r[3]) / 2] for r in regions])
        dist = np.hypot(centers[:, None, 0] - centers[None, :, 0],
                        centers[:, None, 1] - centers[None, :, 1])
        np.fill_diagonal(dist, np.inf)
        self.assertGreaterEqual(float(dist.min()), .5)

    def test_fine_roi_insufficient_when_even_fine_dirty(self):
        rng = np.random.RandomState(23)
        chunks = [slab((0, 1.5, 0, 1.5), rng)]
        for ix in range(15):
            for iy in range(15):
                chunks.append(post((ix + .5) * .1, (iy + .5) * .1, rng,
                                   radius=.015, height=.4, per=40))
        points, ids = source_points(chunks)
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_CLEAN_ROI_SUPPORT"):
            detect_floor_regions_v3(points, ids, 26, 0)

    def test_v3_returns_v2_verbatim_when_25cm_ok(self):
        points, ids = posts_floor(6, 6, {(0, 0), (2, 0), (0, 2), (2, 2)}, seed=24)
        v2 = detect_floor_regions_v2(points, ids, 26, 0)
        self.assertEqual(detect_floor_regions_v3(points, ids, 26, 0), v2)

    def test_v3_returns_v1_verbatim(self):
        points, ids, _ = v1_scene()
        expected = detect_floor_regions(points, ids, 26, 0)
        self.assertEqual(detect_floor_regions_v3(points, ids, 26, 0), expected)

    def test_v3_identity_rejected(self):
        rng = np.random.RandomState(25)
        rects = [(0, .5, 0, .5), (2, 2.5, 0, .5), (0, .5, 2, 2.5), (2, 2.5, 2, 2.5)]
        points, ids = source_points([slab(rect, rng) for rect in rects])
        with self.assertRaisesRegex(ValueError, "floor_regions_invalid"):
            detect_floor_regions_v3(points, ids, 26, 0)

    def test_fine_boxes_keep_purity_gates(self):
        points, ids = posts_floor(6, 6, set(), seed=26)
        boxes = fine_boxes(points, ids, R, PLANE)
        self.assertGreaterEqual(len(boxes), 4)
        for box in boxes:
            self.assertLessEqual(box["height_span_m"], .18)
            self.assertGreaterEqual(box["normal_z"], .94)
            self.assertLessEqual(box["rms_m"], .025)
            self.assertGreaterEqual(box["min_frame_count"], FINE_PROFILE["min_points_per_frame"])


if __name__ == "__main__":
    unittest.main()
