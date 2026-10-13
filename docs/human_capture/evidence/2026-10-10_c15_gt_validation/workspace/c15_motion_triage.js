/* c15_motion_triage.js — C1.5 资产盘点(只读测量,生产零改动)。
 *
 * 目的: 对全部 cap 会话重放生产管线 (find_hot → find_clusters → 关联),
 * 测量逐帧候选簇质心位移, 客观判定"动态人体资产"在哪、有多少。
 * 不评分、不改任何生产阈值; 输出 raw 逐簇轨迹 + 每会话 motion 摘要。
 *
 * 双口径 track 输出:
 *   A_raw  = 全部簇 (无 n_pts 门)  → 用于观察少点簇是否参与
 *   B_gate = 模拟硬门 n_pts>=500 (仅分诊, 匹配 C1.6 候选机制) → A/B 误杀观察
 *
 * 诚实边界: 这是"几何/RF 候选"层的运动指纹, 不是人工 GT. 高运动 ≠ 真人动态
 *           (也可能是 RF 在家具间切换关联). 分类标签仅为分诊假设, 待 portal 人工确认。
 */
"use strict";
var fs = require("fs");
var path = require("path");

// 生产依赖 (PC 侧只读)
var HR_DIR = "D:/Code/ldiar/pc_apps/human_replay";
var RL = require(path.join(HR_DIR, "human_replay_lib.js"));
var SESSION_ROOT = "D:/Code/ldiar/captures/remote";

// ---- 与生产 b2a_shadow_probe 完全一致的常量/几何 (测量口径) ----
var BG_CELL = 0.05;
function grid_key(x, y) { return Math.floor(x / BG_CELL) * 4096 + Math.floor(y / BG_CELL); }
function find_hot(frame, BG, z_lo, z_hi) {
    var hot = [];
    for (var k = 0; k < frame.n; k++) {
        var z = frame.z[k];
        if (z <= z_lo || z >= z_hi) continue;
        var key = grid_key(frame.x[k], frame.y[k]);
        var bg = BG && BG[key] !== undefined ? BG[key] : -10;
        if (bg < -9) continue;
        if (z > bg + 0.25) hot.push(k);
    }
    return hot;
}
function find_clusters(frame, hot) {
    if (!hot.length) return [];
    var grid = {};
    for (var i = 0; i < hot.length; i++) { var k = hot[i]; var key = grid_key(frame.x[k], frame.y[k]); (grid[key] = grid[key] || []).push(k); }
    var seen = {}, comps = [];
    for (var key in grid) {
        if (seen[key]) continue;
        var stack = [key], members = []; seen[key] = 1;
        while (stack.length) {
            var cur = stack.pop(); members.push.apply(members, grid[cur]);
            var cgx = Math.floor(cur / 4096), cgy = cur % 4096;
            for (var dx = -1; dx <= 1; dx++) for (var dy = -1; dy <= 1; dy++) {
                var nk = (cgx + dx) * 4096 + (cgy + dy);
                if (grid[nk] && !seen[nk]) { seen[nk] = 1; stack.push(nk); }
            }
        }
        if (members.length >= 30) comps.push(members);
    }
    comps.sort(function (a, b) { return b.length - a.length; });
    return comps.slice(0, 4).map(function (members) {
        var xs = [], ys = [], zs = [];
        for (var i = 0; i < members.length; i++) { var k = members[i]; xs.push(frame.x[k]); ys.push(frame.y[k]); zs.push(frame.z[k]); }
        xs.sort(function (a, b) { return a - b; }); ys.sort(function (a, b) { return a - b; });
        var cx = xs[Math.floor(xs.length / 2)], cy = ys[Math.floor(ys.length / 2)];
        var r = members.map(function (k) { var ddx = frame.x[k] - cx, ddy = frame.y[k] - cy; return ddx * ddx + ddy * ddy; }).sort(function (a, b) { return a - b; });
        var r90 = Math.sqrt(r[Math.floor(r.length * 0.9)]);
        var zmax = Math.max.apply(null, zs);
        return { cx: cx, cy: cy, r90: r90, zmax: zmax, n: members.length };
    });
}

