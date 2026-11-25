"""摄像头模块：回放按接收时间 ±250 ms 就近对齐，实时模式对板端 :8081 MJPEG 做单连接扇出。

语义边界：摄像头画面仅用于浏览器展示与人工对照，绝不进入任何雷达识别/体态/跌倒算法链。
"""

from __future__ import annotations

import asyncio
from bisect import bisect_left
import json
import math
from pathlib import Path
import time
from typing import Any

import aiohttp

MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 4096
MAX_FRAME_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_DELTA_MS = 250.0


class ReplayCameraIndex:
    """只读访问会话目录中的 camera.mjpeg + camera_frames.jsonl。"""

    def __init__(self, session_dir: Path | str):
        self.session_dir = Path(session_dir)
        self.mjpeg_path = self.session_dir / "camera.mjpeg"
        self.index_path = self.session_dir / "camera_frames.jsonl"
        self.rows: list[dict[str, int]] = []
        self.times_ns: list[int] = []
        self.available: bool = False
        self.duration_sec: float = 0.0
        self.fps: float = 0.0
        self._file = None

        has_mjpeg = self.mjpeg_path.is_file()
        has_index = self.index_path.is_file()
        if not has_mjpeg and not has_index:
            return
        if has_mjpeg != has_index:
            raise ValueError("camera files incomplete: require both camera.mjpeg and camera_frames.jsonl")

        if self.index_path.stat().st_size > MAX_INDEX_BYTES:
            raise ValueError("camera_frames.jsonl exceeds size limit")

        blob_size = self.mjpeg_path.stat().st_size
        covered = 0
        try:
            with self.index_path.open("r", encoding="utf-8") as fp:
                for line_no, line in enumerate(fp, start=1):
                    if len(line) > MAX_LINE_BYTES:
                        raise ValueError(f"camera index line {line_no} exceeds limit")
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError(f"camera index line {line_no} must be a JSON object")
                    offset = row.get("offset")
                    length = row.get("length")
                    stamp_ns = row.get("recv_unix_ns")
                    if any(type(v) is not int for v in (offset, length, stamp_ns)):
                        raise ValueError(f"invalid camera index field types at line {line_no}")
                    if offset != covered or not (0 < length <= MAX_FRAME_BYTES) or offset + length > blob_size:
                        raise ValueError(f"camera index byte range invalid at line {line_no}")
                    if stamp_ns <= 0:
                        raise ValueError(f"camera index recv_unix_ns must be positive at line {line_no}")
                    if self.times_ns and stamp_ns <= self.times_ns[-1]:
                        raise ValueError(f"camera index recv_unix_ns must strictly increase at line {line_no}")
                    self.rows.append({"offset": offset, "length": length, "recv_unix_ns": stamp_ns})
                    self.times_ns.append(stamp_ns)
                    covered = offset + length

            if not self.rows:
                raise ValueError("camera_frames.jsonl contains no frame rows")

            self._file = self.mjpeg_path.open("rb")
            # 抽检首尾帧 JPEG SOI/EOI，快速捕获损坏视频文件
            for idx in sorted({0, len(self.rows) - 1}):
                self._read_validated_jpeg(idx)

            self.available = True
            self.duration_sec = (self.times_ns[-1] - self.times_ns[0]) / 1e9
            self.fps = ((len(self.rows) - 1) / self.duration_sec) if self.duration_sec > 0 else 1.0
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> "ReplayCameraIndex":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._file is not None:
            try:
                self._file.close()
            finally:
                self._file = None

    def _read_validated_jpeg(self, index: int) -> bytes:
        if self._file is None:
            raise ValueError("camera file is closed")
        row = self.rows[index]
        self._file.seek(row["offset"])
        data = self._file.read(row["length"])
        if len(data) != row["length"] or not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
            raise ValueError(f"camera frame #{index} has invalid JPEG SOI/EOI markers")
        return data

    def match_meta(
        self,
        bag_time_sec: float | None,
        max_delta_ms: float = DEFAULT_MAX_DELTA_MS,
    ) -> dict[str, Any]:
        """仅按时间戳查找最近相机帧元信息（不读 JPEG 字节）。"""
        if not self.available:
            return {
                "available": False,
                "state": "unavailable",
                "videoFrameIndex": None,
                "deltaMs": None,
                "alignment": "none",
                "note": "该会话未录制摄像头画面（100% 纯雷达）",
            }
        if bag_time_sec is None or not isinstance(bag_time_sec, (int, float)) or not math.isfinite(float(bag_time_sec)):
            return {
                "available": True,
                "state": "outside",
                "videoFrameIndex": None,
                "deltaMs": None,
                "alignment": "receipt_time_unverified",
                "reason": "雷达帧缺少有效的 bag_time_sec",
            }

        target_ns = round(float(bag_time_sec) * 1_000_000_000)
        at = bisect_left(self.times_ns, target_ns)
        choices = [i for i in (at - 1, at) if 0 <= i < len(self.times_ns)]
        index = min(choices, key=lambda i: (abs(self.times_ns[i] - target_ns), i))
        delta_ns = self.times_ns[index] - target_ns
        delta_ms = round(delta_ns / 1_000_000.0, 3)
        limit_ns = round(float(max_delta_ms) * 1_000_000)

        if abs(delta_ns) > limit_ns:
            return {
                "available": True,
                "state": "outside",
                "videoFrameIndex": index,
                "deltaMs": delta_ms,
                "alignment": "receipt_time_unverified",
                "reason": f"超出接收时间对齐窗口 ±{int(max_delta_ms)} ms",
            }

        return {
            "available": True,
            "state": "ready",
            "videoFrameIndex": index,
            "deltaMs": delta_ms,
            "alignment": "receipt_time_unverified",
            "note": f"接收时间对齐 ±{int(max_delta_ms)} ms，非硬件同步",
        }

    def match(
        self,
        bag_time_sec: float | None,
        max_delta_ms: float = DEFAULT_MAX_DELTA_MS,
    ) -> tuple[bytes | None, dict[str, Any]]:
        """匹配并返回 (jpeg_bytes_or_none, info_dict)。"""
        info = self.match_meta(bag_time_sec, max_delta_ms=max_delta_ms)
        if info["state"] != "ready":
            return None, info
        jpeg = self._read_validated_jpeg(info["videoFrameIndex"])
        return jpeg, info


