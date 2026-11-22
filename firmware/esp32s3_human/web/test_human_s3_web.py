"""Unit tests for ESP32-S3 human kinematics & fall detection web server."""

import json
import sys
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

WEB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(WEB_DIR))

from human_s3_web import HumanFrameAssembler, HumanLiveHub, make_handler  # noqa: E402


class TestHumanS3Web(unittest.TestCase):
    @patch("human_s3_web.monotonic")
    def test_history_expires_from_snapshot_and_sse_without_removing_events(self, now):
        hub = HumanLiveHub("test")
        q, initial = hub.subscribe()
        self.assertEqual(initial["trails"], {})
        track = {"id": 7, "xyz_m": [3.0, 0.1, 0.5]}
        now.return_value = 100.0
        hub.publish({"seq": 1, "state": "active", "tracks": [track]})
        latest = json.loads(q.get_nowait()[6:])
        self.assertEqual(latest["history_ids"], ["7"])

        now.return_value = 119.9
        hub.publish({"seq": 2, "state": "active", "tracks": []})
        self.assertEqual(json.loads(q.get_nowait()[6:])["history_ids"], ["7"])
        self.assertIn("7", hub.snapshot()["trails"])

        now.return_value = 120.0
        hub.publish({"seq": 3, "state": "active", "tracks": [{**track, "id": 8}]})
        latest = json.loads(q.get_nowait()[6:])
        snap = hub.snapshot()
        self.assertEqual(latest["history_ids"], ["8"])
        self.assertEqual(list(snap["trails"]), ["8"])
        self.assertEqual(list(snap["kinematics"]), ["8"])
        self.assertEqual(len(snap["events"]), 2)

        now.return_value = 141.0
        self.assertEqual(hub.snapshot()["trails"], {})
        hub.clear_history()
        q.get_nowait()
        hub.publish({"seq": 4, "state": "active", "tracks": [track]})
        self.assertGreater(json.loads(q.get_nowait()[6:])["history_epoch"], latest["history_epoch"])
        self.assertEqual(len(hub.snapshot()["trails"]["7"]), 1)

    def test_assembler_groups_frame_and_tracks_with_kinematics(self):
        asm = HumanFrameAssembler()
        f_msg = {
            "type": "frame",
            "seq": 1000,
            "state": "active",
            "warmup": 0,
            "locked": 1,
            "candidates": 2,
            "tentative": 0,
            "valid_cells": 46500,
            "fg_seeds": 310,
            "fall_suspected": 1,
            "tail_read_us": 100000,
            "grid_ready_us": 152500,
            "tracker_start_us": 152600,
            "result_ready_us": 173900,
        }
        t_msg = {
            "type": "track",
            "seq": 1000,
            "id": 7,
            "box": [100, 80, 140, 150],
            "xyz_m": [2.5, -0.3, 0.2],
            "points": 420,
            "range_m": 2.53,
            "height_m": 0.42,
            "h_p95": 0.45,
            "horiz_m": 1.15,
            "aspect": 0.365,
            "drop_m": 1.25,
            "vel_mps": -2.1,
            "acc_mps2": -6.8,
            "peak_down_vel": 2.8,
            "peak_down_acc": 7.9,
            "low_sec": 1.4,
            "still_sec": 3.2,
            "baseline_ready": True,
            "fall_state": "FALL_SUSPECTED",
            "fall_reason": "FAST_KINEMATIC",
        }
        self.assertEqual(asm.push_message(f_msg), [])
        out = asm.push_message(t_msg)
        self.assertEqual(len(out), 1)
        frame = out[0]
        self.assertAlmostEqual(frame["materialize_ms"], 52.5, places=2)
        self.assertAlmostEqual(frame["tracker_ms"], 21.3, places=2)
        self.assertAlmostEqual(frame["latency_ms"], 73.9, places=2)
        self.assertEqual(frame["fall_suspected"], 1)
        self.assertEqual(len(frame["tracks"]), 1)
        tr = frame["tracks"][0]
        self.assertEqual(tr["id"], 7)
        self.assertEqual(tr["fall_state"], "FALL_SUSPECTED")
        self.assertEqual(tr["fall_reason"], "FAST_KINEMATIC")
        self.assertAlmostEqual(tr["drop_m"], 1.25, places=2)
        self.assertEqual(tr["still_sec"], 3.2)
        del t_msg["still_sec"]
        self.assertEqual(asm.push_message(f_msg), [])
        self.assertIsNone(asm.push_message(t_msg)[0]["tracks"][0]["still_sec"])

    def test_http_endpoints_and_snapshot(self):
        hub = HumanLiveHub("test")
        hub.set_device_info({"profile": "human_kinematic_v3", "internal_free": 173499,
                             "psram_free": 5911052, "mount_pitch_deg": 26.0})
        hub.input_status("streaming")
        hub.publish({
            "seq": 2000,
            "state": "active",
            "locked": 1,
            "candidates": 1,
            "tentative": 0,
            "valid_cells": 47000,
            "fg_seeds": 200,
            "fall_suspected": 0,
            "latency_ms": 74.0,
            "materialize_ms": 52.6,
            "tracker_ms": 21.3,
            "tracks": [{
                "id": 1,
                "box": [90, 50, 120, 160],
                "xyz_m": [3.0, 0.1, 0.5],
                "points": 800,
                "range_m": 3.04,
                "height_m": 1.68,
                "h_p95": 1.70,
                "horiz_m": 0.55,
                "aspect": 3.05,
                "drop_m": 0.02,
                "vel_mps": 0.01,
                "acc_mps2": 0.0,
                "peak_down_vel": 0.1,
                "peak_down_acc": 0.2,
                "low_sec": 0.0,
                "baseline_ready": True,
                "fall_state": "UPRIGHT",
                "fall_reason": "NONE",
            }],
        })

        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(hub))
        port = server.server_address[1]
        th = threading.Thread(target=server.serve_forever, daemon=True)
        th.start()
        try:
            with urlopen(f"http://127.0.0.1:{port}/") as resp:
                html = resp.read().decode("utf-8")
                self.assertEqual(resp.status, 200)
                self.assertIn("ESP32-S3 无空场人体运动学与跌倒监控", html)
                self.assertIn('id="mProfile"', html)
                self.assertIn("距上次续期", html)

            with urlopen(f"http://127.0.0.1:{port}/api/snapshot") as resp:
                snap = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(snap["input_status"], "streaming")
                self.assertEqual(snap["device"]["profile"], "human_kinematic_v3")
                self.assertEqual(snap["latest"]["seq"], 2000)
                self.assertEqual(snap["latest"]["tracks"][0]["fall_state"], "UPRIGHT")
                self.assertIn("1", snap["kinematics"])

            req = Request(f"http://127.0.0.1:{port}/api/clear", method="POST")
            with urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
            self.assertEqual(hub.snapshot()["trails"], {})
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
