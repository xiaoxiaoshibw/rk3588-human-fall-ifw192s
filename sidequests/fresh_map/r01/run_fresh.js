/* run_fresh.js — FRESH-MAP r01 离线 runner（单会话×单参数组）。
 * 证据纪律照 human_core/runner.js：--outdir 必须新目录、源码/输入 SHA 冻结、拒运行期篡改。
 * 用法：node run_fresh.js --session <captures/remote/sid目录> --outdir <新目录>
 *   [--ref-session <空场目录> | --warmup 40] [--tau 8] [--ev-hit-min 2] [--ev-confirm 2]
 *   [--move-tol 0.12] [--hot-f-min 0.15] [--slow-alpha 0.02] [--decay exp|linear]
 *   [--ref-occ-min 0.5] [--pset-window fA:fB] [--revive-from fX] [--frames-max N]
 *   [--compare-base-a] [--tag 名称]
 * 坐标系：配平 REF_RT（同 runner.js 缺省 leveling:'ref'）；dt=bag_time_sec 真实秒。
 */
"use strict";
var fs = require("fs"), path = require("path"), crypto = require("crypto"), os = require("os");
var D = require("../../../pc_apps/human_core/data_loader.js");
var L = require("../../../pc_apps/human_core/leveling.js");
var P = require("../../../pc_apps/human_replay/human_pipe_lib.js");
var F = require("./fresh_lib.js");

var PARAM_FLAGS = { "--tau": "tau_s", "--ev-hit-min": "ev_hit_min_pts", "--ev-confirm": "ev_confirm_frames",
    "--move-tol": "move_tol_m", "--hot-f-min": "hot_f_min", "--slow-alpha": "slow_alpha",
    "--decay": "decay", "--ref-occ-min": "ref_occ_min" };
var INT_FLAGS = ["--warmup", "--frames-max", "--revive-from"];
var FLAGS = ["--session", "--outdir", "--ref-session", "--pset-window", "--tag"].concat(Object.keys(PARAM_FLAGS), INT_FLAGS);
var BOOL_FLAGS = ["--compare-base-a"];

function parse_args(argv) {
    var o = { warmup: 40, frames_max: 0, compare_base_a: false, tag: "default",
              params: {}, pset: null, revive_from: null };
    for (var i = 2; i < argv.length; i++) {
        var a = argv[i];
        if (BOOL_FLAGS.indexOf(a) >= 0) { o.compare_base_a = (a === "--compare-base-a"); continue; }
        if (FLAGS.indexOf(a) < 0 || i + 1 === argv.length) throw new Error("未知参数/缺值 " + a);
        var v = argv[++i];
        if (a === "--session") o.session = v;
        else if (a === "--outdir") o.outdir = v;
        else if (a === "--ref-session") o.ref_session = v;
        else if (a === "--tag") o.tag = v;
        else if (a === "--pset-window") {
            var m = /^(\d+):(\d+)$/.exec(v);
            if (!m || +m[1] >= +m[2]) throw new Error("--pset-window 需 fA:fB 且 fA<fB");
            o.pset = [ +m[1], +m[2] ];
        } else if (INT_FLAGS.indexOf(a) >= 0) {
            if (!Number.isSafeInteger(+v) || +v < 0) throw new Error(a + " 需非负整数");
            if (a === "--warmup") o.warmup = +v; else if (a === "--frames-max") o.frames_max = +v;
            else o.revive_from = +v;
        } else {
            var key = PARAM_FLAGS[a];
            if (key === "decay") { if (v !== "exp" && v !== "linear") throw new Error("--decay 仅 exp/linear"); o.params[key] = v; }
            else o.params[key] = +v;
        }
    }
    if (!o.session || !o.outdir) throw new Error("--session 与新 --outdir 必传");
    return o;
}

