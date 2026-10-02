// HR-02 lib 单测：node human_replay_lib.test.js（无框架，fail 即 exit 1）
"use strict";
const assert = require("assert");
const L = require("./human_replay_lib.js");

let n = 0;
function t(name, fn) { fn(); n++; console.log("ok", name); }

// ---- frame_slice ----------------------------------------------------------
t("frame_slice: 正常帧表 + 累计区间", () => {
    const meta = { frames: [
        { seq: 101, offset_points: 0, count_points: 10, bag_time_sec: 1.0, stamp_sec: 5, stamp_nanosec: 1 },
        { seq: 102, offset_points: 10, count_points: 8, bag_time_sec: 1.1, stamp_sec: 5, stamp_nanosec: 2 },
        { seq: 103, offset_points: 18, count_points: 4, bag_time_sec: 1.2, stamp_sec: 5, stamp_nanosec: 3 },
    ] };
    const fs = L.frame_slice(meta);
    assert.strictEqual(fs.length, 3);
    assert.deepStrictEqual([fs[0].start_pts, fs[0].end_pts], [0, 10]);
    assert.deepStrictEqual([fs[1].start_pts, fs[1].end_pts], [10, 18]);
    assert.deepStrictEqual([fs[2].start_pts, fs[2].end_pts], [18, 22]);
    assert.strictEqual(fs[1].seq, 102);
    assert.strictEqual(fs[2].bag_time_sec, 1.2);
});

t("frame_slice: 断裂 offset 报错", () => {
    assert.throws(() => L.frame_slice({ frames: [
        { seq: 1, offset_points: 0, count_points: 5 },
        { seq: 2, offset_points: 6, count_points: 5 }, // 期望 5
    ] }), /断裂/);
});

t("frame_slice: 空帧表报错", () => {
    assert.throws(() => L.frame_slice({ frames: [] }), /为空/);
});

// ---- strided_f32_copy ------------------------------------------------------
t("strided_f32_copy: 从 7-f32 跨步抽 [x,y,z,i]", () => {
    // 2 点: [x,y,z,i, ring(lo16+pad16), ts, pad] = 7 f32 槽位
    // ring 槽位只是借 f32 视图的位,值无所谓,验证抽前 4 即可
    const buf = new Float32Array(14);
    buf.set([1, 2, 3, 100, 9, 9, 9], 0);      // 点0
    buf.set([4, 5, 6, 200, 9, 9, 9], 7);      // 点1
    const out = L.strided_f32_copy(buf, 0, 2, 7);
    assert.deepStrictEqual(Array.from(out.slice(0, 4)), [1, 2, 3, 100]);
    assert.deepStrictEqual(Array.from(out.slice(4, 8)), [4, 5, 6, 200]);
});

t("strided_f32_copy: 中间帧切片", () => {
    const buf = new Float32Array(7 * 3); // 3 点
    for (let p = 0; p < 3; p++) buf.set([p, p, p, 50 + p, 0, 0, 0], p * 7);
    const out = L.strided_f32_copy(buf, 1, 1, 7); // 只抽点1
    assert.deepStrictEqual(Array.from(out), [1, 1, 1, 51]);
});

// ---- pick_intensity_range ---------------------------------------------------
t("pick_intensity_range: 宽分布给 [p2,p98]", () => {
    // 200 点均匀 0..199
    const fr = new Float32Array(200 * 4);
    for (let p = 0; p < 200; p++) fr[p * 4 + 3] = p;
    const r = L.pick_intensity_range([fr]);
    assert.ok(r.lo < 10, "lo 应靠近低分位, got " + r.lo);
    assert.ok(r.hi > 180, "hi 应靠近高分位, got " + r.hi);
});

t("pick_intensity_range: 常数强度退化为防零窗口", () => {
    const fr = new Float32Array(32 * 4);
    for (let p = 0; p < 32; p++) fr[p * 4 + 3] = 7;
    const r = L.pick_intensity_range([fr]);
    assert.ok(r.hi > r.lo || (r.lo === 0 && r.hi === 1), "不应除零");
});

