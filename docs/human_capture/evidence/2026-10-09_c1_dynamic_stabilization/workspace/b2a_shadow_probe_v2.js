/* b2a_shadow_probe_v2.js — C1.6 A/B: b2a_shadow_probe.js + 硬门 + RF v1 (生产零改动).
 *
 * 模式: same input, same clusters, 只是在 score_clusters 上加硬门 n_pts<500 → person_prob=0,
 * 其余照旧. 这样 A/B 只需与 v1 jsonl 对照, 不需重跑 RF 训炼.
 */
"use strict";

var fs = require("fs");
var path = require("path");

var RL = require("./human_replay_lib.js");
var RF_PERSON = require("./rf_person.js");

var BG_CELL = 0.05;
function grid_key(x, y) {
    var gx = Math.floor(x / BG_CELL), gy = Math.floor(y / BG_CELL);
    return gx * 4096 + gy;
}
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
    for (var i = 0; i < hot.length; i++) {
        var k = hot[i];
        var key = grid_key(frame.x[k], frame.y[k]);
        if (!grid[key]) grid[key] = [];
        grid[key].push(k);
    }
    var seen = {};
    var comps = [];
    for (var key in grid) {
        if (seen[key]) continue;
        var stack = [key], members = [];
        seen[key] = 1;
        while (stack.length) {
            var cur = stack.pop();
            members.push.apply(members, grid[cur]);
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
        for (var i = 0; i < members.length; i++) {
            var k = members[i];
            xs.push(frame.x[k]); ys.push(frame.y[k]); zs.push(frame.z[k]);
        }
        xs.sort(); ys.sort();
        var cx = xs[Math.floor(xs.length / 2)], cy = ys[Math.floor(ys.length / 2)];
        var r = members.map(function (k) {
            var dx = frame.x[k] - cx, dy = frame.y[k] - cy;
            return dx * dx + dy * dy;
        }).sort(function (a, b) { return a - b; });
        var r90 = Math.sqrt(r[Math.floor(r.length * 0.9)]);
        var zmax = Math.max.apply(null, zs);
        return { members: members, cx: cx, cy: cy, r90: r90, zmax: zmax, n: members.length };
    });
}

var TRACK_GATE_M = 1.0;
var TRACK_TTL_FRAMES = 15;
var TRACK_MIN_AGE = 3;

function make_assoc_state() { return { t_id_next: 1, tracks: [], frame_no: 0 }; }
function associate(state, clusters, fps) {
    fps = fps || 10;
    var alive = new Set();
    var claimed = {};
    for (var c = 0; c < clusters.length; c++) {
        var cl = clusters[c];
        var best = null, best_d = TRACK_GATE_M;
        for (var t = 0; t < state.tracks.length; t++) {
            var tr = state.tracks[t];
            if (claimed[tr.id]) continue;
            var d = Math.hypot(cl.cx - tr.cx, cl.cy - tr.cy);
            if (d < best_d) { best_d = d; best = tr; }
        }
        if (best) {
            best.cx = cl.cx; best.cy = cl.cy; best.r90 = cl.r90;
            best.zmax = cl.zmax; best.n = cl.n; best.miss = 0; best.age++;
            claimed[best.id] = 1;
            cl.track_id = best.id;
        } else {
            var tr = { id: state.t_id_next++, cx: cl.cx, cy: cl.cy, r90: cl.r90,
                       zmax: cl.zmax, n: cl.n, miss: 0, age: 1, born: state.frame_no };
            claimed[tr.id] = 1;
            state.tracks.push(tr);
            cl.track_id = tr.id;
        }
        alive.add(cl.track_id);
    }
    for (var t = state.tracks.length - 1; t >= 0; t--) {
        var tr = state.tracks[t];
        if (!alive.has(tr.id)) {
            tr.miss++;
            if (tr.miss > TRACK_TTL_FRAMES) state.tracks.splice(t, 1);
        }
    }
}

/* C1 v2: 硬门 + RF 打分. 硬门过 不了 → 不入 associate (与 v1 filter 的位置完全等同). */
var HARD_GATE_N_PTS = 500;
function score_clusters_v2(rf, clusters, frame, buf_f32, start_pts) {
    var kept = [];
    for (var ci = 0; ci < clusters.length; ci++) {
        var cl = clusters[ci];
        if (cl.n < HARD_GATE_N_PTS) {
            cl.person_prob = 0;
            cl.hard_reject = 1;
            continue;   /* 不入 kept, 与 RF v1 的低分被滤 完全同位置 */
        }
        var sub = { n: cl.members.length, x: new Float32Array(cl.members.length),
                    y: new Float32Array(cl.members.length), z: new Float32Array(cl.members.length) };
        var inten = new Float32Array(cl.members.length);
        for (var mi = 0; mi < cl.members.length; mi++) {
            var k = cl.members[mi];
            sub.x[mi] = frame.x[k]; sub.y[mi] = frame.y[k]; sub.z[mi] = frame.z[k];
            inten[mi] = buf_f32[(start_pts + k) * 7 + 3];
        }
        var fv = rf.extract(sub, inten);
        cl.person_prob = rf.predict_person(fv);
        kept.push(cl);
    }
    return kept;
}

function level_frame_passthrough(buf, start, count) {
    var n = count;
    var out = { n: n, x: new Float32Array(n), y: new Float32Array(n), z: new Float32Array(n) };
    for (var k = 0; k < n; k++) {
        var o = (start + k) * 7;
        out.x[k] = buf[o]; out.y[k] = buf[o + 1]; out.z[k] = buf[o + 2];
    }
    return out;
}

