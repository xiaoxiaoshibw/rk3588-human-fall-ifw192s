#!/usr/bin/env python3
"""capture_server —— 板端采集控制 REST 服务（HC-01）。

只起控制面：健康、状态、会话 CRUD 与状态机迁移。
不起 rosbag（HC-02）、不做 bag→bin 抽取（HC-03）、不做网页（HC-04）。
纯 stdlib，无第三方依赖；可在无外网板容器直接跑。

启动：python3 capture_server.py [--config /path/capture.yaml]
"""

import argparse
import json
import os
import shutil
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from core.session_store import (SERVICE_VERSION, SessionStore, StoreError,
                                validate_session_id)
from core.recorder import Recorder, RecordError
from core.fifo import FifoCleaner, remove_session_artifacts
from core.bag2session import extract, ExtractError

DEFAULT_CONFIG = {
    "port": 8766,
    "bind": "0.0.0.0",
    "staging_dir": "/root/catkin_ws/captures_remote",
    "sessions_db": "/root/catkin_ws/captures_remote/sessions.json",
    "fifo_keep": 10,
    "fifo_interval_sec": 30,
    "disk_floor_mb": 5120,
    # 网页直下文件的速度上限（Kbit/s），与 fetch.py 的 scp -l 同口径：
    # 100M 链路留 30% 给实时预览；0 = 不限速
    "download_limit_kbit": 70000,
    "record_topics": ["/innolidar_points", "/inno_imu", "/device_status"],
    # HC-02
    "record_script": "/root/catkin_ws/src/human_fall_detection/scripts/record_session.py",
    "record_config": None,
    "max_duration_sec": 300,
    "sigint_grace_sec": 15,
    "sigterm_kill_sec": 5,
}

# 仅接受这些可 PATCH 的附加字段，防止调用方往会话里塞任意键污染登记表
PATCHABLE_EXTRA = {"error", "download_requested", "transferred", "frame_count",
                   "duration_sec", "size_bytes", "bag_path", "meta_json_path",
                   "points_bin_path", "source_bag_sha256"}


def _load_config(path):
    cfg = dict(DEFAULT_CONFIG)
    if not path:
        return cfg
    # yaml 解析保持最小依赖：本配置是扁平 key: value，手解析即可
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].rstrip()
            if ":" not in line or line.startswith((" ", "\t", "-")):
                continue
            key, val = line.split(":", 1)
            key, val = key.strip(), val.strip()
            if not val:
                continue
            # YAML null must stay None. Treating "null"/"~" as a string made
            # record_config truthy and appended a literal `--config null`, which
            # made every recording fail at spawn.
            if val.lower() in ("null", "~", "none"):
                cfg[key] = None
                continue
            if val.startswith("["):
                try:
                    cfg[key] = json.loads(val.replace("'", '"'))
                    continue
                except ValueError:
                    pass
            try:
                cfg[key] = int(val)
            except ValueError:
                try:
                    cfg[key] = float(val)
                except ValueError:
                    cfg[key] = val.strip('"').strip("'")
    return cfg