// ---- intensity_to_gray -------------------------------------------------------
t("intensity_to_gray: clamp 0..1", () => {
    assert.strictEqual(L.intensity_to_gray(5, 10, 20), 0);
    assert.strictEqual(L.intensity_to_gray(25, 10, 20), 1);
    assert.strictEqual(L.intensity_to_gray(15, 10, 20), 0.5);
});

// ---- format_hhmmss -------------------------------------------------------------
t("format_hhmmss", () => {
    assert.strictEqual(L.format_hhmmss(0), "00:00.0");
    assert.strictEqual(L.format_hhmmss(65.25), "01:05.3"); // toFixed 四舍五入显示
    assert.strictEqual(L.format_hhmmss(null), "--:--");
});

// ---- 飞行相机 ------------------------------------------------------------------------
t("fly_aim: 鼠标右移=向右转（yaw&lt;旧值），下移=低头，pitch 钳位 ±88.8°", () => {
    const s = 0.0024;
    const np1 = L.fly_aim(0, 0, 100, 0, s);
    assert.ok(np1[0] < 0, "dx 正应减小 yaw");
    assert.strictEqual(np1[1], 0);
    const big = L.fly_aim(0, 0, 0, -100000, s);
    assert.strictEqual(big[1], L.FLY_PITCH_LIMIT);
    const bigNeg = L.fly_aim(0, 0, 0, 100000, s);
    assert.strictEqual(bigNeg[1], -L.FLY_PITCH_LIMIT);
});

t("fly_axes: 零角度时 fwd=+X right=-Y；俯仰 90° 时 fwd=+Z", () => {
    const a = L.fly_axes(0, 0);
    assert.deepStrictEqual(a.fwd, [1, 0, 0]);
    assert.deepStrictEqual(a.right, [0, -1, 0]);
    const b = L.fly_axes(0, Math.PI / 2);
    assert.ok(Math.abs(b.fwd[2] - 1) < 1e-15);
    assert.ok(Math.abs(b.fwd[0]) < 1e-15);
});

t("fly_aim_from_dir: 反推能得到正前方 (1,0,0) 的 yaw=0 pitch=0，向上看 pitch=π/2", () => {
    const f = L.fly_aim_from_dir([1, 0, 0]);
    assert.strictEqual(f[0], 0); assert.strictEqual(f[1], 0);
    const u = L.fly_aim_from_dir([0, 0, 1]);
    assert.ok(Math.abs(u[1] - Math.PI / 2) < 1e-9);
});

// ---- default_fps -----------------------------------------------------------------
t("default_fps: 用 meta 值,异常回退 10", () => {
    assert.strictEqual(L.default_fps({ frame_rate_hz_measured: 9.68 }), 9.68);
    assert.strictEqual(L.default_fps({ frame_rate_hz_measured: 0 }), 10);
    assert.strictEqual(L.default_fps({}), 10);
});

// ---- HR-03 剪辑层 -------------------------------------------------------------
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");

function mk_spec_meta() {
    // 与板上真实 meta 同 schema：frames 顺序 + count 真实区间 + 28B stride
    const frames = [];
    let off = 0;
    const counts = [12, 16, 20, 12, 16, 20];
    for (let i = 0; i < counts.length; i++) {
        frames.push({
            seq: 1000 + i,
            stamp_sec: 184480,
            stamp_nanosec: 472427000 + i * 100000,
            bag_time_sec: 1790931202.5 + i * 0.1,
            offset_points: off,
            count_points: counts[i],
            dropped_points: 0,
        });
        off += counts[i];
    }
    return {
        format: "human_capture_session",
        format_version: 1,
        session_id: "cap_20261002_165321",
        created_iso: "2026-10-02T16:53:27+08:00",
        sensor: { model: "IFW192S", frame_id: "innolidar" },
        time_domain: "device_stamp_s_unanchored",
        duration_sec: 1790931202.5 + (counts.length - 1) * 0.1 - 1790931202.5,
        point_layout: { fields: ["x","y","z","intensity","ring","timestamp"], stride_bytes: 28 },
        point_stride_bytes: 28,
        point_file: "points.bin",
        total_points: off,
        frames: frames,
        human_annotations: [],
        extraction: { tool: "bag2session/0.1.0", point_step_bytes_src: 26, source_bag: "/x.bag" },
    };
}

