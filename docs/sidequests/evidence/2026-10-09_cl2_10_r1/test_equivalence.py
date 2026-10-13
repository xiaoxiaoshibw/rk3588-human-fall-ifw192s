"""Exact full-dict differential checks against CL2-09B, not an approximate oracle."""
import ast
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np

E = Path(__file__).resolve().parent
sys.path[:0] = [str(E/'candidate'), str(E/'frozen')]
import floor_sheet as candidate
spec = importlib.util.spec_from_file_location('cl209b', E/'baseline/floor_sheet.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)

def cells(keys):
    return [{'key':list(k)} for k in keys]

class EquivalenceTest(unittest.TestCase):
    def compare(self, keys, reverse=True):
        data = cells(keys)
        saved = copy.deepcopy(data)
        expected = baseline._roi_metrics(data)
        self.assertEqual(candidate._roi_metrics(data), expected, keys)
        if reverse:
            self.assertEqual(candidate._roi_metrics(list(reversed(data))), expected, keys)
        self.assertEqual(data, saved)

    def test_random_small_exact_full_dict(self):
        rng = np.random.RandomState(20903)
        for size in range(4,15):
            for _ in range(12):
                keys = rng.randint(-20,21,(size,2))
                self.compare(keys.tolist())

    def test_random_large_and_duplicates_exact(self):
        rng = np.random.RandomState(20930)
        for size in [24,25,30,60,100]:
            for _ in range(3):
                self.compare(rng.randint(-30,31,(size,2)).tolist())
        for keys in [[],[(0,0)]*3,[(0,0)]*25,
                     [(0,0)]*5+[(0,4),(4,0),(4,4)],
                     [(0,4*k) for k in range(24)]+[(2,6)],
                     [(0,4*k) for k in range(29)]+[(2,6)]]:
            self.compare(keys)

    def test_noncollinear_no_solution_and_true_collinear(self):
        for size in [5,24,25,40,60]:
            self.compare([(8*(k-size//2),0) for k in range(size-1)]+[(0,1)])
            self.compare([(k*4,0) for k in range(size)])

    def test_symmetric_ties_translations_permutations(self):
        keys = [(0,0),(0,4),(0,8),(0,12),(2,6)]
        for x,y in [(0,0),(200,-300),(-398,387)]:
            self.compare([(a+x,b+y) for a,b in keys])
        for permutation in [[2,0,4,1,3],[4,3,2,1,0]]:
            self.compare([keys[k] for k in permutation])

    def test_gate_adjacent_cases_exact(self):
        # Integer 25cm grid: exact distance=.5, just below/above and
        # slender triangles around the condition gate, including no solution.
        for width in range(1,6):
            for length in range(5,32):
                self.compare([(0,0),(0,length),(width,length//2),
                              (0,length//3),(0,2*length//3)])
        for size in [24,25]:
            self.compare([(0,4*k) for k in range(size-1)]+[(2,6)])

    def test_runtime_profile_and_python38_unchanged(self):
        self.assertEqual(candidate.SHEET_PROFILE, baseline.SHEET_PROFILE)
        self.assertEqual(candidate.PROFILE, baseline.PROFILE)
        ast.parse((E/'candidate/floor_sheet.py').read_text(encoding='utf8'),feature_version=(3,8))

if __name__ == '__main__':
    unittest.main()
