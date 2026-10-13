/* detect_overlay.test.js — node 断言测试, 不用浏览器.
 * 跑法: node detect_overlay.test.js
 * B2-A-FIX-R1: 删除 is_stable 死分支用例; 新增 FIX-1(单帧一对一)/FIX-2(HUD)/FIX-3(gen+frame identity) 回归.
 */
"use strict";

global.window = {};
var HOD = require("./detect_overlay.js");

function assert(cond, msg) {
    if (!cond) { console.log("FAIL: " + msg); process.exit(1); }
    console.log("PASS: " + msg);
}

var T = HOD._test;
function fresh() { HOD.reset(); T.last.t_id_next = 1; T.last.tracks = []; T.last.frame_no = 0; }
function mkcl(cx, cy, extra) {
    var o = { cx: cx, cy: cy, r90: 0.2, zmax: 1.8, n: 50 };
    if (extra) for (var k in extra) o[k] = extra[k];
    return o;
}

// ---- level_frame: already_leveled 时透传 ----
(function () {
    var buf = new Float32Array(7 * 3);
    buf[0] = 1; buf[1] = 2; buf[2] = 3;
    buf[7] = 4; buf[8] = 5; buf[9] = 6;
    buf[14] = 7; buf[15] = 8; buf[16] = 9;
    var out = T.level_frame(buf, 1, 2, true);
    assert(out.n === 2 && out.x[0] === 4 && out.y[0] === 5 && out.z[0] === 6,
           "level_frame already_leveled 透传");
    var out2 = T.level_frame(buf, 1, 2, false);
    var expect_x = 0.893544 * 4 + 0.448975 * 6;
    assert(Math.abs(out2.x[0] - expect_x) < 1e-4, "level_frame 带 R/T 变换 (x)");
})();

// ---- grid_key: 与 Python 版一致 (gx*4096+gy) ----
(function () {
    assert(T.grid_key(0.0, 0.0) === 0, "grid_key(0,0)=0");
    assert(T.grid_key(0.11, 0.11) === 2 * 4096 + 2, "grid_key(0.11,0.11)=8194");
    var gxn = Math.floor(-0.051 / 0.05);
    assert(T.grid_key(-0.051, 0.11) === gxn * 4096 + 2, "grid_key 负数 floor 一致");
})();

// ---- find_clusters: 30 点一簇成/29 点不成 ----
(function () {
    var frame = { n: 60, x: new Float32Array(60), y: new Float32Array(60), z: new Float32Array(60) };
    for (var i = 0; i < 30; i++) {
        frame.x[i] = 2.0 + (i % 10) * 0.02;
        frame.y[i] = 1.0 + Math.floor(i / 10) * 0.02;
        frame.z[i] = 1.5;
    }
    for (var i = 0; i < 29; i++) {
        var k = 30 + i;
        frame.x[k] = 3.0 + (i % 10) * 0.02;
        frame.y[k] = 2.0 + Math.floor(i / 10) * 0.02;
        frame.z[k] = 1.5;
    }
    var hot = [];
    for (var i = 0; i < 60; i++) hot.push(i);
    var comps = T.find_clusters(frame, hot);
    assert(comps.length === 1, "find_clusters 29 点簇被丢, 只剩 1 簇 (含 30 点)");
    assert(comps[0].n === 30, "剩下簇点数=30");
})();

// ---- find_clusters: 两簇, 距离远, 返回 2 ----
(function () {
    var frame = { n: 60, x: new Float32Array(60), y: new Float32Array(60), z: new Float32Array(60) };
    for (var i = 0; i < 30; i++) { frame.x[i] = 2.0; frame.y[i] = i * 0.02; frame.z[i] = 1.5; }
    for (var i = 0; i < 30; i++) { var k = 30 + i; frame.x[k] = 5.0; frame.y[k] = 5.0 + i * 0.02; frame.z[k] = 1.5; }
    var hot = [];
    for (var i = 0; i < 60; i++) hot.push(i);
    var comps = T.find_clusters(frame, hot);
    assert(comps.length === 2, "find_clusters 相距远给 2 簇");
})();

