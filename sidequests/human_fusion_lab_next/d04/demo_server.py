#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HFUS-D04 Demo 一键服务器

设计目标:
  1. 直接 serve 本目录下的 demo_d04.html (GET / 直接返回 HTML)
  2. 提供 JSON API, 让浏览器按 (variant, sid, frame) 懒加载:
     - GET /api/manifest                        -> MANIFEST_DEMO.json
     - GET /api/frames_index                    -> { sid -> sorted [frame_index, ...] }  (跨所有 variant 取并集)
     - GET /api/variants                        -> [variant 名, ...]
     - GET /api/ledger?variant=V&sid=S&fi=N     -> 该行 JSON, 或 null
     - GET /api/capture_meta?sid=S              -> captures/remote/<S>/meta.json
     - GET /points/<sid>                        -> captures/remote/<sid>/points.bin, 支持 HTTP Range
  3. 预构建帧索引缓存到 ./demo_d04_index.json, 5 秒内启动.

路径根目录 (-root/-r) 默认取:
  本文件位于 <LDIAR>/sidequests/human_fusion_lab_next/d04/demo_server.py
  -> 默认 root = 本文件上三级 (即仓库根 D:/Code/ldiar)
  - d04 evidence root: <root>/docs/human_capture/evidence/2026-10-11_hfus_d04_r1/
  - d03 evidence root: <root>/docs/human_capture/evidence/2026-10-11_hfus_d03_r1/
  - captures root:     <root>/captures/remote/
