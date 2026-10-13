/* gt_annotator.js — HUMAN-GT-ANNOTATOR-R1 浏览器层（2D canvas 标注工作台）。
 *
 * 架构：所有可测逻辑（几何/索引/undo/传播/校验）在 gt_lib.js（node 可测）；
 * 本文件只管 画布渲染 / 鼠标键盘 / fetch 持久化 / DnD 会话切换。
 * 坐标契约：点云永远是 leveled-compact（split_frame_indices 全局一次）；
 *          屏幕坐标只由 view transform 得到，不回写点云。
 */
"use strict";
/* global gt_lib */

var GT = gt_lib; // shorthand

// ---------------- state ----------------
var S = {
    sid: null, meta: null, frames: null,
    // 整会话原始 Float32Array（[x,y,z,i,...] stride=7）— 用于展示/级别变换计算
    buf: null,
    // 全局 compact 索引映射（一次算）：leveled_xyz, raw_of_leaf, leaf_of_raw
    split: null,
    // 每帧 [start_leaf, count_leaf]（compact 空间）
    frame_compact_range: null,
    frame_compact_map: null,          // per-frame [local_index → global_compact_index]
    frame_raw_of_leaf: null,          // per-frame Int32Array local_leaf → raw 帧内 idx
    current_frame: 0,
    annotator: null,
    doc: null,                        // GT 工作 doc（make_session_doc 结构）
    objects_by_frame: {},             // frame_idx → [obj] 展示用的去 dict 衍生
    undo: null,
    view: { cx: 5, cy: 4.5, scale_px_per_m: 45, vw: 0, vh: 0, rotation: 0 },  /* rad, 逆 +y 为 +x 方向 */
    selected: null,                   // object_id
    tool: "pan",                      // pan|rect|poly|keyframe|delete
    pending_poly: [],                 // 临时圈选顶点（leveled m）
    z_min: 0.05, z_max: 2.3,
    suggestions: {},                  // frame → [cand]
    save_sha: null,
    dirty: false,
    playing: false,           /* FIX-AUDIT-Q1: 播放中标记 */
    fps: 9.55,                /* 真实会话 fps (manifest frame_rate_hz_measured) */
    play_timer: null,
    nav_dir: null,            /* +1/-1 右键连续翻帧; null=未在走 */
    nav_state: null,          /* {t_start, last_ts, frame_acc} */
    nav_raf: null,
    color: {
        PERSON: "#2ecc71", FURNITURE: "#f1c40f", BACKGROUND: "#888", UNKNOWN: "#9b59b6",
    },
    /* live 模式：从 foxglove_bridge 订阅 /innolidar_points (@9.7Hz)，stride 抽稀渲染。
     * 录制无关 — 真正的录制是板上 rosbag 全量，浏览器这边只是看。
     * active=false 时以下字段都无意义。渲染路径绕开 split/frames。 */
    live: {
        active: false,
        conn: null,             /* GT_LIVE.connect() 句柄 */
        pts: null,              /* 最近一帧紧凑 Float32Array [x,y,z,...] stride=3 */
        n: 0,                   /* 有效点数 */
        fps_received: 0,        /* 服务端到的真实接收 fps */
        seq: 0,                 /* 递增帧号（用于 fps 测窗） */
        recv_window: [],        /* 最近 5s 到达时刻 */
        stride: 4,              /* 空间均匀抽稀步长 */
        max_points: 40000,
    },
};

/* Grip mode (G): 按住左键在已存在的 ROI 附近→拖这个 ROI 平移(鼠标跟随, 不是 WASD 键控).
 * Esc / P / N / L 都退 grip。drag_target = 当前被拖的 object_id. */
var canvas, ctx, hud, side, prog;

// ---------------- transform ----------------
/* View 变换：translate(cx,cy → 屏幕中心) → rotate(rotation) → scale → 屏幕 Y 翻。
 * 计算顺序：先按 (cx,cy) 平移到原心，再按 rotation 旋,再乘 scale,最后屏幕 y 翻（下-y）。
 * 逆变换 (screen→lev) 就是反序：先翻 screen, 再 /scale, 再逆旋, 再 +cx.cy. */
function lev_to_screen(x, y) {
    var v = S.view;
    var u = x - v.cx, w = y - v.cy;
    var c = Math.cos(v.rotation), s = Math.sin(v.rotation);
    var rx = u * c - w * s;
    var ry = u * s + w * c;
    return [v.vw / 2 + rx * v.scale_px_per_m,
            v.vh / 2 - ry * v.scale_px_per_m];
}
function screen_to_lev(px, py) {
    var v = S.view;
    /* 屏幕 y 翻 + 平移 → 得 (rx, ry) 单位 px;  除 scale → 米 */
    var rx = (px - v.vw / 2) / v.scale_px_per_m;
    var ry = -(py - v.vh / 2) / v.scale_px_per_m;
    var c = Math.cos(v.rotation), s = Math.sin(v.rotation);
    /* 逆旋 */
    var u = rx * c + ry * s;
    var w = -rx * s + ry * c;
    return [v.cx + u, v.cy + w];
}
function rotate_view(d_rad) {
    S.view.rotation = (S.view.rotation + d_rad) % (Math.PI * 2);
    var deg = (S.view.rotation * 180 / Math.PI).toFixed(0);
    hud_msg("视角 " + deg + "°", false);
    if (S.live.active) _render_live_frame(); else render_frame(S.current_frame);
}
function reset_view_rotation() {
    S.view.rotation = 0;
    if (S.live.active) _render_live_frame(); else render_frame(S.current_frame);
}
function m_per_px() { return 1 / S.view.scale_px_per_m; }

// ---------------- data load ----------------
function ls_prefix() { return "gt_annotator."; }

/* R3 HUD：会话→推荐标注密度表 (工单 GT_COVERAGE_REPORT §4 权威) */
var CADENCE_HINT = {
    "cap_20261010_175227": { name: "S1 空场带家具", rule: "每 <b>20</b> 帧一个 K + I 插值",
                             note: "家具 (FURNITURE) 每件 ROI； FURN_HARD_NEG 唯一来源" },
    "cap_20261010_180557": { name: "S8 走人后静立 60s", rule: "入场 K+走向 K+静段起 K+静段止 K+离场 K (5 个 K); 静段每 <b>25</b> 帧一抽" },
    "cap_20261010_180751": { name: "S9 双人交叉", rule: "<b>逐帧 126 帧</b>; 别用 I (相对位置不平滑)",
                             note: "P1/P2 独立 track； 交叉期 visibility=partial" },
    "cap_20261010_175429": { name: "S3 走近场", rule: "逐帧 258" },
    "cap_20261010_175553": { name: "S3 走纵向往返", rule: "逐帧 464" },
    "cap_20261010_175804": { name: "S4 走停走", rule: "逐帧 239 + 停段起止" },
    "cap_20261010_175943": { name: "S5 原地转身", rule: "逐帧 202" },
    "cap_20261010_180235": { name: "S6 遮挡", rule: "逐帧 238 <b>+ 遮挡段 visibility=occluded</b>" },
    "cap_20261010_180337": { name: "S7 远 5m", rule: "逐帧 251" },
};
function refresh_cadence_hint() {
    var el = document.getElementById("cadence");
    if (!el) return;
    var c = CADENCE_HINT[S.sid];
    if (!c) { el.style.display = "none"; return; }
    el.style.display = "block";
    el.innerHTML = "<b>" + c.name + "</b>: " + c.rule + (c.note ? "<br><span style='opacity:.75'>" + c.note + "</span>" : "");
}

// ---------------- live 模式 ----------------
/* 进入实时点云渲染模式：开 WebSocket 到 foxglove_bridge，订阅 /innolidar_points,
 * stride 抽稀画到 canvas；绕开 S.split/S.frames 渲染管线（不依赖 leveling）。
 * 与录制完全解耦：此时按 rec_btn 仍触发板端 rosbag 全量录。
 * 返回 true=已启动，false=已有 live（不重复启）。 */
function enter_live() {
    if (S.live.active) return true;
    if (typeof GT_LIVE === "undefined") {
        hud_msg("gt_live.js 未加载", true); return false;
    }
    /* 退出任何会话上下文（draft未必保存，用户应先 Ctrl+S） */
    if (S.dirty && S.sid) {
        if (!confirm("当前会话有未保存修改，进入实时模式将离开会话。仍要继续吗？")) return false;
    }
    /* 清会话渲染状态（保留 S 上其它缓存）。
     * FIX-REVIEW-H2: 还要清 undo/last_edit_frame/pending_poly/tool — 否则 live 下
     * 误按 N/L/Ctrl+Z 仍走会话路径读 null 抛 TypeError。 */
    S.sid = null; S.doc = null; S.objects_by_frame = {}; S.selected = null;
    S.suggestions = {}; S.dirty = false; S.split = null; S.frames = null;
    S.buf = null; S.frame_compact_range = null;
    S.frame_compact_map = null; S.frame_raw_of_leaf = null;
    S.undo = null; S.last_edit_frame = null;
    S.pending_poly = []; S.tool = "pan";
    if (S.play_timer) { clearInterval(S.play_timer); S.play_timer = null; S.playing = false; }
    stop_nav_hold();
    /* 视角初始化：默认鸟瞰 z-down 不旋转 */
    S.view = { cx: 0, cy: 5, scale_px_per_m: 30, vw: canvas.width, vh: canvas.height, rotation: 0 };
    /* 连 foxglove_bridge: ws://<hostname>:8765 (与 webui/human_fall 同一桥) */
    var proto = "ws://";
    var host = location.hostname || "192.168.31.58";
    var url = proto + host + ":8765";
    var live_hud = document.getElementById("live_banner");
    var live_text = document.getElementById("live_text");
    S.live.active = true;
    S.live.seq = 0;
    S.live.recv_window = [];
    if (live_hud) live_hud.style.display = "block";
    if (live_text) live_text.textContent = "连接实时点云 " + url + " (stride=" + S.live.stride + ")…";
    hud_msg("实时模式 (抽稀显示; 录制走 rec_btn 全量 rosbag)", false);
    try {
        S.live.conn = GT_LIVE.connect(url, {
            stride: S.live.stride,
            max_points: S.live.max_points,
            render: function (pts, n) {
                S.live.pts = pts; S.live.n = n;
                S.live.seq++;
                /* fps 测窗：5s 滑动窗口 */
                var now = Date.now();
                S.live.recv_window.push(now);
                while (S.live.recv_window.length && now - S.live.recv_window[0] > 5000)
                    S.live.recv_window.shift();
                S.live.fps_received = S.live.recv_window.length / 5;
                if (live_text) live_text.textContent =
                    "实时 " + n + " 点 · " + S.live.fps_received.toFixed(1) + " Hz (stride=" + S.live.stride + ")";
                /* 用 rAF 合并渲染（避免 ws 回调同帧多次触发） */
                if (!S._live_render_pend) {
                    S._live_render_pend = true;
                    requestAnimationFrame(function () {
                        S._live_render_pend = false;
                        _render_live_frame();
                    });
                }
            },
            on_state: function (connected) {
                if (live_text) live_text.textContent = connected ?
                    "已连实时点云，等待帧…" : "实时点云断开 (自动重连)";
            },
            on_error: function (msg) {
                if (live_text) live_text.textContent = "实时错误: " + msg;
            },
        });
    } catch (e) {
        hud_msg("实时模式启动失败: " + e.message, true);
        S.live.active = false;
        if (live_hud) live_hud.style.display = "none";
        return false;
    }
    return true;
}

