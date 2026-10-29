"""Source-time continuity of pending stance; geometry simulation only."""
import math
import sys
from pathlib import Path
import unittest
import copy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.baseline import StanceBaselineCollector
from test_human_entry_gate import candidate
from core.node_runtime import FallNodeCore
from core.pipeline import ReplayPipeline
from core.lidar_candidates import build_snapshot
from test_hf07_node import VALID_GROUND

CURRENT = Path(__file__).resolve().parents[3] / 'sidequests/hfus_tcms_02/realdev/current'
sys.path.insert(0, str(CURRENT))
from project_fall import FallRuntime


class BaselineContinuity(unittest.TestCase):
    def setUp(self):
        self.collector = StanceBaselineCollector('s')
        self.track = dict(track_id='t1', time_epoch=0, selection_version=1,
                          action_generation=1, calibration_version='g',
                          track_status='locked', position_predicted=False)

    def feed(self, stamp, c=True):
        return self.collector.feed_automatic(candidate(x=3.44) if c else None, self.track, stamp)

    def test_point_four_second_implicit_gap_restarts_segment(self):
        for stamp in [3.5+i*.1 for i in range(14)]+[5.2+i*.1 for i in range(14)]:
            self.feed(stamp)
        self.assertEqual(self.collector.status, 'pending')
        self.assertEqual(len(self.collector.samples), 14)
        self.assertAlmostEqual(self.collector.start_source_s, 5.2)

    def test_gap_boundaries(self):
        for gap, count in ((.299999, 2), (.3, 2), (math.nextafter(.3, 0), 2),
                           (math.nextafter(.3, math.inf), 1), (.300001, 1), (.4, 1)):
            with self.subTest(gap=gap):
                self.setUp()
                self.feed(0.)
                self.feed(gap)
                self.assertEqual(len(self.collector.samples), count)

    def test_invalid_duplicate_and_backward_do_not_accumulate(self):
        for stamp in (None, float('nan'), float('inf'), 1., .9):
            with self.subTest(stamp=stamp):
                self.setUp()
                self.feed(1.)
                self.feed(stamp)
                self.assertEqual(len(self.collector.samples), 0)
                self.assertIsNone(self.collector.baseline)
                self.feed(2.)
                self.assertEqual(len(self.collector.samples), 1)

    def test_explicit_gap_and_new_binding(self):
        self.feed(0.)
        self.feed(.1, False)
        self.feed(.2)
        self.assertEqual(len(self.collector.samples), 1)
        self.track['action_generation'] = 2
        self.feed(.3)
        self.assertEqual(len(self.collector.samples), 1)
        self.assertEqual(self.collector.action_generation, 2)

    def test_ready_survives_stationary_low_and_short_occlusion(self):
        for i in range(32):
            self.feed(i*.1)
        baseline = self.collector.baseline
        self.assertIsNotNone(baseline)
        self.feed(3.2, False)
        c = candidate(x=3.44, height=.4)
        self.collector.feed_automatic(c, self.track, 3.4)
        self.assertIs(self.collector.baseline, baseline)
        self.track['track_id'] = 't2'
        self.feed(3.5)
        self.assertIsNone(self.collector.baseline)

    def test_manual_pending_cannot_cross_gap_or_explicit_missing(self):
        c = self.collector
        c.start('t1', 'g', start_source_s=0.)
        obs = dict(track_id='t1', calibration_version='g', ground_relative=True,
                   point_count=100, height_m=candidate()['height_m'], position_m=[0, 0, 1])
        c.feed(obs, 0.)
        c.feed(obs, .4)
        self.assertEqual(c.status, 'failed')
        self.assertIsNone(c.baseline)

    def test_manual_gap_emits_failed_ack_with_original_request(self):
        core = FallNodeCore('s', ground=VALID_GROUND)
        core.baseline.start('t1', 'g', start_source_s=0., operator_confirmed=True)
        core._baseline_request_id = 'baseline_request'
        core._baseline_status = 'pending'
        c = candidate(x=3.44)
        self.assertIsNone(core._feed_baseline(c, self.track, 0., 0., 0))
        ack = core._feed_baseline(c, self.track, .4, .4, 0)
        self.assertEqual(ack['request_id'], 'baseline_request')
        self.assertFalse(ack['accepted'])
        self.assertEqual(ack['baseline']['status'], 'failed')
        self.assertEqual(ack['reason'], 'observation_gap')


