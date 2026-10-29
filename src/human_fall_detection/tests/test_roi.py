"""Dynamic ROI contracts: mask geometry, state machine, equivalence and bounds.

Everything here is synthetic geometry and a fixed clock. No board data, no human
ground truth; a ROI that keeps a point set is not a human-recognition result.
"""
import copy
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.lidar_candidates import build_snapshot
from core.pipeline import ReplayPipeline
from core.roi import (DEFAULT_SETTINGS, RoiController, ground_basis, resolve_settings,
                      roi_mask)
from test_hf07_node import VALID_GROUND


TILT = dict(status='valid', frame='innolidar',
            normal=[0.2, 0.0, math.sqrt(1.0 - 0.04)], offset_m=1.2)


def points_grid(x=(1.0, 3.0), y=(-0.5, 0.5), z=(0.2, 1.6), nx=9, ny=5, nz=14):
    return np.stack(np.meshgrid(np.linspace(*x, nx), np.linspace(*y, ny),
                                np.linspace(*z, nz)), -1).reshape(-1, 3)


def controller(**overrides):
    settings = dict(enabled=True)
    settings.update(overrides)
    return RoiController(settings)


def locked_state(**overrides):
    state = dict(track_id='t0001', track_status='locked', candidate_id='c0000',
                 position_m=[2.0, 0.0, 0.9], position_predicted=False,
                 velocity_m_s=None, last_measured_source_s=0.0)
    state.update(overrides)
    return state


