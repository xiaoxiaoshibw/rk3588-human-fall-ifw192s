"""Synthetic software contracts only; no human classification claim."""

# Explicit legacy acquisition keeps these original lifecycle contracts covered.
import copy
import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.tracking import TargetTracker
from core.target_acquisition import TargetAcquisition
from core.pipeline import ReplayPipeline
from core.node_runtime import FallNodeCore
from core.lidar_candidates import build_snapshot
from core import lidar_candidates
from test_hf07_node import VALID_GROUND


def candidate(cid='a', x=2., low=False):
    return dict(candidate_id=cid, center_reference_m=[x, 0., .3 if low else 1.],
                ground_relative_available=True, point_count=100,
                height_m=dict(min=.1, p10=.15, median=.3 if low else 1.,
                              p90=.45 if low else 1.6, max=.5 if low else 1.7),
                horizontal_extent_m=dict(max=.5), semantic='unknown')


class AutomaticTarget(unittest.TestCase):
    def setUp(self):
        self.a = TargetAcquisition(TargetTracker('synthetic'), {'human_entry_gate': False})

    def step(self, t, candidates=None, **kwargs):
        return self.a.step([candidate()] if candidates is None else candidates, 0, t,
                           calibration_version='g1', coordinate_version='raw', **kwargs)

    def lock(self):
        for i in range(7):
            result = self.step(i * .1)
        self.assertEqual(result[0]['track_status'], 'locked')
        self.assertEqual(result[0]['history_reset_reason'], 'automatic_acquisition')
        return result

    def test_stationary_persistence_and_empty_noise(self):
        for i in range(10):
            self.assertIsNone(self.step(-2+i*.1, [])[0]['track_id'])
        for i in range(6):
            state, acq, observed = self.step(i*.1)
            self.assertEqual(acq['status'], 'acquiring')
            self.assertIsNone(observed)
        self.assertEqual(self.step(.6)[0]['track_status'], 'locked')

    def test_competition_then_automatic_exit_from_ambiguity(self):
        for i in range(10):
            state, acq, observed = self.step(i*.1, [candidate(), candidate('b',2.2)])
            self.assertEqual(acq['status'], 'ambiguous')
            self.assertIsNone(state['track_id'])
        for i in range(7): result = self.step(1.+i*.1)
        self.assertEqual(result[0]['track_status'], 'locked')

    def test_short_occlusion_and_long_loss_new_identity(self):
        first = self.lock()[0]['track_id']
        state, _, observed = self.step(.8, [])
        self.assertTrue(state['position_predicted'])
        self.assertIsNone(observed)
        self.assertEqual(self.step(1.)[0]['track_id'], first)
        state = self.step(4.1)[0]
        self.assertEqual(state['track_status'], 'lost')
        self.assertFalse(state['requires_reselection'])
        for i in range(7): result = self.step(4.2+i*.1)
        self.assertEqual(result[0]['track_status'], 'locked')
        self.assertNotEqual(result[0]['track_id'], first)

    def test_split_ambiguity_never_produces_measurement(self):
        self.lock()
        state, acq, observed = self.step(.7, [candidate('a',1.95), candidate('b',2.05)])
        self.assertEqual(state['track_status'], 'ambiguous')
        self.assertIsNone(observed)
        for i in range(7): result = self.step(.8+i*.1)
        self.assertEqual(result[0]['track_status'], 'locked')
        self.assertEqual(result[0]['track_id'], 't0002')

    def test_large_cluster_rejected_low_posture_can_acquire(self):
        big=candidate();big['horizontal_extent_m']['max']=5.
        for i in range(10):
            state, acq, _=self.step(i*.1,[big])
            self.assertEqual(acq['rejected']['a'],'extent_out_of_range')
            self.assertIsNone(state['track_id'])
        for i in range(7): result=self.step(2+i*.1,[candidate(low=True)])
        self.assertEqual(result[0]['track_status'],'locked')

    def test_possible_merge_is_prediction_and_wide_low_pose_keeps_id(self):
        first=self.lock()[0]['track_id']
        merged=candidate();merged['point_count']=500;merged['horizontal_extent_m']['max']=1.5
        state,acq,observed=self.step(.7,[merged])
        self.assertEqual(acq['reason'],'possible_merge_support_jump')
        self.assertIsNone(observed)
        self.assertEqual(state['track_id'],first)
        low=candidate(low=True);low['horizontal_extent_m']['max']=1.5
        state,_,observed=self.step(.8,[low])
        self.assertEqual(state['track_id'],first)
        self.assertIsNotNone(observed)

    def test_bad_candidates_do_not_reach_association(self):
        self.lock()
        bad=candidate();bad['center_reference_m']=[float('nan'),0.,0.]
        state,_,observed=self.step(.7,[bad])
        self.assertEqual(state['track_status'],'occluded')
        self.assertIsNone(observed)

    def test_invalid_time_and_input_reset_windows(self):
        for bad in (float('nan'),float('inf'),None,.2):
            self.a=TargetAcquisition(TargetTracker('synthetic'), {'human_entry_gate': False})
            for i in range(4): self.step(i*.1)
            result=self.step(bad)
            self.assertIsNone(result[0]['track_id'])
            for i in range(6): result=self.step(1+i*.1)
            self.assertIsNone(result[0]['track_id'])
        self.lock_after_reset()
        self.assertIsNone(self.step(4., valid=False)[0]['track_id'])

    def lock_after_reset(self):
        self.a=TargetAcquisition(TargetTracker('synthetic'), {'human_entry_gate': False})
        return self.lock()

    def test_gap_epoch_coordinate_and_calibration_reset(self):
        for i in range(4): self.step(i*.1)
        self.assertEqual(self.step(1.)[1]['persistence_frames'],1)
        for key,value in [('time_epoch',1),('coordinate_version','other'),('calibration_version','g2')]:
            self.lock_after_reset()
            args=dict(time_epoch=0,calibration_version='g1',coordinate_version='raw')
            args[key]=value
            result=self.a.step([candidate()],source_stamp_s=.7,**args)
            self.assertIsNone(result[0]['track_id'])
            self.assertEqual(result[1]['reason'],'binding_changed')

    def test_raw_pipeline_and_production_core_without_requests(self):
        grid=np.stack(np.meshgrid(np.linspace(1.9,2.1,7),np.linspace(-.1,.1,7),
                                 np.linspace(-1.35,.1,20)), -1).reshape(-1,3)
        replay=ReplayPipeline('synthetic',target_mode='automatic', settings={'acquisition': {'human_entry_gate': False}});replay.ground=copy.deepcopy(VALID_GROUND)
        core=FallNodeCore('synthetic',ground=VALID_GROUND,target_mode='automatic', settings={'acquisition': {'human_entry_gate': False}})
        for i in range(12):
            t=100+i*.1;sec=int(t);ns=round((t-sec)*1e9)
            a=replay.step(grid,t,0,i)
            b=core.process(grid,t,seq=i,stamp_secs=sec,stamp_nsecs=ns,now=t)['state']
            self.assertEqual(a['track']['track_status'],b['track_status'])
            self.assertEqual(a['track']['track_id'],b['track_id'])
            self.assertEqual(a['acquisition'],b['acquisition'])
            self.assertEqual(a['target_source_rows'],b['target_source_rows'])
            self.assertEqual(b['time_epoch'], core.cloud_timebase.time_epoch)
            json.dumps(b,allow_nan=False)
        self.assertEqual(b['selection_source'],'automatic_acquisition')
        self.assertEqual(b['track_status'],'locked')
        stale_watchdog=core.status_state(104.)
        self.assertIsNone(stale_watchdog['track_id'])
        self.assertEqual(stale_watchdog['acquisition']['reason'],'required_cloud_stale')
        stale=core.process(grid,102.,seq=12,stamp_secs=102,stamp_nsecs=0,now=104.)['state']
        self.assertIsNone(stale['track_id'])
        self.assertFalse(stale['requires_reselection'])

    def test_unselected_wire_epoch_follows_source_on_start_reset_and_stale(self):
        core=FallNodeCore('synthetic',ground=VALID_GROUND,target_mode='automatic', settings={'acquisition': {'human_entry_gate': False}})
        self.assertEqual(core.status_state(99.)['time_epoch'], 0)
        points=np.empty((0,3))
        for stamp in (100., 100.1, 50.):
            result=core.process(points,stamp,seq=1,stamp_secs=int(stamp),
                                stamp_nsecs=round((stamp-int(stamp))*1e9),now=101.)
            self.assertIsNone(result['state']['track_id'])
            self.assertEqual(result['state']['time_epoch'], result['snapshot']['time_epoch'])
        self.assertEqual(result['state']['time_epoch'], 1)
        self.assertEqual(core.status_state(105.)['time_epoch'], 1)

    def test_future_frames_do_not_change_prefix(self):
        def run(n):
            a=TargetAcquisition(TargetTracker('synthetic'), {'human_entry_gate': False})
            return [a.step([candidate(x=2+i*.01)],0,i*.1) for i in range(n)]
        self.assertEqual(run(12),run(25)[:12])

    def test_raw_spatial_components_exclude_disconnected_tail_from_target(self):
        body=np.stack(np.meshgrid(np.linspace(2,2.2,7),np.linspace(0,.2,7),
                                 np.linspace(-1.3,.1,40)), -1).reshape(-1,3)
        tail=np.array([[2.01,.01,.5],[3.5,.01,.7]])
        points=np.vstack([body,tail])
        snapshot=build_snapshot(points,dict(cluster_mode='spatial_3d',cluster_cell_m=.05),
            ground=VALID_GROUND,session_id='s',time_epoch=0,snapshot_id='f')
        self.assertEqual(len(snapshot['candidates']),1)
        picked=snapshot['candidates'][0]
        self.assertEqual(picked['evidence_indices'],list(range(len(body))))
        self.assertEqual(picked['bbox_source_min_m'],body.min(0).tolist())
        self.assertEqual(picked['bbox_source_max_m'],body.max(0).tolist())
        self.assertEqual(sum(len(c['evidence_indices']) for c in snapshot['rejected_clusters']),2)

    def test_rejected_small_components_skip_features_and_preserve_rows(self):
        points=np.array([[1.,0.,.2]]*5+[[3.,0.,.2],[np.nan,0.,0.]])
        for mode in ('horizontal','spatial_3d'):
            with patch.object(lidar_candidates,'_point_features',wraps=lidar_candidates._point_features) as features:
                snapshot=build_snapshot(points,dict(cluster_mode=mode,min_cluster_points=5,
                    denoise_enabled=False),session_id='s',time_epoch=0,snapshot_id='f')
            self.assertEqual(features.call_count,1)
            self.assertEqual(snapshot['candidates'][0]['evidence_indices'],list(range(5)))
            self.assertEqual(snapshot['rejected_clusters'],[
                dict(evidence_indices=[5],reason='insufficient_points')])

    def test_spatial_components_match_pairwise_voxel_graph_at_boundaries(self):
        rng=np.random.default_rng(31)
        for dtype in (np.float32,np.float64):
            for cell in (.04,.05,.06):
                p=(rng.integers(-4,5,(80,3))*cell).astype(dtype)
                p[:30]=np.nextafter(p[:30],np.asarray(np.inf,dtype=dtype))
                p[30:60]=np.nextafter(p[30:60],np.asarray(-np.inf,dtype=dtype))
                # Independent O(N^2) point graph, including coincident cells.
                grid=np.asarray([np.floor(row/cell).astype(int) for row in p])
                adjacent=np.max(np.abs(grid[:,None,:]-grid[None,:,:]),axis=2)<=1
                remaining=set(range(len(p)));expected=[]
                while remaining:
                    pending=[min(remaining)];remaining.remove(pending[0]);group=[]
                    while pending:
                        i=pending.pop();group.append(i)
                        neighbours={j for j in remaining if adjacent[i,j]}
                        remaining-=neighbours;pending.extend(neighbours)
                    expected.append(sorted(group))
                expected.sort(key=lambda g:min(tuple(grid[i]) for i in g))
                self.assertEqual(lidar_candidates.spatial_components(p,cell),expected)

    def test_replay_ground_parameter_change_clears_lock_and_baseline(self):
        grid=np.stack(np.meshgrid(np.linspace(1.9,2.1,7),np.linspace(-.1,.1,7),
                                 np.linspace(-1.35,.1,20)),-1).reshape(-1,3)
        pipeline=ReplayPipeline('s',target_mode='automatic', settings={'acquisition': {'human_entry_gate': False}});pipeline.ground=copy.deepcopy(VALID_GROUND)
        for i in range(8):result=pipeline.step(grid,100+i*.1,0,i)
        self.assertEqual(result['track']['track_status'],'locked')
        pipeline.baseline={'status':'ready','track_id':result['track']['track_id']}
        pipeline.ground['offset_m']+=.1
        result=pipeline.step(grid,100.8,0,8)
        self.assertEqual(result['acquisition']['reason'],'binding_changed')
        self.assertIsNone(result['track']['track_id'])
        self.assertIsNone(pipeline.baseline)
        for i in range(7):result=pipeline.step(grid,101+i*.1,0,9+i)
        self.assertEqual(result['track']['track_status'],'locked')
        pipeline.ground['frame']='other'
        result=pipeline.step(grid,102.,0,20)
        self.assertIsNone(result['track']['track_id'])
        self.assertEqual(result['acquisition']['reason'],'input_unavailable')


if __name__=='__main__':unittest.main()