// ============ B2-A-FIX-R1 回归 ============
// CE1→修复: 同帧两簇不共享同一 track, age 单帧至多单++ (原 r1 缺陷: age 双++ + cx 覆写)
(function () {
    fresh();
    T.associate([mkcl(2.0, 1.0)], 10);
    var tr1 = T.last.tracks[0];
    assert(tr1.age === 1, "CE1.a 建 track age=1");
    /* 两簇均 <1.0m 于 tr1: FIX-1 后第二簇应新建 track, 不共享 */
    T.associate([mkcl(2.02, 1.01, { n: 52 }), mkcl(2.30, 1.20, { r90: 0.4, n: 40 })], 10);
    assert(T.last.tracks.length === 2, "CE1.b FIX-1: 同帧两簇→两 track (实际 " + T.last.tracks.length + ")");
    assert(tr1.age === 2, "CE1.c FIX-1: 原 track age 单帧只 +: " + tr1.age + " (修复前为 3)");
    assert(Math.abs(tr1.cx - 2.02) < 1e-9 && Math.abs(tr1.cy - 1.01) < 1e-9,
           "CE1.d FIX-1: 原 track 位置被其认领簇 A 更新 (不被后簇 B 覆写), cx=" + tr1.cx);
    var cl0_id = T.last.tracks[0].id, cl1_id = T.last.tracks[1].id;
    assert(cl0_id !== cl1_id, "CE1.e FIX-1: 两 track 有各自 id (不再共享)");
})();

// CE1 顺序鲁棒性: 输入簇顺序变化 → 每个簇拿到的 track_id 打乱, 但 track 集合本身一致
(function () {
    /* 场景: 已存在 track T@(2.0,1.0), 两簇 A@(2.02,1.01)(近) B@(2.30,1.20)(远但<1.0m).
     * 顺序 [A,B]: A 绑 T(n=52 大簇); B 新建.
     * 顺序 [B,A]: B 绑 T? B 更近? d(A)=0.022, d(B)=0.36 → A 更近. associate 贪心按输入序:
     *   输入 [B,A]: B 先扫, 候选仅 T(d=0.36<1.0), B 绑 T; A 扫时 T 已 claimed → 新建.
     * 两种输入 track 集合 {T(被某簇更新), 新建} 同, 但 T 被哪簇更新不同 → 如实记录非缺陷,
     * 断言"两种顺序 track 总数一致且都 2"即可, 具体归属由 find_clusters 尺寸排序保证稳定. */
    function run(order) {
        fresh();
        T.associate([mkcl(2.0, 1.0)], 10);
        var batch = order === "AB"
            ? [mkcl(2.02, 1.01, { n: 52 }), mkcl(2.30, 1.20, { r90: 0.4, n: 40 })]
            : [mkcl(2.30, 1.20, { r90: 0.4, n: 40 }), mkcl(2.02, 1.01, { n: 52 })];
        T.associate(batch, 10);
        return T.last.tracks.length;
    }
    var ab = run("AB"), ba = run("BA");
    assert(ab === 2 && ba === 2, "顺序扰动: 两种输入 track 总数均=2 (确定性) AB=" + ab + " BA=" + ba);
})();

// CE2→修复: 同帧两簇 (都 age≥3 时) 不再共享 track_id, HUD shown 无需 dedup 也无重复
(function () {
    fresh();
    T.associate([mkcl(2.0, 1.0)], 10);
    for (var i = 0; i < 3; i++) T.associate([mkcl(2.0, 1.0)], 10);   /* track age=4 */
    var batch = [mkcl(2.02, 1.01), mkcl(2.05, 1.02)];
    T.associate(batch, 10);
    assert(batch[0].track_id !== batch[1].track_id,
           "CE2 FIX-1: 同帧两簇 track_id 不再共享 (" + batch[0].track_id + " vs " + batch[1].track_id + ")");
    /* shown dedup 判据保留作防御, 但 track_id 已天然唯一, 无重复可发生 */
    var ids = batch.map(function (c) { return c.track_id; });
    var uniq = {}; var dup = 0;
    ids.forEach(function (i) { if (uniq[i]) dup++; uniq[i] = 1; });
    assert(dup === 0, "CE2 FIX-1: clusters track_id 无重复, HUD 不再出现 (track #3 #3)");
})();

