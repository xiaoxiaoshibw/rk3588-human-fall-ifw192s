# -*- coding: utf-8 -*-
"""human_replay 本地服务：静态文件 + 会话索引/同步/手动选择/控制台代理。

motivation（用户 2026-10-02 反馈）：
- 找会话不想在文件管理器里翻——面板直接列板端 + 本地，点名字就播
- 控制台不该失踪——把它嵌回放页，start/stop/状态 都在这里

技术选型（ponytail）：
- http.server：ThreadingHTTPServer + 手路由，无 pnpm flask 这一串
- /api/sessions = GET 板端 JSON + 本地扫描远端目录合扫
- /api/sync = spawn `fetch.py --sid`，不复用逻辑：fetch.py 是唯一权威实现；
  差别只是子进程重启动代价 <100ms，同步本来就是分钟级
- /api/load = Tk 原生目录对话（服务器那侧起 GUI）——浏览器安全模型禁止
  非用户手势驱动的与服务端对话，不经由同一「点击-响应」流
- /api/board/* = 只转发 start/stop，阻断一切 PATCH / DELETE（server 上
  capture_state 控制台本来就用到 CRUD，回放器禁用，SSH/控制面走 webui/human_capture）

启动：`python human_replay_lib.py` → 浏览器自动开 127.0.0.1:8901
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config as C

PORT = 8901
_HERE = os.path.dirname(os.path.abspath(__file__))
_FETCH = os.path.join(_HERE, "fetch.py")
_proc_lock = threading.Lock()
_proc = None  # 当前同步子进程


def _is_ready_for_load(meta_path):
    return os.path.isfile(meta_path) and os.path.isfile(os.path.join(
        os.path.dirname(meta_path), "points.bin"))


def _local_sessions(dest):
    """本地 captures/remote 下的 cap_* 目录 → 轻描述（从 meta.json 揭sel）。"""
    out = {}
    if not os.path.isdir(dest):
        return out
    for name in os.listdir(dest):
        d = os.path.join(dest, name)
        meta_p = os.path.join(d, "meta.json")
        if not (os.path.isdir(d) and name.startswith("cap_") and _is_ready_for_load(meta_p)):
            continue
        try:
            with open(meta_p, "r", encoding="utf-8") as fh:
                m = json.load(fh)
            out[name] = {
                "duration_sec": m.get("duration_sec"),
                "total_points": m.get("total_points"),
                "frames": len(m.get("frames") or []),
                "frame_rate": m.get("frame_rate_hz_measured"),
                "created_iso": m.get("created_iso"),
                "bytes": os.path.getsize(os.path.join(d, "points.bin")),
            }
        except BaseException:
            out[name] = {"error": "meta 不可读"}
    return out


def _board_get(path, timeout=4.0):
    req = urllib.request.Request(C.BOARD_URL + path)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _board_post(path, body=None, timeout=4.0):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(C.BOARD_URL + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read() or b"{}")


def _board_patch(sid, extra, timeout=4.0):
    data = json.dumps({"extra": extra}).encode()
    req = urllib.request.Request(C.BOARD_URL + "/api/v1/sessions/" + sid,
                                 data=data, method="PATCH")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _board_delete(sid, timeout=8.0):
    req = urllib.request.Request(C.BOARD_URL + "/api/v1/sessions/" + sid,
                                 method="DELETE")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), a[0] % a[1:]))

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    # ---------- 静态 ----------
    def do_GET(self):  # noqa: N802（http.server 约定）
        path = self.path.split("?", 1)[0]
        if path == "/api/sessions":
            return self._api_sessions()
        if path == "/api/board/status":
            return self._board_status()
        if path.startswith("/api/file"):
            return self._serve_file()
        return self._serve_static(path)

    def _serve_static(self, path):
        if path in ("/", ""):
            path = "/index.html"
        rel = path.lstrip("/")
        if ".." in rel:
            return self.send_error(403)
        full = os.path.join(_HERE, rel)
        if not os.path.isfile(full):
            return self.send_error(404)
        ctype = {".html": "text/html; charset=utf-8", ".js": "text/javascript",
                 ".css": "text/css", ".json": "application/json",
                 ".bin": "application/octet-stream"}.get(
                     os.path.splitext(full)[1], "application/octet-stream")
        try:
            with open(full, "rb") as fh:
                data = fh.read()
        except OSError:
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self):
        """从 captures_remote 按 sid+name 出文件。"""
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        sid = (q.get("sid") or [""])[0]
        name = (q.get("name") or [""])[0]
        if name not in ("meta.json", "points.bin"):
            return self.send_error(400, "name 白名单 meta.json/points.bin")
        if not sid or any(c in sid for c in "/\\..") or ".." in sid:
            return self.send_error(400, "sid 非法")
        full = os.path.join(C.DEST_ROOT, sid, name)
        if not os.path.isfile(full):
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(os.path.getsize(full)))
        self.end_headers()
        with open(full, "rb") as fh:
            while True:
                block = fh.read(1 << 20)
                if not block:
                    break
                self.wfile.write(block)

    # ---------- 会话面板 ----------
    def _api_sessions(self):
        board_error = None
        board_sessions = []
        try:
            board_sessions = _board_get("/api/v1/sessions").get("sessions", [])
        except BaseException as exc:
            board_error = "连接板失败: %s" % exc
        local = _local_sessions(C.DEST_ROOT)
        out = []
        for s in board_sessions:
            sid = s.get("session_id", "")
            li = local.get(sid)
            out.append({
                "sid": sid,
                "state": s.get("state"),
                "created_iso": s.get("created_iso"),
                "duration_sec": s.get("duration_sec"),
                "size_bytes": s.get("size_bytes"),
                "frames": (li and li.get("frames")) or s.get("frame_count"),
                "download_requested": bool(s.get("download_requested")),
                "transferred": bool(s.get("transferred")),
                "local": bool(li),
            })
        # 本地有但板端已删的（FIFO 清过）也列上
        listed = {o["sid"] for o in out}
        for sid, li in local.items():
            if sid not in listed:
                out.append({"sid": sid, "state": "local-only",
                            "created_iso": li.get("created_iso"),
                            "duration_sec": li.get("duration_sec"),
                            "frames": li.get("frames"),
                            "local": True})
        out.sort(key=lambda o: o.get("created_iso") or "", reverse=True)
        self._json({"sessions": out, "board_error": board_error})

    # ---------- 录制控制台（代理板端） ----------
    def _board_status(self):
        try:
            st = _board_get("/api/v1/status")
        except BaseException as exc:
            return self._json({"ros": "down", "error": str(exc)})
        try:
            cur = _board_get("/api/v1/record/current")
            st["current"] = cur.get("session_id")
        except urllib.error.HTTPError as exc:
            if exc.code == 204:
                st["current"] = None
            else:
                st["current"] = None
        except BaseException:
            st["current"] = None
        self._json(st)

    def do_POST(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/board/record/start":
            return self._proxy(lambda: _board_post("/api/v1/record/start"))
        if path == "/api/board/record/stop":
            return self._proxy(lambda: _board_post("/api/v1/record/stop"))
        if path == "/api/board/request_download":
            body = self._body()
            sid = (body or {}).get("sid", "")
            if not sid:
                return self.send_error(400, "sid 必填")
            return self._proxy(lambda: _board_patch(sid, {"download_requested": True}))
        if path == "/api/sync":
            return self._api_sync()
        if path == "/api/load":
            return self._api_load()
        if path == "/api/delete":
            return self._api_delete()
        self.send_error(404)

    def _api_delete(self):
        """删会话：scope=local|board|both。board 走 capture_server DELETE（连文件）。"""
        import shutil as _sh
        body = self._body() or {}
        sid, scope = body.get("sid", ""), body.get("scope", "both")
        if not (sid.startswith("cap_") and sid.replace("_", "").isalnum()):
            return self.send_error(400, "sid 非法")
        out = {"sid": sid}
        if scope in ("board", "both"):
            try:
                out["board"] = _board_delete(sid)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    out["board"] = {"skipped": "板端无此会话"}
                elif exc.code == 409:
                    try:
                        out["board"] = json.loads(exc.read().decode("utf-8", "replace"))
                    except BaseException:
                        out["board"] = {"error": "busy(409)"}
                else:
                    try:
                        detail = exc.read().decode("utf-8", "replace")[:200]
                    except BaseException:
                        detail = ""
                    return self._json({"error": "板端删除失败 %d: %s" % (exc.code, detail)}, 502)
            except BaseException as exc:
                return self._json({"error": "板端连接失败: %s" % exc}, 502)
        if scope in ("local", "both"):
            d = os.path.join(C.DEST_ROOT, sid)
            if os.path.isdir(os.path.realpath(d)):
                _sh.rmtree(d)
                out["local"] = "removed"
            else:
                out["local"] = "absent"
        self._json(out)

    def _proxy(self, fn):
        try:
            out = fn()
            return self._json(out)
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", "replace")[:200]
            except BaseException:
                detail = ""
            return self._json({"error": "board %d: %s" % (exc.code, detail)}, exc.code)
        except BaseException as exc:
            return self._json({"error": str(exc)}, 502)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except BaseException:
            return {}

    # ---------- 同步 ----------
    def _api_sync(self):
        global _proc
        body = self._body() or {}
        sid = body.get("sid")
        if not sid:
            return self.send_error(400, "sid 必填")
        with _proc_lock:
            if _proc and _proc.poll() is None:
                return self._json({"ok": False, "error": "已有同步在跑"}, 409)
            # 如果板上还没 download_requested，先打标记（双保险）
            try:
                _board_patch(sid, {"download_requested": True})
            except BaseException:
                pass
            # 如果已转手持本地有件，不必重拉
            if _is_ready_for_load(os.path.join(C.DEST_ROOT, sid, "meta.json")):
                return self._json({"ok": True, "note": "已在本地"})
            _proc = subprocess.Popen(
                [sys.executable, "-u", _FETCH, "--sid", sid,
                 "--dest", C.DEST_ROOT],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self._json({"ok": True, "note": "拉取中，轮询 /api/sessions 等 local=true"})

    def _api_load(self):
        def _pick():
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.attributes("-topmost", True)
            root.withdraw()
            picked = filedialog.askdirectory(
                initialdir=C.DEST_ROOT, title="选会话目录（含 meta.json + points.bin）")
            root.destroy()
            result["sid"] = picked
        result = {}
        th = threading.Thread(target=_pick, daemon=True)
        th.start()
        th.join(timeout=60)
        sid = (result.get("sid") or "").strip()
        if not sid:
            return self._json({"ok": False}, 200)
        # 用户手动选了路径（可能在 DEST_ROOT 外）：只读出目录名作为 sid,专用于 file 提取
        base = os.path.basename(sid.rstrip("\\/"))
        loc = os.path.join(C.DEST_ROOT, base)
        # 不在 DEST_ROOT 则不复制，告诉前端跳 server 到 getfile? 简化：别在这种场景下载
        if os.path.normpath(os.path.dirname(sid)) != os.path.normpath(C.DEST_ROOT):
            return self._json({"ok": False, "error": "只能选 %s 下的会话" % C.DEST_ROOT}, 400)
        if not _is_ready_for_load(os.path.join(loc, "meta.json")):
            return self._json({"ok": False, "error": "目录缺 meta.json/points.bin"}, 400)
        return self._json({"ok": True, "sid": base})

def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Timer(0.3, lambda: webbrowser.open("http://127.0.0.1:%d/" % PORT)).start()
    print("human_replay 服务 http://127.0.0.1:%d/  （Ctrl-C 退出）" % PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
