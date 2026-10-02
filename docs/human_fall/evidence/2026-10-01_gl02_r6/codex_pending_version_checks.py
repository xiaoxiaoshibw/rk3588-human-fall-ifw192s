"""GL02 v1 request matrix: settle an accepted capture on context switching."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'docs/human_fall/evidence/2026-10-01_gl02_r5_codex'))
import codex_r5_lifecycle_checks as lifecycle


class PendingVersionChecks(unittest.TestCase):
    def test_changed_context_returns_original_capture_terminal_before_clear(self):
        helper = lifecycle.LifecycleChecks()
        core, person, scene, request, accepted = helper.setup_capture()
        prior_epoch = core.cloud_timebase.time_epoch
        new = copy.deepcopy(core.calibration)
        new['calibration_id'] = 'v2'
        result = core.apply_ground_context(calibration=new)
        self.assertTrue(result['changed'])
        self.assertEqual(core.baseline.status, 'idle')
        self.assertIsNone(core.tracker.track_id)
        self.assertEqual(core.cloud_timebase.time_epoch, prior_epoch)
        # This explicit pure API has no ROS reload caller: the lifecycle return
        # must expose the terminal receipt before throwing away the old binding.
        # Also accept the existing status channel as the bounded delivery path.
        terminal = result.get('baseline_ack') or core.status_state(1.03).get('baseline_ack')
        self.assertIsNotNone(terminal, 'context reset silently erased an accepted request')
        self.assertEqual(terminal['kind'], 'selection_ack')
        self.assertEqual(terminal['request_id'], request['request_id'])
        self.assertEqual(terminal['track_id'], accepted['track_id'])
        self.assertFalse(terminal['accepted'])
        self.assertEqual(terminal['baseline']['status'], 'failed')
        self.assertIsNotNone(terminal['reason'])
        self.assertIsNone(core.status_state(1.04).get('baseline_ack'))

    def test_same_context_pending_stays_pending_and_invalid_switch_is_atomic(self):
        helper = lifecycle.LifecycleChecks()
        core, person, scene, request, accepted = helper.setup_capture()
        result = core.apply_ground_context()
        self.assertFalse(result['changed'])
        self.assertIsNone(result.get('baseline_ack'))
        self.assertEqual(core.baseline.status, 'pending')
        self.assertEqual(core._baseline_request_id, request['request_id'])
        malformed = copy.deepcopy(core.calibration)
        malformed['calibration_id'] = None
        with self.assertRaises(ValueError):
            core.apply_ground_context(calibration=malformed)
        self.assertEqual(core.baseline.status, 'pending')
        self.assertEqual(core._baseline_request_id, request['request_id'])
        self.assertEqual(core.calibration['calibration_id'], 'v1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
