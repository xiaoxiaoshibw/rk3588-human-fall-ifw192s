import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))

from core.sensor_quality import (ImuSemantics, device_motion_status, orientation_report,
                                 six_axis_report, static_background_usable)
from core.timebase import (PAIRING_TIME_INVALID_CODE, SYNC_EPOCH_INVALIDATED_CODE,
                           TimebaseSession, UNIT_MISMATCH_CODE, UNVERIFIED_PAIRING_CODE,
                           linear_fit, split_device_seconds, stamp_from_health_block)
from sensor_health import dumps_strict


def make_session(mode="monotonic", cache_size=32, jump=30.0):
    session = TimebaseSession("hf02_test", clock_domain=mode, max_forward_jump_s=jump,
                              cache_size=cache_size)
    session.register("cloud", 0.6, required=True)
    session.register("imu", 0.3, required=False)
    return session


class SplitStampTest(unittest.TestCase):
    def test_nanosecond_carry_at_rounding_boundary(self):
        self.assertEqual(split_device_seconds(409.9999999996), (410, 0))
        self.assertEqual(split_device_seconds(409.9999999994), (409, 999999999))
        self.assertEqual(split_device_seconds(12.5), (12, 500000000))
        self.assertEqual(split_device_seconds(0.0), (0, 0))

    def test_nonfinite_and_negative_seconds_never_become_a_stamp(self):
        for value in (float("nan"), float("inf"), -1.0, None, "x"):
            self.assertIsNone(split_device_seconds(value), repr(value))

    def test_carry_keeps_stamp_usable_in_the_frozen_classifier(self):
        sec, nsec = split_device_seconds(9817.9999999996)
        self.assertTrue(0 <= nsec < 10 ** 9)
        self.assertEqual((sec, nsec), (9818, 0))


class EpochTest(unittest.TestCase):
    def test_repeat_regress_and_jump_rebuild_epoch_and_clear_history(self):
        session = make_session()
        session.note("cloud", 1, (10, 0), 0.0, "innolidar")
        session.note("imu", 1, (10, 0), 0.0, "innolidar")
        session.note("cloud", 2, (10, 100000000), 0.1, "innolidar")
        session.note("imu", 2, (10, 100000000), 0.1, "innolidar")
        self.assertEqual(session.time_epoch, 0)
        self.assertEqual(len(session.streams["imu"].recent()), 2)

        result = session.note("cloud", 3, (10, 100000000), 0.2, "innolidar")
        self.assertTrue(result["epoch_reset"])
        self.assertEqual(session.time_epoch, 1)
        self.assertEqual(session.epoch_reason, "cloud_stamp_repeated")
        self.assertEqual(len(session.streams["cloud"].recent()), 1)
        self.assertEqual(len(session.streams["imu"].recent()), 0)

        result = session.note("imu", 3, (9, 900000000), 0.3, "innolidar")
        self.assertTrue(result["epoch_reset"])
        self.assertEqual(session.time_epoch, 2)
        self.assertEqual(session.epoch_reason, "imu_stamp_regressed")
        session.note("cloud", 4, (10, 200000000), 0.4, "innolidar")
        self.assertEqual(session.time_epoch, 2)
        session.note("cloud", 5, (60, 0), 0.5, "innolidar")
        self.assertEqual(session.time_epoch, 3)
        self.assertEqual(session.epoch_reason, "cloud_stamp_forward_jump")

    def test_invalid_stamp_keeps_epoch_and_previous_valid_baseline(self):
        session = make_session()
        session.note("cloud", 1, (10, 0), 0.0, "innolidar")
        session.note("cloud", 2, (0, 0), 0.1, "innolidar")
        session.note("cloud", 3, (10, 2000000000), 0.2, "innolidar")
        session.note("cloud", 4, (float("nan"), 0), 0.3, "innolidar")
        cloud = session.streams["cloud"]
        self.assertEqual(cloud.stamp_status, "invalid")
        self.assertIsNone(cloud.source_stamp_s)
        self.assertEqual(session.time_epoch, 0)
        self.assertEqual(cloud.last_stamp, (10, 0))
        result = session.note("cloud", 5, (9, 900000000), 0.4, "innolidar")
        self.assertTrue(result["epoch_reset"])
        self.assertEqual(session.epoch_reason, "cloud_stamp_regressed")

    def test_forward_jump_threshold_is_configurable(self):
        session = make_session(jump=30.0)
        session.note("cloud", 1, (100, 0), 0.0)
        self.assertFalse(session.note("cloud", 2, (129, 900000000), 0.1)["epoch_reset"])
        self.assertTrue(session.note("cloud", 3, (160, 0), 0.2)["epoch_reset"])

    def test_cache_is_bounded_and_keeps_sequence_traceability(self):
        session = make_session(cache_size=3)
        for index in range(10):
            session.note("cloud", 100 + index, (10, index * 1000000), 0.01 * index)
        entries = session.streams["cloud"].recent()
        self.assertEqual(len(entries), 3)
        self.assertEqual([entry["seq"] for entry in entries], [107, 108, 109])
        self.assertEqual(entries[-1]["stamp_nsecs"], 9000000)


