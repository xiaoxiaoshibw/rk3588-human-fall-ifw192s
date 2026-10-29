import unittest
import numpy as np
from regions import estimate
from common import SK

def plane():
    u,d,z=np.meshgrid(np.linspace(-.49,.49,35),[-.03,0,.03],np.linspace(-.82,.82,63),indexing='ij')
    axis=np.array([-.3,0,np.sqrt(.91)]);lat=np.array([np.sqrt(.91),0,.3]);dep=np.cross(lat,axis)
    return np.array([1.55,1.275,.7])+u.reshape(-1,1)*lat+d.reshape(-1,1)*dep+z.reshape(-1,1)*axis

def call(p,rows=None,**kw):
    return estimate(p,list(range(len(p))) if rows is None else rows,coordinate_version=kw.get('coordinate','RAW/innolidar'),session_id=kw.get('sid','SYNTHETIC_IN_CONTRACT'))[0]

class RegionTests(unittest.TestCase):
    def test_plane_mechanism_and_source_support(self):
        p=plane();before=p.copy();new=call(p);old,_=SK.estimate(p,list(range(len(p))))
        self.assertFalse(old['nodes']['CHEST']['valid'])
        self.assertTrue(new['nodes']['CHEST']['valid'])
        self.assertEqual(sum(n['valid'] for n in new['nodes'].values()),13)
        for n in new['nodes'].values():
            self.assertTrue(np.allclose(n['xyz'],np.median(p[n['support_rows']],0),atol=1e-12,rtol=0))
        self.assertTrue(np.array_equal(p,before))
    def test_order_and_no_history(self):
        p=plane();rows=np.arange(len(p));order=np.random.default_rng(7).permutation(len(p))
        a=call(p);b=call(p[order],rows[order].tolist())
        for k in SK.SLOTS:
            self.assertEqual(a['nodes'][k]['valid'],b['nodes'][k]['valid'])
            self.assertTrue(np.allclose(a['nodes'][k]['xyz'],b['nodes'][k]['xyz'],atol=1e-12,rtol=0))
            self.assertEqual(set(a['nodes'][k]['support_rows']),set(b['nodes'][k]['support_rows']))
    def test_sparse_degenerate_and_contract(self):
        self.assertEqual(call(plane()[:5])['reason'],'LOW_OR_INVALID_SUPPORT')
        self.assertEqual(call(np.repeat([[1.5,1.2,.5]],50,0))['reason'],'AMBIGUOUS_BODY_AXIS')
        p=plane()
        for kw in (dict(coordinate='S3'),dict(sid='cap_20261017_113516')):
            with self.assertRaises(ValueError):call(p,**kw)
        with self.assertRaises(ValueError):call(p,rows=[0]*len(p))
        with self.assertRaises(ValueError):call(p+np.array([10,0,0]))
        p[0]=np.nan;self.assertEqual(call(p)['reason'],'LOW_OR_INVALID_SUPPORT')
    def test_unchanged_conflict_gate(self):
        params=SK.PARAMS
        self.assertEqual(params['node_max_xy_span_m'],.8)
        xyz=np.array([[-.5,0,.1],[.5,0,.2],[-.5,0,.3],[.5,0,.4],[-.5,0,.5],[.5,0,.6]])
        rows=list(range(len(xyz)))
        norm=SK.G.normalize(dict(receipt=dict(rows=rows),global_rows=rows,xyz=xyz.tolist(),invalid_source_rows=[]),params)
        self.assertEqual(SK.G.observe(norm,rows,params)['reason'],'CONFLICTING_SPATIAL_SUPPORT')
    def test_transverse_ambiguity_and_horizontal_contract(self):
        theta,z=np.meshgrid(np.linspace(0,2*np.pi,32,endpoint=False),np.linspace(-.7,.7,40))
        p=np.column_stack([1.55+.15*np.cos(theta.ravel()),1.275+.15*np.sin(theta.ravel()),.7+z.ravel()])
        self.assertEqual(call(p)['reason'],'AMBIGUOUS_TRANSVERSE_PLANE')
        p=plane();center=p.mean(0);q=p-center
        q[:,[0,2]]=q[:,[2,0]]
        # Compress to stay within the registered ROI while retaining horizontal axis.
        q*=.8
        self.assertEqual(call(q+center)['reason'],'OUTSIDE_UPRIGHT_RAW_CONTRACT')

if __name__=='__main__':unittest.main()
