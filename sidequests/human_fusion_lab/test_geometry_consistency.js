/* test_geometry_consistency.js — geometry(post) 决策/track 一致性回归（Q01 P0）。
 * 断言：detector 层覆盖几何决策后，凡是带 track_id 的候选，其 track_confirmed 必须与
 * 最终 classifier_decision 在显示语义上一致（CONFIRMED_HUMAN ⇔ track_confirmed=true）。
 * 若不一致，则该 detector 是"研究型后处理对照"且必须在响应中显式标记，不得冒充纯几何基线。
 * 运行：node test_geometry_consistency.js   （exit 0 = 一致或已明确标记研究对照）
 */
"use strict";
const assert = require("node:assert/strict");
const D = require("./detector.js");

function runGeometryConsistency() {
    const det = D.createDetector("geometry");
    assert.equal(det.name, "geometry(post)", "geometry 必须显式标注 (post) 研究型后处理");
    // 合成最小帧：两候选，一个几何 CONFIRMED、一个 NON_HUMAN
    const S = require("./core/schema.js");
    const gen = det.begin("cap_20261010_180557");
    let mismatch = 0, tracked = 0;
    for (let i = 0; i < 30; i++) {
        const n = 200;
        const xyzi = new Float32Array(n * 4);
        for (let k = 0; k < n; k++) {
            // 人形簇（z 0..1.8, x 近 2）
            xyzi[k * 4] = 2 + (k % 10) * 0.02;
            xyzi[k * 4 + 1] = (k % 5) * 0.02;
            xyzi[k * 4 + 2] = 0.2 + (k / n) * 1.6;
            xyzi[k * 4 + 3] = 0.8;
        }
        const d = det.tick(S.make_frame_context({
            session_id: "cap_20261010_180557", session_generation: gen,
            frame_index: i, timestamp: i * 0.1, xyzi,
            meta: { model: "IFW192S" }
        }));
        for (const c of (d._candidates || [])) {
            if (!c.track_id) continue;
            tracked++;
            const expectConfirmed = c.classifier_decision === S.CLS_DECISION.CONFIRMED_HUMAN;
            if (c.track_confirmed !== expectConfirmed) mismatch++;
        }
    }
    return { tracked, mismatch };
}

const r = runGeometryConsistency();
console.log("geometry(post) tracked candidates:", r.tracked, "mismatched:", r.mismatch);
if (r.mismatch > 0) {
    console.log("Q01 P0 CONFIRMED: geometry(post) 的 track_confirmed 与最终决策不一致。", r.mismatch, "/", r.tracked);
    console.log("结论：geometry(post) 不得作为纯几何生产基线；须标记为研究型后处理对照或在 detector 层同步 track 显示语义。");
    process.exit(1); // 当前缺陷仍在：返回非零以驱动修复
}
console.log("PASS geometry(post) 决策与 track 显示语义一致");
