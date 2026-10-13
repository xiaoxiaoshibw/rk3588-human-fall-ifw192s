# -*- coding: utf-8 -*-
"""gt_server.py — HUMAN-GT-ANNOTATOR-R1 GT 标注持久化 + 自动建议 + 冻结导出。

挂在 human_replay_lib.py Handler 的 /api/gt/* 路由下（plugin in-proc 风格，
与 validation.handle / leveling.handle 一致）。

目录约定（只碰这些；不动 captures/remote 原始会话一字节）：
    pc_apps/human_replay/gt_store/<sid>/
        draft.json            # 最近一次保存的工作草稿（含全部对象）
        draft.json.tmp        # 原子写中间态
        history.jsonl         # 每次保存追加一行（崩溃重放 / 审计）
        GT_V<n>.json          # 冻结版本；生成 SHA 存入 manifest
        manifest.json         # {versions:[{version,sha256,object_count,frozen_at}]}
    pc_apps/human_replay/gt_store/<sid>/AUTO_CANDIDATES.json
        # 上游 gt_workbench_export.py --auto 的落盘副本（可选，服务端预标注路径）
    pc_apps/human_replay/gt_store/GT_POS.json / GT_FURN_HARD_NEG.json / SPLITS.json
        # 会话冻结后由 export() 产出

安全性：
  * 原子写 .tmp → fsync → os.replace；崩溃不留半截 JSON。
  * 写前快照比对 — 若 draft 已存在且 sha 变（别的写者动了），409 拒绝。
  * 冻结版本号 = manifest 现存版本 +1；GT_V*.json 只增不改。
  * /api/gt/auto 触发 human_core/engine FUSION 预跑（伪标）+ AUTO_CANDIDATES 渲染；
     产物永远标 source=model / PSEUDO_LABEL。
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

import config as _hr_config  # 同目录；SID_RE 白名单单点收敛

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))

# STORE 覆盖：HR_STORE_DIR 单独生效（板端模式由 deploy 脚本设它；
# 测试/隔离模式也直接设它，不必 BOARD_MODE=1）。不设则回落 HERE/gt_store。
def _default_store():
    if os.environ.get("HR_STORE_DIR"):
        return os.environ["HR_STORE_DIR"]
    return os.path.join(HERE, "gt_store")

STORE = _default_store()
# 白名单与 config.SID_RE 收敛（synth_* 等 PC 生成会话同样可标）；防穿越语义不变。
SID_RE = _hr_config.SID_RE

# 3 类终态导出文件名（与工单 STEP 6 兼容；GT_POS/FURN_HARD_NEG/SPLITS 由人工冻结产生）
FINAL_EXPORTS = (
    "GT_POS.json",
    "GT_FURN_HARD_NEG.json",
    "SPLITS.json",
)

# 冻结版别名侧表文件名（不写进 manifest.json — 后者带 sha256 登记，
# 加字段会破坏序列化内容上的信任边界；别名存独立 doc，identity 仍是 sha）。
ALIASES_NAME = "aliases.json"

# 别名字端长度上限（与服务端板端校验对齐；PC/板一致才不变）
ALIAS_MAX_LEN = 60

# aliases.json 形态：{"draft": str|None, "versions": {"V1": str|None, ...}}
def _empty_aliases():
    return {"draft": None, "versions": {}}

# FIX-AUDIT-R2-Q7#6: freeze 并发锁,防 TOCTOU 同号覆盖
_freeze_lock = threading.Lock()

# FIX-REVIEW-M1: alias 读-改-写锁；无锁时两客户端并发 set_alias 会 lost-update。
_alias_lock = threading.Lock()


def get_store_dir():
    return STORE


def export_whitelist_ok(sid, name, path):
    """下载/读白名单判定。无 name 时只看 sid 合法性。"""
    if sid is not None and not _sid_ok(sid):
        return False, "sid 非法"
    if name is None:
        return True, ""
    if name in ("draft.json", "manifest.json", "AUTO_CANDIDATES.json", "fusion_frames.json",
                ALIASES_NAME):
        return True, ""
    if name in FINAL_EXPORTS:
        return True, ""
    if name.startswith("GT_V") and name.endswith(".json"):
        return True, ""
    return False, "文件名不在白名单"


def list_exports(store_dir, sid=None):
    """列可下载文件：sid=None→全局；否则该 store 下的全部 GT 产物。"""
    if not os.path.isdir(store_dir):
        return {"files": [], "sessions": []}
    if sid is None:
        sessions = sorted(
            d for d in os.listdir(store_dir) if os.path.isdir(os.path.join(store_dir, d)))
        files = sorted(f for f in FINAL_EXPORTS if os.path.isfile(os.path.join(store_dir, f)))
        return {"files": files, "sessions": sessions}
    sdir = os.path.join(store_dir, sid)
    files = sorted(os.listdir(sdir)) if os.path.isdir(sdir) else []
    return {"files": files, "sessions": []}


def _sid_ok(sid):
    return isinstance(sid, str) and SID_RE.match(sid) is not None


def _sid_dir(sid):
    return os.path.join(STORE, sid)


def _ensure_store():
    os.makedirs(STORE, exist_ok=True)


def _atomic_write(path, payload_bytes):
    """tmp → fsync → replace；同目录 .bak 留上一版（读旧快照/崩溃回退用）。"""
    tmp = path + ".tmp"
    bak = path + ".bak"
    if os.path.exists(tmp):
        raise ValueError("另一写者在途（.tmp 存在）: " + path)
    if os.path.exists(path):
        shutil.copy2(path, bak)
    with open(tmp, "wb") as fh:
        fh.write(payload_bytes)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read_json(path, default=None):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _sha256_hex(s):
    if isinstance(s, str):
        s = s.encode("utf-8")
    return hashlib.sha256(s).hexdigest()


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------- 建议工程

_FUSION_RUNS = os.path.join(
    REPO, "docs", "human_capture", "evidence", "2026-10-10_human_unify_fusion_r1",
    "runs_fusion_v3")


def _load_u3_suggestions(sid):
    """从 runs_fusion_v3/<sid>/<sid>__FUSION.json 取逐帧 tracks/candidates →
    每帧 [{cls:'PERSON', x, y, r_xy, track_id, confidence, source:'fusion_u3'}]。无 run 目录返回 {}。"""
    run_path = os.path.join(_FUSION_RUNS, sid, sid + "__FUSION.json")
    if not os.path.isfile(run_path):
        run_path = os.path.join(_FUSION_RUNS, sid, sid + "__U3.json")
    if not os.path.isfile(run_path):
        return {}
    run = _read_json(run_path)
    if not run:
        return {}
    frames = run.get("frames") or []
    tracks = run.get("tracks") or []
    out = {}
    # tracks 是 frame-by-frame snapshot？引擎返回的是末帧活跃列表，先按 frames[].frame_index
    # 索引 candidates 信息再 join。FUSION track 行本身带 (x,y,z,track_id_fusion)，直接用。
    last_by_frame = {}
    for f in frames:
        fi = f.get("frame_index")
        # 引擎没有在 frames[] 暴露 tracks；只能用 tracks[] 末端快照。
        # 取法：tracks[] 末尾含 lost/last_seen；全部 track 按 last_seen ∈ [fi-30, fi]
        # 近似投到本帧；r_xy 用 cluster r90 估计。说明：这是伪标建议，下游仍要人工核。
        pass
    out["_note"] = "FUSION/U3 run 的 tracks 列表是会话末尾快照；annotator 端自动预标仍以 /api/gt/auto 预跑（重算）为准"
    return out


def _auto_candidates(sid):
    """本机优先：gt_workbench/<sid>/AUTO_CANDIDATES.json（工单 gt_workbench_export.py --auto 生成）。"""
    p = os.path.join(REPO, "docs", "human_capture", "evidence",
                     "2026-10-10_human_unify_fusion_r1", "gt_workbench", sid,
                     "AUTO_CANDIDATES.json")
    if os.path.isfile(p):
        data = _read_json(p)
        if data and data.get("frames"):
            out = {}
            for fk, cands in data["frames"].items():
                out[fk] = [{"cls": "PERSON", "x": c["x"], "y": c["y"],
                            "r_xy": c["r_xy"], "n_pts": c.get("n_pts"),
                            "z_max": c.get("z_max"),
                            "source": "auto_candidates",
                            "note": "bg_envelope + 5cm 连通分量; PSEUDO_LABEL"} for c in cands]
            return out
    return {}


def _fusion_rerun_suggestions(sid, dest_root, max_frames=None):
    """子进程跑 human_core FUSION，输出逐帧 candidates（centroid+r90+rf51+track_id_fusion）。
    子进程出口 = <store>/<sid>/fusion_frames.json（原 gt_suggest.js 落盘）。
    慢（9 会话各一遍），所以放建议路径可选——默认 annotator 加载时只读缓存。"""
    store_dir = _sid_dir(sid)
    cache = os.path.join(store_dir, "fusion_frames.json")
    if os.path.isfile(cache):
        data = _read_json(cache)
        if data and data.get("frames"):
            return data["frames"]
    sess_dir = os.path.join(dest_root, sid)
    if not os.path.isfile(os.path.join(sess_dir, "meta.json")):
        return {}
    if not os.path.isfile(os.path.join(sess_dir, "points.bin")):
        return {}
    script = os.path.join(HERE, "gt_suggest.js")
    cmd = ["node", "--max-old-space-size=2048", script, "--session", sess_dir, "--sid", sid]
    if max_frames:
        cmd += ["--max-frames", str(max_frames)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        raise ValueError("gt_suggest 预跑失败: %s" % (proc.stderr or proc.stdout)[-400:])
    data = _read_json(cache)
    if not data:
        raise ValueError("gt_suggest 未落盘 fusion_frames.json")
    return data.get("frames", {})


# ---------------------------------------------------------------- 处理入口

def handle(handler, method, dest_root):
    """入口适配 human_replay_lib._gt_dispatch(method)；与 validation.handle 同款签名。"""
    path = handler.path.split("?", 1)[0]
    body = {}
    if method == "POST":
        try:
            body = json.loads(handler.rfile.read(
                int(handler.headers.get("Content-Length") or 0)).decode("utf-8"))
        except (ValueError, OSError):
            return handler._json({"ok": False, "error": "POST body 非 JSON"}, 400)

    if path == "/api/gt/session" and method == "GET":
        return _get_session(handler, dest_root)
    if path == "/api/gt/save" and method == "POST":
        return _save_draft(handler, body, dest_root)
    if path == "/api/gt/auto" and method == "POST":
        return _auto(handler, body, dest_root)
    if path == "/api/gt/freeze" and method == "POST":
        return _freeze(handler, body)
    if path == "/api/gt/export" and method == "GET":
        return _export(handler)
    if path == "/api/gt/progress" and method == "GET":
        return _progress(handler, dest_root)
    if path == "/api/gt/alias":
        return _alias(handler, method, body)
    return handler._json({"ok": False, "error": "未知 gt 路由 " + path}, 404)


def _progress(handler, dest_root):
    from urllib.parse import urlparse, parse_qs
    sid = parse_qs(urlparse(handler.path).query).get("sid", [""])[0]
    if not _sid_ok(sid):
        return handler._json({"ok": False, "error": "sid 非法"}, 400)
    meta_path = os.path.join(dest_root, sid, "meta.json")
    meta = _read_json(meta_path)
    n_frames = len(meta.get("frames") or []) if meta else 0
    doc = _read_json(os.path.join(_sid_dir(sid), "draft.json"))
    if not doc:
        return handler._json({"ok": True, "sid": sid, "n_frames": n_frames,
                              "annotated_frames": 0, "reviewed_frames": 0,
                              "unknown_frames": n_frames, "person_objects": 0,
                              "furniture_objects": 0, "track_ids": 0, "conflicts": 0})
    frames_objects = doc.get("frames_objects") or {}
    objects = doc.get("objects") or {}
    reviewed = set()
    tracks, furn, person = set(), 0, 0
    for o in objects.values():
        if o.get("review_status") == "reviewed":
            reviewed.add(o.get("frame_idx"))
        if o.get("class_name") == "PERSON" and o.get("track_id"):
            tracks.add(o["track_id"])
            person += 1
        elif o.get("class_name") == "FURNITURE":
            furn += 1
    return handler._json({"ok": True, "sid": sid, "n_frames": n_frames,
                          "annotated_frames": len([f for f, ids in frames_objects.items() if ids]),
                          "reviewed_frames": len(reviewed),
                          "unknown_frames": n_frames - len([f for f, ids in frames_objects.items() if ids]),
                          "person_objects": person, "furniture_objects": furn,
                          "track_ids": len(tracks), "conflicts": doc.get("_conflicts_cache", 0)})


def _get_session(handler, dest_root):
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(handler.path).query)
    sid = q.get("sid", [""])[0]
    if not _sid_ok(sid):
        return handler._json({"ok": False, "error": "sid 非法"}, 400)
    meta_path = os.path.join(dest_root, sid, "meta.json")
    bin_path = os.path.join(dest_root, sid, "points.bin")
    if not os.path.isfile(meta_path):
        return handler._json({"ok": False, "error": "本地无此会话 meta"}, 404)
    meta = _read_json(meta_path)
    # FIX-AUDIT-Q5: 分别报 meta 与 points sha，前端用 points_sha 锚定 doc.session_sha256.points
    with open(meta_path, "rb") as fh:
        meta_sha = _sha256_hex(fh.read())
    points_sha = None
    if os.path.isfile(bin_path):
        with open(bin_path, "rb") as fh:
            points_sha = _sha256_hex(fh.read())
    draft = _read_json(os.path.join(_sid_dir(sid), "draft.json"))
    suggestions = _auto_candidates(sid)          # 不上 fusion 预跑（贵）；按钮显式触发
    manifest = _read_json(os.path.join(_sid_dir(sid), "manifest.json"), {"versions": []})
    aliases = _read_aliases(sid)                 # 显示层别名（不改 manifest，不进 hash 链）
    return handler._json({
        "ok": True, "sid": sid,
        "meta_sha": meta_sha,
        "points_sha": points_sha,
        "n_frames": len(meta.get("frames") or []),
        "display_name": meta.get("name") or sid,
        "duration_sec": meta.get("duration_sec"),
        "frame_rate_hz": meta.get("frame_rate_hz_measured"),
        "draft": draft,
        "draft_alias": aliases.get("draft"),
        "version_aliases": aliases.get("versions") or {},
        "suggestions_auto": suggestions,
        "suggestions_fusion_run": _load_u3_suggestions(sid),
        "frozen_versions": manifest.get("versions", []),
    })


def _save_draft(handler, body, session_dest_root_unused):
    sid = body.get("sid", "")
    doc = body.get("doc")
    expected_sha = body.get("expected_sha")
    if not _sid_ok(sid):
        return handler._json({"ok": False, "error": "sid 非法"}, 400)
    if not isinstance(doc, dict) or doc.get("session_id") != sid:
        return handler._json({"ok": False, "error": "doc.session_id 不匹配"}, 400)
    _ensure_store()
    sdir = _sid_dir(sid)
    os.makedirs(sdir, exist_ok=True)
    draft_path = os.path.join(sdir, "draft.json")
    old = _read_json(draft_path)
    if expected_sha and old:
        # FIX-AUDIT-Q4: 序列化与返回端一致: compact + sort_keys=True (幂等)
        old_blob = json.dumps(old, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":")).encode("utf-8")
        old_sha = _sha256_hex(old_blob)
        if old_sha != expected_sha:
            return handler._json({"ok": False, "error": "draft sha 变化（另一写者）"}, 409)
    doc["annotated_at"] = _now_iso()
    # blob 同样 compact + sort_keys → 返回的 sha256 与下次守卫一致
    blob = json.dumps(doc, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    try:
        _atomic_write(draft_path, blob)
    except ValueError as exc:
        return handler._json({"ok": False, "error": str(exc)}, 409)
    hist = os.path.join(sdir, "history.jsonl")
    with open(hist, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": _now_iso(), "n_objects": len(doc.get("objects") or {}),
                             "review_status": doc.get("review_status")}) + "\n")
    sid_meta = os.path.join(REPO, "captures", "remote", sid, "meta.json")
    return handler._json({"ok": True, "sid": sid,
                          "sha256": _sha256_hex(blob),
                          "n_objects": len(doc.get("objects") or {}),
                          "session_meta_present": os.path.isfile(sid_meta)})


def _now_iso_local():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def _read_aliases(sid):
    """读 <sid>/aliases.json；缺/损均回默认。schema 见 ALIASES_NAME 注释。"""
    if not _sid_ok(sid):
        return _empty_aliases()
    p = os.path.join(_sid_dir(sid), ALIASES_NAME)
    doc = _read_json(p)
    if not isinstance(doc, dict):
        return _empty_aliases()
    draft = doc.get("draft")
    versions = doc.get("versions") if isinstance(doc.get("versions"), dict) else {}
    return {"draft": draft if isinstance(draft, str) and draft else None,
            "versions": {str(k): v for k, v in versions.items() if isinstance(v, str) and v}}


def _write_aliases(sid, doc):
    """原子写 <sid>/aliases.json；parent 目录不存在代表从未标注过（拒绝）。"""
    sdir = _sid_dir(sid)
    if not os.path.isdir(sdir):
        raise ValueError("GT 目录不存在（先得至少保存过一次 draft）")
    blob = json.dumps(doc, ensure_ascii=False, indent=1).encode("utf-8")
    _atomic_write(os.path.join(sdir, ALIASES_NAME), blob)


_VERSION_RE = re.compile(r"^V[0-9]+$")


def _validate_alias_label(name):
    """空 → None（清除别名）；否则校验控制字符 + 长度。"""
    if name is None:
        return None, None
    if not isinstance(name, str):
        return None, "name 必须是字符串或 null"
    name = name.strip()
    if not name:
        return None, None
    if len(name) > ALIAS_MAX_LEN:
        return None, "别名最长 %d 字符" % ALIAS_MAX_LEN
    if any(ord(c) < 32 for c in name):
        return None, "别名不能含控制字符"
    return name, None


def _alias(handler, method, body):
    """GET ?sid= → {ok,draft,versions}; POST {sid, scope, version, name} 原子更新。

    POST scope ∈ {"draft","version"}; scope=version 时必须给 version 且存在 manifest 登记。
    name="" 或 None 都视作清除。变更内容只进 aliases.json；冻结版 sha 完全不受影响。
    """
    from urllib.parse import urlparse, parse_qs
    if method == "GET":
        sid = parse_qs(urlparse(handler.path).query).get("sid", [""])[0]
        if not _sid_ok(sid):
            return handler._json({"ok": False, "error": "sid 非法"}, 400)
        sdir = _sid_dir(sid)
        if not os.path.isdir(sdir):
            return handler._json({"ok": False, "error": "GT 目录不存在"}, 404)
        return handler._json({"ok": True, "sid": sid, **_read_aliases(sid)})

    sid = body.get("sid", "")
    if not _sid_ok(sid):
        return handler._json({"ok": False, "error": "sid 非法"}, 400)
    scope = body.get("scope", "")
    if scope not in ("draft", "version"):
        return handler._json({"ok": False, "error": "scope 必须是 draft 或 version"}, 400)
    label, err = _validate_alias_label(body.get("name"))
    if err:
        return handler._json({"ok": False, "error": err}, 400)

    sdir = _sid_dir(sid)
    if not os.path.isdir(sdir):
        return handler._json({"ok": False, "error": "GT 目录不存在（先保存 draft）"}, 404)

    doc = _read_aliases(sid)
    with _alias_lock:
        if scope == "draft":
            doc["draft"] = label
        else:
            version = str(body.get("version", "")).strip()
            if not _VERSION_RE.match(version):
                return handler._json({"ok": False, "error": "version 必须是 V<数字>"}, 400)
            manifest = _read_json(os.path.join(sdir, "manifest.json"), {"versions": []})
            known = {v.get("version") for v in manifest.get("versions", [])}
            if version not in known:
                return handler._json({"ok": False, "error": "未冻结的版本 %s" % version}, 404)
            if label:
                doc["versions"][version] = label
            else:
                doc["versions"].pop(version, None)
        try:
            _write_aliases(sid, doc)
        except ValueError as exc:
            return handler._json({"ok": False, "error": str(exc)}, 409)
    return handler._json({"ok": True, "sid": sid, "scope": scope,
                          "version": body.get("version") if scope == "version" else None,
                          "name": label,
                          "written_at": _now_iso_local()})


def _auto(handler, body, dest_root):
    sid = body.get("sid", "")
    if not _sid_ok(sid):
        return handler._json({"ok": False, "error": "sid 非法"}, 400)
    max_frames = body.get("max_frames")
    try:
        frames = _fusion_rerun_suggestions(sid, dest_root, max_frames=max_frames)
    except (ValueError, subprocess.TimeoutExpired) as exc:
        return handler._json({"ok": False, "error": "fusion 预跑失败: %s" % exc}, 500)
    return handler._json({"ok": True, "sid": sid, "n_frames_with_suggestions": len(frames),
                          "frames": frames, "source": "model", "review_status_default": "unreviewed"})


def _freeze(handler, body):
    sid = body.get("sid", "")
    annotator = body.get("annotator")
    if not _sid_ok(sid):
        return handler._json({"ok": False, "error": "sid 非法"}, 400)
    sdir = _sid_dir(sid)
    draft_path = os.path.join(sdir, "draft.json")
    doc = _read_json(draft_path)
    if not doc:
        return handler._json({"ok": False, "error": "无 draft 可冻结"}, 404)
    if annotator:
        doc["annotator"] = annotator
    if not doc.get("annotator"):
        return handler._json({"ok": False, "error": "冻结需 annotator 字段"}, 400)
    errs = _validate_doc(doc)
    if errs:
        return handler._json({"ok": False, "error": "校验失败", "errors": errs[:20]}, 400)
    # FIX-AUDIT-Q2: 冻结前必须所有对象 reviewed；否则拒绝，不拉扁全部对象等级
    obj_vals = list((doc.get("objects") or {}).values())
    n_unreviewed = sum(1 for o in obj_vals if o.get("review_status") != "reviewed")
    if obj_vals and n_unreviewed > 0:
        return handler._json(
            {"ok": False,
             "error": "冻结前需对象全部 reviewed；当前 %d/%d 未审" % (n_unreviewed, len(obj_vals)),
             "n_unreviewed": n_unreviewed}, 400)
    doc["review_status"] = "reviewed"
    doc["frozen_at"] = _now_iso()
    # FIX-AUDIT-R2-Q7#6: _freeze_lock 全程持锁防 TOCTOU + GT_V*.json 孤儿早期 refuse
    with _freeze_lock:
        manifest_path = os.path.join(sdir, "manifest.json")
        manifest = _read_json(manifest_path, {"versions": []})
        n = len(manifest.get("versions", [])) + 1
        version = "V%d" % n
        payload = json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")
        sha = _sha256_hex(payload)
        out = os.path.join(sdir, "GT_%s.json" % version)
        if os.path.exists(out):
            # 早期 refuse — 上次 manifest 写失败留下孤儿；让人工排查而不是默默覆盖
            return handler._json({
                "ok": False,
                "error": "%s 已存在（孤儿版本，manifest 无记录）；请人工排查上次 freeze 崩溃窗口" % version,
                "orphan_version": version}, 409)
        try:
            _atomic_write(out, payload)     # 原子
            manifest.setdefault("versions", []).append({
                "version": version, "sha256": sha, "frozen_at": _now_iso(),
                "object_count": len(doc.get("objects") or {}),
                "annotator": doc.get("annotator"),
            })
            _atomic_write(manifest_path,
                          json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8"))
        except ValueError as exc:
            return handler._json({"ok": False, "error": "写盘失败: %s" % exc}, 500)
    return handler._json({"ok": True, "sid": sid, "version": version, "sha256": sha,
                          "object_count": len(doc.get("objects") or {})})


def _validate_doc(doc):
    errs = []
    if not doc.get("session_sha256") or not doc["session_sha256"].get("points"):
        errs.append("session_sha256.points 缺")
    seen = {}
    objects = doc.get("objects") or {}
    for oid, o in objects.items():
        if o.get("class_name") not in ("PERSON", "FURNITURE", "BACKGROUND", "UNKNOWN"):
            errs.append("%s class 非法" % oid)
        if o.get("source") not in ("human", "model", "propagated"):
            errs.append("%s source 非法" % oid)
        if o.get("review_status") == "reviewed" and o.get("source") == "model":
            errs.append("%s reviewed 但 source=model（模型不可冒充人工）" % oid)
        if not o.get("raw_point_indices"):
            errs.append("%s 缺 raw_point_indices" % oid)
        if not (o.get("point_count", 0) > 0):
            errs.append("%s point_count 非正" % oid)
        if o.get("class_name") == "PERSON":
            if not o.get("track_id"):
                errs.append("%s PERSON 缺 track_id" % oid)
            fk = "%s|%s" % (o.get("frame_idx"), o.get("track_id"))
            if fk in seen:
                errs.append("帧 %s track %s 同帧多对象" % (o.get("frame_idx"), o.get("track_id")))
            seen[fk] = oid
    return errs


def _export(handler):
    """列出 gt_store 下可导出的文件 / 读单个文件。"""
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(handler.path).query)
    sid = q.get("sid", [""])[0]
    name = q.get("name", [""])[0]
    _ensure_store()
    if not sid:
        # 列全局
        sessions = sorted(d for d in os.listdir(STORE)
                          if os.path.isdir(os.path.join(STORE, d)))
        return handler._json({"ok": True, "sessions": sessions,
                              "final_exports": [f for f in FINAL_EXPORTS
                                                if os.path.isfile(os.path.join(STORE, f))]})
    if not _sid_ok(sid):
        return handler._json({"ok": False, "error": "sid 非法"}, 400)
    sdir = _sid_dir(sid)
    if not name:
        files = sorted(os.listdir(sdir)) if os.path.isdir(sdir) else []
        return handler._json({"ok": True, "sid": sid, "files": files})
    if name not in ("draft.json", "manifest.json", "AUTO_CANDIDATES.json",
                    "fusion_frames.json", ALIASES_NAME) and not (
                        name.startswith("GT_V") and name.endswith(".json")):
        return handler._json({"ok": False, "error": "文件名不在白名单"}, 400)
    p = os.path.join(sdir, name)
    if not os.path.isfile(p):
        return handler._json({"ok": False, "error": "不存在"}, 404)
    with open(p, "rb") as fh:
        payload_bytes = fh.read()
    return handler._json({"ok": True, "sid": sid, "name": name,
                          "sha256": _sha256_hex(payload_bytes),
                          "doc": json.loads(payload_bytes.decode("utf-8"))})
