"""W2合成已知场景只验证软件关联，不替代真人身份GT。"""
from dataclasses import replace
import unittest

import numpy as np

from test_range_frontend import scene
from core.range_contract import binding_tuple
from core.range_features import measured_features
from core.range_tracker import RangeTracker


def measurement(centers, split=False, ground_binding=None):
    _,_,frame=scene(np.full((4,24),2.0))
    labels=np.full(frame.grid.shape,-1,dtype=np.int32)
    components=[]
    for k,center in enumerate(centers):
        rows=np.arange(k*32,(k+1)*32,dtype=np.int64)
        # 每个组件32个真实合成测量；row只是本帧索引。
        local=np.array([(x,y,z) for x in (-.03,-.01,.01,.03) for y in (-.02,.02) for z in (-.03,.01,.04,.07)])
        frame.xyz=np.array(frame.xyz,copy=True)
        frame.xyz[rows]=np.asarray(center)+local
        chunks=np.array_split(rows,2) if split and k==0 else [rows]
        for chunk in chunks:
            cid=len(components)
            labels.ravel()[chunk]=cid
            components.append(dict(component_id=cid,source_rows=chunk,points=len(chunk),retained=True))
    if ground_binding:
        frame.binding=binding_tuple(ground_binding)
    return frame,labels,components


def step(tracker, centers, t, index, **kwargs):
    f,l,c=measurement(centers,**kwargs)
    return tracker.update(f,l,c,t,index)


