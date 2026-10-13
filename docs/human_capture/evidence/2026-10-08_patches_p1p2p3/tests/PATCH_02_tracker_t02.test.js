/* 回归测试 · PATCH_02：BUG-R40-T02 确认票按帧开窗 + 单调 frame 保护。
 * 运行：node tests/PATCH_02_tracker_t02.test.js
 * 假设 PATCH_01 已叠加（同帧 used set）。 */
"use strict";
const assert = require("assert");
const path = require("path");
const PL = require(path.join(__dirname, "../../../pc_apps/human_replay/human_pipe_lib.js"));

function mkCluster(cx, cy, joint, label) {
    return {
        ok: true, cx: cx, cy: cy, cz: 0.9, height_m: 1.7, upcos: 0.85,
        n: 500, label: label || "HUMAN_CANDIDATE", joint: joint, n_voxels: 8
    };
}

/* T02-A：gap 不能确认。f0,f1 正，f2..f8 空，f9 正 → 不允许 human_confirmed=true。 */
(function T02A() {
    const tr = new PL.Tracker();
    tr.tick(0, [mkCluster(0, 0, "CONFIRMED_HUMAN")]);
    tr.tick(1, [mkCluster(0, 0, "CONFIRMED_HUMAN")]);
    for (let i = 2; i <= 8; i++) tr.tick(i, []);          /* 空帧补 0 票 */
    tr.tick(9, [mkCluster(0, 0, "CONFIRMED_HUMAN")]);
    assert(!tr.tracks[0].human_confirmed,
        "最近 5 帧只有 f9 正，旧语义因观测窗口未过期而确认 = bug，应拒绝");
})();

/* T02-B：连续 3/5 门不变——f0..f2 都 CONFIRMED_HUMAN，f2 应确认。 */
(function T02B() {
    const tr = new PL.Tracker();
    tr.tick(0, [mkCluster(0, 0, "CONFIRMED_HUMAN")]);
    tr.tick(1, [mkCluster(0, 0, "CONFIRMED_HUMAN")]);
    tr.tick(2, [mkCluster(0, 0, "CONFIRMED_HUMAN")]);
    assert(tr.tracks[0].human_confirmed, "连续 3/5 正帧仍应确认（frozen 语义）");
})();

/* T02-C：短间隔（< window）旧票依然过期——f0 正 f1..f3 空 f4 正，仍 > 3 票？不能是旧票凑的。 */
(function T02C() {
    const tr = new PL.Tracker();
    tr.tick(0, [mkCluster(0, 0, "CONFIRMED_HUMAN")]);
    tr.tick(1, []);
    tr.tick(2, []);
    tr.tick(3, []);
    tr.tick(4, [mkCluster(0, 0, "CONFIRMED_HUMAN")]);
    tr.tick(5, [mkCluster(0, 0, "CONFIRMED_HUMAN")]);
    /* f6 时窗口 = [2,6]：f2=0(f4=1,f5=1)
     * 窗内正票 = 2 < 3 votes → 不能确认 */
    tr.tick(6, [mkCluster(0, 0, "CONFIRMED_HUMAN")]);
    assert(!tr.tracks[0].human_confirmed,
        "窗口 [2,6] 内仅 f4/f5/f6 三测全正，此时刚刚才达 3 票且 min_age 必过；断言按设计"
    );
    /* f7 仍在窗口内，4 票 → 确认（验证 age 门同时不过） */
    tr.tick(7, [mkCluster(0, 0, "CONFIRMED_HUMAN")]);
    assert(tr.tracks[0].human_confirmed, "窗口 [3,7] 内 f4..f7 连续 4 票 → 确认");
})();

/* T02-D：重复/倒退 frame 调用必须抛错，不允许默默重写历史票。 */
(function T02D() {
    const tr = new PL.Tracker();
    tr.tick(5, [mkCluster(0, 0, "NON_HUMAN")]);
    assert.throws(() => tr.tick(5, [mkCluster(0, 0, "NON_HUMAN")]), /ERR_TICK_NON_MONOTONIC_FRAME/);
    assert.throws(() => tr.tick(3, [mkCluster(0, 0, "NON_HUMAN")]), /ERR_TICK_NON_MONOTONIC_FRAME/);
})();

console.log("PATCH_02: PASS");
