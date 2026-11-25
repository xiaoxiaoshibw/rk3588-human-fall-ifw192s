"""P4 实时模式数据源：TCP 可达性探测 + 只读 Foxglove WS 订阅 + 本地算法/降采样打包。

红线与约束：
- 只读订阅板端已有话题（/innolidar_points + 可选 /single_target_live/state），绝不发布控制/写板端。
- 板端不可达时如实上报 offline/"板端不可达"，绝不伪造任何点云或状态数据。
"""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
import struct
import sys
import time
from typing import Any, Callable
from urllib.parse import urlparse

import aiohttp
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
HF_DIR = REPO_ROOT / "src" / "human_fall_detection"
if str(HF_DIR) not in sys.path:
    sys.path.insert(0, str(HF_DIR))

from core.capture_input import ROW_DTYPE  # noqa: E402
from core.range_contract import binding_tuple  # noqa: E402
from core.range_demo_alert import DemoAlert  # noqa: E402
from core.range_ground_alert import GroundAlertObserver  # noqa: E402
from core.range_live import pointcloud_rows  # noqa: E402
from core.range_runtime import RangeRuntime  # noqa: E402
from core.range_skeleton import estimate as estimate_skeleton, project_regions  # noqa: E402
from core.range_wire import parse_cloud  # noqa: E402

from protocol import FLAG_FOREGROUND, FLAG_OTHER_TRACK, FLAG_RECOVERY_ADDED, FLAG_TARGET_CORE, pack_frame, sanitize_json
from replay_source import (
    build_point_flags_and_masks,
    compact_physical_v1,
    compact_skeleton,
    compute_bbox,
    display_basis,
    get_shared_grid,
)


async def probe_tcp(
    host: str,
    port: int,
    timeout: float = 2.5,
    retries: int = 1,
) -> tuple[bool, float | None, str | None]:
    """探测单个 host:port 的 TCP 可达性，不发送应用层写请求，失败可重试一次以抗网络抖动。"""
    last_err: str | None = None
    attempts = max(1, 1 + int(retries))
    for attempt in range(attempts):
        t0 = time.perf_counter()
        try:
            conn = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(conn, timeout=timeout)
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return True, elapsed_ms, None
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt + 1 < attempts:
                await asyncio.sleep(0.15)
    return False, None, last_err


async def probe_board(
    ws_url: str = "ws://192.168.31.58:8765",
    camera_url: str = "http://192.168.31.58:8081/stream",
    timeout: float = 2.5,
    retries: int = 1,
) -> dict[str, Any]:
    """探测板端 Foxglove WS 与相机 HTTP 端口可达性，不可达时如实返回 offline。"""
    ws_parsed = urlparse(ws_url)
    cam_parsed = urlparse(camera_url)
    ws_host = ws_parsed.hostname or "192.168.31.58"
    ws_port = ws_parsed.port or (443 if ws_parsed.scheme == "wss" else 80)
    cam_host = cam_parsed.hostname or ws_host
    cam_port = cam_parsed.port or (443 if cam_parsed.scheme == "https" else 80)

    (ws_ok, ws_ms, ws_err), (cam_ok, cam_ms, cam_err) = await asyncio.gather(
        probe_tcp(ws_host, ws_port, timeout=timeout, retries=retries),
        probe_tcp(cam_host, cam_port, timeout=timeout, retries=retries),
    )

    if ws_ok:
        reason = "板端雷达服务在线"
    else:
        reason = f"板端不可达（{ws_host}:{ws_port} {ws_err or '连接失败'}）"

    return {
        "reachable": ws_ok,
        "ws_reachable": ws_ok,
        "ws_latency_ms": ws_ms,
        "ws_error": ws_err,
        "camera_reachable": cam_ok,
        "camera_latency_ms": cam_ms,
        "camera_error": cam_err,
        "board_ws": ws_url,
        "board_camera": camera_url,
        "reason": reason,
        "checked_at_unix": round(time.time(), 3),
    }


