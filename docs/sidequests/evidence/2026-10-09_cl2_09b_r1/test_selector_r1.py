"""Contract regression: frozen success, known false refusal, complete oracle."""
import ast,copy,importlib.util,itertools,time,unittest
import numpy as np
from pathlib import Path
from floor_sheet import _roi_metrics, SHEET_PROFILE
from floor_detector import PROFILE
E=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('baseline_sheet',E/'frozen/floor_sheet.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

def clean(keys):return [{'key':list(k)} for k in keys]
def feasible_combos(keys):
    keys=sorted(keys); feasible=[]
    for combo in itertools.combinations(keys,4):
        pairwise=[float(np.hypot(a[0]-b[0],a[1]-b[1]))*.25 for a,b in itertools.combinations(combo,2)]
        q=np.array(combo,dtype=float);s=np.linalg.svd(q-q.mean(axis=0),compute_uv=False)
        condition=s[1]/max(s[0],1e-30)
        if min(pairwise)>=.5 and condition>=.1:feasible.append((min(pairwise),combo))
    return feasible

class SelectorTest(unittest.TestCase):
    def test_known_five_cell_false_rejection(self):
        keys=[(0,0),(0,4),(0,8),(0,12),(2,6)]
        self.assertFalse(old._roi_metrics(clean(keys))['ok'])
        got=_roi_metrics(clean(keys));self.assertTrue(got['ok'])
        self.assertGreaterEqual(got['condition'],.1)
        self.assertGreaterEqual(got['min_sep_m'],.5)
        self.assertEqual(got['independent_count'],4)
        self.assertEqual(len(feasible_combos(keys)),4)

    def test_large_greedy_failure_has_feasible_alternative(self):
        keys=[(0,4*k) for k in range(24)]+[(2,6)]
        self.assertFalse(old._roi_metrics(clean(keys))['ok'])
        got=_roi_metrics(clean(keys));self.assertTrue(got['ok'])
        self.assertEqual(got['min_sep_m'],max(x[0] for x in feasible_combos(keys)))

    def test_frozen_success_and_determinism_and_caller_ownership(self):
        rng=np.random.default_rng(20261009)
        checked=0
        for size in [4,5,10,24,25,60]:
            for _ in range(5):
                keys=sorted(set(map(tuple,rng.integers(-20,21,(size*3,2)).tolist())))[:size]
                data=clean(keys);saved=copy.deepcopy(data);expected=old._roi_metrics(data)
                actual=_roi_metrics(data)
                if expected['ok']:
                    self.assertEqual(actual,expected);checked+=1
                self.assertEqual(actual,_roi_metrics(list(reversed(data))))
                self.assertEqual(data,saved)
        self.assertGreater(checked,20)

    def test_complete_small_corpus_matches_feasibility_oracle(self):
        rng=np.random.default_rng(18)
        for size in range(4,11):
            for _ in range(10):
                keys=sorted(set(map(tuple,rng.integers(-5,6,(size*4,2)).tolist())))[:size]
                choices=feasible_combos(keys);actual=_roi_metrics(clean(keys));previous=old._roi_metrics(clean(keys))
                self.assertEqual(actual['ok'],bool(choices),(keys,actual))
                if actual['ok'] and not previous['ok']:
                    self.assertAlmostEqual(actual['min_sep_m'],max(x[0] for x in choices),places=12)
                if previous['ok']:self.assertEqual(actual,previous)

    def test_true_insufficiency_and_condition_failure_still_rejected(self):
        for keys in [[(0,0),(4,0),(8,0)],[(0,0),(0,1),(1,0),(1,1)],
                     [(0,0),(0,8),(1,16),(1,24)],[(0,k) for k in range(64)],
                     [(0,0)]*4]:
            actual=_roi_metrics(clean(keys));self.assertFalse(actual['ok'])
            self.assertEqual(actual,old._roi_metrics(clean(keys)))

    def test_gate_boundary_and_profiles_unchanged(self):
        keys=[(0,0),(0,2),(2,0),(2,2)]
        got=_roi_metrics(clean(keys));self.assertTrue(got['ok']);self.assertEqual(got['min_sep_m'],.5)
        self.assertEqual(SHEET_PROFILE,old.SHEET_PROFILE)
        self.assertEqual(PROFILE['cell_m'],.25)

    def test_candidate_python38_syntax(self):
        ast.parse((E/'candidate/floor_sheet.py').read_text(encoding='utf8'),feature_version=(3,8))

if __name__=='__main__':unittest.main()
