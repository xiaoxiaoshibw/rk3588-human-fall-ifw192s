# -*- coding: utf-8 -*-
"""summarize_eval.py — eval_frames.jsonl -> 汇总报告 (Wilson by-track-run CI, 分层).

指标域 (与 evidence/README §4 一致):
  integrity_hit:   人锚点在任一 top4 簇的 (cx,cy) 半径 0.55m 内 (是/否)
  top1_is_person:  人锚点在 top0 簇半径 0.55m 内 (主簇正确; 是/否)
  fragment_extra:  人锚 0.55m 内成员所在的簇的 n (完整度反映 — 越大越好); 记录 top0/top1/top2 n
  frag_in_person:  anchor 内同一 clusters 数 (碎簇 = #comps 包含 anchor 内的点但 d_anchor>0.55 的 ≥30pt 簇)
  cab_person_merge:柜位 0.30m 与人锚 0.55m 是否同簇 (粘连; 是/否)
  n_hot=0:         背景吞人信号 (为 UNKNOWN 不归聚类)

分层: 动静 (gt_type), r 带 (0-1.5, 1.5-3, >3), 会话独立性
Wilson CI: 按 track-run 连续同值段为一个独立单元 (≥3 连帧), 用段数 n
"""
import json
import math
import os
import sys
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (p, max(0.0, center - half), min(1.0, center + half))


def track_runs(flags):
    """[True, True, False, True, True, True] -> [(True,2),(False,1),(True,3)] 段序列"""
    runs = []
    if not flags:
        return runs
    cur = flags[0]; n = 1
    for f in flags[1:]:
        if f == cur:
            n += 1
        else:
            runs.append((cur, n))
            cur = f; n = 1
    runs.append((cur, n))
    return runs


def independent_units(flags, min_consec=3):
    """连续同值段 >=min_consec 记为独立单元; 不足段不计. 返回 (n_units_true, n_units_false)."""
    runs = track_runs(flags)
    n_true = sum(1 for v, n in runs if v and n >= min_consec)
    n_false = sum(1 for v, n in runs if (not v) and n >= min_consec)
    return n_true, n_false


def summarize_rows(records, gt_anchor_lookup):
    """records: [rec] where rec has 'session', 'frame', 'gt_type', 'n_hot', 'A'/'B'/'C' each
    with clusters[]. Returns metrics dict keyed by variant and stratum."""
    variants = ("A", "B", "C")
    out = {v: [] for v in variants}
    for rec in records:
        n_hot = rec.get("n_hot", 0)
        if n_hot == 0:
            # 背景吞人 — 不算入聚类成败
            continue
        for v in variants:
            vc = rec.get(v, {})
            clusters = vc.get("clusters", [])
            # person hit: top0..3 有一簇包含 anchor (0.55m)
            hit = False; top1_hit = False; d_anchor = None
            for i, c in enumerate(clusters):
                if c.get("d_anchor") is not None and c["d_anchor"] <= 0.55:
                    hit = True
                    if i == 0:
                        top1_hit = True
                    if d_anchor is None or c["d_anchor"] < d_anchor:
                        d_anchor = c["d_anchor"]
            # frag: 人 anchor 内 (0.55) 不中所含的 30-pt 簇 (按 d_anchor>0.55 且 n≥30)
            frag_n = 0
            for c in clusters:
                if c.get("d_anchor") is not None and c["d_anchor"] > 0.55 and c.get("n", 0) >= 30:
                    frag_n += 1
            # 柜+人同簇 (cab 的 d_cabinet<0.3 与人 anchor 同簇)
            merged = False
            for c in clusters:
                if (c.get("d_anchor") is not None and c["d_anchor"] <= 0.55
                        and c.get("d_cabinet") is not None and c["d_cabinet"] <= 0.30):
                    merged = True
                    break
            # 柜被 RF 同簇纳入候选 (即柜位被某 top4 簇覆盖)
            cab_captured = False
            cab_rank = None
            for i, c in enumerate(clusters):
                if c.get("d_cabinet") is not None and c["d_cabinet"] <= 0.30:
                    cab_captured = True; cab_rank = i
                    break
            out[v].append(dict(session=rec["session"], frame=rec["frame"],
                               gt_type=rec.get("gt_type"),
                               n_hot=n_hot, hit=hit, top1_hit=top1_hit,
                               d_anchor=d_anchor, frag_n=frag_n, merged=merged,
                               cab_captured=cab_captured, cab_rank=cab_rank,
                               n_clusters=len(clusters),
                               cluster_n=[c.get("n") for c in clusters],
                               ms_cluster=vc.get("ms_cluster", 0.0)))
    return out


