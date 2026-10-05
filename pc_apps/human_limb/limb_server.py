# -*- coding: utf-8 -*-
"""human_limb 本地服务：静态文件 + 会话面板 + 一键 fetch→limb→播放。

用法：
    python limb_server.py            # http://127.0.0.1:8902 （自动开浏览器）

API：
    GET  /                         → limb_viewer.html
    GET  /api/sessions             → 列 captures/remote/cap_*（含 limb 状态）
    POST /api/prepare {"sid":...}  → 检查 limb_labels.json 是否存在；不存在则 spawn fetch + run_session_limb
    GET  /api/file?sid=xxx&name=meta.json|points.bin|limb_labels.json
                                     → 会话文件（白名单）
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8902
_HERE = os.path.dirname(os.path.abspath(__file__))
DEST_ROOT = r"D:\Code\ldiar\captures\remote"
FETCH = os.path.join(_HERE, "..", "human_replay", "fetch.py")
RUN_LIMB = os.path.join(_HERE, "run_session_limb.py")

_sid_re = re.compile(r"^cap_[0-9_]+$")
_jobs_lock = threading.Lock()
_jobs = {}  # sid → {stage: fetch|limb|done|error, ts, error}


def _sid_state(sid_dir):
    """看会话目录里文件齐不齐。"""
    meta = os.path.join(sid_dir, "meta.json")
    binp = os.path.join(sid_dir, "points.bin")
    limb_json = os.path.join(sid_dir, "limb_labels.json")
    out = {"exists": os.path.isdir(sid_dir),
           "has_meta": os.path.isfile(meta),
           "has_points": os.path.isfile(binp),
           "has_limb": os.path.isfile(limb_json),
           "limb_detected": None,
           "limb_total": None,
           "frames": None,
           "duration": None}
    if out["has_meta"]:
        try:
            m = json.load(open(meta, "r", encoding="utf-8"))
            out["duration"] = m.get("duration_sec")
            out["frames"] = len(m.get("frames") or [])
        except BaseException:
            pass
    if out["has_limb"]:
        try:
            j = json.load(open(limb_json, "r", encoding="utf-8"))
            st = j.get("stats") or {}
            out["limb_detected"] = st.get("frames_detected")
            out["limb_total"] = st.get("frames_total")
        except BaseException:
            pass
    return out


def _run_pipeline(sid):
    """子线程：fetch (若缺) → run_session_limb → 完成。"""
    sid_dir = os.path.join(DEST_ROOT, sid)
    def _upd(**kw):
        with _jobs_lock:
            d = _jobs.setdefault(sid, {})
            d.update(kw); d["ts"] = time.time()
    try:
        # fetch：只有缺 meta/bin 才拉
        st = _sid_state(sid_dir)
        if not (st["has_meta"] and st["has_points"]):
            _upd(stage="fetch")
            r = subprocess.run(
                [sys.executable, "-u", FETCH, "--sid", sid, "--dest", DEST_ROOT],
                capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                _upd(stage="error", error="fetch rc=%s: %s" % (r.returncode, r.stderr[-300:]))
                return
        st = _sid_state(sid_dir)
        if st["has_limb"]:
            _upd(stage="done", note="limb 早已跑过")
            return
        _upd(stage="limb")
        r = subprocess.run(
            [sys.executable, "-u", RUN_LIMB, sid_dir],
            capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            _upd(stage="error", error="limb rc=%s: %s" % (r.returncode, r.stderr[-300:]))
            return
        _upd(stage="done", note="limb 跑完")
    except BaseException as exc:
        _upd(stage="error", error=str(exc))


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

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except BaseException:
            return {}

    # ---------- GET ----------
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            return self._serve("limb_viewer.html", "text/html; charset=utf-8")
        if path == "/api/sessions":
            return self._api_sessions()
        if path == "/api/prepare_status":
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            sid = (q.get("sid") or [""])[0]
            with _jobs_lock:
                d = dict(_jobs.get(sid) or {"stage": "idle"})
            d.update(_sid_state(os.path.join(DEST_ROOT, sid)))
            # 附上 lock
            lockp = os.path.join(DEST_ROOT, sid, "limb_lock.json")
            if os.path.isfile(lockp):
                try:
                    lk = json.load(open(lockp, encoding="utf-8"))
                    d["lock"] = {"x": lk.get("x"), "y": lk.get("y")}
                except BaseException:
                    pass
            return self._json(d)
        if path.startswith("/api/file"):
            return self._serve_file()
        if path == "/api/lock":
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            sid = (q.get("sid") or [""])[0]
            if not _sid_re.match(sid):
                return self.send_error(400, "sid 非法")
            p = os.path.join(DEST_ROOT, sid, "limb_lock.json")
            if os.path.isfile(p):
                try:
                    return self._json(json.load(open(p, encoding="utf-8")))
                except BaseException:
                    pass
            return self._json({"x": None, "y": None})
        if path == "/limb_viewer.html":
            return self._serve("limb_viewer.html", "text/html; charset=utf-8")
        if path == "/vendor/three.min.js":
            return self._serve("../human_replay/vendor/three.min.js", "text/javascript")
        if path == "/vendor/OrbitControls.js":
            return self._serve("../human_replay/vendor/OrbitControls.js", "text/javascript")
        self.send_error(404)

    def _serve(self, rel, ctype):
        full = os.path.normpath(os.path.join(_HERE, rel))
        if not full.startswith(os.path.normpath(os.path.join(_HERE, ".."))):
            return self.send_error(403)
        if not os.path.isfile(full):
            return self.send_error(404)
        try:
            data = open(full, "rb").read()
        except OSError:
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self):
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        sid = (q.get("sid") or [""])[0]
        name = (q.get("name") or [""])[0]
        if name not in ("meta.json", "points.bin", "limb_labels.json"):
            return self.send_error(400, "name 白名单 meta/points/limb_labels")
        if not _sid_re.match(sid):
            return self.send_error(400, "sid 非法")
        full = os.path.join(DEST_ROOT, sid, name)
        if not os.path.isfile(full):
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type",
                          "application/json" if name.endswith(".json") else "application/octet-stream")
        self.send_header("Content-Length", str(os.path.getsize(full)))
        self.end_headers()
        with open(full, "rb") as fh:
            while True:
                b = fh.read(1 << 20)
                if not b:
                    break
                self.wfile.write(b)

    def _api_sessions(self):
        out = []
        if os.path.isdir(DEST_ROOT):
            for name in sorted(os.listdir(DEST_ROOT), reverse=True):
                if not name.startswith("cap_"):
                    continue
                d = os.path.join(DEST_ROOT, name)
                if not os.path.isdir(d):
                    continue
                st = _sid_state(d)
                with _jobs_lock:
                    job = dict(_jobs.get(name) or {})
                out.append({"sid": name, **st, "job": job})
        self._json({"sessions": out})

    # ---------- POST ----------
    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/lock":
            body = self._body() or {}
            sid = body.get("sid", "")
            x, y = body.get("x"), body.get("y")
            if not _sid_re.match(sid):
                return self.send_error(400, "sid 非法")
            if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                return self.send_error(400, "x/y 必填数值")
            p = os.path.join(DEST_ROOT, sid, "limb_lock.json")
            try:
                tmp = p + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump({"x": float(x), "y": float(y),
                               "set_iso": time.strftime("%Y-%m-%dT%H:%M:%S")}, fh)
                    fh.flush(); os.fsync(fh.fileno())
                os.replace(tmp, p)
            except OSError as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
            # 删掉已生成的 limb_labels，让用户点 "rerun" 重新跑
            for f in ("limb_labels.json", "limb_labels.js"):
                fp = os.path.join(DEST_ROOT, sid, f)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                    except OSError:
                        pass
            return self._json({"ok": True, "x": x, "y": y, "note": "已删除旧 limb_labels，需点「重跑」"})
        if path == "/api/prepare":
            body = self._body() or {}
            sid = body.get("sid", "")
            if not _sid_re.match(sid):
                return self.send_error(400, "sid 非法")
            force = bool(body.get("force"))   # 强制重跑： 即使有 limb_labels.json
            sid_dir = os.path.join(DEST_ROOT, sid)
            st = _sid_state(sid_dir)
            if st["has_limb"] and not force:
                return self._json({"ok": True, "note": "已有 limb_labels.json", "stage": "done"})
            with _jobs_lock:
                j = _jobs.get(sid)
                if j and j.get("stage") in ("fetch", "limb"):
                    return self._json({"ok": False, "error": "已有任务在跑", "stage": j.get("stage")}, 409)
                _jobs[sid] = {"stage": "queued", "ts": time.time()}
            # force: 删旧 labels 再 spawn
            if force:
                for f in ("limb_labels.json", "limb_labels.js"):
                    fp = os.path.join(DEST_ROOT, sid, f)
                    if os.path.isfile(fp):
                        try:
                            os.remove(fp)
                        except OSError:
                            pass
            th = threading.Thread(target=_run_pipeline, args=(sid,), daemon=True)
            th.start()
            return self._json({"ok": True, "note": "任务已排", "stage": "queued"})
        self.send_error(404)


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Timer(0.3, lambda: webbrowser.open("http://127.0.0.1:%d/" % PORT)).start()
    print("human_limb 服务 http://127.0.0.1:%d/  （Ctrl-C 退出）" % PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
