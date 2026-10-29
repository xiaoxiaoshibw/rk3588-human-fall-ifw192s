"""Counterexamples for causal geometry, independent event scoring and cache binding."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from evaluate_fall_events import evaluate, poisson_interval
from fall_annotation import event_windows
from fall_candidate_runtime import file_sha256
from fall_geometry import FallGeometryRuntime, frame_geometry
from prepare_fall_events import prepare
from test_fall_gate import tilted, upright, lying
from urfall_geometry_proxy import feature_evidence, read_sync


def annotation():
    return dict(schema='fall_events_v1', session='test_session', subject='S01', duration_s=20.,
                clock=dict(offset_s=2., uncertainty_s=.1), events=[
                    dict(id='e1', kind='fall', t_start=2., t_impact=2.6, t_end=5., observable=True),
                    dict(id='e2', kind='fall', t_start=8., t_impact=8.6, t_end=10., observable=False)])


def body(angle):
    return tilted(angle)[:, :3]


def sequence(hz=10):
    # Analytic moving body; these are software fixtures, never physical evidence.
    rows = []
    for t in np.arange(0., 2.1, 1./hz):
        angle = 0. if t < .5 else min(90., (t-.5)*180.)
        rows.append((float(t), body(angle)))
    return rows


def feed(runtime, rows, generation='g1'):
    return [runtime.push(p, t, 'person', generation, 'calibration') for t, p in rows]


class GeometryTest(unittest.TestCase):
    def test_seconds_and_rate_equivalence(self):
        alarms = []
        for hz in (10, 20):
            values = feed(FallGeometryRuntime([0, 0, 1], 0.), sequence(hz))
            events = [v['new_event'] for v in values if v['new_event']]
            self.assertEqual(len(events), 1)
            alarms.append(events[0]['alarm_s'])
        self.assertLessEqual(abs(alarms[0]-alarms[1]), .1)

    def test_lying_without_descent_never_alarms(self):
        values = feed(FallGeometryRuntime([0, 0, 1], 0.), [(i/10, body(90)) for i in range(30)])
        self.assertFalse(any(v['new_event'] for v in values))
        self.assertEqual(values[-1]['state'], 'low_without_descent')

    def test_truncated_hold_is_pending_not_absent_descent(self):
        runtime = FallGeometryRuntime([0, 0, 1], 0.)
        result = feed(runtime, sequence()[:12])[-1]
        self.assertEqual(result['state'], 'low_hold_pending')
        self.assertTrue(result['descent_evidence'])
        self.assertIsNone(result['new_event'])

    def test_missing_ground_is_unknown(self):
        self.assertEqual(feed(FallGeometryRuntime(), sequence())[0]['reason'], 'missing_ground')

    def test_coordinate_invariance(self):
        theta = .4
        rotation = np.array([[math.cos(theta), 0, math.sin(theta)], [0, 1, 0],
                             [-math.sin(theta), 0, math.cos(theta)]])
        translation = np.array([1., 2., 3.])
        normal = rotation @ np.array([0., 0., 1.])
        p = body(45)
        a = frame_geometry(p, [0, 0, 1], 0.)
        b = frame_geometry(p @ rotation.T + translation, normal, -float(normal @ translation))
        for key in ('centroid_height_m', 'inclination_deg', 'vertical_span_m'):
            self.assertAlmostEqual(a[key], b[key], places=10)

    def test_gap_never_bridges_descent(self):
        runtime = FallGeometryRuntime([0, 0, 1], 0.)
        feed(runtime, [(0., body(0)), (.1, body(45))])
        result = runtime.push(body(90), 2., 'person', 'g1', 'calibration')
        self.assertEqual(result['reason'], 'time_discontinuity')
        self.assertFalse(any(v['new_event'] for v in feed(runtime, [(2.1, body(90)), (2.5, body(90))])))

    def test_identity_and_calibration_changes_reset(self):
        for index in (0, 1, 2):
            runtime = FallGeometryRuntime([0, 0, 1], 0.)
            feed(runtime, [(0., body(0)), (.1, body(45))])
            key = ['person', 'g1', 'calibration']
            key[index] = 'changed'
            values = [runtime.push(body(90), t, *key) for t in (.2, .4, .6)]
            self.assertFalse(any(v['new_event'] for v in values))

    def test_unknown_preserves_latch_but_not_motion(self):
        runtime = FallGeometryRuntime([0, 0, 1], 0.)
        feed(runtime, sequence())
        event = runtime.active_event
        self.assertIsNotNone(event)
        missing = runtime.push(np.empty((0, 3)), 2.2, 'person', 'g1', 'calibration', observed=False)
        self.assertEqual(missing['state'], 'unknown')
        self.assertEqual(missing['event_id'], event)
        values = feed(runtime, [(2.3, body(90)), (2.6, body(90))])
        self.assertFalse(any(v['new_event'] for v in values))
        feed(runtime, [(2.7+i/10, body(0)) for i in range(8)])
        self.assertIsNone(runtime.active_event)

    def test_prefix_is_causal_and_bad_points_unknown(self):
        first = feed(FallGeometryRuntime([0, 0, 1], 0.), sequence()[:9])
        full = feed(FallGeometryRuntime([0, 0, 1], 0.), sequence())
        self.assertEqual(first, full[:9])
        bad = body(40); bad[0, 0] = np.nan
        self.assertFalse(frame_geometry(bad, [0, 0, 1], 0.)['valid'])


class EventScoreTest(unittest.TestCase):
    def test_unobservable_true_event_stays_in_main_denominator(self):
        result = evaluate([dict(annotation=annotation(), alarms=[dict(alarm_s=5.)])])['overall']
        self.assertEqual(result['end_to_end_recall'], .5)
        self.assertEqual(result['observable_recall'], 1.)
        self.assertIsNone(result['false_alarms_per_hour'])

    def test_one_to_one_duplicates_and_unknown_exposure(self):
        result = evaluate([dict(annotation=annotation(), alarms=[dict(alarm_s=t) for t in (5., 5.2, 15.)],
                                negative_intervals=[[12., 20.]], unknown_intervals=[[12., 16.]])])['overall']
        self.assertEqual(result['duplicates'], 1)
        self.assertEqual(result['false_alarms'], 1)
        self.assertEqual(result['negative_s'], 8.)
        self.assertEqual(result['observed_negative_fraction'], .5)
        self.assertEqual(result['false_alarms_per_hour'], 450.)

    def test_uncertain_label_never_becomes_negative(self):
        doc = annotation(); doc['events'][0]['certainty'] = 'probable'
        result = evaluate([dict(annotation=doc, alarms=[dict(alarm_s=5.)])])['overall']
        self.assertEqual(result['all_events'], 1)
        self.assertEqual(result['unscored_alarms'], 1)
        self.assertIsNone(event_windows(doc)[0]['label'])
        self.assertIsNone(event_windows(doc)[1]['label'])

    def test_invalid_exposure_clock_duplicate_sessions(self):
        record = dict(annotation=annotation(), alarms=[])
        for negative in ([[0., 3.]], [[12., 16.], [15., 20.]], [[10., 21.]]):
            with self.assertRaises(ValueError):
                evaluate([dict(record, negative_intervals=negative)])
        with self.assertRaises(ValueError):
            evaluate([record, record])
        doc = annotation(); doc['clock']['uncertainty_s'] = .3
        with self.assertRaises(ValueError):
            evaluate([dict(annotation=doc)])

    def test_zero_events_and_poisson_zero_count(self):
        doc = annotation(); doc['events'] = []
        report = evaluate([dict(annotation=doc, negative_intervals=[[0., 20.]])])
        self.assertIsNone(report['overall']['end_to_end_recall'])
        low, high = poisson_interval(0, 1.)
        self.assertEqual(low, 0.)
        self.assertAlmostEqual(high, -math.log(.025), places=10)

    def test_deadline_and_timely_are_separate(self):
        report = evaluate([dict(annotation=annotation(), alarms=[dict(alarm_s=5.8)])])['overall']
        self.assertEqual(report['detected_events'], 1)
        self.assertEqual(report['timely_events'], 0)


class CacheTest(unittest.TestCase):
    def test_alignment_mask_binding_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = annotation(); doc['session'] = 'test_session'
            annotation_path = root/'annotation.json'
            annotation_path.write_text(json.dumps(doc), encoding='utf-8')
            frames = root/'geometry_frames.jsonl'
            values = feed(FallGeometryRuntime([0, 0, 1], 0.), sequence())
            rows = [dict(frame=i, timestamp_s=i/10, geometry=v, binding=['person', 'g1', 'c1'])
                    for i, v in enumerate(values)]
            frames.write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
            summary = dict(session='test_session', frame_schema='fall_geometry_frames_v1',
                           runs=[dict(frames=len(rows))], frames_sha256=file_sha256(frames))
            (root/'SUMMARY.json').write_text(json.dumps(summary), encoding='utf-8')
            result = prepare(frames, annotation_path, root/'cache')
            self.assertEqual(result['windows'][0]['event_start'], 4.)
            self.assertEqual(result['windows'][0]['event_impact'], 4.6)
            self.assertEqual(result['windows'][0]['clock_uncertainty_s'], .1)
            self.assertFalse(result['windows'][1]['supervision_eligible'])
            with np.load(root/'cache/frames.npz', allow_pickle=False) as data:
                self.assertFalse(data['feature_mask'][0, 3])
                self.assertTrue(np.isnan(data['features'][0, 3]))
                self.assertEqual(len(data['bindings']), len(rows))
            frames.write_text(frames.read_text(encoding='utf-8')+'\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'SHA'):
                prepare(frames, annotation_path, root/'bad_cache')


class URProxyTest(unittest.TestCase):
    def test_units_and_no_standing_ratio_leakage(self):
        row = [2., 3., .5, 100., 1., 1800., 1000., .1]
        first = feature_evidence(row)
        self.assertEqual(first['centroid_height_m'], 1.)
        self.assertTrue(first['upright'])
        row[4] = 100000.
        self.assertEqual(first, feature_evidence(row))
        self.assertFalse(feature_evidence([0.] * 8)['valid'])

    def test_sync_uses_real_time_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'sync.csv'
            path.write_text('1,0\n3,110\n', encoding='utf-8')
            self.assertEqual(read_sync(path), {1:0., 3:.11})
            path.write_text('1,0\n1,20\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                read_sync(path)


if __name__ == '__main__':
    unittest.main()