// ---- 简单贪心关联器 (复现生产 TRACK gate/TTL/age 语义, 只读) ----
var TRACK_GATE_M = 1.0, TRACK_TTL_FRAMES = 15, TRACK_MIN_AGE = 3, HARD_GATE_N_PTS = 500;
function make_state() { return { next: 1, tracks: [] }; }
function associate(state, clusters, use_gate) {
    var alive = {};
    var pool = use_gate ? clusters.filter(function (c) { return c.n >= HARD_GATE_N_PTS; }) : clusters;
    for (var c = 0; c < pool.length; c++) {
        var cl = pool[c], best = null, best_d = TRACK_GATE_M;
        for (var t = 0; t < state.tracks.length; t++) {
            var tr = state.tracks[t];
            if (alive[tr.id]) continue;
            var d = Math.hypot(cl.cx - tr.cx, cl.cy - tr.cy);
            if (d < best_d) { best_d = d; best = tr; }
        }
        if (best) {
            best.cx = cl.cx; best.cy = cl.cy; best.zmax = cl.zmax; best.n = cl.n;
            best.age++; best.miss = 0; best.last_seen = true; alive[best.id] = 1; cl._tid = best.id;
        } else {
            var nt = { id: state.next++, cx: cl.cx, cy: cl.cy, zmax: cl.zmax, n: cl.n, age: 1, miss: 0, last_seen: true };
            state.tracks.push(nt); alive[nt.id] = 1; cl._tid = nt.id;
        }
    }
    for (var t2 = 0; t2 < state.tracks.length; t2++) {
        var tr2 = state.tracks[t2];
        if (!alive[tr2.id]) { tr2.miss++; tr2.last_seen = false; }
    }
    state.tracks = state.tracks.filter(function (tr) { return tr.miss <= TRACK_TTL_FRAMES; });
}

function load_session(sid) {
    var dir = path.join(SESSION_ROOT, sid);
    var meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    var buf = fs.readFileSync(path.join(dir, "points.bin"));
    var ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
    var f32 = new Float32Array(ab);
    var d = RL.DEFAULT_LEVEL_TRANSFORM, r = d.R, t = d.t;
    for (var p = 0; p < f32.length / 7; p++) {
        var s = p * 7, x = f32[s], y = f32[s + 1], z = f32[s + 2];
        f32[s] = r[0] * x + r[1] * y + r[2] * z + t[0];
        f32[s + 1] = r[3] * x + r[4] * y + r[5] * z + t[1];
        f32[s + 2] = r[6] * x + r[7] * y + r[8] * z + t[2];
    }
    return { meta: meta, buf: f32, frames: RL.frame_slice(meta), fps: RL.default_fps(meta) };
}
function slice_frame(f32, start, count) {
    var out = { n: count, x: new Float32Array(count), y: new Float32Array(count), z: new Float32Array(count) };
    for (var k = 0; k < count; k++) { var o = (start + k) * 7; out.x[k] = f32[o]; out.y[k] = f32[o + 1]; out.z[k] = f32[o + 2]; }
    return out;
}

function median(a) { if (!a.length) return 0; var s = a.slice().sort(function (x, y) { return x - y; }); return s[Math.floor(s.length / 2)]; }
function mean(a) { return a.length ? a.reduce(function (x, y) { return x + y; }, 0) / a.length : 0; }

