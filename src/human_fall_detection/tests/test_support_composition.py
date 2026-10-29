"""Supported fragment composition contracts: geometric software checks only.

Every input here is synthetic geometry. Nothing in this file claims a human
classification, a point-level ground truth or a fall detection rate.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.candidate_history import CandidateHistory
from core.lidar_candidates import rebuild_candidate
from core.support_composition import (DEFAULT_SETTINGS, connectivity, evaluate,
                                      resolve_settings, rigid_fit, support_cells,
                                      _spatial_blocks, _verified_gap)
from core.target_acquisition import TargetAcquisition
from core.tracking import TargetTracker


GROUND = dict(status='valid', frame='innolidar', normal=[0., 0., 1.], offset_m=0.)


def body(z_low=0.10, z_high=1.70, n=48):
    return np.column_stack((np.full(n, 2.0), np.linspace(.02, .30, n),
                            np.linspace(z_low, z_high, n)))


def slab(x, y=0.16, z=(0.10, 1.70), n=48):
    return np.column_stack((np.full(n, x), np.full(n, y),
                            np.linspace(z[0], z[1], n)))


def rounded(x=2.0, y=0.16, radius=0.12, z=(0.10, 1.70), n=48):
    """Cylindrical shell: a shift inside a cell never removes all support."""
    theta = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    return np.column_stack((x + radius * np.cos(theta), y + radius * np.sin(theta),
                            np.linspace(z[0], z[1], n)))


def item(cid, points, rows, height=(.1, .2, .9, 1.6, 1.7)):
    block = dict(min=height[0], p10=height[1], median=height[2], p90=height[3],
                 max=height[4])
    return dict(candidate_id=cid, center_source_m=np.median(points, axis=0).tolist(),
                point_count=len(points), evidence_indices=list(rows),
                semantic='unknown', ground_relative_available=True, height_m=block,
                horizontal_extent_m=dict(max=.3))


def rebuild(points):
    return lambda rows: rebuild_candidate(points, np.asarray(rows, dtype=np.int64),
                                          ground=GROUND)


class CompositionScorer(unittest.TestCase):
    def setUp(self):
        self.prior = body()
        self.prior_cells = support_cells(self.prior)

    def fragments(self, *sets):
        return [dict(candidate_id='c%d' % index, points=points,
                     cells=support_cells(points))
                for index, points in enumerate(sets)]

    def test_spatial_gap_matches_full_distance_for_rotations_and_row_orders(self):
        rng = np.random.RandomState(81)
        for count in (129, 257, 600):
            a = rng.normal(size=(count, 3))
            b = rng.normal(size=(count + 13, 3)) + [3., 0., 0.]
            # Degenerate/repeated rows and coordinate permutations exercise box
            # boundaries as well as ordinary volume data.
            b[:20] = b[0]
            for axes in ((0, 1, 2), (2, 0, 1)):
                x, y = a[:, axes], b[:, axes]
                delta = x[:, None, :] - y[None, :, :]
                exact = float(np.sqrt(np.einsum('ijk,ijk->ij', delta, delta).min()))
                upper = float(np.linalg.norm(x[0] - y[0]))
                self.assertEqual(_verified_gap(x, y, upper), exact)
                self.assertEqual(_verified_gap(x[rng.permutation(len(x))],
                                               y[rng.permutation(len(y))], upper), exact)

    def test_spatial_partition_keeps_all_rows_without_mutating_input(self):
        rng = np.random.RandomState(82)
        points = rng.normal(size=(1000, 3))
        points[100:200] = points[0]
        original = points.copy()
        parts = _spatial_blocks(points)
        self.assertLessEqual(max(len(p) for p in parts), 64)
        ordered = lambda p: p[np.lexsort((p[:, 2], p[:, 1], p[:, 0]))]
        np.testing.assert_array_equal(ordered(np.vstack(parts)), ordered(points))
        np.testing.assert_array_equal(points, original)
        repeated_a = np.tile([2., 0., .5], (1000, 1))
        repeated_b = np.tile([2., 0., .9], (1000, 1))
        self.assertEqual(_verified_gap(repeated_a, repeated_b, .4), .4)

    def test_spatial_gap_keeps_inclusive_gate_and_true_separation(self):
        a = np.column_stack((np.linspace(1., 2., 300), np.zeros(300), np.zeros(300)))
        for gap in (.25, np.nextafter(.25, np.inf), .4):
            b = a + [0., 0., gap]
            graph = connectivity(self.fragments(a, b), .25)
            self.assertEqual(graph['connected'], gap <= .25)
            self.assertEqual(graph['gaps'][0][1], gap)

    def test_unsampled_measured_bridge_is_checked_before_rejecting_gap(self):
        # Canonical sample misses the lone near edge at interior sorted row 1.
        a = np.column_stack((np.full(1000, 2.), np.linspace(0., 1., 1000),
                             np.full(1000, .5)))
        b = a + [0., 0., .4]
        b[1, 2] = .70
        fragments = self.fragments(a, b)
        graph = connectivity(fragments, .25)
        self.assertTrue(graph['connected'])
        self.assertAlmostEqual(graph['gaps'][0][1], .2)
        prior = np.vstack((a, b))
        decision = evaluate(prior, support_cells(prior), fragments)
        self.assertTrue(decision['accepted'])
        for seed in range(3):
            rng = np.random.RandomState(seed)
            shuffled = self.fragments(a[rng.permutation(len(a))], b[rng.permutation(len(b))])
            self.assertEqual(connectivity(shuffled, .25), graph)
            self.assertEqual(evaluate(prior, support_cells(prior), shuffled), decision)

    def test_full_point_gap_and_nearby_competition_still_refuse(self):
        a = np.column_stack((np.full(1000, 2.), np.linspace(0., 1., 1000),
                             np.full(1000, .5)))
        b = a + [0., 0., .4]
        prior = np.vstack((a,b))
        decision = evaluate(prior, support_cells(prior), self.fragments(a,b))
        self.assertFalse(decision['accepted'])
        self.assertEqual(decision['reason'], 'fragment_gap_exceeded')
        self.assertAlmostEqual(decision['metrics']['fragment_gap_m'], .4)
        b[1,2] = .70
        prior = np.vstack((a,b))
        decision = evaluate(prior, support_cells(prior), self.fragments(a,b),
                            competitor_positions=[[2.,.5,.7]], gate_m=.8)
        self.assertEqual(decision['reason'], 'competing_support')

    def test_single_body_split_is_accepted_with_explicit_metrics(self):
        low, high = self.prior[:24], self.prior[24:]
        decision = evaluate(self.prior, self.prior_cells, self.fragments(low, high))
        self.assertTrue(decision['accepted'])
        self.assertEqual(decision['reason'], 'supported_fragment_composition')
        metrics = decision['metrics']
        self.assertEqual(metrics['fragment_count'], 2)
        self.assertGreaterEqual(metrics['anchor_support'], 0.05)
        self.assertGreaterEqual(metrics['target_coverage'], 0.20)
        self.assertLessEqual(metrics['new_fraction'], 0.80)
        self.assertLessEqual(metrics['rigid_rms_m'], 0.16)
        self.assertTrue(metrics['fragment_gap_connected'])
        json.dumps(decision, allow_nan=False)

    def test_static_partition_adds_no_new_support(self):
        low, high = self.prior[:24], self.prior[24:]
        decision = evaluate(self.prior, self.prior_cells, self.fragments(low, high))
        self.assertEqual(decision['metrics']['target_coverage'], 1.0)
        self.assertEqual(decision['metrics']['new_fraction'], 0.0)
        # The union is exactly the already locked support: nothing new is absorbed.
        self.assertTrue(decision['accepted'])

    def test_small_old_support_with_large_external_blob_is_refused(self):
        small = self.prior[:6]
        external = self.prior + np.array([2.0, 0.0, 0.0])
        decision = evaluate(self.prior, self.prior_cells,
                            self.fragments(small, external))
        self.assertFalse(decision['accepted'])
        self.assertIn(decision['reason'],
                      ('target_coverage_low', 'unexplained_new_support'))
        graph = connectivity(self.fragments(small, external), 0.25)
        self.assertFalse(graph['connected'])
        self.assertGreater(graph['largest_gap_m'], 1.0)

    def test_no_fragment_carries_the_target_support(self):
        other = self.prior + np.array([1.5, 0.0, 0.0])
        decision = evaluate(self.prior, self.prior_cells,
                            self.fragments(other[:24], other[24:]))
        self.assertFalse(decision['accepted'])
        self.assertEqual(decision['reason'], 'no_supported_fragment')

    def test_two_objects_moving_apart_are_not_one_rigid_body(self):
        low, high = self.prior[:24], self.prior[24:]
        moved = high + np.array([0.4, 0.0, 0.0])
        graph = connectivity(self.fragments(low, moved), 0.25)
        self.assertFalse(graph['connected'])
        decision = evaluate(self.prior, self.prior_cells, self.fragments(low, moved))
        # The anchor requirement alone cannot tell them apart; the caller drops
        # the unsupported, disconnected fragment before scoring. The metric is
        # explicit so the rejection is traceable.
        self.assertEqual(decision['metrics']['fragment_support'][1], 0.0)
        self.assertFalse(decision['metrics']['fragment_gap_connected'])

    def test_body_sized_envelope_and_rigid_residual_are_enforced(self):
        low, high = self.prior[:24], self.prior[24:]
        decision = evaluate(self.prior, self.prior_cells, self.fragments(low, high),
                            settings=dict(max_union_extent_m=0.2))
        self.assertFalse(decision['accepted'])
        self.assertEqual(decision['reason'], 'union_envelope_exceeded')
        with self.assertRaises(ValueError):
            evaluate(self.prior, self.prior_cells, self.fragments(low, high),
                     settings=dict(max_union_extent_m=0.0))
        random = np.random.default_rng(7)
        scattered = random.uniform(-3.0, 3.0, (96, 3))
        decision = evaluate(self.prior, self.prior_cells,
                            self.fragments(scattered[:48], scattered[48:]))
        self.assertFalse(decision['accepted'])
        self.assertIn(decision['reason'],
                      ('no_supported_fragment', 'target_coverage_low',
                       'union_envelope_exceeded', 'rigid_motion_inconsistent',
                       'unexplained_new_support'))

    def test_competing_candidate_near_the_composition_refuses_it(self):
        low, high = self.prior[:24], self.prior[24:]
        centre = np.median(np.vstack((low, high)), axis=0)
        decision = evaluate(self.prior, self.prior_cells, self.fragments(low, high),
                            competitor_positions=[centre + np.array([0.2, 0.0, 0.0])],
                            gate_m=0.8)
        self.assertFalse(decision['accepted'])
        self.assertEqual(decision['reason'], 'competing_support')
        far = evaluate(self.prior, self.prior_cells, self.fragments(low, high),
                       competitor_positions=[centre + np.array([3.0, 0.0, 0.0])],
                       gate_m=0.8)
        self.assertTrue(far['accepted'])

    def test_prediction_residual_is_bounded_when_supplied(self):
        low, high = self.prior[:24], self.prior[24:]
        centre = np.median(np.vstack((low, high)), axis=0)
        decision = evaluate(self.prior, self.prior_cells, self.fragments(low, high),
                            predicted_position=centre + np.array([1.1, 0.0, 0.0]),
                            gate_m=0.8)
        self.assertFalse(decision['accepted'])
        self.assertEqual(decision['reason'], 'prediction_residual_exceeded')

    def test_disabled_and_invalid_settings_are_explicit(self):
        low, high = self.prior[:24], self.prior[24:]
        decision = evaluate(self.prior, self.prior_cells, self.fragments(low, high),
                            settings=dict(enabled=False))
        self.assertFalse(decision['accepted'])
        self.assertEqual(decision['reason'], 'disabled')
        with self.assertRaises(ValueError):
            resolve_settings(dict(unknown_key=1))
        with self.assertRaises(ValueError):
            resolve_settings(dict(min_target_coverage=2.0))
        with self.assertRaises(ValueError):
            resolve_settings(dict(enabled='yes'))
        with self.assertRaises(ValueError):
            evaluate(self.prior, self.prior_cells, self.fragments(low),
                     settings=dict(icp_iterations=0))
        self.assertEqual(evaluate(self.prior, self.prior_cells,
                                  self.fragments(low))['reason'], 'single_fragment')
        self.assertEqual(DEFAULT_SETTINGS['cell_m'], 0.1)

    def test_scoring_is_bounded_and_deterministic(self):
        random = np.random.default_rng(11)
        prior = random.uniform(1.5, 2.5, (400, 3))
        union = np.vstack((prior[:200] + 0.02, prior[200:] + 0.02))
        first = rigid_fit(prior, union)
        second = rigid_fit(prior, union)
        self.assertEqual(first, second)
        self.assertEqual(first['source_samples'], DEFAULT_SETTINGS['icp_samples'])
        self.assertEqual(first['target_samples'], DEFAULT_SETTINGS['icp_samples'])
        self.assertLess(first['rms_m'], 0.16)

    def test_cells_are_order_independent_and_bounded(self):
        random = np.random.default_rng(13)
        points = random.uniform(0.0, 1.0, (200, 3))
        shuffled = points.copy()
        np.random.default_rng(17).shuffle(shuffled)
        self.assertEqual(support_cells(points), support_cells(shuffled))
        limited = support_cells(points, 0.1, 10)
        self.assertEqual(len(limited), 10)
        self.assertEqual(limited, support_cells(shuffled, 0.1, 10))

    def test_decision_is_independent_of_row_order(self):
        low, high = self.prior[:24], self.prior[24:]
        fragments = self.fragments(low, high)
        first = evaluate(self.prior, self.prior_cells, fragments)
        shuffled_prior = self.prior.copy()
        np.random.default_rng(23).shuffle(shuffled_prior)
        shuffled_fragments = []
        for fragment in fragments:
            points = fragment['points'].copy()
            np.random.default_rng(29).shuffle(points)
            shuffled_fragments.append(dict(candidate_id=fragment['candidate_id'],
                                           points=points,
                                           cells=support_cells(points)))
        second = evaluate(shuffled_prior, support_cells(shuffled_prior),
                          shuffled_fragments)
        self.assertEqual(first, second)


class AcquisitionComposition(unittest.TestCase):
    def make(self, **kwargs):
        settings = {'human_entry_gate': False}
        settings.update(kwargs)
        return TargetAcquisition(TargetTracker('synthetic'), settings)

    def lock_body(self, acquisition, points, frames=8, x=2.0):
        state = None
        for index in range(frames):
            moved = points + np.array([x - 2.0, 0.0, 0.0])
            stage = self.lock_points(acquisition, moved, index * 0.1, index)
            state = stage
        self.assertEqual(state[0]['track_status'], 'locked')
        return state

    @staticmethod
    def lock_points(acquisition, points, stamp, seq):
        return acquisition.step([item('body', points, range(len(points)))], 0, stamp,
                                points=points, frame_seq=seq, ground=GROUND)

    def split_frame(self, acquisition, lower, upper, stamp, seq):
        points = np.vstack((lower, upper))
        candidates = [item('lower', lower, range(len(lower))),
                      item('upper', upper, range(len(lower), len(points)))]
        return acquisition.step(candidates, 0, stamp, points=points, frame_seq=seq,
                                ground=GROUND, rebuild=rebuild(points))

    def test_one_locked_target_is_supported_by_two_real_fragments(self):
        acquisition = self.make()
        whole = body()
        self.lock_body(acquisition, whole)
        history_id = acquisition.history.ledger[0]['history_id']
        lower, upper = whole[:24], whole[24:]
        state, acquisition_state, observed = self.split_frame(
            acquisition, lower, upper, 0.8, 8)
        self.assertEqual(state['track_status'], 'locked')
        self.assertFalse(state['position_predicted'])
        self.assertIsNotNone(observed)
        self.assertEqual(observed['point_count'], len(whole))
        self.assertEqual(state['candidate_id'], 'g0000')
        # Identity continues through the same history record, committed once.
        self.assertEqual(acquisition.history.ledger[0]['history_id'], history_id)
        self.assertEqual([record['candidate_id'] for record in acquisition.history.ledger],
                         ['g0000'])
        self.assertEqual(acquisition.history.ledger[0]['observed_frames'], 9)
        composition = acquisition_state['composition']
        self.assertTrue(composition['accepted'])
        self.assertEqual(composition['grouped'], ['lower', 'upper'])
        self.assertEqual(composition['union_point_count'], len(whole))
        # The original candidate list is still available for traceability.
        snapshot_rows = sorted(observed['evidence_indices'])
        self.assertEqual(snapshot_rows, list(range(len(whole))))
        self.assertEqual(acquisition_state['rejected']['lower'],
                         'composed_into_target_support')
        self.assertIsNone(acquisition_state['rejected']['g0000'])
        # Downstream consumers get exactly the composed measured rows.
        self.assertEqual(sorted(observed['source_rows']), list(range(len(whole))))

    def test_independent_far_cluster_is_never_absorbed(self):
        acquisition = self.make()
        whole = body()
        self.lock_body(acquisition, whole)
        other = slab(6.0, 3.0, (0.1, 1.7))
        lower, upper = whole[:24], whole[24:]
        points = np.vstack((lower, upper, other))
        candidates = [item('lower', lower, range(24)),
                      item('upper', upper, range(24, 48)),
                      item('other', other, range(48, 48 + len(other)))]
        state, acquisition_state, observed = acquisition.step(
            candidates, 0, 0.8, points=points, frame_seq=8, ground=GROUND,
            rebuild=rebuild(points))
        self.assertEqual(state['track_status'], 'locked')
        self.assertEqual(observed['point_count'], len(whole))
        self.assertFalse(set(observed['evidence_indices']) & set(range(48, len(points))))
        self.assertEqual(acquisition_state['composition']['grouped'], ['lower', 'upper'])
        self.assertEqual(acquisition_state['composition']['competitors'], 1)

    def test_two_objects_that_separate_do_not_become_one_measurement(self):
        acquisition = self.make()
        left, right = slab(2.0, 0.0), slab(2.2, 0.0)
        joined = np.vstack((left, right))
        for index in range(8):
            points = joined
            state = acquisition.step([item('joined', points, range(len(points)))], 0,
                                     index * 0.1, points=points, frame_seq=index,
                                     ground=GROUND, rebuild=rebuild(points))
        self.assertEqual(state[0]['track_status'], 'locked')
        moved = right + np.array([0.4, 0.0, 0.0])
        points = np.vstack((left, moved))
        candidates = [item('left', left, range(len(left))),
                      item('moved', moved, range(len(left), len(points)))]
        state, acquisition_state, observed = acquisition.step(
            candidates, 0, 0.8, points=points, frame_seq=8, ground=GROUND,
            rebuild=rebuild(points))
        composition = acquisition_state['composition']
        self.assertFalse(composition['accepted'])
        self.assertEqual(composition['grouped'], ['left'])
        # The moved object is never part of the target's measured rows. The
        # tracker may keep the one uniquely supported cluster; it may not take a
        # composed union of two independently moving objects.
        if observed is not None:
            self.assertNotEqual(observed['candidate_id'], 'g0000')
            self.assertFalse(set(observed['evidence_indices'])
                             & set(range(len(left), len(points))))

    def test_foreign_history_with_own_support_is_competing_not_member(self):
        acquisition = self.make(change_gate=True)
        whole = rounded()
        foreign = rounded(x=3.6, y=-0.30, z=(0.20, 1.60))
        state = None
        for index in range(14):
            moved = whole + np.array([0.05 * index, 0.0, 0.0])
            points = np.vstack((moved, foreign))
            state, acquisition_state, observed = acquisition.step(
                [item('body', moved, range(len(whole))),
                 item('foreign', foreign, range(len(whole), len(points)))],
                0, index * 0.1, points=points, frame_seq=index, ground=GROUND,
                rebuild=rebuild(points))
        self.assertEqual(state['track_status'], 'locked')
        self.assertEqual(state['candidate_id'], 'body')
        moved = whole + np.array([0.70, 0.0, 0.0])
        lower, upper = moved[:24], moved[24:]
        points = np.vstack((lower, upper, foreign))
        candidates = [item('lower', lower, range(24)),
                      item('upper', upper, range(24, 48)),
                      item('foreign', foreign, range(48, 48 + len(foreign)))]
        state, acquisition_state, observed = acquisition.step(
            candidates, 0, 1.4, points=points, frame_seq=14, ground=GROUND,
            rebuild=rebuild(points))
        self.assertEqual(state['track_status'], 'locked')
        self.assertEqual(observed['point_count'], len(whole))
        self.assertEqual(observed['candidate_id'], 'g0000')
        self.assertEqual(acquisition_state['composition']['grouped'], ['lower', 'upper'])
        self.assertEqual(acquisition_state['composition']['competitors'], 1)

    def test_nonzero_row_offset_keeps_both_row_domains_separate(self):
        acquisition = self.make()
        offset = 1000
        whole = body()
        for index in range(8):
            points = whole
            candidate = item('body', points, range(len(points)))
            del candidate['evidence_indices']
            candidate['source_rows'] = [row + offset for row in range(len(points))]
            acquisition.step([candidate], 0, index * 0.1, points=points,
                             row_offset=offset, frame_seq=index, ground=GROUND,
                             rebuild=rebuild(points))
        lower, upper = whole[:24], whole[24:]
        points = whole
        candidates = []
        for name, rows in (('lower', range(24)), ('upper', range(24, 48))):
            candidate = item(name, points[list(rows)], rows)
            del candidate['evidence_indices']
            candidate['source_rows'] = [row + offset for row in rows]
            candidates.append(candidate)
        state, acquisition_state, observed = acquisition.step(
            candidates, 0, 0.8, points=points, row_offset=offset, frame_seq=8,
            ground=GROUND, rebuild=rebuild(points))
        self.assertEqual(state['track_status'], 'locked')
        self.assertEqual(sorted(observed['source_rows']),
                         [row + offset for row in range(len(whole))])
        self.assertEqual(acquisition.history.ledger[0]['row_offset'], offset)
        self.assertEqual(sorted(acquisition.history.ledger[0]['source_rows']),
                         [row + offset for row in range(len(whole))])

    def test_composition_can_be_disabled_and_then_ambiguity_returns(self):
        acquisition = self.make(composition=dict(enabled=False))
        whole = body()
        self.lock_body(acquisition, whole)
        lower, upper = whole[:24], whole[24:]
        state, acquisition_state, observed = self.split_frame(
            acquisition, lower, upper, 0.8, 8)
        self.assertIsNone(observed)
        self.assertEqual(state['track_status'], 'ambiguous')
        self.assertNotIn('composition', acquisition_state)

    def test_invalid_candidate_rows_never_produce_a_composition(self):
        acquisition = self.make()
        whole = body()
        self.lock_body(acquisition, whole)
        lower, upper = whole[:24], whole[24:]
        points = np.vstack((lower, upper))
        for rows in ([0] * 24, range(23), range(24, 72)):
            candidates = [item('lower', lower, rows), item('upper', upper, range(24, 48))]
            state, acquisition_state, observed = acquisition.step(
                candidates, 0, 0.8, points=points, frame_seq=8, ground=GROUND,
                rebuild=rebuild(points))
            composition = acquisition_state.get('composition')
            self.assertTrue(composition is None or not composition['accepted'])
            if observed is not None:
                self.assertNotEqual(observed['candidate_id'], 'g0000')

    def test_future_frames_do_not_change_the_composition_prefix(self):
        def run(frames):
            acquisition = self.make()
            whole = body()
            outputs = []
            for index in range(frames):
                if index < 8:
                    points = whole + np.array([-0.01 * index, 0.0, 0.0])
                    outputs.append(acquisition.step(
                        [item('body', points, range(len(points)))], 0, index * 0.1,
                        points=points, frame_seq=index, ground=GROUND,
                        rebuild=rebuild(points))[0])
                else:
                    moved = whole + np.array([-0.01 * index, 0.0, 0.0])
                    lower, upper = moved[:24], moved[24:]
                    points = np.vstack((lower, upper))
                    outputs.append(acquisition.step(
                        [item('lower', lower, range(24)),
                         item('upper', upper, range(24, 48))], 0, index * 0.1,
                        points=points, frame_seq=index, ground=GROUND,
                        rebuild=rebuild(points))[0])
            return outputs
        self.assertEqual(run(12), run(18)[:12])


if __name__ == '__main__':
    unittest.main()
