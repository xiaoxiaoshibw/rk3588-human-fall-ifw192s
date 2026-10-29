import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src/human_fall_detection'))
sys.path.insert(0, str(ROOT/'src/human_fall_detection/scripts'))
sys.path.insert(0, str(ROOT/'src/human_follow_calibration/scripts'))
from core.node_runtime import LatestFrameQueue, FallNodeCore
from core.lidar_candidates import build_snapshot
from core.pipeline import ReplayPipeline
from core.baseline import StanceBaselineCollector
from core.association import associate_tracks
from core.tracking import TargetTracker
from human_fall_node import publish_json
from calibrate_human_follow import xyz_from_cloud
from test_hf07_node import VALID_GROUND
from test_human_entry_gate import candidate


def message(points):
    return SimpleNamespace(header=SimpleNamespace(seq=7, frame_id='innolidar',
        stamp=SimpleNamespace(secs=100,nsecs=123)), width=len(points), height=1,
        row_step=len(points)*12, point_step=12, data=np.asarray(points,dtype='<f4').tobytes(),
        is_bigendian=False, fields=[SimpleNamespace(name=n,offset=i*4,count=1,datatype=7)
                                   for i,n in enumerate(('x','y','z'))])


class Diagnostics(unittest.TestCase):
    def test_overwrites_record_actual_source_headers_not_just_count(self):
        q = LatestFrameQueue()
        a = message([[1,2,3]])
        q.put((1., a))
        q.put((2., message([[2,3,4]])))
        self.assertEqual(q.dropped, 1)
        lost = q.drain_overwritten()
        self.assertEqual(lost['headers'][0], dict(seq=7,stamp_secs=100,stamp_nsecs=123,
                                                frame_id='innolidar',receive_s=1.))
        self.assertEqual(q.drain_overwritten()['headers'], [])

    def test_online_decode_keeps_original_row_for_candidate_and_region_indexing(self):
        cloud = message([[2,0,-1.], [float('nan'),0,0], [2,0,-.6], [2,0,-.2]])
        decoded = xyz_from_cloud(cloud, 0, preserve_rows=True)
        snap = build_snapshot(decoded, dict(denoise_enabled=False,min_cluster_points=1,
            cluster_cell_m=.5),ground=VALID_GROUND,session_id='decode',time_epoch=0,snapshot_id='7')
        rows = sorted(r for c in snap['candidates'] for r in c['evidence_indices'])
        self.assertEqual(rows, [0,2,3])
        np.testing.assert_allclose(decoded[rows], [[2,0,-1.],[2,0,-.6],[2,0,-.2]])

    def test_timings_additive_finite_and_json_publication_measured(self):
        core = FallNodeCore('timing',ground=VALID_GROUND)
        result = core.process(np.empty((0,3)),100.,seq=1,stamp_secs=100,stamp_nsecs=0,now=100.)
        self.assertTrue(all(np.isfinite(v) and v>=0 for v in result['timings_s'].values()))
        sent=[]
        publisher=SimpleNamespace(publish=sent.append)
        measured=publish_json(publisher,result['state'],SimpleNamespace)
        self.assertEqual(len(sent),1)
        self.assertTrue(all(v>=0 for v in measured.values()))

    def test_size_ratio_is_inactive_in_tracker_and_strict_ratio_loses_partial_support(self):
        a = candidate(); b = candidate(); b['horizontal_extent_m']['max']=.1
        tracker=TargetTracker('size')
        tracker.select('t',0,candidate=a,source_stamp_s=0.)
        self.assertEqual(tracker.update([b],0,source_stamp_s=.1)['track_status'],'locked')
        strict=associate_tracks([dict(track_id='t',position_m=[2.,0.,.85],size_m=.5)],
            [dict(candidate_id='b',position_m=[2.,0.,.85],size_m=.1)],.1)
        self.assertFalse(strict['matches'])

    def test_shared_baseline_checks_moving_stance_and_height_jitter(self):
        track=dict(track_id='t',time_epoch=0,selection_version=1,action_generation=1,
                   calibration_version='g',track_status='locked',position_predicted=False)
        for cause in ('position','height'):
            collector=StanceBaselineCollector('s')
            for i in range(40):
                c=candidate(x=2.+i*.1 if cause=='position' else 2.)
                if cause=='height':c['height_m']['median']=.85+(.2 if i%2 else -.2)
                collector.feed_automatic(c,track,i*.1)
                self.assertIsNone(collector.baseline)
        collector=StanceBaselineCollector('s')
        for i in range(40):collector.feed_automatic(candidate(),track,i*.1)
        self.assertIsNotNone(collector.baseline)
        track['action_generation']=2
        collector.feed_automatic(candidate(),track,4.)
        self.assertIsNone(collector.baseline)


if __name__ == '__main__':unittest.main()
