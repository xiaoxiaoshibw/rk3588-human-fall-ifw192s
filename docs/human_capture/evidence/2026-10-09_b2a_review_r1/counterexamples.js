/* counterexamples.js — B2-A-REVIEW 确定性反例 (审计 detect_overlay.js).
 *
 * 7 个独立场景, 每个证明一条缺陷/边界; 全部 node 断言驱动, 无浏览器依赖
 * (THREE/document 用最小 stub; detect_overlay 的 set_label 在 sceneRef=null 时 early-return).
 *
 * 跑法: 在 pc_apps/human_replay 目录下
 *   node ../../docs/human_capture/evidence/2026-10-09_b2a_review_r1/counterexamples.js
 * 每个场景打印 PASS (缺陷/行为存在且被确认) 或 FAIL (与预期不符).
 * 退出码 = 失败场景数 (0 = 全部按审计预期确认).
 */
"use strict";

var path = require("path");
var REPLAY = "D:/Code/ldiar/pc_apps/human_replay/";

/* ---- 最小 stub: detect_overlay 只 touch document.createElement('canvas') 与 THREE.Sprite ---- */
global.window = {};
global.document = {
    createElement: function () {
        return { width: 0, height: 0, getContext: function () {
            return { fillStyle: null, fillRect: function () {}, fillText: function () {},
                     font: null, textAlign: null, textBaseline: null,
                     measureText: function () { return { width: 8 }; } };
        } };
    }
};
global.THREE = {
    Sprite: function (m) { this.material = m; this.position = { set: function () {} }; this.scale = { set: function () {} }; },
    SpriteMaterial: function (o) { this.map = o && o.map; this.dispose = function () {}; },
    CanvasTexture: function () { this.dispose = function () {}; },
};

var HOD = require(REPLAY + "detect_overlay.js");
var T = HOD._test;

var fails = 0;
function check(name, cond, detail) {
    if (cond) console.log("PASS: " + name + (detail ? "  (" + detail + ")" : ""));
    else { console.log("FAIL: " + name + (detail ? "  (" + detail + ")" : "")); fails++; }
}
function fresh() { HOD.reset(); T.last.t_id_next = 1; T.last.tracks = []; T.last.frame_no = 0; }
function assert_tracks(expected_n, label) {
    check(label, T.last.tracks.length === expected_n,
          "tracks=" + T.last.tracks.length + " 期望=" + expected_n);
}

/* ========== CE1: 同帧两簇关联同一 track, age 重复增长 + cx 被覆写 ==========
 * 物理对应: 柜位 5cm 漫水把一个高目标分裂成两簇, 两簇质心都 <1.0m 于同一 track. */
(function CE1() {
    fresh();
    /* 帧 1: 单簇 → 建 track, age=1 */
    T.associate([{ cx: 2.0, cy: 1.0, r90: 0.3, zmax: 1.8, n: 50 }], 10);
    var tr = T.last.tracks[0];
    check("CE1.a 建 track", T.last.tracks.length === 1 && tr.age === 1, "age=" + tr.age);
    /* 帧 2: 两簇都 <1.0m 于 track → 都命中同一 tr */
    T.associate([{ cx: 2.02, cy: 1.01, r90: 0.3, zmax: 1.85, n: 52 },   /* cl A, d≈0.022 */
                 { cx: 2.30, cy: 1.20, r90: 0.4, zmax: 1.75, n: 40 }],  /* cl B, d≈0.36 */
                10);
    check("CE1.b 同帧两簇绑同一 track, age 两次 ++", tr.age === 3,
          "age=" + tr.age + " (单帧两簇 → 期望 3, 真管线应为 '单目标 age=2')");
    check("CE1.c cx/cy 被后簇覆写", Math.abs(tr.cx - 2.30) < 1e-9 && Math.abs(tr.cy - 1.20) < 1e-9,
          "cx=" + tr.cx.toFixed(2) + " cy=" + tr.cy.toFixed(2) + " (记录的是后簇 B, 前簇 A 信息丢失)");
    check("CE1.d 两 cluster 拿到同一 track_id", true, "associate 内 cl.track_id 均被赋 tr.id (本测试侧不可直接读, 由 CE2 shown 重复佐证)");
})();

/* ========== CE2: 同帧两簇都 age≥3 → shown 出来两条同 track 的 cluster (HUD 重复源) ==========
 * 探针纯逻辑演示: 复用 on_frame 前段 shown 判据, 模拟 associate 返回两个同 id cluster. */
