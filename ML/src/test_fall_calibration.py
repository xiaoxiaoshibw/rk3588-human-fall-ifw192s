import unittest

from calibrate_fall_candidate import fit_rule, simulate


class FallCalibrationTest(unittest.TestCase):
    def test_rule_selection_is_group_budgeted_and_conservative_on_ties(self):
        records, windows = [], {}
        for person in ['p1', 'p2']:
            positive = person+'/fall'
            records.append({'sequence': positive, 'group': person, 'label': 1})
            windows[positive] = [{'end_index_exclusive': i+10, 'fall_probability': .85} for i in range(3)]
            for i in range(50):
                seq = person+'/negative%d' % i
                records.append({'sequence': seq, 'group': person, 'label': 0})
                values = [.85, .85, .1] if i == 0 else [.1, .1, .1]
                windows[seq] = [{'end_index_exclusive': j+10, 'fall_probability': p} for j, p in enumerate(values)]
        grid, selected = fit_rule(records, windows)
        self.assertEqual(len(grid), 21)
        self.assertEqual(selected['high'], .8)
        self.assertEqual(selected['positive_windows'], 3)
        self.assertEqual(selected['mean_positive_person_recall'], 1.)
        self.assertEqual(selected['false_candidates'], 0)

    def test_gaps_unknowns_and_no_eligible_rule_remain_explicit(self):
        records = [{'sequence': 'a', 'group': 'p', 'label': 1}, {'sequence': 'b', 'group': 'p', 'label': 0}]
        windows = {'a': [{'end_index_exclusive': 10, 'fall_probability': 1.},
                         {'end_index_exclusive': 12, 'fall_probability': 1.}]}
        result = simulate(records, windows, .8, 2)
        self.assertEqual(result[0]['candidate'], 0)
        self.assertIsNone(result[1]['candidate'])
        windows['b'] = [{'end_index_exclusive': i+10, 'fall_probability': 1.} for i in range(3)]
        _, selected = fit_rule(records, windows)
        self.assertIsNone(selected)


if __name__ == '__main__': unittest.main()