class MaskGeometry(unittest.TestCase):
    def setUp(self):
        self.points = points_grid()
        self.ground = VALID_GROUND

    def decision(self, **overrides):
        decision = dict(kind='roi_decision', apply=True, state='LOCKED',
                        reason='locked_target', predicted=False,
                        center_m=[2.0, 0.0, 0.9], radius_m=1.0, sigma_m=0.0,
                        margin_m=0.8, height_band_m=[-0.10, 2.50],
                        settings=dict(DEFAULT_SETTINGS, enabled=True, margin_m=0.8,
                                      height_band_m=[-0.10, 2.50]))
        decision.update(overrides)
        return decision

    def test_hand_calculated_circle_and_height_band(self):
        mask, diagnostics = roi_mask(self.points, self.decision(), self.ground)
        ground_relative = self.points[:, 2] + VALID_GROUND['offset_m']
        expected = (np.abs(self.points[:, 0] - 2.0) ** 2
                    + np.abs(self.points[:, 1] - 0.0) ** 2) <= 1.0
        expected &= (ground_relative >= -0.10) & (ground_relative <= 2.50)
        np.testing.assert_array_equal(mask, expected)
        self.assertEqual(diagnostics['kept_points'], int(expected.sum()))
        self.assertEqual(diagnostics['dropped_points'],
                         int(len(self.points) - expected.sum()))
        self.assertEqual(diagnostics['input_points'], len(self.points))
        self.assertTrue(diagnostics['applied'])

    def test_boundary_points_are_exact_and_shell_reports_them(self):
        radius = 1.0
        inside = np.array([[2.0 + radius * (1 - 1e-9), 0.0, 0.9]])
        outside = np.array([[2.0 + radius * (1 + 1e-9), 0.0, 0.9]])
        points = np.vstack((inside, outside))
        mask, diagnostics = roi_mask(points, self.decision(radius_m=radius),
                                     self.ground)
        np.testing.assert_array_equal(mask, [True, False])
        self.assertEqual(diagnostics['boundary_shell_points'], 1)

    def test_row_numbers_are_never_renumbered(self):
        snapshot = build_snapshot(self.points, dict(cluster_mode='spatial_3d',
                                                    cluster_cell_m=0.3),
                                  session_id='s', time_epoch=0, snapshot_id='f',
                                  frame_id='innolidar', ground=self.ground,
                                  roi=self.decision())
        mask, _ = roi_mask(self.points, self.decision(), self.ground)
        kept = set(np.flatnonzero(mask).tolist())
        self.assertTrue(snapshot['roi']['applied'])
        self.assertTrue(set(snapshot['foreground_indices']) <= kept)
        for candidate in snapshot['candidates']:
            self.assertTrue(set(candidate['evidence_indices']) <= kept)
        self.assertLess(len(snapshot['foreground_indices']), len(self.points))

    def test_tilted_ground_uses_the_tangent_plane_not_raw_xy(self):
        basis = ground_basis(TILT)[0]
        normal, u, v = basis['normal'], basis['u'], basis['v']
        centre = np.array([2.0, 0.0, 1.5]) @ normal * 0.0  # any point on the plane
        height = 0.8
        centre = np.array([2.0, 0.0, 0.0]) - (np.array([2.0, 0.0, 0.0]) @ normal
                                             + TILT['offset_m'] - height) * normal
        along_u = centre + 0.9 * u
        along_normal = centre + 0.9 * normal     # 0.9 m in raw XY terms mostly z
        points = np.vstack((centre, along_u, along_normal, centre + 1.4 * u))
        decision = self.decision(center_m=centre.tolist(), radius_m=1.0,
                                 height_band_m=[-0.5, 2.5])
        mask, _ = roi_mask(points, decision, TILT)
        np.testing.assert_array_equal(mask, [True, True, True, False])

    def test_missing_or_mismatched_ground_falls_back_to_full_view(self):
        for ground, reason in ((None, 'ground_unavailable'),
                               (dict(VALID_GROUND, status='unknown'), 'ground_unavailable'),
                               (dict(VALID_GROUND, frame='other'), 'ground_frame_mismatch')):
            mask, diagnostics = roi_mask(self.points, self.decision(), ground)
            self.assertTrue(mask.all())
            self.assertFalse(diagnostics['applied'])
            self.assertEqual(diagnostics['reason'], reason)
        with self.assertRaises(ValueError):
            roi_mask(self.points, self.decision(),
                     dict(VALID_GROUND, normal=[0.0, 0.0, 0.0]))
        with self.assertRaises(ValueError):
            roi_mask(self.points, self.decision(),
                     dict(VALID_GROUND, normal=[float('nan'), 0.0, 1.0]))

    def test_invalid_radius_and_basis_are_explicit_errors(self):
        for radius in (float('nan'), float('inf'), 0.05, -1.0):
            with self.assertRaises(ValueError):
                roi_mask(self.points, self.decision(radius_m=radius), self.ground)
        with self.assertRaises(ValueError):
            ground_basis(dict(VALID_GROUND, normal=[float('inf'), 0.0, 1.0]))
        with self.assertRaises(ValueError):
            resolve_settings(dict(base_radius_m=float('nan')))
        with self.assertRaises(ValueError):
            resolve_settings(dict(unknown=1))
        with self.assertRaises(ValueError):
            resolve_settings(dict(height_band_m=[1.0, 0.0]))
        with self.assertRaises(ValueError):
            resolve_settings(dict(min_radius_m=0.0))
        with self.assertRaises(ValueError):
            resolve_settings(dict(recover_radius_m=1.0))

    def test_no_none_or_disabled_path_adds_fields_or_changes_rows(self):
        settings = dict(cluster_mode='spatial_3d', cluster_cell_m=0.3)
        baseline = build_snapshot(self.points, settings, session_id='s', time_epoch=0,
                                  snapshot_id='f', frame_id='innolidar',
                                  ground=self.ground)
        explicit = build_snapshot(self.points, settings, session_id='s', time_epoch=0,
                                  snapshot_id='f', frame_id='innolidar',
                                  ground=self.ground, roi=None, timings=None)
        self.assertEqual(json.dumps(baseline, sort_keys=True),
                         json.dumps(explicit, sort_keys=True))
        self.assertNotIn('roi', baseline)
        pipeline = ReplayPipeline('s', {'candidates': settings,
                                        'roi': dict(enabled=False)})
        self.assertIsNone(pipeline.roi_controller)
        pipeline_off = ReplayPipeline('s', {'candidates': settings})
        frame = points_grid()
        self.assertEqual(json.dumps(pipeline.step(frame, 1.0, 0, 0), sort_keys=True),
                         json.dumps(pipeline_off.step(frame, 1.0, 0, 0), sort_keys=True))

    def test_stride_is_unchanged_and_before_stride_variant_changes_density(self):
        settings = dict(cluster_mode='spatial_3d', cluster_cell_m=0.05, max_points=100)
        full = points_grid(nx=40, ny=30, nz=30)
        base = build_snapshot(full, settings, session_id='s', time_epoch=0,
                              snapshot_id='f', frame_id='innolidar', ground=self.ground)
        self.assertEqual(len(base['foreground_indices']), 100)
        decision = self.decision(radius_m=0.5, height_band_m=[-3.0, 3.0])
        after = build_snapshot(full, settings, session_id='s', time_epoch=0,
                               snapshot_id='f', frame_id='innolidar', ground=self.ground,
                               roi=decision)
        mask, _ = roi_mask(full, decision, self.ground)
        kept = set(np.flatnonzero(mask).tolist())
        # The stride still samples the full frame first; the ROI only filters those
        # already-strided rows, so the retained sampling density is unchanged.
        self.assertEqual(after['foreground_indices'],
                         [index for index in base['foreground_indices'] if index in kept])
        self.assertGreater(after['roi']['dropped_points'], 0)
        before = build_snapshot(full, settings, session_id='s', time_epoch=0,
                                snapshot_id='f', frame_id='innolidar',
                                ground=self.ground,
                                roi=dict(decision, settings=dict(
                                    DEFAULT_SETTINGS, enabled=True, margin_m=0.8,
                                    height_band_m=[-3.0, 3.0], before_stride=True)))
        self.assertTrue(before['roi']['before_stride'])
        # Placing the ROI before the full-frame stride changes the sampling
        # density of the retained rows (that is why it stays a comparison arm).
        self.assertLess(len(before['foreground_indices']),
                        len(after['foreground_indices']))
        self.assertNotEqual(sorted(before['foreground_indices']),
                            sorted(after['foreground_indices']))
        self.assertTrue(set(before['foreground_indices']) <= kept)
        self.assertTrue(set(after['foreground_indices']) <= kept)