function exit_live() {
    if (!S.live.active) return;
    if (S.live.conn) { try { S.live.conn.close(); } catch (e) {} S.live.conn = null; }
    S.live.active = false;
    S.live.pts = null; S.live.n = 0;
    var live_hud = document.getElementById("live_banner");
    if (live_hud) live_hud.style.display = "none";
    hud_msg("已退出实时模式", false);
    /* 画布清空 → 黑屏（提示「选会话开始」由 hud 提供） */
    if (ctx) {
        ctx.fillStyle = "#0c0d10"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
}

/* live 渲染：与 _render_frame_impl 同一 canvas 接口，但读 S.live.pts (raw 雷达 XYZ)。
 * 不 level、不 split；stride 抽稀已在上游完成，这里只做 XY 俯视 + z-tint。 */
function _render_live_frame() {
    if (!S.live.active || !S.live.pts || S.live.n === 0) return;
    var img = S._pixel_buf;
    var W = canvas.width, H = canvas.height;
    if (!img || S._pixel_w !== W || S._pixel_h !== H) {
        S._pixel_buf = img = new ImageData(W, H);
        S._pixel_w = W; S._pixel_h = H;
    }
    var data = img.data;
    /* 底色 #0c0d10 */
    for (var pi = 0; pi < data.length; pi += 4) {
        data[pi] = 12; data[pi + 1] = 13; data[pi + 2] = 16; data[pi + 3] = 255;
    }
    var v = S.view;
    var vs = v.scale_px_per_m, vw2 = v.vw / 2, vh2 = v.vh / 2;
    var cr = Math.cos(v.rotation), sr = Math.sin(v.rotation);
    var ccx = v.cx, ccy = v.cy;
    var pts = S.live.pts, n = S.live.n;
    var zz = S.z_min, zz2 = S.z_max;
    for (var k = 0; k < n; k++) {
        var x = pts[k * 3], y = pts[k * 3 + 1], z = pts[k * 3 + 2];
        if (z < zz || z > zz2) continue;      /* FIX-REVIEW-H1: live 也过 z 带 */
        var u = x - ccx, w = y - ccy;
        var rx = u * cr - w * sr;
        var ry = u * sr + w * cr;
        var px_i = (vw2 + rx * vs) | 0;
        var py_i = (vh2 - ry * vs) | 0;
        if (px_i < 0 || px_i >= W || py_i < 0 || py_i >= H) continue;
        var o4 = (py_i * W + px_i) * 4;
        if (z < 0.15)      { data[o4] = 40;  data[o4 + 1] = 60;  data[o4 + 2] = 92; }
        else if (z < 0.60) { data[o4] = 66;  data[o4 + 1] = 200; data[o4 + 2] = 235; }
        else if (z < 1.20) { data[o4] = 90;  data[o4 + 1] = 228; data[o4 + 2] = 128; }
        else if (z < 1.80) { data[o4] = 240; data[o4 + 1] = 224; data[o4 + 2] = 84; }
        else               { data[o4] = 245; data[o4 + 1] = 104; data[o4 + 2] = 78; }
        data[o4 + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    draw_grid();
}

/* 载入会话：与 live 模式互斥 — 进会前先 exit_live，避免双渲染源。 */
function load_session(sid) {
    if (S.live.active) exit_live();
    _tid_map = {};                                     /* 跨会话隔离：FUS_t... → P1/P2 映射清零 */
    S.suggestions = {};
    S.doc = null;
    S.objects_by_frame = {};
    S.undo = null;
    S.selected = null;
    S.dirty = false;
    S.last_edit_frame = null;                          /* 跨会话隔离: V 源指针 */
    if (S.play_timer) { clearInterval(S.play_timer); S.play_timer = null; S.playing = false; }
    stop_nav_hold();                                   /* FIX-navi: 会话切换强停 */
    fetch("/api/gt/session?sid=" + encodeURIComponent(sid))
        .then(function (r) { return r.json(); })
        .then(function (payload) {
            /* FIX-REVIEW-M1: fetch 返回时若用户已点「实时」进 live，丢弃这个 stale payload。
             * 否则会话点云被填回 S.split/S.frames 与 live 同屏互绘。 */
            if (S.live.active) return;
            if (!payload.ok) { hud_msg("加载失败: " + (payload.error || "?"), true); return; }
            S.sid = sid;
            S.session_info = payload;
            /* FIX-OPS: 别名同步到 S.meta（当 draft_alias 存在），progress 抬头可直接用 */
            if (!S.session_info.display_name || typeof S.session_info.display_name !== "string") {
                S.session_info.display_name = sid;
            }
            S.suggestions = payload.suggestions_auto || {};
            // 已有冻结记录 → manifest，加载到页脚
            render_frozen_section(payload.frozen_versions || []);
            return load_points(sid).then(function () {
                /* FIX-REVIEW-M1: load_points 也是异步 — 再判一次 */
                if (S.live.active) return;
                init_doc_if_needed(sid);
                if (payload.draft) {
                    try {
                        ingest_draft(payload.draft);
                        hud_msg("已载入 draft（annotate at " + payload.draft.annotated_at + "）", false);
                    } catch (e) {
                        hud_msg("draft 损坏,从空起: " + e.message, true);
                    }
                }
                refresh_frame_ui();
                refresh_progress();
                refresh_objects_panel();
                refresh_cadence_hint();                          /* 会话类 型 -> 节拍 */
            });
        })
        .catch(function (e) { hud_msg("网络错误: " + e.message, true); });
}

function load_points(sid) {
    /* FIX-PERF: 大会话 (>/~100MB) 时给 HUD 进度提示，避免用户以为卡死。 */
    var t_start = Date.now();
    hud_msg("载入会话元数据…", false);
    return Promise.all([
        fetch("/api/file?sid=" + encodeURIComponent(sid) + "&name=meta.json").then(function (r) { return r.json(); }),
        fetch("/api/file?sid=" + encodeURIComponent(sid) + "&name=points.bin").then(function (r) {
            if (!r.ok) throw new Error("points.bin HTTP " + r.status);
            var total = parseInt(r.headers.get("Content-Length") || "0", 10);
            /* 流式读: 显示下载进度 (大文件 328MB 让用户看到 MB 进度) */
            if (!r.body || !r.body.getReader) return r.arrayBuffer();
            var reader = r.body.getReader();
            var chunks = [], received = 0;
            function pump() {
                return reader.read().then(function (x) {
                    if (x.done) {
                        var ab = new ArrayBuffer(received);
                        var u8 = new Uint8Array(ab);
                        var off = 0;
                        for (var i = 0; i < chunks.length; i++) { u8.set(chunks[i], off); off += chunks[i].length; }
                        return ab;
                    }
                    chunks.push(x.value);
                    received += x.value.length;
                    if ((received & 0xFFFFFF) < 65536 && total > 0) {
                        hud_msg("下载点云 " + (received / 1048576).toFixed(0) + "/" + (total / 1048576).toFixed(0) + " MB…", false);
                    }
                    return pump();
                });
            }
            return pump();
        }),
    ]).then(function (both) {
        var meta = both[0], bin = both[1];
        var t_download = Date.now() - t_start;
        hud_msg("点云下载完 (" + (bin.byteLength / 1048576).toFixed(0) + " MB / " + (t_download / 1000).toFixed(1) + "s)，处理索引…", false);
        S.meta = meta;
        S.buf = new Float32Array(bin);
        S.frames = meta.frames;
        S.fps = meta.frame_rate_hz_measured || 9.55;      /* FIX-AUDIT-Q1: 真实 fps */
        var total_pts = S.buf.length / 7;
        var split = GT.split_frame_indices(S.buf, 7);
        S.split = split;
        /* 每帧的 compact 区间 + local→global 映射 */
        var n = meta.frames.length;
        var begin = new Int32Array(n + 1), cnt = new Int32Array(n);
        var ptr = 0;
        for (var fi = 0; fi < n; fi++) {
            var f = meta.frames[fi];
            var cnt_f = 0;
            for (var k = 0; k < f.count_points; k++) {
                if (split.leaf_of_raw[f.offset_points + k] >= 0) cnt_f++;
            }
            begin[fi] = ptr; cnt[fi] = cnt_f; ptr += cnt_f;
        }
        begin[n] = ptr;
        S.frame_compact_range = { begin: begin, cnt: cnt };
        // local → global compact 索引（渲染用）
        var maps = new Array(n), raw_maps = new Array(n);
        for (var fi2 = 0; fi2 < n; fi2++) {
            var f2 = meta.frames[fi2];
            var local = new Int32Array(cnt[fi2]);
            var loc_raw = new Int32Array(cnt[fi2]);
            var w = 0;
            for (var k2 = 0; k2 < f2.count_points; k2++) {
                var g = split.leaf_of_raw[f2.offset_points + k2];
                if (g >= 0) { local[w] = g; loc_raw[w] = k2; w++; }
            }
            maps[fi2] = local;
            raw_maps[fi2] = loc_raw;
        }
        S.frame_compact_map = maps;
        S.frame_raw_of_leaf = raw_maps;
        var t_total = ((Date.now() - t_start) / 1000).toFixed(1);
        hud_msg("点云 OK: " + (split.n_leveled / 1e6).toFixed(2) + "M 有效点 (载入耗时 " + t_total + "s)", false);
        render_frame(S.current_frame);
    }).catch(function (e) {
        hud_msg("点云载入失败: " + e.message, true);
    });
}

// ---------------- doc ----------------
function init_doc_if_needed(sid) {
    if (S.doc && S.doc.session_id === sid) return;
    /* FIX-R3-Q1: 每会话单调 object 序号 — 同帧多人 / paste / interpolate 不再撞 id */
    S._oseq = 0;
    /* FIX-AUDIT-Q5: points sha 必须真的对应 points.bin,不是 meta */
    var sha = {
        points: (S.session_info && S.session_info.points_sha) || "",
        meta: (S.session_info && S.session_info.meta_sha) || "",
    };
    S.doc = GT.make_session_doc(sid, sha, S.annotator || "annotator-1");
    S.objects_by_frame = {};
    S.undo = GT.undo_new();
    S.save_sha = null;
}

function ingest_draft(d) {
    if (d.session_id !== S.sid) throw new Error("draft sid 不匹配");
    S.doc = d;
    /* PERF-JIT: 立即剥离全部 raw_point_indices — 撤销/删除不再复制 78MB；
     * 之后每次 save 时按需原地 inflate，回去从盘中重读也可。 */
    Object.keys(d.objects).forEach(function (id) {
        delete d.objects[id].raw_point_indices;
        delete d.objects[id].point_count;
        d.objects[id]._inflated = 0;
    });
    /* FIX-AUDIT-R2: 用 doc_render_map 保参照——不拷贝，让 mark_reviewed/set_class
     * 直接写 S.doc.objects，渲染也读 S.doc，单一数据源。 */
    S.objects_by_frame = GT.doc_render_map(d);
    S.undo = GT.undo_new();
    refresh_objects_panel();
}

function doc_add(obj, skip_undo_push) {
    mark_dirty();
    if (!skip_undo_push) {
        var prev = GT.doc_snapshot_objects(S.doc);
        S.undo = GT.undo_push(S.undo, prev);
    }
    GT.doc_add_object(S.doc, obj);
    /* FIX-AUDIT-R2: 单一数据源——render map 重建以同步 doc 参照 */
    S.objects_by_frame = GT.doc_render_map(S.doc);
    S.selected = obj.object_id;
}

function doc_remove(object_id) {
    mark_dirty();
    var prev = GT.doc_snapshot_objects(S.doc);
    S.undo = GT.undo_push(S.undo, prev);
    var o = S.doc.objects[object_id];
    if (!o) return;
    GT.doc_remove_object(S.doc, object_id);
    /* FIX-AUDIT-R2: 重建 render map 保单一数据源 */
    S.objects_by_frame = GT.doc_render_map(S.doc);
    if (S.selected === object_id) S.selected = null;
}

function doc_history_log(action, before_nullable, after_nullable) {
    /* STEP 3 要求保存建议原样 + 人工修改历史 */
    S.doc.history = S.doc.history || [];
    S.doc.history.push({
        at: new Date().toISOString(),
        action: action,
        before: before_nullable ? JSON.parse(JSON.stringify(before_nullable)) : null,
        after: after_nullable ? JSON.parse(JSON.stringify(after_nullable)) : null,
    });
}

function mark_dirty() { S.dirty = true; hud_msg("未保存变更", false); }

// ---------------- 渲染 ----------------
/* 渲染节流: rAF 合并 — 一次 rAF 周期最多一次完整绘制。
 * mousemove/pan/wasdq 高速触发时不 49k 点 * 每 event 跑完整 paint。 */
var _render_pending = false, _render_timer = null;
function render_frame(frame_idx) {
    if (!S.split || !S.frames) return;
    S.current_frame = Math.max(0, Math.min(S.frames.length - 1, frame_idx));
    if (_render_pending) return;         /* 已计划 — 下层一次性画最新状态 */
    _render_pending = true;
    _render_timer = requestAnimationFrame(_render_frame_now);
}
function _render_frame_now() {
    _render_pending = false; _render_timer = null;
    _render_frame_impl(S.current_frame);
}

function _render_frame_impl(frame_idx) {
    ctx.fillStyle = "#0c0d10";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    var v = S.view;
    var rng = S.frame_compact_range;
    var beg = rng.begin[S.current_frame], cnt = rng.cnt[S.current_frame];
    var lm = S.frame_compact_map[S.current_frame];
    var pts = S.split.leveled_xyz;
    /* 画点: z-tint 同 render_person_label.py — ImageData 直写 (复用 buffer 防每帧 alloc) */
    var W = canvas.width, H = canvas.height;
    if (!S._pixel_buf || S._pixel_w !== W || S._pixel_h !== H) {
        S._pixel_buf = new ImageData(W, H);
        S._pixel_w = W; S._pixel_h = H;
    }
    var img = S._pixel_buf;
    var data = img.data;
    /* 底色 (#0c0d10)预填整个 buffer — 之前只拷贝 49k 点,剩余黑边是目前 bug */
    var base_r = 12, base_g = 13, base_b = 16;
    for (var pi = 0; pi < data.length; pi += 4) {
        data[pi] = base_r; data[pi + 1] = base_g; data[pi + 2] = base_b; data[pi + 3] = 255;
    }
    var cw = W, ch = H;
    var zz = S.z_min, zz2 = S.z_max;
    var vs = v.scale_px_per_m, vw2 = v.vw / 2, vh2 = v.vh / 2;
    var cr = Math.cos(v.rotation), sr = Math.sin(v.rotation);
    var ccx = v.cx, ccy = v.cy;
    for (var k = 0; k < cnt; k++) {
        var g = lm[k];
        var x = pts[g * 3], y = pts[g * 3 + 1], z = pts[g * 3 + 2];
        if (z < zz || z > zz2) continue;
        var u = x - ccx, w = y - ccy;
        var rx = u * cr - w * sr;
        var ry = u * sr + w * cr;
        var px_i = (vw2 + rx * vs) | 0;
        var py_i = (vh2 - ry * vs) | 0;
        if (px_i < 0 || px_i >= cw || py_i < 0 || py_i >= ch) continue;
        /* z-tint 简化为 5 档 (40,60,92 / 66,200,235 / 90,228,128 / 240,224,84 / 245,104,78) */
        var r_, g_, b_;
        if (z < 0.15) { r_ = 40; g_ = 60; b_ = 92; }
        else if (z < 0.60) { r_ = 66; g_ = 200; b_ = 235; }
        else if (z < 1.20) { r_ = 90; g_ = 228; b_ = 128; }
        else if (z < 1.80) { r_ = 240; g_ = 224; b_ = 84; }
        else { r_ = 245; g_ = 104; b_ = 78; }
        var o4 = (py_i * cw + px_i) * 4;
        data[o4] = r_; data[o4 + 1] = g_; data[o4 + 2] = b_; data[o4 + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    /* 网格在点云之后 stroke, 覆盖 grid 不被点云废 */
    draw_grid();
    /* 画中 objects / suggestions / pending shape */
    draw_objects(S.current_frame);
    draw_suggestions(S.current_frame);
    draw_pending();
    /* 帧 HUD */
    refresh_frame_ui();
    refresh_suggestions_panel();
}

function z_tint(z) {
    if (z < 0.15) return "rgb(40,60,92)";
    if (z < 0.60) return "rgb(66,200,235)";
    if (z < 1.20) return "rgb(90,228,128)";
    if (z < 1.80) return "rgb(240,224,84)";
    return "rgb(245,104,78)";
}

function draw_grid() {
    ctx.strokeStyle = "#22242a"; ctx.lineWidth = 1;
    var step = 1;  // 1m 格
    var x_min = Math.floor(v_left()), x_max = Math.ceil(v_right());
    var y_min = Math.floor(v_bot()), y_max = Math.ceil(v_top());
    ctx.beginPath();
    for (var x = x_min; x <= x_max; x += step) {
        var s = lev_to_screen(x, 0);
        ctx.moveTo(s[0], 0); ctx.lineTo(s[0], canvas.height);
    }
    for (var y = y_min; y <= y_max; y += step) {
        var s2 = lev_to_screen(0, y);
        ctx.moveTo(0, s2[1]); ctx.lineTo(canvas.width, s2[1]);
    }
    ctx.stroke();
    /* 原点 */
    ctx.fillStyle = "#fff";
    var o = lev_to_screen(0, 0);
    ctx.fillRect(o[0] - 2, o[1] - 2, 4, 4);
}
function v_left() { return S.view.cx - canvas.width / 2 / S.view.scale_px_per_m; }
function v_right() { return S.view.cx + canvas.width / 2 / S.view.scale_px_per_m; }
function v_top() { return S.view.cy + canvas.height / 2 / S.view.scale_px_per_m; }
function v_bot() { return S.view.cy - canvas.height / 2 / S.view.scale_px_per_m; }

function draw_objects(frame_idx) {
    var objs = S.objects_by_frame[String(frame_idx)] || [];
    objs.forEach(function (o) {
        var col = S.color[o.class_name] || "#fff";
        var stroke = col, fill = col + "22"; // 半透明填充
        if (o.review_status === "unreviewed") { stroke = col + "cc"; fill = col + "10"; }
        if (o.source === "propagated") { stroke = col + "88"; }
        if (o.object_id === S.selected) { stroke = "#fff"; }
        ctx.strokeStyle = stroke; ctx.fillStyle = fill; ctx.lineWidth = (o.object_id === S.selected ? 3 : 1.5);
        ctx.beginPath();
        if (o.polygon_xy) {
            o.polygon_xy.forEach(function (p, i) {
                var s = lev_to_screen(p[0], p[1]);
                if (i === 0) ctx.moveTo(s[0], s[1]); else ctx.lineTo(s[0], s[1]);
            });
            ctx.closePath();
        } else if (o.box_xy) {
            var a = lev_to_screen(o.box_xy[0], o.box_xy[1]);
            var b = lev_to_screen(o.box_xy[2], o.box_xy[3]);
            ctx.rect(Math.min(a[0], b[0]), Math.min(a[1], b[1]),
                Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1]));
        } else {
            var c = lev_to_screen(o.x, o.y);
            ctx.arc(c[0], c[1], o.r_xy * S.view.scale_px_per_m, 0, Math.PI * 2);
        }
        ctx.stroke();
        if (o.object_id === S.selected) ctx.fill();
        /* 文本 */
        var label_pt = o.polygon_xy ? o.polygon_xy[0] : (o.box_xy ? [o.box_xy[0], o.box_xy[1]] : [o.x, o.y]);
        var s3 = lev_to_screen(label_pt[0], label_pt[1]);
        ctx.fillStyle = stroke;
        ctx.font = "11px Consolas";
        ctx.fillText(o.class_name.slice(0, 4) + (o.track_id ? (" " + o.track_id) : "") +
            " [" + o.source + "/" + (o.review_status === "reviewed" ? "R" : "U") + "]", s3[0] + 4, s3[1] - 4);
    });
}

function draw_suggestions(frame_idx) {
    var sugs = S.suggestions[String(frame_idx)] || [];
    sugs.forEach(function (c, idx) {
        ctx.strokeStyle = "#ff6" + "88"; ctx.lineWidth = 1.5; ctx.setLineDash([4, 3]);
        ctx.beginPath();
        var c0 = lev_to_screen(c.x, c.y);
        ctx.arc(c0[0], c0[1], c.r_xy * S.view.scale_px_per_m, 0, Math.PI * 2);
        ctx.stroke(); ctx.setLineDash([]);
        /* 每个建议上方挂号码 (#1/#2 ) 跟右侧 sug_row #N 一一对应；再叠 track_id 名字 */
        ctx.fillStyle = "#ff6";
        ctx.font = "bold 11px 'Segoe UI'";
        ctx.fillText("#" + (idx + 1) + " " + (c.track_id || ""), c0[0] + 4, c0[1] - 4);
        ctx.font = "10px 'Segoe UI'";
        ctx.fillStyle = "#ff6cc";
        ctx.fillText("conf " + (c.confidence != null ? c.confidence.toFixed(2) : "—"),
            c0[0] + 4, c0[1] + 13);
    });
}

function draw_pending() {
    /* 画工具进行中的 rect/poly;
     * 右键连续翻帧中不画 pending（鼠标此时没有 ROI 语义，挂了 stale 线会误导） */
    if (S.nav_dir != null) { ctx.setLineDash([]); return; }
    ctx.strokeStyle = "#4ecdc4"; ctx.lineWidth = 1; ctx.setLineDash([6, 4]);
    if (S.tool === "rect" && S.rect_p0) {
        var p1 = S.rect_p0  ; var p2 = S.mouse_lev;
        if (p2) {
            var a = lev_to_screen(p1[0], p1[1]), b = lev_to_screen(p2[0], p2[1]);
            ctx.strokeRect(Math.min(a[0], b[0]), Math.min(a[1], b[1]),
                Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1]));
        }
    } else if ((S.tool === "poly") && S.pending_poly.length) {
        ctx.beginPath();
        S.pending_poly.forEach(function (p, i) {
            var s = lev_to_screen(p[0], p[1]);
            if (i === 0) ctx.moveTo(s[0], s[1]); else ctx.lineTo(s[0], s[1]);
        });
        if (S.mouse_lev) { var mm = lev_to_screen(S.mouse_lev[0], S.mouse_lev[1]); ctx.lineTo(mm[0], mm[1]); }
        ctx.stroke();
    }
    ctx.setLineDash([]);
}

// ---------------- UI ----------------
function hud_msg(msg, err) {
    hud.textContent = msg;
    hud.style.color = err ? "#f66" : "#8f8";
}
function refresh_frame_ui() {
    var cur = document.getElementById("frame_label");
    var slider = document.getElementById("frame_slider");
    if (cur && S.frames) {
        cur.textContent = "帧 " + (S.current_frame + 1) + "/" + S.frames.length +
            " t=" + (S.frames[S.current_frame].bag_time_sec || 0).toFixed(2) + "s";
        slider.max = String(S.frames.length - 1);
        slider.value = String(S.current_frame);
    }
    var sid_sel = document.getElementById("sid_select");
    if (sid_sel && sid_sel.value !== S.sid) sid_sel.value = S.sid || "";
    refresh_objects_panel();
    refresh_progress();
}
function refresh_progress() {
    if (!S.doc || !S.frames) return;
    var p = GT.session_progress(S.doc, S.frames.length);
    var sess_disp = (S.session_info && S.session_info.display_name) || S.sid;
    /* FIX-OPS: draft 别名与会话名分开——会话名是 meta.name（同一机器所有面板共用），
     * draft 别名只是当前这份"工作稿"的标签。两者都有时并列显示。 */
    var draft_alias = (S.session_info && S.session_info.draft_alias) || null;
    var disp = draft_alias ? (sess_disp + " · <i>" + escape_html(draft_alias) + "</i>") : sess_disp;
    prog.innerHTML =
        "<b>" + disp + "</b> <span style='opacity:.55;font-size:10px'>" + S.sid + "</span><br>" +
        p.track_ids + " 人ID · " +
        p.person_objects + " 人块 · " + p.furniture_objects + " 家具 · " +
        "标注帧 " + p.annotated_frames + "/" + p.total_frames +
        " · 已审 " + p.reviewed_frames +
        " · 冲突 " + p.conflicts +
        " · GT_LEVEL " + GT.compute_gt_level(S.doc);
}

function render_frozen_section(versions) {
    var el = document.getElementById("frozen_list");
    if (!el) return;
    /* FIX-OPS: 别名叠在 V 行右侧。别名为可写显示层，不进 hash 链。
     * FIX-REVIEW-M2: draft 行出了 S.session_info.draft 即可（不依赖 S.doc.objects，后者在
     * load 时序上晚于本函数调用）。FIX-REVIEW-M6: annotator 来自 prompt 必须转义，
     * 否则存储型 XSS——冻结者忘了清洗的话，后续打开页面的标注人会被执行。 */
    var aliases = (S.session_info && S.session_info.version_aliases) || {};
    var draft_alias = (S.session_info && S.session_info.draft_alias) || null;
    var has_draft = !!(S.session_info && S.session_info.draft);
    el.innerHTML = (has_draft
            ? "<div>draft" + (draft_alias ? (" <b>" + escape_html(draft_alias) + "</b>") : " <i style='opacity:.6'>(未命名)</i>") +
              " <button data-alias-ver='__draft__' style='font-size:10px;padding:0 6px'>✎</button></div>"
            : "") +
        (versions.length === 0 ? "<i>尚无冻结</i>" :
            versions.map(function (v) {
                var a = aliases[v.version];
                return "<div>" + v.version +
                    (a ? (" <b>" + escape_html(a) + "</b>") : "") +
                    " sha=" + v.sha256.slice(0, 12) +
                    " n=" + v.object_count + " by " + escape_html(v.annotator || "?") +
                    " <button data-alias-ver='" + v.version + "' style='font-size:10px;padding:0 6px'>✎</button>" +
                    "</div>";
            }).join(""));
}

function escape_html(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
}

function refresh_objects_panel() {
    var objs = S.objects_by_frame[String(S.current_frame)] || [];
    var el = document.getElementById("objects_panel");
    if (!el) return;
    if (!objs.length) { el.innerHTML = "<i>本帧无对象</i>"; return; }
    el.innerHTML = objs.map(function (o) {
        var sel = o.object_id === S.selected ? " style='background:#223'" : "";
        return "<div" + sel + " data-oid='" + o.object_id + "' class='obj_row'>" +
            o.class_name.padEnd(10, " ").slice(0, 10) +
            (o.track_id ? " [" + o.track_id + "]" : "") +
            " <span style='opacity:.7'>" + o.source + "/" + o.review_status + "</span>" +
            "</div>";
    }).join("");
    Array.prototype.forEach.call(el.querySelectorAll(".obj_row"), function (e) {
        e.onclick = function () {
            S.selected = e.getAttribute("data-oid");
            refresh_objects_panel();
            render_frame(S.current_frame);
        };
    });
}

// ---------------- tools ----------------
function on_canvas_mousedown(e) {
    /* FIX-REVIEW-H2: live 模式只允许 pan/wheel/z 滑杆 — 标注/选择/编辑按键不响应。
     * （S.doc/S.split/S.frame_compact_* 在 live 下全是 null，跑了会 TypeError。） */
    if (S.live.active) {
        if (e.button === 1 || e.button === 2 || S.tool === "pan" || S.tool === "grip") {
            /* 允许 live 下的中键平移/右键压 */
            if (e.button === 1 || S.tool === "pan") {
                var mx = e.clientX, my = e.clientY;
                S.pan_drag = { x0: mx, y0: my, cx: S.view.cx, cy: S.view.cy };
            }
        }
        return;
    }
    /* DBG: 任何 canvas mousedown 都打印，用于诊断 "画不了第二个 poly" */
    console.log("[mousedown]", e.button, "xy:", e.clientX, e.clientY,
        "tool:", S.tool, "pending:", S.pending_poly.length, "nav:", S.nav_dir, "sel:", S.selected);
    /* 防 sidebar input 收焦阻断后续 key 快捷键: canvas 点击一律 blur */
    if (document.activeElement && document.activeElement.blur) {
        try { document.activeElement.blur(); } catch (e2) {}
    }
    var rect = canvas.getBoundingClientRect();
    var mx = e.clientX - rect.left, my = e.clientY - rect.top;
    S.mouse_lev = screen_to_lev(mx, my);
    /* 右键: 按住连续前进(rAF 节流; 不按 button==2 区分工具, 统一语义)
     * Shift+右键: 反向连续倒退 */
    if (e.button === 2) {
        e.preventDefault();
        if (S.nav_dir) return;                                   /* 长按防抖重入 */
        S.nav_dir = e.shiftKey ? -1 : 1;
        if (S.playing) toggle_play();                            /* 撞: 优先右键 */
        start_nav_hold();
        return;
    }
    if (e.button === 1) {                                        /* 中键 = 平移(无论当前工具) */
        e.preventDefault();
        S.pan_drag = { x0: mx, y0: my, cx: S.view.cx, cy: S.view.cy };
        return;
    }
    if (e.button !== 0) return;
    if (S.tool === "pan") {
        S.pan_drag = { x0: mx, y0: my, cx: S.view.cx, cy: S.view.cy };
        return;
    }
    if (S.tool === "rect") {
        if (!S.rect_p0) { S.rect_p0 = screen_to_lev(mx, my); }
        else {
            var p0 = S.rect_p0, p1 = screen_to_lev(mx, my);
            finish_rect(p0, p1);
            S.rect_p0 = null;
        }
        return;
    }
    if (S.tool === "poly") {
        var np = screen_to_lev(mx, my);
        S.pending_poly.push(np);
        /* 双击判定锚点: dblclick 会来 pop 这一顶点,需知时间 */
        S._poly_last_click_ts = performance.now();
        // DBG: 帮排查 "同帧画两个 poly" 复现路径
        console.log("[poly-pending]", S.pending_poly.length, "顶点", "帧", S.current_frame,
            "lobj", Object.keys(S.doc ? S.doc.objects : {}).length);
        return;
    }
    /* G grip 模式: 命中对象 → 按下拖(不是 WASD 键控) */
    if (S.tool === "grip") {
        var hit_g = pick_object_at(mx, my);
        if (hit_g) {
            S.selected = hit_g;
            /* 拖动全过程压一次 undo — mousemove 不重复压, up 落最终状态为 undo 一条 entry */
            S.undo = GT.undo_push(S.undo, GT.doc_snapshot_objects(S.doc));
            S.grip_drag = { object_id: hit_g, last_mouse_lev: screen_to_lev(mx, my), started: true };
            hud_msg("拖框 " + hit_g + "（按左键动 / 松手落）", false);
        } else {
            S.grip_drag = null;
        }
        refresh_objects_panel(); render_frame(S.current_frame);
        return;
    }
    var hit = pick_object_at(mx, my);
    if (hit) S.selected = hit;
    refresh_objects_panel();
    render_frame(S.current_frame);
}

/* 双击(左键) — rect: 立即用(rect_p0, 双击点)闭合; poly: pop 掉刚才 click 加的多余顶点并闭合。
 * dblclick 之前浏览器已经发过 2 次 mousedown/click，所以
 *   - rect: 第一次 mousedown 已记 rect_p0，第二次 mousedown 实际上已 finish_rect，rect_p0 已清空；
 *           这里 dblclick 相当于冗余触发，直接当无操作返回（不改现状）。
 *   - poly: 两次 mousedown 各 push 一个顶点，导致最后两点重叠或很近；pop 1 个让形状正确，再 finish。 */
function on_canvas_dblclick(e) {
    if (e.button !== 0) return;
    if (S.tool === "poly") {
        /* 若 pending 顶点数 >=4 且末尾两点间距很小（重复点击），pop 一次 */
        if (S.pending_poly.length >= 4) {
            var a = S.pending_poly[S.pending_poly.length - 2];
            var b = S.pending_poly[S.pending_poly.length - 1];
            var d = Math.hypot(a[0] - b[0], a[1] - b[1]);
            if (d < 0.01) {                       /* 1cm 内视作同一点 */
                S.pending_poly.pop();
            }
        }
        finish_poly();
        e.preventDefault();
        return;
    }
    /* rect / pan / grip: 双击不做额外动作。rect 第二次点已闭合。 */
}

/* 右键连续导航状态: {dir:+1/-1, t_start, last_ts, raf} */
function start_nav_hold() {
    S.nav_state = { t_start: performance.now(), last_ts: performance.now(), frame_acc: 0 };
    S.nav_raf = requestAnimationFrame(nav_hold_tick);
}
function stop_nav_hold() {
    if (S.nav_raf) { cancelAnimationFrame(S.nav_raf); S.nav_raf = null; }
    S.nav_dir = null;
    S.nav_state = null;
}
function nav_hold_tick(ts) {
    if (S.nav_dir == null || !S.frames) { stop_nav_hold(); return; }
    var st = S.nav_state;
    /* 前 300ms 慢 (one-shot 防误触; 然后再提速到 ~10fps) */
    var elapsed = ts - st.t_start;
    var fps_eff = elapsed < 350 ? 2 : 10;
    st.frame_acc = (st.frame_acc || 0) + (ts - st.last_ts) / 1000 * fps_eff;
    st.last_ts = ts;
    while (st.frame_acc >= 1) {
        st.frame_acc -= 1;
        var nxt = S.current_frame + S.nav_dir;
        if (nxt < 0 || nxt >= S.frames.length) { stop_nav_hold(); return; }
        set_frame(nxt);
    }
    S.nav_raf = requestAnimationFrame(nav_hold_tick);
}
function on_canvas_mousemove(e) {
    var rect = canvas.getBoundingClientRect();
    var mx = e.clientX - rect.left, my = e.clientY - rect.top;
    /* 右键 nav 期间不刷新 mouse_lev, 防 pending ROI 粘连 stale 位置 */
    if (S.nav_dir == null) S.mouse_lev = screen_to_lev(mx, my);
    if (S.pan_drag) {
        /* 屏幕像素 Δ → 米; 屏幕 y 向下, leveled y 向上 → dy 翻号;
         * 再按 view.rotation 逆旋 (屏幕 u/w 反映到 leveled x/y) */
        var du_px = mx - S.pan_drag.x0, dv_px = my - S.pan_drag.y0;
        var du = du_px * m_per_px();
        var dv = -dv_px * m_per_px();
        var c = Math.cos(S.view.rotation), s = Math.sin(S.view.rotation);
        /* 拖屏幕 +du/+dv 应把 view center 在 leveled 里反向移动同一向量 */
        var dx_lev = du * c + dv * s;
        var dy_lev = -du * s + dv * c;
        S.view.cx = S.pan_drag.cx - dx_lev;
        S.view.cy = S.pan_drag.cy - dy_lev;
    }
    /* Grip drag: 左键按 下时未松开 → 拿 当前 mouse_lev - 上次 mouse_lev 做增量,
     * 平移 ROI. 按鼠标移动速度自由精细(不需 WASD 离散步). */
    if (S.grip_drag && S.mouse_lev) {
        var last = S.grip_drag.last_mouse_lev;
        var dobj = S.doc ? S.doc.objects[S.grip_drag.object_id] : null;
        if (dobj) {
            var ddx = S.mouse_lev[0] - last[0];
            var ddy = S.mouse_lev[1] - last[1];
            if (ddx !== 0 || ddy !== 0) {
                /* 一次性 undo_push 在 mousedown 时压; 拖动各 step 不压(否则一次 drag 多 undo 项) */
                GT.translate_shape(dobj, ddx, ddy);
                S.grip_drag.last_mouse_lev = S.mouse_lev;
                mark_dirty();
            }
        }
    }
    render_frame(S.current_frame);
}
function on_canvas_mouseup(e) {
    S.pan_drag = null;
    if (e && e.button === 2) stop_nav_hold();                 /* 右键松 → 停止翻帧 */
    /* Grip drag 结束: 拿最终位置重选点 + 记录 */
    if (S.grip_drag) {
        var dobj = S.doc ? S.doc.objects[S.grip_drag.object_id] : null;
        if (dobj) {
            reselect_points_in_frame(dobj, dobj.frame_idx, S.z_min, S.z_max);
            doc_history_log("grip_drag", null, dobj);
            refresh_objects_panel(); refresh_progress(); render_frame(S.current_frame);
        }
        S.grip_drag = null;
    }
}
/* 脱离画布/失焦也停 (防右键让窗口 out-of-focus 后仍走) */
function on_canvas_mouseleave(e) { stop_nav_hold(); }
window.addEventListener("blur", stop_nav_hold);
function on_canvas_wheel(e) {
    e.preventDefault();
    var rect = canvas.getBoundingClientRect();
    var mx = e.clientX - rect.left, my = e.clientY - rect.top;
    var m0 = screen_to_lev(mx, my);
    var f = e.deltaY < 0 ? 1.2 : 0.83;
    S.view.scale_px_per_m = Math.max(5, Math.min(400, S.view.scale_px_per_m * f));
    var m1 = screen_to_lev(mx, my);
    S.view.cx += m0[0] - m1[0];
    S.view.cy += m0[1] - m1[1];
    if (S.live.active) _render_live_frame(); else render_frame(S.current_frame);
}
function on_keydown(e) {
    /* FIX-REVIEW-H2: live 模式禁用标注/编辑/导航按键；仅保留 R/E/T 视角键。 */
    if (S.live.active) {
        if (e.code === "KeyR") rotate_view(-Math.PI / 12);
        else if (e.code === "KeyE") rotate_view(+Math.PI / 12);
        else if (e.code === "KeyT") reset_view_rotation();
        return;
    }
    /* 提交/取消快捷键（其余见 USER_GUIDE）。注意输入框聚焦时不抢按键。 */
    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") && e.code !== "Escape") return;
    /* 工具键触发时 blur 当前 focus 元素，防 sidebar input 收】后续 key */
    if (["KeyL", "KeyN", "KeyP", "KeyV", "KeyI", "KeyC", "KeyK", "KeyB", "KeyG", "KeyH", "Enter", "Escape"].indexOf(e.code) >= 0
        && document.activeElement && document.activeElement.blur) {
        try { document.activeElement.blur(); } catch (e2) {}
    }
    var o = S.selected ? S.doc.objects[S.selected] : null;
    var handled = true;
    if (e.code === "KeyP") S.tool = "pan";
    else if (e.code === "KeyN") {
        /* 已按 N 且有 rect_p0 → N 把 corners 提交（像 poly 续续，N 双击 = Finish-Rect） */
        if (S.tool === "rect" && S.rect_p0 && S.mouse_lev) {
            finish_rect(S.rect_p0, S.mouse_lev);
            S.rect_p0 = null;
        } else {
            S.tool = "rect";
        }
    }
    else if (e.code === "KeyL") {
        /* L 双义:
         * - 当前工具非 poly → 切入 poly 工具（累积顶点）
         * - 当前工具已 poly 且 pending_poly>=3 → 立即闭合提交（双击 L = Enter） */
        if (S.tool === "poly" && S.pending_poly.length >= 3) {
            finish_poly();
        } else {
            S.tool = "poly";
        }
    }
    else if (e.code === "Escape") { S.tool = "pan"; S.rect_p0 = null; S.pending_poly = []; }
    else if (e.code === "Enter" && S.tool === "poly") finish_poly();
    else if (e.code === "Digit1") set_class("PERSON");
    else if (e.code === "Digit2") set_class("FURNITURE");
    else if (e.code === "Digit3") set_class("BACKGROUND");
    else if (e.code === "Digit4") set_class("UNKNOWN");
    else if (e.code === "KeyT" && o && o.class_name === "PERSON") assign_track_id();
    else if (e.code === "Delete" && o) { doc_remove(o.object_id); render_frame(S.current_frame); }
    else if (e.code === "KeyZ" && e.ctrlKey) do_undo();
    else if (e.code === "KeyY" && e.ctrlKey) do_redo();
    else if (e.code === "ArrowLeft") set_frame(S.current_frame - (e.shiftKey ? 10 : 1));
    else if (e.code === "ArrowRight") set_frame(S.current_frame + (e.shiftKey ? 10 : 1));
    else if (e.code === "Comma") set_frame(S.current_frame - (e.shiftKey ? 50 : 25));
    else if (e.code === "Period") set_frame(S.current_frame + (e.shiftKey ? 50 : 25));
    else if (e.code === "KeyS" && e.ctrlKey) { save_draft(); }
    else if (e.code === "KeyC" && S.selected) copy_to_next_frame();
    else if (e.code === "KeyK") mark_keyframe();
    else if (e.code === "KeyB") show_breaks_dialog();
    else if (e.code === "KeyF") S.tool = "grip";              /* F 框拖模式 (鼠标连续跟) */
    else if (e.code === "KeyG") mark_reviewed();              /* FIX-AUDIT-Q2 */
    else if (e.code === "KeyH") mark_frame_reviewed();        /* FIX-AUDIT-Q2 */
    else if (e.code === "Space") { toggle_play(); }           /* FIX-AUDIT-Q1 */
    else if (e.code === "KeyV") paste_from_prev_frame();      /* V 粘贴上一帧全部 */
    else if (e.code === "KeyI") interpolate_between_keyframes(); /* I 两 K 帧间线性插值 */
    else if (e.code === "KeyR") rotate_view(-Math.PI / 12);   /* 逆 15° */
    else if (e.code === "KeyE") rotate_view(+Math.PI / 12);   /* 顺 15° */
    else if (e.code === "KeyT" && !S.selected) reset_view_rotation(); /* 回正 (T 无选中时) */
    else if (e.code === "KeyW") nudge_selected(0, +1, e.shiftKey ? 0.5 : 0.05);   /* FIX-R3-Q10: W=上移=leveled +y */
    else if (e.code === "KeyA") nudge_selected(-1, 0, e.shiftKey ? 0.5 : 0.05);
    else if (e.code === "KeyS" && !e.ctrlKey) nudge_selected(0, -1, e.shiftKey ? 0.5 : 0.05);
    else if (e.code === "KeyD") nudge_selected(1, 0, e.shiftKey ? 0.5 : 0.05);
    else handled = false;
    if (handled) { e.preventDefault(); render_frame(S.current_frame); }
}

function pick_object_at(mx, my) {
    var objs = S.objects_by_frame[String(S.current_frame)] || [];
    var best = null; var best_d = 1e9;
    for (var i = 0; i < objs.length; i++) {
        var o = objs[i];
        var d = 0;
        if (o.polygon_xy) {
            d = poly_dist(S.mouse_lev[0], S.mouse_lev[1], o.polygon_xy);
        } else if (o.box_xy) {
            d = rect_dist(S.mouse_lev[0], S.mouse_lev[1], o.box_xy);
        } else {
            d = Math.hypot(S.mouse_lev[0] - o.x, S.mouse_lev[1] - o.y) - o.r_xy;
        }
        if (d < best_d) { best_d = d; best = o.object_id; }
    }
    return best;
}
function poly_dist(px, py, poly) {
    if (GT.point_in_poly(px, py, poly)) return 0;
    var d = 1e9;
    for (var i = 0; i < poly.length; i++) {
        var a = poly[i], b = poly[(i + 1) % poly.length];
        d = Math.min(d, seg_dist(px, py, a[0], a[1], b[0], b[1]));
    }
    return d;
}
function rect_dist(px, py, r) {
    var x0 = Math.min(r[0], r[2]), x1 = Math.max(r[0], r[2]);
    var y0 = Math.min(r[1], r[3]), y1 = Math.max(r[1], r[3]);
    if (px >= x0 && px <= x1 && py >= y0 && py <= y1) return 0;
    var dx = Math.max(x0 - px, px - x1, 0), dy = Math.max(y0 - py, py - y1, 0);
    return Math.hypot(dx, dy);
}
function seg_dist(px, py, ax, ay, bx, by) {
    var t = ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / ((bx - ax) * (bx - ax) + (by - ay) * (by - ay) + 1e-12);
    t = Math.max(0, Math.min(1, t));
    var qx = ax + t * (bx - ax), qy = ay + t * (by - ay);
    return Math.hypot(px - qx, py - qy);
}

/* 完成一个 rect：按 z 带 + ROI 选点，make object，push history */
function finish_rect(p0, p1) {
    var sel = { type: "rect", x0: p0[0], y0: p0[1], x1: p1[0], y1: p1[1] };
    commit_selection(sel);
}
function finish_poly() {
    if (S.pending_poly.length < 3) { hud_msg("多边形至少 3 顶点", true); return; }
    var sel = { type: "poly", poly: S.pending_poly.slice() };
    S.pending_poly = [];
    commit_selection(sel);
}
/* 从建议建对象 */
function accept_suggestion(idx) {
    var sugs = S.suggestions[String(S.current_frame)] || [];
    var c = sugs[idx];
    if (!c) return;
    var sel = { type: "circle", x: c.x, y: c.y, r_xy: c.r_xy };
    var obj = mk_object_from_selection(sel, "model-suggested");
    obj.source = "human";
    obj.class_name = "PERSON";
    /* 引擎建议 track_id 形如 FUS_t0_1；GT 契约要 P1/P2。
     * 不是最近的"哪个 track 是新"，而同帧段内保持 propose_track_id 一致性。 */
    obj.track_id = suggest_to_person_tid(c.track_id) || ("P" + (obj.frame_idx + 1));
    obj.review_status = "unreviewed";
    obj.suggested_engine_track = c.track_id;
    obj.suggested = c;
    doc_add(obj);
    doc_history_log("accept_suggestion", null, obj);
    refresh_objects_panel(); refresh_progress(); render_frame(S.current_frame);
}

/* FUS_t0_1 → P1；FUS_t0_2 → P2；FUS_t1_3 → P3 (track_segment 不同 = 新身份)。
 * 已用过的 track_id_fusion → 同 session doc 里已存在的 track_id。 */
var _tid_map = {};
function suggest_to_person_tid(engine_tid) {
    if (!engine_tid) return null;
    if (_tid_map[engine_tid]) return _tid_map[engine_tid];
    /* 找当前 doc 已用 P 标签最大编号 */
    var max = 0;
    Object.keys(S.doc ? S.doc.objects : {}).forEach(function (id) {
        var t = S.doc.objects[id].track_id;
        if (t && t[0] === "P") { var n = parseInt(t.slice(1), 10) || 0; max = Math.max(max, n); }
    });
    var out = "P" + (max + 1);
    _tid_map[engine_tid] = out;
    return out;
}
function reject_suggestion(idx) {
    var sugs = S.suggestions[String(S.current_frame)] || [];
    var c = sugs[idx];
    if (!c) return;
    doc_history_log("reject_suggestion", c, null);
    sugs.splice(idx, 1);
    mark_dirty();
    render_frame(S.current_frame);
}

/* 提交当前 pending shape —— 写入 doc */
/* PERF-JIT: 对象落盘时**不**立即存 raw_point_indices (5K 点 ROI * 1800 对象 = 60MB+)。
 * 运行时只存 ROI 形状 + class + track + z_range；真实点索引在 save/freeze/导出 时按需
 * 从本帧点云现选。这消掉 99% 的 RAM/GC churn — 点开 annotator / paste / undo 不再卡。
 * save_draft 或 service 冻结前需要先调用 inflate_doc_indices(S.doc)。 */
function inflate_doc_indices(doc, frame_idx_filter) {
    /* inflate 所有对象的 raw_point_indices/point_count (复用 per-frame 缓存)。 */
    if (!S.split || !S.frames) return 0;
    var n_inflated = 0;
    var frames_with = frame_idx_filter || Object.keys(doc.frames_objects).map(Number);
    for (var fi = 0; fi < frames_with.length; fi++) {
        var fidx = frames_with[fi];
        var ids = doc.frames_objects[String(fidx)] || [];
        for (var k = 0; k < ids.length; k++) {
            var o = doc.objects[ids[k]];
            if (!o || o._inflated || (o.raw_point_indices && o.point_count > 0)) continue;
            reselect_points_in_frame(o, fidx, S.z_min, S.z_max);
            o._inflated = 1;
            n_inflated++;
        }
    }
    return n_inflated;
}

function commit_selection(sel) {
    var obj = mk_object_from_selection(sel, "human");
    /* PERF-JIT: 标对象 提交不选点; 点索引 在 inflate 时生成 */
    delete obj.raw_point_indices; delete obj.point_count;
    doc_add(obj);
    S.last_edit_frame = S.current_frame;   /* V 取源: 上次"画"的帧, 不是 current_frame-1 */
    // DBG
    console.log("[commit]", obj.object_id, obj.class_name, "total objs:", Object.keys(S.doc ? S.doc.objects : {}).length,
        "frame objs:", (S.doc.frames_objects[String(S.current_frame)] || []).length);
    refresh_objects_panel();
    refresh_progress();
    render_frame(S.current_frame);
}
/* 公共: 形状 → 选区对象化（circle/rect/poly 走 GT.select_points，帧上下文当前帧）。
 * paste_frame 用: 传 frame_idx 参数→在那一帧重选点（否则用当前帧）。 */
function selection_of_shape(o, frame_idx) {
    if (o.polygon_xy) return { type: "poly", poly: o.polygon_xy };
    if (o.box_xy) return { type: "rect", x0: o.box_xy[0], y0: o.box_xy[1], x1: o.box_xy[2], y1: o.box_xy[3] };
    return { type: "circle", x: o.x, y: o.y, r_xy: o.r_xy };
}
function reselect_points_in_frame(o, frame_idx, z_min, z_max) {
    var rng = S.frame_compact_range;
    var beg = rng.begin[frame_idx], cnt = rng.cnt[frame_idx];
    var gm = S.frame_compact_map[frame_idx];
    var local_lev = new Float32Array(cnt * 3);
    for (var k = 0; k < cnt; k++) {
        var g = gm[k];
        local_lev[k * 3] = S.split.leveled_xyz[g * 3];
        local_lev[k * 3 + 1] = S.split.leveled_xyz[g * 3 + 1];
        local_lev[k * 3 + 2] = S.split.leveled_xyz[g * 3 + 2];
    }
    var sel = selection_of_shape(o);
    var idx = GT.select_points(local_lev, sel, z_min, z_max);
    /* FIX-R3-Q5b: 空 ROI 不静默覆旧索引（否则复制=到没点位置,冻结 400) */
    if (idx.length === 0 && o.raw_point_indices) {
        o._empty_roi_warning = 1;             /* 审计字段 */
        return o;                              /* 保留旧索引 */
    }
    o.raw_point_indices = GT.encode_indices(idx);
    o.point_count = idx.length;
    return o;
}

function mk_object_from_selection(sel, src) {
    /* 选点（用统一助手） */
    var shape_to_obj = { polygon_xy: null, box_xy: null, x: 0, y: 0, r_xy: 0 };
    if (sel.type === "poly") shape_to_obj.polygon_xy = sel.poly;
    else if (sel.type === "rect") shape_to_obj.box_xy = [sel.x0, sel.y0, sel.x1, sel.y1];
    else { shape_to_obj.x = sel.x; shape_to_obj.y = sel.y; shape_to_obj.r_xy = sel.r_xy; }
    var tmp = reselect_points_in_frame(shape_to_obj, S.current_frame, S.z_min, S.z_max);
    var local_idx = GT.decode_indices(tmp.raw_point_indices);
    var enc = tmp.raw_point_indices;
    var o = GT.make_object({
        session_id: S.sid,
        frame_idx: S.current_frame,
        timestamp: S.frames[S.current_frame].bag_time_sec,
        seq: S.frames[S.current_frame].seq || 0,
        object_id: GT.mk_object_id_unique(S.current_frame, ++S._oseq),   /* FIX: 同帧多对象不撞 id */
        shape: sel,
        class_name: "PERSON",            /* 默认人; 按 2家具/3背景/4未知 改 */
        z_min: S.z_min, z_max: S.z_max,
        raw_point_indices: enc,
        point_count: local_idx.length,
        source: src === "human" ? "human" : src === "model-suggested" ? "model" : "model",
        review_status: "unreviewed",
        annotator: S.annotator,
    });
    return o;
}

function set_class(c) {
    if (!S.selected) return;
    var o = S.doc.objects[S.selected];
    if (!o) return;
    var before = JSON.parse(JSON.stringify(o));
    S.undo = GT.undo_push(S.undo, GT.doc_snapshot_objects(S.doc));      /* FIX-R3-Q2 */
    o.class_name = c;
    o.source = "human";
    doc_history_log("set_class", before, o);
    mark_dirty();
    refresh_objects_panel();
    render_frame(S.current_frame);
}

/* FIX-AUDIT-Q2 + N1: 人工单对象 reviewed. source ∈ human|propagated 可 accept（传播对象
 * 的人在环确认是它的语义本质）；source=model 永不 G。 */
function mark_reviewed() {
    if (!S.selected) { hud_msg("先选对象", true); return; }
    var o = S.doc.objects[S.selected];
    if (!o) return;
    if (o.source === "model") { hud_msg("model 建议不可 reviewed", true); return; }
    var before = JSON.parse(JSON.stringify(o));
    S.undo = GT.undo_push(S.undo, GT.doc_snapshot_objects(S.doc));      /* FIX-R3-Q2 */
    o.review_status = "reviewed";
    doc_history_log("mark_reviewed", before, o);
    mark_dirty();
    refresh_objects_panel(); refresh_progress(); render_frame(S.current_frame);
}

/* FIX-AUDIT-Q2 + N1: 一键本帧所有 human|propagated 对象 reviewed */
function mark_frame_reviewed() {
    var objs = S.objects_by_frame[String(S.current_frame)] || [];
    if (!objs.length) { hud_msg("本帧无对象", true); return; }
    var before = JSON.parse(JSON.stringify(objs));
    S.undo = GT.undo_push(S.undo, GT.doc_snapshot_objects(S.doc));      /* FIX-R3-Q2 */
    objs.forEach(function (o) {
        if (o.source !== "model") o.review_status = "reviewed";
    });
    doc_history_log("mark_frame_reviewed", before, objs);
    mark_dirty();
    refresh_objects_panel(); refresh_progress(); render_frame(S.current_frame);
}

/* FIX-AUDIT-Q1: 播放 / 暂停 */
function toggle_play() {
    if (S.playing) {
        S.playing = false;
        if (S.play_timer) { clearInterval(S.play_timer); S.play_timer = null; }
        hud_msg("暂停", false);
    } else {
        S.playing = true;
        var fps = S.fps || 9.55;
        S.play_timer = setInterval(function () {
            if (S.current_frame < (S.frames ? S.frames.length - 1 : 0)) set_frame(S.current_frame + 1);
            else toggle_play();                          /* 播到头自动停 */
        }, Math.max(33, Math.round(1000 / fps)));
        hud_msg("播放 @ " + fps.toFixed(2) + " Hz", false);
    }
}

function assign_track_id() {
    var tid = prompt("Track ID (P1/P2/...)", (S.doc.objects[S.selected].track_id) || "P1");
    if (!tid) return;
    var o = S.doc.objects[S.selected];
    var before = JSON.parse(JSON.stringify(o));
    S.undo = GT.undo_push(S.undo, GT.doc_snapshot_objects(S.doc));      /* FIX-R3-Q2 */
    o.track_id = tid;
    o.source = "human";
    doc_history_log("assign_track", before, o);
    mark_dirty();
}

/* FIX-R3-Q2/Q6: K 只标记 当前选中 的对象不是全帧；list 里显示的 is_keyframe
 * 来源于 undo snapshot 可撤销 S.undo. 暂未加 un-K 键 — I 依赖 keyframe 定位,
 * 不要无 undo 路径的 toggle。 */
function mark_keyframe() {
    if (!S.selected) { hud_msg("先选对象再按 K", true); return; }
    var o = S.doc.objects[S.selected];
    if (!o) return;
    S.undo = GT.undo_push(S.undo, GT.doc_snapshot_objects(S.doc));
    o.is_keyframe = true;
    mark_dirty(); hud_msg("已设 " + o.object_id + " 为关键帧", false);
}

/* 复制到下一帧 = 一步传播（用统一助手重选点） */
function copy_to_next_frame() {
    if (!S.selected) return;
    var src = S.doc.objects[S.selected];
    var nxt = S.current_frame + 1;
    if (nxt >= S.frames.length) return;
    var clone = GT.propagate_object(src, nxt, S.frames[nxt].bag_time_sec, {});
    /* PERF-JIT: 不重选点 — 标记 _inflated=0, 后续 save 时 inflate */
    delete clone.raw_point_indices; delete clone.point_count; clone._inflated = 0;
    doc_add(clone);
    doc_history_log("propagate", src, clone);
    set_frame(nxt);
    refresh_objects_panel();
}

/* V: 粘贴"上次画的帧"全部对象副本——当帧人画了多个对象（比如 S9 双人 P1+P2）就一次都带来。
 * 取源优先级: S.last_edit_frame (rect/poly 提交或 nudge 时记录) → 否则退回 current_frame-1（兼容老习惯）。
 * 如果目标源就是当前帧，则视作无效操作不粘贴。
 * 副本 source=human（用户主动粘，不是自动传播）；review_status=unreviewed（仍须按 G/H 审）。
 * 若本帧已存在同 track_id 的对象（体系上 track 是唯一），则跳过不重复加。 */
function paste_from_prev_frame() {
    if (!S.sid) { hud_msg("未载入会话", true); return; }
    var src_f;
    if (S.last_edit_frame != null && S.last_edit_frame !== S.current_frame) {
        src_f = S.last_edit_frame;
    } else if (S.current_frame > 0) {
        src_f = S.current_frame - 1;
    } else {
        hud_msg("无源帧可粘（先画一帧）", true); return;
    }
    var prev_f = String(src_f);
    var prev_objs = S.objects_by_frame[prev_f] || [];
    if (!prev_objs.length) { hud_msg("源帧(" + src_f + ")无对象", true); return; }
    var cur_f = String(S.current_frame);
    var cur_objs = S.objects_by_frame[cur_f] || [];
    var cur_tids = {};
    cur_objs.forEach(function (o) { if (o.track_id) cur_tids[o.track_id] = 1; });
    /* FIX-R3-Q2: 批量压一次快照 → 整批 V/I 一条 undo */
    S.undo = GT.undo_push(S.undo, GT.doc_snapshot_objects(S.doc));
    var added = 0, skipped = 0;
    prev_objs.forEach(function (src) {
        if (src.track_id && cur_tids[src.track_id]) { skipped++; return; }
        var clone = JSON.parse(JSON.stringify(src));
        clone.object_id = GT.mk_object_id_unique(S.current_frame, ++S._oseq);   /* FIX-R3-Q1 */
        clone.frame_idx = S.current_frame;
        clone.frame_id = S.sid + ":" + S.current_frame;
        clone.timestamp = S.frames[S.current_frame].bag_time_sec;
        clone.parent_object_id = src.object_id;
        clone.source = "human";
        clone.review_status = "unreviewed";
        delete clone.is_keyframe;   /* FIX-R3-Q6 不再传染 */
        delete clone.raw_point_indices; delete clone.point_count; clone._inflated = 0;
        /* FIX-R3-Q2: 循环内 skip_undo_push（整批已压外圈） */
        doc_add(clone, /*skip_undo_push*/true);
        doc_history_log("paste_from_prev", src, clone);
        added++;
    });
    if (added === 0) { hud_msg("本帧已有同 track 对象(" + skipped + " 个)——未粘贴", true); return; }
    hud_msg("从帧 " + src_f + " 粘贴 " + added + " 个对象(跳过重 track " + skipped + ")", false);
    S.last_edit_frame = S.current_frame;   /* 粘完,目的地成为新源 */
    refresh_objects_panel(); refresh_progress(); render_frame(S.current_frame);
}

/* I: 在当前帧附近找 最近的 keyframe(前) 和 keyframe(后) 之间的所有帧，按 track_id
 * 对 pair，用 interpolate_shapes 线性插值 ROI，逐帧加 ROI（source=propagated, unreviewed）。
 * 规则：
 *   1. 必须前后都 有 K 帧（同 track_id 出现在两侧 keyframe）才插；找不到或单人只标一侧 → 拒绝。
 *   2. 双人交叉 S9：不会替「谁是谁」决定；只按 track_id 一对一配对（P1↔P1, P2↔P2）。
 *   3. 中间已经有对象的帧跳过（不覆盖）。
 *   4. 插完后按 1/2/H 手工逐帧审 — propagated + unreviewed 不会自动成 GT。 */
function interpolate_between_keyframes() {
    if (!S.doc || !S.frames) return;
    var cur = S.current_frame;
    var kf_before = null, kf_after = null;
    for (var i = cur - 1; i >= 0; i--) {
        var objs = S.objects_by_frame[String(i)] || [];
        if (objs.some(function (o) { return o.is_keyframe; })) { kf_before = i; break; }
    }
    for (var j = cur + 1; j < S.frames.length; j++) {
        var objs2 = S.objects_by_frame[String(j)] || [];
        if (objs2.some(function (o) { return o.is_keyframe; })) { kf_after = j; break; }
    }
    if (kf_before == null || kf_after == null) {
        hud_msg("需前后各一个关键帧(K 键标记)才能插值", true); return;
    }
    var gap = kf_after - kf_before - 1;
    if (gap <= 0) { hud_msg("两关键帧间无中间帧", true); return; }

    /* 建立 track_id → {src_obj, dst_obj} 对 */
    var before_objs = S.objects_by_frame[String(kf_before)] || [];
    var after_objs = S.objects_by_frame[String(kf_after)] || [];
    var pairs = [];
    before_objs.forEach(function (sb) {
        if (!sb.is_keyframe) return;
        /* dst 同 track_id 的 keyframe；无 track_id（家具）也允许一对一 */
        var match = after_objs.filter(function (sa) {
            if (!sa.is_keyframe) return false;
            if (sb.track_id && sa.track_id) return sb.track_id === sa.track_id && sb.class_name === sa.class_name;
            return sb.class_name === sa.class_name && !sa.track_id;
        })[0];
        if (match) pairs.push({ src: sb, dst: match });
    });
    if (!pairs.length) { hud_msg("两 K 帧无可配对 track/class", true); return; }

    /* FIX-R3-Q2: 批量插值 压一次 大 快照 */
    S.undo = GT.undo_push(S.undo, GT.doc_snapshot_objects(S.doc));

    var inserted = 0, skipped_frame = 0;
    for (var fi = kf_before + 1; fi < kf_after; fi++) {
        var existing = S.objects_by_frame[String(fi)] || [];
        /* 本帧已有这些 track_id 的对象 → 跳过 */
        var have_tids = {};
        existing.forEach(function (o) { if (o.track_id) have_tids[o.track_id] = 1; });
        pairs.forEach(function (p) {
            if (p.src.track_id && have_tids[p.src.track_id]) return;
            var gap_pos = fi - kf_before;   /* 1..gap */
            var out = GT.interpolate_shapes(GT.shape_of_object(p.src), GT.shape_of_object(p.dst), gap);
            if (!out.length) return;                       /* 形状不兼容 */
            var shp = out[gap_pos - 1];
            /* 用 mk_object 产对象（source=propagated, unreviewed） */
            var sel_rect_or_poly_or_circle = shp.type === "rect"
                ? { type: "rect", x0: shp.x0, y0: shp.y0, x1: shp.x1, y1: shp.y1 }
                : shp.type === "poly" ? { type: "poly", poly: shp.poly }
                : { type: "circle", x: shp.x, y: shp.y, r_xy: shp.r_xy };
            /* 创建对象先走 make_object（不选点）再 reselect */
            var o = GT.make_object({
                session_id: S.sid,
                frame_idx: fi,
                timestamp: S.frames[fi].bag_time_sec,
                seq: S.frames[fi].seq | 0,
                object_id: GT.mk_object_id_unique(fi, ++S._oseq),     /* FIX-R3-Q1 */
                shape: sel_rect_or_poly_or_circle,
                class_name: p.src.class_name,
                z_min: p.src.z_min, z_max: p.src.z_max,
                raw_point_indices: ["s"],     /* 占位：下步重选点重写 */
                point_count: 1,
                source: "propagated",
                review_status: "unreviewed",
                annotator: S.annotator,
                track_id: p.src.track_id || null,
            });
            /* 形状更新到插值后的 ROI 中心 */
            if (shp.type === "circle") { o.x = shp.x; o.y = shp.y; o.r_xy = shp.r_xy; }
            if (shp.type === "rect") o.box_xy = [shp.x0, shp.y0, shp.x1, shp.y1];
            if (shp.type === "poly") o.polygon_xy = shp.poly;
            o.interpolated_from = { from_frame: kf_before, to_frame: kf_after, track_id: p.src.track_id };
            /* PERF-JIT: interpolate 不重选点；save 时 1850 个对象统一 inflate */
            delete o.raw_point_indices; delete o.point_count; o._inflated = 0;
            doc_add(o, /*skip_undo_push*/true);
            doc_history_log("interpolate", { src_kf: kf_before, dst_kf: kf_after, track: p.src.track_id }, o);
            inserted++;
        });
        if (existing.length) skipped_frame++;
    }
    hud_msg("插值完成: 插入 " + inserted + " 个 ROI (kf" + kf_before + "→kf" + kf_after + ", " + pairs.length + " 组 track)",
        false);
    refresh_objects_panel(); refresh_progress(); render_frame(S.current_frame);
}

/* WASD 移动当前选中对象的 ROI。226 步=像素对应值(1px=1/scale px/m 米)，
 * Shift 加速 ×10。移动后重选点 → 永远是对象的真实点集。 */
/* FIX-R3-Q2: 快照压 undo（一次 nudge 一条，undo 可逐步退回） */
function nudge_selected(dx_px, dy_px, scale) {
    if (!S.selected) return false;
    var o = S.doc.objects[S.selected];
    if (!o) return false;
    scale = scale || 0.05;                        /* 默认 5cm 一次 */
    /* FIX-R3-Q5a: 重选点用对象所在帧(irrespective 视口在哪帧),
     * 否则跨帧选中的 ROI 会被"当前帧点云"误覆, 索引错位. */
    S.undo = GT.undo_push(S.undo, GT.doc_snapshot_objects(S.doc));
    GT.translate_shape(o, dx_px * scale, dy_px * scale);
    /* PERF-JIT: ROI 移动 → 使已 inflate 的状态失效，下次 save 重新选 */
    o._inflated = 0;
    S.last_edit_frame = S.current_frame;   /* 微调也算"画了" */
    mark_dirty();
    refresh_objects_panel(); render_frame(S.current_frame);
    return true;
}

/* 断点提示弹窗（两人交叉用） */
function show_breaks_dialog() {
    var tids = [];
    Object.keys(S.doc.objects).forEach(function (id) {
        var t = S.doc.objects[id].track_id;
        if (t && tids.indexOf(t) < 0) tids.push(t);
    });
    var breaks = GT.find_breaks(S.doc.frames_objects, tids);
    alert("轨迹断点: " + breaks.length + " 处\n" +
        breaks.slice(0, 8).map(function (b) {
            return "  帧 " + b.frame + " " + b.kind + (b.track_id ? (" [" + b.track_id + "]") : "");
        }).join("\n"));
}

/* undo / redo */
function do_undo() {
    var r = GT.undo_undo(S.undo, GT.doc_snapshot_objects(S.doc));
    if (!r.objects) return;
    S.undo = r.stack;
    restore_snapshot(r.objects);
}
function do_redo() {
    var r = GT.undo_redo(S.undo, GT.doc_snapshot_objects(S.doc));
    if (!r.objects) return;
    S.undo = r.stack;
    restore_snapshot(r.objects);
}
function restore_snapshot(snap) {
    /* 从 frame map 快照重建 doc.objects（对象本体已被快照） */
    var objs = {};
    Object.keys(snap).forEach(function (f) { snap[f].forEach(function (o) { objs[o.object_id] = o; }); });
    S.doc.objects = objs;
    S.doc.frames_objects = {};
    Object.keys(snap).forEach(function (f) { S.doc.frames_objects[f] = snap[f].map(function (o) { return o.object_id; }); });
    S.objects_by_frame = snap;
    mark_dirty();
    refresh_objects_panel(); refresh_progress();
}

function set_frame(i) {
    if (!S.frames) return;
    i = Math.max(0, Math.min(S.frames.length - 1, i));
    S.current_frame = i;
    S.rect_p0 = null; S.pending_poly = [];
    render_frame(i);
}

// ---------------- 持久化 ----------------
function save_draft() {
    if (!S.doc) { hud_msg("无 doc", true); return; }
    /* PERF-JIT: 落盘前 inflate 所有 raw_point_indices — 服务端要真点索引持久化;
     * 这一步会扫 1830 对象×49k 点/帧 ≈ 5-10 秒，比之前 undo 操作时的多次 78MB 拷贝快得多 */
    var n_inflated = inflate_doc_indices(S.doc);
    /* _inflated 是运行时标记，不进 JSON；删除防止污染 */
    Object.keys(S.doc.objects).forEach(function (id) {
        delete S.doc.objects[id]._inflated;
        delete S.doc.objects[id]._empty_roi_warning;
    });
    var payload = {
        sid: S.sid,
        doc: S.doc,
        expected_sha: S.save_sha,
    };
    fetch("/api/gt/save", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    }).then(function (r) { return r.json(); })
        .then(function (r) {
            if (!r.ok) { hud_msg("保存失败: " + r.error, true); return; }
            S.save_sha = r.sha256;
            S.dirty = false;
            hud_msg("已保存 (sha=" + r.sha256.slice(0, 12) + ", " + r.n_objects + " 对象)", false);
        })
        .catch(function (e) { hud_msg("网络错误: " + e.message, true); });
}