def _merge_board_ground(board_overlay: dict[str, Any] | None) -> dict[str, Any]:
    local_from_board = (board_overlay or {}).get("local_range") or {}
    ground = dict(local_from_board.get("ground") or {})
    gb = (board_overlay or {}).get("groundBinding") or {}
    if not ground:
        if gb:
            ground = {
                "available": bool(gb.get("available")),
                "reason": gb.get("reason") or "ground_binding_only",
                "sha256": gb.get("sha256"),
                "physicalGroundTruth": "UNKNOWN",
            }
        else:
            ground = {
                "available": False,
                "reason": "not_declared_in_readonly_live_mode",
                "physicalGroundTruth": "UNKNOWN",
            }
    if not ground.get("displayPlane") and gb.get("displayPlane"):
        ground["displayPlane"] = gb["displayPlane"]
    return ground


def decode_ros_std_string(payload: bytes | bytearray | memoryview) -> str:
    """解码 ROS1 std_msgs/String 线格式（<I len + UTF-8）。"""
    mv = memoryview(payload)
    if mv.nbytes < 4:
        raise ValueError("truncated ROS String")
    (length,) = struct.unpack_from("<I", mv, 0)
    if 4 + length != mv.nbytes:
        raise ValueError("ROS String length mismatch")
    return bytes(mv[4 : 4 + length]).decode("utf-8")


