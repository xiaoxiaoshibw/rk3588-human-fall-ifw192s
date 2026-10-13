"""Minimal negative cases for GT version selection, binding and compressed indices."""
import json
import pathlib
import tempfile
import unittest

from frozen_gt import audit_session, decode_indices, sha


class FrozenGTTest(unittest.TestCase):
    def test_encodings_and_invalid(self):
        self.assertEqual(decode_indices(["s", 1, 4]).tolist(), [1, 4])
        self.assertEqual(decode_indices(["r", 2, 3, 4]).tolist(), [2, 5, 8, 11])
        self.assertEqual(decode_indices(["m", [2, 3, 4], [20]]).tolist(), [2, 5, 8, 11, 20])
        for v in (["s"], ["s", 1, 1], ["s", -1], ["r", 1, 0, 2], ["r", 1, 1, -1], ["bad"]):
            with self.assertRaises(ValueError):
                decode_indices(v)

    def test_binding_and_skip_e2e(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            store, capture, sid = root / "store", root / "capture", "synthetic"
            sd, cd = store / sid, capture / sid
            sd.mkdir(parents=True)
            cd.mkdir(parents=True)
            def put(p, doc):
                p.write_text(json.dumps(doc), encoding="utf-8")
            put(cd / "meta.json", {"point_stride_bytes": 28, "frames": [{"count_points": 10}]})
            (cd / "points.bin").write_bytes(bytes(280))
            doc = {"session_id": sid, "schema_version": "gt_workbench/1", "review_status": "reviewed",
                   "session_sha256": {"points": sha(cd / "points.bin"), "meta": sha(cd / "meta.json")},
                   "objects": {"a": {"session_id": sid, "object_id": "a", "frame_idx": 0, "class_name": "PERSON",
                                      "track_id": "P1", "review_status": "reviewed", "source": "human",
                                      "coordinate_frame": "leveled-IFW192S", "leveling_transform_id": "render_person_label.R/T",
                                      "point_count": 2, "raw_point_indices": ["s", 0, 1]}},
                   "frames_objects": {"0": ["a"]}}
            put(sd / "GT_V1.json", doc)
            versions = [{"version": "V1", "annotator": "human", "sha256": sha(sd / "GT_V1.json"), "object_count": 1},
                        {"version": "V2", "annotator": "e2e", "sha256": "bad", "object_count": 0}]
            put(sd / "manifest.json", {"versions": versions})
            r, _, _ = audit_session(sid, store, capture)
            self.assertTrue(r["eligible"])
            self.assertEqual(r["version"], "V1")
            doc["session_sha256"]["points"] = "a" * 64
            put(sd / "GT_V1.json", doc)
            versions[0]["sha256"] = sha(sd / "GT_V1.json")
            put(sd / "manifest.json", {"versions": versions})
            r, _, _ = audit_session(sid, store, capture)
            self.assertFalse(r["eligible"])
            self.assertIn("SESSION_SHA_MISMATCH_OR_MISSING", r["issues"])
            versions[0]["annotator"] = "e2e"
            put(sd / "manifest.json", {"versions": versions[:1]})
            r, _, _ = audit_session(sid, store, capture)
            self.assertIn("NO_USABLE_NON_E2E_VERSION", r["issues"])


if __name__ == "__main__":
    unittest.main()
