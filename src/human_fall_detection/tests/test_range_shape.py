"""2D旁路的来源、几何与连续观测回归；合成数据不提供人体语义。"""
from dataclasses import replace
import unittest

import numpy as np

from test_range_frontend import scene
from core.range_image import ScanGrid
from core.range_shape import shape_features, ShapeObserver
from core.range_runtime import RangeRuntime, serial


def record(rows, i=0, stamp=None, tid='t1', generation=0, observed=True):
    return dict(frame=i, time_s=i*.1 if stamp is None else stamp, generation=generation,
        target_track_id=tid, target_source_rows=rows, inference_sha256='fixture',
        tracks=[dict(track_id=tid, status='tracked' if observed else 'predicted', observed=observed,
                     position_predicted=not observed, source_rows=rows)])


class ShapeTests(unittest.TestCase):
    def setUp(self):
        self.grid, self.raw, self.frame = scene(np.full((6, 10), 2.))
        self.rows = [12, 13, 22, 23, 32, 33]
        self.labels = np.zeros((6, 10), dtype=np.int32)

    def test_exact_rectangle_and_inherited_fragments(self):
        self.labels[3, 2:4] = 4
        s = shape_features(self.frame, self.rows, self.labels)
        self.assertEqual(s['bbox_rc'], [1, 2, 3, 3])
        self.assertEqual((s['pixel_count'], s['row_span'], s['col_span']), (6, 3, 2))
        self.assertEqual(s['fill_ratio'], 1.)
        self.assertEqual(s['fragment_count'], 2)
        self.assertAlmostEqual(s['largest_fragment_fraction'], 4/6)
        self.assertAlmostEqual(s['range_squared_sum_px_m2'], 24., places=5)
        self.assertAlmostEqual(s['azimuth_span_deg'], 40/9)
        self.assertEqual(s['completeness'], 'UNKNOWN')
        self.assertFalse(s['touches_grid_boundary'])

    def test_reordered_raw_rows_and_reversed_columns(self):
        raw = self.raw[::-1].copy()
        grid = ScanGrid(self.grid.azimuth_deg[:, ::-1], self.grid.elevation_deg[:, ::-1])
        frame = grid.decode(raw, self.frame.binding)
        rows = (len(raw)-1-np.array(self.rows)).tolist()
        a, b = shape_features(self.frame, self.rows), shape_features(frame, rows)
        for k in ('pixel_count', 'row_span', 'col_span', 'azimuth_span_deg', 'range_squared_sum_px_m2'):
            self.assertAlmostEqual(a[k], b[k])
        self.assertEqual(b['bbox_rc'], [1, 6, 3, 7])

    def test_boundaries_invalid_neighbours_and_sparse_fill(self):
        depth = np.full((6, 10), 2.); depth[1, 1] = 0
        _, _, frame = scene(depth)
        s = shape_features(frame, [0, 1, 10, 22])
        self.assertTrue(s['boundary_edges']['top'])
        self.assertTrue(s['boundary_edges']['left'])
        self.assertEqual(s['adjacent_invalid_pixel_count'], 2)
        self.assertAlmostEqual(s['fill_ratio'], 4/9)
        self.assertEqual(s['occlusion'], 'UNKNOWN')

    def test_reject_bad_rows_duplicate_echo_and_labels(self):
        for rows in ([], [1, 1], [-1], [60], [True], [1.5], [[1]]):
            with self.assertRaises(ValueError): shape_features(self.frame, rows)
        raw = np.concatenate((self.raw, self.raw[12:13]))
        frame = self.grid.decode(raw, self.frame.binding)
        with self.assertRaises(ValueError): shape_features(frame, [60])
        for labels in (np.zeros((2, 2), dtype=int), np.zeros((6, 10)), np.full((6, 10), -1, dtype=int)):
            with self.assertRaises(ValueError): shape_features(self.frame, self.rows, labels)
        bad = self.frame.source_rows.copy(); bad[1, 2] = bad[1, 3]
        with self.assertRaises(ValueError): shape_features(replace(self.frame, source_rows=bad), self.rows)

    def test_history_ratios_and_no_input_mutation(self):
        observer = ShapeObserver()
        before = self.frame.source_rows.copy()
        a = observer.update(self.frame, record(self.rows), self.labels)
        b = observer.update(self.frame, record(self.rows[:3], 1), self.labels)
        self.assertIsNone(a['temporal']['pixel_ratio_previous'])
        self.assertEqual(b['temporal']['pixel_ratio_previous'], .5)
        self.assertEqual(b['temporal']['samples'], 2)
        np.testing.assert_array_equal(before, self.frame.source_rows)

    def test_target_generation_binding_clock_gap_and_prediction_reset(self):
        for change in ('target', 'generation', 'binding', 'grid', 'repeat', 'rollback', 'gap', 'skip', 'prediction'):
            observer = ShapeObserver()
            observer.update(self.frame, record(self.rows), self.labels)
            frame, r = self.frame, record(self.rows, 1)
            if change == 'target': r['target_track_id'] = 'other'; r['tracks'][0]['track_id'] = 'other'
            if change == 'generation': r['generation'] = 1
            if change == 'binding': frame = replace(frame, binding=('different',))
            if change == 'grid':
                grid = ScanGrid(self.grid.azimuth_deg, self.grid.elevation_deg, tolerance_deg=.03)
                frame = replace(frame, grid=grid)
            if change == 'repeat': r['time_s'] = 0.
            if change == 'rollback': r['time_s'] = -.1
            if change == 'gap': r['time_s'] = .31
            if change == 'skip': r['frame'] = 2
            if change == 'prediction': r = record(self.rows, 1, observed=False)
            s = observer.update(frame, r, self.labels)
            if change == 'prediction':
                self.assertFalse(s['available']); self.assertIsNone(s['shape'])
            else:
                self.assertEqual(s['temporal']['samples'], 1, change)
                self.assertIsNone(s['temporal']['pixel_ratio_previous'], change)

    def test_empty_ambiguous_and_invalid_rows_cannot_bridge_history(self):
        observer = ShapeObserver()
        observer.update(self.frame, record(self.rows), self.labels)
        empty = record([], 1, tid=None)
        self.assertFalse(observer.update(self.frame, empty)['available'])
        s = observer.update(self.frame, record(self.rows, 2))
        self.assertEqual(s['temporal']['samples'], 1)
        with self.assertRaises(ValueError): observer.update(self.frame, record([100], 3))
        self.assertEqual(observer.update(self.frame, record(self.rows, 4))['temporal']['samples'], 1)

    def test_history_is_bounded_and_window_is_causal(self):
        observer = ShapeObserver(); outputs = []
        for i in range(1000):
            s = observer.update(self.frame, record(self.rows, i))
            self.assertLessEqual(s['temporal']['observed_span_s'], 1.2)
            self.assertLessEqual(s['temporal']['samples'], 128)
            if i < 10: outputs.append(s)
        again = ShapeObserver()
        self.assertEqual(outputs, [again.update(self.frame, record(self.rows, i)) for i in range(10)])

    def test_capacity_bad_clock_and_conflicting_track_do_not_bridge(self):
        observer = ShapeObserver()
        for i in range(129):
            s = observer.update(self.frame, record(self.rows, i, stamp=i*.001))
        self.assertEqual(s['reset_reason'], 'history_capacity')
        self.assertEqual(s['temporal']['samples'], 1)
        with self.assertRaises(ValueError):
            observer.update(self.frame, record(self.rows, 129, stamp=float('nan')))
        self.assertEqual(observer.update(self.frame, record(self.rows, 130))['temporal']['samples'], 1)
        r = record(self.rows, 131); r['tracks'][0]['source_rows'] = self.rows[:2]
        self.assertFalse(observer.update(self.frame, r)['available'])
        self.assertEqual(observer.update(self.frame, record(self.rows, 132))['temporal']['samples'], 1)

    def test_runtime_baseline_remains_equal_with_shadow(self):
        identity = dict(session='synthetic', coordinate='RAW/lidar', grid_sha256=self.grid.sha256)
        plain = RangeRuntime(self.grid, identity, empty_prefix_frames=2)
        shadow = RangeRuntime(self.grid, identity, empty_prefix_frames=2)
        observer = ShapeObserver()
        available = 0
        for i in range(16):
            depth = np.full((6, 10), 3.)
            if i >= 2: depth[1:5, 2:7] = 2.
            _, packed, _ = scene(depth)
            a, _, _ = plain.update(packed, i*.1, i)
            b, frame, components = shadow.update(packed, i*.1, i)
            before = serial(dict(tracking=b['tracking'], rule=b['rule']))
            labels = np.full(frame.grid.shape, -1, dtype=int)
            for c in components: labels.ravel()[c['cells']] = c['component_id']
            s = observer.update(frame, b['tracking'], labels)
            available += int(s['available'])
            self.assertEqual(before, serial(dict(tracking=b['tracking'], rule=b['rule'])))
            self.assertEqual(a['tracking'], b['tracking']); self.assertEqual(a['rule'], b['rule'])
        self.assertGreater(available, 0)


if __name__ == '__main__': unittest.main()
