from pathlib import Path
import json
import tempfile
import unittest

import numpy as np
import torch
from torch.nn import functional as F

from fall_mil_numpy import NumpyMIL
from fall_candidate_runtime import FallCandidateRuntime, file_sha256
from train_fall_mil import WindowScorer, export, consecutive_starts, sustained_logit, feature_mask
from lidar_numpy_runtime import summarize_ordered, frame_feature
from train_causal_fall import matrix


class FallMILTest(unittest.TestCase):
    def test_ordered_schema_matrix_and_stream_parity(self):
        rng = np.random.default_rng(42)
        clouds = [rng.normal(size=(30, 3)) + [0, 0, -i*.03] for i in range(35)]
        frames = np.array([frame_feature(p) for p in clouds])
        rows, spans = matrix({'s': frames}, [{'sequence': 's'}], feature_schema='sequence_ordered_xyz_v1')
        model = WindowScorer().eval()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export(model, np.zeros(114, np.float32), np.ones(114, np.float32), root/'m.npz')
            manifest = {'task': 'laseract_sequence_falling_vs_other', 'model_format': 'numpy_mil_v1',
                'feature_schema': 'sequence_ordered_xyz_v1', 'positive_class': 1, 'model': 'm.npz',
                'model_sha256': file_sha256(root/'m.npz'), 'window_frames': 30, 'minimum_frames': 10,
                'max_gap_s': .5, 'episode': {}}
            (root/'m.json').write_text(json.dumps(manifest), encoding='utf-8')
            runtime = FallCandidateRuntime(root/'m.json')
            expected = NumpyMIL(root/'m.npz').predict_proba(rows)[:, 1]
            got = []
            for i, points in enumerate(clouds):
                result = runtime.push(points, i*.1, 'a', 0, 'c')
                if i >= 9: got.append(result['fall_probability'])
            np.testing.assert_allclose(got, expected, atol=1e-6)
            result = runtime.push(clouds[0], 5., 'a', 0, 'c')
            self.assertEqual(result['state'], 'warming')
            self.assertEqual(result['cached_frames'], 1)
        self.assertEqual(spans[-1]['begin_index'], 5)
        # Relative centroids remove fixed translation, but ordered bins retain reversal.
        translated = frames.copy(); translated[:, 1:4] += 10
        np.testing.assert_allclose(summarize_ordered(frames), summarize_ordered(translated), atol=1e-6)
        self.assertFalse(np.allclose(summarize_ordered(frames), summarize_ordered(frames[::-1])))
        with self.assertRaises(ValueError): summarize_ordered(frames[:5])

    def test_motion_profile_folds_into_numpy_weights(self):
        mask = feature_mask('motion_only')
        self.assertEqual(int(mask.sum()), 63)
        self.assertFalse(mask[::19].any())
        torch.manual_seed(42)
        model = WindowScorer().eval()
        raw = np.random.default_rng(42).normal(size=(4, 114)).astype(np.float32)
        mean = (raw*mask).mean(0)
        scale = np.maximum((raw*mask).std(0), 1e-6)
        with torch.no_grad():
            expected = torch.sigmoid(model(torch.from_numpy((raw*mask-mean)/scale))).numpy()
            model.layers[0].weight.mul_(torch.from_numpy(mask))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'motion.npz'
            export(model, mean, scale, path)
            actual = NumpyMIL(path).predict_proba(raw)[:, 1]
            np.testing.assert_allclose(actual, expected, atol=1e-6)
        with self.assertRaises(ValueError): feature_mask('unknown')

    def test_sustained_pooling_rejects_spikes_and_gaps(self):
        spans = [{'end_index_exclusive': i} for i in [10, 11, 12, 20, 21, 22]]
        starts = consecutive_starts(spans)
        self.assertEqual(starts, [0, 3])
        logits = torch.tensor([9., -3., 8., 2., 4., 3.], requires_grad=True)
        pooled = sustained_logit(logits, starts)
        self.assertEqual(float(pooled.detach()), 2.)
        F.binary_cross_entropy_with_logits(pooled[None], torch.ones(1)).backward()
        self.assertLess(float(logits.grad[3]), 0.)
        self.assertEqual(float(logits.grad[0]), 0.)
        with self.assertRaises(ValueError): sustained_logit(logits, [])

    def test_bound_mil_runtime_and_overflow_clear_history(self):
        model = WindowScorer().eval()
        with torch.no_grad():
            for parameter in model.parameters(): parameter.zero_()
            model.layers[-1].bias.fill_(3.)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root/'model.npz'
            export(model, np.zeros(114, np.float32), np.ones(114, np.float32), path)
            manifest = root/'model.json'
            manifest.write_text(json.dumps({'task': 'laseract_sequence_falling_vs_other',
                'model_format': 'numpy_mil_v1', 'feature_schema': 'sequence_xyz_v1', 'positive_class': 1,
                'model': path.name, 'model_sha256': file_sha256(path), 'window_frames': 5,
                'minimum_frames': 5, 'max_gap_s': .5, 'episode': {}}), encoding='utf-8')
            runtime = FallCandidateRuntime(manifest)
            for i in range(7): result = runtime.push(np.zeros((12, 3)), i*.1, 'a', 0, 'c')
            self.assertIsNotNone(result['new_event'])
            self.assertFalse(result['confirmed_enabled'])
            result = runtime.push(np.full((12, 3), 1e200), .8, 'a', 0, 'c')
            self.assertEqual(result['state'], 'unknown')
            self.assertEqual(result['cached_frames'], 0)

    def test_bag_supervision_does_not_label_every_positive_window(self):
        logits = torch.tensor([-3., 2., -4.], requires_grad=True)
        loss = F.binary_cross_entropy_with_logits(logits.max()[None], torch.ones(1))
        loss.backward()
        self.assertEqual(float(logits.grad[0]), 0.)
        self.assertLess(float(logits.grad[1]), 0.)
        self.assertEqual(float(logits.grad[2]), 0.)

    def test_numpy_export_probabilities_and_invalid_input(self):
        torch.manual_seed(42)
        model = WindowScorer().eval()
        rng = np.random.default_rng(42)
        X = rng.normal(size=(200, 114)).astype(np.float32)
        mean = rng.normal(size=114).astype(np.float32)
        scale = rng.uniform(.1, 3, size=114).astype(np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'mil.npz'
            export(model, mean, scale, path)
            runtime = NumpyMIL(path)
            with torch.no_grad(): expected = torch.sigmoid(model(torch.from_numpy((X-mean)/scale))).numpy()
            np.testing.assert_allclose(runtime.predict_proba(X)[:, 1], expected, atol=1e-6, rtol=1e-6)
            for bad in [np.zeros((2, 113)), np.full((2, 114), np.inf), np.full((2, 114), 1e100)]:
                with self.assertRaises(ValueError): runtime.predict_proba(bad)
            with self.assertRaises(FileExistsError): export(model, mean, scale, path)


if __name__ == '__main__':
    unittest.main()
