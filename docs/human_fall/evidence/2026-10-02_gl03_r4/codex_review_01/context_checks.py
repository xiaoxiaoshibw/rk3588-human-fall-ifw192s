"""Independent GL03 v1 context boundaries; no production writes."""
import copy
import sys
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT/'src/human_fall_detection'),
               str(ROOT/'docs/human_fall/evidence/2026-10-02_gl03_r2')]
import codex_reference_checks as ref
from core.calibration import make_unknown_transform
from core.node_runtime import FallNodeCore


class ContextChecks(unittest.TestCase):
    def snapshot(self, record):
        return ref.ReferenceBinding().snapshot(None, record)

    def no_reference(self, record):
        try:
            snap = self.snapshot(record)
        except ValueError:
            return
        self.assertTrue(all(c['center_reference_m'] is None for c in snap['candidates']))

    def test_G03_full_parent_wrong_kind_cannot_become_legacy_summary(self):
        record = ref.calibration(ref.transform())
        record['kind'] = 'unsupported_geometry_calibration'
        self.no_reference(record)

    def test_G03_parent_lidar_label_must_match_reference_source(self):
        record = ref.calibration(ref.transform())
        record['frames']['lidar'] = 'other_lidar'
        self.no_reference(record)

    def test_G05_standalone_binding_stays_fixed_across_same_id_reload(self):
        tf = ref.transform()
        record = ref.calibration(make_unknown_transform('innolidar','fixture_reference'))
        core = FallNodeCore('s',calibration=record,transform=tf)
        fixture = ref.ReferenceBinding()
        first = fixture.frame(core,0)
        request = dict(schema_version=1,request_id='standalone-select',action='select',
                       session_id='s',time_epoch=0,snapshot_id=first['snapshot']['snapshot_id'],
                       candidate_id=first['snapshot']['candidates'][0]['candidate_id'],
                       selection_version=0)
        self.assertTrue(core.handle_request(request,1.01)['accepted'])
        measured = fixture.frame(core,1)
        bound_before = copy.deepcopy(core._reference_transform)
        source_before = np.asarray(core._last_candidate['center_source_m'])
        tf['translation_m'][0] = 9.
        try:
            result = core.apply_ground_context(calibration=copy.deepcopy(record))
        except ValueError:
            self.assertEqual(core._reference_transform,bound_before)
            return
        self.assertFalse(result['changed'])
        # No reference supplied through this API; caller edits are not a reload.
        after = core.process(np.empty((0,3)),1.2,seq=3,stamp_secs=100,
                             stamp_nsecs=200000000,frame_id='innolidar')['state']
        print('STANDALONE_RELOAD',dict(changed=result['changed'],
              before=bound_before['translation_m'],after=core._reference_transform['translation_m'],
              source_before=source_before.tolist(),source_after=after.get('position_source_m')))
        self.assertEqual(core._reference_transform,bound_before)
        np.testing.assert_allclose(after['position_source_m'],source_before,atol=1e-8)

    def test_G05_rejected_canonical_reload_preserves_locked_state(self):
        record = ref.calibration(ref.transform())
        core = FallNodeCore('s',calibration=record)
        fixture=ref.ReferenceBinding()
        first=fixture.frame(core,0)
        request=dict(schema_version=1,request_id='canonical-select',action='select',
                     session_id='s',time_epoch=0,snapshot_id=first['snapshot']['snapshot_id'],
                     candidate_id=first['snapshot']['candidates'][0]['candidate_id'],selection_version=0)
        self.assertTrue(core.handle_request(request,1.01)['accepted'])
        fixture.frame(core,1)
        before=copy.deepcopy(core.tracker.snapshot())
        state_before=copy.deepcopy(core.status_state(1.11))
        with self.assertRaises(ValueError):
            core.apply_ground_context(calibration=ref.calibration(ref.transform(translation=(9.,-2.,.7))))
        self.assertEqual(core.tracker.snapshot(),before)
        self.assertEqual(core.status_state(1.11),state_before)


if __name__=='__main__':
    unittest.main(verbosity=2)
