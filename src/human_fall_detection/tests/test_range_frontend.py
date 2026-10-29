"""W1测量来源、因果背景和独立图遍历回归；不提供人体GT。"""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from core.capture_input import ROW_DTYPE
from core.range_image import ScanGrid
from core.range_background import RayBackground
from core.range_denoise import denoise, depth_continuous
from core.range_components import label_components, merge_components
from replay_range_frontend import run


def scene(depth, binding=('session', 'frame', 'calibration', 0)):
    depth = np.asarray(depth, dtype=float)
    h, w = depth.shape
    az = np.broadcast_to(np.linspace(-20, 20, w), (h, w))
    el = np.broadcast_to(np.linspace(-10, 10, h)[:, None], (h, w))
    grid = ScanGrid(az, el)
    raw = np.zeros(h*w, dtype=ROW_DTYPE)
    raw['ring'] = np.repeat(np.arange(h), w)
    a, e = np.radians(az.ravel()), np.radians(el.ravel())
    r = depth.ravel()
    raw['x'], raw['y'], raw['z'] = r*np.cos(e)*np.cos(a), r*np.cos(e)*np.sin(a), r*np.sin(e)
    raw['timestamp'] = np.float32(200000.125)
    raw['intensity'] = np.arange(h*w)
    return grid, raw, grid.decode(raw, binding)


def oracle(frame, mask):
    pending = set(map(tuple, np.argwhere(mask)))
    groups = []
    while pending:
        todo, group = [min(pending)], []
        pending.remove(todo[0])
        while todo:
            a = todo.pop()
            group.append(int(frame.source_rows[a]))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    b = (a[0]+dy, a[1]+dx)
                    if b in pending and depth_continuous(frame.range_m[a], frame.range_m[b]):
                        pending.remove(b)
                        todo.append(b)
        groups.append(sorted(group))
    return sorted(groups)


class RangeImageTests(unittest.TestCase):
    def test_calibrated_nonuniform_reversed_columns_and_source_rebuild(self):
        grid, raw, frame = scene(np.full((3, 4), 2.0))
        reversed_grid = ScanGrid(grid.azimuth_deg[:, ::-1], grid.elevation_deg[:, ::-1])
        actual = reversed_grid.decode(raw, frame.binding)
        np.testing.assert_array_equal(actual.source_rows, frame.source_rows[:, ::-1])
        np.testing.assert_array_equal(actual.xyz[actual.source_rows[actual.valid]],
                                      frame.xyz[frame.source_rows[:, ::-1].ravel()])
        np.testing.assert_allclose(actual.range_m, 2, atol=1e-6)
        self.assertFalse(grid.azimuth_deg.flags.writeable)

    def test_duplicate_nearest_and_equal_range_tie(self):
        grid, raw, frame = scene(np.full((2, 3), 2.0))
        extra = raw[[1, 1]].copy()
        for name in ('x', 'y', 'z'):
            extra[name][0] *= 0.5
            extra[name][1] *= 0.5
        actual = grid.decode(np.r_[raw, extra], frame.binding)
        self.assertEqual(actual.source_rows[0, 1], len(raw))
        self.assertEqual(set(actual.rejected['duplicate_rows']), {1, len(raw)+1})
        self.assertEqual(actual.range_m[0, 1], frame.range_m[0, 1]*0.5)

    def test_zero_nonfinite_bad_ring_and_wrong_direction_are_separate(self):
        grid, raw, frame = scene(np.full((2, 3), 2.0))
        for k in ('x', 'y', 'z'):
            raw[k][0] = 0
        raw['x'][1] = np.nan
        raw['ring'][2] = 999
        raw['z'][3] += 1
        actual = grid.decode(raw, frame.binding)
        self.assertEqual(actual.rejected['zero_or_near_rows'].tolist(), [0])
        self.assertEqual(actual.rejected['nonfinite_rows'].tolist(), [1])
        self.assertEqual(actual.rejected['invalid_ring_rows'].tolist(), [2])
        self.assertEqual(actual.rejected['unknown_direction_rows'].tolist(), [3])
        self.assertEqual(int(actual.valid.sum()), 2)
        self.assertTrue(np.isnan(actual.range_m[0, 0]))

    def test_empty_decode_and_truncated_record(self):
        grid, _, frame = scene(np.ones((2, 3)))
        actual = grid.decode(b'', frame.binding)
        self.assertEqual(int(actual.valid.sum()), 0)
        self.assertTrue(np.isnan(actual.row_time_s).all())
        with self.assertRaises(ValueError):
            grid.decode(b'x', frame.binding)
        with self.assertRaises(ValueError):
            grid.decode(b'', ())

    def test_table_ambiguity_and_elevation_validation(self):
        with self.assertRaises(ValueError):
            ScanGrid([[0, .01], [0, .01]], [[0, 0], [1, 1]])
        with self.assertRaises(ValueError):
            ScanGrid([[0, 1], [1, 0]], [[0, 0], [1, 1]])
        grid, raw, frame = scene(np.ones((2, 3)))
        raw['timestamp'][0] = np.nan
        actual = grid.decode(raw, frame.binding)
        self.assertTrue(actual.valid[0, 0])
        self.assertTrue(np.isnan(actual.point_time_s[0, 0]))
        np.testing.assert_array_equal(actual.point_time_s[1], raw['timestamp'][3:])

    def test_dense_direction_bins_use_exact_nearest_fallback(self):
        grid = ScanGrid([[0, .05], [0, .05]], [[0, 0], [1, 1]])
        raw = np.zeros(1, dtype=ROW_DTYPE)
        raw['x'], raw['y'] = 2*np.cos(np.radians(.031)), 2*np.sin(np.radians(.031))
        frame = grid.decode(raw, ('s', 'f', 'c', 0))
        self.assertEqual(frame.source_rows[0, 1], 0)
        self.assertEqual(len(frame.rejected['unknown_direction_rows']), 0)


