# -*- coding: utf-8 -*-
"""finalize_c15_metrics.py — C1.5 最终指标聚合 (目标 5/6/7/8, 分析型, 生产零改动)。

诚实分层 (不凑数):
  - GT 坐标不可靠 (多标注员数格互斥) → 空间匹配只能在"探针 confirmed track 锚定"口径做,
    且仅对 GT 自洽会话 (154007 / 静态两段 / 空场)。143945 标 CONTESTED, 不算 recall。
  - 动态 confirmed-recall: 用 GT 真人区 (y≈2.2) 是否有持久 confirmed track 测量。
  - 独立样本 = 会话 (Wilson), 帧不作独立样本。
"""
import io
import json
import math
import os

WS = os.path.dirname(os.path.abspath(__file__))
GT = os.path.join(WS, "gt_labels")
THR = "0.55"


def load_tracks(root, sid):
    p = os.path.join(root, sid + ".tracks.jsonl")
    if not os.path.exists(p):
        return None
    out = {}
    for l in io.open(p, encoding="utf-8"):
        r = json.loads(l)
        out[r["frame"]] = r["per_thr"][THR]["tracks"]
    return out


def confirmed(tracks):
    return [t for t in tracks if t["confirmed_now"]]


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / den
    return (max(0, c - h), min(1, c + h))


# ---- 154007 动态会话: GT 真人区 y≈2.2 的 confirmed 覆盖 ----
def eval_154007(root):
    tr = load_tracks(root, "cap_20261007_154007")
    # GT chunk1: y≈2.1-2.4 walk region; chunk2: y≈2.3-2.5 stand (f42-82).
    # 判据 (与标注员口径一致): 真人活动区 = cy in [1.7, 3.0] (覆盖 GT y≈2.1-2.5 + 锚定余量)。
    frames = sorted(tr.keys())
    gt_person_frames = [f for f in frames if f <= 82]   # 全程有人 (chunk1+2)
    cov = 0
    low_prob_short = 0
    tgt_ids = []
    track_id_set = set()
    for f in gt_person_frames:
        c = confirmed(tr[f])
        # 真人区 confirmed?
        inregion = [t for t in c if 1.7 <= t["cy"] <= 3.0]
        if inregion:
            cov += 1
            for t in inregion:
                track_id_set.add(t["id"])
        # 记录全場 confirmed ids (供 id-switch)
        tgt_ids.append(tuple(sorted(t["id"] for t in c)))
    # ID switch (全场 confirmed id 集合相邻变化次数) — 粗糙 proxy
    switches = 0
    for i in range(1, len(tgt_ids)):
        if tgt_ids[i] != tgt_ids[i - 1]:
            switches += 1
    n = len(gt_person_frames)
    return {
        "gt_person_frames": n,
        "person_region_confirmed_frames": cov,
        "person_region_confirmed_recall": round(cov / n, 4) if n else None,
        "distinct_confirmed_ids_in_person_region": len(track_id_set),
        "confirmed_id_set_changes_all_tracks": switches,
        "note": "GT真人区 cy∈[1.7,3.0]; 探针confirmed多集中 y<0.75 非人静态簇",
    }


# ---- 静态会话 (114340/114254): 主 confirmed track 持续保留 ----
def eval_still(root, sid):
    tr = load_tracks(root, sid)
    frames = sorted(tr.keys())
    pres = 0
    ids = []
    for f in frames:
        c = confirmed(tr[f])
        if c:
            pres += 1
            ids.append(tuple(sorted(t["id"] for t in c)))
    # still-retention: 主 confirmed track 持续存在的帧占比
    switches = sum(1 for i in range(1, len(ids)) if ids[i] != ids[i - 1])
    return {"frames": len(frames), "confirmed_present_frames": pres,
            "still_retention": round(pres / len(frames), 4), "confirmed_id_set_changes": switches}


