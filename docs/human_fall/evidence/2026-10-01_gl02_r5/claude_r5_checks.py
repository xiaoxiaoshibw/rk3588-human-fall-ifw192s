"""GL02 R5 checks: boundary coverage for the two closed root causes.

1. Empty / identical paired reload preserves the full canonical artifact at
   the node entry (metadata content + monitor continuity + pending task).
2. An accepted capture ends with a terminal ack on the *first* frame where the
   monitor is unavailable, and post-recovery sampling cannot stitch pre/post
   failure samples into a ready baseline.
3. A stale/no-new-frame stream settles a pending capture on the receive
   monotonic clock (watchdog path), with a bounded terminal ack, without
   advancing the source-stamp sampling duration.
4. Version-switched reload retires an old target's ready baseline eligibility
   (the artifact history is kept, the eligibility is not inherited).
"""
import copy
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src/human_fall_detection'))
sys.path.insert(0, str(ROOT / 'src/human_fall_detection/tests'))
from core.calibration import build_geometry_calibration
from core.node_runtime import FallNodeCore
from test_gl02_ground_frame import flat_ground, trusted_block
from test_hf07_node import standing_person, settings


def scene_fixture(person=None):
    """The R4 monitor-ok scene: dense trusted plane plus an optional person."""
    xy = np.random.RandomState(13).uniform(-1., 1., (4000, 2))
    floor = np.column_stack([xy, np.full(4000, -1.2)])
    if person is None:
        return floor
    return np.vstack([floor, person])