// 构造点缓冲：沿剪辑 [s,e) 字节区间能直接放进一个 ~100 点 fixture。
function mk_spec_bin(meta) {
    const buf = Buffer.alloc(meta.total_points * 28);
    for (let p = 0; p < meta.total_points; p++) {
        const b = p * 28;
        buf.writeFloatLE(p, b);           // x
        buf.writeFloatLE(p + 1000, b + 4); // y
        buf.writeFloatLE(-p, b + 8);      // z
        buf.writeFloatLE(50 + (p % 97), b + 12); // intensity
    }
    return buf;
}

t("trim: 合法 [s,e] 切片 → frames 重新 0 起累计 + byte_range 对齐", () => {
    const meta = mk_spec_meta();
    const bin_sz = meta.total_points * 28;
    const sl = L.compute_trim_slice(meta, 1001, 1004, bin_sz);
    assert.deepStrictEqual(sl.seq_range, [1001, 1004]);
    // counts=[12,16,20,12,16,20]: clip=counts[1..4]=[16,20,12,16]
    assert.deepStrictEqual(sl.byte_range, [12 * 28, (12 + 16 + 20 + 12 + 16) * 28]);
    assert.strictEqual(sl.frames.length, 4);
    assert.strictEqual(sl.frames[0].offset_points, 0);
    assert.strictEqual(sl.frames[0].count_points, 16); // 继承
    assert.strictEqual(sl.frames[3].offset_points, 16 + 20 + 12);
    assert.strictEqual(sl.frames[0].seq, 1001);
    assert.strictEqual(sl.frames[3].seq, 1004);
    assert.deepStrictEqual(
        sl.frames.map(f => +f.bag_time_sec.toFixed(6)),
        [0, 0.1, 0.2, 0.3].map(v => +v.toFixed(6))
    );
    assert.strictEqual(sl.point_total, 64);
});
t("trim: 越界 [s,e] 抛 '区间越界'", () => {
    const meta = mk_spec_meta();
    const bin_sz = meta.total_points * 28;
    assert.throws(() => L.compute_trim_slice(meta, 9999, 10002, bin_sz), /区间越界/);
    assert.throws(() => L.compute_trim_slice(meta, 1003, 1002, bin_sz), /区间越界/);
});
t("trim: seq 断档抛 'seq 非连续'（中断 clip 视为不合法）", () => {
    const meta = mk_spec_meta();
    meta.frames[2].seq = 1099; // 打断
    const bin_sz = meta.total_points * 28;
    assert.throws(() => L.compute_trim_slice(meta, 1000, 1005, bin_sz), /seq 非连续/);
});
t("trim: 累计和 ≠ bin 大小抛 '字节数不符'", () => {
    const meta = mk_spec_meta();
    meta.frames[5].count_points += 1; // 改 count
    const bin_sz = meta.total_points * 28;
    assert.throws(() => L.compute_trim_slice(meta, 1000, 1005, bin_sz), /字节数不符/);
});
t("trim: rewrite_meta_for_trim 白名单 + extraction 重写 + 刻度继承", () => {
    const meta = mk_spec_meta();
    const sl = L.compute_trim_slice(meta, 1001, 1004, meta.total_points * 28);
    const nm = L.rewrite_meta_for_trim(meta, sl, "cap_20261002_165321_clip_1001-1004", undefined, "2030-01-01T00:00:00Z");
    assert.strictEqual(nm.session_id, "cap_20261002_165321_clip_1001-1004");
    assert.strictEqual(nm.format_version, 1);
    assert.strictEqual(nm.point_stride_bytes, 28);
    assert.deepStrictEqual(nm.human_annotations, []);
    assert.strictEqual(nm.extraction.tool, L.TRIM_TOOL);
    assert.strictEqual(nm.extraction.source_session, "cap_20261002_165321");
    assert.deepStrictEqual(nm.extraction.source_range, [1001, 1004]);
    assert.strictEqual(nm.total_points, 64);
    assert.ok(Math.abs(nm.duration_sec - 0.3) < 1e-6);
    assert.ok(!("topics" in nm), "不继承 topics");
    assert.ok(!("topic_message_counts" in nm), "不继承 counts");
    assert.ok(!("frame_rate_hz_measured" in nm), "不落 fps（板上真实样本也无）");
});
t("trim: pre_trim_check 磁盘余量档位", () => {
    assert.strictEqual(L.pre_trim_check("/x", 1000, 1000 + 16 * 1024 * 1024, 16 * 1024 * 1024), true);
    assert.throws(() => L.pre_trim_check("/x", 1000, 1000 + 100, 16 * 1024 * 1024), /磁盘空间不足/);
});
t("trim: trim_command_string 含 src/start/end", () => {
    const s = L.trim_command_string("D:\\Code\\ldiar\\captures\\remote\\cap_x", 100, 200, "D:\\Code\\ldiar\\pc_apps\\human_replay");
    assert.ok(s.indexOf("--start 100") >= 0 && s.indexOf("--end 200") >= 0);
    assert.ok(s.indexOf("cap_x") >= 0);
});

