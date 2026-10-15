import unittest
import numpy as np
import yaml
from pathlib import Path
from actions import Posture, choose


class ActionChecks(unittest.TestCase):
    def setUp(self):
        here=Path(__file__).resolve().parent
        self.cfg=yaml.safe_load((here/'config.yaml').read_text())
        self.cfg.update(yaml.safe_load((here/'config_actions.yaml').read_text()))

    def test_initial_lying_is_not_a_fall_and_gap_clears_standing(self):
        standing=np.array([[1,1,z] for z in np.linspace(0,1.8,100)])
        lying=np.array([[x,1,.3] for x in np.linspace(.5,2,100)])
        p=Posture(self.cfg)
        for t in np.arange(0,2,.1):r=p.update(float(t),lying)
        self.assertEqual(r['state'],'INITIAL_LOW_POSTURE');self.assertIsNone(r['event'])
        p.update(2.,standing)
        events=[]
        for t in np.arange(2.1,4.1,.1):events.append(p.update(float(t),lying)['event'])
        self.assertEqual(events.count('DOWN_POSTURE_CANDIDATE'),1)
        r=p.update(6.,lying);self.assertTrue(r['time_reset'])
        for t in np.arange(6.1,8,.1):r=p.update(float(t),lying)
        self.assertEqual(r['state'],'INITIAL_LOW_POSTURE');self.assertFalse(r['confirmed'])

    def test_outside_roi_furniture_cannot_take_target(self):
        person=np.array([[1.6,1.,z] for z in np.linspace(0,1.8,400)])
        furniture=np.array([[4.,4.,z] for z in np.linspace(0,1.8,900)])
        p=np.vstack([person,furniture]);fg=np.arange(len(p))
        selected=choose([np.arange(400),np.arange(400,1300)],p,fg,self.cfg,None,None)
        self.assertEqual(selected[1],0)
        self.assertIsNone(choose([np.arange(400)],p,fg,self.cfg,np.array([8.,8.]),.1))


if __name__=='__main__':unittest.main()
