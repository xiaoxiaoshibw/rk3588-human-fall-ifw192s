import unittest
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.range_skeleton import estimate, project_regions


class TestSkeleton(unittest.TestCase):
    def test_support_rotation_missing_and_invalid(self):
        rng = np.random.RandomState(7)
        points = rng.normal(size=(900,3))*[.17,.04,.5]
        rows = list(range(1000,1900))
        pose = estimate(points, rows)
        self.assertTrue(pose['edges'])
        for n in pose['nodes'].values():
            ids = [r-1000 for r in n['sourceRows']]
            np.testing.assert_array_equal(n['xyz'], np.median(points[ids],axis=0))
            self.assertEqual(n['supportCount'],len(ids))
        # Horizontal support rotates with the target, not an upright stick figure.
        rotated = points[:,[2,1,0]]
        horizontal = estimate(rotated, rows)
        for key in pose['nodes']:
            np.testing.assert_allclose(horizontal['nodes'][key]['xyz'],np.array(pose['nodes'][key]['xyz'])[[2,1,0]],atol=1e-10)
        self.assertEqual(estimate([],[])['nodes'],{})
        self.assertEqual(estimate([[float('nan'),0,0]]*40,list(range(40)))['nodes'],{})
        sphere = np.array([[s if j==i else 0 for j in range(3)] for i in range(3) for s in [-1,1]]*20)
        self.assertEqual(estimate(sphere,list(range(len(sphere))))['reason'],'ambiguous_axis')
        with self.assertRaises(ValueError):estimate(points,[1]*len(points))
        with self.assertRaises(ValueError):estimate(points,[-1]+rows[1:])
        self.assertEqual(pose['anatomicalJoints'],'UNKNOWN')

    def test_pixel_support_uses_rotated_native_indices(self):
        from types import SimpleNamespace
        frame=SimpleNamespace(valid=np.ones((3,4),dtype=bool),source_rows=np.arange(12).reshape(3,4))
        pose=dict(nodes=dict(TOP=dict(sourceRows=[0,1,4,5],supportCount=4)))
        project_regions(pose,frame)
        self.assertEqual(pose['nodes']['TOP']['imageXY'],[2.5,1.5])
        frame.valid[0,0]=False
        with self.assertRaises(ValueError):project_regions(pose,frame)


if __name__ == '__main__':unittest.main()
