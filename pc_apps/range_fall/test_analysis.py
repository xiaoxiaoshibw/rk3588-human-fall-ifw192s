import copy
import unittest

from analysis import AnalysisStore, content_sha, suspected_intervals, ground_alerts, all_intervals


def row(i=0, **changes):
    r = dict(frameIndex=i, stampSec=100+i*.1, state='suspected', measured=True,
             trackId='T1', generation=0, observationGap=False, sourceRows=[0],
             box=dict(x=1,y=2,w=1,h=1,zMin=0,zMax=1))
    r.update(changes)
    return r


def document(frames):
    d = dict(format='range_fall_analysis', version=1, sessionId='cap_test',
             coordinateFrame='sensor-IFW192S-raw', units='m', sourceFrameCount=10,
             confirmedEnabled=False, semantic='UNKNOWN', frames=frames,
             intervals=suspected_intervals(frames))
    d['contentSha256'] = content_sha(d)
    return d


class TestAnalysis(unittest.TestCase):
    def test_low_posture_is_separate_causal_hint_with_verified_intervals(self):
        frames=[row(i,state='unknown',heightMedianM=.4) for i in range(20)]
        d=document(frames);d['sourceFrameCount']=20
        states,intervals,algorithm=ground_alerts(frames,'ground_alert_v1')
        for r,s in zip(frames,states):r['groundAlert']=s
        d['alertAlgorithm']=algorithm;d['intervals']=all_intervals(frames,intervals)
        d['contentSha256']=content_sha({k:v for k,v in d.items() if k!='contentSha256'})
        AnalysisStore.validate(d)
        self.assertFalse(states[14]['active']);self.assertTrue(states[15]['active'])
        self.assertEqual(intervals[0]['label'],'sustained_low_posture')
        bad=copy.deepcopy(d);bad['frames'][0]['groundAlert']['active']=True
        bad['contentSha256']=content_sha({k:v for k,v in bad.items() if k!='contentSha256'})
        with self.assertRaisesRegex(ValueError,'causality'):AnalysisStore.validate(bad)

    def test_contiguous_suspected_segment(self):
        intervals = suspected_intervals([row(i) for i in range(3)])
        self.assertEqual([(r['startFrame'],r['endFrame']) for r in intervals], [(0,2)])

    def test_missing_frames_identity_and_time_break_intervals(self):
        for frames in ([row(0),row(2)], [row(0),row(1,trackId='T2')],
                       [row(0),row(1,generation=1)], [row(0),row(1,observationGap=True)],
                       [row(0),row(1,stampSec=100)], [row(0),row(1,stampSec=101)]):
            self.assertEqual(len(suspected_intervals(frames)),2)

    def test_unknown_and_missing_are_not_suspected(self):
        self.assertEqual(suspected_intervals([row(0,state='unknown'),row(1,measured=False)]),[])

    def test_integrity_coordinate_confirmation_and_geometry_rejected(self):
        good=document([row()]);AnalysisStore.validate(good)
        bad=copy.deepcopy(good);bad['frames'][0]['trackId']='changed'
        with self.assertRaises(ValueError):AnalysisStore.validate(bad)
        for changes in ({'coordinateFrame':'leveled'},{'units':'cm'},{'confirmedEnabled':True}):
            bad={**good,**changes};bad.pop('contentSha256');bad['contentSha256']=content_sha(bad)
            with self.assertRaises(ValueError):AnalysisStore.validate(bad)
        for r in (row(state='confirmed'),row(measured=False),row(box=dict(x=float('nan')))):
            with self.assertRaises(ValueError):AnalysisStore.validate(document([r]))


if __name__=='__main__':unittest.main()
