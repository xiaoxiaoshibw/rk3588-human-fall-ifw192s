import copy
import unittest
import numpy as np
from coordinates import Transform,plane_basis,valid_xyz,check_points


def fixture():
    R,t,n,d=plane_basis([-.4,-.03,.9],1.3,[1,0,0])
    return dict(R=R.tolist(),t=t.tolist(),plane=dict(normal=n.tolist(),d_m=d),
        transform_id='fixture-1',coordinate_version='fixture/v1',from_frame='innolidar',to_frame='candidate_local',
        units='m',state='CANDIDATE_PLANE_PREVIEW',mode='OFFLINE_REVIEW',qualification=dict(geometry=False,physical=False))


class Coordinates(unittest.TestCase):
    def setUp(self):self.a=fixture();self.T=Transform(self.a)
    def test_plane_normalization_scales_d(self):
        x=plane_basis([0,0,2],4,[1,0,0]);self.assertEqual(x[3],2);np.testing.assert_allclose(x[1],[0,0,2])
    def test_reference_axis_degenerate_rejected(self):
        for n,a in [([0,0,1],[0,0,9]),([0,0,0],[1,0,0]),([np.nan,0,1],[1,0,0])]:
            with self.assertRaises(ValueError):plane_basis(n,1,a)
    def test_rotation_negative_cases(self):
        for r in [np.diag([1,1,-1]),np.eye(3)*1.001,np.full((3,3),np.inf)]:
            a=copy.deepcopy(self.a);a['R']=r.tolist()
            with self.assertRaises(ValueError):Transform(a)
    def test_wrong_direction(self):
        a=copy.deepcopy(self.a);a['from_frame'],a['to_frame']=a['to_frame'],a['from_frame']
        with self.assertRaises(ValueError):Transform(a)
    def test_plane_wrong_direction(self):
        a=copy.deepcopy(self.a);a['R']=np.asarray(a['R']).T.tolist()
        with self.assertRaises(ValueError):Transform(a)
    def test_float64_and_float32_roundtrip(self):
        p=np.random.RandomState(19).normal(size=(10000,3))*100
        q=self.T.points(p,self.T.tag(8,False),8,True);check_points(self.T,p,q)
    def test_invalid_and_zero_original_position_preserved(self):
        p=np.array([[0,0,0],[np.nan,2,3],[np.inf,0,2],[1,2,3]],dtype=float)
        q=self.T.points(p,self.T.tag(0,False),0,True);check_points(self.T,p,q)
        self.assertEqual(valid_xyz(p).tolist(),[False,False,False,True])
    def test_wrong_frame_and_fi(self):
        for tag in [self.T.tag(2,False),dict(self.T.tag(1,False),frame='other')]:
            with self.assertRaises(ValueError):self.T.points([[1,2,3]],tag,1)
    def test_repeated_transform_rejected(self):
        with self.assertRaises(ValueError):self.T.points([[1,2,3]],self.T.tag(1),1)
    def test_version_mix_and_update(self):
        a=copy.deepcopy(self.a);a['transform_id']='fixture-2';a['coordinate_version']='fixture/v2';other=Transform(a)
        with self.assertRaises(ValueError):other.points([[1,2,3]],self.T.tag(1),1)
        self.assertNotEqual(other.tag(1),self.T.tag(1))
    def test_eight_corner_obb(self):
        q=self.T.box([-1,-2,-3],[4,5,6],0);self.assertEqual(q.shape,(8,3))
        restored=self.T.inverse(q)
        self.assertEqual(len(set(map(tuple,np.round(restored,9)))),8)
        self.assertFalse(np.allclose(q.min(axis=0),self.T.points([-1,-2,-3],self.T.tag(0,False),0)))
    def test_velocity_no_translation_and_covariance(self):
        v=np.array([1,2,3]);np.testing.assert_allclose(self.T.vectors(v),self.T.R@v)
        self.assertFalse(np.allclose(self.T.vectors(v),self.T.R@v+self.T.t))
        s=np.diag([1,2,3]);expected=self.T.R@s@self.T.R.T
        np.testing.assert_allclose(self.T.covariance(s),expected)
    def test_object_members_prediction_and_identity(self):
        o=dict(self.T.tag(6,False),center=[1,2,3],predicted_center=[2,3,4],velocity=[0,0,1],
            min=[0,0,0],max=[2,3,4],rows=[7,9],version='old',identity_source={'old':'review'},human_confirmation=True)
        q=self.T.object(o,6)
        self.assertEqual(q['rows'],[7,9]);self.assertEqual(len(q['obb_corners']),8)
        self.assertFalse(q['identity_valid_for_coordinate_version']);self.assertNotIn('identity_source',q)
        self.assertFalse(q['human_confirmation']);self.assertIn('historical_identity_source',q)
    def test_no_qualification_promotion(self):
        a=copy.deepcopy(self.a);a['qualification']['geometry']=True
        with self.assertRaises(ValueError):Transform(a)
    def test_persisted_output_version_binding(self):
        from preview import validate_output_binding
        index=dict(tag=self.T.tag(-1),transform_sha256='sha1',source_sha256={'points':'p'})
        validate_output_binding(self.T,index,'sha1',{'points':'p'})
        for key,value in [('tag',dict(self.T.tag(-1),transform_id='other')),('transform_sha256','sha2'),('source_sha256',{})]:
            bad=copy.deepcopy(index);bad[key]=value
            with self.assertRaises(ValueError):validate_output_binding(self.T,bad,'sha1',{'points':'p'})
    def test_source_query_no_mixed_top_level_version(self):
        from preview import source_payload
        raw=dict(fi=1,coordinate_version='RAW_UNVERIFIED_INSTALLATION/v1',xyz=[1,2,3],raw_bytes_hex='00'*28)
        local=self.T.points([1,2,3],self.T.tag(1,False),1)
        result=source_payload(self.T,raw,local)
        self.assertEqual(result['coordinate_version'],result['tag']['coordinate_version'])
        self.assertEqual(result['source_coordinate_version'],result['raw_tag']['coordinate_version'])
        self.assertEqual(result['raw_xyz'],[1,2,3]);self.assertNotIn('xyz',result)
    def test_item_output_rejects_data_alias_and_overwrite(self):
        from bootstrap import ROOT,OUT,write
        import time
        for target in [ROOT/'data/s01_forbidden.json',ROOT/'captures/remote/s01_forbidden.json',OUT/'../s01_forbidden.json']:
            with self.assertRaises(ValueError):write(target,{'test':'must not create'})
        p=OUT/('unit_write_guard_%d.json'%time.time_ns());write(p,{'test':'new item-local fixture'})
        with self.assertRaises(FileExistsError):write(p,{'test':'must not overwrite'})


if __name__=='__main__':unittest.main()