function analyze(sid, BG, outDir) {
    var sess;
    try { sess = load_session(sid); } catch (e) { return { session_id: sid, error: String(e.message || e) }; }
    var dt = 1 / sess.fps;
    var stA = make_state(), stB = make_state();
    var topDisps = [];          // level-1 (raw) 每帧 rank0 簇相对上一帧位移 (运动指纹)
    var topPresent = 0;
    var nptsAll = [];           // 所有簇 n (供少点占比)
    var gateRejects = 0;        // B口径 因 n<500 被拒的簇数
    // track 轨迹
    var tracksA = {};           // id -> [{frame,cx,cy}]
    var tracksB = {};
    var t2dA = null, t2dB = null; // time-to-detect: 首帧有候选 -> 首 confirmed(age>=3)
    var firstCandFrame = null;
    var rawStream = fs.createWriteStream(path.join(outDir, sid + ".triage_clusters.jsonl"));
    for (var fi = 0; fi < sess.frames.length; fi++) {
        var f = sess.frames[fi];
        var frame = slice_frame(sess.buf, f.start_pts, f.count);
        var hot = find_hot(frame, BG, 0.1, 2.3);
        var clusters = find_clusters(frame, hot);
        for (var ci = 0; ci < clusters.length; ci++) nptsAll.push(clusters[ci].n);
        var nRej = clusters.filter(function (c) { return c.n < HARD_GATE_N_PTS; }).length;
        gateRejects += nRej;
        if (clusters.length) {
            topPresent++;
            if (firstCandFrame === null) firstCandFrame = fi;
        }
        // 关联 (A/B 两口径, 独立状态机)
        associate(stA, clusters.map(function (c) { return Object.assign({}, c); }), false);
        associate(stB, clusters.map(function (c) { return Object.assign({}, c); }), true);
        // rank0 位移指纹 (raw cluster 层)
        if (clusters.length) {
            var c0 = clusters[0];
            rawStream.write(JSON.stringify({ frame: fi, rank: 0, n: c0.n, cx: +c0.cx.toFixed(3), cy: +c0.cy.toFixed(3), zmax: +c0.zmax.toFixed(3), tid_A: c0._tid, tid_B: (c0.n >= HARD_GATE_N_PTS ? c0._tid : null) }) + "\n");
        } else {
            rawStream.write(JSON.stringify({ frame: fi, rank: -1 }) + "\n");
        }
        // 记录轨迹
        [stA, stB].forEach(function (st, si) {
            var map = si === 0 ? tracksA : tracksB;
            st.tracks.forEach(function (tr) {
                if (!tr.last_seen) return;
                (map[tr.id] = map[tr.id] || []).push({ frame: fi, cx: tr.cx, cy: tr.cy, age: tr.age, n: tr.n });
                if (tr.age >= TRACK_MIN_AGE) {
                    if (si === 0 && t2dA === null) t2dA = (fi - (firstCandFrame || 0)) * dt;
                    if (si === 1 && t2dB === null) t2dB = (fi - (firstCandFrame || 0)) * dt;
                }
            });
        });
    }
    rawStream.end();
    // rank0 位移序列
    function traj_span(map) {
        // 取"全程点数最多"的 track 的 xy 位移 span + 中位步长
        var best = null, bestLen = 0;
        for (var id in map) { if (map[id].length > bestLen) { bestLen = map[id].length; best = map[id]; } }
        if (!best || best.length < 2) return { span_m: 0, median_step_m: 0, max_step_m: 0, track_len: bestLen, n_tracks: Object.keys(map).length };
        var xs = best.map(function (p) { return p.cx; }), ys = best.map(function (p) { return p.cy; });
        var span = Math.hypot(Math.max.apply(null, xs) - Math.min.apply(null, xs), Math.max.apply(null, ys) - Math.min.apply(null, ys));
        var steps = [];
        for (var i = 1; i < best.length; i++) { if (best[i].frame === best[i - 1].frame + 1) steps.push(Math.hypot(best[i].cx - best[i - 1].cx, best[i].cy - best[i - 1].cy)); }
        return { span_m: +span.toFixed(3), median_step_m: +median(steps).toFixed(4), max_step_m: +(steps.length ? Math.max.apply(null, steps) : 0).toFixed(4), track_len: bestLen, n_tracks: Object.keys(map).length };
    }
    var sA = traj_span(tracksA), sB = traj_span(tracksB);
    // fragmentation: track 段数 (confirmed track 的连续段)
    function frag_count(map) {
        var ep = 0;
        for (var id in map) { var seq = map[id]; if (!seq.length) continue; ep++; }  // 粗: track 数 = 潜在碎片
        return ep;
    }
    var hasLabel = fs.existsSync(path.join(SESSION_ROOT, sid, "ai_labels.json"));
    // 分诊假设 (非 GT): 基于运动指纹 + 是否已有人工/auto 标签
    var cls;
    if (sess.frames.length === 0) cls = "EMPTY";
    else if (topPresent / sess.frames.length < 0.05) cls = "LIKELY_EMPTY_OR_NO_CAND";
    else if (sA.span_m >= 0.5) cls = "MOTION_CANDIDATE_DYNAMIC";
    else if (sA.span_m >= 0.2) cls = "MOTION_CANDIDATE_SLOW_DRIFT";
    else cls = "MOTION_LOW_STATIC";
    return {
        session_id: sid, n_frames: sess.frames.length, fps: sess.fps,
        top_present_frac: +(topPresent / sess.frames.length).toFixed(3),
        span_m_A: sA.span_m, median_step_m_A: sA.median_step_m_A, max_step_m_A: sA.max_step_m_A,
        track_len_A: sA.track_len, n_tracks_A: sA.n_tracks,
        span_m_B: sB.span_m, n_tracks_B: sB.n_tracks, track_len_B: sB.track_len,
        median_n_pts: median(nptsAll), gate_reject_n: gateRejects,
        t2d_s_A: t2dA === null ? null : +t2dA.toFixed(3), t2d_s_B: t2dB === null ? null : +t2dB.toFixed(3),
        has_ai_label: hasLabel, triage_class: cls
    };
}

function main() {
    var outDir = process.argv[2];
    var BG = JSON.parse(fs.readFileSync(path.join(HR_DIR, "bg_envelope.json"), "utf8"));
    var sids = fs.readdirSync(SESSION_ROOT).filter(function (d) {
        return /^cap_\d/.test(d) && fs.existsSync(path.join(SESSION_ROOT, d, "meta.json")) && fs.existsSync(path.join(SESSION_ROOT, d, "points.bin"));
    }).sort();
    var summaries = [];
    sids.forEach(function (sid) {
        var s = analyze(sid, BG, outDir);
        summaries.push(s);
        console.log("[triage] " + sid + " frames=" + s.n_frames + " spanA=" + s.span_m_A + "m stepA=" + s.median_step_m_A + " present=" + s.top_present_frac + " cls=" + s.triage_class);
    });
    fs.writeFileSync(path.join(outDir, "triage_summary.json"), JSON.stringify({ generated: "2026-10-10 C1.5", note: "几何/RF候选层运动指纹, 非人工GT", sessions: summaries }, null, 1));
    console.log("[triage] wrote triage_summary.json, n=" + summaries.length);
}
main();
