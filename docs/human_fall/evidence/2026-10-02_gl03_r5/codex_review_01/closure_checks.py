"""GL03 v1 independent closure checks on input classification and reload."""
import copy
import sys
import unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT/'src/human_fall_detection'),str(ROOT/'docs/human_fall/evidence/2026-10-02_gl03_r2')]
import codex_reference_checks as ref
from core.calibration import make_unknown_transform
from core.node_runtime import FallNodeCore

class ClosureChecks(unittest.TestCase):
    def test_G03_unsupported_full_parent_cannot_hide_behind_missing_kind(self):
        for mode in ['removed','null']:
            with self.subTest(mode=mode):
                record=ref.calibration(ref.transform())
                record['schema_version']=99
                if mode=='removed':record.pop('kind')
                else:record['kind']=None
                try:
                    snap=ref.ReferenceBinding().snapshot(None,record)
                except ValueError:
                    continue
                self.assertTrue(all(c['center_reference_m'] is None for c in snap['candidates']),
                                'complete unsupported artifact was treated as a minimal legacy summary')

    def test_G05_no_argument_reload_keeps_frozen_standalone(self):
        tf=ref.transform()
        record=ref.calibration(make_unknown_transform('innolidar','fixture_reference'))
        core=FallNodeCore('s',calibration=record,transform=tf)
        initial=copy.deepcopy(core._reference_transform)
        tf['rotation']=[[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]]
        tf['translation_m'][0]=9.
        result=core.apply_ground_context()
        self.assertFalse(result['changed'])
        self.assertEqual(core._reference_transform,initial)
        point=[3.,-2.,.7]
        np.testing.assert_allclose(core._prediction_in_source(point),[2.,0.,0.],atol=1e-9)

    def test_G05_new_version_known_to_unknown_retires_old_track(self):
        tf=ref.transform()
        core=FallNodeCore('s',calibration=ref.calibration(tf),transform=tf)
        fixture=ref.ReferenceBinding()
        first=fixture.frame(core,0)
        request=dict(schema_version=1,request_id='closure-select',action='select',session_id='s',time_epoch=0,
            snapshot_id=first['snapshot']['snapshot_id'],candidate_id=first['snapshot']['candidates'][0]['candidate_id'],selection_version=0)
        self.assertTrue(core.handle_request(request,1.01)['accepted'])
        fixture.frame(core,1)
        events=copy.deepcopy(core.event_log.recent)
        tf['translation_m'][0]=9.
        result=core.apply_ground_context(calibration=ref.calibration(
            make_unknown_transform('innolidar','fixture_reference'),'reference-b'))
        self.assertTrue(result['changed'])
        self.assertIsNone(core._latest_valid_snapshot)
        self.assertIsNone(core._last_candidate)
        self.assertEqual(core.event_log.recent,events)
        self.assertEqual(core.cloud_timebase.time_epoch,0)
        np.testing.assert_allclose(core._reference_transform['translation_m'],[1.,-2.,.7])
        state=core.status_state(1.11)
        self.assertIsNone(state.get('position_reference_m'))

if __name__=='__main__':unittest.main(verbosity=2)
