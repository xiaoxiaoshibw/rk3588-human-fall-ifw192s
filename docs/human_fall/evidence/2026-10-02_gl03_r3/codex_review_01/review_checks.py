"""Independent GL03 R3 checks; no production writes."""
import copy
import sys
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT / 'src/human_fall_detection'),
               str(ROOT / 'docs/human_fall/evidence/2026-10-02_gl03_r2')]
import codex_reference_checks as ref
from core.node_runtime import FallNodeCore
from core.lidar_candidates import build_snapshot


class ReviewChecks(ref.ReferenceBinding):
    def selected(self, record, explicit=None):
        core = FallNodeCore('s', calibration=record, transform=explicit)
        first = self.frame(core, 0)
        request = dict(schema_version=1, request_id='select-review', action='select',
                       session_id='s', time_epoch=0,
                       snapshot_id=first['snapshot']['snapshot_id'],
                       candidate_id=first['snapshot']['candidates'][0]['candidate_id'],
                       selection_version=0)
        self.assertTrue(core.handle_request(request, 1.01)['accepted'])
        self.frame(core, 1)
        return core

    def test_G05_same_id_changed_reference_cannot_keep_old_eligibility(self):
        old = ref.calibration(ref.transform())
        core = self.selected(old)
        new = ref.calibration(ref.transform(translation=(9., -2., .7)))
        try:
            result = core.apply_ground_context(calibration=new)
        except ValueError:
            return
        self.assertTrue(result['changed'], 'same ID changed T silently kept eligibility')
        self.assertIsNone(core._latest_valid_snapshot)
        self.assertIsNone(core._last_candidate)

    def test_G03_node_rejects_conflicting_explicit_reference_at_start(self):
        record = ref.calibration(ref.transform())
        try:
            core = FallNodeCore('s', calibration=record,
                                transform=ref.transform(translation=(9., -2., .7)))
            out = self.frame(core, 0)
        except ValueError:
            return
        self.assertTrue(all(c['center_reference_m'] is None
                            for c in out['snapshot']['candidates']),
                        'node silently discarded conflicting standalone transform')

    def test_G03_malformed_standalone_never_projects(self):
        for key, value in [('from_frame', None), ('to_frame', None),
                           ('status', 'broken'), ('units', 'mm')]:
            with self.subTest(key=key):
                tf = ref.transform()
                tf[key] = value
                try:
                    out = self.snapshot(tf, None)
                except ValueError:
                    continue
                self.assertTrue(all(c['center_reference_m'] is None
                                    for c in out['candidates']), key)

    def test_G05_standalone_caller_mutation_cannot_change_live_binding(self):
        tf = ref.transform()
        core = FallNodeCore('s', transform=tf)
        before = copy.deepcopy(self.frame(core, 0)['snapshot'])
        tf['translation_m'][0] = 9.
        after = self.frame(core, 1)['snapshot']
        np.testing.assert_allclose(before['candidates'][0]['center_reference_m'],
                                   after['candidates'][0]['center_reference_m'])

    def test_G03_invalid_parent_cannot_enable_reference(self):
        for key, value in [('schema_version', 99), ('calibration_id', None)]:
            with self.subTest(key=key):
                record = ref.calibration(ref.transform())
                record[key] = value
                try:
                    snap = self.snapshot(None, record)
                except ValueError:
                    continue
                self.assertTrue(all(c['center_reference_m'] is None
                                    for c in snap['candidates']))

    def test_G04_same_id_reload_then_occlusion_cannot_use_new_inverse_for_old_track(self):
        core = self.selected(ref.calibration(ref.transform()))
        before = np.asarray(core._last_candidate['center_source_m'])
        try:
            lifecycle = core.apply_ground_context(calibration=ref.calibration(
                ref.transform(translation=(9., -2., .7))))
        except ValueError:
            return
        if lifecycle['changed']:
            return
        out = core.process(np.empty((0,3)), 1.2, seq=3,
                           stamp_secs=100, stamp_nsecs=200000000, frame_id='innolidar')
        position = out['state'].get('position_source_m')
        if position is not None:
            np.testing.assert_allclose(position, before, atol=1e-8,
                err_msg='old reference track decoded with new inverse')


if __name__ == '__main__':
    unittest.main(verbosity=2)
