#!/usr/bin/env python3
# S1 (cap_20261010_175227) propagated 对象 reselect raw_point_indices（向量化版）.
#
# 问题: propagate_s1.py 克隆时直接沿用 f=0 帧的 raw_point_indices，
#       但 frames count_points 微变 (49126 vs 49124), 旧 idx 在后续帧越界。
# 修法: 每帧用对象 polygon_xy + z 带对该帧 leveled 有效点重选, 重新生成
#        raw_point_indices + point_count -> draft.json -> server freeze V2。
#
# 语义: 与 gt_lib.js point_in_poly 相同 (ray casting), numpy 向量化。
# 用法: python reselect_propagated_indices.py [--yes]

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SID = "cap_20261010_175227"
DRAFT = os.path.join(HERE, "gt_store", SID, "draft.json")
SERVER = "http://127.0.0.1:8901"

sys.path.insert(0, os.path.join(HERE, "..", "human_ml"))
from render_person_label import R, T  # noqa: E402


def points_in_poly(xs, ys, poly):
    """numpy 向量化 ray casting, 与 gt_lib.point_in_poly 等价。"""
    inside = np.zeros(len(xs), dtype=bool)
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i][0], poly[i][1]
        xj, yj = poly[j][0], poly[j][1]
        dy = (yj - yi)
        # 水平边 dy==0 时 ((yi>y)!=(yj>y)) 恒 False, 安全
        with np.errstate(divide="ignore", invalid="ignore"):
            x_cross = (xj - xi) * (ys - yi) / dy + xi
        cond = ((yi > ys) != (yj > ys)) & (xs < x_cross)
        inside ^= cond
        j = i
    return inside


def encode_indices_set(indices):
    """'s' 直列编码, 与 frozen_gt.decode_indices / gt_lib 兼容。"""
    return ["s"] + [int(x) for x in sorted(indices)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--report-only", action="store_true",
                    help="只输出每帧每对象点数统计, 不改文件")
    args = ap.parse_args()

    if not os.path.isfile(DRAFT):
        print("无 draft:", DRAFT)
        sys.exit(1)

    with open(DRAFT, "r", encoding="utf-8") as f:
        doc = json.load(f)
    objs = doc.get("objects") or {}

    cap_dir = os.path.join(HERE, "..", "..", "captures", "remote", SID)
    raw = np.memmap(os.path.join(cap_dir, "points.bin"), dtype="<f4", mode="r").reshape(-1, 7)
    with open(os.path.join(cap_dir, "meta.json"), "r", encoding="utf-8") as f:
        meta = json.load(f)
    frames_meta = meta["frames"]

    prop_oids = [oid for oid, o in objs.items() if o.get("source") == "propagated"]
    by_frame = {}
    for oid in prop_oids:
        by_frame.setdefault(objs[oid]["frame_idx"], []).append(oid)
    print(f"propagated 对象: {len(prop_oids)}  跨帧: {len(by_frame)}")

    n_updated, n_zero = 0, 0
    pc_stats = []
    for fi in sorted(by_frame.keys()):
        fmeta = frames_meta[fi]
        seg = raw[fmeta["offset_points"]:fmeta["offset_points"] + fmeta["count_points"], :4]
        valid = np.isfinite(seg[:, :3]).all(axis=1) & np.any(seg[:, :3] != 0, axis=1)
        seg_v = seg[valid]
        xyz = (seg_v[:, :3].astype(np.float64) @ R.T + T)
        xs, ys, zs = xyz[:, 0], xyz[:, 1], xyz[:, 2]

        for oid in by_frame[fi]:
            o = objs[oid]
            poly = o.get("polygon_xy")
            if not poly:
                continue
            z_min = o.get("z_min", 0.05)
            z_max = o.get("z_max", 2.3)
            z_ok = (zs >= z_min) & (zs <= z_max)
            inside = points_in_poly(xs, ys, poly) & z_ok
            # 索引用「valid 后数组内索引」—— 与 compact_frame 一致; 下游 export_samples
            # 用 points[idx] 取, points 就是 valid 后的 seg_v 数组。
            sel = np.where(inside)[0]
            pc_stats.append((fi, oid, len(sel)))
            if len(sel) == 0:
                n_zero += 1
                # 区域无点: 不更新 (freeze 校验 point_count>0 会拒;
                # 但当前 draft 已有旧 point_count,留着更糟 — 标记出来人工定夺)
                continue
            o["raw_point_indices"] = encode_indices_set(sel)
            o["point_count"] = int(len(sel))
            n_updated += 1

    pcs = [p for _, _, p in pc_stats]
    print(f"reselect: {n_updated}/{len(prop_oids)} 更新, {n_zero} 对象区域内 0 点")
    if pcs:
        arr = np.array(pcs)
        print(f"point_count: min={arr.min()} p50={int(np.median(arr))} max={arr.max()}")
    # 0 点对象按帧分布, 判断"家具是否真的出 ROI"还是"空帧"
    if n_zero:
        zeros = [(fi, oid) for fi, oid, p in pc_stats if p == 0]
        zf = {}
        for fi, oid in zeros:
            zf.setdefault(fi, []).append(oid)
        print(f"0 点对象帧分布: {len(zf)} 帧; 前 5 帧: {sorted(zf.keys())[:5]}")

    if args.report_only:
        return
    if not args.yes:
        print("\n[DRY-RUN] 未写盘未 freeze。加 --yes 实做。")
        return

    bak = DRAFT + ".reselect_bak"
    if not os.path.exists(bak):
        shutil.copy2(DRAFT, bak)
        print(f"[BACKUP] {bak}")
    with open(DRAFT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"[WRITE] {DRAFT}")

    body = json.dumps({"sid": SID, "annotator": doc.get("annotator", "annotator-1")}).encode("utf-8")
    req = urllib.request.Request(SERVER + "/api/gt/freeze", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        resp = json.loads(e.read().decode("utf-8"))
        print(f"[FREEZE FAIL] HTTP {e.code}")
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        sys.exit(3)
    print(f"[FREEZE] {json.dumps(resp, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
