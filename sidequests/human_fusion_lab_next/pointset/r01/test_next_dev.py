import copy
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from actions import OUT, read, sha
from core import skeleton
from next_contract import validate_meta, FrozenRun
from next_dev import CANDIDATES, CausalSelection, conditional_graph, validate_run_contract, selection_key,validate_source_directory
from next_temporal import RecentEvent, RecentNonLowEvent, RecentAxis, WeakContinuation


class NextContracts(unittest.TestCase):
    def setUp(self):
        self.cfg=read(OUT/'RUN_MANIFEST.json')['config']
        rng=np.random.RandomState(8)
        self.stand=rng.uniform([1,.7,.1],[1.3,1,1.8],(600,3))
        self.low=rng.uniform([.8,.7,.1],[2,1,.3],(600,3))
        self.ids=np.arange(600)

    def test_recent_event_clears_missing_and_stale_standing(self):
        event=RecentEvent(self.cfg)
        event.update(0,0,'A',self.stand,self.ids)
        event.update(.1,1,None,self.stand,np.empty(0,int))
        emitted=[]
        for i in range(20):emitted.append(event.update(.2+i*.1,i+2,'A',self.low,self.ids)['event'])
        self.assertFalse(any(emitted))
        event=RecentEvent(self.cfg)
        event.update(0,0,'A',self.stand,self.ids)
        for i in range(1,40):
            row=event.update(i*.1,i,'A',self.low,self.ids)
            if i>20:self.assertIsNone(row['armed'])

    def test_fast_and_slow_have_source_evidence_no_true_fall_claim(self):
        for transition,low,expected in [(.1,self.low,'FAST_DESCENT_TO_LOW'),(1.6,self.low+.3,'SLOW_DESCENT_TO_LOW')]:
            event=RecentEvent(self.cfg);event.update(0,0,'A',self.stand,self.ids)
            if transition>1:
                for i in range(1,16):event.update(i*.1,i,'A',self.low+.6,self.ids)
            outputs=[event.update(transition+i*.1,i+1,'A',low,self.ids) for i in range(17)]
            events=[r['event'] for r in outputs if r['event']]
            self.assertEqual(len(events),1)
            self.assertFalse(events[0]['confirmed'])
            self.assertEqual(events[0]['kind'],expected)
            self.assertEqual(events[0]['before']['source_rows'],self.ids.tolist())
            self.assertLess(events[0]['before']['device_time'],events[0]['after']['device_time'])

    def test_hold_does_not_dilute_fast_descent(self):
        event=RecentEvent(self.cfg);event.update(0,0,'A',self.stand,self.ids)
        low=self.low+.3
        first=event.update(.1,1,'A',low,self.ids)
        self.assertIsNone(first['event'])
        outputs=[event.update(.2+i*.1,i+2,'A',low,self.ids) for i in range(20)]
        emitted=[r['event'] for r in outputs if r['event']]
        self.assertEqual(len(emitted),1)
        self.assertEqual(emitted[0]['kind'],'FAST_DESCENT_TO_LOW')
        self.assertAlmostEqual(emitted[0]['after']['device_time'],.1)
        self.assertGreaterEqual(emitted[0]['low_confirmation']['device_time'],1.6)

    def test_nonlow_reference_r2_survives_slow_transition_without_unbounded_standing(self):
        event=RecentNonLowEvent(self.cfg);event.update(0,0,'A',self.stand,self.ids)
        # Standing is now older than 2s; the recent measured non-low plateau is reliable.
        for i in range(1,31):event.update(i*.1,i,'A',self.low+.6,self.ids)
        outputs=[event.update(3.1+i*.1,31+i,'A',self.low+.3,self.ids) for i in range(17)]
        emitted=[r['event'] for r in outputs if r['event']]
        self.assertEqual(len(emitted),1)
        self.assertGreaterEqual(emitted[0]['before']['device_time'],1.1)
        self.assertIn('reliability',emitted[0]['before'])
        event.update(5,50,None,self.low,np.empty(0,int))
        self.assertFalse(event.nonlow)

    def test_axis_identity_time_and_support(self):
        axis=RecentAxis(self.cfg);sk=skeleton(self.stand,self.ids,self.cfg)
        axis.update(0,0,'A',self.stand,self.ids,sk)
        result=axis.update(.1,1,'B',self.stand,self.ids,sk)
        self.assertIsNone(result['orientation']['reference'])
        axis.update(.05,2,'B',self.stand,self.ids,sk)
        result=axis.update(.2,3,None,self.stand,np.empty(0,int),skeleton(np.empty((0,3)),np.empty(0,int),self.cfg))
        self.assertIsNone(axis.reference)

    def test_caller_config_copy(self):
        cfg=copy.deepcopy(self.cfg);state=CausalSelection(cfg);cfg['max_gap_s']=999
        self.assertEqual(state.cfg['max_gap_s'],.5)
        cfg=copy.deepcopy(self.cfg);state=RecentEvent(cfg);cfg['lying_hold_s']=999
        self.assertEqual(state.cfg['lying_hold_s'],1.5)

    def test_graph_permutation_symmetry_and_full_current_members(self):
        p=self.low.copy();cfg=copy.deepcopy(self.cfg);cfg['cluster_min_points']=1
        for rule in CANDIDATES.values():
            groups,graph=conditional_graph(p,cfg,rule,np.ones(len(p)),.05)
            order=np.random.RandomState(2).permutation(len(p))
            other,_=conditional_graph(p[order],cfg,rule,np.ones(len(p)),.05)
            self.assertEqual({frozenset(g.tolist()) for g in groups},{frozenset(order[g].tolist()) for g in other})
            ids=np.concatenate(groups);self.assertEqual(len(ids),len(p));self.assertEqual(len(np.unique(ids)),len(p))
            self.assertTrue(np.all(graph['local_scale_m']>=.1));self.assertTrue(np.all(graph['local_scale_m']<=.17))
            np.testing.assert_array_equal(p,self.low)

    def test_weak_never_starts_and_ambiguity_lost(self):
        tracker=WeakContinuation(self.cfg);fg=np.arange(600);groups=[np.arange(100)]
        ids,identity,status=tracker.update(0,groups,self.low,fg)
        self.assertEqual(len(ids),0);self.assertIsNone(identity)
        tracker.update(.1,[fg],self.low,fg)
        ids,_,_=tracker.update(.2,[np.arange(100),np.arange(100,200)],self.low,fg)
        self.assertEqual(len(ids),0)
        ids,_,_=tracker.update(.8,[np.arange(100)],self.low,fg);self.assertEqual(len(ids),0)

    def test_schema_offsets_time_and_truncation(self):
        m={'format':'human_capture_session','format_version':1,'point_stride_bytes':28,'total_points':1,
           'frames':[{'offset_points':0,'count_points':1,'stamp_sec':1,'stamp_nanosec':0}]}
        validate_meta(m,28)
        for key,value in [('format_version',2),('point_stride_bytes',True),('total_points',1.0)]:
            bad=copy.deepcopy(m);bad[key]=value
            with self.assertRaises(ValueError):validate_meta(bad,28)
        with self.assertRaises(ValueError):validate_meta(m,27)
        bad=copy.deepcopy(m);bad['frames'][0]['stamp_nanosec']=1000000000
        with self.assertRaises(ValueError):validate_meta(bad,28)

    def test_zero_not_na_and_manifest_candidates_are_authoritative(self):
        record={'axis_missing':0,'slot_jump_m':{'P95':0.},'cpu_ms':{'P95':1.}}
        self.assertEqual(selection_key([record],'G1')[1],0.)
        manifest={'schema':'hfus-next/1','code_sha256':{},'transforms':{},'candidates':copy.deepcopy(CANDIDATES)}
        validate_run_contract(manifest)
        manifest['candidates']['G1_fixed']['radius_max_m']=.99
        with self.assertRaises(ValueError):validate_run_contract(manifest)
        manifest['candidates']=copy.deepcopy(CANDIDATES)
        manifest['transforms']={str(Path(__file__)):'0'*64}
        with self.assertRaises(ValueError):validate_run_contract(manifest)

    def test_producer_rejects_source_schema_before_computation(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);(p/'points.bin').write_bytes(b'\x00'*28)
            (p/'meta.json').write_text(json.dumps({'format':'human_capture_session','format_version':2,'point_stride_bytes':28,'total_points':1,'frames':[]}),encoding='utf8')
            with self.assertRaises(ValueError):validate_source_directory(p)

    def test_prefix_selection_deterministic(self):
        def sequence(n):
            state=CausalSelection(self.cfg);result=[]
            for i in range(n):
                p=self.stand if i<4 else self.low
                ids,identity,posture,_=state.update(i*.1,[self.ids],p,self.ids)
                result.append((ids.tolist(),identity,posture))
            return result
        full=sequence(10)
        for end in range(1,11):self.assertEqual(sequence(end),full[:end])

    def test_frozen_reader_rejects_bad_schema_and_same_id_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            e=Path(directory);sid='s';(e/'runs/A'/sid).mkdir(parents=True);(e/'common'/sid).mkdir(parents=True)
            put=lambda path,obj:path.write_text(json.dumps(obj),encoding='utf8')
            manifest={'schema':'hfus-next/1','run_id':e.name,'source_sha256':{sid:{'meta':'m','points':'p'}},'code_sha256':{}}
            put(e/'RUN_MANIFEST.json',manifest);put(e/'catalog.json',{'sessions':[{'session_id':sid,'available_frames':[0]}]})
            np.savez(e/'common'/sid/'0000.npz',xyz=np.zeros((1,3)))
            np.savez(e/'runs/A'/sid/'0000_members.npz',selected=np.array([0]))
            row={'schema':'hfus-next-frame/1','run_id':e.name,'variant':'A','session_id':sid,'frame_index':0,'body_3d':[],'semantic':{},'source_sha256':manifest['source_sha256'][sid],
                 'manifest_sha256':sha(e/'RUN_MANIFEST.json'),'code_sha256':{},'common_sha256':sha(e/'common'/sid/'0000.npz'),
                 'member_sha256':sha(e/'runs/A'/sid/'0000_members.npz')}
            put(e/'runs/A'/sid/'0000.json',row)
            files={str(p.relative_to(e)).replace('\\','/'):sha(p) for p in e.rglob('*') if p.is_file() and p.name!='RUN_MANIFEST.json'}
            index={'schema':'hfus-next-index/1','manifest_sha256':sha(e/'RUN_MANIFEST.json'),'groups':['A'],'files':files}
            put(e/'ARTIFACT_INDEX.json',index)
            run=FrozenRun(e);result=run.frame(sid,0,'A');self.assertEqual(result['source_sha256'],row['source_sha256'])
            row['schema']='bad';put(e/'runs/A'/sid/'0000.json',row)
            with self.assertRaises(ValueError):run.frame(sid,0,'A')
            index['files']['runs/A/s/0000.json']=sha(e/'runs/A'/sid/'0000.json');put(e/'ARTIFACT_INDEX.json',index)
            run=FrozenRun(e)
            with self.assertRaises(ValueError):run.frame(sid,0,'A')
            put(e/'catalog.json',{'sessions':[]})
            with self.assertRaises(ValueError):FrozenRun(e)


if __name__=='__main__':unittest.main()
