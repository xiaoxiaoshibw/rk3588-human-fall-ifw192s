import copy
import itertools
import json
from pathlib import Path
import unittest
import numpy as np
from temporal import HMM, HSMM, Track, geometry, sequence, transition

CFG = json.loads((Path(__file__).parent/'config.json').read_text())


def feature(z=1.6, center=.9):
    return dict(height=z-.1, width=.5, depth=.3, z90=z, centroid_z=center,
                center=[0, 0, center], count=500, tilt_deg=10)


class TemporalTests(unittest.TestCase):
    def test_viterbi_exhaustive(self):
        h = HMM([.6, .4], [[.8, .2], [.3, .7]])
        emissions = [[.9, .1], [.3, .7], [.2, .8], [.8, .2]]
        times = [0, .1, .25, .36]
        def prob(path):
            p = h.initial[path[0]]*emissions[0][path[0]]
            for i in range(1, len(path)):
                p *= transition(h.a, times[i]-times[i-1])[path[i-1], path[i]]*emissions[i][path[i]]
            return p
        expected = max(itertools.product(range(2), repeat=4), key=prob)
        self.assertEqual(h.viterbi(emissions, times), list(expected))

    def test_forward_exact(self):
        h = HMM([.6, .4], [[.8, .2], [.3, .7]])
        np.testing.assert_allclose(h.update([.9, .1]), [.54/.58, .04/.58])
        p = h.p @ h.a*np.array([.3, .7]); p /= p.sum()
        np.testing.assert_allclose(h.update([.3, .7], .1), p)

    def test_missing_not_zero_and_no_event(self):
        m = Track(CFG); m.update(0, feature(), .9)
        o = m.update(.1, None, None)
        self.assertIsNone(o['feature']); self.assertTrue(o['missing']); self.assertFalse(o['candidate'])
        self.assertIsNone(o['baseline']); self.assertTrue(o['hold_prediction'])
        self.assertFalse(m.update(.6, None, None)['hold_prediction'])

    def test_real_delta_and_reset(self):
        m = Track(CFG); m.update(10, feature(center=1), .9)
        o = m.update(10.25, feature(center=.8), .9)
        self.assertAlmostEqual(o['feature']['vertical_velocity'], -.8)
        self.assertTrue(m.update(10.2, feature(), .9)['reset'])
        self.assertIsNone(m.update(12, feature(), .9)['feature']['vertical_velocity'])
        m.reset(); a = m.update(0, feature(), .9)
        self.assertEqual(a, Track(CFG).update(0, feature(), .9))

    def test_causal_prefix_and_identity(self):
        rows = [dict(sid='s', track_id='A', fi=i, time=i*.1, feature=feature(), rf=.9 if i < 5 else .1) for i in range(12)]
        full = sequence(rows, CFG); prefix = sequence(rows[:6], CFG)
        for a, b in zip(full, prefix):
            a = dict(a); b = dict(b); a.pop('offline_viterbi'); b.pop('offline_viterbi')
            self.assertEqual(a, b)
        mixed = copy.deepcopy(rows[:2]); mixed[1]['track_id'] = 'B'
        actual = sequence(mixed, CFG)[1]
        fresh = sequence(mixed[1:], CFG)[0]
        self.assertEqual(actual, fresh)

    def test_duration_survival(self):
        c = dict(initial=[1, 0], matrix=[[0, 1], [1, 0]], duration_scale_s=[1, 1], duration_shape=[2, 2], max_duration_s=30)
        h = HSMM(c); h.update([1, 1], 0)
        p = h.update([1, 1], .37)
        self.assertAlmostEqual(h.mass[0, 0], np.exp(-.37**2))
        with self.assertRaises(ValueError):
            h.update([1, 1], .2)
        h = HSMM(c)
        with self.assertRaises(ValueError):
            h.update([0, 1], 0)

    def test_interleaved_viterbi(self):
        rows = [dict(sid='s', track_id='A' if i%2 else 'B', fi=i, time=i*.1,
                     feature=feature(1.6 if i%4 else .4), rf=.8) for i in range(30)]
        actual = sequence(rows, CFG)
        for ident in ['A', 'B']:
            single = sequence([r for r in rows if r['track_id']==ident], CFG)
            self.assertEqual([r['offline_viterbi'] for r in actual if r['track_id']==ident], [r['offline_viterbi'] for r in single])

    def test_reject_invalid(self):
        for matrix in [[[1, -1], [0, 1]], [[1, 1], [0, 1]], [[float('nan'), 0], [0, 1]]]:
            with self.assertRaises(ValueError): HMM([.5, .5], matrix)
        with self.assertRaises(ValueError): geometry([[0, 0, float('nan')]])
        with self.assertRaises(ValueError): Track(CFG).update(0, feature(), 2)
        for key,value in [('height',-1),('count',-1),('centroid_z',float('nan')),('center',[0,0,float('inf')])]:
            f=feature();f[key]=value
            with self.assertRaises(ValueError):Track(CFG).update(0,f,.9)
        with self.assertRaises(ValueError): transition(np.eye(2), 0)

    def test_initial_low_slow_furniture(self):
        m = Track(CFG)
        for i in range(30):
            self.assertFalse(m.update(i*.1, feature(.4, .2), .95)['candidate'])
        # A persistent furniture-like false positive is NOT cured by temporal filtering.
        m = Track(CFG)
        out = [m.update(i*.1, feature(), .95) for i in range(30)]
        self.assertTrue(out[-1]['presence'][0] > .5)
        self.assertFalse(any(o['candidate'] for o in out))

    def test_stability_long(self):
        h = HMM(CFG['posture']['initial'], CFG['posture']['matrix'])
        for i in range(10000):
            p = h.update([1e-200, .1, .2, .3, .1, .3], None if i == 0 else .103)
        self.assertTrue(np.isfinite(p).all()); self.assertAlmostEqual(float(p.sum()), 1)


if __name__ == '__main__': unittest.main()
