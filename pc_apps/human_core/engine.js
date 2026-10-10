/* engine.js — HUMAN-UNIFY-R1 统一引擎。
 *
 * 以 human_pipe_lib 为主干（因为它已有 denoise/fg/clean/cluster/evidence/joint/tracker/fall
 * 全链），外插：
 *  - 可选 REF_ENVELOPE 背景（路线 B 语义）
 *  - 候选 → rf_person.js 分类器（复用生产 100 树 json）
 *  - 静止保留 (retention)： 对曾在 ≥W 帧确认过人形、当前帧前景消失的 track，
 *    从其历史 hot cell 把点重新纳入候选（self_retained 来源）
 *  - 层间诊断： 每层输入/输出点数/原因/耗时
 *
 * 不修改 human_replay 任何文件；只 require。两次调用同一帧由 frame_id 去重。
 */
"use strict";
var path = require("path");

var S = require("./schema.js");
var leveling = require("./leveling.js");
var pipe = require("../human_replay/human_pipe_lib.js");
var RF_PERSON = require("../human_replay/rf_person.js");

var RF_MODEL_JSON = path.join(__dirname, "..", "human_replay", "rf_person_v1.json");
var BG_ENVELOPE_JSON = path.join(__dirname, "..", "human_replay", "bg_envelope.json");

/* ---------- 配置 ---------- */
var MODE = Object.freeze({
    /* route A 全等： 在线管道 + 几何判定 */
    BASE_A: "BASE_A",
    /* route B 全等： 空场包络 + 网格热点聚类 + RF, 不用 A 的 vox/evidence/tracker */
    BASE_B: "BASE_B",
    /* U1: A 管道基础上, 用统一 candidate/trackable model (A 已带 tracker, 等价) */
    U1: "U1",
    /* U2: U1 + 静止保留 */
    U2: "U2",
    /* U3: U2 + rf51 分类器 */
    U3: "U3",
    /* U4: U2 + rf69 - blocked (rf69 json 未导出) */
    U4: "U4",
    /* U5: U2 + gbdt - blocked (gbdt json 未导出) */
    U5: "U5",
    /* U6: U3/U4/U5 中可验证的跟踪组合 = U3 + 更长 lost_max (验证 tracker 持续时间) */
    U6: "U6",
});

var DEFAULT_CFG = {
    mode: MODE.U1,
    /* 背景： online= pipe 在线 3D 体素; ref_only= 只用 BG_ENVELOPE （路线 B); ref_plus_online= 融合 */
    background: "online",
    /* 候选： fg_only / fg_plus_retained */
    candidates: "fg_only",
    /* 分类器： geometry_gate | rf51 | none */
    classifier: "geometry_gate",
    /* rf51 阈值 */
    rf51_threshold: 0.55,
    /* 时序： A 默认值 */
    confirm_window: 5, confirm_votes: 3, min_age_frames: 3,
    /* 跟踪： pipe Tracker 默认 */
    track_gate_xy_m: 0.75,
    track_lost_max: 8,
    ema_alpha: 0.35,
    /* 保留： 静止 person retention */
    retention: {
        window_confirm: 3,      /* recent N 帧 CONFIRMED_HUMAN 才算"曾确认" */
        timeout_s: 180,
        hot_cell_radius_m: 0.4, /* 从历史 track 中心扩半径 hot cell */
        max_lost_for_retain: 30, /* 超过 30 帧 lost 不再保留 */
        re_fail_keep: false,    /* confirm 失效是否保留 hot cell */
    },
    /* leveling R/T: null=用 meta.leveling; 否则吹哨 R 9元 T 3元 */
    leveling_rt: null,
    /* hard n_pts ≥500 (C1.5 已证动态失效， 默认关闭） */
    hard_gate_n500: false,
    /* 回放合同： strict | lenient */
    replay_policy: "strict",
    diagnostics: true,
};

function now_ms() { return Date.now(); }

/* 同步计时: 用 performance API */
var _perf = (typeof performance !== "undefined") ? performance : { now: now_ms };

/* ---------- 静止保留状态 ---------- */
function RetentionState() {
    /* track_id -> {cells: Map<"ix,iy", {x,y,zmax_hits,n_last_seen}>, last_confirmed_frame, last_frame_idx} */
    this.tracks = {};
}