class StateMachine(unittest.TestCase):
    def setUp(self):
        self.ground = VALID_GROUND
        self.controller = controller()
        self.controller.note_measured([2.0, 0.0, 0.9], 0.0, support_extent_m=0.4,
                                      velocity_m_s=None)

    def test_four_states_and_short_occlusion(self):
        decision = self.controller.advance(locked_state(), source_stamp_s=0.1,
                                           ground=self.ground)
        self.assertEqual(decision['state'], 'LOCKED')
        self.assertTrue(decision['apply'])
        self.assertEqual(self.controller.state, 'LOCKED')
        search = self.controller.advance(dict(track_id=None, track_status='unselected'),
                                         source_stamp_s=0.2, ground=self.ground)
        self.assertEqual((search['state'], search['apply']), ('SEARCH', False))
        self.assertEqual(search['reason'], 'no_selected_target')
        lost = self.controller.advance(locked_state(track_status='lost',
                                                    position_predicted=True),
                                       source_stamp_s=0.2, ground=self.ground)
        self.assertEqual(lost['state'], 'LOST')
        self.assertTrue(lost['apply'])
        farther = self.controller.advance(locked_state(track_status='lost'),
                                          source_stamp_s=1.2, ground=self.ground)
        self.assertGreater(farther['radius_m'], lost['radius_m'])
        recovered = self.controller.advance(locked_state(track_status='lost'),
                                            source_stamp_s=10.0, ground=self.ground)
        self.assertEqual((recovered['state'], recovered['apply']), ('RECOVER', False))

    def test_short_occlusion_keeps_the_roi(self):
        self.controller.advance(locked_state(), source_stamp_s=0.1, ground=self.ground)
        occluded = self.controller.advance(
            locked_state(track_status='occluded', position_predicted=True),
            source_stamp_s=0.2, ground=self.ground)
        self.assertEqual(occluded['state'], 'LOCKED')
        self.assertTrue(occluded['apply'])
        self.assertEqual(occluded['radius_m'], occluded['radius_m'])

    def test_relock_shrinks_at_the_configured_rate(self):
        self.controller.advance(locked_state(), source_stamp_s=0.1, ground=self.ground)
        grown = self.controller.advance(locked_state(track_status='lost'),
                                        source_stamp_s=2.5, ground=self.ground)
        self.controller.note_measured([2.0, 0.0, 0.9], 2.6, support_extent_m=0.4)
        first = self.controller.advance(locked_state(), source_stamp_s=2.7,
                                        ground=self.ground)
        self.assertEqual(first['state'], 'LOCKED')
        self.assertLessEqual(first['radius_m'], grown['radius_m'])
        self.assertGreaterEqual(first['radius_m'],
                                grown['radius_m'] - 2.0 * 0.1 - 1e-9)
        decision = first
        for index in range(40):
            stamp = 2.8 + index * 0.1
            self.controller.note_measured([2.0, 0.0, 0.9], stamp - 0.05,
                                          support_extent_m=0.4)
            decision = self.controller.advance(locked_state(), source_stamp_s=stamp,
                                               ground=self.ground)
        self.assertLess(decision['radius_m'], grown['radius_m'])
        self.assertGreaterEqual(decision['radius_m'], 1.5 + 0.8)

    def test_prediction_is_not_integrated_twice(self):
        self.controller.reset('test')
        self.controller.note_measured([2.0, 0.0, 0.9], 0.0, support_extent_m=0.2,
                                      velocity_m_s=[1.0, 0.0, 0.0])
        first = self.controller.advance(locked_state(), source_stamp_s=0.1,
                                        ground=self.ground)
        second = self.controller.advance(locked_state(), source_stamp_s=0.2,
                                         ground=self.ground)
        self.assertTrue(first['predicted'])
        self.assertAlmostEqual(first['center_m'][0], 2.1, places=9)
        self.assertAlmostEqual(second['center_m'][0], 2.2, places=9)

    def test_prediction_can_be_disabled_and_speed_is_bounded(self):
        disabled = controller(prediction=False)
        disabled.note_measured([2.0, 0.0, 0.9], 0.0, support_extent_m=0.2,
                               velocity_m_s=[1.0, 0.0, 0.0])
        decision = disabled.advance(locked_state(), source_stamp_s=0.5,
                                    ground=self.ground)
        self.assertFalse(decision['predicted'])
        self.assertEqual(decision['center_m'], [2.0, 0.0, 0.9])
        bounded = controller()
        bounded.note_measured([2.0, 0.0, 0.9], 0.0, support_extent_m=0.2,
                              velocity_m_s=[10.0, 0.0, 0.0])
        decision = bounded.advance(locked_state(), source_stamp_s=1.0,
                                   ground=self.ground)
        self.assertLessEqual(decision['center_m'][0], 2.0 + 0.8 * 1.5 + 1e-9)

    def test_missing_velocity_never_extrapolates(self):
        decision = self.controller.advance(locked_state(), source_stamp_s=0.5,
                                           ground=self.ground)
        self.assertFalse(decision['predicted'])
        self.assertEqual(decision['center_m'], [2.0, 0.0, 0.9])

    def test_anomalous_source_time_and_binding_reset_safely(self):
        for stamp, reason in ((float('nan'), 'invalid_source_time'),
                              (None, 'invalid_source_time'),
                              (-1.0, 'nonincreasing_source_time')):
            fresh = controller()
            fresh.note_measured([2.0, 0.0, 0.9], 0.0, support_extent_m=0.2)
            decision = fresh.advance(locked_state(), source_stamp_s=stamp,
                                     ground=self.ground)
            self.assertEqual(decision['reason'], reason)
            self.assertFalse(decision['apply'])
            self.assertEqual(fresh.state, 'SEARCH')
        fresh = controller()
        fresh.note_measured([2.0, 0.0, 0.9], 0.0, support_extent_m=0.2,
                            velocity_m_s=[1.0, 0.0, 0.0])
        fresh.advance(locked_state(), source_stamp_s=0.1, ground=self.ground,
                      binding=('s', 0, 'g', 'innolidar', 'v1'))
        decision = fresh.advance(locked_state(), source_stamp_s=0.2, ground=self.ground,
                                 binding=('s', 0, 'g', 'innolidar', 'v2'))
        self.assertEqual(decision['reason'], 'binding_changed')
        self.assertFalse(decision['apply'])
        self.assertIsNone(fresh.last_center_m)

    def test_diagnostics_carry_every_required_field(self):
        decision = self.controller.advance(locked_state(), source_stamp_s=0.1,
                                           ground=self.ground)
        for key in ('state', 'predicted', 'center_m', 'radius_m', 'margin_m',
                    'height_band_m', 'sigma_m', 'age_s', 'reason'):
            self.assertIn(key, decision)
        mask, diagnostics = roi_mask(points_grid(), decision, self.ground)
        for key in ('state', 'applied', 'reason', 'input_points', 'kept_points',
                    'dropped_points', 'boundary_shell_points', 'radius_m',
                    'margin_m', 'height_band_m', 'center_m', 'predicted'):
            self.assertIn(key, diagnostics)
        json.dumps(decision, allow_nan=False)


