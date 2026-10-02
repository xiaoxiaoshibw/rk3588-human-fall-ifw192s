# -*- coding: utf-8 -*-
"""HR-01: PC 侧轮询拉取板端 ready 会话（控制面 HTTP + 数据面 scp）。

流程（README §1/§8 状态机）：
  GET /api/v1/sessions → 挑 state==ready 且 download_requested 且非 transferred
  → PATCH state=transferring（server 状态机决定成败，防重叠）
  → scp -l 限速拉 meta.json/points.bin（.part 落盘，全绿后一步换名）
  → meta.json 静态契约校验 + sha256 校验（按 frame offset/count 实际点区，
    与 bag2session 的 write 动线同源）
  → PATCH extra.transferred=true + state=transferred 回报板端。

传输前用 `ssh du` 预判盘余量，防止 100M 链路把时间浪费在注定失败的传输上。

只 stdlib + 系统 ssh/scp（Win11 自带 OpenSSH；`scp -l` 单位 Kbit/s，
以接近 70Mbit=70000 Kbit/s 限速，给 100M 链路的实时预览留 30%）。
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

import config as C

# sessions.json 用容器内视角记路径（/root/catkin_ws/captures_remote/），
# 板上已建 symlink 把它指到宿主机 SSD /mnt/captures/captures_remote/；
# scp 走宿主机必须走 /mnt/captures/ 前缀，这里做字面映射。
_CONTAINER_PREFIX = "/root/catkin_ws/captures_remote/"
_HOST_PREFIX = "/mnt/captures/captures_remote/"


def _host_path(paths):
    """把 sessions.json 里的容器内路径映射成宿主/sshd 可 scp 的路径。"""
    if paths.startswith(_CONTAINER_PREFIX):
        return _HOST_PREFIX + paths[len(_CONTAINER_PREFIX):]
    return paths

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


# ---- scp / ssh（数据面，容错部分下载） -------------------------------------


def _dst_tmp_path(dest_dir, name):
    return os.path.join(dest_dir, name + ".part")


def _scp_one(remote_path, local_path, bwlimit_kbit=None):
    cmd = ["scp", "-p"]
    if bwlimit_kbit:
        cmd += ["-l", str(bwlimit_kbit)]
    cmd += ["%s:%s" % (C.SSH_TARGET, remote_path), local_path]
    return subprocess.call(cmd, timeout=C.SCP_TIMEOUT_S)


def _ssh_du_bytes(remote_paths):
    """对远端 afford 文件估字节。任一失败/为 0 就拒绝，说服 du 返回 0。

    防转移：size<=0 时本轮直接放回，避免把时间耗在注定崩的传输上。
    """
    quoted = " ".join("'%s'" % p.replace("'", "'\\''") for p in remote_paths)
    cmd = ["ssh", "-o", "BatchMode=yes", C.SSH_TARGET,
           "du -cb -- %s 2>/dev/null | tail -n1 | awk '{print $1}'" % quoted]
    out = subprocess.check_output(cmd, timeout=C.SSH_TIMEOUT_S).decode().strip()
    return int(out) if out.isdigit() else 0


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


def _remote_files(session):
    meta_remote = _host_path(session["meta_json_path"])
    bin_remote = _host_path(session["points_bin_path"])
    return [(meta_remote, "meta.json"), (bin_remote, "points.bin")]


def transfer_one(session, http, ssh_du, scp, dest_root, bwlimit_kbit, log):
    """返回 True=已置 transferred,False=留给下一轮重试；所有失败已就地清理 .part。

    http/ssh_du/scp 用参数注入，单测混合你方便换，代码本体保持 1 层不抽象。
    """
    sid = session["session_id"]
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
        try:
            http("PATCH", "/api/v1/sessions/%s" % sid,
                 {"state": "ready", "extra": {"error": "hr01: %s" % reason}})
        except Exception:
            pass
        log("FAIL %s: %s" % (sid, reason))
        return False

    # 1) 抢占：状态机硬约束，只有 ready→transferring 会成功
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
        # 2) 盘余量预估：先拒绝总比下到一半发现盘满好
        files = _remote_files(session)
        remote_paths = [r for r, _ in files]
        size = ssh_du(remote_paths)
        if size <= 0:
            return _fail("du 拿不到远端大小")
        free = C.free_bytes(dest_root)
        if free < size + C.SPACE_SLACK_BYTES:
            return _fail("盘余量 %dB 装不下会话 %dB（含 slack）" % (free, size))

        os.makedirs(dest_dir, exist_ok=True)

        # 3) 逐文件 scp；每个文件下来立刻落盘校验，失败立即清 .part 退回
        meta_path = None
        bin_path = None
        for remote, name in files:
            tmp = _dst_tmp_path(dest_dir, name)
            if scp(remote, tmp) != 0:
                return _fail("scp %s 失败" % name)
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
    finally:
        # 非 success 路径统一再扫余下 .part；成功路径上方已逐文件清过
        _cleanup_parts()


# ---- 主循环 -----------------------------------------------------------------


def process_session(sid, dest_root=None, log=print):
    """拉单个 ready 会话（回放器「同步」按钮的子进程入口）。返回 True=已 transferred。"""
    try:
        sess = _http_json("GET", "/api/v1/sessions/%s" % sid)
    except BaseException as exc:
        log("FAIL %s: 取会话失败: %s" % (sid, exc))
        return False
    return transfer_one(sess, _http_json, _ssh_du_bytes,
                        lambda r, l: _scp_one(r, l, C.SCP_LIMIT_KBIT),
                        dest_root or C.DEST_ROOT, C.SCP_LIMIT_KBIT, log)


def run(args):
    dest_root = args.dest or C.DEST_ROOT
    os.makedirs(dest_root, exist_ok=True)
    bwlimit_kbit = args.kbit

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
        ok = transfer_one(
            job, _http_json,
            lambda paths: _ssh_du_bytes(paths),
            lambda remote, local: _scp_one(remote, local, bwlimit_kbit),
            dest_root, bwlimit_kbit, log)
        transferred += 1 if ok else 0
        if args.once:
            break
    return transferred


def cli(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--once", action="store_true", help="只拉一轮后退出（默认常驻轮询）")
    p.add_argument("--sid", metavar="SID", help="只拉指定会话（回放器内部调用）")
    p.add_argument("--interval", type=float, default=C.POLL_INTERVAL_S, help="轮询间隔秒")
    p.add_argument("--kbit", type=int, default=C.SCP_LIMIT_KBIT, help="scp -l 限速 (Kbit/s)")
    p.add_argument("--dest", default=C.DEST_ROOT, help="本地落盘根目录")
    args = p.parse_args(argv)
    if args.sid:
        return 0 if process_session(args.sid, args.dest) else 1
    transferred = run(args)


if __name__ == "__main__":
    sys.exit(cli())
