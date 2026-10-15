"""SYNTHETIC boundary checks; never creates human reviewed labels."""
import unittest
import sys
import hashlib
import tempfile
from pathlib import Path
from copy import deepcopy
import numpy as np
from close_data_bg import ROOT,PS,module
import skeleton
import track
import close_data_bg as diagnostic


class Contracts(unittest.TestCase):
    def test_malformed_source_time_and_truncation_refused(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            prior=diagnostic.ROOT;diagnostic.ROOT=Path(tmp)
            d=Path(tmp)/'captures/remote/SYNTHETIC';d.mkdir(parents=True)
            meta={'point_stride_bytes':28,'total_points':3,'frames':[
                {'offset_points':i,'count_points':1,'stamp_sec':i+1,'stamp_nanosec':0} for i in range(3)]}
            (d/'points.bin').write_bytes(bytes(84));(d/'meta.json').write_text(json.dumps(meta),encoding='utf8')
            try:
                diagnostic.source('SYNTHETIC')
                for stamps in [[1,1,3],[3,2,1]]:
                    for frame,stamp in zip(meta['frames'],stamps):frame['stamp_sec']=stamp
                    (d/'meta.json').write_text(json.dumps(meta),encoding='utf8')
                    with self.assertRaises(ValueError):diagnostic.source('SYNTHETIC')
                (d/'points.bin').write_bytes(bytes(83))
                with self.assertRaises(ValueError):diagnostic.source('SYNTHETIC')
            finally:diagnostic.ROOT=prior

    def test_source_membership_and_gap(self):
        rng=np.random.default_rng(4)
        p=rng.normal(size=(80,3))*[.1,.12,.5]+[2,1,1]
        ids=list(range(80))
        measured,_=skeleton.estimate(p,ids)
        for n in measured['nodes'].values():
            if n['valid']:self.assertTrue(set(n['support_rows']).issubset(ids))
        with self.assertRaises(ValueError):skeleton.estimate(p,[0]*80)
        weak=np.array([[np.cos(t),np.sin(t),0] for t in np.linspace(0,2*np.pi,80,endpoint=False)])
        rejected,_=skeleton.estimate(weak,ids,previous_axis=[0,0,1],reference_age=.251)
        self.assertEqual(rejected['reason'],'AMBIGUOUS_BODY_AXIS')
        empty,_=skeleton.estimate(np.empty((0,3)),[])
        self.assertFalse(any(n['valid'] for n in empty['nodes'].values()))
        self.assertEqual(track.components(np.empty((0,4))),[])

    def test_display_never_overwrites_raw(self):
        sk={'nodes':{'a':{'valid':True,'xyz':[1.,2.,3.]}},'edges':[]}
        before=deepcopy(sk['nodes']['a']['xyz']);history={};ref={}
        skeleton.stabilize_display(sk,0.,history,ref)
        sk['nodes']['a']['xyz']=[2.,2.,3.]
        raw=deepcopy(sk['nodes']['a']['xyz'])
        skeleton.stabilize_display(sk,.1,history,ref)
        self.assertEqual(sk['nodes']['a']['xyz'],raw)
        self.assertNotEqual(sk['nodes']['a']['display_xyz'],raw)
        self.assertEqual(before,[1.,2.,3.])
        sk['nodes']['a']={'valid':False,'xyz':None}
        skeleton.stabilize_display(sk,.15,history,ref)
        self.assertTrue(sk['nodes']['a']['display_predicted']);self.assertIsNone(sk['nodes']['a']['xyz'])
        skeleton.stabilize_display(sk,.5,history,ref)
        self.assertIsNone(sk['nodes']['a']['display_xyz']);self.assertFalse(sk['nodes']['a']['display_predicted'])

    def test_part_contract_rejects_proposed_drift_duplicate_and_bad_frame(self):
        prior=sys.modules.get('core')
        sys.modules['core']=module('pointset_review_core',PS/'core.py')
        try:server=module('pointset_review_contract',PS/'server.py')
        finally:
            if prior is None:sys.modules.pop('core',None)
            else:sys.modules['core']=prior
        cat={'sessions':[{'session_id':'SYNTHETIC','source_sha256':{'meta':'m','points':'p'}}]}
        obj={'id':'a','kind':'AUTOMATIC_CANDIDATE','source_indices':[1,2]}
        frame={'session_id':'SYNTHETIC','frame_index':0,'source_frame':{'count_points':4},'full_3d':[obj]}
        row={'schema_version':'pointset-annotation/1','session_id':'SYNTHETIC','frame_index':0,'source_sha256':{'meta':'m','points':'p'},
             'reviewer':'SYNTHETIC_TEST','provenance':'HUMAN_REVIEW','part_class':'UNKNOWN','source_indices':[1],
             'object_scope':'full_3d','object_id':'a','object_kind':'AUTOMATIC_CANDIDATE'}
        self.assertEqual(server.validate_review(row,cat,frame),row)
        filtered=server.bound_reviews([row,{**row,'provenance':'PROPOSED'},{**row,'source_sha256':{}},[]],cat,frame)
        self.assertEqual(filtered['records'],[row]);self.assertEqual(len(filtered['rejected']),3)
        for key,value in [('provenance','PROPOSED'),('source_sha256',{}),('source_indices',[1,1]),('source_indices',[]),('source_indices',[True]),('frame_index',1),('frame_index',False)]:
            bad={**row,key:value}
            with self.assertRaises(ValueError):server.validate_review(bad,cat,frame)
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);(d/'meta.json').write_bytes(b'{}');(d/'points.bin').write_bytes(b'SYNTHETIC')
            expected={'meta':hashlib.sha256(b'{}').hexdigest(),'points':hashlib.sha256(b'SYNTHETIC').hexdigest()}
            server.validate_source_binding(d,expected)
            (d/'points.bin').write_bytes(b'DRIFT')
            with self.assertRaises(ValueError):server.validate_source_binding(d,expected)


if __name__=='__main__':unittest.main()
