import unittest
import numpy as np
from scipy.spatial import cKDTree
from experiment import D, foreground_mask

class StatisticsTests(unittest.TestCase):
    def record(self, fi, x, valid=True, chest=True):
        return dict(fi=fi,nodes=dict(A=dict(valid=valid,xyz=[x,0,0]),CHEST=dict(valid=chest,xyz=[x,0,0])))
    def test_missing_no_bridge_and_millimeters(self):
        rs=[self.record(0,0),self.record(1,.002),self.record(2,10,False),self.record(3,1)]
        stats=D.vector_stats(rs,'A')
        self.assertEqual(stats['consecutive_pairs'],1);self.assertEqual(stats['max_consecutive_step_mm'],2)
        self.assertEqual(D.vector_stats(rs,'A','CHEST')['rms_position_std_mm'],0)
    def test_missing_chest_null(self):
        self.assertIsNone(D.vector_stats([self.record(0,0,chest=False)],'A','CHEST')['rms_position_std_mm'])
    def test_population_std(self):
        self.assertAlmostEqual(D.vector_stats([self.record(0,0),self.record(1,.002)],'A')['rms_position_std_mm'],1.)
    def test_frozen_background_stationary_and_threshold(self):
        tree=cKDTree(np.array([[0.,0,0]]))
        points=np.array([[.01,0,0],[.06,0,0],[.061,0,0],[.5,0,0]])
        first=foreground_mask(tree,points)[0]
        self.assertEqual(first.tolist(),[False,False,True,True])
        for _ in range(300):self.assertTrue(np.array_equal(first,foreground_mask(tree,points)[0]))
        self.assertFalse(foreground_mask(tree,np.array([[.01,0,0]]))[0][0])

if __name__=='__main__':unittest.main()
