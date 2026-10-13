# -*- coding: utf-8 -*-
"""HFUS-RD-02 工作二：构建人工审核队列（冻结、可复跑、分层抽样）。

依据工作一审计：
  - S1 (175227) 644 候选：10 个 n30-59 / 72 个 n60-199 / 304 个 n200-999 /
    258 个 n>=2000。RF 的 FP 集中在 n200-999（100% 被接受）→ 该桶优先。
  - 其他会话困难负例：S3-near (175429) 高 prob 但无 GT 交集的候选（Casebook FC-5）。

抽样（seed=20261012 固定，先冻结后跑）：
  S1: A(30-59) 全 10 + B(60-199) 30 + C(200-999) 50 + D(>=2000) 15  = 105
  S3-near: prob>=0.7 且无 GT 交集候选 20
  合计 ~125 条。

每条携带：quest id / sid / frame / cand_id / pointset_sha256(不可篡改绑定) /
n / prob / decision / bbox尺寸 / 采样点(leveled, 供审核台渲染)。

输出 work/review_queue.json（冻结产物，审核台只读）。
标注写入 work/review_labels.jsonl（append-only，未审核=UNKNOWN 不落盘）。

ponytail: 复用 common.py 的 ledger 流式读；只有 S1/S3-near 两个会话需要扫。
"""
import json
import os
import random
import sys
from collections import defaultdict

import numpy as np

_RD1 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "HFUS-RD-01", "tools")
sys.path.insert(0, os.path.abspath(_RD1))
import common as C  # noqa: E402

WORK = os.path.join(C.REPO, "sidequests", "HFUS-RD-02", "work")
os.makedirs(WORK, exist_ok=True)
SEED = 20261012
S1 = "cap_20261010_175227"
S3N = "cap_20261010_175429"
MAX_PTS_STORE = 1200     # 每条候选最多存 1200 点（可视化够用）
BUCKETS = {"A_30_59": (30, 59), "B_60_199": (60, 199),
           "C_200_999": (200, 999), "D_2000p": (2000, 10 ** 9)}
QUOTA = {"A_30_59": 10, "B_60_199": 30, "C_200_999": 50, "D_2000p": 15}
QUOTA_S3N = 20


def bucket_of(n):
    for k, (lo, hi) in BUCKETS.items():
        if lo <= n <= hi:
            return k
    return "E_mid_1000_1999"


