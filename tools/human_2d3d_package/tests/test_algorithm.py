"""算法包自检：输入契约、2D→3D 来源行提升、跟踪、地面、部位、确定性与 JSON 安全。"""
import json
from pathlib import Path
import sys
import unittest

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

import human_2d3d
import synthetic

DT = 0.1
PREFIX = 10


def make(**kwargs):
    return human_2d3d.Human2D3D(calibration_dir=PACKAGE / 'calibration', session='unit',
                                empty_prefix_frames=PREFIX, **kwargs)


class Human2D3DTest(unittest.TestCase):
    def setUp(self):
        self.algorithm = make()
        self.background = synthetic.scene_rows(self.algorithm.grid)
        self.person = synthetic.scene_rows(self.algorithm.grid, person=True)

    def warm(self, algorithm=None):
        algorithm = self.algorithm if algorithm is None else algorithm
        result = None
        for index in range(PREFIX):
            result = algorithm.feed(self.background, index * DT, index)
        return result

    def lock(self, algorithm=None, extras=0):
        algorithm = self.algorithm if algorithm is None else algorithm
        self.warm(algorithm)
        result = None
        for step in range(3 + extras):
            index = PREFIX + step
            result = algorithm.feed(self.person, index * DT, index)
        return result

    def test_empty_prefix_is_explicit_and_tracking_needs_birth_window(self):
        first = self.warm()
        self.assertEqual(first['status'], 'prefix_warmup')
        self.assertEqual(first['image2d']['validCells'], int(np.prod(self.algorithm.grid.shape)))
        second = self.algorithm.feed(self.person, PREFIX * DT, PREFIX)
        third = self.algorithm.feed(self.person, (PREFIX + 1) * DT, PREFIX + 1)
        self.assertEqual(second['status'], 'ready')
        self.assertIsNone(second['target3d']['trackId'])
        self.assertIsNone(third['target3d']['trackId'])
        locked = self.algorithm.feed(self.person, (PREFIX + 2) * DT, PREFIX + 2)
        self.assertIsNotNone(locked['target3d']['trackId'])
        self.assertGreater(locked['target3d']['pointCount'], 0)
        self.assertFalse(locked['confirmedEnabled'])

    def test_two_dimensional_components_lift_to_the_same_measured_rows(self):
        locked = self.lock()
        retained = [c for c in locked['image2d']['components'] if c['retained']]
        self.assertEqual(len(retained), 1)
        component = retained[0]
        measured = np.column_stack((self.person['x'], self.person['y'],
                                    self.person['z'])).astype(np.float64)
        np.testing.assert_array_equal(component['xyz'], measured[component['sourceRows']])
        target = locked['target3d']
        np.testing.assert_array_equal(target['xyz'], measured[target['sourceRows']])
        self.assertTrue(set(target['sourceRows'].tolist())
                        <= set(component['sourceRows'].tolist()))
        labels = locked['image2d']['labels']
        np.testing.assert_array_equal(labels.ravel()[component['cells']],
                                      np.full(len(component['cells']), component['id']))
        self.assertEqual(locked['image2d']['foregroundCells'],
                         sum(c['points'] for c in locked['image2d']['components']))

    def test_invalid_rows_stamp_and_clock_are_rejected(self):
        with self.assertRaises(ValueError):
            make().feed(np.zeros(8, dtype=np.float64), 0.0, 0)
        with self.assertRaises(ValueError):
            make().feed(self.background, float('nan'), 0)
        with self.assertRaises(ValueError):
            make().feed(self.background.reshape(2, -1), 0.0, 0)
        with self.assertRaises(ValueError):
            make().feed(self.background, 0.0, 1)
        self.algorithm.feed(self.background, 0.0, 0)
        with self.assertRaises(ValueError):
            self.algorithm.feed(self.background, 0.0, 1)
        with self.assertRaises(ValueError):
            self.algorithm.feed(self.background, 0.2, 0)
        with self.assertRaises(ValueError):
            self.algorithm.feed(self.background, 0.2, True)

    def test_raw_bytes_are_accepted(self):
        result = make().feed(self.background.tobytes(), 0.0, 0)
        self.assertEqual(result['status'], 'prefix_warmup')

    def test_prefix_discontinuity_requires_a_rebind(self):
        for index in range(5):
            self.algorithm.feed(self.background, index * DT, index)
        broken = self.algorithm.feed(self.background, 5 * DT, 30)
        self.assertEqual(broken['status'], 'background_requires_explicit_rebind')
        for index in (31, 32, 33):
            result = self.algorithm.feed(self.person, index * DT, index)
            self.assertEqual(result['status'], 'background_requires_explicit_rebind')
            self.assertIsNone(result['target3d']['trackId'])

    def test_declared_ground_gives_ground_relative_height(self):
        self.algorithm.install_ground()
        locked = self.lock()
        height = locked['target3d']['heightM']
        self.assertIsNotNone(height)
        self.assertIsNone(locked['target3d']['heightReason'])
        self.assertGreater(height['median'], 0.0)
        self.assertLess(height['median'], 2.0)
        with self.assertRaises(ValueError):
            self.algorithm.install_ground(normal=(0.0, 0.0, 2.0))
        with self.assertRaises(ValueError):
            self.algorithm.install_ground(offset_m=float('inf'))
        with self.assertRaises(ValueError):
            self.algorithm.install_ground(frame_id='another_cloud')
        self.algorithm.clear_ground()
        self.assertIsNone(self.algorithm.runtime.ground)

    def test_skeleton_and_body_parts_use_only_locked_rows(self):
        algorithm = make(body_parts=True)
        algorithm.install_ground()
        locked = self.lock(algorithm)
        rows = set(locked['target3d']['sourceRows'].tolist())
        skeleton = locked['skeleton']
        self.assertIn('nodes', skeleton)
        for node in skeleton['nodes'].values():
            self.assertTrue(set(node['sourceRows']) <= rows)
        body = locked['bodyParts']
        self.assertIsNotNone(body)
        self.assertEqual(len(body['parts']), len(human_2d3d.BODY_NAMES))
        for part in body['parts']:
            self.assertIn(part['part'], human_2d3d.BODY_NAMES)
            if part['state'] == 'visible':
                self.assertTrue(set(part['sourceRows'].tolist()) <= rows)
                self.assertEqual(len(part['sourceRows']), len(part['cells']))
                self.assertTrue((part['cells'] >= 0).all())
                self.assertTrue((part['cells'] < int(np.prod(algorithm.grid.shape))).all())
            else:
                self.assertEqual(len(part['sourceRows']), 0)

    def test_identical_inputs_produce_identical_results(self):
        first = self.lock()
        second_algorithm = make()
        second = self.lock(second_algorithm)
        first_summary = human_2d3d.summary(first)
        second_summary = human_2d3d.summary(second)
        first_summary.pop('timingsMs')
        second_summary.pop('timingsMs')
        self.assertEqual(json.dumps(first_summary, sort_keys=True),
                         json.dumps(second_summary, sort_keys=True))
        np.testing.assert_array_equal(first['target3d']['sourceRows'],
                                      second['target3d']['sourceRows'])
        np.testing.assert_array_equal(first['image2d']['labels'],
                                      second['image2d']['labels'])

    def test_encode_points_rebuilds_the_same_target(self):
        measured = np.column_stack((self.person['x'], self.person['y'],
                                    self.person['z'])).astype(np.float64)
        encoded = self.algorithm.encode_points(measured)
        self.assertEqual(encoded.dtype, human_2d3d.ROW_DTYPE)
        self.assertEqual(len(encoded), len(self.person))
        other = make()
        for index in range(PREFIX):
            other.feed(self.background, index * DT, index)
        result = None
        for step in range(3):
            index = PREFIX + step
            result = other.feed(encoded, index * DT, index)
        self.assertIsNotNone(result['target3d']['trackId'])
        self.assertGreater(result['target3d']['pointCount'], 0)
        self.assertEqual(result['image2d']['rejected']['unknown_direction_rows'], 0)
        with self.assertRaises(ValueError):
            other.encode_points(np.array([[1.0, 2.0, float('nan')]]))

    def test_summary_is_strict_json(self):
        locked = self.lock()
        payload = human_2d3d.summary(locked)
        text = json.dumps(payload, allow_nan=False, sort_keys=True)
        self.assertIn('target', json.loads(text))


if __name__ == '__main__':
    unittest.main()