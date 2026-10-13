"use strict";
/* HR-RET-V2 inc2 · V2-07：v2 语义下空场 0 candidate / 0 confirmed（离线只读；输出独占写）。
 * 口径：空场 cap_20261007_233658（既有配平 job 3c793d…）以自身全帧参考图为 refkeys
 *  （identity-reference：删除集合不窄于任何真实模板 → 这是 v2 的"保留上界"，对 0/0 结论最严）；
 *  在线图同帧构建；P 臂同输入对照。通过：v2 臂 cluster joint CONFIRMED_HUMAN==0 ∧ HUMAN_CANDIDATE==0 ∧ 无确认 track 帧。 */
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const R = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));
const sha = b => crypto.createHash("sha256").update(b).digest("hex");
const shaFile = f => sha(fs.readFileSync(f));

const SID = "cap_20261007_233658", JOB = "3c793d7bda0f4ced86b20ac8076e7b0e";
const raw = R.loadFrames(ROOT, SID, R.levelingBinding(ROOT, SID, JOB), false).frames;
const ded = raw.map(PL.denoise);
const online = PL.build_static_map(ded, { drop_ground: true });
const refkeys = new Map([...PL.build_reference_map(ded).voxels].filter(([, v]) => v.occ >= PL.PIPE.bg_ref_occ_min));

function arm(useFusion) {
    const tracker = new PL.Tracker();
    const joint = { CONFIRMED_HUMAN: 0, HUMAN_CANDIDATE: 0, NON_HUMAN: 0 };
    let confirmedFrames = 0, nFg = 0, onlineOnlyKept = 0;
    const rows = [];
    for (let i = 0; i < raw.length; i++) {
        const ctx = { static_keys: online, tracker };
        if (useFusion) ctx.fusion = { refkeys };
        const r = PL.pipeline_frame(raw[i], i, ctx);
        nFg += r.n_foreground;
        if (useFusion && r.fusion) onlineOnlyKept += r.fusion.n_online_only_kept;
        for (const c of r.clusters) joint[c.joint] = (joint[c.joint] || 0) + 1;
        const cf = r.tracks.filter(t => t.human_confirmed).length;
        confirmedFrames += cf ? 1 : 0;
        rows.push({ i, n_foreground: r.n_foreground, clusters: r.clusters.length,
            joint: r.clusters.map(c => c.joint), confirmed_tracks: cf });
    }
    return { joint, confirmedFrames, nFg, onlineOnlyKept, digest: sha(JSON.stringify(rows)) };
}

const p = arm(false), v = arm(true);
const pass = v.joint.CONFIRMED_HUMAN === 0 && v.joint.HUMAN_CANDIDATE === 0 && v.confirmedFrames === 0;
const out = { schema: 1, kind: "hrretv2_inc2_empty_scene_v2", created_utc: new Date().toISOString(),
    inputs: { session: SID, leveling_job: JOB, nframes: raw.length, ref_voxels: refkeys.size,
        online_voxels: online.size, human_pipe_lib: shaFile(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js")) },
    p_arm: p, v2_arm: v,
    verdict: { id: "V2-07", target: "v2 语义下空场 0 candidate / 0 confirmed", pass,
        actual: "v2 joint=" + JSON.stringify(v.joint) + " confirmed_frames=" + v.confirmedFrames } };
fs.writeFileSync(path.join(__dirname, "empty_v2_results.json"), JSON.stringify(out, null, 2) + "\n", { flag: "wx" });
console.log("P  arm:", JSON.stringify(p));
console.log("V2 arm:", JSON.stringify(v));
console.log((pass ? "PASS" : "FAIL") + "  V2-07: " + out.verdict.actual);