class R5BoundaryChecks(unittest.TestCase):
    def artifact(self):
        return build_geometry_calibration(
            'v1', '2026-10-01T00:00:00Z', 'innolidar',
            ground=flat_ground(), ground_derived=trusted_block(),
            input_info={'source': 'synthetic_fixture', 'sha256': 'a' * 64,
                        'evidence': 'synthetic input evidence'},
            note='candidate provenance to retain')

    def core(self):
        return FallNodeCore('s1', settings=settings(),
                            calibration=self.artifact())

    def _select_and_capture(self, core):
        person = standing_person(x=1., bottom=-1.2, top=0.3)
        scene = scene_fixture(person)
        out = core.process(scene, 1., seq=1,
                           stamp_secs=100, stamp_nsecs=0)
        self.assertEqual(core.ground_monitor_report['status'], 'ok')
        snap = out['snapshot']
        select = core.handle_request(
            {'schema_version': 1, 'request_id': 'select-r5', 'action': 'select',
             'session_id': 's1', 'time_epoch': 0,
             'snapshot_id': snap['snapshot_id'],
             'candidate_id': snap['candidates'][0]['candidate_id'],
             'selection_version': 0}, 1.01)
        self.assertTrue(select['accepted'])
        ack = core.handle_request(
            {'schema_version': 1, 'request_id': 'baseline-r5',
             'action': 'capture_baseline', 'session_id': 's1',
             'time_epoch': 0, 'selection_version': select['selection_version']},
            1.02)
        self.assertTrue(ack['accepted'])
        self.assertEqual(core.baseline.status, 'pending')
        return person

    def test_empty_reload_preserves_metadata_monitor_and_pending_task(self):
        core = self.core()
        self._select_and_capture(core)
        monitor_before = core.ground_monitor
        before = copy.deepcopy(core.calibration)
        record = core.apply_ground_context()
        self.assertFalse(record['changed'])
        self.assertEqual(core.calibration, before)               # full artifact
        self.assertEqual(core.calibration['input']['sha256'], 'a' * 64)
        self.assertEqual(core.calibration['input']['evidence'],
                         'synthetic input evidence')
        self.assertEqual(core.calibration['note'],
                         'candidate provenance to retain')
        # Bound copy: a later empty reload cannot alias caller-side mutation.
        self.assertIsNot(core.calibration, self.core().calibration)
        # Monitor continuity: same instance, never reset by an unchanged reload.
        self.assertIs(core.ground_monitor, monitor_before)
        self.assertEqual(core.ground_monitor_report['status'], 'ok')
        # In-progress capture and its track binding are kept.
        self.assertEqual(core.baseline.status, 'pending')
        self.assertEqual(core.baseline.track_id, core.tracker.track_id)

    def test_first_bad_frame_cancels_and_recovery_cannot_stitch(self):
        core = self.core()
        person = self._select_and_capture(core)
        track_id = core.baseline.track_id
        calibration_version = core.baseline.calibration_version
        first_bad = core.process(person, 2., seq=2, stamp_secs=101,
                                 stamp_nsecs=0)
        self.assertEqual(core.baseline.status, 'failed')
        self.assertEqual(core.baseline.reason, 'ground_monitor_unavailable')
        ack = first_bad['baseline_ack']
        self.assertIsNotNone(ack)
        self.assertEqual(ack['request_id'], 'baseline-r5')
        self.assertEqual(ack['accepted'], False)
        self.assertEqual(ack['reason'], 'ground_monitor_unavailable')
        self.assertEqual(ack['track_id'], track_id)
        # A failed collection cannot become ready by stitching: rejected
        # feeds leave a failed collector failed (same gate as
        # test_new_selection_invalidates... uses for calibration drift).
        for i in range(3, 12):
            previous = core.baseline.feed(
                {"track_id": track_id,
                 "calibration_version": calibration_version,
                 "ground_relative": True, "point_count": 200,
                 "height_m": {"median": 1.65, "p10": 1.15, "p90": 1.8,
                              "min": 1.05, "max": 1.85},
                 "position_m": [1.0, 0.0, -0.35]},
                source_stamp_s=float(i))
            self.assertEqual(previous['status'], 'failed')
        self.assertEqual(len(core.baseline.samples), 0)

    def test_watchdog_settles_pending_without_new_cloud_frame(self):
        core = self.core()
        self._select_and_capture(core)
        # No new cloud frames: only status_state advances the receive
        # monotonic clock past the stream timeout (0.6 s); the watchdog
        # settles the pending capture without feeding source-stamp samples.
        state = core.status_state(25.0)
        self.assertEqual(core.baseline.status, 'failed')
        self.assertEqual(state['baseline']['status'], 'failed')
        self.assertEqual(state['baseline']['reason'],
                         'ground_monitor_unavailable')
        self.assertIsNotNone(state.get('baseline_ack'))
        self.assertEqual(state['baseline_ack']['request_id'], 'baseline-r5')
        self.assertEqual(state['baseline_ack']['accepted'], False)
        self.assertEqual(state['baseline_ack']['action'], 'capture_baseline')
        self.assertEqual(state['baseline_ack']['idempotent_replay'], False)
        # Receive seconds were not used to advance the sampling window, and
        # no stitched sample exists.
        self.assertEqual(core.baseline.start_source_s, 100.0)
        self.assertEqual(len(core.baseline.samples), 0)

    def test_ready_baseline_retires_on_version_switch_not_on_same_reload(self):
        """Collector-level retire: a changed context retires an old ready
        eligibility; same-version reload keeps it and monitor continuity.

        Drives the collector directly (same pattern as
        test_hf05_tracking.test_new_selection_invalidates_previous_ready_baseline);
        the end-to-end request flow is covered by tests 1–3.
        """
        core = self.core()
        self._select_and_capture(core)          # binds track + monitor ok
        self.assertEqual(core.baseline.status, 'pending')
        track_id = core.baseline.track_id
        calibration_version = core.baseline.calibration_version
        start_source_s = core.baseline.start_source_s
        self.assertIsNotNone(start_source_s)
        for step in range(20):
            core.baseline.feed(
                {"track_id": track_id,
                 "calibration_version": calibration_version,
                 "ground_relative": True, "point_count": 200,
                 "height_m": {"median": 1.65, "p10": 1.15, "p90": 1.8,
                              "min": 1.05, "max": 1.85},
                 "position_m": [1.0, 0.0, -0.35]},
                source_stamp_s=start_source_s + step * 0.2)
        self.assertEqual(core.baseline.status, 'ready',
                         core.baseline.snapshot())
        ready_version = core.baseline.baseline['baseline_version']
        monitor_before = core.ground_monitor
        # Same-version reload keeps the ready eligibility and monitor continuity.
        record = core.apply_ground_context()
        self.assertFalse(record['changed'])
        self.assertEqual(core.baseline.status, 'ready')
        self.assertEqual(core.baseline.baseline['baseline_version'],
                         ready_version)
        self.assertIs(core.ground_monitor, monitor_before)
        # Legal new version of the same geometry retires the old eligibility;
        # the artifact stays in the retired history, never deleted.
        changed = self.artifact()
        changed['calibration_id'] = 'v2'
        record = core.apply_ground_context(calibration=changed)
        self.assertTrue(record['changed'])
        self.assertEqual(core.baseline.status, 'idle')
        self.assertEqual(core.baseline.reason, 'ground_derived_changed')
        self.assertEqual(len(core.baseline.retired), 1)
        self.assertEqual(core.baseline.retired[0]['baseline_version'],
                         ready_version)


if __name__ == '__main__':
    unittest.main(verbosity=2)
