"""SYNTHETIC contracts; these are not human/physical evidence."""
import unittest
import numpy as np
from scipy.spatial import cKDTree
from research_retention import ledger, Past, recover


class Contracts(unittest.TestCase):
    def test_duplicate_source_and_terminal_counterfactual(self):
        q=np.array([[1.,0,0],[1.,0,0],[0,0,0],[np.nan,1,1],[20,0,0],[1,0,-1],[1,0,3.]])
        p=q.copy();cfg={'range_min_m':.2,'range_max_m':15,'z_min_m':-.25,'z_max_m':2.6}
        a=ledger(q,p,cKDTree([[1,0,0],[1,0,-1]]),.06,cfg,[],np.array([],int),np.array([],int))
        self.assertEqual(a['first_terminal_reason'].tolist(),[6,6,2,1,3,4,5])
        self.assertTrue(a['overlapping_predicates'][5] & 32)
        self.assertFalse(a['reached_stage_bits'][5] & 32)
        self.assertEqual(len(a['first_terminal_reason']),len(q))
    def test_history_reset_expiry_and_no_inherited_refresh(self):
        cfg={'max_gap_s':.5,'past_age_s':.4,'past_frames':4,'past_radius_m':.1}
        for next_t,identity in [(0.,'A'),(.1,'B'),(.6,'A'),(.1,None)]:
            h=Past(cfg);h.reset(.05,'A');h.append(.05,0,np.array([[1.,1,1]]));h.reset(next_t,identity)
            self.assertFalse(h.frames)
        h=Past(cfg);h.reset(0,'A');h.append(0,0,np.array([[1.,1,1]]));h.reset(.45,'A');self.assertFalse(h.frames)
    def test_current_background_only_and_no_target_no_recovery(self):
        p=np.array([[1.,1,1],[1.02,1,1],[4.,4,4]])
        cfg={'attachment_m':.1,'minimum_anchor_neighbors':1,'maximum_fit_coverage':10,'roi_xy':[[0,0],[2,0],[2,2],[0,2]],'max_gap_s':.5,'past_age_s':.4,'past_frames':4,'past_radius_m':.1}
        h=Past(cfg);h.reset(.1,'A');h.append(.1,0,p[:1]);h.reset(.2,'A')
        pool,added,_=recover(p,np.array([0]),np.array([1,2]),cfg,np.array([0,0,1]),np.array([0,33]),h,'combined')
        self.assertEqual(pool.tolist(),[1]);self.assertEqual(added.tolist(),[1])
        self.assertEqual(len(recover(p,np.array([],int),np.array([1]),cfg,np.array([0,0,1]),np.array([0,33]),h,'local')[1]),0)


if __name__=='__main__':unittest.main()