// 端到端（trim.js 子进程）：fixture ~100 点 bin → 切片 → 字节比对
t("trim.js: 端到端切片 byte-identical + 字段契约", () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "hr03-"));
    const meta = mk_spec_meta();
    const bin = mk_spec_bin(meta);
    const src_dir = path.join(tmp, meta.session_id);
    fs.mkdirSync(src_dir);
    fs.writeFileSync(path.join(src_dir, "meta.json"), JSON.stringify(meta));
    fs.writeFileSync(path.join(src_dir, "points.bin"), bin);
    const trim_js = path.join(__dirname, "trim.js");
    const out_json = JSON.parse(execFileSync(process.execPath,
        [trim_js, "--src", src_dir, "--start", "1001", "--end", "1004"]).toString());
    const dst = out_json.dst_dir;
    const dst_meta = JSON.parse(fs.readFileSync(path.join(dst, "meta.json"), "utf-8"));
    const dst_bin = fs.readFileSync(path.join(dst, "points.bin"));
    assert.strictEqual(dst_bin.length, (16 + 20 + 12 + 16) * 28);
    // 字节级一致（零重编码）
    const src_bytes = fs.readFileSync(path.join(src_dir, "points.bin"));
    assert.deepStrictEqual(dst_bin, src_bytes.slice(12 * 28, (12 + 16 + 20 + 12 + 16) * 28));
    // meta 契约
    assert.deepStrictEqual(dst_meta.frames.map(f => f.seq), [1001, 1002, 1003, 1004]);
    assert.strictEqual(dst_meta.frames[0].bag_time_sec, 0);
    assert.strictEqual(dst_meta.total_points, 64);
    // 只读源守门
    const src_meta_orig = mk_spec_meta();
    assert.deepStrictEqual(JSON.parse(fs.readFileSync(path.join(src_dir, "meta.json"), "utf-8")), src_meta_orig);
    fs.rmSync(tmp, { recursive: true, force: true });
});

t("trim.js: 已存在 dst → exit 2", () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "hr03-"));
    const meta = mk_spec_meta();
    const bin = mk_spec_bin(meta);
    const src_dir = path.join(tmp, meta.session_id);
    fs.mkdirSync(src_dir);
    fs.writeFileSync(path.join(src_dir, "meta.json"), JSON.stringify(meta));
    fs.writeFileSync(path.join(src_dir, "points.bin"), bin);
    const trim_js = path.join(__dirname, "trim.js");
    // 先跑一遍建立 dst
    execFileSync(process.execPath, [trim_js, "--src", src_dir, "--start", "1001", "--end", "1004"]);
    // 再跑同区间 → exit 2
    let code = 0;
    try { execFileSync(process.execPath, [trim_js, "--src", src_dir, "--start", "1001", "--end", "1004"], { stdio: "pipe" }); }
    catch (e) { code = e.status; }
    assert.strictEqual(code, 2);
    fs.rmSync(tmp, { recursive: true, force: true });
});

