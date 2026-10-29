import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core.human_prior import (CLASS_FRAGMENT, CLASS_LYING, CLASS_PLANAR,
                              CLASS_SITTING, CLASS_STANDING, CLASS_UNKNOWN,
                              choose_single, describe, quick_screen)
from core.range_contract import binding_tuple

IDENTITY = dict(session='s', meta_sha256='m', points_sha256='p',
                coordinate='RAW/innolidar', units='m',
                coordinate_transform='identity', grid_sha256='g',
                epoch='source_header_epoch')
BINDING = binding_tuple(IDENTITY)
GROUND = dict(status='valid', normal=[0.0, 0.0, 1.0], offset_m=0.0,
              frame='innolidar', binding=IDENTITY)


class Frame:
    """最小 RangeFrame 替身：只需要 xyz / valid / source_rows / binding。"""

    def __init__(self, xyz, binding=BINDING):
        self.xyz = np.asarray(xyz, dtype=np.float64)
        self.binding = binding
        count = len(self.xyz)
        self.valid = np.ones((1, count), dtype=bool)
        self.source_rows = np.arange(count, dtype=np.int64).reshape(1, count)


def shell(radius, top, base=0.02, center=(3.0, 0.0), n_az=25, n_z=18):
    """竖直圆柱正面壳（半圈方位），模拟雷达只看到人体前半面。"""
    az = np.radians(np.linspace(-80.0, 80.0, n_az))
    z = np.linspace(base, top, n_z)
    grid_az, grid_z = np.meshgrid(az, z)
    x = center[0] + radius * np.cos(grid_az)
    y = center[1] + radius * np.sin(grid_az)
    return np.column_stack((x.ravel(), y.ravel(), grid_z.ravel()))


def lying_box(length=1.70, width=0.45, height=0.30, center=(3.0, 0.0)):
    """躺倒的条状体：顶面 + 两个长侧面。"""
    x = np.linspace(center[0] - length / 2, center[0] + length / 2, 34)
    y = np.linspace(center[1] - width / 2, center[1] + width / 2, 5)
    top_x, top_y = np.meshgrid(x, y)
    parts = [np.column_stack((top_x.ravel(), top_y.ravel(), np.full(top_x.size, height)))]
    x_side, z_side = np.meshgrid(x, np.linspace(0.02, height, 4))
    for sign in (-1.0, 1.0):
        parts.append(np.column_stack((x_side.ravel(),
                                      np.full(x_side.size, center[1] + sign * width / 2),
                                      z_side.ravel())))
    return np.vstack(parts)


def wall(length=2.0, height=2.0, center=(3.0, 0.0)):
    x = np.linspace(center[0] - length / 2, center[0] + length / 2, 40)
    z = np.linspace(0.05, height, 40)
    x_grid, z_grid = np.meshgrid(x, z)
    return np.column_stack((x_grid.ravel(), np.full(x_grid.size, center[1]), z_grid.ravel()))


def entry(track_id, compatible, class_name, score, point_count=100):
    return dict(track_id=track_id, compatible=compatible, score=score,
                point_count=point_count, **{'class': class_name})


def describe_candidate(xyz, ground=GROUND):
    frame = Frame(xyz)
    return describe(frame, np.arange(len(frame.xyz)), ground)