function hash_file(f) { return crypto.createHash("sha256").update(fs.readFileSync(f)).digest("hex"); }
function source_sha() {
    var files = {
        "sidequests/fresh_map/r01/fresh_lib.js": path.join(__dirname, "fresh_lib.js"),
        "sidequests/fresh_map/r01/run_fresh.js": path.join(__dirname, "run_fresh.js"),
        "pc_apps/human_replay/human_pipe_lib.js": path.join(__dirname, "../../../pc_apps/human_replay/human_pipe_lib.js"),
        "pc_apps/human_core/data_loader.js": path.join(__dirname, "../../../pc_apps/human_core/data_loader.js"),
        "pc_apps/human_core/leveling.js": path.join(__dirname, "../../../pc_apps/human_core/leveling.js"),
    };
    var out = {}; Object.keys(files).forEach(function (k) { out[k] = hash_file(files[k]); }); return out;
}

/* 加载会话 → leveled+denoised 帧数组 + 时间戳数组 */
function load_side(dir) {
    var s = D.load_session(dir);
    var contract = L.resolve_contract({ meta: s.meta }, L.REF_RT);
    var frames = s.frames.map(function (f) { return P.denoise(L.level_frame(f.xyzi, contract.R, contract.T, contract.already_leveled)); });
    var ts = s.frames.map(function (f) { return f.timestamp; });
    return { s: s, frames: frames, ts: ts };
}

function median(arr) { var a = arr.slice().sort(function (x, y) { return x - y; }); return a.length ? (a.length % 2 ? a[(a.length - 1) / 2] : (a[a.length / 2 - 1] + a[a.length / 2]) / 2) : null; }
function p95(arr) { if (!arr.length) return null; var a = arr.slice().sort(function (x, y) { return x - y; }); return a[Math.min(a.length - 1, Math.ceil(0.95 * a.length) - 1)]; }

