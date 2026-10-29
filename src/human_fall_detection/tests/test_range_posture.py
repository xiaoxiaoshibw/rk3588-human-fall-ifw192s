import os
import sys
import unittest

import numpy as np

sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from core.range_posture import PostureObserver
from core.features import FeatureExtractor
from core.fall_state import FallStateMachine
from core.lidar_candidates import rebuild_candidate


def feature(**changes):
    f=dict(observable=True,ground_relative=True,height_m={'max':.4},horizontal_extent_m=1.4,
           axis_verticality=.1,axis_ambiguous=False,point_count=100,observation_gap=False,reset_now=False)
    f.update(changes)
    return f


def record(i, **changes):
    r=dict(frame=i,time_s=i*.1,generation=0,target_track_id='T1',target_source_rows=[0])
    r.update(changes)
    return r


class TestPosture(unittest.TestCase):
    def test_float_boundary_gap(self):
        observer=PostureObserver()
        for i in range(11):out=observer.update(feature(),record(i,time_s=i*.3),('src',))
        self.assertEqual(out['state'],'lying_candidate')
        out=observer.update(feature(),record(11,time_s=3.3001),('src',))
        self.assertEqual(out['durationSec'],0)

    def test_static_lying_and_lookalike_remain_geometric_only(self):
        observer=PostureObserver()
        for i in range(16):out=observer.update(feature(),record(i),('source','ground1'))
        self.assertEqual(out['state'],'lying_candidate')
        self.assertEqual(out['humanSemantic'],'UNKNOWN')
        self.assertFalse(out['fallEvent'])

    def test_low_fragments_bent_crouched_and_bad_axis_do_not_pass_height_alone(self):
        for f in (feature(horizontal_extent_m=.2),feature(axis_verticality=.96),
                  feature(height_m={'max':1.1}),feature(axis_ambiguous=True),feature(point_count=4),
                  feature(ground_relative=False),feature(observable=False),feature(axis_verticality=float('nan'))):
            observer=PostureObserver()
            for i in range(30):out=observer.update(f,record(i),('source',))
            self.assertNotEqual(out['state'],'lying_candidate')

    def test_context_missing_prediction_time_and_skipped_frames_restart_duration(self):
        cases=[(feature(observable=False),record(16),('src',)),
               (feature(),record(16,target_track_id='T2'),('src',)),
               (feature(),record(16,generation=1),('src',)),
               (feature(),record(16),('other',)),
               (feature(),record(17),('src',)),
               (feature(),record(16,time_s=1.5),('src',)),
               (feature(),record(16,time_s=2.),('src',)),
               (feature(observation_gap=True),record(16),('src',)),
               (feature(reset_now=True),record(16),('src',))]
        for f,r,binding in cases:
            observer=PostureObserver()
            for i in range(16):observer.update(feature(),record(i),('src',))
            out=observer.update(f,r,binding)
            self.assertNotEqual(out['state'],'lying_candidate')
            self.assertEqual(out['durationSec'],0)

    def test_real_geometry_feature_pipeline_static_and_measured_descent(self):
        # Injected rigid surface only: this fixture is not a human or physical fall GT.
        ground=dict(status='valid',normal=[0,0,1],offset_m=0,frame='sensor')
        for dynamic in (False,True):
            extractor=FeatureExtractor('s');event=FallStateMachine('s');posture=PostureObserver()
            states=[];poses=[]
            for i in range(50):
                if dynamic and i<15:
                    height=1.6-min(1.,max(0,i-5)*.15)
                    xx,yy,zz=np.meshgrid(np.linspace(2.8,3.2,8),np.linspace(-.15,.15,5),np.linspace(height-.3,height+.3,8))
                else:
                    xx,yy,zz=np.meshgrid(np.linspace(2.3,3.7,12),np.linspace(-.2,.2,5),np.linspace(.1,.4,4))
                xyz=np.column_stack((xx.ravel(),yy.ravel(),zz.ravel()))
                candidate=rebuild_candidate(xyz,np.arange(len(xyz)),ground=ground,frame_id='sensor')
                obs=dict(session_id='s',track_id='T1',time_epoch=0,action_generation=0,selection_version=0,
                         calibration_version='ground1',source_stamp_s=i*.1,track_status='locked',position_predicted=False,candidate=candidate)
                f=extractor.update(obs)
                states.append(event.update(f,obs)['state'])
                poses.append(posture.update(f,record(i),('s','ground1'))['state'])
            self.assertEqual(poses[-1],'lying_candidate')
            self.assertNotIn('confirmed',states)
            self.assertEqual('suspected' in states,dynamic)

    def test_duration_pending_reason_preserves_low_state(self):
        state=FallStateMachine('s');state._descent_seen=True;state._low_since_s=0
        result=state._classify({'height_median_m':.3,'horizontal_extent_m':1.,'height_m':{'max':.4}},False,None,.5)
        self.assertEqual(result[0],'low_posture_unclassified')
        self.assertIn('low_posture_duration_pending',result[1])


if __name__=='__main__':unittest.main()
