"""Numerical/causal contracts only: no optimizer steps or trained detector."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

from event_model_numpy import (FEATURES,EPISODE,transform,NumpyEventGRU,
                               EventEvidenceRuntime,TimedScoreLatch)
from fall_candidate_runtime import file_sha256,load_candidate_runtime
from train_event_model import EventScorer,export,load_cache,preflight,normalizer
from test_fall_events import body,sequence


def evidence(height=1.2):
    return dict(valid=True,centroid_height_m=height,inclination_deg=None,
                vertical_span_m=1.7,vertical_velocity_m_s=None,points=100)


def write_cache(root,subject,session,shift=0.):
    path=root/session;path.mkdir()
    times=np.arange(31,dtype=np.float64)/10
    values=np.tile([1.2+shift,10.,1.7,0.,100.+shift,.1,1.,1.],(len(times),1))
    values[0,3:4]=np.nan;values[0,5]=np.nan
    segments=np.zeros(len(times),dtype=np.int64)
    bindings=np.asarray([json.dumps([subject,session,'c'])]*len(times))
    np.savez_compressed(path/'frames.npz',features=values,feature_mask=np.isfinite(values),
                        timestamps_s=times,segment_index=segments,bindings=bindings)
    windows=[dict(id=session+':fall',label=1,certainty='confirmed',event_start=.2,event_impact=1.2,
                  event_end=1.6,clock_uncertainty_s=.1),
             dict(id=session+':adl',label=0,certainty='confirmed',event_start=2.,event_impact=None,
                  event_end=2.8,clock_uncertainty_s=.1),
             dict(id=session+':unknown',label=None,certainty='probable')]
    doc=dict(schema='fall_event_cache_v1',feature_names=list(FEATURES),subject=subject,
             session=session,frames=len(times),windows=windows,frame_cache_sha256=file_sha256(path/'frames.npz'))
    (path/'INPUT.json').write_text(json.dumps(doc),encoding='utf-8')
    return path


class EventModelTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        torch.manual_seed(42);self.model=EventScorer(5).double().eval()
        self.mean=np.arange(8,dtype=float)/10;self.scale=np.arange(1,9,dtype=float)
        self.path=export(self.model,self.mean,self.scale,self.root/'model')

    def test_pytorch_numpy_sequence_and_reset_parity(self):
        rng=np.random.RandomState(9);raw=rng.random_sample((23,8));raw[:,4]*=100
        raw[::3,1]=np.nan;raw[0,3]=np.nan
        encoded=transform(raw,np.isfinite(raw),self.mean,self.scale)
        portable=NumpyEventGRU(self.path.parent/'weights.npz');hidden=None;ps=[]
        for row in encoded:
            p,hidden=portable.step(row,hidden);ps.append(p)
        with torch.no_grad():
            logits,expected=self.model(torch.from_numpy(encoded[None]))
        np.testing.assert_allclose(ps,torch.sigmoid(logits)[0].numpy(),atol=1e-12,rtol=1e-12)
        np.testing.assert_allclose(hidden,expected[0,0].numpy(),atol=1e-12,rtol=1e-12)
        self.assertEqual(portable.step(encoded[0])[0],ps[0])
        # A deliberately different suffix cannot change an earlier probability.
        prefix=None
        for row in encoded[:7]:p,prefix=portable.step(row,prefix)
        self.assertEqual(p,ps[6])

    def test_mask_is_distinct_and_bad_numeric_inputs_refused(self):
        raw=np.zeros(8);masked=raw.copy();masked[1]=np.nan
        a=transform(raw,np.isfinite(raw),self.mean,self.scale)
        b=transform(masked,np.isfinite(masked),self.mean,self.scale)
        self.assertEqual(b[1],0.);self.assertEqual(b[9],0.);self.assertEqual(a[9],1.)
        for bad in (np.full(8,np.inf),np.ones(8,dtype=complex)):
            with self.assertRaises(ValueError):transform(bad,np.isfinite(bad),self.mean,self.scale)
        with self.assertRaises(ValueError):transform(masked,np.ones(8,dtype=bool),self.mean,self.scale)
        with self.assertRaises(ValueError):NumpyEventGRU(self.path.parent/'weights.npz').step(np.zeros(16,dtype=complex))

    def test_float32_export_matches_training_precision(self):
        path=export(self.model.float(),self.mean,self.scale,self.root/'float32')
        raw=np.tile([1.1,40.,1.,-.3,100.,.1,1.,1.],(40,1));raw[::3,1]=np.nan
        encoded=transform(raw,np.isfinite(raw),self.mean,self.scale)
        portable=NumpyEventGRU(path.parent/'weights.npz');hidden=None;ps=[]
        for row in encoded:
            p,hidden=portable.step(row,hidden);ps.append(p)
        with torch.no_grad():logits,_=self.model(torch.from_numpy(encoded.astype(np.float32)[None]))
        np.testing.assert_allclose(ps,torch.sigmoid(logits)[0].numpy(),atol=1e-6,rtol=1e-6)

    def test_fixture_has_scores_but_no_events_and_causal_prefix(self):
        def run(rows):
            runtime=load_candidate_runtime(self.path,ground=dict(normal=[0,0,1],offset_m=0.))
            return [runtime.push(points,t,'p','g','c') for t,points in rows]
        full=run(sequence());self.assertEqual(full[:8],run(sequence()[:8]))
        self.assertTrue(any(v['fall_probability'] is not None for v in full))
        self.assertTrue(all(v['new_event'] is None and v['event_id'] is None for v in full))
        self.assertTrue(all(not v['confirmed_enabled'] for v in full))

    def test_gap_unknown_and_every_binding_component_reset_hidden(self):
        for changed in range(3):
            runtime=EventEvidenceRuntime(self.path)
            for t in np.arange(8)/10:runtime.push_evidence(evidence(),float(t),'p','g','c')
            key=['p','g','c'];key[changed]='new'
            result=runtime.push_evidence(evidence(),.8,*key)
            self.assertEqual(result['state'],'warming')
            fresh=EventEvidenceRuntime(self.path);fresh.push_evidence(evidence(),.8,*key)
            np.testing.assert_array_equal(runtime.hidden,fresh.hidden)
        self.assertEqual(runtime.push_evidence(evidence(),2.,*key)['reason'],'time_discontinuity')
        self.assertIsNone(runtime.hidden)
        self.assertEqual(runtime.push_evidence(evidence(),2.1,*key)['state'],'warming')
        self.assertEqual(runtime.push_evidence(evidence(),2.2,*key,observed=False)['reason'],'not_measured')
        self.assertIsNone(runtime.hidden)
        bad=evidence();bad['inclination_deg']='bad'
        self.assertEqual(runtime.push_evidence(bad,2.3,*key)['state'],'unknown')

    def test_contract_and_weight_tampering_refused(self):
        doc=json.loads(self.path.read_text(encoding='utf-8'))
        for field,value in (('gate_order','zrn'),('feature_names',list(reversed(FEATURES))),
                            ('model','../weights.npz'),('model_sha256','0'*64)):
            changed=dict(doc);changed[field]=value
            self.path.write_text(json.dumps(changed),encoding='utf-8')
            with self.assertRaises((ValueError,FileNotFoundError)):EventEvidenceRuntime(self.path)
        self.path.write_text(json.dumps(doc),encoding='utf-8')
        weights=self.path.parent/'weights.npz';weights.write_bytes(weights.read_bytes()+b'tampered')
        with self.assertRaisesRegex(ValueError,'SHA'):EventEvidenceRuntime(self.path)

    def test_boolean_time_cannot_advance_parallel_geometry(self):
        runtime=EventEvidenceRuntime(self.path,ground=dict(normal=[0,0,1],offset_m=0.))
        runtime.push(body(0),0.,'p','g','c')
        result=runtime.push(body(90),True,'p','g','c')
        self.assertEqual(result['reason'],'invalid_time')
        self.assertIsNone(runtime.geometry.last_time)
        self.assertIsNone(runtime.geometry.previous)
        self.assertEqual(runtime.push(body(90),1.1,'p','g','c')['state'],'warming')

    def test_geometry_gate_and_event_binding_control_probe(self):
        runtime=EventEvidenceRuntime(self.path)
        # Exercise emission logic using a constant test double. Export remains
        # explicitly UNTRAINED; no real weights are presented as a fitted model.
        runtime.manifest=dict(runtime.manifest,training_status='trained')
        with patch.object(runtime.model,'step',return_value=(.95,np.zeros(5))):
            out=[]
            for i in range(10):
                geo=dict(event_id='geo1' if i>=6 else None,
                         new_event=dict(event_id='geo1',alarm_s=i/10) if i==6 else None)
                out.append(runtime.push_evidence(evidence(),i/10,'p','g','c',geometry_output=geo))
            events=[v['new_event'] for v in out if v['new_event']]
            self.assertEqual(len(events),1)
            self.assertEqual(events[0]['model_sha256'],runtime.model_sha256)
            first=events[0]['event_id']
            for i in range(10,17):
                geo=dict(event_id='geo1' if i==16 else None,
                         new_event=dict(event_id='geo1') if i==16 else None)
                result=runtime.push_evidence(evidence(),i/10,'other','g','c',geometry_output=geo)
            self.assertNotEqual(result['new_event']['event_id'],first)
        cold=EventEvidenceRuntime(self.path)
        cold.manifest=dict(cold.manifest,training_status='trained')
        with patch.object(cold.model,'step',side_effect=[(p,np.zeros(5)) for p in [.95]*5+[.1]*3]):
            for i in range(8):
                geo=dict(event_id='geo2' if i>=6 else None,
                         new_event=dict(event_id='geo2') if i==6 else None)
                result=cold.push_evidence(evidence(),i/10,'p','g','c',geometry_output=geo)
                self.assertIsNone(result['new_event'])


class LatchTest(unittest.TestCase):
    def test_seconds_hold_release_gap_and_no_duplicate(self):
        alarms=[]
        for hz in (10,20):
            latch=TimedScoreLatch(EPISODE)
            emitted=[latch.update(.9,i/hz) for i in range(hz)]
            events=[v for v in emitted if v];self.assertEqual(len(events),1)
            alarms.append(events[0]['source_stamp_s']);active=latch.active
            latch.update(.9,5.);self.assertEqual(latch.active,active)
            for i in range(hz):latch.update(.1,5.1+i/hz)
            self.assertIsNone(latch.active)
            with self.assertRaises(ValueError):latch.update(float('nan'),7.)
        self.assertAlmostEqual(alarms[0],alarms[1])
        latch=TimedScoreLatch(EPISODE)
        for t in (0.,.2,1.,1.2):self.assertIsNone(latch.update(.9,t))


class TrainingContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.paths=[write_cache(self.root,'S'+str(i),'session'+str(i),i*10.) for i in range(3)]
        self.index=self.root/'index.json'
        self.doc=dict(train_subjects=['S0'],validation_subjects=['S1'],test_subjects=['S2'],
                      caches=[p.name for p in self.paths])
        self.save()

    def save(self):self.index.write_text(json.dumps(self.doc),encoding='utf-8')

    def test_interval_uncertainty_warmup_and_unknown_retention(self):
        record=load_cache(self.paths[0]);t,y=record['times'],record['y']
        self.assertTrue(np.all(y[t<.5]==-1));self.assertEqual(y[6],1)
        self.assertEqual(y[15],-1);self.assertEqual(y[22],0);self.assertEqual(y[-1],-1)
        self.assertEqual(record['event_audit'][-1]['reason'],'unknown_annotation')
        self.assertEqual(len(record['X']),31)

    def test_heldout_arrays_not_loaded_or_used_for_normalization(self):
        import train_event_model
        original=train_event_model.load_cache
        with patch.object(train_event_model,'load_cache',wraps=original) as loader:
            records,report=preflight(self.index)
        self.assertEqual(loader.call_count,1);self.assertTrue(report['training_ready'])
        self.assertFalse(report['test_arrays_read_for_training'])
        mean,scale=normalizer(records);self.assertAlmostEqual(mean[0],1.2)
        self.assertTrue(np.all(scale>0));self.assertEqual(report['retained_events'],3)
        self.assertEqual(len(report['training_events_without_usable_supervision']),1)

    def test_person_leak_duplicate_content_and_cache_tampering_refused(self):
        self.doc['test_subjects']=['S0'];self.save()
        with self.assertRaisesRegex(ValueError,'person-isolated'):preflight(self.index)
        self.doc['test_subjects']=['S2'];self.save()
        weights=self.paths[2]/'frames.npz';weights.write_bytes(weights.read_bytes()+b'bad')
        with self.assertRaisesRegex(ValueError,'SHA'):preflight(self.index)

    def test_invalid_contact_or_legacy_cache_requires_rebuild(self):
        path=self.paths[0]/'INPUT.json';doc=json.loads(path.read_text(encoding='utf-8'))
        old=copy.deepcopy(doc);del old['windows'][0]['event_impact'];path.write_text(json.dumps(old),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Rebuild'):load_cache(self.paths[0])
        doc['windows'][0]['event_impact']=10.;path.write_text(json.dumps(doc),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'contact'):load_cache(self.paths[0])


if __name__=='__main__':unittest.main()