// ---- HR-04 导航层纯函数 -------------------------------------------------------
t("view_preset: 四个预设 + home 字段齐全", () => {
    ["top", "front", "side", "persp", "home"].forEach(name => {
        const p = L.view_preset(name);
        assert.ok(Array.isArray(p.pos) && p.pos.length === 3);
        assert.ok(["ortho", "persp"].includes(p.proj));
        assert.strictEqual(p.up.length, 3);
    });
    // 预设之间相对位置合理
    assert.strictEqual(L.view_preset("top").proj, "ortho");
    assert.strictEqual(L.view_preset("persp").proj, "persp");
    assert.strictEqual(L.view_preset("home").proj, "persp");
    // top 相机在天上往下看（z 为正且大于 5m）
    assert.ok(L.view_preset("top").pos[2] > 5);
});
t("view_preset: front 与 VIEW_FRONT 同向（雷达后方朝 +X，驾驶第二视角）", () => {
    /* rework R1 问题 1：原 front 是回望位（pos x=+12），与 README §5 驾驶视角语义反。
     * 必须与 replay.js VIEW_FRONT = { pos:[-6,0,1.6], tgt:[5,0,1.0] } 完全同位（只差投影）。 */
    const p = L.view_preset("front");
    assert.strictEqual(p.pos[1], 0, "y=0（雷达中轴）");
    assert.ok(p.pos[0] < 0, "front 必须在雷达后方");
    assert.deepStrictEqual(p.pos, [-6, 0, 1.6], "pos 必须与 VIEW_FRONT 一致");
    assert.deepStrictEqual(p.tgt, [5, 0, 1.0], "tgt 必须与 VIEW_FRONT 一致");
});
t("view_preset: 未知名称抛错", () => {
    assert.throws(() => L.view_preset("nowhere"), /未知名称/);
});
t("measure_dist / measure_format: 欧氏距离 + 格式化", () => {
    assert.strictEqual(L.measure_dist([0, 0, 0], [3, 4, 0]), 5);
    assert.strictEqual(L.measure_format(5), "5.00m");
    assert.strictEqual(L.measure_format(0.003), "<0.01m");
    assert.strictEqual(L.measure_format(1.234), "1.23m");
});
t("ray_ground_intersect: 射线打地", () => {
    // 自空中 (2,3,5) 垂直向下
    const p = L.ray_ground_intersect([2, 3, 5], [0, 0, -1]);
    assert.deepStrictEqual(p, [2, 3, 0]);
    // 斜射
    const p2 = L.ray_ground_intersect([0, 0, 1], [1, 0, -1]);
    assert.deepStrictEqual(p2, [1, 0, 0]);
    // 相机在地下 (dir=(0,0,-1) 朝更下) → t<0 返 null
    assert.strictEqual(L.ray_ground_intersect([0, 0, -1], [0, 0, -1]), null);
    // 视线平行地面 → null
    assert.strictEqual(L.ray_ground_intersect([0, 0, 1], [1, 0, 0]), null);
});
t("find_nearest_xy: 按 xy 最近点", () => {
    // 4 点田字格
    const buf = new Float32Array([
        1, 1, 5, 100,
        2, 1, 6, 110,
        1, 2, 7, 120,
        3, 3, 8, 130,
    ]);
    const r = L.find_nearest_xy(buf, 1.4, 1.1);
    assert.strictEqual(r.idx, 0); assert.strictEqual(r.z, 5); assert.strictEqual(r.i, 100);
    assert.ok(r.d_xy < 0.5);
    // 空缓冲 null
    assert.strictEqual(L.find_nearest_xy(new Float32Array(0), 0, 0), null);
});
t("HR-04 exports: LS_PREFIX 非空前缀", () => {
    assert.ok(L.LS_PREFIX.startsWith("human_replay."));
    assert.ok(L.ORTHO_HALF_W > 0 && L.ORTHO_HALF_H > 0);
});

