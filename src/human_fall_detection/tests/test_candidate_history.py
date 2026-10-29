"""Known synthetic surfaces exercise history contracts, not human accuracy."""

# Explicit legacy acquisition keeps these original lifecycle contracts covered.
import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.candidate_history import CandidateHistory
from core.target_acquisition import TargetAcquisition
from core.tracking import TargetTracker
from core.lidar_candidates import build_snapshot
from core.pipeline import ReplayPipeline
from core.node_runtime import FallNodeCore
from test_hf07_node import VALID_GROUND


GROUND = dict(status='valid', normal=[0., 0., 1.], offset_m=0.)


def surface(x, n=60):
    return np.column_stack((np.full(n, x), np.linspace(.01, .29, n), np.linspace(.1, 1.7, n)))


def item(cid, points, rows):
    return dict(candidate_id=cid, center_source_m=np.median(points, axis=0).tolist(),
                point_count=len(points), evidence_indices=list(rows), semantic='unknown',
                ground_relative_available=True,
                height_m=dict(min=.1, p10=.2, median=.9, p90=1.6, max=1.7),
                horizontal_extent_m=dict(max=.3))


class CandidateHistories(unittest.TestCase):
    def test_ids_follow_support_not_sort_order_or_row_number(self):
        p = np.vstack((surface(2), surface(4)))
        a, b = item('c0', p[:60], range(60)), item('c1', p[60:], range(60, 120))
        h = CandidateHistory()
        first = h.step([a, b], 0., ('s', 'g'), points=p, frame_seq=0, ground=GROUND)
        saved = copy.deepcopy(first)
        a['candidate_id'], b['candidate_id'] = 'c1', 'c0'
        for c in (a, b):
            c['source_rows'] = [r+1000 for r in c['evidence_indices']]
        h.step([b, a], .1, ('s', 'g'), points=p, row_offset=1000, frame_seq=1, ground=GROUND)
        ids = {r['candidate_id']:r['history_id'] for r in h.ledger}
        self.assertEqual(ids['c1'], first['candidates'][0]['history_id'])
        self.assertEqual(ids['c0'], first['candidates'][1]['history_id'])
        self.assertEqual(h.ledger[1]['observed_frames'], 2)
        self.assertEqual(h.ledger[1]['membership']['added_source_rows'], [])
        self.assertEqual(first, saved)
        json.dumps(h.ledger, allow_nan=False)

    def test_static_plane_at_quantization_boundary_keeps_history(self):
        h = CandidateHistory()
        ids = []
        for i in range(12):
            p = surface(2.+(-1 if i % 2 else 1)*1e-6)
            h.step([item('c', p, range(len(p)))], i*.1, ('s',), points=p, ground=GROUND)
            ids.append(h.ledger[0]['history_id'])
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(h.ledger[0]['observed_frames'], 12)
        self.assertEqual(h.ledger[0]['semantic'], 'unknown')

    def test_initial_static_and_move_then_stop_never_become_background(self):
        a = TargetAcquisition(TargetTracker('s'), {'human_entry_gate': False})
        for i in range(24):
            p = surface(2.+min(i, 8)*.005)
            result = a.step([item('c%d' % (i%3), p, range(len(p)))], 0, i*.1,
                            points=p, frame_seq=i, ground=GROUND)
        self.assertEqual(result[0]['track_status'], 'locked')
        self.assertEqual(a.history.ledger[0]['observed_frames'], 24)
        self.assertEqual(result[1]['semantic'], 'unknown')
        self.assertIsNotNone(result[2])
        self.assertEqual(a.history.ledger[0]['source_rows'], list(range(len(p))))

    def test_competition_retains_all_stationary_histories(self):
        a = TargetAcquisition(TargetTracker('s'), {'human_entry_gate': False})
        p = np.vstack((surface(2), surface(4)))
        candidates = [item('a', p[:60], range(60)), item('b', p[60:], range(60,120))]
        for i in range(12):
            state, acq, observed = a.step(candidates, 0, i*.1, points=p, ground=GROUND)
        self.assertEqual(acq['status'], 'ambiguous')
        self.assertIsNone(observed)
        self.assertEqual([r['observed_frames'] for r in a.history.ledger], [12,12])
        self.assertIsNone(state['track_id'])

    def test_merge_topology_outside_center_gate_and_persistent_conflict(self):
        a = TargetAcquisition(TargetTracker('s'), {'human_entry_gate': False, 'support_history_guard':True})
        left, right = surface(2.,30), surface(2.6,60)
        for i in range(7):
            state, _, _ = a.step([item('a',left,range(30))], 0, i*.1, points=left, ground=GROUND)
        self.assertEqual(state['track_status'], 'locked')
        p = np.vstack((left,right))
        a.step([item('a',left,range(30)),item('b',right,range(30,90))],0,.7,points=p,ground=GROUND)
        for i in range(3):
            state, acq, observed = a.step([item('merge',p,range(90))],0,.8+i*.1,points=p,ground=GROUND)
            self.assertIsNone(observed)
            self.assertTrue(state['position_predicted'])
            self.assertEqual(acq['reason'], 'support_split_merge_conflict')
            self.assertTrue(a.history.ledger[0]['association']['unresolved_ancestors'])
        self.assertEqual(a.history.ledger[0]['source_rows'], list(range(90)))

    def test_split_departure_and_measurement_deltas_are_explicit(self):
        h = CandidateHistory()
        left, right = surface(2),surface(2.3)
        p = np.vstack((left,right))
        h.step([item('all',p,range(120))],0.,('s',),points=p,frame_seq=0)
        h.step([item('l',left,range(60)),item('r',right,range(60,120))],.1,('s',),points=p,frame_seq=1)
        self.assertTrue(all(r['association']['status']=='support_conflict' for r in h.ledger))
        self.assertEqual(h.departed[0]['source_rows'],list(range(120)))
        h.step([], .2, ('s',), points=p, frame_seq=2)
        self.assertEqual(len(h.departed),2)
        self.assertEqual(h.departed[0]['reason'],'no_current_support')
        self.assertEqual(h.ledger,[])

    def test_conflict_membership_uses_all_linked_predecessors(self):
        left, right, extra = surface(2., 30), surface(2.6, 30), surface(3.2, 30)
        p = np.vstack((left, right))
        h = CandidateHistory()
        h.step([item('l', left, range(30)), item('r', right, range(30, 60))],
               0., ('s',), points=p, frame_seq=0)
        merged = np.vstack((left, right, extra))
        rows = list(range(30)) + list(range(30, 60)) + list(range(60, 90))
        h.step([item('m', merged, rows)], .1, ('s',), points=merged, frame_seq=1)
        record = h.ledger[0]
        self.assertEqual(record['association']['status'], 'support_conflict')
        self.assertEqual(len(record['membership']['compared_history_ids']), 2)
        self.assertEqual(record['membership']['comparison'],
                         'spatial_cells_against_all_linked_previous_histories')
        self.assertEqual(record['membership']['added_source_rows'], list(range(60, 90)))
        self.assertEqual(record['membership']['removed_source_rows'], [])
        self.assertEqual(set(record['membership']['added_source_rows']) & set(range(60)), set())

    def test_split_membership_reports_rows_lost_from_previous_support(self):
        left, right = surface(2.), surface(2.6)
        p = np.vstack((left, right))
        h = CandidateHistory()
        h.step([item('all', p, range(120))], 0., ('s',), points=p, frame_seq=0)
        h.step([item('l', left, range(60))], .1, ('s',), points=left, frame_seq=1)
        record = h.ledger[0]
        self.assertEqual(record['membership']['removed_source_rows'], list(range(60, 120)))
        self.assertEqual(record['membership']['added_source_rows'], [])

    def test_change_gate_acquires_unique_moving_candidate_without_static_competitor(self):
        static = surface(2.)
        results = []
        a = TargetAcquisition(TargetTracker('s'), {'human_entry_gate': False, 'change_gate': True})
        for i in range(25):
            moving = surface(4. + .02 * i)
            p = np.vstack((static, moving))
            state, acq, observed = a.step(
                [item('s', static, range(60)), item('m', moving, range(60, 120))],
                0, i * .1, points=p, ground=GROUND)
            results.append((state, acq, observed))
        self.assertEqual(results[-1][0]['track_status'], 'locked')
        self.assertEqual(results[-1][2]['candidate_id'], 'm')
        self.assertEqual(results[-1][1]['selection_basis'],
                         'causal_change_not_human_classification')
        self.assertEqual(results[-1][1]['change_gate'], 'experimental_causal_change')
        self.assertIn(results[-1][1]['reason'], ('unique_causal_change', 'associated'))
        # Default gate off: the same competition stays ambiguous.
        b = TargetAcquisition(TargetTracker('s'), {'human_entry_gate': False})
        for i in range(25):
            moving = surface(4. + .02 * i)
            p = np.vstack((static, moving))
            state, acq, observed = b.step(
                [item('s', static, range(60)), item('m', moving, range(60, 120))],
                0, i * .1, points=p, ground=GROUND)
        self.assertEqual(state['track_status'], 'unselected')
        self.assertEqual(acq['status'], 'ambiguous')

    def test_change_gate_keeps_unique_static_boot_candidate(self):
        a = TargetAcquisition(TargetTracker('s'), {'human_entry_gate': False, 'change_gate': True})
        for i in range(8):
            p = surface(2.)
            state, acq, observed = a.step([item('c', p, range(60))], 0, i * .1,
                                          points=p, ground=GROUND)
        self.assertEqual(state['track_status'], 'locked')
        self.assertEqual(acq['selection_basis'],
                         'unique_persistent_geometry_not_human_classification')

    def test_change_gate_rejects_multiple_moving_candidates(self):
        a = TargetAcquisition(TargetTracker('s'), {'human_entry_gate': False, 'change_gate': True})
        for i in range(25):
            left = surface(4. + .02 * i)
            right = surface(5. + .02 * i)
            p = np.vstack((left, right))
            state, acq, observed = a.step(
                [item('l', left, range(60)), item('r', right, range(60, 120))],
                0, i * .1, points=p, ground=GROUND)
        self.assertIsNone(state['track_id'])
        self.assertEqual(acq['status'], 'ambiguous')
        self.assertEqual(acq['reason'], 'competing_change_candidates')

    def test_history_hold_gate_refuses_different_history_identity(self):
        a = TargetAcquisition(TargetTracker('s'), {'human_entry_gate': False, 'history_hold_gate': True})
        for i in range(7):
            p = surface(2.)
            state, acq, observed = a.step([item('a', p, range(60))], 0, i * .1,
                                          points=p, ground=GROUND)
        self.assertEqual(state['track_status'], 'locked')
        p = surface(2.2)
        state, acq, observed = a.step([item('b', p, range(60))], 0, .7,
                                      points=p, ground=GROUND)
        self.assertEqual(state['track_status'], 'occluded')
        self.assertIsNone(observed)
        self.assertEqual(acq['reason'], 'history_identity_conflict')
        self.assertEqual(acq['history_hold_gate'], 'experimental_same_history')

    def test_invalid_rows_do_not_acquire_or_hold(self):
        p = surface(2)
        for rows in ([0]*60,range(1,61),range(59)):
            a = TargetAcquisition(TargetTracker('s'), {'human_entry_gate': False})
            for i in range(8):
                state, acq, observed = a.step([item('c',p,rows)],0,i*.1,points=p)
                self.assertIsNone(observed)
                self.assertEqual(acq['rejected']['c'],'invalid_source_support')
            self.assertIsNone(state['track_id'])

    def test_faults_and_binding_clear_observed_history(self):
        p = surface(2)
        for fault in ('time','epoch','coordinate','ground','invalid','gap'):
            a = TargetAcquisition(TargetTracker('s'), {'human_entry_gate': False})
            for i in range(4):a.step([item('c',p,range(60))],0,i*.1,points=p,ground=GROUND)
            args=dict(time_epoch=0,source_stamp_s=.4,coordinate_version=None,ground=GROUND)
            if fault=='time':args['source_stamp_s']=.3
            if fault=='epoch':args['time_epoch']=1
            if fault=='coordinate':args['coordinate_version']='other'
            if fault=='ground':args['ground']=dict(GROUND,offset_m=.1)
            if fault=='invalid':args['valid']=False
            if fault=='gap':args['source_stamp_s']=1.
            state, _, _=a.step([item('c',p,range(60))],points=p,**args)
            self.assertIsNone(state['track_id'])
            self.assertLessEqual(len(a.history.ledger),1)
            if a.history.ledger:self.assertEqual(a.history.ledger[0]['observed_frames'],1)

    def test_prefix_and_repeat_are_exact(self):
        def run(n):
            h=CandidateHistory();result=[]
            for i in range(n):
                p=surface(2.+min(i,8)*.005)
                summary=h.step([item('c%d'%(i%3),p,range(60))],i*.1,('s','g'),points=p,frame_seq=i,ground=GROUND)
                result.append(dict(summary=summary,ledger=h.ledger,departed=h.departed))
            return result
        self.assertEqual(run(12),run(24)[:12])
        self.assertEqual(run(24),run(24))

    def test_prediction_does_not_append_measurements(self):
        p=surface(2);a=TargetAcquisition(TargetTracker('s'), {'human_entry_gate': False})
        for i in range(7):a.step([item('c',p,range(60))],0,i*.1,points=p)
        state, _, observed=a.step([],0,.7,points=p)
        self.assertTrue(state['position_predicted'])
        self.assertIsNone(observed)
        self.assertEqual(a.history.ledger,[])

    def test_ground_reload_clears_pending_and_status_immediately(self):
        p=np.stack(np.meshgrid(np.linspace(1.9,2.1,7),np.linspace(-.1,.1,7),
                               np.linspace(-1.35,.1,20)),-1).reshape(-1,3)
        for count in (4,8):
            core=FallNodeCore('s',ground=copy.deepcopy(VALID_GROUND),target_mode='automatic', settings={'acquisition': {'human_entry_gate': False}})
            for i in range(count):
                t=100+i*.1; sec=int(t); ns=round((t-sec)*1e9)
                core.process(p,t,seq=i,stamp_secs=sec,stamp_nsecs=ns,now=t)
            self.assertTrue(core.acquisition.history.ledger)
            new_ground=copy.deepcopy(VALID_GROUND);new_ground['offset_m']+=.1
            core.apply_ground_context(ground=new_ground)
            state=core.status_state(100+(count-1)*.1)
            self.assertEqual(state['acquisition']['reason'],'ground_derived_changed')
            self.assertEqual(state['acquisition']['status'],'searching')
            self.assertIsNone(state['track_id'])
            self.assertEqual(core.acquisition.history.ledger,[])
            self.assertEqual(core.acquisition._count,0)

    def test_board_status_publishes_compact_history_not_source_rows(self):
        p=np.stack(np.meshgrid(np.linspace(1.9,2.1,7),np.linspace(-.1,.1,7),
                               np.linspace(-1.35,.1,20)),-1).reshape(-1,3)
        core=FallNodeCore('s',ground=copy.deepcopy(VALID_GROUND),target_mode='automatic', settings={'acquisition': {'human_entry_gate': False}})
        for i in range(6):
            t=100+i*.1; sec=int(t); ns=round((t-sec)*1e9)
            core.process(p,t,seq=i,stamp_secs=sec,stamp_nsecs=ns,now=t)
        state=core.status_state(100.5)
        candidate=state['acquisition']['candidate_history']['candidates'][0]
        self.assertNotIn('source_rows',candidate)
        self.assertGreater(candidate['source_row_count'],0)
        self.assertEqual(len(candidate['source_rows_sha256']),64)
        self.assertEqual(state['acquisition']['history_policy'],'evidence_only')


if __name__ == '__main__':unittest.main()
