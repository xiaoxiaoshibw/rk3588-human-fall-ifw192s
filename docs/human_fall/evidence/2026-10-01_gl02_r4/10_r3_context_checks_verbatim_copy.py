"""Independent GL02 R3 checks across supported context/request entry points."""
import copy
import sys
import unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'src/human_fall_detection'))
sys.path.insert(0,str(ROOT/'src/human_fall_detection/tests'))
from core.calibration import build_geometry_calibration
from core.node_runtime import FallNodeCore
from core.ground import GroundMonitor
from test_gl02_ground_frame import flat_ground, trusted_block
from test_hf07_node import standing_person, settings


class ContextChecks(unittest.TestCase):
    def test_minor_one_sided_obstacle_is_not_whole_ground_shift(self):
        xy=np.random.RandomState(4).uniform(-1.,1.,(400,2))
        z=np.full(400,-1.2)
        z[:40]=-.9  # original ground unchanged; 10 percent object occlusion
        monitor=GroundMonitor()
        for _ in range(10):
            report=monitor.feed(np.column_stack([xy,z]),trusted_block())
        self.assertGreaterEqual(report['support_fraction'],.8)
        self.assertNotEqual(report['status'],'recalibration_required')

    def artifact(self,version='v1',height=1.2):
        return build_geometry_calibration(version,'2026-10-01T00:00:00Z',
            'innolidar',ground=flat_ground(height),ground_derived=trusted_block(height))

    def core(self):
        a=self.artifact()
        return FallNodeCore('s1',settings=settings(),calibration=a)

    def test_paired_context_publishes_its_actual_derived_version(self):
        core=self.core()
        g,b=flat_ground(1.4),trusted_block(1.4)
        core.apply_ground_context(ground=g,ground_derived=b)
        xy=np.random.RandomState(3).uniform(-1.,1.,(200,2))
        p=np.column_stack([xy,np.full(200,-1.4)])
        out=core.process(p,1.,seq=1,stamp_secs=100,stamp_nsecs=0)
        self.assertEqual(out['snapshot']['calibration']['ground_derived_id'],
                         core._ground_derived_id)

    def test_paired_context_is_detached_from_caller_mutation(self):
        core=self.core()
        g,b=flat_ground(1.4),trusted_block(1.4)
        core.apply_ground_context(ground=g,ground_derived=b)
        g['offset_m']=99.
        b['t'][2]=99.
        self.assertAlmostEqual(core.ground['offset_m'],1.4)
        self.assertAlmostEqual(core.ground_derived['t'][2],1.4)

    def test_calibration_version_change_invalidates_old_target(self):
        core=self.core()
        core.tracker.select('t-old',0,position_m=[1.,0.,.2],
            calibration_version='v1',receive_s=1.,source_stamp_s=100.)
        changed=self.artifact('v2')
        self.assertEqual(changed['ground_derived']['ground_derived_id'],
                         core._ground_derived_id)
        core.apply_ground_context(calibration=changed)
        self.assertIsNone(core.tracker.position_m)
        self.assertIsNone(core.tracker.track_id)

    def test_monitor_unavailable_cannot_accept_baseline_capture(self):
        core=self.core()
        person=standing_person(x=1.,bottom=-1.2,top=.3)
        first=core.process(person,1.,seq=1,stamp_secs=100,stamp_nsecs=0)
        snap=first['snapshot']
        select=core.handle_request({'schema_version':1,'request_id':'select-r3',
            'action':'select','session_id':'s1','time_epoch':0,
            'snapshot_id':snap['snapshot_id'],
            'candidate_id':snap['candidates'][0]['candidate_id'],
            'selection_version':0},1.01)
        self.assertTrue(select['accepted'])
        ack=core.handle_request({'schema_version':1,'request_id':'baseline-r3',
            'action':'capture_baseline','session_id':'s1','time_epoch':0,
            'selection_version':select['selection_version']},1.02)
        self.assertFalse(ack['accepted'])
        self.assertNotEqual(core.baseline.status,'pending')


if __name__=='__main__':
    unittest.main(verbosity=2)