class PipelineIntegration(unittest.TestCase):
    def frame(self, x=2.0):
        return np.stack(np.meshgrid(np.linspace(x - 0.2, x + 0.2, 13),
                                    np.linspace(-0.15, 0.15, 9),
                                    np.linspace(-1.4, 0.1, 40)), -1).reshape(-1, 3)

    def test_roi_enabled_keeps_target_rows_and_downstream_state(self):
        settings = dict(candidates=dict(cluster_mode='spatial_3d', cluster_cell_m=0.05,
                                        denoise_enabled=False),
                        acquisition=dict(human_entry_gate=False))
        off = ReplayPipeline('s', copy.deepcopy(settings), target_mode='automatic')
        on = ReplayPipeline('s', dict(copy.deepcopy(settings), roi=dict(enabled=True)),
                            target_mode='automatic')
        for pipeline in (off, on):
            pipeline.ground = copy.deepcopy(VALID_GROUND)
        previous_locked = False
        for index in range(14):
            frame = self.frame(2.0 - 0.02 * index)
            a = off.step(frame, 100.0 + index * 0.1, 0, index)
            b = on.step(frame, 100.0 + index * 0.1, 0, index)
            self.assertEqual(a['track']['track_status'], b['track']['track_status'])
            self.assertEqual(a['track']['track_id'], b['track']['track_id'])
            self.assertEqual(sorted(a['target_source_rows']),
                             sorted(b['target_source_rows']))
            self.assertEqual(a['fall']['fall_status'], b['fall']['fall_status'])
            self.assertIn('roi', b)
            # The first locking frame is full view by contract; later locked
            # frames apply the ROI and still keep the identical target rows.
            if previous_locked and b['track']['track_status'] == 'locked':
                self.assertTrue(b['roi']['applied'])
            previous_locked = b['track']['track_status'] == 'locked'
            self.assertTrue(b['timings_s']['roi_controller_s'] >= 0.0)
            self.assertIn('roi_mask_s', b['timings_s'])
            self.assertGreaterEqual(b['timings_s']['roi_mask_s'], 0.0)

    def test_first_lock_frame_is_full_view(self):
        settings = dict(candidates=dict(cluster_mode='spatial_3d', cluster_cell_m=0.05,
                                        denoise_enabled=False),
                        acquisition=dict(human_entry_gate=False),
                        roi=dict(enabled=True))
        pipeline = ReplayPipeline('s', settings, target_mode='automatic')
        pipeline.ground = copy.deepcopy(VALID_GROUND)
        locked = False
        for index in range(14):
            result = pipeline.step(self.frame(), 100.0 + index * 0.1, 0, index)
            if result['track']['track_status'] == 'locked':
                if not locked:
                    self.assertFalse(result['roi']['applied'])
                    locked = True
                else:
                    self.assertTrue(result['roi']['applied'])
        self.assertTrue(locked)