function main() {
    var args = parse_args(process.argv);
    if (fs.existsSync(args.outdir) && fs.readdirSync(args.outdir).length) throw new Error("outdir 非空，拒绝覆盖");
    var frozen = source_sha();
    var main_side = load_side(args.session);
    var sid = path.basename(main_side.s.session_dir);
    var N = args.frames_max > 0 ? Math.min(args.frames_max, main_side.frames.length) : main_side.frames.length;

    /* 背景层 */
    var ref_pack, ref_desc;
    if (args.ref_session) {
        var rs = load_side(args.ref_session);
        ref_pack = F.build_reference(rs.frames, args.params);
        ref_desc = { type: "external_session", sid: path.basename(rs.s.session_dir),
                     nframes: rs.frames.length, sha: { points: rs.s.points_sha256, meta: rs.s.meta_sha256 } };
    } else {
        var w = Math.min(args.warmup, N);
        ref_pack = F.build_reference(main_side.frames.slice(0, w), args.params);
        ref_desc = { type: "self_warmup", frames: w, note: w > 0 && args.pset && args.pset[0] < w
                     ? "warmup 覆盖运动段：人可能被并入参考图（自污染，预期降级）" : "" };
    }

    /* 新鲜度层 + 记忆 */
    var st = F.create_fresh_state(ref_pack, args.params);
    var mem = F.FreshMemory(args.params);
    var bgA = args.compare_base_a ? P.build_static_map(main_side.frames.slice(0, N), { drop_ground: true }) : null;

    var pset = new Set();                       /* P-set：运动窗内 HOT 体素键并集 */
    var rows = [], revive = null, revive_mode = null, region = null, first_fire_after = null;
    var fired_total = 0, ghost_max = 0, hot_max = 0, anchors_live_max = 0,
        frames_live_anchor = 0, n_clusters_total = 0, n_humanish_total = 0;
    var sum_ms = 0, max_ms = 0, sum_all = 0;

    for (var i = 0; i < N; i++) {
        var t_all0 = Date.now();
        var fr = main_side.frames[i], t = main_side.ts[i];
        var rep = F.fresh_update(st, fr, t);
        /* 锚点库推进：候选点 → XY 柱聚类 → 形心 */
        var cand = F.candidate_xyzi(st, fr, mem);
        var clusters = P.cluster_voxels(P.voxelize(cand));
        /* r7 证据门：簇含 HOT/GHOST 新证据柱才许锚点建/续（防锚点自吞续命） */
        /* r7.1 证据门（续命语义与显示分离）：格 ¬ref_sup∧ever_event 即证据——
         * 静坐者残影超寿沉黑后身份仍由锚点保留；背景/家具永不算证据，锚点不自吞。 */
        var evCols = new Set();
        for (var cp = 0; cp < cand.length; cp += 4) {
            var vv = st.voxels.get(P.key_bg(cand[cp], cand[cp + 1], cand[cp + 2]));
            if (vv && !vv.ref_sup && vv.ever_event) evCols.add(P.key_vox(cand[cp], cand[cp + 1]));
        }
        var cls = clusters.map(function (c) {
            var a = c.acc; return { cx: a.sx / a.n, cy: a.sy / a.n, cz: a.sz / a.n, n: a.n,
                ev: c.keys.some(function (k) { return evCols.has(k); }) };
        });
        var mrep = F.mem_tick(mem, cls, i, t);
        /* 几何门统计（F2 证据用，不做裁决） */
        for (var ci = 0; ci < clusters.length; ci++) {
            n_clusters_total++;
            var ftr = P.cluster_features(clusters[ci]);
            if (ftr.ok && P.classify_human(ftr).label === "HUMAN_CANDIDATE") n_humanish_total++;
        }
        /* P-set 累积（运动窗内） */
        if (args.pset && i >= args.pset[0] && i <= args.pset[1]) {
            rep.obs.forEach(function (a, key) {
                if (F.voxel_state(st, key) === "HOT") pset.add(key);
            });
        }
        /* 存活统计（P-set 体素当帧被观测 → 是否仍是候选） */
        var obs_p = 0, kept_f = 0, kept_a = -1;
        var fgkeys = null;
        if (bgA) {
            var fgA = P.extract_foreground(fr, bgA);
            fgkeys = new Set();
            for (var k = 0; k < fgA.fg_xyzi.length; k += 4)
                fgkeys.add(P.key_bg(fgA.fg_xyzi[k], fgA.fg_xyzi[k + 1], fgA.fg_xyzi[k + 2]));
        }
        if (pset.size) {
            var live = F.mem_live(mem);
            var r2 = st.o.retention.hot_cell_radius_m * st.o.retention.hot_cell_radius_m;
            kept_a = 0;
            pset.forEach(function (key) {
                if (!rep.obs.has(key)) return;                     /* 当帧无点落入：几何收缩，不计 */
                obs_p++;
                var s2 = F.voxel_state(st, key);
                var v = st.voxels.get(key);
                var keep = (s2 === "HOT" || s2 === "GHOST");
                if (!keep) for (var li = 0; li < live.length; li++) {
                    var dx = live[li].x - v.rx, dy = live[li].y - v.ry;
                    if (dx * dx + dy * dy <= r2) { keep = true; break; }
                }
                if (keep) kept_f++;
                if (fgkeys && fgkeys.has(key)) kept_a++;
            });
        }
        /* 复活延迟（--revive-from）：区域=revive 帧的 P-set∩obs；首次 ≥50% 体素 f≥0.5 */
        if (args.revive_from !== null && i === args.revive_from && pset.size) {
            region = [];
            pset.forEach(function (key) { if (rep.obs.has(key)) region.push(key); });
        }
        if (region && region.length && revive === null && i > args.revive_from) {
            var half = 0;
            for (var ri = 0; ri < region.length; ri++) {
                var vr = st.voxels.get(region[ri]);
                if (vr && vr.f >= 0.5) half++;
            }
            if (half / region.length >= 0.5) { revive = i - args.revive_from; revive_mode = "region50"; }
        }
        /* 兜底口径：revive_from 后首次任意发火帧（目标新出现场景 region 常空） */
        if (args.revive_from !== null && i >= args.revive_from && first_fire_after === null && rep.n_event_fired > 0)
            first_fire_after = i - args.revive_from;
        fired_total += rep.n_event_fired;
        ghost_max = Math.max(ghost_max, rep.n_ghost); hot_max = Math.max(hot_max, rep.n_hot);
        anchors_live_max = Math.max(anchors_live_max, mrep.n_live);
        if (mrep.n_live > 0) frames_live_anchor++;
        sum_ms += rep.frame_ms; max_ms = Math.max(max_ms, rep.frame_ms);
        var all_ms = Date.now() - t_all0; sum_all += all_ms;
        rows.push({ i: i, t: t, n_pts: rep.n_pts, n_obs_vox: rep.n_obs_vox, n_fired: rep.n_event_fired,
                    n_hot: rep.n_hot, n_ghost: rep.n_ghost, n_cand: cand.length / 4,
                    anchors_live: mrep.n_live, obs_pset: obs_p, kept_fresh: kept_f,
                    kept_baseA: bgA ? kept_a : "", ms_fresh: +rep.frame_ms.toFixed(3) });
    }

    /* 指标汇总 */
    var tail = Math.floor(N * 0.75), surv_f = [], surv_a = [];
    rows.forEach(function (r) {
        if (pset.size && r.i > (args.pset ? args.pset[1] : tail) && r.obs_pset > 0) {
            surv_f.push(r.kept_fresh / r.obs_pset);
            if (r.kept_baseA !== "") surv_a.push(r.kept_baseA / r.obs_pset);
        }
    });
    var tail_f = [], tail_a = [];
    rows.forEach(function (r) {
        if (pset.size && r.i >= tail && r.obs_pset > 0) {
            tail_f.push(r.kept_fresh / r.obs_pset);
            if (r.kept_baseA !== "") tail_a.push(r.kept_baseA / r.obs_pset);
        }
    });
    var dur_min = N > 1 ? (main_side.ts[N - 1] - main_side.ts[0]) / 60 : 0;
    if (revive === null && first_fire_after !== null) { revive = first_fire_after; revive_mode = "first_fire"; }
    var summary = {
        format_version: 1, item: "FRESH-MAP-01", sid: sid, tag: args.tag,
        params_used: Object.assign({}, F.FP, args.params),
        ref: ref_desc, n_frames: N, duration_s: +(dur_min * 60).toFixed(1),
        pset: args.pset ? { window: args.pset, size: pset.size } : null,
        metrics: {
            still_survival_ratio_fresh_after_pset: surv_f.length ? +(surv_f.reduce(function (s, x) { return s + x; }, 0) / surv_f.length).toFixed(4) : null,
            still_survival_ratio_fresh_tail25: tail_f.length ? +(tail_f.reduce(function (s, x) { return s + x; }, 0) / tail_f.length).toFixed(4) : null,
            still_survival_ratio_baseA_tail25: (bgA && tail_a.length) ? +(tail_a.reduce(function (s, x) { return s + x; }, 0) / tail_a.length).toFixed(4) : null,
            revive_latency_frames: revive === null ? "NOT_RUN" : revive,
            revive_metric_mode: revive === null ? null : revive_mode,
            fired_total: fired_total,
            fired_per_min: dur_min > 0 ? +(fired_total / dur_min).toFixed(1) : null,
            hot_vox_max: hot_max, ghost_vox_max: ghost_max,
            anchors_live_max: anchors_live_max, frames_with_live_anchor: frames_live_anchor,
            clusters_total: n_clusters_total, clusters_humanish: n_humanish_total,
            clusters_humanish_ratio: n_clusters_total ? +(n_humanish_total / n_clusters_total).toFixed(4) : null,
            mean_ms_fresh_update: +(sum_ms / N).toFixed(2), max_ms_fresh_update: +max_ms.toFixed(2),
            mean_ms_full_tick: +(sum_all / N).toFixed(2),
        },
        caveats: [
            "P-set 未标身份，可含边缘家具体素（同 TRADITIONAL_CLUSTER_ML_EFFECT_REPORT 披露口径）",
            "move_tol(0.12) ≥ 单体素半对角(≈0.118)：单格内位移门几乎不可达，事件主要靠新占用/跨格；EMA 滞后重触发未标定",
            "ref 错配（跨日会话）由 永不硬删+ever_event 消化，只影响灰度/暗记配色",
        ],
    };
    if (JSON.stringify(source_sha()) !== JSON.stringify(frozen)) throw new Error("实现文件在运行期间改变，拒绝生成证据");
    if (D.sha256_path(path.join(main_side.s.session_dir, "points.bin")) !== main_side.s.points_sha256
        || D.sha256_path(path.join(main_side.s.session_dir, "meta.json")) !== main_side.s.meta_sha256)
        throw new Error("输入文件在运行期间改变，拒绝生成证据");

    fs.mkdirSync(args.outdir, { recursive: true });
    var base = sid + "__" + args.tag;
    var csv = ["i,t,n_pts,n_obs_vox,n_fired,n_hot,n_ghost,n_cand,anchors_live,obs_pset,kept_fresh,kept_baseA,ms_fresh"]
        .concat(rows.map(function (r) {
            return [r.i, r.t, r.n_pts, r.n_obs_vox, r.n_fired, r.n_hot, r.n_ghost, r.n_cand,
                    r.anchors_live, r.obs_pset, r.kept_fresh, r.kept_baseA, r.ms_fresh].join(",");
        })).join("\n") + "\n";
    fs.writeFileSync(path.join(args.outdir, base + ".csv"), csv, { encoding: "utf8", flag: "wx" });
    fs.writeFileSync(path.join(args.outdir, base + ".json"), JSON.stringify(summary, null, 1), { encoding: "utf8", flag: "wx" });
    /* swallow_curve 采样序列（画"变黑过程"用） */
    fs.writeFileSync(path.join(args.outdir, base + "__survival_curve.csv"),
        "i,obs_pset,kept_fresh,kept_baseA\n" + rows.filter(function (r) { return r.obs_pset > 0; })
            .map(function (r) { return [r.i, r.obs_pset, r.kept_fresh, r.kept_baseA].join(","); }).join("\n") + "\n",
        { encoding: "utf8", flag: "wx" });
    var manifest = {
        generated_iso: new Date().toISOString(), node: process.version,
        platform: process.platform + "/" + process.arch, cpu: os.cpus()[0].model,
        source_sha256: frozen,
        input_sha256: { points: main_side.s.points_sha256, meta: main_side.s.meta_sha256 },
        args: { session: args.session, ref_session: args.ref_session || null,
                warmup: args.warmup, pset: args.pset, revive_from: args.revive_from,
                compare_base_a: args.compare_base_a, params: args.params, frames_max: args.frames_max },
        files: [base + ".csv", base + ".json", base + "__survival_curve.csv"]
            .map(function (f) { return { name: f, sha256: hash_file(path.join(args.outdir, f)) }; }),
    };
    fs.writeFileSync(path.join(args.outdir, "manifest.json"), JSON.stringify(manifest, null, 1), { encoding: "utf8", flag: "wx" });
    var m = summary.metrics;
    console.log(sid + "[" + args.tag + "] f=" + N + " surv_fresh=" + m.still_survival_ratio_fresh_after_pset
        + " surv_baseA=" + m.still_survival_ratio_baseA_tail25 + " fired/min=" + m.fired_per_min
        + " revive=" + m.revive_latency_frames + " ms=" + m.mean_ms_fresh_update + "/" + m.mean_ms_full_tick);
}
if (require.main === module) main();
module.exports = { parse_args: parse_args, load_side: load_side };
