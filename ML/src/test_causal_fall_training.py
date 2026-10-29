import io
import unittest

import numpy as np

from evaluate_fall_candidate import scores
from train_causal_fall import decode_person_npz, matrix, segments


class CausalFallTrainingTest(unittest.TestCase):
    def test_livox_aggregation_uses_only_past_source_packets(self):
        rng = np.random.default_rng(5)
        points = rng.normal(size=(24, 4)).astype(np.float32)
        def payload(p, times):
            stream = io.BytesIO()
            np.savez(stream, points=p, frame_offsets=np.arange(0, 25, 4), timestamps_bag=times)
            return stream.getvalue()
        times = np.arange(6)*.033
        raw = payload(points, times)
        native, _, _ = decode_person_npz(raw)
        self.assertTrue(np.isnan(native).all())
        ff, counts, stamps, metadata = decode_person_npz(raw, aggregate_packets=3, return_metadata=True)
        self.assertEqual(counts, [12, 12]); self.assertEqual(stamps, [times[2], times[5]])
        self.assertTrue(np.isfinite(ff).all())
        self.assertEqual(metadata['source_packet_spans'], [(0, 3), (3, 6)])
        changed = points.copy(); changed[12:] *= 100
        other, _, _ = decode_person_npz(payload(changed, times), aggregate_packets=3)
        np.testing.assert_array_equal(ff[0], other[0])
        gap_times = np.array([0., .03, .9, .93, .96, .99])
        gap, _, _ = decode_person_npz(payload(points, gap_times), aggregate_packets=3)
        self.assertTrue(np.isnan(gap[0]).all())

    def test_invalid_frames_break_windows_and_keep_source_indices(self):
        rng = np.random.default_rng(42)
        features = rng.normal(size=(80, 19))
        features[20] = np.nan
        self.assertEqual([len(s) for s in segments(features)], [20, 59])
        records = [{'sequence': 's', 'group': 'p', 'label': 1}]
        X, rows = matrix({'s': features}, records, stride=1)
        self.assertEqual(X.shape[1], 114)
        self.assertTrue(all(not (r['begin_index'] <= 20 < r['end_index_exclusive']) for r in rows))
        self.assertEqual(rows[0]['begin_index'], 0)
        self.assertEqual(rows[0]['end_index_exclusive'], 10)
        self.assertTrue(all(10 <= r['end_index_exclusive']-r['begin_index'] <= 30 for r in rows))
        changed = features.copy(); changed[50:] = 500
        changed_X, changed_rows = matrix({'s': changed}, records)
        prefix = [i for i, r in enumerate(rows) if r['end_index_exclusive'] <= 50]
        np.testing.assert_array_equal(X[prefix], changed_X[prefix])
        empty, rows = matrix({'s': np.empty((0, 19))}, records)
        self.assertEqual(empty.shape, (0, 114)); self.assertEqual(rows, [])

    def test_person_archive_offsets_empty_frames_and_time_gaps(self):
        def payload(points, offsets, times):
            stream = io.BytesIO()
            np.savez(stream, points=points, frame_offsets=offsets, timestamps_bag=times)
            return stream.getvalue()
        points = np.zeros((36, 4), dtype=np.float32)
        ff, counts, stamps = decode_person_npz(payload(points, np.array([0, 12, 12, 24, 36]), np.array([0., .1, .2, 1.])))
        self.assertEqual(counts, [12, 0, 12, 12])
        self.assertTrue(np.isfinite(ff[[0, 2]]).all())
        self.assertTrue(np.isnan(ff[[1, 3]]).all())
        for offsets, times in [(np.array([0, 24, 12, 36]), np.array([0., .1, .2])),
                               (np.array([0, 12, 36]), np.array([0., 0.])),
                               (np.array([0, 12, 35]), np.array([0., .1]))]:
            with self.assertRaises(ValueError): decode_person_npz(payload(points, offsets, times))
        self.assertIsNone(scores([], [])['fall_recall'])


if __name__ == '__main__':
    unittest.main()