class BackgroundTests(unittest.TestCase):
    def test_declared_prefix_and_missing_rays_have_no_nan_warning(self):
        _, _, frame = scene([[2, 0, 2], [2, 0, 2]])
        with self.assertRaises(ValueError):
            RayBackground([frame], empty_prefix_declared=False)
        bg = RayBackground([frame]*10, empty_prefix_declared=True)
        self.assertEqual(int(bg.known.sum()), 4)
        self.assertFalse(bg.foreground(frame)['mask'].any())
        _, _, target = scene(np.full((2, 3), 1.0))
        result = bg.foreground(target)
        self.assertEqual(int(result['unknown'].sum()), 2)
        self.assertFalse(result['mask'][:, 1].any())

    def test_four_sigma_gate_and_frozen_update(self):
        _, _, base = scene(np.full((4, 5), 2.0))
        prefix = [replace(base, range_m=base.range_m + offset) for offset in (-.01, 0, .01)*4]
        bg = RayBackground(prefix, empty_prefix_declared=True)
        near = replace(base, range_m=base.range_m+.02)
        self.assertFalse(bg.foreground(near)['mask'].any())
        freeze = np.ones(base.grid.shape, dtype=bool)
        before = bg.mean_m.copy()
        self.assertEqual(bg.update(near, freeze_mask=freeze, alpha=.5), 0)
        np.testing.assert_array_equal(before, bg.mean_m)
        self.assertEqual(bg.update(near, freeze_mask=~freeze, alpha=.5), 20)
        self.assertGreater(float(bg.mean_m.mean()), float(before.mean()))
        target = replace(base, range_m=base.range_m.copy())
        target.range_m[1, 1] = 1.0
        before = bg.mean_m[1, 1]
        bg.update(target, freeze_mask=~freeze, alpha=1)
        self.assertEqual(bg.mean_m[1, 1], before)

    def test_binding_changes_reject_old_background(self):
        _, _, base = scene(np.full((3, 4), 2.0))
        bg = RayBackground([base]*10, empty_prefix_declared=True)
        for i in range(4):
            binding = list(base.binding)
            binding[i] = 'new'
            with self.assertRaises(ValueError):
                bg.foreground(replace(base, binding=tuple(binding)))
        changed = ScanGrid(base.grid.azimuth_deg+.01, base.grid.elevation_deg)
        with self.assertRaises(ValueError):
            bg.foreground(replace(base, grid=changed))

    def test_large_scene_change_latches_and_dropout_is_temporary(self):
        _, _, base = scene(np.full((3, 4), 2.0))
        bg = RayBackground([base]*10, empty_prefix_declared=True)
        dropout = replace(base, valid=np.zeros(base.grid.shape, dtype=bool))
        self.assertEqual(bg.foreground(dropout)['status'], 'insufficient_valid_cells')
        self.assertEqual(bg.foreground(base)['status'], 'ready')
        moved = replace(base, range_m=base.range_m+1)
        self.assertEqual(bg.foreground(moved)['status'], 'background_invalidated')
        self.assertFalse(bg.foreground(base)['mask'].any())
        self.assertEqual(bg.foreground(base)['status'], 'background_invalidated')

    def test_adding_future_frames_does_not_change_prefix_background(self):
        _, _, base = scene(np.full((3, 4), 2.0))
        prefix = [base]*10
        a = RayBackground(prefix, empty_prefix_declared=True)
        b = RayBackground(prefix, empty_prefix_declared=True)
        first = a.foreground(base)['mask'].copy()
        b.foreground(base)
        b.foreground(replace(base, range_m=base.range_m+2))
        np.testing.assert_array_equal(first, a.foreground(base)['mask'])

    def test_shallow_same_voxel_surface_and_stationary_foreground_remain_measured(self):
        _, _, base = scene(np.full((4, 5), 2.08))
        bg = RayBackground([base]*10, empty_prefix_declared=True)
        target = replace(base, range_m=base.range_m.copy())
        target.range_m[1:3, 1:3] = 2.0
        for _ in range(20):
            result = bg.foreground(target)
            self.assertTrue(result['mask'][1:3, 1:3].all())
            bg.update(target, freeze_mask=np.zeros(base.grid.shape, dtype=bool), alpha=1)
        np.testing.assert_allclose(bg.mean_m[1:3, 1:3], 2.08, atol=1e-6)


