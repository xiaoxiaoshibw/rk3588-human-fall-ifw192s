/* HR-03 剪辑 CLI（node 落盘路径，唯一权威切片入口）。
 *
 * 用法:
 *   node trim.js --src <src_dir> --start <seq> --end <seq> [--out <dst_dir>] [--tool-version 0.1]
 *
 * 出口: 0=正常; 1=校验/IO错; 2=src/dst 状态错(已存在/缺件); 3=磁盘不足
 *
 * 只在 PC 上跑——不接板端 8766、不动 fetch.py、不写回 8090。
 */
"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const L = require("./human_replay_lib.js");

const SPACE_SLACK_BYTES = 16 * 1024 * 1024; // 与 fetch.py slack 同量级给写入留头

function die(msg, code) { console.error("[trim] " + msg); process.exit(code || 1); }

function parse_args(argv) {
    const args = {};   // --src/--out 取字符串，--start/--end 取整数，--tool-version 透传
    for (let i = 2; i < argv.length; i++) {
        const k = argv[i];
        if (k === "--src" || k === "--out" || k === "--tool-version") {
            args[k.replace(/^--/, "").replace(/-/g, "_")] = argv[++i];
        } else if (k === "--start" || k === "--end") {
            args[k.replace(/^--/, "")] = parseInt(argv[++i], 10);
        } else die("未知参数: " + k);
    }
    if (!args.src) die("--src 必填");
    if (args.start == null || args.end == null || !isFinite(args.start) || !isFinite(args.end))
        die("--start/--end 必填且须为整数");
    return args;
}

/* 向上找已存在祖先目录；Windows 盘符固定，statfsSync 在该盘上测余量。 */
function free_bytes_for_path(p) {
    let cur = path.resolve(p);
    for (;;) {
        if (fs.existsSync(cur)) {
            const st = fs.statfsSync(cur);
            return st.bavail * st.bsize;   // bavail=非特权可用块，Linux 上是正确口径
        }
        const parent = path.dirname(cur);
        if (parent === cur) die("路径无已存在祖先: " + p);
        cur = parent;
    }
}

function sha256_file(fp) {
    return new Promise(function (res, rej) {
        const h = crypto.createHash("sha256");
        fs.createReadStream(fp)
            .on("data", function (d) { h.update(d); })
            .on("end", function () { res(h.digest("hex")); })
            .on("error", rej);
    });
}

function pipe_slice(src_bin, dst_bin, start_byte, end_byte) {
    return new Promise(function (res, rej) {
        // end 是闭区间，需 -1；字节数 = end_byte - start_byte
        const r = fs.createReadStream(src_bin, { start: start_byte, end: end_byte - 1 });
        const w = fs.createWriteStream(dst_bin, { flags: "wx" }); // 拒覆盖
        r.on("error", rej);
        w.on("error", rej);
        w.on("finish", res);
        r.pipe(w);
    });
}

async function main() {
    const args = parse_args(process.argv);
    const src = path.resolve(args.src);
    const meta_fp = path.join(src, "meta.json");
    const bin_fp = path.join(src, "points.bin");
    if (!fs.existsSync(meta_fp)) die("src 缺 meta.json: " + src, 2);
    if (!fs.existsSync(bin_fp)) die("src 缺 points.bin: " + src, 2);

    const src_meta = JSON.parse(fs.readFileSync(meta_fp, "utf-8"));
    const bin_size = fs.statSync(bin_fp).size;
    const slice = L.compute_trim_slice(src_meta, args.start, args.end, bin_size);
    const new_sid = L.trim_session_id(src_meta.session_id, args.start, args.end);
    const dst = args.out
        ? path.resolve(args.out)
        : path.join(path.dirname(src), new_sid);
    if (fs.existsSync(dst)) die("目标目录已存在: " + dst, 2);

    const need_bytes = slice.byte_range[1] - slice.byte_range[0];
    const free = free_bytes_for_path(path.dirname(dst));
    L.pre_trim_check(dst, need_bytes, free, SPACE_SLACK_BYTES);

    const now_iso = new Date().toISOString();
    const new_meta = L.rewrite_meta_for_trim(
        src_meta, slice, new_sid, "human_replay_trim/" + (args.tool_version || "0.1"), now_iso);

    fs.mkdirSync(dst, { recursive: false });
    const dst_meta = path.join(dst, "meta.json");
    const dst_bin = path.join(dst, "points.bin");
    try {   /* 中途失败回滚半成品目录，保 dst 要么完整要么不存在 */
        fs.writeFileSync(dst_meta, JSON.stringify(new_meta, null, 1), "utf-8");
        await pipe_slice(bin_fp, dst_bin, slice.byte_range[0], slice.byte_range[1]);
    } catch (e) {
        fs.rmSync(dst, { recursive: true, force: true });
        throw e;
    }

    const [m_sha, b_sha] = await Promise.all([sha256_file(dst_meta), sha256_file(dst_bin)]);
    const record = {
        tool: L.TRIM_TOOL,
        tool_version: args.tool_version || "0.1",
        source_session: src_meta.session_id,
        source_seq_range: slice.seq_range,
        frames_out: new_meta.frames.length,
        point_total: new_meta.total_points,
        byte_range: slice.byte_range,
        bytes_written: need_bytes,
        created_iso: now_iso,
        meta_sha256: m_sha,
        points_sha256: b_sha,
        dst_dir: dst,
    };
    fs.writeFileSync(path.join(dst, "__trim_record.json"), JSON.stringify(record, null, 1));
    console.log(JSON.stringify(record, null, 1));
}

if (require.main === module) {
    main().catch(function (e) {
        const msg = e && e.message ? e.message : String(e);
        const m = msg.match(/空间不足/);
        const m2 = msg.match(/已存在/);
        die(msg, m ? 3 : (m2 ? 2 : 1));
    });
}
