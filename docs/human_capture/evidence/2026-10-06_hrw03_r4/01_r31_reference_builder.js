/* W03-R3.1 Reference Builder — READ-ONLY evidence script（不改生产行为，不接在线路径）。
 *
 * 用 console 同口径（该 sid 最新 recommended=="tls" 的 job transform → apply_Rt → denoise）
 * 在指定空场会话上构建 reference static map（PL.build_reference_map），并输出：
 *   - 体素总数 / 占用率直方图
 *   - 阈值扫描（含「稀疏远场回收量」= occ≥thr 且 pts_per_frame<2，在线 ≥2 门看不见的面）
 *   - 与在线 build_static_map 的相互覆盖
 *   - 自吸收自检（同会话点按现行 0.12m 匹配规则 / 仅邻域存在）
 *   - 复现 digest（同输入重建两次 hash 相等）
 *
 * 用法: node 01_r31_reference_builder.js [cap_20261004_203349]
 */
"use strict";
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

/* 与生产 key_bg 同源的整数编码（本脚本本地复刻，仅供邻域枚举） */
const BG_BASE = 8192, BG_OFF = 4096;
function bg_key_ijk(ix, iy, iz) { return ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF); }
function bg_decode(key) {
    let iz = key % BG_BASE; key = (key - iz) / BG_BASE;
    const iy = key % BG_BASE;
    return [(key - iy) / BG_BASE - BG_OFF, iy - BG_OFF, iz - BG_OFF];
}

function sha256_file(p) { return crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex"); }

/* 与 console 载入路径一致：取该 sid 最新 recommended=="tls" 的 job transform（captures/leveled）。 */
function resolve_transform(sid) {
    const LV = path.join(REPO, "captures", "leveled");
    if (!fs.existsSync(LV)) return null;
    let best = null;
    for (const job of fs.readdirSync(LV)) {
        const jd = path.join(LV, job);
        const tfPath = path.join(jd, "tls", "transform.json");
        const rpPath = path.join(jd, "report.json");
        if (!fs.existsSync(tfPath) || !fs.existsSync(rpPath)) continue;
        let report, tr;
        try {
            report = JSON.parse(fs.readFileSync(rpPath, "utf8"));
            tr = JSON.parse(fs.readFileSync(tfPath, "utf8"));
        } catch (e) { continue; }
        if (report.sid !== sid || report.recommended !== "tls") continue;
        if (!tr || !tr.R || !tr.t) continue;
        const mt = fs.statSync(jd).mtimeMs;
        if (!best || mt > best.mtime) best = { mtime: mt, R: tr.R, t: tr.t, job: job, transform_id: tr.transform_id };
    }
    return best;
}

/* 复刻 human_detect.js apply_Rt：行主序 R，leveled = R·p + t（原位） */
function apply_Rt(arr, R, t) {
    const r = R.flat ? R.flat() : R;
    for (let k = 0; k < arr.length; k += 4) {
        const x = arr[k], y = arr[k + 1], z = arr[k + 2];
        arr[k] = r[0] * x + r[1] * y + r[2] * z + t[0];
        arr[k + 1] = r[3] * x + r[4] * y + r[5] * z + t[1];
        arr[k + 2] = r[6] * x + r[7] * y + r[8] * z + t[2];
    }
}

function load_leveled_denoised(sid) {
    const dir = path.join(REPO, "captures", "remote", sid);
    const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    const raw = fs.readFileSync(path.join(dir, "points.bin"));
    const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    const frames = RL.frame_slice(meta);
    const STRIDE = RL.STRIDE_F32;
    const tf = resolve_transform(sid);
    const ded = frames.map(f => {
        const s = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        if (tf) apply_Rt(s, tf.R, tf.t);
        return PL.denoise(s);
    });
    return { dir, meta, frames: ded, tf };
}

function digest_ref(ref) {
    const rows = [];
    ref.voxels.forEach((rec, key) => {
        rows.push(key + ":" + rec.occ.toFixed(6) + ":" +
            rec.x.toFixed(4) + "," + rec.y.toFixed(4) + "," + rec.z.toFixed(4) + ":" + rec.obs + ":" + rec.pts_total);
    });
    rows.sort();
    return crypto.createHash("sha256").update(rows.join("\n")).digest("hex");
}

const sid = process.argv[2] || "cap_20261004_203349";
const t0 = Date.now();
const S = load_leveled_denoised(sid);
const ref = PL.build_reference_map(S.frames);
const online = PL.build_static_map(S.frames, { drop_ground: true });

/* ---- 占用率直方图（0.1 宽） ---- */
const NB = 10;
const hist = new Array(NB).fill(0);
ref.voxels.forEach(rec => { hist[Math.min(NB - 1, Math.floor(rec.occ * NB))]++; });

/* ---- 阈值扫描 ---- */
const THR = [0.2, 0.3, 0.5, 0.65, 0.8, 0.9, 0.95, 1.0];
const sweep = THR.map(thr => {
    let keys = 0, sparse = 0, inOnline = 0, onlineNotRef = 0;
    ref.voxels.forEach((rec, key) => {
        if (rec.occ < thr) return;
        keys++;
        if (rec.pts_per_frame < 2) sparse++;          /* 在线 ≥2 每帧门看不见的面 */
        if (online.has(key)) inOnline++;
    });
    online.forEach((rec, key) => {
        const r = ref.voxels.get(key);
        if (!r || r.occ < thr) onlineNotRef++;
    });
    return { thr: thr, keys: keys, sparse_lt2: sparse, in_online: inOnline, online_not_ref: onlineNotRef };
});
let onlineStrong = 0, onlineSupported = 0;
online.forEach(rec => { if (rec.tier === "strong") onlineStrong++; else onlineSupported++; });

/* ---- 自吸收自检（同会话；thr=0.5）：现行规则（邻域 + 形心距 <0.12）与仅邻域存在 ---- */
const ABS_THR = 0.5;
const refSet = new Map();
ref.voxels.forEach((rec, key) => { if (rec.occ >= ABS_THR) refSet.set(key, rec); });
const r2 = PL.PIPE.bg_match_radius * PL.PIPE.bg_match_radius;
function point_match(x, y, z, checkDist) {
    const ij = bg_decode(PL.key_bg(x, y, z));
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const rec = refSet.get(bg_key_ijk(ij[0] + a, ij[1] + b, ij[2] + c));
        if (!rec) continue;
        if (!checkDist) return true;
        const dx = rec.x - x, dy = rec.y - y, dz = rec.z - z;
        if (dx * dx + dy * dy + dz * dz < r2) return true;
    }
    return false;
}
let nPts = 0, curMatch = 0, nbMatchOnly = 0;
for (const frame of S.frames) {
    for (let k = 0; k < frame.length; k += 4) {
        const z = frame[k + 2];
        if (z < PL.PIPE.ground_keep_below_m || z > PL.PIPE.z_max_m) continue;
        nPts++;
        if (point_match(frame[k], frame[k + 1], z, true)) curMatch++;
        else if (point_match(frame[k], frame[k + 1], z, false)) nbMatchOnly++;
    }
}

