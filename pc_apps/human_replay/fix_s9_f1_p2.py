#!/usr/bin/env python3
# 给 cap_20261010_180751 (S9) 补 f=1 缺失的 P2 对象。
# 因为 f=0 P2 / f=2 P2 同位置站桩，直接以 f=2 P2 的几何 + point_count 克隆到 f=1。
# 克隆的对象 source=propagated（不是 human，因为它来自 paste 语义而非手画）。
# 之后走 server /api/gt/freeze 出 V3。
# 用法: python fix_s9_f1_p2.py [--yes]

import argparse
import copy
import json
import os
import shutil
import sys
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
SID = "cap_20261010_180751"
DRAFT = os.path.join(HERE, "gt_store", SID, "draft.json")
SERVER = "http://127.0.0.1:8901"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    with open(DRAFT, "r", encoding="utf-8") as f:
        doc = json.load(f)
    objs = doc["objects"]
    fo = doc["frames_objects"]

    # 找 f=1 / f=2 的 P2 / P1 状态
    f1_oids = fo.get("1", [])
    p2_at_f1 = [o for o in (objs[x] for x in f1_oids) if o.get("track_id") == "P2"]
    if p2_at_f1:
        print("f=1 已有 P2:", [o["object_id"] for o in p2_at_f1])
        sys.exit(0)
    p2_f2_oid = next((x for x in (fo.get("2") or []) if objs[x].get("track_id") == "P2"), None)
    if not p2_f2_oid:
        print("[ABORT] f=2 无 P2 可克隆")
        sys.exit(2)
    p2_f2 = objs[p2_f2_oid]

    # 构造 f=1 P2 克隆
    clone = copy.deepcopy(p2_f2)
    clone["object_id"] = "obj_f1_p2_propagated"    # 唯一,避 f1 前缀撞 n*
    clone["frame_idx"] = 1
    clone["frame_id"] = f"{SID}:1"
    clone["timestamp"] = (p2_f2["timestamp"] + objs[next(x for x in fo["0"] if objs[x].get("track_id") == "P2")]["timestamp"]) / 2
    clone["parent_object_id"] = p2_f2_oid
    clone["source"] = "propagated"     # 不再冒 human；:propagated 终态可 reviewed (工单认可)
    clone["review_status"] = "reviewed"
    if "is_keyframe" in clone: del clone["is_keyframe"]

    plan = {
        "will_add": clone["object_id"],
        "frame_idx": 1, "track": "P2",
        "n_points": clone.get("point_count"),
        "clone_from": p2_f2_oid,
        "source": "propagated",
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))

    if not args.yes:
        print("\n[DRY-RUN] 未写盘未 freeze。加 --yes 实做。")
        return

    # 备份 + 写
    bak = DRAFT + ".fix_s9_f1_p2_bak"
    if not os.path.exists(bak):
        shutil.copy2(DRAFT, bak)
        print(f"[BACKUP] {bak}")

    objs[clone["object_id"]] = clone
    fo.setdefault("1", []).append(clone["object_id"])

    with open(DRAFT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"[WRITE] {DRAFT}")

    # freeze
    body = json.dumps({"sid": SID, "annotator": "annotator-1"}).encode("utf-8")
    req = urllib.request.Request(SERVER + "/api/gt/freeze", data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        resp = json.loads(e.read().decode("utf-8"))
        print(f"[FREEZE FAIL] HTTP {e.code}: {resp}")
        sys.exit(3)
    print(f"[FREEZE] {json.dumps(resp, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
