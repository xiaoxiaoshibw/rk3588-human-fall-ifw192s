/* fusion.js — HUMAN-UNIFY-FUSION-R1 F2: 统一候选融合 (MODE=FUSION).
 *
 * 只做 A 链 (PIPE + U3 保留/bank) 与 B 链 (原 detect_overlay 子链) 的「候选组织 + 联合跟踪」;
 * 不改 human_replay 生产源; 点输入与 engine.js tick 一致 (Float32Array xyzi 传感系)。
 *
 * 融合原则 (与工单 §4 对应):
 *  - candidate.source ∈ {A, B, A+B}; 保留 raw point_indices, scores.geometry/rf51 与来源诊断。
 *  - A/B 重复候选按质心门+A-members/B-members 合并 (raw 属系归并), 不重复起 Track。
 *  - 一套权威 Track ID: FUS_t{track_segment}_{id}。
 *  - 融合 Track 只由本帧 A/B 独立命中刷新; 融合产物自己不续命, lost>track_lost_max 退出。
 *  - 分类不足 → CLS_DECISION.UNKNOWN (不强制 PERSON)。
 */
"use strict";
var S = require("./schema.js");

var MODE_NAME = "FUSION";

var DEFAULT_FUSION_CFG = {
    assoc_gate_xy_m: 0.75,          /* A/B 关联质心门 (m) */
    track_gate_xy_m: 0.75,
    track_lost_max: 30,
    track_still_confirm_window: 5,
    track_still_confirm_votes: 3,
    track_still_confirm_min_age: 3,
    rf51_threshold: 0.55,
    bg_envelope_path: null,
    online_background: false,
};

/* FusionTracker (与 human_pipe_lib.Tracker 独立):
 * 输入 = 已合并的 fusion 候选; track_id 由 engine 以 FUS_t{segment}_{id} 回写。 */
function FusionTracker(cfg) {
    this.cfg = cfg;
    this.next_id = 1;
    this.tracks = [];
}
FusionTracker.prototype.tick = function (frame_idx, fusions) {
    var gate2 = this.cfg.track_gate_xy_m * this.cfg.track_gate_xy_m, self = this;
    fusions.forEach(function (fc) {
        var best = null, best_d2 = gate2;
        self.tracks.forEach(function (t) {
            if (!t.active) return;
            var dx = t.x - fc.centroid.x, dy = t.y - fc.centroid.y, d2 = dx * dx + dy * dy;
            if (d2 < best_d2) { best_d2 = d2; best = t; }
        });
        if (best) {
            best.lost = 0; best.last_seen = frame_idx;
            best.x = fc.centroid.x; best.y = fc.centroid.y; best.z = fc.centroid.z;
            best.source_a_hit = best.source_a_hit || fc.fusion_source_SRC === "A" || fc.fusion_source_SRC === "A+B";
            best.source_b_hit = best.source_b_hit || fc.fusion_source_SRC === "B" || fc.fusion_source_SRC === "A+B";
        } else {
            best = { id: self.next_id++, active: true, born_frame_idx: frame_idx,
                x: fc.centroid.x, y: fc.centroid.y, z: fc.centroid.z,
                lost: 0, last_seen: frame_idx, votes: [], pose_history: [],
                human_confirmed: false, track_segment: fc.track_segment,
                source_a_hit: fc.fusion_source_SRC === "A" || fc.fusion_source_SRC === "A+B",
                source_b_hit: fc.fusion_source_SRC === "B" || fc.fusion_source_SRC === "A+B",
            };
            self.tracks.push(best);
        }
        var vote = fc.classifier_decision === S.CLS_DECISION.CONFIRMED_HUMAN ? 1 : 0;
        best.votes.push(vote);
        if (best.votes.length > self.cfg.track_still_confirm_window) best.votes.shift();
        var vs = best.votes.reduce(function (a, b) { return a + b; }, 0);
        best.human_confirmed = vs >= self.cfg.track_still_confirm_votes
            && (frame_idx - best.born_frame_idx + 1) >= self.cfg.track_still_confirm_min_age;
        fc.track_id = "FUS_t" + fc.track_segment + "_" + best.id;
        fc.track_confirmed = best.human_confirmed;
    });
    this.tracks.forEach(function (t) {
        if (!t.active) return;
        if (t.last_seen !== frame_idx) {
            t.lost++;
            if (t.lost > self.cfg.track_lost_max) t.active = false;
        }
    });
};

module.exports = {
    MODE_NAME: MODE_NAME,
    DEFAULT_FUSION_CFG: DEFAULT_FUSION_CFG,
    FusionTracker: FusionTracker,
};