def collect(sid, want_gt_intersect=False, prob_min=None):
    """流式扫 ledger，收候选（含 valid 局部点 → leveled 坐标）。"""
    mm = None
    meta = C.load_meta(sid)
    out = []
    # GT 交集需要逐帧 GT；S3-near 用它过滤"无 GT 交集"
    gt = C.load_gt(sid)
    objs_by_frame = defaultdict(list)
    if gt:
        for o in gt["objects"]:
            if (o["class_name"] == "PERSON"
                    and o["review_status"] == "reviewed"
                    and o["source"] == "human"):
                objs_by_frame[o["frame_idx"]].append(o)
    for rec in C.iter_ledger(sid, fields=["frame_index", "candidates"]):
        fi = rec["frame_index"]
        cands = rec.get("candidates") or []
        if not cands:
            continue
        need = False
        for c in cands:
            if prob_min is not None and (c.get("prob") or 0) < prob_min:
                continue
            need = True
            break
        if not need:
            continue
        xyz, _i, mm = C.read_frame_xyz(sid, fi, mm=mm)
        lev = C.level(xyz)
        raw_of_leaf = np.nonzero(np.isfinite(xyz).all(axis=1)
                                 & (xyz != 0).any(axis=1))[0]
        gt_sets = [set(C.gt_raw_indices(o, raw_of_leaf).tolist())
                   for o in objs_by_frame.get(fi, [])]
        for c in cands:
            p = c.get("prob")
            if prob_min is not None and (p or 0) < prob_min:
                continue
            raw_idx = np.asarray(c["raw_indices"], dtype=np.int64)
            if want_gt_intersect:
                cs = set(raw_idx.tolist())
                if any(len(cs & gs) >= max(1, len(gs) // 10)
                       for gs in gt_sets):
                    continue   # 有 GT 交集 → 跳过（只要纯困难负例候选）
            pts = lev[raw_idx]
            # 采样存点（均匀抽稀，保形）
            if len(pts) > MAX_PTS_STORE:
                sel = np.linspace(0, len(pts) - 1, MAX_PTS_STORE).astype(int)
                pts_s = pts[sel]
            else:
                pts_s = pts
            out.append({
                "sid": sid, "frame": int(fi), "cand_id": c["id"],
                "pointset_sha256": c.get("pointset_sha256"),
                "n": int(c.get("n", len(raw_idx))),
                "prob": round(float(p), 6) if p is not None else None,
                "decision": c.get("decision"),
                "bucket": bucket_of(int(c.get("n", len(raw_idx)))),
                "zmin": round(float(pts[:, 2].min()), 3),
                "zmax": round(float(pts[:, 2].max()), 3),
                "size_x": round(float(np.ptp(pts[:, 0])), 3),
                "size_y": round(float(np.ptp(pts[:, 1])), 3),
                "size_z": round(float(np.ptp(pts[:, 2])), 3),
                "cx": round(float(pts[:, 0].mean()), 3),
                "cy": round(float(pts[:, 1].mean()), 3),
                "pts": [[round(float(v), 3) for v in q] for q in pts_s],
            })
        if len(out) > 4000:
            break
    return out


def main():
    rng = random.Random(SEED)
    print("[w2] collect S1 ...")
    s1 = collect(S1)
    print("[w2]   S1 candidates =", len(s1))
    by_b = defaultdict(list)
    for c in s1:
        by_b[c["bucket"]].append(c)
    queue = []
    for b, q in QUOTA.items():
        pool = sorted(by_b.get(b, []), key=lambda x: -(x["prob"] or 0))
        # 高 prob 优先（最像人的先审）+ 均匀补
        take = pool[:q]
        queue.extend(take)
        print("[w2]   %s: pool=%d take=%d" % (b, len(pool), len(take)))
    # 未进 QUOTA 的桶（如 1000-1999）如存在也看一眼
    for b, pool in by_b.items():
        if b not in QUOTA and pool:
            take = pool[:10]
            queue.extend(take)
            print("[w2]   extra %s: take=%d" % (b, len(take)))

    print("[w2] collect S3-near hard-neg hard candidates ...")
    s3 = collect(S3N, want_gt_intersect=False, prob_min=0.70)
    # 只留"高 prob 且(经上面已排除有GT交集)"的——重新过滤 GT 交集
    # collect 里 want_gt_intersect=False 表示不过滤；这里再收一次带过滤
    print("[w2]   S3N prob>=0.70 =", len(s3))
    gt = C.load_gt(S3N)
    # 简化：用已存 pts 无法反推 GT；改为信任 collect 的第二遍
    s3b = collect(S3N, want_gt_intersect=True, prob_min=0.70)
    print("[w2]   S3N prob>=0.70 且无GT交集 =", len(s3b))
    pool3 = sorted(s3b, key=lambda x: -(x["prob"] or 0))
    take3 = pool3[:QUOTA_S3N]
    for c in take3:
        c["bucket"] = "S3N_HARDNEG"
        c["note"] = "高prob无GT交集（Casebook FC-5 类）"
    queue.extend(take3)
    print("[w2]   S3N take =", len(take3))

    for i, c in enumerate(queue):
        c["qid"] = "Q%03d" % i
    # 五类家具 subtype 桶提示（供审核时心理分类）：按形状粗分组
    out = {
        "date": "2026-10-12", "seed": SEED,
        "quota": QUOTA, "quota_s3n": QUOTA_S3N,
        "n_items": len(queue),
        "buckets_summary": {b: sum(1 for c in queue if c["bucket"] == b)
                            for b in set(c["bucket"] for c in queue)},
        "split_note": ("会话级划分沿用 common.FOLDS：S1∈train、S3-near∈train；"
                       "S4/S8 UNK 未纳入本轮队列（须先确认帧内人在场）。"
                       "审核标签只增补 reviewed 负例，不改动 fold 定义。"),
        "items": queue,
    }
    op = os.path.join(WORK, "review_queue.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print("[w2] written", op, "n =", len(queue))


if __name__ == "__main__":
    main()