function freeze() {
    var annotator = prompt("冻结签署人 (annotator id)", S.annotator || "annotator-1");
    if (!annotator) return;
    fetch("/api/gt/freeze", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sid: S.sid, annotator: annotator }),
    }).then(function (r) { return r.json(); })
        .then(function (r) {
            if (!r.ok) { hud_msg("冻结失败: " + r.error, true); if (r.errors) alert(r.errors.join("\n")); return; }
            hud_msg("冻结版 " + r.version + " sha=" + r.sha256.slice(0, 12), false);
            load_session(S.sid);   /* 刷新 frozen list */
        })
        .catch(function (e) { hud_msg("网络错误: " + e.message, true); });
}

function export_json() {
    fetch("/api/gt/export?sid=" + encodeURIComponent(S.sid) + "&name=manifest.json")
        .then(function (r) { return r.json(); })
        .then(function (r) {
            if (!r.ok) { hud_msg("导出失败: " + r.error, true); return; }
            var url = "data:application/json;charset=utf-8," + encodeURIComponent(JSON.stringify(r.doc, null, 1));
            var a = document.createElement("a");
            a.href = url;
            a.download = S.sid + "_manifest.json";
            a.click();
        });
}

function run_auto_suggest() {
    if (!S.sid) return;
    hud_msg("正在跑 fusion 预标（慢）…", false);
    fetch("/api/gt/auto", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sid: S.sid }),
    }).then(function (r) { return r.json(); })
        .then(function (r) {
            if (!r.ok) { hud_msg("auto 预标失败: " + r.error, true); return; }
            S.suggestions = r.frames;
            hud_msg("auto 预标 OK, " + Object.keys(r.frames).length + " 帧有候选", false);
            render_frame(S.current_frame);
        })
        .catch(function (e) { hud_msg("auto 网络错误: " + e.message, true); });
}