class FreshnessTest(unittest.TestCase):
    def test_online_freshness_uses_receive_time(self):
        session = make_session()
        session.note("cloud", 1, (10, 0), 100.0)
        self.assertEqual(session.streams["cloud"].freshness(100.1)[0], "fresh")
        self.assertEqual(session.streams["cloud"].freshness(100.7)[0], "stale")
        self.assertEqual(session.streams["imu"].freshness(100.1)[0], "no_data")

    def test_replay_freshness_is_driven_by_message_time_only(self):
        session = make_session(mode="message_time")
        with patch("time.monotonic", side_effect=AssertionError("wall clock must not be read")):
            session.note("cloud", 1, (100, 0), 1000.0)
            session.note("imu", 1, (100, 5000000), 1000.0)
            session.note("cloud", 2, (100, 100000000), 1000.103)
            self.assertEqual(session.streams["cloud"].freshness(1000.31)[0], "fresh")
            self.assertEqual(session.streams["imu"].freshness(1000.31)[0], "stale")
            snapshot = session.snapshot(1000.31)
            dumps_strict(snapshot)
            self.assertEqual(snapshot["clock_domain"], "message_time")
            self.assertEqual(snapshot["streams"]["cloud"]["status"], "fresh")
            self.assertEqual(snapshot["streams"]["imu"]["status"], "stale")
        self.assertIn("imu_stale", session.snapshot(1000.31)["reason_codes"])

    def test_missing_auxiliary_imu_never_blocks_the_required_cloud(self):
        session = make_session()
        session.note("cloud", 1, (10, 0), 0.0)
        snapshot = session.snapshot(0.1)
        self.assertEqual(snapshot["streams"]["cloud"]["status"], "fresh")
        self.assertEqual(snapshot["streams"]["imu"]["status"], "no_data")
        self.assertTrue(snapshot["streams"]["cloud"]["required"])
        self.assertIn("imu_no_data", snapshot["reason_codes"])
        self.assertNotIn("cloud_no_data", snapshot["reason_codes"])


class PairingAndEvidenceTest(unittest.TestCase):
    def test_close_stamps_and_perfect_fit_do_not_verify_sync(self):
        session = make_session()
        for index in range(4):
            session.note("cloud", index, (100 + index, 0), 1000.0 + index)
            session.note("imu", index, (100 + index, 100000), 1000.0 + index + 0.001)
        fit = session.clock_fit("cloud")
        self.assertEqual(fit["classification"], "transport_fit_only")
        self.assertLess(fit["fit"]["rms_residual_s"], 1e-6)
        pairs = session.pair("cloud", "imu", 0.01)
        self.assertEqual(pairs["status"], "unverified_domain")
        self.assertEqual(pairs["pairs"], [])
        self.assertEqual(pairs["reason"], UNVERIFIED_PAIRING_CODE)
        snapshot = session.snapshot(1005.0)
        self.assertFalse(snapshot["sync"]["cross_stream_same_clock_verified"])
        self.assertIsNone(snapshot["normalized_stamp_s"])
        self.assertIn("clock_cross_stream_unverified", snapshot["reason_codes"])

    def test_receive_time_fit_is_not_accepted_as_physical_offset_evidence(self):
        session = make_session()
        before = copy.deepcopy(session.sync)
        for evidence in ("receive_time_fit", "similar_stamps", "same_frame_id",
                         "static_magnitude_hint"):
            with self.subTest(evidence), self.assertRaises(ValueError):
                session.apply_sync_evidence(evidence, offset_s=0.001)
        self.assertEqual(session.sync, before)

    def test_vendor_or_controlled_event_evidence_allows_pairing(self):
        session = make_session()
        for index in range(3):
            session.note("cloud", index, (100 + index, 500000000), 12.0 + index * 0.02)
            session.note("imu", index, (100 + index, 512000000), 12.001 + index * 0.02)
        session.apply_sync_evidence("vendor_protocol", offset_s=0.012, uncertainty_s=0.001,
                                    note="test fixture")
        result = session.pair("cloud", "imu", 0.02, now=12.05)
        self.assertEqual(result["status"], "paired")
        self.assertEqual(len(result["pairs"]), 3)
        self.assertAlmostEqual(result["pairs"][0]["delta_s"], 0.012)
        self.assertAlmostEqual(result["pairs"][0]["residual_s"], 0.0)
        self.assertEqual(result["mapping"]["first_label"], "cloud")
        self.assertEqual(result["mapping"]["second_label"], "imu")
        self.assertAlmostEqual(result["mapping"]["offset_s"], 0.012)
        snapshot = session.snapshot(13.0)
        self.assertTrue(snapshot["sync"]["cross_stream_same_clock_verified"])
        self.assertEqual(snapshot["sync"]["offset_evidence"], "vendor_protocol")
        self.assertFalse(snapshot["sync"]["host_anchor_verified"])

    def test_unit_mismatch_is_detected_and_never_paired(self):
        session = make_session()
        for index in range(3):
            session.note("cloud", index, (100 + index, 0), 10.0 + index)
            session.note("imu", index, (100 + index, 0), 10.0 + index)
        for entry in session.streams["imu"].entries:
            entry["stamp_secs"] = int(entry["stamp_secs"] * 10 ** 9)
            entry["source_stamp_s"] = entry["source_stamp_s"] * 10 ** 9
        session.apply_sync_evidence("vendor_protocol", offset_s=0.0)
        result = session.pair("cloud", "imu", 1.0)
        self.assertEqual(result["status"], "unit_mismatch_suspected")
        self.assertEqual(result["reason"], UNIT_MISMATCH_CODE)
        self.assertEqual(result["pairs"], [])
        self.assertTrue(session.snapshot(20.0)["unit_mismatch_suspected"])


