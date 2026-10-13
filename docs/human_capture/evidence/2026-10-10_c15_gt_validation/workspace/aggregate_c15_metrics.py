# -*- coding: utf-8 -*-
"""aggregate_c15_metrics.py — C1.5 指标聚合 (目标 5/7/8, 只读取证, 生产零改动)。

输入 (全部只读):
  - GT:    workspace/gt_labels/<sid>.(chunk|assess).json      (source:human 逐帧 GT)
  - 检测:  workspace/motion_triage/<sid>.triage_clusters.jsonl (rank0 簇, 几何/RF 候选, 非 GT)
输出:
  - workspace/metrics_per_session.json   逐会话 FN/FP/ID-switch/fragmentation/time-to-detect
  - workspace/metrics_summary.md         汇总 + 段级 Wilson CI (独立样本=会话, 非帧)

诚实边界:
  - 检测侧现仅有几何簇探针 (rank0), 无逐帧 RF→track 结果; FN/FP 以"候选簇存在性"为口径,
    标 DETECTOR_PROXY, 不冒称生产 track 判定。
  - GT 为 vision 辅助人工真值 (assist 级); 计入口径仅限 conf=high 帧。
  - 置信区间按独立会话 (n=会话数) 计算 Wilson, 帧不当作独立样本。
"""
import io
import json
import math
import os
import sys

WS = os.path.dirname(os.path.abspath(__file__))
GT_DIR = os.path.join(WS, "gt_labels")
TRIAGE_DIR = os.path.join(WS, "motion_triage")

# 判定 GT-present 的置信门槛: 只用 high (人工/vision 高置信)
GT_CONF_OK = {"high"}


def load_gt(sid):
    """合并该会话所有 chunk/assess GT → {frame:int: record}."""
    gt = {}
    if not os.path.isdir(GT_DIR):
        return gt
    for fn in sorted(os.listdir(GT_DIR)):
        if not fn.startswith(sid) or not fn.endswith(".json"):
            continue
        d = json.load(io.open(os.path.join(GT_DIR, fn), encoding="utf-8"))
        for k, v in (d.get("frames") or {}).items():
            gt[int(k)] = v
    return gt


def load_triage(sid):
    p = os.path.join(TRIAGE_DIR, sid + ".triage_clusters.jsonl")
    if not os.path.exists(p):
        return None
    rows = [json.loads(l) for l in io.open(p, encoding="utf-8")]
    return {r["frame"]: r for r in rows}


def gt_present(rec):
    return rec is not None and rec.get("conf") in GT_CONF_OK and rec.get("present") is True


def eval_session(sid, min_n_pts_gate=500):
    gt = load_gt(sid)
    tri = load_triage(sid)
    if not gt or tri is None:
        return None
    frames = sorted(set(list(gt.keys()) + list(tri.keys())))
    tp = fn = fp = tn = 0
    uncertain = 0
    first_gt_frame = None
    first_det_frame = None
    t2d = None
    prev_gt_present = False
    # proxy ID-switch/fragmentation: 用 rank0 簇 cx/cy 连续性 (无 tid) — 位移>gate 视为潜在新"段"
    frag = 0
    last_cxy = None
    GATE_M = 1.0
    det_series = []
    for fi in frames:
        g = gt.get(fi)
        t = tri.get(fi)
        gpres = gt_present(g)
        if g is not None and g.get("conf") not in GT_CONF_OK:
            uncertain += 1
        # 检测存在性: rank0 簇存在 且 (gate 口径 n>=min) — 双口径记
        det_raw = t is not None and t.get("rank") == 0
        det_n = t.get("n", 0) if det_raw else 0
        det_gate = det_raw and det_n >= min_n_pts_gate
        det_series.append((fi, gpres, det_raw, det_gate, det_n, t.get("cx") if det_raw else None, t.get("cy") if det_raw else None))
        if gpres and first_gt_frame is None:
            first_gt_frame = fi
        if det_gate and first_det_frame is None:
            first_det_frame = fi
        # 分类计数 (gate 口径)
        if gpres and det_gate:
            tp += 1
        elif gpres and not det_gate:
            fn += 1
        elif (not gpres) and det_gate and g is not None:
            # 仅对 GT 判定过(存在与否)的帧计 FP; 无 GT 帧不算
            fp += 1
        elif (not gpres) and not det_gate and g is not None:
            tn += 1
        # fragmentation: GT-present 段中检测 rank0 簇质心出现 >GATE_M 跳变 => proxy 段断裂
        if gpres and det_raw:
            cxy = (t.get("cx"), t.get("cy"))
            if last_cxy is not None and cxy[0] is not None and last_cxy[0] is not None:
                if math.hypot(cxy[0] - last_cxy[0], cxy[1] - last_cxy[1]) > GATE_M:
                    frag += 1
            last_cxy = cxy
        elif not gpres:
            last_cxy = None
        prev_gt_present = gpres
    if first_gt_frame is not None and first_det_frame is not None:
        t2d = max(0, first_det_frame - first_gt_frame)
    total = tp + fn + fp + tn
    recall = tp / (tp + fn) if (tp + fn) else None
    # still-retention: GT-present 且 activity in stand/still 帧中, 检测仍 present 的比例
    still_denom = sum(1 for fi, gpres, dr, dg, dn, cx, cy in det_series
                      if gpres and (gt.get(fi, {}).get("activity") in ("stand", "still", None)))
    still_num = sum(1 for fi, gpres, dr, dg, dn, cx, cy in det_series
                    if gpres and dg and (gt.get(fi, {}).get("activity") in ("stand", "still", None)))
    return {
        "session_id": sid, "n_frames_scored": total,
        "tp": tp, "fn": fn, "fp": fp, "tn": tn, "uncertain_frames": uncertain,
        "recall_gate500": recall,
        "time_to_detect_frames": t2d,
        "fragmentation_proxy_events": frag,
        "still_retention": (still_num / still_denom) if still_denom else None,
        "_detector": "PROXY_rank0_cluster", "_gt": "vision_assisted_human",
    }


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / den
    return (p, c - half, c + half)


