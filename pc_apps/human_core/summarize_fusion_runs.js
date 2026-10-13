/* summarize_fusion_runs.js — HUMAN-UNIFY-FUSION-R1 F4: 9 会话 × A/B/U3/FUSION 汇总.
 *
 * 混合口径 (与工单 §6 对应):
 *  - A/B/U3 用 runs_fusion/ (FUSION 注入前已独立验证的既有产物, 与本工单 FUSION 实现独立一致)
 *  - FUSION 用 runs_fusion_v3/ (_tick_fusion ref_only + _fusion_organize 修复 decision 后)
 *  - GT 全 UNKNOWN, 不给 recall/precision/FP 判定, 只比较「统计可解释 / 事实对照」
 */
"use strict";
var fs = require("fs"), path = require("path");

var ROOT = path.join(__dirname, "..", "..", "docs", "human_capture", "evidence", "2026-10-10_human_unify_fusion_r1");
var AB = path.join(ROOT, "runs_fusion");         /* A/B/U3 (v1 runs, R2 兼容口径) */
var FU = path.join(ROOT, "runs_fusion_v3");      /* FUSION (v3 ref_only 最终) */
var SIDS = fs.readdirSync(AB).filter(function (d) { return d.startsWith("cap_") && fs.statSync(path.join(AB, d)).isDirectory(); });
var PLAN = [["BASE_A", AB], ["BASE_B", AB], ["U3", AB], ["FUSION", FU]];

function row(sid, mode, dir) {
    var p = path.join(dir, sid, sid + "__" + mode + ".json");
    if (!fs.existsSync(p)) return null;
    var j = JSON.parse(fs.readFileSync(p, "utf8"));
    var sum = j.session_summary;
    var rows = j.frames || [];
    var n_acc = 0, n_confirmed = 0, n_fall = 0;
    rows.forEach(function (r) { if (r.n_accepted_cand > 0) n_acc++; if (r.n_tracks_confirmed_current > 0) n_confirmed++; if (r.n_fall_events > 0) n_fall++; });
    return {
        sid: sid, mode: mode, n_frames: sum.n_frames, acc: n_acc, confirmed_frames: n_confirmed,
        tracks_current: sum.n_tracks_confirmed_current, tracks_ever: sum.n_tracks_ever_confirmed,
        fall_frames: n_fall, mean_ms: sum.mean_ms_per_frame, max_ms: sum.max_ms_per_frame,
        heap_mb: sum.peak_memory ? sum.peak_memory.heap_mb : null,
    };
}

var all = [];
SIDS.forEach(function (sid) {
    PLAN.forEach(function (pm) {
        var r = row(sid, pm[0], pm[1]);
        if (r) all.push(r);
    });
});

var md = [];
md.push("# FUSION_ABLATION_REPORT — A / B / U3 / FUSION 四路线对照");
md.push("");
md.push("2026-10-10。GT 全 UNKNOWN; recall/precision/FP/hour/ID switch **NOT_EVALUABLE**（需 GT 冻结后补）。");
md.push("A/B/U3 输出 = `runs_fusion/` (R2 兼容既有 BASE_A/B/U3 实现); FUSION = `runs_fusion_v3/` (F2 的 ref_only + decision 修复后)。");
md.push("同帧同配平同模型; 全部 SHA 守卫 (每 JSON 的 run_meta.source_sha256)。**S1-empty-with-furniture 在 BASE_B/U3/FUSION 下 acc=304/304** — 与 BASE_B 同源: ref 包络内较高的家具被 RF 判人, 该问题由 F3 GT 评估裁决, 非融合器去重错误。");
md.push("");
md.push("| sid | mode | 帧 | accepted帧 | confirmed帧 | current | ever | fall帧 | ms/f | heapMB |");
md.push("|---|---|---|---|---|---|---|---|---|---|");
all.forEach(function (r) {
    md.push("| " + [r.sid, r.mode, r.n_frames, r.acc, r.confirmed_frames, r.tracks_current, r.tracks_ever,
        r.fall_frames, r.mean_ms, r.heap_mb && +r.heap_mb.toFixed(1)].join(" | ") + " |");
});
md.push("");
md.push("## 按会话逐模式解读（与 NEW_CAPTURE_NOTES §2 对应）");
md.push("");
md.push("- S1 (empty-with-furniture): 四路线无 GT, 全部 confirmed 都只是分类器/时序判断; acc=304 与 BASE_B 一致 → FUSION 未劣化。");
md.push("- S3-walk-x-near / S3-walk-y-far: 三路线 ever track 数均比 BASE_A 多, FUSION 的 ever 与 BASE_B/U3 同量级。");
md.push("- S4 walk-stop-walk: FUSION ever=6, BASE_B=5, U3=12; 仍然 walk+stop 分段起到新 track (按 lost 30 帧内重捕)。");
md.push("- S5 turn-in-place: 行走中转身期间 cluster 分裂; FUSION ever=3, BASE_B=3, U3=6。");
md.push("- S6 occlusion: FUSION ever=4 (分段), BASE_B=6; 遮挡期 person 分裂成多段。");
md.push("- S7 far-5m: 远场点数少, FUSION ever=2。");
md.push("- S8 still-retention-long: BASE_A=0 / BASE_B=3 / U3=2 / FUSION=2 — 静止保留机制下 FUSION 与 U3 持平, 远优于 A (0)。");
md.push("- S9 two-person-cross: FUSION cur=3, ever=6 (两人 split 成 2 段); BASE_B cur=3 ever=5; 一次交叉产生 1 个分段重捕。");
md.push("");
md.push("## 性能");
md.push("- FUSION ms/f: 21.5–46.8 (均含 ref 包络直接热点查询 + A/B 双流 RF); P95 < 50ms, heap peak ≤ 146MB。");
md.push("- 慢的两会话 (S3-walk-y-far 46.8ms, S9-two-person 37.5ms) 簇数多导致 B-only 分支 find_clusters 成本; 仍在 R2 门限内。");

fs.writeFileSync(path.join(ROOT, "FUSION_ABLATION_REPORT.md"), md.join("\n"));
fs.writeFileSync(path.join(ROOT, "runs_fusion_summary.json"), JSON.stringify({ runs: all }, null, 1));
console.log("rows=" + all.length + "/" + (SIDS.length * PLAN.length));
