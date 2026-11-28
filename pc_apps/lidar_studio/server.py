"""雷达体态工作台（LiDAR Studio）单端口 aiohttp 服务。

默认监听 127.0.0.1:8960（避开 8765/8766/8081/8090/8899/8901/8902/8936/8952）：
- 静态页面：web/
- REST：/api/sessions、/api/sessions/{sid}/summary、/api/camera/{sid}/{frame}、/api/live/status、/api/live/camera
- WebSocket：/ws（控制指令 + LDSF v1 二进制帧推送 + 慢客户端丢旧帧不堆积）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
from pathlib import Path
import time
from typing import Any

from aiohttp import WSMsgType, web

from camera_hub import LiveCameraHub
from live_source import LiveSource, probe_board
from replay_source import (
    REPLAY_MODE_BOARD_CAUSAL,
    REPLAY_MODE_OFFLINE_RESEARCH,
    ReplayManager,
    ReplaySessionData,
    VALID_REPLAY_MODES,
    validate_sid,
)

WEB_ROOT = Path(__file__).resolve().parent / "web"

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/json", ".json")


class ClientSessionHandler:
    """单个 WebSocket 客户端的连接控制器：独立单槽推帧（慢客户端丢旧帧）与源时间回放时钟。"""

    def __init__(self, ws: web.WebSocketResponse, ctx: "StudioContext"):
        self.ws = ws
        self.ctx = ctx
        self.mode = "replay"  # replay | live
        self.replay_mode = REPLAY_MODE_OFFLINE_RESEARCH
        self.session: ReplaySessionData | None = None
        self.frame_index = 0
        self.playing = False
        self.rate = 1.0
        self.decimation = 2
        self.dropped_frames = 0
        self._closed = False

        self._text_queue: asyncio.Queue[str] = asyncio.Queue()
        self._pending_binary: bytes | None = None
        self._binary_event = asyncio.Event()
        self._play_task: asyncio.Task[None] | None = None
        self._send_task: asyncio.Task[None] | None = None
        self._open_task: asyncio.Task[None] | None = None
        self._open_gen = 0

    def start(self) -> None:
        self._send_task = asyncio.create_task(self._sender_loop())

    async def close(self) -> None:
        self._closed = True
        self.playing = False
        tasks = [t for t in (self._play_task, self._open_task, self._send_task) if t is not None]
        self._play_task = None
        self._open_task = None
        self._send_task = None
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def send_text(self, obj: dict[str, Any]) -> None:
        if self._closed or self.ws.closed:
            return
        self._text_queue.put_nowait(json.dumps(obj, ensure_ascii=False, allow_nan=False))
        self._binary_event.set()

    def push_binary_frame(self, packet: bytes, *, count_drop: bool = True) -> None:
        if self._closed or self.ws.closed:
            return
        if self._pending_binary is not None and count_drop:
            self.dropped_frames += 1
        self._pending_binary = packet
        self._binary_event.set()

    def emit_playback_state(self) -> None:
        self.send_text(
            {
                "type": "playback_state",
                "mode": self.mode,
                "replay_mode": self.replay_mode,
                "sid": self.session.sid if self.session else None,
                "playing": self.playing,
                "rate": self.rate,
                "frame": self.frame_index,
                "decimation": self.decimation,
                "dropped_frames": self.dropped_frames,
            }
        )

    async def _sender_loop(self) -> None:
        try:
            while not self._closed and not self.ws.closed:
                while not self._text_queue.empty():
                    txt = self._text_queue.get_nowait()
                    await self.ws.send_str(txt)

                pkt = self._pending_binary
                if pkt is not None:
                    self._pending_binary = None
                    await self.ws.send_bytes(pkt)
                    continue

                self._binary_event.clear()
                if not self._text_queue.empty() or self._pending_binary is not None:
                    continue
                await self._binary_event.wait()
        except (asyncio.CancelledError, ConnectionResetError, RuntimeError):
            pass

    async def _stop_play_task(self) -> None:
        self.playing = False
        task = self._play_task
        self._play_task = None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _send_replay_frame(self, idx: int, *, count_drop: bool = False) -> None:
        if self.session is None:
            return
        clamped = max(0, min(self.session.frame_count - 1, int(idx)))
        self.frame_index = clamped
        packet = await asyncio.to_thread(self.session.get_packed_frame, clamped, self.decimation)
        if not self._closed and self.mode == "replay":
            self.push_binary_frame(packet, count_drop=count_drop)

    async def _playback_loop(self, start_frame: int) -> None:
        try:
            if self.session is None or self.session.frame_count <= 0:
                return
            stamps = self.session.summary["stamp_secs"]
            n = len(stamps)
            idx = max(0, min(n - 1, start_frame))
            if idx >= n - 1:
                idx = 0
            self.frame_index = idx
            await self._send_replay_frame(idx, count_drop=True)
            wall_anchor = time.monotonic()
            stamp_anchor = stamps[idx]
            rate_anchor = self.rate

            while self.playing and not self._closed and self.mode == "replay":
                if rate_anchor != self.rate:
                    wall_anchor = time.monotonic()
                    stamp_anchor = stamps[self.frame_index]
                    rate_anchor = self.rate

                next_idx = self.frame_index + 1
                if next_idx >= n:
                    self.playing = False
                    self.emit_playback_state()
                    return

                target_wall_dt = max(0.0, (stamps[next_idx] - stamp_anchor) / max(0.05, rate_anchor))
                elapsed = time.monotonic() - wall_anchor
                sleep_s = target_wall_dt - elapsed
                if sleep_s > 0.002:
                    await asyncio.sleep(min(sleep_s, 0.25))
                    continue

                # 若源时间戳已继续向前，跳到与目标时刻对齐的最新真实帧（不堆积慢帧）
                cur_source_t = stamp_anchor + (time.monotonic() - wall_anchor) * rate_anchor
                chosen = next_idx
                while chosen + 1 < n and stamps[chosen + 1] <= cur_source_t:
                    chosen += 1
                await self._send_replay_frame(chosen, count_drop=True)
                if chosen >= n - 1:
                    self.playing = False
                    self.emit_playback_state()
                    return
        except asyncio.CancelledError:
            pass

    async def handle_command(self, cmd: dict[str, Any]) -> None:
        action = cmd.get("cmd")
        if action == "open":
            sid = str(cmd.get("sid") or "")
            initial_frame = int(cmd.get("frame") or 0)
            req_rm = str(cmd.get("replay_mode") or REPLAY_MODE_OFFLINE_RESEARCH)
            if req_rm not in VALID_REPLAY_MODES:
                raise ValueError(f"unsupported replay_mode: {req_rm!r}")
            self.replay_mode = req_rm
            if "decimation" in cmd:
                self.decimation = max(1, min(16, int(cmd["decimation"])))
            await self._stop_play_task()
            self.mode = "replay"
            await self.ctx.ensure_live_stopped_if_unused(self)
            self._open_gen += 1
            gen = self._open_gen
            if self._open_task is not None and not self._open_task.done():
                self._open_task.cancel()
                await asyncio.gather(self._open_task, return_exceptions=True)
            self._open_task = asyncio.create_task(self._open_session_job(sid, initial_frame, gen, req_rm))

        elif action == "play":
            if self.mode != "replay" or self.session is None:
                return
            if not self.playing:
                self.playing = True
                self._play_task = asyncio.create_task(self._playback_loop(self.frame_index))
                self.emit_playback_state()

        elif action == "pause":
            await self._stop_play_task()
            self.emit_playback_state()

        elif action == "seek":
            if self.mode != "replay" or self.session is None:
                return
            was_playing = self.playing
            await self._stop_play_task()
            target = max(0, min(self.session.frame_count - 1, int(cmd.get("frame") or 0)))
            await self._send_replay_frame(target, count_drop=False)
            if was_playing and target < self.session.frame_count - 1:
                self.playing = True
                self._play_task = asyncio.create_task(self._playback_loop(target))
            self.emit_playback_state()

        elif action == "step":
            if self.mode != "replay" or self.session is None:
                return
            await self._stop_play_task()
            delta = int(cmd.get("delta") or 1)
            target = max(0, min(self.session.frame_count - 1, self.frame_index + delta))
            await self._send_replay_frame(target, count_drop=False)
            self.emit_playback_state()

        elif action == "rate":
            rate = float(cmd.get("rate") or 1.0)
            if not (0.1 <= rate <= 8.0):
                raise ValueError("rate must be in [0.1, 8.0]")
            self.rate = rate
            self.emit_playback_state()

        elif action == "decimation":
            self.decimation = max(1, min(16, int(cmd.get("decimation") or 2)))
            if self.mode == "live":
                self.ctx.live_source.set_decimation(self.decimation)
            elif self.session is not None and not self.playing:
                await self._send_replay_frame(self.frame_index, count_drop=False)
            self.emit_playback_state()

        elif action == "mode":
            target_mode = cmd.get("mode")
            if target_mode not in ("replay", "live"):
                raise ValueError(f"unsupported mode: {target_mode!r}")
            await self._stop_play_task()
            self.mode = target_mode
            if target_mode == "live":
                self.ctx.live_source.set_decimation(self.decimation)
                req_stream = cmd.get("stream_mode")
                if req_stream in ("json_only", "cloud_and_json"):
                    await self.ctx.live_source.set_stream_mode(req_stream)
                status = await self.ctx.live_source.start()
                self.send_text({"type": "live_status", **status})
            else:
                await self.ctx.ensure_live_stopped_if_unused(self)
                if self.session is not None:
                    await self._send_replay_frame(self.frame_index, count_drop=False)
            self.emit_playback_state()

        elif action == "live_stream_mode":
            req_stream = str(cmd.get("stream_mode") or "")
            status = await self.ctx.live_source.set_stream_mode(req_stream)
            self.send_text({"type": "live_status", **status})

        elif action == "live_probe":
            probe = await probe_board(self.ctx.board_ws, self.ctx.board_camera, timeout=2.5, retries=1)
            self.send_text({"type": "live_status", **self.ctx.live_source.status(), **probe})

        else:
            self.send_text({"type": "error", "code": "unknown_cmd", "message": f"未知命令: {action}"})

    async def _open_session_job(self, sid: str, initial_frame: int, gen: int, replay_mode: str = REPLAY_MODE_OFFLINE_RESEARCH) -> None:
        loop = asyncio.get_running_loop()

        def on_progress(stage: str, current: int, total: int, message: str) -> None:
            if self._closed or gen != self._open_gen:
                return
            loop.call_soon_threadsafe(
                self.send_text,
                {
                    "type": "loading",
                    "sid": sid,
                    "replay_mode": replay_mode,
                    "stage": stage,
                    "current": current,
                    "total": total,
                    "message": message,
                },
            )

        try:
            session_obj = await asyncio.to_thread(
                self.ctx.replay_manager.open_session,
                sid,
                on_progress,
                replay_mode=replay_mode,
            )
            if self._closed or gen != self._open_gen:
                return
            self.session = session_obj
            self.frame_index = max(0, min(session_obj.frame_count - 1, initial_frame))
            self.send_text(
                {
                    "type": "session_ready",
                    "sid": sid,
                    "replay_mode": replay_mode,
                    "summary": session_obj.summary,
                }
            )
            await self._send_replay_frame(self.frame_index, count_drop=False)
            self.emit_playback_state()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if not self._closed and gen == self._open_gen:
                self.send_text({"type": "error", "code": "open_failed", "message": str(exc)})


class StudioContext:
    """共享后端上下文。"""

    def __init__(
        self,
        sessions_root: Path | None = None,
        cache_dir: Path | None = None,
        board_ws: str = "ws://192.168.31.58:8765",
        board_camera: str = "http://192.168.31.58:8081/stream",
        live_empty_prefix: int | None = None,
        live_stream_mode: str = "json_only",
    ):
        self.board_ws = board_ws
        self.board_camera = board_camera
        self.replay_manager = ReplayManager(sessions_root=sessions_root, cache_dir=cache_dir)
        self.camera_hub = LiveCameraHub(board_camera)
        self.clients: set[ClientSessionHandler] = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.live_source = LiveSource(
            ws_url=board_ws,
            camera_url=board_camera,
            empty_prefix_frames=live_empty_prefix,
            stream_mode=live_stream_mode,
            on_frame=self._on_live_frame,
            on_status=self._on_live_status,
        )

    def _on_live_frame(self, packet: bytes) -> None:
        for c in list(self.clients):
            if c.mode == "live":
                c.push_binary_frame(packet, count_drop=True)

    def _on_live_status(self, st: dict[str, Any]) -> None:
        for c in list(self.clients):
            if c.mode == "live":
                c.send_text({"type": "live_status", **st})

    async def ensure_live_stopped_if_unused(self, excluding: ClientSessionHandler | None = None) -> None:
        any_live = any(c is not excluding and c.mode == "live" for c in self.clients)
        if not any_live and self.live_source.status()["running"]:
            await self.live_source.stop()

    async def shutdown(self) -> None:
        for c in list(self.clients):
            await c.close()
        self.clients.clear()
        await self.live_source.stop()
        await self.camera_hub.close()
        self.replay_manager.close_all()


CTX_KEY = web.AppKey("ctx", "StudioContext")


def create_app(
    *,
    sessions_root: Path | None = None,
    cache_dir: Path | None = None,
    board_ws: str = "ws://192.168.31.58:8765",
    board_camera: str = "http://192.168.31.58:8081/stream",
    live_empty_prefix: int | None = None,
    live_stream_mode: str = "json_only",
    web_root: Path = WEB_ROOT,
) -> web.Application:
    ctx = StudioContext(
        sessions_root=sessions_root,
        cache_dir=cache_dir,
        board_ws=board_ws,
        board_camera=board_camera,
        live_empty_prefix=live_empty_prefix,
        live_stream_mode=live_stream_mode,
    )
    app = web.Application()
    app[CTX_KEY] = ctx
    web_resolved = web_root.resolve()

    async def on_startup(application: web.Application) -> None:
        ctx.loop = asyncio.get_running_loop()

    async def on_cleanup(application: web.Application) -> None:
        await ctx.shutdown()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    async def handle_index(request: web.Request) -> web.Response:
        index_p = web_resolved / "index.html"
        if not index_p.is_file():
            raise web.HTTPNotFound(text="index.html missing")
        return web.FileResponse(index_p)

    async def handle_static(request: web.Request) -> web.Response:
        rel = request.match_info.get("asset", "")
        if not rel or rel == "/":
            return await handle_index(request)
        target = (web_resolved / rel).resolve()
        if web_resolved not in target.parents or not target.is_file():
            raise web.HTTPNotFound(text="not found")
        return web.FileResponse(target)

    async def handle_sessions(request: web.Request) -> web.Response:
        rm = request.query.get("replay_mode", REPLAY_MODE_OFFLINE_RESEARCH)
        if rm not in VALID_REPLAY_MODES:
            rm = REPLAY_MODE_OFFLINE_RESEARCH
        sessions = await asyncio.to_thread(ctx.replay_manager.list_sessions, rm)
        return web.json_response({"sessions": sessions, "replay_mode": rm})

    async def handle_session_summary(request: web.Request) -> web.Response:
        sid = request.match_info["sid"]
        rm = request.query.get("replay_mode", REPLAY_MODE_OFFLINE_RESEARCH)
        if rm not in VALID_REPLAY_MODES:
            return web.json_response({"error": f"unsupported replay_mode: {rm}"}, status=400)
        try:
            validate_sid(sid, ctx.replay_manager.sessions_root)
            s = await asyncio.to_thread(ctx.replay_manager.open_session, sid, replay_mode=rm)
            return web.json_response(s.summary)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)

    async def handle_camera_frame(request: web.Request) -> web.Response:
        sid = request.match_info["sid"]
        try:
            frame_idx = int(request.match_info["frame"])
            validate_sid(sid, ctx.replay_manager.sessions_root)
            session_obj = await asyncio.to_thread(ctx.replay_manager.open_session, sid)
            if not (0 <= frame_idx < session_obj.frame_count):
                return web.json_response({"error": "frame index out of range"}, status=404)
            if not session_obj.camera.available:
                return web.json_response(
                    {"state": "unavailable", "reason": "no_camera_in_session"},
                    status=404,
                    headers={"X-Camera-State": "unavailable"},
                )
            bag_t = session_obj.meta["frames"][frame_idx].get("bag_time_sec")
            jpeg, info = await asyncio.to_thread(session_obj.camera.match, bag_t)
            headers = {
                "X-Camera-State": info["state"],
                "X-Camera-Alignment": str(info.get("alignment", "receipt_time_unverified")),
                "Cache-Control": "no-store",
            }
            if info.get("deltaMs") is not None:
                headers["X-Camera-Delta-Ms"] = str(info["deltaMs"])
            if info.get("videoFrameIndex") is not None:
                headers["X-Camera-Frame-Index"] = str(info["videoFrameIndex"])

            if jpeg is None:
                return web.Response(status=204, headers=headers)
            return web.Response(body=jpeg, content_type="image/jpeg", headers=headers)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)

    async def handle_live_status(request: web.Request) -> web.Response:
        probe = await probe_board(ctx.board_ws, ctx.board_camera, timeout=2.5, retries=1)
        return web.json_response(
            {
                **probe,
                "live": ctx.live_source.status(),
                "camera": ctx.camera_hub.status(),
            }
        )

    async def handle_live_camera(request: web.Request) -> web.StreamResponse:
        probe = await probe_board(ctx.board_ws, ctx.board_camera, timeout=2.5, retries=1)
        if not probe["camera_reachable"]:
            return web.json_response(
                {"error": "板端相机不可达", **probe},
                status=503,
            )

        q = await ctx.camera_hub.subscribe()
        resp = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "multipart/x-mixed-replace; boundary=frame",
                "Cache-Control": "no-store",
            },
        )
        await resp.prepare(request)
        try:
            while True:
                try:
                    jpeg = await asyncio.wait_for(q.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    if ctx.camera_hub.status()["state"] == "offline":
                        break
                    continue
                part = (
                    b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(jpeg)).encode("ascii")
                    + b"\r\n\r\n"
                    + jpeg
                    + b"\r\n"
                )
                await resp.write(part)
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            await ctx.camera_hub.unsubscribe(q)
        return resp

    async def handle_ws(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(max_msg_size=16 * 1024 * 1024)
        await ws.prepare(request)
        handler = ClientSessionHandler(ws, ctx)
        ctx.clients.add(handler)
        handler.start()
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        cmd = json.loads(msg.data)
                        await handler.handle_command(cmd)
                    except Exception as exc:
                        handler.send_text({"type": "error", "code": "bad_request", "message": str(exc)})
                elif msg.type == WSMsgType.ERROR:
                    break
        finally:
            ctx.clients.discard(handler)
            await handler.close()
            await ctx.ensure_live_stopped_if_unused()
        return ws

    app.router.add_get("/", handle_index)
    app.router.add_get("/api/sessions", handle_sessions)
    app.router.add_get("/api/sessions/{sid}/summary", handle_session_summary)
    app.router.add_get("/api/camera/{sid}/{frame}", handle_camera_frame)
    app.router.add_get("/api/live/status", handle_live_status)
    app.router.add_get("/api/live/camera", handle_live_camera)
    app.router.add_get("/ws", handle_ws)
    app.router.add_get("/{asset:.*}", handle_static)
    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="LiDAR Studio Web Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8960)
    parser.add_argument("--sessions-root", type=Path, default=None)
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--board-ws", default="ws://192.168.31.58:8765")
    parser.add_argument("--board-camera", default="http://192.168.31.58:8081/stream")
    parser.add_argument("--live-empty-prefix", type=int, default=None)
    parser.add_argument("--live-stream-mode", choices=("json_only", "cloud_and_json"), default="json_only")
    args = parser.parse_args(argv)

    app = create_app(
        sessions_root=args.sessions_root,
        cache_dir=args.cache_dir,
        board_ws=args.board_ws,
        board_camera=args.board_camera,
        live_empty_prefix=args.live_empty_prefix,
        live_stream_mode=args.live_stream_mode,
    )
    print(f"LiDAR Studio serving at http://{args.host}:{args.port}/", flush=True)
    web.run_app(app, host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
