"""P4 实时模式数据源：TCP 可达性探测 + 只读 Foxglove WS 订阅 + 同源精确配对 + 本地算法/降采样打包。

红线与约束：
- 只读订阅板端已有话题（/innolidar_points + 可选 /single_target_live/state），绝不发布控制/写板端。
- 板端不可达时如实上报 offline/"板端不可达"，绝不伪造任何点云或状态数据。
- 同源配对硬契约：点云、识别状态与 2D 预览严格按 (conn_gen, seq, stamp_secs, stamp_nsecs, frame_id)
  和原始 ROS PointCloud2 wire SHA256 配对；错帧/缺字段/重连/回拨/过期绝不叠加旧目标或旧预览。
"""

from __future__ import annotations

import asyncio
import base64
from collections import OrderedDict, deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys
import threading
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

SourceKey = tuple[int, int, int, int, str]  # (conn_gen, seq, stamp_secs, stamp_nsecs, frame_id)
DEFAULT_STATE_TTL_S = 0.5
MAX_TTL_S = 5.0


@dataclass
class _CachedCloud:
    key: SourceKey
    order: int
    raw_bytes_len: int
    wire_sha256: str
    seq: int
    stamp_secs: int
    stamp_nsecs: int
    stamp_sec: float
    frame_id: str
    received_ts: float
    frame: Any
    packed: np.ndarray
    valid_pt: np.ndarray
    r_mm: np.ndarray
    frame_idx: int
    matched: bool = False
    matched_with_preview: bool = False
    matched_ts: float = 0.0
    matched_ttl_s: float = DEFAULT_STATE_TTL_S
    paired_preview_sha: str | None = None


@dataclass
class _CachedState:
    key: SourceKey
    board_overlay: dict[str, Any]
    received_ts: float
    ttl_s: float
    wire_sha256: str | None
    has_preview: bool
    session_id: str
    time_epoch: int


def _is_hex64(val: Any) -> bool:
    if not isinstance(val, str) or len(val) != 64:
        return False
    try:
        int(val, 16)
        return True
    except ValueError:
        return False


def _extract_source_key(src: Any, conn_gen: int) -> tuple[SourceKey | None, int | None, str | None]:
    if not isinstance(src, dict) or not src:
        return None, None, "missing_source_header"
    seq = src.get("seq")
    secs = src.get("stamp_secs")
    nsecs = src.get("stamp_nsecs")
    frame_id = src.get("frame_id")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        return None, None, "invalid_source_seq"
    if isinstance(secs, bool) or not isinstance(secs, int) or secs < 0:
        return None, None, "invalid_source_stamp"
    if isinstance(nsecs, bool) or not isinstance(nsecs, int) or not (0 <= nsecs < 1_000_000_000):
        return None, None, "invalid_source_stamp"
    if not isinstance(frame_id, str) or not frame_id.strip():
        return None, None, "missing_source_frame_id"
    key: SourceKey = (int(conn_gen), int(seq), int(secs), int(nsecs), frame_id)
    stamp_ns = int(secs) * 1_000_000_000 + int(nsecs)
    return key, stamp_ns, None


def _extract_ttl_s(board_overlay: dict[str, Any], default_ttl_s: float = DEFAULT_STATE_TTL_S) -> float:
    svc = board_overlay.get("service")
    if isinstance(svc, dict):
        ttl_ms = svc.get("ttlMs")
        if not isinstance(ttl_ms, bool) and isinstance(ttl_ms, (int, float)) and 0 < float(ttl_ms) <= MAX_TTL_S * 1000.0:
            return float(ttl_ms) / 1000.0
    return float(default_ttl_s)


