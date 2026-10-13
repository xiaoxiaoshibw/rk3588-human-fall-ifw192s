"""Independent source-row geometry audit plus causal tracker/unknown checks."""
import hashlib
import json
import subprocess
import unittest
import numpy as np
from prepare import ROOT, OUT
from track import CONFIG, components, SID


class Checks(unittest.TestCase):
    def test_components_invalid_and_disconnected(self):
        rng=np.random.default_rng(10)
        a=rng.uniform(0,.06,(90,4));b=a.copy();b[:,:3]+=2
        pts=np.vstack([a,b,[[float('nan'),0,0,1]]])
        found=components(pts)
        self.assertEqual(sorted(c['count'] for c in found),[90,90])
        self.assertTrue(all(np.isfinite(c['center']).all() for c in found))

    def test_actual_source_rows_and_states(self):
        manifest=json.loads((OUT/(SID+'_foreground.json')).read_text(encoding='utf8'))
        fg=np.memmap(OUT/(SID+'_foreground.bin'),dtype='<f4',mode='r').reshape(-1,4)
        ids=np.memmap(OUT/(SID+'_source_rows.bin'),dtype='<u4',mode='r')
        meta=json.loads((ROOT/'captures/remote'/SID/'meta.json').read_text(encoding='utf8'))
        raw=np.memmap(ROOT/'captures/remote'/SID/'points.bin',dtype='u1',mode='r')
        xyz=np.ndarray((meta['total_points'],3),dtype='<f4',buffer=raw,strides=(28,4))
        R,t=np.array(manifest['transform']['R']),np.array(manifest['transform']['t'])
        errors=[]
        for f,m in zip(manifest['frames'],meta['frames']):
            rows=ids[f['offset']:f['offset']+f['count']]
            self.assertTrue(np.all(rows<m['count_points']))
            self.assertTrue(np.all(np.diff(rows.astype('i8'))>0))
            expected=xyz[m['offset_points']+rows].astype('f8')@R.T+t
            actual=fg[f['offset']:f['offset']+f['count'],:3]
            error=float(np.max(abs(expected-actual))) if len(actual) else 0
            self.assertLess(error,2e-6);errors.append(error)
        track=json.loads((OUT/'tracking_v1.json').read_text(encoding='utf8'))
        self.assertEqual(len(track['rows']),164)
        self.assertTrue(all(not r['observed'] and r['state']['state']=='unknown' for r in track['rows'][:10]))
        self.assertTrue(all(not r['state']['confirmed_enabled'] for r in track['rows']))
        self.assertTrue(all(r['track_id']=='REAL-01' for r in track['rows'][10:]))
        self.assertEqual(len(track['events']),1)
        event=track['events'][0];self.assertEqual(event['kind'],'prototype_fall_alert');self.assertFalse(event['verified'])
        r=track['rows'][event['frame']];self.assertEqual(r['state']['state'],'suspected')
        self.assertLessEqual(r['candidate']['height_m']['p90'],CONFIG['alert_p90_max_m'])
        self.assertEqual(track['rows'][-1]['state']['state'],'upright')
        with (OUT/'SOURCE_ROW_AUDIT.json').open('x',encoding='utf8') as f:
            json.dump({'frames':164,'points':len(ids),'max_abs_xyz_error_m':max(errors),'note':'independent f64 source transform versus f32 foreground; source rows complete'},f)


if __name__=='__main__':unittest.main()
