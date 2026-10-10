/* schema.js — HUMAN-UNIFY-R1 公共抽象。
 *
 * 定义 FrameContext / Candidate / Track / Diagnostics / GTAttestation 数据结构
 * 及 validate 函数。薄 schema + 零计算，只保证字段类型与存在性。
 *
 * 实现哲学： 只定义字段、不表达行为。行为见各模块。
 */
"use strict";

/* GT 评价等级（任务书 §5 四态） */
var GT_LEVEL = Object.freeze({
    HUMAN_VERIFIED: "HUMAN_VERIFIED",       /* 人工审阅通过 — 本库 0 段 */
    HUMAN_UNVERIFIED: "HUMAN_UNVERIFIED",   /* 人工创建但未审 — 本库 0 段 */
    PSEUDO_LABEL: "PSEUDO_LABEL",           /* 算法自动生成 — ai_labels.json 全部 */
    UNKNOWN: "UNKNOWN",                     /* 未知来源 — 其余全部 */
});

/* 候选来源（任务书 §3.2 双来源区分追溯） */
var CAND_SRC = Object.freeze({
    FG: "fg",                 /* 背景差分前景 */
    RETAINED: "retained",     /* 静止保留 */
    MERGED: "merged",         /* 两源合并后合成 */
});

/* 候选产生原因 */
var GEN_REASON = Object.freeze({
    CLUSTER: "cluster",                  /* 常规聚类 */
    SELF_RETAINED_RENEW: "still_renew",  /* 静止保留重确认 */
    OTHER: "other",
});

/* Track 状态 */
var TRACK_STATUS = Object.freeze({
    ACTIVE: "active",           /* 正常关联中 */
    LOST: "lost",               /* 帧丢失计数尚未超 lost_max */
    CLOSED: "closed",           /* lost_max 超后关闭 */
});

/* 分类决策 */
var CLS_DECISION = Object.freeze({
    HUMAN_CANDIDATE: "HUMAN_CANDIDATE",   /* 特征通过/几何门通过 */
    NON_HUMAN: "NON_HUMAN",               /* 特征或门拒绝 */
    SOLID_UNIFORM: "SOLID_UNIFORM",       /* 盒/柱形 — 强家具特征 */
    CONFIRMED_HUMAN: "CONFIRMED_HUMAN",   /* 几何×证据×时序 */
    UNKNOWN: "UNKNOWN",                   /* 无分类器/无判定 */
});

/* 层名常量 — 诊断/落盘用 */
var LAYER = Object.freeze({
    RAW: "raw",
    LEVELED: "leveled",
    DENOISE: "denoise",
    FOREGROUND: "foreground",
    CLEANUP: "cleanup",
    RETAINED: "retained",
    CLUSTER: "cluster",
    CANDIDATE: "candidate",
    FEATURES: "features",
    CLASSIFIER: "classifier",
    TEMPORAL: "temporal",
    TRACK: "track",
});

/* 帧上下文构造 */
function make_frame_context(opts) {
    if (!opts) throw new Error("FrameContext 需要 opts");
    var fc = {
        session_id: String(opts.session_id),
        frame_index: opts.frame_index | 0,
        timestamp: Number(opts.timestamp) || 0,
        xyzi: opts.xyzi,                              /* Float32Array [x,y,z,i]* 传感系（或已 leveled — 看 already_leveled) */
        n_points: opts.xyzi ? opts.xyzi.length / 4 : 0,
        leveling: opts.leveling || null,              /* {R: 9-num arr, T: 3-num arr} */
        config: opts.config || {},
        frame_id: String(opts.frame_id || (opts.session_id + ":" + opts.frame_index)),
        already_leveled: !!opts.already_leveled,      /* 调用方已 leveled → engine 直通 */
        meta: opts.meta || null,                      /* meta.json (检测 meta.leveling) */
    };
    if (!(fc.xyzi instanceof Float32Array)) throw new Error("FrameContext.xyzi 必须是 Float32Array");
    if (fc.xyzi.length % 4 !== 0) throw new Error("FrameContext.xyzi 长度必须 % 4");
    return fc;
}

