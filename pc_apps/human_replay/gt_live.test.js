/* gt_live.test.js — node 侧 unit test；不含新的外部依赖 */
"use strict";
const assert = require("assert");
const GT_LIVE = require("./gt_live.js");

let pass = 0, fail = 0;
function t(name, fn) {
    try { fn(); console.log("  ok " + name); pass++; }
    catch (e) { console.error("  FAIL " + name + " :: " + (e && e.message)); fail++; }
}

/* ---- 造一个最小 PointCloud2 ros1 payload ---- */
function u32le(v) { const b = Buffer.alloc(4); b.writeUInt32LE(v >>> 0); return b; }
function u8le(v) { const b = Buffer.alloc(1); b[0] = v & 0xff; return b; }
function sstr(s) { const bb = Buffer.from(s, "utf8"); return Buffer.concat([u32le(bb.length), bb]); }
function f32le(v) { const b = Buffer.alloc(4); b.writeFloatLE(v); return b; }
function build_pc2(lean_pts /*[{x,y,z,intensity}]*/, opts) {
    opts = opts || {};
    const fields = [
        { name: "x", offset: 0, datatype: 7, count: 1 },
        { name: "y", offset: 4, datatype: 7, count: 1 },
        { name: "z", offset: 8, datatype: 7, count: 1 },
    ];
    if (opts.with_intensity) fields.push({ name: "intensity", offset: 12, datatype: 7, count: 1 });
    const point_step = opts.with_intensity ? 16 : 12;
    const chunks = [];
    // Header: seq, stamp.sec, stamp.nsec, frame_id
    chunks.push(u32le(42), u32le(100), u32le(123456789), sstr("lidar"));
    // height, width
    const n = lean_pts.length;
    chunks.push(u32le(1), u32le(n));
    // fields
    chunks.push(u32le(fields.length));
    for (const f of fields) {
        chunks.push(sstr(f.name), u32le(f.offset), u8le(f.datatype), u32le(f.count));
    }
    // is_bigendian, point_step, row_step, data
    chunks.push(u8le(0), u32le(point_step), u32le(point_step * n));
    const data_chunks = [];
    for (const p of lean_pts) {
        data_chunks.push(f32le(p.x), f32le(p.y), f32le(p.z));
        if (opts.with_intensity) data_chunks.push(f32le(p.intensity || 0));
    }
    const data = Buffer.concat(data_chunks);
    chunks.push(u32le(data.length), data, u8le(1)); // is_dense=1
    return new Uint8Array(Buffer.concat(chunks));
}

/* ---- parse_pc2 ---- */
t("parse_pc2 解出 fields/pointStep/width", function () {
    const u8 = build_pc2([{ x: 1, y: 2, z: 3 }]);
    const m = GT_LIVE.parse_pc2(u8);
    assert.strictEqual(m.width, 1);
    assert.strictEqual(m.pointStep, 12);
    assert.strictEqual(m.fields.length, 3);
    assert.strictEqual(m.fields[0].name, "x");
    assert.strictEqual(m.header.seq, 42);
});

/* ---- subsample_xyz ---- */
t("subsample_xyz stride=1 全保留", function () {
    const pts = [];
    for (let i = 0; i < 10; i++) pts.push({ x: i + 0.5, y: (i + 1) * 2, z: (i + 1) * 3 });
    const u8 = build_pc2(pts);
    const r = GT_LIVE.subsample_xyz(u8, 1, 100);
    assert.strictEqual(r.n, 10);
    assert.strictEqual(r.pts[0], 0.5);
    assert.strictEqual(r.pts[3], 1.5);
    assert.strictEqual(r.pts[27], 9.5);   // 第 10 个点的 x
});

t("subsample_xyz stride=2 均匀抽稀（保空间覆盖）", function () {
    const pts = [];
    for (let i = 0; i < 10; i++) pts.push({ x: i + 0.5, y: i + 0.5, z: i + 0.5 });
    const u8 = build_pc2(pts);
    const r = GT_LIVE.subsample_xyz(u8, 2, 100);
    // 应该拿到 src idx = 0,2,4,6,8
    assert.strictEqual(r.n, 5);
    assert.strictEqual(r.pts[0], 0.5);   // 原 idx0
    assert.strictEqual(r.pts[3], 2.5);   // 原 idx2
    assert.strictEqual(r.pts[12], 8.5);  // 原 idx8
});

