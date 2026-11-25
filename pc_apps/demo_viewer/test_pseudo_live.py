import unittest
import numpy as np
from pseudo_live import Activity, target_geometry, target_rectangle
from session_compare import display_basis
from target_expansion import supplemental
from types import SimpleNamespace

def obs(i, **changes):
    record=dict(frame=i,time_s=i*.1,generation=0,target_track_id='t1',target_source_rows=[1,2])
    record.update(changes)
    return record

def rule(measured=True, state='unknown', posture='unknown', **changes):
    f=dict(observable=measured,ground_relative=True,height_m={'max':.4},height_median_m=.2,horizontal_extent_m=.8)
    f.update(changes)
    return dict(features=f,state={'state':state},posture={'state':posture})

class ActivityTests(unittest.TestCase):
    def test_low_is_candidate_not_confirmed(self):
        classifier=Activity()
        for i in range(32): result=classifier.update(rule(),obs(i),('source',))
        self.assertEqual(result['label'],'low_horizontal_sustained')
        self.assertFalse(result['confirmed'])
        self.assertEqual(result['human_semantic'],'UNKNOWN')
    def test_missing_track_and_gap_reset(self):
        for replacement in (obs(20,target_source_rows=[]),obs(20,target_track_id='t2'),obs(22),obs(20,time_s=3.0),obs(20,generation=1)):
            classifier=Activity()
            for i in range(20): classifier.update(rule(),obs(i),('source',))
            result=classifier.update(rule(),replacement,('source',))
            self.assertEqual(result['level'],0)
    def test_observation_gap_breaks_low_duration(self):
        classifier=Activity()
        for i in range(20): classifier.update(rule(),obs(i),('source',))
        self.assertEqual(classifier.update(rule(observation_gap=True),obs(20),('source',))['level'],0)
    def test_descent_and_fall_suspected_remain_distinct(self):
        classifier=Activity()
        self.assertEqual(classifier.update(rule(state='descending'),obs(0),('source',))['label'],'descending')
        result=classifier.update(rule(state='suspected'),obs(1),('source',))
        self.assertEqual(result['label'],'fall_suspected')
        self.assertFalse(result['confirmed'])
    def test_missing_observation_never_reuses_old_label(self):
        classifier=Activity()
        classifier.update(rule(posture='standing'),obs(0),('source',))
        self.assertEqual(classifier.update(rule(False,posture='standing'),obs(1),('source',))['label'],'unknown')

    def test_full_target_coordinates_in_ground_frame_and_empty(self):
        xyz=np.array([[1.,2.,3.],[2.,4.,7.],[8.,6.,5.]])
        basis=display_basis([0.,0.,1.])
        result=target_geometry(xyz,[0,1,2],basis,-1.)
        np.testing.assert_allclose(result['center_m'],[2.,4.,4.])
        np.testing.assert_allclose(result['min_m'],[1.,2.,2.])
        np.testing.assert_allclose(result['max_m'],[8.,6.,6.])
        self.assertIsNone(target_geometry(xyz,[],basis,-1.))

    def test_depth_rectangle_tracks_rotation_and_empty(self):
        valid=np.ones((3,4),dtype=bool)
        rows=np.arange(12).reshape(3,4)
        self.assertEqual(target_rectangle(valid,rows,[0,6]),[1,1,3,2])
        self.assertIsNone(target_rectangle(valid,rows,[]))

    def test_expansion_keeps_existing_target_and_refuses_competing_track(self):
        h,w=4,4
        grid=SimpleNamespace(shape=(h,w))
        indices=np.arange(h*w).reshape(h,w)
        xyz=np.column_stack((indices.ravel()*.01,np.zeros(h*w),np.ones(h*w)))
        frame=SimpleNamespace(grid=grid,valid=np.ones((h,w),bool),
                              source_rows=indices,range_m=np.ones((h,w)),xyz=xyz)
        bg=SimpleNamespace(known=np.ones((h,w),bool),mean_m=np.full((h,w),1.25))
        record=dict(target_track_id='A',target_source_rows=[0,1,2,3,4,5],tracks=[])
        result=supplemental(frame,bg,record,np.eye(3),0.)
        self.assertEqual(result['status'],'candidate')
        self.assertFalse(set(result['source_rows']) & set(record['target_source_rows']))
        self.assertEqual(result['added'],10)
        record['tracks']=[dict(track_id='B',observed=True,source_rows=[15])]
        result=supplemental(frame,bg,record,np.eye(3),0.)
        self.assertEqual(result['reason'],'other_observed_track')
        self.assertEqual(result['source_rows'],[])
        record['tracks']=[]
        record['target_source_rows']=[0]
        self.assertEqual(supplemental(frame,bg,record,np.eye(3),0.)['reason'],
                         'expanded_points_exceed_threefold')
        record['target_source_rows']=[]
        self.assertEqual(supplemental(frame,bg,record,np.eye(3),0.)['status'],'no_target')

    def test_exploration_keeps_seed_and_excludes_new_near_ground(self):
        h,w=4,4
        indices=np.arange(h*w).reshape(h,w)
        xyz=np.column_stack((indices.ravel()*.01,np.zeros(h*w),np.ones(h*w)*.2))
        xyz[0,2]=.05
        xyz[15,2]=.05
        frame=SimpleNamespace(grid=SimpleNamespace(shape=(h,w)),valid=np.ones((h,w),bool),
                              source_rows=indices,range_m=np.ones((h,w)),xyz=xyz)
        bg=SimpleNamespace(known=np.ones((h,w),bool),mean_m=np.full((h,w),1.25))
        record=dict(target_track_id='A',target_source_rows=[0,1,2,3,4,5],tracks=[])
        result=supplemental(frame,bg,record,np.eye(3),0.,delta_m=.15)
        self.assertEqual(result['status'],'candidate')
        self.assertNotIn(15,result['source_rows'])
        self.assertNotIn(0,result['source_rows'])
        with self.assertRaises(ValueError):
            supplemental(frame,bg,record,np.eye(3),0.,delta_m=.05)

if __name__=='__main__': unittest.main()
