"""R3 单元测试：射线格、聚类、OBB、背景模型、前景判据、跟踪、逐帧检测、相机 2D。

跑法（仓库根目录）：
    python -B -W error -m unittest discover -s sidequests/plane_track/r03 -p "test_*.py"
"""
import unittest

import numpy as np

import plane_live_core as core


def synth_frame(targets, ring_rows=24, cols=64, noise=6, seed=0):
    """构造一帧：规则射线网格 + 3 m 墙面 + 指定目标球簇；返回 (xyz, ring, n_target_pts)。"""
    rng = np.random.default_rng(seed)
    rings = np.repeat(np.arange(ring_rows), cols)
    az = np.tile(np.linspace(-20.0, 20.0, cols), ring_rows)
    pts = []
    for (cx, cy, cz, r, n) in targets:
        u = rng.normal(size=(n, 3))
        u /= np.linalg.norm(u, axis=1, keepdims=True)
        pts.append(np.array([cx, cy, cz]) + u * r * rng.uniform(0.5, 1.0, size=(n, 1)))
    xyz_t = np.concatenate(pts) if pts else np.zeros((0, 3))
    rr = 3.0 + rng.normal(scale=0.002, size=len(rings))
    wall = np.stack([rr * np.cos(np.radians(az)), rr * np.sin(np.radians(az)),
                     np.zeros(len(rings))], axis=1)
    noise_pts = rng.normal(scale=0.001, size=(noise, 3)) + np.array([6.0, 0.0, 0.0])
    xyz = np.concatenate([wall, xyz_t, noise_pts])
    ring = np.concatenate([rings, np.zeros(len(xyz_t), dtype=np.int64),
                           np.zeros(noise, dtype=np.int64)])
    return xyz, ring, len(xyz_t)


def ready_background(frames=4, n_target=0):
    bg = core.BackgroundModel(frames=frames)
    for i in range(frames):
        xyz, ring, _ = synth_frame([(1.5, 0.2, 0.8, 0.06, n_target)] if n_target else [],
                                   seed=100 + i)
        cell, ok = core.ray_cells(xyz, ring)
        bg.observe(cell, ok, xyz)
    return bg


class TestRayCells(unittest.TestCase):
    def test_forward_center(self):
        xyz = np.array([[2.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        ring = np.array([10, 10])
        cell, ok = core.ray_cells(xyz, ring)
        self.assertTrue(ok.all())
        self.assertEqual(int(cell[0]), 10 * core.COLS + 128)

    def test_invalid_points(self):
        cell, ok = core.ray_cells(np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]), np.array([10, 999]))
        self.assertFalse(ok[0])
        self.assertFalse(ok[1])

    def test_grid_bounds(self):
        _, ok = core.ray_cells(np.array([[1.0, 20.0, 0.0], [1.0, -20.0, 0.0]]), np.array([5, 5]))
        self.assertFalse(ok.any())


class TestCluster(unittest.TestCase):
    def test_two_blobs(self):
        a = np.random.default_rng(1).normal(scale=0.02, size=(20, 3)) + [1, 2, 3]
        b = np.random.default_rng(2).normal(scale=0.02, size=(15, 3)) + [4, 2, 3]
        clusters = core.cluster_points(np.concatenate([a, b]), eps=0.09, min_points=5)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(sorted(len(c) for c in clusters), [15, 20])

    def test_small_cluster_dropped(self):
        a = np.random.default_rng(3).normal(scale=0.01, size=(12, 3)) + [1, 1, 1]
        b = np.zeros((3, 3)) + [5, 5, 5]
        clusters = core.cluster_points(np.concatenate([a, b]), eps=0.09, min_points=8)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]), 12)

    def test_chain_single_link(self):
        a = np.zeros((6, 3)) + [0, 0, 0]
        b = np.zeros((6, 3)) + [0.10, 0, 0]
        clusters = core.cluster_points(np.concatenate([a, b]), eps=0.09, min_points=5)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]), 12)


