"""GL-02 R2 static-counterexample probes: each must FAIL-CLOSED (raise / not-ok)."""
import copy, sys, unittest
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src/human_fall_detection'))
sys.path.insert(0, str(ROOT / 'src/human_fall_detection/tests'))
from core.calibration import (build_ground_derived, build_geometry_calibration,
    validate_ground_derived, validate_geometry_calibration,
    ground_derived_id_for)
from core.ground import (GroundMonitor, monitor_ground_residual,
    resolve_ground_monitor_settings, MONITOR_OK, MONITOR_RECALIBRATION,
    MONITOR_UNKNOWN)
from test_gl02_ground_frame import flat_ground, trusted_block


def block(height=1.2):
    return trusted_block(height)

def points(z=-1.2):
    xy = np.random.RandomState(800).uniform(-1., 1., (200, 2))
    return np.column_stack([xy, np.full(200, z)])


class StaticProbes(unittest.TestCase):

    def test_float_count_is_not_truncated(self):
        # sustained_frames=0.99 must NOT silently become 0 frames.
        with self.assertRaises(ValueError):
            resolve_ground_monitor_settings({"sustained_frames": 0.99})
        with self.assertRaises(ValueError):
            resolve_ground_monitor_settings({"history_frames": 2.5})
        with self.assertRaises(ValueError):
            resolve_ground_monitor_settings({"min_support_points": 3.0})

    def test_auto_aabb_without_trusted_is_not_ok(self):
        b = build_ground_derived(flat_ground(1.2), [1., 0., 0.])
        # No trusted flag on the auto source-corner AABB.
        report = monitor_ground_residual(points(), b)
        self.assertEqual(report["status"], MONITOR_UNKNOWN)
        self.assertEqual(report["reason"], "no_trusted_region")

    def test_trusted_flag_must_have_evidence(self):
        with self.assertRaises(ValueError):
            build_ground_derived(flat_ground(1.2), [1., 0., 0.],
                                 valid_region_ground_local={
                                     "available": True, "x_min_m": -2., "x_max_m": 2.,
                                     "y_min_m": -2., "y_max_m": 2., "z_min_m": -0.1,
                                     "z_max_m": 0.1, "point_count": 400,
                                     "trusted": True})
        # A trusted ROI is only meaningful with a recorded evidence source.

    def test_stream_gap_clears_continuity(self):
        monitor = GroundMonitor({"sustained_frames": 3, "history_frames": 5})
        b = block()
        for _ in range(2):
            monitor.feed(points(-1.1), b)          # two shifted frames
        monitor.note_invalid()                      # stream gap
        for _ in range(2):
            monitor.feed(points(-1.1), b)          # only 2 after gap
        # sustained_frames=3 not yet reached -> still degraded, not recalibration
        report = monitor.feed(points(-1.1), b)
        self.assertEqual(report["status"], MONITOR_RECALIBRATION)

    def test_bad_units_n_or_t_rejected(self):
        b = block()
        for mutate in (lambda x: x.update(units="mm"),
                       lambda x: x["n"].__setitem__(2, 0.5),
                       lambda x: x["t"].__setitem__(2, 99.),
                       lambda x: x.update(d=-1.0)):
            damaged = copy.deepcopy(b)
            mutate(damaged)
            with self.assertRaises(ValueError):
                validate_ground_derived(damaged)

    def test_mixed_bool_region_point_count_and_bool_trusted_rejected(self):
        b = block()
        damaged = copy.deepcopy(b)
        damaged["valid_region_ground_local"]["point_count"] = True
        with self.assertRaises(ValueError):
            validate_ground_derived(damaged)
        damaged2 = copy.deepcopy(b)
        damaged2["valid_region_ground_local"]["trusted"] = "yes"
        with self.assertRaises(ValueError):
            validate_ground_derived(damaged2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
