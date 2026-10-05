"""HF-09 profiler parsing/bounds tests. No ROS: pure helpers only."""

import sys
import unittest
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))

from core.node_runtime import dumps_strict, sample_point_data
from human_fall_node import performance_block
from profile_pipeline import (_finite_positive, _latency_stats, _ms,
                              _percentile, frame_key, parse_state)


def state_payload(seq=5, secs=100, nsecs=250000000, session="s", epoch=0,
                  kind="target_state", version=1):
    return {"kind": kind, "schema_version": version, "session_id": session,
            "time_epoch": epoch,
            "source": {"seq": seq, "stamp_secs": secs, "stamp_nsecs": nsecs,
                       "source_stamp_s": secs + nsecs / 1e9}}


class FiniteWindowTest(unittest.TestCase):
    def test_rejects_nonpositive_and_nonfinite(self):
        for bad in (0, -1, -0.5, float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError):
                _finite_positive(bad, "duration")

    def test_accepts_finite_positive(self):
        self.assertEqual(_finite_positive(1800, "duration"), 1800.0)
        self.assertEqual(_finite_positive("10.5", "window"), 10.5)


class ParseStateTest(unittest.TestCase):
    def test_rejects_bad_json_and_unknown_schema(self):
        self.assertIsNone(parse_state("{not json"))
        self.assertIsNone(parse_state("null"))
        self.assertIsNone(parse_state('{"kind": "target_state", "schema_version": 999}'))
        self.assertIsNone(parse_state('{"kind": "other", "schema_version": 1}'))

    def test_boolean_version_is_not_a_supported_integer_schema(self):
        import json
        self.assertIsNone(parse_state(json.dumps(
            {"kind": "target_state", "schema_version": True})))

    def test_accepts_valid_state(self):
        import json
        payload = parse_state(json.dumps(state_payload()))
        self.assertIsNotNone(payload)
        self.assertEqual(payload["kind"], "target_state")


class FrameKeyTest(unittest.TestCase):
    def test_key_includes_session_epoch_and_stamp(self):
        base = frame_key(state_payload())
        self.assertEqual(base, ("s", 0, 5, 100, 250000000))
        # Same seq but a different stamp is a different frame (restart/repeat seq).
        self.assertNotEqual(base, frame_key(state_payload(nsecs=260000000)))
        # Same source frame in a new epoch/session is not a duplicate.
        self.assertNotEqual(base, frame_key(state_payload(epoch=1)))
        self.assertNotEqual(base, frame_key(state_payload(session="s2")))

    def test_missing_source_is_not_a_frame(self):
        self.assertIsNone(frame_key({"session_id": "s", "time_epoch": 0}))
        self.assertIsNone(frame_key({"session_id": "s", "time_epoch": 0,
                                     "source": {"seq": None, "stamp_secs": 1,
                                                "stamp_nsecs": 0}}))

    def test_malformed_header_returns_none_without_raising(self):
        valid = state_payload()
        for field, bad in [("seq", "garbage"), ("stamp_secs", 100.5),
                           ("stamp_nsecs", 1000000000), ("seq", True)]:
            payload = dict(valid, source=dict(valid["source"], **{field: bad}))
            self.assertIsNone(frame_key(payload), (field, bad))
        # Whole-payload non-dict / bad epoch also rejected.
        self.assertIsNone(frame_key(None))
        self.assertIsNone(frame_key(dict(valid, time_epoch=True)))


class PercentileTest(unittest.TestCase):
    def test_linear_interpolation_and_empty(self):
        self.assertIsNone(_percentile([], 0.5))
        self.assertEqual(_percentile([2.0], 0.95), 2.0)
        self.assertAlmostEqual(_percentile([0.0, 0.1], 0.5), 0.05)
        self.assertAlmostEqual(_percentile([0.0, 0.1], 0.95), 0.095)

    def test_ms_handles_absent_and_invalid(self):
        self.assertIsNone(_ms(None))
        self.assertIsNone(_ms("nope"))
        self.assertIsNone(_ms(float("nan")))
        self.assertAlmostEqual(_ms(0.25), 250.0)

    def test_negative_or_boolean_latency_is_not_a_sample(self):
        for value in (-1, True, False, float("nan"), float("inf"), float("-inf")):
            self.assertIsNone(_ms(value), value)
        self.assertEqual(_ms(0), 0)
        self.assertEqual(_ms(0.075), 75)


