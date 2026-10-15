import unittest
import numpy as np
from experiment_actions import AxisHistory, recover, supported_regions
from research_actions import read, HERE, OUT


class ResearchChecks(unittest.TestCase):
    def setUp(self):
        self.cfg = read(OUT/'RUN_MANIFEST.json')['config']
        self.cfg.update(read(HERE/'config_research_r2.json'))

    def test_single_attachment_no_floor_roi_or_cascade(self):
        cfg = dict(self.cfg, roi_xy=[[0, 0], [1, 0], [1, 1], [0, 1]])
        p = np.array([[.5,.5,.2],[.6,.5,.2],[.72,.5,.2],[.8,.5,.2],[.55,.5,-.01],[1.1,.5,.2]])
        ids, reasons = recover(p,np.array([0,1]),np.arange(6),[],np.ones(6),.055,cfg,cfg['variants']['point12'])
        self.assertEqual(ids.tolist(),[0,1,2]);self.assertEqual(reasons[0]['anchor_source_index'],1)
        self.assertTrue(all(r['above_frozen_tolerance'] and r['within_original_roi'] for r in reasons))
        empty, records = recover(p,np.array([],dtype=int),np.arange(6),[],np.ones(6),.055,cfg,cfg['variants']['low20'])
        self.assertEqual(len(empty),0);self.assertFalse(records)

    def test_axis_reference_expires_gap_loss_identity_and_no_future(self):
        rng=np.random.default_rng(42)
        p=np.column_stack([rng.uniform(-.9,.9,1000),rng.uniform(-.10,.10,1000),rng.uniform(.15,.25,1000)])
        broad=np.column_stack([rng.uniform(-.8,.8,1000),rng.uniform(-.7,.7,1000),rng.uniform(.15,.25,1000)])
        ids=np.arange(1000);h=AxisHistory(self.cfg)
        r=h.update(0.,0,'A',p,ids);self.assertIn('axis',r)
        r=h.update(.1,1,'A',broad,ids)
        self.assertEqual(r['direction']['source'],'PAST_DIRECTION_CURRENT_SUPPORT')
        self.assertEqual(r['direction']['reference']['fi'],0)
        for n in r['nodes'].values():
            if n['valid']:
                self.assertTrue(set(n['support_source_indices'])<=set(ids))
                np.testing.assert_allclose(n['xyz'],broad[n['support_source_indices']].mean(axis=0))
            else:self.assertIsNone(n['xyz'])
        self.assertFalse(r['predicted_nodes'])
        for t,fi in [(.2,2),(.3,3),(.4,4),(.6,5)]:r=h.update(t,fi,'A',broad,ids)
        self.assertEqual(r['direction']['source'],'MISSING')
        self.assertFalse(any(n['valid'] for n in r['nodes'].values()))
        h.update(.7,6,'A',p,ids)
        r=h.update(1.5,7,'A',broad,ids);self.assertEqual(r['direction']['source'],'MISSING')
        h.update(1.6,8,'A',p,ids)
        r=h.update(1.7,9,'B',broad,ids);self.assertEqual(r['direction']['source'],'MISSING')
        h.update(1.8,10,'B',p,ids);h.update(1.9,11,None,p[:0],ids[:0])
        r=h.update(2.,12,'B',broad,ids);self.assertEqual(r['direction']['source'],'MISSING')

    def test_regions_same_frozen_rules_for_reliable_axis(self):
        from core import skeleton
        rng=np.random.default_rng(11);p=np.column_stack([rng.uniform(-.15,.15,1000),rng.uniform(-.1,.1,1000),rng.uniform(.1,1.8,1000)])
        ids=np.arange(1000);old=skeleton(p,ids,self.cfg);new=supported_regions(p,ids,np.array(old['axis']),self.cfg)
        self.assertEqual(old['nodes'].keys(),new['nodes'].keys())
        for k in old['nodes']:
            self.assertEqual(old['nodes'][k]['support_source_indices'],new['nodes'][k]['support_source_indices'])


if __name__=='__main__':unittest.main()
