"""Synthetic explicit expectations; none of these fixtures is human GT."""
import copy
import json
import math
import unittest
from pathlib import Path
import numpy as np
from record import OUT, save
from skeleton import normalize, nodes, process, SkeletonTracker, unknown, ALL_SLOTS, minimum_gt

PARAMS = json.loads((OUT/'prototype_params_v1.json').read_text('utf8'))

def fixture():
    points = []
    for z in [0.2, 0.4, 0.6, 0.8, 1.0, 1.1, 1.2, 1.35, 1.55, 1.7]:
        for x in [-0.16, -0.12, 0.12, 0.16]:
            for y in [-0.03, 0.03]:
                points.append([10+x, 20+y, z])
    rows = list(range(len(points)))
    member = {'receipt': {'id': 'SYNTHETIC/0', 'rows': rows}, 'global_rows': [100+r for r in rows], 'xyz': points, 'invalid_source_rows': []}
    review = {}
    for k in ALL_SLOTS:
        lo, hi = PARAMS['bands_m'].get(k, [1.5, 1.8] if k == 'HEAD' else [0.1, 0.55])
        rr = [i for i, p in enumerate(points) if lo <= p[2] < hi]
        if k in ['LOWER_A', 'LOWER_B']:
            rr = [i for i in rr if (points[i][0] < 10) == (k == 'LOWER_A')]
        review[k] = {'visibility': 'VISIBLE', 'region_rows': rr, 'reason': 'HEAD_CONFIRMED' if k == 'HEAD' else 'SYNTHETIC_VISIBLE_REGION'}
    return member, review

