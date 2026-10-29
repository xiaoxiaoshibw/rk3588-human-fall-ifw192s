import copy
import unittest
import tempfile
import json
from pathlib import Path
import numpy as np
from tcms import Window, support, explain, calibrate, active, BASE
from run_experiment import load, validate_meta


class ContractTests(unittest.TestCase):
    def test_invalid_and_original_indices(self):
        p = np.array([[1., 1., 1.], [np.nan, 0, 0], [0, 0, 0], [1.01, 1, 1], [20, 0, 0]])
        hits, rejected = support(p, .12)
        self.assertEqual(rejected, 3)
        self.assertEqual(next(iter(hits.values()))[1].tolist(), [0, 3])
        with self.assertRaises(ValueError): support(p[:, :2], .12)
        with self.assertRaises(ValueError): support(p, float('nan'))

    def test_static_and_translating_same_support(self):
        a = {i*BASE*BASE+j*BASE+2 for i in range(3) for j in range(3)}
        self.assertEqual(explain(a, a), (0., 0., (0, 0, 0)))
        b = {v+BASE*BASE for v in a}
        static, gain, shift = explain(a, b)
        self.assertGreater(static, .3)
        self.assertGreater(gain, .25)
        self.assertEqual(shift, (-1, 0, 0))
        # Shifted furniture has identical motion evidence: no human label.
        self.assertEqual(explain(a, b), explain(a, b))

    def test_unknown_gap_session_and_mutation(self):
        cells = {i for i in range(10)}
        hits = {(0, 0, 0): (cells, np.arange(10))}
        w = Window(.12, 2)
        w.update(hits, 0.)
        cells.clear()
        self.assertEqual(len(w.history[0][1][(0, 0, 0)]), 10)
        rows, state = w.update({}, .1)
        self.assertEqual(state['state'], 'WARMUP')
        w.update({}, .2)
        rows, state = w.update({}, .3)
        self.assertEqual(rows, [])
        rows, state = w.update(hits, 2.)
        self.assertTrue(state['gap_reset'])
        self.assertEqual(state['state'], 'WARMUP')
        self.assertEqual(Window(.12, 2).last, None)
        with self.assertRaises(ValueError): w.update({}, 1.)

    def test_causal_prefix_and_sparse_support(self):
        hits = {(0, 0, 0): (set(range(10)), np.arange(10))}
        a, b = Window(.12, 2), Window(.12, 2)
        prefix = [a.update(hits, t*.1) for t in range(6)]
        full = [b.update(hits, t*.1) for t in range(9)]
        self.assertEqual(prefix, full[:6])
        sparse = Window(.12, 2)
        for i in range(4): rows, state = sparse.update({(0, 0, 0): ({1}, [0])}, i*.1)
        self.assertEqual(rows, [])
        self.assertEqual(state['unknown_current_tiles'], 1)

    def test_calibration_unknown_and_no_report_leak(self):
        rows = [dict(range_bin=0, B1=0., B2=.1, B3=0.) for _ in range(30)]
        limits = calibrate(rows)
        original = copy.deepcopy(limits)
        row = dict(range_bin=0, B1=.5, B2=.5, B3=.2)
        self.assertTrue(active(row, limits, 'B3'))
        self.assertEqual(limits, original)
        row['range_bin'] = 2
        self.assertFalse(active(row, limits, 'B3'))

    def test_source_layout_truncation_time_and_identity(self):
        meta = dict(format='human_capture_session', format_version=1, session_id='sample',
                    point_stride_bytes=28, total_points=1,
                    point_layout=dict(fields=['x', 'y', 'z'], dtypes=['<f4']*3, stride_bytes=28, endian='little'),
                    frames=[dict(offset_points=0, count_points=1, stamp_sec=1, stamp_nanosec=0)])
        validate_meta(meta, 28)
        with self.assertRaises(ValueError): validate_meta(meta, 27)
        bad = copy.deepcopy(meta); bad['frames'].append(dict(bad['frames'][0]))
        with self.assertRaises(ValueError): validate_meta(bad, 28)
        bad = copy.deepcopy(meta); bad['point_stride_bytes'] = 26
        with self.assertRaises(ValueError): validate_meta(bad, 28)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'sample'; folder.mkdir()
            (folder/'points.bin').write_bytes(np.array([1., 2., 3.], dtype='<f4').tobytes()+b'\xff'*16)
            (folder/'meta.json').write_text(json.dumps(meta), encoding='utf8')
            record, xyz, binding = load(folder)
            self.assertEqual(xyz.tolist(), [[1., 2., 3.]])
            del xyz
            meta['point_layout']['endian'] = 'big'
            (folder/'meta.json').write_text(json.dumps(meta), encoding='utf8')
            with self.assertRaises(ValueError): load(folder)


if __name__ == '__main__': unittest.main()