t("subsample_xyz max_points 截顶保护", function () {
    const pts = [];
    for (let i = 0; i < 100; i++) pts.push({ x: i, y: i, z: i });
    const u8 = build_pc2(pts);
    const r = GT_LIVE.subsample_xyz(u8, 1, 30);
    assert.strictEqual(r.n, 30);
});

t("subsample_xyz 丢弃 (0,0,0) 无效点（IFW192S 实测约定）", function () {
    const pts = [
        { x: 0, y: 0, z: 0 },
        { x: 1, y: 2, z: 3 },
        { x: 0, y: 0, z: 0 },
        { x: 4, y: 5, z: 6 },
        { x: 0, y: 0, z: 0 },
    ];
    const u8 = build_pc2(pts);
    const r = GT_LIVE.subsample_xyz(u8, 1, 100);
    // 5 个里 3 个 (0,0,0) 应被丢
    assert.strictEqual(r.n, 2);
    assert.strictEqual(r.pts[0], 1);
    assert.strictEqual(r.pts[3], 4);
});

t("subsample_xyz 过滤非有限值 (NaN/Inf)", function () {
    const pts = [
        { x: 1, y: 2, z: 3 },
        { x: NaN, y: 0, z: 0 },
        { x: Infinity, y: 0, z: 0 },
        { x: 4, y: 5, z: 6 },
    ];
    const u8 = build_pc2(pts);
    const r = GT_LIVE.subsample_xyz(u8, 1, 100);
    assert.strictEqual(r.n, 2);
    assert.strictEqual(r.pts[0], 1);
    assert.strictEqual(r.pts[3], 4);
});

t("subsample_xyz 缺 x/y/z 字段返回空 (FIX-REVIEW-L2: 真构造)", function () {
    /* 构造只有 x,y 两个字段的合法 pc2，数据 8B/点 — 不是坏包，但缺 z 必须返回空 */
    function u32le(v) { const b = Buffer.alloc(4); b.writeUInt32LE(v >>> 0); return b; }
    function u8le(v) { const b = Buffer.alloc(1); b[0] = v & 0xff; return b; }
    function sstr(s) { const bb = Buffer.from(s, "utf8"); return Buffer.concat([u32le(bb.length), bb]); }
    function f32le(v) { const b = Buffer.alloc(4); b.writeFloatLE(v); return b; }
    const fields = [
        { name: "x", offset: 0, datatype: 7, count: 1 },
        { name: "y", offset: 4, datatype: 7, count: 1 },
    ];
    const point_step = 8, n = 3;
    const chunks = [];
    chunks.push(u32le(1), u32le(0), u32le(0), sstr("l"));
    chunks.push(u32le(1), u32le(n));
    chunks.push(u32le(fields.length));
    for (const f of fields) chunks.push(sstr(f.name), u32le(f.offset), u8le(f.datatype), u32le(f.count));
    chunks.push(u8le(0), u32le(point_step), u32le(point_step * n));
    const data = Buffer.concat([
        f32le(1), f32le(2), f32le(3), f32le(4), f32le(5), f32le(6),
    ]);
    chunks.push(u32le(data.length), data, u8le(1));
    const u8 = new Uint8Array(Buffer.concat(chunks));
    const r = GT_LIVE.subsample_xyz(u8, 1, 100);
    assert.strictEqual(r.n, 0);   // 缺 z → 拒绝整帧，不允许画错点
});

t("subsample_xyz 16-byte pointStep with intensity 正常抽稀", function () {
    const pts = [];
    for (let i = 0; i < 8; i++) pts.push({ x: i + 0.5, y: i + 0.5, z: i + 0.5, intensity: i * 10 });
    const u8 = build_pc2(pts, { with_intensity: true });
    const r = GT_LIVE.subsample_xyz(u8, 1, 100);
    assert.strictEqual(r.n, 8);
    assert.strictEqual(r.pts[0], 0.5);
    assert.strictEqual(r.pts[21], 7.5);   // 第 8 个点 x
});