class GeometryTests(unittest.TestCase):
    def test_full_map_xy_and_z(self):
        member, _ = fixture()
        n = normalize(member, PARAMS)
        self.assertEqual(n['rows'], member['receipt']['rows'])
        self.assertEqual(n['global_rows'], member['global_rows'])
        np.testing.assert_array_equal(np.array(n['xyz'])[:, 2], np.array(member['xyz'])[:, 2])
        np.testing.assert_allclose(np.array(n['xyz'])+n['inverse_translation_m'], member['xyz'], atol=1e-5, rtol=0)
        self.assertLessEqual(n['inverse_max_error_m'], 1e-5)

    def test_realistic_legal_positive_not_all_reject(self):
        m, r = fixture()
        n, result = process(m, 'PERSON', r, PARAMS, True)
        self.assertEqual(len(result), 7)
        for v in result.values():
            self.assertTrue(v['valid'])
            self.assertGreaterEqual(v['support_n'], 6)
            self.assertEqual(v['support_n'], len(v['support_rows']))
        np.testing.assert_allclose(result['CHEST']['xyz'], [10, 20, 1.05], atol=1e-12)
        np.testing.assert_allclose(result['PELVIS_REGION']['xyz'], [10, 20, 0.7], atol=1e-12)
        self.assertEqual(result['CHEST']['support_rows'], list(range(32, 48)))

    def test_nonperson_and_gate_reject(self):
        m, r = fixture()
        for label in ['STATIC_OBJECT', 'MIXED', 'UNKNOWN', 'UNREVIEWED']:
            n, out = process(m, label, r, PARAMS, True)
            self.assertIsNone(n)
            self.assertTrue(all(not v['valid'] and v['xyz'] is None for v in out.values()))
        self.assertTrue(all(not v['valid'] for v in process(m, 'PERSON', r, PARAMS, False)[1].values()))

    def test_invalid_source_not_rehabilitated(self):
        m, _ = fixture()
        # A raw zero becomes nonzero after TLS translation but remains invalid.
        m['xyz'] += [[0.02, -0.03, 1.05], [None, 0, 1], [float('inf'), 0, 1]]
        m['receipt']['rows'] += [80, 81, 82]
        m['global_rows'] += [180, 181, 182]
        m['invalid_source_rows'] = [80, 81, 82]
        n = normalize(m, PARAMS)
        self.assertEqual(n['excluded_source_rows'], [80, 81, 82])
        self.assertNotIn(80, n['rows'])

    def test_empty_sparse_conflict(self):
        m, r = fixture()
        empty = {'receipt': {'rows': []}, 'global_rows': [], 'xyz': [], 'invalid_source_rows': []}
        result = nodes(normalize(empty, PARAMS), r, PARAMS)
        self.assertTrue(all(not v['valid'] for v in result.values()))
        m['xyz'] = m['xyz'][:4];m['receipt']['rows'] = list(range(4));m['global_rows'] = list(range(4))
        self.assertFalse(nodes(normalize(m, PARAMS), r, PARAMS)['LOWER_REGION']['valid'])
        m, r = fixture()
        for p in m['xyz']:
            p[0] *= 10
        self.assertEqual(nodes(normalize(m, PARAMS), r, PARAMS)['CHEST']['reason'], 'CONFLICTING_SPATIAL_SUPPORT')

    def test_head_hand_and_missing(self):
        m, r = fixture()
        r['HEAD']['reason'] = 'HEAD_OR_HAND_AMBIGUOUS'
        self.assertEqual(nodes(normalize(m, PARAMS), r, PARAMS)['HEAD']['reason'], 'HEAD_OR_HAND_AMBIGUOUS')
        r['HEAD']['visibility'] = 'INVISIBLE'
        self.assertEqual(nodes(normalize(m, PARAMS), r, PARAMS)['HEAD']['reason'], 'NO_VISIBLE_HEAD_SUPPORT')
        # The high hand is never chosen automatically.
        r['HEAD']['visibility'] = 'UNCERTAIN'
        self.assertIsNone(nodes(normalize(m, PARAMS), r, PARAMS)['HEAD']['xyz'])

    def test_lower_single_and_axis_degeneracy(self):
        m, r = fixture()
        for p in m['xyz']:
            p[0] = 10
        n = normalize(m, PARAMS)
        self.assertNotIn('LOWER_A', nodes(n, r, PARAMS))
        m['xyz'] = [[1, 1, 1]]*80
        self.assertEqual(normalize(m, PARAMS)['principal_axis']['status'], 'UNKNOWN_DEGENERATE')
        self.assertEqual(n['principal_axis']['sign'], 'UNKNOWN')

    def test_duplicate_map(self):
        m, _ = fixture();m['receipt']['rows'][1] = 0
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_MEMBER_ROWS'):
            normalize(m, PARAMS)

    def test_minimum_gt_not_machine_id(self):
        entries = [{'sid': 'D1', 'split': 'development'}, {'sid': 'D2', 'split': 'development'}]
        self.assertFalse(minimum_gt([], entries)['satisfied'])
        _, r = fixture();r['HEAD']['visibility'] = 'INVISIBLE'
        records = [{'sid': sid, 'ordinal': i, 'label': 'PERSON', 'person_id': 'p', 'track_epoch': 'e', 'nodes': r} for sid in ['D1', 'D2'] for i in [10, 11, 12]]
        self.assertTrue(minimum_gt(records, entries)['satisfied'])
        records[-1]['person_id'] = 'other'
        self.assertFalse(minimum_gt(records, entries)['satisfied'])