class SyncOffsetPairingTest(unittest.TestCase):
    def _mapped_session(self):
        session = make_session()
        session.note("cloud", 1, (100, 0), 10.0)
        session.note("imu", 1, (100, 500000000), 10.0)
        session.apply_sync_evidence("controlled_common_event", offset_s=0.5,
                                    uncertainty_s=0.001,
                                    note="fixture: imu stamp = cloud stamp + 0.5")
        return session

    def test_verified_offset_matches_corresponding_sample_and_keeps_raw(self):
        session = self._mapped_session()
        result = session.pair("cloud", "imu", 0.01, now=10.1)
        self.assertEqual(result["status"], "paired")
        self.assertEqual([p["second"]["seq"] for p in result["pairs"]], [1])
        pair = result["pairs"][0]
        self.assertAlmostEqual(pair["delta_s"], 0.5)
        self.assertAlmostEqual(pair["residual_s"], 0.0)
        self.assertEqual((pair["first"]["stamp_secs"], pair["first"]["stamp_nsecs"]),
                         (100, 0))
        self.assertEqual((pair["second"]["stamp_secs"], pair["second"]["stamp_nsecs"]),
                         (100, 500000000))
        self.assertEqual(result["mapping"]["first_label"], "cloud")
        self.assertEqual(result["mapping"]["second_label"], "imu")
        self.assertAlmostEqual(result["mapping"]["offset_s"], 0.5)
        self.assertEqual(result["mapping"]["direction"], "second = first + offset_s")

    def test_swapped_argument_order_uses_the_same_mapping(self):
        session = self._mapped_session()
        result = session.pair("imu", "cloud", 0.01, now=10.1)
        self.assertEqual(result["status"], "paired")
        self.assertEqual([p["first"]["seq"] for p in result["pairs"]], [1])
        self.assertAlmostEqual(result["pairs"][0]["residual_s"], 0.0)
        self.assertAlmostEqual(result["pairs"][0]["delta_s"], 0.5)

    def test_raw_close_but_physically_wrong_sample_is_excluded(self):
        session = make_session()
        session.note("cloud", 1, (100, 0), 10.0)
        session.note("imu", 1, (100, 0), 10.0)
        session.note("imu", 2, (100, 500000000), 10.0)
        session.apply_sync_evidence("controlled_common_event", offset_s=0.5)
        for first, second in (("cloud", "imu"), ("imu", "cloud")):
            with self.subTest(order=(first, second)):
                result = session.pair(first, second, 0.01, now=10.1)
                self.assertEqual(result["status"], "paired")
                matched = {p["first"]["seq"] for p in result["pairs"]}
                matched |= {p["second"]["seq"] for p in result["pairs"]}
                self.assertEqual(matched, {1, 2})

    def test_evidence_is_bound_to_its_stream_pair(self):
        session = make_session()
        session.register("device", 0.6)
        session.note("cloud", 1, (100, 0), 10.0)
        session.note("imu", 1, (100, 500000000), 10.0)
        session.note("device", 1, (100, 0), 10.0)
        with self.assertRaises(ValueError):
            session.apply_sync_evidence("controlled_common_event", offset_s=0.5)
        session.apply_sync_evidence("controlled_common_event", offset_s=0.5,
                                    first_label="cloud", second_label="imu")
        self.assertEqual(session.pair("cloud", "imu", 0.01, now=10.1)["status"], "paired")
        other = session.pair("cloud", "device", 0.01, now=10.1)
        self.assertEqual(other["status"], "unverified_domain")
        self.assertIsNone(other["mapping"])

    def test_offset_uncertainty_and_tolerance_ranges_are_enforced(self):
        session = self._mapped_session()
        for offset in (None, float("nan"), float("inf"), 1e9):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                session.apply_sync_evidence("vendor_protocol", offset_s=offset)
        for uncertainty in (-0.1, float("inf"), 1e9):
            with self.subTest(uncertainty=uncertainty), self.assertRaises(ValueError):
                session.apply_sync_evidence("vendor_protocol", offset_s=0.0,
                                            uncertainty_s=uncertainty)
        with self.assertRaises(ValueError):
            session.pair("cloud", "imu", -0.01, now=10.1)
        with self.assertRaises(ValueError):
            session.pair("cloud", "imu", float("nan"), now=10.1)


