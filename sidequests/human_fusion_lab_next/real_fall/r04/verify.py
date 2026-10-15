import json
import unittest
import numpy as np
from paths import ROOT,OUT
from skeleton import estimate,stabilize_display


class Checks(unittest.TestCase):
    def test_invalid_sparse_and_ambiguous_skeleton(self):
        for p in [np.empty((0,3)),np.full((40,3),np.nan),np.zeros((40,3))]:
            s,a=estimate(p,list(range(len(p))))
            self.assertFalse(any(n['valid'] for n in s['nodes'].values()))
        with self.assertRaises(ValueError):estimate(np.zeros((40,3)),[0]*40)
        p=np.array([[x,y,z] for x in (-.2,.2) for y in (-.2,.2) for z in (.1,.5)]*10)
        s,a=estimate(p,list(range(len(p))));self.assertEqual(s['reason'],'AMBIGUOUS_BODY_AXIS')

    def test_source_geometry_and_support_bindings(self):
        audits=[]
        for sid in ['cap_20261013_094333','cap_20261013_131958']:
            m=json.loads((OUT/(sid+'_foreground.json')).read_text(encoding='utf8'))
            meta=json.loads((ROOT/'captures/remote'/sid/'meta.json').read_text(encoding='utf8'))
            raw=np.memmap(ROOT/'captures/remote'/sid/'points.bin',dtype='u1',mode='r')
            xyz=np.ndarray((meta['total_points'],3),dtype='<f4',buffer=raw,strides=(28,4))
            fg=np.memmap(OUT/(sid+'_foreground.bin'),dtype='<f4',mode='r').reshape(-1,4)
            ids=np.memmap(OUT/(sid+'_source_rows.bin'),dtype='<u4',mode='r')
            R,t=np.array(m['transform']['R']),np.array(m['transform']['t']);errors=[]
            track=json.loads((OUT/('process.json' if sid.endswith('094333') else sid+'_tracking.json')).read_text(encoding='utf8'))
            for f,fr,row in zip(m['frames'],meta['frames'],track['rows']):
                source=ids[f['offset']:f['offset']+f['count']]
                self.assertTrue(np.all(source<fr['count_points']));self.assertTrue(np.all(np.diff(source.astype('i8'))>0))
                expected=xyz[fr['offset_points']+source].astype('f8')@R.T+t
                if m['transform'].get('reference_alignment'):
                    a=m['transform']['reference_alignment'];expected=expected@np.array(a['R']).reshape(3,3).T+np.array(a['t'])
                actual=fg[f['offset']:f['offset']+f['count'],:3]
                err=float(np.max(abs(expected-actual))) if len(actual) else 0;self.assertLess(err,3e-6);errors.append(err)
                if row.get('skeleton'):
                    target_sources=set(source[row['source_fg_indices']].tolist())
                    for n in row['skeleton']['nodes'].values():
                        if n['valid']:
                            self.assertTrue(set(n['support_rows']).issubset(target_sources))
                            self.assertEqual(n['support_n'],len(n['support_rows']))
                            self.assertTrue(np.isfinite(n['xyz']).all());self.assertGreaterEqual(n['support_n'],6)
                        else:self.assertIsNone(n['xyz'])
            if sid.endswith('094333'):
                self.assertTrue(all(r['observed'] for r in track['rows']))
                self.assertEqual(len(track['events']),1)
                self.assertEqual(track['rows'][-1]['state']['state'],'upright')
                self.assertTrue(any(r['alert_active'] for r in track['rows']))
                self.assertTrue(all(not r['state']['confirmed_enabled'] for r in track['rows']))
            else:
                self.assertEqual(track['events'],[]);self.assertTrue(all(not r['observed'] for r in track['rows']))
            audits.append({'sid':sid,'frames':len(m['frames']),'fg_points':len(ids),'max_abs_xyz_error_m':max(errors)})
        with (OUT/'SOURCE_AND_SKELETON_AUDIT_FINAL.json').open('x',encoding='utf8') as f:json.dump(audits,f,indent=2)


class DisplayBoundary(unittest.TestCase):
    def test_hold_expiry_never_becomes_measurement(self):
        history={};reference={}
        s={'nodes':{'TEST':{'valid':True,'xyz':[0.,0.,1.]}},'edges':[]}
        stabilize_display(s,0.,history,reference)
        s={'nodes':{'TEST':{'valid':False,'xyz':None,'support_rows':[]}},'edges':[]}
        stabilize_display(s,.1,history,reference)
        self.assertTrue(s['nodes']['TEST']['display_predicted']);self.assertFalse(s['nodes']['TEST']['valid'])
        stabilize_display(s,.21,history,reference);self.assertIsNone(s['nodes']['TEST']['display_xyz'])
    def test_weak_axis_reference_requires_recent_past(self):
        p=np.array([[x,y,z] for x in (-.2,.2) for y in (-.2,.2) for z in (.1,.5)]*10)
        s,a=estimate(p,list(range(len(p))),[0,0,1],reference_age=.1)
        self.assertTrue(s.get('axis_prior_reference'))
        s,a=estimate(p,list(range(len(p))),[0,0,1],reference_age=.3)
        self.assertEqual(s['reason'],'AMBIGUOUS_BODY_AXIS');self.assertIsNone(a)
        s,a=estimate(p,list(range(len(p))),[0,0,1],dt=.8,reference_age=.1)
        self.assertEqual(s['reason'],'AMBIGUOUS_BODY_AXIS');self.assertIsNone(a)

if __name__=='__main__':unittest.main()