class TestObb(unittest.TestCase):
    def test_flat_plate(self):
        rng = np.random.default_rng(4)
        u = rng.uniform(-0.12, 0.12, size=(200, 1))
        v = rng.uniform(-0.06, 0.06, size=(200, 1))
        pts = np.concatenate([u, v, np.zeros_like(u)], axis=1)
        th = np.radians(30.0)
        rot = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1]])
        pts = pts @ rot.T + np.array([1.0, 2.0, 0.5])
        box = core.fit_obb(pts, pad=0.0, min_half=0.0)
        extent = np.sort(np.asarray(box["extent"]))
        self.assertAlmostEqual(extent[2], 0.24, delta=0.02)
        self.assertAlmostEqual(extent[1], 0.12, delta=0.02)
        self.assertAlmostEqual(extent[0], 0.00, delta=0.01)
        self.assertTrue(np.allclose(np.abs(box["axes"] @ box["axes"].T), np.eye(3), atol=1e-9))
        self.assertAlmostEqual(float(np.linalg.det(box["axes"])), 1.0, places=9)

    def test_axes_stable_sign(self):
        rng = np.random.default_rng(5)
        pts = rng.normal(scale=[0.15, 0.05, 0.03], size=(80, 3))
        b1 = core.fit_obb(pts)
        b2 = core.fit_obb(pts * 1.0)
        axis = b1["axes"][0]
        self.assertGreaterEqual(axis[int(np.argmax(np.abs(axis)))], 0.0)
        self.assertTrue(np.allclose(b1["axes"], b2["axes"]))


class TestBackground(unittest.TestCase):
    def test_window_then_ready(self):
        bg = core.BackgroundModel(frames=4)
        for i in range(3):
            xyz, ring, _ = synth_frame([], seed=i)
            cell, ok = core.ray_cells(xyz, ring)
            bg.observe(cell, ok, xyz)
            self.assertFalse(bg.ready)
        xyz, ring, _ = synth_frame([], seed=9)
        cell, ok = core.ray_cells(xyz, ring)
        bg.observe(cell, ok, xyz)
        self.assertTrue(bg.ready)
        self.assertEqual(bg.seen, 4)
        finite = np.isfinite(bg.range_map)
        self.assertGreater(int(finite.sum()), 100)
        self.assertTrue(np.all(bg.range_map[finite] > 0.5))

    def test_frozen_after_ready(self):
        bg = ready_background(frames=3)
        before = bg.range_map.copy()
        xyz, ring, _ = synth_frame([(1.5, 0.2, 0.8, 0.06, 12)], seed=77)
        cell, ok = core.ray_cells(xyz, ring)
        bg.observe(cell, ok, xyz)          # ready 后不应再改背景
        np.testing.assert_allclose(before, bg.range_map, equal_nan=True)
        self.assertEqual(bg.seen, 3)

    def test_points_map_consistent(self):
        bg = ready_background(frames=4)
        finite = np.isfinite(bg.range_map)
        self.assertTrue(np.allclose(np.linalg.norm(bg.points_map[finite], axis=1),
                                    bg.range_map[finite], atol=1e-6))


class TestForeground(unittest.TestCase):
    def test_closer_return_is_foreground(self):
        bg = ready_background(frames=4)
        cell = np.array([0 * core.COLS + 128])
        ok = np.array([True])
        pts = np.array([[1.0, 0.0, 0.0]])
        mask = core.foreground_mask(pts, cell, ok, bg)
        self.assertTrue(mask[0])

    def test_same_surface_not_foreground(self):
        bg = ready_background(frames=4)
        xyz, ring, _ = synth_frame([], seed=3)
        cell, ok = core.ray_cells(xyz, ring)
        mask = core.foreground_mask(xyz, cell, ok, bg, drop=10.0)  # 关掉距离判据
        self.assertLess(float(mask.mean()), 0.02)

    def test_off_surface_point_is_foreground(self):
        bg = ready_background(frames=4)
        # 墙面上方 8 cm 的一个点：距离判据不动，靠 3D 新点判据
        pts = np.array([[3.0, 0.0, 0.08]])
        cell, ok = core.ray_cells(pts, np.array([0]))
        mask = core.foreground_mask(pts, cell, ok, bg, drop=10.0)
        self.assertTrue(mask[0])


