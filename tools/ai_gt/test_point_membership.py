"""Self-check for the point-membership GT channel (no real labels involved)."""
import json
import tempfile
import unittest
from pathlib import Path

import point_membership as pm

SOURCE = {"meta_sha256": "0" * 64, "points_sha256": "1" * 64}


def labels(rows):
    return {"schema": pm.SCHEMA, "sid": "SYNTHETIC", "source": SOURCE, "frame": 0,
            "labels": [{"source_row": row, "label": label} for row, label in rows]}


class PointMembership(unittest.TestCase):
    def test_score_counts_and_metrics(self):
        doc = labels([(row, "HUMAN") for row in range(10)]
                     + [(row, "NON_HUMAN") for row in range(10, 20)]
                     + [(20, "UNCERTAIN")])
        result = pm.score(doc, {"sid": "SYNTHETIC", "frame": 0,
                                "rows": [0, 1, 2, 3, 4, 5, 10, 11, 20]})
        self.assertEqual(result["counts"]["TP"], 6)
        self.assertEqual(result["counts"]["FP"], 2)
        self.assertEqual(result["counts"]["FN"], 4)
        self.assertEqual(result["counts"]["uncertain_predicted"], 1)
        self.assertAlmostEqual(result["purity"], 0.75)
        self.assertAlmostEqual(result["recall"], 0.6)
        self.assertEqual(result["status"], "SCORED")

    def test_unlabeled_prediction_makes_metrics_unknown(self):
        doc = labels([(0, "HUMAN")])
        result = pm.score(doc, {"sid": "SYNTHETIC", "frame": 0, "rows": [0, 1]})
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIsNone(result["purity"])
        self.assertIsNone(result["recall"])
        self.assertEqual(result["reason"], "UNLABELED_PREDICTED_ROWS")

    def test_empty_labels_rejected(self):
        with self.assertRaises(ValueError):
            pm.validate_labels({"schema": pm.SCHEMA, "sid": "SYNTHETIC",
                                "source": SOURCE, "frame": 0, "labels": []})

    def test_conflicting_row_flags_audit_and_blocks_score(self):
        doc = labels([(1, "HUMAN"), (1, "NON_HUMAN")])
        self.assertFalse(pm.audit(doc)["ok"])
        with self.assertRaises(ValueError):
            pm.score(doc, {"sid": "SYNTHETIC", "frame": 0, "rows": [1]})

    def test_audit_detects_frame_bounds_and_conflict(self):
        with tempfile.TemporaryDirectory() as folder:
            meta = Path(folder) / "meta.json"
            meta.write_text(json.dumps({"frames": [{"offset_points": 100, "count_points": 10}]}),
                            encoding="utf8")
            inside = labels([(105, "HUMAN")])
            self.assertTrue(pm.audit(inside, meta)["ok"])
            outside = labels([(105, "HUMAN"), (200, "NON_HUMAN")])
            report = pm.audit(outside, meta)
            self.assertFalse(report["ok"])
            self.assertEqual(report["outside_frame_rows"], [200])
            conflict = {"schema": pm.SCHEMA, "sid": "SYNTHETIC", "source": SOURCE,
                        "frame": 0, "labels": [{"source_row": 1, "label": "HUMAN"}]}
            conflict["labels"].append({"source_row": 1, "label": "NON_HUMAN"})
            self.assertFalse(pm.audit(conflict)["ok"])
            self.assertTrue(pm.audit(inside)["ok"])

    def test_prediction_binding_mismatch_rejected(self):
        doc = labels([(0, "HUMAN")])
        with self.assertRaises(ValueError):
            pm.score(doc, {"sid": "OTHER", "frame": 0, "rows": [0]})

    def test_selfcheck_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "bundle"
            result = pm.selfcheck(out)
            self.assertTrue(result["ok"])
            self.assertTrue((out / "SELFCHECK.json").is_file())


if __name__ == "__main__":
    unittest.main()