/* ---------- 主引擎 ---------- */
function UnifiedEngine(cfg) {
    this.cfg = Object.assign({}, DEFAULT_CFG, cfg || {});
    this._validate_mode_cfg();
    this.pipe_ctx = null;                 /* {static_keys, tracker, fusion} per session */
    this.rf = null;
    this.rf_model_sha = null;
    if (this.cfg.classifier === "rf51" || this.cfg.mode === MODE.BASE_B || this.cfg.mode === MODE.U3 || this.cfg.mode === MODE.U6) {
        var fs = require("fs");
        var txt = fs.readFileSync(RF_MODEL_JSON, "utf-8");
        this.rf = Object.create(RF_PERSON);
        var n = this.rf.init(txt);
        var crypto = require("crypto");
        this.rf_model_sha = crypto.createHash("sha256").update(txt, "utf-8").digest("hex").slice(0, 16);
    }
    this.retention = new RetentionState();
    this.session_id = null;
    this.frame_history = {};              /* frame_id → 摘要（水线守卫） */
    this.report_rows = [];                /* 每帧 diagnostics */
    this.track_log = [];
    this._seen_frames = new Set();        /* 重入守卫 */
}

UnifiedEngine.prototype._validate_mode_cfg = function () {
    var m = this.cfg.mode;
    if (m === MODE.U4) throw new Error("U4 (rf69) BLOCKED — rf_subset_pc.json 未导出为推理 json");
    if (m === MODE.U5) throw new Error("U5 (gbdt) BLOCKED — 无 GBDT artifact");
};

/* 新会话： 重置 tracker/online 背景/retention */
/* 新会话/循环/回退入口。三者都重置 tracker/retention/frame_seen,
 * 但区分语义让 track_log 可追溯： reason='new' | 'loop_back' | 'session_switch' */
UnifiedEngine.prototype.begin_session = function (session_id, reason) {
    var last_sid = this.session_id;
    var r = reason || ((last_sid === null) ? "new" : (last_sid === session_id ? "loop_back" : "session_switch"));
    if (this.session_id !== session_id || r !== "new" || this.pipe_ctx === null || this.pipe_ctx.tracker.tracks.length > 0) {
        this.session_id = session_id;
        this._seen_frames.clear();
        this.retention = new RetentionState();
        this.pipe_ctx = { static_keys: null, tracker: new pipe.Tracker(), fusion: null };
        this.track_log.push({ at: "session_begin", session_id: session_id, reason: r });
    }
    /* online 背景需要 build_static_map（跨全帧）, 调用方须先 set_online_background(frames_xyzi)*/
};

/* 设 online 背景： pipe 一句话。frames_xyzi 必须已与 engine.tick() 内 leveling 同构 (默认 ref R/T)。
 * runner 应该传原始传感系 frames_xyzi, 由本方法内部用 ref R/T 一次性 leveled 再建图。 */
UnifiedEngine.prototype.set_online_background = function (frames_xyzi) {
    if (!this.pipe_ctx) throw new Error("先 begin_session");
    var RT = this.cfg.leveling_rt || {
        R: [0.893544, 0.0, 0.448975, -0.014337, 0.99949, 0.028533, -0.448746, -0.031932, 0.893089],
        T: [0.0, 0.0, 1.380286],
    };
    var leveled = frames_xyzi.map(function (xyzi) {
        return leveling.level_frame(xyzi, RT.R, RT.T, false);
    });
    this.pipe_ctx.static_keys = pipe.build_static_map(leveled);
};

/* ref envelope 从 json 文件 load （路线 B 包络） */
UnifiedEngine.prototype.load_ref_envelope = function (jsonfile) {
    var fs = require("fs");
    var txt = fs.readFileSync(jsonfile || BG_ENVELOPE_JSON, "utf-8");
    this._ref_env = JSON.parse(txt);      /* {gridkey: z_p95} */
    this._ref_env_sha = require("crypto").createHash("sha256").update(txt, "utf-8").digest("hex").slice(0, 16);
};

/* 帧处理主入口。
 * fc: FrameContext (xyzi 传感系 — 模块内自动 leveled)
 * 返回： Diagnostics 对象 */
