import copy
import json
from pathlib import Path
import sys
import time
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contracts import ITEM, ROOT, PREDEV, Source, new_output, write_new, save_array, protocol_gate, diagnostic_evaluation, digest, module, sha,layout_evidence,bound_json,verify_ai_review
from pipeline import FrozenMap, Engine, validity


class RealdevContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=new_output(ITEM/('new_tests_%d'%time.time_ns()))
        cls.protocol=json.loads((ITEM/'PROTOCOL_V1.json').read_text(encoding='utf8'))
        cls.p=np.array([[x,y,0.] for x in np.arange(1.,1.5,.05) for y in np.arange(-.2,.21,.05)])
        cls.map=FrozenMap(cls.out,{'meta':'synthetic-m','points':'synthetic-p'},'synthetic-coordinate',cls.protocol)
        for i in range(20):cls.map.add(cls.frame(i,cls.p))
        cls.map.freeze();cls.map.bind_exact_time([i*100000000 for i in range(30)])

    @staticmethod
    def frame(i,p):
        return dict(sid='synthetic',kind='SYNTHETIC',fi=i,time_ns=i*100000000,relative_s=i*.1,offset=i*1000,
                    source_sha256={'meta':'synthetic-m','points':'synthetic-p'},coordinate_version='synthetic-coordinate',xyz=np.asarray(p).copy())

    def manifest(self):
        return dict(mode='DIAGNOSTIC',real_protocol=dict(pass_lines=None,matching_rules=None,annotation_coverage=dict(status='DECLARED_ZERO',label_count=0,audited_rows=0),development_split=self.protocol['split']))

    def test_diagnostic_explicit_nulls_and_labelled_rejection(self):
        m=self.manifest();protocol_gate(m)
        for key,v in [('pass_lines','x'),('matching_rules',1),('annotation_coverage',{})]:
            q=copy.deepcopy(m);q['real_protocol'][key]=v
            with self.assertRaises(ValueError):protocol_gate(q)
        m['mode']='LABELLED'
        with self.assertRaises(ValueError):protocol_gate(m)
        r=diagnostic_evaluation();self.assertIsNone(r['effectiveness_pass']);self.assertIsNone(r['point_purity']);self.assertEqual(r['reason'],'NO_LABELS_IS_NOT_ZERO_CONTAMINATION')

    def test_no_new_kind_or_d_unknown_role_before_read(self):
        for kind,role,ind in [('DIAGNOSTIC','B',False),('REAL_DEVELOPMENT','D',False),('REAL_DEVELOPMENT','unknown',False),('REAL_DEVELOPMENT','B',1),('REAL_DEVELOPMENT','B',True),('REUSED_DIAGNOSTIC','FAILURE_REGRESSION_ONLY',False)]:
            with self.assertRaises(ValueError):Source(dict(kind=kind,role=role,independent_test=ind))

    def test_all_aggregate_sources_reverse_to_actual_cells(self):
        m=self.map
        self.assertEqual(len(m.support_global),20*len(self.p))
        self.assertEqual(int(m.count.sum()),20*len(self.p))
        for i in range(m.n):
            a,b=m.indptr[i:i+2]
            for global_row in m.support_global[a:b]:
                fi,row=divmod(int(global_row),1000)
                self.assertLess(row,len(self.p));self.assertLess(fi,20)
                self.assertTrue(np.all(self.p[row]>=m.minimum[i]));self.assertTrue(np.all(self.p[row]<=m.maximum[i]))

    def test_matching_index_equal_bruteforce_reference(self):
        p=np.r_[self.p,self.p+[0,0,.2],[[np.nan,0,0],[0,0,0]]];_,v=validity(p)
        bg,d,s=self.map.match(p,v)
        for row in np.flatnonzero(v):
            ds=np.linalg.norm(self.map.centers[self.map.tree_ids]-p[row],axis=1)
            self.assertAlmostEqual(d[row],float(ds.min()),places=12)
            self.assertEqual(bg[row],bool(d[row]<=.08 and np.all(p[row]>=self.map.minimum[s[row]]-.08) and np.all(p[row]<=self.map.maximum[s[row]]+.08)))

    def test_fingerprint_actual_matching_buffer_and_freeze(self):
        m=self.map;before=m.fingerprint()
        with self.assertRaises(ValueError):m.tree.data[0,0]+=1
        m.tree.data.setflags(write=True);old=m.tree.data[0,0];m.tree.data[0,0]+=.001
        self.assertNotEqual(before,m.fingerprint());m.tree.data[0,0]=old;m.tree.data.setflags(write=False)
        self.assertEqual(before,m.fingerprint())
        with self.assertRaises(ValueError):m.add(self.frame(20,self.p))

    def test_candidate_not_qualified_and_no_early_backfill(self):
        f=self.frame(20,self.p)
        e=Engine(None);r,_,_=e.step(f,'MAP_BUILDING');self.assertFalse(r['candidate_map_exists'])
        e.map=self.map;r,_,_=e.step(self.frame(21,self.p),'TEMPORAL_VALIDATION',False)
        self.assertTrue(r['candidate_map_exists']);self.assertFalse(r['qualified_M0']);self.assertFalse(r['effective_growth'])
        self.assertFalse(Engine(None).step(self.frame(0,self.p),'MAP_BUILDING')[0]['candidate_map_exists'])

    def test_raw_conservation_invalid_zero_and_stream_equivalence(self):
        frames=[self.frame(i,np.r_[self.p,[[np.nan,0,0],[0,0,0],[2,0,.5],[2.05,0,.5],[2.1,0,.5]]]) for i in [20,21,22]]
        memory=[Engine(self.map).step(f)[0] for f in frames]
        e=Engine(self.map);stream=[]
        for f in frames:
            r,rows,_=e.step(f);stream.append(r)
            self.assertEqual(len(rows),len(f['xyz']));self.assertEqual(sum(r['accounting']['labels'].values()),len(rows))
            self.assertEqual(r['accounting']['raw'],r['accounting']['valid']+r['accounting']['invalid'])
        self.assertEqual(memory,stream)
        for stop in [1,2,3]:
            e=Engine(self.map);self.assertEqual(stream[:stop],[e.step(f)[0] for f in frames[:stop]])

    def test_different_prefix_maps_recompute_and_no_future(self):
        out=new_output(self.out/'different_prefix');m=FrozenMap(out,self.map.binding,self.map.coordinate,self.protocol)
        for i in range(10):m.add(self.frame(i,self.p))
        m.freeze();m.bind_exact_time([i*100000000 for i in range(20)])
        self.assertNotEqual(m.map_id,self.map.map_id);self.assertEqual(int(m.count.sum()),10*len(self.p))

    def test_source_drift_initial_and_mutable_reset(self):
        f=self.frame(20,self.p);f['source_sha256']['meta']='changed'
        r,_,_=Engine(self.map).step(f);self.assertFalse(r['candidate_map_exists'])
        e=Engine(self.map);f=self.frame(20,self.p);e.step(f);f['source_sha256']['meta']='drift';f.update(fi=21,time_ns=2100000000)
        self.assertEqual(e.step(f)[0]['reset'],'SOURCE_OR_COORDINATE_CHANGED')

    def confirmed(self):
        f=self.frame(20,np.array([[2.,0,1],[2.05,0,1],[2.1,0,1]]));e=Engine(self.map,run_version='run',protocol_sha='protocol');r,rows,_=e.step(f)
        c=r['candidates'][0];q={k:copy.deepcopy(f[k]) for k in ['sid','fi','time_ns','source_sha256','coordinate_version']}
        q.update(candidate_version=c['version'],run_version='run',protocol_sha='protocol',reviewer='FIXTURE_NOT_HUMAN',provenance='SYNTHETIC_SIMULATED_CONFIRMATION')
        return e,f,r,rows,q

    def test_confirmation_sync_and_zero_ttl_lost(self):
        e,f,r,rows,q=self.confirmed();e.confirm(f,r,q,rows)
        self.assertEqual(r['accounting']['measured_target'],3);self.assertEqual(int(((rows['flags']&16)!=0).sum()),3)
        a=e.step(self.frame(21,np.empty((0,3))))[0];self.assertEqual(a['track']['state'],'PREDICTED');self.assertEqual(a['track']['rows'],[])
        a=e.step(self.frame(29,np.empty((0,3))))[0];self.assertEqual(a['track']['state'],'LOST');self.assertEqual(a['track']['last_measured_ns'],2000000000)

    def test_wrong_source_record_run_protocol_no_identity(self):
        for key,value in [('reviewer',None),('reviewer',123),('reviewer',''),('run_version','other'),('protocol_sha','other'),('candidate_version','wrong'),('source_sha256',{}),('time_ns',0)]:
            e,f,r,rows,q=self.confirmed();q[key]=value
            with self.assertRaises(ValueError):e.confirm(f,r,q,rows)
        e,f,r,rows,q=self.confirmed();r['fi']=0
        with self.assertRaises(ValueError):e.confirm(f,r,q,rows)
        e,f,r,rows,q=self.confirmed();e.variant='no_identity'
        with self.assertRaises(ValueError):e.confirm(f,r,q,rows)
        e,f,r,rows,q=self.confirmed();e.step(self.frame(21,self.p))
        with self.assertRaises(ValueError):e.confirm(f,r,q,rows)

    def test_output_boundaries_no_overwrite_data_or_other_evidence(self):
        for p in [ROOT/'data/forbidden',ROOT/'captures/remote/forbidden',ROOT/'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_predev_r1/new']:
            with self.assertRaises(ValueError):new_output(p)
        with self.assertRaises(FileExistsError):new_output(self.out)
        p=self.out/'exclusive.json';write_new(p,{})
        with self.assertRaises(FileExistsError):write_new(p,{})

    def test_explicit_ai_visual_delegation_never_human_confirmation(self):
        e,f,r,rows,q=self.confirmed();q.update(provenance='AI_VISUAL_REVIEW',human_confirmation=False)
        with self.assertRaises(ValueError):e.confirm(f,r,q,rows)
        q.update(user_delegation_evidence='SYNTHETIC_USER_DELEGATION_FIXTURE',visual_review_evidence='SYNTHETIC_SCREENSHOT_FIXTURE',evidence_verified=True)
        e.confirm(f,r,q,rows);self.assertFalse(r['track']['human_confirmation']);self.assertEqual(r['track']['track_id'],'ai-reviewed-1')
        self.assertEqual(r['track']['quality'],'mixed/ambiguous');self.assertEqual(r['track']['identity_claim'],'AMBIGUOUS_REVIEWED_OBJECT')

    def test_evidence_placeholders_and_layout_sha_rejected(self):
        for value in ['placeholder',{},dict(path=str(self.out/'missing.json'),sha256='0'*64)]:
            with self.assertRaises(ValueError):bound_json(value)
        p=copy.deepcopy(self.protocol);p['qualification']['layout_consistent']=True;p['qualification']['layout_evidence']=dict(file='missing.json',sha256='0'*64,fact='test')
        with self.assertRaises(ValueError):layout_evidence(p)
        self.assertFalse(layout_evidence(self.protocol))
        self.assertTrue(layout_evidence(json.loads((ITEM/'PROTOCOL_V3.json').read_text(encoding='utf8'))))

    def test_qualified_static_growth_and_disabled_boundary(self):
        p=np.array([[1.2,0,.2],[1.2,0,.23],[1.2,0,.26],[1.2,0,.04]])
        f=self.frame(21,p)
        a=Engine(self.map).step(f,qualified=True)[0]
        b=Engine(self.map,'no_growth').step(f,qualified=True)[0]
        c=Engine(self.map).step(f,qualified=False)[0]
        self.assertGreater(sum(x['grown_count'] for x in a['candidates']),0)
        self.assertEqual(sum(x['grown_count'] for x in b['candidates']),0)
        self.assertEqual(sum(x['grown_count'] for x in c['candidates']),0)
        self.assertTrue(all(max(np.subtract(x['max'],x['min']))<=2.4 for x in a['candidates']))

    def replay_fixture(self,name):
        import hashlib
        from server import Replay
        out=new_output(self.out/name);(out/'main').mkdir()
        fixture=module('realdev_drift_fixture',PREDEV/'fixtures.py')
        entry=fixture.write_source(out/'synthetic_raw',[self.p])
        s=Source(entry)
        try:
            f=s.frame(0);r,rows,hits=Engine().step(f,'MAP_BUILDING')
            write_new(out/'main/0000.json',r);save_array(out/'main/0000.npz',current=rows,map_hits=hits)
            frame_index=dict(fi=0,offset_points=0,count_points=len(self.p),relative_s=0,time_ns=0,
                        raw28_sha256=hashlib.sha256(s.buffer).hexdigest(),variants=dict(main=dict(record='main/0000.json',ledger='main/0000.npz')))
            write_new(out/'INDEX.json',dict(entries=[entry],variants=['main'],frames=[frame_index]))
            write_new(out/'OUTPUT_INDEX.json',{str(p.relative_to(out)).replace('\\','/'):sha(p) for p in out.rglob('*') if p.is_file()})
        finally:s.close()
        return Replay(out)

    def test_frame_byte_drift_with_preserved_size_and_mtime(self):
        import os
        replay=self.replay_fixture('raw_drift')
        try:
            replay.record(0,'main');path=replay.source.folder/'points.bin';stat=path.stat()
            with path.open('r+b') as f:f.seek(12);f.write(b'\x00')
            os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
            self.assertEqual(replay.source_stats(),replay.stats)
            with self.assertRaisesRegex(ValueError,'Raw28 frame byte drift'):replay.record(0,'main')
        finally:replay.source.close()

    def test_replay_rejects_wrong_frame_even_with_matching_artifact_sha(self):
        replay=self.replay_fixture('record_drift')
        try:
            path=replay.path/'main/0000.json';r=json.loads(path.read_text());r['fi']=1
            path.write_text(json.dumps(r),encoding='utf8');replay.hashes['main/0000.json']=sha(path)
            with self.assertRaisesRegex(ValueError,'Frame/ledger/source mismatch'):replay.record(0,'main')
        finally:replay.source.close()


if __name__=='__main__':unittest.main()