def stratum_of(rec, gt_anchor_lookup):
    sid = rec["session"]
    cx_map = {(c["cx"], c["cy"]): True for c in rec.get("clusters", [])}
    # 用 anchor r 做粗分位
    gt = gt_anchor_lookup.get(sid)
    if not gt or not gt.get("xy"):
        return "empty"
    r = math.hypot(gt["xy"][0], gt["xy"][1])
    if r < 1.5:
        return "r_lt1.5"
    if r < 3.0:
        return "r_1_3"
    return "r_gt3"


def report(records, gt_anchor_lookup, out_path):
    by_variant = summarize_rows(records, gt_anchor_lookup)
    strata_bins = {}
    for v, lst in by_variant.items():
        bins = defaultdict(list)
        for row in lst:
            strata = stratum_of(row, gt_anchor_lookup)
            gt_type = row.get("gt_type", "empty")
            bins[(strata, gt_type)].append(row)
        strata_bins[v] = bins

    lines = []
    lines.append("# CLUSTER-ADAPTIVE-SPIKE-R1 — 汇总报告\n")
    lines.append("n_frames (n_hot>0): " + str(sum(len(v) for v in by_variant.values())
                                            // 3) + " (3 variants)\n")
    lines.append("\n## A. 汇总: 每变体每 strata\n")
    for v in ("A", "B", "C"):
        lines.append("\n### 变体 %s\n" % v)
        for (strata, gt_type), rows in sorted(strata_bins[v].items()):
            if not rows:
                continue
            hits = [r["hit"] for r in rows]
            t1h = [r["top1_hit"] for r in rows]
            merged = [r["merged"] for r in rows]
            cab_cap = [r["cab_captured"] for r in rows]
            frags = [r["frag_n"] for r in rows]
            n_cls = [r["n_clusters"] for r in rows]
            hot_units = independent_units(hits)
            top1_units = independent_units(t1h)
            merged_units = independent_units(merged)
            cab_units = independent_units(cab_cap)
            p_hit, lo_h, hi_h = wilson_ci(hot_units[0], hot_units[0] + hot_units[1])
            p_t1, lo_t1, hi_t1 = wilson_ci(top1_units[0], top1_units[0] + top1_units[1])
            n_runs = hot_units[0] + hot_units[1]
            mean_frag = sum(frags) / max(1, len(frags))
            mean_ncls = sum(n_cls) / max(1, len(n_cls))
            lines.append(
                "- **%s / %s** n_frames=%d, 独立段=%d (T=%d F=%d)\n  - 人锚命中: %.1f%%"
                " CI=[%.0f,%.0f]\n  - top0 为主人: %.1f%% CI=[%.0f,%.0f]\n  - 碎簇(anchor外,≥30pt): mean=%.2f/帧\n  - 人+柜粘连段: T=%d F=%d\n  - 柜位进入 top4: %.1f%% of frames\n  - 平均簇数: %.2f\n"
                % (strata, gt_type, len(rows), n_runs, hot_units[0], hot_units[1],
                   100 * p_hit, 100 * lo_h, 100 * hi_h, 100 * p_t1, 100 * lo_t1, 100 * hi_t1,
                   mean_frag, merged_units[0], merged_units[1], 100 * sum(cab_cap) / len(rows),
                   mean_ncls))
    # 全局耗时
    lines.append("\n## B. 耗时 (find_clusters only, 不含 find_hot)\n")
    for v in ("A", "B", "C"):
        lst = by_variant[v]
        if not lst:
            continue
        ms = sorted(r["ms_cluster"] for r in lst)
        def q(p):
            return ms[min(len(ms) - 1, int(len(ms) * p))]
        lines.append("- %s: n=%d p50=%.2fms p95=%.2fms p99=%.2fms max=%.2fms"
                     % (v, len(lst), q(0.5), q(0.95), q(0.99), ms[-1]))
    # per-session 明细附录
    lines.append("\n## C. 逐会话 × 变体 (命中段数 / 独立段数)\n")
    sess_runs = defaultdict(lambda: defaultdict(list))
    for v in ("A", "B", "C"):
        for row in by_variant[v]:
            sess_runs[row["session"]][v].append(row["hit"])
    for sid in sorted(sess_runs):
        row_desc = []
        for v in ("A", "B", "C"):
            hits = sess_runs[sid][v]
            t, f = independent_units(hits)
            row_desc.append("%s=%d/%d段" % (v, t, t + f))
        lines.append("- `%s`: %s" % (sid, ", ".join(row_desc)))

    text = "\n".join(lines) + "\n"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("wrote", out_path, "n_sessions=", len(sess_runs))


def main():
    ev_dir = sys.argv[1]
    frames_path = os.path.join(ev_dir, "eval_frames.jsonl")
    records = []
    with open(frames_path, encoding="utf-8") as fh:
        for line in fh:
            records.append(json.loads(line))
    # 从 eval_cluster 拉 GT 锚
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from eval_cluster import GT_ANCHORS
    report(records, GT_ANCHORS, os.path.join(ev_dir, "SUMMARY.md"))


if __name__ == "__main__":
    main()
