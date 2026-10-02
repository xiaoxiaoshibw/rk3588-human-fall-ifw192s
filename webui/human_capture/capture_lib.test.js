/* capture_lib 单测：cd webui/human_capture && node capture_lib.test.js
 * 风格与 human_fall_preview/human_fall_lib.test.js 一致（无三方依赖）。 */
"use strict";
const LIB = require("./capture_lib.js");

let passed = 0, failed = 0;
const failures = [];

function ok(cond, name) {
  if (cond) { passed++; }
  else { failed++; failures.push(name); }
}

function eq(a, b, name) { ok(a === b, `${name}: got=${JSON.stringify(a)} want=${JSON.stringify(b)}`); }

// fmtBytes
eq(LIB.fmtBytes(0), "0 B", "fmtBytes 0");
eq(LIB.fmtBytes(512), "512 B", "fmtBytes 512");
eq(LIB.fmtBytes(2048), "2.00 KB", "fmtBytes 2KB");
eq(LIB.fmtBytes(114550423), "109.2 MB", "fmtBytes 114MB (1dp)");
eq(LIB.fmtBytes(null), "—", "fmtBytes null");
eq(LIB.fmtBytes(NaN), "—", "fmtBytes NaN");

// fmtDuration
eq(LIB.fmtDuration(9.2), "9.2s", "fmtDuration 9.2");
eq(LIB.fmtDuration(92.5), "1m33s", "fmtDuration 92.5");
eq(LIB.fmtDuration(600), "10m00s", "fmtDuration 600");
eq(LIB.fmtDuration(null), "—", "fmtDuration null");

// fmtElapsed
eq(LIB.fmtElapsed(5), "00:05", "fmtElapsed 5");
eq(LIB.fmtElapsed(65), "01:05", "fmtElapsed 65");
eq(LIB.fmtElapsed(3665), "1:01:05", "fmtElapsed 3665");

// stateBadgeHtml 含 class 和 label
ok(LIB.stateBadgeHtml("ready").includes("badge ready"), "badge ready cls");
ok(LIB.stateBadgeHtml("ready").includes("就绪"), "badge ready label");
ok(LIB.stateBadgeHtml("recording").includes("rec"), "badge recording pulse");
ok(LIB.stateBadgeHtml("garbage").includes('class="badge"'), "badge unknown → bare");

// sortSessionsDesc
const sorted = LIB.sortSessionsDesc([
  { session_id: "a", created_iso: "2026-10-02T10:00:00" },
  { session_id: "c", created_iso: "2026-10-02T12:00:00" },
  { session_id: "b", created_iso: "2026-10-02T11:00:00" },
]);
eq(sorted.map(s => s.session_id).join(","), "c,b,a", "sort desc");
eq(LIB.sortSessionsDesc(null).length, 0, "sort null");
eq(LIB.sortSessionsDesc([{ session_id: "x" }])[0].session_id, "x", "sort missing created");

// canRequestDownload
ok(LIB.canRequestDownload({ state: "ready" }), "can ready");
ok(!LIB.canRequestDownload({ state: "ready", transferred: true }), "already transferred");
ok(!LIB.canRequestDownload({ state: "ready", download_requested: true }), "already requested");
ok(!LIB.canRequestDownload({ state: "recording" }), "recording not ready");
ok(!LIB.canRequestDownload(null), "null");

// elapsedSec
const t0 = Date.parse("2026-10-02T10:00:00Z");
eq(LIB.elapsedSec("2026-10-02T10:00:00Z", t0 + 30 * 1000), 30, "elapsed 30s");
eq(LIB.elapsedSec("garbage", t0), 0, "elapsed garbage");
eq(LIB.elapsedSec("2026-10-02T11:00:00Z", t0), 0, "elapsed future→0");

// 汇总
console.log(`capture_lib.test.js: ${passed} passed, ${failed} failed`);
if (failed > 0) {
  console.error("FAILED:");
  failures.forEach(f => console.error("  - " + f));
  process.exit(1);
}
