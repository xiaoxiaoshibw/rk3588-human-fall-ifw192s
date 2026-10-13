#!/usr/bin/env python3
# 一键把指定 sid 的所有对象批 reviewed + 分 track_id，doc.review_status 升 reviewed。
# 用法:
#   python approve_session.py <sid> [--track-id t1] [--yes]
# 默认 DRY-RUN，只打印不写；加 --yes 才实写（先备份 draft.json.approve_bak）。
# 只做元数据，不动几何框/不 freeze（freeze 留给用户在 UI 上点）。

import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GT_STORE = os.path.join(HERE, "gt_store")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sid")
    ap.add_argument("--track-id", default="t1", help="要写入的 track_id（默认 t1；单人会话用这个就行）")
    ap.add_argument("--yes", action="store_true", help="真写盘；不带则 dry-run")
    args = ap.parse_args()

    draft_path = os.path.join(GT_STORE, args.sid, "draft.json")
    if not os.path.isfile(draft_path):
        print("找不到 draft:", draft_path)
        sys.exit(1)

    with open(draft_path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    objs = doc.get("objects") or {}
    n = len(objs)
    n_reviewed_before = sum(1 for o in objs.values() if o.get("review_status") == "reviewed")
    n_tid_before = sum(1 for o in objs.values() if o.get("track_id"))

    # 预检 freeze 会过的硬指标
    n_no_pts = sum(1 for o in objs.values() if not o.get("raw_point_indices"))
    n_no_pc = sum(1 for o in objs.values() if not (o.get("point_count", 0) > 0))
    if n_no_pts or n_no_pc:
        print(f"[ABORT] 有对象缺 raw_point_indices ({n_no_pts}) 或 point_count<=0 ({n_no_pc})，"
              f"freeze 一定被拒，先补数据再来。")
        sys.exit(2)
    if not doc.get("annotator"):
        print("[ABORT] doc.annotator 空。在 UI 标注者输入框填一下再存。")
        sys.exit(2)
    if not (doc.get("session_sha256") or {}).get("points"):
        print("[ABORT] doc.session_sha256.points 缺。")
        sys.exit(2)

    # 同帧 track 冲突预检（按目标 track_id）
    from collections import defaultdict
    by_frame = defaultdict(list)
    for oid, o in objs.items():
        if o.get("class_name") == "PERSON":
            by_frame[o.get("frame_idx")].append(oid)
    conflicts = {f: l for f, l in by_frame.items() if len(l) > 1}
    if conflicts:
        print(f"[ABORT] 有 {len(conflicts)} 帧同时含多个 PERSON，"
              f"同一 track_id 会冲突，先人工合并：{list(conflicts.items())[:3]}")
        sys.exit(2)

    plan = {
        "sid": args.sid,
        "objects": n,
        "reviewed_before": n_reviewed_before,
        "tid_before": n_tid_before,
        "track_id_to_write": args.track_id,
        "will_set_reviewed": n - n_reviewed_before,
        "will_set_track_id": n - n_tid_before,
        "doc_review_status_now": doc.get("review_status"),
        "doc_review_status_will_be": "reviewed",
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))

    if not args.yes:
        print("\n[DRY-RUN] 未写盘。加 --yes 实写。")
        return

    # 实写：先备份
    bak = draft_path + ".approve_bak"
    shutil.copy2(draft_path, bak)
    print(f"[BACKUP] {bak}")

    for oid, o in objs.items():
        o["review_status"] = "reviewed"
        if o.get("class_name") == "PERSON" and not o.get("track_id"):
            o["track_id"] = args.track_id

    doc["review_status"] = "reviewed"

    # 覆盖写（不走 server 原子写也无妨：草稿 locally edited，server 只读）
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"[WRITE] {draft_path}  n_objects={n}")
    print("现在到 UI 上点【冻结】就会生成 GT_V1.json。")


if __name__ == "__main__":
    main()