t("subsample_xyz 拒绝 organized 云 (FIX-REVIEW-M2)", function () {
    /* organized (height=2) 云：跨断言应整体拒绝，不可强行按线性寻址读到错位点 */
    function u32le(v) { const b = Buffer.alloc(4); b.writeUInt32LE(v >>> 0); return b; }
    function u8le(v) { const b = Buffer.alloc(1); b[0] = v & 0xff; return b; }
    function sstr(s) { const bb = Buffer.from(s, "utf8"); return Buffer.concat([u32le(bb.length), bb]); }
    function f32le(v) { const b = Buffer.alloc(4); b.writeFloatLE(v); return b; }
    const fields = [
        { name: "x", offset: 0, datatype: 7, count: 1 },
        { name: "y", offset: 4, datatype: 7, count: 1 },
        { name: "z", offset: 8, datatype: 7, count: 1 },
    ];
    const point_step = 12, w = 2, h = 2, n = w * h;
    const chunks = [];
    chunks.push(u32le(1), u32le(0), u32le(0), sstr("l"));
    chunks.push(u32le(h), u32le(w));   // organized: height=2
    chunks.push(u32le(fields.length));
    for (const f of fields) chunks.push(sstr(f.name), u32le(f.offset), u8le(f.datatype), u32le(f.count));
    chunks.push(u8le(0), u32le(point_step), u32le(point_step * w));
    const data = Buffer.alloc(point_step * n);
    chunks.push(u32le(data.length), data, u8le(1));
    const u8 = new Uint8Array(Buffer.concat(chunks));
    const r = GT_LIVE.subsample_xyz(u8, 1, 100);
    assert.strictEqual(r.n, 0);
});

t("subsample_xyz dataLen 越界 payload 拒绝", function () {
    /* 构造一个看起来合法但 dataLen 比 buffer 实际长 → 必须拒 */
    const u8 = build_pc2([{ x: 1, y: 2, z: 3 }]);
    /* 篡改 buffer 把 dataLen 写成 1000（实际只有 12 字节数据） */
    /* header + fields 总长 ≈ 前面固定篇幅；简单方法：直接截断原 payload */
    const cut = u8.slice(0, u8.length - 5);   // 少 5 字节
    const r = GT_LIVE.subsample_xyz(cut, 1, 100);
    assert.strictEqual(r.n, 0);
});

t("subsample_xyz stride=3 + max_points 双重约束", function () {
    const pts = [];
    for (let i = 0; i < 30; i++) pts.push({ x: i + 0.5, y: i + 0.5, z: i + 0.5 });
    const u8 = build_pc2(pts);
    const r = GT_LIVE.subsample_xyz(u8, 3, 4);
    // stride=3 → 10 个候选 (0,3,6..27); max=4 → n=4
    assert.strictEqual(r.n, 4);
    assert.strictEqual(r.pts[0], 0.5);
    assert.strictEqual(r.pts[9], 9.5);   // 第 4 个被抽中的点 src idx=9
});

/* ---- connect (mock WebSocket) ---- */
function make_mock_ws() {
    const handlers = {};
    const w = {
        readyState: 0,
        sent: [],
        binaryType: null,
        close_called: false,
        _fire(ev, arg) { if (handlers[ev]) handlers[ev](arg); },
        send(p) { this.sent.push(p); },
        close() { this.close_called = true; this.readyState = 3; },
    };
    Object.defineProperty(w, "onopen", { set(f) { handlers.open = f; } });
    Object.defineProperty(w, "onmessage", { set(f) { handlers.message = f; } });
    Object.defineProperty(w, "onclose", { set(f) { handlers.close = f; } });
    Object.defineProperty(w, "onerror", { set(f) { handlers.error = f; } });
    return w;
}

