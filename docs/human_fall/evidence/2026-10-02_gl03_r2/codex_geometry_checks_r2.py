"""Independent GL03 v1 compatibility, binding and real state-transition checks."""
import copy
import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'src/human_fall_detection'),
                str(ROOT / 'src/human_fall_detection/tests')]
from core.calibration import build_geometry_calibration, build_ground_derived, make_transform
from core.lidar_candidates import build_snapshot, validate_snapshot
from core.node_runtime import FallNodeCore, dumps_strict
from test_gl02_ground_frame import flat_ground, trusted_block, valid_ground, tilted_normal


def artifact(ground=None, reference=None):
    ground = flat_ground() if ground is None else ground
    return build_geometry_calibration('independent-v1', 'synthetic-only', 'innolidar',
        ground=ground, ground_derived=trusted_block() if reference is not False and
        np.allclose(ground['normal'], [0., 0., 1.]) and ground['offset_m'] == 1.2
        else build_ground_derived(ground, [1., 0., 0.]),
        reference_frame='fixture_reference' if isinstance(reference, dict) else None,
        transforms={'T_reference_lidar': reference} if isinstance(reference, dict) else None)


def points():
    return np.random.RandomState(71).normal(0., .1, (150, 3)) + [2., .1, -.5]


class IndependentGeometry(unittest.TestCase):
    def snapshot(self, data=None, ground=None, calibration=None, **kwargs):
        return build_snapshot(points() if data is None else data,
            {'min_cluster_points': 5, 'preferred_cluster_points': 10, 'max_points': 50},
            session_id='s', time_epoch=0, snapshot_id='seq:1', ground=ground,
            calibration=calibration, **kwargs)

    def unavailable_or_rejected(self, **context):
        try:
            snap = self.snapshot(**context)
        except ValueError:
            return
        self.assertIsNone(snap['coordinate'].get('ground_derived_id'))
        self.assertTrue(all(c.get('bbox_ground_from') == 'unavailable'
                            for c in snap['candidates']))

    def test_G07_legacy_snapshot_without_optional_ground_extension_validates(self):
        snap = self.snapshot()
        for candidate in snap['candidates']:
            for key in ('bbox_ground_from', 'bbox_ground_min_m', 'bbox_ground_max_m', 'center_ground_m'):
                candidate.pop(key, None)
        validate_snapshot(snap)

    def test_G03_complete_parent_corruption_cannot_enable_ground_geometry(self):
        for change in ('schema_bool', 'missing_id', 'invalid_verification'):
            with self.subTest(change=change):
                record = artifact()
                if change == 'schema_bool':
                    record['schema_version'] = True
                elif change == 'missing_id':
                    record['calibration_id'] = None
                else:
                    record['verification']['extrinsics_verified'] = True
                self.unavailable_or_rejected(ground=flat_ground(), calibration=record)

    def test_G03_actual_frame_and_supplied_ground_must_match_bound_context(self):
        record = artifact()
        with self.subTest(case='actual source frame differs'):
            self.unavailable_or_rejected(ground=flat_ground(), calibration=record, frame_id='other_lidar')
        with self.subTest(case='explicit ground differs'):
            self.unavailable_or_rejected(ground=flat_ground(1.4), calibration=record)

    def test_G03_foreign_frame_cannot_enable_legacy_height_or_live_measurements(self):
        for record in (None, artifact()):
            with self.subTest(entry='pure source-only' if record is None else 'pure full'):
                snap = self.snapshot(ground=flat_ground(), calibration=record, frame_id='other_lidar')
                self.assertFalse(snap['quality']['ground_valid'])
                self.assertFalse(snap['coordinate']['ground_relative_available'])
                self.assertTrue(all(c['height_m'] is None for c in snap['candidates']))
        core, floor, person, scene, selected, transform = self.core_fixture()
        epoch = core.cloud_timebase.time_epoch
        result = core.process(scene, 1.2, seq=3, stamp_secs=100, stamp_nsecs=200000000,
                              frame_id='other_lidar')
        self.assertEqual(result['state']['observability'], 'invalid')
        self.assertIsNone(result['state']['position_source_m'])
        self.assertEqual(result['state']['bbox_ground_from'], 'unavailable')
        self.assertEqual(core.cloud_timebase.time_epoch, epoch)
        snap = selected['snapshot']
        request = {'schema_version': 1, 'request_id': 'foreign-new-select', 'action': 'select',
            'session_id': 's', 'time_epoch': epoch, 'snapshot_id': snap['snapshot_id'],
            'candidate_id': snap['candidates'][0]['candidate_id'],
            'selection_version': core.tracker.selection_version}
        self.assertFalse(core.handle_request(request, 1.21)['accepted'])
        self.assertEqual(core.status_state(1.22)['observability'], 'invalid')
        self.assertEqual(self.frame(core, scene, 3)['state']['bbox_ground_from'], 'actual_points')

    def test_G02_filtered_indices_reconstruct_actual_ground_geometry(self):
        ground = valid_ground(tilted_normal(27., 31.), 1.2)
        record = artifact(ground)
        data = points()
        data[0] = [np.nan, 0., 0.]
        before = data.copy()
        snap = self.snapshot(data=data, ground=ground, calibration=record)
        block = record['ground_derived']
        rotation, translation = np.asarray(block['R']), np.asarray(block['t'])
        noncommuting = False
        self.assertGreater(len(snap['candidates']), 0)
        for candidate in snap['candidates']:
            actual = data[np.asarray(candidate['evidence_indices'], dtype=int)]
            transformed = actual @ rotation.T + translation
            np.testing.assert_allclose(candidate['center_source_m'], np.median(actual, axis=0))
            np.testing.assert_allclose(candidate['bbox_source_min_m'], actual.min(axis=0))
            np.testing.assert_allclose(candidate['bbox_ground_min_m'], transformed.min(axis=0))
            np.testing.assert_allclose(candidate['bbox_ground_max_m'], transformed.max(axis=0))
            np.testing.assert_allclose(candidate['center_ground_m'], np.median(transformed, axis=0))
            np.testing.assert_allclose(transformed[:, 2], actual @ np.asarray(ground['normal']) + 1.2)
            noncommuting |= np.max(np.abs(np.median(transformed, axis=0) -
                (np.median(actual, axis=0) @ rotation.T + translation))) > 1e-4
        self.assertTrue(noncommuting, 'fixture must expose median/rotation non-commutation')
        np.testing.assert_equal(data, before)
        dumps_strict(snap)

    def core_fixture(self, reference=False):
        angle = math.radians(41.)
        rotation = [[math.cos(angle), -math.sin(angle), 0.],
                    [math.sin(angle), math.cos(angle), 0.], [0., 0., 1.]]
        transform = make_transform(rotation, [1., -2., .7], 'innolidar',
                                   'fixture_reference', evidence='synthetic') if reference else None
        core = FallNodeCore('s', settings={'candidates': {'min_cluster_points': 20,
            'preferred_cluster_points': 30, 'height_min_m': .1}},
            calibration=artifact(reference=transform), transform=transform)
        xy = np.random.RandomState(13).uniform(-1., 1., (4000, 2))
        floor = np.column_stack((xy, np.full(4000, -1.2)))
        person = np.column_stack((np.ones(80), np.zeros(80), np.linspace(-1.2, .6, 80)))
        scene = np.vstack((floor, person))
        first = self.frame(core, scene, 0)
        self.assertEqual(core.ground_monitor_report['status'], 'ok')
        request = {'schema_version': 1, 'request_id': 'select-1', 'action': 'select',
            'session_id': 's', 'time_epoch': 0, 'snapshot_id': first['snapshot']['snapshot_id'],
            'candidate_id': first['snapshot']['candidates'][0]['candidate_id'], 'selection_version': 0}
        self.assertTrue(core.handle_request(request, 1.01)['accepted'])
        selected = self.frame(core, scene, 1)
        self.assertEqual(selected['state']['track_status'], 'locked')
        self.assertEqual(selected['state']['bbox_ground_from'], 'actual_points')
        return core, floor, person, scene, selected, transform

    def frame(self, core, data, index):
        return core.process(data, 1. + .1 * index, seq=index + 1,
                            stamp_secs=100, stamp_nsecs=index * 100000000)

    def test_G05_release_without_new_cloud_cannot_publish_old_target_geometry(self):
        core, floor, person, scene, selected, transform = self.core_fixture()
        release = {'schema_version': 1, 'request_id': 'release-1', 'action': 'release',
            'session_id': 's', 'time_epoch': 0, 'selection_version': core.tracker.selection_version}
        self.assertTrue(core.handle_request(release, 1.11)['accepted'])
        state = core.status_state(1.12)
        self.assertIsNone(state['track_id'])
        self.assertIsNone(state['center_ground_m'])
        self.assertEqual(state['bbox_ground_from'], 'unavailable')
        self.assertEqual(state['selection_version'], core.tracker.selection_version)

    def test_G05_new_selection_without_cloud_cannot_publish_previous_binding(self):
        core, floor, person, scene, selected, transform = self.core_fixture()
        snap = selected['snapshot']
        request = {'schema_version': 1, 'request_id': 'select-2', 'action': 'select',
            'session_id': 's', 'time_epoch': 0, 'snapshot_id': snap['snapshot_id'],
            'candidate_id': snap['candidates'][0]['candidate_id'],
            'selection_version': core.tracker.selection_version}
        self.assertTrue(core.handle_request(request, 1.11)['accepted'])
        state = core.status_state(1.12)
        self.assertEqual(state['track_id'], core.tracker.track_id)
        self.assertEqual(state['selection_version'], core.tracker.selection_version)
        self.assertIsNone(state['center_ground_m'])

    def test_G04_prediction_converts_source_and_does_not_keep_stale_reference_box(self):
        core, floor, person, scene, selected, transform = self.core_fixture(reference=True)
        moved_person = person.copy()
        moved_person[:, 0] += .1
        moved = self.frame(core, np.vstack((floor, moved_person)), 2)
        previous = moved['snapshot']['candidates'][0]
        predicted = self.frame(core, floor, 3)['state']
        self.assertEqual(predicted['track_status'], 'occluded')
        self.assertTrue(predicted['position_predicted'])
        rotation, translation = np.asarray(transform['rotation']), np.asarray(transform['translation_m'])
        expected_source = (np.asarray(core.tracker.position_m) - translation) @ rotation
        np.testing.assert_allclose(predicted['position_source_m'], expected_source, atol=1e-9)
        self.assertEqual(predicted['bbox_ground_from'], 'unavailable')
        if predicted.get('bbox_reference_min_m') is not None:
            delta = np.asarray(core.tracker.position_m) - np.asarray(previous['center_reference_m'])
            np.testing.assert_allclose(predicted['bbox_reference_min_m'],
                                       np.asarray(previous['bbox_reference_min_m']) + delta)

    def test_G05_stale_and_monitor_failure_clear_current_ground_geometry(self):
        for loss in ('stale', 'monitor'):
            with self.subTest(loss=loss):
                core, floor, person, scene, selected, transform = self.core_fixture()
                state = core.status_state(3.) if loss == 'stale' else self.frame(core, person, 2)['state']
                self.assertEqual(state['observability'], 'invalid')
                for name in ('center_ground_m', 'bbox_ground_min_m', 'bbox_ground_max_m'):
                    self.assertIsNone(state[name])
                self.assertEqual(state['bbox_ground_from'], 'unavailable')


if __name__ == '__main__':
    unittest.main(verbosity=2)