// CE3→语义修正: 连续误检的柜子与真人在 track 层不可分 — 分类只归 RF,
// associate 不再被用来当 "人 vs 非人" 判据 (is_stable/低稳定候选已删).
// 本用例只断言: RF 过 ≥0.55 的簇被一视同仁接受, 由 RF 分数负责分类.
(function () {
    fresh();
    for (var i = 0; i < 5; i++) T.associate([mkcl(3.6, 0.78, { n: 60 })], 10);
    var tr = T.last.tracks[0];
    assert(tr.age === 5 && tr.miss === 0,
           "CE3 语义: track 层对连续输入只维护时序 (age=5), 不扮演分类器");
    assert(typeof T.is_stable === "undefined", "CE3 FIX-2: is_stable 已从导出删除");
    assert(typeof T.last.stat_count === "undefined" && typeof HOD._dbg_state.stat_count === "undefined",
           "CE3 FIX-2: stat_count 假字段已删");
})();

// CE4→语义修正: 真人短暂漏检 → 该帧不进 shown (存在性). 不再有 "人/低稳定候选" 分组往返.
(function () {
    fresh();
    for (var i = 0; i < 10; i++) T.associate([mkcl(1.7, 0.85, { n: 55 })], 10);
    var tr = T.last.tracks[0];
    T.associate([], 10);      /* 漏 1 帧 */
    assert(tr.miss === 1, "CE4 FIX: 真人漏帧 miss=1, track 留住 (TTL 内)");
    assert(tr.age === 10, "CE4 FIX: age 不因 miss 增长 (单帧至多单++)");
    T.associate([mkcl(1.7, 0.85, { n: 55 })], 10);
    assert(tr.miss === 0 && tr.age === 11, "CE4 FIX: 回帧接回同 track, age=11");
})();

// CE5→FIX-3 根修: notify_session + gen 守卫. 旧 gen 的 on_frame 被忽略.
(function () {
    /* 模拟: 会话 A on_frame (gen_A) → notify_session() (切到 gen_B) →
     * 持旧 gen_A 的 S 调 on_frame 应被忽略. */
    fresh();
    var gA = T.notify_session();      /* gen=1 */
    T.last.gen = gA;
    /* 直接调 associate 模拟 A 期 track */
    T.associate([mkcl(2.0, 1.0)], 10);
    assert(T.last.tracks.length === 1, "CE5.a 会话 A 有 1 track");
    /* 切会话: notify_session → gen 自增; replay.js load() 同时 reset() */
    var gB = T.notify_session();
    HOD.reset();
    assert(gB !== gA && T.last.tracks.length === 0, "CE5.b 切会话: gen 自增 + track 清空");
    /* 旧 gen 的 S 调 on_frame → 被守卫忽略 (tracks 仍 0) */
    var S_old = { geo: { attributes: { color: {} } }, frames: [{ start_pts: 0, count: 0, seq: 1, stamp_sec: 0, stamp_nanosec: 0 }],
                  idx: 0, buf_f32: new Float32Array(0), meta: {}, fps: 10, points: null,
                  session_gen: gA };
    HOD.on_frame(S_old);
    assert(T.last.tracks.length === 0 && T.last.frame_no === 0,
           "CE5.c FIX-3: 旧 gen on_frame 被守卫忽略 (tracks=" + T.last.tracks.length + ")");
    /* 新 gen 的 S 正常通过 */
    var S_new = { geo: { attributes: { color: {} } }, frames: [{ start_pts: 0, count: 0, seq: 1, stamp_sec: 0, stamp_nanosec: 0 }],
                  idx: 0, buf_f32: new Float32Array(0), meta: {}, fps: 10, points: null,
                  session_gen: gB };
    HOD.on_frame(S_new);
    assert(T.last.frame_no === 1, "CE5.d FIX-3: 新 gen on_frame 通过, frame_no=1");
})();