class ConfigBinding(unittest.TestCase):
    def test_roi_config_matches_code_defaults_and_is_disabled(self):
        import yaml
        path = Path(__file__).resolve().parents[1] / 'config/perception_roi_v1.yaml'
        document = yaml.safe_load(path.read_text(encoding='utf8'))
        section = dict(document['roi'])
        self.assertFalse(section['enabled'])
        resolved = resolve_settings(section)
        for key, value in section.items():
            self.assertEqual(resolved[key], value, key)
        frozen = yaml.safe_load((Path(__file__).resolve().parents[1]
                                 / 'config/perception_single_target_v3.yaml'
                                 ).read_text(encoding='utf8'))
        from core.support_composition import DEFAULT_SETTINGS as COMPOSITION_DEFAULTS
        composition = frozen['acquisition']['composition']
        for key, value in composition.items():
            self.assertEqual(COMPOSITION_DEFAULTS[key], value, key)
        self.assertNotIn('roi', document['candidates'])
        self.assertNotIn('roi', frozen['acquisition'])

    def test_invalid_roi_section_is_refused_by_the_pipeline(self):
        with self.assertRaises(ValueError):
            ReplayPipeline('s', {'roi': dict(enabled=True, base_radius_m=-1.0)})
        with self.assertRaises(ValueError):
            ReplayPipeline('s', {'roi': dict(enabled=True, unexpected=1)})


if __name__ == '__main__':
    unittest.main()