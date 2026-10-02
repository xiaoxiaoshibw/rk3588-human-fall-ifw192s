/* HR-03 验收脚本：在真实 captures/remote/cap_20261002_165321 上跑 R1/R2/R3
 * 输出 SHA 对账 + 字段契约 + 字节一致性
 */
"use strict";
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { execFileSync } = require("child_process");

const ROOT = "D:\\Code\\ldiar\\captures\\remote";
const SID = "cap_20261002_165321";
const TRIM = path.join("D:\\Code\\ldiar\\pc_apps\\human_replay", "trim.js");

const sha = (p) => {
    const h = crypto.createHash("sha256");
    const fd = fs.openSync(p, "r");
    const buf = Buffer.alloc(1 << 20);
    let n;
    while ((n = fs.readSync(fd, buf, 0, buf.length, null)) > 0) h.update(buf.subarray(0, n));
    fs.closeSync(fd);
    return h.digest("hex");
};

function run(args, expect_ok) {
    try {
        const out = execFileSync(process.execPath, [TRIM].concat(args), { encoding: "utf-8" });
        return { code: 0, out: out };
    } catch (e) {
        return { code: e.status, out: (e.stdout || "") + (e.stderr || "") };
    }
}

const src_dir = path.join(ROOT, SID);
const src_meta = JSON.parse(fs.readFileSync(path.join(src_dir, "meta.json"), "utf-8"));
const src_bin_fp = path.join(src_dir, "points.bin");
const src_bin_size = fs.statSync(src_bin_fp).size;
const src_meta_sha0 = sha(path.join(src_dir, "meta.json"));
const src_bin_sha0 = sha(src_bin_fp);
const src_mtime_meta0 = fs.statSync(path.join(src_dir, "meta.json")).mtimeMs;
const src_mtime_bin0 = fs.statSync(src_bin_fp).mtimeMs;

console.log("=== 基线 ===");
console.log("src frames(n):", src_meta.frames.length);
console.log("src seq range:", src_meta.frames[0].seq, "…",
    src_meta.frames[src_meta.frames.length - 1].seq);
console.log("src meta sha256:", src_meta_sha0);
console.log("src points.bin sha256:", src_bin_sha0, " bytes:", src_bin_size);
console.log();

// R1: 合法剪辑 [5,12] (帧 idx，不是 seq; seq = 1989282+5=1989287 .. +12=1989294)
const S_SEQ = src_meta.frames[5].seq;
const E_SEQ = src_meta.frames[12].seq;
console.log("=== R1 合法剪辑: 帧 idx [5, 12] = seq [" + S_SEQ + ", " + E_SEQ + "] ===");
const dst_sid = SID + "_clip_" + S_SEQ + "-" + E_SEQ;
const dst_dir = path.join(ROOT, dst_sid);
if (fs.existsSync(dst_dir)) fs.rmSync(dst_dir, { recursive: true, force: true });

let r = run(["--src", src_dir, "--start", String(S_SEQ), "--end", String(E_SEQ)], true);
console.log("trim.js exit:", r.code);
if (r.code !== 0) { console.error("FAIL:", r.out); process.exit(1); }
const rec = JSON.parse(fs.readFileSync(path.join(dst_dir, "__trim_record.json"), "utf-8"));
const dst_meta = JSON.parse(fs.readFileSync(path.join(dst_dir, "meta.json"), "utf-8"));
console.log("dst sid:", dst_meta.session_id);
console.log("dst frames(n):", dst_meta.frames.length);
console.log("dst seqs:", dst_meta.frames.map(f => f.seq));
console.log("dst bag_time_sec[0]:", dst_meta.frames[0].bag_time_sec);
console.log("dst bag_time_sec[7]:", dst_meta.frames[7].bag_time_sec);
console.log("dst duration_sec:", dst_meta.duration_sec);
console.log("dst total_points:", dst_meta.total_points);
console.log("dst meta sha256:", rec.meta_sha256);
console.log("dst bin sha256:", rec.points_sha256);
console.log("dst extraction:", JSON.stringify(dst_meta.extraction));
console.log("does_not_have topics/topics_counts/dropped_points/frame_rate_hz_measured:",
    !("topics" in dst_meta),
    !("topic_message_counts" in dst_meta),
    !("total_dropped_points" in dst_meta),
    !("frame_rate_hz_measured" in dst_meta));
console.log();

// 与源时段一致性: duration 差 == 源 frames[12].bag_time - frames[5].bag_time
const src_dur = src_meta.frames[12].bag_time_sec - src_meta.frames[5].bag_time_sec;
console.log("源 [5,12] 区间时长:", src_dur, "  dst duration:", dst_meta.duration_sec);
console.log("diff:", Math.abs(src_dur - dst_meta.duration_sec));
console.log();

// R2: 字节级一致（手动切片 vs dst）
console.log("=== R2 字节一致性 ===");
const s_off = src_meta.frames[5].offset_points * 28;
const e_off = (src_meta.frames[12].offset_points + src_meta.frames[12].count_points) * 28;
const src_fd = fs.openSync(src_bin_fp, "r");
const expect_slice = Buffer.alloc(e_off - s_off);
fs.readSync(src_fd, expect_slice, 0, e_off - s_off, s_off);
fs.closeSync(src_fd);
const dst_bin = fs.readFileSync(path.join(dst_dir, "points.bin"));
console.log("expect_slice bytes:", expect_slice.length, "  dst_bin bytes:", dst_bin.length);
console.log("byte_identical:", expect_slice.equals(dst_bin));
console.log("expect_slice sha256:", crypto.createHash("sha256").update(expect_slice).digest("hex"));
console.log("dst_bin sha256 (re-hash):", sha(path.join(dst_dir, "points.bin")));
console.log();

// R3: 只读源
console.log("=== R3 只读源 ===");
console.log("src meta sha256 (pre→post):", src_meta_sha0, "→", sha(path.join(src_dir, "meta.json")));
console.log("src bin sha256 (pre→post):", src_bin_sha0, "→", sha(src_bin_fp));
console.log("src meta mtime (pre):", src_mtime_meta0, "  (post):", fs.statSync(path.join(src_dir, "meta.json")).mtimeMs);
console.log("src bin mtime (pre):", src_mtime_bin0, "  (post):", fs.statSync(src_bin_fp).mtimeMs);
console.log();

// 清理(dst_dir 属产物,由用户决定是否删——本测试保留以便 R6 UI 自测)
console.log("=== 产物保留 ===");
console.log("dst_dir:", dst_dir);