UnifiedEngine.prototype.tick = function (fc) {
    var t0 = _perf.now();
    var diag = S.make_diagnostics(fc.frame_id);

    /* 回放合同： 重入守卫 */
    if (this._seen_frames.has(fc.frame_id)) {
        if (this.cfg.replay_policy === "strict")
            throw new Error("重复帧 frame_id=" + fc.frame_id + " (strict)");
        diag.notes && diag.notes.push("duplicate_frame_ignored");
        diag.total_ms = _perf.now() - t0;
        return diag;
    }
    this._seen_frames.add(fc.frame_id);

    /* 1. leveling */
    var L0 = S.make_layer_diag(S.LAYER.LEVELED);
    L0.in_points = fc.n_points;
    var already = leveling.is_leveled_in_meta(fc.meta || null) || fc.already_leveled;
    var RT = this.cfg.leveling_rt;
    if (!RT && !already && !fc.already_leveled) {
        /* 路线 B 硬编码空场模板 R/T 作为缺省 */
        RT = {
            R: [0.893544, 0.0, 0.448975, -0.014337, 0.99949, 0.028533, -0.448746, -0.031932, 0.893089],
            T: [0.0, 0.0, 1.380286],
        };
    }
    var leveled = already ? fc.xyzi.slice(0) : leveling.level_frame(fc.xyzi, RT ? RT.R : null, RT ? RT.T : null, already);
    L0.out_points = leveled.length / 4; L0.elapsed_ms = _perf.now() - t0; diag.layers.push(L0);

    /* 2. 模式分发 */
    var m = this.cfg.mode;
    var t1 = _perf.now();
    if (m === MODE.BASE_B) this._tick_base_b(fc, leveled, diag);
    else this._tick_pipechain(fc, leveled, diag);
    var t2 = _perf.now();

    diag.total_ms = _perf.now() - t0;
    diag.peak_heap_mb = (process.memoryUsage ? process.memoryUsage().heapUsed / (1024 * 1024) : 0);
    this.report_rows.push(this._flatten_frame_row(fc, diag));
    return diag;
};