// ---------------- 初始化 ----------------
function init_sessions_dropdown() {
    var sel = document.getElementById("sid_select");
    var sessions = (S.session_info || {}).sessions || [];
    /* 默认硬编码 9 个 work-order 会话（与 CADENCE_HINT 对齐）作为离线回退；
     * 能从 /api/sessions?scope=local 拉到就用动态清单——板端模式下 staging 的会话
     * 会全部出现（不只这 9 个），PC 侧有额外本地会话也出现。 */
    var FALLBACK_ORDER = [
        "cap_20261010_175227", "cap_20261010_180557", "cap_20261010_180751",
        "cap_20261010_175429", "cap_20261010_175553", "cap_20261010_175804",
        "cap_20261010_175943", "cap_20261010_180235", "cap_20261010_180337",
    ];
    /* 从 /api/sessions?scope=local 拿会话名 (板端模式下 scope=local 语义已在服务端映射为 staging)。
     * 用户说 "我不是给会话取名字了嘛" —— 用 display name 而不只是 sid。 */
    fetch("/api/sessions?scope=local").then(function (r) { return r.json(); }).then(function (all) {
        var list = (all.sessions || []).slice();
        if (list.length) {
            /* 本地文件顺序：FALLBACK_ORDER 优先（保 CADENCE 提示关联），其余按 created 日期倒序 */
            var in_order = {}, opts = [], extras = [];
            FALLBACK_ORDER.forEach(function (s) { in_order[s] = true; });
            list.forEach(function (s) {
                /* FIX-PERF-R2: 把 points.bin 大小放进下拉 label — 选会话前预估加载时间 */
                var mb = s.bytes ? (s.bytes / 1048576).toFixed(0) : "?";
                var row = { sid: s.sid, name: s.name || s.sid,
                            label: (s.name || s.sid) + " · " + s.sid.replace("cap_2026", "") +
                                   " · " + (s.frames || "?") + "f · " + mb + "MB" };
                if (in_order[s.sid]) opts[FALLBACK_ORDER.indexOf(s.sid)] = row;
                else extras.push(row);
            });
            extras.sort(function (a, b) { return b.sid.localeCompare(a.sid); });
            var rows = opts.filter(Boolean).concat(extras);
            rows.forEach(function (row) {
                var opt = document.createElement("option");
                opt.value = row.sid;
                opt.textContent = row.label;
                sel.appendChild(opt);
            });
        } else {
            FALLBACK_ORDER.forEach(function (sid) {
                var opt = document.createElement("option");
                opt.value = sid;
                opt.textContent = sid;
                sel.appendChild(opt);
            });
        }
    }).catch(function () {
        FALLBACK_ORDER.forEach(function (sid) {
            var opt = document.createElement("option");
            opt.value = sid;
            opt.textContent = sid;
            sel.appendChild(opt);
        });
    });
    sel.onchange = function () {
        var v = sel.value;
        if (v) load_session(v);
    };
}

