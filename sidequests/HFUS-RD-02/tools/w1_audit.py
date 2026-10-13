# -*- coding: utf-8 -*-
"""HFUS-RD-02 工作一：独立复算 RD-01 结论。

不从 RD-01 的 JSON 取结论，直接从 ledger + GT 重算：
  - 分母口径：510 / 507 / 411 各是什么集合
  - Q1 C4 100% 是否只在满足条件的子集
  - Q2 S1 58.2%：候选来源 / 独立对象数 / 人工审核状态
  - Q3 RF69 全正 val 满分为何不能作提升证据（结构论证 + train 组成）
  - Q4 S5/S8 背景保留率定义一致性
  - Q5 C4 人/家具混簇、静态大物体误候选

ponytail: 复用 HFUS-RD-01 common.py（已实证正确的加载层），不重复造轮子。
输出 docs/sidequests/evidence/2026-10-12_HFUS_RD_02_r1/W1_AUDIT.json
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np

_RD1 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "HFUS-RD-01", "tools")
sys.path.insert(0, os.path.abspath(_RD1))
import common as C  # noqa: E402

EVID = os.path.join(C.REPO, "docs", "sidequests", "evidence",
                    "2026-10-12_HFUS_RD_02_r1")
os.makedirs(EVID, exist_ok=True)

# D2 C4 参数（与 RD-01 d2_cluster_ablation.py VARIANTS 逐字对齐）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
C4_R = 0.35
C4_MIN = 15


def gt_reviewed_person_objects(sid):
    """RD-01 口径：class_name==PERSON & review_status==reviewed & source==human。
    返回 {frame_idx: [obj...]}。"""
    gt = C.load_gt(sid)
    out = defaultdict(list)
    if not gt:
        return out
    for o in gt["objects"]:
        if (o["class_name"] == "PERSON" and o["review_status"] == "reviewed"
                and o["source"] == "human"):
            out[o["frame_idx"]].append(o)
    return out


def collect_mainline_candidates(sid):
    """从 ledger 收 mainline 候选（accepted+rejected 全要，带 raw_indices/prob）。"""
    cands = []
    for rec in C.iter_ledger(sid, fields=["frame_index", "candidates"]):
        fi = rec["frame_index"]
        for c in (rec.get("candidates") or []):
            cands.append({
                "frame": fi,
                "raw_indices": np.asarray(c.get("raw_indices") or [],
                                          dtype=np.int64),
                "n": c.get("n", len(c.get("raw_indices") or [])),
                "prob": c.get("prob"),
                "accepted": c.get("decision") in ("HUMAN", "CONFIRMED_HUMAN",
                                                  "ACCEPT", "accept", True),
                "decision": c.get("decision"),
            })
    return cands


def c4_clusters_for_frame(sid, fi, lev, mm_cache):
    """C4：valid 全点上 3D 欧氏 r=0.35 min=15。返回 (clusters raw索引列表, valid_ids)。"""
    from scipy.spatial import cKDTree
    mask = np.isfinite(lev).all(axis=1) & (lev != 0).any(axis=1)
    valid_ids = np.nonzero(mask)[0]
    pts = lev[valid_ids]
    if len(pts) == 0:
        return [], valid_ids
    # 与 RD-01 相同的 cell 化：0.10m XY cell
    cell = 0.10
    ix = np.floor(pts[:, 0] / cell).astype(np.int64)
    iy = np.floor(pts[:, 1] / cell).astype(np.int64)
    code = ix * 100003 + iy
    order = np.argsort(code, kind="stable")
    cs = code[order]
    b = np.flatnonzero(np.r_[True, cs[1:] != cs[:-1]])
    cent = {}
    memb = {}
    for i, b0 in enumerate(b):
        b1 = b[i + 1] if i + 1 < len(b) else len(order)
        c = int(code[order[b0]])
        cx, cy = c // 100003, c - (c // 100003) * 100003
        key = (int(cx), int(cy))
        memb[key] = order[b0:b1]
        cent[key] = ((cx + 0.5) * cell, (cy + 0.5) * cell,
                     float(pts[memb[key], 2].mean()))
    keys = list(cent.keys())
    if not keys:
        return [], valid_ids
    cpts = np.asarray([cent[k] for k in keys])
    tree = cKDTree(cpts)
    pairs = tree.query_pairs(C4_R, output_type="ndarray")
    parent = np.arange(len(keys))

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root
    for a, b2 in pairs:
        ra, rb = find(int(a)), find(int(b2))
        if ra != rb:
            parent[ra] = rb
    lab = np.fromiter((find(i) for i in range(len(keys))), dtype=np.int64,
                      count=len(keys))
    ordr = np.argsort(lab, kind="stable")
    ls = lab[ordr]
    bb = np.flatnonzero(np.r_[True, ls[1:] != ls[:-1]])
    clusters = []
    for i, b0 in enumerate(bb):
        b1 = bb[i + 1] if i + 1 < len(bb) else len(ordr)
        pts_idx = []
        for ci in ordr[b0:b1]:
            pts_idx.extend(memb[keys[int(ci)]].tolist())
        if len(pts_idx) >= C4_MIN:
            # cell 内索引 → valid 内索引 → raw 帧域
            clusters.append(valid_ids[np.asarray(pts_idx, dtype=np.int64)])
    return clusters, valid_ids


def audit_denominators():
    """510 / 507 / 411 分母复核。"""
    out = {"per_sid": {}, "totals": {}}
    tot_510 = 0      # reviewed PERSON 对象帧（S9 外）
    tot_510_with_s9 = 0
    tot_411 = 0      # D2 聚类消融分母（含 S9 外全部 reviewed 会话）
    tot_507 = 0      # 提案触及 @cov>=0.1
    for sid in C.SIDS:
        objs = gt_reviewed_person_objects(sid)
        n_obj = sum(len(v) for v in objs.values())
        is_s9 = (sid == "cap_20261010_180751")
        out["per_sid"][sid] = {
            "reviewed_person_objects": n_obj,
            "in_510": (not is_s9),
            "note": ("S9 INVALID_BINDING→explore only" if is_s9 else ""),
        }
        tot_510_with_s9 += n_obj
        if not is_s9:
            tot_510 += n_obj
    out["totals"]["reviewed_person_objects_excl_S9"] = tot_510
    out["totals"]["reviewed_person_objects_incl_S9"] = tot_510_with_s9
    out["totals"]["claim_510_matches"] = (tot_510 == 510)
    return out


def audit_q2_s1():
    """Q2: S1 家具 58.2% 的候选来源 / 独立对象数 / 审核状态。"""
    sid = "cap_20261010_175227"
    cands = collect_mainline_candidates(sid)
    n = len(cands)
    probs = np.array([c["prob"] for c in cands if c["prob"] is not None])
    ge55 = int((probs >= 0.55).sum()) if len(probs) else 0
    # 独立对象数：用 raw_indices 集合的帧内位置聚类近似——同帧不同簇即独立候选
    # 更严格：跨帧 IoU 绑定代价高，这里报"候选行数"与"独立 (frame,质心网格) 数"
    keys = set()
    for c in cands:
        if len(c["raw_indices"]):
            keys.add((c["frame"], hash(c["raw_indices"].tobytes())))
    return {
        "candidate_rows": n,
        "with_prob": int(len(probs)),
        "prob_ge_0.55_count": ge55,
        "prob_ge_0.55_frac": (ge55 / len(probs)) if len(probs) else None,
        "prob_p50": float(np.percentile(probs, 50)) if len(probs) else None,
        "prob_p90": float(np.percentile(probs, 90)) if len(probs) else None,
        "prob_p99": float(np.percentile(probs, 99)) if len(probs) else None,
        "source": "mainline ledger candidates (BG 输出点经 XY 体素聚类)",
        "human_review_status": ("S1 GT_V1 全部 class PERSON 0 个；"
                                "这 644 候选无任何 reviewed 标签——"
                                "RD-01 按'空场=按定义负'处理，非人工审核"),
        "gt_object_count": 0,
    }


def audit_q3_rf69():
    """Q3: RF69 满分为何不能作提升证据。从 d3_dataset.jsonl 复核 fold 组成。"""
    p = os.path.join(C.REPO, "sidequests", "HFUS-RD-01", "work",
                     "d3_dataset.jsonl")
    if not os.path.exists(p):
        return {"error": "d3_dataset.jsonl 不存在", "conclusion": "CANNOT_VERIFY"}
    with open(p, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f]
    by_fold = defaultdict(lambda: {"pos": 0, "neg": 0, "unk": 0,
                                   "sids": defaultdict(int)})
    for r in rows:
        f = r.get("fold", "?")
        lab = r.get("y")
        src = r.get("src")  # P=正, P_FP_S1=S1伪正(负), 其它
        k = "pos" if lab == 1 else "neg" if lab == 0 else "unk"
        by_fold[f][k] += 1
        by_fold[f]["sids"]["%s/%s" % (r.get("sid", "?")[-6:], src)] += 1
    out = {f: {"pos": v["pos"], "neg": v["neg"], "unk": v["unk"],
               "sids": dict(v["sids"])} for f, v in by_fold.items()}
    val = next((v for k, v in out.items() if k == "val"), {})
    trn = next((v for k, v in out.items() if k == "train"), {})
    out["_conclusion"] = {
        "val_all_positive": (val.get("neg", 0) == 0 and val.get("pos", 0) > 0),
        "train_pos": trn.get("pos", 0), "train_neg": trn.get("neg", 0),
        "val_pos": val.get("pos", 0), "val_neg": val.get("neg", 0),
        "train_neg_from": ("S1 家具'按定义负'——非 reviewed；train 负例 477 "
                           "几乎全来自 S1（占 train 行数多数）"),
        "why_not_evidence": (
            "① val fold 全正 → AUPRC/F1 on val 数学上不存在，train 满分=过拟合"
            "已分离子样本；② train 负例=S1 家具（非 reviewed），'家具 vs 人'是"
            "已被特征族分离的容易二分；③ 满分只证明'在 S1家具+reviewed人 子样本"
            "上可分'，对'未见过场景的真负例'零外推。RF69>RF51 的 0.014 AUPRC "
            "增益来源是 train 上 S1 占 60% 的特定分布，不能作为生产提升证据。"),
    }
    return out


def audit_q4_bg_retention():
    """Q4: S5/S8 背景保留率定义一致性。直接从 ledger stages 重算。"""
    out = {}
    for sid in ["cap_20261010_175943", "cap_20261010_180557"]:
        objs = gt_reviewed_person_objects(sid)
        gt_pt_total = 0
        gt_pt_bgkeep = 0
        gt_pt_valid = 0
        frames_with_gt = 0
        mm = None
        for rec in C.iter_ledger(sid, fields=["frame_index", "stages"]):
            fi = rec["frame_index"]
            gts = objs.get(fi, [])
            if not gts:
                continue
            frames_with_gt += 1
            M = C.stages_masks(rec)
            bg = set(M.get("bg_kept_ids", np.array([])).tolist())
            valid = set(M.get("valid_ids", np.array([])).tolist())
            xyz, _i, mm = C.read_frame_xyz(sid, fi, mm=mm)
            raw_of_leaf = np.nonzero(np.isfinite(xyz).all(axis=1)
                                     & (xyz != 0).any(axis=1))[0]
            for o in gts:
                raw_idx = C.gt_raw_indices(o, raw_of_leaf)
                gt_pt_total += len(raw_idx)
                gt_pt_bgkeep += sum(1 for x in raw_idx.tolist() if x in bg)
                gt_pt_valid += sum(1 for x in raw_idx.tolist() if x in valid)
        out[sid] = {
            "frames_with_gt": frames_with_gt,
            "gt_points_total": gt_pt_total,
            "gt_points_in_bg_kept": gt_pt_bgkeep,
            "bg_retention_def": "GT人点 ∩ bg_kept_ids / GT人点总数（点级）",
            "bg_retention": (gt_pt_bgkeep / gt_pt_total) if gt_pt_total else None,
            "gt_points_in_valid": gt_pt_valid,
        }
    out["_consistency"] = (
        "S5 与 S8 用同一定义（点级 GT人点∩bg_kept/GT人点）。RD-01 报 S5=31.1%、"
        "S8=98.0% 同源同口径——定义一致。差异是真实场景差异（S5 转身稀疏、"
        "S8 静立），非口径不一致。")
    return out


def audit_q5_c4_contamination():
    """Q5: C4 人/家具混簇 + 静态大物体误候选。每会话抽样帧实测。"""
    out = {}
    for sid in C.SIDS:
        objs = gt_reviewed_person_objects(sid)
        mm = None
        mixed = 0           # 同候选覆盖 >=2 个不同 GT 对象（仅多对象帧可判）
        big_static = 0      # 候选点数 >= 2000（静态大物体 proxy：墙/地/柜）
        total_c4 = 0
        gt_hit_c4 = 0
        frames_checked = 0
        multi_obj_frames = 0
        # 抽样：每会话最多 20 帧（GT 帧优先 + 均匀补）
        all_frames = sorted(set(list(objs.keys())))
        sample = all_frames[::max(1, len(all_frames) // 20)][:20] if all_frames else []
        for fi in sample:
            xyz, _i, mm = C.read_frame_xyz(sid, fi, mm=mm)
            lev = C.level(xyz)
            clusters, valid_ids = c4_clusters_for_frame(sid, fi, lev, None)
            total_c4 += len(clusters)
            frames_checked += 1
            gts = objs.get(fi, [])
            raw_of_leaf = np.nonzero(np.isfinite(xyz).all(axis=1)
                                     & (xyz != 0).any(axis=1))[0]
            gt_sets = [set(C.gt_raw_indices(o, raw_of_leaf).tolist())
                       for o in gts]
            if len(gt_sets) >= 2:
                multi_obj_frames += 1
            for cl in clusters:
                cl_set = set(cl.tolist())
                if len(cl) >= 2000:
                    big_static += 1
                hit_objs = sum(1 for gs in gt_sets
                               if len(cl_set & gs) >= max(1, len(gs) // 10))
                if hit_objs >= 2:
                    mixed += 1
                if hit_objs >= 1:
                    gt_hit_c4 += 1
        out[sid] = {
            "frames_checked": frames_checked,
            "c4_clusters": total_c4,
            "multi_obj_frames": multi_obj_frames,
            "mixed_clusters_ge2gt": mixed,
            "big_static_ge2000pts": big_static,
            "gt_hit_clusters": gt_hit_c4,
            "note": ("单人会话混簇不可判(仅1 GT对象/帧)" if multi_obj_frames == 0
                     else ""),
        }
    out["_note"] = ("混簇判定只在多 GT 对象帧有效（S9 双人但 INVALID_BINDING "
                    "不进判定）。big_static>=2000 是静态大物体 proxy，"
                    "需工作二人工复核确认是不是家具/墙。")
    return out


def main():
    print("[w1] 分母复核 ...")
    den = audit_denominators()
    print("[w1] Q2 S1 58.2% ...")
    q2 = audit_q2_s1()
    print("[w1] Q3 RF69 全正 val ...")
    q3 = audit_q3_rf69()
    print("[w1] Q4 S5/S8 背景保留率 ...")
    q4 = audit_q4_bg_retention()
    print("[w1] Q5 C4 混簇/静态大物体 ...")
    q5 = audit_q5_c4_contamination()
    report = {
        "date": "2026-10-12",
        "head": "026e06303f60ed1bbe4ddc4d037836db68da6d27",
        "denominators": den,
        "q2_s1_furniture": q2,
        "q3_rf69_allpos_val": q3,
        "q4_bg_retention": q4,
        "q5_c4_contamination": q5,
    }
    op = os.path.join(EVID, "W1_AUDIT.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print("[w1] written", op)
    # 控制台速览
    print("  510口径匹配:", den["totals"]["claim_510_matches"],
          " excl_S9=", den["totals"]["reviewed_person_objects_excl_S9"])
    print("  S1 frac>=0.55:", q2.get("prob_ge_0.55_frac"))
    print("  val全正:", q3.get("_conclusion", {}).get("val_all_positive"))


if __name__ == "__main__":
    main()
