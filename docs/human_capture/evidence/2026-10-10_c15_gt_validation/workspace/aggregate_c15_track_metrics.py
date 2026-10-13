# -*- coding: utf-8 -*-
"""aggregate_c15_track_metrics.py — C1.5 生产级 track 指标 (目标 5/6/7/8, 只读)。

检测证据 = 生产 FIX-R1 探针 b2a_shadow_probe.js 的 tracks.jsonl (三档影子 track 状态机,
与 detect_overlay.js associate 同一实现; C1 label_audit 已校验语义等价)。非几何 proxy。
GT = workspace/gt_labels/*.json (vision 辅助人工真值, 仅 conf=high 计入)。

判定口径 (threshold 档 0.55):
  - GT 有人帧: 取 GT top_xy, 找该帧 confirmed(age>=3 且本帧关联) track 中
    质心距 GT <= MATCH_M 者 → TP; 无 → FN。
  - GT 无人帧(empty): 任一 confirmed track → FP。
  - ID switch: 匹配到 GT-target 的 confirmed track 的 id 相对上一 GT-present 帧改变 → +1。
  - fragmentation: GT-present 段内连续 detection gap (FN gap) 次数 + track id 段数。
  - time-to-detect: 首个 GT-present 帧 → 首个匹配 TP 帧的帧数差。
A/B: probe_v1 (无硬门) vs probe_v2 (n_pts>=500 硬门) 同口径 → 少点误杀观察。
置信区间: 独立样本 = 会话, Wilson95。
"""
import io
import json
import math
import os
import sys

WS = os.path.dirname(os.path.abspath(__file__))
GT_DIR = os.path.join(WS, "gt_labels")
V1 = os.path.join(WS, "probe_v1")
V2 = os.path.join(WS, "probe_v2")
THR = "0.55"
MATCH_M = 0.6          # GT-target 与 confirmed track 质心最大匹配距离
GT_CONF_OK = {"high"}


def load_gt(sid):
    gt = {}
    for fn in sorted(os.listdir(GT_DIR)):
        if not (fn.startswith(sid) and fn.endswith(".json")):
            continue
        if "verdict" in fn:
            continue
        d = json.load(io.open(os.path.join(GT_DIR, fn), encoding="utf-8"))
        # chunk 用 frames; assess 用 sampled_frames
        if d.get("frames"):
            for k, v in d["frames"].items():
                gt[int(k)] = v
        elif d.get("sampled_frames"):
            for v in d["sampled_frames"]:
                gt[int(v["frame"])] = {"present": v.get("present"), "top_xy": v.get("top_xy"),
                                       "activity": "stand", "conf": v.get("conf", "high")}
    return gt


def load_tracks(root, sid):
    p = os.path.join(root, sid + ".tracks.jsonl")
    if not os.path.exists(p):
        return None
    out = {}
    for l in io.open(p, encoding="utf-8"):
        r = json.loads(l)
        pt = r["per_thr"][THR]
        confirmed = [t for t in pt["tracks"] if t["confirmed_now"]]
        out[r["frame"]] = confirmed
    return out


def gt_ok(rec):
    return rec is not None and rec.get("conf") in GT_CONF_OK and rec.get("present") is True and rec.get("top_xy")


def eval_sid(sid, probe_root):
    gt = load_gt(sid)
    tr = load_tracks(probe_root, sid)
    if tr is None:
        return None
    frames = sorted(set(list(gt.keys()) + list(tr.keys())))
    tp = fn = fp = 0
    uncertain = 0
    id_switch = 0
    frag_gaps = 0
    prev_matched_id = None
    in_gap = False
    first_gt = None
    first_tp = None
    still_n = still_d = 0
    fn_frames = []
    idsw_frames = []
    for fi in frames:
        g = gt.get(fi)
        conf = tr.get(fi, [])
        has_gt_field = g is not None
        gpres = gt_ok(g)
        if g is not None and g.get("conf") not in GT_CONF_OK:
            uncertain += 1
        matched_id = None
        if gpres:
            if first_gt is None:
                first_gt = fi
            gx, gy = g["top_xy"][0], g["top_xy"][1]
            best = None
            bd = MATCH_M
            for t in conf:
                d = math.hypot(t["cx"] - gx, t["cy"] - gy)
                if d < bd:
                    bd = d
                    best = t
            if best is not None:
                tp += 1
                matched_id = best["id"]
                if first_tp is None:
                    first_tp = fi
                if prev_matched_id is not None and matched_id != prev_matched_id:
                    id_switch += 1
                    idsw_frames.append(fi)
                in_gap = False
                if g.get("activity") in ("stand", "still", None):
                    still_n += 1
                    still_d += 1
            else:
                fn += 1
                fn_frames.append(fi)
                if not in_gap:
                    frag_gaps += 1
                    in_gap = True
                if g.get("activity") in ("stand", "still", None):
                    still_d += 1
            prev_matched_id = matched_id
        else:
            # 无人帧 (GT 判过 empty) → confirmed 即 FP
            if has_gt_field and g.get("conf") in GT_CONF_OK and g.get("present") is False:
                fp += len(conf)
    t2d = (first_tp - first_gt) if (first_gt is not None and first_tp is not None) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    return {
        "session_id": sid, "n_gt_frames": sum(1 for f in frames if gt.get(f) is not None),
        "gt_present_frames": tp + fn, "tp": tp, "fn": fn, "fp_empty_frames_fp_events": fp,
        "uncertain_frames_excluded": uncertain,
        "recall": recall, "id_switch": id_switch, "fragmentation_gaps": frag_gaps,
        "time_to_detect_frames": t2d,
        "still_retention": (still_n / still_d) if still_d else None,
        "fn_frames_head": fn_frames[:12], "id_switch_frames": idsw_frames[:12],
    }


