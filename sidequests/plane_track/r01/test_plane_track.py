"""PLANE-01 自检：候选层/跟踪/泄漏判据的最小回归。

运行：python -B -W error -m unittest test_plane_track -v
（仓库 A08 的既有套件不包含本目录；本文件是本支线的单文件检查。）
"""
import unittest

import numpy as np

import plane_track as pt
from background import background_keys, foreground_mask


class StreakTest(unittest.TestCase):
    def test_streak_is_the_swept_length(self):
        head = np.array([[6.0, 0.0, 3.0]])
        streak_points = head + np.array([[0.0, 0.0, 0.0], [0.0, 0.5, 0.0]])
        length, direction = pt.streak_m(streak_points)
        self.assertAlmostEqual(length, 0.5, places=6)
        self.assertAlmostEqual(abs(direction[1]), 1.0, places=6)

    def test_single_point_has_no_streak(self):
        self.assertEqual(pt.streak_m(np.zeros((1, 3)))[0], 0.0)


class GateTest(unittest.TestCase):
    def _rows(self, offsets):
        rows = []
        for index, offset in enumerate(offsets):
            rows.append({"frame": index, "stamp_s": index * pt.FRAME_PERIOD_S, "candidate_count": 1,
                         "candidates": [{"point_count": 5, "center": [6.0, offset, 3.0],
                                         "streak_m": 0.0, "streak_direction": (0.0, 1.0),
                                         "range_median_m": 6.0, "intensity_median": 100.0}]})
        return rows

    def test_fast_target_steps_beyond_base_gate_are_followed_by_streak_gate(self):
        rows = self._rows([0.0, 0.515, 2 * 0.515, 3 * 0.515])
        for row in rows:
            row["candidates"][0]["streak_m"] = 0.515      # target already streaks in frame 0
        track_rows, _speeds, summary, _events = pt.track(rows, seed_center=[6.0, 0.0, 3.0])
        self.assertEqual(summary["detected_frames"], 4)
        self.assertEqual(summary["lost_frames"], 0)

    def test_first_frame_jump_without_streak_is_a_known_limitation(self):
        """A compact frame-0 object that jumps > base gate next frame is lost: the gate can
        only grow after a streak was observed. Documented, not fixed (see return PLANE-01)."""
        rows = self._rows([0.0, 0.515, 2 * 0.515, 3 * 0.515])
        track_rows, _speeds, summary, _events = pt.track(rows, seed_center=[6.0, 0.0, 3.0])
        self.assertEqual(summary["detected_frames"], 1)

    def test_static_target_keeps_the_base_gate(self):
        rows = self._rows([0.0, 0.05, 0.1])
        table, _speeds, summary, _events = pt.track(rows, seed_center=[6.0, 0.0, 3.0])
        self.assertTrue(all(row["detected"] for row in table))
        self.assertTrue(all(row["gate_m"] == pt.GATE_M for row in table))

    def test_target_leaving_the_gate_is_lost_not_reassigned(self):
        rows = self._rows([0.0, 0.05, 5.0, 5.0, 5.0, 5.0])
        table, _speeds, summary, _events = pt.track(rows, seed_center=[6.0, 0.0, 3.0])
        self.assertEqual(summary["detected_frames"], 2)
        self.assertEqual(summary["lost_frames"], 4)


class ReachableTest(unittest.TestCase):
    def test_reachable_distance_matches_the_density_model(self):
        self.assertAlmostEqual(pt.reachable_distance_m(area_m2=0.0117, threshold=25), 2.585, places=3)
        self.assertAlmostEqual(pt.reachable_distance_m(area_m2=0.0117, threshold=8), 4.570, places=3)


class CandidateLayerTest(unittest.TestCase):
    def test_sparse_streak_still_becomes_one_candidate(self):
        points = np.array([[6.0, y, 3.0] for y in np.linspace(0.0, 0.5, 5)])
        rows = pt.run_frames([(0, 0.0, points, None)], pt.snapshot_settings(), session_id="test")
        candidates = rows[0]["candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["point_count"], 5)
        self.assertAlmostEqual(candidates[0]["streak_m"], 0.5, places=4)

    def test_four_points_are_below_the_min_cluster_threshold(self):
        points = np.array([[6.0, y, 3.0] for y in np.linspace(0.0, 0.3, 4)])
        self.assertEqual(len(pt.frame_candidates(points, pt.snapshot_settings(), "test", 0, 0.0)), 0)


class BackgroundTest(unittest.TestCase):
    def test_leak_criterion_flags_only_missing_regions(self):
        empty = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]) + np.random.default_rng(7).normal(
            0, 0.005, size=(2, 3))
        keys, origin, base = background_keys(empty, 0.05)
        same = empty + np.random.default_rng(8).normal(0, 0.005, size=(2, 3))
        moved = same + np.array([[0.5, 0.0, 0.0]])
        self.assertFalse(foreground_mask(same, keys, origin, base, 0.05).any())
        self.assertTrue(foreground_mask(moved, keys, origin, base, 0.05).all())


class TbdTest(unittest.TestCase):
    def _frames(self):
        """三帧：一个 2.8 m/s 的动目标 + 一个静止泄漏簇。"""
        frames = []
        for k in range(3):
            stamp = k * 0.103
            center = np.array([1.0 + 2.8 * stamp, 1.0, 1.5])
            frames.append((k, stamp, [
                {"center": center, "points": 3, "weight": 3.0},
                {"center": np.array([9.2, 5.3, 0.0]), "points": 5, "weight": 5.0},
            ]))
        return frames

    def test_batch_tbd_finds_moving_hypothesis_and_separates_static(self):
        import tbd_track
        ranked, static_count = tbd_track.batch_tbd(self._frames())
        self.assertTrue(ranked, "moving hypotheses expected")
        best = ranked[0]
        self.assertGreaterEqual(best["best_window"], 2)
        self.assertGreater(float(np.linalg.norm(best["v_m_s"])), 2.0)
        self.assertGreaterEqual(static_count, 1)

    def test_kf_confirms_after_four_hits_and_coasts(self):
        import tbd_track
        frames = []
        for k in range(6):
            stamp = k * 0.103
            candidates = [{"center": np.array([1.0 + 2.8 * stamp, 1.0, 1.5]),
                           "points": 3, "weight": 3.0}]
            if k == 4:          # 第 5 帧丢一次，验证 coast 不掉
                candidates = []
            frames.append((k, stamp, candidates))
        rows, finished = tbd_track.run_kf(frames)
        self.assertEqual(len(finished), 1)
        self.assertTrue(finished[0]["confirmed"])
        self.assertEqual(finished[0]["hits"], 5)
        self.assertTrue(finished[0]["moving"])


if __name__ == "__main__":
    unittest.main()
