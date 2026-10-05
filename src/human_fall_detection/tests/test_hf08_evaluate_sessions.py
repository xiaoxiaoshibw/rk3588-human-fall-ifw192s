import json
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))

from evaluate_sessions import evaluate_document, main


def session(session_id="synthetic", **values):
    result = {
        "session_id": session_id,
        "prediction_time_domain": "device_stamp_s_unanchored",
        "labels_time_domain": "device_stamp_s_unanchored",
        "time_epoch": 0,
        "split_role": "synthetic",
        "split_group": session_id,
        "dataset_kind": "synthetic",
        "labels_status": "known_synthetic",
        "labeled_events": [],
        "predicted_events": [],
        "negative_intervals": [],
        "event_target_bindings": [],
        "track_observations": [],
        "observation_intervals": [],
    }
    result.update(values)
    return result


def document(sessions):
    return {"schema_version": 1, "dataset_version": "hf08-test-v1",
            "event_time_domain": "device_stamp_s_unanchored",
            "match_tolerance_s": 1.0, "sessions": sessions}


def test_artifacts(with_labels=True):
    artifacts = {role: {"path": "test-fixture/" + role, "sha256": "0" * 64}
                 for role in ("prediction_source", "frozen_parameters", "prediction_data")}
    if with_labels:
        artifacts["human_labels"] = {"path": "test-fixture/human_labels", "sha256": "0" * 64}
    return artifacts


