import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import numpy as np

from human_pointset import TargetPointCache, crop_rows, sample_rows, transform_joints
from prepare_human_pointset import run


class HumanPointsetTest(unittest.TestCase):
    def test_crop_transform_source_rows_and_invalid(self):
        joints = np.array([[0., 0., 0.], [1., 1., 1.]])
        matrix = np.eye(4)
        matrix[:3, 3] = [3, 0, 0]
        cloud = np.array([[0, 0, 0], [3, 0, 0], [4.25, 1.25, 1.25], [4.251, 1, 1]])
        np.testing.assert_array_equal(crop_rows(cloud, joints, matrix), [1, 2])
        np.testing.assert_array_equal(cloud[crop_rows(cloud, joints, matrix)], cloud[[1, 2]])
        for bad in [np.zeros((4, 4)), np.diag([-1, 1, 1, 1]), np.eye(4)*2,
                    np.full((4, 4), np.nan)]:
            with self.assertRaises(ValueError): transform_joints(joints, bad)
        for margin in [-1, np.nan, np.inf]:
            with self.assertRaises(ValueError): crop_rows(cloud, joints, matrix, margin)
        for bad in [np.zeros((0, 3)), np.full((17, 3), np.nan), np.zeros((17, 2))]:
            with self.assertRaises(ValueError): crop_rows(cloud, bad, matrix)

    def test_sampling_matches_frozen_baseline_and_is_source_only(self):
        cloud = np.arange(60).reshape(20, 3)
        key = 'E01/S01/A12/lidar/frame001.bin'
        seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], 'little')
        expected = np.random.default_rng(seed).choice(20, 16, replace=False)
        np.testing.assert_array_equal(sample_rows(cloud, 16, key), expected)
        self.assertEqual(len(set(sample_rows(cloud, 16, key))), 16)
        repeated = sample_rows(cloud, 256, key)
        self.assertEqual(len(repeated), 256)
        np.testing.assert_array_equal(repeated, sample_rows(cloud, 256, key))
        with self.assertRaises(ValueError): sample_rows(cloud[:9], 256, key)

    def test_target_windows_and_lifecycle(self):
        cloud = np.arange(90).reshape(30, 3)
        rows = np.arange(2, 20)
        cache = TargetPointCache(window=3, points=16)
        def push(t, identity='a', generation=1, calibration='c', **kwargs):
            return cache.push(cloud, rows, t, identity, generation, calibration, str(t), **kwargs)
        self.assertIsNone(push(0))
        self.assertIsNone(push(.1))
        window = push(.2)
        self.assertEqual(window.shape, (3, 16, 3))
        np.testing.assert_array_equal(window[-1], cloud[cache.last_sample_rows])
        self.assertTrue(set(cache.last_sample_rows) <= set(rows))
        saved = window.copy()
        push(.3)
        np.testing.assert_array_equal(window, saved)
        for t, binding in [(.4, ('b', 1, 'c')), (.5, ('b', 2, 'c')), (.6, ('b', 2, 'd')),
                           (2., ('b', 2, 'd')), (1., ('b', 2, 'd')), (1., ('b', 2, 'd'))]:
            self.assertIsNone(push(t, *binding))
            self.assertEqual(len(cache.frames), 1)
        self.assertIsNone(push(1.1, locked=False))
        self.assertEqual(len(cache.frames), 0)
        push(1.2)
        self.assertIsNone(push(1.3, predicted=True))
        self.assertEqual(len(cache.frames), 0)
        for bad in [np.arange(9), np.array([2]*12), np.arange(12)+50, np.arange(12)*1.,
                    np.arange(-1, 12)]:
            push(2)
            with self.assertRaises(ValueError): cache.push(cloud, bad, 2.1, 'a', 1, 'c', 'bad')
            self.assertEqual(len(cache.frames), 0)
        with self.assertRaises(ValueError): push(float('nan'))
        self.assertEqual(len(cache.frames), 0)
        for binding in [(('sid', None), 1, 'c'), ('a', (0, None), 'c'), ('a', 1, ('sha', None)),
                        ('', 1, 'c')]:
            with self.assertRaises(ValueError): push(3, *binding)
            self.assertEqual(len(cache.frames), 0)

    def test_frame_pairing_rejects_missing_numbers_and_bad_gt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for case, numbers, joints in [('gap', [1, 3], np.zeros((2, 17, 3))),
                                          ('count', [1, 2], np.zeros((3, 17, 3))),
                                          ('nonfinite', [1, 2], np.full((2, 17, 3), np.nan))]:
                archive = root/(case+'.zip')
                buffer = io.BytesIO()
                np.save(buffer, joints)
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr('E01/S01/A01/ground_truth.npy', buffer.getvalue())
                    for i in numbers:
                        z.writestr('E01/S01/A01/lidar/frame%03d.bin' % i, np.zeros((12, 3), '<f8').tobytes())
                with self.assertRaises(ValueError): run(archive, root/case)
                self.assertFalse((root/case/'points256.npz').exists())

    def test_archive_to_cache_and_no_silent_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root/'source.zip'
            sequence = 'E01/S01/A01'
            gt = np.zeros((3, 17, 3))
            buffer = io.BytesIO()
            np.save(buffer, gt)
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr(sequence+'/ground_truth.npy', buffer.getvalue())
                for i in range(1, 4):
                    z.writestr(sequence+'/lidar/frame%03d.bin' % i, np.zeros((12, 3), '<f8').tobytes())
            with self.assertRaises(ValueError): run(archive, root/'forbidden', prepare=True)
            self.assertFalse((root/'forbidden').exists())
            evidence = root/'calibration.json'
            evidence.write_text('{"scope":"synthetic test extrinsics only"}', encoding='utf-8')
            transform = root/'transform.json'
            contract = {'joint_to_lidar': np.eye(4).tolist(), 'status': 'verified', 'units': 'm',
                        'evidence': {'path': evidence.name, 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}}
            transform.write_text(json.dumps(contract), encoding='utf-8')
            result = run(archive, root/'ok', transform=transform, prepare=True)
            self.assertTrue(result['cache_published'])
            with np.load(root/'ok/points256.npz', allow_pickle=False) as cache:
                self.assertEqual(cache[sequence].shape, (3, 256, 3))
            # Misalignment leaves every frame in ledger and publishes no cache.
            contract['joint_to_lidar'][0][3] = 10
            transform.write_text(json.dumps(contract), encoding='utf-8')
            with self.assertRaises(ValueError): run(archive, root/'empty', transform=transform, prepare=True)
            self.assertFalse((root/'empty/points256.npz').exists())
            self.assertEqual(len((root/'empty/frames.jsonl').read_text().splitlines()), 3)
            self.assertEqual(json.loads((root/'empty/INPUT.json').read_text())['insufficient_frames'], 3)
            contract['evidence']['sha256'] = 'wrong'
            transform.write_text(json.dumps(contract), encoding='utf-8')
            with self.assertRaises(ValueError): run(archive, root/'unbound', transform=transform, prepare=True)
            self.assertFalse((root/'unbound').exists())


if __name__ == '__main__':
    unittest.main()
