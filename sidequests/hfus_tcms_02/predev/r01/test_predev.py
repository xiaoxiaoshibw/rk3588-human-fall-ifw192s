"""Boundary checks are synthetic contracts, never human-effectiveness tests."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
import numpy as np
from contracts import ROOT, Source, digest, module, new_output, production_geometry, sha, validate_members, write_new
from pipeline import DEFAULTS, Engine, FrozenMap, ground_candidate, temporal_ground_check
from run import replay
from evaluate import evaluate
import fixtures


class PredevContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = new_output(os.environ.get('PREDEV_TEST_OUTPUT',
            str(ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_predev_r1/tests_r1')))
        cls.fixture = fixtures.build(cls.out / 'inputs')
        cls.a = Source(cls.fixture['map_entry'])
        cls.b = Source(cls.fixture['action_entry'])
        cls.ground = ground_candidate(cls.a.frame(0)['xyz'], cls.fixture['ground_spec'])
        cls.map = FrozenMap([cls.a.frame(0)], cls.fixture['authorization'])
        cls.records = replay(cls.b, cls.map, cls.ground, 'full', simulate=True)

    @classmethod
    def tearDownClass(cls):
        cls.a.close()
        cls.b.close()

    def source_variant(self, name, mutate):
        entry = fixtures.write_source(self.out / name, [np.array([[1., 0., -1.], [2., 0., -1.]])])
        meta_path = Path(entry['path']) / 'meta.json'
        meta = json.loads(meta_path.read_text(encoding='utf8'))
        mutate(meta)
        # Fixture creation only, never production/real source.
        meta_path.write_text(json.dumps(meta), encoding='utf8')
        entry['source_sha256']['meta'] = sha(meta_path)
        return entry

    def confirm_engine(self):
        engine = Engine(self.map, self.ground)
        engine.step(self.b.frame(0))
        f = self.b.frame(1)
        r = engine.step(f)
        c = min(r['candidates'], key=lambda c: abs(c['center'][0] - 1.9))
        q = dict(sid=f['sid'], fi=f['fi'], source_sha256=f['source_sha256'],
                 time_ns=f['time_ns'],
                 coordinate_version=f['coordinate_version'], candidate_version=c['version'],
                 reviewer='fixture', provenance='SYNTHETIC_SIMULATED_CONFIRMATION')
        return engine, f, r, q

    def test_strict_stride_and_layout(self):
        for name, mutate in [('badstride', lambda m:m.update(point_stride_bytes=16)),
                             ('badlayout', lambda m:m['point_layout'].update(endian='big')),
                             ('badframe', lambda m:m['frames'][0].update(offset_points=1)),
                             ('badsize', lambda m:m.update(total_points=1)),
                             ('badtime', lambda m:m['frames'][0].update(stamp_nanosec=1000000000))]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    Source(self.source_variant(name, mutate))

    def test_sha_and_truncation(self):
        entry = copy.deepcopy(self.fixture['map_entry'])
        entry['source_sha256']['points'] = '0' * 64
        with self.assertRaises(ValueError):
            Source(entry)
        entry=fixtures.write_source(self.out/'truncated',[fixtures.body()])
        path=Path(entry['path'])/'points.bin'
        with path.open('r+b') as stream:
            stream.truncate(path.stat().st_size-1)
        entry['source_sha256']['points']=sha(path)
        with self.assertRaises(ValueError):
            Source(entry)
        with self.assertRaises(ValueError):
            Source({'role':'D'})
        for role in ['D_ACTION','HOLD_OUT','DEVELOPMENT','unknown']:
            with self.assertRaises(ValueError):
                Source({'kind':'REAL_DEVELOPMENT','role':role})
        with self.assertRaises(ValueError):
            Source({'kind':'REAL_DEVELOPMENT','role':'B','independent_test':1})

    def test_reader_equivalence_to_audited_load(self):
        paths = list(sys.path)
        existing = {k:sys.modules.get(k) for k in ['next_contract','tcms']}
        try:
            sys.path.insert(0, str(ROOT / 'sidequests/hfus_tcms'))
            old = module('predev_audited_old_load', ROOT / 'sidequests/hfus_tcms/run_experiment.py')
            meta, xyz, binding = old.load(self.a.folder)
            np.testing.assert_array_equal(xyz, self.a.xyz)
            self.assertEqual(meta, self.a.meta)
            self.assertEqual(set(binding.values()), set(self.a.binding.values()))
            del xyz
        finally:
            sys.path[:] = paths
            for k,v in existing.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

    def test_row_mapping_and_illegal_members(self):
        f = self.b.frame(1)
        a = self.b.mapping(1, source_row=3)
        self.assertEqual(a, self.b.mapping(1, global_row=a['global_row']))
        for kwargs in [dict(source_row=-1), dict(source_row=len(f['xyz'])),
                       dict(global_row=f['offset'] - 1), dict(source_row=True)]:
            with self.assertRaises(ValueError):
                self.b.mapping(1, **kwargs)
        with self.assertRaises(ValueError):
            validate_members(f, [a, a])
        with self.assertRaises(ValueError):
            validate_members(f, [dict(a, sid='other')])
        with self.assertRaises(ValueError):
            validate_members(f, [dict(a, fi=0)])

    def test_empty_nan_and_conservation(self):
        for name,p in [('empty', np.empty((0,3))), ('invalid', np.array([[np.nan,0,1],[0,0,0],[1,0,0]]))]:
            e = fixtures.write_source(self.out / name, [p])
            s = Source(e)
            try:
                r = Engine().step(s.frame(0))
                self.assertEqual(len(r['current_rows']), len(p))
                self.assertEqual(r['accounting']['raw'], r['accounting']['valid'] + r['accounting']['invalid'])
            finally:
                s.close()

    def test_source_nonmonotonic_rejected(self):
        e = fixtures.write_source(self.out / 'same_time', [fixtures.body(),fixtures.body()], [1,1])
        with self.assertRaises(ValueError):
            Source(e)

    def test_time_reset_source_and_coordinate(self):
        for key,value,expected in [('time_ns',4000000000,'LONG_DEVICE_TIME_GAP'),
                                    ('coordinate_version','changed','MAP_COORDINATE_CHANGED'),
                                    ('source_sha256',{'meta':'x','points':'y'},'SOURCE_OR_COORDINATE_CHANGED')]:
            engine,f,r,q = self.confirm_engine()
            engine.confirm(f,r,q)
            f2 = self.b.frame(2)
            f2[key] = value
            r2 = engine.step(f2)
            self.assertEqual(r2['reset'], expected)
            self.assertEqual(r2['track']['state'], 'UNCONFIRMED')
            self.assertEqual(r2['map_usable'],expected=='LONG_DEVICE_TIME_GAP')
        engine = Engine()
        f=self.b.frame(1)
        engine.step(f)
        with self.assertRaises(ValueError):
            engine.step(f)

    def test_ground_missing_overlap_wall_and_wrong_priors(self):
        p,s = fixtures.plane_fixture()
        self.assertFalse(ground_candidate(p,{})['geometric_valid'])
        overlap=copy.deepcopy(s)
        overlap['validation_regions'][0]['indices'].append(0)
        g=ground_candidate(p,overlap)
        self.assertFalse(g['geometric_valid'])
        self.assertIn('overlap', str(g['reason']).lower())
        wrong=copy.deepcopy(s)
        wrong['sensor_height_interval_m']=[2.,2.1]
        self.assertFalse(ground_candidate(p,wrong)['geometric_valid'])
        wall=p[:,[2,1,0]]
        self.assertFalse(ground_candidate(wall,s)['geometric_valid'])
        spatial=p.copy()
        ids=s['validation_regions'][0]['indices']
        spatial[ids]=p[s['fit_indices'][:len(ids)]]
        g=ground_candidate(spatial,s)
        self.assertFalse(g['geometric_valid'])
        self.assertEqual(g['reason'],'VALIDATION_SPATIAL_SUPPORT_OVERLAP')

    def test_ground_table_competition_not_identity(self):
        p,s=fixtures.plane_fixture()
        # A tabletop within the explicit height interval competes with the floor.
        table=p[:len(s['fit_indices'])].copy();table[:,2]=-.93
        joined=np.concatenate([p,table])
        spec=copy.deepcopy(s)
        spec['fit_indices'] += list(range(len(p),len(joined)))
        g=ground_candidate(joined,spec)
        self.assertIsNotNone(g['candidate'])
        self.assertEqual(g['candidate']['status'],'orientation_unverified')
        self.assertTrue(g['candidate']['ambiguous'])
        self.assertEqual(g['reason'],'ground_orientation_ambiguous')
        self.assertFalse(g['identity_confirmed'])
        self.assertFalse(g['physical_verified'])

    def test_ground_roundtrip_and_flags(self):
        self.assertTrue(self.ground['geometric_valid'])
        _,cal=production_geometry()
        block=self.ground['transform']
        p=self.a.frame(0)['xyz'][:10]
        mapped=cal.apply_ground_derived(p,block)
        inv=cal.ground_derived_inverse(block)
        back=mapped @ np.array(inv['R']).T + inv['t']
        np.testing.assert_allclose(back,p,atol=1e-12)
        self.assertFalse(block['physical_verified'])
        self.assertFalse(block['applicability']['single_plane_confirmed'])
        self.assertFalse(self.ground['valid_range']['trusted'])
        self.assertEqual(temporal_ground_check(p,self.ground)['status'],'CONTRACT_ONLY')

    def test_map_authorization_freeze_and_separate_ledger(self):
        with self.assertRaises(ValueError):
            FrozenMap([self.a.frame(0)], {'confirmed_empty':False})
        before=digest(self.map.xyz.tolist())
        replay(self.b,self.map,self.ground,'full',simulate=True)
        self.assertEqual(before,digest(self.map.xyz.tolist()))
        with self.assertRaises(ValueError):
            self.map.xyz[0]=[1,2,3]
        separate=FrozenMap([self.a.frame(0)],self.fixture['authorization'])
        original=separate.fingerprint()
        separate.surfaces.centers.setflags(write=True)
        separate.surfaces.centers[0,0]+=.1
        separate.surfaces.centers.setflags(write=False)
        self.assertNotEqual(original,separate.fingerprint())
        for r in self.records:
            self.assertFalse(r['capabilities']['strong_free'])
            self.assertFalse(r['capabilities']['strong_occlusion'])
            self.assertEqual(len(r['current_rows']),r['accounting']['raw'])
            self.assertTrue(all('source_row' not in s and not s['current_member'] for s in r['map_ledger']))

    def test_background_label_not_predeleted_and_reappearance(self):
        r=self.records[0]
        self.assertTrue(any(p['label']=='bg_match' for p in r['current_rows']))
        self.assertEqual(r['accounting']['raw'],len(self.a.frame(0)['xyz']))
        reappeared=self.records[7]
        self.assertTrue(all(p['label']=='bg_match' for p in reappeared['current_rows']))
        self.assertEqual(reappeared['track']['rows'],[])

    def test_enter_stop_low_continuation_floor_bound(self):
        base=len(self.a.frame(0)['xyz'])
        self.assertTrue(self.records[1]['candidates'])
        self.assertEqual(self.records[2]['track']['state'],'MEASURED')
        low=self.records[3]
        self.assertEqual(low['track']['state'],'MEASURED')
        self.assertTrue(set(range(base,len(low['current_rows']))).issubset(low['track']['rows']))
        self.assertTrue(all(i>=base for i in low['track']['rows']))
        self.assertTrue(any(c['continuation_rows'] for c in low['candidates']))
        no=replay(self.b,self.map,self.ground,'no_continuation',simulate=True)
        self.assertEqual(no[3]['track']['rows'],[])

    def test_prediction_zero_members_device_ttl_lost(self):
        self.assertEqual(self.records[4]['track']['state'],'PREDICTED')
        self.assertEqual(self.records[4]['track']['measured_count'],0)
        self.assertEqual(self.records[6]['track']['state'],'LOST')
        self.assertEqual(self.records[6]['track']['last_measured_ns'],500000000)
        self.assertTrue(all(not p['target_member'] for p in self.records[6]['current_rows']))
        self.assertNotEqual(self.records[8]['track']['state'],'MEASURED')

    def test_wrong_source_expired_and_candidate_confirmation(self):
        for key,value in [('sid','wrong'),('fi',0),('time_ns',-1),('source_sha256',{}),('candidate_version','stale'),('reviewer','')]:
            engine,f,r,q=self.confirm_engine()
            q[key]=value
            with self.assertRaises(ValueError):
                engine.confirm(f,r,q)
        engine,f,r,q=self.confirm_engine()
        engine.step(self.b.frame(2))
        with self.assertRaises(ValueError):
            engine.confirm(f,r,q)

    def test_mutable_source_binding_cannot_hide_reset(self):
        engine=Engine(self.map,self.ground)
        f=self.b.frame(0)
        # Own copy: never mutate Source's binding or raw data.
        f['source_sha256']=copy.deepcopy(f['source_sha256'])
        engine.step(f)
        f['source_sha256']['meta']='a'*64
        f.update(fi=1,time_ns=100000000)
        self.assertEqual(engine.step(f)['reset'],'SOURCE_OR_COORDINATE_CHANGED')

    def test_dense_jittered_floor_cannot_replace_person(self):
        floor,spec=fixtures.plane_fixture()
        dense=np.array([[x,y,-1.] for x in np.arange(1.,2.91,.1) for y in np.arange(-.7,.71,.1)])
        bg=np.concatenate([floor,dense])
        f=self.b.frame(0)
        f['xyz']=bg
        auth=copy.deepcopy(self.fixture['authorization'])
        auth['segments']=[dict(sid=f['sid'],source_sha256=f['source_sha256'],start_fi=0,end_fi=0)]
        frozen=FrozenMap([f],auth)
        engine=Engine(frozen,self.ground)
        engine.step(f)
        f1=dict(f,fi=1,time_ns=100000000,xyz=np.concatenate([bg,fixtures.body()]))
        r=engine.step(f1)
        c=min(r['candidates'],key=lambda c:abs(c['center'][0]-1.9))
        q=dict(sid=f1['sid'],fi=1,time_ns=f1['time_ns'],source_sha256=f1['source_sha256'],coordinate_version=f1['coordinate_version'],
               candidate_version=c['version'],reviewer='fixture',provenance='SYNTHETIC_SIMULATED_CONFIRMATION')
        engine.confirm(f1,r,q)
        f2=dict(f,fi=2,time_ns=300000000,xyz=bg+[0,0,.025])
        r2=engine.step(f2)
        self.assertEqual(r2['track']['rows'],[])
        self.assertNotEqual(r2['track']['state'],'MEASURED')
        self.assertTrue(r2['rejected_unknown_objects'])

    def test_ground_validation_regions_are_spatially_disjoint(self):
        p,s=fixtures.plane_fixture()
        fit=p[s['fit_indices']]
        self.assertGreaterEqual(len(fit),100)
        for reg in s['validation_regions']:
            q=p[reg['indices']]
            inside=np.all((fit[:,:2]>=q[:,:2].min(axis=0))&(fit[:,:2]<=q[:,:2].max(axis=0)),axis=1)
            self.assertFalse(inside.any())

    def test_missing_boundary_and_synthetic_angular_visibility(self):
        r=Engine(None,self.ground).step(self.b.frame(1))
        self.assertFalse(r['effective_growth'])
        self.assertEqual(r['boundary_reason'],'DISABLED_NO_STATIC_BOUNDARY')
        auth=copy.deepcopy(self.fixture['authorization'])
        auth.update(origin_xyz=[0.,0.,0.],return_mode_verified=True,angular_support_verified=True)
        frozen=FrozenMap([self.a.frame(0)],auth)
        f=self.b.frame(1)
        f['xyz']=self.a.frame(0)['xyz'][[10,40,80]]*.6
        r=Engine(frozen,self.ground).step(f)
        self.assertTrue(any(s['visibility']=='occlusion_possible' for s in r['map_ledger']))
        self.assertFalse(r['capabilities']['strong_occlusion'])

    def test_contact_mixed_and_local_chair_conflict(self):
        self.assertTrue(any(c['quality']=='mixed/ambiguous' for c in self.records[8]['candidates']))
        chair=self.records[10]
        self.assertTrue(chair['local_map_conflict_rows'])
        self.assertTrue(chair['map_usable'])
        self.assertEqual(chair['global_map_status'],'UNKNOWN_NO_RELIABLE_ANCHOR_AUDIT')
        self.assertTrue(all(c['semantic']=='UNKNOWN' for c in chair['candidates']))

    def test_five_ablations_switch_and_prefix(self):
        for variant,step in [('no_ground','ground'),('no_frozen','frozen'),('no_continuation','continuation'),('no_growth','growth'),('no_identity','identity')]:
            records=replay(self.b,self.map,self.ground,variant,simulate=True)
            self.assertFalse(records[0]['steps'][step])
            self.assertEqual(sum(not v for v in records[0]['steps'].values()),1)
            self.assertEqual(len(records[3]['current_rows']),len(self.records[3]['current_rows']))
        for n in [1,4,7,12]:
            self.assertEqual(digest(replay(self.b,self.map,self.ground,'full',simulate=True,stop=n)),digest(self.records[:n]))

    def test_growth_and_ground_switch_change_consumption(self):
        f=self.b.frame(0)
        extra=np.array([[1.9,y,-.8] for y in [-.05,0,.05]]+[[1.9,y,-.95] for y in [-.05,0,.05]])
        f['xyz']=np.concatenate([f['xyz'],extra])
        full=Engine(self.map,self.ground).step(f)
        no=Engine(self.map,self.ground,'no_growth').step(f)
        self.assertGreater(sum(len(c['grown_rows']) for c in full['candidates']),0)
        self.assertEqual(sum(len(c['grown_rows']) for c in no['candidates']),0)
        f['xyz']=np.array([[1.9,y,-1.2] for y in [-.05,0,.05]])
        full=Engine(self.map,self.ground).step(f)
        no=Engine(self.map,self.ground,'no_ground').step(f)
        self.assertFalse(full['candidates'])
        self.assertTrue(no['candidates'])

    def test_evaluation_denominator_missing_box_unknown(self):
        r=copy.deepcopy(self.records[1])
        r['track']['rows']=[];r['track']['state']='PREDICTED'
        # Includes an invalid upstream row and a missed visible member.
        r['current_rows'][0]['filter_reason']='NONFINITE'
        labels=[dict(fi=1,human_rows=[0,1],background_rows=[2],reviewed=True,annotation_kind='points')]
        ev=evaluate([r],labels,'SYNTHETIC')
        self.assertEqual(ev['human_denominator'],2)
        self.assertEqual(ev['point_retention'],0.)
        self.assertFalse(ev['effectiveness_pass'])
        self.assertIsNone(evaluate([r],None,'SYNTHETIC')['point_purity'])
        labels[0]['annotation_kind']='box'
        self.assertIn('CANNOT_REPORT_POINT',evaluate([r],labels,'SYNTHETIC')['reason'])

    def test_evaluation_session_binding_gap_and_occlusion(self):
        a=copy.deepcopy(self.records[1]);b=copy.deepcopy(a)
        a['sid']='A';b['sid']='B';a['fi']=b['fi']=0
        b['track']['rows']=[];b['track']['state']='PREDICTED'
        row=a['track']['rows'][0]
        labels=[dict(sid=s,fi=0,human_rows=[row],background_rows=[],reviewed=True,annotation_kind='points') for s in ['A','B']]
        x=evaluate([a,b],labels,'SYNTHETIC');y=evaluate([b,a],labels,'SYNTHETIC')
        self.assertEqual(x['point_retention'],.5)
        self.assertEqual(x,y)
        labels[0]['source_sha256']={}
        with self.assertRaises(ValueError):
            evaluate([a,b],labels,'SYNTHETIC')
        b=copy.deepcopy(a);b['fi']=1;b['time_ns']=a['time_ns']+500000000;b['track']['rows']=[];b['track']['state']='PREDICTED'
        labels=[dict(sid='A',fi=i,human_rows=[row],background_rows=[],reviewed=True,annotation_kind='points') for i in [0,1]]
        self.assertEqual(evaluate([a,b],labels,'SYNTHETIC')['maximum_measured_gap_s'],.5)
        labels[1]['human_rows']=[]
        self.assertIsNone(evaluate([a,b],labels,'SYNTHETIC')['false_track_duration_s'])
        labels[0]['identity_present']=False
        with self.assertRaises(ValueError):
            evaluate([a,b],labels,'SYNTHETIC')

    def test_output_refuses_overwrite_and_data(self):
        with self.assertRaises(FileExistsError):
            new_output(self.out)
        with self.assertRaises(ValueError):
            new_output(ROOT/'data'/'forbidden_predev')
        p=self.out/'exclusive.json'
        write_new(p,{'x':1})
        with self.assertRaises(FileExistsError):
            write_new(p,{'x':2})


if __name__=='__main__':
    unittest.main(verbosity=2)
