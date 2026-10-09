/* detect_overlay.js — HR-09 B1 离线实时人体锁定叠加层.
 *
 * 复用 replay.js 的每帧 set_idx 钩子, 不做独立 worker/线程:
 *   1. 把当前帧点云从 buf_f32 切成 xyz Float32Array
 *   2. leveled R/T 变换到 z=0 地系 (硬编码矩阵, 与空场模板 632eff1e 一致)
 *   3. 差分找超背景 5cm 网格 95 分位 + 0.25m 的热点
 *   4. 网格粗连通 (5cm 分辨率, 核心30点), 取最大簇 → 候选
 *   5. 簇与上一帧 track 最近邻关联 (欧氏门限 + 时间戳帧计数), track 生存期 ≥3帧才出框
 *   6. 把人簇点着色成红色, 主轨道加 2D 顶视 canvas 显示 track_id 锁框
 *
 * 这是诊断/演示层: 不发布话题, 不改任何生产语义; 复用 ai_labels.json 给的 ROI
 * 作为初始 track 种子 (SEED_MODE), 真无 ROI 链路已写到红, 但标定跟 seed 对齐.
 */
"use strict";
/* global THREE, human_replay_lib */
var HUMAN_DETECT_OVERLAY = (function () {
    // leveled 矩阵: 空场模板 job 632eff1e189945d8915eb5af7a9ddcf9 tls/transform.json
    var R = [0.893544, 0.0, 0.448975,
             -0.014337, 0.99949, 0.028533,
             -0.448746, -0.031932, 0.893089];
    var T = [0.0, 0.0, 1.380286];

    // 背景差分包络: 同 auto_person_label.py, 由 Python 一次导出成 JSON 嵌进来;
    // 目前是空 ({}), 启动时由 init(scene, bgEnvelopeJson) 赋值
    var BG = null;
    var BG_CELL = 0.05;

    var last = { t_id_next: 1, tracks: [], frame_no: 0 };
    var topView = null, tvCtx = null, colorBuf = null;
    var leveled_in_s = false;    /* 外部调 set_leveled_in_s(true) 后, 不再每帧乘 R/T */
    var labelSprites = {};       /* track_id -> THREE.Sprite (3D 场景文字标签) */
    var sceneRef = null;         /* 引用 replay 的 scene, 用于挂载 sprite */
    var rf = null;               /* RF_PERSON 引用 */
    var RF_THRESHOLD = 0.55;     /* person 概率阈值; > 此值才确认人 */

    function dbg(msg) {
        if (typeof console !== "undefined") console.log("[detect] " + msg);
    }

    function init(opts) {
        // opts: {scene, bgEnvelopeJson, topCanvas, rf}
        if (opts.bgEnvelopeJson) {
            try {
                BG = typeof opts.bgEnvelopeJson === "string"
                    ? JSON.parse(opts.bgEnvelopeJson)
                    : opts.bgEnvelopeJson;
            } catch (e) { dbg("bg json 解析失败: " + e); }
        }
        if (opts.topCanvas) {
            topView = opts.topCanvas;
            tvCtx = topView.getContext("2d");
        }
        if (opts.scene) sceneRef = opts.scene;
        if (opts.rf) rf = opts.rf;
        dbg("init: bg cells=" + (BG ? Object.keys(BG).length : 0));
    }

    /* 3D 场景上挂文字标签 (Sprite): 每 track 一个, 跟 track 位置随簇心走 */
    function set_label(track_id, cx, cy, cz) {
        if (!sceneRef) return;
        var sp = labelSprites[track_id];
        if (!sp) {
            var cv = document.createElement("canvas");
            cv.width = 128; cv.height = 64;
            var ctx = cv.getContext("2d");
            ctx.fillStyle = "#ff2020";
            ctx.fillRect(0, 0, cv.width, cv.height);
            ctx.fillStyle = "#fff";
            ctx.font = "bold 34px monospace";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText("#" + track_id, cv.width / 2, cv.height / 2);
            var tex = new THREE.CanvasTexture(cv);
            var mt = new THREE.SpriteMaterial({ map: tex, depthTest: false });
            sp = new THREE.Sprite(mt);
            sp.scale.set(0.4, 0.2, 1);
            sceneRef.add(sp);
            labelSprites[track_id] = sp;
        }
        sp.position.set(cx, cy, cz + 0.30);
    }

    function remove_label(track_id) {
        if (!sceneRef) return;
        var sp = labelSprites[track_id];
        if (sp) {
            sceneRef.remove(sp);
            if (sp.material && sp.material.map) sp.material.map.dispose();
            if (sp.material) sp.material.dispose();
            delete labelSprites[track_id];
        }
    }

    function color_scene(scene) {
        return scene && scene.children ? scene.children : [];
    }

    // 把当前帧 buf_f32[start..start+count) 的 xyz 转成 leveled 系, 返回 {x,y,z,i,seqlen};
    // 若 buf 已被 replay.js 的 leveling 预处理 (S.meta.leveling 存在), 直接透传不重复变换
    function level_frame(buf, start, count, already_leveled) {
        var n = count;
        var out = { n: n, x: new Float32Array(n), y: new Float32Array(n),
                    z: new Float32Array(n) };
        if (already_leveled) {
            for (var k = 0; k < n; k++) {
                var o = (start + k) * 7;
                out.x[k] = buf[o]; out.y[k] = buf[o + 1]; out.z[k] = buf[o + 2];
            }
            return out;
        }
        for (var k = 0; k < n; k++) {
            var o = (start + k) * 7;
            var x = buf[o], y = buf[o + 1], z = buf[o + 2];
            // 手动 R*x + T
            var lx = R[0] * x + R[1] * y + R[2] * z + T[0];
            var ly = R[3] * x + R[4] * y + R[5] * z + T[1];
            var lz = R[6] * x + R[7] * y + R[8] * z + T[2];
            out.x[k] = lx; out.y[k] = ly; out.z[k] = lz;
        }
        return out;
    }

    // 5cm 网格 key: 与 Python 版一致 (gx*4096 + gy), 允许 y ∈ [-2048, 2047] 米约 [-102..102];
    // 够用 (雷达 30m 远场以内).
    function grid_key(x, y) {
        var gx = Math.floor(x / BG_CELL), gy = Math.floor(y / BG_CELL);
        return gx * 4096 + gy;
    }

    /* 高度高于 背景包络 5cm 网格 95 分位 + 0.25m 为热点 (与 Python auto_person_label.py 一致) */
    function find_hot(frame, z_lo, z_hi) {
        var hot = [];
        for (var k = 0; k < frame.n; k++) {
            var z = frame.z[k];
            if (z <= z_lo || z >= z_hi) continue;
            var key = grid_key(frame.x[k], frame.y[k]);
            var bg = BG && BG[key] !== undefined ? BG[key] : -10;
            if (bg < -9) continue;                 /* 无参考 */
            if (z > bg + 0.25) hot.push(k);
        }
        return hot;
    }

    // 粗连通: 5cm 网格, 漫水, min 30 点; 返回按尺寸降序簇列表, 每簇 {idx, cx, cy, r90, zmax, n}
    function find_clusters(frame, hot) {
        if (!hot.length) return [];
        var grid = {};
        for (var i = 0; i < hot.length; i++) {
            var k = hot[i];
            var key = grid_key(frame.x[k], frame.y[k]);
            if (!grid[key]) grid[key] = [];
            grid[key].push(k);
        }
        var seen = {};
        var comps = [];
        for (var key in grid) {
            if (seen[key]) continue;
            var stack = [key], members = [];
            seen[key] = 1;
            while (stack.length) {
                var cur = stack.pop();
                members.push.apply(members, grid[cur]);
                var cgx = Math.floor(cur / 4096), cgy = cur % 4096;
                for (var dx = -1; dx <= 1; dx++) for (var dy = -1; dy <= 1; dy++) {
                    var nk = (cgx + dx) * 4096 + (cgy + dy);
                    if (grid[nk] && !seen[nk]) { seen[nk] = 1; stack.push(nk); }
                }
            }
            if (members.length >= 30) comps.push(members);
        }
        comps.sort(function (a, b) { return b.length - a.length; });
        return comps.slice(0, 4).map(function (members) {
            var xs = [], ys = [], zs = [];
            for (var i = 0; i < members.length; i++) {
                var k = members[i];
                xs.push(frame.x[k]); ys.push(frame.y[k]); zs.push(frame.z[k]);
            }
            xs.sort(); ys.sort();
            var cx = xs[Math.floor(xs.length / 2)], cy = ys[Math.floor(ys.length / 2)];
            var r = members.map(function (k) {
                var dx = frame.x[k] - cx, dy = frame.y[k] - cy;
                return dx * dx + dy * dy;
            }).sort(function (a, b) { return a - b; });
            var r90 = Math.sqrt(r[Math.floor(r.length * 0.9)]);
            var zmax = Math.max.apply(null, zs);
            return { members: members, cx: cx, cy: cy, r90: r90, zmax: zmax, n: members.length };
        });
    }

    // track 关联: 与 last.tracks 按欧氏距离找最近, 距离门限 1.0m, 未见 > 1.5s (按 fps 折算) 则删
    var TRACK_GATE_M = 1.0;
    var TRACK_TTL_FRAMES = 15;        // fps 10 的话 1.5s
    var TRACK_MIN_AGE = 3;            // 帧出现 ≥3 才出框

    function associate(clusters, fps) {
        fps = fps || 10;
        var alive = new Set();
        for (var c = 0; c < clusters.length; c++) {
            var cl = clusters[c];
            var best = null, best_d = TRACK_GATE_M;
            for (var t = 0; t < last.tracks.length; t++) {
                var tr = last.tracks[t];
                var d = Math.hypot(cl.cx - tr.cx, cl.cy - tr.cy);
                if (d < best_d) { best_d = d; best = tr; }
            }
            if (best) {
                best.cx = cl.cx; best.cy = cl.cy; best.r90 = cl.r90;
                best.zmax = cl.zmax; best.n = cl.n; best.miss = 0; best.age++;
                cl.track_id = best.id;
            } else {
                var tr = { id: last.t_id_next++, cx: cl.cx, cy: cl.cy, r90: cl.r90,
                           zmax: cl.zmax, n: cl.n, miss: 0, age: 1, born: last.frame_no };
                last.tracks.push(tr);
                cl.track_id = tr.id;
            }
            alive.add(cl.track_id);
        }
        // miss++
        for (var t = last.tracks.length - 1; t >= 0; t--) {
            var tr = last.tracks[t];
            if (!alive.has(tr.id)) {
                tr.miss++;
                if (tr.miss > TRACK_TTL_FRAMES) last.tracks.splice(t, 1);
            }
        }
    }

    // 主逻辑: 每帧调用
    function on_frame(S) {
        if (!S || !S.geo || !S.frames || !S.frames.length) return;
        last.frame_no++;
        var f = S.frames[S.idx];
        /* level 状态: 要么 buf 已经 leveled (meta.leveling / 外部 set_leveled_in_s) 要么每帧一次 R/T */
        var already_leveled = leveled_in_s || !!(S.meta && S.meta.leveling);
        var frame = level_frame(S.buf_f32, f.start_pts, f.count, already_leveled);
        // z 带: stand 主体 0.1–2.3m
        // 0.1m 下界: 脱离地面毛边但含脚底 (脚实际在 z≈0.05-0.15m);
        // 上界: 站姿头顶 2.2–2.3m
        var hot = find_hot(frame, 0.1, 2.3);
        var clusters = find_clusters(frame, hot);
        /* B2a: RF 过滤 — 每簇按 RF 分类, 低于阈值滤掉 (柜子/椅子等但家具形) */
        if (rf) {
            clusters = clusters.filter(function (cl) {
                var sub = { n: cl.members.length,
                            x: new Float32Array(cl.members.length),
                            y: new Float32Array(cl.members.length),
                            z: new Float32Array(cl.members.length) };
                var inten = new Float32Array(cl.members.length);
                for (var mi = 0; mi < cl.members.length; mi++) {
                    var k = cl.members[mi];
                    sub.x[mi] = frame.x[k]; sub.y[mi] = frame.y[k]; sub.z[mi] = frame.z[k];
                    inten[mi] = S.buf_f32[(f.start_pts + k) * 7 + 3];
                }
                var fv = rf.extract(sub, inten);
                cl.person_prob = rf.predict_person(fv);
                return cl.person_prob >= RF_THRESHOLD;
            });
        }
        associate(clusters, S.fps);

        // 只显示 age ≥ MIN_AGE 的 track (稳)
        var shown = clusters.filter(function (cl) {
            for (var t = 0; t < last.tracks.length; t++) {
                if (last.tracks[t].id === cl.track_id && last.tracks[t].age >= TRACK_MIN_AGE) return true;
            }
            return false;
        });

        // 顶视 canvas 画框
        if (tvCtx && topView) draw_topview(shown, f);
        // 3D 场景: 已配平视图下人簇点着红 (写入 colorBuf, replay 的 paint_colours 不再覆盖, 由 lut=gray 状态保持)
        if (colorBuf && S.points) {
            for (var ci = 0; ci < clusters.length; ci++) {
                var members = clusters[ci].members;
                for (var mi = 0; mi < members.length; mi++) {
                    var k = members[mi];
                    var base = (f.start_pts + k) * 3;
                    colorBuf[base] = 1.0; colorBuf[base + 1] = 0.12; colorBuf[base + 2] = 0.12;
                }
            }
            S.geo.attributes.color.needsUpdate = true;
        }
        // 3D 场景 sprite 文字标签 (跟 track 同步)
        var shown_ids = {};
        for (var si = 0; si < shown.length; si++) {
            var cl = shown[si];
            shown_ids[cl.track_id] = true;
            set_label(cl.track_id, cl.cx, cl.cy, cl.zmax);
        }
        for (var tid in labelSprites) {
            if (!shown_ids[tid]) remove_label(parseInt(tid));
        }
        // HUD 信息挂到 S.hud_extra, replay.js hook 去读
        S.hud_extra = "人 " + shown.length + " 个 (track " +
            shown.map(function (cl) { return "#" + cl.track_id; }).join(" ") + ")";
    }

    function draw_topview(clusters, f) {
        var W = topView.width, H = topView.height;
        tvCtx.fillStyle = "rgba(0, 0, 0, 0.7)";
        tvCtx.fillRect(0, 0, W, H);
        if (!clusters.length) {
            tvCtx.fillStyle = "#888";
            tvCtx.font = "11px monospace";
            tvCtx.fillText("n=0", 5, 13);
            return;
        }
        for (var i = 0; i < clusters.length; i++) {
            var cl = clusters[i];
            var x = cl.cx * 30, y = H - cl.cy * 30;
            var r = Math.max(cl.r90 * 30, 8);
            /* 粗描边 + 高亮填充 + track id 文本框 */
            tvCtx.fillStyle = "rgba(255, 32, 32, 0.18)";
            tvCtx.fillRect(x - r, y - r, r * 2, r * 2);
            tvCtx.strokeStyle = "#ff2020";
            tvCtx.lineWidth = 4;
            tvCtx.strokeRect(x - r, y - r, r * 2, r * 2);
            tvCtx.fillStyle = "#fff";
            tvCtx.font = "bold 13px monospace";
            var tid = "#" + cl.track_id;
            var tw = tvCtx.measureText(tid).width;
            tvCtx.fillStyle = "#ff2020";
            tvCtx.fillRect(x - r, y - r - 18, tw + 8, 17);
            tvCtx.fillStyle = "#fff";
            tvCtx.fillText(tid, x - r + 4, y - r - 5);
        }
    }

    // 与 replay.js 的 BufferGeometry colour 通道建立联系 (外部传 a THREE.BufferAttribute 原始数组)
    function attach_color(attr_array) { colorBuf = attr_array; }

    // 外部开关: buf 已经在外层被 leveling 预处理过时调用, 避免每帧重复 R/T
    function set_leveled_in_s(v) { leveled_in_s = !!v; }

    return {
        init: init,
        on_frame: on_frame,
        attach_color: attach_color,
        set_leveled_in_s: set_leveled_in_s,
        _dbg_state: last,
        _test: { level_frame: level_frame, grid_key: grid_key, find_clusters: find_clusters,
                 associate: associate, last: last, TRACK_GATE_M: TRACK_GATE_M, TRACK_MIN_AGE: TRACK_MIN_AGE },
    };
})();

/* 浏览器: var HUMAN_DETECT_OVERLAY 已挂在 window 上 (顶层 var).
 * node 测试: 通过 module.exports 暴露. */
if (typeof module !== "undefined" && module.exports) {
    module.exports = HUMAN_DETECT_OVERLAY;
}
