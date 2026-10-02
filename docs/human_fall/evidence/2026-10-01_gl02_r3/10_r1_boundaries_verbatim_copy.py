"""Independent GL-02 lifecycle, monitor and cross-record checks."""
import copy
import sys
import unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'src/human_fall_detection'))
sys.path.insert(0,str(ROOT/'src/human_fall_detection/tests'))
from core.calibration import (build_ground_derived, build_geometry_calibration,
    validate_ground_derived, ground_derived_id_for)
from core.ground import GroundMonitor, monitor_ground_residual
from core.node_runtime import FallNodeCore
from test_gl02_ground_frame import flat_ground


class GL02Boundaries(unittest.TestCase):
    def block(self, height=1.2, trusted=False):
        block=build_ground_derived(flat_ground(height),[1.,0.,0.],
            source={'kind':'synthetic','sha256':'a'*64},created_at_utc='2026-10-01T00:00:00Z')
        block['valid_region_ground_local']['trusted']=trusted
        block['valid_region_ground_local']['evidence']='synthetic known floor' if trusted else None
        block['ground_derived_id']=ground_derived_id_for(block)
        return block

    def points(self, z=-1.2):
        xy=np.random.RandomState(800).uniform(-1.,1.,(200,2))
        return np.column_stack([xy,np.full(200,z)])

    def core(self):
        ground=flat_ground()
        block=self.block()
        artifact=build_geometry_calibration('old','2026-10-01T00:00:00Z',
            'innolidar',ground=ground,ground_derived=block)
        return FallNodeCore('gl02-review',ground=ground,calibration=artifact)

    def test_coherent_ground_shift_requires_recalibration(self):
        monitor=GroundMonitor()
        block=self.block(trusted=True)
        for _ in range(10):
            report=monitor.feed(self.points(-1.1),block)
        self.assertEqual(report['status'],'recalibration_required')

    def test_unconfirmed_auto_bounds_cannot_be_trusted_ground(self):
        report=monitor_ground_residual(self.points(),self.block(trusted=False))
        self.assertNotEqual(report['status'],'ok')

    def test_switch_clears_tracked_position(self):
        core=self.core()
        core.tracker.select('t1',0,position_m=[1.,0.,.5],
                            calibration_version='old',receive_s=1.,source_stamp_s=100.)
        core.apply_ground_context(ground_derived=self.block(1.4))
        self.assertIsNone(core.tracker.position_m)

    def test_reload_rejects_damaged_same_id(self):
        core=self.core()
        damaged=copy.deepcopy(core.calibration)
        damaged['ground_derived']['t'][2]=99.
        with self.assertRaises(ValueError):
            core.apply_ground_context(calibration=damaged)

    def test_parent_plane_and_derived_plane_must_match(self):
        with self.assertRaises(ValueError):
            build_geometry_calibration('mismatch','2026-10-01T00:00:00Z',
                'innolidar',ground=flat_ground(1.4),ground_derived=self.block(1.2))

    def test_bool_nested_version_is_rejected(self):
        damaged=self.block()
        damaged['schema_version']=True
        with self.assertRaises(ValueError):
            validate_ground_derived(damaged)


if __name__=='__main__':
    unittest.main(verbosity=2)
