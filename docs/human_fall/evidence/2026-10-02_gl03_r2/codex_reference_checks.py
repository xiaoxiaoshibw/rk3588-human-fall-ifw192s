"""GL03 v1: reference frame/context ownership, including no-ground nodes."""
import copy
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'src/human_fall_detection'),
                str(ROOT / 'docs/human_fall/evidence/2026-10-02_gl03_r1')]
from core.calibration import build_geometry_calibration, make_transform
from core.lidar_candidates import build_snapshot
from core.node_runtime import FallNodeCore
import codex_geometry_checks as geo


def transform(source='innolidar', target='fixture_reference', translation=(1., -2., .7)):
    return make_transform(np.eye(3).tolist(), list(translation), source, target,
                          evidence='synthetic')


def calibration(tf, version='reference-a'):
    return build_geometry_calibration(version, 'synthetic', 'innolidar',
        reference_frame='fixture_reference', transforms={'T_reference_lidar': tf})


class ReferenceBinding(unittest.TestCase):
    def snapshot(self, tf, record, frame='innolidar'):
        return build_snapshot(geo.points(), session_id='s', time_epoch=0,
            snapshot_id='seq:1', transform=tf, calibration=record, frame_id=frame)

    def test_G03_reference_source_mismatch_does_not_project(self):
        tf = transform(source='other_lidar')
        try:
            snap = self.snapshot(tf, calibration(tf))
        except ValueError:
            return
        self.assertTrue(all(c['center_reference_m'] is None for c in snap['candidates']))

    def test_G03_reference_target_cannot_conflict_with_known_label(self):
        tf = transform(target='other_reference')
        try:
            snap = self.snapshot(tf, calibration(transform()))
        except ValueError:
            return
        self.assertTrue(all(c['center_reference_m'] is None for c in snap['candidates']))

    def frame(self, core, index, frame='innolidar'):
        return core.process(geo.points(), 1. + .1 * index, seq=index+1,
            stamp_secs=100, stamp_nsecs=index*100000000, frame_id=frame)

    def test_G03_no_ground_reference_node_masks_foreign_frame(self):
        tf = transform()
        core = FallNodeCore('s', calibration=calibration(tf), transform=tf)
        first = self.frame(core, 0)
        request = {'schema_version': 1, 'request_id': 'reference-select', 'action': 'select',
            'session_id': 's', 'time_epoch': 0, 'snapshot_id': first['snapshot']['snapshot_id'],
            'candidate_id': first['snapshot']['candidates'][0]['candidate_id'], 'selection_version': 0}
        self.assertTrue(core.handle_request(request, 1.01)['accepted'])
        measured = self.frame(core, 1)
        self.assertIsNotNone(measured['state']['position_reference_m'])
        foreign = self.frame(core, 2, 'other_lidar')
        self.assertEqual(foreign['state']['observability'], 'invalid')
        self.assertIsNone(foreign['state']['position_reference_m'])
        fresh_request = dict(request, request_id='foreign-reference-select', selection_version=1)
        self.assertFalse(core.handle_request(fresh_request, 1.21)['accepted'])
        self.assertEqual(core.status_state(1.22)['observability'], 'invalid')
        restored = self.frame(core, 3)
        self.assertNotEqual(restored['state']['observability'], 'invalid')

    def test_G05_full_reload_uses_current_artifact_reference_transform(self):
        old_tf = transform()
        core = FallNodeCore('s', calibration=calibration(old_tf), transform=old_tf)
        self.frame(core, 0)
        new_tf = transform(translation=(2., -1., .2))
        new_record = calibration(new_tf, 'reference-b')
        core.apply_ground_context(calibration=new_record)
        current = self.frame(core, 1)['snapshot']
        self.assertEqual(current['calibration']['calibration_id'], 'reference-b')
        for candidate in current['candidates']:
            expected = np.asarray(candidate['center_source_m']) + np.asarray(new_tf['translation_m'])
            np.testing.assert_allclose(candidate['center_reference_m'], expected, atol=1e-9)
        # Caller mutation cannot change the adopted reference context.
        new_record['transforms']['T_reference_lidar']['translation_m'][0] = 99.
        after = self.frame(core, 2)['snapshot']['candidates'][0]
        expected = np.asarray(after['center_source_m']) + np.asarray(new_tf['translation_m'])
        np.testing.assert_allclose(after['center_reference_m'], expected, atol=1e-9)


if __name__ == '__main__':
    unittest.main(verbosity=2)
