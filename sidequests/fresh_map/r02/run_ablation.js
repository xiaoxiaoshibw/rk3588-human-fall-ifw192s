"use strict";
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const { performance } = require("perf_hooks");
const ROOT = path.resolve(__dirname, "../../..");
const M = require("./mots_lib.js"), F = require("../r01/fresh_lib.js");
const R = require("../r01/run_fresh.js");
const D = require("../../../pc_apps/human_core/data_loader.js");
const groups = ["A0", "A1", "A2"];
const source_files = ["sidequests/fresh_map/r02/mots_lib.js", "sidequests/fresh_map/r02/mots_lib.test.js",
    "sidequests/fresh_map/r02/run_ablation.js", "sidequests/fresh_map/r01/fresh_lib.js",
    "sidequests/fresh_map/r01/run_fresh.js", "pc_apps/human_core/data_loader.js",
    "pc_apps/human_core/leveling.js", "pc_apps/human_replay/human_pipe_lib.js"];
function sha(file) { return D.sha256_path(file); }
function sources() { return Object.fromEntries(source_files.map(f => [f, sha(path.join(ROOT, f))])); }
function input(side) { return { points: side.s.points_sha256, meta: side.s.meta_sha256 }; }
function verify(side) {
    for (const [name, expected] of [["meta.json", side.s.meta_sha256], ["points.bin", side.s.points_sha256]])
        if (sha(path.join(side.s.session_dir, name)) !== expected) throw new Error("input changed: " + side.s.session_dir);
}
function main(argv) {
    if (argv.length !== 2 || argv[0] !== "--outdir") throw new Error("usage: node run_ablation.js --outdir NEW_DIR");
    const out = path.resolve(argv[1]);
    if (fs.existsSync(out)) throw new Error("output must be a new directory");
    fs.mkdirSync(out, { recursive: true });
    const frozen = sources();
    const data = path.join(ROOT, "captures/remote"), ref_sid = "cap_20261014_221808";
    const sids = fs.readdirSync(data).filter(sid => /^cap_/.test(sid) &&
        fs.existsSync(path.join(data, sid, "meta.json")) && fs.existsSync(path.join(data, sid, "points.bin"))).sort();
    const plan = { item: "FRESH-MOTS-01", version: 1, source_sha256: frozen, cfg: M.CFG,
        groups, sids, reference: ref_sid, reference_identity: "historical reference; empty-room identity not revalidated",
        diagnostics: ["cap_20261013_082717", "cap_20261013_083218"],
        policy: "parameters frozen before all runs; remaining non-reference sessions are untouched evaluation split; no GT supplied",
        stage: "voxel candidates only, anchors and classifiers disabled equally", node: process.version };
    fs.writeFileSync(path.join(out, "plan.json"), JSON.stringify(plan, null, 2), { flag: "wx" });
    let reference = R.load_side(path.join(data, ref_sid));
    const ref_pack = F.build_reference(reference.frames);
    const ref_input = input(reference);
    // Keep only loader identity/hashes; release reference frame arrays before sessions.
    reference.frames = null; reference.s.frames = null;
    const all = [];
    for (const sid of sids) {
        const side = R.load_side(path.join(data, sid)), states = groups.map(g => M.create(ref_pack, g));
        const rows = [], cohort = new Set(), stats = groups.map(() => ({ points: 0, candidate_points: 0,
            fired: 0, mots_fired: 0, flicker: 0, common_observed: 0, common_kept: 0, ms: [],
            tail_observed: 0, tail_kept: 0 }));
        let previous_obs = new Map(), previous_kept = groups.map(() => new Set());
        const end = Math.min(170, side.frames.length - 1);
        for (let i = 0; i < side.frames.length; i++) {
            const frame = side.frames[i], t = side.ts[i], reps = [], keys = [];
            for (let g = 0; g < groups.length; g++) {
                const start = performance.now();
                const rep = M.update(states[g], frame, t), kept = M.kept_keys(states[g], rep.obs);
                const cand = M.candidates(states[g], frame, kept);
                const elapsed = performance.now() - start;
                reps.push(rep); keys.push(kept);
                const s = stats[g];
                s.points += frame.length / 4; s.candidate_points += cand.length / 4;
                s.fired += rep.n_event_fired; s.mots_fired += rep.n_mots_fired || 0; s.ms.push(elapsed);
                kept.forEach(k => { if (previous_obs.has(k) && !previous_kept[g].has(k)) s.flicker++; });
                previous_kept[g].forEach(k => { if (rep.obs.has(k) && !kept.has(k)) s.flicker++; });
                rows.push({ i, t, group: groups[g], observed: rep.n_obs_vox, kept: kept.size,
                    candidate_points: cand.length / 4, fired: rep.n_event_fired,
                    mots_fired: rep.n_mots_fired || 0, tick_ms: elapsed.toFixed(3), cohort_obs: 0, cohort_kept: 0 });
            }
            // Identical A0-defined geometric cohort for every group; NOT a human label.
            if (i >= 20 && i <= end) keys[0].forEach(k => cohort.add(k));
            if (i > end) for (let g = 0; g < groups.length; g++) {
                const row = rows[rows.length - 3 + g], s = stats[g];
                cohort.forEach(k => {
                    if (!reps[0].obs.has(k)) return;
                    row.cohort_obs++; if (keys[g].has(k)) row.cohort_kept++;
                });
                s.common_observed += row.cohort_obs; s.common_kept += row.cohort_kept;
                if (i >= Math.floor(side.frames.length * 0.75)) {
                    s.tail_observed += row.cohort_obs; s.tail_kept += row.cohort_kept;
                }
            }
            previous_obs = reps[0].obs; previous_kept = keys;
        }
        verify(side);
        const result = { sid, role: sid === ref_sid ? "reference_control" :
            plan.diagnostics.includes(sid) ? "diagnostic" : "held_out_unlabelled", input_sha256: input(side),
            frames: side.frames.length, cohort_window: [20, end], cohort_voxels: cohort.size,
            groups: Object.fromEntries(stats.map((s, g) => {
                s.candidate_ratio = s.candidate_points / s.points;
                s.cohort_retention = s.common_observed ? s.common_kept / s.common_observed : null;
                s.tail_retention = s.tail_observed ? s.tail_kept / s.tail_observed : null;
                s.ms.sort((a, b) => a - b);
                s.mean_tick_ms = s.ms.reduce((a, b) => a + b, 0) / s.ms.length;
                s.p95_tick_ms = s.ms[Math.ceil(s.ms.length * 0.95) - 1];
                delete s.ms; return [groups[g], s];
            })) };
        const columns = Object.keys(rows[0]);
        fs.writeFileSync(path.join(out, sid + ".csv"), columns.join(",") + "\n" +
            rows.map(r => columns.map(k => r[k]).join(",")).join("\n") + "\n", { flag: "wx" });
        fs.writeFileSync(path.join(out, sid + ".json"), JSON.stringify(result, null, 2), { flag: "wx" });
        all.push(result);
        console.log(sid + " frames=" + result.frames + " candidate%=" + groups.map(g =>
            (100 * result.groups[g].candidate_ratio).toFixed(2)).join("/") + " retention=" + groups.map(g =>
            result.groups[g].cohort_retention?.toFixed(3) ?? "NA").join("/"));
    }
    verify(reference);
    if (JSON.stringify(sources()) !== JSON.stringify(frozen)) throw new Error("source changed during run");
    fs.writeFileSync(path.join(out, "summary.json"), JSON.stringify({ plan, reference_input_sha256: ref_input,
        sessions: all, human_accuracy: "BLOCKED: independently audited GT required",
        visibility: "NOT_RUN: absent returns treated UNKNOWN; no ray model" }, null, 2), { flag: "wx" });
    const outputs = fs.readdirSync(out).map(name => ({ name, sha256: sha(path.join(out, name)) }));
    fs.writeFileSync(path.join(out, "manifest.json"), JSON.stringify({ source_sha256: frozen, outputs }, null, 2), { flag: "wx" });
}
if (require.main === module) main(process.argv.slice(2));
