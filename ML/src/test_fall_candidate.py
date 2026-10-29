import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from fall_candidate_runtime import FallCandidateRuntime, FallEpisodeLatch, file_sha256
from lidar_numpy_runtime import frame_feature, summarize


def fixture(root, probability=0.95, classes=(0, 1)):
    model = root/'forest.npz'
    np.savez(model, classes=np.asarray(classes), left=np.array([-1]), right=np.array([-1]),
             feature=np.array([-2]), threshold=np.array([-2.]), roots=np.array([0]),
             value=np.array([[1-probability, probability]]), n_features=np.asarray(114))
    manifest = {'task': 'synthetic_sequence_fall_vs_nonfall', 'feature_schema': 'sequence_xyz_v1',
                'positive_class': 1, 'model': model.name, 'model_sha256': file_sha256(model),
                'window_frames': 5, 'max_gap_s': 0.5,
                'episode': dict(high=0.8, low=0.2, positive_windows=3, release_windows=5)}
    path = root/'manifest.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    return path, manifest


class FallCandidateTest(unittest.TestCase):
    def test_latch_boundaries_duplicates_release_and_gaps(self):
        latch = FallEpisodeLatch()
        self.assertIsNone(latch.update(.8, 'a')['new_event'])
        self.assertIsNone(latch.update(.8, 'a')['new_event'])
        first = latch.update(.8, 'a')
        self.assertEqual(first['new_event']['kind'], 'ml_fall_candidate')
        self.assertFalse(first['new_event']['physically_verified'])
        for _ in range(10): self.assertIsNone(latch.update(.99, 'a')['new_event'])
        latch.gap()
        for _ in range(3): self.assertIsNone(latch.update(.99, 'a')['new_event'])
        for _ in range(4): self.assertEqual(latch.update(.2, 'a')['event_id'], first['event_id'])
        self.assertIsNone(latch.update(.2, 'a')['event_id'])
        for _ in range(2): self.assertIsNone(latch.update(.8, 'a')['new_event'])
        second = latch.update(.8, 'a')
        self.assertNotEqual(first['event_id'], second['event_id'])
        self.assertIsNone(latch.update(.9, 'b')['event_id'])
        latch.update(.9, 'b')
        latch.gap()
        self.assertIsNone(latch.update(.9, 'b')['event_id'])
        for bad in [float('nan'), float('inf'), -0.1, 1.1]:
            with self.assertRaises(ValueError): latch.update(bad, 'b')

    def test_runtime_history_warmup_and_no_confirmed(self):
        cloud = np.zeros((12, 3))
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = fixture(Path(tmp))
            runtime = FallCandidateRuntime(path)
            def push(index, **kwargs):
                return runtime.push(cloud, index*.1, ('sid', 1), (0, 0, 0), ('sha', 1), **kwargs)
            result = [push(i) for i in range(7)]
            self.assertTrue(all(r['state'] == 'warming' for r in result[:4]))
            self.assertIsNotNone(result[-1]['new_event'])
            self.assertFalse(result[-1]['confirmed_enabled'])
            self.assertEqual(result[-1]['validity'], 'UNVERIFIED_TARGET_DOMAIN')
            self.assertAlmostEqual(result[-1]['new_event']['source_stamp_s'], .6)
            event = result[-1]['event_id']
            self.assertEqual(push(7, observed=False)['state'], 'unknown')
            after_gap = [push(i) for i in range(8, 15)]
            self.assertTrue(all(r['new_event'] is None for r in after_gap))
            self.assertEqual(after_gap[-1]['event_id'], event)
            self.assertEqual(push(14)['reason'], 'nonincreasing_time')
            self.assertEqual(len(runtime.cache.frames), 0)
            for i in range(15, 22): r = push(i)
            self.assertEqual(r['event_id'], event)
            # Identity/generation/calibration reset episodes, not only feature history.
            for binding in [(('sid', 2), (0, 0, 0), ('sha', 1)),
                            (('sid', 2), (1, 0, 0), ('sha', 1)),
                            (('sid', 2), (1, 0, 0), ('other', 2))]:
                r = runtime.push(cloud, 3., *binding)
                self.assertIsNone(r['event_id'])
                self.assertEqual(r['cached_frames'], 1)

    def test_invalid_observation_clears_votes_and_features(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = fixture(Path(tmp))
            runtime = FallCandidateRuntime(path)
            cloud = np.zeros((12, 3))
            for i in range(6): runtime.push(cloud, i*.1, 'a', 0, 'c')
            self.assertEqual(runtime.latch.positive_count, 2)
            for bad in [np.full((12, 3), np.nan), np.zeros((9, 3)), np.zeros((12, 4))]:
                result = runtime.push(bad, .7, 'a', 0, 'c')
                self.assertEqual(result['state'], 'unknown')
                self.assertEqual(result['cached_frames'], 0)
                self.assertEqual(runtime.latch.positive_count, 0)
            for bad in [float('nan'), float('inf')]:
                self.assertEqual(runtime.push(cloud, bad, 'a', 0, 'c')['state'], 'unknown')
            self.assertEqual(runtime.push(cloud.astype(complex), .8, 'a', 0, 'c')['reason'], 'invalid_points')
            self.assertEqual(runtime.push(cloud, .8, 'a', 0, 'c', observed='locked')['reason'], 'invalid_observed_flag')
            self.assertEqual(runtime.push(cloud, 1., ('sid', None), 0, 'c')['reason'], 'invalid_binding')
            for i in range(6): runtime.push(cloud, 1+i*.1, 'a', 0, 'c')
            self.assertEqual(runtime.push(cloud, 5., 'a', 0, 'c')['cached_frames'], 1)
            self.assertEqual(runtime.latch.positive_count, 0)

    def test_model_binding_and_action_ids_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, manifest = fixture(root, classes=(1, 2))
            with self.assertRaises(ValueError): FallCandidateRuntime(path)
            manifest['model_sha256'] = 'wrong'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaises(ValueError): FallCandidateRuntime(path)
            manifest['task'] = 'mmfi_action_classification'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaises(ValueError): FallCandidateRuntime(path)

    def test_expanding_context_is_causal_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, manifest = fixture(Path(tmp))
            manifest.update(window_frames=8, minimum_frames=5)
            path.write_text(json.dumps(manifest), encoding='utf-8')
            runtime = FallCandidateRuntime(path)
            rng = np.random.default_rng(42)
            clouds = [rng.normal(size=(12, 3)) for _ in range(12)]
            saved = None
            for i, cloud in enumerate(clouds):
                result = runtime.push(cloud, i*.1, 'a', 1, 'c')
                if i < 4:
                    self.assertIsNone(result['fall_probability'])
                else:
                    self.assertIsNotNone(result['fall_probability'])
                    np.testing.assert_array_equal(summarize(runtime.cache.frames),
                        summarize([frame_feature(p) for p in clouds[max(0, i-7):i+1]]))
                if i == 4: saved = result.copy()
                self.assertLessEqual(len(runtime.cache.frames), 8)
            other = FallCandidateRuntime(path)
            for i, cloud in enumerate(clouds[:5]): other_result = other.push(cloud, i*.1, 'a', 1, 'c')
            self.assertEqual(saved, other_result)

    def test_event_ids_bind_model_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, manifest = fixture(root)
            first = FallCandidateRuntime(path)
            manifest['episode']['high'] = .7
            changed = root/'changed.json'
            changed.write_text(json.dumps(manifest), encoding='utf-8')
            second = FallCandidateRuntime(changed)
            for i in range(7):
                a = first.push(np.zeros((12, 3)), i*.1, 'a', 0, 'c')
                b = second.push(np.zeros((12, 3)), i*.1, 'a', 0, 'c')
            self.assertEqual(a['model_sha256'], b['model_sha256'])
            self.assertNotEqual(a['event_id'], b['event_id'])


if __name__ == '__main__':
    unittest.main()
