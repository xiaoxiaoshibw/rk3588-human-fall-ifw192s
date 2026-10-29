import copy
import unittest
import numpy as np
from region_runtime import LiveRegions, RegionRuntime
from project_regions import estimate


class RegionAdapterTest(unittest.TestCase):
    def test_same_existing_estimator_and_source_point_medians(self):
        rng=np.random.RandomState(4)
        p=rng.normal(size=(1000,3))*[.18,.05,.5]+[2,0,1]
        rows=list(range(len(p)))
        expected,_=estimate(p,rows,coordinate_version='RAW/innolidar',session_id='s',
            partition_branch=True,region_contract='target_ground_v1',ground_up=[0,0,1])
        runtime=RegionRuntime('s')
        actual,_,_=runtime.feed(p,rows,0,('s',0),True,[0,0,1])
        self.assertEqual(actual,expected)
        for n in actual['nodes'].values():
            if n['valid']:
                np.testing.assert_array_equal(n['xyz'],np.median(p[n['support_rows']],axis=0))

    def test_no_target_does_not_create_regions_and_prediction_is_rejected(self):
        adapter=LiveRegions()
        state=dict(session_id='s',time_epoch=0,action_generation=0,track_status='unselected',
            position_predicted=False,observability='valid',target_source_rows=[],
            source=dict(seq=1,stamp_secs=12,stamp_nsecs=0,frame_id='innolidar'),
            frame_id='innolidar',calibration=dict(calibration_id='g'),ground=dict(normal=[0,0,1]))
        adapter.process(np.ones((30,3)),dict(state=state))
        self.assertFalse(adapter.state(state)['regions']['observed'])
        self.assertFalse(adapter.state(state)['regions']['nodes'])
        predicted=copy.deepcopy(state);predicted.update(track_status='occluded',position_predicted=True)
        self.assertFalse(adapter.state(predicted)['regions']['observed'])

    def test_invalid_stream_clears_region_calibration_history(self):
        adapter=LiveRegions()
        adapter.runtime=RegionRuntime('s')
        adapter.latest=dict(observed=True)
        out=adapter.state(dict(observability='invalid'))
        self.assertIsNone(adapter.runtime)
        self.assertIsNone(adapter.latest)
        self.assertFalse(out['regions']['observed'])
