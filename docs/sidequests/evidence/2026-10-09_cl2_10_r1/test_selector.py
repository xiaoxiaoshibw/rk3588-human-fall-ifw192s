"""Contract regression: frozen success, known false refusal, complete oracle."""
import ast,copy,importlib.util,itertools,time,unittest,sys
import numpy as np
from unittest.mock import patch
from contextlib import ExitStack
from pathlib import Path
E=Path(__file__).resolve().parent
sys.path[:0]=[str(E/'candidate'),str(E/'frozen')]
from floor_sheet import _roi_metrics, SHEET_PROFILE
from floor_detector import PROFILE
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

    def test_tied_feasible_fallback_keeps_first_sorted_combo(self):
        keys=[(0,0),(0,4),(0,8),(0,12),(2,6)]
        got=_roi_metrics(clean(keys))
        self.assertEqual(got['selected'],[[0.,0.],[0.,4.],[0.,8.],[2.,6.]])
        self.assertEqual(got,_roi_metrics(clean(list(reversed(keys)))))

    def test_duplicate_keys_cannot_displace_valid_four(self):
        keys=[(0,0),(0,0),(0,0),(0,4),(4,0),(4,4)]
        result=_roi_metrics(clean(keys));self.assertTrue(result['ok'])
        self.assertEqual(len(set(map(tuple,result['selected']))),4)

    def test_v3_defers_to_repaired_v2_without_fine_reselection(self):
        import floor_sheet as module
        import floor_roi
        keys=[(0,0),(0,4),(0,8),(0,12),(2,6)]
        self.assertFalse(old._roi_metrics(clean(keys))['ok'])
        cells=[dict(key=list(k),count=100,min_frame_count=30,height_span_m=.01,
            local_rms_m=.001,local_normal_z=1.) for k in keys]
        plane=dict(normal=[0.,0.,1.],offset_m=1.3,voxels=100)
        sheet=dict(effective_area_m2=1.,effective_coverage=1.,temporal_p05=1.,
            bridging_needed=False,gap_pairs=[],occupied_cells=400,largest_area_m2=1.,
            effective_cells=400,unexplained_gap_count=0)
        with ExitStack() as stack:
            stack.enter_context(patch.object(module,'detect_floor_regions',side_effect=ValueError('floor_regions_invalid')))
            stack.enter_context(patch.object(module,'_discover_planes',return_value=[plane]))
            stack.enter_context(patch.object(module,'_sheet_metrics',return_value=sheet))
            stack.enter_context(patch.object(module,'_clean_cells',return_value=cells))
            stack.enter_context(patch.object(floor_roi,'fine_boxes',side_effect=AssertionError('fine fallback must not run')))
            result=floor_roi.detect_floor_regions_v3(np.ones((80,3)),np.zeros(80,dtype='i4'),26,0)
        self.assertEqual(result['candidate']['kind'],'lowest_floor_sheet_v2')
        self.assertTrue(all(abs(b[1]-b[0]-.25)<1e-12 for b in result['regions']))

if __name__=='__main__':unittest.main()