class _Handler(BaseHTTPRequestHandler):
    server_version = "human_capture/" + SERVICE_VERSION
    protocol_version = "HTTP/1.1"

    # ---------- 工具 ----------

    def _send_json(self, code, payload):
        body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")  # 板端网页跨端口访问
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_error_json(self, code, err_code, message):
        self._send_json(code, {"error": {"code": err_code, "message": message}})

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 1 << 20:  # 控制面不会出现大 body
            return None, "Content-Length 非法或过大"
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8")), None
        except ValueError as exc:
            return None, "body 不是合法 JSON: %s" % exc

    def log_message(self, fmt, *args):  # 降噪：交给外层日志
        sys.stderr.write("[capture_server] %s %s\n" % (self.address_string(), fmt % args))

    # ---------- 会话文件直下 ----------

    def _serve_session_file(self, sid, name):
        if not validate_session_id(sid):
            self._send_error_json(404 if sid in ('.', '..') else 400, 'bad_id', 'session_id 非法')
            return
        session = self.server.store.get(sid)
        if session is not None and (session.get('cleanup_pending') or session['state']
                                   not in ('ready', 'transferred', 'transferring')):
            self._send_error_json(409, 'busy', '会话不可下载')
            return
        with self.server.store.session_guard(sid):
            session = self.server.store.get(sid)
            if session is not None and (session.get('cleanup_pending') or session['state']
                                       not in ('ready', 'transferred', 'transferring')):
                self._send_error_json(409, 'busy', '会话不可下载')
                return
            self._serve_session_file_locked(sid, name)

    def _serve_session_file_locked(self, sid, name):
        """GET/HEAD /api/v1/sessions/<sid>/files/<name>：meta.json / points.bin 本体。

        给没配 SSH key 的普通 PC 一条免配置回传路（浏览器直接另存，再放进
        Console 的 captures/remote/<sid>/），与 fetch.py 的 scp 通道并存。
        路径由 staging_dir 现拼、不走登记表字段；限速保护实时预览。
        """
        if not validate_session_id(sid):
            self._send_error_json(400, "bad_id", "session_id 非法")
            return
        if name not in ("meta.json", "points.bin"):
            self._send_error_json(400, "bad_name", "只允许下载 meta.json / points.bin")
            return
        staging = os.path.realpath(self.server.cfg["staging_dir"])
        path = os.path.realpath(os.path.join(staging, sid, name))
        if not path.startswith(staging + os.sep) or not os.path.isfile(path):
            self._send_error_json(404, "file_missing", "会话文件不存在: %s/%s" % (sid, name))
            return
        size = os.path.getsize(path)
        self.send_response(200)
        self.send_header("Content-Type",
                         "application/json; charset=utf-8" if name == "meta.json"
                         else "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", 'attachment; filename="%s"' % name)
        self.send_header("Access-Control-Allow-Origin", "*")  # 板端 8090 页跨端口引用
        self.end_headers()
        if self.command == "HEAD":
            return
        limit = int(self.server.cfg.get("download_limit_kbit") or 0)
        rate = limit * 1000.0 / 8.0  # Kbit/s → 字节/s；0 = 不限速
        t0 = time.monotonic()
        sent = 0
        try:
            with open(path, "rb") as fh:
                while True:
                    chunk = fh.read(256 * 1024)
                    if not chunk:
                        break
                    if rate > 0:
                        # 本块预算：按已发+本块字节对齐到限速时间表（先等后发）
                        behind = (sent + len(chunk)) / rate - (time.monotonic() - t0)
                        if behind > 0:
                            time.sleep(behind)
                    self.wfile.write(chunk)
                    sent += len(chunk)
        except OSError:
            self.close_connection = True  # 客户端中断：本端无状态，可整份重下

    # ---------- 路由 ----------

    def _route(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        store = self.server.store

        if self.command == "GET" and parts == ["healthz"]:
            # Health must mean something: the old static body reported ok even
            # with a dead extractor or a recorder that never started.
            threads = {name: bool(thread and thread.is_alive())
                       for name, thread in (
                           ("extractor", self.server._extract_thread),
                           ("fifo", getattr(self.server.fifo, "_thread", None)),
                           ("recorder_watcher", getattr(self.server.recorder, "_watcher", None)))}
            live_session = self.server.recorder.current_session_id()
            self._send_json(200, {
                "ok": True,
                "service": "human_capture",
                "version": SERVICE_VERSION,
                "pid": os.getpid(),
                "release_id": self.server.release_id,
                "started_wall": self.server.started_wall,
                "uptime_sec": round(time.monotonic() - self.server.t0, 3),
                "recording": live_session is not None,
                "recording_session": live_session,
                "threads": threads,
                "record_script": self.server.cfg.get("record_script"),
                "record_script_present": self.server.record_script_present,
                "sessions_db": self.server.cfg.get("sessions_db"),
            })
            return

        if self.command == "GET" and parts == ["api", "v1", "status"]:
            usage = shutil.disk_usage(self.server.cfg["staging_parent"])
            counts = store.summary_counts()
            rows = store.list_sessions()
            states = {}
            for row in rows:
                states[row["state"]] = states.get(row["state"], 0) + 1
            live_session = self.server.recorder.current_session_id()
            self._send_json(200, {
                "ros": self.server.ros_probe(),  # HC-02 接真实探测；先恒 "unknown"
                "disk_free_mb": usage.free // (1024 * 1024),
                "sessions_total": counts["sessions_total"],
                "recording": counts["recording"],
                "uptime_sec": round(time.monotonic() - self.server.t0, 3),
                "version": SERVICE_VERSION,
                "pid": os.getpid(),
                "release_id": self.server.release_id,
                "recording_session": live_session,
                # DB says recording but no live recorder owns it: a crash or an
                # abrupt kill left the registry behind. Surface it, never hide it.
                "inconsistent_recording": bool(counts["recording"] and live_session is None),
                "states": states,
                "record_script": self.server.cfg.get("record_script"),
                "record_script_present": self.server.record_script_present,
            })
            return

        if parts[:3] == ["api", "v1", "record"]:
            rec = self.server.recorder
            if len(parts) == 4 and parts[3] == "start" and self.command == "POST":
                from datetime import datetime
                sid = "cap_" + datetime.now().strftime("%Y%m%d_%H%M%S")
                try:
                    rec.start(sid)
                except RecordError as exc:
                    self._send_error_json(409, "conflict", str(exc))
                    return
                self._send_json(201, {"session_id": sid})
                return
            if len(parts) == 4 and parts[3] == "stop" and self.command == "POST":
                sid = rec.stop(reason="manual")
                if sid is None:
                    self._send_error_json(409, "conflict", "not_recording")
                    return
                self._send_json(200, {"session_id": sid, "stopping": True})
                return
            if len(parts) == 4 and parts[3] == "current" and self.command == "GET":
                sid = rec.current_session_id()
                if sid is None:
                    self.send_response(204)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                s = store.get(sid) or {}
                import time as _time
                self._send_json(200, {
                    "session_id": sid,
                    "state": s.get("state"),
                    "created_iso": s.get("created_iso"),
                })
                return
            self._send_error_json(404, "no_route",
                                  "%s /api/v1/record/%s"
                                  % (self.command, "/".join(parts[3:])))
            return

        if parts[:2] == ["api", "v1"] and len(parts) >= 3 and parts[2] == "sessions":
            sid = parts[3] if len(parts) >= 4 else None
            if len(parts) == 3:
                if self.command == "GET":
                    self._send_json(200, {"sessions": store.list_sessions()})
                    return
                if self.command == "POST":
                    body, err = self._read_body()
                    if err:
                        self._send_error_json(400, "bad_body", err)
                        return
                    if isinstance(body, dict) and (body.get('state') == 'purged' or
                            any(k in body for k in ('cleanup_pending', 'cleanup_error', 'purged_reason'))):
                        self._send_error_json(409, 'cleanup_required', '清理状态及字段只能由安全清理路径登记')
                        return
                    try:
                        store.upsert(body, create_only=True)
                    except ValueError as exc:
                        self._send_error_json(409 if str(exc) == 'session_already_exists' else 400,
                                              'bad_meta', str(exc))
                        return
                    self._send_json(201, {"session_id": body["session_id"]})
                    return
            if sid is not None and len(parts) == 4:
                if not validate_session_id(sid):
                    self._send_error_json(400, "bad_id", "session_id 非法")
                    return
                if self.command == "GET":
                    s = store.get(sid)
                    if s is None:
                        self._send_error_json(404, "not_found", "会话不存在")
                        return
                    self._send_json(200, s)
                    return
                if self.command == "PATCH":
                    body, err = self._read_body()
                    if err:
                        self._send_error_json(400, "bad_body", err)
                        return
                    new_state = body.get("state")
                    if new_state == 'purged':
                        self._send_error_json(409, 'cleanup_required', 'purged 只能由安全清理路径登记')
                        return
                    extra = {k: v for k, v in (body.get("extra") or {}).items()
                             if k in PATCHABLE_EXTRA}
                    if not new_state and not extra:
                        self._send_error_json(400, "bad_body", "PATCH 需带 state 或 extra")
                        return
                    if new_state:
                        ok, reason = store.transition(sid, new_state, extra)
                        if not ok:
                            code = 404 if reason == "会话不存在" else 409
                            self._send_error_json(code, "bad_transition", reason)
                            return
                    else:
                        # 仅更新 extra 字段，不动状态机
                        with store.session_guard(sid):
                            s = store.get(sid)
                            if s is None:
                                self._send_error_json(404, 'not_found', '会话不存在')
                                return
                            s.update(extra)
                            try:
                                store.upsert(s)
                            except ValueError as exc:
                                self._send_error_json(409, 'busy', str(exc))
                                return
                    self._send_json(200, {"session_id": sid,
                                          "state": new_state or store.get(sid)["state"]})
                    return
                if self.command == "DELETE":
                    try:
                        ok, reason, removed = store.cleanup(sid,
                            lambda: remove_session_artifacts(self.server.cfg['staging_dir'], sid),
                            'delete', delete_record=True)
                    except (OSError, ValueError) as exc:
                        self._send_error_json(500, 'cleanup_failed', str(exc))
                        return
                    if not ok:
                        self._send_error_json(404 if reason == '会话不存在' else 409,
                                              'not_found' if reason == '会话不存在' else 'busy', reason)
                        return
                    self._send_json(200, {"deleted": sid, "removed": removed})
                    return

            # 网页直下文件本体（免 SSH 的普通 PC 回传路）：
            # /api/v1/sessions/<sid>/files/<meta.json|points.bin>
            if (sid is not None and len(parts) == 6 and parts[4] == "files"
                    and self.command in ("GET", "HEAD")):
                self._serve_session_file(sid, parts[5])
                return

        self._send_error_json(404, "no_route", "未匹配路由: %s %s" % (self.command, self.path))

    do_GET = _route
    do_POST = _route
    do_PATCH = _route
    do_DELETE = _route
    do_HEAD = _route

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, handler, cfg):
        self.cfg = cfg
        self.t0 = time.monotonic()
        self.started_wall = time.time()
        self.release_id = os.environ.get("HF_RELEASE_ID") or None
        os.makedirs(cfg["staging_dir"], exist_ok=True)
        self.store = SessionStore(cfg["sessions_db"])

        def _log(msg):
            sys.stderr.write("[capture_server] %s\n" % msg)

        self.recorder = Recorder(self.store, cfg, logger=_log)
        record_script = cfg.get("record_script")
        self.record_script_present = bool(record_script and os.path.isfile(record_script))
        if not self.record_script_present:
            # Do not hide it: recording will fail at spawn time and the operator
            # needs to see which path was expected.
            _log("WARNING: record_script missing: %r" % record_script)
        self.fifo = FifoCleaner(self.store, cfg, logger=_log)
        self.fifo.start()
        # HC-03 抽取守护：扫 extracting 状态，跑 bag→meta+bin，置 ready/failed
        self._stop_extract = threading.Event()
        self._extract_thread = threading.Thread(
            target=self._extract_loop, args=(_log,), daemon=True, name="extractor")
        self._extract_thread.start()
        super().__init__(addr, handler)

    def _extract_loop(self, log):
        """单线程扫 extracting，一个个抽。抢失败让下一个 tick 重试。"""
        while not self._stop_extract.wait(2.0):
            try:
                sessions = [s for s in self.store.list_sessions()
                            if s["state"] == "extracting"]
                for s in sessions:
                    if self._stop_extract.is_set():
                        break
                    with self.store.session_guard(s['session_id']):
                        # The scan is advisory; recheck after acquiring execution.
                        current = self.store.get(s['session_id'])
                        if current is not None and current['state'] == 'extracting' and not current.get('cleanup_pending'):
                            self._extract_one(current, log)
            except Exception as exc:  # noqa: BLE001
                log('抽取循环异常: %r' % exc)

    def _extract_one(self, s, log):
        sid = s['session_id']
        bag_path = s.get("bag_path")
        if not bag_path or not os.path.exists(bag_path):
            self.store.transition(sid, "failed", {"error": "bag_missing"})
            return
        # 守护线程是单线程执行者，无抢占；extracting 状态保留到最后
        # 一次性迁移到 ready 或 failed。
        session_dir = os.path.join(self.cfg["staging_dir"], sid)
        try:
            meta = extract(bag_path, session_dir, sid)
        except ExtractError as exc:
            self.store.transition(sid, "failed",
                                  {"error": "extract: %s" % exc})
            log("抽取失败 %s: %s" % (sid, exc))
            return
        except Exception as exc:  # noqa: BLE001
            self.store.transition(sid, "failed",
                                  {"error": "extract_crash: %r" % exc})
            log("抽取崩溃 %s: %r" % (sid, exc))
            return
        info = meta.get("_computed") or {}
        self.store.transition(
            sid, "ready",
            {"meta_json_path": os.path.join(session_dir, "meta.json"),
             "points_bin_path": os.path.join(session_dir, "points.bin"),
             "frame_count": len(meta.get("frames", [])),
             "duration_sec": meta.get("duration_sec"),
             "size_bytes": info.get("points_bin_size_bytes")})
        log("抽取完成 %s: %d 帧, %d 点"
            % (sid, len(meta.get("frames", [])), meta.get("total_points", 0)))

    def server_close(self):
        # Signal first; every cleanup runs even if a previous one failed.
        self._stop_extract.set()
        self.fifo._stop_event.set()
        errors = []
        def stop_extract():
            self._extract_thread.join(timeout=3)
            if self._extract_thread.is_alive():
                raise RuntimeError('extractor_shutdown_timeout')
        for name, cleanup in (('recorder', self.recorder.close), ('extractor', stop_extract),
                              ('fifo', self.fifo.stop), ('http', super().server_close)):
            try:
                cleanup()
            except Exception as exc:
                errors.append((name, exc))
        self.close_errors = [(name, repr(exc)) for name, exc in errors]
        self.shutdown_state = dict(
            recorder_watcher_alive=bool(self.recorder._watcher and self.recorder._watcher.is_alive()),
            recording_session_id=self.recorder.current_session_id(),
            extractor_alive=self._extract_thread.is_alive(),
            fifo_alive=self.fifo._thread.is_alive(), socket_closed=self.socket.fileno() == -1)
        # Persist the honest stop result: a caller (deploy script, operator) must
        # be able to see that a thread survived instead of assuming a clean exit.
        sys.stderr.write("[capture_server] shutdown_state %s\n"
                         % json.dumps(dict(self.shutdown_state, close_errors=self.close_errors),
                                      sort_keys=True))
        sys.stderr.flush()
        if errors:
            raise errors[0][1]

    def ros_probe(self):
        # HC-02 真实探测：调用 `rosnode list`（CLI 一定存在，python rosgraph 可能没有）。
        # 2s 超时，任一失败一律 down，不阻塞 HTTP。
        import subprocess
        try:
            rc = subprocess.run(["rosnode", "list"],
                                capture_output=True, timeout=2).returncode
            return "up" if rc == 0 else "down"
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return "down"
        except Exception:
            return "unknown"


