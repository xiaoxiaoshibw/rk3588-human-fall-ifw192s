import asyncio
import json
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest

import aiohttp
from aiohttp import web
import numpy as np

STUDIO_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = STUDIO_DIR.parents[1]
if str(STUDIO_DIR) not in sys.path:
    sys.path.insert(0, str(STUDIO_DIR))

from live_source import LiveSource, probe_board  # noqa: E402
from protocol import unpack_frame  # noqa: E402
from replay_source import get_shared_grid  # noqa: E402
from server import create_app  # noqa: E402


def _build_ros_pointcloud2(seq: int, sec: int, nsec: int, xyz_points: np.ndarray) -> bytes:
    """构造标准 ROS1 sensor_msgs/PointCloud2 二进制载荷（6 字段 x/y/z/intensity/ring/timestamp）。"""
    frame_id = b"innolidar"
    header = struct.pack("<III", seq, sec, nsec) + struct.pack("<I", len(frame_id)) + frame_id
    n = len(xyz_points)
    fields_spec = [
        (b"x", 0, 7, 1),
        (b"y", 4, 7, 1),
        (b"z", 8, 7, 1),
        (b"intensity", 12, 7, 1),
        (b"ring", 16, 4, 1),
        (b"timestamp", 20, 7, 1),
    ]
    parts = [header, struct.pack("<III", 1, n, len(fields_spec))]
    for name, off, dt, cnt in fields_spec:
        parts.append(struct.pack("<I", len(name)) + name + struct.pack("<IBI", off, dt, cnt))
    step = 24
    stride = n * step
    row_dtype = np.dtype(
        [
            ("x", "<f4"),
            ("y", "<f4"),
            ("z", "<f4"),
            ("intensity", "<f4"),
            ("ring", "<u2"),
            ("pad", "<u2"),
            ("timestamp", "<f4"),
        ]
    )
    arr = np.zeros(n, dtype=row_dtype)
    arr["x"] = xyz_points[:, 0]
    arr["y"] = xyz_points[:, 1]
    arr["z"] = xyz_points[:, 2]
    arr["intensity"] = 600.0
    arr["ring"] = np.arange(n, dtype="<u2") % 192
    arr["timestamp"] = float(sec) + nsec / 1e9
    data = arr.tobytes()
    parts.append(struct.pack("<?III", False, step, stride, len(data)))
    parts.append(data)
    parts.append(struct.pack("<?", True))
    return b"".join(parts)


