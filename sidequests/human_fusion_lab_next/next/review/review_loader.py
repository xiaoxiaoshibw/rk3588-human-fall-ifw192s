# -*- coding: utf-8 -*-
"""HFUS-D02 review_loader：只读加载会话与 GT，做严格 SHA 绑定校验与索引映射。

职责边界：不做切片、不做资格评级（资格是 review_schema.machine_default_* 的事）。
本模块只回答三件事：
  1. 会话 meta/points 实际 SHA 是多少；
  2. GT 文件声明的 SHA 与会话实际 SHA 是否绑定（含 aaaa… 占位检测）；
  3. GT 对象 raw_point_indices（leveled-compact 域）如何无歧义翻译回 raw28 点号。

索引编码等价 sidequests/human_fusion_lab/human_replay/gt_lib.js：
  ["s", i...]      稀疏
  ["r", a0, d, m]  等差 run
  ["m", [run头三元组...], [tail...]]  混合
与 gt_lib 的兼容性差异（比 gt_lib 更严格，D01 集成时按本口径）：本加载器
对负步长 run 与非 3 整数倍 run 头/缺 runs/tail 一律 ValueError；gt_lib 对负步长无声接受。
这影响接口期望：D01 若以 gt_lib 口径生成索引，本侧会拒绝其（潜在）退化编码。
compact→raw 映射等价 gt_lib.split_frame_indices：finite 且 (x,y,z) 不全 0。
纯 stdlib；numpy 非必需。
"""
import hashlib
import json
import math
import os
import struct

_PLACEHOLDER_SHA = "a" * 64  # S9 占位：声明了但从未真正计算，等价绑定损坏
_STRIDE = 28                    # 28 字节/点：x,y,z,intensity,ring,timestamp + 2 pad
_CHUNK = 1 << 20                # 流式 sha 块大小