class TestDescribe(unittest.TestCase):
    def test_standing_cylinder_is_standing_geometry_not_identity(self):
        out = describe_candidate(shell(0.22, 1.70))
        self.assertTrue(out['available'])
        self.assertEqual(out['class'], CLASS_STANDING)
        self.assertTrue(out['compatible'])
        self.assertEqual(out['posture'], 'standing')
        self.assertEqual(out['semantic'], 'UNKNOWN')
        self.assertEqual(out['identity'], 'UNKNOWN')
        self.assertNotIn('person', out['class'])
        features = out['features']
        self.assertAlmostEqual(features['top_m'], 1.70, places=2)
        self.assertGreater(features['aspect_height_over_footprint'], 2.0)
        self.assertLess(features['footprint_area_m2'], 0.5)
        self.assertGreaterEqual(len(features['height_histogram']), 10)
        self.assertEqual(len(features['tier_width_m']), len(features['height_histogram']))

    def test_lying_body_is_lying_geometry(self):
        out = describe_candidate(lying_box())
        self.assertEqual(out['class'], CLASS_LYING)
        self.assertTrue(out['compatible'])
        self.assertGreaterEqual(out['features']['horizontal_span_m'], 1.5)
        self.assertLessEqual(out['features']['top_m'], 0.35)

    def test_sitting_body_is_sitting_geometry(self):
        out = describe_candidate(shell(0.20, 0.90))
        self.assertEqual(out['class'], CLASS_SITTING)
        self.assertTrue(out['compatible'])

    def test_small_object_is_fragment_and_never_compatible(self):
        x = np.linspace(2.9, 3.1, 6)
        y = np.linspace(-0.1, 0.1, 4)
        z = np.linspace(0.02, 0.25, 5)
        xg, yg, zg = np.meshgrid(x, y, z)
        out = describe_candidate(np.column_stack((xg.ravel(), yg.ravel(), zg.ravel())))
        self.assertEqual(out['class'], CLASS_FRAGMENT)
        self.assertFalse(out['compatible'])
        self.assertEqual(out['compatible_with'], [])

    def test_wall_is_planar_structure_not_a_person(self):
        out = describe_candidate(wall())
        self.assertEqual(out['class'], CLASS_PLANAR)
        self.assertFalse(out['compatible'])

    def test_lying_near_threshold_top_is_still_lying(self):
        # 四段摸底里真实出现过的边界：top≈0.75 m、水平跨度 0.9 m、垂直度 0.24。
        out = describe_candidate(lying_box(length=1.40, width=0.45, height=0.75))
        self.assertEqual(out['class'], CLASS_LYING)
        self.assertTrue(out['compatible'])
        self.assertLessEqual(out['features']['top_m'], 0.85)

    def test_vertical_sliver_at_head_height_is_not_compatible(self):
        # 门框/柜边那种 1.1 m 高、0.1 m 宽的竖条，不是碎片也不是人。
        x = np.linspace(2.95, 3.05, 5)
        y = np.linspace(-0.05, 0.05, 5)
        z = np.linspace(1.00, 1.17, 8)
        xg, yg, zg = np.meshgrid(x, y, z)
        out = describe_candidate(np.column_stack((xg.ravel(), yg.ravel(), zg.ravel())))
        self.assertFalse(out['compatible'])
        self.assertIn(out['class'], (CLASS_FRAGMENT, 'not_compatible'))

    def test_floating_structure_is_not_standing(self):
        # 悬空 1.2–1.8 m 的板：高度够了，但接地条件不成立（衣架/吊柜）。
        x = np.linspace(2.8, 3.4, 8)
        y = np.linspace(-0.1, 0.1, 4)
        z = np.linspace(1.2, 1.8, 30)
        xg, yg, zg = np.meshgrid(x, y, z)
        out = describe_candidate(np.column_stack((xg.ravel(), yg.ravel(), zg.ravel())))
        self.assertFalse(out['compatible'])
        self.assertEqual(out['class'], 'not_compatible')

    def test_unbound_ground_is_unknown_not_a_guess(self):
        other = dict(GROUND, binding=dict(IDENTITY, session='other'))
        frame = Frame(shell(0.22, 1.70))
        result = describe(frame, np.arange(len(frame.xyz)), other)
        self.assertFalse(result['available'])
        self.assertEqual(result['class'], CLASS_UNKNOWN)
        self.assertFalse(result['compatible'])
        self.assertEqual(result['reason'], 'ground_unavailable_or_unbound')

    def test_few_points_stays_unknown_and_not_compatible(self):
        out = describe_candidate(shell(0.22, 1.70, n_az=6, n_z=4))
        self.assertFalse(out['available'])
        self.assertEqual(out['class'], CLASS_UNKNOWN)
        self.assertEqual(out['reason'], 'insufficient_points')

    def test_invalid_rows_are_rejected(self):
        frame = Frame(shell(0.22, 1.70))
        for rows in ([], [0, 0], [-1], [len(frame.xyz)]):
            with self.assertRaises(ValueError):
                describe(frame, rows, GROUND)

    def test_deterministic_output(self):
        first = describe_candidate(shell(0.22, 1.70))
        second = describe_candidate(shell(0.22, 1.70))
        self.assertEqual(first, second)
        self.assertEqual(first['thresholds'], second['thresholds'])

    def test_quick_screen_matches_describe_on_clear_cases(self):
        for xyz, expected in ((shell(0.22, 1.70), CLASS_UNKNOWN),
                              (wall(), CLASS_PLANAR),
                              (shell(0.22, 1.70, n_az=5, n_z=3), CLASS_UNKNOWN)):
            out = quick_screen(xyz, GROUND)
            self.assertTrue(out['evaluated'])
            self.assertEqual(out['class'], expected)
        frag = quick_screen(np.column_stack((np.linspace(2.9, 3.1, 6),
                                             np.linspace(-0.1, 0.1, 6),
                                             np.linspace(0.02, 0.25, 6))), GROUND)
        self.assertEqual(frag['class'], CLASS_FRAGMENT)
        self.assertFalse(quick_screen(shell(0.22, 1.70), {'status': 'invalid'})['evaluated'])