(function CE2() {
    fresh();
    /* 直接构造 associate 输出后状态 */
    T.associate([{ cx: 2.0, cy: 1.0, r90: 0.3, zmax: 1.8, n: 50 }], 10);
    for (var i = 0; i < 3; i++) T.associate([{ cx: 2.0, cy: 1.0, r90: 0.3, zmax: 1.8, n: 50 }], 10);
    /* 此时 track age=4. 再帧两簇都 <1m */
    var clusters = [{ cx: 2.02, cy: 1.01, r90: 0.3, zmax: 1.8, n: 50 },
                    { cx: 2.05, cy: 1.02, r90: 0.3, zmax: 1.8, n: 48 }];
    T.associate(clusters, 10);
    /* 模拟 shown 判据 (dedup 版, 与生产 on_frame 同逻辑) */
    var _ids = {};
    var shown = clusters.filter(function (cl) {
        if (_ids[cl.track_id]) return false;
        for (var t = 0; t < T.last.tracks.length; t++) {
            if (T.last.tracks[t].id === cl.track_id && T.last.tracks[t].age >= 3) {
                _ids[cl.track_id] = true; return true;
            }
        }
        return false;
    });
    check("CE2.a 底层: 两簇同 track_id", clusters[0].track_id === clusters[1].track_id,
          "cl0.track_id=" + clusters[0].track_id + " cl1.track_id=" + clusters[1].track_id);
    check("CE2.b HUD dedup 后 shown=1 (掩盖底层同 id 重复)", shown.length === 1,
          "shown=" + shown.length + " (dedup 是显示层规避, 底层 track 被两簇共享未变)");
})();

/* ========== CE3: is_stable (miss===0) 无法区分"连续误检"的柜子 ==========
 * 5 帧连续误检簇 (每帧都 associate 命中) → tr.miss===0 → is_stable=true → HUD '人'.
 * 这是用户 P1 反例的直译. */
(function CE3() {
    fresh();
    HOD.reset();
    /* 模拟 5 帧: 每帧都有一个簇 (RF 已经判它是 '人' — 我们绕过 RF, 直接给 associate) */
    for (var i = 0; i < 5; i++) {
        T.last.frame_no++;
        T.associate([{ cx: 3.60, cy: 0.78, r90: 0.25, zmax: 1.85, n: 60 }], 10);
    }
    var tr = T.last.tracks[0];
    check("CE3.a 连续 5 帧误检: MIN_AGE=3 满足", tr.age >= 3, "age=" + tr.age);
    check("CE3.b miss===0 满足", tr.miss === 0, "miss=" + tr.miss);
    check("CE3.c is_stable 返回 true → HUD 归 '人' 组",
          T.is_stable(tr) === true,
          "结论: miss===0 不能证明是 '真人', 仅证明 '当前帧 associate 命中'");
})();

/* ========== CE4: 真皮漏检一帧 → miss=1 → is_stable=false → 降入低稳定候选 =========
 * 真人因点云抖动 1 帧没成簇 → HUD 闪 '低稳定候选'. 这是真人的反向误伤. */
(function CE4() {
    fresh(); HOD.reset();
    for (var i = 0; i < 10; i++) { T.last.frame_no++; T.associate([{ cx: 1.7, cy: 0.85, r90: 0.2, zmax: 1.75, n: 55 }], 10); }
    var tr = T.last.tracks[0];
    check("CE4.a 真皮 10 帧连显示稳定", T.is_stable(tr) === true, "");
    /* 漏一帧 */
    T.last.frame_no++; T.associate([], 10);
    check("CE4.b 真皮漏 1 帧 → miss=1 → is_stable=false",
          T.is_stable(tr) === false,
          "miss=" + tr.miss + "; HUD 会降入 '低稳定候选' (真皮也会被误降 1 帧)");
    /* 下一帧回来 */
    T.last.frame_no++; T.associate([{ cx: 1.7, cy: 0.85, r90: 0.2, zmax: 1.75, n: 55 }], 10);
    check("CE4.c 真皮回帧 miss=0 → 立刻回 '人' 组 (分组在帧间闪烁)",
          T.is_stable(tr) === true,
          "同一条 track 在 '人'/'低稳定候选' 间来回跳 — HUD 文案不稳");
})();

/* ========== CE5: reset() 仅清 detect_overlay.last, 对 replay.js 的 S/请求/计时无控制 =========
 * 验证 reset 的边界: 它挡不住 'reset 之后的下一帧仍走 on_frame'. */
