/* runner.js — 离线跑实验并落盘。
 *
 * 用法：
 *   node pc_apps/human_core/runner.js --session <dir> --modes BASE_A,BASE_B,U1,U2,U3 [--outdir <dir>]
 *
 * 输出 （每 mode 一个 json):
 *   <outdir>/<sid>__<MODE>.json  → {config, session, frames:[row...], tracks:[...], gt_attestation, run_meta}
 *   <outdir>/all__manifest.json → 全部 mode + SHA + 时间戳
 */
"use strict";
var fs = require("fs");
var path = require("path");
var crypto = require("crypto");

var D = require("./data_loader.js");
var E = require("./engine.js");
var S = require("./schema.js");
var leveling = require("./leveling.js");

var IDENTITY_RT = { R: [1, 0, 0, 0, 1, 0, 0, 0, 1], T: [0, 0, 0] };
/* 与 engine.js 内硬编码一致 — BASE_B 已通过 meta.leveling=False 走这条路 */
var REF_RT = {
    R: [0.893544, 0.0, 0.448975, -0.014337, 0.99949, 0.028533, -0.448746, -0.031932, 0.893089],
    T: [0.0, 0.0, 1.380286],
};

function parse_args(argv) {
    var o = { modes: ["BASE_A"], outdir: null, frames_max: 0 };
    for (var i = 2; i < argv.length; i++) {
        var a = argv[i];
        if (a === "--session") o.session = argv[++i];
        else if (a === "--modes") o.modes = argv[++i].split(",");
        else if (a === "--outdir") o.outdir = argv[++i];
        else if (a === "--frames-max") o.frames_max = parseInt(argv[++i], 10);
        else if (a === "--leveling") o.leveling = argv[++i]; /* "identity" | "ref" (default ref) */
    }
    return o;
}

function run_mode(s, mode, opts) {
    var cfg_map = {
        BASE_A: { mode: E.MODE.BASE_A },
        BASE_B: { mode: E.MODE.BASE_B },
        U1: { mode: E.MODE.U1 },
        U2: { mode: E.MODE.U2, candidates: "fg_plus_retained" },
        U3: { mode: E.MODE.U3, classifier: "rf51" },
        U6: { mode: E.MODE.U6, classifier: "rf51", track_lost_max: 30 },
    };
    var cfg = cfg_map[mode];
    if (!cfg) throw new Error("未实现 mode " + mode);
    var eng = new E.UnifiedEngine(cfg);
    var sid = path.basename(s.session_dir);
    eng.begin_session(sid);
    if (cfg.mode !== E.MODE.BASE_B) {
        /* 传原始传感系 frames — engine.set_online_background 内部 ref leveling */
        eng.set_online_background(s.frames.map(function (f) { return f.xyzi; }));
    }
    var n_frames = opts.frames_max > 0 ? Math.min(opts.frames_max, s.frames.length) : s.frames.length;
    var gt = S.gt_attestation(s.session_dir, s.meta);
    var t0 = Date.now();
    for (var i = 0; i < n_frames; i++) {
        var f = s.frames[i];
        /* 引擎内会自己 leveling （内置 ref R/T), 所以 runner 直传传感系 xyzi + already_leveled=false */
        var fc = S.make_frame_context({
            session_id: sid,
            frame_index: i,
            timestamp: f.timestamp,
            xyzi: f.xyzi,
            meta: s.meta,
            already_leveled: false,
        });
        eng.tick(fc);
    }
    var dt = Date.now() - t0;
    var rep = eng.report();
    var rows = rep.rows;

    /* 会话级聚合 */
    var sum_ms = 0, max_ms = 0, person_frames = 0, furn_frames = 0;
    var track_ids = new Set();
    for (var i2 = 0; i2 < rows.length; i2++) {
        sum_ms += rows[i2].total_ms;
        if (rows[i2].total_ms > max_ms) max_ms = rows[i2].total_ms;
        if (rows[i2].n_person_cand > 0) person_frames++;
        if (rows[i2].n_furn_cand > 0) furn_frames++;
    }
    for (var ti = 0; ti < rep.tracks.length; ti++) track_ids.add(rep.tracks[ti].id);

    return {
        run_meta: {
            sid: sid,
            mode: mode,
            started_iso: new Date(t0).toISOString(),
            elapsed_sec: +(dt / 1000).toFixed(2),
            n_frames_run: n_frames,
            gt_level: gt.level,
            engine_sha_requires: "node_modules - (none)",
        },
        config: eng.cfg,
        frames: rows,
        tracks: rep.tracks.map(function (t) {
            return {
                id: t.id, active: t.active, born_idx: t.born_idx, last_seen: t.last_seen, lost: t.lost,
                human_confirmed: t.human_confirmed,
            };
        }),
        session_summary: {
            n_frames: n_frames,
            mean_ms_per_frame: +(sum_ms / n_frames).toFixed(2),
            max_ms_per_frame: +max_ms.toFixed(2),
            frames_with_person_cand: person_frames,
            frames_with_furniture_cand: furn_frames,
            n_tracks_total: rep.tracks.length,
            n_tracks_confirmed: rep.tracks.filter(function (t) { return t.human_confirmed; }).length,
            n_track_ids_unique: track_ids.size,
        },
        /* 注意： 不打印 precision/recall/f1 — gt_level != HUMAN_VERIFIED 全部 NOT_MEASURABLE */
        prf: { level: gt.level, measurable: gt.level === S.GT_LEVEL.HUMAN_VERIFIED },
    };
}

function main() {
    var opts = parse_args(process.argv);
    if (!opts.session) { console.error("--session 必传"); process.exit(2); }
    var outdir = opts.outdir || path.join("docs/human_capture/evidence/2026-10-10_human_unify_r1/runs",
        path.basename(opts.session));
    fs.mkdirSync(outdir, { recursive: true });

    console.log("[runner] load:", opts.session);
    var s = D.load_session(opts.session);
    console.log("[runner] frames:", s.frames.length, "pts:", s.meta.total_points);

    var manifest = { sessions: [], generated_iso: new Date().toISOString(), session_sha: { points: s.points_sha256, meta: s.meta_sha256 } };
    for (var i = 0; i < opts.modes.length; i++) {
        var m = opts.modes[i];
        console.log("[runner] mode:", m);
        var result = run_mode(s, m, opts);
        var fp = path.join(outdir, path.basename(s.session_dir) + "__" + m + ".json");
        fs.writeFileSync(fp, JSON.stringify(result, null, 1), "utf-8");
        var sha = crypto.createHash("sha256").update(fs.readFileSync(fp)).digest("hex").slice(0, 16);
        console.log("[runner]  →", fp, "(", result.session_summary.n_frames, "frames,", result.session_summary.mean_ms_per_frame, "ms/f,", sha, ")");
        manifest.sessions.push({
            mode: m, file: fp, sha256_16: sha,
            mean_ms: result.session_summary.mean_ms_per_frame,
            person_frames: result.session_summary.frames_with_person_cand,
        });
    }
    var mp = path.join(outdir, "manifest.json");
    fs.writeFileSync(mp, JSON.stringify(manifest, null, 1), "utf-8");
    console.log("[runner] manifest →", mp);
}

if (require.main === module) main();

module.exports = { run_mode: run_mode };
