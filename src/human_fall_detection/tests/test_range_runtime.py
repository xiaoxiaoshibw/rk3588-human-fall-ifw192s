"""运行时与W2/规则逐帧对照；合成测量不代表人体GT。"""
import hashlib
from pathlib import Path
import sys
import unittest

import numpy as np

from test_range_frontend import scene
from test_range_tracking import measurement
from core.range_contract import binding_tuple
from core.range_runtime import RangeRuntime, serial
from core.range_tracker import INFERENCE_KEYS, RangeTracker
from core.range_background import RayBackground
from core.range_components import label_components
from core.range_denoise import denoise

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from range_experiment import RuleBaseline, inference_serial


class RuntimeTests(unittest.TestCase):
    def test_inference_ledger_accepts_known_schemas_and_rejects_tampering(self):
        record = dict(frame=1, tracks=[], single_person_policy={'chosen_track_id': None},
                      dropped_fragments=[])
        for keys in (INFERENCE_KEYS, INFERENCE_KEYS + ('single_person_policy', 'dropped_fragments')):
            data = serial({k:record[k] for k in keys if k in record})
            signed = dict(record, inference_sha256=hashlib.sha256(data.encode()).hexdigest())
            self.assertEqual(inference_serial(signed), data)
            signed['frame'] = 2
            with self.assertRaisesRegex(ValueError, 'inference record SHA mismatch'):
                inference_serial(signed)

    def test_background_sorted_medians_exactly_match_nanmedian_reference(self):
        rng=np.random.default_rng(197)
        for count in (3,10,50):
            frames=[]
            for _ in range(count):
                grid,packed,_=scene(rng.uniform(1,5,size=(8,24)))
                frame=grid.decode(packed,('same',))
                frame.range_m[rng.random((8,24))<.15]=np.nan
                frames.append(frame)
            actual=RayBackground(frames,empty_prefix_declared=True,min_observations=1)
            values=np.stack([f.range_m for f in frames])[:,actual.known]
            expected=np.nanmedian(values,axis=0)
            np.testing.assert_array_equal(actual.mean_m[actual.known],expected)
            np.testing.assert_array_equal(actual.sigma_m[actual.known],np.maximum(.005,1.4826*np.nanmedian(abs(values-expected),axis=0)))

    def make(self, ground=False):
        grid,raw,_ = scene(np.full((8,24),3.))
        identity = dict(session='synthetic', coordinate='RAW/lidar', grid_sha256=grid.sha256)
        plane = dict(status='valid',binding=identity,frame='lidar',normal=[0,0,1],offset_m=.5) if ground else None
        return RangeRuntime(grid,identity,empty_prefix_frames=2,ground=plane,ground_sha='fixture' if ground else None),raw

    def test_same_input_w1_w2_and_rule_oracle(self):
        runtime,raw = self.make(True)
        tracker = RangeTracker(); baseline = RuleBaseline('synthetic',runtime.ground,'fixture')
        prefix=[]; bg=None
        for i in range(12):
            depth = np.full((8,24),3.)
            if i>=2: depth[2:6,8:14]=2.
            _,packed,_ = scene(depth)
            actual,frame,components = runtime.update(packed,i*.1,i)
            if bg is None:
                prefix.append(frame); foreground=np.zeros(frame.grid.shape,dtype=bool)
            else:
                foreground=bg.foreground(frame)['mask']
            labels,expected_components=label_components(frame,denoise(frame,foreground)['mask'])
            expected=tracker.update(frame,labels,expected_components,i*.1,i,ground=runtime.ground)
            expected['inference_sha256']=hashlib.sha256(serial({k:expected[k] for k in INFERENCE_KEYS if k in expected}).encode()).hexdigest()
            self.assertEqual(expected,actual['tracking'])
            self.assertEqual(baseline.update(frame,expected),actual['rule'])
            self.assertEqual([c['source_rows'].tolist() for c in components],
                [c['source_rows'].tolist() for c in expected_components])
            if i==1: bg=RayBackground(prefix,empty_prefix_declared=True,min_observations=2)

    def test_clock_repeat_rollback_gap_clear_measurements(self):
        for end in (.2,.1,3.):
            runtime,raw=self.make()
            for i in range(3):runtime.update(raw,i*.1,i)
            out,_,_=runtime.update(raw,end,3)
            self.assertEqual(out['tracking']['generation'],1)
            self.assertIsNotNone(out['tracking']['reset_reason'])
            self.assertEqual(out['tracking']['target_source_rows'],[])
            self.assertEqual(out['status'],'background_requires_explicit_rebind')
            self.assertEqual(out['rule']['state']['state'],'unknown')

    def test_source_or_calibration_change_invalidates_frozen_background(self):
        for field in ('session','grid_sha256','coordinate'):
            runtime,raw=self.make(True)
            for i in range(3):runtime.update(raw,i*.1,i)
            identity=dict(runtime.identity);identity[field]='changed'
            out,_,_=runtime.update(raw,.3,3,identity=identity)
            self.assertEqual(out['tracking']['reset_reason'],'binding_changed')
            self.assertEqual(out['tracking']['target_source_rows'],[])
            self.assertFalse(out['rule']['features']['observable'])

    def test_missing_prefix_frame_is_not_redeclared_as_empty(self):
        runtime,raw=self.make()
        runtime.update(raw,0.,0)
        out,_,_=runtime.update(raw,.2,2)
        self.assertEqual(out['status'],'background_requires_explicit_rebind')
        self.assertIsNone(runtime.background)

    def test_missing_ground_low_birth_prediction_and_fragment_rule_parity(self):
        for grounded in (False,True):
            runtime,_=self.make(grounded)
            oracle=RuleBaseline('synthetic',runtime.ground,runtime.ground_sha)
            tracker=RangeTracker()
            for i in range(25):
                centers=[] if i in (8,9,10) else [(2,0,.05)]
                frame,labels,components=measurement(centers,split=i==7)
                frame.binding=runtime.binding
                record=tracker.update(frame,labels,components,i*.1,i,ground=runtime.ground)
                record['inference_sha256']=hashlib.sha256(serial({k:record[k] for k in INFERENCE_KEYS if k in record}).encode()).hexdigest()
                rule=runtime.rules(frame,record,{})
                self.assertEqual(rule,oracle.update(frame,record))
                self.assertFalse(rule['state']['confirmed_enabled'])
                self.assertIsNone(rule['state']['new_event'])
                self.assertNotEqual(rule['state']['state'],'suspected')
                if not centers:
                    self.assertFalse(rule['source_rows'])
                    self.assertFalse(rule['features']['observable'])
                if not grounded:self.assertIsNone(rule['features']['height_median_m'])

    def test_invalid_prefix_and_nonfinite_clock_rejected(self):
        runtime,raw=self.make()
        with self.assertRaises(ValueError):RangeRuntime(runtime.grid,runtime.identity,empty_prefix_frames=0)
        with self.assertRaises(ValueError):runtime.update(raw,float('nan'),0)

    def test_dropped_input_does_not_bridge_low_duration_or_descent(self):
        runtime,_=self.make(True)
        depth=np.full((8,24),3.)
        for i in range(8):
            if i>=2:depth[2:6,8:14]=2.
            _,raw,_=scene(depth)
            result,_,_=runtime.update(raw,i*.1,i)
        self.assertGreater(result['rule']['features']['near_ground_duration_s'],0.)
        result,_,_=runtime.update(raw,.9,9)
        self.assertEqual(result['skipped_input_frames'],1)
        self.assertTrue(result['rule']['features']['observation_gap'])
        self.assertEqual(result['rule']['features']['near_ground_duration_s'],0.)
        self.assertIsNone(result['rule']['features']['descent_rate_m_s'])


if __name__=='__main__':unittest.main()
