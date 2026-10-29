"""Height/recent-motion entry contracts on known synthetic measurements."""
import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.target_acquisition import TargetAcquisition
from core.tracking import TargetTracker
from core.node_runtime import FallNodeCore
from core.pipeline import ReplayPipeline
from test_hf07_node import VALID_GROUND


def candidate(cid='a',x=2.,height=1.7):
    return dict(candidate_id=cid,center_source_m=[x,0.,height/2],
        ground_relative_available=True,point_count=100,
        height_m=dict(min=.1,p10=.15,median=height/2,p90=height,max=height+.1),
        horizontal_extent_m=dict(max=.5),semantic='unknown')


class HumanEntryGate(unittest.TestCase):
    def setUp(self):self.a=TargetAcquisition(TargetTracker('synthetic_entry'))

    def step(self,i,candidates=None,**kwargs):
        return self.a.step(candidates if candidates is not None else [candidate(x=2.+.06*i)],
            0,i*.1,calibration_version='g',coordinate_version='raw',**kwargs)

    def lock(self):
        for i in range(25):result=self.step(i)
        self.assertEqual(result[0]['track_status'],'locked')
        self.assertIsNotNone(result[2])
        return result[0]['track_id']

    def test_stationary_candidate_and_jitter_never_lock(self):
        for i in range(100):
            state,acq,observed=self.step(i,[candidate(x=2.+(.01 if i%2 else -.01))])
            self.assertIsNone(state['track_id']);self.assertIsNone(observed)
        self.assertEqual(acq['rejected']['a'],'entry_motion_not_observed')
        self.assertEqual(acq['semantic'],'unknown')

    def test_moving_low_and_too_tall_candidates_never_lock(self):
        for height in (.45,2.4):
            self.setUp()
            for i in range(40):
                state,acq,_=self.step(i,[candidate(x=2.+.06*i,height=height)])
                self.assertIsNone(state['track_id'])
                self.assertEqual(acq['rejected']['a'],'entry_height_out_of_range')

    def test_default_locks_unique_moving_candidate_among_stationary_competitors(self):
        for i in range(25):
            state,acq,observed=self.step(i,[candidate(x=2.+.06*i),candidate('static',x=6.),
                                          candidate('low',x=7.,height=.45)])
        self.assertEqual(state['track_status'],'locked')
        self.assertEqual(observed['candidate_id'],'a')
        self.assertEqual(acq['selection_basis'],'height_and_recent_motion_not_human_classification')

    def test_two_moving_candidates_are_ambiguous(self):
        for i in range(30):
            state,acq,_=self.step(i,[candidate(x=2.+.06*i),candidate('b',x=5.+.06*i)])
            self.assertIsNone(state['track_id'])
        self.assertEqual(acq['reason'],'competing_moving_candidates')

    def test_isolated_center_spike_is_not_motion(self):
        for i in range(60):
            state,_,_=self.step(i,[candidate(x=2.4 if i==10 else 2.)])
            self.assertIsNone(state['track_id'])

    def test_motion_uses_actual_source_points_over_candidate_metadata(self):
        points=np.column_stack((np.full(60,2.),np.linspace(0.,.3,60),np.linspace(.1,1.7,60)))
        for i in range(40):
            c=candidate(x=2.+.06*i)
            c.update(point_count=60,source_rows=list(range(60)))
            state,acq,_=self.step(i,[c],points=points)
            self.assertIsNone(state['track_id'])
        self.assertEqual(acq['entry_gate']['evidence']['a']['motion_displacement_m'],0.)

    def test_old_motion_expires_before_competitor_disappears(self):
        for i in range(50):
            x=2.+.06*min(i,10)
            items=[candidate(x=x)]
            if i<40:items.append(candidate('b',x=5.+.06*min(i,10)))
            state,acq,_=self.step(i,items)
            self.assertIsNone(state['track_id'])
        self.assertEqual(acq['rejected']['a'],'entry_motion_not_observed')
        self.assertGreater(self.a.history.ledger[0]['temporal']['net_displacement_m'],.3)

    def test_lock_holds_when_still_and_when_low(self):
        track=self.lock()
        for i in range(25,70):
            height=1.7 if i<40 else .45
            state,_,observed=self.step(i,[candidate(x=3.44,height=height)])
            self.assertEqual(state['track_id'],track)
            self.assertEqual(state['track_status'],'locked')
            self.assertIsNotNone(observed)
            self.assertFalse(state['position_predicted'])

    def test_loss_requires_fresh_motion_before_reacquisition(self):
        track=self.lock()
        for i in range(25,60):self.step(i,[])
        for i in range(60,90):
            state,_,_=self.step(i,[candidate(x=3.44)])
            self.assertIsNone(state['track_id'])
        for i in range(90,120):state,_,_=self.step(i,[candidate(x=3.44+.06*(i-90))])
        self.assertEqual(state['track_status'],'locked');self.assertNotEqual(state['track_id'],track)

    def test_coexisting_low_object_cannot_take_over_during_occlusion(self):
        for i in range(25):
            state,_,_=self.step(i,[candidate(x=2.+.06*i),candidate('low',x=6.,height=.45)])
        track=state['track_id'];self.assertIsNotNone(track)
        observed_count=0
        for i in range(25,65):
            state,acq,observed=self.step(i,[candidate('low',x=6.,height=.45)])
            observed_count+=observed is not None
            if state['track_status']=='occluded':
                self.assertEqual(acq['rejected']['low'],'known_non_target_history')
                self.assertEqual(state['track_id'],track)
        self.assertEqual(observed_count,0)
        self.assertIsNone(state['track_id'])

    def test_non_target_labels_retire_before_a_fresh_acquisition(self):
        for i in range(25):
            state,_,_=self.step(i,[candidate(x=2.+.06*i),candidate('other',x=6.)])
        first=state['track_id']
        for i in range(25,65):self.step(i,[candidate('other',x=6.)])
        for i in range(65,95):
            state,_,_=self.step(i,[candidate('other',x=6.+.06*(i-65))])
        self.assertEqual(state['track_status'],'locked')
        self.assertNotEqual(state['track_id'],first)

    def test_nearby_fragments_are_not_foreign_due_to_vertical_separation(self):
        for ground in (None,dict(VALID_GROUND,normal=[0.,0.,2.])):
            self.setUp()
            for i in range(25):
                body=candidate(x=2.+.06*i)
                fragment=candidate('fragment',x=2.25+.06*i,height=.45)
                if ground is not None:
                    fragment['center_source_m'][2]=body['center_source_m'][2]+2.
                state,acq,_=self.step(i,[body,fragment],ground=ground)
                self.assertNotEqual(acq['rejected']['fragment'],'known_non_target_history')
            self.assertEqual(state['track_status'],'locked')

    def test_merge_with_known_non_target_support_is_not_a_measurement(self):
        def surface(x,top):
            return np.column_stack((np.full(60,x),np.linspace(0.,.3,60),np.linspace(.1,top,60)))
        def item(cid,p,rows):
            c=candidate(cid,x=float(np.median(p[:,0])),height=float(np.quantile(p[:,2],.9)))
            c.update(point_count=len(p),source_rows=list(rows));return c
        for i in range(25):
            body=surface(2.+.06*i,1.7);other=surface(6.5,.45);points=np.vstack((body,other))
            state,_,_=self.step(i,[item('a',body,range(60)),item('b',other,range(60,120))],points=points)
        self.assertEqual(state['track_status'],'locked')
        state,acq,observed=self.step(25,[item('merged',points,range(120))],points=points)
        self.assertIsNone(observed)
        self.assertEqual(acq['rejected']['merged'],'known_non_target_history')
        state,acq,observed=self.step(26,[item('a',body,range(60)),item('b',other,range(60,120))],points=points)
        self.assertIsNone(observed)
        self.assertEqual(acq['rejected']['a'],'known_non_target_history')

    def test_gap_and_bad_height_reset_recent_motion(self):
        for i in range(9):self.step(i)
        state,_,_=self.step(20,[candidate(x=2.48)])
        self.assertIsNone(state['track_id'])
        for i in range(21,35):state,_,_=self.step(i,[candidate(x=2.48)])
        self.assertIsNone(state['track_id'])
        self.setUp()
        for i in range(9):self.step(i)
        self.step(9,[candidate(x=2.54,height=.45)])
        for i in range(10,30):state,_,_=self.step(i,[candidate(x=2.54)])
        self.assertIsNone(state['track_id'])

    def test_history_replacement_cannot_accumulate_pending(self):
        for i in range(30):
            # Missing candidates repeatedly break measured history before persistence.
            state,_,_=self.step(i,[] if i%8==7 else [candidate(x=2.+.06*(i%8))])
            self.assertIsNone(state['track_id'])

    def test_invalid_profile_is_rejected(self):
        for settings in ({'human_entry_gate':1},{'entry_height_min_m':3.},
                         {'entry_motion_min_frames':4},{'entry_motion_min_frames':5.5},
                         {'entry_motion_window_s':float('nan')}):
            with self.assertRaises(ValueError):TargetAcquisition(TargetTracker('s'),settings)

    def test_live_and_replay_defaults_share_ground_height_motion_gate(self):
        grid=np.stack(np.meshgrid(np.linspace(1.9,2.1,5),np.linspace(-.1,.1,5),
                                 np.linspace(-1.35,.25,30)),-1).reshape(-1,3)
        replay=ReplayPipeline('integration',target_mode='automatic');replay.ground=copy.deepcopy(VALID_GROUND)
        core=FallNodeCore('integration',ground=VALID_GROUND,target_mode='automatic')
        for i in range(45):
            points=grid+np.array([.06*max(0,min(i-10,25)),0.,0.])
            t=100.+i*.1;sec=int(t);ns=round((t-sec)*1e9)
            a=replay.step(points,t,0,i)
            b=core.process(points,t,seq=i,stamp_secs=sec,stamp_nsecs=ns,now=t)['state']
            self.assertEqual(a['track']['track_status'],b['track_status'])
            self.assertEqual(a['target_source_rows'],b['target_source_rows'])
            self.assertEqual(a['acquisition'],b['acquisition'])
            if i<10:self.assertIsNone(b['track_id'])
            json.dumps(b,allow_nan=False)
        self.assertEqual(b['track_status'],'locked')
        self.assertFalse(b['confirmed_enabled'])


if __name__=='__main__':unittest.main()
