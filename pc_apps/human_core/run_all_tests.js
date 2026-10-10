/* run_all_tests.js — 跑所有 human_core 测试。 node --max-old-space-size=2048 pc_apps/human_core/run_all_tests.js */
"use strict";
var cp = require("child_process");
var path = require("path");

var TESTS = [
    "test_schema.js",
    "test_data_loader.js",
    "test_engine_smoke.js",
    "test_replay_contract.js",
    "test_edge_cases.js",
    "test_model_compat.js",
];

var failed = 0;
for (var i = 0; i < TESTS.length; i++) {
    var tp = path.join(__dirname, TESTS[i]);
    console.log("=== " + TESTS[i] + " ===");
    var r = cp.spawnSync(process.execPath,
        ["--max-old-space-size=2048", tp],
        { stdio: "inherit", cwd: path.join(__dirname, "../..") });
    if (r.status !== 0) { failed++; console.log("FAIL: " + TESTS[i]); }
}
console.log("\n========== overall: " + (TESTS.length - failed) + "/" + TESTS.length + " suites pass ==========");
process.exit(failed ? 1 : 0);
