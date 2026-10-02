"""Independent R4 reload and pending-baseline boundary checks."""
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


class ReloadChecks(unittest.TestCase):
    def core(self):
        artifact = build_geometry_calibration(
            'v1', '2026-10-01T00:00:00Z', 'innolidar',
            ground=flat_ground(), ground_derived=trusted_block(),
            input_info={'source': 'synthetic_fixture', 'sha256': 'a' * 64,
                        'evidence': 'synthetic input evidence'},
            note='candidate provenance to retain')
        return FallNodeCore('s1', settings=settings(), calibration=artifact)

    def test_empty_reload_preserves_full_canonical_artifact(self):
        core = self.core()
        before = copy.deepcopy(core.calibration)
        record = core.apply_ground_context()
        self.assertFalse(record['changed'])
        self.assertEqual(core.calibration, before)

    def test_identical_paired_reload_preserves_full_canonical_artifact(self):
        core = self.core()
        before = copy.deepcopy(core.calibration)
        record = core.apply_ground_context(ground=copy.deepcopy(core.ground),
                                           ground_derived=copy.deepcopy(core.ground_derived))
        self.assertFalse(record['changed'])
        self.assertEqual(core.calibration, before)

    def test_accepted_pending_request_does_not_hang_after_monitor_loss(self):
        core = self.core()
        xy = np.random.RandomState(13).uniform(-1., 1., (4000, 2))
        floor = np.column_stack([xy, np.full(4000, -1.2)])
        person = standing_person(x=1., bottom=-1.2, top=.3)
        out = core.process(np.vstack([floor, person]), 1., seq=1,
                           stamp_secs=100, stamp_nsecs=0)
        self.assertEqual(core.ground_monitor_report['status'], 'ok')
        snap = out['snapshot']
        ack = core.handle_request({'schema_version': 1, 'request_id': 'select-r4',
            'action': 'select', 'session_id': 's1', 'time_epoch': 0,
            'snapshot_id': snap['snapshot_id'],
            'candidate_id': snap['candidates'][0]['candidate_id'],
            'selection_version': 0}, 1.01)
        self.assertTrue(ack['accepted'])
        ack = core.handle_request({'schema_version': 1, 'request_id': 'baseline-r4',
            'action': 'capture_baseline', 'session_id': 's1', 'time_epoch': 0,
            'selection_version': ack['selection_version']}, 1.02)
        self.assertTrue(ack['accepted'])
        completions = []
        for i in range(1, 21):
            out = core.process(person, 1. + i, seq=1 + i,
                               stamp_secs=100 + i, stamp_nsecs=0)
            if out.get('baseline_ack') is not None:
                completions.append(out['baseline_ack'])
        self.assertNotEqual(core.baseline.status, 'pending')
        self.assertTrue(any(item.get('request_id') == 'baseline-r4'
                            and item.get('accepted') is False
                            for item in completions))


if __name__ == '__main__':
    unittest.main(verbosity=2)