/* 路线 B 全等： 空场包络 + 网格聚类 + rf51 + overlay.associate 简化等价 */
UnifiedEngine.prototype._tick_base_b = function (fc, leveled, diag) {
    /* 用 pipe.denoise + 这里重写 BG 检查 + 网格 5cm 聚类 + RF 分类 + NN 关联 */
    var t0 = _perf.now();
    var clean = pipe.denoise(leveled);
    var L = S.make_layer_diag(S.LAYER.DENOISE); L.in_points = leveled.length / 4; L.out_points = clean.length / 4; L.elapsed_ms = _perf.now() - t0; diag.layers.push(L);
    if (!this._ref_env) this.load_ref_envelope();
    /* find_hot 等价： z>bg+0.25 and z∈(0.1, 2.3) */
    t0 = _perf.now();
    var BG_CELL = 0.05;
    var n = clean.length / 4;
    var hot_mask = new Uint8Array(n);
    var n_hot = 0;
    for (var k = 0; k < n; k++) {
        var x = clean[k * 4], y = clean[k * 4 + 1], z = clean[k * 4 + 2];
        if (z <= 0.1 || z >= 2.3) continue;
        var key = Math.floor(x / BG_CELL) * 4096 + Math.floor(y / BG_CELL);
        var bg = this._ref_env[key];
        if (bg === undefined) continue;
        if (z > bg + 0.25) { hot_mask[k] = 1; n_hot++; }
    }
    var Lf = S.make_layer_diag(S.LAYER.FOREGROUND); Lf.in_points = n; Lf.out_points = n_hot; Lf.elapsed_ms = _perf.now() - t0; diag.layers.push(Lf);
    /* 5cm 粗聚类 min 30 点 */
    t0 = _perf.now();
    var grid = {};
    for (var k2 = 0; k2 < n; k2++) {
        if (!hot_mask[k2]) continue;
        var key2 = Math.floor(clean[k2 * 4] / BG_CELL) * 4096 + Math.floor(clean[k2 * 4 + 1] / BG_CELL);
        (grid[key2] = grid[key2] || []).push(k2);
    }
    var seen = {};
    var comps = [];
    for (var kk in grid) {
        if (seen[kk]) continue;
        var stack = [kk], mem = [];
        seen[kk] = 1;
        while (stack.length) {
            var cur = stack.pop();
            var arr = grid[cur]; for (var a = 0; a < arr.length; a++) mem.push(arr[a]);
            var cgx = Math.floor(cur / 4096), cgy = cur % 4096;
            for (var dx = -1; dx <= 1; dx++)for (var dy = -1; dy <= 1; dy++) {
                var nk = (cgx + dx) * 4096 + (cgy + dy);
                if (grid[nk] && !seen[nk]) { seen[nk] = 1; stack.push(nk); }
            }
        }
        if (mem.length >= 30) comps.push(mem);
    }
    comps.sort(function (a, b) { return b.length - a.length; });
    comps = comps.slice(0, 4);
    var Lc = S.make_layer_diag(S.LAYER.CLUSTER); Lc.in_candidates = 0; Lc.out_candidates = comps.length; Lc.elapsed_ms = _perf.now() - t0; diag.layers.push(Lc);
    /* RF 分类 */
    t0 = _perf.now();
    var cands = [];
    for (var ci = 0; ci < comps.length; ci++) {
        var mem = comps[ci];
        var sx = 0, sy = 0, sz = 0;
        var sub_x = new Float32Array(mem.length), sub_y = new Float32Array(mem.length), sub_z = new Float32Array(mem.length), inten = new Float32Array(mem.length);
        var pi = new Uint32Array(mem.length);
        for (var mi = 0; mi < mem.length; mi++) {
            var pp = mem[mi];
            sub_x[mi] = clean[pp * 4]; sub_y[mi] = clean[pp * 4 + 1]; sub_z[mi] = clean[pp * 4 + 2];
            inten[mi] = fc.xyzi[pp * 4 + 3];       /* intensity 来自原始 */
            pi[mi] = pp;
            sx += sub_x[mi]; sy += sub_y[mi]; sz += sub_z[mi];
        }
        var fv = this.rf.extract({ n: mem.length, x: sub_x, y: sub_y, z: sub_z }, inten);
        var prob = this.rf.predict_person(fv);
        var c = S.make_candidate({
            candidate_id: "b_" + fc.frame_index + "_" + ci,
            point_indices: pi,
            centroid: { x: sx / mem.length, y: sy / mem.length, z: sz / mem.length },
            point_count: mem.length,
            foreground_source: S.CAND_SRC.FG,
            gen_reason: S.GEN_REASON.CLUSTER,
            scores: { rf51: { prob: prob, threshold: this.cfg.rf51_threshold, model_sha: this.rf_model_sha } },
            classifier_decision: (prob >= this.cfg.rf51_threshold) ? S.CLS_DECISION.HUMAN_CANDIDATE : S.CLS_DECISION.NON_HUMAN,
        });
        if (prob < this.cfg.rf51_threshold) c.rejection_reasons.push("rf51<" + this.cfg.rf51_threshold);
        cands.push(c);
        diag.cls_scores.push({ candidate_id: c.candidate_id, model: "rf51_v1", score: prob, decision: c.classifier_decision });
    }
    var Lf2 = S.make_layer_diag(S.LAYER.CLASSIFIER); Lf2.in_candidates = comps.length; Lf2.out_candidates = cands.filter(function (c) { return c.classifier_decision === S.CLS_DECISION.HUMAN_CANDIDATE; }).length; Lf2.elapsed_ms = _perf.now() - t0; diag.layers.push(Lf2);
    /* NN 关联： 用 pipe 的 Tracker 作为统一实现 （等价 associate)，但要求 c.ok */
    t0 = _perf.now();
    var pseudo_clusters = cands.filter(function (c) { return c.classifier_decision === S.CLS_DECISION.HUMAN_CANDIDATE; }).map(function (c) {
        return { ok: true, cx: c.centroid.x, cy: c.centroid.y, cz: c.centroid.z, height_m: 1.7, upcos: 0.95, n: c.point_count, label: "HUMAN_CANDIDATE", joint: "CONFIRMED_HUMAN" };
    });
    this.pipe_ctx.tracker.tick(fc.frame_index, pseudo_clusters);
    /* 把 pipe tracker 的 track_id 回填候选 */
    for (var pi2 = 0; pi2 < pseudo_clusters.length; pi2++)
        if (pseudo_clusters[pi2].track_id !== undefined)
            cands.filter(function (c) { return c.classifier_decision === S.CLS_DECISION.HUMAN_CANDIDATE; })[pi2].track_id = pseudo_clusters[pi2].track_id;
    var Lt = S.make_layer_diag(S.LAYER.TRACK); Lt.in_candidates = pseudo_clusters.length;
    Lt.out_candidates = this.pipe_ctx.tracker.tracks.filter(function (t) { return t.active; }).length;
    Lt.elapsed_ms = _perf.now() - t0; diag.layers.push(Lt);
    diag._candidates = cands;
};