function load_session_leveled(session_root, sid) {
    var dir = path.join(session_root, sid);
    var meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    var buf = fs.readFileSync(path.join(dir, "points.bin"));
    var ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
    var f32 = new Float32Array(ab);
    var d = RL.DEFAULT_LEVEL_TRANSFORM, r = d.R, t = d.t;
    var total_pts = f32.length / 7;
    for (var p = 0; p < total_pts; p++) {
        var s = p * 7;
        var x = f32[s], y = f32[s + 1], z = f32[s + 2];
        f32[s] = r[0] * x + r[1] * y + r[2] * z + t[0];
        f32[s + 1] = r[3] * x + r[4] * y + r[5] * z + t[1];
        f32[s + 2] = r[6] * x + r[7] * y + r[8] * z + t[2];
    }
    var frames = RL.frame_slice(meta);
    var fps = (typeof RL.default_fps === "function") ? RL.default_fps(meta) : 10;
    return { meta: meta, buf_f32: f32, frames: frames, fps: fps };
}

function main() {
    var argv = process.argv.slice(2);
    if (argv.length < 3) {
        console.error("usage: node b2a_shadow_probe_v2.js <session_root> <out_dir> <sid1> [sid2...]");
        process.exit(2);
    }
    var session_root = argv[0], out_dir = argv[1], sids = argv.slice(2);
    fs.mkdirSync(out_dir, { recursive: true });
    var BG = JSON.parse(fs.readFileSync(path.join(__dirname, "bg_envelope.json"), "utf8"));
    var rf_json = fs.readFileSync(path.join(__dirname, "rf_person_v1.json"), "utf8");
    var n_trees = RF_PERSON.init(rf_json);
    console.log("[probe v2] bg cells=" + Object.keys(BG).length + " rf trees=" + n_trees +
                " hard_gate_n_pts=" + HARD_GATE_N_PTS);

    var THRESHOLDS = [0.55, 0.65, 0.80];
    sids.forEach(function (sid) {
        var sess = load_session_leveled(session_root, sid);
        var states = THRESHOLDS.map(make_assoc_state);
        var cl_stream = fs.createWriteStream(path.join(out_dir, sid + ".clusters.jsonl"));
        var tr_stream = fs.createWriteStream(path.join(out_dir, sid + ".tracks.jsonl"));
        for (var fi = 0; fi < sess.frames.length; fi++) {
            var f = sess.frames[fi];
            var frame = level_frame_passthrough(sess.buf_f32, f.start_pts, f.count);
            var hot = find_hot(frame, BG, 0.1, 2.3);
            var clusters = find_clusters(frame, hot);
            var surviv = score_clusters_v2(RF_PERSON, clusters, frame, sess.buf_f32, f.start_pts);
            for (var ci = 0; ci < clusters.length; ci++) {
                var cl = clusters[ci];
                cl_stream.write(JSON.stringify({
                    frame: fi, rank: ci, n: cl.n, cx: +cl.cx.toFixed(4), cy: +cl.cy.toFixed(4),
                    r90: +cl.r90.toFixed(4), zmax: +cl.zmax.toFixed(4),
                    person_prob: +cl.person_prob.toFixed(4),
                    hard_reject: cl.hard_reject || 0
                }) + "\n");
            }
            if (!clusters.length) {
                cl_stream.write(JSON.stringify({ frame: fi, rank: -1, n: 0, person_prob: null }) + "\n");
            }
            var per_thr = {};
            for (var ti = 0; ti < THRESHOLDS.length; ti++) {
                var thr = THRESHOLDS[ti];
                states[ti].frame_no++;
                var kept = surviv.filter(function (cl) { return cl.person_prob >= thr; })
                    .map(function (cl) {
                        return { cx: cl.cx, cy: cl.cy, r90: cl.r90, zmax: cl.zmax, n: cl.n,
                                 person_prob: cl.person_prob, track_id: null };
                    });
                associate(states[ti], kept, sess.fps);
                var confirmed = [];
                for (var ki = 0; ki < kept.length; ki++) {
                    var k = kept[ki];
                    for (var t2 = 0; t2 < states[ti].tracks.length; t2++) {
                        var tr = states[ti].tracks[t2];
                        if (tr.id === k.track_id && tr.age >= TRACK_MIN_AGE) {
                            confirmed.push({ id: k.track_id, person_prob: +k.person_prob.toFixed(4),
                                             cx: +k.cx.toFixed(3), cy: +k.cy.toFixed(3), age: tr.age });
                            break;
                        }
                    }
                }
                var track_snap = states[ti].tracks.map(function (tr) {
                    var assoc_cl = null;
                    for (var ki2 = 0; ki2 < kept.length; ki2++) {
                        if (kept[ki2].track_id === tr.id) { assoc_cl = kept[ki2]; break; }
                    }
                    return { id: tr.id, age: tr.age, miss: tr.miss,
                             cx: +tr.cx.toFixed(3), cy: +tr.cy.toFixed(3),
                             zmax: +tr.zmax.toFixed(3),
                             assoc_prob: assoc_cl ? +assoc_cl.person_prob.toFixed(4) : null,
                             confirmed_now: tr.age >= TRACK_MIN_AGE && assoc_cl !== null };
                });
                per_thr[String(thr)] = { kept_n: kept.length, confirmed: confirmed, tracks: track_snap };
            }
            tr_stream.write(JSON.stringify({ frame: fi, per_thr: per_thr }) + "\n");
        }
        cl_stream.end(); tr_stream.end();
        console.log("[probe v2] " + sid + " frames=" + sess.frames.length + " done");
    });
}

main();
