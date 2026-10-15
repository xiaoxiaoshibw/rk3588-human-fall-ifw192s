"""SYNTHETIC boundary tests; physical identity is never asserted."""
import unittest
import numpy as np
from experiment_r3 import Past, graph_groups, recover_r3, axis_r3, AxisHistory, read, HERE, OUT
from axis_sign_r3 import AxisSign

def config():
    cfg=read(OUT/'RUN_MANIFEST.json')['config'];cfg.update(read(HERE/'config_research_r2.json'));cfg.update(read(HERE/'config_research_r3.json'));return cfg

class R3Tests(unittest.TestCase):
    def test_graph_separates_disconnected_tail(self):
        q=np.array([[0,0,0],[.1,0,0],[1,0,0],[1.1,0,0]])
        groups=graph_groups(q,np.arange(4),config())
        self.assertEqual([g.tolist() for g in groups],[[0,1],[2,3]])

    def test_past_strict_causal_bounded_resets(self):
        past=Past(config());q=np.array([[1.,1.,.5]])
        past.reset(0,'A');past.append(0,0,'A',q,np.array([0]),np.array([0]))
        past.reset(.1,'A');self.assertEqual(past.evidence(q)[0]['fi'],0)
        past.reset(.6,'A');self.assertFalse(past.frames)
        past.append(.6,6,'A',q,np.array([0]),np.array([0]));past.reset(.7,'B');self.assertFalse(past.frames)
        past.append(.7,7,'B',q,np.array([0]),np.array([0]));past.reset(.7,'B');self.assertFalse(past.frames)

    def test_only_current_fg_unknown_no_deleted_background(self):
        cfg=config();cfg['roi_xy']=[[-2,-2],[2,-2],[2,2],[-2,2]]
        q=np.array([[0,0,.4],[.05,0,.4],[.15,0,.4],[.16,0,.4]])
        ids=np.array([0,1]);fg=np.array([0,1,2]);dist=np.array([.2,.2,.2,.01]);past=Past(cfg)
        past.reset(0,'A');past.append(0,0,'A',q,np.array([0,1,2]),fg);past.reset(.1,'A')
        members,records,_=recover_r3(q,ids,fg,[],dist,.05,cfg,[False,True,True,False],past)
        self.assertEqual(members.tolist(),[0,1,2]);self.assertNotIn(3,members)
        self.assertTrue(all(r['identity']=='UNKNOWN' for r in records))
        empty,_,_=recover_r3(q,np.array([],dtype=int),fg,[],dist,.05,cfg,[True,True,True,True],past)
        self.assertEqual(len(empty),0)

    def test_axis_has_current_source_support(self):
        cfg=config();rng=np.random.default_rng(42);q=rng.normal(0,.025,(120,3));q[:,2]=np.linspace(.2,1.8,120)
        ids=np.arange(len(q));sk=axis_r3(q,ids,ids,cfg,AxisHistory(cfg),0,0,'A')
        self.assertEqual(sk['predicted_nodes'],[])
        for n in sk['nodes'].values():
            if n['valid']:
                self.assertTrue(set(n['support_source_indices'])<=set(ids))
                np.testing.assert_allclose(n['xyz'],q[n['support_source_indices']].mean(axis=0))

    def test_sign_reference_never_refreshed_by_carried_axis(self):
        cfg=config();rng=np.random.default_rng(7);q=rng.normal(0,.025,(120,3));q[:,2]=np.linspace(.2,1.8,120);ids=np.arange(120)
        sk=axis_r3(q,ids,ids,cfg,AxisHistory(cfg),0,0,'A');sign=AxisSign(cfg)
        first=sign.update(0,0,'A',sk,q,ids);self.assertIsNone(first['orientation']['reference'])
        import copy
        carried=copy.deepcopy(sk);carried['direction']['source']='CURRENT_BASE_OR_BOUNDED_PAST_DIRECTION';carried['axis']=(-np.array(sk['axis'])).tolist()
        fixed=sign.update(.1,1,'A',carried,q,ids);self.assertTrue(fixed['orientation']['flipped']);self.assertEqual(sign.reference['t_sec'],0)
        for n in fixed['nodes'].values():
            if n['valid']:np.testing.assert_allclose(n['xyz'],q[n['support_source_indices']].mean(axis=0))
        expired=sign.update(.6,6,'A',carried,q,ids);self.assertIsNone(expired['orientation']['reference']);self.assertIsNone(sign.reference)
        sign.update(.7,7,'A',sk,q,ids);reset=sign.update(.8,8,'B',sk,q,ids);self.assertIsNone(reset['orientation']['reference'])

if __name__=='__main__':unittest.main()