# ---- 空场 FP ----
def eval_empty(root):
    tr = load_tracks(root, "cap_20261009_113611")
    frames = sorted(tr.keys())
    fp = sum(len(confirmed(tr[f])) for f in frames)
    return {"frames": len(frames), "confirmed_fp_events": fp}


def main():
    out = {"generated": "2026-10-10 C1.5", "threshold": THR, "independent_unit": "session",
           "gt_quality": {
               "coordinate_gt": "UNRELIABLE (multi-labeller grid-count disagreement; 143945 x=0.55/1.9/3.4 互斥)",
               "usable": "categorical present/activity for self-consistent sessions only",
               "contested": ["cap_20261007_143945"],
           }}
    res = {}
    for tag, root in (("v1_no_gate", os.path.join(WS, "probe_v1")), ("v2_hard_gate", os.path.join(WS, "probe_v2"))):
        r = {}
        r["dyn_154007"] = eval_154007(root)
        r["still_114340"] = eval_still(root, "cap_20261008_114340")
        r["still_114254"] = eval_still(root, "cap_20261008_114254")
        res[tag] = r
    res["v1_no_gate"]["empty_113611_fp"] = eval_empty(os.path.join(WS, "probe_v1"))
    out["results"] = res

    # 硬门 A/B: 少点误杀 — 动态/静止会话 recall delta
    ab = {}
    for key in ("dyn_154007", "still_114340", "still_114254"):
        a = res["v1_no_gate"][key]
        b = res["v2_hard_gate"][key]
        if "person_region_confirmed_recall" in a:
            ab[key] = {"recall_v1": a["person_region_confirmed_recall"],
                       "recall_v2": b["person_region_confirmed_recall"],
                       "delta": round((b["person_region_confirmed_recall"] or 0) - (a["person_region_confirmed_recall"] or 0), 4)}
        else:
            ab[key] = {"retention_v1": a["still_retention"], "retention_v2": b["still_retention"],
                       "delta": round((b["still_retention"] or 0) - (a["still_retention"] or 0), 4)}
    out["ab_hard_gate_effect"] = ab
    out["ab_note"] = "delta<0 = 硬门误杀 (recall/retention 降); 本批 GT 会话主导簇 n_pts>>500, 预期 delta≈0; R2 已证 6 静态段家具清零人零回归"

    # 段级 Wilson: 独立=会话
    # 动态样本仅 154007 可用 (143945 contested) → n=1, 无效 Wilson, 诚实标注
    dyn_recall = res["v1_no_gate"]["dyn_154007"]["person_region_confirmed_recall"]
    out["dynamic_recall"] = {
        "n_usable_sessions": 1, "session": "cap_20261007_154007",
        "person_region_confirmed_recall_v1": dyn_recall,
        "wilson95": "n=1 不可算 (需>=2 独立动态会话); 单点观察",
        "contested_excluded": ["cap_20261007_143945"],
    }
    # still retention Wilson (n=2)
    st = [res["v1_no_gate"]["still_114340"]["still_retention"], res["v1_no_gate"]["still_114254"]["still_retention"]]
    k = sum(1 for x in st if x >= 0.95)
    lo, hi = wilson(k, 2)
    out["still_retention_summary"] = {"per_session": st, "ge_0.95_sessions": k, "n": 2, "wilson95": [lo, hi]}
    out["caveats"] = [
        "detector=生产 FIX-R1 探针 (associate≡detect_overlay.js, C1 label_audit 已校验), 档 0.55",
        "GT 坐标不可靠 → 仅分类级 + 探针锚定; 143945 CONTESTED 不计 recall",
        "动态有效样本 n=1 → 动态 recall 是单点观察, 无 Wilson, 不足以支撑 C2",
        "空场 FP=0 (203 帧 confirmed=0) 强截证, 但单会话",
        "样本域=同房间近/中场; 无 >2.5m 远距 GT / 多人 / 跌倒 / 明确转身遮挡",
    ]
    with io.open(os.path.join(WS, "metrics_final.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