class TestDetectFrame(unittest.TestCase):
    def _run(self, frames_targets, **kw):
        bg = core.BackgroundModel(frames=kw.pop("bg_frames", 3))
        trk = core.PlaneTracker(**kw.pop("tracker", {}))
        out = []
        for i, targets in enumerate(frames_targets):
            xyz, ring, n_t = synth_frame(targets, seed=i)
            out.append(core.detect_frame(xyz, ring, bg, trk, i, 0.1, **kw))
            out[-1]["n_target"] = n_t
        return out

    def test_bootstrap_then_no_target(self):
        res = self._run([[] for _ in range(8)])
        for i in range(3):
            self.assertTrue(res[i]["bootstrap"])
            self.assertIsNone(res[i]["target"])
        for row in res[3:]:
            self.assertIsNone(row["target"])

    def test_moving_target_confirmed_then_rest(self):
        targets = [[] for _ in range(3)]
        targets += [[(1.2, 0.4, 0.8, 0.06, 25)],
                    [(1.5, 0.4, 0.8, 0.06, 25)],
                    [(1.8, 0.4, 0.8, 0.06, 25)],
                    [(2.0, 0.4, 0.8, 0.06, 25)],
                    [(2.0, 0.4, 0.8, 0.06, 25)],
                    [(2.0, 0.4, 0.8, 0.06, 25)],
                    [(2.0, 0.4, 0.8, 0.06, 25)]]
        res = self._run(targets)
        self.assertIsNone(res[2]["target"])
        first = res[3]["target"]
        self.assertIsNotNone(first)
        self.assertFalse(first["confirmed"])
        self.assertTrue(any(res[i]["target"] and res[i]["target"]["confirmed"] for i in range(4, 10)))
        last = res[9]["target"]
        self.assertEqual(last["track_id"], first["track_id"])
        np.testing.assert_allclose(last["center"], [2.0, 0.4, 0.8], atol=0.12)
        self.assertGreaterEqual(last["point_count"], 16)

    def test_noise_cluster_rejected(self):
        targets = [[] for _ in range(8)]
        targets[7] = [(1.0, 0.0, 0.5, 0.03, 6)]
        res = self._run(targets)
        self.assertIsNone(res[-1]["target"])

    def test_big_scene_cluster_rejected(self):
        rng = np.random.default_rng(11)
        big = rng.uniform(-0.9, 0.9, size=(120, 3)) + np.array([2.0, 0.0, 1.0])
        targets = [[] for _ in range(8)]
        res = self._run(targets + [])  # 背景先建立
        bg = core.BackgroundModel(frames=3)
        trk = core.PlaneTracker()
        for i in range(3):
            xyz, ring, _ = synth_frame([], seed=i)
            cell, ok = core.ray_cells(xyz, ring)
            bg.observe(cell, ok, xyz)
        xyz, ring, _ = synth_frame([(2.0, 0.0, 1.0, 0.0, 0)], seed=99)
        xyz = np.concatenate([xyz, big])
        ring = np.concatenate([ring, np.zeros(len(big), dtype=np.int64)])
        out = core.detect_frame(xyz, ring, bg, trk, 3, 0.1)
        self.assertIsNone(out["target"])


class TestTracker(unittest.TestCase):
    def test_gate_and_id(self):
        trk = core.PlaneTracker(gate_m=0.5, confirm_hits=3)
        trk.step(0, 0.1, [dict(center=np.array([0.0, 0.0, 0.0]), box={}, points=np.zeros((20, 3)))])
        far = [dict(center=np.array([3.0, 0.0, 0.0]), box={}, points=np.zeros((20, 3)))]
        links = trk.step(1, 0.1, far)
        self.assertEqual(len(links), 1)
        self.assertNotEqual(links[0][0].id, 1)

    def test_confirm_by_move(self):
        trk = core.PlaneTracker(gate_m=1.0, confirm_hits=10, confirm_move_m=0.30)
        trk.step(0, 0.1, [dict(center=np.array([0.0, 0.0, 0.0]), box={}, points=np.zeros((9, 3)))])
        links = trk.step(1, 0.1, [dict(center=np.array([0.4, 0.0, 0.0]), box={}, points=np.zeros((9, 3)))])
        self.assertTrue(links[0][0].confirmed)

    def test_miss_removes_track(self):
        trk = core.PlaneTracker(max_misses=1)
        trk.step(0, 0.1, [dict(center=np.zeros(3), box={}, points=np.zeros((9, 3)))])
        trk.step(1, 0.1, [])
        trk.step(2, 0.1, [])
        self.assertEqual(trk.tracks, [])


class TestCamera(unittest.TestCase):
    def _frames(self, n=24, w=160, h=120):
        base = 120 * np.ones((h, w), dtype=np.float32)
        out = [base.copy() for _ in range(n)]
        for i in range(8, 16):
            x = 10 + 12 * (i - 8)
            out[i][40:60, x:x + 14] = 240.0
        return out

    def test_moving_bright_blob(self):
        boxes, bg = core.camera_boxes(self._frames(), min_area=20, min_travel_px=40.0,
                                      link_px=40.0, max_side=80)
        hits = [b for b in boxes if b]
        self.assertGreaterEqual(len(hits), 6)
        self.assertIsNotNone(bg)
        self.assertLess(hits[0]["x0"], hits[-1]["x0"])

    def test_empty_scene(self):
        frames = [np.zeros((60, 80), dtype=np.float32) for _ in range(6)]
        boxes, _ = core.camera_boxes(frames)
        self.assertTrue(all(b is None for b in boxes))


if __name__ == "__main__":
    unittest.main()