class ClockRestartEvidenceTest(unittest.TestCase):
    def test_controlled_event_offset_is_revoked_by_clock_restart(self):
        session = make_session()
        session.note("cloud", 1, (100, 0), 10.0)
        session.note("imu", 1, (100, 0), 10.0)
        session.apply_sync_evidence("controlled_common_event", offset_s=0.0,
                                    note="measured once")
        self.assertTrue(session.snapshot(10.1)["sync"]["cross_stream_same_clock_verified"])
        session.note("cloud", 2, (1, 0), 10.1)
        self.assertGreater(session.time_epoch, 0)
        snapshot = session.snapshot(10.1)
        self.assertFalse(snapshot["sync"]["cross_stream_same_clock_verified"])
        self.assertEqual(snapshot["sync"]["offset_evidence"], "none")
        self.assertEqual(snapshot["sync"]["evidence_records"][0]["time_epoch"], 0)
        self.assertIn(SYNC_EPOCH_INVALIDATED_CODE, snapshot["reason_codes"])
        result = session.pair("cloud", "imu", 0.01, now=10.1)
        self.assertEqual(result["status"], "unverified_domain")
        self.assertEqual(result["reason"], SYNC_EPOCH_INVALIDATED_CODE)
        self.assertEqual(result["pairs"], [])

    def test_vendor_protocol_survives_restart_without_new_experiment(self):
        session = make_session()
        session.note("cloud", 1, (100, 0), 10.0)
        session.note("imu", 1, (100, 500000000), 10.0)
        session.apply_sync_evidence("vendor_protocol", offset_s=0.5,
                                    note="permanent device relation")
        session.note("cloud", 2, (1, 0), 11.0)
        session.note("imu", 2, (1, 500000000), 11.0)
        self.assertGreater(session.time_epoch, 0)
        self.assertTrue(session.snapshot(11.1)["sync"]["cross_stream_same_clock_verified"])
        session.note("cloud", 3, (2, 0), 11.1)
        session.note("imu", 3, (2, 500000000), 11.1)
        result = session.pair("cloud", "imu", 0.01, now=11.15)
        self.assertEqual(result["status"], "paired")
        self.assertEqual(result["pairs"][0]["first"]["seq"], 3)
        self.assertEqual(result["pairs"][0]["second"]["seq"], 3)

    def test_reapplying_evidence_rearms_after_restart(self):
        session = make_session()
        session.note("cloud", 1, (100, 0), 10.0)
        session.note("imu", 1, (100, 0), 10.0)
        session.apply_sync_evidence("controlled_common_event", offset_s=0.0)
        session.note("cloud", 2, (1, 0), 10.1)
        self.assertFalse(session.snapshot(10.1)["sync"]["cross_stream_same_clock_verified"])
        session.apply_sync_evidence("controlled_common_event", offset_s=0.0,
                                    note="re-verified after restart")
        snapshot = session.snapshot(10.1)
        self.assertTrue(snapshot["sync"]["cross_stream_same_clock_verified"])
        self.assertEqual(len(snapshot["sync"]["evidence_records"]), 2)
        dumps_strict(snapshot)


