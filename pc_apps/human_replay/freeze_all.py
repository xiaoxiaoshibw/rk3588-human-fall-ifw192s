#!/usr/bin/env python3
# 批量: 把所有 draft 会话批 reviewed + 补 track_id (PERSON) + 调 server freeze。
# 用法: python freeze_all.py [--yes]
# 默认 dry-run。--yes 实写 draft 并 HTTP 调 freeze。
# 跳过: 已冻结过 / 无 draft / 缺 annotator 且补不了。

import argparse
import json
import os
import shutil
import sys
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
GT_STORE = os.path.join(HERE, "gt_store")
SERVER = "http://127.0.0.1:8901"


def http_post(path, payload):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(SERVER + path, data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def approve_one(sid, do_write):
    """返回 (ok, msg, plan) — 只改 draft,不 freeze。"""
    draft_path = os.path.join(GT_STORE, sid, "draft.json")
    if not os.path.isfile(draft_path):
        return False, "无 draft.json", None
    with open(draft_path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("frozen_versions"):
        return False, f"已冻结 {len(doc['frozen_versions'])} 个版本", None

    objs = doc.get("objects") or {}
    n = len(objs)
    if n == 0:
        return False, "无对象", None

    # 清污: E2E 测试写入的占位对象 (annotator='e2e' 且 point_count=0) 删除
    bad_oids = [oid for oid, o in objs.items()
                if o.get("annotator") == "e2e" and not (o.get("point_count", 0) > 0)]
    n_cleaned = len(bad_oids)
    if bad_oids:
        for oid in bad_oids:
            del objs[oid]
        # frames_objects 同步去引用
        fo = doc.get("frames_objects") or {}
        for f, oids in fo.items():
            fo[f] = [x for x in oids if x not in set(bad_oids)]
        # doc.annotator 是 e2e → 重置成 annotator-1
        if doc.get("annotator") == "e2e":
            doc["annotator"] = "annotator-1"
        n = len(objs)
        if n == 0:
            return False, f"清污后无对象 (删除 {n_cleaned} 个 e2e 占位)", None

    # 预检 hard requirements (清污后复测)
    n_no_pts = sum(1 for o in objs.values() if not o.get("raw_point_indices"))
    n_no_pc = sum(1 for o in objs.values() if not (o.get("point_count", 0) > 0))
    if n_no_pts or n_no_pc:
        return False, f"缺点索引 {n_no_pts} / 点数非正 {n_no_pc}", None

    if not doc.get("annotator"):
        doc["annotator"] = "annotator-1"

    # 同帧 track 冲突预检 (PERSON 同 track_id)
    from collections import defaultdict
    pers_by_frame = defaultdict(list)
    for oid, o in objs.items():
        if o.get("class_name") == "PERSON":
            pers_by_frame[o.get("frame_idx")].append((oid, o.get("track_id")))
    # 已存在 track 冲突: 同帧同 tid 多对象
    conflicts = []
    for f, lst in pers_by_frame.items():
        seen = defaultdict(list)
        for oid, tid in lst:
            if tid: seen[tid].append(oid)
        for tid, oids in seen.items():
            if len(oids) > 1: conflicts.append((f, tid, len(oids)))

    # 多人帧: 同帧含 > 1 个 PERSON
    multi_person_frames = sum(1 for f, l in pers_by_frame.items() if len(l) > 1)

    plan = {
        "sid": sid, "objects": n, "cleaned_e2e": n_cleaned,
        "frames": len(doc.get("frames_objects") or {}),
        "persons": sum(1 for o in objs.values() if o.get("class_name") == "PERSON"),
        "persons_track_ids": sorted({o.get("track_id") for o in objs.values() if o.get("class_name") == "PERSON" and o.get("track_id")}),
        "conflicts": len(conflicts),
        "multi_person_frames": multi_person_frames,
        "reviewed_before": sum(1 for o in objs.values() if o.get("review_status") == "reviewed"),
        "tid_before": sum(1 for o in objs.values() if o.get("class_name") == "PERSON" and o.get("track_id")),
    }

    if conflicts:
        plan["conflict_examples"] = conflicts[:5]
        return False, f"同帧同 track 冲突 {len(conflicts)} 处", plan

    # 多人帧但只有一个 track_id: 需要人工把第二个 track 分出来,不批
    if multi_person_frames > 0 and len(plan["persons_track_ids"]) <= 1:
        return False, f"疑似双人/多人会话但 track 未分开 ({multi_person_frames} 多人帧, 仅 {len(plan['persons_track_ids'])} track)", plan

    # 批量改: reviewed + PERSON 缺 tid 补 t1
    for oid, o in objs.items():
        o["review_status"] = "reviewed"
        if o.get("class_name") == "PERSON" and not o.get("track_id"):
            o["track_id"] = "t1"
    doc["review_status"] = "reviewed"

    if do_write:
        bak = draft_path + ".freeze_all_bak"
        if not os.path.exists(bak):
            shutil.copy2(draft_path, bak)
        with open(draft_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=True)
    return True, "ok", plan


def freeze_one(sid, annotator):
    status, resp = http_post("/api/gt/freeze", {"sid": sid, "annotator": annotator})
    return status, resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--sids", nargs="*", default=None, help="只处理指定 sid")
    args = ap.parse_args()

    sids = sorted(d for d in os.listdir(GT_STORE)
                  if os.path.isdir(os.path.join(GT_STORE, d)))
    if args.sids:
        sids = [s for s in sids if s in args.sids]

    print(f"模式: {'实写+freeze' if args.yes else 'DRY-RUN'}")
    print(f"目标: {len(sids)} 会话")
    print()

    results = []
    for sid in sids:
        ok, msg, plan = approve_one(sid, do_write=args.yes)
        status = "OK" if ok else "SKIP"
        print(f"[{status}] {sid}: {msg}")
        if plan:
            print(f"       帧={plan['frames']} 对象={plan['objects']} PERSON={plan['persons']} 多人帧={plan['multi_person_frames']} rev {plan['reviewed_before']}->全 tid {plan['tid_before']}->PERSON 清污e2e={plan['cleaned_e2e']}")
            if plan.get("conflict_examples"):
                print(f"       冲突: {plan['conflict_examples']}")
        results.append((sid, ok, msg, plan))

    if not args.yes:
        print("\n[DRY-RUN] 没写盘没 freeze。加 --yes 实做。")
        return

    # freeze 阶段
    print("\n=== freeze 阶段 ===")
    freeze_res = []
    for sid, ok, msg, plan in results:
        if not ok:
            continue
        status, resp = freeze_one(sid, "annotator-1")
        ok_fr = resp.get("ok")
        ver = resp.get("version")
        err = resp.get("error", "")
        print(f"[{'OK' if ok_fr else 'FAIL'}] {sid}: status={status} {ver or ''} {err if not ok_fr else ''}")
        freeze_res.append((sid, ok_fr, ver, err))

    n_ok = sum(1 for _, k, _, _ in freeze_res if k)
    print(f"\nfreeze 成功 {n_ok}/{len(freeze_res)}")


if __name__ == "__main__":
    main()
