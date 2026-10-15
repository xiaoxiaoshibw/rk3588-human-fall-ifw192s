"""SYNTHETIC guard contracts, not identity or physical evidence."""
import unittest
from unittest.mock import patch
import numpy as np
import research_retention_guard as guard


class GuardContracts(unittest.TestCase):
    def evaluate(self,p,anchor,added):
        cfg={'guard_anchor_fraction_min':.85,'guard_center_max_m':.12,'guard_axis_change_max_deg':30}
        with patch.object(guard,'_recover',return_value=(added,added,{})):
            return guard.guarded_recover(p,anchor,added,cfg,None,None,None,'combined')

    def test_whole_proposal_rejected_by_independent_anchor_budget(self):
        p=np.column_stack([np.ones(30),np.ones(30),np.linspace(0,1,30)])
        _,kept,ev=self.evaluate(p,np.arange(10),np.arange(10,30))
        self.assertFalse(len(kept));self.assertIn('INSUFFICIENT_INDEPENDENT_ANCHOR_FRACTION',ev['guard_reasons'])

    def test_center_guard_with_sufficient_anchor_fraction(self):
        p=np.column_stack([np.ones(16),np.ones(16),[0]*7+[3]*7+[0,0]])
        _,kept,ev=self.evaluate(p,np.arange(14),np.arange(14,16))
        self.assertFalse(len(kept));self.assertIn('EXCESS_MEDIAN_CENTER_SHIFT',ev['guard_reasons'])

    def test_bounded_proposal_unchanged(self):
        p=np.column_stack([np.ones(16),np.ones(16),np.linspace(.9,1.,16)])
        _,kept,ev=self.evaluate(p,np.arange(14),np.arange(14,16))
        self.assertEqual(kept.tolist(),[14,15]);self.assertFalse(ev['guard_reasons'])


if __name__=='__main__':unittest.main()
