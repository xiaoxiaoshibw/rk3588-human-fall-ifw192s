"""Automatic floor identity checks: dominant table, mixed-height cells and missing floor."""
import unittest
import numpy as np
from floor_detector import detect_floor_regions
from leveling_quality import rotation


def scene(table=True, floor=True):
    rng = np.random.RandomState(33); chunks, ids = [], []
    for frame in range(3):
        if floor:
            chunks.append(np.column_stack([rng.uniform(0,4,18000),rng.uniform(-2,2,18000),rng.normal(0,.002,18000)]))
            ids.append(np.full(18000,frame))
        if table:
            chunks.append(np.column_stack([rng.uniform(1,2.5,60000),rng.uniform(-.75,.75,60000),rng.normal(.75,.002,60000)]))
            ids.append(np.full(60000,frame))
        # A person shares the same XY as floor; this whole XY cell must be excluded.
        chunks.append(np.column_stack([rng.uniform(.45,.7,1200),rng.uniform(.45,.7,1200),rng.uniform(0,1.7,1200)]))
        ids.append(np.full(1200,frame))
    points = np.vstack(chunks)
    return (points - [0,0,1.3]) @ rotation(26,0), np.concatenate(ids), points


class FloorDetectorTest(unittest.TestCase):
    def test_dense_table_never_wins_and_mixed_height_cells_are_not_ground(self):
        points, ids, display = scene()
        result = detect_floor_regions(points,ids,26,0)
        self.assertAlmostEqual(result["candidate"]["offset_source_m"],1.3,delta=.04)
        self.assertFalse(result["candidate"]["uses_manual_reference"])
        for xl,xh,yl,yh in result["regions"]:
            chosen = display[(display[:,0]>=xl)&(display[:,0]<xh)&(display[:,1]>=yl)&(display[:,1]<yh)]
            self.assertGreater(len(chosen),90)
            self.assertLess(np.ptp(chosen[:,2]),.18)
            self.assertLess(np.max(chosen[:,2]),.03)

    def test_table_without_visible_floor_is_rejected(self):
        points, ids, _ = scene(floor=False)
        with self.assertRaisesRegex(ValueError,"floor_(not_found|regions_invalid)"):
            detect_floor_regions(points,ids,26,0)

    def test_scattered_small_patches_do_not_make_four_arbitrary_floor_boxes(self):
        rng=np.random.RandomState(9)
        display=np.vstack([np.column_stack([rng.uniform(x,x+.45,500),rng.uniform(y,y+.45,500),rng.normal(0,.002,500)])
                           for x,y in ((0,0),(2,0),(0,2),(2,2))])
        with self.assertRaisesRegex(ValueError,"floor_regions_invalid"):
            detect_floor_regions((display-[0,0,1.3])@rotation(26,0),np.zeros(len(display),dtype="i4"),26,0)


if __name__ == "__main__":
    unittest.main()