class EvaluateSessionsTest(unittest.TestCase):
    def _evaluate(self, value):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json",
                                         delete=False) as handle:
            json.dump(value, handle)
            path = handle.name
        try:
            return evaluate_document(value, path)
        finally:
            os.unlink(path)

    def test_conflict_matching_is_one_to_one_and_maximizes_matches(self):
        data = session(
            labeled_events=[{"event_id": "l0", "target_id": "p0", "start_s": 100.0},
                            {"event_id": "l1", "target_id": "p0", "start_s": 101.0}],
            event_target_bindings=[{"event_id": "p0", "target_id": "p0"},
                                   {"event_id": "p1", "target_id": "p0"}],
            predicted_events=[{"event_id": "p0", "track_id": "t0", "time_s": 99.5},
                              {"event_id": "p1", "track_id": "t0", "time_s": 100.5}],
        )
        result = self._evaluate(document([data]))["sessions"][0]
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (2, 0, 0))
        self.assertEqual({item["label_event_id"] for item in result["matches"]}, {"l0", "l1"})
        self.assertEqual({item["prediction_event_id"] for item in result["matches"]}, {"p0", "p1"})

    def test_duplicate_predictions_boundary_epoch_and_target_binding(self):
        data = session(
            labeled_events=[{"event_id": "l0", "target_id": "p0", "start_s": 10.0}],
            event_target_bindings=[{"event_id": "edge", "target_id": "p0"},
                                   {"event_id": "duplicate", "target_id": "p0"},
                                   {"event_id": "wrong_epoch", "target_id": "p0"}],
            predicted_events=[{"event_id": "edge", "track_id": "t0", "time_s": 11.0},
                              {"event_id": "duplicate", "track_id": "t0", "time_s": 10.1},
                              {"event_id": "wrong_epoch", "track_id": "t0", "time_epoch": 1,
                               "time_s": 10.0},
                              {"event_id": "unbound", "track_id": "unknown", "time_s": 10.0}],
        )
        result = self._evaluate(document([data]))["sessions"][0]
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (1, 3, 0))
        self.assertEqual(result["unmatched_predictions"], ["edge", "wrong_epoch", "unbound"])
        boundary = session(
            "boundary",
            labeled_events=[{"event_id": "edge-label", "target_id": "p0", "start_s": 100.0}],
            event_target_bindings=[{"event_id": "edge-prediction", "target_id": "p0"}],
            predicted_events=[{"event_id": "edge-prediction", "track_id": "t0", "time_s": 101.0}],
        )
        boundary_result = self._evaluate(document([boundary]))["sessions"][0]
        self.assertEqual((boundary_result["tp"], boundary_result["fp"]), (1, 0))
        wrong_target = session(
            "wrong-target",
            labeled_events=[{"event_id": "person-a-fall", "target_id": "person-a",
                             "start_s": 100.0}],
            event_target_bindings=[{"event_id": "person-b-prediction", "target_id": "person-b"}],
            predicted_events=[{"event_id": "person-b-prediction", "track_id": "t0002",
                               "time_s": 100.0}],
        )
        target_result = self._evaluate(document([wrong_target]))["sessions"][0]
        self.assertEqual((target_result["tp"], target_result["fp"], target_result["fn"]),
                         (0, 1, 1))

    def test_negative_duration_zero_denominators_latency_switches_and_observation(self):
        data = session(
            labeled_events=[{"event_id": "l0", "target_id": "p0", "start_s": 2.0}],
            event_target_bindings=[{"event_id": "p0", "target_id": "p0"},
                                   {"event_id": "negative_fp", "target_id": "p0"}],
            predicted_events=[{"event_id": "p0", "track_id": "t0", "time_s": 2.25},
                              {"event_id": "negative_fp", "track_id": "t0", "time_s": 20.0}],
            negative_intervals=[{"time_epoch": 0, "start_s": 20.0, "end_s": 30.0},
                                {"time_epoch": 0, "start_s": 25.0, "end_s": 35.0},
                                {"time_epoch": 1, "start_s": 20.0, "end_s": 30.0}],
            track_observations=[{"target_id": "p0", "track_id": "t0", "time_s": 1.0},
                                {"target_id": "p0", "track_id": "t1", "time_s": 2.0}],
            observation_intervals=[{"start_s": 0.0, "end_s": 3.0, "observability": "valid"},
                                   {"start_s": 3.0, "end_s": 5.0, "observability": "degraded"}],
        )
        result = self._evaluate(document([data]))["sessions"][0]
        self.assertEqual(result["negative_duration_s"], 25.0)
        self.assertEqual(result["false_alarms_per_hour"], 144.0)
        self.assertEqual(result["latency_s"]["values"], [0.25])
        self.assertEqual(result["track_switches"], 1)
        self.assertEqual(result["effective_observation_s"], 3.0)
        self.assertEqual(result["observation_window_s"], 5.0)
        self.assertEqual(result["effective_observation_fraction"], 0.6)

    def test_unlabeled_and_empty_data_never_turn_into_pass_metrics(self):
        pending = session("pending", split_role="blind_test", dataset_kind="offline",
                          labels_status="pending", labels_time_domain=None, labeled_events=None,
                          predicted_events=[], negative_intervals=None,
                          track_observations=None, observation_intervals=None,
                          artifacts=test_artifacts(with_labels=False))
        partial = session(
            "partial", split_role="blind_test", dataset_kind="offline",
            labels_status="human_reviewed",
            artifacts=test_artifacts(),
            labeled_events=[{"event_id": "missing-prediction", "target_id": "p0",
                             "start_s": 100.0}],
        )
        empty = session("empty")
        report = self._evaluate(document([pending, partial, empty]))
        self.assertEqual(report["status"], "pending_annotation")
        self.assertEqual(report["sessions"][0]["status"], "pending_annotation")
        self.assertIsNone(report["sessions"][0]["precision"])
        self.assertIsNone(report["sessions"][0]["recall"])
        self.assertIsNone(report["sessions"][0]["false_alarms_per_hour"])
        self.assertEqual(report["aggregates"][0]["status"], "pending_annotation")
        self.assertIsNone(report["aggregates"][0]["recall"])
        self.assertEqual(report["sessions"][2]["status"], "no_data")
        self.assertIsNone(report["sessions"][2]["precision"])
        self.assertIsNone(report["sessions"][2]["recall"])
        self.assertIsNone(report["sessions"][2]["false_alarms_per_hour"])

    def test_zero_negative_time_and_zero_event_denominators_are_null(self):
        result = self._evaluate(document([session()]))["sessions"][0]
        self.assertEqual(result["status"], "no_data")
        self.assertEqual(result["tp"], 0)
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["recall"])
        self.assertEqual(result["negative_duration_s"], 0.0)
        self.assertIsNone(result["false_alarms_per_hour"])

    def test_cli_output_is_byte_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = os.path.join(directory, "input.json")
            out_a = os.path.join(directory, "a.json")
            out_b = os.path.join(directory, "b.json")
            with open(input_path, "w", encoding="utf-8") as target:
                json.dump(document([session()]), target)
            self.assertEqual(main(["--input", input_path, "--output", out_a]), 0)
            self.assertEqual(main(["--input", input_path, "--output", out_b]), 0)
            with open(out_a, "rb") as source:
                first = source.read()
            with open(out_b, "rb") as source:
                second = source.read()
            self.assertEqual(first, second)

    def test_reads_hf07_event_jsonl_and_checks_its_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            prediction_path = os.path.join(directory, "events.jsonl")
            event = {"kind": "event", "event_id": "device-event", "session_id": "device-1",
                     "time_epoch": 0, "track_id": "t0001", "start_source_s": 101.0}
            content = (json.dumps(event) + "\n").encode("utf-8")
            with open(prediction_path, "wb") as target:
                target.write(content)
            digest = hashlib.sha256(content).hexdigest()
            data = session(
                "device-1", split_role="tuning", split_group="device-1",
                dataset_kind="offline", labels_status="human_reviewed", predicted_events=None,
                predicted_events_path="events.jsonl",
                labeled_events=[{"event_id": "truth", "target_id": "p0", "start_s": 100.0}],
                event_target_bindings=[{"event_id": "device-event", "target_id": "p0"}],
                artifacts=test_artifacts(),
            )
            data["artifacts"]["prediction_data"] = {
                "path": "events.jsonl", "sha256": digest}
            report_path = os.path.join(directory, "dataset.json")
            with open(report_path, "w", encoding="utf-8") as target:
                json.dump(document([data]), target)
            with open(report_path, encoding="utf-8") as source:
                report = evaluate_document(json.load(source), report_path)
            self.assertEqual(report["sessions"][0]["tp"], 1)
            self.assertEqual(report["sessions"][0]["matches"][0]["latency_s"], 1.0)
            data["artifacts"]["prediction_data"]["sha256"] = "0" * 64
            with open(report_path, "w", encoding="utf-8") as target:
                json.dump(document([data]), target)
            with open(report_path, encoding="utf-8") as source:
                with self.assertRaisesRegex(ValueError, "SHA256 does not match"):
                    evaluate_document(json.load(source), report_path)

    def test_nonmatching_tolerance_and_split_group_leakage_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "fixed at"):
            self._evaluate({**document([]), "match_tolerance_s": 0.25})
        mixed_clock = session("mixed_clock", labels_time_domain="host_monotonic")
        with self.assertRaisesRegex(ValueError, "time domains must match"):
            self._evaluate(document([mixed_clock]))
        a = session("tuning", split_role="tuning", dataset_kind="offline", labels_status="human_reviewed", split_group="same",
                    artifacts=test_artifacts())
        b = session("blind", split_role="blind_test", dataset_kind="offline", labels_status="human_reviewed", split_group="same",
                    artifacts=test_artifacts())
        with self.assertRaisesRegex(ValueError, "multiple split roles"):
            self._evaluate(document([a, b]))

    def test_schema_version_bool_is_not_an_integer_version(self):
        with self.assertRaisesRegex(ValueError, "schema_version must be 1"):
            evaluate_document({"schema_version": True}, "unused.json")


if __name__ == "__main__":
    unittest.main()
