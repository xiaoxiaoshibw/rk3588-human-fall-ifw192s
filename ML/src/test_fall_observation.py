"""Regression cases for the observation ledger and posture attribution.

Synthetic person streams are used so the expected classification is known
beforehand: a vertical slab is an upright actor, a horizontal one is an actor
on the ground, and a dropout between the two must be reported as a transition
the actor crop does not cover - never as a detected fall.
"""
import io
import unittest

import numpy as np

from analyse_fall_observations import (LYING_MIN_INCL, UPRIGHT_MAX_INCL, analyse_clip,
                                       clip_inclinations, inclination, posture)
from fall_observation_ledger import decode, frame_shape, segments


def upright_frame(count=200, height=1.7, seed=0):
    rng = np.random.default_rng(seed)
    z = np.linspace(0.0, height, count)
    return np.stack([rng.normal(0, 0.05, count), rng.normal(0, 0.05, count), z,
                     np.zeros(count)], axis=1)


def lying_frame(count=200, length=1.7, seed=1):
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, length, count)
    return np.stack([x, rng.normal(0, 0.05, count), rng.normal(0, 0.05, count),
                     np.zeros(count)], axis=1)


def stream(frames, stamps=None):
    blocks = [np.asarray(f, dtype=np.float32) for f in frames]
    offsets = np.concatenate([[0], np.cumsum([len(b) for b in blocks])]).astype(np.int32)
    if stamps is None:
        stamps = np.arange(len(blocks), dtype=np.float64) * 0.143
    return {'points': np.concatenate(blocks) if blocks else np.zeros((0, 4), np.float32),
            'frame_offsets': offsets, 'timestamps_bag': np.asarray(stamps, dtype=np.float64)}


def record_for(raw, minimum=10):
    counts = [int(raw['frame_offsets'][i + 1] - raw['frame_offsets'][i])
              for i in range(len(raw['timestamps_bag']))]
    runs = segments(counts, minimum, 0.5, raw['timestamps_bag'])
    return {'frames': len(counts),
            'zero_frames': [i for i, c in enumerate(counts) if c == 0],
            'short_frames': [i for i, c in enumerate(counts) if 0 < c < minimum],
            'valid_runs': runs, 'longest_valid_run': max((len(r) for r in runs), default=0)}


class FrameShapeTest(unittest.TestCase):
    def test_standing_axis_is_vertical(self):
        shape = frame_shape(upright_frame()[:, :3])
        self.assertLess(inclination(shape['axis']), 5.0)

    def test_lying_axis_is_horizontal(self):
        shape = frame_shape(lying_frame()[:, :3])
        self.assertGreater(inclination(shape['axis']), 85.0)

    def test_two_points_have_no_second_moment(self):
        self.assertIsNone(frame_shape(np.zeros((2, 3))))


class SegmentTest(unittest.TestCase):
    def test_gap_breaks_run(self):
        counts = [20] * 5 + [0] * 3 + [20] * 5
        runs = segments(counts, 10, 0.5, np.arange(13) * 0.1)
        self.assertEqual([len(r) for r in runs], [5, 5])

    def test_short_frames_are_not_valid(self):
        counts = [20, 3, 20, 20]
        runs = segments(counts, 10, 0.5, np.arange(4) * 0.1)
        self.assertEqual(len(runs), 2)

    def test_time_gap_breaks_run_even_with_dense_indices(self):
        runs = segments([20] * 4, 10, 0.5, np.array([0.0, 0.1, 0.9, 1.0]))
        self.assertEqual(len(runs), 2)


class DecodeTest(unittest.TestCase):
    def test_round_trip(self):
        raw = stream([upright_frame(), lying_frame()])
        buffer = io.BytesIO()
        np.savez_compressed(buffer, points=raw['points'], frame_offsets=raw['frame_offsets'],
                            timestamps_bag=raw['timestamps_bag'])
        points, offsets, stamps, keys = decode(buffer.getvalue())
        self.assertEqual(len(points), len(raw['points']))
        self.assertEqual(list(offsets), list(raw['frame_offsets']))
        self.assertEqual(sorted(keys), ['frame_offsets', 'points', 'timestamps_bag'])
        self.assertAlmostEqual(float(stamps[-1]), 0.143, places=6)

    def test_negative_offset_rejected(self):
        points = np.zeros((4, 4), np.float32)
        buffer = io.BytesIO()
        np.savez_compressed(buffer, points=points, frame_offsets=np.array([0, 3, 2, 4]),
                            timestamps_bag=np.array([0.0, 0.1, 0.2]))
        with self.assertRaises(ValueError):
            decode(buffer.getvalue())


class AttributionTest(unittest.TestCase):
    def talk(self, frames):
        raw = stream(frames)
        return analyse_clip(raw, record_for(raw))

    def test_descent_observed(self):
        frames = [upright_frame(seed=i) for i in range(4)] + [lying_frame(seed=i) for i in range(4)]
        result = self.talk(frames)
        self.assertEqual(result['posture'], 'DESCENT_OBSERVED')
        self.assertLess(result['min_incl'], UPRIGHT_MAX_INCL)
        self.assertGreater(result['max_incl'], LYING_MIN_INCL)

    def test_descent_hidden_by_dropout(self):
        frames = [upright_frame(seed=i) for i in range(4)] + [np.zeros((0, 4))] * 5 + \
                 [lying_frame(seed=i) for i in range(4)]
        result = self.talk(frames)
        self.assertEqual(result['posture'], 'DESCENT_INSIDE_GAP')
        self.assertEqual(result['gaps'], [[4, 8]])

    def test_actor_always_down(self):
        result = self.talk([lying_frame(seed=i) for i in range(6)])
        self.assertEqual(result['posture'], 'LOW_WITHOUT_UPRIGHT')

    def test_actor_never_down(self):
        result = self.talk([upright_frame(seed=i) for i in range(6)])
        self.assertEqual(result['posture'], 'NEVER_LYING')

    def test_rising_is_not_a_descent(self):
        frames = [lying_frame(seed=i) for i in range(4)] + [upright_frame(seed=i) for i in range(4)]
        self.assertEqual(self.talk(frames)['posture'], 'LIES_THEN_UPRIGHT')

    def test_no_usable_frame(self):
        raw = stream([np.zeros((0, 4))] * 3)
        self.assertEqual(analyse_clip(raw, record_for(raw))['posture'], 'NO_VALID_FRAME')

    def test_ledger_inclinations_skip_short_frames(self):
        record = {'per_frame': [{'n': 100, 'shape': {'axis': [0.0, 0.0, 1.0]}},
                                {'n': 6, 'shape': {'axis': [1.0, 0.0, 0.0]}},
                                {'n': 0, 'shape': None}]}
        self.assertEqual(len(clip_inclinations(record)), 1)


if __name__ == '__main__':
    unittest.main()