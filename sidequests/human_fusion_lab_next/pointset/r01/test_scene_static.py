import unittest
from pathlib import Path
import numpy as np
import yaml
from core import cluster
from scene_static import static_reference_mask, change_proposals


class StaticSceneTest(unittest.TestCase):
    def test_protected_roi_and_all_current_3d_proposals(self):
        h=Path(__file__).parent
        cfg=yaml.safe_load((h/'config.yaml').read_text(encoding='utf8'))
        grid=np.array([[x,y,z] for x in np.arange(0,.35,.05) for y in np.arange(0,.35,.05) for z in np.arange(0,.2,.05)])
        p=np.concatenate((grid,grid+[0,0,1.]))
        cfg['roi_xy']=[[-.1,-.1],[.5,-.1],[.5,.5],[-.1,.5]]
        protected=static_reference_mask(p,np.ones(len(p),bool),cfg['roi_xy'])
        self.assertFalse(protected.any())
        outside=np.array([[1.,1.,1.]])
        self.assertTrue(static_reference_mask(outside,[True],cfg['roi_xy'])[0])
        fg=np.arange(len(p));groups,_=cluster(p,cfg)
        proposals=change_proposals(p,fg,groups,cfg,np.ones(len(p)),.055,[])
        self.assertEqual(len(proposals),2)
        ids=[i for row in proposals for i in row['source_indices']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(set(ids),set(fg))
        self.assertTrue(all(row['semantic_identity']=='UNKNOWN' for row in proposals))
        self.assertTrue(all(not n['valid'] for row in proposals for n in row['skeleton']['nodes'].values()))
        self.assertEqual(change_proposals(np.empty((0,3)),np.empty(0,int),[],cfg,np.empty(0),.055,[]),[])


if __name__=='__main__':unittest.main()
