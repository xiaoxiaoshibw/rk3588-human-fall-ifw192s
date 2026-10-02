"""Independent check that lighter ROS payloads leave selection evidence intact."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/human_fall_detection"))
from core.node_runtime import FallNodeCore, project_snapshot_for_ros
from review_hf07_codex import cloud, command


class TransportProjection(unittest.TestCase):
    def test_reused_candidate_id_does_not_replace_lost_target_geometry(self):
        core = FallNodeCore("review")
        first = core.process(cloud(), 10, seq=1, stamp_secs=100,
            stamp_nsecs=0, frame_id="innolidar", now=10)["snapshot"]
        self.assertTrue(core.handle_request(command(first), 10.01)["accepted"])
        state = core.process(cloud() + [4, 0, 0], 14, seq=2, stamp_secs=104,
            stamp_nsecs=0, frame_id="innolidar", now=14)["state"]
        self.assertEqual(state["track_status"], "lost")
        self.assertIsNone(state["position_source_m"])
        self.assertIsNone(state["range_m"])
        self.assertIsNone(state["bbox_source_min_m"])
        self.assertFalse(state["bbox_observed"])

    def test_reused_candidate_id_is_not_a_measurement_during_occlusion(self):
        core = FallNodeCore("review")
        first = core.process(cloud(), 10, seq=1, stamp_secs=100,
            stamp_nsecs=0, frame_id="innolidar", now=10)["snapshot"]
        self.assertTrue(core.handle_request(command(first), 10.01)["accepted"])
        state = core.process(cloud() + [4, 0, 0], 10.1, seq=2, stamp_secs=100,
            stamp_nsecs=100000000, frame_id="innolidar", now=10.1)["state"]
        self.assertEqual(state["track_status"], "occluded")
        self.assertTrue(state["position_predicted"])
        self.assertLess(state["position_source_m"][0], 4)
        self.assertFalse(state["bbox_observed"])
        self.assertIsNone(state["range_m"])

    def test_projection_preserves_cached_snapshot_and_selection(self):
        core = FallNodeCore("review")
        original = core.process(cloud(), 10, seq=1, stamp_secs=100,
            stamp_nsecs=0, frame_id="innolidar", now=10)["snapshot"]
        before = json.dumps(original, sort_keys=True)
        wire = project_snapshot_for_ros(original)
        self.assertEqual(json.dumps(original, sort_keys=True), before)
        self.assertIsNot(wire, original)
        self.assertIsNot(wire["candidates"][0], original["candidates"][0])
        self.assertIn("evidence_indices", original["candidates"][0])
        self.assertNotIn("evidence_indices", wire["candidates"][0])
        self.assertEqual(wire["source"], original["source"])
        self.assertLess(len(json.dumps(wire)), len(json.dumps(original)))
        self.assertTrue(core.handle_request(command(wire), 10.01)["accepted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