class OnlineFreshnessGateTest(unittest.TestCase):
    def test_pair_requires_now_and_never_serves_stale_observations(self):
        session = make_session()
        session.note("cloud", 1, (100, 0), 10.0)
        session.note("imu", 1, (100, 0), 10.0)
        session.apply_sync_evidence("vendor_protocol", offset_s=0.0)
        result = session.pair("cloud", "imu", 0.01)
        self.assertEqual(result["status"], "invalid_now")
        self.assertEqual(result["reason"], PAIRING_TIME_INVALID_CODE)
        self.assertEqual(result["pairs"], [])
        result = session.pair("cloud", "imu", 0.01, now=11.0)
        self.assertEqual(result["status"], "input_not_fresh")
        self.assertEqual(result["reason"], "cloud_stale")
        self.assertEqual(result["pairs"], [])

    def test_stale_auxiliary_never_waits_and_blocks_pairing(self):
        session = make_session()
        session.note("cloud", 1, (100, 0), 10.5)
        session.apply_sync_evidence("vendor_protocol", offset_s=0.0)
        session.note("imu", 1, (100, 0), 10.0)
        result = session.pair("cloud", "imu", 0.01, now=10.55)
        self.assertEqual(result["status"], "input_not_fresh")
        self.assertEqual(result["reason"], "imu_stale")
        self.assertEqual(result["pairs"], [])

    def test_current_invalid_frame_never_reuses_previous_observation(self):
        session = make_session()
        session.note("cloud", 1, (100, 0), 10.0)
        session.note("imu", 1, (100, 0), 10.0)
        session.apply_sync_evidence("vendor_protocol", offset_s=0.0)
        session.note("cloud", 2, (0, 0), 10.05)
        self.assertEqual(session.time_epoch, 0)
        self.assertEqual(session.streams["cloud"].last_stamp, (100, 0))
        self.assertIsNone(session.snapshot(10.05)["streams"]["cloud"]["source_stamp_s"])
        result = session.pair("cloud", "imu", 0.01, now=10.05)
        self.assertEqual(result["status"], "current_frame_invalid")
        self.assertEqual(result["reason"], "cloud_stamp_invalid")
        self.assertEqual(result["pairs"], [])
        session.note("cloud", 3, (100, 100000000), 10.1)
        self.assertEqual(session.time_epoch, 0)
        recovered = session.pair("cloud", "imu", 0.01, now=10.1)
        self.assertEqual(recovered["status"], "paired")
        self.assertEqual([p["first"]["seq"] for p in recovered["pairs"]], [1])

    def test_expired_cache_entries_are_not_matched(self):
        session = make_session()
        session.note("cloud", 1, (100, 0), 10.0)
        session.note("cloud", 2, (102, 0), 12.5)
        session.note("imu", 1, (102, 0), 12.5)
        session.apply_sync_evidence("vendor_protocol", offset_s=0.0)
        result = session.pair("cloud", "imu", 0.01, now=12.55)
        self.assertEqual(result["status"], "paired")
        self.assertEqual([p["first"]["seq"] for p in result["pairs"]], [2])

    def test_replay_clock_regression_is_stale_not_clamped_fresh(self):
        session = make_session(mode="message_time")
        session.note("cloud", 1, (100, 0), 1000.0)
        session.note("imu", 1, (100, 0), 1000.0)
        session.apply_sync_evidence("vendor_protocol", offset_s=0.0)
        status, age = session.streams["cloud"].freshness(500.0)
        self.assertEqual(status, "stale")
        self.assertLess(age, 0.0)
        self.assertEqual(session.snapshot(500.0)["streams"]["cloud"]["status"], "stale")
        result = session.pair("cloud", "imu", 0.01, now=500.0)
        self.assertEqual(result["status"], "input_not_fresh")
        self.assertEqual(result["pairs"], [])

    def test_cross_epoch_observations_are_not_paired(self):
        session = make_session()
        session.note("cloud", 1, (100, 0), 10.0)
        session.note("cloud", 2, (1, 0), 10.1)
        session.note("imu", 1, (1, 0), 10.1)
        session.apply_sync_evidence("vendor_protocol", offset_s=0.0)
        result = session.pair("cloud", "imu", 0.01, now=10.15)
        self.assertEqual(result["status"], "paired")
        self.assertEqual([p["first"]["seq"] for p in result["pairs"]], [2])

    def test_invalid_current_receive_time_never_pretends_fresh_or_paired(self):
        for label in ("cloud", "imu"):
            for invalid_receive in (None, float("nan"), float("inf")):
                with self.subTest(label=label, receive=invalid_receive):
                    session = make_session()
                    session.note("cloud", 1, (100, 0), 10.0)
                    session.note("imu", 1, (100, 0), 10.0)
                    session.apply_sync_evidence("vendor_protocol", offset_s=0.0)
                    session.note(label, 2, (100, 100000000), invalid_receive)
                    self.assertEqual(session.time_epoch, 0)
                    self.assertEqual(session.streams[label].last_stamp,
                                     (100, 100000000))
                    self.assertEqual(session.streams[label].freshness(10.1)[0], "stale")
                    snapshot = session.snapshot(10.1)
                    self.assertEqual(snapshot["streams"][label]["status"], "stale")
                    self.assertEqual(snapshot["streams"][label]["receive_status"],
                                     "invalid")
                    self.assertIn(label + "_receive_time_invalid",
                                  snapshot["reason_codes"])
                    dumps_strict(snapshot)
                    result = session.pair("cloud", "imu", 0.01, now=10.1)
                    self.assertEqual(result["status"], "input_receive_invalid")
                    self.assertEqual(result["reason"], label + "_receive_time_invalid")
                    self.assertEqual(result["pairs"], [])
                    session.note(label, 3, (100, 200000000), 10.1)
                    self.assertEqual(session.streams[label].receive_status, "ok")
                    recovered = session.pair("cloud", "imu", 0.01, now=10.1)
                    self.assertEqual(recovered["status"], "paired")

    def test_first_frame_with_invalid_receive_time_is_stale(self):
        session = make_session()
        session.note("cloud", 1, (100, 0), float("nan"))
        self.assertEqual(session.streams["cloud"].freshness(10.0)[0], "stale")
        self.assertEqual(session.snapshot(10.0)["streams"]["cloud"]["receive_status"],
                         "invalid")

    def test_invalid_receive_alone_keeps_the_source_stamp_epoch_rules(self):
        session = make_session()
        session.note("cloud", 1, (100, 0), 10.0)
        session.note("cloud", 2, (200, 0), None)
        self.assertEqual(session.time_epoch, 1)
        self.assertEqual(session.epoch_reason, "cloud_stamp_forward_jump")
        session.note("cloud", 3, (200, 100000000), 10.1)
        self.assertEqual(session.time_epoch, 1)
        self.assertEqual(session.streams["cloud"].freshness(10.1)[0], "fresh")