// ---- HR-05 标注编辑层（新增，0 依赖浏览器） -----------------------------------
t("bbox_from_ground_rect: 无点云回退默认 1.8m", () => {
    const b = L.bbox_from_ground_rect([1, 2], [5, 7], null);
    assert.deepStrictEqual(b.center, [3, 4.5, 0.9]);
    assert.deepStrictEqual(b.size, [4, 5, 1.8]);
    assert.strictEqual(b.yaw, 0);
});
t("bbox_from_ground_rect: 点云 z 分位 = 2%/98%", () => {
    // 50 点散布 z=0..1，框内人形在 z=0.5..1.5
    const pts = new Float32Array(50 * 4);
    for (let i = 0; i < 50; i++) pts.set([2 + (i % 10), 3 + (i / 10 | 0), 0.5 + (i % 20) * 0.05, 100], i * 4);
    const b = L.bbox_from_ground_rect([0, 0], [10, 10], pts);
    assert.ok(b.size[2] > 0.89 && b.size[2] < 1.11, "z 高度约 1m，got " + b.size[2]);
    assert.ok(Math.abs(b.zmin - 0.5) < 0.06);
    assert.ok(Math.abs(b.zmax - 1.45) < 0.06);
});
t("bbox_from_rect: 点云缺失/空时回退", () => {
    const b = L.bbox_from_rect([1, 2], [5, 7], 0.1, 1.9);
    function near(a, b, eps) { return Math.abs(a - b) < (eps || 1e-6); }
    assert.ok(near(b.center[0], 3) && near(b.center[1], 4.5) && near(b.center[2], 1.0), "center");
    assert.ok(near(b.size[0], 4) && near(b.size[1], 5) && near(b.size[2], 1.8), "size");
});
t("undo_stack: 20 层容量 + pop/push 往返", () => {
    let st = L.undo_stack_new();
    assert.strictEqual(st.capacity, 20);
    for (let i = 0; i < 25; i++) st = L.undo_stack_push(st, { op: "add", id: i });
    assert.strictEqual(st.stack.length, 20);
    assert.strictEqual(st.stack[0].id, 5, "第 21 条推入后最老出局");
    const pop1 = L.undo_stack_pop(st);
    assert.strictEqual(pop1.entry.id, 24);
    assert.strictEqual(pop1.new_stack.stack.length, 19);
    // 空栈 pop 安全
    let empty = L.undo_stack_new();
    assert.strictEqual(L.undo_stack_pop(empty).entry, null);
});
t("annotation_validate_box: 字段/数值合法双通道", () => {
    // 合法
    assert.strictEqual(L.annotation_validate_box({ center: [1, 2, 0.5], size: [1, 1, 1.8], yaw: 0 }), true);
    // 缺字段
    assert.notStrictEqual(L.annotation_validate_box({}), true);
    // NaN
    assert.notStrictEqual(L.annotation_validate_box({ center: [NaN, 0, 0], size: [1, 1, 1], yaw: 0 }), true);
    // 零/负 size
    assert.notStrictEqual(L.annotation_validate_box({ center: [0, 0, 0], size: [0, 1, 1], yaw: 0 }), true);
    // 超界 center
    assert.notStrictEqual(L.annotation_validate_box({ center: [101, 0, 0], size: [1, 1, 1], yaw: 0 }), true);
    // yaw 超 π
    assert.notStrictEqual(L.annotation_validate_box({ center: [0, 0, 0], size: [1, 1, 1], yaw: Math.PI + 0.1 }), true);
    assert.strictEqual(L.annotation_validate_box({ center: [0, 0, 0], size: [1, 1, 1], yaw: Math.PI }), true);
});
t("annotation_snap_step: 捕捉步进表", () => {
    assert.strictEqual(L.annotation_snap_step("move", 0.234, true), 0.2);
    assert.strictEqual(L.annotation_snap_step("move", 0.234, false), 0.234);
    assert.ok(Math.abs(L.annotation_snap_step("rotate", Math.PI / 5, true) - 7 * Math.PI / 36) < 1e-9);
    assert.strictEqual(L.annotation_snap_step("scale", 1.234, true), 1.25);
});
t("annotation_serialize: 只输出已定稿，契约字段全", () => {
    const meta = {
        frames: [
            { seq: 100, stamp_sec: 1000, stamp_nanosec: 500 },
            { seq: 101, stamp_sec: 1001, stamp_nanosec: 600 },
        ],
    };
    const by_seq = {
        100: [
            { id: "ann_a", label: "person", center: [1, 2, 0.5], size: [1, 1, 1.8], yaw: 0, fixed: true },
            { id: "ann_b", label: "person", center: [3, 4, 0.9], size: [1, 1, 1.8], yaw: 0, fixed: false },
        ],
        101: [
            { id: "ann_c", label: "person", center: [5, 6, 0.5], size: [1, 1, 1.8], yaw: 0, fixed: true },
        ],
    };
    const out = L.annotation_serialize(by_seq, meta, false);
    assert.strictEqual(out.length, 2, "只收已定稿 2 条");
    assert.strictEqual(out[0].id, "ann_a");
    assert.strictEqual(out[1].id, "ann_c");
    assert.strictEqual(out[0].source, "human");
    assert.strictEqual(out[0].frame_seq, 100);
    assert.strictEqual(out[0].stamp_sec, 1000);
    assert.strictEqual(out[0].tool, L.ANNOTATION_TOOL);
    assert.strictEqual(out[0].frame_valid, true);
    // include_unfinished 也通
    assert.strictEqual(L.annotation_serialize(by_seq, meta, true).length, 3);
});
t("HR-05 exports: 必备函数齐全", () => {
    ["bbox_from_ground_rect", "bbox_from_rect", "undo_stack_new",
     "annotation_validate_box", "annotation_snap_step", "annotation_serialize",
     "ANNOTATION_TOOL"].forEach(k => {
        assert.strictEqual(typeof L[k], k === "ANNOTATION_TOOL" ? "string" : "function",
            k + " 未导出");
    });
});

