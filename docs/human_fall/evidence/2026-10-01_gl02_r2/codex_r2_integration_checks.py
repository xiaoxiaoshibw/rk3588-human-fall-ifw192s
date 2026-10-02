"""Independent GL02 R2 monitor/runtime integration regressions."""
import copy
import sys
import unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'src/human_fall_detection'))
sys.path.insert(0,str(ROOT/'src/human_fall_detection/tests'))
from core.calibration import (build_geometry_calibration, validate_ground_derived,
                              ground_derived_id_for)
from core.ground import GroundMonitor
from core.node_runtime import FallNodeCore
from test_gl02_ground_frame import flat_ground, trusted_block
from test_hf07_node import standing_person, settings


class IntegrationChecks(unittest.TestCase):
    def test_nested_version_must_be_integer(self):
        b=trusted_block()
        b['schema_version']=1.0
        with self.assertRaises(ValueError):
            validate_ground_derived(b)

    def test_mixed_boolean_rotation_must_be_rejected_before_coercion(self):
        b=copy.deepcopy(trusted_block())
        b['R'][0][0]=True
        b['ground_derived_id']=ground_derived_id_for(b)
        with self.assertRaises(ValueError):
            validate_ground_derived(b)

    def points(self,z=-1.2):
        xy=np.random.RandomState(222).uniform(-1.,1.,(200,2))
        return np.column_stack([xy,np.full(200,z)])

    def core(self):
        g=flat_ground()
        a=build_geometry_calibration('v1','2026-10-01T00:00:00Z','innolidar',
            ground=g,ground_derived=trusted_block())
        return FallNodeCore('s1',settings=settings(),ground=g,calibration=a)

    def test_two_sided_scatter_is_not_coherent_plane_shift(self):
        monitor=GroundMonitor()
        p=self.points(-1.1)
        p[100:,2]=-1.3
        for _ in range(10):
            report=monitor.feed(p,trusted_block())
        self.assertNotEqual(report['status'],'recalibration_required')

    def test_recalibration_requirement_latches_until_new_version(self):
        monitor=GroundMonitor()
        for _ in range(5):
            report=monitor.feed(self.points(-1.1),trusted_block())
        self.assertEqual(report['status'],'recalibration_required')
        report=monitor.feed(self.points(),trusted_block())
        self.assertEqual(report['status'],'recalibration_required')

    def test_bare_block_cannot_leave_live_parent_and_derived_mismatched(self):
        core=self.core()
        try:
            core.apply_ground_context(ground_derived=trusted_block(1.4))
        except ValueError:
            return  # rejecting an incomplete context is a valid fix
        if core.ground is not None:
            self.assertAlmostEqual(core.ground['offset_m'],core.ground_derived['d'])
        result=core.process(self.points(),1.,seq=1,stamp_secs=100,stamp_nsecs=0)
        published=result['snapshot']['calibration'].get('ground_derived_id')
        self.assertIn(published,(None,core._ground_derived_id))

    def test_full_artifact_reload_replaces_actual_ground(self):
        core=self.core()
        g=flat_ground(1.4)
        a=build_geometry_calibration('v2','2026-10-01T00:00:00Z','innolidar',
            ground=g,ground_derived=trusted_block(1.4))
        core.apply_ground_context(calibration=a)
        self.assertAlmostEqual(core.ground['offset_m'],1.4)

    def test_bad_ground_monitor_blocks_real_target_position(self):
        core=self.core()
        person=standing_person(x=1.,bottom=-1.2,top=.3)
        first=core.process(person,1.,seq=1,stamp_secs=100,stamp_nsecs=0)
        snap=first['snapshot']
        ack=core.handle_request({'schema_version':1,'request_id':'select-r2',
            'action':'select','session_id':'s1','time_epoch':0,
            'snapshot_id':snap['snapshot_id'],
            'candidate_id':snap['candidates'][0]['candidate_id'],
            'selection_version':0},1.01)
        self.assertTrue(ack['accepted'])
        result=core.process(person,1.1,seq=2,stamp_secs=100,stamp_nsecs=100000000)
        self.assertFalse(result['state']['sensor_quality']['ground_valid'])
        self.assertIsNone(result['state']['position_source_m'])


if __name__=='__main__':
    unittest.main(verbosity=2)
