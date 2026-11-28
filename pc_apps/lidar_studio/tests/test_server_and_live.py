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


class TestLiveFramePairing(unittest.TestCase):
    """Step 1 回归：错帧绝不叠加、同帧必须正常显示、覆盖 7 类时序与故障边界。"""

    @staticmethod
    def _two_point_cloud(seq: int, sec: int, nsec: int, first_x: float) -> tuple[bytes, str]:
        import hashlib

        pts = np.array([[first_x, 0.0, 0.0], [first_x + 0.5, 0.2, 0.0]], dtype=np.float32)
        raw = _build_ros_pointcloud2(seq, sec, nsec, pts)
        return raw, hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _board_state(
        seq: int,
        sec: int,
        nsec: int,
        wire_sha: str | None,
        *,
        track_id: str | None = "old_A",
        fall_status: str = "suspected",
        rows: list[int] | None = None,
        preview: str | None = None,
        session_id: str = "board_pair_sess",
        ttl_ms: int = 500,
    ) -> dict:
        rows_out = [0] if rows is None else list(rows)
        lr: dict = {
            "version": 1,
            "heightMedianM": 0.42 if rows_out else None,
            "background": {"status": "adaptive_ready", "declaration": "instant_adaptive_far_bg"},
            "ground": {"available": True, "refinementStage": "refined_plane"},
            "bbox": (
                {"raw": {"min": [1.0, -0.2, -0.2], "max": [4.2, 0.2, 0.5], "center": [2.5, 0.0, 0.1]}, "leveled": None}
                if rows_out
                else None
            ),
            "preview": preview,
        }
        if wire_sha is not None:
            lr["wireSha256"] = wire_sha
        return {
            "schema_version": 1,
            "kind": "target_state",
            "session_id": session_id,
            "time_epoch": 0,
            "source": {"seq": seq, "stamp_secs": sec, "stamp_nsecs": nsec, "frame_id": "innolidar"},
            "target_mode": "instant_kinematic_automatic",
            "track_id": track_id,
            "track_status": "locked" if rows_out else "unselected",
            "observability": "valid",
            "bbox_observed": bool(rows_out),
            "position_predicted": False,
            "target_source_rows": rows_out,
            "fall_status": fall_status,
            "acquisition": {"reason": "current_target" if rows_out else "no_locked_human_target"},
            "confirmed_enabled": False,
            "service": {"protocol": "range_recognition/1", "version": 1, "ttlMs": ttl_ms, "confirmedEnabled": False},
            "local_range": lr,
        }

    def test_counterexample_mismatched_frame_never_overlays_and_matched_frame_displays(self):
        from protocol import FLAG_TARGET_CORE

        raw_a, sha_a = self._two_point_cloud(10, 1000, 0, 4.1)
        raw_b, sha_b = self._two_point_cloud(11, 1000, 100_000_000, 1.1)
        self.assertNotEqual(sha_a, sha_b)

        src = LiveSource("ws://127.0.0.1:8765", "http://127.0.0.1:8081/stream", decimation=1, stream_mode="cloud_and_json")
        state_a = self._board_state(10, 1000, 0, sha_a, track_id="old_A", fall_status="suspected", rows=[0], preview="iVBORw0KGgo=")
        # State A arrives, then Cloud B arrives (wrong frame: 100 ms later, 3 m away!)
        t0 = 100.0
        src._board_state = (state_a, t0)
        if hasattr(src, "ingest_board_state"):
            src.ingest_board_state(state_a, t0)
        pkt_b = src._process_one_sync(raw_b, t0 + 0.1)
        self.assertIsNotNone(pkt_b)
        ub = unpack_frame(pkt_b)
        self.assertIsNone(ub["state"]["track_id"])
        self.assertEqual(ub["state"]["fall_status"], "unknown")
        self.assertEqual(ub["state"]["local_range"]["depth"]["metadata"]["targetPixels"], 0)
        self.assertEqual(int((ub["point_flags"] & FLAG_TARGET_CORE).sum()), 0)
        self.assertIsNone(ub["state"]["local_range"].get("preview"))
        self.assertIsNone(ub["state"]["local_range"].get("bbox"))

        # Now test properly paired frame A (state-first) -> MUST show exact source row 0 and track old_A!
        src2 = LiveSource("ws://127.0.0.1:8765", "http://127.0.0.1:8081/stream", decimation=1, stream_mode="cloud_and_json")
        if hasattr(src2, "ingest_board_state"):
            src2.ingest_board_state(state_a, t0)
        else:
            src2._board_state = (state_a, t0)
        pkt_a = src2._process_one_sync(raw_a, t0 + 0.02)
        self.assertIsNotNone(pkt_a)
        ua = unpack_frame(pkt_a)
        self.assertEqual(ua["state"]["track_id"], "old_A")
        self.assertEqual(ua["state"]["fall_status"], "suspected")
        self.assertEqual(ua["state"]["local_range"]["depth"]["metadata"]["targetPixels"], 1)
        target_mask = (ua["point_flags"] & FLAG_TARGET_CORE).astype(bool)
        self.assertEqual(int(target_mask.sum()), 1)
        self.assertAlmostEqual(float(ua["xyz"][target_mask][0, 0]), 4.1, places=3)
        self.assertEqual(ua["state"]["pairing"]["status"], "matched")

    def test_cloud_first_then_state_and_late_same_frame_preview(self):
        from protocol import FLAG_TARGET_CORE

        raw_a, sha_a = self._two_point_cloud(10, 1000, 0, 4.1)
        src = LiveSource("ws://127.0.0.1:8765", "http://127.0.0.1:8081/stream", decimation=1, stream_mode="cloud_and_json")
        t0 = 200.0
        # 1. Cloud arrives first -> displayed immediately without stale overlay
        pkts0 = src.ingest_cloud(raw_a, t0)
        self.assertEqual(len(pkts0), 1)
        u0 = unpack_frame(pkts0[0])
        self.assertIsNone(u0["state"]["track_id"])
        self.assertEqual(u0["state"]["pairing"]["status"], "awaiting_state")
        self.assertEqual(int((u0["point_flags"] & FLAG_TARGET_CORE).sum()), 0)

        # 2. Matching state arrives 45 ms later (no preview yet) -> enriches currently displayed frame
        st_no_prev = self._board_state(10, 1000, 0, sha_a, track_id="g0_t0007", fall_status="upright", rows=[0], preview=None)
        pkts1 = src.ingest_board_state(st_no_prev, t0 + 0.045)
        self.assertEqual(len(pkts1), 1)
        u1 = unpack_frame(pkts1[0])
        self.assertEqual(u1["state"]["track_id"], "g0_t0007")
        self.assertEqual(u1["state"]["fall_status"], "upright")
        self.assertEqual(u1["state"]["pairing"]["status"], "matched")
        self.assertIsNone(u1["state"]["local_range"].get("preview"))
        self.assertEqual(int((u1["point_flags"] & FLAG_TARGET_CORE).sum()), 1)

        # 3. Late preview arrives 20 ms later for the SAME frame -> updates preview cleanly
        st_prev = self._board_state(10, 1000, 0, sha_a, track_id="g0_t0007", fall_status="upright", rows=[0], preview="iVBORw0KGgo=")
        pkts2 = src.ingest_board_state(st_prev, t0 + 0.065)
        self.assertEqual(len(pkts2), 1)
        u2 = unpack_frame(pkts2[0])
        self.assertEqual(u2["state"]["local_range"]["preview"], "iVBORw0KGgo=")
        self.assertEqual(u2["state"]["pairing"]["preview_state"], "late_same_frame")

        metrics = src.pairing_metrics()
        self.assertEqual(metrics["matched_frames"], 1)
        self.assertEqual(metrics["late_preview_updates"], 1)
        self.assertGreaterEqual(metrics["wait_ms_p95"], 40.0)

    def test_json_only_no_cross_frame_preview_and_late_same_frame_preview(self):
        src = LiveSource("ws://127.0.0.1:8765", "http://127.0.0.1:8081/stream", stream_mode="json_only")
        t0 = 300.0
        # seq 10 without preview, then late preview for seq 10
        p10a = src._process_board_json_sync(self._board_state(10, 1000, 0, "a" * 64, preview=None), t0)
        self.assertIsNone(unpack_frame(p10a)["state"]["local_range"]["preview"])
        p10b = src._process_board_json_sync(self._board_state(10, 1000, 0, "a" * 64, preview="iVBORw0KGgo="), t0 + 0.02)
        u10b = unpack_frame(p10b)
        self.assertEqual(u10b["state"]["local_range"]["preview"], "iVBORw0KGgo=")
        self.assertEqual(u10b["state"]["pairing"]["preview_state"], "late_same_frame")

        # Duplicate heartbeat for SAME seq 10 without preview may not leak to seq 11;
        # when seq 11 arrives without preview, preview MUST be None!
        p11 = src._process_board_json_sync(self._board_state(11, 1000, 100_000_000, "b" * 64, preview=None), t0 + 0.1)
        u11 = unpack_frame(p11)
        self.assertIsNone(u11["state"]["local_range"]["preview"])
        self.assertEqual(u11["state"]["pairing"]["preview_state"], "pending_for_frame")

        # Heartbeat with source=None MUST clear target, fall_status, and preview
        hb = {
            "session_id": "board_pair_sess",
            "source": None,
            "track_id": None,
            "fall_status": "unknown",
            "observability": "invalid",
            "acquisition": {"reason": "required_cloud_stale"},
        }
        phb = src._process_board_json_sync(hb, t0 + 0.2)
        uhb = unpack_frame(phb)
        self.assertIsNone(uhb["state"]["local_range"]["preview"])
        self.assertIsNone(uhb["state"]["track_id"])
        self.assertEqual(uhb["state"]["fall_status"], "unknown")
        self.assertEqual(uhb["state"]["pairing"]["status"], "invalid_source")

    def test_same_seq_different_sha_rejected_and_reconnect_seq_reuse_isolated(self):
        from protocol import FLAG_TARGET_CORE

        raw_a, sha_a = self._two_point_cloud(10, 1000, 0, 4.1)
        raw_tampered, sha_tampered = self._two_point_cloud(10, 1000, 0, 1.1)
        self.assertNotEqual(sha_a, sha_tampered)

        src = LiveSource("ws://127.0.0.1:8765", "http://127.0.0.1:8081/stream", decimation=1, stream_mode="cloud_and_json")
        t0 = 400.0
        # Same seq=10, stamp=1000.0, frame_id=innolidar, DIFFERENT wire SHA!
        src.ingest_board_state(self._board_state(10, 1000, 0, sha_a, track_id="bad_overlay", fall_status="suspected"), t0)
        pkts = src.ingest_cloud(raw_tampered, t0 + 0.01)
        self.assertEqual(len(pkts), 1)
        u = unpack_frame(pkts[0])
        self.assertIsNone(u["state"]["track_id"])
        self.assertEqual(u["state"]["fall_status"], "unknown")
        self.assertEqual(u["state"]["pairing"]["reason"], "wire_sha256_mismatch")
        self.assertEqual(int((u["point_flags"] & FLAG_TARGET_CORE).sum()), 0)
        self.assertEqual(src.pairing_metrics()["wire_sha_mismatches"], 1)

        # Reconnect reusing seq=10: pre-reconnect state MUST NOT match post-reconnect cloud
        src.ingest_board_state(self._board_state(10, 1000, 0, sha_a, track_id="pre_reconnect", fall_status="suspected"), t0 + 0.1)
        src.on_reconnect()
        pkts_re = src.ingest_cloud(raw_a, t0 + 0.15)
        self.assertEqual(len(pkts_re), 1)
        ure = unpack_frame(pkts_re[0])
        self.assertIsNone(ure["state"]["track_id"])
        self.assertEqual(ure["state"]["fall_status"], "unknown")
        self.assertEqual(ure["state"]["pairing"]["status"], "awaiting_state")

    def test_ttl_expiry_and_eviction_accounting(self):
        raw_a, sha_a = self._two_point_cloud(10, 1000, 0, 4.1)
        raw_b, sha_b = self._two_point_cloud(11, 1000, 100_000_000, 1.1)
        src = LiveSource("ws://127.0.0.1:8765", "http://127.0.0.1:8081/stream", decimation=1, stream_mode="cloud_and_json")
        t0 = 500.0
        # 1. State arrives, then 600 ms (> 500 ms TTL) passes before cloud arrives -> expired!
        src.ingest_board_state(self._board_state(10, 1000, 0, sha_a, track_id="stale_t", fall_status="suspected"), t0)
        pkts = src.ingest_cloud(raw_a, t0 + 0.65)
        self.assertEqual(len(pkts), 1)
        u = unpack_frame(pkts[0])
        self.assertIsNone(u["state"]["track_id"])
        self.assertEqual(u["state"]["fall_status"], "unknown")
        self.assertGreaterEqual(src.pairing_metrics()["lost_valid_results_evicted"], 1)

        # 2. Cloud A arrives, then Cloud B supersedes it before State A arrives -> State A counted as superseded, NOT overlaid on B!
        src.ingest_cloud(raw_a, t0 + 1.0)
        src.ingest_cloud(raw_b, t0 + 1.1)
        pkts_late_a = src.ingest_board_state(self._board_state(10, 1000, 0, sha_a, track_id="late_A", fall_status="suspected"), t0 + 1.15)
        self.assertEqual(pkts_late_a, [])
        self.assertGreaterEqual(src.pairing_metrics()["lost_valid_results_superseded"], 1)

        # 3. Active matched frame expires after > TTL with no new updates -> check_expiry clears targets!
        pkts_b_match = src.ingest_board_state(self._board_state(11, 1000, 100_000_000, sha_b, track_id="live_B", fall_status="suspected"), t0 + 1.16)
        self.assertEqual(len(pkts_b_match), 1)
        self.assertEqual(unpack_frame(pkts_b_match[0])["state"]["track_id"], "live_B")
        exp_pkts = src.check_expiry(t0 + 1.80)
        self.assertEqual(len(exp_pkts), 1)
        uexp = unpack_frame(exp_pkts[0])
        self.assertIsNone(uexp["state"]["track_id"])
        self.assertEqual(uexp["state"]["fall_status"], "unknown")
        self.assertEqual(uexp["state"]["pairing"]["status"], "expired")

    def test_missing_sha_out_of_bounds_rows_rewind_and_mock_foxglove_ws_e2e(self):
        from protocol import FLAG_TARGET_CORE

        raw_10, sha_10 = self._two_point_cloud(10, 1000, 0, 4.1)
        raw_11, sha_11 = self._two_point_cloud(11, 1000, 100_000_000, 1.1)
        raw_09, sha_09 = self._two_point_cloud(9, 999, 900_000_000, 2.5)
        src = LiveSource("ws://127.0.0.1:8765", "http://127.0.0.1:8081/stream", decimation=1, stream_mode="cloud_and_json")
        t0 = 600.0

        # Missing wireSha256 (legacy state) must NOT overlay target
        src.ingest_board_state(self._board_state(10, 1000, 0, None, track_id="legacy_t", fall_status="suspected"), t0)
        p_legacy = src.ingest_cloud(raw_10, t0 + 0.01)
        u_leg = unpack_frame(p_legacy[0])
        self.assertIsNone(u_leg["state"]["track_id"])
        self.assertEqual(u_leg["state"]["pairing"]["reason"], "missing_wire_sha256")
        self.assertEqual(int((u_leg["point_flags"] & FLAG_TARGET_CORE).sum()), 0)

        # Out-of-bounds target_source_rows rejected cleanly
        src.ingest_board_state(self._board_state(11, 1000, 100_000_000, sha_11, track_id="oob_t", rows=[999]), t0 + 0.05)
        p_oob = src.ingest_cloud(raw_11, t0 + 0.06)
        u_oob = unpack_frame(p_oob[0])
        self.assertIsNone(u_oob["state"]["track_id"])
        self.assertEqual(u_oob["state"]["pairing"]["reason"], "source_rows_out_of_bounds")

        # Source time/seq rewind rejected cleanly
        p_rew = src.ingest_cloud(raw_09, t0 + 0.12)
        u_rew = unpack_frame(p_rew[0])
        self.assertEqual(u_rew["state"]["pairing"]["reason"], "source_time_rewind")

        # Full mock Foxglove WS end-to-end: cloud_and_json cloud-first -> state match -> mismatched frame
        async def run_ws_e2e():
            emitted = []

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
                sub_map = {}
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        cmd = json.loads(msg.data)
                        if cmd.get("op") == "subscribe":
                            for sub in cmd.get("subscriptions") or []:
                                sub_map[sub["channelId"]] = sub["id"]
                            if 1 in sub_map and 2 in sub_map:
                                # 1. Send cloud 10 first
                                await ws.send_bytes(struct.pack("<BIQ", 1, sub_map[1], 1000_000_000_000) + raw_10)
                                await asyncio.sleep(0.03)
                                # 2. Send matching state 10
                                st10 = json.dumps(self._board_state(10, 1000, 0, sha_10, track_id="ws_t10", fall_status="suspected", rows=[0])).encode("utf-8")
                                await ws.send_bytes(struct.pack("<BIQ", 1, sub_map[2], 1000_030_000_000) + struct.pack("<I", len(st10)) + st10)
                                await asyncio.sleep(0.03)
                                # 3. Send cloud 11 WITHOUT state 11 (must NOT carry ws_t10 / suspected!)
                                await ws.send_bytes(struct.pack("<BIQ", 1, sub_map[1], 1000_100_000_000) + raw_11)
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
                decimation=1,
                stream_mode="cloud_and_json",
                on_frame=emitted.append,
            )
            try:
                await live.start()
                for _ in range(80):
                    if len(emitted) >= 3:
                        break
                    await asyncio.sleep(0.025)
                self.assertGreaterEqual(len(emitted), 3)
                u_all = [unpack_frame(p) for p in emitted]
                # Packet 0: cloud 10 provisional (awaiting_state, 0 targets)
                self.assertEqual(u_all[0]["state"]["source"]["seq"], 10)
                self.assertEqual(u_all[0]["state"]["pairing"]["status"], "awaiting_state")
                self.assertIsNone(u_all[0]["state"]["track_id"])
                # Packet 1: cloud 10 matched with ws_t10 and exact row 0 (x=4.1)
                self.assertEqual(u_all[1]["state"]["source"]["seq"], 10)
                self.assertEqual(u_all[1]["state"]["pairing"]["status"], "matched")
                self.assertEqual(u_all[1]["state"]["track_id"], "ws_t10")
                self.assertEqual(u_all[1]["state"]["fall_status"], "suspected")
                tmask = (u_all[1]["point_flags"] & FLAG_TARGET_CORE).astype(bool)
                self.assertEqual(int(tmask.sum()), 1)
                self.assertAlmostEqual(float(u_all[1]["xyz"][tmask][0, 0]), 4.1, places=3)
                # Packet 2: cloud 11 awaiting (MUST NOT inherit ws_t10 or suspected!)
                self.assertEqual(u_all[2]["state"]["source"]["seq"], 11)
                self.assertEqual(u_all[2]["state"]["pairing"]["status"], "awaiting_state")
                self.assertIsNone(u_all[2]["state"]["track_id"])
                self.assertEqual(u_all[2]["state"]["fall_status"], "unknown")
                self.assertEqual(int((u_all[2]["point_flags"] & FLAG_TARGET_CORE).sum()), 0)
            finally:
                await live.stop()
                await runner.cleanup()

        asyncio.run(run_ws_e2e())


if __name__ == "__main__":
    unittest.main()
