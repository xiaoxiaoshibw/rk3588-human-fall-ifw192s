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
import shutil
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
_EXTRA_STATIC = frozenset({"human_detect_lib.js", "human_pipe_lib.js", "gt_workbench_ops.js", "gt_live.js"})
_proc_lock = threading.Lock()
_sync_thread = None      # 当前同步线程（替代旧 subprocess _proc）
_sync_last_error = None  # 最近一次同步失败原因，前端轮询 /api/sync_status 看
_sync_running_sid = None # 当前正在拉的 sid（None = 没在拉）
_sync_last_sid = None     # 最近一次的 sid（成功/失败/短路"已在本地"都会写）
_sync_last_result = None  # 最近一次结果：None（还在跑/未启动）/ "ok" / "failed"
_sync_recoverable_sid = None  # 最近失败若因板端卡 transferring：允许人工「退回重试」的 sid

# GT 产物同步：PC 从板端 8088 GT 服务拉 draft/manifest/GT_V*/aliases 回本地 gt_store。
# 权威实现是 pull_gt_from_board.pull（同名+同 sha 短路、GT_V* 冲突不覆盖）；这里只做
# worker 线程封装与状态查询，板端模式禁用（板上 GT 本就地，无须同步）。
_gt_pull_lock = threading.Lock()
_gt_pull_thread = None
_gt_pull_last_error = None
_gt_pull_last_result = None     # None / "ok" / "failed"
_gt_pull_last_detail = None     # {"pulled":[...],"skipped":[...],"conflicts":[...]}
_GT_PULL_BOARD_DEFAULT = "http://192.168.31.58:8088"  # GT 服务端口；≠ capture_server :8766


def _deny_local_only(h, action):
    """板端协作模式下禁用只对本机有意义的动作（音箱式：不删原始数据、不拖拽拉取、不弹 Tk）。
    403-JSON（不是裸 send_error）以便前端可解析。"""
    h._json({"ok": False,
             "error": "板端模式下 %s 被禁用（保护原始数据/协同一致性）" % action,
             "board_mode": True}, 403)


def _is_ready_for_load(meta_path):
    return os.path.isfile(meta_path) and os.path.isfile(os.path.join(
        os.path.dirname(meta_path), "points.bin"))


def _local_sessions(dest):
    """dest 下含 meta.json + points.bin 的会话目录 → 轻描述（从 meta.json 揭sel）。
    目录名过 C.SID_RE（字母/数字/下划线/连字符），synth_* 等 PC 生成会话同列。"""
    out = {}
    if not os.path.isdir(dest):
        return out
    for name in os.listdir(dest):
        d = os.path.join(dest, name)
        meta_p = os.path.join(d, "meta.json")
        if not (os.path.isdir(d) and C.SID_RE.match(name) and _is_ready_for_load(meta_p)):
            continue
        try:
            with open(meta_p, "r", encoding="utf-8") as fh:
                m = json.load(fh)
            frames = m.get("frames")
            size = os.path.getsize(os.path.join(d, "points.bin"))
            if not isinstance(frames, list) or not frames or not size or size % 28:
                continue  # 两页消费固定 28B/点；空帧表/空文件/未完整写入不预选。
            # 完整性（2026-10-14 用户要求）：meta 声明了 stride 时，末帧 offset+count 必须
            # 正好等于文件字节数；半写/被截断的 points.bin 不算「本机有的会话」，不列。
            stride = (m.get("point_layout") or {}).get("stride_bytes")
            last = frames[-1]
            if (stride and isinstance(last, dict)
                    and isinstance(last.get("offset_points"), int)
                    and isinstance(last.get("count_points"), int)
                    and (last["offset_points"] + last["count_points"]) * stride != size):
                continue
            out[name] = {
                "duration_sec": m.get("duration_sec"),
                "total_points": m.get("total_points"),
                "frames": len(m.get("frames") or []),
                "frame_rate": m.get("frame_rate_hz_measured"),
                "created_iso": m.get("created_iso"),
                "bytes": size,
                "name": m.get("name"),
            }
        except (OSError, ValueError, TypeError, AttributeError):
            continue  # 元数据不可读不能当作本地可载入会话。
    return out