class ThreeEntryContinuity(unittest.TestCase):
    def harness(self):
        grid = np.stack(np.meshgrid(np.linspace(1.9, 2.1, 7), np.linspace(-.1, .1, 7),
                                   np.linspace(-1.35, .1, 20)), -1).reshape(-1, 3)
        settings = {'acquisition': {'human_entry_gate': False}}
        core = FallNodeCore('s', ground=VALID_GROUND, target_mode='automatic', settings=settings)
        replay = ReplayPipeline('s', target_mode='automatic', settings=settings)
        replay.ground = copy.deepcopy(VALID_GROUND)
        current = FallRuntime('s', 'g', acquisition_settings=settings['acquisition'])
        c = build_snapshot(grid, ground=VALID_GROUND, session_id='s', time_epoch=0,
                           snapshot_id='fixture')['candidates'][0]
        low_grid = grid.copy()
        low_grid[:, 2] = -1.35+(grid[:, 2]+1.35)*.25
        low_c = build_snapshot(low_grid, ground=VALID_GROUND, session_id='s', time_epoch=0,
                               snapshot_id='low_fixture')['candidates'][0]
        collectors = (core.baseline, replay.baseline_collector, current.baseline_collector)
        index = [0]
        def step(stamp, missing=False, low=False):
            seq = index[0]
            index[0] += 1
            points = np.empty((0, 3)) if missing else low_grid if low else grid
            sec = int(stamp)
            nsec = round((stamp-sec)*1e9)
            stamp = sec+nsec*1e-9  # The live entry consumes integer ROS nanoseconds.
            live_output = core.process(points, stamp, seq=seq, stamp_secs=sec,
                                       stamp_nsecs=nsec, now=stamp)
            replay_output = replay.step(points, stamp, 0, seq)
            current_output = current.step(stamp, None if missing else copy.deepcopy(low_c if low else c))
            step.outputs = (live_output, replay_output, current_output)
            return [(b.status, len(b.samples), b.baseline is not None) for b in collectors]
        for i in range(35):
            step(100+i*.1)
        for b in collectors:
            b.invalidate('test_new_collection')
        return step, collectors

    def test_all_three_entry_gap_boundaries(self):
        for end in (103.7, 103.8, math.nextafter(103.8, -math.inf),
                    math.nextafter(103.8, math.inf), 103.800000001, 103.9):
            with self.subTest(end=end):
                step, collectors = self.harness()
                first = step(103.5)
                self.assertEqual(first, [('pending', 1, False)]*3)
                after = step(end)
                encoded = int(end)+round((end-int(end))*1e9)*1e-9
                count = 1 if encoded-103.5 > .3 else 2
                self.assertEqual(after, [('pending', count, False)]*3)

    def test_all_three_point_four_and_explicit_gap(self):
        for explicit in (False, True):
            with self.subTest(explicit=explicit):
                step, collectors = self.harness()
                for i in range(14):
                    step(103.5+i*.1)
                if explicit:
                    step(105., missing=True)
                for i in range(14):
                    result = step(105.2+i*.1)
                self.assertEqual(result, [('pending', 14, False)]*3)
                self.assertTrue(all(abs(b.start_source_s-105.2)<1e-9 for b in collectors))

    def test_all_three_ready_binding_and_invalid_times(self):
        step, collectors = self.harness()
        for i in range(32):
            step(103.5+i*.1)
        self.assertTrue(all(b.baseline is not None for b in collectors))
        step(106.7, missing=True)
        step(106.9)
        self.assertTrue(all(b.baseline is not None for b in collectors))
        originals = [b.baseline for b in collectors]
        for stamp in (107., 107.1, 107.2):
            step(stamp, low=True)
            live, replay, current = step.outputs
            self.assertTrue(live['state']['target_features']['baseline_bound'])
            self.assertTrue(replay['features']['baseline_bound'])
            self.assertTrue(current['fall']['baseline_ready'])
            self.assertLess(current['fall']['height_m'], .4)
            self.assertNotEqual(current['fall']['status'], 'unknown')
            self.assertTrue(all(b.baseline is old for b, old in zip(collectors, originals)))
        # A source-time rollback invalidates acquisition binding in every entry.
        step(100.)
        self.assertTrue(all(b.baseline is None for b in collectors))