class RangeTrackingTests(unittest.TestCase):
    def test_stationary_and_constant_motion_birth_and_velocity(self):
        tracker=RangeTracker()
        for i in range(6):
            result=step(tracker,[(2+i*.02,0,.5)],i*.1,i)
            row=result['tracks'][0]
            self.assertEqual(row['track_id'],'g0_t0001')
            self.assertEqual(row['status'],'tentative' if i<2 else 'tracked')
            if i:
                np.testing.assert_allclose(row['velocity_m_s'],[.2,0],atol=1e-5)
        self.assertEqual(len(result['target_source_rows']),32)

    def test_identical_row_numbers_are_not_point_identity(self):
        tracker=RangeTracker()
        for i in range(3):
            step(tracker,[(2,0,.5)],i*.1,i)
        result=step(tracker,[(5,0,.5)],.3,3)
        self.assertEqual(result['target_source_rows'],[])
        self.assertEqual(result['tracks'][0]['status'],'predicted')
        self.assertEqual(result['tracks'][1]['status'],'tentative')

    def test_row_permutation_preserves_association(self):
        tracker=RangeTracker()
        for i in range(3):
            step(tracker,[(2,0,.5)],i*.1,i)
        f,l,c=measurement([(2,0,.5)])
        permutation=np.arange(len(f.xyz))[::-1]
        f.xyz=f.xyz[permutation]
        f.source_rows=permutation[f.source_rows]
        c[0]['source_rows']=np.sort(permutation[c[0]['source_rows']])
        result=tracker.update(f,l,c,.3,3)
        self.assertEqual(result['target_track_id'],'g0_t0001')

    def test_occlusion_has_no_measured_features_and_recovers(self):
        tracker=RangeTracker()
        for i in range(3):
            step(tracker,[(2,0,.5)],i*.1,i)
        result=step(tracker,[],.3,3)
        row=result['tracks'][0]
        self.assertFalse(row['observed'])
        self.assertEqual(row['source_rows'],[])
        self.assertIsNone(row['features'])
        self.assertIsNone(row['velocity_m_s'])
        result=step(tracker,[(2,0,.5)],.4,4)
        self.assertEqual(result['target_track_id'],'g0_t0001')
        self.assertIsNone(result['tracks'][0]['velocity_m_s'])

    def test_crossing_and_competing_tracks_stay_unknown(self):
        tracker=RangeTracker()
        for i in range(3):
            step(tracker,[(2,-.6,.5),(2,.6,.5)],i*.1,i)
        result=step(tracker,[(2,0,.5)],.3,3)
        self.assertEqual(result['target_source_rows'],[])
        self.assertTrue(all(not r['observed'] for r in result['tracks']))
        self.assertTrue(result['ambiguous_component_ids'])

    def test_two_symmetric_candidates_ambiguous_not_arbitrary(self):
        tracker=RangeTracker()
        for i in range(3):
            step(tracker,[(2,0,.5)],i*.1,i)
        # 相距0.6m，原组合gap规则拒绝；等距候选保留歧义。
        result=step(tracker,[(2,-.3,.5),(2,.3,.5)],.3,3)
        self.assertEqual(result['target_source_rows'],[])
        self.assertEqual(len(result['tracks']),1)
        self.assertEqual(result['tracks'][0]['status'],'ambiguous')

    def test_moving_crossing_exact_overlap_has_no_identity_claim(self):
        tracker=RangeTracker()
        outputs=[]
        for i in range(10):
            y=-.6+.1*i
            outputs.append(step(tracker,[(2,y,.5),(2,-y,.5)],i*.1,i))
        self.assertTrue(outputs[2]['tracks'])
        self.assertTrue(all(not r['observed'] for r in outputs[6]['tracks']))
        self.assertIsNone(outputs[6]['target_track_id'])

    def test_fragments_use_only_real_current_union(self):
        tracker=RangeTracker()
        for i in range(3):
            step(tracker,[(2,0,.5)],i*.1,i)
        result=step(tracker,[(2,0,.5)],.3,3,split=True)
        self.assertEqual(result['target_source_rows'],list(range(32)))
        self.assertEqual(result['tracks'][0]['component_ids'],[0,1])
        self.assertTrue(result['compositions'][0]['accepted'])

    def test_composition_cannot_ignore_unbound_geometric_competitor(self):
        tracker=RangeTracker()
        for i in range(3): step(tracker,[(2,0,.5)],i*.1,i)
        r=step(tracker,[(2,0,.5),(2,.15,.5)],.3,3,split=True)
        self.assertEqual(r['target_source_rows'],[])
        self.assertTrue(all(not t['observed'] for t in r['tracks']))
        self.assertEqual(r['compositions'][0]['reason'],'unbound_geometric_competitor')

    def test_low_posture_birth_not_filtered_or_fall(self):
        tracker=RangeTracker()
        for i in range(3):
            result=step(tracker,[(2,0,.1)],i*.1,i)
        self.assertEqual(len(result['target_source_rows']),32)
        self.assertEqual(result['target_features']['semantic'],'unknown')
        self.assertNotIn('fall',result)

    def test_repeated_backward_gap_and_binding_reset(self):
        for mode in ('repeat','backward','gap','calibration','epoch'):
            tracker=RangeTracker()
            for i in range(3):
                step(tracker,[(2,0,.5)],i*.1,i)
            f,l,c=measurement([(2,0,.5)])
            t=.3
            if mode=='repeat': t=.2
            if mode=='backward': t=.1
            if mode=='gap': t=3
            if mode in ('calibration','epoch'):
                b=list(f.binding); b[2 if mode=='calibration' else 3]='new'; f.binding=tuple(b)
            r=tracker.update(f,l,c,t,3)
            self.assertIsNotNone(r['reset_reason'],mode)
            self.assertEqual(r['generation'],1)
            self.assertEqual(r['target_source_rows'],[])

    def test_empty_frame_expiry_and_nonfinite_clock(self):
        tracker=RangeTracker()
        for i in range(3): step(tracker,[(2,0,.5)],i*.1,i)
        for i in range(3,19): result=step(tracker,[],i*.1,i)
        self.assertEqual(result['tracks'],[])
        f,l,c=measurement([])
        with self.assertRaises(ValueError):tracker.update(f,l,c,float('nan'),20)

    def test_ground_unknown_and_pca_degenerate(self):
        f,_,c=measurement([(2,0,.1)])
        features=measured_features(f,c[0]['source_rows'])
        self.assertIsNone(features['height_m'])
        self.assertIsNone(features['visible_ratio'])
        f.xyz[c[0]['source_rows']]=[2,0,.1]
        self.assertFalse(measured_features(f,c[0]['source_rows'])['axis_valid'])

    def test_ground_requires_exact_stream_binding(self):
        binding=dict(session='s',coordinate='RAW/innolidar')
        f,_,c=measurement([(2,0,.1)],ground_binding=binding)
        ground=dict(status='valid',frame='innolidar',normal=[0,0,1],offset_m=0,binding=binding)
        self.assertIsNotNone(measured_features(f,c[0]['source_rows'],ground)['height_m'])
        self.assertIsNone(measured_features(f,c[0]['source_rows'],dict(ground,binding=dict(session='other')))['height_m'])
        self.assertIsNone(measured_features(f,c[0]['source_rows'],dict(ground,normal=[0,0,0]))['height_m'])

    def test_nonfinite_ground_is_unknown_and_cannot_break_tracking(self):
        tracker=RangeTracker()
        binding=dict(session='s',coordinate='RAW/innolidar')
        f,l,c=measurement([(2,0,.1)],ground_binding=binding)
        for i,ground in enumerate([
                dict(status='valid',binding=binding,normal=[0,0,float('nan')],offset_m=0),
                dict(status='valid',binding=dict(session=float('nan')),normal=[0,0,1],offset_m=0)]):
            r=tracker.update(f,l,c,i*.1,i,ground=ground)
            self.assertIsNone(r['tracks'][0]['features']['height_m'])

    def test_causal_prefix_matches_complete_and_deterministic(self):
        def replay(n):
            tracker=RangeTracker()
            return [step(tracker,[(2+i*.01,0,.5)] if i!=5 else [],i*.1,i) for i in range(n)]
        self.assertEqual(replay(7),replay(12)[:7])
        self.assertEqual(replay(12),replay(12))


if __name__=='__main__':
    unittest.main()
