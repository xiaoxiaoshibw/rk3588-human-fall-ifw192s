"""Software fixtures only; never included in real performance/semantic tables."""
import copy
import unittest
from pathlib import Path
import tempfile
import numpy as np
from scipy.spatial import cKDTree
from prototype import E, HERE, read, run_frame, transform, cluster, validate_meta, sha
import sys
sys.path.insert(0, str(HERE))
from server import Store

class ContractTests(unittest.TestCase):
    def test_source_partition_and_frozen_cluster(self):
        cfg=read(E/'RUN_MANIFEST.json')['cfg']
        q=np.array([[1+x*.02,y*.02,.1+z*.02] for x in range(5) for y in range(5) for z in range(3)],dtype=float)
        q=np.vstack((q, [0,0,0], [20,0,0], [np.nan,0,0], [1,0,10]))
        p=transform(q,None); tree=cKDTree([[30,30,30]])
        code,labels,groups,_,_=run_frame(q,p,tree,cfg,.05,dict(last=None,seen=None,t=None),1.)
        self.assertEqual(len(code),len(q));self.assertTrue(np.all(code <= 5))
        self.assertTrue(np.array_equal(np.flatnonzero(labels>=0),np.flatnonzero(code>=4)))
        expected,_=cluster(p[:75],cfg)
        self.assertEqual([len(x) for x in expected],[c['count'] for c in groups])
        self.assertTrue(np.array_equal(code[-4:], [0,0,0,1]))

    def test_coordinate_contract(self):
        q=np.array([[1.,2.,3.]])
        reg=dict(R=np.eye(3).ravel().tolist(),t=[.2,.3,.4])
        np.testing.assert_allclose(transform(q,reg),transform(q,None)+[.2,.3,.4],atol=1e-12)

    def test_bad_meta_and_offsets(self):
        m=dict(format='human_capture_session',format_version=1,point_stride_bytes=28,total_points=1,
            frames=[dict(offset_points=0,count_points=1,stamp_sec=1,stamp_nanosec=0)])
        validate_meta(m,28)
        for key,val in [('point_stride_bytes',16),('total_points',2),('format_version',2)]:
            bad=copy.deepcopy(m);bad[key]=val
            with self.assertRaises(ValueError):validate_meta(bad,28)
        bad=copy.deepcopy(m);bad['frames'][0]['offset_points']=1
        with self.assertRaises(ValueError):validate_meta(bad,28)

    def test_unknown_review_gate(self):
        store=Store.__new__(Store)
        for record in [{},dict(schema='local-human-review/1',human_attestation=False),
                       dict(schema='local-human-review/1',human_attestation=True)]:
            with self.assertRaises(ValueError):store.append_review(record)

    def test_artifact_drift_and_missing(self):
        with tempfile.TemporaryDirectory(dir=HERE,prefix='software_fixture_') as tmp:
            folder=Path(tmp);p=folder/'frame.json';p.write_text('{}',encoding='utf8')
            store=Store.__new__(Store);store.target=folder;store.index={'artifacts':{'frame.json':sha(p)}}
            self.assertEqual(store.artifact('frame.json'),p)
            p.write_text('{"drift":true}',encoding='utf8')
            with self.assertRaises(ValueError):store.artifact('frame.json')
            with self.assertRaises(ValueError):store.artifact('../frame.json')
            p.unlink()
            with self.assertRaises(FileNotFoundError):store.artifact('frame.json')

    def test_live_review_counts_and_served_source_drift(self):
        from unittest.mock import patch
        import server as local_server
        with tempfile.TemporaryDirectory(dir=HERE,prefix='software_fixture_') as tmp:
            folder=Path(tmp);p=folder/'app.js';p.write_text('original',encoding='utf8')
            (folder/'REVIEW_QUEUE.json').write_text('{"real_human_reviews":0,"tasks":[]}',encoding='utf8')
            (folder/'FRAME_LEDGER.json').write_text('[]',encoding='utf8')
            s=Store.__new__(Store);s.target=folder;s.m={};s.manifest_sha='fixture';s.delivery_sha='fixture'
            s.review_records=lambda:[dict(sid='fixture',fi=0),dict(sid='fixture',fi=0)]
            s.served_hashes={str(p):sha(p)}
            with patch.object(local_server,'E',folder):
                counts=s.catalog()['queue']
                self.assertEqual(counts['real_human_reviews'],1)
                self.assertEqual(counts['human_candidate_assertions'],2)
                self.assertEqual(counts['creation_snapshot_reviews'],0)
            s.check_served(p);p.write_text('drift',encoding='utf8')
            with self.assertRaises(ValueError):s.check_served(p)

    def test_unknown_flags_uniform_schema_software_only(self):
        from unittest.mock import patch
        import server as local_server
        import threading
        with tempfile.TemporaryDirectory(dir=HERE,prefix='software_fixture_') as tmp:
            s=Store.__new__(Store);s.lock=threading.Lock();s.m={'run_id':'SOFTWARE_FIXTURE'};s.manifest_sha='fixture'
            row=dict(source_sha256={'meta':'fixture','points':'fixture'},candidates=[dict(id=0,member_sha256='fixture')])
            s.frame=lambda sid,fi:(row,None,None,None,None)
            record=dict(schema='local-human-review/1',human_attestation=True,reviewer='SOFTWARE_FIXTURE_NOT_HUMAN',date='2026-10-15',
                basis='synthetic schema check only',label_version='fixture',scope='fixture only',sid='fixture',fi=0,
                source_sha256=row['source_sha256'],granularity='CANDIDATE_LEVEL',candidate_id=0)
            record['class']='UNKNOWN'
            with patch.object(local_server,'E',Path(tmp)):
                for value in [None,False,True]:
                    rec=dict(record,occlusion=value,ambiguity=value,missing_labels=value,frame_complete=value)
                    self.assertEqual(s.append_review(rec)['occlusion'],value)
                with self.assertRaises(ValueError):s.append_review(dict(record,occlusion='unknown',ambiguity=None,missing_labels=None,frame_complete=None))

if __name__=='__main__':unittest.main()
