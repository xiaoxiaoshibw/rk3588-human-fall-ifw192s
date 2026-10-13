/* run_unify_tests.js — HUMAN-FUSION-UNIFY-R1 统一回归入口（exit 0 = 全绿）。
 * 覆盖：master会话契约镜像 / R5对拍 / 模型对拍 / 引擎rework / human_core套件。
 */
"use strict";
const cp = require("child_process"), path = require("path"), fs = require("fs");
const LAB = __dirname, CORE = path.resolve(LAB, "../../pc_apps/human_core"), REPLAY = path.resolve(LAB, "../../pc_apps/human_replay");
const suites = [
    ["lab session contract (S01-S12镜像+SHA守卫)", LAB, "test_session_contract.js"],
    ["lab R5 2605帧对拍/43联合候选", LAB, "test_r5.js"],
    ["lab 模型对拍6模型200样本+回退", LAB, "test_models.js"],
    ["lab unique tracker", LAB, "unique_tracker.js"],
    ["lab geometry(post) 决策/track 一致性(Q01 P0)", LAB, "test_geometry_consistency.js"],
    ["human_core R4候选审计", CORE, "test_candidate_audit.js"],
    ["human_core 全套件7/7", CORE, "run_all_tests.js"],
    ["master session_selection S01-S12", REPLAY, "session_selection.test.js"],
];
let pass = 0; const detail = [];
for (const [name, cwd, file] of suites) {
    let ok = false, tail = "";
    try { cp.execFileSync("node", [file], { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }); ok = true; }
    catch (e) { tail = (e.stdout || "") + (e.stderr || ""); }
    console.log((ok ? "PASS " : "FAIL ") + name);
    if (!ok) console.log("  tail: " + tail.split("\n").filter(Boolean).slice(-4).join(" | "));
    detail.push({ name, file: path.join(cwd, file), pass: ok });
    if (ok) pass++;
}
const r5 = JSON.parse(fs.readFileSync(path.join(LAB, "results/R5_TEST.json"), "utf8"));
const mp = JSON.parse(fs.readFileSync(path.join(LAB, "results/MODEL_PARITY.json"), "utf8"));
const summary = { workitem: "HUMAN-FUSION-UNIFY-R1", when: new Date().toISOString(), suites: detail, suites_pass: pass, suites_total: suites.length, r5: { status: r5.status, frames: r5.frames, merged_candidates: r5.merged_candidates }, model_parity: { status: mp.status, max_abs_error: mp.max_abs_error }, status: pass === suites.length ? "PASS" : "FAIL" };
fs.writeFileSync(path.join(LAB, "results/UNIFY_REGRESSION.json"), JSON.stringify(summary, null, 2));
console.log("\n== " + summary.status + " " + pass + "/" + suites.length + " suites; r5 frames=" + r5.frames + " merged=" + r5.merged_candidates + " ; model max_err=" + mp.max_abs_error.toExponential(2) + " ==");
process.exit(pass === suites.length ? 0 : 1);
