"""Measured composition regressions; synthetic geometry, no human GT claims."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_support_composition as fixtures
from test_support_composition import slab
from core.support_composition import evaluate, rigid_fit, support_cells


class CompositionRegressions(unittest.TestCase):
    def test_icp_translation_does_not_oscillate_with_iteration_parity(self):
        y, z = np.meshgrid(np.linspace(.02, .3, 8), np.linspace(.1, 1.7, 12))
        source = np.column_stack((np.full(y.size, 2.), y.ravel(), z.ravel()))
        target = source + [.2, 0., 0.]
        for iterations in (1, 2, 11, 12):
            with self.subTest(iterations=iterations):
                fit = rigid_fit(source, target, iterations=iterations)
                self.assertLess(fit['rms_m'], 1e-10)
                np.testing.assert_allclose(fit['rotation'], np.eye(3), atol=1e-10)
                np.testing.assert_allclose(fit['translation'], [.2, 0., 0.], atol=1e-10)

    def test_icp_returns_cumulative_rotation_and_translation(self):
        source = np.random.default_rng(831).uniform(-1., 1., (80, 3)) * [.7, .4, 1.2]
        z, y = np.deg2rad([12., -8.])
        rz = np.array([[np.cos(z), -np.sin(z), 0.],
                       [np.sin(z), np.cos(z), 0.], [0., 0., 1.]])
        ry = np.array([[np.cos(y), 0., np.sin(y)], [0., 1., 0.],
                       [-np.sin(y), 0., np.cos(y)]])
        rotation = rz @ ry
        translation = np.array([.04, -.03, .07])
        target = source @ rotation.T + translation
        fit = rigid_fit(source, target)
        self.assertLess(fit['rms_m'], 1e-10)
        np.testing.assert_allclose(fit['rotation'], rotation, atol=1e-10)
        np.testing.assert_allclose(fit['translation'], translation, atol=1e-10)
        shuffled = np.random.default_rng(22).permutation(len(source))
        self.assertEqual(fit, rigid_fit(source[shuffled], target[::-1]))

    def test_gap_is_a_hard_gate_even_when_every_fragment_has_support(self):
        for gap, accepted in ((.25, True), (.250001, False), (.29, False)):
            with self.subTest(gap=gap):
                parts = [slab(2.), slab(2. + gap)]
                prior = np.vstack(parts)
                decision = evaluate(prior, support_cells(prior),
                    [dict(points=p, cells=support_cells(p)) for p in parts])
                self.assertEqual(decision['accepted'], accepted)
                self.assertEqual(decision['metrics']['target_coverage'], 1.)
                self.assertEqual(decision['metrics']['new_fraction'], 0.)
                if not accepted:
                    self.assertEqual(decision['reason'], 'fragment_gap_exceeded')
                    self.assertFalse(decision['metrics']['fragment_gap_connected'])

    def test_connected_chain_can_span_more_than_one_gap(self):
        parts = [slab(x) for x in (2., 2.2, 2.4)]
        prior = np.vstack(parts)
        decision = evaluate(prior, support_cells(prior),
            [dict(points=p, cells=support_cells(p)) for p in parts])
        self.assertTrue(decision['accepted'])
        self.assertTrue(decision['metrics']['fragment_gap_connected'])

    def test_disconnected_anchors_keep_ordinary_ambiguity(self):
        helper = fixtures.AcquisitionComposition()
        acquisition = helper.make()
        left, right = slab(2.), slab(2.2)
        helper.lock_body(acquisition, np.vstack((left, right)))
        state, diagnostics, observed = helper.split_frame(
            acquisition, left, right + [.09, 0., 0.], .8, 8)
        self.assertFalse(diagnostics['composition']['accepted'])
        self.assertEqual(diagnostics['composition']['reason'], 'fragment_gap_exceeded')
        self.assertEqual(state['track_status'], 'ambiguous')
        self.assertIsNone(observed)

    def test_large_predecessor_is_invariant_before_first_sampling_limit(self):
        low = slab(2., z=(.1, .9), n=800)
        high = slab(2., z=(.91, 1.7), n=800)
        prior = np.vstack((low, high))
        indices = np.linspace(0, len(prior) - 1, 768).astype(np.int64)
        remaining = np.setdiff1d(np.arange(len(prior)), indices)
        samples, outputs = [], []
        helper = fixtures.AcquisitionComposition()
        for selected in (np.arange(768), np.arange(800, 1568)):
            order = np.empty(len(prior), dtype=np.int64)
            order[indices] = selected
            order[remaining] = np.setdiff1d(np.arange(len(prior)), selected)
            acquisition = helper.make()
            helper.lock_body(acquisition, prior[order])
            samples.append(acquisition._last_target_support['points'].copy())
            state, diagnostics, observed = helper.split_frame(
                acquisition, low, high + [.18, 0., 0.], .8, 8)
            outputs.append((state, diagnostics['composition'], observed))
        self.assertEqual(samples[0].shape, (768, 3))
        np.testing.assert_array_equal(samples[0], samples[1])
        self.assertEqual(outputs[0], outputs[1])


if __name__ == '__main__':
    unittest.main()