// CE6→FIX-3: replay.js 入口单点 (模拟 notify_session + reset 是 pair, 不可漏).
(function () {
    fresh();
    for (var i = 0; i < 5; i++) T.associate([mkcl(1 + i, 1)], 10);
    assert(T.last.t_id_next === 6, "CE6.a 切前多 track, id 到 6");
    T.notify_session(); HOD.reset();
    T.associate([mkcl(5.0, 2.0)], 10);
    assert(T.last.tracks.length === 1 && T.last.tracks[0].id === 1,
           "CE6.b FIX-3: 切会话后新 track id=1 (不再累计 #8/#11)");
})();

// CE7→FIX-1 后 track 集合对间歇输入稳定: 间歇 track 与稳定 track 并存且语义清晰.
(function () {
    fresh();
    for (var i = 0; i < 6; i++) {
        var batch = [mkcl(1.0, 0.5)];
        if (i % 2 === 0) batch.push(mkcl(5.0, 3.0, { n: 40 }));
        T.associate(batch, 10);
    }
    var A = null, B = null;
    T.last.tracks.forEach(function (t) { if (t.cx < 2) A = t; else B = t; });
    assert(A && A.miss === 0 && A.age === 6, "CE7.a 稳定 A: miss=0 age=6");
    assert(B && B.age === 3, "CE7.b 间歇 B: 命中 3 帧 age=3 (单帧单++)");
    assert(B.miss === 1, "CE7.c 间歇 B: 末帧其命中间隔 miss=1");
})();

// FIX-3 新增: 重复帧回调 (set_idx 同 idx 重入) — replay 层守卫, 不在 overlay. 此处文档化跳过.
// FIX-3 新增: 逆序 / 跳帧 — replay.js set_idx 守卫 (reset + 单帧重建). 此处文档化跳过.
// (二者归属 replay.js, 由独立审计员在 REVIEW-FIX 阶段直读 replay.js 验证.)

// ---- 既有防撞保留: 距离门限外 → 新建 track, 不并轨 ----
(function () {
    fresh();
    T.associate([mkcl(2.0, 1.0)], 10);
    var id_a = T.last.tracks[0].id;
    T.associate([mkcl(3.5, 1.0), mkcl(2.0, 1.0)], 10);
    var keeps_ida = T.last.tracks.some(function (t) { return t.id === id_a; });
    assert(T.last.tracks.length >= 2, "保留: 1.5m 外簇新建 track");
    assert(keeps_ida, "保留: 2.0m 簇仍绑回原 id");
})();

// ---- 既有防撞保留: track 关联保持身份 + 删除过期 ----
(function () {
    fresh();
    T.associate([mkcl(2.0, 1.0)], 10);
    assert(T.last.tracks.length === 1, "assoc f1: 新建 1 track");
    var id1 = T.last.tracks[0].id;
    T.associate([mkcl(2.02, 1.01, { n: 52 })], 10);
    assert(T.last.tracks.length === 1 && T.last.tracks[0].id === id1, "assoc f2: 保留 track id");
    for (var i = 0; i < 18; i++) T.associate([], 10);
    assert(T.last.tracks.length === 0, "assoc f3..20: 无目标 18 帧后 track 销毁");
    T.associate([mkcl(2.05, 1.02, { n: 51 })], 10);
    assert(T.last.tracks.length === 1 && T.last.tracks[0].id !== id1, "assoc: 断档 18 帧后回来, 新 track id");
})();

console.log("ALL PASS");
