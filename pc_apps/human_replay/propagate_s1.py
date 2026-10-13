#!/usr/bin/env python3
# S1 (cap_20261010_175227, 静止空场+家具): f=0 6个对象 propagate 到全部 304 帧。
# 每个 propagated 克隆: source=propagated / review_status=reviewed / parent=源对象。
# FURNITURE/BACKGROUND 不需要 track_id (freeze 校验只 PERSON 要)。
# 然后所有对象批 reviewed + 走 server freeze。
# 用法: python propagate_s1.py [--yes]

import argparse
import copy
import json
import os
import shutil
import sys
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
SID = "cap_20261010_175227"
N_FRAMES = 304     # 与 SESSION_DATASET_MANIFEST.json 一致
DRAFT = os.path.join(HERE, "gt_store", SID, "draft.json")
SERVER = "http://127.0.0.1:8901"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(DRAFT):
        print(f"无 draft: {DRAFT}")
        sys.exit(1)

    with open(DRAFT, "r", encoding="utf-8") as f:
        doc = json.load(f)
    objs = doc.get("objects") or {}
    fo = doc.get("frames_objects") or {}

    # 用户标的是哪一帧? 应该是 f=0
    src_frame = None
    for f_str, oids in fo.items():
        if oids:
            src_frame = int(f_str)
            break
    if src_frame is None:
        print("[ABORT] draft 里没有任何已标帧")
        sys.exit(2)
    src_oids = fo[str(src_frame)]
    print(f"源帧 f={src_frame}, 对象数={len(src_oids)}")
    for oid in src_oids:
        o = objs[oid]
        print(f"  {oid}: class={o.get('class_name')} x={o.get('x')} y={o.get('y')} poly={len(o.get('polygon_xy') or [])} 顶点")

    # doc.annotator 必填
    if not doc.get("annotator"):
        doc["annotator"] = "annotator-1"

    # 构造 304 帧 propagate 计划
    propagate_plan = []
    for f in range(N_FRAMES):
        if f == src_frame:
            continue
        for src_oid in src_oids:
            propagate_plan.append((f, src_oid))

    print(f"\n传播计划: {len(propagate_plan)} 个克隆 = {N_FRAMES - 1} 帧 × {len(src_oids)} 对象")
    print(f"预计总对象数: {len(objs) + len(propagate_plan)}")

    if not args.yes:
        print("\n[DRY-RUN] 未写盘未 freeze。加 --yes 实做。")
        return

    # 备份
    bak = DRAFT + ".propagate_bak"
    if not os.path.exists(bak):
        shutil.copy2(DRAFT, bak)
        print(f"[BACKUP] {bak}")

    # 先标记所有现有对象为 reviewed
    seq = max(int(o.get("object_id", "obj_f0_n0").rsplit("_n", 1)[-1]) if "_n" in o.get("object_id", "") else 0 for o in objs.values()) + 1
    for oid, o in objs.items():
        o["review_status"] = "reviewed"
        # FURNITURE/BACKGROUND 不需要 track_id
        # 保持 track_id 为 None（freeze 校验：PERSON 才需要 track_id）

    # 传播
    for f, src_oid in propagate_plan:
        src = objs[src_oid]
        c = copy.deepcopy(src)
        new_oid = f"obj_f{f}_n{seq}"; seq += 1
        c["object_id"] = new_oid
        c["frame_idx"] = f
        c["frame_id"] = f"{SID}:{f}"
        c["parent_object_id"] = src_oid
        c["source"] = "propagated"
        c["review_status"] = "reviewed"
        # 时间戳: 按 frame_rate 9.54fps 估计, 不重要
        c["timestamp"] = src.get("timestamp")
        if "is_keyframe" in c: del c["is_keyframe"]
        objs[new_oid] = c
        fo.setdefault(str(f), []).append(new_oid)

    doc["review_status"] = "reviewed"

    with open(DRAFT, "w", encoding="utf-8") as ff:
        json.dump(doc, ff, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"[WRITE] {DRAFT}  total_objects={len(objs)}")

    # freeze
    body = json.dumps({"sid": SID, "annotator": doc["annotator"]}).encode("utf-8")
    req = urllib.request.Request(SERVER + "/api/gt/freeze", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        resp = json.loads(e.read().decode("utf-8"))
        print(f"[FREEZE FAIL] HTTP {e.code}")
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        sys.exit(3)
    print(f"[FREEZE]")
    print(json.dumps(resp, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
