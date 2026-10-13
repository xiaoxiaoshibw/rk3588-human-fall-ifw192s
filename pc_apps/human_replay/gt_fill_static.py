# -*- coding: utf-8 -*-
"""gt_fill_static.py — 把静态对象（家具）从源帧 ROI 复制到目标全部帧。

用途（工单 GT_COVERAGE §4 S1 空场抽稀口径）：
  用户在 S1 某帧画好 N 件家具 → 这条命令把每件家具 ROI 原样复制到全部
  304 帧（点按目标帧重选），标 source="propagated" + review_status="unreviewed"。
  用户仍必须 Ctrl+S 保存 → 之后逐帧「H 一键整帧审」/冻结时才全 reviewed。

跑法：
  python pc_apps/human_replay/gt_fill_static.py --sid cap_20261010_175227

小心：draft.json 必须存在（你保存过的）。脚本读取、计算、原子覆盖；失败残留由
.draft.json.bak 备份。

对象语义（与 gt_lib.propagate_object 一致）：
  - source="propagated"  — 工单标 记为「跨帧复制」，与「人工 source=human」互斥。
  - review_status="unreviewed" — 仍需人工审，冻结时 server 会拒全部未审。
  - parent_object_id=<src_oid> — 追溯。
  - 同帧 track_id/对象 class_name 完全继承（track_id 是稳定身份）。
  - raw_point_indices 用目标帧点云在相同 ROI 重选（leveled + z_min/z_max 一致）。

缺陷说明（ponytail 接受）:
  - frames_objects 中已有同 track_id 的 frame 自动跳过（避免 S9 双人错插）。
  - 没有重新验证成 K 帧等高级情态。
  - 静态对象例外：非空场会话不应跑这条（人动了 ROI 就错），但不再加 watchdog。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gt_server as G  # noqa: E402

STRUCT = 28
STRIDE_F32 = 7


def _load_points(sid_dir):
    meta_path = os.path.join(sid_dir, "meta.json")
    bin_path = os.path.join(sid_dir, "points.bin")
    import numpy as np
    meta = json.load(open(meta_path, encoding="utf-8"))
    raw = np.memmap(bin_path, dtype=np.uint8, mode="r").reshape(-1, STRUCT).view(np.float32).reshape(-1, STRIDE_F32)
    return meta, raw


def _leveled_compact_frame_np(raw, offset_pts, count_pts, R, T):
    """numpy 向量化: 返回 (leveled_xyz (n,3) float32, )。"""
    import numpy as np
    seg = raw[offset_pts: offset_pts + count_pts, :3].astype(np.float64)
    v = np.isfinite(seg).all(axis=1) & np.any(seg != 0, axis=1)
    if not v.any():
        return np.zeros((0, 3), dtype=np.float32)
    seg_v = seg[v]
    Rm = np.asarray(R, dtype=np.float64).reshape(3, 3)
    lev = seg_v @ Rm.T + np.asarray(T, dtype=np.float64)
    return lev.astype(np.float32)


def _select_idx_in_frame_np(leveled, shape, z_min, z_max):
    """向量化选点 → int32 array 帧内 compact idx (升序)。"""
    import numpy as np
    if len(leveled) == 0:
        return np.zeros(0, dtype=np.int32)
    x = leveled[:, 0]
    y = leveled[:, 1]
    z = leveled[:, 2]
    m = (z >= z_min) & (z <= z_max)
    if isinstance(shape, dict) and "box_xy" in shape:
        x0, y0, x1, y1 = shape["box_xy"]
        xmin, xmax = min(x0, x1), max(x0, x1)
        ymin, ymax = min(y0, y1), max(y0, y1)
        m &= (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
    elif isinstance(shape, dict) and "polygon_xy" in shape:
        # 5m 网格 coarse prefilter + 精确 ray-cast 精筛（简化；region小所以快）
        poly = np.asarray(shape["polygon_xy"], dtype=np.float64)
        xmin, xmax = poly[:, 0].min(), poly[:, 0].max()
        ymin, ymax = poly[:, 1].min(), poly[:, 1].max()
        m &= (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
        pre = np.nonzero(m)[0]
        keep = []
        for k in pre:
            if _point_in_poly_scalar(float(x[k]), float(y[k]), shape["polygon_xy"]):
                keep.append(int(k))
        m = np.zeros(len(leveled), dtype=bool)
        if keep:
            m[np.asarray(keep, dtype=np.int64)] = True
    else:
        cx, cy, r = shape.get("x", 0), shape.get("y", 0), shape.get("r_xy", 0.5)
        m &= ((x - cx) ** 2 + (y - cy) ** 2) <= r * r
    return np.nonzero(m)[0].astype(np.int32)


def _point_in_poly_scalar(px, py, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i][0], poly[i][1]
        xj, yj = poly[j][0], poly[j][1]
        if (yi > py) != (yj > py) and px < ((xj - xi) * (py - yi)) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _encode_indices(arr):
    """与 gt_lib.encode_indices 一致的最小子集：稀疏 ≤64；否则合成 mixed/run。"""
    a = list(arr)
    if not a:
        return ["s"]
    if len(a) <= 64:
        return ["s"] + a
    runs = []
    i = 0
    while i < len(a) - 1:
        a0, d = a[i], a[i + 1] - a[i]
        m = 2
        while i + m < len(a) and a[i + m] == a0 + m * d:
            m += 1
        if m >= 4:
            runs.extend([a0, d, m])
            i += m
        else:
            break
    if i == 0:
        return ["s"] + a
    tail = a[i:]
    if len(runs) == 3 and not tail:
        return ["r"] + runs
    return ["m", runs, tail]


def fill_static(sid, only_frames_with_objects=None, verbose=False):
    store_dir = os.path.join(G.STORE, sid)
    draft_path = os.path.join(store_dir, "draft.json")
    if not os.path.isfile(draft_path):
        raise SystemExit("无 draft.json；先在 annotator 画至少一帧 + Ctrl+S 保存")
    doc = json.load(open(draft_path, encoding="utf-8"))

    src_frames = [int(f) for f, ids in (doc.get("frames_objects") or {}).items()
                  if ids]
    if not src_frames:
        raise SystemExit("draft 没有任何已标帧")
    src_frame = min(src_frames)
    src_objs = [doc["objects"][oid] for oid in doc["frames_objects"][str(src_frame)]]
    if verbose:
        print("源帧:", src_frame, "对象数:", len(src_objs))

    sid_dir = os.path.join(G.REPO, "captures", "remote", sid)
    meta, raw = _load_points(sid_dir)
    # 用与 render_person_label.py 同一份 R/T
    R = [0.893544, 0.0, 0.448975,
         -0.014337, 0.99949, 0.028533,
         -0.448746, -0.031932, 0.893089]
    T = [0.0, 0.0, 1.380286]

    n_frames = len(meta["frames"])
    frames_map = doc.setdefault("frames_objects", {})
    objects = doc.setdefault("objects", {})
    existing_tracks = {o.get("track_id") for o in objects.values()

                       if o.get("track_id")}
    added_total = 0
    skipped = 0
    next_oseq = getattr(fill_static, "_oseq", 0)

    # 记录后续 source_frame 的 track_id → src_obj
    src_by_tid = {}
    for o in src_objs:
        tid = o.get("track_id") or ("__no_track__" + o["object_id"])
        src_by_tid[tid] = o

    for fi in range(n_frames):
        if only_frames_with_objects is not None and fi not in only_frames_with_objects:
            continue
        existing_ids = set(frames_map.get(str(fi), []))
        existing_tids_this_frame = {objects[i].get("track_id")
                                    for i in existing_ids if i in objects}
        frame = meta["frames"][fi]
        off, cnt = frame["offset_points"], frame["count_points"]
        leveled = _leveled_compact_frame_np(raw, off, cnt, R, T)
        for tid, src_obj in src_by_tid.items():
            if tid != "__no_track__" + src_obj["object_id"] and tid in existing_tids_this_frame:
                skipped += 1
                continue
            shape = {}
            if src_obj.get("box_xy"):
                shape = {"box_xy": src_obj["box_xy"]}
            elif src_obj.get("polygon_xy"):
                shape = {"polygon_xy": src_obj["polygon_xy"]}
            else:
                shape = {"x": src_obj["x"], "y": src_obj["y"], "r_xy": src_obj["r_xy"]}
            idx = _select_idx_in_frame_np(leveled, shape,
                                          src_obj["z_min"], src_obj["z_max"])
            if len(idx) == 0:
                skipped += 1
                continue
            next_oseq += 1
            new_oid = "obj_f%d_n%d_static" % (fi, next_oseq)
            new_obj = dict(src_obj)
            new_obj.update({
                "object_id": new_oid,
                "frame_id": "%s:%d" % (sid, fi),
                "frame_idx": fi,
                "timestamp": frame.get("bag_time_sec"),
                "raw_point_indices": _encode_indices(map(int, idx)),
                "point_count": int(len(idx)),
                "source": "propagated",
                "review_status": "unreviewed",
                "parent_object_id": src_obj["object_id"],
                "propagate_kind": "static_fill",
            })
            new_obj.pop("is_keyframe", None)
            objects[new_oid] = new_obj
            frames_map.setdefault(str(fi), []).append(new_oid)
            added_total += 1

    # 保存
    blob = json.dumps(doc, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    G._atomic_write(draft_path, blob)
    print("静态填充完成: %d 帧 × %d 对象 → %d 新增 (跳过 %d)" %
          (len(frames_map), len(src_by_tid), added_total, skipped))
    print("draft sha256:", G._sha256_hex(blob)[:16])
    print("仍须人工审：H 整帧审 或质检抽检; 冻结时若含 unreviewed 对象 server 会拒")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", required=True)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if not G._sid_ok(args.sid):
        raise SystemExit("sid 非法")
    fill_static(args.sid, verbose=args.verbose)


if __name__ == "__main__":
    main()