class HealthCompatibilityTest(unittest.TestCase):
    def test_frozen_block_fields_are_read(self):
        block = {"stamp_secs": 6381, "stamp_nsecs": 889296000,
                 "source_stamp_s": 6381.889296}
        parsed = stamp_from_health_block(block)
        self.assertEqual(parsed["compatibility"], "frozen_stamp_fields")
        self.assertEqual((parsed["stamp_secs"], parsed["stamp_nsecs"]), (6381, 889296000))
        self.assertAlmostEqual(parsed["source_stamp_s"], 6381.889296)

    def test_draft_round_sample_without_stamp_fields_still_reads(self):
        draft = {"topic": "/innolidar_points", "source_stamp_s": 6381.889296}
        parsed = stamp_from_health_block(draft)
        self.assertEqual(parsed["compatibility"], "draft_source_stamp_s")
        self.assertEqual((parsed["stamp_secs"], parsed["stamp_nsecs"]), (6381, 889296000))

    def test_invalid_and_missing_blocks_return_none_not_fabrication(self):
        self.assertIsNone(stamp_from_health_block(None))
        self.assertIsNone(stamp_from_health_block({}))
        parsed = stamp_from_health_block({"stamp_secs": 10, "stamp_nsecs": 2000000000})
        self.assertIsNone(parsed["source_stamp_s"])


class StrictJsonTest(unittest.TestCase):
    def test_nonfinite_inputs_produce_strict_json_without_nan(self):
        session = make_session()
        session.note("cloud", 1, (float("nan"), 0), float("nan"))
        session.note("cloud", 2, (float("inf"), 0), 0.2)
        session.note("imu", 1, (10, 0), float("inf"))
        text = dumps_strict(session.snapshot(float("nan")))
        parsed = json.loads(text)
        self.assertEqual(parsed["streams"]["cloud"]["stamp_status"], "invalid")
        self.assertIsNone(parsed["streams"]["cloud"]["source_stamp_s"])
        self.assertEqual(parsed["streams"]["imu"]["stamp_status"], "first")
        self.assertEqual(parsed["streams"]["imu"]["source_stamp_s"], 10.0)
        self.assertIsNone(parsed["streams"]["imu"]["age_s"])
        self.assertEqual(parsed["time_epoch"], 0)
        with self.assertRaises(ValueError):
            dumps_strict({"bad": float("nan")})

    def test_linear_fit_needs_two_distinct_points(self):
        self.assertIsNone(linear_fit([], []))
        self.assertIsNone(linear_fit([1.0], [1.0]))
        self.assertIsNone(linear_fit([1.0, 1.0], [1.0, 2.0]))
        fit = linear_fit([1.0, 2.0, 3.0], [2.5, 4.5, 6.5])
        self.assertAlmostEqual(fit["slope"], 2.0)
        self.assertAlmostEqual(fit["intercept"], 0.5)
        self.assertAlmostEqual(fit["rms_residual_s"], 0.0)


