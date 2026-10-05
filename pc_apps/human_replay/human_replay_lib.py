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

# HR-W02: 静态服务文件白名单扩展位。打包/改 flist 时只在此追加，
# 不许补 prefix/目录通配——保持「单文件 explicit」的最小攻击面（同 _serve_file 白名单精神）。
_EXTRA_STATIC = frozenset({"human_detect_lib.js"})
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
        # PyInstaller's windowed console has no stderr stream.
        if sys.stderr is not None:
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
        if path.startswith("/api/validation/"):
            return self._validation("GET")
        if path.startswith("/api/leveling/"):
            return self._leveling("GET")
        if path.startswith("/api/human_detect/"):
            return self._human_detect("GET")
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
        if os.path.basename(rel).endswith(".test.js") and os.path.basename(rel) not in _EXTRA_STATIC:
            return self.send_error(404)
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
        from urllib.parse import urlparse, parse_qs
        local_only = parse_qs(urlparse(self.path).query).get("scope") == ["local"]
        local = _local_sessions(C.DEST_ROOT)
        board_error = None
        board_sessions = []
        if not local_only:
            try:
                board_sessions = _board_get("/api/v1/sessions").get("sessions", [])
            except BaseException as exc:
                board_error = "连接板失败: %s" % exc
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
        if path.startswith("/api/validation/"):
            return self._validation("POST")
        if path.startswith("/api/leveling/"):
            return self._leveling("POST")
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
        if path == "/api/save_annotations":
            return self._api_save_annotations()
        self.send_error(404)

    def _leveling(self, method):
        """以 in-proc 方式导入并 dispatch；ImportError → 503 降级，不使进程死亡。"""
        try:
            import leveling
        except ImportError as exc:
            return self._json({"error": "本地配平需要NumPy及完整工作台模块: " + str(exc)}, 503)
        return leveling.handle(self, method, C.DEST_ROOT)

    def _validation(self, method):
        try:
            import validation
        except ImportError as exc:
            return self._json({"error": "算法验证需要完整工作台模块: " + str(exc)}, 503)
        return validation.handle(self, method, C.DEST_ROOT)

    def _human_detect(self, method):
        """HR-W02 人体识别工作台 API 入口。当前只有 sessions 一个只读 route；
        未来加任务/上传/导出时走 _human_detect/*.py 里注册，别打补丁本文件。"""
        try:
            import human_detect as HD
        except ImportError as exc:
            return self._json({"error": "人体识别工作台需要完整插件: " + str(exc)}, 503)
        return HD.handle(self, method, C.DEST_ROOT)

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

    # ---------- HR-05 标注保存（原子写 meta.human_annotations） ----------

    # 冻结字段：除 human_annotations 外一律快照比对，任一字段变更 → fail
    _FROZEN_META_KEYS = (
        "format", "format_version", "session_id", "sensor", "time_domain",
        "duration_sec", "frame_rate_hz_measured", "topics",
        "point_layout", "point_stride_bytes", "point_file",
        "total_points", "frames", "extraction",
    )
    _SID_RE = re.compile(r"^cap_[0-9_]+$")

    @staticmethod
    def _validate_annotation_box(box):
        """与 human_replay_lib.js annotation_validate_box 对齐。"""
        if not isinstance(box, dict):
            return "box 不是 dict"
        c, s, yaw = box.get("center"), box.get("size"), box.get("yaw", 0.0)
        if not (isinstance(c, (list, tuple)) and len(c) == 3):
            return "center 不是 3 元"
        if not (isinstance(s, (list, tuple)) and len(s) == 3):
            return "size 不是 3 元"
        try:
            for i in range(3):
                cv, sv = float(c[i]), float(s[i])
                if not (-100.0 <= cv <= 100.0):
                    return "center[%d]=%s 超界" % (i, cv)
                if not (0.0 < sv <= 20.0):
                    return "size[%d]=%s 超界" % (i, sv)
            yv = float(yaw)
            if not (-3.141592653589793 < yv <= 3.141592653589793):
                return "yaw=%s 超界" % yv
        except (TypeError, ValueError):
            return "数值解析失败"
        return None

    def _api_save_annotations(self):
        body = self._body()
        sid = (body or {}).get("sid", "")
        anns = (body or {}).get("annotations", [])
        if not self._SID_RE.match(sid):
            return self._json({"ok": False, "error": "sid 非法"}, 400)
        if not isinstance(anns, list):
            return self._json({"ok": False, "error": "annotations 必须是 list"}, 400)
        for i, a in enumerate(anns):
            if not isinstance(a, dict) or a.get("source") != "human":
                return self._json(
                    {"ok": False, "error": "annotations[%d].source 必须是 human" % i}, 400)
            err = self._validate_annotation_box(a.get("box", {}))
            if err:
                return self._json(
                    {"ok": False, "error": "annotations[%d].box 非法: %s" % (i, err)}, 400)

        meta_dir = os.path.join(C.DEST_ROOT, sid)
        meta_path = os.path.join(meta_dir, "meta.json")
        tmp_path = meta_path + ".tmp"
        bak_path = meta_path + ".bak"

        if not os.path.isfile(meta_path):
            return self._json({"ok": False, "error": "meta.json 不存在"}, 404)
        if os.path.exists(tmp_path):
            return self._json({"ok": False, "error": "另一写者在途（.tmp 存在）"}, 409)

        # 读旧 meta 做冻结字段快照 + backup
        try:
            with open(meta_path, "r", encoding="utf-8") as fh:
                old_meta = json.load(fh)
        except (OSError, ValueError) as exc:
            return self._json({"ok": False, "error": "meta 读取失败: %s" % exc}, 500)
        try:
            shutil.copy2(meta_path, bak_path)
        except OSError as exc:
            return self._json({"ok": False, "error": "备份失败: %s" % exc}, 500)
        frozen_before = {k: old_meta.get(k) for k in self._FROZEN_META_KEYS}

        new_meta = dict(old_meta)
        new_meta["human_annotations"] = anns

        # 原子写（tmp → fsync → replace）
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(new_meta, fh, ensure_ascii=False, indent=1)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, meta_path)   # Windows 原子
        except OSError as exc:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                if os.path.exists(bak_path) and os.path.exists(meta_path):
                    # meta 可能半截：以 bak 回滚
                    os.replace(bak_path, meta_path)
            except OSError:
                pass
            return self._json({"ok": False, "error": "写盘失败: %s" % exc}, 500)

        # 写后再校验一遍（防 silent corruption）+ 快照对比冻结字段
        try:
            with open(meta_path, "rb") as fh:
                data = fh.read()
            sha = hashlib.sha256(data).hexdigest()
            re_meta = json.loads(data.decode("utf-8"))
            frozen_after = {k: re_meta.get(k) for k in self._FROZEN_META_KEYS}
            if frozen_before != frozen_after:
                # 回滚
                os.replace(bak_path, meta_path)
                return self._json({"ok": False, "error": "冻结字段被意外修改，已回滚"}, 500)
        except (OSError, ValueError) as exc:
            return self._json({"ok": False, "error": "写后校验失败: %s" % exc}, 500)

        return self._json({
            "ok": True,
            "count": len(anns),
            "meta_path": meta_path,
            "sha256": sha,
        })


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
