/* fresh_overlay.js — FRESH-MAP M2 浏览器叠加层（纯 UI 适配器，算法全在 fresh_lib.js）。
 *
 * 挂 replay.js 的 HUMAN_DETECT_OVERLAY 钩子（契约 = notify_session/reset/attach_color/
 * set_leveled_in_s/on_frame，同 detect_overlay.js），把当前帧每点染色：
 *   HOT   = heat_rgb(f)（亮黄白，f→0 渐暗 = 用户要的"渐黑"）
 *   GHOST = 暗蓝（曾动后停，候选保留）
 *   COLD_BG = 灰度（长期不动背景）
 *   带外(z) = 近黑
 * 无删除权：全部点都画，只改颜色。参考图 = 外部空场目录 或 本会话前 warmN 帧自 warmup。
 * replay.js 已把 REF_RT 配平就地写进 S.buf_f32（/api/leveling 成功时 set_leveled_in_s(true)）；
 * file:// 手动选目录时配平失败 → 本层对逻辑坐标自乘 REF_RT（同 detect_overlay 语义），
 * 渲染本身仍是原始系（视觉略歪不影响判读新鲜度行为）。
 */
(function () {
    "use strict";
    var R = [0.893544, 0.0, 0.448975, -0.014337, 0.99949, 0.028533, -0.448746, -0.031932, 0.893089];
    var T = [0.0, 0.0, 1.380286];
    /* r8 亮度层级：热白(HOT认领) ≫ 中蓝(GHOST认领) > 弱蓝(超寿但被锚点认领=人还在这)
     * > 暗青(裸证据) ≈ 远蓝(裸残影) ≈ 背景黑 */
    var C_CLAIM = [0.16, 0.45, 0.75], C_CLAIM_DIM = [0.06, 0.16, 0.26],
        C_GHOST = [0.05, 0.07, 0.18],
        C_BG = [0.055, 0.055, 0.07], C_OUT = [0.03, 0.03, 0.035];
    /* 未认领证据压到雾感以下：密集堆叠后仍远暗于认领对象（r5 截图自验再降一档） */
    function _dim_cyan(f) { var w = f * f; return [0.05 * w, 0.17 * w + 0.03, 0.21 * w + 0.04]; }

    var st = null, mem = null, refPack = null, refDesc = "self-warmup40", referenceSource = null;
    var gen = 0, colorBuf = null, leveled_in_s = false, warmN = 40;
    var lastRep = null, lastCand = 0, lastClusters = 0, lastClaims = 0, lastLive = 0;
    var lowKeys = new Set(), lastLow = 0;
    var pipelineMode = "legacy", perceptionOptions = {}, perception = null, currentAudit = null;
    var currentSourceRows = [], claimedRows = new Set();
    var cpuSamples = [];
    var paint_stats = { claim_hot: 0, claim_cool: 0, dim_hot: 0, ghost: 0, bg: 0, out: 0 };

    function _libs() {
        return { F: globalThis.fresh_map_lib, P: globalThis.human_pipe_lib };
    }
    function _frame_xyzi(S, idx) {
        var P = _libs().P, f = S.meta.frames[idx];
        var start = f.offset_points | 0, count = f.count_points | 0;
        var raw = new Float32Array(count * 4);
        var already = leveled_in_s || !!(S.meta && S.meta.leveling);
        for (var k = 0; k < count; k++) {
            var o = (start + k) * 7;
            var x = S.buf_f32[o], y = S.buf_f32[o + 1], z = S.buf_f32[o + 2];
            if (!already) {
                var lx = R[0] * x + R[1] * y + R[2] * z + T[0];
                var ly = R[3] * x + R[4] * y + R[5] * z + T[1];
                var lz = R[6] * x + R[7] * y + R[8] * z + T[2];
                x = lx; y = ly; z = lz;
            }
            raw[k * 4] = x; raw[k * 4 + 1] = y; raw[k * 4 + 2] = z; raw[k * 4 + 3] = S.buf_f32[o + 3];
        }
        currentSourceRows = [];
        for (var j = 0; j < count; j++) {
            var q = j * 4, r2 = raw[q] * raw[q] + raw[q + 1] * raw[q + 1] + raw[q + 2] * raw[q + 2];
            if (Number.isFinite(r2) && r2 >= P.PIPE.range_min_m * P.PIPE.range_min_m &&
                r2 <= P.PIPE.range_max_m * P.PIPE.range_max_m) currentSourceRows.push(start + j);
        }
        return P.denoise(raw);
    }
    /* r4：页面挂 M1 冻结选组（10_SELECT.json evconf3），不用默认 conf=2 */
    var SEL = { ev_confirm_frames: 3 };
    /* r5：渲染认领要求"新鲜确认"（≤2s 内有簇过门续命），防僵尸锚点误导目视；
     * FreshMemory 本体不动（M1 数字口径不变），只是展示层收紧。 */
    var CLAIM_FRESH_FRAMES = 20;
    function _live_fresh(mem, frame_index) {
        var out = [];
        var all = _libs().F.mem_live(mem);
        for (var i = 0; i < all.length; i++)
            if (frame_index - all[i].frame_index <= CLAIM_FRESH_FRAMES) out.push(all[i]);
        return out;
    }
    /* 低姿只续接已确认站姿，绝不创建身份。沿用0.4m关联半径和2s显示失联窗。
     * ponytail: 单目标邻域须无歧义；分裂/并人时拒接，后续需要身份GT再换关联器。 */
    function _continuations(rows, live, standing, frame_index, t) {
        var r2 = st.o.retention.hot_cell_radius_m * st.o.retention.hot_cell_radius_m;
        function near(a, b) { var dx = a.x - b.cx, dy = a.y - b.cy; return dx * dx + dy * dy < r2; }
        var matches = [];
        rows.forEach(function (row) {
            var f = row.f;
            if (!f.ok || f.height_m < 0.2 || f.height_m > 1.2 || f.zmax > 1.3 ||
                f.radius_m > _libs().P.PIPE.track_gate_xy_m ||
                row.evidenceN < _libs().P.PIPE.human_n_min || row.evidenceN < f.n * 0.5) return;
            var parents = live.filter(function (a) {
                return frame_index > a.frame_index && frame_index - a.frame_index <= CLAIM_FRESH_FRAMES &&
                    t >= a.timestamp && t - a.timestamp <= 2 && near(a, f) &&
                    a.standing_z - f.cz >= 0.25 && a.standing_height - f.height_m >= 0.25;
            });
            if (parents.length === 1 && !mem.anchors.some(function (a) { return a !== parents[0] && near(a, f); }) &&
                !standing.some(function (c) { return near(parents[0], c); }))
                matches.push({ row: row, anchor: parents[0] });
        });
        return matches.filter(function (m) {
            return matches.filter(function (n) { return n.anchor === m.anchor; }).length === 1;
        });
    }
    function _ensure_state(S) {
        var L = _libs();
        if (st) return;
        var ref = refPack;
        if (!ref) {   /* 自 warmup：本会话前 warmN 帧建不可变参考图 */
            var fr = [];
            var n = Math.min(warmN, S.meta.frames.length);
            for (var i = 0; i < n; i++) fr.push(_frame_xyzi(S, i));
            ref = L.F.build_reference(fr, {});
            refDesc = "self-warmup" + n;
        }
        st = L.F.create_fresh_state(ref, SEL);
        mem = L.F.FreshMemory(SEL);
    }
    /* r4 分层语义（用户"别把桌角当人"反馈）：
     *   亮白/亮青蓝 = live 人形锚点（过 classify_human 几何门 + 3 帧连续）半径内 —— "对象"
     *   淡青        = 未认领 HOT（原始运动/新占用证据，含近距振动噪点）—— "证据"
     *   暗蓝        = 未认领 GHOST；近黑 = 背景/带外。证据永不冒充对象。 */
    function _paint(S, live) {
        var F = _libs().F, P = _libs().P, K = P.key_bg;
        var f = S.meta.frames[S.idx];
        var start = f.offset_points | 0, count = f.count_points | 0;
        var ar2 = st.o.retention.hot_cell_radius_m * st.o.retention.hot_cell_radius_m;
        for (var k = 0; k < count; k++) {
            var o = (start + k) * 7;
            var x = S.buf_f32[o], y = S.buf_f32[o + 1], z = S.buf_f32[o + 2];
            if (!(leveled_in_s || S.meta.leveling)) {
                var lx = R[0] * x + R[1] * y + R[2] * z + T[0];
                var ly = R[3] * x + R[4] * y + R[5] * z + T[1];
                var lz = R[6] * x + R[7] * y + R[8] * z + T[2];
                x = lx; y = ly; z = lz;
            }
            var c, s = F.point_state(st, x, y, z);
            var v = st.voxels.get(K(x, y, z));
            var lowClaim = lowKeys.has(P.key_vox(x, y)) && v && !v.ref_sup && v.ever_event;
            if (s === "OUT_OF_BAND") { c = C_OUT; paint_stats.out++; }
            else if (pipelineMode !== "legacy") {
                if (claimedRows.has(start + k)) {
                    c = s === "HOT" ? F.heat_rgb(1) : C_CLAIM;
                    paint_stats[s === "HOT" ? "claim_hot" : "claim_cool"]++;
                } else if (s === "HOT") { c = _dim_cyan(v.f); paint_stats.dim_hot++; }
                else if (s === "GHOST") { c = C_GHOST; paint_stats.ghost++; }
                else { c = C_BG; paint_stats.bg++; }
            }
            else if (lowClaim) {
                c = s === "HOT" ? F.heat_rgb(1.0) : C_CLAIM;
                paint_stats[s === "HOT" ? "claim_hot" : "claim_cool"]++;
            }
            else {
                var claimed = false;
                for (var li = 0; li < live.length; li++) {
                    var dx = live[li].x - x, dy = live[li].y - y;
                    if (dx * dx + dy * dy <= ar2) { claimed = true; break; }
                }
                /* 认领只点亮 HOT/GHOST；半径内 COLD_BG 背景格保持沉黑
                 * （r6 截图数据定罪：0.4m 盘内柜子被 claim_cool 误点亮 = 用户"别把旁边当人"） */
                if (claimed && (s === "HOT" || s === "GHOST")) {
                    if (s === "HOT") { c = F.heat_rgb(1.0); paint_stats.claim_hot++; }
                    else { c = C_CLAIM; paint_stats.claim_cool++; }
                }
                else if (claimed) { c = C_CLAIM_DIM; paint_stats.claim_cool++; }
                else if (s === "HOT") { c = _dim_cyan(st.voxels.get(K(x, y, z)).f); paint_stats.dim_hot++; }
                else if (s === "GHOST") { c = C_GHOST; paint_stats.ghost++; }
                else { c = C_BG; paint_stats.bg++; }
            }
            var b = (start + k) * 3;
            colorBuf[b] = c[0]; colorBuf[b + 1] = c[1]; colorBuf[b + 2] = c[2];
        }
        if (S.geo.attributes.color.updateRange) {
            S.geo.attributes.color.updateRange.offset = start * 3;
            S.geo.attributes.color.updateRange.count = count * 3;
        }
        S.geo.attributes.color.needsUpdate = true;
    }
    function _hud() {
        if (typeof document === "undefined") return;
        var el = document.getElementById("freshHud");
        if (!el || !lastRep) return;
        el.textContent = (colorMissing ? "⚠高亮未生效：颜色缓冲未挂接 · " : "") +
            "人物高亮 · 目标 " + lastLive + " · 低姿保持 " + lastLow +
            " · 空场 " + refDesc + " · 亮白/蓝=已认领，暗青=运动痕迹";
        if (pipelineMode !== "legacy" && currentAudit) {
            var names = {STANDING:"站立",LOW:"低姿",LYING:"躺卧",FALL_CANDIDATE:"疑似跌倒（待核实）",RECOVERING:"恢复中",UNKNOWN:"未知"};
            var poses = currentAudit.tracks.filter(function(a){return a.confirmed;}).map(function(a){return "#"+a.id+" "+
                (a.last_frame===currentAudit.frame?(names[a.posture]||"未知"):"暂失");});
            var unverified = currentAudit.tracks.filter(function(a){return !a.confirmed;}).length;
            el.textContent = "传统感知v2（" + (pipelineMode==="xy"?"XY":"3D") + "）· 人体候选 " + lastLive + " · " + (poses.join(" / ") || "暂无确认目标") +
                (unverified?" · 待核实 " + unverified:"") +
                " · 空场 " + refDesc + (Number.isFinite(currentAudit.reference_support) && currentAudit.reference_support < perception.cfg.reference_min_support ? " · 参考覆盖偏低，新身份需运动证据" : "");
            if (currentAudit.overflow) el.textContent += " · 候选过多，身份未知";
            if (colorMissing) el.textContent = "⚠高亮未生效：颜色缓冲未挂接 · " + el.textContent;
            var events = document.getElementById("perceptionEvents");
            if (events) {
                var base = currentAudit.session_start_t;
                events.textContent = poses.join("\n") + "\n" + (currentAudit.events.length ?
                    currentAudit.events.slice(-8).map(function(e){return (e.t-base).toFixed(1)+"s · #"+e.track_id+" "+
                        ({FALL_CANDIDATE:"疑似跌倒（待核实）",RECOVERED:"候选事件后恢复站立",POSTURE_RETURNED:"躺卧后回到站立"}[e.type]||e.type);}).join("\n") : "暂无候选事件");
                if (cpuSamples.length) {
                    var sorted=cpuSamples.slice().sort(function(a,b){return a-b;});
                    events.textContent += "\n计算与着色 P95 " + sorted[Math.ceil(sorted.length*0.95)-1].toFixed(1) + "ms（不含GPU）";
                    if (performance.memory) events.textContent += " · JS堆 " + Math.round(performance.memory.usedJSHeapSize/1048576) + "MB";
                }
            }
        }
    }

    /* ---- replay.js 钩子契约 ---- */
    function notify_session() { gen++; return gen; }
    function reset() { st = null; mem = null; lastRep = null; lastCand = 0; lowKeys = new Set(); lastLow = 0;
        perception = null; currentAudit = null; claimedRows = new Set(); lastLive = 0; cpuSamples = [];
        Object.keys(paint_stats).forEach(function(k){paint_stats[k]=0;}); }
    function set_mode(mode, options) {
        if (!["legacy", "metric3d", "xy"].includes(mode)) throw new Error("未知感知版本");
        if (mode !== "legacy" && !globalThis.traditional_perception) throw new Error("传统感知引擎未载入");
        pipelineMode = mode; perceptionOptions = Object.assign({}, options || {}, {cluster: mode}); reset();
    }
    /* replay.js 实际传的是裸 Float32Array（detect_overlay L364 同款契约）；
     * r8 判决截图定案：此前误读 attr.array → colorBuf=undefined → _paint 静默跳过，
     * 浏览器整场显示的是底着色 LUT，叠加层从未上屏。两种形态都兼容，且缺色必报。 */
    function attach_color(attr_or_array) {
        colorBuf = (attr_or_array && attr_or_array.array) ? attr_or_array.array : attr_or_array;
        colorMissing = !(colorBuf && colorBuf.length > 2);
    }
    var colorMissing = true;
    function set_leveled_in_s(b) { leveled_in_s = !!b; }
    function on_frame(S) {
        if (!S || !S.meta || !S.meta.frames || !S.meta.frames.length) return;
        if (typeof S.session_gen === "number" && S.session_gen !== gen) return;
        var cpuStart = performance.now();
        _ensure_state(S);
        var F = _libs().F, P = _libs().P;
        var t = S.meta.frames[S.idx].bag_time_sec;
        if (pipelineMode !== "legacy" && currentAudit && currentAudit.frame === S.idx && currentAudit.t === t) {
            if (colorBuf && S.geo && S.geo.attributes && S.geo.attributes.color) _paint(S, []);
            return;
        }
        var xyzi = _frame_xyzi(S, S.idx);
        lastRep = F.fresh_update(st, xyzi, t);
        if (pipelineMode !== "legacy") {
            if (!perception) perception = new globalThis.traditional_perception.Engine(perceptionOptions);
            currentAudit = perception.tick(xyzi, st, S.idx, t);
            currentAudit.session_gen = gen; currentAudit.reference = refDesc;
            currentAudit.session_start_t = S.meta.frames[0].bag_time_sec;
            currentAudit.transform = {R:R.slice(),t:T.slice(),already_leveled:leveled_in_s || !!S.meta.leveling};
            claimedRows = new Set(currentAudit.claims.map(function(c){return currentSourceRows[c.index];}));
            currentAudit.source_rows = Array.from(claimedRows);
            currentAudit.source_offset = S.meta.frames[S.idx].offset_points;
            lastLive = currentAudit.tracks.filter(function(a){return a.confirmed && a.last_frame === S.idx;}).length;
            lastLow = currentAudit.branches.filter(function(a){return a.confirmed && a.branch === "low_continue";}).length;
            lastCand = currentAudit.candidate_points;
            if (colorBuf && S.geo && S.geo.attributes && S.geo.attributes.color) _paint(S, []);
            currentAudit.cpu_ms = performance.now() - cpuStart;
            cpuSamples.push(currentAudit.cpu_ms); if (cpuSamples.length > 600) cpuSamples.shift();
            _hud(); return;
        }
        var cand = F.candidate_xyzi(st, xyzi, mem);
        lastCand = cand.length / 4;
        /* r7.1 证据柱（续命语义，与显示分离）：格 ¬ref_sup ∧ ever_event 即算——
         * 长期静坐的人 GHOST 虽超寿沉黑，占住的非背景格仍是"这里有过活动"的身份证据；
         * 背景/家具（ref 支撑或从未动过）永不算证据，锚点无法自吞。 */
        var evCols = new Set(), evCounts = new Map();
        for (var cp = 0; cp < cand.length; cp += 4) {
            var vv = st.voxels.get(globalThis.human_pipe_lib.key_bg(cand[cp], cand[cp + 1], cand[cp + 2]));
            if (vv && !vv.ref_sup && vv.ever_event) {
                var ek = P.key_vox(cand[cp], cand[cp + 1]);
                evCols.add(ek); evCounts.set(ek, (evCounts.get(ek) || 0) + 1);
            }
        }
        var clusters = P.cluster_voxels(P.voxelize(cand)), claims = [], lowRows = [];
        lastClusters = clusters.length;
        for (var ci = 0; ci < clusters.length; ci++) {
            var a = clusters[ci].acc;
            var ftr = P.cluster_features(clusters[ci]);
            var hasEv = clusters[ci].keys.some(function (k) { return evCols.has(k); });
            if (ftr.ok && P.classify_human(ftr).label === "HUMAN_CANDIDATE")
                claims.push({ cx: a.sx / a.n, cy: a.sy / a.n, cz: a.sz / a.n, n: a.n, ev: hasEv,
                    standing_height: ftr.height_m });
            else lowRows.push({ f: ftr, keys: clusters[ci].keys,
                evidenceN: clusters[ci].keys.reduce(function (n, k) { return n + (evCounts.get(k) || 0); }, 0) });
        }
        lastClaims = claims.length;
        var continued = _continuations(lowRows, _live_fresh(mem, S.idx), claims, S.idx, t);
        lowKeys = new Set(); lastLow = continued.length;
        continued.forEach(function (m) {
            var f = m.row.f;
            claims.push({ cx: f.cx, cy: f.cy, cz: f.cz, n: f.n, ev: true });
            m.row.keys.forEach(function (k) { lowKeys.add(k); });
        });
        F.mem_tick(mem, claims, S.idx, t);
        mem.anchors.forEach(function (a) {
            if (a.frame_index !== S.idx || a.confirmations < mem.o.retention.window_confirm) return;
            var standing = claims.find(function (c) {
                return c.standing_height !== undefined && c.cx === a.x && c.cy === a.y && c.ev;
            });
            if (standing) {
                a.standing_z = Math.max(a.standing_z || -Infinity, a.z);
                a.standing_height = Math.max(a.standing_height || 0, standing.standing_height);
            }
        });
        continued.forEach(function (m) {
            /* 一次短缺测后mem_tick会清连续计数；已确认身份的唯一续接保留资格。 */
            m.anchor.confirmations = Math.max(m.anchor.confirmations, mem.o.retention.window_confirm);
        });
        var live = _live_fresh(mem, S.idx);   /* 站姿确认或唯一低姿续接，不能无证据续命 */
        lastLive = live.length;
        if (colorBuf && S.geo && S.geo.attributes && S.geo.attributes.color) _paint(S, live);
        _hud();
    }

    /* ---- 页面侧工具（file:// 手动选空场目录） ---- */
    function set_ref_frames(frames_xyzi, desc) {
        refPack = _libs().F.build_reference(frames_xyzi, {});
        refDesc = desc || "external";
        reset();   /* 换参考 → 状态重建 */
    }
    function rebuild_reference() {
        var P = _libs().P, meta = referenceSource.meta, buf = referenceSource.buf, fr = [];
        var n = Math.min(meta.frames.length, 600);
        for (var i = 0; i < n; i++) {
            var f = meta.frames[i], start = f.offset_points, count = f.count_points, raw = new Float32Array(count * 4);
            for (var k = 0; k < count; k++) {
                var o = (start + k) * 7, x = buf[o], y = buf[o + 1], z = buf[o + 2];
                raw[k * 4] = R[0] * x + R[1] * y + R[2] * z + T[0];
                raw[k * 4 + 1] = R[3] * x + R[4] * y + R[5] * z + T[1];
                raw[k * 4 + 2] = R[6] * x + R[7] * y + R[8] * z + T[2];
                raw[k * 4 + 3] = buf[o + 3];
            }
            fr.push(P.denoise(raw));
        }
        set_ref_frames(fr, meta.session_id || "external");
        return n;
    }
    function set_transform(r, t) {
        var flat = r.flat ? r.flat() : r;
        if (flat.length !== 9 || t.length !== 3 || !flat.concat(t).every(Number.isFinite))
            throw new Error("配平变换无效");
        if (R.every(function (v, i) { return v === flat[i]; }) && T.every(function (v, i) { return v === t[i]; })) return;
        R = flat.slice(); T = t.slice();
        if (referenceSource) rebuild_reference();
    }
    function load_ref_dir(files) {
        var Lb = globalThis.human_replay_lib, P = _libs().P;
        var metaF = files.find(function (f) { return f.name === "meta.json"; });
        var binF = files.find(function (f) { return f.name === "points.bin"; });
        if (!metaF || !binF) return Promise.reject(new Error("空场目录缺 meta.json/points.bin"));
        return metaF.text().then(function (txt) {
            var meta = JSON.parse(txt);
            if (meta.leveling || meta.point_stride_bytes !== 28 || !Array.isArray(meta.frames) || !meta.frames.length)
                throw new Error("空场须为原始28字节点云会话");
            return binF.arrayBuffer().then(function (b) {
                if (!Number.isSafeInteger(meta.total_points) || meta.total_points * 28 !== b.byteLength)
                    throw new Error("空场点云尺寸不匹配");
                var end = 0;
                meta.frames.forEach(function (f) {
                    if (f.offset_points !== end || !Number.isSafeInteger(f.count_points) || f.count_points < 0 ||
                        f.count_points > meta.total_points - end) throw new Error("空场帧索引无效");
                    end += f.count_points;
                });
                if (end !== meta.total_points) throw new Error("空场帧点数不匹配");
                referenceSource = { meta: meta, buf: new Float32Array(b) };
                return rebuild_reference();
            });
        });
    }

    var api = {
        notify_session: notify_session, reset: reset, attach_color: attach_color,
        set_leveled_in_s: set_leveled_in_s, on_frame: on_frame,
        set_transform: set_transform,
        set_mode: set_mode,
    };
    globalThis.FRESH_OVERLAY = api;
    globalThis.FRESH_SET_REF = load_ref_dir;
    globalThis.FRESH_INTERNAL = { set_ref_frames: set_ref_frames, state: function () { return st; },
                                  audit: function () { return currentAudit; },
                                  continuations: _continuations,
                                  mem: function () { return mem; }, lastRep: function () { return lastRep; },
                                  paintStats: function () { return paint_stats; },
                                  anchorList: function () { return mem ? mem.anchors.map(function (a) {
                                      return { id:a.id, x: +a.x.toFixed(2), y: +a.y.toFixed(2), z: +a.z.toFixed(2),
                                               conf: a.confirmations, f: a.frame_index, t:a.timestamp }; }) : []; } };
    if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
