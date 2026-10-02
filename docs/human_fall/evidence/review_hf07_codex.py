"""Independent node composition contracts, synthetic and ROS-free."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/human_fall_detection"))
from core.node_runtime import FallNodeCore
from core.ground import fit_ground_plane


def cloud():
    rng = np.random.RandomState(25)
    return rng.normal(size=(500, 3)) * [0.06, 0.06, 0.25] + [3, 0, -0.3]


def command(snapshot, request_id="r1", version=0):
    return {"schema_version": 1, "request_id": request_id, "action": "select",
            "session_id": "review", "time_epoch": snapshot["time_epoch"],
            "snapshot_id": snapshot["snapshot_id"],
            "candidate_id": snapshot["candidates"][0]["candidate_id"],
            "selection_version": version}


class CompositionContracts(unittest.TestCase):
    def test_invalid_source_stamp_frame_cannot_be_selected(self):
        core = FallNodeCore("review")
        result = core.process(cloud(), 10, seq=1, stamp_secs=0, stamp_nsecs=0,
                              frame_id="innolidar", now=10)
        ack = core.handle_request(command(result["snapshot"]), 10.1)
        self.assertFalse(ack["accepted"], ack)

    def test_stopped_required_cloud_blocks_selection_before_snapshot_ttl(self):
        core = FallNodeCore("review")
        result = core.process(cloud(), 10, seq=1, stamp_secs=100, stamp_nsecs=0,
                              frame_id="innolidar", now=10)
        ack = core.handle_request(command(result["snapshot"]), 11)
        self.assertFalse(ack["accepted"], ack)

    def test_disappeared_candidate_in_old_snapshot_is_not_selected(self):
        core = FallNodeCore("review")
        result = core.process(cloud(), 10, seq=1, stamp_secs=100, stamp_nsecs=0,
                              frame_id="innolidar", now=10)
        core.process(np.zeros((0, 3)), 10.1, seq=2, stamp_secs=100,
                     stamp_nsecs=100000000, frame_id="innolidar", now=10.1)
        ack = core.handle_request(command(result["snapshot"]), 10.2)
        self.assertFalse(ack["accepted"], ack)

    def test_auxiliary_clock_repeat_does_not_break_geometry_selection(self):
        core = FallNodeCore("review")
        core.process(cloud(), 10, seq=1, stamp_secs=100, stamp_nsecs=0,
                     frame_id="innolidar", now=10)
        core.note_imu(10.05, (50, 0), "innolidar", True)
        core.note_imu(10.06, (50, 0), "innolidar", True)
        result = core.process(cloud(), 10.1, seq=2, stamp_secs=100,
                              stamp_nsecs=100000000, frame_id="innolidar", now=10.1)
        ack = core.handle_request(command(result["snapshot"]), 10.2)
        self.assertTrue(ack["accepted"], ack)

    def test_ready_current_baseline_reaches_upright_through_runtime(self):
        x, y = np.meshgrid(np.linspace(-4, 4, 25), np.linspace(-4, 4, 25))
        floor = np.column_stack((x.ravel(), y.ravel(), np.full(x.size, -1.5)))
        ground = fit_ground_plane(floor, {"range_min_m": 0}, frame="innolidar")
        core = FallNodeCore("review", {"baseline": {"require_seconds": 0.2,
                           "max_duration_s": 1, "min_samples": 3}}, ground=ground,
                           calibration={"calibration_id": "geo",
                                        "frames": {"lidar": "innolidar", "reference": None}})
        result = core.process(cloud(), 10, seq=1, stamp_secs=100, stamp_nsecs=0,
                              frame_id="innolidar", now=10)
        selected = core.handle_request(command(result["snapshot"]), 10.01)
        self.assertTrue(selected["accepted"], selected)
        capture = command(result["snapshot"], "r2", version=1)
        capture.update(action="capture_baseline", track_id=selected["track_id"])
        ack = core.handle_request(capture, 10.02)
        self.assertTrue(ack["accepted"], ack)
        for index in range(1, 6):
            result = core.process(cloud(), 10 + index * 0.1, seq=index + 1,
                                  stamp_secs=100, stamp_nsecs=index * 100000000,
                                  frame_id="innolidar", now=10 + index * 0.1)
        self.assertEqual(core.baseline.status, "ready", core.baseline.snapshot())
        self.assertEqual(result["state"]["fall_status"], "upright", result["state"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