class LiveSource:
    """只读订阅板端 Foxglove 点云，在 PC 本地运行解码与可选 RangeRuntime，输出 LDSF 二进制帧。"""

    def __init__(
        self,
        ws_url: str = "ws://192.168.31.58:8765",
        camera_url: str = "http://192.168.31.58:8081/stream",
        *,
        decimation: int = 2,
        empty_prefix_frames: int | None = None,
        stream_mode: str = "cloud_and_json",
        on_frame: Callable[[bytes], None] | None = None,
        on_status: Callable[[dict[str, Any]], None] | None = None,
    ):
        parsed = urlparse(ws_url)
        if parsed.scheme not in ("ws", "wss") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError(f"invalid upstream Foxglove WS URL: {ws_url!r}")
        if stream_mode not in ("json_only", "cloud_and_json"):
            raise ValueError(f"unsupported stream_mode: {stream_mode!r}")
        self.ws_url = ws_url
        self.camera_url = camera_url
        self.decimation = max(1, min(16, int(decimation)))
        self.empty_prefix_frames = empty_prefix_frames
        self.stream_mode = "cloud_and_json" if (empty_prefix_frames is not None and empty_prefix_frames > 0) else stream_mode
        self.on_frame = on_frame
        self.on_status = on_status

        self._running = False
        self._tasks: list[asyncio.Task[None]] = []
        self._pending: tuple[str, Any, float] | None = None
        self._changed = asyncio.Event()
        self._lock = asyncio.Lock()

        self._status_state = "offline"
        self._reason = "尚未连接实时流"
        self._received = 0
        self._processed = 0
        self._dropped = 0
        self._errors = 0
        self._fps = 0.0
        self._last_frame_ts = 0.0
        self._board_state: tuple[dict[str, Any], float] | None = None
        self._last_board_preview: str | None = None
        self._last_board_session: str | None = None

        self._runtime: RangeRuntime | None = None
        self._demo_alert = DemoAlert()
        self._ground_alert = GroundAlertObserver()
        self._identity: dict[str, Any] | None = None
        self._binding: tuple | None = None
        self._base_stamp: float | None = None
        self._frame_seq = 0

    def set_decimation(self, decimation: int) -> None:
        self.decimation = max(1, min(16, int(decimation)))

    async def set_stream_mode(self, stream_mode: str) -> dict[str, Any]:
        if stream_mode not in ("json_only", "cloud_and_json"):
            raise ValueError(f"unsupported stream_mode: {stream_mode!r}")
        if self.empty_prefix_frames is not None and self.empty_prefix_frames > 0:
            stream_mode = "cloud_and_json"
        if stream_mode == self.stream_mode:
            return self.status()
        was_running = self._running
        if was_running:
            await self.stop()
        self.stream_mode = stream_mode
        self._last_board_preview = None
        self._base_stamp = None
        self._frame_seq = 0
        if was_running:
            return await self.start()
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "status": self._status_state,
            "reachable": self._status_state in ("connecting", "streaming"),
            "reason": self._reason,
            "board_ws": self.ws_url,
            "board_camera": self.camera_url,
            "received": self._received,
            "processed": self._processed,
            "dropped": self._dropped,
            "errors": self._errors,
            "fps": round(self._fps, 2),
            "decimation": self.decimation,
            "stream_mode": self.stream_mode,
            "empty_prefix_frames": self.empty_prefix_frames,
        }

    def _emit_status(self) -> None:
        if self.on_status is not None:
            self.on_status(self.status())

    def _reset_pipeline(self, frame_id: str) -> None:
        grid, az_sha, el_sha = get_shared_grid()
        self._identity = {
            "session": "live_studio_" + str(int(time.time())),
            "coordinate": "RAW/" + frame_id,
            "units": "m",
            "coordinate_transform": "identity",
            "grid_sha256": grid.sha256,
            "azimuth_sha256": az_sha,
            "elevation_sha256": el_sha,
            "epoch": "live_source_header",
        }
        self._binding = binding_tuple(self._identity)
        self._base_stamp = None
        self._frame_seq = 0
        self._demo_alert = DemoAlert()
        self._ground_alert = GroundAlertObserver()
        if self.empty_prefix_frames is not None and self.empty_prefix_frames > 0:
            self._runtime = RangeRuntime(
                grid,
                self._identity,
                empty_prefix_frames=int(self.empty_prefix_frames),
                human_physical_v1=True,
            )
        else:
            self._runtime = None

    async def start(self) -> dict[str, Any]:
        async with self._lock:
            probe = await probe_board(self.ws_url, self.camera_url, timeout=2.5, retries=1)
            if not probe["ws_reachable"]:
                self._status_state = "offline"
                self._reason = probe["reason"]
                self._emit_status()
                return {**self.status(), **probe}

            if not self._running:
                self._running = True
                self._status_state = "connecting"
                self._reason = (
                    "正在连接板端纯 JSON 状态流 (/single_target_live/state)..."
                    if self.stream_mode == "json_only"
                    else "正在连接板端 Foxglove 流..."
                )
                self._emit_status()
                self._tasks = [
                    asyncio.create_task(self._receive_loop()),
                    asyncio.create_task(self._process_loop()),
                ]
            return {**self.status(), **probe}

    async def stop(self) -> None:
        async with self._lock:
            self._running = False
            tasks = list(self._tasks)
            self._tasks.clear()
            self._pending = None
            self._status_state = "offline"
            self._reason = "已停止实时流"
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _receive_loop(self) -> None:
        retry = 0
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=2.5, sock_read=5.0)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                while self._running:
                    try:
                        self._status_state = "connecting"
                        self._reason = f"正在订阅 {self.ws_url} ..."
                        self._emit_status()
                        async with session.ws_connect(
                            self.ws_url,
                            protocols=("foxglove.websocket.v1",),
                            max_msg_size=33554432,
                        ) as ws:
                            retry = 0
                            sub_to_topic: dict[int, str] = {}
                            next_sub_id = 1
                            subscribed_topics: set[str] = set()
                            async for msg in ws:
                                if not self._running:
                                    break
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    event = json.loads(msg.data)
                                    if event.get("op") == "advertise":
                                        want_topics = (
                                            ("/single_target_live/state",)
                                            if self.stream_mode == "json_only"
                                            else ("/innolidar_points", "/single_target_live/state")
                                        )
                                        subs = []
                                        for ch in event.get("channels") or []:
                                            topic = ch.get("topic")
                                            if topic in want_topics and topic not in subscribed_topics:
                                                sid = next_sub_id
                                                next_sub_id += 1
                                                sub_to_topic[sid] = topic
                                                subscribed_topics.add(topic)
                                                subs.append({"id": sid, "channelId": ch["id"]})
                                        if subs:
                                            await ws.send_json({"op": "subscribe", "subscriptions": subs})
                                elif msg.type == aiohttp.WSMsgType.BINARY:
                                    data = msg.data
                                    if len(data) < 13 or data[0] != 1:
                                        continue
                                    (sub_id,) = struct.unpack_from("<I", data, 1)
                                    topic = sub_to_topic.get(sub_id)
                                    payload = data[13:]
                                    now = time.monotonic()
                                    if topic == "/innolidar_points" and self.stream_mode != "json_only":
                                        self._received += 1
                                        if self._pending is not None:
                                            self._dropped += 1
                                        self._pending = ("cloud", payload, now)
                                        self._changed.set()
                                    elif topic == "/single_target_live/state":
                                        try:
                                            board_json = json.loads(decode_ros_std_string(payload))
                                            self._board_state = (board_json, now)
                                            if self.stream_mode == "json_only":
                                                self._received += 1
                                                if self._pending is not None:
                                                    self._dropped += 1
                                                self._pending = ("board_json", board_json, now)
                                                self._changed.set()
                                        except Exception:
                                            pass
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                        if self._running:
                            raise OSError("Foxglove 连接已关闭")
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        if not self._running:
                            break
                        self._status_state = "offline"
                        self._reason = f"板端不可达 ({exc})"
                        self._errors += 1
                        self._emit_status()
                        delay = min(2.0 * (2 ** retry), 10.0)
                        retry = min(retry + 1, 6)
                        await asyncio.sleep(delay)
        except asyncio.CancelledError:
            pass

    async def _process_loop(self) -> None:
        try:
            while self._running:
                try:
                    await asyncio.wait_for(self._changed.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                self._changed.clear()
                item = self._pending
                self._pending = None
                if item is None:
                    continue
                kind, payload, received_ts = item
                if kind == "board_json":
                    packet = await asyncio.to_thread(self._process_board_json_sync, payload, received_ts)
                else:
                    packet = await asyncio.to_thread(self._process_one_sync, payload, received_ts)
                if packet is not None and self.on_frame is not None:
                    now = time.monotonic()
                    if self._last_frame_ts > 0:
                        dt = now - self._last_frame_ts
                        if dt > 0:
                            inst = 1.0 / dt
                            self._fps = inst if self._fps <= 0 else (0.8 * self._fps + 0.2 * inst)
                    self._last_frame_ts = now
                    self._status_state = "streaming"
                    self._reason = (
                        "板端纯 JSON 实时接收中"
                        if self.stream_mode == "json_only"
                        else "实时只读接收中"
                    )
                    self.on_frame(packet)
                    if self._processed % 10 == 1:
                        self._emit_status()
        except asyncio.CancelledError:
            pass

    def _process_board_json_sync(self, board_overlay: dict[str, Any], received_ts: float) -> bytes | None:
        t0 = time.perf_counter()
        try:
            src = board_overlay.get("source") or {}
            stamp = (
                float(src.get("stamp_secs", 0)) + float(src.get("stamp_nsecs", 0)) / 1e9
                if src
                else time.time()
            )
            session_id = str(board_overlay.get("session_id") or "board_live_json")
            if session_id != self._last_board_session:
                self._last_board_session = session_id
                self._last_board_preview = None
                self._base_stamp = stamp
                self._frame_seq = 0
            if self._base_stamp is None:
                self._base_stamp = stamp
            idx = int(src.get("seq")) if isinstance(src.get("seq"), int) else self._frame_seq
            self._frame_seq += 1

            local_from_board = board_overlay.get("local_range") or {}
            if not src:
                self._last_board_preview = None
            elif local_from_board.get("preview"):
                self._last_board_preview = str(local_from_board["preview"])

            ground_obj = _merge_board_ground(board_overlay)
            bg_obj = local_from_board.get("background") or {
                "status": "background_not_declared",
                "declaration": "board",
            }
            board_perf = board_overlay.get("performance") or {}
            board_phys = board_overlay.get("human_physical_v1")
            rows = board_overlay.get("target_source_rows") or []

            state_obj = {
                "schema_version": 1,
                "kind": "target_state",
                "mode": "live",
                "stream_mode": "json_only",
                "session_id": session_id,
                "frame_index": idx,
                "frame_count": 0,
                "stamp_sec": stamp,
                "relative_time_sec": round(stamp - self._base_stamp, 4),
                "time_epoch": board_overlay.get("time_epoch", 0),
                "target_mode": board_overlay.get("target_mode", "range_service_automatic"),
                "track_id": board_overlay.get("track_id"),
                "track_status": board_overlay.get("track_status", "unselected"),
                "observability": board_overlay.get("observability", "valid"),
                "bbox_observed": bool(board_overlay.get("bbox_observed")),
                "position_predicted": bool(board_overlay.get("position_predicted", False)),
                "fall_status": board_overlay.get("fall_status", "unknown"),
                "acquisition": board_overlay.get("acquisition") or {"reason": "board_state"},
                "semantic": "unknown",
                "confirmed_enabled": False,
                "service": board_overlay.get("service"),
                "health": board_overlay.get("health"),
                "local_range": {
                    "version": 1,
                    "heightMedianM": local_from_board.get("heightMedianM"),
                    "groundAlert": local_from_board.get("groundAlert"),
                    "measurement": local_from_board.get("measurement"),
                    "background": bg_obj,
                    "ground": ground_obj,
                    "fallEvidence": local_from_board.get("fallEvidence"),
                    "kinematics": local_from_board.get("kinematics"),
                    "demoFallCandidate": local_from_board.get("demoFallCandidate"),
                    "posture": local_from_board.get("posture"),
                    "skeleton": local_from_board.get("skeleton")
                    or {"version": "0.1.0", "semantic": "GEOMETRIC_REGIONS", "anatomicalJoints": "UNKNOWN", "nodes": {}, "edges": []},
                    "bbox": local_from_board.get("bbox"),
                    "preview": self._last_board_preview,
                    "depth": local_from_board.get("depth")
                    or {
                        "metadata": {
                            "format": "lidar_range_image",
                            "version": 2,
                            "width": 256,
                            "height": 192,
                            "nativeTransform": "rotate180",
                            "validPixels": 0,
                            "targetPixels": len(rows),
                        }
                    },
                },
                "performance": {
                    "process_ms": board_perf.get("service_compute_ms", board_perf.get("process_ms", (time.perf_counter() - t0) * 1000.0)),
                    "pc_pack_ms": (time.perf_counter() - t0) * 1000.0,
                    "local_age_ms": (time.monotonic() - received_ts) * 1000.0,
                    "runtime": board_perf.get("runtime") or {},
                    "board_stages": board_perf.get("stages") or {},
                },
                "diagnostics": board_overlay.get("diagnostics") or {"tracking": None},
                "human_physical_v1": board_phys,
                "camera": {"available": True, "state": "live_mjpeg", "alignment": "live_unaligned_visual_only"},
            }

            self._processed += 1
            return pack_frame(
                np.empty((0, 3), dtype="<f4"),
                np.empty(0, dtype=np.uint8),
                np.empty((0, 0), dtype="<u2"),
                sanitize_json(state_obj),
                decimation=1,
                is_live=True,
            )
        except Exception as exc:
            self._errors += 1
            self._reason = f"板端 JSON 解析异常: {exc}"
            return None

    def _process_one_sync(self, raw: bytes, received_ts: float) -> bytes | None:
        t0 = time.perf_counter()
        try:
            msg = parse_cloud(raw)
            h = msg.header
            stamp = h.stamp.secs + h.stamp.nsecs / 1e9
            if self._identity is None or self._identity["coordinate"] != "RAW/" + h.frame_id:
                self._reset_pipeline(h.frame_id)
            if self._base_stamp is None:
                self._base_stamp = stamp

            grid, _, _ = get_shared_grid()
            packed = pointcloud_rows(msg)
            idx = self._frame_seq
            self._frame_seq += 1

            target_rows_arr = np.empty(0, dtype=np.int32)
            rec_rows_arr = np.empty(0, dtype=np.int32)
            other_rows_arr = np.empty(0, dtype=np.int32)
            fg_rows_arr = np.empty(0, dtype=np.int32)

            if self._runtime is not None:
                result, frame, _ = self._runtime.update(packed, stamp, idx)
                record = result["tracking"]
                rule = result["rule"]
                phys = result.get("human_physical_v1") or {}
                features = rule["features"]
                hb = features.get("height_m") or {}
                rows = record["target_source_rows"]
                height = features.get("height_median_m")
                measured = bool(rows) and features.get("observable") and features.get("ground_relative")
                demo_level = self._demo_alert.update(
                    {
                        "i": idx,
                        "t": stamp,
                        "tid": record["target_track_id"],
                        "n": len(rows) if measured else 0,
                        "hm": height if measured else None,
                        "ht": hb.get("max") if measured else None,
                        "sp": features.get("horizontal_extent_m") if measured else None,
                        "generation": record["generation"],
                        "binding": frame.binding,
                        "reset": features.get("reset_now"),
                    }
                )
                demo = {
                    "variant": "horizontal_low_posture_v1",
                    "level": demo_level,
                    "active": demo_level > 0,
                    "state": (
                        "unavailable"
                        if not measured
                        else "sustained"
                        if demo_level == 2
                        else "suspected"
                        if demo_level == 1
                        else "pending"
                        if self._demo_alert.eligible
                        else "not_matched"
                    ),
                    "durationSec": self._demo_alert.duration,
                    "confirmedEnabled": False,
                    "semantic": "UNKNOWN",
                }
                alert = self._ground_alert.update(
                    {
                        "frameIndex": idx,
                        "stampSec": stamp,
                        "trackId": record["target_track_id"],
                        "generation": record["generation"],
                        "measured": bool(rows),
                        "heightMedianM": height,
                        "observationGap": features.get("observation_gap"),
                    }
                )[0]
                try:
                    pose = project_regions(
                        estimate_skeleton(frame.xyz[rows] if rows else [], rows if rows else []),
                        frame,
                    )
                except (ValueError, TypeError, FloatingPointError):
                    pose = project_regions(estimate_skeleton([], []), frame)
                bbox = compute_bbox(frame.xyz[rows]) if rows else None

                target_rows_arr = np.unique(np.asarray(rows, dtype=np.int32)) if rows else target_rows_arr
                rec_added = (phys.get("recovery") or {}).get("added_rows") or []
                if rec_added:
                    rec_rows_arr = np.unique(np.asarray(rec_added, dtype=np.int32))
                other_raw: list[int] = []
                for tr in record.get("tracks") or []:
                    if tr.get("track_id") != record["target_track_id"] and tr.get("observed") and tr.get("source_rows"):
                        other_raw.extend(tr["source_rows"])
                if other_raw:
                    other_rows_arr = np.unique(np.asarray(other_raw, dtype=np.int32))
                if self._runtime.background is not None:
                    bg_res = self._runtime.background.foreground(frame)
                    fg_r = frame.source_rows[bg_res["mask"] & frame.valid]
                    fg_rows_arr = np.unique(fg_r[fg_r >= 0].astype(np.int32))

                state_obj = {
                    "schema_version": 1,
                    "kind": "target_state",
                    "mode": "live",
                    "session_id": self._identity["session"],
                    "frame_index": idx,
                    "frame_count": 0,
                    "stamp_sec": stamp,
                    "relative_time_sec": round(stamp - self._base_stamp, 4),
                    "time_epoch": record["generation"],
                    "target_mode": "local_range_automatic",
                    "track_id": record["target_track_id"],
                    "track_status": "locked" if rows else "unselected",
                    "observability": "valid",
                    "bbox_observed": bool(rows),
                    "position_predicted": False,
                    "fall_status": rule["state"]["state"],
                    "acquisition": {
                        "reason": result["status"] if result["status"] != "ready" else (record.get("target_reason") or "current_target")
                    },
                    "semantic": "unknown",
                    "confirmed_enabled": False,
                    "local_range": {
                        "version": 1,
                        "heightMedianM": height,
                        "groundAlert": alert,
                        "measurement": {
                            "topHeightM": hb.get("max"),
                            "horizontalExtentM": features.get("horizontal_extent_m"),
                            "descentRateMps": features.get("descent_rate_m_s"),
                            "axisVerticality": features.get("axis_verticality"),
                        },
                        "background": {
                            "status": result["status"],
                            "configSha256": self._runtime.config_sha,
                            "declaration": "live_empty_prefix",
                        },
                        "ground": {
                            "available": False,
                            "reason": "live_ground_not_loaded",
                            "physicalGroundTruth": "UNKNOWN",
                        },
                        "fallEvidence": rule["state"],
                        "demoFallCandidate": demo,
                        "posture": rule.get("posture"),
                        "skeleton": compact_skeleton(pose),
                        "bbox": bbox,
                        "depth": {
                            "metadata": {
                                "format": "lidar_range_image",
                                "version": 2,
                                "width": grid.shape[1],
                                "height": grid.shape[0],
                                "nativeTransform": "rotate180",
                                "validPixels": int(frame.valid.sum()),
                                "targetPixels": len(rows),
                            }
                        },
                    },
                    "performance": {
                        "process_ms": (time.perf_counter() - t0) * 1000.0,
                        "local_age_ms": (time.monotonic() - received_ts) * 1000.0,
                        "runtime": result["timings"],
                    },
                    "diagnostics": {
                        "tracking": {
                            "reason": record.get("target_reason"),
                            "tracks": [
                                {
                                    "track_id": t.get("track_id"),
                                    "status": t.get("status"),
                                    "component_ids": t.get("component_ids"),
                                    "selection_score": t.get("selection_score"),
                                    "reason": t.get("reason"),
                                    "point_count": len(t.get("source_rows") or []),
                                }
                                for t in (record.get("tracks") or [])[:32]
                            ],
                            "trackCount": len(record.get("tracks") or []),
                        }
                    },
                    "human_physical_v1": compact_physical_v1(phys) if phys else None,
                    "camera": {"available": True, "state": "live_mjpeg", "alignment": "live_unaligned_visual_only"},
                }
            else:
                # 未声明空场背景：只做原生距离图与点云解码（若有板端 /single_target_live/state 完整透传结果、配平与物理评估）
                frame = grid.decode(packed, self._binding)
                board_overlay = None
                if self._board_state is not None and (time.monotonic() - self._board_state[1]) <= 1.0:
                    board_overlay = self._board_state[0]
                local_from_board = (board_overlay or {}).get("local_range") or {}
                board_phys = (board_overlay or {}).get("human_physical_v1")
                board_perf = (board_overlay or {}).get("performance") or {}
                ground_obj = _merge_board_ground(board_overlay)
                rows = (board_overlay or {}).get("target_source_rows") or []
                if rows:
                    valid_rows = [r for r in rows if 0 <= int(r) < len(frame.xyz)]
                    target_rows_arr = np.unique(np.asarray(valid_rows, dtype=np.int32))
                rec_added = ((board_phys or {}).get("recovery") or {}).get("added_rows") or []
                if rec_added:
                    valid_rec = [r for r in rec_added if 0 <= int(r) < len(frame.xyz)]
                    if valid_rec:
                        rec_rows_arr = np.unique(np.asarray(valid_rec, dtype=np.int32))

                dp = ground_obj.get("displayPlane") or {}
                bbox_val = local_from_board.get("bbox")
                if bbox_val is None and target_rows_arr.size:
                    basis = display_basis(dp["normal"]) if dp.get("normal") is not None else None
                    offset_m = float(dp.get("offsetM", 0.0)) if basis is not None else 0.0
                    bbox_val = compute_bbox(frame.xyz[target_rows_arr], basis=basis, offset_m=offset_m)

                state_obj = {
                    "schema_version": 1,
                    "kind": "target_state",
                    "mode": "live",
                    "stream_mode": "cloud_and_json",
                    "session_id": (board_overlay or {}).get("session_id") or self._identity["session"],
                    "frame_index": idx,
                    "frame_count": 0,
                    "stamp_sec": stamp,
                    "relative_time_sec": round(stamp - self._base_stamp, 4),
                    "time_epoch": (board_overlay or {}).get("time_epoch", 0),
                    "target_mode": (board_overlay or {}).get("target_mode", "local_range_automatic"),
                    "track_id": (board_overlay or {}).get("track_id"),
                    "track_status": (board_overlay or {}).get("track_status", "unselected"),
                    "observability": (board_overlay or {}).get("observability", "valid"),
                    "bbox_observed": bool(target_rows_arr.size or (board_overlay or {}).get("bbox_observed")),
                    "position_predicted": bool((board_overlay or {}).get("position_predicted", False)),
                    "fall_status": (board_overlay or {}).get("fall_status", "unknown"),
                    "acquisition": (board_overlay or {}).get("acquisition", {"reason": "background_not_declared"}),
                    "semantic": "unknown",
                    "confirmed_enabled": False,
                    "service": (board_overlay or {}).get("service"),
                    "health": (board_overlay or {}).get("health"),
                    "local_range": {
                        "version": 1,
                        "heightMedianM": local_from_board.get("heightMedianM"),
                        "groundAlert": local_from_board.get("groundAlert"),
                        "measurement": local_from_board.get("measurement"),
                        "background": local_from_board.get("background")
                        or {"status": "background_not_declared", "declaration": "none"},
                        "ground": ground_obj,
                        "fallEvidence": local_from_board.get("fallEvidence"),
                        "kinematics": local_from_board.get("kinematics"),
                        "demoFallCandidate": local_from_board.get("demoFallCandidate"),
                        "posture": local_from_board.get("posture"),
                        "skeleton": local_from_board.get("skeleton")
                        or compact_skeleton(project_regions(estimate_skeleton([], []), frame)),
                        "bbox": bbox_val,
                        "depth": {
                            "metadata": {
                                "format": "lidar_range_image",
                                "version": 2,
                                "width": grid.shape[1],
                                "height": grid.shape[0],
                                "nativeTransform": "rotate180",
                                "validPixels": int(frame.valid.sum()),
                                "targetPixels": int(target_rows_arr.size),
                            }
                        },
                    },
                    "performance": {
                        "process_ms": board_perf.get("service_compute_ms", (time.perf_counter() - t0) * 1000.0),
                        "pc_decode_ms": (time.perf_counter() - t0) * 1000.0,
                        "local_age_ms": (time.monotonic() - received_ts) * 1000.0,
                        "runtime": board_perf.get("runtime") or {},
                    },
                    "diagnostics": (board_overlay or {}).get("diagnostics") or {"tracking": None},
                    "human_physical_v1": board_phys,
                    "camera": {"available": True, "state": "live_mjpeg", "alignment": "live_unaligned_visual_only"},
                }

            xyz_all = frame.xyz
            n_raw = len(packed)
            if n_raw > 0:
                sq = np.sum(xyz_all.astype(np.float64) ** 2, axis=1)
                valid_pt = np.isfinite(xyz_all).all(axis=1) & (sq > 0.01)
            else:
                valid_pt = np.zeros(0, dtype=bool)

            keep_idx, point_flags, range_mask = build_point_flags_and_masks(
                n_raw,
                frame.valid,
                frame.source_rows,
                target_rows_arr,
                rec_rows_arr,
                other_rows_arr,
                fg_rows_arr,
                valid_pt,
                self.decimation,
            )
            xyz_out = xyz_all[keep_idx].astype("<f4")
            inten_out = packed["intensity"][keep_idx].astype("<f4")
            inten_out = np.where(np.isfinite(inten_out), inten_out, 0.0).astype("<f4")
            with np.errstate(invalid="ignore"):
                r_mm = np.where(
                    frame.valid & np.isfinite(frame.range_m),
                    np.clip(np.rint(frame.range_m * 1000.0), 1, 65535),
                    0,
                ).astype("<u2")[::-1, ::-1]

            self._processed += 1
            return pack_frame(
                xyz_out,
                point_flags,
                r_mm,
                sanitize_json(state_obj),
                intensity=inten_out,
                range_mask=range_mask,
                decimation=self.decimation,
                is_live=True,
            )
        except Exception as exc:
            self._errors += 1
            self._reason = f"实时解码异常: {exc}"
            return None