/* 路线 A 全链 （含 U1/U2/U3/U6): denoise→fg→iso→cluster→features→evidence→joint→rf optional→retention→tracker→fall */
UnifiedEngine.prototype._tick_pipechain = function (fc, leveled, diag) {
    var t0 = _perf.now();
    var clean = pipe.denoise(leveled);
    var L0 = S.make_layer_diag(S.LAYER.DENOISE); L0.in_points = leveled.length / 4; L0.out_points = clean.length / 4; L0.elapsed_ms = _perf.now() - t0; diag.layers.push(L0);

    if (!this.pipe_ctx.static_keys)
        throw new Error("online 背景未 set — 需先 set_online_background(frames_xyzi)");

    t0 = _perf.now();
    var fg = pipe.extract_foreground(clean, this.pipe_ctx.static_keys);
    var L1 = S.make_layer_diag(S.LAYER.FOREGROUND); L1.in_points = clean.length / 4; L1.out_points = fg.n_fg; L1.elapsed_ms = _perf.now() - t0; diag.layers.push(L1);

    t0 = _perf.now();
    var iso = pipe.cleanup_isolated_fg(fg.fg_xyzi);
    var L2 = S.make_layer_diag(S.LAYER.CLEANUP); L2.in_points = iso.fg_before_cleanup; L2.out_points = iso.fg_after_cleanup; L2.elapsed_ms = _perf.now() - t0; diag.layers.push(L2);

    /* 保留模块（U2+）：把 retention 的 hot cell 点并入 — 真时机: track 已 lost≥1 */
    t0 = _perf.now();
    var fg_final = iso.xyzi;
    var n_retained_added = 0;
    if (this.cfg.candidates === "fg_plus_retained" || this.cfg.mode === MODE.U2 || this.cfg.mode === MODE.U3 || this.cfg.mode === MODE.U6) {
        var trks = this.pipe_ctx.tracker.tracks;
        for (var ti = 0; ti < trks.length; ti++) {
            var t = trks[ti];
            if (!t.active) continue;
            if (!t.human_confirmed) continue;
            if (t.lost < 1 || t.lost > this.cfg.retention.max_lost_for_retain) continue;
            var cells = this._cells_for_track(t);
            if (!cells.length) continue;
            /* 把当前 leveled (denoised) 中落在 cell 内的点也并入 fg_final —
             * 但跳过已在 fg_final 内的（避免双计）: 简单全部并入, 主要靠 cluster dedupe */
            var extra = [];
            var R2 = this.cfg.retention.hot_cell_radius_m * this.cfg.retention.hot_cell_radius_m;
            for (var k = 0; k < clean.length; k += 4) {
                var x = clean[k], y = clean[k + 1], z = clean[k + 2], ii = clean[k + 3];
                if (z < pipe.PIPE.ground_keep_below_m || z > pipe.PIPE.z_max_m) continue;
                for (var cc = 0; cc < cells.length; cc++) {
                    var ddx = x - cells[cc].x, ddy = y - cells[cc].y;
                    if (ddx * ddx + ddy * ddy <= R2) {
                        extra.push(x, y, z, ii); break;
                    }
                }
            }
            if (extra.length) {
                var merged = new Float32Array(fg_final.length + extra.length);
                merged.set(fg_final); merged.set(extra, fg_final.length);
                fg_final = merged;
                n_retained_added += extra.length / 4;
            }
        }
    }
    var L3 = S.make_layer_diag(S.LAYER.RETAINED); L3.in_points = iso.fg_after_cleanup; L3.out_points = fg_final.length / 4 - iso.fg_after_cleanup; L3.elapsed_ms = _perf.now() - t0; diag.layers.push(L3);
    if (n_retained_added) L3.notes.push("added=" + n_retained_added);

    /* 聚类 */
    t0 = _perf.now();
    var vox = pipe.voxelize(fg_final);
    var clusters_raw = pipe.cluster_voxels(vox);
    var ev_pack = pipe.evidence_postpass(fg_final, clusters_raw);
    var L4 = S.make_layer_diag(S.LAYER.CLUSTER); L4.in_points = fg_final.length / 4; L4.out_candidates = clusters_raw.length; L4.elapsed_ms = _perf.now() - t0; diag.layers.push(L4);

    /* 特征 + 分类 + joint */
    t0 = _perf.now();
    var cands = [];
    var rejected_count = 0;
    for (var i = 0; i < clusters_raw.length; i++) {
        var f = pipe.cluster_features(clusters_raw[i]);
        if (!f.ok) { rejected_count++; continue; }
        /* hard n≥500 门 (C1.5: 动态域会误杀， 默认 false) */
        if (this.cfg.hard_gate_n500 && f.n < 500) { rejected_count++; continue; }
        var cgeo = pipe.classify_human(f);
        f.label = cgeo.label; f.confidence = cgeo.confidence; f.reasons = cgeo.reasons;
        f.evidence = ev_pack.clusters_extra[i];
        f.evidence_tag = pipe.evidence_label(ev_pack.clusters_extra[i]);
        f.joint = pipe.joint_status(f);
        /* 可选 rf51 打分 */
        var scores = { geometry: { gates: f.confidence, label: f.label } };
        var cls_decision = f.joint === "CONFIRMED_HUMAN" ? S.CLS_DECISION.CONFIRMED_HUMAN
            : f.joint === "HUMAN_CANDIDATE" ? S.CLS_DECISION.HUMAN_CANDIDATE : S.CLS_DECISION.NON_HUMAN;
        if (this.cfg.classifier === "rf51") {
            /* 需把簇点喂 RF — 用 acc 逆推 (近似： 从 voxel 域), 与 detect_overlay 同口径 */
            /* 这里我们不再扫点， 直接用 pipe 的 acc 估计； RF 需要原始点 — 扫 fg_final 找属于 cluster i 的点 */
            var keyset = new Set(clusters_raw[i].keys);
            var n_in_cl = 0;
            for (var k = 0; k < fg_final.length; k += 4)
                if (keyset.has(pipe.key_vox(fg_final[k], fg_final[k + 1]))) n_in_cl++;
            var sub_x = new Float32Array(n_in_cl), sub_y = new Float32Array(n_in_cl), sub_z = new Float32Array(n_in_cl), inten = new Float32Array(n_in_cl);
            var w = 0;
            for (var k2 = 0; k2 < fg_final.length; k2 += 4) {
                if (keyset.has(pipe.key_vox(fg_final[k2], fg_final[k2 + 1]))) {
                    sub_x[w] = fg_final[k2]; sub_y[w] = fg_final[k2 + 1]; sub_z[w] = fg_final[k2 + 2]; inten[w] = fg_final[k2 + 3]; w++;
                }
            }
            var fv = this.rf.extract({ n: n_in_cl, x: sub_x, y: sub_y, z: sub_z }, inten);
            var prob = this.rf.predict_person(fv);
            scores.rf51 = { prob: prob, threshold: this.cfg.rf51_threshold, model_sha: this.rf_model_sha };
            /* 决策： 路线 B 语义 = rf51 ≥ 阈才认人;
             * **关键**: 同时也写回 f.joint, 否则 pipe.tracker 仍按几何 joint 判 CONFIRMED,
             * rf 即使把人推到 HUMAN_CANDIDATE 时间确认也看不到 — 导致 U3 confirmed=0 假死 */
            cls_decision = (prob >= this.cfg.rf51_threshold) ? S.CLS_DECISION.HUMAN_CANDIDATE : S.CLS_DECISION.NON_HUMAN;
            f.joint = (prob >= this.cfg.rf51_threshold) ? "CONFIRMED_HUMAN" : "NON_HUMAN";
        }
        var pi = new Uint32Array(0); /* point_indices 留空— 簇 acc 已含， 避免冗余内存 */
        var c = S.make_candidate({
            candidate_id: "a_" + fc.frame_index + "_" + i,
            point_indices: pi,
            centroid: { x: f.cx, y: f.cy, z: f.cz },
            bbox: { min: [0, 0, f.zmin], max: [0, 0, f.zmax] },
            point_count: f.n,
            foreground_source: S.CAND_SRC.FG,
            gen_reason: S.GEN_REASON.CLUSTER,
            geo_features: f,
            evidence_tag: f.evidence_tag,
            classifier_decision: cls_decision,
            scores: scores,
            rejection_reasons: f.reasons || [],
            cluster_keys: clusters_raw[i].keys,
        });
        c._pipe_f = f;     /* 供 tracker 用 */
        cands.push(c);
        diag.cls_scores.push({ candidate_id: c.candidate_id, model: this.cfg.classifier, score: scores.rf51 ? scores.rf51.prob : f.confidence, decision: cls_decision });
    }
    var L5 = S.make_layer_diag(S.LAYER.CLASSIFIER); L5.in_candidates = clusters_raw.length; L5.out_candidates = cands.length; L5.elapsed_ms = _perf.now() - t0;
    if (rejected_count) L5.reject_reasons["n<60_or_n500"] = rejected_count;
    diag.layers.push(L5);

    /* 时序： pipe Tracker 已含 3/5 vote + age; fall_assess 仍在 pipe 内 */
    t0 = _perf.now();
    var pseudo = cands.map(function (c) { return c._pipe_f; });
    this.pipe_ctx.tracker.tick(fc.frame_index, pseudo);
    for (var pi = 0; pi < pseudo.length && pi < cands.length; pi++) {
        if (pseudo[pi].track_id !== undefined) cands[pi].track_id = pseudo[pi].track_id;
    }
    /* retention: 记录 confirmed 的 track 的历史 cell */
    var trks = this.pipe_ctx.tracker.tracks;
    for (var ti = 0; ti < trks.length; ti++) {
        var t = trks[ti];
        if (t.active && t.human_confirmed) this._register_track_cells(t, fg_final);
    }
    /* fall 检查 */
    var events = [];
    for (var ti2 = 0; ti2 < trks.length; ti2++) {
        var tr = trks[ti2];
        if (!tr.active) continue;
        var ev = pipe.fall_assess(tr);
        if (ev) events.push(Object.assign({ track_id: tr.id }, ev));
    }
    var L6 = S.make_layer_diag(S.LAYER.TRACK);
    L6.in_candidates = pseudo.length;
    L6.out_candidates = trks.filter(function (t) { return t.active; }).length;
    L6.elapsed_ms = _perf.now() - t0; diag.layers.push(L6);

    diag._candidates = cands;
    diag._tracks = trks.filter(function (t) { return t.active; });
    diag._events = events;
};