window.addEventListener("DOMContentLoaded", function () {
    canvas = document.getElementById("view");
    ctx = canvas.getContext("2d");
    hud = document.getElementById("hud");
    prog = document.getElementById("progress");
    side = document.getElementById("side");

    /* FIX-OPS: GT/SYNC/REC/RENAME 操作层。绑定到本页的容器后由 GT_OPS 全权处理 fetch+UI。 */
    var _ops = GT_OPS && GT_OPS.bind({
        els: {
            noteEl: document.getElementById("ops_note"),
            renameInput: document.getElementById("rename_input"),
            renameOk: document.getElementById("rename_ok"),
            renameCancel: document.getElementById("rename_cancel"),
            aliasDraftBtn: document.getElementById("alias_btn"),
            aliasVersionRefresh: null,
            pullBtn: document.getElementById("pull_btn"),
            recBtn: document.getElementById("rec_btn"),
            frozenListEl: document.getElementById("frozen_list"),
        },
        get_session_info: function () { return S.session_info; },
        reload_session: function (sid) { load_session(sid); },
        after_pull_ok: function () { /* 成功后刷新一次下拉，若当前 sid 已在板上也刷新本身 */
            var cur = S.sid;
            var opt = document.querySelector("#sid_select option[value='" + cur + "']");
            if (cur && opt) load_session(cur);
        },
        set_alias_on_version: function (ver) {
            /* FIX-REVIEW-L3: 委托路径也要 catch（未 catch 会成 unhandled rejection）。 */
            var fail = function (e) {
                var msg = (e && e.message) || String(e);
                hud_msg("别名写失败: " + msg, true);
            };
            if (ver === "__draft__") {
                var info = S.session_info || {};
                var cur = info.draft_alias || "";
                var v = prompt("draft 显示名（空 = 清除）", cur);
                if (v == null) return;
                return _ops && _ops.set_alias(info.sid, "draft", null, v).then(function () {
                    load_session(info.sid);
                }).catch(fail);
            }
            var info2 = S.session_info || {};
            var aliases = info2.version_aliases || {};
            var curv = aliases[ver] || "";
            var vv = prompt(ver + " 显示名（空 = 清除）", curv);
            if (vv == null) return;
            return _ops && _ops.set_alias(info2.sid, "version", ver, vv).then(function () {
                load_session(info2.sid);
            }).catch(fail);
        },
    });
    /* rename_btn 只是控制 rename_row 的开合（不直接发请求） */
    var rename_btn = document.getElementById("rename_btn");
    var rename_row = document.getElementById("ops_rename_row");
    var rename_cancel = document.getElementById("rename_cancel");
    if (rename_btn && rename_row) {
        rename_btn.addEventListener("click", function () {
            var cur = (S.session_info && S.session_info.display_name) || "";
            var input = document.getElementById("rename_input");
            if (input) input.value = cur;
            rename_row.style.display = rename_row.style.display === "none" ? "" : "none";
            if (rename_row.style.display !== "none" && input) input.focus();
        });
    }
    if (rename_cancel && rename_row) {
        rename_cancel.addEventListener("click", function () {
            rename_row.style.display = "none";
        });
    }
    var rename_input = document.getElementById("rename_input");
    if (rename_input) {
        rename_input.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape") { rename_row.style.display = "none"; }
            else if (ev.key === "Enter") {
                ev.preventDefault();
                var ok = document.getElementById("rename_ok");
                if (ok) ok.click();
            }
        });
    }

    /* FIX-OPS: 周期性刷新板端录制状态（与 panel.js 的 5s 芯片节奏对齐）。 */
    var _ops_poll = setInterval(function () { _ops && _ops.refresh_board_status(); }, 5000);

    canvas.addEventListener("mousedown", on_canvas_mousedown);
    canvas.addEventListener("mousemove", on_canvas_mousemove);
    canvas.addEventListener("dblclick", on_canvas_dblclick);
    window.addEventListener("mouseup", on_canvas_mouseup);
    canvas.addEventListener("wheel", on_canvas_wheel, { passive: false });
    window.addEventListener("keydown", on_keydown);
    /* 右键: context menu 拦截 + 失焦/离画布都停 */
    canvas.addEventListener("contextmenu", function (ev) { ev.preventDefault(); });
    canvas.addEventListener("mouseleave", on_canvas_mouseleave);

    document.getElementById("save_btn").onclick = save_draft;
    document.getElementById("freeze_btn").onclick = freeze;
    document.getElementById("export_btn").onclick = export_json;
    document.getElementById("auto_btn").onclick = run_auto_suggest;
    document.getElementById("frame_slider").addEventListener("input", function (e) {
        set_frame(parseInt(e.target.value, 10) || 0);
    });
    document.getElementById("prev_frame").onclick = function () { set_frame(S.current_frame - 1); };
    document.getElementById("next_frame").onclick = function () { set_frame(S.current_frame + 1); };
    document.getElementById("prev_frame_25").onclick = function () { set_frame(S.current_frame - 25); };
    document.getElementById("next_frame_25").onclick = function () { set_frame(S.current_frame + 25); };
    document.getElementById("z_min").addEventListener("input", function (e) {
        S.z_min = parseFloat(e.target.value);
        if (S.live.active) _render_live_frame(); else render_frame(S.current_frame);
    });
    document.getElementById("z_max").addEventListener("input", function (e) {
        S.z_max = parseFloat(e.target.value);
        if (S.live.active) _render_live_frame(); else render_frame(S.current_frame);
    });
    /* live 进入 / 退出 */
    var live_btn = document.getElementById("live_btn");
    if (live_btn) live_btn.addEventListener("click", function () { enter_live(); });
    var live_close = document.getElementById("live_close");
    if (live_close) live_close.addEventListener("click", function () { exit_live(); });
    document.getElementById("annotator_input").addEventListener("change", function (e) {
        S.annotator = e.target.value || null;
        if (S.doc) S.doc.annotator = S.annotator;
        mark_dirty();
    });

    /* DBG: 让 iframe 里 S 可从 console 查看 (诊断多 poly 不保存问题) */
    if (typeof window !== "undefined") window.S = S;

    /* 建议操作面板（事件委托） */
    document.getElementById("suggestions_panel").addEventListener("click", function (e) {
        var action = e.target.getAttribute("data-action");
        if (!action) return;
        var idx = parseInt(e.target.getAttribute("data-idx"), 10);
        if (action === "accept") accept_suggestion(idx);
        else if (action === "reject") reject_suggestion(idx);
    });

    window.addEventListener("resize", function () {
        canvas.width = canvas.clientWidth; canvas.height = canvas.clientHeight;
        S.view.vw = canvas.width; S.view.vh = canvas.height;
        if (S.live.active) _render_live_frame(); else render_frame(S.current_frame);
    });
    canvas.width = canvas.clientWidth; canvas.height = canvas.clientHeight;
    S.view.vw = canvas.width; S.view.vh = canvas.height;

    init_sessions_dropdown();

    /* URL 参数路由：?sid=X 优先进会话；否则默认进实时模式（不黑屏）;
     * ?live=0 显式关闭（罕见：避免浏览器反复重连）。 */
    var qs = new URLSearchParams(location.search);
    var sid = qs.get("sid");
    var live_qs = qs.get("live");
    if (sid) {
        load_session(sid);
    } else if (live_qs === "0") {
        hud_msg("选会话开始（默认实时已被 ?live=0 关闭）", false);
    } else {
        /* 默认 live：用户开 GT 台先看现场，标注会话才需要选会话 */
        enter_live();
    }
});

