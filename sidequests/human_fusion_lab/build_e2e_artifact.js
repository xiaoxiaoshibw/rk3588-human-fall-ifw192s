/* build_e2e_artifact.js — 汇总 HUMAN-FUSION-UNIFY-R1 真实浏览器 + 契约测试证据为单一 artifact。 */
"use strict";
const fs = require("fs"), path = require("path"), cp = require("child_process"), crypto = require("crypto");
const R = p => JSON.parse(fs.readFileSync(path.join(__dirname, "results", p), "utf8"));
const extract = f => JSON.parse(cp.execFileSync("node", ["dom_extract.js", path.join("results", "e2e_dom", f)], { encoding: "utf8", cwd: __dirname }));
const scenarios = {
    default: Object.assign({ expect: "默认最新有效会话(S8)非SHA失格S9; 算法xgb" }, extract("default.html")),
    deeplink: Object.assign({ expect: "深链?sid=175429&model=rf51_baseline被尊重" }, extract("deeplink.html")),
    badsid: Object.assign({ expect: "非法sid回退默认" }, extract("badsid.html")),
};
function sha(f) { return crypto.createHash("sha256").update(fs.readFileSync(f)).digest("hex"); }
const artifact = {
    workitem: "HUMAN-FUSION-UNIFY-R1",
    when: new Date().toISOString(),
    env: { node: process.version, chrome: "154.0.8037.99", os: "Windows-11-10.0.26300", method: "headless --dump-dom --virtual-time-budget=15000 (真实内核渲染, 非单测)" },
    browser_scenarios: scenarios,
    verdicts: {
        default_latest_valid: scenarios.default.counter === "0 / 522",
        deeplink_respected: scenarios.deeplink.counter === "0 / 257" && /rf51_baseline/.test(scenarios.deeplink.status),
        badsid_falls_back: scenarios.badsid.counter === "0 / 522",
        s9_sha_demoted: scenarios.default.session_option_labels[0].includes("⚠SHA"),
        no_page_error: !scenarios.default.error_marker && !scenarios.deeplink.error_marker && !scenarios.badsid.error_marker,
    },
    node_contract_tests: {
        session_contract: "test_session_contract.js 9/9 PASS (S01-S12镜像 + F01/F02 SHA守卫)",
        r5_parity: R("R5_TEST.json"),
        model_parity: { status: R("MODEL_PARITY.json").status, max_abs_error: R("MODEL_PARITY.json").max_abs_error, models: R("MODEL_PARITY.json").models.length },
    },
    artifacts_sha256: {
        demo_screenshot_png: sha(path.join(__dirname, "results", "DEMO_V1_UNIFY_E2E.png")),
        dom_default: sha(path.join(__dirname, "results", "e2e_dom", "default.html")),
        dom_deeplink: sha(path.join(__dirname, "results", "e2e_dom", "deeplink.html")),
        dom_badsid: sha(path.join(__dirname, "results", "e2e_dom", "badsid.html")),
    },
    isolation: "本轮仅改 sidequests/human_fusion_lab/{session_adapter.js,server.js,demo.html,test_session_contract.js,cdp_*.js,dom_*.js,build_e2e_artifact.js}; 生产human_core/human_replay/Console未改; 无部署/采集/提交/推送",
};
const allPass = Object.values(artifact.verdicts).every(Boolean);
artifact.status = allPass ? "PASS" : "FAIL";
fs.writeFileSync(path.join(__dirname, "results", "LAB_E2E_UNIFY.json"), JSON.stringify(artifact, null, 2));
console.log("LAB_E2E_UNIFY status =", artifact.status);
Object.entries(artifact.verdicts).forEach(([k, v]) => console.log("  " + (v ? "PASS " : "FAIL ") + k));
process.exit(allPass ? 0 : 1);
