/* CL-01 · 13_sha_recheck.js — 收尾 SHA 复核 + EOL 事件取证（不修改 production）。
 * 用法：node 13_sha_recheck.js  → 13_sha_recheck.log
 */
"use strict";
const fs = require("fs");
const c = require("crypto");
const path = require("path");
const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..");
const P = path.join(REPO, "pc_apps", "human_replay", "human_pipe_lib.js");
const EXPECT = "5bce92a433e58d537c05bfd36f516077f94e80bf351a94aae8efad46b04142b4";

const buf = fs.readFileSync(P);
const s = buf.toString("utf8");
const raw = c.createHash("sha256").update(buf).digest("hex");
const norm = c.createHash("sha256").update(Buffer.from(s.split("\r\n").join("\n"), "utf8")).digest("hex");
const st = fs.statSync(P);
const L = [];
L.push("== CL-01 phase-2 final SHA recheck / EOL incident =================================");
L.push("file      : pc_apps/human_replay/human_pipe_lib.js");
L.push("size      : " + buf.length + " bytes; CRLF count=" + (s.match(/\r\n/g) || []).length + "; line count=" + s.split("\n").length);
L.push("raw sha256: " + raw);
L.push("expected  : " + EXPECT + "   (phase-1, LF)");
L.push("RAW GATE  : " + (raw === EXPECT ? "PASS" : "FAIL (byte-level)"));
L.push("normalized(CRLF->LF) sha256: " + norm);
L.push("CONTENT GATE: " + (norm === EXPECT ? "PASS (content identical modulo line endings)" : "FAIL"));
L.push("mtime     : " + st.mtime.toISOString());
L.push("");
L.push("same-second mtimes in pc_apps/human_replay/ (bulk external rewrite):");
const dir = path.join(REPO, "pc_apps", "human_replay");
for (const f of fs.readdirSync(dir)) {
    const q = path.join(dir, f);
    let qs; try { qs = fs.statSync(q); } catch (e) { continue; }
    const mm = qs.mtime.toISOString().slice(0, 19);
    if (mm === "2026-10-06T13:15:11") L.push("  " + f + "  " + qs.size);
}
L.push("");
L.push("note: 11_ab_real_frame_results.json 记录的 inputs.human_pipe_lib = " + EXPECT);
L.push("      → AB 计算读取的是 phase-1 LF 内容；CRLF 改写发生在 11 run 之后（外部进程）。");
L.push("      本文件仅取证；未修改 production 文件（EOL 未回改）。");
fs.writeFileSync(path.join(HERE, "13_sha_recheck.log"), L.join("\n") + "\n");
console.log(L.join("\n"));