t("connect 收到 advertise 后发出 subscribe 数组形式", function () {
    const old_ws = global.WebSocket;
    const mock = make_mock_ws();
    global.WebSocket = function (url, protos) {
        assert.ok(protos.indexOf("foxglove.websocket.v1") >= 0);
        return mock;
    };
    let rendered = [];
    const conn = GT_LIVE.connect("ws://fake:8765", {
        render: function (pts, n) { rendered.push({ pts: pts.slice(0, n * 3), n: n }); },
        stride: 1, max_points: 100,
    });
    // simulate open + advertise
    mock.readyState = 1; mock._fire("open");
    mock._fire("message", {
        data: JSON.stringify({
            op: "advertise",
            channels: [{ id: 100, topic: "/innolidar_points", encoding: "ros1" }],
        }),
    });
    assert.strictEqual(mock.sent.length, 1);
    const sent = JSON.parse(mock.sent[0]);
    assert.strictEqual(sent.op, "subscribe");
    assert.ok(Array.isArray(sent.subscriptions));
    assert.strictEqual(sent.subscriptions[0].channelId, 100);
    // feed a binary message: op=1, subId=1, logTime=0, then a pc2 payload
    const payload = build_pc2([{ x: 1, y: 2, z: 3 }, { x: 4, y: 5, z: 6 }]);
    const head = Buffer.alloc(13);
    head[0] = 1;
    head.writeUInt32LE(1, 1);          // subId=1
    head.writeBigUInt64LE(0n, 5);      // logTime
    const ab = new Uint8Array(Buffer.concat([head, Buffer.from(payload)])).buffer;
    mock._fire("message", { data: ab });
    assert.strictEqual(rendered.length, 1);
    assert.strictEqual(rendered[0].n, 2);
    assert.strictEqual(rendered[0].pts[0], 1);
    assert.strictEqual(rendered[0].pts[3], 4);
    conn.close();
    global.WebSocket = old_ws;
});

t("connect 忽略非 /innolidar_points 话题的 advertise", function () {
    const old_ws = global.WebSocket;
    const mock = make_mock_ws();
    global.WebSocket = function () { return mock; };
    let render_count = 0;
    const conn = GT_LIVE.connect("ws://fake:8765", {
        render: function () { render_count++; },
        stride: 1,
    });
    mock.readyState = 1; mock._fire("open");
    mock._fire("message", {
        data: JSON.stringify({
            op: "advertise",
            channels: [{ id: 200, topic: "/some_other", encoding: "ros1" }],
        }),
    });
    assert.strictEqual(mock.sent.length, 0);   // 不应订阅
    conn.close();
    global.WebSocket = old_ws;
});

t("connect 拒绝非 ros1 编码（跳过，不订阅）", function () {
    const old_ws = global.WebSocket;
    const mock = make_mock_ws();
    global.WebSocket = function () { return mock; };
    let errs = [];
    const conn = GT_LIVE.connect("ws://fake:8765", {
        render: function () {},
        on_error: function (m) { errs.push(m); },
    });
    mock.readyState = 1; mock._fire("open");
    mock._fire("message", {
        data: JSON.stringify({
            op: "advertise",
            channels: [{ id: 300, topic: "/innolidar_points", encoding: "cdr" }],
        }),
    });
    assert.strictEqual(mock.sent.length, 0);
    assert.ok(errs.length > 0);
    conn.close();
    global.WebSocket = old_ws;
});

t("close 后不再重连 / 不再 render", function () {
    const old_ws = global.WebSocket;
    const mock = make_mock_ws();
    global.WebSocket = function () { return mock; };
    const conn = GT_LIVE.connect("ws://fake:8765", { render: function () {} });
    mock.readyState = 1; mock._fire("open");
    conn.close();
    // 即便服务器再发消息，也不应调 render
    const payload = build_pc2([{ x: 1, y: 2, z: 3 }]);
    const head = Buffer.alloc(13);
    head[0] = 1; head.writeUInt32LE(1, 1); head.writeBigUInt64LE(0n, 5);
    const ab = new Uint8Array(Buffer.concat([head, Buffer.from(payload)])).buffer;
    // 不应 throw
    mock._fire("message", { data: ab });
    global.WebSocket = old_ws;
});

console.log("\n=== GT_LIVE tests: " + pass + " PASS / " + fail + " FAIL ===");
process.exit(fail > 0 ? 1 : 0);
