# -*- coding: utf-8 -*-
"""HFUS-RD-01 公共层：九会话/GT/ledger 索引解析与背景常量。

契约来源（逐项核实日期 2026-10-12，禁止凭历史对话重推）：
- GT 对象 `raw_point_indices`（gt_workbench/1，字段名误导——历史 D02 已记录）
  == ledger `gt[].indices` == **leveled-compact 域**（gt_lib.js 核心不变量 1：
  每帧按 finite && (x,y,z)!=(0,0,0) 过滤后的稠密下标；映射回原始帧域
  raw_of_leaf = nonzero(valid_mask)，紧凑→raw 用 raw_of_leaf[gt_idx]）。
  实证（175429/f0）：ledger 域直读残差 median 2.13m（伪），
  compact→raw 映射后残差 median 0.13m/p90 0.21m，z p5..p95=[0.13..1.48]
  与人形一致；且 100% 落在 ledger stages.valid_ids 内。
- ledger `candidate.raw_indices`、`stages.*_ids` 则是**原始帧域**
  （引擎内部 filter 保持点顺序子序列契约）。跨域集合运算必须先做
  compact→raw 映射（本文件 gt_raw_indices()）。
- 坐标：points.bin 为传感系原始坐标；leveled 坐标 = R@xyz + T，
  R/T 冻结于 R04_fast_SUMMARY.json['reference']['coordinate']
  （= render_person_label.R/T，GT 在同一 leveled 系标注）。
- 帧切片：meta.frames[i].offset_points/count_points，28B/点:
  [x,y,z,i]f32 + ring u16 + timestamp f32 + pads，见 point_layout。
- intensity：原始 uint16/f32 档位（f32 view 值域约 0..13000，60 档），
  JS rf_person.js extract 对强度做 log2 变换；复现 RF51 需要同一变换。
"""
import json
import os
import struct

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CAPTURES = os.path.join(REPO, "captures", "remote")
GT_STORE = os.path.join(REPO, "pc_apps", "human_replay", "gt_store")
LEDGER_DIR = os.path.join(
    REPO, "docs", "human_capture", "evidence",
    "2026-10-12_hfus_d05_r4", "runs", "fast")
WORK = os.path.join(REPO, "sidequests", "HFUS-RD-01", "work")
EVIDENCE = os.path.join(REPO, "docs", "sidequests",
                        "evidence", "2026-10-12_HFUS_RD_01_r1")

SIDS = [
    "cap_20261010_175227",  # S1 empty-with-furniture（无 PERSON GT）
    "cap_20261010_175429",  # S3 walk-x near
    "cap_20261010_175553",  # S3 walk-y far
    "cap_20261010_175804",  # S4 walk-stop-walk
    "cap_20261010_175943",  # S5 turn-in-place
    "cap_20261010_180235",  # S6 occlusion
    "cap_20261010_180337",  # S7 far 5m
    "cap_20261010_180557",  # S8 still retention
    "cap_20261010_180751",  # S9 GT 绑定无效（EXPLORATION only）
]
SID_SHORT = {
    "cap_20261010_175227": "S1-furniture",
    "cap_20261010_175429": "S3-near",
    "cap_20261010_175553": "S3-far",
    "cap_20261010_175804": "S4-walkstop",
    "cap_20261010_175943": "S5-turn",
    "cap_20261010_180235": "S6-occlusion",
    "cap_20261010_180337": "S7-far5m",
    "cap_20261010_180557": "S8-still",
    "cap_20261010_180751": "S9-explore",
}

# 预登记数据划分（沿用 D02 split；S1 无 GT 人 → 所属折叠不设为 test）
FOLDS = {
    "train": ["cap_20261010_175227", "cap_20261010_175429",
              "cap_20261010_175804", "cap_20261010_175943"],
    "val": ["cap_20261010_175553"],
    "test": ["cap_20261010_180337", "cap_20261010_180557"],
    "stress": ["cap_20261010_180235"],
    "explore": ["cap_20261010_180751"],
}

STRIDE = 28
_F4 = np.dtype("<f4")

_LEV_RT = None


def leveling_rt():
    """冻结的 R/T（D05 R04 reference.coordinate）。"""
    global _LEV_RT
    if _LEV_RT is None:
        with open(os.path.join(LEDGER_DIR, "R04_fast_SUMMARY.json"),
                  encoding="utf-8") as f:
            ref = json.load(f)["reference"]["coordinate"]
        _LEV_RT = (np.asarray(ref["R"], dtype=np.float64).reshape(3, 3),
                   np.asarray(ref["T"], dtype=np.float64))
    return _LEV_RT


def level(xyz, out=None):
    """传感系 (N,3) → leveled (N,3)。out 可传 float32 复用缓冲。"""
    R, T = leveling_rt()
    res = xyz.astype(np.float64) @ R.T + T
    if out is not None:
        np.copyto(out, res, casting="unsafe")
        return out
    return res