class ComponentsTests(unittest.TestCase):
    def test_random_graph_matches_independent_pixel_oracle(self):
        rng = np.random.RandomState(61)
        for _ in range(30):
            depth = 2 + rng.randint(0, 3, (7, 9))*.08
            _, _, frame = scene(depth)
            mask = rng.rand(7, 9) > .3
            _, groups = label_components(frame, mask, min_points=1)
            self.assertEqual(sorted(c['source_rows'].tolist() for c in groups), oracle(frame, mask))

    def test_diagonal_no_wrap_and_depth_discontinuity(self):
        _, _, frame = scene(np.full((3, 5), 2.0))
        mask = np.zeros((3, 5), dtype=bool)
        mask[0, 4] = mask[1, 0] = mask[2, 1] = True
        _, groups = label_components(frame, mask, min_points=1)
        self.assertEqual(sorted(c['source_rows'].tolist() for c in groups), [[4], [5, 11]])
        depth = np.full((3, 5), 8.0)
        depth[:, 2:] += .11
        _, _, frame = scene(depth)
        _, groups = label_components(frame, frame.valid, min_points=1)
        self.assertEqual(len(groups), 2)

    def test_minimum_component_size_is_flagged_without_losing_rows(self):
        _, _, frame = scene(np.full((3, 10), 2.0))
        mask = np.zeros((3, 10), dtype=bool)
        mask.ravel()[:14] = True
        _, groups = label_components(frame, mask)
        self.assertFalse(groups[0]['retained'])
        mask.ravel()[14] = True
        labels, groups = label_components(frame, mask)
        self.assertTrue(groups[0]['retained'])
        self.assertEqual(int((labels >= 0).sum()), 15)

    def test_depth_edge_is_preserved_and_isolated_return_removed(self):
        depth = np.full((6, 8), 5.0)
        depth[1:5, 1:4] = 2.0
        depth[4, 6] = 3.0
        _, _, frame = scene(depth)
        foreground = depth < 5
        result = denoise(frame, foreground)
        self.assertTrue(result['edge'][1, 1])
        self.assertTrue(result['mask'][1:5, 1:4].all())
        self.assertFalse(result['mask'][4, 6])
        np.testing.assert_allclose(frame.range_m, depth, atol=1e-6)

    def test_invalid_mask_and_settings_rejected(self):
        _, _, frame = scene(np.ones((2, 3)))
        for bad in (-1, True, 1.5, 9):
            with self.assertRaises(ValueError):
                denoise(frame, frame.valid, bad)
        with self.assertRaises(ValueError):
            label_components(frame, frame.valid, min_points=0)
        with self.assertRaises(ValueError):
            denoise(frame, np.ones((2, 2), dtype=bool))

    def test_merge_uses_real_3d_gap_and_shape_with_exact_row_union(self):
        _, _, frame = scene(np.full((3, 8), 2.0))
        frame.xyz = np.column_stack((np.tile(np.arange(8)*.02, 3), np.zeros(24), np.ones(24)))
        depth = frame.range_m.copy()
        depth[:, 4:] += .06
        frame.range_m = depth
        labels, components = label_components(frame, frame.valid, min_points=1)
        self.assertEqual(len(components), 2)
        new_labels, merged = merge_components(frame, labels, components,
                                              dict(normal=[0, 0, 1], offset_m=0))
        self.assertEqual(len(merged), 1)
        np.testing.assert_array_equal(merged[0]['source_rows'], np.arange(24))
        self.assertTrue((new_labels == 0).all())
        # 前后表面虽像素相邻，真实3D相隔1m不能被合并。
        frame.xyz[frame.source_rows[:, 4:].ravel(), 0] += 1
        _, merged = merge_components(frame, labels, components, dict(normal=[0, 0, 1], offset_m=0))
        self.assertEqual(len(merged), 2)
        self.assertTrue(all(c['retained'] for c in merged))

    def test_merge_preserves_minimum_without_membership_change(self):
        _, _, frame = scene(np.full((3, 8), 2.0))
        labels, components = label_components(frame, frame.valid, min_points=30)
        _, merged = merge_components(frame, labels, components, dict(normal=[0, 0, 1], offset_m=0))
        self.assertFalse(merged[0]['retained'])
        self.assertEqual(merged[0]['min_points'], 30)

    def test_transitive_merge_enforces_three_times_original_size(self):
        _, _, frame = scene(np.full((3, 16), 2.0))
        frame.xyz = np.column_stack((np.tile(np.arange(16)*.02, 3), np.zeros(48), np.ones(48)))
        frame.range_m += np.repeat(np.arange(4)*.06, 4)[None, :]
        labels, components = label_components(frame, frame.valid, min_points=1)
        self.assertEqual(len(components), 4)
        new_labels, merged = merge_components(frame, labels, components, dict(normal=[0, 0, 2], offset_m=0))
        self.assertEqual(len(merged), 2)
        self.assertEqual(max(c['points'] for c in merged), 36)
        self.assertEqual(sorted(r for c in merged for r in c['source_rows']), list(range(48)))
        for component in merged:
            rows = np.sort(frame.source_rows[new_labels == component['component_id']])
            np.testing.assert_array_equal(rows, component['source_rows'])


class ReplayBoundaryTests(unittest.TestCase):
    def test_output_cannot_be_source_descendant_or_ancestor_even_outside_repo(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source'
            source.mkdir()
            for output in (source, source / 'new', Path(temp)):
                with self.assertRaisesRegex(ValueError, 'outside source data'):
                    run(source, output, empty_prefix_frames=1,
                        azimuth='unused.csv', elevation='unused.csv')

    def test_merge_requires_ground_and_rejects_excess_height(self):
        _, _, frame = scene(np.full((3, 8), 2.0))
        frame.xyz = np.column_stack((np.tile(np.arange(8)*.02, 3), np.zeros(24), np.ones(24)*3))
        frame.range_m[:, 4:] += .06
        labels, components = label_components(frame, frame.valid, min_points=1)
        with self.assertRaises(ValueError):
            merge_components(frame, labels, components, {})
        _, merged = merge_components(frame, labels, components, dict(normal=[0, 0, 1], offset_m=0))
        self.assertEqual(len(merged), 2)


if __name__ == '__main__':
    unittest.main()
