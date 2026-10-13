/* 回归测试 · PATCH_01：BUG-R40-T01 同帧多簇不再复用同一 track。
 * 运行：从 pc_apps/human_replay 下 `node ../../docs/human_capture/evidence/2026-10-08_patches_p1p2p3/tests/PATCH_01_tracker_t01.test.js`
 * 依赖：仅 human_pipe_lib.js（其导出在文件颈部，既有 API 不变）。 */
"use strict";
const assert = require("assert");
const path = require("path");
const PL = require(path.join(__dirname, "../../../pc_apps/human_replay/human_pipe_lib.js"));

function mkCluster(cx, cy, joint, label) {
    return {
        ok: true, cx: cx, cy: cy, cz: 0.9, height_m: 1.7, upcos: 0.85,
        n: 500, label: label || "HUMAN_CANDIDATE", joint: joint, /* joint_status 的输出 */
        n_voxels: 8
    };
}

/* T01-A：同帧 3 簇两两在 0.75m 内，全部都 ok 且 CONFIRMED_HUMAN —— 必须各自拿独立 track，
 * 不允许任意两条候选命中同一条 track 而产生 votes=[...,1,1,1] 这种同帧多票。 */
(function T01A() {
    const tr = new PL.Tracker();
    /* 预热 3 帧给出 min_age=3、并立 contest 票,让 age 门提前满足，
     * 那后后一帧仅写入 1 次 vote 唯一性也得关住「同帧 3 簇」的问题。 */
    tr.tick(0, [mkCluster(0.0, 0.0, "NON_HUMAN")]);
    tr.tick(1, [mkCluster(0.0, 0.0, "NON_HUMAN")]);
    tr.tick(2, [mkCluster(0.0, 0.0, "NON_HUMAN")]);
    /* f3：同帧放 3 个 CONFIRMED_HUMAN 簇，两两距离 ~0.3m < gate */
    tr.tick(3, [
        mkCluster(0.0, 0.0, "CONFIRMED_HUMAN"),
        mkCluster(0.3, 0.0, "CONFIRMED_HUMAN"),
        mkCluster(0.0, 0.3, "CONFIRMED_HUMAN")
    ]);
    assert.strictEqual(tr.tracks.length, 3, "同帧 3 簇应各自独立 track");
    const ids = tr.tracks.map(t => t.id).sort((a, b) => a - b);
    assert.deepStrictEqual(ids, [1, 2, 3], "不允许同帧候选合并到同一 track id");
    for (const t of tr.tracks) {
        const votes = t.votes || [];
        assert(votes.length <= 4, "min_age 前预热 + f3 至多 4 条观测记录，不应同帧叠加票");
    }
})();

/* T01-B：同帧后一簇跟前 EMA 刚位移过的 track 距离在 gate 内，仍**必须另起新 track**。 */
(function T01B() {
    const tr = new PL.Tracker();
    tr.tick(0, [mkCluster(0, 0, "NON_HUMAN")]);
    /* f1：第一簇贴原点命中（id=1）,第二簇离 id=1 最近距离 0.6m < 0.75，若没守卫会同 track */
    tr.tick(1, [mkCluster(0, 0, "NON_HUMAN"), mkCluster(0.6, 0, "NON_HUMAN")]);
    assert.strictEqual(tr.tracks.length, 2, "同帧两条候选必须两个 track，而不是先后 EMA 同一条");
    assert(tr.tracks[0].id !== tr.tracks[1].id, "两 track id 必须不同");
    /* 每 track 每帧 ≤1 条 vote / pose_history */
    for (const t of tr.tracks) {
        const ph = t.pose_history || [];
        const votes = t.votes || [];
        assert(ph.length <= 2, "f0/f1 至多 2 个 pose_history 样本");
        assert(votes.length <= 2, "f0/f1 至多 2 个 vote 观测");
    }
})();

/* T01-C：单人连续轨迹行为不变——同一人同一簇连续 3 帧 CONFIRMED_HUMAN 应该在 f2 确认。 */
(function T01C() {
    const tr = new PL.Tracker();
    tr.tick(0, [mkCluster(1.0, 1.0, "CONFIRMED_HUMAN")]);
    tr.tick(1, [mkCluster(1.05, 1.0, "CONFIRMED_HUMAN")]);
    tr.tick(2, [mkCluster(1.05, 1.05, "CONFIRMED_HUMAN")]);
    assert.strictEqual(tr.tracks.length, 1, "单人 3 帧仍应单 track");
    assert(tr.tracks[0].human_confirmed, "连续 3 帧 CONFIRMED_HUMAN 后 track_confirmed 应为 true");
    assert.strictEqual((tr.tracks[0].votes || []).filter(v => v === 1 || v.v === 1).length, 3, "票必须 = 3");
})();

console.log("PATCH_01: PASS");