class TestServerAndLive(unittest.TestCase):
    def test_unreachable_board_probe_does_not_fabricate(self):
        async def run():
            # 找一个肯定未监听的本地端口
            import socket
            s = socket.socket()
            s.bind(("127.0.0.1", 0))
            closed_port = s.getsockname()[1]
            s.close()

            res = await probe_board(
                ws_url=f"ws://127.0.0.1:{closed_port}",
                camera_url=f"http://127.0.0.1:{closed_port}/stream",
                timeout=0.3,
            )
            self.assertFalse(res["reachable"])
            self.assertFalse(res["ws_reachable"])
            self.assertFalse(res["camera_reachable"])
            self.assertIn("板端不可达", res["reason"])

        asyncio.run(run())

    def test_live_source_with_mock_foxglove(self):
        grid, _, _ = get_shared_grid()
        az_rad = np.radians(grid.azimuth_deg)
        el_rad = np.radians(grid.elevation_deg)
        # 选前 500 像素构造合法点云
        xs = (3.5 * np.cos(el_rad) * np.cos(az_rad)).ravel()[:500]
        ys = (3.5 * np.cos(el_rad) * np.sin(az_rad)).ravel()[:500]
        zs = (3.5 * np.sin(el_rad)).ravel()[:500]
        pts = np.column_stack([xs, ys, zs]).astype(np.float32)

        async def run():
            received_packets = []
            client_sent_non_subscribe = False

            async def mock_fg(request):
                nonlocal client_sent_non_subscribe
                ws = web.WebSocketResponse(protocols=("foxglove.websocket.v1",))
                await ws.prepare(request)
                await ws.send_json(
                    {
                        "op": "advertise",
                        "channels": [
                            {
                                "id": 1,
                                "topic": "/innolidar_points",
                                "encoding": "ros1",
                                "schemaName": "sensor_msgs/PointCloud2",
                            }
                        ],
                    }
                )
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        cmd = json.loads(msg.data)
                        if cmd.get("op") != "subscribe":
                            client_sent_non_subscribe = True
                        else:
                            for i in range(4):
                                raw_pc2 = _build_ros_pointcloud2(i + 1, 1000 + i, 0, pts)
                                frame_msg = struct.pack("<BIQ", 1, 1, (1000 + i) * 1_000_000_000) + raw_pc2
                                try:
                                    await ws.send_bytes(frame_msg)
                                except (ConnectionResetError, RuntimeError):
                                    break
                                await asyncio.sleep(0.02)
                return ws

            fg_app = web.Application()
            fg_app.router.add_get("/", mock_fg)
            runner = web.AppRunner(fg_app)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            port = site._server.sockets[0].getsockname()[1]

            live = LiveSource(
                ws_url=f"ws://127.0.0.1:{port}/",
                camera_url="http://127.0.0.1:1/stream",
                decimation=2,
                empty_prefix_frames=2,
                on_frame=received_packets.append,
            )
            try:
                res = await live.start()
                self.assertTrue(res["ws_reachable"])
                for _ in range(50):
                    if len(received_packets) >= 2:
                        break
                    await asyncio.sleep(0.05)
                self.assertGreaterEqual(len(received_packets), 2)
                self.assertFalse(client_sent_non_subscribe)
                u = unpack_frame(received_packets[-1])
                self.assertTrue(u["is_live"])
                self.assertEqual(u["state"]["mode"], "live")
            finally:
                await live.stop()
                await runner.cleanup()

        asyncio.run(run())

    def test_live_source_json_only_subscribes_state_not_cloud(self):
        async def run():
            received_packets = []
            subscribed_topics = []

            async def mock_fg(request):
                ws = web.WebSocketResponse(protocols=("foxglove.websocket.v1",))
                await ws.prepare(request)
                await ws.send_json(
                    {
                        "op": "advertise",
                        "channels": [
                            {"id": 1, "topic": "/innolidar_points", "encoding": "ros1", "schemaName": "sensor_msgs/PointCloud2"},
                            {"id": 2, "topic": "/single_target_live/state", "encoding": "ros1", "schemaName": "std_msgs/String"},
                        ],
                    }
                )
                id_to_topic = {1: "/innolidar_points", 2: "/single_target_live/state"}
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        cmd = json.loads(msg.data)
                        if cmd.get("op") == "subscribe":
                            for sub in cmd.get("subscriptions") or []:
                                subscribed_topics.append(id_to_topic.get(sub["channelId"]))
                                if sub["channelId"] == 2:
                                    board_state = {
                                        "session_id": "board_json_test",
                                        "source": {"seq": 10, "stamp_secs": 100, "stamp_nsecs": 0, "frame_id": "innolidar"},
                                        "track_id": "g0_t0001",
                                        "track_status": "locked",
                                        "bbox_observed": True,
                                        "target_source_rows": [1, 2, 3],
                                        "fall_status": "upright",
                                        "groundBinding": {"available": True, "displayPlane": {"normal": [0, 0, 1], "offsetM": 1.2}},
                                        "local_range": {
                                            "heightMedianM": 1.1,
                                            "background": {"status": "ready"},
                                            "ground": {"available": True, "reason": "current_patch_support"},
                                            "bbox": {"raw": {"min": [1, 0, 0], "max": [2, 1, 1.7], "center": [1.5, 0.5, 0.85]}, "leveled": None},
                                            "preview": "iVBORw0KGgo=",
                                        },
                                        "human_physical_v1": {
                                            "status": "ok",
                                            "target_belief": {"belief_state": "CANDIDATE_HUMAN", "log_odds": 1.5, "belief_score": 0.82},
                                            "semantic_truth": "UNKNOWN",
                                        },
                                        "performance": {"service_compute_ms": 42.5, "runtime": {"physical_total_ms": 12.3}},
                                    }
                                    raw_json = json.dumps(board_state).encode("utf-8")
                                    ros_str = struct.pack("<I", len(raw_json)) + raw_json
                                    frame_msg = struct.pack("<BIQ", 1, sub["id"], 100_000_000_000) + ros_str
                                    await ws.send_bytes(frame_msg)
                return ws

            fg_app = web.Application()
            fg_app.router.add_get("/", mock_fg)
            runner = web.AppRunner(fg_app)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            port = site._server.sockets[0].getsockname()[1]

            live = LiveSource(
                ws_url=f"ws://127.0.0.1:{port}/",
                camera_url="http://127.0.0.1:1/stream",
                stream_mode="json_only",
                on_frame=received_packets.append,
            )
            try:
                res = await live.start()
                self.assertTrue(res["ws_reachable"])
                for _ in range(50):
                    if received_packets:
                        break
                    await asyncio.sleep(0.05)
                self.assertEqual(subscribed_topics, ["/single_target_live/state"])
                self.assertGreaterEqual(len(received_packets), 1)
                u = unpack_frame(received_packets[-1])
                self.assertEqual(len(u["xyz"]), 0)
                self.assertEqual(u["state"]["stream_mode"], "json_only")
                self.assertEqual(u["state"]["track_id"], "g0_t0001")
                self.assertEqual(u["state"]["local_range"]["background"]["status"], "ready")
                self.assertEqual(u["state"]["local_range"]["ground"]["displayPlane"]["offsetM"], 1.2)
                self.assertEqual(u["state"]["human_physical_v1"]["status"], "ok")
                self.assertEqual(u["state"]["local_range"]["preview"], "iVBORw0KGgo=")
            finally:
                await live.stop()
                await runner.cleanup()

        asyncio.run(run())

    def test_server_http_and_ws_end_to_end(self):
        houdao_dir = REPO_ROOT / "data" / "sessions" / "cap_20261028_houdao"
        if not houdao_dir.is_dir():
            self.skipTest("houdao session missing")

        async def run():
            with tempfile.TemporaryDirectory() as tmp_cache:
                app = create_app(
                    sessions_root=REPO_ROOT / "data" / "sessions",
                    cache_dir=Path(tmp_cache),
                    board_ws="ws://127.0.0.1:1",
                    board_camera="http://127.0.0.1:1/stream",
                )
                runner = web.AppRunner(app)
                await runner.setup()
                site = web.TCPSite(runner, "127.0.0.1", 0)
                await site.start()
                port = site._server.sockets[0].getsockname()[1]
                base = f"http://127.0.0.1:{port}"

                try:
                    async with aiohttp.ClientSession() as client:
                        async with client.get(f"{base}/api/sessions") as resp:
                            self.assertEqual(resp.status, 200)
                            sdata = await resp.json()
                            sids = [s["sid"] for s in sdata["sessions"]]
                            self.assertIn("cap_20261028_houdao", sids)

                        async with client.ws_connect(f"ws://127.0.0.1:{port}/ws") as ws:
                            await ws.send_json({"cmd": "open", "sid": "cap_20261028_houdao", "frame": 83, "decimation": 2})
                            got_frame = None
                            got_ready = False
                            while got_frame is None:
                                msg = await asyncio.wait_for(ws.receive(), timeout=30.0)
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    j = json.loads(msg.data)
                                    if j.get("type") == "session_ready":
                                        got_ready = True
                                    elif j.get("type") == "error":
                                        self.fail(f"unexpected ws error: {j}")
                                elif msg.type == aiohttp.WSMsgType.BINARY:
                                    got_frame = unpack_frame(msg.data)
                            self.assertTrue(got_ready)
                            self.assertEqual(got_frame["state"]["frame_index"], 83)
                            self.assertEqual(got_frame["state"]["fall_status"], "suspected")

                            # 测试 step +1 到 84
                            await ws.send_json({"cmd": "step", "delta": 1})
                            step_frame = None
                            while step_frame is None:
                                msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                                if msg.type == aiohttp.WSMsgType.BINARY:
                                    step_frame = unpack_frame(msg.data)
                            self.assertEqual(step_frame["state"]["frame_index"], 84)

                        # 检查相机 HTTP 端点返回有效 JPEG 与对齐头
                        async with client.get(f"{base}/api/camera/cap_20261028_houdao/83") as cam_resp:
                            self.assertEqual(cam_resp.status, 200)
                            self.assertEqual(cam_resp.headers.get("X-Camera-State"), "ready")
                            self.assertEqual(cam_resp.headers.get("X-Camera-Alignment"), "receipt_time_unverified")
                            body = await cam_resp.read()
                            self.assertTrue(body.startswith(b"\xff\xd8") and body.endswith(b"\xff\xd9"))

                        # 检查无相机会话返回 404
                        async with client.get(f"{base}/api/camera/cap_20261018_110029/0") as no_cam:
                            self.assertEqual(no_cam.status, 404)

                        # 检查路径穿越拒绝
                        async with client.get(f"{base}/api/camera/..%2Fetc/0") as bad_cam:
                            self.assertIn(bad_cam.status, (400, 404))
                finally:
                    await runner.cleanup()

        asyncio.run(run())

    def test_json_only_passthrough_instant_start_and_silent_refinement(self):
        src = LiveSource("ws://127.0.0.1:8765", "http://127.0.0.1:8081/stream", stream_mode="json_only")
        overlay = {
            "session_id": "instant_live_s1",
            "source": {"seq": 10, "stamp_secs": 1000, "stamp_nsecs": 0, "frame_id": "innolidar"},
            "target_mode": "instant_kinematic_automatic",
            "track_id": "g0_t0001",
            "track_status": "locked",
            "observability": "valid",
            "bbox_observed": True,
            "fall_status": "suspected",
            "target_source_rows": [1, 2, 3],
            "service": {"capabilities": ["instant_start", "silent_ground_refinement"]},
            "local_range": {
                "background": {"status": "adaptive_ready", "declaration": "instant_adaptive_far_bg"},
                "ground": {
                    "available": True,
                    "refinementStage": "refined_plane",
                    "gravitySource": "imu_static_gravity",
                    "displayPlane": {"normal": [-0.45, 0.0, 0.893], "offsetM": 1.38},
                },
                "kinematics": {
                    "method": "instant_gravity_kinematics_v1",
                    "drop_top_m": 1.05,
                    "vel_top_mps": -1.2,
                    "fall_reason": "FAST_KINEMATIC",
                },
            },
        }
        pkt = src._process_board_json_sync(overlay, time.monotonic())
        self.assertIsNotNone(pkt)
        unpacked = unpack_frame(pkt)
        st = unpacked["state"]
        self.assertEqual(st["fall_status"], "suspected")
        self.assertEqual(st["local_range"]["background"]["status"], "adaptive_ready")
        self.assertEqual(st["local_range"]["ground"]["refinementStage"], "refined_plane")
        self.assertEqual(st["local_range"]["kinematics"]["fall_reason"], "FAST_KINEMATIC")


if __name__ == "__main__":
    unittest.main()
