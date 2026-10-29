/* MOTS/MapMOS-inspired statistical ablation, not a reproduction of either network.
 * Motion-event confidence is NOT human probability. Missing returns are UNKNOWN.
 * r01 is reused unchanged; all groups compare the voxel candidate stage, no anchors.
 */
"use strict";
const F = require("../r01/fresh_lib.js");
const P = require("../../../pc_apps/human_replay/human_pipe_lib.js");
const CFG = Object.freeze({ window: 8, min_history: 6, min_changed_neighbors: 2,
    min_variance: 0.015, confirm: 2, evidence_interval_s: 0.5,
    prior_log_odds: -1.4, event_gain: 1.2, stable_loss: 0.12,
    log_limit: 4, candidate_log_odds: 0 });
const OFFSETS = [];
for (let x = -1; x <= 1; x++) for (let y = -1; y <= 1; y++) for (let z = -1; z <= 1; z++)
    OFFSETS.push(x * 8192 * 8192 + y * 8192 + z);

function create(ref, group) {
    if (!["A0", "A1", "A2"].includes(group)) throw new Error("group must be A0/A1/A2");
    return { group, base: F.create_fresh_state(ref), history: [], counts: new Map(), runs: new Map(),
        beliefs: new Map(), last_t: null };
}

function update(st, xyzi, t) {
    if (!(xyzi instanceof Float32Array) || xyzi.length % 4 || !Number.isFinite(t))
        throw new Error("finite timestamp and packed Float32Array XYZI required");
    // Reject before mutating: duplicate/reversed clocks are not independent evidence.
    if (st.last_t !== null && t <= st.last_t) throw new Error("strictly increasing timestamp required");
    st.last_t = t;
    const rep = F.fresh_update(st.base, xyzi, t);
    if (st.group === "A0") return rep;
    const occupied = new Set();
    rep.obs.forEach((a, key) => { if (a.n >= st.base.o.ev_hit_min_pts) occupied.add(key); });
    st.history.push(occupied);
    occupied.forEach(key => st.counts.set(key, (st.counts.get(key) || 0) + 1));
    if (st.history.length > CFG.window) st.history.shift().forEach(key => {
        const n = st.counts.get(key) - 1;
        if (n) st.counts.set(key, n); else st.counts.delete(key);
    });
    let mots_fired = 0;
    const next_runs = new Map();
    occupied.forEach(key => {
        let changed = 0, variance = 0;
        if (st.history.length >= CFG.min_history) {
            // 27 binary time series: variance per neighbor, not variance of their sum.
            for (const offset of OFFSETS) {
                const k = key + offset;
                const hits = st.counts.get(k) || 0;
                const p = hits / st.history.length;
                variance += p * (1 - p);
                if (st.history.at(-1).has(k) !== st.history.at(-2).has(k)) changed++;
            }
        }
        const event = changed >= CFG.min_changed_neighbors && variance / 27 >= CFG.min_variance;
        const run = event ? (st.runs.get(key) || 0) + 1 : 0;
        if (run) next_runs.set(key, run);
        const v = st.base.voxels.get(key);
        if (run >= CFG.confirm) {
            // This frame's reference EMA already ran; it remains r01's estimator.
            if (v.last_event_t !== t) { rep.n_event_fired++; mots_fired++; }
            v.f = 1; v.ever_event = true; v.last_event_t = t;
        }
        if (st.group === "A2") {
            let b = st.beliefs.get(key);
            if (!b) { b = { log_odds: CFG.prior_log_odds, evidence_t: null, pending_event: false }; st.beliefs.set(key, b); }
            b.pending_event = b.pending_event || v.last_event_t === t;
            if (b.evidence_t === null || t - b.evidence_t >= CFG.evidence_interval_s) {
                const gain = b.pending_event ? CFG.event_gain : -CFG.stable_loss;
                b.log_odds = Math.max(-CFG.log_limit, Math.min(CFG.log_limit, b.log_odds + gain));
                b.evidence_t = t;
                b.pending_event = false;
            }
        }
    });
    // Absent / unsupported cells: UNKNOWN; no free-space or negative Bayes update.
    st.runs = next_runs;
    rep.n_mots_fired = mots_fired;
    return rep;
}

function kept_keys(st, obs) {
    const keys = new Set();
    obs.forEach((a, key) => {
        const state = F.voxel_state(st.base, key);
        const b = st.beliefs.get(key);
        if ((state === "HOT" || state === "GHOST") &&
            (st.group !== "A2" || (b && b.log_odds >= CFG.candidate_log_odds))) keys.add(key);
    });
    return keys;
}

function candidates(st, xyzi, keys) {
    const out = [], o = st.base.o;
    for (let i = 0; i < xyzi.length; i += 4) {
        const x = xyzi[i], y = xyzi[i + 1], z = xyzi[i + 2];
        if (Number.isFinite(x + y + z) && z >= o.z_min_m && z <= o.z_max_m && keys.has(P.key_bg(x, y, z)))
            out.push(x, y, z, xyzi[i + 3]);
    }
    return new Float32Array(out);
}
module.exports = { CFG, create, update, kept_keys, candidates };
