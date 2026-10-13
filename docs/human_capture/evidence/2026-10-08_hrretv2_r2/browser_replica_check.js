"use strict";
/* HR-RET-V2 inc2 · 浏览器实际行为复现（离线只读 + 本机 8901 只读端点；输出独占写）。
 * 对 human_detect.html 在 223757 上显示的第 1 帧/第 30 帧（页面 DOM 读数见 browser_check.md），
 * 在 node 用同字节输入复刻页面的 载入/变换(leveled_latest R,t)/静态背景/逐帧管线，
 * 比对三组计数（点链 / 清理 / 簇 joint）。页面旗标缺省（S.pipe 无 fusion）⇒ P 路径；
 * 本检查即「浏览器缺省行为 == 节点 P 行为」。输入 SHA 与 transform 值记录在本产物内。 */
const fs = require("fs"), path = require("path"), http = require("http"), crypto = require("crypto");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const RL = require(path.join(ROOT, "pc_apps/human_replay/human_replay_lib.js"));
const sha = b => crypto.createHash("sha256").update(b).digest("hex");

const SID = "cap_20261002_223757";
/* 页面 DOM 读数（2026-10-08 本机浏览器，见 browser_check.md） */
const PAGE = {
    0: { counts: "49126 → 49126 → 3913（削 45213）",
        cleanup: "候选 39 · veto 4 · 删 35 点 / 35 voxel · 其他z保活 6 cell · 簇 24→23",
        clusters: "5 簇 · 确认 ×2 · 候选 ×0 · 非人 ×3" },
    29: { counts: "49134 → 49134 → 3930（削 45204）",
        cleanup: "候选 31 · veto 3 · 删 28 点 / 28 voxel · 其他z保活 4 cell · 簇 25→25",
        clusters: "5 簇 · 确认 ×1 · 候选 ×0 · 非人 ×4" },
    staticVoxels: 1720,
};
function getJSON(url) {
    return new Promise((res, rej) => {
        http.get(url, r => { let d = ""; r.on("data", c => d += c); r.on("end", () => { try { res(JSON.parse(d)); } catch (e) { rej(e); } }); }).on("error", rej);
    });
}
(async () => {
    const lv = await getJSON("http://127.0.0.1:8901/api/leveling/leveled_latest?sid=" + SID);
    if (!lv.ok || !lv.transform || !lv.transform.R || !lv.transform.t) throw new Error("leveled_latest 不可用: " + JSON.stringify(lv).slice(0, 200));
    const Rm = lv.transform.R.flat(), t = lv.transform.t;
    const meta = JSON.parse(fs.readFileSync(path.join(ROOT, "captures/remote", SID, "meta.json"), "utf8"));
    const bins = fs.readFileSync(path.join(ROOT, "captures/remote", SID, "points.bin"));
    const f32 = new Float32Array(bins.buffer, bins.byteOffset, bins.byteLength / 4);
    for (let p = 0; p < f32.length / RL.STRIDE_F32; p++) {   /* 页面 apply_Rt：原位单遍，仅 xyz */
        const s = p * RL.STRIDE_F32, x = f32[s], y = f32[s + 1], z = f32[s + 2];
        f32[s] = Rm[0] * x + Rm[1] * y + Rm[2] * z + t[0];
        f32[s + 1] = Rm[3] * x + Rm[4] * y + Rm[5] * z + t[1];
        f32[s + 2] = Rm[6] * x + Rm[7] * y + Rm[8] * z + t[2];
    }
    const frames = RL.frame_slice(meta);
    const slices = frames.map(f => RL.strided_f32_copy(f32, f.start_pts, f.count, RL.STRIDE_F32));
    const ded = slices.map(PL.denoise);
    const static_keys = PL.build_static_map(ded, { drop_ground: true });
    const tracker = new PL.Tracker();
    const calc = {};
    for (let i = 0; i <= 29; i++) {
        const r = PL.pipeline_frame(slices[i], i, { static_keys, tracker });
        if (i !== 0 && i !== 29) continue;
        const joint = { CONFIRMED_HUMAN: 0, HUMAN_CANDIDATE: 0, NON_HUMAN: 0 };
        r.clusters.forEach(c => joint[c.joint] = (joint[c.joint] || 0) + 1);
        calc[i] = { counts: r.n_in + " → " + r.n_denoise + " → " + r.n_foreground + "（削 " + r.n_dropped + "）",
            cleanup: "候选 " + r.isolated_3d_candidates + " · veto " + r.xy_topology_vetoed + " · 删 " + r.actually_removed_points
                + " 点 / " + r.actually_removed_voxels + " voxel · 其他z保活 " + r.xy_cells_preserved_by_other_z
                + " cell · 簇 " + r.clusters_before_cleanup + "→" + r.clusters_after_cleanup,
            clusters: r.clusters.length + " 簇 · 确认 ×" + joint.CONFIRMED_HUMAN + " · 候选 ×" + joint.HUMAN_CANDIDATE + " · 非人 ×" + joint.NON_HUMAN };
    }
    const verdicts = [];
    const V = (id, target, pass, actual) => verdicts.push({ id, target, pass, actual });
    V("B-static", "节点复刻静态体素数 == 页面 " + PAGE.staticVoxels, static_keys.size === PAGE.staticVoxels, "node=" + static_keys.size);
    for (const i of [0, 29]) {
        for (const k of ["counts", "cleanup", "clusters"]) {
            V("B-" + i + "-" + k, "idx " + i + " " + k + " == 页面", calc[i][k] === PAGE[i][k], calc[i][k]);
        }
    }
    const out = { schema: 1, kind: "hrretv2_inc2_browser_replica", created_utc: new Date().toISOString(),
        inputs: { sid: SID, points_bin: sha(bins), meta_sha256: sha(fs.readFileSync(path.join(ROOT, "captures/remote", SID, "meta.json"))),
            human_pipe_lib: sha(fs.readFileSync(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"))),
            transform: { R: lv.transform.R, t: lv.transform.t } },
        page: PAGE, node: { static_voxels: static_keys.size, frames: { 0: calc[0], 29: calc[29] } }, verdicts };
    fs.writeFileSync(path.join(__dirname, "browser_replica_results.json"), JSON.stringify(out, null, 2) + "\n", { flag: "wx" });
    for (const v of verdicts) console.log((v.pass ? "PASS" : "FAIL") + "  " + v.id + ": " + v.target + " | " + v.actual);
    console.log("done. fails=" + verdicts.filter(v => !v.pass).length);
})().catch(e => { console.error(e.stack || e); process.exitCode = 1; });
