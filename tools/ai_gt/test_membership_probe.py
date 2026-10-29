import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from membership_probe import RawSession
from joint_camera_probe import nearest_camera, recorded_frames


class MembershipProbeTest(unittest.TestCase):
    def fixture(self, folder):
        path = Path(folder)
        array = np.zeros(3, dtype=np.dtype({'names': ['xyz'], 'formats': [('<f4', 3)],
                                          'offsets': [0], 'itemsize': 28}))
        array['xyz'] = [[1, 2, 3], [0, 0, 0], [4, 5, 6]]
        (path / 'points.bin').write_bytes(array.tobytes())
        meta = dict(format_version=1, session_id='fixture', total_points=3,
            point_layout=dict(stride_bytes=28, fields=['x', 'y', 'z'], dtypes=['<f4'] * 3),
            frames=[dict(offset_points=0, count_points=3, bag_time_sec=10.0)])
        (path / 'meta.json').write_text(json.dumps(meta), encoding='utf8')
        return path, meta

    def test_original_zero_row_is_preserved_before_display_filter(self):
        with tempfile.TemporaryDirectory() as folder:
            path, _ = self.fixture(folder)
            source = RawSession(path)
            try:
                points, rows = source.frame(0)
                np.testing.assert_array_equal(rows, [0, 1, 2])
                np.testing.assert_array_equal(points[1], [0, 0, 0])
                with self.assertRaises(ValueError):
                    source.frame(-1)
                source.frames[0]['offset_points'] = 2
                with self.assertRaises(ValueError):
                    source.frame(0)
            finally:
                source.close()

    def test_truncated_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path, _ = self.fixture(folder)
            (path / 'points.bin').write_bytes(b'abc')
            with self.assertRaisesRegex(ValueError, 'byte count'):
                RawSession(path)

    def test_nearest_camera_keeps_signed_difference(self):
        rows = [dict(recv_unix_ns=9_900_000_000), dict(recv_unix_ns=10_200_000_000)]
        index, dt = nearest_camera(rows, 10.0)
        self.assertEqual(index, 0)
        self.assertAlmostEqual(dt, -0.1)

    def test_bad_camera_clock_is_rejected(self):
        for rows in [[], [dict(recv_unix_ns=1), dict(recv_unix_ns=1)],
                     [dict(recv_unix_ns=2), dict(recv_unix_ns=1)]]:
            with self.assertRaises(ValueError):
                nearest_camera(rows, 10.0)
        with self.assertRaises(ValueError):
            nearest_camera([dict(recv_unix_ns=1)], float('nan'))

    def test_camera_range_outside_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path, _ = self.fixture(folder)
            (path / 'camera_frames.jsonl').write_text(json.dumps(dict(
                offset=1, length=20, recv_unix_ns=10_000_000_000)), encoding='utf8')
            (path / 'camera.mjpeg').write_bytes(b'\xff\xd8\xff\xd9')
            with self.assertRaisesRegex(ValueError, 'byte range'):
                recorded_frames(path, [0])


if __name__ == '__main__':
    unittest.main()