def extract_jpegs_from_buffer(buf: bytes) -> tuple[list[bytes], bytes]:
    """从字节流缓冲中提取完整 SOI (ff d8 ff) 到 EOI (ff d9) JPEG 帧。"""
    frames: list[bytes] = []
    while True:
        start = buf.find(b"\xff\xd8\xff")
        if start < 0:
            buf = buf[-2:] if len(buf) >= 2 else buf
            break
        buf = buf[start:]
        end = buf.find(b"\xff\xd9", 3)
        if end < 0:
            break
        frames.append(buf[: end + 2])
        buf = buf[end + 2 :]
    if len(buf) > MAX_FRAME_BYTES:
        raise ValueError("MJPEG frame exceeds 32 MB limit")
    return frames, buf


class LiveCameraHub:
    """单上游连接扇出中心：板端 :8081 只保持最多一条 HTTP MJPEG 连接。"""

    def __init__(self, camera_url: str = "http://192.168.31.58:8081/stream"):
        self.camera_url = camera_url
        self._subscribers: set[asyncio.Queue[bytes]] = set()
        self._task: asyncio.Task[None] | None = None
        self._state = "idle"  # idle | connecting | streaming | offline | error
        self._error: str | None = None
        self._frames = 0
        self._last_frame_ts = 0.0
        self._fps = 0.0
        self._latest_jpeg: bytes | None = None
        self._closed = False
        self._lock = asyncio.Lock()

    def status(self) -> dict[str, Any]:
        return {
            "url": self.camera_url,
            "state": self._state,
            "error": self._error,
            "subscribers": len(self._subscribers),
            "frames": self._frames,
            "fps": round(self._fps, 2),
        }

    async def subscribe(self) -> asyncio.Queue[bytes]:
        q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1)
        async with self._lock:
            if self._closed:
                raise RuntimeError("LiveCameraHub is closed")
            self._subscribers.add(q)
            if self._latest_jpeg is not None and (time.monotonic() - self._last_frame_ts) < 2.0:
                q.put_nowait(self._latest_jpeg)
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._upstream_loop())
        return q

    async def unsubscribe(self, q: asyncio.Queue[bytes]) -> None:
        task_to_wait: asyncio.Task[None] | None = None
        async with self._lock:
            self._subscribers.discard(q)
            if not self._subscribers and self._task is not None and not self._task.done():
                self._task.cancel()
                task_to_wait = self._task
                self._task = None
                self._state = "idle"
                self._latest_jpeg = None
        if task_to_wait is not None:
            await asyncio.gather(task_to_wait, return_exceptions=True)

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            self._subscribers.clear()
            task = self._task
            self._task = None
            self._state = "idle"
            self._latest_jpeg = None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def _broadcast(self, jpeg: bytes) -> None:
        now = time.monotonic()
        if self._last_frame_ts > 0:
            dt = now - self._last_frame_ts
            if dt > 0:
                inst = 1.0 / dt
                self._fps = inst if self._fps <= 0 else (0.8 * self._fps + 0.2 * inst)
        self._last_frame_ts = now
        self._frames += 1
        self._latest_jpeg = jpeg
        self._state = "streaming"
        self._error = None
        for q in list(self._subscribers):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(jpeg)
            except asyncio.QueueFull:
                pass

    async def _upstream_loop(self) -> None:
        retry = 0
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=3.0, sock_read=10.0)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                while not self._closed and self._subscribers:
                    self._state = "connecting"
                    buf = b""
                    try:
                        async with session.get(self.camera_url) as resp:
                            if resp.status != 200:
                                raise OSError(f"HTTP {resp.status} from board camera")
                            retry = 0
                            async for chunk in resp.content.iter_chunked(65536):
                                if self._closed or not self._subscribers:
                                    return
                                buf += chunk
                                frames, buf = extract_jpegs_from_buffer(buf)
                                for jpg in frames:
                                    self._broadcast(jpg)
                        raise OSError("camera stream ended")
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        self._state = "offline"
                        self._error = f"板端相机不可达或中断: {exc}"
                        delay = min(2.0 * (2 ** retry), 10.0)
                        retry = min(retry + 1, 6)
                        await asyncio.sleep(delay)
        except asyncio.CancelledError:
            pass