以上可用命令行参数覆盖 (--d04 / --d03 / --cap).
"""
from __future__ import annotations
import argparse, io, json, os, re, sys, threading, time, urllib.parse
from http import server as http_server
from pathlib import Path
from socketserver import ThreadingTCPServer

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[2]  # <repo>/sidequests/human_fusion_lab_next/d04/demo_server.py -> <repo>

LEDGER_RE = re.compile(r"^D04_(.+?)_(cap_\d{8}_\d{6})\.jsonl$")
D03_RE    = re.compile(r"^([AB])_(cap_\d{8}_\d{6})\.jsonl$")

# ---------- 全局数据 (单进程内常驻) ----------
class State:
    def __init__(self, root: Path, d04: Path, d03: Path, cap: Path):
        self.root = root
        self.d04 = d04; self.d03 = d03; self.cap = cap
        self.demo_html_path = HERE / "demo_d04.html"
        self.index_cache_path = HERE / "demo_d04_index.json"
        self.manifest_cache: dict | None = None
        # variant -> sid -> [fi,...]  以及 "D03:A" / "D03:B" 特例变体
        self.frames_index: dict[str, dict[str, list[int]]] = {}
        self.sids: set[str] = set()
        self.variants: list[str] = []
        self._built = False
        # 每帧行缓存 (避免重复扫同一文件)
        # key: (variant_key, sid, fi)  -> dict | None;  variant_key in variants or "A"/"B" for d03
        self._row_cache: dict[tuple[str, str, int], dict | None] = {}
        self._cache_lock = threading.Lock()
        # 文件级行索引: path -> { fi -> parsed row }; 首次完整扫一次后所有 (sid,fi) 查询都走内存
        self._file_rows: dict[str, dict[int, dict]] = {}
        self._file_lock = threading.Lock()

    # ---------- 索引构建 ----------
    def _ledger_paths(self) -> list[tuple[str, str, Path, str]]:
        """返回 (variant_key, sid, path, channel) ; channel in {'d04','d03:A','d03:B'}"""
        out: list[tuple[str, str, Path, str]] = []
        # D04 变体
        runs_dir = self.d04 / "runs"
        if runs_dir.is_dir():
            for variant_dir in sorted(runs_dir.iterdir()):
                if not variant_dir.is_dir(): continue
                vname = variant_dir.name
                for f in sorted(variant_dir.glob("*.jsonl")):
                    m = LEDGER_RE.match(f.name)
                    if not m: continue
                    # m.group(1)=variantFromFileName, m.group(2)=sid
                    sid = m.group(2)
                    out.append((vname, sid, f, "d04"))
        # D03 A/B 旧版 ledger
        if self.d03.is_dir():
            for f in sorted(self.d03.glob("*.jsonl")):
                m = D03_RE.match(f.name)
                if not m: continue
                mode, sid = m.group(1), m.group(2)
                out.append((f"D03:{mode}", sid, f, f"d03:{mode}"))
        return out

    def _scan_file_frames(self, path: Path) -> list[int]:
        """流式扫 jsonl, 只取 frame_index"""
        fis = []
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line: continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    fi = row.get("frame_index")
                    if isinstance(fi, int):
                        fis.append(fi)
        except FileNotFoundError:
            return []
        return fis

    def build_index(self, force: bool = False):
        if self._built and not force:
            return
        t0 = time.time()
        # 先试缓存
        if self.index_cache_path.exists() and not force:
            try:
                with self.index_cache_path.open("r", encoding="utf-8") as fh:
                    cached = json.load(fh)
                if cached.get("version") == 1 and "frames_index" in cached and "variants" in cached:
                    self.frames_index = cached["frames_index"]
                    self.variants = cached["variants"]
                    self.sids = set(cached.get("sids", []))
                    self._built = True
                    print(f"[demo_server] 索引缓存命中: {self.index_cache_path.name} "
                          f"({sum(len(v2) for v2 in self.frames_index.values())} entries)", flush=True)
                    return
            except Exception as e:
                print(f"[demo_server] 缓存读取失败, 重建: {e}", flush=True)
        # 重建
        idx: dict[str, dict[str, list[int]]] = {}
        sids: set[str] = set()
        variant_set: list[str] = []
        for vkey, sid, path, channel in self._ledger_paths():
            fis = self._scan_file_frames(path)
            if not fis:
                continue
            fis = sorted(set(fis))
            idx.setdefault(vkey, {})[sid] = fis
            sids.add(sid)
        # variants: 只列 d04 真实 variant (D03:A / D03:B 通过 curLedgers 走另一通道, 不需要列进 variant 下拉)
        for vkey in idx.keys():
            if not vkey.startswith("D03:"):
                variant_set.append(vkey)
        variant_set.sort()
        self.frames_index = idx
        self.sids = sids
        self.variants = variant_set
        self._built = True
        # 落盘缓存
        try:
            payload = {
                "version": 1,
                "built_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "sids": sorted(sids),
                "variants": variant_set,
                "frames_index": idx,
            }
            with self.index_cache_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
        except Exception as e:
            print(f"[demo_server] 缓存写盘失败(忽略): {e}", flush=True)
        print(f"[demo_server] 索引重建完成, 耗时 {time.time()-t0:.1f}s, sids={len(sids)}, variants={variant_set}", flush=True)

    # ---------- 按需取一帧 ledger 行 ----------
    def _load_file_rows(self, path: Path) -> dict[int, dict]:
        """完整扫一次 jsonl, 把 {fi: row} 放内存缓存; 之后所有 (fi) 查询都 O(1)."""
        key = str(path)
        with self._file_lock:
            if key in self._file_rows:
                return self._file_rows[key]
        frames: dict[int, dict] = {}
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    fi = row.get("frame_index")
                    if isinstance(fi, int):
                        frames[fi] = row
        except FileNotFoundError:
            pass
        with self._file_lock:
            self._file_rows[key] = frames
        return frames

    def _find_row_in_file(self, path: Path, fi: int) -> dict | None:
        frames = self._load_file_rows(path)
        return frames.get(fi)

    def _resolve_ledger_path(self, variant_key: str, sid: str) -> Path | None:
        """variant_key 是 'base'/'point30_only'/... 或者 'A'/'B' (走 d03); 该函数返回应去哪个 jsonl 里找."""
        if variant_key == "A":
            return self.d03 / f"A_{sid}.jsonl"
        if variant_key == "B":
            return self.d03 / f"B_{sid}.jsonl"
        # D04 变体
        return self.d04 / "runs" / variant_key / f"D04_{variant_key}_{sid}.jsonl"

    def get_row(self, variant_key: str, sid: str, fi: int) -> dict | None:
        cache_key = (variant_key, sid, fi)
        with self._cache_lock:
            if cache_key in self._row_cache:
                return self._row_cache[cache_key]
        path = self._resolve_ledger_path(variant_key, sid)
        row = self._find_row_in_file(path, fi) if path is not None else None
        with self._cache_lock:
            self._row_cache[cache_key] = row
        return row

    def get_manifest(self) -> dict | None:
        if self.manifest_cache is not None:
            return self.manifest_cache
        p = self.d04 / "MANIFEST_DEMO.json"
        if not p.exists():
            self.manifest_cache = None
            return None
        try:
            self.manifest_cache = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            self.manifest_cache = None
        return self.manifest_cache

    # ---------- captures ----------
    def cap_dir(self, sid: str) -> Path:
        return self.cap / sid

    def get_capture_meta(self, sid: str) -> dict | None:
        p = self.cap_dir(sid) / "meta.json"
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def capture_points_path(self, sid: str) -> Path | None:
        p = self.cap_dir(sid) / "points.bin"
        return p if p.exists() else None

STATE: State | None = None

# ---------- HTTP Handler ----------
class Handler(http_server.BaseHTTPRequestHandler):
    server_version = "HFUS-D04-Demo/1.0"

    def log_message(self, fmt, *args):
        # 静默一点, 错误仍然进 stderr
        pass

    # --- helpers ---
    def _json(self, code: int, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _text(self, code: int, body: bytes, content_type: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code: int, msg: str):
        self._json(code, {"error": msg})

    # --- GET ---
    def do_GET(self):
        if STATE is None:
            self._err(503, "server not ready")
            return
        try:
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)
        except Exception as e:
            self._err(400, f"bad url: {e}")
            return
        try:
            if path in ("/", "/demo_d04.html", "/index.html"):
                body = STATE.demo_html_path.read_bytes()
                self._text(200, body, "text/html; charset=utf-8")
                return
            if path == "/api/manifest":
                m = STATE.get_manifest()
                self._json(200 if m is not None else 404, m if m is not None else {"error": "no manifest"})
                return
            if path == "/api/frames_index":
                STATE.build_index()
                # 抽换成 sid -> [fi] 跨 variant 并集
                merged: dict[str, set[int]] = {}
                for vkey, smap in STATE.frames_index.items():
                    for sid, fis in smap.items():
                        merged.setdefault(sid, set()).update(fis)
                out = {s: sorted(fs) for s, fs in sorted(merged.items())}
                self._json(200, {"sids": out, "variants": STATE.variants})
                return
            if path == "/api/variants":
                STATE.build_index()
                self._json(200, {"variants": STATE.variants})
                return
            if path == "/api/ledger":
                STATE.build_index()
                v = (qs.get("variant") or [None])[0]
                sid = (qs.get("sid") or [None])[0]
                fi_s = (qs.get("fi") or [None])[0]
                if not (v and sid and fi_s is not None):
                    self._err(400, "missing variant/sid/fi")
                    return
                try:
                    fi = int(fi_s)
                except ValueError:
                    self._err(400, "fi must be int")
                    return
                row = STATE.get_row(v, sid, fi)
                self._json(200 if row is not None else 404, row if row is not None else {"error": "not found"})
                return
            if path == "/api/capture_meta":
                sid = (qs.get("sid") or [None])[0]
                if not sid:
                    self._err(400, "missing sid")
                    return
                m = STATE.get_capture_meta(sid)
                self._json(200 if m is not None else 404, m if m is not None else {"error": "no meta"})
                return
            if path.startswith("/points/"):
                sid = path[len("/points/"):]
                # 简单防目录穿越
                if "/" in sid or ".." in sid:
                    self._err(400, "bad sid")
                    return
                p = STATE.capture_points_path(sid)
                if p is None:
                    self._err(404, "no points.bin")
                    return
                self._serve_range(p)
                return
            self._err(404, f"unknown: {path}")
        except Exception as e:
            self._err(500, f"server error: {e}")

    # --- Range for points.bin ---
    def _serve_range(self, path: Path):
        size = path.stat().st_size
        rng = self.headers.get("Range")
        if not rng:
            # 全量, 直接 stream
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with path.open("rb") as fh:
                _shutil_copy(fh, self.wfile)
            return
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        if not m:
            self.send_response(416); self.end_headers(); return
        start_s, end_s = m.group(1), m.group(2)
        if start_s == "" and end_s == "":
            self.send_response(416); self.end_headers(); return
        if start_s == "":
            # suffix range
            n = int(end_s)
            start = max(0, size - n); end = size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
        if start > end or start >= size:
            self.send_response(416); self.end_headers(); return
        end = min(end, size - 1)
        length = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        with path.open("rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(65536, remaining))
                if not chunk: break
                self.wfile.write(chunk)
                remaining -= len(chunk)

def _shutil_copy(src, dst, chunk: int = 1 << 20):
    while True:
        b = src.read(chunk)
        if not b: return
        dst.write(b)

# ---------- 启动 ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--d04", default=None)
    ap.add_argument("--d03", default=None)
    ap.add_argument("--cap", default=None)
    ap.add_argument("--port", type=int, default=8907)
    ap.add_argument("--rebuild", action="store_true", help="忽略缓存强制重建索引")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    d04 = Path(args.d04).resolve() if args.d04 else root / "docs/human_capture/evidence/2026-10-11_hfus_d04_r1"
    d03 = Path(args.d03).resolve() if args.d03 else root / "docs/human_capture/evidence/2026-10-11_hfus_d03_r1"
    cap = Path(args.cap).resolve() if args.cap else root / "captures/remote"

    global STATE
    STATE = State(root=root, d04=d04, d03=d03, cap=cap)

    t0 = time.time()
    STATE.build_index(force=args.rebuild)
    print(f"[demo_server] 启动参数: root={root}", flush=True)
    print(f"[demo_server]   d04={d04}", flush=True)
    print(f"[demo_server]   d03={d03}", flush=True)
    print(f"[demo_server]   cap={cap}", flush=True)
    print(f"[demo_server] sids={sorted(STATE.sids)}", flush=True)
    print(f"[demo_server] variants={STATE.variants}", flush=True)
    print(f"[demo_server] 索引耗时 {time.time()-t0:.1f}s", flush=True)

    # 后台静默预读所有 ledger jsonl 到内存 (不影响 listen 启动)
    def _warm():
        t1 = time.time()
        n_files = 0
        total_rows = 0
        for vkey, sid, path, channel in STATE._ledger_paths():
            try:
                frames = STATE._load_file_rows(path)
                n_files += 1
                total_rows += len(frames)
            except Exception:
                pass
        print(f"[demo_server] 预热完成: {n_files} 文件 / {total_rows} 行, 耗时 {time.time()-t1:.1f}s", flush=True)
    threading.Thread(target=_warm, daemon=True).start()

    class Threading(ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = True

    addr = ("", args.port)
    with Threading(addr, Handler) as httpd:
        url = f"http://127.0.0.1:{args.port}/?AUTO=1"
        print(f"[demo_server] listening on {url}", flush=True)
        print(f"[demo_server] 请浏览器打开: {url}", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[demo_server] bye", flush=True)

if __name__ == "__main__":
    main()
