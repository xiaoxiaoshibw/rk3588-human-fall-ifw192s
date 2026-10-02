"""Independent HF-02 contract checks; synthetic, no ROS or hardware access."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/human_fall_detection"))
from core.timebase import TimebaseSession
from core.sensor_quality import ImuSemantics, device_motion_status, six_axis_report


def session():
    result = TimebaseSession("codex_hf02")
    result.register("cloud", 0.6, required=True)
    result.register("imu", 0.3)
    return result


class ContractBoundaries(unittest.TestCase):
    def test_r1_verified_offset_corrects_match_and_excludes_wrong_raw_match(self):
        for imu_stamps, expected_seq in (
                ([(1, (100, 500000000))], 1),
                ([(1, (100, 0)), (2, (100, 500000000))], 2)):
            with self.subTest(imu_stamps=imu_stamps):
                s = session()
                s.note("cloud", 1, (100, 0), 10.0)
                for seq, stamp in imu_stamps:
                    s.note("imu", seq, stamp, 10.0)
                # Known fixture convention: imu = cloud + 0.5 s.
                s.apply_sync_evidence("controlled_common_event", offset_s=0.5,
                                      uncertainty_s=0.001, note="synthetic fixture")
                pairs = s.pair("cloud", "imu", 0.01, now=10.1)["pairs"]
                self.assertEqual([p["second"]["seq"] for p in pairs], [expected_seq])

    def test_r2_stopped_streams_cannot_return_observations(self):
        s = session()
        s.note("cloud", 1, (100, 0), 10.0)
        s.note("imu", 1, (100, 0), 10.0)
        s.apply_sync_evidence("vendor_protocol", offset_s=0.0)
        self.assertEqual(s.snapshot(11.0)["streams"]["cloud"]["status"], "stale")
        self.assertEqual(s.pair("cloud", "imu", 0.01, now=11.0)["pairs"], [])

    def test_r2_invalid_current_frame_cannot_reuse_previous_observation(self):
        s = session()
        s.note("cloud", 1, (100, 0), 10.0)
        s.note("imu", 1, (100, 0), 10.0)
        s.apply_sync_evidence("vendor_protocol", offset_s=0.0)
        s.note("cloud", 2, (0, 0), 10.1)
        self.assertIsNone(s.snapshot(10.1)["streams"]["cloud"]["source_stamp_s"])
        self.assertEqual(s.pair("cloud", "imu", 0.01, now=10.1)["pairs"], [])

    def test_r3_empirical_sync_does_not_survive_clock_restart(self):
        s = session()
        s.note("cloud", 1, (100, 0), 10.0)
        s.note("imu", 1, (100, 0), 10.0)
        s.apply_sync_evidence("controlled_common_event", offset_s=0.0,
                              note="measured before clock restart")
        s.note("cloud", 2, (1, 0), 10.1)
        s.note("imu", 2, (1, 0), 10.1)
        self.assertGreater(s.time_epoch, 0)
        self.assertFalse(s.snapshot(10.1)["sync"]["cross_stream_same_clock_verified"])

    def test_r4_non_si_raw_values_need_conversion_or_unknown(self):
        semantics = ImuSemantics()
        try:
            semantics.verify("acceleration_units", "g", "vendor_protocol")
            semantics.verify("angular_velocity_units", "deg_s", "vendor_protocol")
        except ValueError:
            return  # Explicitly rejecting unsupported raw units is acceptable.
        semantics.verify("axis_mapping", "x_forward_y_left_z_up", "controlled_attitude")
        semantics.verify("bias", [0.0] * 6, "controlled_motion")
        result = device_motion_status((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), semantics)
        self.assertIn(result["status"], ("static", "unknown"), result)

    def test_r4_empty_verification_value_cannot_enable_motion_classification(self):
        semantics = ImuSemantics()
        try:
            for field in ("acceleration_units", "angular_velocity_units", "axis_mapping"):
                semantics.verify(field, None, "vendor_protocol")
        except ValueError:
            return  # Rejection before state mutation is also acceptable.
        result = device_motion_status((0.0, 0.0, 9.80665), (0.0, 0.0, 0.0), semantics)
        self.assertEqual(result["status"], "unknown", result)

    def test_r4_missing_axes_are_not_finite_six_axis_data(self):
        self.assertIsNot(six_axis_report([], [0.0, 0.0, 0.0])["finite"], True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
