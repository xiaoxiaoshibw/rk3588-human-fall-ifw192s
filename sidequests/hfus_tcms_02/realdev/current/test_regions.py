import sys
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
from project_regions import orient_lateral,estimate
from project_dependencies import module,SK
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'r12'))

OLD=module('frozen_region_tests',Path(__file__).resolve().parent.parent/'r12/test_regions2.py')

class ActiveRegions(unittest.TestCase):
    def test_observations_share_one_normalized_array(self):
        p=OLD.plane();seen=[]
        observe=SK.G.observe
        def checked(norm,ids,params):
            xyz=norm['xyz']
            self.assertIsInstance(xyz,np.ndarray)
            self.assertEqual(xyz.dtype,np.dtype('float64'))
            if seen:self.assertIs(xyz,seen[0])
            seen.append(xyz)
            before=xyz.copy()
            node=observe(norm,ids,params)
            np.testing.assert_array_equal(xyz,before)
            return node
        with patch.object(SK.G,'normalize',wraps=SK.G.normalize) as normalize, \
                patch.object(SK.G,'observe',side_effect=checked):
            estimate(p,list(range(len(p))),coordinate_version='RAW/innolidar',session_id='synthetic')
        self.assertIsInstance(normalize.call_args.args[0]['xyz'],np.ndarray)
        self.assertEqual(len(seen),13)

    def test_sign_crossing_is_not_position_smoothing(self):
        a=np.array([-.70,.71,0.]);a/=np.linalg.norm(a)
        b=np.array([.72,-.69,0.]);b/=np.linalg.norm(b)
        out,flipped=orient_lateral(b,a)
        self.assertTrue(flipped);np.testing.assert_array_equal(out,-b)
        self.assertGreater(np.dot(out,a),.99)
        for q in [np.zeros(3),[np.nan,0,1],[1,1,1],[1,0]]:
            with self.assertRaises(ValueError):orient_lateral(b,q)

    def test_current_source_points_and_disjoint_regions(self):
        p=OLD.plane();before=p.copy()
        x=estimate(p,list(range(len(p))),coordinate_version='RAW/innolidar',session_id='SYNTHETIC_IN_CONTRACT',partition_branch=True)[0]
        self.assertEqual(sum(n['valid'] for n in x['nodes'].values()),13)
        for n in x['nodes'].values():np.testing.assert_array_equal(n['xyz'],np.median(p[n['support_rows']],0))
        for s in ('A','B'):
            self.assertFalse(set(x['nodes']['UPPER_'+s]['support_rows'])&set(x['nodes']['OUTER_'+s]['support_rows']))
        np.testing.assert_array_equal(before,p)
        order=np.random.default_rng(7).permutation(len(p))
        y=estimate(p[order],order.tolist(),coordinate_version='RAW/innolidar',session_id='SYNTHETIC_IN_CONTRACT',partition_branch=True)[0]
        self.assertEqual(x,y)

    def test_first_frame_preserves_frozen_baseline(self):
        p=OLD.plane()
        old=OLD.call(p,OLD.estimate2)
        new=estimate(p,list(range(len(p))),coordinate_version='RAW/innolidar',session_id='SYNTHETIC_IN_CONTRACT')[0]
        self.assertEqual(old['nodes'],new['nodes'])
        self.assertEqual(old['basis_lateral'],new['basis_lateral'])

    def test_target_contract_translation_and_source_rows(self):
        p=OLD.plane()+np.random.default_rng(13).normal(0,1e-5,OLD.plane().shape)
        kw=dict(coordinate_version='RAW/innolidar',session_id='synthetic',
                region_contract='target_ground_v1',ground_up=[0,0,1],partition_branch=True)
        rows=list(range(len(p)));shift=np.array([8.,-4.,2.])
        a=estimate(p,rows,**kw)[0];b=estimate(p+shift,rows,**kw)[0]
        self.assertEqual(sum(n['valid'] for n in b['nodes'].values()),13)
        for name,n in b['nodes'].items():
            self.assertEqual(a['nodes'][name]['support_rows'],n['support_rows'])
            np.testing.assert_array_equal(n['xyz'],np.median((p+shift)[n['support_rows']],0))
        legacy=estimate(p+shift,rows,coordinate_version='RAW/innolidar',session_id='synthetic')[0]
        self.assertEqual(legacy['reason'],'OUTSIDE_REGION_DEVELOPMENT_DOMAIN')
        inside=estimate(p,rows,coordinate_version='RAW/innolidar',session_id='synthetic',partition_branch=True)[0]
        self.assertEqual(a['nodes'],inside['nodes'])

    def test_target_contract_bound_ground_and_low_posture(self):
        p=OLD.plane();rows=list(range(len(p)))
        kw=dict(coordinate_version='RAW/innolidar',session_id='synthetic',region_contract='target_ground_v1')
        q=p[:,[2,1,0]]*np.array([1,1,-1])
        out=estimate(q,rows,ground_up=[1,0,0],**kw)[0]
        self.assertEqual(sum(n['valid'] for n in out['nodes'].values()),13)
        self.assertGreater(out['axis'][0],.9)
        for n in out['nodes'].values():
            np.testing.assert_array_equal(n['xyz'],np.median(q[n['support_rows']],0))
        rejected=estimate(q,rows,ground_up=[0,0,1],**kw)[0]
        self.assertEqual(rejected['reason'],'OUTSIDE_UPRIGHT_GROUND_CONTRACT')
        self.assertTrue(all(not n['valid'] for n in rejected['nodes'].values()))
        for up in (None,[0,0,2],[0,0,float('nan')],[0,1]):
            with self.assertRaises(ValueError):estimate(p,rows,ground_up=up,**kw)

if __name__=='__main__':unittest.main()