def sha256_path(path):
    """流式 sha256（大文件逐块），返回 hex。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(_CHUNK)
            if not b:
                return h.hexdigest()
            h.update(b)


def load_session_meta(session_dir):
    """解析会话 meta.json + 计算 points.bin 实际 sha。

    返回 {meta, frames, points_path, points_sha256, meta_sha256, stride_bytes, n_frames}。
    校验：frames 必须非空且每帧 count_points/offset_points 为非负 int。
    """
    meta_path = os.path.join(session_dir, "meta.json")
    with open(meta_path, "rb") as f:
        meta_raw = f.read()
    meta = json.loads(meta_raw.decode("utf-8"))
    frames = meta.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ValueError("meta.json 缺 frames 或为空: " + meta_path)
    for i, fr in enumerate(frames):
        for k in ("count_points", "offset_points"):
            v = fr.get(k)
            if not isinstance(v, int) or v < 0:
                raise ValueError("frames[%d].%s 非法: %r" % (i, k, v))
    points_path = os.path.join(session_dir, "points.bin")
    return {
        "meta": meta,
        "frames": frames,
        "points_path": points_path,
        "points_sha256": sha256_path(points_path),
        "meta_sha256": hashlib.sha256(meta_raw).hexdigest(),
        "stride_bytes": int(meta.get("point_layout", {}).get("stride_bytes", _STRIDE)),
        "n_frames": len(frames),
    }


def read_frame_xyz(points_path, offset_points, count_points, stride_bytes=_STRIDE):
    """按帧偏移读出前 3 列 xyz，返回 [(x,y,z), ...]（纯 struct.unpack，不要 numpy）。"""
    fmt = "<%df" % (stride_bytes // 4)
    row = struct.Struct(fmt)
    out = []
    with open(points_path, "rb") as f:
        f.seek(offset_points * stride_bytes)
        for _ in range(count_points):
            vals = row.unpack(f.read(stride_bytes))
            out.append((vals[0], vals[1], vals[2]))
    return out


def build_compact_maps(frame_xyz):
    """等价 gt_lib.split_frame_indices（只取前 3 列，忽略 leveling 输出）。

    frame_xyz: (n, >=3) 可索引序列。ok = 三分量均 finite 且不全 0。
    返回 {raw_of_leaf, leaf_of_raw, n_leveled}。
    """
    n = len(frame_xyz)
    leaf_of_raw = [-1] * n
    raw_of_leaf = []
    for p in range(n):
        x, y, z = frame_xyz[p][0], frame_xyz[p][1], frame_xyz[p][2]
        if (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)
                and (x != 0.0 or y != 0.0 or z != 0.0)):
            leaf_of_raw[p] = len(raw_of_leaf)
            raw_of_leaf.append(p)
    return {"raw_of_leaf": raw_of_leaf, "leaf_of_raw": leaf_of_raw,
            "n_leveled": len(raw_of_leaf)}


def _is_bad_sha(declared, actual):
    return declared != actual or declared == _PLACEHOLDER_SHA


def load_gt(gt_path, session_points_sha_actual, session_meta_sha_actual):
    """读 GT json 并做 SHA 绑定校验。原样保留 objects 与未识别字段。

    返回 {doc, objects, binding_ok, binding_reason, gt_sha256, gt_level, review_status}。
    objects 元素：{object_id, class_name, frame_idx, polygon_xy, r_xy, point_count,
                  source, review_status, raw_point_indices(编码原样)}，
    未提供字段给 None —— 保守，不猜（缺 source 不默认 human）。
    """
    with open(gt_path, "rb") as f:
        raw = f.read()
    doc = json.loads(raw.decode("utf-8"))
    declared = doc.get("session_sha256") or {}
    bad = []
    if _is_bad_sha(declared.get("points"), session_points_sha_actual):
        bad.append("points(declared=%s)" % str(declared.get("points"))[:16])
    if _is_bad_sha(declared.get("meta"), session_meta_sha_actual):
        bad.append("meta(declared=%s)" % str(declared.get("meta"))[:16])
    objects = []
    for oid, o in (doc.get("objects") or {}).items():
        objects.append({
            "object_id": o.get("object_id", oid),
            "class_name": o.get("class_name"),
            "frame_idx": o.get("frame_idx"),
            "polygon_xy": o.get("polygon_xy"),
            "r_xy": o.get("r_xy"),
            "point_count": o.get("point_count"),
            "source": o.get("source"),
            "review_status": o.get("review_status"),
            "raw_point_indices": o.get("raw_point_indices"),
        })
    return {
        "doc": doc,
        "objects": objects,
        "binding_ok": not bad,
        "binding_reason": "ok" if not bad else "broken: " + ",".join(bad),
        "gt_sha256": hashlib.sha256(raw).hexdigest(),
        "gt_level": doc.get("gt_level"),
        "review_status": doc.get("review_status"),
    }


def decode_indices(encoded):
    """三格式解码 → list[int]。等价 gt_lib decode_indices，带校验。"""
    if not encoded:
        return []
    tag = encoded[0]
    if tag == "s":
        return list(encoded[1:])
    if tag == "r":
        if len(encoded) != 4:
            raise ValueError("r 编码长度应为 4: %r" % (encoded,))
        a0, d, m = encoded[1], encoded[2], encoded[3]
        return _check_run(a0, d, m)
    if tag == "m":
        if len(encoded) < 3:
            raise ValueError("m 编码缺 runs/tail: %r" % (encoded,))
        runs, tail = encoded[1], encoded[2]
        if len(runs) % 3 != 0:
            raise ValueError("m 编码 run 头长度非 3 的倍数: %r" % (runs,))
        out = []
        for r in range(0, len(runs), 3):
            out.extend(_check_run(runs[r], runs[r + 1], runs[r + 2]))
        out.extend(tail)
        return out
    raise ValueError("未知 index 编码 tag: %r" % (tag,))


def _check_run(a0, d, m):
    if d < 0:
        raise ValueError("负步长 run: d=%r" % (d,))
    if m < 0:
        raise ValueError("负长度 run: m=%r" % (m,))
    return [a0 + k * d for k in range(m)]


def object_member_raw_indices(obj_encoded, raw_of_leaf):
    """compact 下标 → raw 点号（index-binding 正确性核心）。

    返回 {raw_indices, out_of_bounds, decoded_n}；c >= len(raw_of_leaf) 计越界跳过。
    """
    decoded = decode_indices(obj_encoded)
    raw_indices = []
    oob = 0
    for c in decoded:
        if 0 <= c < len(raw_of_leaf):
            raw_indices.append(raw_of_leaf[c])
        else:
            oob += 1
    return {"raw_indices": raw_indices, "out_of_bounds": oob,
            "decoded_n": len(decoded)}


if __name__ == "__main__":
    import tempfile

    tmp = tempfile.mkdtemp(prefix="review_loader_selftest_")
    # ---- 合成会话：2 帧, 帧0 有 5 点(含 0 点/nan), 帧1 有 3 点 ----
    pts_f0 = [(1.0, 2.0, 3.0), (0.0, 0.0, 0.0), (float("nan"), 1.0, 1.0),
              (4.0, 5.0, 6.0), (0.0, 7.0, 0.0)]
    pts_f1 = [(8.0, 9.0, 10.0), (float("inf"), 0.0, 0.0), (1.0, 1.0, 1.0)]
    count0, count1 = len(pts_f0), len(pts_f1)
    meta = {
        "frames": [
            {"bag_time_sec": 1.0, "count_points": count0, "offset_points": 0, "seq": 0},
            {"bag_time_sec": 1.1, "count_points": count1,
             "offset_points": count0, "seq": 1},
        ],
        "point_layout": {"stride_bytes": 28,
                         "fields": ["x", "y", "z", "intensity", "ring", "timestamp"],
                         "pad_offsets_bytes": [18, 24]},
    }
    meta_path = os.path.join(tmp, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    points_path = os.path.join(tmp, "points.bin")
    with open(points_path, "wb") as f:
        for x, y, z in pts_f0 + pts_f1:
            f.write(struct.pack("<7f", x, y, z, 100.0, 5.0, 1.5, 0.0))

    sess = load_session_meta(tmp)
    assert sess["n_frames"] == 2 and sess["stride_bytes"] == 28
    assert sess["points_sha256"] == sha256_path(points_path)
    assert len(sess["meta_sha256"]) == 64

    # ---- compact 映射: 帧0 ok 点 = raw 0,3,4 ----
    maps = build_compact_maps(read_frame_xyz(points_path, 0, count0))
    assert maps["raw_of_leaf"] == [0, 3, 4], maps["raw_of_leaf"]
    assert maps["leaf_of_raw"] == [0, -1, -1, 1, 2]
    assert maps["n_leveled"] == 3

    # ---- decode 三格式 ----
    assert decode_indices(["s", 2, 0, 1]) == [2, 0, 1]
    assert decode_indices(["r", 10, 3, 4]) == [10, 13, 16, 19]
    assert decode_indices(["m", [0, 2, 3, 100, 5, 2], [7, 9]]) == \
        [0, 2, 4, 100, 105, 7, 9]
    for bad in (["x", 1], ["r", 0, -1, 3], ["m", [1, 2], []], ["m"]):
        try:
            decode_indices(bad)
            raise AssertionError("应拒绝: %r" % (bad,))
        except ValueError:
            pass

    # ---- compact→raw + 越界 ----
    r = object_member_raw_indices(["s", 0, 2, 3, 99], maps["raw_of_leaf"])
    assert r["raw_indices"] == [0, 4] and r["out_of_bounds"] == 2 and r["decoded_n"] == 4
    r2 = object_member_raw_indices(["r", 0, 1, 3], maps["raw_of_leaf"])
    assert r2["raw_indices"] == [0, 3, 4]

    # ---- GT 绑定: 正确 / aaaa 占位 / sha 错 ----
    def _mk_gt(points_sha, meta_sha):
        p = os.path.join(tmp, "gt.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({
                "session_sha256": {"points": points_sha, "meta": meta_sha},
                "gt_level": "V1", "review_status": "draft",
                "objects": {"o1": {"object_id": "o1", "class_name": "person",
                                   "frame_idx": 0, "polygon_xy": [[0, 0]],
                                   "point_count": 2, "source": "human",
                                   "review_status": "reviewed",
                                   "raw_point_indices": ["s", 0, 2]}},
            }, f)
        return p

    g1 = load_gt(_mk_gt(sess["points_sha256"], sess["meta_sha256"]),
                 sess["points_sha256"], sess["meta_sha256"])
    assert g1["binding_ok"] and g1["binding_reason"] == "ok"
    assert g1["objects"][0]["source"] == "human"
    assert g1["objects"][0]["raw_point_indices"] == ["s", 0, 2]
    g2 = load_gt(_mk_gt(_PLACEHOLDER_SHA, sess["meta_sha256"]),
                 sess["points_sha256"], sess["meta_sha256"])
    assert not g2["binding_ok"] and "points" in g2["binding_reason"]
    g3 = load_gt(_mk_gt("b" * 64, "c" * 64),
                 sess["points_sha256"], sess["meta_sha256"])
    assert not g3["binding_ok"] and "points" in g3["binding_reason"] \
        and "meta" in g3["binding_reason"]

    print("selftest OK: tmp=%s" % tmp)