class TrackerTests(unittest.TestCase):
    def frame(self, i=0, ns=0):
        return {'sid': 'SYNTHETIC', 'branch': 'test', 'coordinate_id': 'coords', 'person_id': 'fixture', 'track_epoch': 'e', 'ordinal': i, 'stamp_sec': 100, 'stamp_nanosec': ns}

    def obs(self, x=1):
        return {'CHEST': {'valid': True, 'xyz': [x, 2, 1], 'reason': 'SYNTHETIC'}}

    def test_actual_dt_ema(self):
        t = SkeletonTracker(PARAMS);t.tick(self.frame(), self.obs())
        r = t.tick(self.frame(1, 150000000), self.obs(1.1))
        self.assertEqual(r['dt_s'], 0.15)
        self.assertAlmostEqual(r['nodes']['CHEST']['filtered_xyz'][0], 1+0.1*(1-math.exp(-0.15/0.2)))

    def test_missing_no_valid_history_fill(self):
        t = SkeletonTracker(PARAMS);t.tick(self.frame(), self.obs())
        r = t.tick(self.frame(1, 100000000), {'CHEST': unknown('MISSING')})
        self.assertFalse(r['nodes']['CHEST']['measurement_valid'])
        self.assertIsNone(r['nodes']['CHEST']['filtered_xyz'])
        self.assertEqual(r['nodes']['CHEST']['history_xyz'], [1, 2, 1])
        r = t.tick(self.frame(2, 200000000), self.obs(1.2))
        self.assertEqual(r['nodes']['CHEST']['filtered_xyz'], [1.2, 2, 1])

    def test_all_key_changes(self):
        for field in ['sid', 'branch', 'coordinate_id', 'person_id', 'track_epoch']:
            t = SkeletonTracker(PARAMS);t.tick(self.frame(), self.obs())
            f = self.frame(1, 100000000);f[field] += '_new'
            self.assertEqual(t.tick(f, self.obs(1.2))['reset_reason'], 'KEY_CHANGED')

    def test_missing_duplicate_reverse_seek_gap(self):
        cases = [(self.frame(2, 100000000), False, 'MISSING_FRAME_OR_SEEK'),
                 (self.frame(1, 0), False, 'DUPLICATE_OR_REVERSE_STAMP'),
                 (self.frame(1, 0), True, 'EXPLICIT_SEEK'),
                 (self.frame(1, 900000000), False, 'TIME_GAP')]
        for f, seek, reason in cases:
            t = SkeletonTracker(PARAMS);t.tick(self.frame(), self.obs())
            self.assertEqual(t.tick(f, self.obs(1.2), seek)['reset_reason'], reason)
        t = SkeletonTracker(PARAMS);t.tick(self.frame(1, 200000000), self.obs())
        self.assertEqual(t.tick(self.frame(0, 100000000), self.obs())['reset_reason'], 'DUPLICATE_OR_REVERSE_STAMP')

    def test_jump_raw_retained_and_recovery(self):
        t = SkeletonTracker(PARAMS);t.tick(self.frame(), self.obs())
        r = t.tick(self.frame(1, 100000000), self.obs(10))['nodes']['CHEST']
        self.assertTrue(r['measurement_valid']);self.assertFalse(r['filter_valid']);self.assertEqual(r['raw_xyz'], [10, 2, 1])
        self.assertEqual(t.tick(self.frame(2, 200000000), self.obs(10))['nodes']['CHEST']['filtered_xyz'], [10, 2, 1])

    def test_invalid_stamp(self):
        f = self.frame();f['stamp_nanosec'] = 1000000000
        with self.assertRaisesRegex(ValueError, 'INVALID_STAMP'):
            SkeletonTracker(PARAMS).tick(f, self.obs())

def export_synthetic():
    m, review = fixture()
    norm = normalize(m, PARAMS)
    raw = nodes(norm, review, PARAMS)
    tracker = SkeletonTracker(PARAMS)
    frame = TrackerTests().frame()
    lifecycle = [tracker.tick(frame, raw)]
    frame = TrackerTests().frame(1, 150000000)
    lifecycle.append(tracker.tick(frame, {k: unknown('SYNTHETIC_MISSING') for k in raw}))
    frame = TrackerTests().frame(2, 250000000)
    lifecycle.append(tracker.tick(frame, raw))
    save(OUT/'synthetic_fixture.json', {'source': 'synthetic', 'counts_as_real_gt': False, 'member': m, 'node_review': review})
    save(OUT/'synthetic_output.json', {'source': 'synthetic', 'counts_as_real_gt': False, 'normalized': norm, 'nodes_raw': raw, 'lifecycle': lifecycle})

if __name__ == '__main__':
    import sys
    if '--dump' in sys.argv:
        export_synthetic()
    else:
        unittest.main()
