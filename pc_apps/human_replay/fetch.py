# -*- coding: utf-8 -*-
"""HR-01: PC 侧轮询拉取板端 ready 会话（控制面 + 数据面全 HTTP，免 SSH）。

流程（README §1/§8 状态机）：
  GET /api/v1/sessions → 挑 state==ready 且 download_requested 且非 transferred
  → PATCH state=transferring（server 状态机决定成败，防重叠）
  → HTTP 流式拉 meta.json/points.bin（.part 落盘，全绿后一步换名）
  → meta.json 静态契约校验 + sha256 校验（按 frame offset/count 实际点区，
    与 bag2session 的 write 动线同源）
  → PATCH extra.transferred=true + state=transferred 回报板端。

数据面走 capture_server 的 /api/v1/sessions/<sid>/files/<name>（8766）：
同网段任何 PC 都无需 SSH key；限速在板端（download_limit_kbit，默认 ≈800Mbit，
2026-10-14 起；旧值 ≈70Mbit 是百兆链路时代给实时预览留余量用的）。

传输前用 HEAD Content-Length 预判盘余量，防止把时间浪费在注定失败的传输上。

只 stdlib（urllib 流式）。
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request

import config as C

# ---- HTTP（控制面，KB 级） -------------------------------------------------


def _http_json(method, path, body=None, timeout=None):
    timeout = timeout if timeout is not None else C.HTTP_TIMEOUT_S
    req = urllib.request.Request(C.BOARD_URL + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
        payload = resp.read()
        return json.loads(payload) if payload else {}


def _http_error_status(exc):
    """从 urllib 的 HTTPError 里抠 status code 和 server 的 error payload。"""
    status = getattr(exc, "code", None)
    detail = ""
    try:
        payload = exc.read()
        detail = payload.decode("utf-8", "replace")[:200]
    except BaseException:
        pass
    return status, detail


def _file_url(sid, name):
    return "%s/api/v1/sessions/%s/files/%s" % (C.BOARD_URL, sid, name)


def _http_size(sid, name):
    """HEAD 拿远端文件字节数；失败/无长度返回 0（调用方据此放弃本轮）。"""
    req = urllib.request.Request(_file_url(sid, name), method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=C.HTTP_TIMEOUT_S) as resp:
            return int(resp.headers.get("Content-Length") or 0)
    except (urllib.error.URLError, OSError, ValueError):
        return 0


def _http_download(sid, name, local_path):
    """流式下载单文件到 local_path（.part）；落盘字节数与 Content-Length 不符也算失败。"""
    try:
        with urllib.request.urlopen(_file_url(sid, name),
                                    timeout=C.DOWNLOAD_TIMEOUT_S) as resp:
            expect = int(resp.headers.get("Content-Length") or 0)
            with open(local_path, "wb") as fh:
                shutil.copyfileobj(resp, fh, 1 << 20)
                fh.flush()
                os.fsync(fh.fileno())
                written = fh.tell()
            return written > 0 and written == expect
    except (urllib.error.URLError, OSError, ValueError):
        return False


# ---- 预选（纯函数，单测量靶） ----------------------------------------------


def pick_sessions(sessions_json):
    """从 GET /sessions 的 payload 里挑本轮可拉的新会话（新旧顺序）。

    条件（HR-01 契约）：
    - state == "ready"
    - download_requested 为真（兼容 None/False/缺失）
    - transferred 不为真（兼容 None/False/缺失）
    - 至少带 meta_json_path 与 points_bin_path（你方可能字段缺失就直接跳过）
    """
    ready = []
    for s in sessions_json.get("sessions", []):
        if s.get("state") != "ready":
            continue
        if not s.get("download_requested"):
            continue
        if s.get("transferred"):
            continue
        if not s.get("meta_json_path") or not s.get("points_bin_path"):
            continue
        ready.append(s)
    # 稳定拉取顺序：created_iso 升序 → session_id
    ready.sort(key=lambda s: (s.get("created_iso", ""), s.get("session_id", "")))
    return ready


def select_job(sessions_json):
    """返回本轮的会话；并发下仅靠 PATCH state=transferring 判定。"""
    jobs = pick_sessions(sessions_json)
    return jobs[0] if jobs else None


# ---- 落盘小工具 -------------------------------------------------------------


def _dst_tmp_path(dest_dir, name):
    return os.path.join(dest_dir, name + ".part")


# ---- 校验（meta 静态 + bin 实际点区 sha256） -------------------------------


def _walk_points(frames):
    """frame 的点索引区间 (started, ended)；总数是最后一个 frame 的终点。"""
    pts = [0]
    for f in frames:
        start = int(f["offset_points"])
        end = start + int(f["count_points"])
        pts.append(end)
    return pts


def _validate_meta(meta, meta_name, bin_size):
    """静态契约：不匹配 README §2/D3 就抛错，客侧拒绝认领。

    为什么按实拍检查,而不是抄一段文档：你方写死了 frame_layout=16B 旧版,
    但板上真实 meta 是 point_stride_bytes=28 + point_layout.fields=[...,ring,timestamp]。
    显式拒绝避免 HR-02 读到 28B 变体时炸出难懂的 ValueError。
    """
    if meta.get("format") != "human_capture_session" or int(meta.get("format_version", 0) or 0) != 1:
        raise ValueError("meta.format/version 不识别")
    if meta.get("point_file") != "points.bin":
        raise ValueError("point_file 非 points.bin: %r" % meta.get("point_file"))
    layout = meta.get("point_layout") or {}
    if layout.get("endian") != "little":
        raise ValueError("endian 非 little")
    if meta.get("point_stride_bytes") != 28:
        raise ValueError("point_stride_bytes 非 28: %r" % meta.get("point_stride_bytes"))
    if layout.get("stride_bytes") != 28 or layout.get("fields") != ["x", "y", "z", "intensity", "ring", "timestamp"]:
        raise ValueError("point_layout 非 28B 契约 x,y,z,intensity,ring,timestamp")
    frames = meta.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ValueError("frames 为空")
    pts = _walk_points(frames)
    # 单调不減 + 终点不超 bin 实际大小（允许 bin 后端有少量无效/收尾填充）
    last = 0
    for end in pts:
        if end < last:
            raise ValueError("frames 点索引非单调")
        last = end
    used_bytes = pts[-1] * 28
    if used_bytes > bin_size:
        raise ValueError("frames 点总数越界：需要 %dB > bin %dB" % (used_bytes, bin_size))
    return pts[-1] * 28


def _sha256_of_points(path, used_bytes, total_points):
    """按 28B/点、只算 frame 实际点区（时序的 bag2session 点数据末尾可能冭 0）。"""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        remaining = used_bytes
        while remaining:
            block = fh.read(min(1 << 20, remaining))
            if not block:
                raise ValueError("points.bin 读不到 %d 字节实际点区" % used_bytes)
            h.update(block)
            remaining -= len(block)
    return h.hexdigest()


def _local_verify(meta_path, bin_path):
    with open(meta_path, "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    bin_size = os.path.getsize(bin_path)
    used_bytes = _validate_meta(meta, os.path.basename(meta_path), bin_size)
    digest = _sha256_of_points(bin_path, used_bytes, meta.get("total_points", 0))
    return meta, digest


# ---- 单个会话一轮的工作 -----------------------------------------------------


def transfer_one(session, http, http_size, download, dest_root, log):
    """返回 True=文件已落地,False=留给下一轮重试；所有失败已就地清理 .part。

    http/http_size/download 参数注入，单测好换，代码本体保持 1 层不抽象。
    任何未预期异常也必走 _fail 退回 ready——绝不把会话卡在 transferring。
    state=transferred 的会话走只读复制（别的 PC 拉过/本机删过再要）：文件直下，
    不动状态机——transferred 只能转 purged，PATCH transferring 必被板端 409 拒绝。
    """
    sid = session["session_id"]
    readonly = session.get("state") == "transferred"
    dest_dir = os.path.join(dest_root, sid)
    meta_tmp = _dst_tmp_path(dest_dir, "meta.json")
    bin_tmp = _dst_tmp_path(dest_dir, "points.bin")

    def _cleanup_parts():
        for p in (meta_tmp, bin_tmp):
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass

    def _fail(reason):
        # 任何一步失败：清 .part、退回 ready、留下错误证据；下一轮会重新挑中本 session
        _cleanup_parts()
        if not readonly:
            try:
                http("PATCH", "/api/v1/sessions/%s" % sid,
                     {"state": "ready", "extra": {"error": "hr01: %s" % reason}})
            except Exception:
                pass
        log("FAIL %s: %s" % (sid, reason))
        return False

    # 1) 抢占：状态机硬约束，只有 ready→transferring 会成功（只读复制不抢）
    if not readonly:
        try:
            http("PATCH", "/api/v1/sessions/%s" % sid, {"state": "transferring"})
        except urllib.error.HTTPError as exc:
            status, _ = _http_error_status(exc)
            if status == 409:
                log("SKIP %s: 已被他人抢走（409）" % sid)
            elif status == 404:
                log("SKIP %s: 板上会话已被删" % sid)
            else:
                log("SKIP %s: PATCH transferring 失败: %s" % (sid, exc))
            return False

    try:
        # 2) 盘余量预估：HEAD 拿两文件大小；先拒绝总比下到一半发现盘满好
        files = ("meta.json", "points.bin")
        sizes = [http_size(sid, name) for name in files]
        if min(sizes) <= 0:
            return _fail("HEAD 拿不到远端大小")
        total = sum(sizes)
        free = C.free_bytes(dest_root)
        if free < total + C.SPACE_SLACK_BYTES:
            return _fail("盘余量 %dB 装不下会话 %dB（含 slack）" % (free, total))

        os.makedirs(dest_dir, exist_ok=True)

        # 3) 逐文件下载；每个文件下来立刻落盘校验，失败立即清 .part 退回
        meta_path = None
        bin_path = None
        for name in files:
            tmp = _dst_tmp_path(dest_dir, name)
            if not download(sid, name, tmp):
                return _fail("下载 %s 失败" % name)
            final = os.path.join(dest_dir, name)
            # meta 下完先初步 parse；bin 下完再统一 sha256 校验
            if name == "meta.json":
                try:
                    with open(tmp, "r", encoding="utf-8") as fh:
                        json.load(fh)
                except BaseException as exc:
                    return _fail("meta.json parse 失败: %s" % exc)
                meta_path = final
            else:
                bin_path = final
            try:
                os.replace(tmp, final)
            except OSError as exc:
                return _fail("换名→%s 失败: %s" % (name, exc))

        # 4) 静态 + sha256
        try:
            meta, digest = _local_verify(meta_path, bin_path)
        except BaseException as exc:
            # 客侧不认领：毁掉板侧还会重复给我破损数据——错误入库不动终态
            return _fail("校验失败: %s" % exc)
        log("OK   %s: meta_points=%s digest=%s" % (sid, meta.get("total_points"), digest[:16]))

        # 5) 回报板端：extra.transferred=true + state=transferred（一次补丁）
        if not readonly:
            try:
                http("PATCH", "/api/v1/sessions/%s" % sid,
                     {"state": "transferred", "extra": {"transferred": True}})
            except urllib.error.HTTPError as exc:
                # 极端竞争：你方板端在 transferred 前会话被删/FIFO 被清了；本地已验收
                status, detail = _http_error_status(exc)
                log("WARN %s: 本地已验收但板回报失败(%s %s)" % (sid, status, detail))
                _cleanup_parts()
                return False
        return True
    except BaseException as exc:
        # 兜底：任何未预期异常都必须退回 ready（旧版 ssh 异常就让会话卡死在 transferring）
        return _fail("异常 %s: %s" % (type(exc).__name__, exc))
    finally:
        # 非 success 路径统一再扫余下 .part；成功路径上方已逐文件清过
        _cleanup_parts()


def recover(sid):
    """人工把板端卡在 transferring 的会话退回 ready（面板「退回重试」调用）。

    motivation：下载客户端在传输中被关/崩溃时，没人跑 _fail 的自动回退，
    板端会话会永远停在 transferring，后续同步在抢占一步被 409 拒。
    仅当板端当前确实是 transferring 时才 PATCH（状态机允许的回退），
    返回 (ok, reason)；已 ready/已 transferred 等状态一律拒绝。
    """
    try:
        sess = _http_json("GET", "/api/v1/sessions/%s" % sid)
    except urllib.error.HTTPError as exc:
        status, _ = _http_error_status(exc)
        if status == 404:
            return False, "板端无此会话（可能已被删）"
        return False, "取会话失败(%s)" % status
    except BaseException as exc:
        return False, "取会话失败: %s" % exc
    state = sess.get("state")
    if state != "transferring":
        return False, "板端状态为 %s，无需退回" % (state or "未知")
    try:
        _http_json("PATCH", "/api/v1/sessions/%s" % sid, {"state": "ready"})
    except urllib.error.HTTPError as exc:
        status, detail = _http_error_status(exc)
        return False, "退回失败(%s): %s" % (status, detail)
    except BaseException as exc:
        return False, "退回失败: %s" % exc
    return True, ""


# ---- 主循环 -----------------------------------------------------------------


def process_session(sid, dest_root=None, log=print):
    """拉单个会话（回放器「同步」按钮的入口）。返回 True=文件已落地。

    ready 走状态机；transferred 只读复制（板端已回传但本机没有：删过再要/别的 PC 拉过）。
    """
    try:
        sess = _http_json("GET", "/api/v1/sessions/%s" % sid)
    except BaseException as exc:
        log("FAIL %s: 取会话失败: %s" % (sid, exc))
        return False
    return transfer_one(sess, _http_json, _http_size, _http_download,
                        dest_root or C.DEST_ROOT, log)


def run(args):
    dest_root = args.dest or C.DEST_ROOT
    os.makedirs(dest_root, exist_ok=True)

    def log(msg):
        print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)

    transferred = 0
    while True:
        try:
            sessions = _http_json("GET", "/api/v1/sessions")
        except BaseException as exc:
            log("轮询失败: %s" % exc)
            sessions = {"sessions": []}
        job = select_job(sessions)
        if job is None:
            if args.once:
                break
            time.sleep(args.interval)
            continue
        ok = transfer_one(job, _http_json, _http_size, _http_download,
                          dest_root, log)
        transferred += 1 if ok else 0
        if args.once:
            break
    return transferred


def cli(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--once", action="store_true", help="只拉一轮后退出（默认常驻轮询）")
    p.add_argument("--sid", metavar="SID", help="只拉指定会话（回放器内部调用）")
    p.add_argument("--interval", type=float, default=C.POLL_INTERVAL_S, help="轮询间隔秒")
    p.add_argument("--dest", default=C.DEST_ROOT, help="本地落盘根目录")
    args = p.parse_args(argv)
    if args.sid:
        return 0 if process_session(args.sid, args.dest) else 1
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(cli())
