"""Independent evaluation checks across clock restarts."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "hf08_eval", ROOT / "src/human_fall_detection/scripts/evaluate_sessions.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def dataset():
    return {"schema_version": 1, "dataset_version": "independent",
            "event_time_domain": "device_stamp_s_unanchored", "match_tolerance_s": 1.0,
            "sessions": [{"session_id": "r", "time_epoch": 0,
                "prediction_time_domain": "device_stamp_s_unanchored",
                "labels_time_domain": "device_stamp_s_unanchored",
                "split_role": "synthetic", "split_group": "r", "dataset_kind": "synthetic",
                "labels_status": "known_synthetic", "labeled_events": [],
                "predicted_events": [], "track_bindings": [], "track_observations": [],
                "negative_intervals": [], "observation_intervals": []}]}


def evaluate(data):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "input.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return ev.evaluate_document(data, str(path))["sessions"][0]


class EpochDenominator(unittest.TestCase):
    def test_boolean_schema_version_rejected(self):
        data = dataset()
        data["schema_version"] = True
        with self.assertRaises(ValueError):
            evaluate(data)

    def test_overlapping_numeric_seconds_across_epochs_add_duration(self):
        data = dataset()
        data["sessions"][0]["negative_intervals"] = [
            {"time_epoch": 0, "start_s": 0, "end_s": 3600},
            {"time_epoch": 1, "start_s": 0, "end_s": 3600}]
        self.assertEqual(evaluate(data)["negative_duration_s"], 7200)

    def test_negative_interval_in_another_epoch_does_not_count_event(self):
        data = dataset()
        session = data["sessions"][0]
        session["negative_intervals"] = [{"time_epoch": 0, "start_s": 0, "end_s": 3600}]
        session["predicted_events"] = [{"event_id": "p", "track_id": "t",
                                        "time_epoch": 1, "time_s": 10}]
        self.assertEqual(evaluate(data)["negative_fp_count"], 0)

    def test_observation_duration_is_separate_across_epochs(self):
        data = dataset()
        data["sessions"][0]["observation_intervals"] = [
            {"time_epoch": 0, "start_s": 0, "end_s": 10, "observability": "valid"},
            {"time_epoch": 1, "start_s": 0, "end_s": 10, "observability": "invalid"}]
        result = evaluate(data)
        self.assertEqual(result["observation_window_s"], 20)
        self.assertEqual(result["effective_observation_fraction"], 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
