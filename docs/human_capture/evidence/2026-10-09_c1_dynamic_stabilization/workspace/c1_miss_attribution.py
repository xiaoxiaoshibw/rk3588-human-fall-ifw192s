#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c1_miss_attribution.py — C1.2 逐帧漏检归因 (BG / 聚类 / RF / Track 四级).

输入: shadow_raw/<sid>.clusters.jsonl + <sid>.tracks.jsonl + captures/remote/<sid>/ai_labels.json
输出: attribution/<sid>.attribution.json + attribution/summary.md
"""
import json, os, sys, math, collections

EVID = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.abspath(os.path.join(EVID, "..", "..", "..", ".."))
RAW = os.path.join(EVID, "workspace", "shadow_raw")
OUT = os.path.join(EVID, "attribution")
SIX = ["cap_20261009_122637", "cap_20261009_122616", "cap_20261009_122700",
       "cap_20261009_121647", "cap_20261009_121622", "cap_20261009_121723"]
NAMES = {s: n for s, n in zip(SIX, ["男近", "男中", "男远", "女近", "女中", "女远"])}


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def person_xy(sid):
    """真人 stand 水平坐标 (x,y) — 从 ai_labels.json 逐帧 (x,y) 取中位数.

    坐标域: leveled 地面系 (z=0)。为什么: ai_labels 已由 auto_person_label.py
    归一到 leveled 再裁 ROI; b2a_shadow_probe 线上探针用 DEFAULT_LEVEL_TRANSFORM
    把帧 in-place leveled 后跑簇; 所以两侧同源, median 即真人固定 stand 位.
    """
    al = json.load(open(os.path.join(ROOT, "captures", "remote", sid, "ai_labels.json"),
                        encoding="utf-8"))
    xs, ys = [], []
    for k, v in al.get("frames", {}).items():
        if v.get("posture") not in (None, "none"):
            xs.append(v.get("x")); ys.append(v.get("y"))
    if not xs:
        return None
    xs.sort(); ys.sort()
    mid = len(xs) // 2
    return (xs[mid], ys[mid], len(xs))


def run_sid(sid):
    clusters = {}
    for o in load_jsonl(os.path.join(RAW, sid + ".clusters.jsonl")):
        clusters.setdefault(o["frame"], []).append(o)
    tracks = load_jsonl(os.path.join(RAW, sid + ".tracks.jsonl"))
    pc = person_xy(sid)
    px, py, n_person_frames = pc
    slist = []
    for tr in tracks:
        fr_lin = None
        for rec in clusters.get(tr["frame"], []):
            if rec["rank"] >= 0:
                d = math.hypot(rec["cx"] - px, rec["cy"] - py)
                slist.append((d, rec["cx"], rec["cy"]))
        if not slist:
            continue
    if slist:
        slist.sort()
        near_med = sum(d for d, _, _ in slist[:max(1, len(slist) // 10)]) / max(1, len(slist) // 10)
    else:
        near_med = None

    frames = {}
    for tr in tracks:
        fi = tr["frame"]
        recs = clusters.get(fi, [])
        frames[fi] = {
            "n_clusters": sum(1 for r in recs if r["rank"] >= 0),
            "person_cluster": None,
            "kept_055": 0, "kept_065": 0, "kept_080": 0,
            "confirmed_055": 0,
            "track_ids_055": [],
        }
        for r in recs:
            if r["rank"] < 0:
                continue
            d = math.hypot(r["cx"] - px, r["cy"] - py)
            if d <= 0.75:
                frames[fi]["person_cluster"] = r
                pp = r["person_prob"]
                if pp >= 0.55: frames[fi]["kept_055"] += 1
                if pp >= 0.65: frames[fi]["kept_065"] += 1
                if pp >= 0.80: frames[fi]["kept_080"] += 1
        pt = tr["per_thr"]["0.55"]
        frames[fi]["confirmed_055"] = len(pt["confirmed"])
        frames[fi]["track_ids_055"] = [c["id"] for c in pt["confirmed"]]

    person_present = 0
    attr = collections.Counter()
    for fi in sorted(frames):
        f = frames[fi]
        person_present += 1
        cl = f["person_cluster"]
        if f["n_clusters"] == 0:
            attr["bg_or_cluster_none"] += 1
        elif cl is None:
            attr["cluster_no_person"] += 1
        elif cl["person_prob"] < 0.55:
            attr["rf_reject"] += 1
        elif f["confirmed_055"] == 0:
            attr["track_age_lt3_or_missed"] += 1
        else:
            attr["shown"] += 1

    runs = []
    for fi in sorted(frames):
        st = "shown" if frames[fi]["confirmed_055"] > 0 else "missing"
        if runs and runs[-1][2] == st:
            runs[-1][1] = fi
        else:
            runs.append([fi, fi, st])
    flicker = [r for r in runs if r[2] == "shown" and (r[1] - r[0] + 1) <= 2]

    probs = [frames[fi]["person_cluster"]["person_prob"]
             for fi in frames if frames[fi]["person_cluster"]]
    probs.sort()
    p50 = probs[len(probs) // 2] if probs else None
    p10 = probs[max(0, int(len(probs) * 0.10) - 1)] if probs else None

    out = {
        "sid": sid, "name": NAMES[sid],
        "n_frames": len(frames),
        "person_xy_median": [round(px, 3), round(py, 3)],
        "person_frames_from_ai_labels": n_person_frames,
        "person_to_nearest_cluster_med_m": round(near_med, 3) if near_med is not None else None,
        "attribution": dict(attr),
        "person_cluster_prob_p10": p10, "person_cluster_prob_p50": p50,
        "flicker_episodes_le2": len(flicker),
        "episodes_shown_total": sum(1 for r in runs if r[2] == "shown"),
        "first_frames_age_lt3": sum(1 for fi in sorted(frames)[:3]
                                    if frames[fi]["confirmed_055"] == 0),
    }
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for sid in SIX:
        rep = run_sid(sid)
        json.dump(rep, open(os.path.join(OUT, sid + ".attribution.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        rows.append(rep)
        print("[attr]", sid, rep["attribution"], "p50=", rep["person_cluster_prob_p50"],
              "flicker=", rep["flicker_episodes_le2"])
    with open(os.path.join(OUT, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("# C1.2 逐帧漏检归因 (0.55 档)\n\n")
        fh.write("级联: 原始点云 → BG 差分 → 聚类 → RF → Track(age≥3)\n\n")
        fh.write("| 会话 | 帧数 | 无簇 | 无人簇 | RF拒绝 | Track未确认 | 正常显示 | 闪烁(≤2帧) | 人x,y中位m | 最近簇距人 | 人簇prob p10/p50 |\n")
        fh.write("|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            a = r["attribution"]
            fh.write("| %s %s | %d | %d | %d | %d | %d | %d | %d | %s | %s | %s / %s |\n" % (
                r["name"], r["sid"][15:], r["n_frames"],
                a.get("bg_or_cluster_none", 0), a.get("cluster_no_person", 0),
                a.get("rf_reject", 0), a.get("track_age_lt3_or_missed", 0),
                a.get("shown", 0), r["flicker_episodes_le2"], r["person_xy_median"],
                r["person_to_nearest_cluster_med_m"],
                r["person_cluster_prob_p10"], r["person_cluster_prob_p50"]))
        fh.write("\n注: Track未确认 含开场前 3 帧 age<MIN_AGE (预期) 及 confirmed 真空洞。\n")
        fh.write("\n## 六段汇总\n\n")
        tot = collections.Counter()
        for r in rows:
            tot.update(r["attribution"])
        for k, v in tot.most_common():
            fh.write("- %s: %d 帧 (%.1f%%)\n" % (k, v, 100.0 * v / sum(tot.values())))
        fh.write("\n")
    print("attribution →", OUT)


if __name__ == "__main__":
    main()