def load_meta(sid):
    with open(os.path.join(CAPTURES, sid, "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def read_frame_xyz(sid, frame_idx, mm=None):
    """返回 (xyz float32 (N,3) 传感系, intensity float32 (N,), raw uint8 view)。

    raw_mmap 整文件一次性 memmap，跨帧复用；intensity 是从 28B 步进
    视图里 offset 12 的 <f4（JS/annotator 同款读法）。"""
    meta = load_meta(sid)
    fr = meta["frames"][frame_idx]
    if mm is None:
        mm = np.memmap(os.path.join(CAPTURES, sid, "points.bin"),
                       dtype=np.uint8, mode="r")
    b0 = fr["offset_points"] * STRIDE
    n = fr["count_points"]
    chunk = mm[b0:b0 + n * STRIDE]
    v = chunk.view(np.uint8).reshape(n, STRIDE)
    xyz = np.empty((n, 3), dtype=np.float32)
    for d in range(3):
        xyz[:, d] = v[:, d * 4:(d + 1) * 4].ravel().view(_F4)
    inten = v[:, 12:16].ravel().view(_F4).copy()
    return xyz, inten, mm


def decode_indices(v, n):
    """GT/ledger 的 [tag,...] 压缩索引 → bool 掩码（长度 n）。"""
    out = np.zeros(n, dtype=bool)
    if not v:
        return out
    tag = v[0]
    if tag == "s":
        idx = v[1:]
    elif tag == "r":
        idx = range(v[1], v[1] + v[2] * v[3], v[2])
    elif tag == "m":
        runs, tail = v[1], v[2]
        idx = []
        for r in range(0, len(runs), 3):
            a0, d, m = runs[r], runs[r + 1], runs[r + 2]
            idx.extend(range(a0, a0 + d * m, d))
        idx.extend(tail)
    else:
        raise ValueError("未知 index 编码 tag: %r" % (tag,))
    idx = np.asarray(list(idx) if not isinstance(idx, np.ndarray) else idx,
                     dtype=np.int64)
    if idx.size:
        out[idx] = True
    return out


def decode_indices_list(v):
    """同上但返回排序 int 数组。"""
    tag = v[0]
    if tag == "s":
        return np.asarray(v[1:], dtype=np.int64)
    if tag == "r":
        a0, d, m = v[1], v[2], v[3]
        return a0 + d * np.arange(m, dtype=np.int64)
    if tag == "m":
        runs, tail = v[1], v[2]
        parts = []
        for r in range(0, len(runs), 3):
            parts.append(runs[r] + runs[r + 1] * np.arange(runs[r + 2],
                                                             dtype=np.int64))
        parts.append(np.asarray(tail, dtype=np.int64))
        return np.concatenate(parts)
    raise ValueError("未知 index 编码 tag: %r" % (tag,))


GT_CACHE = {}


def load_gt(sid):
    """GT_V1.json → {objects: [dict(indices=list[int], class_name, source,
    review_status, frame_idx, track_id)], sha: {...}}。S9 返回 None。"""
    if sid in GT_CACHE:
        return GT_CACHE[sid]
    p = os.path.join(GT_STORE, sid, "GT_V1.json")
    if not os.path.exists(p):
        GT_CACHE[sid] = None
        return None
    with open(p, encoding="utf-8") as f:
        g = json.load(f)
    objs = []
    for o in g["objects"].values():
        objs.append({
            "id": o["object_id"], "frame_idx": o["frame_idx"],
            "class_name": o["class_name"], "source": o.get("source"),
            "review_status": o.get("review_status"),
            "track_id": o.get("track_id"),
            "point_count": o.get("point_count"),
            "x": o.get("x"), "y": o.get("y"),
            "z_min": o.get("z_min"), "z_max": o.get("z_max"),
            "indices": decode_indices_list(o["raw_point_indices"]),
        })
    meta_sha = (g.get("session_sha256") or {})
    res = {"objects": objs, "session_sha256": meta_sha,
           "review_status": g.get("review_status")}
    GT_CACHE[sid] = res
    return res


LEDGER_PATHS = {
    sid: os.path.join(LEDGER_DIR, "R04_fast_%s.jsonl" % sid) for sid in SIDS
}


def raw_of_leaf_frame(sid, frame_idx, mm=None):
    """一帧的 compact→raw 映射（int64 数组，长度 = 有效点数）。"""
    xyz, _i, mm = read_frame_xyz(sid, frame_idx, mm=mm)
    mask = np.isfinite(xyz).all(axis=1) & (xyz != 0).any(axis=1)
    return np.nonzero(mask)[0], mm


def gt_raw_indices(obj, raw_of_leaf):
    """GT 对象 compact 索引 → 原始帧域 raw 索引。"""
    return raw_of_leaf[obj["indices"]]


def iter_ledger(sid, fields=None):
    """流式 yield ledger 记录（~1-2MB/行，严禁 readlines）。"""
    with open(LEDGER_PATHS[sid], encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if fields is None:
                yield rec
            else:
                yield {k: rec.get(k) for k in fields}


def stages_masks(rec):
    """ledger 一行的 stages → dict(name→ int 数组)。原始帧域。"""
    s = rec["stages"]
    return {k: np.asarray(v, dtype=np.int64) for k, v in s.items()
            if isinstance(v, list)}


def reason_masks(rec):
    """stages.reason_ids → dict(reason → int 数组)。"""
    out = {}
    for k, v in rec["stages"].get("reason_ids", {}).items():
        out[k] = np.asarray(v, dtype=np.int64)
    return out
