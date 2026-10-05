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
from core.fifo import FifoCleaner
from core.bag2session import extract, ExtractError

DEFAULT_CONFIG = {
    "port": 8766,
    "bind": "0.0.0.0",
    "staging_dir": "/root/catkin_ws/captures_remote",
    "sessions_db": "/root/catkin_ws/captures_remote/sessions.json",
    "fifo_keep": 10,
    "fifo_interval_sec": 30,
    "disk_floor_mb": 5120,
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

    # ---------- 路由 ----------

    def _route(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        store = self.server.store

        if self.command == "GET" and parts == ["healthz"]:
            self._send_json(200, {"ok": True, "service": "human_capture",
                                  "version": SERVICE_VERSION})
            return

        if self.command == "GET" and parts == ["api", "v1", "status"]:
            usage = shutil.disk_usage(self.server.cfg["staging_parent"])
            counts = store.summary_counts()
            self._send_json(200, {
                "ros": self.server.ros_probe(),  # HC-02 接真实探测；先恒 "unknown"
                "disk_free_mb": usage.free // (1024 * 1024),
                "sessions_total": counts["sessions_total"],
                "recording": counts["recording"],
                "uptime_sec": round(time.monotonic() - self.server.t0, 3),
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
            sid = parts[3] if len(parts) == 4 else None
            if len(parts) == 3:
                if self.command == "GET":
                    self._send_json(200, {"sessions": store.list_sessions()})
                    return
                if self.command == "POST":
                    body, err = self._read_body()
                    if err:
                        self._send_error_json(400, "bad_body", err)
                        return
                    try:
                        store.upsert(body)
                    except ValueError as exc:
                        self._send_error_json(400, "bad_meta", str(exc))
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
                        s = store.get(sid)
                        if s is None:
                            self._send_error_json(404, "not_found", "会话不存在")
                            return
                        s.update(extra)
                        store.upsert(s)
                    self._send_json(200, {"session_id": sid,
                                          "state": new_state or store.get(sid)["state"]})
                    return
                if self.command == "DELETE":
                    s = store.get(sid)
                    if s is None:
                        self._send_error_json(404, "not_found", "会话不存在")
                        return
                    if s["state"] in ("recording", "transferring"):
                        self._send_error_json(409, "busy",
                                              "录制/传输中，不可删（%s）" % s["state"])
                        return
                    # 连文件一起删（限 staging_dir 内），仅剩登记会让文件成孤儿
                    staging = os.path.realpath(self.server.cfg["staging_dir"])
                    removed = []
                    for key in ("bag_path", "manifest_path",
                                "meta_json_path", "points_bin_path"):
                        p = s.get(key)
                        if not p:
                            continue
                        rp = os.path.realpath(p)
                        if not (rp == staging or rp.startswith(staging + os.sep)):
                            continue  # 路径在 staging 外，不动
                        try:
                            if os.path.isdir(rp):
                                os.rmdir(rp)  # 只对空目录兜底，正常走下方显式删
                            else:
                                os.remove(rp)
                            removed.append(os.path.basename(rp))
                        except FileNotFoundError:
                            pass
                        except OSError:
                            pass
                    # 会话产物目录（含 meta+bin 的 <sid>/）：
                    sdir = os.path.join(staging, sid)
                    if os.path.isdir(os.path.realpath(sdir)):
                        try:
                            for f in os.listdir(sdir):
                                os.remove(os.path.join(sdir, f))
                            os.rmdir(sdir)
                            removed.append(sid + "/")
                        except OSError:
                            pass
                    # recorder 的容量预留占位（命名为 <sid>.reserve，注册表里无字段）
                    rp = os.path.join(staging, sid + ".reserve")
                    if os.path.isfile(os.path.realpath(rp)):
                        try:
                            os.remove(rp)
                            removed.append(sid + ".reserve")
                        except OSError:
                            pass
                    store.delete(sid)
                    self._send_json(200, {"deleted": sid, "removed": removed})
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
        os.makedirs(cfg["staging_dir"], exist_ok=True)
        self.store = SessionStore(cfg["sessions_db"])

        def _log(msg):
            sys.stderr.write("[capture_server] %s\n" % msg)

        self.recorder = Recorder(self.store, cfg, logger=_log)
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
                    sid = s["session_id"]
                    bag_path = s.get("bag_path")
                    if not bag_path or not os.path.exists(bag_path):
                        self.store.transition(sid, "failed", {"error": "bag_missing"})
                        continue
                    # 守护线程是单线程执行者，无抢占；extracting 状态保留到最后
                    # 一次性迁移到 ready 或 failed。
                    session_dir = os.path.join(self.cfg["staging_dir"], sid)
                    try:
                        meta = extract(bag_path, session_dir, sid)
                    except ExtractError as exc:
                        self.store.transition(sid, "failed",
                                              {"error": "extract: %s" % exc})
                        log("抽取失败 %s: %s" % (sid, exc))
                        continue
                    except Exception as exc:  # noqa: BLE001
                        self.store.transition(sid, "failed",
                                              {"error": "extract_crash: %r" % exc})
                        log("抽取崩溃 %s: %r" % (sid, exc))
                        continue
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
            except Exception as exc:  # noqa: BLE001
                log("抽取循环异常: %r" % exc)

    def server_close(self):
        self._stop_extract.set()
        if self._extract_thread:
            self._extract_thread.join(timeout=3)
        self.fifo.stop()
        super().server_close()

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

    print("[capture_server] listening on %s:%d, db=%s"
          % (cfg["bind"], cfg["port"], cfg["sessions_db"]))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