class TestChooseSingle(unittest.TestCase):
    def test_no_compatible_target_prefers_no_lock(self):
        out = choose_single([entry('t1', False, CLASS_FRAGMENT, 5.0)])
        self.assertIsNone(out['chosen_track_id'])
        self.assertEqual(out['reason'], 'no_human_compatible_target')
        self.assertEqual(out['rejected'], [{'track_id': 't1', 'class': CLASS_FRAGMENT,
                                            'reason': 'not_human_compatible'}])

    def test_unknown_stays_eligible_but_loses_to_compatible(self):
        out = choose_single([entry('t1', False, CLASS_UNKNOWN, 9.0),
                             entry('t2', True, CLASS_STANDING, 1.0)])
        self.assertEqual(out['chosen_track_id'], 't2')
        self.assertEqual(out['reason'], 'best_compatible_target')
        self.assertEqual(out['eligible_count'], 2)
        self.assertEqual(out['compatible_count'], 1)

    def test_previous_target_retained_by_hysteresis(self):
        entries = [entry('t1', True, CLASS_STANDING, 1.00),
                   entry('t2', True, CLASS_STANDING, 1.05)]
        self.assertEqual(choose_single(entries)['chosen_track_id'], 't2')
        kept = choose_single(entries, previous_track_id='t1')
        self.assertEqual(kept['chosen_track_id'], 't1')
        self.assertEqual(kept['reason'], 'previous_target_retained')
        far = choose_single([entry('t1', True, CLASS_STANDING, 1.0),
                             entry('t2', True, CLASS_STANDING, 3.0)],
                            previous_track_id='t1')
        self.assertEqual(far['chosen_track_id'], 't2')

    def test_close_scores_are_flagged_ambiguous(self):
        out = choose_single([entry('t1', True, CLASS_STANDING, 1.00),
                             entry('t2', True, CLASS_STANDING, 0.95)])
        self.assertTrue(out['ambiguous'])
        self.assertEqual(out['chosen_track_id'], 't1')
        clear = choose_single([entry('t1', True, CLASS_STANDING, 1.0),
                               entry('t2', True, CLASS_STANDING, 0.4)])
        self.assertFalse(clear['ambiguous'])

    def test_empty_entries(self):
        out = choose_single([])
        self.assertIsNone(out['chosen_track_id'])
        self.assertEqual(out['reason'], 'no_human_compatible_target')
        self.assertEqual(out['policy'], 'single_person')


if __name__ == '__main__':
    unittest.main()