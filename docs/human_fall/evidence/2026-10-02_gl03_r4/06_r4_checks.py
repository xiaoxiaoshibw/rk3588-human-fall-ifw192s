"""GL-03 R4 independent checks (new adversarial cases; R3 checks kept read-only).

Focus: full-artifact/reference-record qualification, same-id binding refusal
without side effects, legal standalone/legacy support and fixed caller bindings.
"""
import copy
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'src/human_fall_detection'),
                str(ROOT / 'docs/human_fall/evidence/2026-10-02_gl03_r2')]
import codex_reference_checks as ref
from core.lidar_candidates import build_snapshot
from core.node_runtime import FallNodeCore
import codex_geometry_checks as geo


class R4ReferenceQualification(unittest.TestCase):
    def snapshot(self, transform=None, calibration=None, frame_id='innolidar'):
        return build_snapshot(geo.points(), session_id='s', time_epoch=0,
                              snapshot_id='seq:1', transform=transform,
                              calibration=calibration, frame_id=frame_id)

    def assert_no_reference(self, snap, label):
        self.assertTrue(all(c['center_reference_m'] is None
                            for c in snap['candidates']), label)
        self.assertEqual(snap['coordinate']['transform_status'], 'unknown', label)

    def test_full_artifact_with_bad_reference_record_never_projects(self):
        for key, value in (('units', 'mm'), ('evidence', None),
                           ('status', 'broken'), ('direction', 'p_from = x'),
                           ('from_frame', None), ('to_frame', None)):
            with self.subTest(key=key):
                artifact = ref.calibration(ref.transform())
                artifact['transforms']['T_reference_lidar'][key] = value
                self.assert_no_reference(self.snapshot(calibration=artifact), key)

    def test_legacy_summary_with_bad_record_never_projects(self):
        for key, value in (('units', 'mm'), ('status', 'broken'),
                           ('evidence', None)):
            with self.subTest(key=key):
                bad = ref.transform()
                bad[key] = value
                summary = {'calibration_id': 'legacy',
                           'frames': {'lidar': 'innolidar',
                                      'reference': 'fixture_reference'},
                           'transforms': {'T_reference_lidar': bad}}
                self.assert_no_reference(self.snapshot(calibration=summary), key)

    def test_legacy_summary_with_good_record_still_projects(self):
        tf = ref.transform()
        summary = {'calibration_id': 'legacy',
                   'frames': {'lidar': 'innolidar',
                              'reference': 'fixture_reference'},
                   'transforms': {'T_reference_lidar': tf}}
        candidate = self.snapshot(calibration=summary)['candidates'][0]
        self.assertIsNotNone(candidate['center_reference_m'])

    def test_node_level_standalone_with_unknown_artifact_reference_still_binds(self):
        record = ref.calibration(ref.transform())
        record['transforms']['T_reference_lidar'] = \
            {'status': 'unknown', 'rotation': None, 'translation_m': None,
             'from_frame': 'innolidar', 'to_frame': 'fixture_reference',
             'units': 'm', 'evidence': None}
        tf = ref.transform()
        core = FallNodeCore('s', calibration=record, transform=tf)
        snap = core.process(geo.points(), 1.0, seq=1, stamp_secs=100,
                            stamp_nsecs=0, frame_id='innolidar')['snapshot']
        candidate = snap['candidates'][0]
        expected = np.asarray(candidate['center_source_m']) \
            + np.asarray(tf['translation_m'])
        np.testing.assert_allclose(candidate['center_reference_m'], expected,
                                   atol=1e-9)

    def test_startup_conflict_refused_even_for_malformed_explicit(self):
        record = ref.calibration(ref.transform())
        bad = ref.transform()
        bad['status'] = 'broken'
        with self.assertRaises(ValueError):
            FallNodeCore('s', calibration=record, transform=bad)

    def test_same_id_reference_change_refused_without_side_effects(self):
        core = FallNodeCore('s', calibration=ref.calibration(ref.transform()))
        first = core.process(geo.points(), 1.0, seq=1, stamp_secs=100,
                             stamp_nsecs=0, frame_id='innolidar')
        snap_before = core._latest_valid_snapshot
        bound_before = copy.deepcopy(core._reference_transform)
        core.baseline.start('t1', core.calibration['calibration_id'])
        with self.assertRaises(ValueError):
            core.apply_ground_context(calibration=ref.calibration(
                ref.transform(translation=(9., -2., .7))))
        self.assertIs(core._latest_valid_snapshot, snap_before)
        self.assertEqual(core._reference_transform, bound_before)
        self.assertEqual(core.calibration['calibration_id'], 'reference-a')
        self.assertEqual(core.baseline.status, 'pending')
        self.assertIsNotNone(first['snapshot'])

    def test_new_version_reload_adopts_new_reference_despite_old_standalone(self):
        old_tf = ref.transform()
        core = FallNodeCore('s', calibration=ref.calibration(old_tf),
                            transform=copy.deepcopy(old_tf))
        new_tf = ref.transform(translation=(2., -1., .2))
        lifecycle = core.apply_ground_context(
            calibration=ref.calibration(new_tf, 'reference-b'))
        self.assertTrue(lifecycle['changed'])
        snap = core.process(geo.points(), 1.2, seq=2, stamp_secs=100,
                            stamp_nsecs=200000000, frame_id='innolidar')['snapshot']
        self.assertEqual(snap['calibration']['calibration_id'], 'reference-b')
        for candidate in snap['candidates']:
            expected = np.asarray(candidate['center_source_m']) \
                + np.asarray(new_tf['translation_m'])
            np.testing.assert_allclose(candidate['center_reference_m'], expected,
                                       atol=1e-9)

    def test_standalone_mutation_cannot_rebind_prediction_inverse(self):
        tf = ref.transform()
        core = FallNodeCore('s', transform=tf)
        reference_point = [3.006022, -1.90591, 0.204184]
        before = core._prediction_in_source(reference_point)
        tf['translation_m'][0] = 9.
        after = core._prediction_in_source(reference_point)
        np.testing.assert_allclose(before, after, atol=0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
