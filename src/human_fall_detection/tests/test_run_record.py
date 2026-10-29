"""Run-record regression: transitions, suspected hints, rotation, failure paths."""
import json
import os
import tempfile
import unittest

from core.run_record import RunRecorder


class Clock:
    def __init__(self, value=1000.0):
        self.value = float(value)

    def __call__(self):
        return self.value


def _state(**overrides):
    state = {
        "session_id": "hfd_test",
        "time_epoch": 1000.0,
        "track_id": None,
        "track_status": "unselected",
        "action_generation": 0,
        "selection_version": None,
        "source": {"seq": 1, "stamp_secs": 12.0, "stamp_nsecs": 0, "frame_id": "innolidar"},
        "observability": "ok",
        "reason_codes": ["waiting_for_target"],
        "fall_status": "unknown",
        "acquisition": {"status": "searching", "reason": None},
        "baseline": {"status": "idle", "reason": None, "sample_count": 0},
        "fall_state": {"state_since_source_s": None, "reason_codes": [],
                       "features": {"height_median_m": 1.6}},
        "sensor_quality": {"cloud": {"status": "fresh", "age_s": 0.01}},
        "confirmed_enabled": False,
        "mode_verified": False,
        "input_source": {"mode": "live_lidar", "evidence": "test"},
        "worker": {"healthy": True, "errors": 0},
    }
    state.update(overrides)
    return state


class RunRecorderTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "run_events.jsonl")
        self.clock = Clock()
        self.recorders = []

    def tearDown(self):
        for recorder in self.recorders:
            recorder.close()
        self.dir.cleanup()

    def _read(self):
        with open(self.path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def _recorder(self, **kwargs):
        kwargs.setdefault("run_id", "run-1")
        kwargs.setdefault("release_id", "rel-1")
        kwargs.setdefault("scene_id", "scene-1")
        kwargs.setdefault("wall_fn", self.clock)
        recorder = RunRecorder(self.path, **kwargs)
        self.recorders.append(recorder)
        return recorder

    def test_identical_states_write_once(self):
        recorder = self._recorder()
        recorder.start({"argv": ["node"]})
        first = recorder.observe(_state())
        second = recorder.observe(_state())
        self.assertEqual(second, [])
        self.assertTrue(any(r["event"] == "run_start" for r in self._read()))
        self.assertTrue(first)
        for record in first:
            self.assertEqual(record["run_id"], "run-1")
            self.assertEqual(record["release_id"], "rel-1")
            self.assertEqual(record["scene_id"], "scene-1")

    def test_target_and_baseline_transitions(self):
        recorder = self._recorder()
        recorder.observe(_state())
        records = recorder.observe(_state(track_id="t0001", track_status="locked",
                                          baseline={"status": "pending", "reason": None,
                                                    "sample_count": 3}))
        events = {(r["event"], json.dumps(r["to"])) for r in records}
        self.assertIn(("target_transition", '"locked"'), events)
        self.assertIn(("baseline_transition", '["pending", null]'), events)

    def test_suspected_notification_ids_and_end(self):
        recorder = self._recorder()
        recorder.observe(_state(track_id="t1", track_status="locked",
                                fall_status="low_posture_unclassified"))
        recorder.observe(_state(track_id="t1", track_status="locked", fall_status="suspected"))
        report = recorder.report()
        self.assertEqual(report["notifications"], 1)
        first = report["last_notification"]["notification_id"]
        self.clock.value += 2.5
        recorder.observe(_state(track_id="t1", track_status="locked", fall_status="upright"))
        report = recorder.report()
        self.assertEqual(report["notifications"], 1)
        self.assertEqual(report["last_notification"]["end_state"], "upright")
        records = [r for r in self._read() if r["event"] == "suspected_notification"]
        self.assertEqual([r["action"] for r in records], ["start", "end"])
        self.assertEqual(records[1]["notification_id"], first)
        self.assertGreaterEqual(records[1]["duration_s"], 0.0)
        self.assertEqual(records[1]["to_state"], "upright")

    def test_second_suspected_episode_gets_new_id(self):
        recorder = self._recorder()
        recorder.observe(_state(track_id="t1", track_status="locked", fall_status="suspected"))
        first = recorder.report()["last_notification"]["notification_id"]
        recorder.observe(_state(track_id="t1", track_status="locked", fall_status="upright"))
        recorder.observe(_state(track_id="t1", track_status="locked", fall_status="suspected"))
        second = recorder.report()["last_notification"]["notification_id"]
        self.assertNotEqual(first, second)
        records = [r for r in self._read() if r["event"] == "suspected_notification"]
        self.assertEqual([r["action"] for r in records], ["start", "end", "start"])

    def test_reason_and_input_source_change(self):
        recorder = self._recorder()
        recorder.observe(_state())
        records = recorder.observe(_state(reason_codes=["ground_unavailable"],
                                          input_source={"mode": "unknown"}))
        events = {r["event"] for r in records}
        self.assertIn("reason_change", events)
        self.assertIn("input_source_change", events)
        input_record = [r for r in records if r["event"] == "input_source_change"][0]
        self.assertEqual(input_record["to"], "unknown")
        self.assertEqual(recorder.observe(_state(reason_codes=["ground_unavailable"],
                                                input_source={"mode": "unknown"})), [])

    def test_performance_window(self):
        recorder = self._recorder(perf_interval_s=30.0)
        for value in (0.10, 0.20, 0.30):
            recorder.observe(_state(), {"process_s": value, "receive_to_finish_s": value * 2,
                                        "queue_dropped": 0})
        self.assertEqual([r for r in self._read() if r["event"] == "performance_window"], [])
        self.clock.value += 31.0
        recorder.observe(_state(), {"process_s": 0.4, "receive_to_finish_s": 0.8,
                                    "queue_dropped": 2})
        windows = [r for r in self._read() if r["event"] == "performance_window"]
        self.assertTrue(windows)
        self.assertEqual(windows[0]["frames"], 3)
        self.assertAlmostEqual(windows[0]["summary"]["process_s"]["p50"], 0.20, places=6)
        self.assertAlmostEqual(windows[0]["summary"]["receive_to_finish_s"]["max"], 0.60,
                               places=6)

    def test_drop_delta_includes_boundary_and_survives_sample_compaction(self):
        recorder = self._recorder(perf_interval_s=30.)
        recorder.observe(_state(), dict(process_s=.1, queue_dropped=0))
        self.clock.value += 31.
        # The only drop occurs between the last sample of window 1 and first of 2.
        recorder.observe(_state(), dict(process_s=.1, queue_dropped=1))
        for i in range(4100):
            recorder.observe(_state(), dict(process_s=.1, queue_dropped=i + 2))
        recorder.close()
        windows = [r for r in self._read() if r['event'] == 'performance_window']
        self.assertEqual(sum(w['summary']['queue_dropped_delta'] for w in windows), 4101)
        self.assertEqual(windows[1]['summary']['queue_dropped_delta_base'], 0)
        self.assertEqual(sum(w['frames'] for w in windows), 4102)

    def test_cached_performance_is_counted_once_across_status_refreshes(self):
        recorder = self._recorder(perf_interval_s=30.)
        perf = dict(frame_count=1, process_finish_s=100., process_s=.1, queue_dropped=0)
        recorder.observe(_state(), perf)
        for _ in range(4):
            recorder.observe(_state(), dict(perf))
        self.clock.value += 31.
        recorder.observe(_state(), dict(perf))
        recorder.observe(_state(), dict(perf, frame_count=2, process_finish_s=101.))
        recorder.close()
        windows = [r for r in self._read() if r['event'] == 'performance_window']
        self.assertEqual(sum(w['frames'] for w in windows), 2)

    def test_rotation_is_bounded(self):
        recorder = self._recorder(max_bytes=1200, max_archives=2)
        for index in range(60):
            recorder.observe(_state(source={"seq": index, "stamp_secs": float(index),
                                            "stamp_nsecs": 0, "frame_id": "innolidar"}))
        recorder.close()
        archives = [name for name in os.listdir(self.dir.name) if ".jsonl." in name]
        self.assertLessEqual(len(archives), 2)
        self.assertTrue(os.path.exists(self.path))

    def test_write_failure_is_reported_not_raised(self):
        bad_path = os.path.join(self.dir.name, "as-directory", "events.jsonl")
        os.makedirs(bad_path)
        recorder = RunRecorder(bad_path, run_id="run-x", wall_fn=self.clock)
        observed = recorder.observe(_state())
        self.assertEqual(observed, [])
        self.assertIsNotNone(recorder.write_error)
        recorder.close()

    def test_nan_values_do_not_break_serialization(self):
        recorder = self._recorder()
        state = _state(track_id="t1", track_status="locked")
        state["source"] = {"seq": 1, "stamp_secs": float("nan"), "stamp_nsecs": 0,
                           "frame_id": "innolidar"}
        recorder.observe(state)
        records = self._read()
        self.assertTrue(records)
        for record in records:
            json.dumps(record, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
