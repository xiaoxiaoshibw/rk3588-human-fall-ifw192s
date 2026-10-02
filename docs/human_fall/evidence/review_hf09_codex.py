"""Independent ROS adapter clock and stalled-stream checks, ROS-free."""
import sys
import threading
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/human_fall_detection"))
sys.path.insert(0, str(ROOT / "src/human_fall_detection/scripts"))
from core.node_runtime import FallNodeCore
from core.ground import fit_ground_plane
from human_fall_node import build_core
from review_hf07_codex import cloud, command


def upright_core():
    x, y = np.meshgrid(np.linspace(-4, 4, 25), np.linspace(-4, 4, 25))
    floor = np.column_stack((x.ravel(), y.ravel(), np.full(x.size, -1.5)))
    ground = fit_ground_plane(floor, {"range_min_m": 0}, frame="innolidar")
    core = FallNodeCore("review", {"baseline": {"require_seconds": 0.2,
        "max_duration_s": 1, "min_samples": 3}}, ground=ground,
        calibration={"calibration_id": "geo", "frames": {"lidar": "innolidar", "reference": None}})
    result = core.process(cloud(), 10, seq=1, stamp_secs=100,
                          stamp_nsecs=0, frame_id="innolidar", now=10)
    selected = core.handle_request(command(result["snapshot"]), 10.01)
    capture = command(result["snapshot"], "capture", 1)
    capture.update(action="capture_baseline", track_id=selected["track_id"])
    assert core.handle_request(capture, 10.02)["accepted"]
    for index in range(1, 6):
        result = core.process(cloud(), 10 + index * 0.1, seq=index + 1,
            stamp_secs=100, stamp_nsecs=index * 100000000,
            frame_id="innolidar", now=10 + index * 0.1)
    assert result["state"]["fall_status"] == "upright"
    return core


class WatchdogContracts(unittest.TestCase):
    def test_ros_builder_never_claims_message_clock(self):
        core = build_core({"mode": {"replay": True}}, {}, session_id="review",
                          config_dir=str(ROOT), event_path=None)
        self.assertEqual(core.clock_domain, "monotonic")

    def test_request_clock_sampled_after_lock_wait(self):
        core = FallNodeCore("review")
        result = core.process(cloud(), 10, seq=1, stamp_secs=100,
                              stamp_nsecs=0, frame_id="innolidar", now=10)
        entered = threading.Event()
        sampled = threading.Event()
        answers = []
        def clock():
            sampled.set()
            return 30
        def request():
            entered.set()
            answers.append(core.handle_request(command(result["snapshot"]), 10.01, now_fn=clock))
        with core._lock:
            thread = threading.Thread(target=request)
            thread.start()
            self.assertTrue(entered.wait(1))
            self.assertFalse(sampled.wait(0.1))
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertTrue(sampled.is_set())
        self.assertFalse(answers[0]["accepted"])

    def test_stalled_stream_no_longer_reports_upright(self):
        state = upright_core().status_state(12)
        self.assertEqual(state["fall_status"], "unknown", state)

    def test_stalled_stream_does_not_report_last_measured_position(self):
        state = upright_core().status_state(12)
        self.assertIsNone(state["position_source_m"])
        self.assertIsNone(state["range_m"])
        self.assertIsNone(state["bbox_source_min_m"])

    def test_before_first_frame_fall_state_is_unknown(self):
        self.assertEqual(FallNodeCore("review").status_state(10)["fall_status"], "unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