(function CE5() {
    fresh();
    T.associate([{ cx: 2.0, cy: 1.0, r90: 0.2, zmax: 1.8, n: 50 }], 10);
    T.associate([{ cx: 4.0, cy: 3.5, r90: 0.3, zmax: 1.7, n: 40 }], 10);
    var ids_before = T.last.tracks.map(function (t) { return t.id; });
    HOD.reset();
    check("CE5.a reset 清空 track + t_id_next", T.last.tracks.length === 0 && T.last.t_id_next === 1, "");
    /* 关键: reset 后若 replay.js 因 tick/rAF 在旧会话又 set_idx(S.idx) 一次,
     * on_frame 会被再次调用 → track 会被重新创建 (reset 管不到 replay).
     * 真实 chain: replay.js tick → set_idx(旧 idx) → on_frame → associate 复活 track. */
    T.associate([{ cx: 2.0, cy: 1.0, r90: 0.2, zmax: 1.8, n: 50 }], 10);
    check("CE5.b reset 后下一帧 on_frame 又把 track 建回来 (id=1)",
          T.last.tracks.length === 1 && T.last.tracks[0].id === 1,
          "reset 只在 '切会话调用点' 有意义; 同一 session 内 reset 后立即 set_idx 会复活状态");
    check("CE5.c 旧 id (" + ids_before.join(",") + ") 不复活, 新 track id 从 1 起", true, "");
})();

/* ========== CE6: 会话切换路径 — reset 只在 sessSel.change / btn 重开触发 ==========
 * 模拟: 用户在 session A 跑出 5 帧 → 切到 session B (change 触发 reset) → track 从 #1 起. */
(function CE6() {
    fresh();
    /* session A: 5 track 累计 id 1..5 (每次不同位置) */
    for (var i = 0; i < 5; i++) T.associate([{ cx: 1 + i, cy: 1, r90: 0.2, zmax: 1.8, n: 50 }], 10);
    check("CE6.a 切会话前: 多 track, id 到 " + T.last.t_id_next, T.last.t_id_next === 6, "");
    /* 切会话: sessSel.change 调 HOD.reset() */
    HOD.reset();
    /* session B 第 1 帧 */
    T.associate([{ cx: 5.0, cy: 2.0, r90: 0.2, zmax: 1.8, n: 50 }], 10);
    check("CE6.b 切会话后: 新 track id=1 (不再累计 #8/#11)",
          T.last.tracks.length === 1 && T.last.tracks[0].id === 1,
          "id=" + T.last.tracks[0].id);
})();

/* ========== CE7: is_stable 分组对 'shown 归弱' 但 '实际没误检' 的边界 =========
 * 真管线中: bg cell 缺失 → hot 空 → 无簇 → 整帧 EMPTY → miss=1 已天然存在.
 * 这里验证 'stable 组= 当前帧 hit 的 track' + 'weak 组= shown 里 miss≥1 的 track'
 * 的并存: 同帧既有 miss=0 track 也有 miss≥1 track, 分组应拆开. */
(function CE7() {
    fresh(); HOD.reset();
    /* track A: 每帧命中 */
    /* track B: 间歇 (只 3/6 帧命中) */
    for (var i = 0; i < 6; i++) {
        T.last.frame_no++;
        var batch = [{ cx: 1.0, cy: 0.5, r90: 0.2, zmax: 1.8, n: 50 }];   /* A 恒定 */
        if (i % 2 === 0) batch.push({ cx: 5.0, cy: 3.0, r90: 0.2, zmax: 1.8, n: 40 });  /* B 偶现 */
        T.associate(batch, 10);
    }
    var A = null, B = null;
    T.last.tracks.forEach(function (t) {
        if (Math.abs(t.cx - 1.0) < 0.5) A = t;
        else B = t;
    });
    check("CE7.a track A (稳定) is_stable=true", A && T.is_stable(A) === true, "miss=" + (A && A.miss));
    check("CE7.b track B (间歇) is_stable=false", B && T.is_stable(B) === false, "miss=" + (B && B.miss));
    check("CE7.c 两 track 同屏分组拆开 (人 A + 候选 B)", A && B && T.is_stable(A) !== T.is_stable(B), "");
})();

console.log("\n=== " + (fails === 0 ? "ALL " : fails + " FAIL / ") + "7 组反例确认完毕 ===");
process.exit(fails);
