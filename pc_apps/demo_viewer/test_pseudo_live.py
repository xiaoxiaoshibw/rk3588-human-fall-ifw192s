import unittest
from pseudo_live import Activity

def obs(i, **changes):
    record=dict(frame=i,time_s=i*.1,generation=0,target_track_id='t1',target_source_rows=[1,2])
    record.update(changes)
    return record

def rule(measured=True, state='unknown', posture='unknown', **changes):
    f=dict(observable=measured,ground_relative=True,height_m={'max':.4},height_median_m=.2,horizontal_extent_m=.8)
    f.update(changes)
    return dict(features=f,state={'state':state},posture={'state':posture})

class ActivityTests(unittest.TestCase):
    def test_low_is_candidate_not_confirmed(self):
        classifier=Activity()
        for i in range(32): result=classifier.update(rule(),obs(i),('source',))
        self.assertEqual(result['label'],'low_horizontal_sustained')
        self.assertFalse(result['confirmed'])
        self.assertEqual(result['human_semantic'],'UNKNOWN')
    def test_missing_track_and_gap_reset(self):
        for replacement in (obs(20,target_source_rows=[]),obs(20,target_track_id='t2'),obs(22),obs(20,time_s=3.0),obs(20,generation=1)):
            classifier=Activity()
            for i in range(20): classifier.update(rule(),obs(i),('source',))
            result=classifier.update(rule(),replacement,('source',))
            self.assertEqual(result['level'],0)
    def test_descent_and_fall_suspected_remain_distinct(self):
        classifier=Activity()
        self.assertEqual(classifier.update(rule(state='descending'),obs(0),('source',))['label'],'descending')
        result=classifier.update(rule(state='suspected'),obs(1),('source',))
        self.assertEqual(result['label'],'fall_suspected')
        self.assertFalse(result['confirmed'])
    def test_missing_observation_never_reuses_old_label(self):
        classifier=Activity()
        classifier.update(rule(posture='standing'),obs(0),('source',))
        self.assertEqual(classifier.update(rule(False,posture='standing'),obs(1),('source',))['label'],'unknown')

if __name__=='__main__': unittest.main()