def main(out_dir):
    # 待评测会话: 已有/将有 GT 的动态+静止+空场
    sids = ["cap_20261007_143945", "cap_20261007_154007",
            "cap_20261008_114340", "cap_20261008_114254",
            "cap_20261009_113611"]
    per = []
    for sid in sids:
        r = eval_session(sid)
        if r:
            per.append(r)
    # 段级 (独立会话) Wilson: recall 口径 — 把每会话"是否 recall>=0.95" 作为 Bernoulli 太重,
    # 改为对"逐会话 recall 值"报均值 + 对 FN-free 会话比例做 Wilson (独立样本=会话)。
    n_sess = len(per)
    fn_free = sum(1 for r in per if r["fn"] == 0)
    p, lo, hi = wilson(fn_free, n_sess) if n_sess else (None, None, None)
    summary = {
        "generated": "2026-10-10 C1.5",
        "independent_unit": "session",
        "n_sessions_scored": n_sess,
        "per_session": per,
        "fn_free_sessions": fn_free,
        "fn_free_wilson95": {"p": p, "lo": lo, "hi": hi},
        "caveats": [
            "detector=几何簇探针(rank0) PROXY, 非生产 RF→track 判定",
            "GT=vision 辅助人工真值, 仅 conf=high 帧计入",
            "样本域=同房间近/中场, 不含 >2.5m 远距/多人/跌倒",
            "置信区间按会话 (n=%d) 为独立样本, 帧未当独立样本" % n_sess,
        ],
    }
    with io.open(os.path.join(out_dir, "metrics_per_session.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    # md
    lines = ["# C1.5 指标汇总 (DETECTOR_PROXY + vision-assist GT)", ""]
    lines.append("| 会话 | 帧 | TP | FN | FP | recall(gate500) | T2D(帧) | frag | still保留 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in per:
        rec = "%.3f" % r["recall_gate500"] if r["recall_gate500"] is not None else "—"
        still = "%.3f" % r["still_retention"] if r["still_retention"] is not None else "—"
        t2d = str(r["time_to_detect_frames"]) if r["time_to_detect_frames"] is not None else "—"
        lines.append("| %s | %d | %d | %d | %d | %s | %s | %d | %s |" % (
            r["session_id"].replace("cap_2026", "..."), r["n_frames_scored"], r["tp"], r["fn"], r["fp"], rec, t2d, r["fragmentation_proxy_events"], still))
    lines.append("")
    lines.append("FN-free 会话 %d/%d, Wilson95=[%s, %s] (独立样本=会话)." % (
        fn_free, n_sess,
        ("%.3f" % lo) if lo is not None else "—", ("%.3f" % hi) if hi is not None else "—"))
    lines.append("")
    for c in summary["caveats"]:
        lines.append("- " + c)
    with io.open(os.path.join(out_dir, "metrics_summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("wrote metrics for n_sessions=%d" % n_sess)


if __name__ == "__main__":
    main(WS)