// ---- HR-06 准星放框 -------------------------------------------------------
t("pick_point_on_ray: 射线正中挑到最近点", () => {
    /* 相机在 (0,0,0) 向 +X 看，点云上 (3,0.1,0) (5,0.05,0) —— 3 更近应该被挑到 */
    const pts = new Float32Array([3, 0.1, 0, 0.5, 5, 0.05, 0, 0.6]);
    const pick = L.pick_point_on_ray([0, 0, 0], [1, 0, 0], pts, 0.5);
    assert(pick, "ray 与 0.5m 半径内有点");
    assert.strictEqual(pick.x, 3);
    assert(pick.d_perp <= 0.5);
});

t("pick_point_on_ray: 距离半径太近/太远都落空", () => {
    /* (3, 0.6, 0) 垂直超出 0.5 → null */
    const pts = new Float32Array([3, 0.6, 0, 0.5]);
    const pick = L.pick_point_on_ray([0, 0, 0], [1, 0, 0], pts, 0.5);
    assert.strictEqual(pick, null);
});

t("pick_point_on_ray: 背后点被跳过", () => {
    const pts = new Float32Array([-3, 0, 0, 0.5]);
    assert.strictEqual(L.pick_point_on_ray([0, 0, 0], [1, 0, 0], pts, 0.5), null);
});

t("human_box_from_pick: 有 pick —— 落 pick 的 (x,y)", () => {
    const b = L.human_box_from_pick({ x: 1.2, y: 3.4, z: 0.7 }, null);
    assert.deepStrictEqual(b.center, [1.2, 3.4, 0.9]);
    assert.deepStrictEqual(b.size, L.HUMAN_DEFAULT.size);
    assert.strictEqual(b.zmax, 1.8);
});
t("human_box_from_pick: 无 pick 有 ray∩z=0 —— 落地面点 (x,y)", () => {
    const b = L.human_box_from_pick(null, [2, 4, 0]);
    assert.deepStrictEqual(b.center, [2, 4, 0.9]);
    assert.deepStrictEqual(b.size, L.HUMAN_DEFAULT.size);
});
t("human_box_from_pick: 两者都无 → null（不放空）", () => {
    assert.strictEqual(L.human_box_from_pick(null, null), null);
});

t("make_click_throttle: 200ms 门闸", () => {
    const th = L.make_click_throttle(200);
    assert.strictEqual(th(), true);   /* 第一次放 */
    assert.strictEqual(th(), false);  /* 立刻被挡 */
    /* 真睡 250ms 太拖，直接跳窗 —— 挂钩成只用 Date.now 的独件 */
    const orig = Date.now;
    Date.now = () => orig() + 500;
    try {
        assert.strictEqual(th(), true);   /* 显著时间已过 */
    } finally { Date.now = orig; }
});

console.log("all " + n + " tests passed");