def main(argv=None):
    ap = argparse.ArgumentParser(description="human_capture 控制面 REST 服务")
    ap.add_argument("--config", default=None)
    ap.add_argument("--port", type=int, default=None)
    args = ap.parse_args(argv)

    cfg = _load_config(args.config)
    if args.port:
        cfg["port"] = args.port
    cfg["staging_parent"] = os.path.dirname(cfg["staging_dir"]) or "/"

    try:
        server = _Server((cfg["bind"], cfg["port"]), _Handler, cfg)
    except StoreError as exc:
        sys.stderr.write("启动失败: %s\n" % exc)
        return 2

    # SIGTERM/SIGHUP must take the same path as Ctrl-C. The default disposition
    # killed the process before server_close(), leaving a rosbag child (started
    # with start_new_session) and a registry row stuck in `recording`. Raising
    # here unwinds serve_forever into the existing `finally: server_close()`;
    # calling shutdown() from the handler would deadlock (it waits for the very
    # loop that is running in this thread).
    class _ShutdownRequested(Exception):
        pass

    def _request_shutdown(signum, _frame):
        raise _ShutdownRequested(signum)

    for _sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
        try:
            signal.signal(_sig, _request_shutdown)
        except (ValueError, OSError):  # pragma: no cover - non-main thread
            pass

    print("[capture_server] listening on %s:%d, db=%s, release=%s, record_script=%s"
          % (cfg["bind"], cfg["port"], cfg["sessions_db"], server.release_id,
             server.record_script_present), flush=True)
    exit_code = 0
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except _ShutdownRequested as exc:
        sys.stderr.write("[capture_server] shutdown requested by signal %s\n" % exc.args)
    finally:
        try:
            server.server_close()
        except Exception as exc:  # noqa: BLE001 - report, do not mask
            sys.stderr.write("[capture_server] server_close failed: %r\n" % exc)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
