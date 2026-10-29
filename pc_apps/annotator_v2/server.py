#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""annotator_v2 API 服务器（PC 端，stdlib only，默认只绑 127.0.0.1:8902）。

端点：
  GET  /api/sessions                       — 扫描数据根目录（默认 <repo>/data/sessions）
  GET  /api/session/<sid>/meta             — meta.json 原文
  GET  /api/session/<sid>/frame/<i>        — 第 i 帧点云字节切片（offset*stride 起）
  GET  /api/gt?sid=<sid>                   — {version, doc|null}
  PUT  /api/gt?sid=<sid>                   — {baseVersion, doc} → 200 {version} / 409 冲突
静态：dist/ 构建产物；dev 时前端走 vite 代理，本服务只出 API。

安全边界：sid 白名单字符；只读 data 根目录；GT 只写 gt_store_v2/<sid>/draft.json
（tmp + os.replace 原子替换）；不触碰 data/sessions、junction 与旧 gt_store。
"""
import argparse
import json
import os
import re
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
DEFAULT_DATA_ROOT = os.path.join(_REPO_ROOT, "data", "sessions")
DEFAULT_STORE_ROOT = os.path.join(_HERE, "gt_store_v2")
DEFAULT_DIST = os.path.join(_HERE, "dist")
sys.path.insert(0, os.path.join(_REPO_ROOT, "pc_apps", "range_fall"))
from analysis import AnalysisStore

_SID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")

_META_CACHE = {}  # sid -> (mtime, meta_dict)  避免每帧都重读 meta
_META_LOCK = threading.Lock()


def _load_meta(data_root, sid):
    path = os.path.join(data_root, sid, "meta.json")
    try:
        st = os.stat(path)
        mtime = (st.st_mtime_ns,st.st_size)
    except OSError:
        return None
    with _META_LOCK:
        key = (os.path.realpath(data_root),sid)
        cached = _META_CACHE.get(key)
        if cached and cached[0] == mtime:
            return cached[1]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return None
    with _META_LOCK:
        _META_CACHE[key] = (mtime, meta)
    return meta


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Handler(BaseHTTPRequestHandler):
    server_version = "annotator_v2/0.1"
    # 类属性由 main() 注入
    data_root = DEFAULT_DATA_ROOT
    store_root = DEFAULT_STORE_ROOT
    dist_root = DEFAULT_DIST
    analysis_store = None
    body_store = None

    # ---------- 基础 ----------
    def log_message(self, fmt, *args):  # 安静些；测试里可读
        sys.stderr.write("[annotator_v2] %s %s\n" % (self.address_string(), fmt % args))

    def _send(self, status, body, ctype="application/json; charset=utf-8", head_only=False):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _send_json(self, status, obj):
        self._send(status, json.dumps(obj, ensure_ascii=False))

    # ---------- 路由 ----------
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path.startswith('/api/body/'):
                return self._api_body(parsed, 'GET')
            if path == "/api/sessions":
                return self._api_sessions()
            m = re.fullmatch(r'/api/session/([A-Za-z0-9_-]{1,128})/depth/(\d+)/(preview|metric|mask|metadata)',path)
            if m:
                if self.analysis_store is None:
                    raise ApiError(404,'analysis not configured')
                sid, index, kind = m.group(1), int(m.group(2)), m.group(3)
                try:
                    raw = self.analysis_store.asset(sid,index,kind)
                except KeyError as e:
                    raise ApiError(404,str(e))
                except (OSError,ValueError) as e:
                    raise ApiError(409,str(e))
                return self._send(200,raw,'application/json' if kind == 'metadata' else 'image/png')
            m = re.match(r"^/api/session/([^/]+)/analysis$", path)
            if m:
                sid = m.group(1)
                if not _SID_RE.fullmatch(sid):
                    raise ApiError(400, "bad sid")
                try:
                    index = int((parse_qs(parsed.query).get('frame') or [''])[0])
                    if index < 0:
                        raise ValueError()
                except ValueError:
                    raise ApiError(400, "frame must be a nonnegative integer")
                if self.analysis_store is None:
                    raise ApiError(404, "analysis not configured")
                try:
                    return self._send_json(200, self.analysis_store.frame(sid, index))
                except KeyError as e:
                    raise ApiError(404, str(e))
                except (OSError, ValueError) as e:
                    raise ApiError(409, str(e))
            m = re.match(r"^/api/session/([^/]+)/meta$", path)
            if m:
                return self._api_meta(m.group(1))
            m = re.match(r"^/api/session/([^/]+)/frame/(\d+)$", path)
            if m:
                return self._api_frame(m.group(1), int(m.group(2)))
            m = re.match(r"^/api/gt$", path)
            if m:
                sid = (parse_qs(parsed.query).get("sid") or [""])[0]
                return self._api_gt_get(sid)
            if path.startswith('/api/'):
                raise ApiError(404, 'unknown API route')
            return self._serve_static(path)
        except ApiError as e:
            return self._send_json(e.status, {"error": e.message})
        except BrokenPipeError:
            pass

    def do_PUT(self):
        try:
            parsed = urlparse(self.path)
            if parsed.path.startswith('/api/body/'):
                return self._api_body(parsed, 'PUT')
            if parsed.path != "/api/gt":
                return self._send_json(404, {"error": "not found"})
            sid = (parse_qs(parsed.query).get("sid") or [""])[0]
            return self._api_gt_put(sid)
        except ApiError as e:
            return self._send_json(e.status, {"error": e.message})

    def do_POST(self):
        try:
            return self._api_body(urlparse(self.path), 'POST')
        except ApiError as e:
            return self._send_json(e.status, {"error": e.message})

    def _api_body(self, parsed, method):
        match = re.fullmatch(r'/api/body/([A-Za-z0-9_-]{1,128})/(\d+)', parsed.path)
        if match is None or self.body_store is None:
            raise ApiError(404, 'body mapping unavailable')
        person = (parse_qs(parsed.query).get('person') or [''])[0]
        try:
            context, xyz, indices = self.body_store.context(match[1], int(match[2]), person)
            if method == 'GET':
                return self._send_json(200, dict(context=context, **self.body_store.load(context, xyz, indices)))
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8*1024*1024:
                raise ValueError('body payload must be 1..8MiB')
            body = json.loads(self.rfile.read(length))
            if method == 'PUT':
                result = self.body_store.save(context, xyz, indices, body)
            elif body.get('action') == 'suggest':
                result = self.body_store.suggest(context, xyz, indices)
            else:
                result = self.body_store.compute(context, xyz, indices, body.get('doc'))
            return self._send_json(200, result)
        except KeyError as e:
            raise ApiError(404, str(e))
        except (ValueError, OSError, TypeError, AttributeError) as e:
            raise ApiError(409, str(e))

    # ---------- API ----------
    def _api_sessions(self):
        out = []
        try:
            names = sorted(os.listdir(self.data_root))
        except OSError:
            names = []
        for sid in names:
            if not _SID_RE.match(sid):
                continue
            meta = _load_meta(self.data_root, sid)
            if not meta:
                continue
            frames = meta.get("frames") or []
            def _stamp(fr):
                s = fr.get("stamp_sec")
                if not isinstance(s, (int, float)):
                    return None
                n = fr.get("stamp_nanosec")
                return s + (n / 1e9 if isinstance(n, (int, float)) else 0.0)
            first = _stamp(frames[0]) if frames else None
            last = _stamp(frames[-1]) if frames else None
            dur = (last - first) if first is not None and last is not None else None
            out.append({
                "sessionId": sid,
                "frameCount": len(frames),
                "durationSec": dur,
                "totalPoints": meta.get("total_points"),
                "createdAtIso": meta.get("created_iso"),
            })
        self._send_json(200, {"sessions": out})

    def _api_meta(self, sid):
        if not _SID_RE.match(sid):
            raise ApiError(400, "bad sid")
        meta = _load_meta(self.data_root, sid)
        if meta is None:
            raise ApiError(404, "session meta not found")
        self._send(200, json.dumps(meta, ensure_ascii=False))

    def _api_frame(self, sid, frame_index):
        if not _SID_RE.match(sid):
            raise ApiError(400, "bad sid")
        meta = _load_meta(self.data_root, sid)
        if meta is None:
            raise ApiError(404, "session meta not found")
        frames = meta.get("frames") or []
        if frame_index >= len(frames):
            raise ApiError(404, "frame out of range")
        fr = frames[frame_index]
        stride = meta.get("point_stride_bytes") or meta.get("point_layout", {}).get("stride_bytes") or 28
        offset = int(fr.get("offset_points", 0))
        count = int(fr.get("count_points", 0))
        start = offset * stride
        length = count * stride
        points_path = os.path.join(self.data_root, sid, "points.bin")
        try:
            with open(points_path, "rb") as fh:
                fh.seek(start)
                data = fh.read(length)
        except OSError:
            raise ApiError(404, "points.bin not found")
        if len(data) != length:
            raise ApiError(500, "short read on points.bin")
        self._send(200, data, ctype="application/octet-stream")

    # ---------- GT ----------
    def _gt_paths(self, sid):
        if not _SID_RE.match(sid):
            raise ApiError(400, "bad sid")
        d = os.path.join(self.store_root, sid)
        return d, os.path.join(d, "draft.json")

    def _api_gt_get(self, sid):
        _dir, draft = self._gt_paths(sid)
        if not os.path.isfile(draft):
            return self._send_json(200, {"version": 0, "doc": None})
        with open(draft, "r", encoding="utf-8") as fh:
            env = json.load(fh)
        self._send_json(200, {"version": env.get("version", 0), "doc": env.get("doc")})

    def _api_gt_put(self, sid):
        _dir, draft = self._gt_paths(sid)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ApiError(400, "bad content-length")
        if length > 64 * 1024 * 1024:
            raise ApiError(413, "payload too large")
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise ApiError(400, "body not json")
        doc = body.get("doc")
        base = body.get("baseVersion", None)
        if base is None:
            base = 0  # 无草稿首存：null 与 0 等价
        if not isinstance(doc, dict) or doc.get("format") != "gt_annotate":
            raise ApiError(400, "doc 必须是 gt_annotate 格式")
        current = 0
        if os.path.isfile(draft):
            with open(draft, "r", encoding="utf-8") as fh:
                current = int(json.load(fh).get("version", 0))
        if base != current:
            return self._send_json(409, {"error": "version conflict", "currentVersion": current})
        os.makedirs(_dir, exist_ok=True)
        import datetime
        env = {"version": current + 1, "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
               "doc": doc}
        fd, tmp = tempfile.mkstemp(prefix=".draft-", suffix=".tmp", dir=_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(env, fh, ensure_ascii=False)
            os.replace(tmp, draft)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        self._send_json(200, {"version": current + 1})

    # ---------- 静态 ----------
    _CTYPES = {
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".wasm": "application/wasm",
    }

    def _serve_static(self, path):
        if path == "/":
            path = "/index.html"
        rel = path.lstrip("/")
        if ".." in rel or rel.startswith("/") or "\\" in rel:
            return self._send_json(403, {"error": "forbidden"})
        full = os.path.join(self.dist_root, rel)
        if not os.path.isfile(full):
            # SPA 回退：未知非 API 路径回 index.html
            full = os.path.join(self.dist_root, "index.html")
            if not os.path.isfile(full):
                raise ApiError(404, "dist not built")
        ext = os.path.splitext(full)[1].lower()
        ctype = self._CTYPES.get(ext, "application/octet-stream")
        with open(full, "rb") as fh:
            data = fh.read()
        self._send(200, data, ctype=ctype)


def main(argv=None):
    ap = argparse.ArgumentParser(description="annotator_v2 API server")
    ap.add_argument("--port", type=int, default=8902)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    ap.add_argument("--store-root", default=DEFAULT_STORE_ROOT)
    ap.add_argument("--dist", default=DEFAULT_DIST)
    ap.add_argument("--analysis", action='append', default=[], help='Completed source-bound analysis.json (repeatable)')
    args = ap.parse_args(argv)
    Handler.data_root = os.path.abspath(args.data_root)
    Handler.store_root = os.path.abspath(args.store_root)
    Handler.dist_root = os.path.abspath(args.dist)
    Handler.analysis_store = AnalysisStore(args.analysis, Handler.data_root)
    from body_parts import BodyStore
    Handler.body_store = BodyStore(Handler.analysis_store, Handler.store_root)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"url": "http://%s:%d/" % (args.host, httpd.server_address[1])}), flush=True)
    sys.stderr.write("[annotator_v2] http://%s:%d/ data=%s store=%s dist=%s\n" % (
        args.host, httpd.server_address[1], Handler.data_root, Handler.store_root, Handler.dist_root))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
