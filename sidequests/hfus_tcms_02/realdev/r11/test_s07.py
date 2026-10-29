import itertools
import unittest
import numpy as np
from association import OLD, associate_tracks, expire

def tr(name, x): return dict(track_id=name, position_m=[x,0,0], size_m=1.)
def ca(name, x): return dict(candidate_id=name, position_m=[x,0,0], size_m=1.)

class ContractTests(unittest.TestCase):
    def partition(self, r, ts, cs):
        mt={m['track_id'] for m in r['matches']}; mc={m['candidate_id'] for m in r['matches']}
        for groups, universe in (([mt,set(r['ambiguous_track_ids']),set(r['unmatched_track_ids'])],{t['track_id'] for t in ts}),([mc,set(r['ambiguous_candidate_ids']),set(r['unmatched_candidate_ids'])],{c['candidate_id'] for c in cs})):
            self.assertEqual(set.union(*groups),universe)
            self.assertEqual(sum(map(len,groups)),len(universe))
    def test_minimal_repro(self):
        ts=[tr('A',0),tr('B',.45)]; cs=[ca('X',.4),ca('Y',-.4)]
        old=OLD.associate_tracks(ts,cs)
        self.assertTrue({m['candidate_id'] for m in old['matches']} & set(old['ambiguous_candidate_ids']))
        new=associate_tracks(ts,cs); self.partition(new,ts,cs)
        self.assertEqual(new['matches'],[]);self.assertEqual(new['ambiguous_track_ids'],['A','B'])
    def test_order_competition_near_three(self):
        for ts,cs in (([tr('A',0),tr('B',.1)],[ca('X',.05)]),([tr('A',0),tr('B',.45)],[ca('X',.4),ca('Y',-.4),ca('Z',-.41)])):
            first=None
            for t in itertools.permutations(ts):
                for c in itertools.permutations(cs):
                    r=associate_tracks(list(t),list(c));self.partition(r,ts,cs)
                    if first is None:first=r
                    self.assertEqual(r,first)
            self.assertEqual(first['unmatched_candidate_ids'],[])
    def test_empty_mismatch_and_match(self):
        for ts,cs in (([],[]),([tr('A',0)],[]),([],[ca('X',0)]),([tr('A',0)],[ca('X',10)]),([tr('A',0)],[ca('X',.1)])):
            self.partition(associate_tracks(ts,cs),ts,cs)
    def test_expiration(self):
        t=dict(last_t=0,state='AMBIGUOUS',events=[])
        self.assertEqual(expire([t],9,1.,1.),[t])
        self.assertEqual(expire([t],10,1.001,1.),[])
        self.assertEqual(t['state'],'LOST');self.assertEqual(t['events'][-1]['old'],'AMBIGUOUS')
    def test_invalid_duplicate_size(self):
        with self.assertRaises(ValueError):associate_tracks([tr('A',0),tr('A',1)],[])
        with self.assertRaises(ValueError):associate_tracks([],[ca('X',float('nan'))])
        c=ca('X',0);c['size_m']=10
        self.assertEqual(associate_tracks([tr('A',0)],[c])['matches'],[])

if __name__=='__main__':unittest.main()