/* 把 track 中心纳入 retention bank （仅当 confirmed) */
UnifiedEngine.prototype._register_track_cells = function (t, fg_xyzi) {
    var R = this.cfg.retention.hot_cell_radius_m;
    /* 简单： 以 track 当前位置为 cell */
    this.retention.tracks[t.id] = {
        x: t.x, y: t.y, last_confirmed_frame: t.last_seen, lost_cur: t.lost,
    };
};

UnifiedEngine.prototype._cells_for_track = function (t) {
    var c = this.retention.tracks[t.id];
    if (!c) return [];
    return [{ x: c.x, y: c.y }];
};

/* 帧摘要行 — 落 CSV/JSON 用 */
UnifiedEngine.prototype._flatten_frame_row = function (fc, diag) {
    var row = {
        session_id: fc.session_id,
        frame_index: fc.frame_index,
        timestamp: fc.timestamp,
    };
    for (var i = 0; i < diag.layers.length; i++) {
        var L = diag.layers[i];
        row[L.layer + "_in"] = L.in_points;
        row[L.layer + "_out_pts"] = L.out_points;
        row[L.layer + "_out_cand"] = L.out_candidates;
        row[L.layer + "_ms"] = +L.elapsed_ms.toFixed(2);
    }
    row.total_ms = +diag.total_ms.toFixed(2);
    if (diag._candidates) {
        row.n_cand = diag._candidates.length;
        var n_person = 0, n_furn = 0;
        for (var i2 = 0; i2 < diag._candidates.length; i2++) {
            var c = diag._candidates[i2];
            if (c.classifier_decision === S.CLS_DECISION.HUMAN_CANDIDATE || c.classifier_decision === S.CLS_DECISION.CONFIRMED_HUMAN) n_person++;
            else n_furn++;
        }
        row.n_person_cand = n_person;
        row.n_furn_cand = n_furn;
    }
    if (diag._tracks) row.n_tracks_active = diag._tracks.length;
    if (diag._events) row.n_fall_events = diag._events.length;
    return row;
};

/* 报告 */
UnifiedEngine.prototype.report = function () {
    return {
        session_id: this.session_id,
        rows: this.report_rows,
        tracks: this.pipe_ctx ? this.pipe_ctx.tracker.tracks : [],
        config: this.cfg,
        rf_model_sha: this.rf_model_sha,
    };
};

module.exports = {
    UnifiedEngine: UnifiedEngine,
    MODE: MODE,
    DEFAULT_CFG: DEFAULT_CFG,
};
