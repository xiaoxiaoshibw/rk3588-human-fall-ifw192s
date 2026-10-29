"""session_compare 契约测试（run: python -B -W error -m unittest discover -s pc_apps/range_fall -p "test_*.py"）。"""
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import session_compare as sc  # noqa: E402

REAL_SESSION = sc.ROOT / 'data' / 'sessions' / 'cap_20261023_221125'


def synthetic_plane(count, normal, offset, noise=0.004, seed=3):
    """平面点云：法向已知，便于验证拟合（随机切向基）。"""
    normal = np.asarray(normal, dtype=np.float64)
    normal = normal / np.linalg.norm(normal)
    seed_vec = np.array([0.0, 1.0, 0.0]) if abs(normal[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(normal, seed_vec)
    u = u / np.linalg.norm(u)
    v = np.cross(normal, u)
    rng = np.random.default_rng(seed)
    uv = rng.uniform(-2.5, 2.5, size=(count, 2))
    plane = -offset * normal
    points = (plane[None, :] + uv[:, :1] * u[None, :] + uv[:, 1:] * v[None, :]
              + rng.normal(0.0, noise, size=(count, 1)) * normal[None, :])
    return points


class GroundTest(unittest.TestCase):
    def test_recovers_tilted_floor_and_ignores_clutter_above(self):
        normal = np.array([0.42, 0.01, 0.907])
        floor = synthetic_plane(12000, normal, 1.31)
        rng = np.random.default_rng(11)
        clutter = rng.uniform(-2.0, 2.0, size=(4000, 3))
        clutter[:, 2] += 2.6  # 桌面/墙面上方的杂物，不应主导拟合
        fit = sc.fit_ground(np.vstack([floor, clutter]), seed=sc.SEED)
        unit = np.asarray(fit['normal']) / np.linalg.norm(fit['normal'])
        reference = normal / np.linalg.norm(normal)
        self.assertLess(math.degrees(math.acos(min(1.0, abs(float(unit @ reference))))), 0.5)
        self.assertAlmostEqual(fit['offset_m'], 1.31, delta=0.03)
        self.assertAlmostEqual(fit['sensor_height_m'], fit['offset_m'], places=9)
        self.assertFalse(fit['physical_verified'])
        self.assertGreater(fit['above_fraction'], 0.2)

    def test_choice_prefers_floor_over_ceiling(self):
        normal = np.array([0.0, 0.0, 1.0])
        floor = synthetic_plane(8000, normal, 1.4)
        ceiling = floor.copy()
        ceiling[:, 2] += 2.8  # 更高的平面，点数相同
        fit = sc.fit_ground(np.vstack([floor, ceiling]), seed=sc.SEED)
        self.assertAlmostEqual(fit['offset_m'], 1.4, delta=0.05)
        self.assertGreater(fit['above_fraction'], 0.2)

    def test_rejects_degenerate_input(self):
        with self.assertRaises(sc.SessionCompareError):
            sc.fit_ground(np.zeros((10, 3)))
        with self.assertRaises(sc.SessionCompareError):
            sc.fit_ground(np.full((500, 3), np.nan))


class BackgroundTest(unittest.TestCase):
    def test_high_quantile_keeps_far_background_and_masks_rare_cells(self):
        frames, height, width = 30, 4, 4
        stack = np.full((frames, height, width), 5.0, dtype=np.float32)
        stack[0:3, 0, 0] = 2.0      # 人挡住 3 帧 → 背景仍是 5 m
        stack[:, 0, 1] = 1.0        # 一直很近的静态物体 → 背景 1 m
        stack[0:5, 0, 2] = np.nan  # 只观测 25 帧
        stack[5:, 0, 2] = 3.0
        stack[:, 0, 3] = np.nan     # 从未观测 → 必须排除且不告警
        observed = np.isfinite(stack).sum(axis=0).astype(np.int32)
        background = sc.background_range(stack, observed)
        self.assertAlmostEqual(float(background[0, 0]), 5.0, places=5)
        self.assertAlmostEqual(float(background[0, 1]), 1.0, places=5)
        self.assertAlmostEqual(float(background[0, 2]), 3.0, places=5)
        self.assertTrue(np.isnan(background[0, 3]))
        self.assertTrue(np.isfinite(background[1:, :]).all())


class GeometryTest(unittest.TestCase):
    def setUp(self):
        self.normal = np.array([0.42, 0.01, 0.907])
        self.normal = self.normal / np.linalg.norm(self.normal)
        self.offset = 1.31
        self.basis = sc.display_basis(self.normal)

    def test_basis_is_right_handed_orthonormal(self):
        basis = self.basis
        np.testing.assert_allclose(basis @ basis.T, np.eye(3), atol=1e-12)
        self.assertAlmostEqual(float(np.linalg.det(basis)), 1.0, places=9)
        np.testing.assert_allclose(basis[2], self.normal, atol=1e-12)

    def test_ground_points_land_on_display_zero(self):
        floor = synthetic_plane(200, self.normal, self.offset, noise=0.0)
        display = sc.to_display(floor, self.basis, self.offset)
        np.testing.assert_allclose(display[:, 2], 0.0, atol=1e-9)
        self.assertTrue(np.isfinite(display).all())

    def test_voxel_pick_dedupes_caps_and_is_deterministic(self):
        points = np.repeat(np.array([[1.0, 2.0, 0.5]]), 50, axis=0)
        points = np.vstack([points, np.random.default_rng(5).uniform(-1, 3, size=(400, 3))])
        picked = sc.voxel_pick(points, 0.03, 20, 'frame:0')
        self.assertLessEqual(len(picked), 20)
        self.assertGreater(len(picked), 1)
        again = sc.voxel_pick(points, 0.03, 20, 'frame:0')
        np.testing.assert_array_equal(picked, again)
        unique_cells = len(np.unique(np.floor(points / 0.03).astype(np.int64), axis=0))
        self.assertGreaterEqual(unique_cells, len(picked))

    def test_quantize_is_centimetre_integer(self):
        values = sc.quantize(np.array([[0.0, 0.014, -0.02], [1.234, 2.5, -1.0]]))
        self.assertEqual(values, [0, 1, -2, 123, 250, -100])
        self.assertTrue(all(isinstance(value, int) for value in values))


class CameraTest(unittest.TestCase):
    def _write_session(self, root, rows, blob):
        root.mkdir(parents=True, exist_ok=True)
        (root / 'camera.mjpeg').write_bytes(blob)
        (root / 'camera_frames.jsonl').write_text(
            '\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf8')

    def test_nearest_frame_and_time_delta(self):
        rows = [dict(offset=0, length=4, recv_unix_ns=10_000_000_000),
                dict(offset=4, length=4, recv_unix_ns=10_100_000_000),
                dict(offset=8, length=4, recv_unix_ns=10_200_000_000)]
        index, delta = sc.nearest_camera(rows, 10.06)
        self.assertEqual(index, 1)
        self.assertAlmostEqual(delta, 0.04, places=6)
        index, delta = sc.nearest_camera(rows, 9.99)
        self.assertEqual(index, 0)
        self.assertGreater(delta, 0)  # 相机接收时刻晚于雷达帧时刻 → 正
        index, delta = sc.nearest_camera(rows, 10.19)
        self.assertEqual(index, 2)
        self.assertAlmostEqual(delta, 0.01, places=6)

    def test_read_camera_validates_ranges_markers_and_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 's1'
            good = b'\xff\xd8AAA\xff\xd9'  # 7 字节完整 JPEG
            self._write_session(root, [dict(offset=0, length=7, recv_unix_ns=1),
                                       dict(offset=7, length=7, recv_unix_ns=2)], good + good)
            rows, blob = sc.read_camera(root)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(blob), 14)

            self._write_session(root, [dict(offset=0, length=7, recv_unix_ns=2),
                                       dict(offset=7, length=7, recv_unix_ns=1)], good + good)
            with self.assertRaises(sc.SessionCompareError):
                sc.read_camera(root)

            self._write_session(root, [dict(offset=0, length=6, recv_unix_ns=1)], b'\xff\xd8AAA\xff')
            with self.assertRaises(sc.SessionCompareError):
                sc.read_camera(root)

    def test_missing_camera_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(sc.read_camera(Path(tmp)))


class OutputGuardTest(unittest.TestCase):
    def test_refuses_output_inside_source_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = sc.ROOT / 'data' / 'sessions' / '__compare_guard__'
            with self.assertRaises(sc.SessionCompareError):
                sc.build(Path(tmp), target, limit=1, preview=False)
            with self.assertRaises(sc.SessionCompareError):
                sc.build(Path(tmp), Path(tmp), limit=1, preview=False)


@unittest.skipUnless(REAL_SESSION.is_dir(), '本地真实会话不可用，跳过集成用例')
class RecordedSessionTest(unittest.TestCase):
    """真实会话端到端：验证产物/绑定/单人绿框/跌倒候选，不评价效果。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'out'
        cls.summary = sc.build(REAL_SESSION, cls.out, preview=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_artifacts_exist_and_template_fully_substituted(self):
        for name in ('index.html', 'data/frames.js', 'SUMMARY.json', 'FRAMES.jsonl',
                     'GROUND.json'):
            self.assertTrue((self.out / name).is_file(), name)
        html = (self.out / 'index.html').read_text(encoding='utf8')
        self.assertNotIn('@@', html)
        self.assertIn('window.FRAMES', (self.out / 'data/frames.js').read_text(encoding='utf8'))
        self.assertTrue((self.out / 'camera').is_dir())
        self.assertEqual(len(list((self.out / 'camera').glob('*.jpg'))), 123)

    def test_summary_binds_source_and_declares_unknowns(self):
        summary = json.loads((self.out / 'SUMMARY.json').read_text(encoding='utf8'))
        self.assertEqual(summary['schema'], sc.SCHEMA)
        self.assertEqual(summary['session'], REAL_SESSION.name)
        self.assertEqual(summary['source']['frames'], 126)
        self.assertEqual(summary['camera_pairing']['pairs'], 126)
        self.assertLess(summary['camera_pairing']['max_abs_dt_s'], 0.2)
        self.assertFalse(summary['camera_pairing']['hardware_sync'])
        self.assertEqual(summary['honesty']['human_gt'], 'UNKNOWN')
        self.assertEqual(summary['honesty']['fall_gt'], 'UNKNOWN')
        self.assertFalse(summary['honesty']['physical_verified'])
        self.assertFalse(summary['honesty']['deployed'])
        self.assertFalse(summary['ground']['physical_verified'])
        self.assertEqual(summary['fall']['events'], [])
        self.assertFalse(summary['fall']['confirmed_enabled'])
        self.assertEqual(list(summary['tracking']['selected_tracks']), ['g0_t0001'])

    def test_single_person_box_and_fall_candidate_are_present(self):
        summary = self.summary
        self.assertGreaterEqual(summary['tracking']['frames_with_target'], 100)
        rows = [json.loads(line) for line in (self.out / 'FRAMES.jsonl').read_text(encoding='utf8').splitlines()]
        alarms = [row for row in rows if row['st'] in sc.ALARM_STATES]
        self.assertEqual(summary['fall']['alarm_frames'], len(alarms))
        self.assertEqual(summary['fall']['first_alarm_s'], alarms[0]['t'] if alarms else None)
        self.assertIn('跌倒嫌疑' if alarms else '本段未触发跌倒候选', summary['verdict'])

    def test_offline_view_runs_shared_core_runtime_with_declared_inputs(self):
        summary = self.summary
        self.assertEqual(summary['pipeline']['module'], 'core.range_runtime.RangeRuntime')
        self.assertEqual(summary['pipeline']['background']['declaration'],
                         'offline_whole_recording_quantile')
        self.assertFalse(summary['pipeline']['background']['causal'])
        self.assertFalse(summary['pipeline']['background']['runtimeEligible'])
        self.assertTrue(summary['pipeline']['config']['background_non_causal'])
        self.assertEqual(summary['honesty']['core_pipeline'], 'core.range_runtime.RangeRuntime')
        self.assertIn('src/human_fall_detection/core/range_runtime.py', summary['sources'])
        self.assertIn('src/human_fall_detection/core/range_offline.py', summary['sources'])
        ground = json.loads((self.out / 'GROUND.json').read_text(encoding='utf8'))
        self.assertTrue(ground['offline_only'])
        self.assertFalse(ground['runtime_eligible'])
        self.assertFalse(ground['physical_verified'])

    def test_ledger_rows_match_frame_count_and_carry_state(self):
        rows = [json.loads(line) for line in
                (self.out / 'FRAMES.jsonl').read_text(encoding='utf8').splitlines()]
        self.assertEqual(len(rows), 126)
        for row in rows:
            self.assertIn(row['st'], ('unknown', 'upright', 'descending',
                                      'low_posture_unclassified', 'suspected',
                                      'confirmed', 'recovering'))
            self.assertIsInstance(row['i'], int)
            if row['n']:
                self.assertIsNotNone(row['hm'])
                self.assertEqual(len(row['bb']), 6)
                low = [value / 100.0 for value in row['bb']]
                self.assertGreater(low[3], low[0])
                self.assertGreater(low[4], low[1])


if __name__ == '__main__':
    unittest.main()
