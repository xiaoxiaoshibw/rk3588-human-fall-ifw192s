"""Checks of diagnosis mechanisms; no fictitious 121647 repair acceptance."""
import unittest
import numpy as np
from diagnostics import Q,tls,weighted_tls,svd,metrics,scalar_check,residual

class DiagnosticTest(unittest.TestCase):
    def plane(self):
        rng=np.random.RandomState(610)
        xy=rng.uniform(-2,2,(400,2))
        points=np.column_stack([xy,.1*xy[:,0]-.2*xy[:,1]-1.+rng.normal(0,.004,len(xy))])
        return points,np.array([0.,0.,1.])

    def test_independent_svd_and_scalar_percentile_match(self):
        p,a=self.plane();n,d=tls(p,a);sn,sd=svd(p,a)
        self.assertLess(np.max(np.abs(residual(p,n,d)-residual(p,sn,sd))),1e-12)
        self.assertAlmostEqual(metrics(p,n,d)['p95_m'],scalar_check(p,n,d)['p95_m'],places=12)

    def test_rigid_change_preserves_real_unit_distances(self):
        p,a=self.plane();n,d=tls(p,a);S=Q.rotation(33,-14);t=np.array([2.,-3.,1.])
        rn=S@n;rd=d-float(rn@t)
        self.assertLess(np.max(np.abs(residual(p@S.T+t,rn,rd)-residual(p,n,d))),1e-12)

    def test_uniform_weights_reproduce_tls_without_discarding_points(self):
        p,a=self.plane();n,d=tls(p,a);wn,wd=weighted_tls(p,np.ones(len(p)),a)
        self.assertLess(np.max(np.abs(residual(p,n,d)-residual(p,wn,wd))),1e-12)
        self.assertEqual(metrics(p,n,d)['count'],metrics(p,wn,wd)['count'])

    def test_reweighting_cannot_lower_unweighted_tls_optimum_rms(self):
        p,a=self.plane();n,d=tls(p,a);weights=np.where(p[:,0]>0,8.,1.)
        wn,wd=weighted_tls(p,weights,a)
        self.assertGreaterEqual(metrics(p,wn,wd)['rms_m']+1e-12,metrics(p,n,d)['rms_m'])
        self.assertTrue(np.all(weights>0))

    def test_local_planes_cannot_be_claimed_as_single_rigid_solution(self):
        blocks=[]
        for x,y,z in [(0,0,-1),(2,0,-1),(0,2,-1),(2,2,-.8)]:
            blocks.append(np.array([[x+dx,y+dy,z] for dx in [0.,.1,.2] for dy in [0.,.1,.2]]))
        p=np.concatenate(blocks);a=np.array([0.,0.,1.]);n,d=tls(p,a)
        self.assertGreater(metrics(p,n,d)['rms_m'],.01)
        for block in blocks:
            ln,ld=tls(block,a);self.assertLess(metrics(block,ln,ld)['rms_m'],1e-12)
        # Different offsets do not define one R,t; no export/correction routine exists here.
        offsets=[tls(block,a)[1] for block in blocks]
        self.assertGreater(max(offsets)-min(offsets),.1)

if __name__=='__main__':unittest.main()
