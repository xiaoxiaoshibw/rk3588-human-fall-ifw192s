"""Synthetic software/geometry checks, never physical ground truth."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from live_ground import fit_site, save_fit, monitor
from live_engine import site_ground


def accepted_fixture(binding, plane, identity):
    return dict(format='live_ground_fit/1',status='geometry_accepted',binding=binding,plane=plane,
        quality=dict(consensus='GOOD',estimators={k:dict(valid=True) for k in ('tls','svd','ransac')},
                     pairwise=[dict(status='PASS')]),
        headers=[dict(seq=i,sec=100+i//10,nsec=i%10*100000000,frame_id=binding['frameId']) for i in range(28)],
        perFrame=[dict(status='PASS',angleDeg=0,offsetGapM=0) for _ in range(28)],
        monitor=dict(initial=np.eye(3).tolist(),regions=[[1,2,1,2],[2,3,1,2],[1,2,2,3],[2,3,2,3]]),
        source=dict(upstream='ws://127.0.0.1:1',identity=identity),physicalGroundTruth='UNKNOWN')


class SiteGroundChecks(unittest.TestCase):
    def test_short_holes_pause_only_unique_same_target_and_never_alarm_stale(self):
        from core.range_ground_alert import GroundAlertObserver,GroundAlertGapCandidate
        old=GroundAlertObserver();new=GroundAlertGapCandidate();old_active=[];new_active=[]
        def row(i,track='a'):
            return dict(frameIndex=i,stampSec=i*.1,trackId=track,generation=0,binding='ground1',
                        measured=True,heightMedianM=.4,groundAvailable=True)
        for i in range(25):
            r=row(i)
            if i==10:
                r.update(trackId=None,measured=False,heightMedianM=None,continuityTrackId='a',uniquePredictedTrack=True)
            a=old.update(r)[0];b=new.update(r)
            if i==10:self.assertFalse(b['active']);self.assertEqual(b['state'],'unavailable')
            if a['active']:old_active.append(i)
            if b['active']:new_active.append(i)
        self.assertEqual(old_active,[])
        self.assertEqual(new_active[0],17)  # 1.5 observed s; the 0.2s hole adds no evidence
        self.assertFalse(new.update(row(25,'b'))['active'])
        self.assertEqual(new.duration,0.)
        r=row(26,'b');r.update(measured=False,trackId=None,continuityTrackId='b',uniquePredictedTrack=True,ambiguous=True)
        self.assertFalse(new.update(r)['active']);self.assertEqual(new.duration,0.)
        self.assertFalse(new.update(row(40,'b'))['active'])
        r=row(41,'b');r['binding']='ground2'
        self.assertFalse(new.update(r)['active']);self.assertEqual(new.duration,0.)

    def test_existing_selector_estimators_and_independent_frames(self):
        x,y=np.meshgrid(np.arange(1.,3.,.025),np.arange(-1.,1.,.025))
        p=np.column_stack((x.ravel(),y.ravel(),np.full(x.size,-1.2)))
        b=dict(siteId='synthetic',frameId='lidar',gridSha256='test')
        h=accepted_fixture(b,{}, {})['headers']
        report=fit_site([p]*28,h,b,dict(upstream='synthetic',identity={}))
        self.assertEqual(report['status'],'geometry_accepted',report.get('reason'))
        self.assertEqual(report['quality']['consensus'],'GOOD')
        np.testing.assert_allclose(report['plane']['normal'],[0,0,1],atol=1e-10)
        self.assertAlmostEqual(report['plane']['offset_m'],1.2)
        self.assertLess(report['selected']['max_abs_m'],1e-10)
        held=[p]*25+[p+np.array([0,0,.2])]*3
        self.assertEqual(fit_site(held,h,b,dict(upstream='synthetic'))['status'],'unavailable')
        self.assertEqual(fit_site([p[:10]]*28,h,b,{})['status'],'unavailable')
        bad=[dict(t) for t in h];bad[10]['seq']+=1
        self.assertEqual(fit_site([p]*28,bad,b,{})['reason'],'fit_source_discontinuous')

    def test_loader_rejects_changed_plane_quality_source_and_sign(self):
        b=dict(siteId='test',frameId='lidar',gridSha256='grid')
        identity=dict(session='test',coordinate='RAW/lidar',grid_sha256='grid',units='m')
        r=accepted_fixture(b,dict(normal=[0,0,1],offset_m=1.2),identity)
        with tempfile.TemporaryDirectory() as d:
            p=save_fit(r,d)
            self.assertEqual(site_ground(p,'lidar','grid','test',identity)['normal'],[0,0,1])
            with self.assertRaises(ValueError):site_ground(p,'lidar','changed','test',identity)
            source=Path(d)/'GROUND_FIT.json'; doc=json.loads(p.read_text())
            def put():
                source.write_text(json.dumps(r));doc['plane']=r['plane']
                doc['provenance']['sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
                p.write_text(json.dumps(doc))
            r['plane']=dict(normal=[0,0,-1],offset_m=-1.2);put()
            with self.assertRaisesRegex(ValueError,'invalid live ground'):site_ground(p,'lidar','grid','test',identity)
            r['plane']=dict(normal=[0,0,1],offset_m=1.2)
            r['quality']['estimators']['tls']['valid']=False;put()
            with self.assertRaisesRegex(ValueError,'quality evidence'):site_ground(p,'lidar','grid','test',identity)
            r['quality']['estimators']['tls']['valid']=True;r['headers'][3]['seq']=999;put()
            with self.assertRaisesRegex(ValueError,'discontinuity'):site_ground(p,'lidar','grid','test',identity)
            source.write_text('{}')
            with self.assertRaisesRegex(ValueError,'provenance changed'):site_ground(p,'lidar','grid','test',identity)

    def test_frozen_patch_monitor_occlusion_shift_and_recovery(self):
        b=dict(siteId='test',frameId='lidar',gridSha256='grid')
        r=accepted_fixture(b,{},{});p=[]
        for xl,xh,yl,yh in r['monitor']['regions']:
            x,y=np.meshgrid(np.linspace(xl+.01,xh-.01,8),np.linspace(yl+.01,yh-.01,8))
            p.append(np.column_stack((x.ravel(),y.ravel(),np.full(x.size,-1.2))))
        g=dict(monitor=r['monitor'],normal=[0,0,1],offset_m=1.2)
        self.assertTrue(monitor(np.concatenate(p),g)['available'])
        self.assertTrue(monitor(np.concatenate(p[:3]),g)['available'])
        self.assertFalse(monitor(np.concatenate(p[:2]),g)['available'])
        self.assertFalse(monitor(np.concatenate(p)+[0,0,.2],g)['available'])
        self.assertTrue(monitor(np.concatenate(p),g)['available'])


if __name__=='__main__':unittest.main()
