import io
import unittest
import numpy as np
from render_full_video import POINT_DTYPE, basis, read_xyz, full_panel, target_position, posture, label_position


class FullVideoTest(unittest.TestCase):
    def test_reads_full_source_frame_and_filters_nonfinite(self):
        self.assertEqual(POINT_DTYPE.itemsize, 28)
        data=np.zeros(3,dtype=POINT_DTYPE)
        data['x']=[1,2,np.nan]
        points,count=read_xyz(io.BytesIO(data.tobytes()),{'offset_points':0,'count_points':3},basis([0,0,1]),1.)
        self.assertEqual(count,3)
        np.testing.assert_allclose(points,[[1,0,1],[2,0,1]])
        image,visible=full_panel(points,{'tg':[],'bb':None},(1,0))
        self.assertEqual(image.size,(380,470))
        self.assertEqual(visible,2)
        with self.assertRaises(ValueError):
            read_xyz(io.BytesIO(data.tobytes()[:-1]),{'offset_points':0,'count_points':3},basis([0,0,1]),1.)

    def test_current_target_coordinates_and_state(self):
        row=dict(tid='g0_t0001',n=20,c=[123,-45],hm=1.1,ht=1.7,
                 bb=[70,-80,0,170,-20,165],st='unknown')
        self.assertEqual(target_position(row),[1.23,-.45,1.1])
        self.assertEqual(posture(row,0),'站立候选')
        self.assertEqual(posture(row,1),'疑似倒地')
        self.assertEqual(posture(row,2),'规则确认倒地')
        self.assertTrue(all(label_position(row,(1.0,0.0),i) is not None for i in range(3)))
        self.assertIsNone(target_position(dict(row,tid=None)))
        self.assertIsNone(target_position(dict(row,hm=float('nan'))))
        self.assertEqual(posture(dict(row,n=0),0),'动作未知')


if __name__=='__main__': unittest.main()