class SensorQualityTest(unittest.TestCase):
    def test_orientation_and_six_axis_are_recorded_separately(self):
        zero = orientation_report((0.0, 0.0, 0.0, 0.0), [0.0] * 9)
        self.assertFalse(zero["usable"])
        self.assertEqual(zero["reason"], "orientation_all_zero")
        self.assertTrue(zero["covariance_zero"])
        not_provided = orientation_report((0.0, 0.0, 0.0, 0.0), [-1.0] + [0.0] * 8)
        self.assertEqual(not_provided["reason"], "orientation_not_provided")
        valid = orientation_report((0.0, 0.0, 0.0, 1.0), [0.1] + [0.0] * 8)
        self.assertTrue(valid["usable"])
        self.assertIsNone(six_axis_report((0.0, 0.0, 9.8), (0.0, 0.0, 0.0))["reason"])
        report = six_axis_report((float("nan"), 0.0, 9.8), (0.0, 0.0, 0.0))
        self.assertFalse(report["finite"])
        self.assertEqual(report["reason"], "imu_measurement_nonfinite")

    def test_units_require_evidence_and_magnitude_clues_are_rejected(self):
        semantics = ImuSemantics()
        self.assertFalse(semantics.units_verified)
        self.assertFalse(semantics.alignment_verified)
        with self.assertRaises(ValueError):
            semantics.verify("acceleration_units", "m_s2", "static_magnitude_near_g")
        with self.assertRaises(ValueError):
            semantics.verify("angular_velocity_units", "rad_s", "near_zero_rate")
        with self.assertRaises(ValueError):
            semantics.verify("chip_guess", "icm", "vendor_protocol")
        semantics.verify("acceleration_units", "m_s2", "vendor_protocol")
        self.assertFalse(semantics.units_verified)
        semantics.verify("angular_velocity_units", "rad_s", "controlled_motion")
        self.assertTrue(semantics.units_verified)
        self.assertFalse(semantics.alignment_verified)
        report = semantics.report()
        self.assertEqual(report["role"], "device_motion_gravity_reference_not_human_impact")
        self.assertEqual(len(report["evidence"]), 2)

    def test_device_motion_stays_unknown_until_units_and_axes_verified(self):
        semantics = ImuSemantics()
        status = device_motion_status((0.0, 0.0, 9.8), (0.0, 0.0, 0.001), semantics)
        self.assertEqual(status["status"], "unknown")
        self.assertEqual(status["reason"], "imu_units_unverified")
        semantics.verify("acceleration_units", "m_s2", "vendor_protocol")
        semantics.verify("angular_velocity_units", "rad_s", "vendor_protocol")
        status = device_motion_status((0.0, 0.0, 9.8), (0.0, 0.0, 0.001), semantics)
        self.assertEqual(status["reason"], "imu_alignment_unverified")
        semantics.verify("axis_mapping", "x_forward_y_left_z_up", "controlled_attitude")
        self.assertEqual(
            device_motion_status((0.0, 0.0, 9.8), (0.0, 0.0, 0.001), semantics)["status"],
            "static")
        self.assertEqual(
            device_motion_status((3.0, 0.0, 9.8), (0.0, 0.0, 1.0), semantics)["status"],
            "moving")

    def test_static_background_gate_never_passes_without_ground_or_motion(self):
        usable = static_background_usable(True, True, "static")
        self.assertTrue(usable["usable"])
        self.assertFalse(usable["reinit_required"])
        for ground, residual, motion in ((False, True, "static"), (True, False, "static"),
                                         (True, True, "unknown"), (True, True, "moving")):
            with self.subTest(ground=ground, residual=residual, motion=motion):
                result = static_background_usable(ground, residual, motion)
                self.assertFalse(result["usable"])
                self.assertTrue(result["reinit_required"])
                self.assertTrue(result["reasons"])