/* 建议面板挂载函数（按帧重渲染；从 render_frame 里调用） */
function refresh_suggestions_panel() {
    var sugs = S.suggestions[String(S.current_frame)] || [];
    var el = document.getElementById("suggestions_panel");
    if (!el) return;
    if (!sugs.length) { el.innerHTML = "<i>本帧无建议</i>"; return; }
    el.innerHTML = sugs.map(function (c, i) {
        /* 用户看到能区分"这是哪个对象": #N(右面板) = #N(画布标号) 一一对应;
         * track_id (FUS_t0_1) 在大字位置；坐标+置信度 在小字位。 */
        var tid = c.track_id || ("cand");
        var num = "#" + (i + 1);
        var loc = "(" + c.x.toFixed(2) + "," + c.y.toFixed(2) + ") r=" + (c.r_xy || 0).toFixed(2);
        var conf = (c.confidence != null ? c.confidence.toFixed(2) : "—");
        return "<div class='sug_row'>" +
            "<div class='sug_main'>" +
              "<b>" + num + " " + tid + "</b> <span class='sug_loc'>" + loc + "</span>" +
              " <span class='sug_conf'>" + conf + "</span>" +
            "</div>" +
            "<div class='sug_ops'>" +
              "<button data-action='accept' data-idx='" + i + "'>接受</button>" +
              "<button data-action='reject' data-idx='" + i + "'>拒</button>" +
            "</div>" +
            "</div>";
    }).join("");
}
