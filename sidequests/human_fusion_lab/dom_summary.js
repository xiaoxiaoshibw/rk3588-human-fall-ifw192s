/* dom_summary.js — 汇总多场景 dump-dom 提取结果。 */
"use strict";
const cp = require("child_process");
const base = "/c/Users/30680/AppData/Local/Temp/fdom_";
for (const s of ["default", "deeplink", "badsid"]) {
    const raw = cp.execFileSync("node", ["dom_extract.js", base + s + "/dom.html"], { encoding: "utf8", cwd: __dirname });
    const v = JSON.parse(raw);
    const algo = (v.status.match(/算法：(\S+)/) || [])[1] || "-";
    const gt = (v.status.match(/GT：(\S+)/) || [])[1] || "-";
    console.log(s.padEnd(9),
        "counter=" + String(v.counter).padEnd(8),
        "algo=" + algo.padEnd(15),
        "gt=" + gt.padEnd(26),
        "fallback_note=" + /回退/.test(v.status),
        "err=" + v.error_marker,
        "rows=" + v.rows_count);
}