/* ---- 稀疏远场示例（occ≥0.5、每帧 <2 点、在线 map 不可见） ---- */
const sparseExamples = [];
ref.voxels.forEach((rec, key) => {
    if (rec.occ >= ABS_THR && rec.pts_per_frame < 2 && !online.has(key)) {
        sparseExamples.push({ key: key, x: +rec.x.toFixed(3), y: +rec.y.toFixed(3), z: +rec.z.toFixed(3),
            occ: +rec.occ.toFixed(3), obs: rec.obs, pts_total: rec.pts_total,
            pts_per_frame: +rec.pts_per_frame.toFixed(3), jit: +rec.jit.toFixed(4) });
    }
});
sparseExamples.sort((a, b) => (b.occ - a.occ) || (b.pts_total - a.pts_total));

/* ---- 复现 digest（同输入重建两次） ---- */
const d1 = digest_ref(ref);
const d2 = digest_ref(PL.build_reference_map(S.frames));

const stats = {
    sid: sid,
    generated: new Date().toISOString(),
    console_leveled: true,
    transform: S.tf ? { job: S.tf.job, transform_id: S.tf.transform_id, R: S.tf.R, t: S.tf.t } : null,
    inputs: {
        meta_sha256: sha256_file(path.join(S.dir, "meta.json")),
        points_sha256: sha256_file(path.join(S.dir, "points.bin")),
        human_pipe_lib_sha256: sha256_file(path.join(RP, "human_pipe_lib.js")),
    },
    params: { bg_ref_hit_min_pts: PL.PIPE.bg_ref_hit_min_pts, bg_ref_occ_min: PL.PIPE.bg_ref_occ_min,
              bg_voxel_xy: PL.PIPE.bg_voxel_xy, bg_voxel_z: PL.PIPE.bg_voxel_z,
              ground_keep_below_m: PL.PIPE.ground_keep_below_m, z_max_m: PL.PIPE.z_max_m },
    nframes: ref.nframes,
    ref: { voxels_total: ref.voxels.size, occupancy_hist: hist },
    online: { size: online.size, strong: onlineStrong, supported: onlineSupported },
    sweep: sweep,
    self_absorb: { thr: ABS_THR, points: nPts,
                   cur_rule_ratio: +(curMatch / nPts).toFixed(4),
                   nb_or_cur_ratio: +((curMatch + nbMatchOnly) / nPts).toFixed(4) },
    sparse_examples_top10: sparseExamples.slice(0, 10),
    sparse_total_ge_0p5_lt2_not_online: sparseExamples.length,
    digest: { digest1: d1, digest2: d2, deterministic: d1 === d2 },
    elapsed_ms: Date.now() - t0,
};

fs.writeFileSync(path.join(HERE, "02_r31_stats.json"), JSON.stringify(stats, null, 1) + "\n");
console.log("[r31] sid=" + sid + " leveled=" + (S.tf ? ("job " + S.tf.job) : "NONE(raw)")
    + " frames=" + ref.nframes);
console.log("[r31] reference voxels=" + ref.voxels.size + "  occupancy hist(0.1 bins)=" + hist.join("/"));
console.log("[r31] online map=" + online.size + " (strong " + onlineStrong + "/supported " + onlineSupported + ")");
for (const s of sweep) {
    console.log("[r31] thr=" + s.thr.toFixed(2) + "  ref_keys=" + s.keys
        + "  sparse(<2pt/frame)=" + s.sparse_lt2 + "  in_online=" + s.in_online + "  online_not_ref=" + s.online_not_ref);
}
console.log("[r31] self-absorb thr=0.5: cur_rule=" + stats.self_absorb.cur_rule_ratio
    + "  nb_or_cur=" + stats.self_absorb.nb_or_cur_ratio + "  (points=" + nPts + ")");
console.log("[r31] sparse recovered (occ>=0.5, <2pt/frame, not in online map): " + sparseExamples.length);
console.log("[r31] digest deterministic=" + stats.digest.deterministic + " " + d1.slice(0, 16) + "...  elapsed=" + stats.elapsed_ms + "ms");
