"""Diagnostics must describe the gate actually blocking recovery."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_identity_recovery as recovery
from test_human_entry_gate import candidate


class RecoveryDiagnostics(unittest.TestCase):
    def test_exceeded_residual_never_reports_verification(self):
        a = recovery.IdentityRecovery().start()
        a.step([], 0, 3.5)
        for stamp in (4.4, 4.5, 4.6):
            _, state, observed = a.step([candidate('return', x=4.44)], 0, stamp)
            self.assertIsNone(observed)
            self.assertIsNone(a._recovery)
            self.assertEqual(state['rejected']['return'], 'recovery_residual_exceeded')

    def test_competition_does_not_accumulate_verification(self):
        a = recovery.IdentityRecovery().start()
        a.step([], 0, 3.5)
        _, state, observed = a.step([candidate('left', x=3.39), candidate('right', x=3.49)], 0, 4.4)
        self.assertIsNone(observed)
        self.assertIsNone(a._recovery)
        self.assertEqual(set(state['rejected'].values()), {'recovery_candidate_competition'})

    def test_unique_in_gate_candidate_really_accumulates(self):
        a = recovery.IdentityRecovery().start()
        a.step([], 0, 3.5)
        for count, stamp in enumerate((4.4, 4.5), 1):
            _, state, observed = a.step([candidate('return', x=3.44)], 0, stamp)
            self.assertIsNone(observed)
            self.assertEqual(a._recovery['frames'], count)
            self.assertEqual(state['rejected']['return'], 'recovery_verification_pending')
