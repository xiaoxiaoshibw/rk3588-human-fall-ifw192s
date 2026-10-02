/* HR-03 exit code 全覆盖探针：exit 1(校验/IO错) / 2(已存在或 src 缺件) / 3(磁盘不足)
 * 3 无法在不造假盘的前提下直接触发——pre_trim_check 已单测覆盖（human_replay_lib.test.js
 * "trim: pre_trim_check 磁盘余量档位"），本探针只跑 1/2 与 r5 bailout。
 */
"use strict";
const fs = require("fs"); const path = require("path");
const { execFileSync } = require("child_process");
const os = require("os");

const TRIM = "D:\\Code\\ldiar\\pc_apps\\human_replay\\trim.js";

function run(args) {
    try { execFileSync(process.execPath, [TRIM].concat(args), { encoding: "utf-8", stdio: "pipe" }); return { code: 0, out: "" }; }
    catch (e) { return { code: e.status, out: (e.stderr || "") + (e.stdout || "") }; }
}

/* 起一部分 fixture：meta + bin 不相符的 src 目录 */
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "hr03x-"));
const src = path.join(tmp, "cap_fake");
fs.mkdirSync(src);
const meta = {
    format: "human_capture_session", format_version: 1, session_id: "cap_fake",
    created_iso: "2030-01-01T00:00:00+08:00", sensor: { model: "IFW192S", frame_id: "innolidar" },
    time_domain: "device_stamp_s_unanchored", duration_sec: 0.1,
    point_layout: { stride_bytes: 28 }, point_stride_bytes: 28, point_file: "points.bin",
    total_points: 2,
    frames: [
        { seq: 1, stamp_sec: 0, stamp_nanosec: 0, bag_time_sec: 100, offset_points: 0, count_points: 1, dropped_points: 0 },
        { seq: 2, stamp_sec: 0, stamp_nanosec: 0, bag_time_sec: 100.1, offset_points: 1, count_points: 1, dropped_points: 0 },
    ],
    human_annotations: [],
    extraction: { tool: "bag2session/0.1.0" },
};
fs.writeFileSync(path.join(src, "meta.json"), JSON.stringify(meta));
fs.writeFileSync(path.join(src, "points.bin"), Buffer.alloc(2 * 28));

console.log("=== exit 1: 越界 ===");
let r1 = run(["--src", src, "--start", "1", "--end", "999"]);
console.log("code:", r1.code, " msg:", r1.out.trim());

console.log("=== exit 1: seq 断 ===");
const meta_broken = JSON.parse(JSON.stringify(meta));
meta_broken.frames[1].seq = 99;
const src2 = path.join(tmp, "cap_fake2"); fs.mkdirSync(src2);
fs.writeFileSync(path.join(src2, "meta.json"), JSON.stringify(meta_broken));
fs.writeFileSync(path.join(src2, "points.bin"), Buffer.alloc(2 * 28));
let r2 = run(["--src", src2, "--start", "1", "--end", "2"]);
console.log("code:", r2.code, " msg:", r2.out.trim());

console.log("=== exit 1: bin size 不符 ===");
fs.writeFileSync(path.join(src, "points.bin"), Buffer.alloc(3 * 28));  // 多了 1 点
let r3 = run(["--src", src, "--start", "1", "--end", "2"]);
console.log("code:", r3.code, " msg:", r3.out.trim());

console.log("=== exit 2: dst 已存在 ===");
const real_src = "D:\\Code\\ldiar\\captures\\remote\\cap_20261002_165321";
let r4 = run(["--src", real_src, "--start", "1989287", "--end", "1989294"]);
console.log("code:", r4.code, " msg:", r4.out.trim());

console.log("=== exit 2: src 缺 meta ===");
const src3 = path.join(tmp, "cap_fake3"); fs.mkdirSync(src3);
fs.writeFileSync(path.join(src3, "points.bin"), Buffer.alloc(2 * 28));
let r5 = run(["--src", src3, "--start", "1", "--end", "2"]);
console.log("code:", r5.code, " msg:", r5.out.trim());

console.log("=== exit 2: src 缺 bin ===");
const src4 = path.join(tmp, "cap_fake4"); fs.mkdirSync(src4);
fs.writeFileSync(path.join(src4, "meta.json"), JSON.stringify(meta));
let r6 = run(["--src", src4, "--start", "1", "--end", "2"]);
console.log("code:", r6.code, " msg:", r6.out.trim());

console.log("=== exit 3: 磁盘不足（pre_trim_check 已在单测覆盖） ===");
console.log("覆盖点：human_replay_lib.test.js 'trim: pre_trim_check 磁盘余量档位'");

fs.rmSync(tmp, { recursive: true, force: true });
console.log("DONE");