def wilson(k, n, z=1.96):
    if not n:
        return (None, None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / den
    return (p, max(0, c - h), min(1, c + h))


def main():
    sids = ["cap_20261007_143945", "cap_20261007_154007",
            "cap_20261008_114340", "cap_20261008_114254"]
    res = {"generated": "2026-10-10 C1.5", "threshold": THR, "match_m": MATCH_M,
           "independent_unit": "session", "v1": [], "v2": []}
    for tag, root in (("v1", V1), ("v2", V2)):
        for sid in sids:
            r = eval_sid(sid, root)
            if r:
                res[tag].append(r)
    # A/B 对比: 少点误杀 — v2 (硬门) 相对 v1, GT-present 帧 FN 是否增加
    ab = []
    v1m = {r["session_id"]: r for r in res["v1"]}
    v2m = {r["session_id"]: r for r in res["v2"]}
    for sid in sids:
        a, b = v1m.get(sid), v2m.get(sid)
        if a and b:
            ab.append({"session_id": sid, "fn_v1": a["fn"], "fn_v2": b["fn"],
                       "fn_delta": b["fn"] - a["fn"],
                       "recall_v1": a["recall"], "recall_v2": b["recall"],
                       "idsw_v1": a["id_switch"], "idsw_v2": b["id_switch"]})
    res["ab_hard_gate"] = ab
    # 段级 Wilson (独立=会话): FN-free 会话比例 (v1 0.55)
    for tag in ("v1", "v2"):
        per = res[tag]
        n = len(per)
        fnfree = sum(1 for r in per if r["fn"] == 0)
        p, lo, hi = wilson(fnfree, n)
        res[tag + "_wilson_fnfree"] = {"n_sessions": n, "fn_free": fnfree, "lo": lo, "hi": hi}
    res["caveats"] = [
        "detector=生产 FIX-R1 探针三档影子 track (associate 同 detect_overlay.js), 档位 0.55",
        "GT=vision 辅助人工真值; 仅 conf=high 计入; uncertain 帧从分子分母剔除",
        "FP 仅在 GT 判空帧统计 confirmed 事件数 (本批动态/静止会话几乎全程有人, 空场 FP 域靠 113611)",
        "独立样本=会话 (Wilson), 帧未当独立样本; 动态样本 n=2, 静止 n=2, 样本量小",
        "样本域=同房间近/中场 (≤约4m), 不含 >2.5m 远距标注/多人/跌倒",
    ]
    with io.open(os.path.join(WS, "metrics_track.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)

    def md_table(per, title):
        L = ["", "### " + title, "", "| 会话 | GT人帧 | TP | FN | recall | IDsw | frag | T2D帧 | still保留 |",
             "|---|---|---|---|---|---|---|---|---|"]
        for r in per:
            rec = "%.3f" % r["recall"] if r["recall"] is not None else "—"
            st = "%.3f" % r["still_retention"] if r["still_retention"] is not None else "—"
            t2d = str(r["time_to_detect_frames"]) if r["time_to_detect_frames"] is not None else "—"
            L.append("| %s | %d | %d | %d | %s | %d | %d | %s | %s |" % (
                r["session_id"].replace("cap_", "…"), r["gt_present_frames"], r["tp"], r["fn"], rec, r["id_switch"], r["fragmentation_gaps"], t2d, st))
        return L

    L = ["# C1.5 生产级 track 指标 (FIX-R1 探针 tracks.jsonl, 档 0.55, vision-assist GT)", ""]
    L += md_table(res["v1"], "A = v1 无硬门 (基线)")
    L += md_table(res["v2"], "B = v2 硬门 n_pts≥500")
    L += ["", "### 硬门 A/B (少点误杀观察)", "", "| 会话 | FN v1 | FN v2 | ΔFN | recall v1 | recall v2 | IDsw v1→v2 |", "|---|---|---|---|---|---|---|"]
    for r in res["ab_hard_gate"]:
        L.append("| %s | %d | %d | %+d | %s | %s | %d→%d |" % (
            r["session_id"].replace("cap_", "…"), r["fn_v1"], r["fn_v2"], r["fn_delta"],
            "%.3f" % r["recall_v1"], "%.3f" % r["recall_v2"], r["idsw_v1"], r["idsw_v2"]))
    L += ["", "硬门 FN 增量 Δ>0 = 少点人体被误杀证据; Δ=0 表示本批 n_pts 均>500 未见误杀。", ""]
    for tag in ("v1", "v2"):
        w = res[tag + "_wilson_fnfree"]
        L.append("%s FN-free 会话 %d/%d, Wilson95=[%s, %s]." % (tag, w["fn_free"], w["n_sessions"],
                 "%.3f" % w["lo"] if w["lo"] is not None else "—", "%.3f" % w["hi"] if w["hi"] is not None else "—"))
    L.append("")
    for c in res["caveats"]:
        L.append("- " + c)
    with io.open(os.path.join(WS, "metrics_track_summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print("wrote metrics_track.json / metrics_track_summary.md; v1 n=%d v2 n=%d" % (len(res["v1"]), len(res["v2"])))


if __name__ == "__main__":
    main()
