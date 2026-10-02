"""Independent round-2 HF-02 checks; synthetic, no ROS or device access."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/human_fall_detection"))
from core.timebase import TimebaseSession
from core.sensor_quality import ImuSemantics, device_motion_status


class RoundTwoBoundaries(unittest.TestCase):
    def test_r2_invalid_current_receive_time_cannot_reuse_cached_pair(self):
        for invalid_receive in (None, float("nan"), float("inf")):
            with self.subTest(receive=invalid_receive):
                session = TimebaseSession("codex_hf02_r2")
                session.register("cloud", 0.6, required=True)
                session.register("imu", 0.3)
                session.note("cloud", 1, (100, 0), 10.0)
                session.note("imu", 1, (100, 0), 10.0)
                session.apply_sync_evidence("vendor_protocol", offset_s=0.0)
                session.note("cloud", 2, (100, 100000000), invalid_receive)
                result = session.pair("cloud", "imu", 0.01, now=10.1)
                self.assertEqual(result["pairs"], [], result)
                self.assertTrue(result["reason"], result)

    def test_r4_unknown_or_duplicate_axis_description_cannot_verify_alignment(self):
        for description in ("unknown", "x_forward_x_left_z_up"):
            with self.subTest(description=description):
                semantics = ImuSemantics()
                semantics.verify("acceleration_units", "m_s2", "vendor_protocol")
                semantics.verify("angular_velocity_units", "rad_s", "vendor_protocol")
                try:
                    semantics.verify("axis_mapping", description, "controlled_attitude")
                except ValueError:
                    pass
                self.assertFalse(semantics.alignment_verified, semantics.report())
                self.assertEqual(device_motion_status(
                    (0.0, 0.0, 9.80665), (0.0, 0.0, 0.0), semantics)["status"],
                    "unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
