"""Regression cases for the dataset admission gate."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from fall_dataset_gate import read_manifest, screen_clip, screen_directory


def upright(count=200, height=1.7, seed=0):
    rng = np.random.default_rng(seed)
    z = np.linspace(0.0, height, count)
    return np.stack([rng.normal(0, .05, count), rng.normal(0, .05, count), z,
                     np.zeros(count)], axis=1)


def lying(count=200, length=1.7, seed=1):
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, length, count)
    return np.stack([x, rng.normal(0, .05, count), rng.normal(0, .05, count),
                     np.zeros(count)], axis=1)


def tilted(degrees, count=200, height=1.7, seed=7):
    """Body sampled mid-descent: the long axis leans by `degrees` from +z."""
    rng = np.random.default_rng(seed)
    length = np.linspace(0.0, height, count)
    radians = np.radians(degrees)
    x = length * np.sin(radians) + rng.normal(0, .03, count)
    z = length * np.cos(radians) + rng.normal(0, .03, count)
    return np.stack([x, rng.normal(0, .03, count), z, np.zeros(count)], axis=1)


def two_actors(count=200, height=1.65, gap=1.40, seed=2):
    """Two standing bodies side by side: wide axis, still full height."""
    left, right = upright(count // 2, height, seed), upright(count // 2, height, seed + 1)
    right = right.copy()
    right[:, 0] += gap
    return np.concatenate([left, right])


def clip(frames, hz=10.0):
    blocks = [np.asarray(f, dtype=np.float32) for f in frames]
    offsets = np.concatenate([[0], np.cumsum([len(b) for b in blocks])]).astype(np.int32)
    stamps = np.arange(len(blocks), dtype=np.float64) / hz
    return np.concatenate(blocks), offsets, stamps


class ScreenClipTest(unittest.TestCase):
    def screen(self, frames, **kwargs):
        return screen_clip(*clip(frames), **kwargs)

    def test_upright_then_floor_is_admitted(self):
        result = self.screen([upright(seed=i) for i in range(4)] +
                             [tilted(45, seed=i) for i in range(2)] +
                             [lying(seed=i) for i in range(4)])
        self.assertEqual(result['verdict'], 'OK')
        self.assertEqual(result['metrics']['descent_frames'], 2)
        self.assertGreater(result['metrics']['transition_s'], 0.0)

    def test_floor_only_is_rejected(self):
        result = self.screen([lying(seed=i) for i in range(8)])
        self.assertEqual(result['verdict'], 'NEVER_UPRIGHT')

    def test_upright_only_is_rejected(self):
        result = self.screen([upright(seed=i) for i in range(8)])
        self.assertEqual(result['verdict'], 'NEVER_LOW')

    def test_transition_across_dropout_is_rejected(self):
        frames = [upright(seed=i) for i in range(4)] + [np.zeros((0, 4), np.float32)] * 3 + \
                 [lying(seed=i) for i in range(4)]
        result = self.screen(frames)
        self.assertEqual(result['verdict'], 'EVENT_IN_GAP')
        self.assertEqual(result['metrics']['blocking_frames'], [4, 5, 6])

    def test_empty_clip(self):
        self.assertEqual(self.screen([np.zeros((0, 4), np.float32)] * 3)['verdict'],
                         'NO_VALID_FRAME')

    def test_descent_sampled_by_adjacent_frames_only(self):
        result = self.screen([upright(seed=i) for i in range(4)] +
                             [lying(seed=i) for i in range(4)])
        self.assertEqual(result['verdict'], 'TOO_SHORT')
        self.assertEqual(result['metrics']['descent_frames'], 0)

    def test_two_actor_crop_is_not_floor(self):
        # One actor, then two standing side by side: wide axis but full height.
        frames = [upright(seed=i) for i in range(3)] + [two_actors(seed=i) for i in range(5)]
        result = self.screen(frames)
        self.assertEqual(result['verdict'], 'NEVER_LOW')
        self.assertIn('two actors', result['reasons'][0])

    def test_two_actor_clip_without_upright(self):
        result = self.screen([two_actors(seed=i) for i in range(6)])
        self.assertEqual(result['verdict'], 'NEVER_UPRIGHT')

    def test_floor_then_standing_is_not_a_fall(self):
        frames = [lying(seed=i) for i in range(4)] + [upright(seed=i) for i in range(4)]
        self.assertEqual(self.screen(frames)['verdict'], 'NEVER_LOW')

    def test_timestamp_gap_is_not_bridged(self):
        points, offsets, stamps = clip([upright(), tilted(45), lying()])
        stamps[1:] += 2
        self.assertEqual(screen_clip(points, offsets, stamps)['verdict'], 'EVENT_IN_GAP')

    def test_sparse_adjacent_endpoints_never_prove_descent(self):
        points, offsets, stamps = clip([upright(), lying()], hz=1.)
        self.assertEqual(screen_clip(points, offsets, stamps, max_gap_s=2.)['verdict'], 'TOO_SHORT')

    def test_later_complete_event_after_initial_floor(self):
        self.assertEqual(self.screen([lying(), upright(), tilted(45), lying()])['verdict'], 'OK')

    def test_later_complete_event_after_broken_event(self):
        frames = [upright(), np.empty((0, 4)), lying(), upright(), tilted(45), lying()]
        self.assertEqual(self.screen(frames)['verdict'], 'OK')

    def test_invalid_clocks_and_layout_rejected(self):
        points, offsets, stamps = clip([upright(), tilted(45), lying()])
        for times in ([0., 0., 1.], [1., 0., 2.], [0., float('nan'), 2.]):
            with self.assertRaises(ValueError):
                screen_clip(points, offsets, times)
        with self.assertRaises(ValueError):
            screen_clip(points, offsets + 1, stamps)

    def test_nonfinite_frame_breaks_descent(self):
        bad = tilted(45)
        bad[0, 0] = np.nan
        self.assertEqual(self.screen([upright(), bad, lying()])['verdict'], 'EVENT_IN_GAP')


class ScreenDirectoryTest(unittest.TestCase):
    def test_writes_gate_json_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            clips = Path(tmp) / 'clips'
            clips.mkdir()
            for name, frames in (('a', [upright(seed=i) for i in range(3)] +
                                       [tilted(45, seed=i) for i in range(2)] +
                                       [lying(seed=i) for i in range(3)]),
                                 ('b', [lying(seed=i) for i in range(6)])):
                points, offsets, stamps = clip(frames)
                np.savez_compressed(clips / (name + '.npz'), points=points,
                                    frame_offsets=offsets, timestamps_bag=stamps)
            manifest_file = Path(tmp) / 'manifest.csv'
            manifest_file.write_text('clip,subject,label\na,S1,1\nb,S2,1\n', encoding='utf-8')
            out = Path(tmp) / 'gate'
            summary = screen_directory(clips, read_manifest(manifest_file), out)
            self.assertEqual(summary['clips'], 2)
            self.assertEqual(summary['verdicts']['OK'], 1)
            self.assertEqual(summary['verdicts']['NEVER_UPRIGHT'], 1)
            written = json.loads((out / 'GATE.json').read_text(encoding='utf-8'))
            self.assertEqual(written['rows'][0]['subject'], 'S1')

    def test_manifest_needs_clip_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'm.csv'
            path.write_text('name,subject\na,S1\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                read_manifest(path)


if __name__ == '__main__':
    unittest.main()