def _validate_preview_payload(local_from_board: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """返回 (preview_b64_or_None, preview_sha_or_None, error_reason_or_None)。"""
    raw_prev = local_from_board.get("preview")
    if raw_prev is None or raw_prev == "":
        return None, None, None
    if not isinstance(raw_prev, str) or len(raw_prev) > 400_000:
        return None, None, "invalid_preview_payload"
    depth = local_from_board.get("depth")
    declared_sha = depth.get("previewSha256") if isinstance(depth, dict) else None
    if declared_sha is not None:
        if not _is_hex64(declared_sha):
            return None, None, "invalid_preview_sha256"
        try:
            decoded = base64.b64decode(raw_prev.encode("ascii"), validate=True)
        except Exception:
            return None, None, "invalid_preview_base64"
        actual_sha = hashlib.sha256(decoded).hexdigest()
        if actual_sha != declared_sha:
            return None, None, "preview_sha256_mismatch"
        return raw_prev, actual_sha, None
    return raw_prev, None, None


def _validate_row_indices(raw_rows: Any, n_raw: int) -> tuple[np.ndarray | None, str | None]:
    if not raw_rows:
        return np.empty(0, dtype=np.int32), None
    if not isinstance(raw_rows, list):
        return None, "invalid_source_rows_type"
    seen: set[int] = set()
    cleaned: list[int] = []
    for r in raw_rows:
        if isinstance(r, bool) or not isinstance(r, int) or r < 0 or r >= n_raw:
            return None, "source_rows_out_of_bounds"
        if r in seen:
            return None, "duplicate_source_rows"
        seen.add(r)
        cleaned.append(r)
    return np.asarray(sorted(cleaned), dtype=np.int32), None


def _empty_skeleton() -> dict[str, Any]:
    return {
        "version": "0.1.0",
        "semantic": "GEOMETRIC_REGIONS",
        "anatomicalJoints": "UNKNOWN",
        "nodes": {},
        "edges": [],
    }


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
    """只读订阅板端 Foxglove 点云与识别状态，严格同源配对并输出 LDSF 二进制帧。"""

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
        state_ttl_s: float = DEFAULT_STATE_TTL_S,
        max_cloud_cache: int = 8,
        max_cloud_bytes: int = 24 * 1024 * 1024,
        max_state_cache: int = 16,
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

        self._default_ttl_s = max(0.05, min(MAX_TTL_S, float(state_ttl_s)))
        self._max_cloud_cache = max(2, int(max_cloud_cache))
        self._max_cloud_bytes = max(256 * 1024, int(max_cloud_bytes))
        self._max_state_cache = max(4, int(max_state_cache))

        self._running = False
        self._tasks: list[asyncio.Task[None]] = []
        self._incoming: deque[tuple[str, Any, float]] = deque()
        self._incoming_lock = threading.Lock()
        self._pair_lock = threading.Lock()
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
        # 保留属性兼容只读检查，不再直接作为无校验覆盖来源
        self._board_state: tuple[dict[str, Any], float] | None = None
        self._last_board_session: str | None = None

        self._runtime: RangeRuntime | None = None
        self._demo_alert = DemoAlert()
        self._ground_alert = GroundAlertObserver()
        self._identity: dict[str, Any] | None = None
        self._binding: tuple | None = None
        self._base_stamp: float | None = None
        self._frame_seq = 0

        # 同源配对状态与双侧有界缓存
        self._conn_gen = 0
        self._cloud_order = 0
        self._cloud_bytes_used = 0
        self._clouds: OrderedDict[SourceKey, _CachedCloud] = OrderedDict()
        self._states: OrderedDict[SourceKey, _CachedState] = OrderedDict()
        self._evicted_cloud_keys: OrderedDict[SourceKey, float] = OrderedDict()
        self._presented_key: SourceKey | None = None
        self._presented_order = 0
        self._presented_expired_emitted = False
        self._last_cloud_seq_stamp: tuple[int, int] | None = None
        self._last_state_session: str | None = None
        self._last_state_epoch: int = -1
        self._last_json_key: SourceKey | None = None
        self._last_json_seq_stamp: tuple[str, int, int] | None = None
        self._json_same_key_preview: tuple[SourceKey, str] | None = None
        self._last_valid_display_plane: dict[str, Any] | None = None

        # 配对与淘汰统计
        self._reset_metrics()

    def _reset_metrics(self) -> None:
        self._m_matched = 0
        self._m_unmatched = 0
        self._m_awaiting = 0
        self._m_late_preview = 0
        self._m_lost_evicted = 0
        self._m_lost_superseded = 0
        self._m_expired = 0
        self._m_wire_sha_mismatch = 0
        self._m_missing_wire_sha = 0
        self._m_source_rewinds = 0
        self._m_invalid_heartbeats = 0
        self._m_row_errors = 0
        self._m_cloud_evicted_ttl = 0
        self._m_cloud_evicted_cap = 0
        self._m_state_evicted_ttl = 0
        self._m_state_evicted_cap = 0
        self._wait_ms_samples: deque[float] = deque(maxlen=256)

    def pairing_metrics(self) -> dict[str, Any]:
        with self._pair_lock:
            samples = list(self._wait_ms_samples)
            if samples:
                arr = np.asarray(samples, dtype=np.float64)
                p50 = round(float(np.percentile(arr, 50.0)), 2)
                p95 = round(float(np.percentile(arr, 95.0)), 2)
                wmax = round(float(np.max(arr)), 2)
            else:
                p50 = p95 = wmax = 0.0
            return {
                "conn_gen": self._conn_gen,
                "matched_frames": self._m_matched,
                "unmatched_frames": self._m_unmatched,
                "awaiting_frames": self._m_awaiting,
                "late_preview_updates": self._m_late_preview,
                "lost_valid_results_evicted": self._m_lost_evicted,
                "lost_valid_results_superseded": self._m_lost_superseded,
                "expired_count": self._m_expired,
                "wire_sha_mismatches": self._m_wire_sha_mismatch,
                "missing_wire_sha": self._m_missing_wire_sha,
                "source_rewinds": self._m_source_rewinds,
                "invalid_source_heartbeats": self._m_invalid_heartbeats,
                "row_bounds_errors": self._m_row_errors,
                "cloud_cache_size": len(self._clouds),
                "cloud_cache_bytes": self._cloud_bytes_used,
                "state_cache_size": len(self._states),
                "cloud_evicted_ttl": self._m_cloud_evicted_ttl,
                "cloud_evicted_capacity": self._m_cloud_evicted_cap,
                "state_evicted_ttl": self._m_state_evicted_ttl,
                "state_evicted_capacity": self._m_state_evicted_cap,
                "wait_ms_count": len(samples),
                "wait_ms_p50": p50,
                "wait_ms_p95": p95,
                "wait_ms_max": wmax,
            }

    def on_reconnect(self) -> int:
        """重连或重置连接代际：彻底清空待配对缓存与旧预览，杜绝序号复用串帧。"""
        with self._pair_lock:
            self._conn_gen += 1
            self._clouds.clear()
            self._states.clear()
            self._evicted_cloud_keys.clear()
            self._cloud_bytes_used = 0
            self._presented_key = None
            self._presented_order = 0
            self._presented_expired_emitted = False
            self._last_cloud_seq_stamp = None
            self._last_state_session = None
            self._last_state_epoch = -1
            self._last_json_key = None
            self._last_json_seq_stamp = None
            self._json_same_key_preview = None
            self._last_valid_display_plane = None
            self._board_state = None
            return self._conn_gen

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
        self._base_stamp = None
        self._frame_seq = 0
        self.on_reconnect()
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
            "pairing_metrics": self.pairing_metrics(),
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
                self.on_reconnect()
                with self._incoming_lock:
                    self._incoming.clear()
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
            with self._incoming_lock:
                self._incoming.clear()
            self._status_state = "offline"
            self._reason = "已停止实时流"
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.on_reconnect()

    def _enqueue_incoming(self, kind: str, payload: Any, now: float) -> None:
        with self._incoming_lock:
            if kind == "cloud":
                # 点云最多缓冲 4 帧，超出时丢弃最老未解码点云，不影响状态消息
                cloud_count = sum(1 for k, _, _ in self._incoming if k == "cloud")
                if cloud_count >= 4:
                    for idx, (k, _, _) in enumerate(self._incoming):
                        if k == "cloud":
                            del self._incoming[idx]
                            self._dropped += 1
                            break
            elif kind == "board_json":
                state_count = sum(1 for k, _, _ in self._incoming if k == "board_json")
                if state_count >= 24:
                    for idx, (k, _, _) in enumerate(self._incoming):
                        if k == "board_json":
                            del self._incoming[idx]
                            self._dropped += 1
                            break
            self._incoming.append((kind, payload, now))
        self._changed.set()

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
                            self._enqueue_incoming("reconnect", None, time.monotonic())
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
                                        self._enqueue_incoming("cloud", payload, now)
                                    elif topic == "/single_target_live/state":
                                        try:
                                            board_json = json.loads(decode_ros_std_string(payload))
                                            self._board_state = (board_json, now)
                                            if self.stream_mode == "json_only":
                                                self._received += 1
                                            self._enqueue_incoming("board_json", board_json, now)
                                        except Exception:
                                            self._errors += 1
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

    def _emit_packets(self, packets: list[bytes]) -> None:
        if not packets or self.on_frame is None:
            return
        for packet in packets:
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

    async def _process_loop(self) -> None:
        try:
            while self._running:
                try:
                    await asyncio.wait_for(self._changed.wait(), timeout=0.1)
                except asyncio.TimeoutError:
                    exp_pkts = await asyncio.to_thread(self.check_expiry, time.monotonic())
                    self._emit_packets(exp_pkts)
                    continue
                self._changed.clear()
                while self._running:
                    with self._incoming_lock:
                        if not self._incoming:
                            break
                        kind, payload, received_ts = self._incoming.popleft()
                    if kind == "reconnect":
                        await asyncio.to_thread(self.on_reconnect)
                        continue
                    if kind == "board_json":
                        packets = await asyncio.to_thread(self.ingest_board_state, payload, received_ts)
                    else:
                        packets = await asyncio.to_thread(self.ingest_cloud, payload, received_ts)
                    self._emit_packets(packets)
        except asyncio.CancelledError:
            pass

    # ------------------------------------------------------------------
    # 双侧有界缓存清理（必须在 self._pair_lock 持锁状态下调用）
    # ------------------------------------------------------------------
    def _record_evicted_cloud(self, key: SourceKey, now: float) -> None:
        self._evicted_cloud_keys[key] = now
        self._evicted_cloud_keys.move_to_end(key)
        while len(self._evicted_cloud_keys) > 64:
            self._evicted_cloud_keys.popitem(last=False)

    def _evict_caches_locked(self, now: float) -> None:
        # 1. 淘汰过期状态（若从未匹配到点云且为有效源状态，计入淘汰丢结果）
        for k in list(self._states.keys()):
            st = self._states[k]
            if now - st.received_ts > st.ttl_s:
                del self._states[k]
                self._m_state_evicted_ttl += 1
                self._m_lost_evicted += 1
                self._m_expired += 1
        while len(self._states) > self._max_state_cache:
            self._states.popitem(last=False)
            self._m_state_evicted_cap += 1
            self._m_lost_evicted += 1

        # 2. 淘汰过期或超容点云（当前正在展示的帧在 TTL 过期前保留供同帧迟到预览）
        for k in list(self._clouds.keys()):
            c = self._clouds[k]
            ttl = c.matched_ttl_s if c.matched else self._default_ttl_s
            if now - c.received_ts > ttl and k != self._presented_key:
                del self._clouds[k]
                self._cloud_bytes_used = max(0, self._cloud_bytes_used - c.raw_bytes_len)
                self._m_cloud_evicted_ttl += 1
                if not c.matched:
                    self._record_evicted_cloud(k, now)

        while (len(self._clouds) > self._max_cloud_cache or self._cloud_bytes_used > self._max_cloud_bytes) and len(self._clouds) > 1:
            oldest_key = next(iter(self._clouds))
            if oldest_key == self._presented_key and len(self._clouds) > 1:
                it = iter(self._clouds)
                next(it)
                oldest_key = next(it)
            c = self._clouds.pop(oldest_key)
            self._cloud_bytes_used = max(0, self._cloud_bytes_used - c.raw_bytes_len)
            self._m_cloud_evicted_cap += 1
            if not c.matched:
                self._record_evicted_cloud(oldest_key, now)

    def _pack_cloud_unpaired_locked(
        self,
        cloud: _CachedCloud,
        *,
        status: str,
        reason: str,
        now: float,
        t0: float,
        board_service: dict[str, Any] | None = None,
        board_health: dict[str, Any] | None = None,
    ) -> bytes:
        grid, _, _ = get_shared_grid()
        n_raw = len(cloud.packed)
        empty = np.empty(0, dtype=np.int32)
        keep_idx, point_flags, range_mask = build_point_flags_and_masks(
            n_raw,
            cloud.frame.valid,
            cloud.frame.source_rows,
            empty,
            empty,
            empty,
            empty,
            cloud.valid_pt,
            self.decimation,
        )
        xyz_out = cloud.frame.xyz[keep_idx].astype("<f4")
        inten_out = cloud.packed["intensity"][keep_idx].astype("<f4")
        inten_out = np.where(np.isfinite(inten_out), inten_out, 0.0).astype("<f4")

        ground_obj: dict[str, Any] = {
            "available": False,
            "reason": "unpaired_awaiting_board_state" if status == "awaiting_state" else reason,
            "physicalGroundTruth": "UNKNOWN",
        }
        if self._last_valid_display_plane is not None and status == "awaiting_state":
            # 仅保留已绑定配平视角防止等待期间画面倾倒，绝不宣称地面高度当前有效
            ground_obj["displayPlane"] = dict(self._last_valid_display_plane)

        state_obj = {
            "schema_version": 1,
            "kind": "target_state",
            "mode": "live",
            "stream_mode": "cloud_and_json",
            "session_id": self._identity["session"] if self._identity else "live_studio",
            "frame_index": cloud.frame_idx,
            "frame_count": 0,
            "stamp_sec": cloud.stamp_sec,
            "relative_time_sec": round(cloud.stamp_sec - (self._base_stamp or cloud.stamp_sec), 4),
            "time_epoch": 0,
            "source": {
                "seq": cloud.seq,
                "stamp_secs": cloud.stamp_secs,
                "stamp_nsecs": cloud.stamp_nsecs,
                "frame_id": cloud.frame_id,
            },
            "target_mode": "local_range_automatic",
            "track_id": None,
            "track_status": "unselected",
            "observability": "valid" if status == "awaiting_state" else "invalid",
            "bbox_observed": False,
            "position_predicted": False,
            "fall_status": "unknown",
            "acquisition": {"reason": reason},
            "semantic": "unknown",
            "confirmed_enabled": False,
            "service": board_service,
            "health": board_health,
            "pairing": {
                "status": status,
                "reason": reason,
                "conn_gen": cloud.key[0],
                "wire_sha256": cloud.wire_sha256,
                "is_provisional": status == "awaiting_state",
                "preview_state": "none",
            },
            "local_range": {
                "version": 1,
                "wireSha256": cloud.wire_sha256,
                "heightMedianM": None,
                "groundAlert": None,
                "measurement": None,
                "background": {"status": "awaiting_board_state" if status == "awaiting_state" else "unpaired", "declaration": "none"},
                "ground": ground_obj,
                "fallEvidence": None,
                "kinematics": None,
                "demoFallCandidate": None,
                "posture": None,
                "skeleton": _empty_skeleton(),
                "bbox": None,
                "preview": None,
                "depth": {
                    "metadata": {
                        "format": "lidar_range_image",
                        "version": 2,
                        "width": grid.shape[1],
                        "height": grid.shape[0],
                        "nativeTransform": "rotate180",
                        "validPixels": int(cloud.frame.valid.sum()),
                        "targetPixels": 0,
                    }
                },
            },
            "performance": {
                "process_ms": (time.perf_counter() - t0) * 1000.0,
                "pc_decode_ms": (time.perf_counter() - t0) * 1000.0,
                "local_age_ms": max(0.0, (now - cloud.received_ts) * 1000.0),
                "runtime": {},
            },
            "diagnostics": {"tracking": None},
            "human_physical_v1": None,
            "camera": {"available": True, "state": "live_mjpeg", "alignment": "live_unaligned_visual_only"},
        }
        self._processed += 1
        return pack_frame(
            xyz_out,
            point_flags,
            cloud.r_mm,
            sanitize_json(state_obj),
            intensity=inten_out,
            range_mask=range_mask,
            decimation=self.decimation,
            is_live=True,
        )

    def _pack_cloud_paired_locked(
        self,
        cloud: _CachedCloud,
        board_overlay: dict[str, Any],
        *,
        now: float,
        t0: float,
        preview_b64: str | None,
        preview_state: str,
        wait_ms: float | None,
    ) -> tuple[bytes | None, str | None]:
        grid, _, _ = get_shared_grid()
        n_raw = len(cloud.packed)
        local_from_board = board_overlay.get("local_range") or {}
        board_phys = board_overlay.get("human_physical_v1")
        board_perf = board_overlay.get("performance") or {}
        ground_obj = _merge_board_ground(board_overlay)

        measured = (
            bool(board_overlay.get("bbox_observed"))
            and not bool(board_overlay.get("position_predicted", False))
            and board_overlay.get("observability", "valid") != "invalid"
        )
        raw_rows = (board_overlay.get("target_source_rows") or []) if measured else []
        target_rows_arr, row_err = _validate_row_indices(raw_rows, n_raw)
        if row_err is not None or target_rows_arr is None:
            self._m_row_errors += 1
            return None, row_err or "source_rows_out_of_bounds"

        raw_rec = (((board_phys or {}).get("recovery") or {}).get("added_rows") or []) if measured else []
        rec_rows_arr, rec_err = _validate_row_indices(raw_rec, n_raw)
        if rec_err is not None or rec_rows_arr is None:
            self._m_row_errors += 1
            return None, rec_err or "source_rows_out_of_bounds"

        dp = ground_obj.get("displayPlane") or {}
        if dp.get("normal") is not None:
            self._last_valid_display_plane = dict(dp)

        bbox_val = local_from_board.get("bbox") if measured else None
        if bbox_val is None and target_rows_arr.size:
            basis = display_basis(dp["normal"]) if dp.get("normal") is not None else None
            offset_m = float(dp.get("offsetM", 0.0)) if basis is not None else 0.0
            bbox_val = compute_bbox(cloud.frame.xyz[target_rows_arr], basis=basis, offset_m=offset_m)

        empty = np.empty(0, dtype=np.int32)
        keep_idx, point_flags, range_mask = build_point_flags_and_masks(
            n_raw,
            cloud.frame.valid,
            cloud.frame.source_rows,
            target_rows_arr,
            rec_rows_arr,
            empty,
            empty,
            cloud.valid_pt,
            self.decimation,
        )
        xyz_out = cloud.frame.xyz[keep_idx].astype("<f4")
        inten_out = cloud.packed["intensity"][keep_idx].astype("<f4")
        inten_out = np.where(np.isfinite(inten_out), inten_out, 0.0).astype("<f4")

        state_obj = {
            "schema_version": 1,
            "kind": "target_state",
            "mode": "live",
            "stream_mode": "cloud_and_json",
            "session_id": board_overlay.get("session_id") or (self._identity["session"] if self._identity else "live_studio"),
            "frame_index": cloud.frame_idx,
            "frame_count": 0,
            "stamp_sec": cloud.stamp_sec,
            "relative_time_sec": round(cloud.stamp_sec - (self._base_stamp or cloud.stamp_sec), 4),
            "time_epoch": board_overlay.get("time_epoch", 0),
            "source": {
                "seq": cloud.seq,
                "stamp_secs": cloud.stamp_secs,
                "stamp_nsecs": cloud.stamp_nsecs,
                "frame_id": cloud.frame_id,
            },
            "target_mode": board_overlay.get("target_mode", "local_range_automatic"),
            "track_id": board_overlay.get("track_id"),
            "track_status": board_overlay.get("track_status", "unselected"),
            "observability": board_overlay.get("observability", "valid"),
            "bbox_observed": bool(target_rows_arr.size or board_overlay.get("bbox_observed")),
            "position_predicted": bool(board_overlay.get("position_predicted", False)),
            "fall_status": board_overlay.get("fall_status", "unknown"),
            "acquisition": board_overlay.get("acquisition", {"reason": "current_target"}),
            "semantic": "unknown",
            "confirmed_enabled": False,
            "service": board_overlay.get("service"),
            "health": board_overlay.get("health"),
            "pairing": {
                "status": "matched",
                "reason": "matched",
                "conn_gen": cloud.key[0],
                "wire_sha256": cloud.wire_sha256,
                "is_provisional": False,
                "preview_state": preview_state,
                "wait_ms": None if wait_ms is None else round(wait_ms, 2),
            },
            "local_range": {
                "version": 1,
                "wireSha256": cloud.wire_sha256,
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
                "skeleton": local_from_board.get("skeleton") or _empty_skeleton(),
                "bbox": bbox_val,
                "preview": preview_b64,
                "depth": {
                    "metadata": {
                        "format": "lidar_range_image",
                        "version": 2,
                        "width": grid.shape[1],
                        "height": grid.shape[0],
                        "nativeTransform": "rotate180",
                        "validPixels": int(cloud.frame.valid.sum()),
                        "targetPixels": int(target_rows_arr.size),
                    }
                },
            },
            "performance": {
                "process_ms": board_perf.get("service_compute_ms", (time.perf_counter() - t0) * 1000.0),
                "pc_decode_ms": (time.perf_counter() - t0) * 1000.0,
                "local_age_ms": max(0.0, (now - cloud.received_ts) * 1000.0),
                "runtime": board_perf.get("runtime") or {},
            },
            "diagnostics": board_overlay.get("diagnostics") or {"tracking": None},
            "human_physical_v1": board_phys,
            "camera": {"available": True, "state": "live_mjpeg", "alignment": "live_unaligned_visual_only"},
        }
        self._processed += 1
        pkt = pack_frame(
            xyz_out,
            point_flags,
            cloud.r_mm,
            sanitize_json(state_obj),
            intensity=inten_out,
            range_mask=range_mask,
            decimation=self.decimation,
            is_live=True,
        )
        return pkt, None

    def _validate_state_against_cloud_locked(
        self,
        cloud: _CachedCloud,
        board_overlay: dict[str, Any],
        state_ts: float,
        now: float,
    ) -> tuple[str | None, str | None, str | None]:
        """校验 board_overlay 与 cloud 的 TTL、wireSha256、预览哈希。返回 (error_reason, preview_b64, preview_sha)。"""
        ttl_s = _extract_ttl_s(board_overlay, self._default_ttl_s)
        if (now - cloud.received_ts) > ttl_s or (now - state_ts) > ttl_s:
            self._m_expired += 1
            return "recognition_result_expired", None, None

        local_from_board = board_overlay.get("local_range")
        if not isinstance(local_from_board, dict):
            self._m_missing_wire_sha += 1
            return "missing_wire_sha256", None, None

        wire_sha = local_from_board.get("wireSha256")
        if not _is_hex64(wire_sha):
            self._m_missing_wire_sha += 1
            return "missing_wire_sha256", None, None
        if wire_sha != cloud.wire_sha256:
            self._m_wire_sha_mismatch += 1
            return "wire_sha256_mismatch", None, None

        preview_b64, preview_sha, prev_err = _validate_preview_payload(local_from_board)
        if prev_err is not None:
            return prev_err, None, None
        return None, preview_b64, preview_sha

    def ingest_board_state(self, board_overlay: dict[str, Any], received_ts: float | None = None) -> list[bytes]:
        """同步接入单条板端 /single_target_live/state，返回 0 或 1 个待下发 LDSF 帧包。"""
        now = time.monotonic() if received_ts is None else float(received_ts)
        if self.stream_mode == "json_only":
            pkt = self._process_board_json_sync(board_overlay, now)
            return [pkt] if pkt is not None else []
        if self._runtime is not None:
            return []

        t0 = time.perf_counter()
        with self._pair_lock:
            self._evict_caches_locked(now)
            src = board_overlay.get("source")
            key, stamp_ns, src_err = _extract_source_key(src, self._conn_gen)
            if src_err is not None or key is None or stamp_ns is None:
                self._m_invalid_heartbeats += 1
                # 无 source 心跳 / 板端失效：若当前展示帧曾已匹配且处于失效，不叠加旧目标
                reason = (board_overlay.get("acquisition") or {}).get("reason") or src_err or "missing_source_header"
                if self._presented_key is not None and self._presented_key in self._clouds:
                    cur_cloud = self._clouds[self._presented_key]
                    if cur_cloud.matched and board_overlay.get("observability") == "invalid":
                        cur_cloud.matched = False
                        cur_cloud.matched_with_preview = False
                        self._m_unmatched += 1
                        return [
                            self._pack_cloud_unpaired_locked(
                                cur_cloud,
                                status="invalid_source",
                                reason=str(reason),
                                now=now,
                                t0=t0,
                                board_service=board_overlay.get("service"),
                                board_health=board_overlay.get("health"),
                            )
                        ]
                return []

            sess_id = str(board_overlay.get("session_id") or "")
            epoch = int(board_overlay.get("time_epoch") or 0)
            if self._last_state_session is not None and (sess_id != self._last_state_session or epoch < self._last_state_epoch):
                if sess_id == self._last_state_session and epoch < self._last_state_epoch:
                    self._m_source_rewinds += 1
                    return []
                # 新会话切换：清空旧会话待配对状态
                self._states.clear()
            self._last_state_session = sess_id
            self._last_state_epoch = epoch

            ttl_s = _extract_ttl_s(board_overlay, self._default_ttl_s)
            local_from_board = board_overlay.get("local_range") or {}
            wire_sha = local_from_board.get("wireSha256")
            has_preview = bool(local_from_board.get("preview"))

            cloud = self._clouds.get(key)
            if cloud is not None:
                if cloud.order < self._presented_order:
                    # 更新的点云已上屏，绝不倒退显示旧帧；诚实计入迟到被覆盖的有效结果
                    if wire_sha == cloud.wire_sha256 and not cloud.matched:
                        self._m_lost_superseded += 1
                    return []

                err, prev_b64, prev_sha = self._validate_state_against_cloud_locked(cloud, board_overlay, now, now)
                if err is not None:
                    self._m_unmatched += 1
                    if err == "recognition_result_expired":
                        self._m_lost_evicted += 1
                    return [
                        self._pack_cloud_unpaired_locked(
                            cloud,
                            status="expired" if err == "recognition_result_expired" else "unpaired",
                            reason=err,
                            now=now,
                            t0=t0,
                            board_service=board_overlay.get("service"),
                            board_health=board_overlay.get("health"),
                        )
                    ]

                # 重复心跳 / 同帧迟到预览判定
                if cloud.matched:
                    if prev_b64 is not None and (not cloud.matched_with_preview or prev_sha != cloud.paired_preview_sha):
                        cloud.matched_with_preview = True
                        cloud.paired_preview_sha = prev_sha
                        cloud.matched_ts = now
                        cloud.matched_ttl_s = ttl_s
                        self._m_late_preview += 1
                        pkt, pack_err = self._pack_cloud_paired_locked(
                            cloud,
                            board_overlay,
                            now=now,
                            t0=t0,
                            preview_b64=prev_b64,
                            preview_state="late_same_frame",
                            wait_ms=max(0.0, (now - cloud.received_ts) * 1000.0),
                        )
                        if pack_err is not None or pkt is None:
                            self._m_unmatched += 1
                            return [self._pack_cloud_unpaired_locked(cloud, status="unpaired", reason=pack_err or "pack_error", now=now, t0=t0)]
                        return [pkt]
                    # 同一帧无新增预览的重复心跳：刷新匹配存活时刻，避免重复刷屏
                    cloud.matched_ts = now
                    cloud.matched_ttl_s = ttl_s
                    return []

                wait_ms = max(0.0, (now - cloud.received_ts) * 1000.0)
                pkt, pack_err = self._pack_cloud_paired_locked(
                    cloud,
                    board_overlay,
                    now=now,
                    t0=t0,
                    preview_b64=prev_b64,
                    preview_state="present" if prev_b64 else "pending_for_frame",
                    wait_ms=wait_ms,
                )
                if pack_err is not None or pkt is None:
                    self._m_unmatched += 1
                    return [self._pack_cloud_unpaired_locked(cloud, status="unpaired", reason=pack_err or "pack_error", now=now, t0=t0)]
                cloud.matched = True
                cloud.matched_with_preview = prev_b64 is not None
                cloud.paired_preview_sha = prev_sha
                cloud.matched_ts = now
                cloud.matched_ttl_s = ttl_s
                self._presented_expired_emitted = False
                self._m_matched += 1
                self._wait_ms_samples.append(wait_ms)
                return [pkt]

            # 点云尚未到达或已被淘汰
            if key in self._evicted_cloud_keys:
                self._m_lost_evicted += 1
                return []

            # 状态先到：暂存待对应点云到达
            prev_cached = self._states.get(key)
            if prev_cached is not None and prev_cached.has_preview and not has_preview:
                # 保留已收到的同帧预览，避免无预览重复心跳覆盖
                return []
            self._states[key] = _CachedState(
                key=key,
                board_overlay=board_overlay,
                received_ts=now,
                ttl_s=ttl_s,
                wire_sha256=wire_sha if _is_hex64(wire_sha) else None,
                has_preview=has_preview,
                session_id=sess_id,
                time_epoch=epoch,
            )
            self._states.move_to_end(key)
            self._evict_caches_locked(now)
            return []

    def ingest_cloud(self, raw: bytes, received_ts: float | None = None) -> list[bytes]:
        """同步接入单帧 /innolidar_points，立即输出原始点云（若同源状态已先到则直接配对输出）。"""
        now = time.monotonic() if received_ts is None else float(received_ts)
        if self._runtime is not None:
            pkt = self._process_local_runtime_sync(raw, now)
            return [pkt] if pkt is not None else []

        t0 = time.perf_counter()
        try:
            raw_bytes = bytes(raw)
            wire_sha = hashlib.sha256(raw_bytes).hexdigest()
            msg = parse_cloud(raw_bytes)
            h = msg.header
            stamp_secs = int(h.stamp.secs)
            stamp_nsecs = int(h.stamp.nsecs)
            stamp = stamp_secs + stamp_nsecs / 1e9
            stamp_ns = stamp_secs * 1_000_000_000 + stamp_nsecs
            frame_id = str(h.frame_id)

            grid, _, _ = get_shared_grid()
            packed = pointcloud_rows(msg)

            with self._pair_lock:
                self._evict_caches_locked(now)
                if self._identity is None or self._identity["coordinate"] != "RAW/" + frame_id:
                    self._reset_pipeline(frame_id)
                if self._base_stamp is None:
                    self._base_stamp = stamp

                frame = grid.decode(packed, self._binding)
                xyz_all = frame.xyz
                n_raw = len(packed)
                if n_raw > 0:
                    sq = np.sum(xyz_all.astype(np.float64) ** 2, axis=1)
                    valid_pt = np.isfinite(xyz_all).all(axis=1) & (sq > 0.01)
                else:
                    valid_pt = np.zeros(0, dtype=bool)
                with np.errstate(invalid="ignore"):
                    r_mm = np.where(
                        frame.valid & np.isfinite(frame.range_m),
                        np.clip(np.rint(frame.range_m * 1000.0), 1, 65535),
                        0,
                    ).astype("<u2")[::-1, ::-1]

                idx = self._frame_seq
                self._frame_seq += 1
                key: SourceKey = (self._conn_gen, int(h.seq), stamp_secs, stamp_nsecs, frame_id)

                # 检测同连接下源序/时间戳回拨
                rewind = False
                if self._last_cloud_seq_stamp is not None:
                    prev_seq, prev_ns = self._last_cloud_seq_stamp
                    if int(h.seq) < prev_seq or stamp_ns < prev_ns:
                        rewind = True
                        self._m_source_rewinds += 1
                if not rewind:
                    self._last_cloud_seq_stamp = (int(h.seq), stamp_ns)

                self._cloud_order += 1
                cloud = _CachedCloud(
                    key=key,
                    order=self._cloud_order,
                    raw_bytes_len=len(raw_bytes),
                    wire_sha256=wire_sha,
                    seq=int(h.seq),
                    stamp_secs=stamp_secs,
                    stamp_nsecs=stamp_nsecs,
                    stamp_sec=stamp,
                    frame_id=frame_id,
                    received_ts=now,
                    frame=frame,
                    packed=packed,
                    valid_pt=valid_pt,
                    r_mm=r_mm,
                    frame_idx=idx,
                )

                if rewind:
                    self._m_unmatched += 1
                    return [self._pack_cloud_unpaired_locked(cloud, status="unpaired", reason="source_time_rewind", now=now, t0=t0)]

                # 写入有界点云缓存
                old_same = self._clouds.pop(key, None)
                if old_same is not None:
                    self._cloud_bytes_used = max(0, self._cloud_bytes_used - old_same.raw_bytes_len)
                self._clouds[key] = cloud
                self._cloud_bytes_used += cloud.raw_bytes_len
                self._presented_key = key
                self._presented_order = cloud.order
                self._presented_expired_emitted = False

                # 若此前展示的点云未匹配就被新点云顶掉，记录待淘汰检查
                self._evict_caches_locked(now)

                # 状态先到检查
                cached_st = self._states.pop(key, None)
                if cached_st is not None:
                    err, prev_b64, prev_sha = self._validate_state_against_cloud_locked(
                        cloud, cached_st.board_overlay, cached_st.received_ts, now
                    )
                    if err is not None:
                        self._m_unmatched += 1
                        if err == "recognition_result_expired":
                            self._m_lost_evicted += 1
                        return [
                            self._pack_cloud_unpaired_locked(
                                cloud,
                                status="expired" if err == "recognition_result_expired" else "unpaired",
                                reason=err,
                                now=now,
                                t0=t0,
                                board_service=cached_st.board_overlay.get("service"),
                                board_health=cached_st.board_overlay.get("health"),
                            )
                        ]

                    wait_ms = max(0.0, (now - cached_st.received_ts) * 1000.0)
                    pkt, pack_err = self._pack_cloud_paired_locked(
                        cloud,
                        cached_st.board_overlay,
                        now=now,
                        t0=t0,
                        preview_b64=prev_b64,
                        preview_state="present" if prev_b64 else "pending_for_frame",
                        wait_ms=wait_ms,
                    )
                    if pack_err is not None or pkt is None:
                        self._m_unmatched += 1
                        return [self._pack_cloud_unpaired_locked(cloud, status="unpaired", reason=pack_err or "pack_error", now=now, t0=t0)]

                    cloud.matched = True
                    cloud.matched_with_preview = prev_b64 is not None
                    cloud.paired_preview_sha = prev_sha
                    cloud.matched_ts = now
                    cloud.matched_ttl_s = cached_st.ttl_s
                    self._m_matched += 1
                    self._wait_ms_samples.append(wait_ms)
                    return [pkt]

                # 状态尚未到达：立即展示无叠加原始点云，等待同帧结果补齐
                self._m_awaiting += 1
                return [
                    self._pack_cloud_unpaired_locked(
                        cloud,
                        status="awaiting_state",
                        reason="awaiting_board_state",
                        now=now,
                        t0=t0,
                    )
                ]
        except Exception as exc:
            self._errors += 1
            self._reason = f"实时解码异常: {exc}"
            return []

    def check_expiry(self, now: float | None = None) -> list[bytes]:
        """检查当前已展示匹配帧是否超出 TTL；超期则显式清目标/疑似/预览并输出过期状态。"""
        now_val = time.monotonic() if now is None else float(now)
        if self.stream_mode == "json_only" or self._runtime is not None:
            return []
        t0 = time.perf_counter()
        with self._pair_lock:
            self._evict_caches_locked(now_val)
            if self._presented_key is None or self._presented_expired_emitted:
                return []
            cloud = self._clouds.get(self._presented_key)
            if cloud is None:
                return []
            if cloud.matched:
                ttl = cloud.matched_ttl_s
                if (now_val - cloud.matched_ts) > ttl and (now_val - cloud.received_ts) > ttl:
                    cloud.matched = False
                    cloud.matched_with_preview = False
                    self._presented_expired_emitted = True
                    self._m_expired += 1
                    self._m_unmatched += 1
                    return [
                        self._pack_cloud_unpaired_locked(
                            cloud,
                            status="expired",
                            reason="recognition_result_expired",
                            now=now_val,
                            t0=t0,
                        )
                    ]
            return []

    def _process_board_json_sync(self, board_overlay: dict[str, Any], received_ts: float) -> bytes | None:
        t0 = time.perf_counter()
        try:
            with self._pair_lock:
                src = board_overlay.get("source")
                key, stamp_ns, src_err = _extract_source_key(src, self._conn_gen)
                session_id = str(board_overlay.get("session_id") or "board_live_json")
                if session_id != self._last_board_session:
                    self._last_board_session = session_id
                    self._json_same_key_preview = None
                    self._last_json_key = None
                    self._last_json_seq_stamp = None
                    self._base_stamp = None
                    self._frame_seq = 0

                local_from_board = board_overlay.get("local_range") or {}
                ground_obj = _merge_board_ground(board_overlay)
                board_perf = board_overlay.get("performance") or {}

                # 1. 无效源帧 / 心跳失效：绝不复用旧预览、旧目标或旧疑似
                if src_err is not None or key is None or stamp_ns is None:
                    self._m_invalid_heartbeats += 1
                    self._m_unmatched += 1
                    self._json_same_key_preview = None
                    reason = (board_overlay.get("acquisition") or {}).get("reason") or src_err or "missing_source_header"
                    stamp_now = time.time()
                    if self._base_stamp is None:
                        self._base_stamp = stamp_now
                    idx = self._frame_seq
                    self._frame_seq += 1
                    state_obj = {
                        "schema_version": 1,
                        "kind": "target_state",
                        "mode": "live",
                        "stream_mode": "json_only",
                        "session_id": session_id,
                        "frame_index": idx,
                        "frame_count": 0,
                        "stamp_sec": stamp_now,
                        "relative_time_sec": round(stamp_now - self._base_stamp, 4),
                        "time_epoch": board_overlay.get("time_epoch", 0),
                        "source": None,
                        "target_mode": board_overlay.get("target_mode", "range_service_automatic"),
                        "track_id": None,
                        "track_status": "unselected",
                        "observability": "invalid",
                        "bbox_observed": False,
                        "position_predicted": False,
                        "fall_status": "unknown",
                        "acquisition": {"reason": str(reason)},
                        "semantic": "unknown",
                        "confirmed_enabled": False,
                        "service": board_overlay.get("service"),
                        "health": board_overlay.get("health"),
                        "pairing": {
                            "status": "invalid_source",
                            "reason": str(reason),
                            "conn_gen": self._conn_gen,
                            "preview_state": "cleared",
                        },
                        "local_range": {
                            "version": 1,
                            "heightMedianM": None,
                            "groundAlert": None,
                            "measurement": None,
                            "background": local_from_board.get("background") or {"status": "invalid_source", "declaration": "board"},
                            "ground": ground_obj,
                            "fallEvidence": None,
                            "kinematics": None,
                            "demoFallCandidate": None,
                            "posture": None,
                            "skeleton": _empty_skeleton(),
                            "bbox": None,
                            "preview": None,
                            "depth": {
                                "metadata": {
                                    "format": "lidar_range_image",
                                    "version": 2,
                                    "width": 256,
                                    "height": 192,
                                    "nativeTransform": "rotate180",
                                    "validPixels": 0,
                                    "targetPixels": 0,
                                }
                            },
                        },
                        "performance": {
                            "process_ms": board_perf.get("service_compute_ms", (time.perf_counter() - t0) * 1000.0),
                            "pc_pack_ms": (time.perf_counter() - t0) * 1000.0,
                            "local_age_ms": max(0.0, (time.monotonic() - received_ts) * 1000.0),
                            "runtime": board_perf.get("runtime") or {},
                            "board_stages": board_perf.get("stages") or {},
                        },
                        "diagnostics": {"tracking": None},
                        "human_physical_v1": None,
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

                seq = key[1]
                stamp = float(key[2]) + float(key[3]) / 1e9
                if self._base_stamp is None:
                    self._base_stamp = stamp

                # 2. 检查乱序/回拨（同会话下不允许倒退到更旧的源帧）
                same_frame = key == self._last_json_key
                if not same_frame and self._last_json_seq_stamp is not None:
                    prev_sess, prev_seq, prev_ns = self._last_json_seq_stamp
                    if prev_sess == session_id and (seq < prev_seq or stamp_ns < prev_ns):
                        self._m_source_rewinds += 1
                        self._m_unmatched += 1
                        return None

                # 3. 严格同源预览绑定：绝不把上一帧 PNG 贴到新帧
                preview_b64, _prev_sha, prev_err = _validate_preview_payload(local_from_board)
                if prev_err is not None:
                    preview_b64 = None
                if same_frame:
                    if preview_b64 is not None:
                        had_prev = self._json_same_key_preview is not None and self._json_same_key_preview[0] == key
                        self._json_same_key_preview = (key, preview_b64)
                        preview_state = "duplicate_same_frame" if had_prev else "late_same_frame"
                        if not had_prev:
                            self._m_late_preview += 1
                    elif self._json_same_key_preview is not None and self._json_same_key_preview[0] == key:
                        # 同一源帧的重复心跳保留该同一源帧的预览
                        preview_b64 = self._json_same_key_preview[1]
                        preview_state = "retained_same_frame"
                    else:
                        preview_state = "pending_for_frame"
                else:
                    # 新源帧：立即清除上一帧缓存的预览！
                    self._last_json_key = key
                    self._last_json_seq_stamp = (session_id, seq, stamp_ns)
                    self._frame_seq += 1
                    self._m_matched += 1
                    if preview_b64 is not None:
                        self._json_same_key_preview = (key, preview_b64)
                        preview_state = "present"
                    else:
                        self._json_same_key_preview = None
                        preview_state = "pending_for_frame"

                bg_obj = local_from_board.get("background") or {
                    "status": "background_not_declared",
                    "declaration": "board",
                }
                board_phys = board_overlay.get("human_physical_v1")
                rows = board_overlay.get("target_source_rows") or []

                state_obj = {
                    "schema_version": 1,
                    "kind": "target_state",
                    "mode": "live",
                    "stream_mode": "json_only",
                    "session_id": session_id,
                    "frame_index": seq,
                    "frame_count": 0,
                    "stamp_sec": stamp,
                    "relative_time_sec": round(stamp - self._base_stamp, 4),
                    "time_epoch": board_overlay.get("time_epoch", 0),
                    "source": {
                        "seq": key[1],
                        "stamp_secs": key[2],
                        "stamp_nsecs": key[3],
                        "frame_id": key[4],
                    },
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
                    "pairing": {
                        "status": "matched",
                        "reason": "matched",
                        "conn_gen": self._conn_gen,
                        "wire_sha256": local_from_board.get("wireSha256"),
                        "preview_state": preview_state,
                        "preview_error": prev_err,
                    },
                    "local_range": {
                        "version": 1,
                        "wireSha256": local_from_board.get("wireSha256"),
                        "heightMedianM": local_from_board.get("heightMedianM"),
                        "groundAlert": local_from_board.get("groundAlert"),
                        "measurement": local_from_board.get("measurement"),
                        "background": bg_obj,
                        "ground": ground_obj,
                        "fallEvidence": local_from_board.get("fallEvidence"),
                        "kinematics": local_from_board.get("kinematics"),
                        "demoFallCandidate": local_from_board.get("demoFallCandidate"),
                        "posture": local_from_board.get("posture"),
                        "skeleton": local_from_board.get("skeleton") or _empty_skeleton(),
                        "bbox": local_from_board.get("bbox"),
                        "preview": preview_b64,
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
                        "local_age_ms": max(0.0, (time.monotonic() - received_ts) * 1000.0),
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
        packets = self.ingest_cloud(raw, received_ts)
        return packets[-1] if packets else None

    def _process_local_runtime_sync(self, raw: bytes, received_ts: float) -> bytes | None:
        """显式声明空场前缀时的本地 RangeRuntime 路径（同帧本地解算，不存在跨帧状态叠加）。"""
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

            assert self._runtime is not None
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

            target_rows_arr = np.unique(np.asarray(rows, dtype=np.int32)) if rows else np.empty(0, dtype=np.int32)
            rec_added = (phys.get("recovery") or {}).get("added_rows") or []
            rec_rows_arr = np.unique(np.asarray(rec_added, dtype=np.int32)) if rec_added else np.empty(0, dtype=np.int32)
            other_raw: list[int] = []
            for tr in record.get("tracks") or []:
                if tr.get("track_id") != record["target_track_id"] and tr.get("observed") and tr.get("source_rows"):
                    other_raw.extend(tr["source_rows"])
            other_rows_arr = np.unique(np.asarray(other_raw, dtype=np.int32)) if other_raw else np.empty(0, dtype=np.int32)
            fg_rows_arr = np.empty(0, dtype=np.int32)
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
                "pairing": {"status": "matched", "reason": "local_runtime_same_frame", "is_provisional": False},
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
                    "local_age_ms": max(0.0, (time.monotonic() - received_ts) * 1000.0),
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