def _dir_manifest(directory):
    """会话目录内每个文件的 (name, bytes, sha256)，按名字排序；只读，供删除前清单用。"""
    files = []
    for name in sorted(os.listdir(directory)):
        full = os.path.join(directory, name)
        if not os.path.isfile(full):
            continue
        digest = hashlib.sha256()
        with open(full, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
        files.append({"name": name, "bytes": os.path.getsize(full), "sha256": digest.hexdigest()})
    return files


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


def _board_files_present(sid, timeout=3.0):
    """板端还有这个会话的数据吗：HEAD meta.json + points.bin，只读头不下正文。

    登记表（sessions.json）会留 FIFO 清过文件的墓碑行，meta/points 路径照样写着——
    所以「有没有数据」只能实查文件。板不可达时返回 True：连不上板不能当作数据缺失，
    列表该照旧显示（否则离线时整屏会话被吞）。
    """
    for name in ("meta.json", "points.bin"):
        req = urllib.request.Request(
            "%s/api/v1/sessions/%s/files/%s" % (C.BOARD_URL, sid, name), method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200 or int(resp.headers.get("Content-Length") or 0) <= 0:
                    return False
        except urllib.error.HTTPError:
            return False          # 404 file_missing：板端文件已被清理
        except (OSError, ValueError):
            return True
    return True


def _sync_failure_note(sid):
    """同步失败后实查板端，给面板可读的失败说明与能否人工退回。

    transferring = 卡死：下载客户端中断时没人跑 fetch._fail 的自动回退。
    干净失败（下载中断/SHA 不符）fetch 会自己退回 ready+extra.error，应显示真实错误。
    返回 (说明文本, 是否可「退回重试」)。
    """
    try:
        sess = _board_get("/api/v1/sessions/" + sid)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "板端无此会话（可能已被删）", False
        return "fetch 返回 False（板端状态查询失败 %d）" % exc.code, False
    except BaseException as exc:
        return "fetch 返回 False（板端状态查询失败: %s）" % exc, False
    state = sess.get("state")
    if state == "transferring":
        return "板端卡在传输中（上次同步中断）：点「退回重试」退回就绪后重新拉取。", True
    err = sess.get("error")  # 板端 GET 是扁平登记记录，error 在顶层
    if err:
        return "fetch 失败：%s" % err, False
    return "fetch 返回 False（板端状态 %s，无错误详情）" % (state or "未知"), False


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
        # board_mode 或来自非环回：远程协作者身份。GET 全放行（静态/点云/会话/GT 导出皆为只读）。
        self._multi = C.BOARD_MODE or self.client_address[0] not in ("127.0.0.1", "::1")
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/validation/"):
            return self._validation("GET")
        if path.startswith("/api/leveling/"):
            return self._leveling("GET")
        if path.startswith("/api/human_detect/"):
            return self._human_detect("GET")
        if path.startswith("/api/gt/exports/"):
            return self._serve_gt_export()
        if path == "/api/gt/exports":
            return self._api_gt_exports()
        if path == "/api/gt/pull_status":
            return self._api_gt_pull_status()
        if path.startswith("/api/gt/"):
            return self._gt("GET")
        if path == "/api/sessions":
            return self._api_sessions()
        if path == "/api/manifest":
            return self._api_manifest()
        if path == "/api/board/status":
            return self._board_status()
        if path == "/api/sync_status":
            return self._api_sync_status()
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
        hidden = {"purged": 0, "missing": 0}   # 登记表还在、数据已不在任何一端的行
        for s in board_sessions:
            sid = s.get("session_id", "")
            li = local.get(sid)
            if not li:
                # 数据完整性（2026-10-14 用户要求「只展示 3588 和本机有的会话」）：
                # state=purged 是板端 FIFO 已删文件；其余 state 也要实查文件在不在，
                # 否则点进去只会拉失败。本机有副本的行照列（数据还在本机）。
                if s.get("state") == "purged":
                    hidden["purged"] += 1
                    continue
                if not _board_files_present(sid):
                    hidden["missing"] += 1
                    continue
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
                "bytes": (li or {}).get("bytes"),          # FIX-PERF-R2: 供 GT 下拉显示大小
                "name": (li or {}).get("name"),
            })
        # 本地有但板端已删的（FIFO 清过）也列上
        listed = {o["sid"] for o in out}
        for sid, li in local.items():
            if sid not in listed:
                out.append({"sid": sid, "state": "local-only",
                            "created_iso": li.get("created_iso"),
                            "duration_sec": li.get("duration_sec"),
                            "frames": li.get("frames"),
                            "local": True,
                            "bytes": li.get("bytes"),      # FIX-PERF-R2
                            "name": li.get("name")})
        out.sort(key=lambda o: o.get("created_iso") or "", reverse=True)
        self._json({"sessions": out, "board_error": board_error, "hidden": hidden})

    # ---------- 录制控制台（代理板端） ----------
    def _board_status(self):
        try:
            st = _board_get("/api/v1/status")
        except BaseException as exc:
            return self._json({"ros": "down", "error": str(exc)})
        try:
            cur = _board_get("/api/v1/record/current")
            st["current"] = cur.get("session_id")
            st["current_created_iso"] = cur.get("created_iso")  # 面板已录时长用
        except urllib.error.HTTPError as exc:
            if exc.code == 204:
                st["current"] = None
            else:
                st["current"] = None
            st["current_created_iso"] = None
        except BaseException:
            st["current"] = None
            st["current_created_iso"] = None
        self._json(st)

    def do_POST(self):  # noqa: N802
        self._multi = C.BOARD_MODE or self.client_address[0] not in ("127.0.0.1", "::1")
        path = self.path.split("?", 1)[0]
        if self._multi:
            # 多人协作：只留 GT 标注写路径；一切动原始数据/拉取/删/改名/板控制都禁
            _deny_post = {
                "/api/delete": "删除会话",
                "/api/sync": "手动拉取会话（板端数据就在原地，无需同步）",
                "/api/recover": "板端 transferring 状态人工回退",
                "/api/load": "Tk 目录选择（板无 GUI）",
                "/api/rename": "本地会话改名",
                "/api/save_annotations": "HR-05 旧标注（HR-05 在 PC 视图继续使用）",
                "/api/board/record/start": "触发板端录制（请走 webui/human_capture）",
                "/api/board/record/stop": "停止板端录制",
                "/api/board/request_download": "标记 download_requested",
                "/api/gt/pull": "从板端拉 GT 产物（板上 GT 就在原地，无须同步）",
            }
            if path in _deny_post:
                return _deny_local_only(self, _deny_post[path])
        if path.startswith("/api/validation/"):
            return self._validation("POST")
        if path.startswith("/api/leveling/"):
            return self._leveling("POST")
        if path == "/api/gt/pull":
            return self._api_gt_pull()
        if path.startswith("/api/gt/"):
            return self._gt("POST")
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
        if path == "/api/recover":
            return self._api_recover()
        if path == "/api/load":
            return self._api_load()
        if path == "/api/delete":
            return self._api_delete()
        if path == "/api/rename":
            return self._api_rename()
        if path == "/api/save_annotations":
            return self._api_save_annotations()
        self.send_error(404)

    # ---------- GT 标注导出下载（板端可拉到 PC） ----------
    def _serve_gt_export(self):
        """GET /api/gt/exports/file?sid&name — 白名单流式下载（标注并发即由 gt_store 保证）。"""
        from urllib.parse import urlparse, parse_qs
        import gt_server as _GS
        q = parse_qs(urlparse(self.path).query)
        sid = (q.get("sid") or [""])[0]
        name = (q.get("name") or [""])[0]
        if name and ("/" in name or ".." in name):
            return self._json({"ok": False, "error": "文件名含路径分隔"}, 400)
        if sid and not _GS._sid_ok(sid):
            return self._json({"ok": False, "error": "sid 非法"}, 400)
        if not name or not _GS.export_whitelist_ok(sid or None, name, None)[0]:
            return self._json({"ok": False, "error": "文件名不在导出白名单"}, 400)
        base = os.path.join(_GS.get_store_dir(), sid) if sid else _GS.get_store_dir()
        full = os.path.join(base, name) if name else base
        if not name or not os.path.isfile(full):
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header(
            "Content-Disposition",
            'attachment; filename="%s_%s"' % ((sid or "global"), name.replace("/", "_")))
        self.send_header("Content-Length", str(os.path.getsize(full)))
        self.end_headers()
        with open(full, "rb") as fh:
            while True:
                block = fh.read(1 << 20)
                if not block:
                    break
                self.wfile.write(block)

    def _api_gt_exports(self):
        """GET /api/gt/exports — 列出可下载文件（全局 + 指定 sid）。

        FIX-REVIEW-H1: sid 必须先过 _sid_ok（与 _serve_gt_export 一致），否则可拿
        `?sid=../..` 这类路径穿越枚举 gt_store 之外目录。GET 板端模式也放行，
        校验必须在路由层完成。
        """
        from urllib.parse import urlparse, parse_qs
        import gt_server as _GS
        q = parse_qs(urlparse(self.path).query)
        sid = (q.get("sid") or [""])[0] or None
        if sid is not None and not _GS._sid_ok(sid):
            return self._json({"ok": False, "error": "sid 非法"}, 400)
        self._json({"ok": True, "sid": sid, **_GS.list_exports(_GS.get_store_dir(), sid)})

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

    def _gt(self, method):
        """HUMAN-GT-ANNOTATOR-R1 GT 工作台路由 (draft 保存 / 冻结 / 导出 / 建议)。"""
        try:
            import gt_server
        except ImportError as exc:
            return self._json({"error": "GT 工作台插件缺失: " + str(exc)}, 503)
        return gt_server.handle(self, method, C.DEST_ROOT)

    # ---------- 删除前清单（清单接口，只读） ----------
    def _api_manifest(self):
        """GET /api/manifest?sid=…：本机会话文件清单（name/bytes/sha256）+ 板端登记行。

        删除纪律（2026-10-14 用户要求）：先出 sid+字节+sha256 清单，再由人显式确认才删；
        本接口只读，不删任何东西。
        """
        from urllib.parse import urlparse, parse_qs
        sid = (parse_qs(urlparse(self.path).query).get("sid") or [""])[0]
        if not C.SID_RE.match(sid):
            return self._json({"ok": False, "error": "sid 非法"}, 400)
        directory = os.path.join(C.DEST_ROOT, sid)
        present = os.path.isdir(os.path.realpath(directory))
        files = _dir_manifest(directory) if present else []
        out = {"sid": sid,
               "local": {"present": present, "files": files,
                         "total_bytes": sum(f["bytes"] for f in files)},
               "board": None}
        try:
            out["board"] = _board_get("/api/v1/sessions/" + sid)
        except urllib.error.HTTPError as exc:
            out["board"] = {"error": "板端无此会话" if exc.code == 404 else "板端 HTTP %d" % exc.code}
        except BaseException as exc:
            out["board"] = {"error": "板端不可达: %s" % exc}
        self._json(out)

    # ---------- 修改（POST） ----------
    def _api_delete(self):
        """删会话：scope=local|board|both。board 走 capture_server DELETE（连文件）。"""
        import shutil as _sh
        body = self._body() or {}
        sid, scope = body.get("sid", ""), body.get("scope", "both")
        if not C.SID_RE.match(sid):
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

    # ---------- 会话改名（本地别名，不动 sid/目录/板端） ----------
    def _api_rename(self):
        """写本机 <sid>/meta.json 的 name 字段；sid 是身份，改名只影响显示。

        空 name = 删除该字段（恢复默认显示）。板端登记不改——要板端
        webui 也显示名字得改 capture_server，属另一次授权。
        """
        body = self._body() or {}
        sid = body.get("sid", "")
        name = body.get("name", "")
        if not self._SID_RE.match(sid):
            return self._json({"ok": False, "error": "sid 非法"}, 400)
        if not isinstance(name, str):
            return self._json({"ok": False, "error": "name 必须是字符串"}, 400)
        name = name.strip()
        if len(name) > 60:
            return self._json({"ok": False, "error": "名称最长 60 字符"}, 400)
        if any(ord(c) < 32 for c in name):
            return self._json({"ok": False, "error": "名称不能含控制字符"}, 400)

        meta_path = os.path.join(C.DEST_ROOT, sid, "meta.json")
        tmp_path = meta_path + ".tmp"
        if not os.path.isfile(meta_path):
            return self._json({"ok": False, "error": "本地无此会话（先下载再改名）"}, 404)
        if os.path.exists(tmp_path):
            return self._json({"ok": False, "error": "另一写者在途（.tmp 存在）"}, 409)
        try:
            with open(meta_path, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, ValueError) as exc:
            return self._json({"ok": False, "error": "meta 读取失败: %s" % exc}, 500)
        if name:
            meta["name"] = name
        else:
            meta.pop("name", None)
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, ensure_ascii=False, indent=1)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, meta_path)
        except OSError as exc:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            return self._json({"ok": False, "error": "写盘失败: %s" % exc}, 500)
        return self._json({"ok": True, "sid": sid, "name": name})

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
        global _sync_thread, _sync_last_error, _sync_running_sid, _sync_last_sid, _sync_last_result
        global _sync_recoverable_sid
        body = self._body() or {}
        sid = body.get("sid")
        if not sid:
            return self.send_error(400, "sid 必填")
        with _proc_lock:
            if _sync_thread and _sync_thread.is_alive():
                return self._json({"ok": False, "error": "已有同步在跑（%s）" % _sync_running_sid}, 409)
            _sync_recoverable_sid = None  # 新一轮尝试开始：上一轮失败留下的「退回重试」入口作废
            # 如果板上还没 download_requested，先打标记（双保险）
            try:
                _board_patch(sid, {"download_requested": True})
            except BaseException:
                pass
            # 如果已转手持本地有件，不必重拉
            if _is_ready_for_load(os.path.join(C.DEST_ROOT, sid, "meta.json")):
                _sync_last_sid = sid
                _sync_last_result = "ok"      # 短路：已在本地——等同成功
                _sync_last_error = None
                _sync_running_sid = None
                return self._json({"ok": True, "note": "已在本地"})
            # 新起一轮：清空上次结果
            _sync_last_error = None
            _sync_last_result = None
            _sync_running_sid = sid
            _sync_last_sid = sid

            def _worker(target_sid):
                global _sync_last_error, _sync_last_result, _sync_recoverable_sid
                try:
                    import fetch as F
                    ok = F.process_session(target_sid, C.DEST_ROOT, log=lambda m: None)
                    if ok:
                        _sync_last_result = "ok"
                        _sync_recoverable_sid = None
                    else:
                        # 实查板端再给结论：卡 transferring ≠ 有 extra.error（旧文案会误导）
                        _sync_last_result = "failed"
                        _sync_last_error, recoverable = _sync_failure_note(target_sid)
                        _sync_recoverable_sid = target_sid if recoverable else None
                except BaseException as exc:
                    _sync_last_result = "failed"
                    _sync_last_error = "%s: %s" % (type(exc).__name__, exc)
                    _sync_recoverable_sid = None
                finally:
                    # 不在这里清 _sync_running_sid——前端一轮 /api/sync_status 看到
                    # 线程死了再清，留给它先看到最终结果
                    pass

            _sync_thread = threading.Thread(target=_worker, args=(sid,), daemon=True)
            _sync_thread.start()
        return self._json({"ok": True, "note": "拉取中，轮询 /api/sync_status 等 local=true"})

    def _api_sync_status(self):
        """轮询端点：返回当前同步状态 + 最近失败原因，前端用来提前失败提示。"""
        alive = bool(_sync_thread and _sync_thread.is_alive())
        return self._json({
            "running": alive,
            "sid": _sync_running_sid if alive else None,
            "last_sid": _sync_last_sid,
            "last_result": _sync_last_result,   # None=未启动/在跑; "ok"=success; "failed"=error
            "last_error": _sync_last_error,
            "recoverable": bool(_sync_recoverable_sid),  # True=板端卡 transferring，可「退回重试」
            "recover_sid": _sync_recoverable_sid,
        })

    def _api_recover(self):
        """人工退回：把板端卡在 transferring 的会话置回 ready（仅面板显式触发）。

        与 fetch._fail 的自动回退同一条状态机转换；区别是用于客户端进程
        在下载中被中断、没人跑 _fail 时留下的卡死会话。
        """
        global _sync_recoverable_sid
        body = self._body() or {}
        sid = body.get("sid", "")
        if not self._SID_RE.match(sid):
            return self._json({"ok": False, "error": "sid 非法"}, 400)
        try:
            import fetch as F
        except ImportError as exc:
            return self._json({"ok": False, "error": "退回需要 fetch 模块: " + str(exc)}, 503)
        ok, reason = F.recover(sid)
        if not ok:
            return self._json({"ok": False, "error": reason}, 409)
        if _sync_recoverable_sid == sid:
            _sync_recoverable_sid = None
        return self._json({"ok": True, "sid": sid})

    # ---------- GT 产物从板端 8088 拉回 PC（权威实现 = pull_gt_from_board.pull） ----------
    def _api_gt_pull(self):
        """POST /api/gt/pull → 后台线程跑 pull_gt_from_board.pull；立刻回 202 风格应答，轮询 status。"""
        global _gt_pull_thread, _gt_pull_last_error, _gt_pull_last_result, _gt_pull_last_detail
        with _gt_pull_lock:
            if _gt_pull_thread and _gt_pull_thread.is_alive():
                return self._json({"ok": False, "error": "已有 GT 拉取在跑"}, 409)
            _gt_pull_last_error = None
            _gt_pull_last_result = None
            _gt_pull_last_detail = None

            def _worker():
                global _gt_pull_last_error, _gt_pull_last_result, _gt_pull_last_detail
                try:
                    import pull_gt_from_board as P
                    import gt_server as G
                    res = P.pull(board=_GT_PULL_BOARD_DEFAULT,
                                 dest_store=G.get_store_dir(),
                                 log=lambda m: None)
                    _gt_pull_last_detail = res
                    _gt_pull_last_result = "ok" if not res.get("conflicts") else "failed"
                    if res.get("conflicts"):
                        _gt_pull_last_error = "GT_V* 冲突（板上与本地不一致，不覆盖）"
                except BaseException as exc:
                    _gt_pull_last_result = "failed"
                    _gt_pull_last_error = "%s: %s" % (type(exc).__name__, exc)
                    _gt_pull_last_detail = None

            _gt_pull_thread = threading.Thread(target=_worker, daemon=True)
            _gt_pull_thread.start()
        return self._json({"ok": True, "note": "GT 拉取中；轮询 /api/gt/pull_status"})

    def _api_gt_pull_status(self):
        alive = bool(_gt_pull_thread and _gt_pull_thread.is_alive())
        return self._json({
            "running": alive,
            "last_result": _gt_pull_last_result,
            "last_error": _gt_pull_last_error,
            "detail": _gt_pull_last_detail,
        })

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
    _SID_RE = C.SID_RE  # 白名单单点收敛 config.SID_RE（synth_*/clip 后缀同可载）

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
    host = "0.0.0.0" if C.BOARD_MODE else "127.0.0.1"
    port = int(os.environ.get("HR_PORT", PORT))
    srv = ThreadingHTTPServer((host, port), Handler)
    url = "http://%s:%d/" % (("127.0.0.1" if host == "0.0.0.0" else host), port)
    if not C.BOARD_MODE:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    print("human_replay 服务 %s  （board_mode=%s, Ctrl-C 退出）" % (url, C.BOARD_MODE))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
