"""DET-06 regression: final-box threshold/NMS/cap, center matching boundary, FP bookkeeping. Synthetic only."""
import unittest

import numpy as np

from det06_metrics import final_boxes, frame_stats


def make_trace(scores):
    aid = np.arange(len(scores), dtype='i8')
    sc = np.zeros((len(scores), 3), dtype='f4')
    sc[:, 0] = scores
    boxes = np.zeros((len(scores), 7), dtype='f4')
    boxes[:, 0] = [2.0, 2.05, 5.0, 2.0][:len(scores)]
    boxes[:, 3] = 1.0
    boxes[:, 4] = 1.0
    return dict(anchor_ids=aid, raw_cls_scores=sc, decoded_boxes=boxes,
                top100=aid.copy(), rank=np.arange(len(scores)), anchors=boxes)


class TestFinalBoxes(unittest.TestCase):
    def test_threshold_nms_and_order(self):
        tr = make_trace([.9, .8, .3, .05])
        out = final_boxes(tr, .1)
        self.assertEqual([round(float(v), 3) for v in out[:, 7]], [.9, .3])  # .8 suppressed by .9; .05 below tau
        out5 = final_boxes(tr, .5)
        self.assertEqual([round(float(v), 3) for v in out5[:, 7]], [.9])
        self.assertTrue((np.diff(out[:, 7]) <= 0).all())  # descending scores

    def test_empty_when_all_below(self):
        tr = make_trace([.09, .05, .04, .01])
        self.assertEqual(len(final_boxes(tr, .1)), 0)


class TestMatching(unittest.TestCase):
    def test_center_boundary_and_fp(self):
        boxes = np.zeros((3, 8))
        boxes[:, 0] = [2.0, 2.5501, 5.0]
        boxes[:, 7] = [.9, .8, .7]
        st = frame_stats(boxes, [2.0, 0.0], None)
        self.assertEqual((st['tp'], st['fp']), (1, 2))  # 2.0 matches; 2.5501 just outside; 5.0 far
        boxes2 = boxes.copy()
        boxes2[1, 0] = 2.55  # exactly 0.55 -> inside
        st2 = frame_stats(boxes2, [2.0, 0.0], None)
        self.assertEqual((st2['tp'], st2['fp']), (1, 1))
        st3 = frame_stats(np.zeros((0, 8)), [0, 0], None)
        self.assertEqual((st3['tp'], st3['fp']), (0, 0))


if __name__ == '__main__':
    unittest.main()