class LatencyStatsTest(unittest.TestCase):
    def test_window_filters_by_timestamp(self):
        samples = [(1.0, 10.0), (1.0, 20.0), (5.0, 100.0)]
        stats = _latency_stats(samples, None, 4.0)
        self.assertEqual(stats["count"], 3)
        self.assertAlmostEqual(stats["p50"], 20.0)       # overall
        self.assertEqual(stats["window_p50"], 100.0)     # only t >= 4.0
        empty = _latency_stats([], None, 0.0)
        self.assertIsNone(empty["p50"])
        self.assertIsNone(empty["window_p95"])


class LatencyStatsConcurrencyTest(unittest.TestCase):
    def test_mutation_during_iteration_is_safe(self):
        import threading
        import time as _time
        from collections import deque
        samples = deque(maxlen=64)
        stop = threading.Event()

        def producer():
            while not stop.is_set():
                samples.append((_time.monotonic(), 1.0))

        thread = threading.Thread(target=producer)
        thread.start()
        try:
            for _ in range(2000):
                stats = _latency_stats(samples, None, 0.0)
                self.assertIn("p50", stats)
        finally:
            stop.set()
            thread.join(2)


class PerformanceBlockTest(unittest.TestCase):
    def test_fields_and_finite_serializable(self):
        block = performance_block(7, 3, True, False, 10.0, 10.02, 10.05, 0.03,
                                  0.05, False, "unknown")
        self.assertEqual(block["kind"], "performance")
        self.assertEqual(block["schema_version"], 1)
        self.assertEqual(block["frame_count"], 7)
        self.assertEqual(block["queue_dropped"], 3)
        self.assertTrue(block["input_valid"])
        self.assertFalse(block["suppressed"])
        self.assertAlmostEqual(block["queue_age_s"], 0.02, places=6)
        self.assertAlmostEqual(block["process_s"], 0.03, places=6)
        self.assertAlmostEqual(block["receive_to_finish_s"], 0.05, places=6)
        dumps_strict({"state": block})  # optional block stays JSON-serializable

    def test_missing_start_leaves_queue_age_null(self):
        block = performance_block(0, 0, False, True, 5.0, None, 5.1, None, 0.1,
                                  False, None)
        self.assertIsNone(block["queue_age_s"])
        self.assertTrue(block["suppressed"])
        self.assertIsNone(block["process_s"])


class DisplaySamplingTest(unittest.TestCase):
    def test_flat_stride_copies_whole_points_without_mutating_source(self):
        data = bytes(i % 256 for i in range(16 * 10))
        out, count, total = sample_point_data(data, 16, 160, 1, 10,
                                              stride=2, max_points=100)
        self.assertEqual((count, total), (5, 10))
        for i in range(count):
            self.assertEqual(out[i * 16:(i + 1) * 16],
                             data[(i * 2) * 16:(i * 2 + 1) * 16])
        self.assertEqual(len(data), 160)  # caller buffer unchanged

    def test_organized_cloud_uses_row_step_for_padding(self):
        # height 2, width 3, point_step 16, row_step 64 (16 bytes row padding)
        data = bytes(i % 251 for i in range(64 + 3 * 16))
        out, count, total = sample_point_data(data, 16, 64, 2, 3,
                                              stride=1, max_points=100)
        self.assertEqual((count, total), (6, 6))
        for row in range(2):
            for col in range(3):
                index = row * 3 + col
                offset = row * 64 + col * 16
                self.assertEqual(out[index * 16:(index + 1) * 16],
                                 data[offset:offset + 16])

    def test_invalid_layout_never_fabricates_display(self):
        self.assertEqual(sample_point_data(b"", 0, 0, 1, 0, 4, 10), (None, 0, 0))
        self.assertEqual(sample_point_data(b"\x00" * 10, 16, 160, 1, 10, 4, 100),
                         (None, 0, 0))                      # data too short
        self.assertEqual(sample_point_data(b"\x00" * 160, 16, 16, 1, 10, 4, 100),
                         (None, 0, 0))                      # row_step < width*step

    def test_max_points_cap(self):
        data = bytes(16 * 10)
        out, count, total = sample_point_data(data, 16, 160, 1, 10,
                                              stride=1, max_points=3)
        self.assertEqual((count, total), (3, 10))
        self.assertEqual(len(out), 3 * 16)


if __name__ == "__main__":
    unittest.main()
