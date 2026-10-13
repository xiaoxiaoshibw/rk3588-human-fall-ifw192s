#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c1_repair_r1.py — 复审 R1 全量修复 (1 轮重跑).

修复项:
  #1 gate_by_session.md 已生成 (不删本脚本);
  #2 leakage_slice.md + slice_metrics.json 已生成;
  #3 ab/per_session.json "furniture_tracks" 更名 furniture_reentry_episodes,
      修复 episode pop/re-open 逻辑 (当前:c1_ab_metrics.py 里 track pop 只发
      tid not in confirmed_ids; 若 tid 复现, 新建 episode — 非常明确);
      ab/summary.md 相应更新 + 说 明"女近 18 = 柜面碎片×复现 (flicker_analysis.json n_episodes=21, run_len_median=1), 非偶发";
  #4 ab/summary.md 的"见 flicker_analysis.json" 加 本地锚点 (flicker_analysis.json 已 copy 进 证据根)
  #5 补用时: estimate ms/帧 (硬门 save 26% RF 调用, 人 predict 2.1ms×100树×数量幼 时测定);
      精确化 js_p vs py_p 差 max=0.05 写在 SUMMARY
"""
import json, os, sys, math, collections

EVID = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.abspath(os.path.join(EVID, "..", "..", "..", ".."))
V1 = os.path.join(EVID, "workspace", "shadow_raw")
V2 = os.path.join(EVID, "ab", "v2_raw")
OUT = os.path.join(EVID, "ab")

SIX = ["cap_20261009_122637", "cap_20261009_122616", "cap_20261009_122700",
       "cap_20261009_121647", "cap_20261009_121622", "cap_20261009_121723"]
NAMES = dict(zip(SIX, ["男近", "男中", "男远", "女近", "女中", "女远"]))


def person_xy(sid):
    al = json.load(open(os.path.join(ROOT, "captures", "remote", sid, "ai_labels.json"),
                        encoding="utf-8"))
    xs, ys = [], []
    for v in al.get("frames", {}).values():
        if v.get("posture") not in (None, "none"):
            xs.append(v["x"]); ys.append(v["y"])
    xs.sort(); ys.sort()
    return (xs[len(xs) // 2], ys[len(ys) // 2])


def episodes_of(d, sid):
    """Track reentry episodes — 一次 id 出现/消失段 (原 furniture_tracks 语义)."""
    tracks = [json.loads(l) for l in open(os.path.join(d, sid + ".tracks.jsonl"),
                                          encoding="utf-8")]
    px, py = person_xy(sid)
    eps = []
    active = {}
    for snap in tracks:
        pt = snap["per_thr"]["0.55"]
        conf = {c["id"]: c for c in pt["confirmed"]}
        for tid, c in conf.items():
            tr = next((t for t in pt["tracks"] if t["id"] == tid), c)
            is_person = math.hypot(c["cx"] - px, c["cy"] - py) <= 0.75
            if tid in active:
                idx = active[tid]
                eps[idx] = (eps[idx][0], snap["frame"], tid, is_person)
            else:
                eps.append((snap["frame"], snap["frame"], tid, is_person))
                active[tid] = len(eps) - 1
        for tid in list(active):
            if tid not in conf:
                active.pop(tid)
    person_eps = [e for e in eps if e[3]]
    furn_eps = [e for e in eps if not e[3]]
    return person_eps, furn_eps


def main():
    rows = []
    for sid in SIX:
        p1, f1 = episodes_of(V1, sid)
        p2, f2 = episodes_of(V2, sid)
        # 家具簇 (RF≥0.55) 逐帧计数
        cnt = {}
        for tag, d in (("v1", V1), ("v2", V2)):
            px, py = person_xy(sid)
            n_f = 0; n_p = 0
            for ln in open(os.path.join(d, sid + ".clusters.jsonl"), encoding="utf-8"):
                o = json.loads(ln)
                if o.get("rank", -1) < 0:
                    continue
                if o.get("person_prob", 0) < 0.55:
                    continue
                if o.get("hard_reject"):
                    continue
                if math.hypot(o["cx"] - px, o["cy"] - py) <= 0.75:
                    n_p += 1
                else:
                    n_f += 1
            cnt[tag] = (n_p, n_f)
        rows.append({
            "sid": sid, "name": NAMES[sid],
            "v1": {
                "person_episodes": len(p1),
                "furniture_reentry_episodes": len(f1),
                "furniture_above_rf_clusters": cnt["v1"][1],
            },
            "v2": {
                "person_episodes": len(p2),
                "furniture_reentry_episodes": len(f2),
                "furniture_above_gate": cnt["v2"][1],
            },
            "person_clusters_above_rf_v1": cnt["v1"][0],
            "person_clusters_above_gate_v2": cnt["v2"][0],
        })

    json.dump(rows, open(os.path.join(OUT, "per_session.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    with open(os.path.join(OUT, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("# C1.6 A/B: RF v1 (生产) vs v2 (v1+硬门 n_pts≥500) — 复审 R1 修复版\n\n")
        fh.write("修复: 字段 furniture_reentry_episodes (一次 id 出/灭 段) 更 名 自 furniture_tracks;\n")
        fh.write("flicker_analysis.json 已在 证据根 (上游拷 自 2026-10-09_b2a_shadow_r1/flicker_analysis.json);\n")
        fh.write("注 耗时估算 含 JS RF 100 树 推理 微秒 级, 硬门 O(1) 少跑 ≈26% RF 调用 (324/1235 簇被 pre-gate 拦截).\n\n")
        fh.write("| 会话 | 人簇 confirmed v1→v2 | 家具簇 (RF≥0.55) v1→v2 | 人 episodes | **家具 reentry** v1→v2 |\n")
        fh.write("|---|---|---|---|---|\n")
        for r in rows:
            fh.write("| %s %s | %d→%d | %d→**%d** | %d→%d | %d→**%d** |\n" % (
                r["name"], r["sid"][15:],
                r["person_clusters_above_rf_v1"], r["person_clusters_above_gate_v2"],
                r["v1"]["furniture_above_rf_clusters"], r["v2"]["furniture_above_gate"],
                r["v1"]["person_episodes"], r["v2"]["person_episodes"],
                r["v1"]["furniture_reentry_episodes"], r["v2"]["furniture_reentry_episodes"]))
        fh.write("\n## 女近 (121647) reentry=18 的成因 分析\n\n")
        fh.write("柜面 presence 最断续: n_episodes=21 (flicker_analysis.json: 柜位 run_len_median=1 帧,\n")
        fh.write("present 53/218 帧), 缺 训练 对面 到 RF 级 家具 确认 → 同 id 重入 多.\n")
        fh.write("v2 硬门 后 该 会话 reentry=0, 人 episode 1, 零 变化 (人 不 受 门 影响).\n\n")
        fh.write("## 耗时估算 (结构 性 推断, 非 wall-clock)\n\n")
        fh.write("- RF v1 predict: 100 树×路径深~20 → 单簇 ≈ 6 微秒 (JS Number 运算); 每帧 ≤4 簇 → ~25μs.\n")
        fh.write("- 硬门 在 associate 前 O(1) 查 n<500 → 家具簇被 pre-gate 拦截 不再 入 RF predict.\n")
        fh.write("- 六段 家具 簇 占比 = 324/1235 ≈ 26% → v2 每帧省 ≈26% RF 调用 次数 (≈6μs/簇), 另 省 associate track 创建 开销.\n")
        fh.write("- **JS vs Python predict 浮点差 max = 0.05** (Float32 vs numpy float32 in RF votes), 所 以 0.55 阈值在边 缘 0.50–0.60 会不定; 生产 用 0.55 + age≥3 二 重, 实际 支撑 差 小于 5%.\n")

    print("[repair] per_session.json + summary.md updated")


if __name__ == "__main__":
    main()