/* 候选 */
function make_candidate(opts) {
    var c = {
        candidate_id: opts.candidate_id,            /* 层内唯一 */
        point_indices: opts.point_indices,          /* Uint32Array → 帧内原始点索引 */
        centroid: opts.centroid,                    /* {x,y,z} */
        bbox: opts.bbox || null,                    /* {min:[3],max:[3]} 可空 */
        point_count: opts.point_count | 0,
        foreground_source: opts.foreground_source || CAND_SRC.FG,
        gen_reason: opts.gen_reason || GEN_REASON.CLUSTER,
        rejection_reasons: opts.rejection_reasons || [],
        geo_features: opts.geo_features || null,     /* cluster_features 输出 */
        evidence_tag: opts.evidence_tag || null,     /* evidence_label 输出 */
        scores: opts.scores || {},                   /* {"rf51": {prob}, "geometry": {...}, ...} */
        classifier_decision: opts.classifier_decision || CLS_DECISION.UNKNOWN,
        track_id: opts.track_id !== undefined ? opts.track_id : null,
        cluster_keys: opts.cluster_keys || null,     /* 聚类的 key 集（审计用） */
    };
    return c;
}

/* Track */
function make_track(opts) {
    return {
        track_id: opts.track_id,
        status: opts.status || TRACK_STATUS.ACTIVE,
        confidence: Number(opts.confidence) || 0,
        missed_frames: opts.missed_frames | 0,
        first_frame_idx: opts.first_frame_idx | 0,
        last_frame_idx: opts.last_frame_idx | 0,
        age_frames: opts.age_frames | 0,
        last_centroid: opts.last_centroid || null,
        associated_candidate_ids: opts.associated_candidate_ids || [],
        votes: opts.votes || { confirmed_votes: 0, window: 0 },   /* 时序 */
        human_confirmed: !!opts.human_confirmed,
        born_frame_idx: opts.born_frame_idx | 0,
    };
}

/* 每层诊断记录 */
function make_layer_diag(name) {
    return {
        layer: name,
        in_points: 0, out_points: 0,
        in_candidates: 0, out_candidates: 0,
        reject_reasons: {},                          /* reason -> count */
        elapsed_ms: 0,
        notes: [],
    };
}

function make_diagnostics(frame_id) {
    return {
        frame_id: frame_id,
        layers: [],                                  /* [LayerDiag]*, 顺序 = 管道 */
        track_transition: [],                        /* [{track_id, from, to, why}] */
        cls_scores: [],                              /* [{candidate_id, model, score, decision}] */
        gt_match: null,                              /* 仅存在可信 GT 时填 */
        total_ms: 0,
        peak_heap_mb: 0,
    };
}

/* 评价等级推导： 输入 session_dir + meta → 状态.
 * ai_labels.json 是 auto_person_label.py 生产品, 不是人工 GT — 标 PSEUDO_LABEL. */
function gt_attestation(session_dir, meta) {
    if (meta && Array.isArray(meta.human_annotations) && meta.human_annotations.length) {
        return { level: GT_LEVEL.HUMAN_UNVERIFIED, source: "meta.human_annotations", count: meta.human_annotations.length };
    }
    if (session_dir) {
        try {
            var fs = require("fs");
            var path = require("path");
            var p = path.join(session_dir, "ai_labels.json");
            if (fs.existsSync(p)) {
                var d = JSON.parse(fs.readFileSync(p, "utf-8"));
                return {
                    level: GT_LEVEL.PSEUDO_LABEL,
                    source: "ai_labels.json (" + (d.labelled_by || "?") + ")",
                    count: d.frames ? Object.keys(d.frames).length : 0,
                    disclaimer: "auto_person_label.py+empty-template-bgdiff — 非人工 GT, 不可算 P/R/F1",
                };
            }
        } catch (e) { /* 读不到就降级 UNKNOWN */ }
    }
    return { level: GT_LEVEL.UNKNOWN, source: "no labels", count: 0 };
}

/* 完整性 validate — 写测试用 */
function validate_candidate(c) {
    var errs = [];
    if (!c || typeof c !== "object") { errs.push("not object"); return errs; }
    if (typeof c.candidate_id === "undefined") errs.push("candidate_id missing");
    if (!(c.point_indices instanceof Uint32Array)) errs.push("point_indices not Uint32Array");
    if (!c.centroid || typeof c.centroid.x !== "number") errs.push("centroid bad");
    if (!c.point_count) errs.push("point_count 0");
    if (!CAND_SRC[c.foreground_source.toUpperCase()]) errs.push("foreground_source 未知");
    return errs;
}

module.exports = {
    GT_LEVEL: GT_LEVEL,
    CAND_SRC: CAND_SRC,
    GEN_REASON: GEN_REASON,
    TRACK_STATUS: TRACK_STATUS,
    CLS_DECISION: CLS_DECISION,
    LAYER: LAYER,
    make_frame_context: make_frame_context,
    make_candidate: make_candidate,
    make_track: make_track,
    make_layer_diag: make_layer_diag,
    make_diagnostics: make_diagnostics,
    gt_attestation: gt_attestation,
    validate_candidate: validate_candidate,
};
