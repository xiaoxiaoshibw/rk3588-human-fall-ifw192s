"""E0/E1 测量工具自检（合成夹具，不碰真实源）。python -B -W error -m unittest test_measure"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import source_io as sio


def make_session(folder, rows_per_frame=6):
    rows = []
    for f in range(2):
        for i in range(rows_per_frame):
            x, y, z = 1.0 + f, 2.0 + i, 3.0 - i
            tail = bytes(range(12, 28))
            rows.append(np.array([x, y, z], '<f4').tobytes() + tail)
    (folder / 'points.bin').write_bytes(b''.join(rows))
    meta = {'point_stride_bytes': 28,
            'frames': [{'stamp_sec': 100, 'stamp_nanosec': 0, 'count_points': rows_per_frame, 'offset_points': 0},
                       {'stamp_sec': 100, 'stamp_nanosec': 100000000, 'count_points': rows_per_frame, 'offset_points': rows_per_frame}]}
    (folder / 'meta.json').write_text(json.dumps(meta), encoding='utf8')
    return sio.Session(folder)


class Measure(unittest.TestCase):
    def test_source_rows_and_validity(self):
        with tempfile.TemporaryDirectory() as d:
            ses = make_session(Path(d))
            p = ses.xyz(1)
            self.assertEqual(p.shape, (6, 3))
            self.assertAlmostEqual(float(p[0, 0]), 2.0, places=5)
            self.assertAlmostEqual(float(p[5, 2]), -2.0, places=5)
            finite, valid = sio.validity(p)
            self.assertTrue(valid.all())
            p[0] = 0.0
            p[1] = np.nan
            finite, valid = sio.validity(p)
            self.assertEqual(int(valid.sum()), 4)
            self.assertEqual(int(finite.sum()), 5)

    def test_write_guards(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'x.json'
            sio.write_new(p, {'a': 1})
            with self.assertRaises(FileExistsError):
                sio.write_new(p, {'a': 2})
            with self.assertRaises(ValueError):
                sio.write_new(Path(d) / 'data' / 'y.json', {'a': 1})

    def test_grid_lock_detects_half_degree(self):
        sys.path.insert(0, str(HERE))
        import e0_density as e0
        az = np.arange(-180.0, 180.0, 0.5)
        self.assertGreater(e0.grid_lock(az, 0.5), 0.999)
        # 0.5° 网格同时锁定 0.25°（其倍数），锁不上更大的 1.0°
        self.assertGreater(e0.grid_lock(az, 0.25), 0.999)
        self.assertLess(e0.grid_lock(az, 1.0), 0.9)
        self.assertAlmostEqual(e0.empirical_step(az)[0], 0.5, delta=0.002)

    def test_nn_spacing_matches_grid_formula(self):
        import e0_density as e0
        # 单帧 0.5° 规则网格、固定距离 6m：最近邻应接近 R*tan(0.5°)
        az = np.radians(np.arange(-20.0, 20.0, 0.5))
        el = np.radians(np.arange(-5.0, 5.0, 0.5))
        a, e = np.meshgrid(az, el, indexing='ij')
        R = 6.0
        v = np.stack([R * np.cos(e) * np.cos(a), R * np.cos(e) * np.sin(a), R * np.sin(e)], -1).reshape(-1, 3)
        st = e0.spacing_by_band(v, np.linalg.norm(v, axis=1))
        med = st['[6,7)']['median']
        self.assertAlmostEqual(med, R * np.tan(np.radians(0.5)), delta=0.004)

    def test_band_peak_sign_convention(self):
        n = np.array([-0.4546594173329524, -0.02722635715441169, 0.8902491447378991])
        d = -1.3566335069482636
        rng = np.random.RandomState(7)
        plane = rng.randn(2000, 3) * 0.3
        plane[:, 2] = 0.0
        # 构造 n·p+d=0 上的点
        u = np.array([1.0, 0, 0])
        u = u - n * (u @ n)
        u /= np.linalg.norm(u)
        w_dir = np.cross(n, u)
        p = (rng.randn(2000, 1) * 0.5) * u + (rng.randn(2000, 1) * 0.5) * w_dir - d * n
        w = p @ n
        self.assertLess(abs(float(np.median(w)) + d), 0.02)


if __name__ == '__main__':
    unittest.main()