class ImuSemanticsGuardTest(unittest.TestCase):
    def test_empty_and_unknown_verification_values_are_rejected(self):
        semantics = ImuSemantics()
        for field in ("acceleration_units", "angular_velocity_units", "axis_mapping",
                      "bias"):
            for value in (None, "", 0):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    semantics.verify(field, value, "vendor_protocol")
        for units in ("deg/s", "furlong_s2", "m/s2", 1, ["m_s2"]):
            with self.subTest(units=units), self.assertRaises(ValueError):
                semantics.verify("acceleration_units", units, "vendor_protocol")
        self.assertFalse(semantics.units_verified)
        self.assertFalse(semantics.alignment_verified)
        self.assertEqual(semantics.evidence, [])

    def test_non_si_units_are_converted_before_si_thresholds(self):
        semantics = ImuSemantics()
        semantics.verify("acceleration_units", "g", "vendor_protocol")
        semantics.verify("angular_velocity_units", "deg_s", "vendor_protocol")
        semantics.verify("axis_mapping", "x_forward_y_left_z_up", "controlled_attitude")
        static = device_motion_status((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), semantics)
        self.assertEqual(static["status"], "static")
        self.assertEqual(static["comparison_units"], "m_s2/rad_s")
        moving = device_motion_status((0.0, 0.0, 1.0), (0.0, 0.0, 100.0), semantics)
        self.assertEqual(moving["status"], "moving")

    def test_bias_shape_and_finiteness_are_validated(self):
        semantics = ImuSemantics()
        with self.assertRaises(ValueError):
            semantics.verify("bias", [0.0] * 5, "controlled_motion")
        with self.assertRaises(ValueError):
            semantics.verify("bias", [0.0] * 5 + [float("nan")], "controlled_motion")
        with self.assertRaises(ValueError):
            semantics.verify("bias", None, "controlled_motion")
        semantics.verify("bias", [0.0] * 6, "controlled_motion")
        self.assertEqual(semantics.status["bias"], "verified")
        self.assertEqual(len(semantics.values["bias"]), 6)

    def test_six_axis_requires_three_finite_axes_each(self):
        for accel, rate in (([], [0.0, 0.0, 0.0]), ([0.0, 0.0], [0.0] * 3),
                            ([0.0] * 4, [0.0] * 3), ([0.0] * 3, [0.0] * 3 + [1.0]),
                            ([0.0, None, 0.0], [0.0] * 3)):
            with self.subTest(accel=accel, rate=rate):
                self.assertIsNot(six_axis_report(accel, rate)["finite"], True)
        self.assertEqual(six_axis_report([], [0.0] * 3)["reason"],
                         "imu_axis_count_invalid")
        self.assertTrue(six_axis_report([0.0, 0.0, 9.8], [0.0] * 3)["finite"])

    def test_empty_semantics_never_enable_motion_or_fusion(self):
        semantics = ImuSemantics()
        try:
            for field in ("acceleration_units", "angular_velocity_units", "axis_mapping"):
                semantics.verify(field, None, "vendor_protocol")
        except ValueError:
            pass
        result = device_motion_status((0.0, 0.0, 9.80665), (0.0, 0.0, 0.0), semantics)
        self.assertEqual(result["status"], "unknown")
        self.assertFalse(static_background_usable(True, True, result["status"])["usable"])

    def test_axis_mapping_requires_a_valid_right_handed_triad(self):
        semantics = ImuSemantics()
        semantics.verify("acceleration_units", "m_s2", "vendor_protocol")
        semantics.verify("angular_velocity_units", "rad_s", "vendor_protocol")
        for description in ("unknown", "x_forward_x_left_z_up", "x_forward_y_left",
                            "x_forward_y_left_z_up_extra", "x_forward_y_forward_z_up",
                            "x_forward_y_right_z_up", "X_forward_Y_left_Z_up",
                            "x_forward_y_left_w_up", "x_forward_y_left_z_sideways", ""):
            with self.subTest(description=description), self.assertRaises(ValueError):
                semantics.verify("axis_mapping", description, "controlled_attitude")
        self.assertFalse(semantics.alignment_verified)
        self.assertNotIn("axis_mapping", semantics.values)
        self.assertEqual(len(semantics.evidence), 2)
        self.assertEqual(device_motion_status(
            (0.0, 0.0, 9.80665), (0.0, 0.0, 0.0), semantics)["status"], "unknown")
        semantics.verify("axis_mapping", "x_forward_y_left_z_up", "controlled_attitude")
        self.assertTrue(semantics.alignment_verified)
        self.assertEqual(device_motion_status(
            (0.0, 0.0, 9.80665), (0.0, 0.0, 0.0), semantics)["status"], "static")

    def test_supported_axis_triad_variants_are_accepted(self):
        for description in ("x_forward_y_left_z_up", "x_forward_y_up_z_right",
                            "x_backward_y_right_z_up"):
            with self.subTest(description=description):
                semantics = ImuSemantics()
                semantics.verify("acceleration_units", "m_s2", "vendor_protocol")
                semantics.verify("angular_velocity_units", "rad_s", "vendor_protocol")
                semantics.verify("axis_mapping", description, "controlled_attitude")
                self.assertTrue(semantics.alignment_verified)
                self.assertEqual(device_motion_status(
                    (0.0, 0.0, 9.80665), (0.0, 0.0, 0.0), semantics)["status"],
                    "static")


if __name__ == "__main__":
    unittest.main()
