/* HR-W02 离线人体识别工作台 — 浏览器层（仅此文件触摸 THREE / DOM）。
 *
 * 数据流（与 replay.js 保持同构）：
 *   meta.json + points.bin → human_replay_lib.frame_slice → 一次性灌满
 *   BufferGeometry（drawRange 切帧，零每帧分配）→ leveled_latest 若有 TLS transform
 *   就 to in-place apply（下游 ROI/PCA 全部在 ground display 系）→
 *   每帧 human_detect_lib.frame_human_features + EmaTracker → 绿色/红色 Jan bbox overlay。
 */
"use strict";
/* global THREE, human_replay_lib, human_detect_lib, human_pipe_lib */

(function () {
    var RL = human_replay_lib;
    var DL = human_detect_lib;
    var PL = human_pipe_lib;

    // ---- state ----------------------------------------------------------------
    var S = {
        meta: null, frames: null, total_pts: 0,
        buf_f32: null,
        geo: null, points: null, colour: null,
        renderer: null, scene: null, camera: null, controls: null,
        idx: 0, playing: false, speed: 1, fps: 10, acc: 0, last_ts: 0,
        range: { lo: 0, hi: 1 },
        leveled: false, transform: null,
        // ---- human-detect 状态 ----
        roi: null,                 // {x,y,r} 圆柱 ROI
        tracker: new DL.EmaTracker(),
        pinArmed: false,           // 是否处于「点一下设 ROI」模式
        ringMesh: null, ballMesh: null, boxMesh: null, axisLine: null,
        lastFeat: null, lastSm: null,
        // ---- HR-W03 自动管线状态 ----
        pipe: {
            static_keys: null,     // Set — 全帧背景模型（载入后建一次）
            bg_building: false,
            bg_done: false,
            tracker: new PL.Tracker(),
            cluster_objs: [],      // [{points:造的聚类高亮点, color}]
            cluster_boxes: [],     // 判定 bbox 组（绿=HUMAN_SHAPE，紫/橙=SOLID_UNIFORM，灰=AMBIGUOUS）
            last_frame_idx: -1,
            fall_log: [],          // 时序 Fall 事件列表（跨帧持久）
        },
    };
    var els = {};
    ["session", "metaInfo", "seekBar", "pinModeBtn", "roiR", "roiRVal", "roiInfo", "clearPinBtn",
     "resetTrackBtn", "poseBlock", "featTable", "status", "hud",
     "pipeOn", "pipeStatus", "pipeCounts", "pipeClusters", "trackList", "fallEvents"]
        .forEach(function (id) { els[id] = document.getElementById(id); });

    function status(msg, is_err) {
        els.status.textContent = msg;
        els.status.style.color = is_err ? "#d46a62" : "#a0a3ab";
    }

    // ---- 会话列表 ------------------------------------------------------------------
    function refresh_sessions() {
        return fetch("/api/leveling/sessions").then(function (r) { return r.json(); })
            .then(function (js) {
                var sel = els.session;
                sel.innerHTML = "<option value=''>请选择…</option>";
                (js.sessions || []).forEach(function (s) {
                    var o = document.createElement("option");
                    o.value = s.sid;
                    o.textContent = s.sid + "  " + (s.frames || "?") + "帧";
                    sel.appendChild(o);
                });
            }).catch(function (e) { status("会话列表失败: " + e.message, true); });
    }

    // ---- 载入（与 replay.js 同构；多一步 leveled_latest in-place transform） ----------
    function load_sid(sid) {
        status("载入 meta…");
        S.roi = null; S.tracker.reset(); S.lastFeat = null; S.lastSm = null;
        _clear_overlays();
        _clear_pipe_overlays();   /* 换会话清旧 pipe bbox — 否则新会话场景里残留上个会话的家具框 */
        var metaF = { name: "meta.json", text: function () { return fetch("/api/file?sid=" + encodeURIComponent(sid) + "&name=meta.json").then(function (r) { if (!r.ok) throw new Error("meta HTTP " + r.status); return r.text(); }); } };
        var binF = { name: "points.bin", arrayBuffer: function () { return fetch("/api/file?sid=" + encodeURIComponent(sid) + "&name=points.bin").then(function (r) { if (!r.ok) throw new Error("bin HTTP " + r.status); return r.arrayBuffer(); }); } };
        return metaF.text().then(function (txt) {
            S.meta = JSON.parse(txt);
            return binF.arrayBuffer();
        }).then(function (buf) {
            status("解析点云…");
            var t0 = performance.now();
            if (buf.byteLength % RL.STRIDE_BYTES !== 0) throw new Error("points.bin 不是 28 的倍数");
            S.buf_f32 = new Float32Array(buf);
            S.total_pts = buf.byteLength / RL.STRIDE_BYTES;
            S.frames = RL.frame_slice(S.meta);
            S.fps = RL.default_fps(S.meta);
            S.leveled = false; S.transform = null;

            /* in-place leveled transform（复刻 replay.js 的 apply_Rt_inplace） */
            function apply_Rt(R, t) {
                var r = R.flat ? R.flat() : R;
                for (var p = 0; p < S.total_pts; p++) {
                    var s = p * RL.STRIDE_F32;
                    var x = S.buf_f32[s], y = S.buf_f32[s + 1], z = S.buf_f32[s + 2];
                    S.buf_f32[s]     = r[0] * x + r[1] * y + r[2] * z + t[0];
                    S.buf_f32[s + 1] = r[3] * x + r[4] * y + r[5] * z + t[1];
                    S.buf_f32[s + 2] = r[6] * x + r[7] * y + r[8] * z + t[2];
                }
            }
            function finish() {
                build_geometry();
                S.range = compute_range();
                paint_colours();
                build_static_background();
                els.metaInfo.innerHTML =
                    "<b class='mono'>" + S.meta.session_id + "</b><br>" +
                    S.frames.length + " 帧 · " + S.total_pts + " 点 · " +
                    (S.meta.duration_sec || 0).toFixed(1) + "s · " + S.fps + "Hz · " +
                    (S.leveled ? "<span style='color:#4bab7d'>已应用 TLS 配平 (z=0=地板)</span>"
                               : "<span style='color:#d0a75a'>未配平：仅供参考 — 请先在「算法验证」页评估</span>");
                status("就绪 (" + Math.round(performance.now() - t0) + "ms)");
                set_idx(0);
                play(true);
            }
            fetch("/api/leveling/leveled_latest?sid=" + encodeURIComponent(sid))
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (lv) {
                    if (lv && lv.ok && lv.transform && lv.transform.R && lv.transform.t) {
                        apply_Rt(lv.transform.R, lv.transform.t);
                        S.leveled = true;
                        S.transform = lv.transform;
                    }
                })
                .catch(function () { /* 无配平结果不阻塞 */ })
                .then(finish);
        }).catch(function (e) {
            status("载入失败: " + e.message, true);
            console.error(e);
            throw e;
        });
    }

    function build_geometry() {
        if (S.points) { S.scene.remove(S.points); S.geo.dispose(); }
        var pos = new Float32Array(S.total_pts * 3);
        S.colour = new Float32Array(S.total_pts * 3);
        var src = S.buf_f32;
        for (var p = 0; p < S.total_pts; p++) {
            var s = p * RL.STRIDE_F32, d = p * 3;
            pos[d] = src[s]; pos[d + 1] = src[s + 1]; pos[d + 2] = src[s + 2];
        }
        S.geo = new THREE.BufferGeometry();
        S.geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        S.geo.setAttribute("color", new THREE.BufferAttribute(S.colour, 3));
        S.points = new THREE.Points(S.geo,
            new THREE.PointsMaterial({ size: 0.032, vertexColors: true, sizeAttenuation: true }));
        S.points.frustumCulled = false;
        S.scene.add(S.points);
    }

    function compute_range() {
        var frames4 = [];
        for (var i = 0; i < S.frames.length; i++) {
            var f = S.frames[i];
            frames4.push(RL.strided_f32_copy(S.buf_f32, f.start_pts, Math.min(f.count, 4096), RL.STRIDE_F32));
        }
        return RL.pick_intensity_range(frames4);
    }

    /* 用 human_replay_lib 的灰度上色让点云别那么刺 */
    function paint_colours() {
        var lo = S.range.lo, hi = S.range.hi;
        var src = S.buf_f32, dst = S.colour;
        for (var p = 0; p < S.total_pts; p++) {
            var t = RL.intensity_to_gray(src[p * RL.STRIDE_F32 + 3], lo, hi);
            var d = p * 3;
            dst[d] = t; dst[d + 1] = t; dst[d + 2] = t;
        }
        S.geo.attributes.color.needsUpdate = true;
    }

    // ---- 场景 ---------------------------------------------------------------------
    function setup_scene() {
        var vp = _viewport(), w = vp.w, h = vp.h;
        S.renderer = new THREE.WebGLRenderer({ antialias: true });
        S.renderer.setSize(w, h);
        S.renderer.setClearColor(0x101114);
        els.seekBar.oninput = function () { play(false); set_idx(+els.seekBar.value); };
        document.getElementById("view").appendChild(S.renderer.domElement);
        S.scene = new THREE.Scene();
        S.camera = new THREE.PerspectiveCamera(62, w / h, 0.05, 400);
        S.camera.up.set(0, 0, 1);
        S.camera.position.set(-3.5, -4, 2.8);
        S.scene.add(new THREE.AxesHelper(1.2));
        var grid = new THREE.GridHelper(40, 40, 0x2e3238, 0x1f2226);
        grid.rotation.x = Math.PI / 2;
        S.scene.add(grid);
        var origin = new THREE.Mesh(new THREE.SphereGeometry(0.08, 12, 12),
            new THREE.MeshBasicMaterial({ color: 0x5c8ade }));
        S.scene.add(origin);
        if (typeof THREE.TrackballControls === "function") {
            S.controls = new THREE.TrackballControls(S.camera, S.renderer.domElement);
        } else {
            S.controls = new THREE.OrbitControls(S.camera, S.renderer.domElement);
        }
        S.controls.target.set(2.5, 0, 0.6);
        S.controls.update();
        window.addEventListener("resize", on_resize);
        S.last_ts = performance.now();
        requestAnimationFrame(tick);
        /* 点选 ROI：点云/地面用 ray 打距离 */
        S.renderer.domElement.addEventListener("mousedown", on_canvas_click);
    }
    function _viewport() {
        var v = document.getElementById("view");
        return { w: v.clientWidth, h: v.clientHeight };
    }
    function on_resize() {
        var vp = _viewport();
        S.camera.aspect = vp.w / vp.h;
        S.camera.updateProjectionMatrix();
        S.renderer.setSize(vp.w, vp.h);
    }

    /* ---- HR-W03：静态背景一次建模（全帧扫一遍，离线 2-4s） ----
     * 直后 pipe tracker/事件日志清空 — 因为前景是相对于新背景的。*/
    function build_static_background() {
        if (!S.frames || !S.buf_f32) return;
        if (!els.pipeOn.checked) {
            S.pipe.bg_done = false; S.pipe.static_keys = null;
            els.pipeStatus.textContent = "自动管线已关停（pin ROI 仍可用）";
            return;
        }
        S.pipe.bg_building = true; S.pipe.bg_done = false;
        S.pipe.static_keys = null;
        S.pipe.tracker = new PL.Tracker();
        S.pipe.fall_log = [];
        els.pipeStatus.textContent = "背景建模：扫全帧 3D 体素占用（strong/supported 两级）…（约 2-4s）";
        var ded = S.frames.map(function (f) {
            return PL.denoise(RL.strided_f32_copy(S.buf_f32, f.start_pts, f.count, RL.STRIDE_F32));
        });
        var t0 = performance.now();
        S.pipe.static_keys = PL.build_static_map(ded, { drop_ground: true });
        S.pipe.bg_done = true; S.pipe.bg_building = false;
        els.pipeStatus.textContent = "静态背景 " + S.pipe.static_keys.size + " 个静态体素（"
            + Math.round(performance.now() - t0) + "ms）· 每帧跑完整管线";
        /* 已经停在末帧 — 手动刷新一次让新背景生效 */
        S.pipe.last_frame_idx = -1;
        set_idx(S.idx);
    }

    // ---- 帧推进 + 本帧检测 -----------------------------------------------------------
    function set_idx(i) {
        var n = S.frames ? S.frames.length : 0;
        if (!n) return;
        S.idx = Math.min(Math.max(i, 0), n - 1);
        var f = S.frames[S.idx];
        S.geo.setDrawRange(f.start_pts, f.count);
        if (els.seekBar) { els.seekBar.max = n - 1; els.seekBar.value = S.idx; }
        var t = (f.bag_time_sec != null) ? RL.format_hhmmss(f.bag_time_sec - S.frames[0].bag_time_sec) : "--:--";
        els.hud.textContent =
            "帧 " + (S.idx + 1) + "/" + n + "  seq=" + f.seq + "  t=" + t +
            "  点=" + f.count + (S.leveled ? "  [TLS 配平]" : "  [原始系]") +
            (S.roi ? "  ROI=(" + S.roi.x.toFixed(2) + "," + S.roi.y.toFixed(2) + ",r=" + S.roi.r.toFixed(2) + ")" : "  [无 ROI]");
        run_detect();
    }

    function tick(now) {
        requestAnimationFrame(tick);
        var dt = (now - S.last_ts) / 1000;
        S.last_ts = now;
        if (S.playing && S.frames) {
            S.acc += dt * S.speed;
            var step = 1 / S.fps;
            while (S.acc >= step) {
                S.acc -= step;
                var nxt = S.idx + 1;
                if (nxt >= S.frames.length) { play(false); break; }
                set_idx(nxt);
            }
        }
        S.controls.update();
        S.renderer.render(S.scene, S.camera);
    }

    function play(on) { S.playing = (on == null) ? !S.playing : !!on; }

    // ---- 核心：本帧检测 + 叠加 ----------------------------------------------------------
    function run_detect() {
        /* HR-W03 自动管线（独立于 pin ROI）：每帧跑 denoise→前景→聚类→证据→track→fall */
        if (S.pipe.bg_done && els.pipeOn.checked) _run_pipe_frame();
        else _clear_pipe_overlays();

        if (!S.roi || !S.frames) {
            els.poseBlock.innerHTML = "<span class='tag unknown'>—</span> 未锁定 ROI";
            els.featTable.tBodies[0].innerHTML = "";
            return;
        }
        var f = S.frames[S.idx];
        var slice = RL.strided_f32_copy(S.buf_f32, f.start_pts, f.count, RL.STRIDE_F32);
        var cyl = DL.points_in_cylinder(slice, S.roi, DL.DETECT.z_min_human, DL.DETECT.z_max_human);
        var feat = DL.frame_human_features(cyl);
        S.lastFeat = feat;
        var sm = S.tracker.push(feat && feat.ok ? feat : null);
        S.lastSm = sm;

        /* 叠加 ROI 圆柱 + 判定 bbox + 主轴 */
        _render_overlays(feat, sm);
        /* 面板 */
        _render_panel(feat, sm, cyl.length / 4);
    }

    /* ---- HR-W03 自动管线：每帧 ---- */
    function _run_pipe_frame() {
        if (S.pipe.last_frame_idx === S.idx) return;   /* 同帧不重跑 */
        S.pipe.last_frame_idx = S.idx;
        var f = S.frames[S.idx];
        var slice = RL.strided_f32_copy(S.buf_f32, f.start_pts, f.count, RL.STRIDE_F32);
        var r = PL.pipeline_frame(slice, S.idx, S.pipe);

        /* 事件并入历史日志（跨帧）。躺姿期间同一 Fall 会逐帧重发（from_idx 不变），
         * 只更新末条——否则一个 Fall 把 10 条日志全刷成重复。 */
        for (var i = 0; i < r.events.length; i++) {
            var e = r.events[i], last = S.pipe.fall_log[S.pipe.fall_log.length - 1];
            if (last && last.track_id === e.track_id && last.from_idx === e.from_idx) {
                last.to_idx = e.to_idx; last.reason = e.reason;
            } else {
                S.pipe.fall_log.push(e);
            }
        }
        /* 只留最近 10 条，防 UI 无界增 */
        while (S.pipe.fall_log.length > 10) S.pipe.fall_log.shift();

        _render_pipe_overlays(r);
        _render_pipe_panel(r);
    }

    function _clear_pipe_overlays() {
        function _drop(o) {
            S.scene.remove(o);
            if (o.geometry) o.geometry.dispose();
            if (o.material) o.material.dispose();   /* 每帧 new 2 个 MeshBasicMaterial — 只清 geometry 会漏 */
        }
        S.pipe.cluster_objs.forEach(_drop);
        S.pipe.cluster_objs = [];
        S.pipe.cluster_boxes.forEach(_drop);
        S.pipe.cluster_boxes = [];
        els.pipeCounts.textContent = "—"; els.pipeClusters.textContent = "—";
        els.trackList.innerHTML = ""; els.fallEvents.innerHTML = "";
    }

    /* 簇 bbox：联合判定（R2.4）定色，绿须经 track 时间确认（R2.5）。
     * 不重建 voxel→cluster 映射（画 bbox 足够，高亮点级覆盖在「细节不够时才需要」— 先不做） */
    function _render_pipe_overlays(r) {
        _clear_pipe_overlays();
        r.clusters.forEach(function (cl) {
            /* bbox：绿=CONFIRMED_HUMAN（且 3/5 帧确认）/ 蓝=HUMAN_CANDIDATE / 弱化灰=NON_HUMAN */
            var color = 0x6b6f78;   /* NON_HUMAN：弱化，不抢注意力 */
            if (cl.joint === "HUMAN_CANDIDATE") color = 0x5c8ade;
            else if (cl.joint === "CONFIRMED_HUMAN") color = cl.track_confirmed ? 0x4bab7d : 0x5c8ade;
            var sx = Math.max(0.2, cl.width_m * 2), sy = Math.max(0.2, cl.depth_m * 2);
            var sz = Math.max(0.2, cl.height_m);
            var box = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz),
                new THREE.MeshBasicMaterial({ color: color, transparent: true, opacity: 0.14, wireframe: false }));
            box.position.set(cl.cx, cl.cy, cl.zmin + cl.height_m / 2);
            S.scene.add(box); S.pipe.cluster_boxes.push(box);
            /* bbox 线框 */
            var wire = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz),
                new THREE.MeshBasicMaterial({ color: color, wireframe: true, transparent: true, opacity: 0.9 }));
            wire.position.copy(box.position);
            S.scene.add(wire); S.pipe.cluster_boxes.push(wire);
        });
    }

    function _render_pipe_panel(r) {
        els.pipeCounts.textContent = r.n_in + " → " + r.n_denoise + " → " + r.n_foreground
            + "（削 " + r.n_dropped + "）"
            + " · 孤立清理：删除 " + r.iso_removed_points + " 点 / " + r.iso_removed_voxels + " voxel";
        var by = { CONFIRMED_HUMAN: 0, HUMAN_CANDIDATE: 0, NON_HUMAN: 0 };
        r.clusters.forEach(function (c) { by[c.joint] = (by[c.joint] || 0) + 1; });
        els.pipeClusters.innerHTML =
            r.clusters.length + " 簇 · "
            + "<span style='color:#4bab7d'>确认 ×" + by.CONFIRMED_HUMAN + "</span> · "
            + "<span style='color:#5c8ade'>候选 ×" + by.HUMAN_CANDIDATE + "</span> · "
            + "<span style='color:#676b73'>非人 ×" + by.NON_HUMAN + "</span>";
        /* track 列表 */
        els.trackList.innerHTML = r.tracks.map(function (t) {
            var cls = t.label === "CONFIRMED_HUMAN" ? "ok" : (t.label === "HUMAN_CANDIDATE" ? "info" : "unknown");
            return "<div class='mono' style='font-size:11px'>#" + t.id + " "
                + "<span class='tag " + cls + "'>" + t.label + "</span>"
                + (t.human_confirmed ? " <span class='tag ok'>确认</span>" : "")
                + " h=" + t.height.toFixed(2) + " upcos=" + t.upcos.toFixed(2)
                + " n=" + t.n + "</div>";
        }).join("") || "<span class='muted' style='font-size:11px'>本帧无活跃 track</span>";
        /* Fall 历史 */
        els.fallEvents.innerHTML = S.pipe.fall_log.map(function (e) {
            return "<div class='tag bad' style='display:block;margin:3px 0'>Fall track#" + e.track_id
                + " " + e.from_idx + "→" + e.to_idx + " · " + e.reason + "</div>";
        }).join("");
    }

    function _render_overlays(feat, sm) {
        /* ROI 圆柱（蓝色 wireframe） */
        if (!S.ringMesh) {
            S.ringMesh = new THREE.Mesh(
                new THREE.CylinderGeometry(1, 1, 1, 24, 1, true),
                new THREE.MeshBasicMaterial({ color: 0x5c8ade, wireframe: true, transparent: true, opacity: 0.4 }));
            S.scene.add(S.ringMesh);
        }
        S.ringMesh.position.set(S.roi.x, S.roi.y, DL.DETECT.z_max_human / 2);
        S.ringMesh.scale.set(S.roi.r, DL.DETECT.z_max_human, S.roi.r);   /* CylinderGeometry 高度沿 Y */
        S.ringMesh.visible = !!S.roi;

        /* 判定 bbox：绿=standing / 黄=bending / 红=lying / 灰=unknown / 紫=非人 furniture */
        if (!S.boxMesh) {
            S.boxMesh = new THREE.Mesh(
                new THREE.BoxGeometry(1, 1, 1),
                new THREE.MeshBasicMaterial({ color: 0x4bab7d, transparent: true, opacity: 0.15, wireframe: false }));
            S.scene.add(S.boxMesh);
        }
        var box = DL.smoothed_to_box(sm);
        if (box && feat && feat.ok) {
            S.boxMesh.position.set(box.center[0], box.center[1], box.center[2]);
            S.boxMesh.scale.set(box.size[0], box.size[1], box.size[2]);
            var color = 0x9fbfdd;
            if (!feat.is_human_like) color = 0x6b6f78;         /* 几何说「不像人」：弱化 */
            else if (feat.pose === "standing") color = 0x4bab7d;
            else if (feat.pose === "bending") color = 0xd0a75a;
            else if (feat.pose === "lying") color = 0xd46a62;
            S.boxMesh.material.color.setHex(color);
            S.boxMesh.visible = true;
        } else {
            S.boxMesh.visible = false;
        }

        /* 主轴（eig0, 主扩散方向）画一条紫线在 ROI 心 */
        if (!S.axisLine) {
            var g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(0, 0, 1)]);
            S.axisLine = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0x5c8ade }));
            S.scene.add(S.axisLine);
        }
        if (feat && feat.ok && feat.pca) {
            var a = feat.pca.axis0;  /* 下面 panel 里把 axis0 全向量填上 */
            if (a) {
                var pos = S.axisLine.geometry.attributes.position;
                pos.setXYZ(0, feat.bbox.cx, feat.bbox.cy, feat.bbox.cz);
                pos.setXYZ(1, feat.bbox.cx + a[0] * 0.9, feat.bbox.cy + a[1] * 0.9, feat.bbox.cz + a[2] * 0.9);
                pos.needsUpdate = true;
                S.axisLine.visible = true;
            } else { S.axisLine.visible = false; }
        } else { S.axisLine.visible = false; }

        /* ROI 外圈停留球（设 ROI 时的可视反馈） */
        if (!S.ballMesh) {
            S.ballMesh = new THREE.Mesh(new THREE.SphereGeometry(0.1, 16, 16),
                new THREE.MeshBasicMaterial({ color: S.leveled ? 0x5c8ade : 0xd0a75a }));
            S.scene.add(S.ballMesh);
        }
        S.ballMesh.position.set(S.roi.x, S.roi.y, 0);
        S.ballMesh.visible = !!S.roi;
    }

    function _clear_overlays() {
        ["ringMesh", "ballMesh", "boxMesh", "axisLine"].forEach(function (k) {
            if (S[k]) { S.scene.remove(S[k]); S[k] = null; }
        });
    }

    function _tag(txt, cls) { return "<span class='tag " + cls + "'>" + txt + "</span>"; }
    function _render_panel(feat, sm, n_cyl) {
        if (!feat) { els.poseBlock.innerHTML = _tag("无数据", "unknown"); return; }
        if (!feat.ok) {
            els.poseBlock.innerHTML = _tag("拒绝", "bad") + " " + (feat.reason || "");
            els.featTable.tBodies[0].innerHTML = "";
            return;
        }
        var poseChip = feat.pose === "standing" ? _tag("站立", "ok") :
                       feat.pose === "bending" ? _tag("弯腰", "warn") :
                       feat.pose === "lying" ? _tag("躺平", "bad") : _tag("未知", "unknown");
        var humanChip = feat.is_human_like ? _tag("像人", "ok") : _tag("像家具", "warn");
        els.poseBlock.innerHTML =
            "<div class='posechip'>" + poseChip + " " + humanChip + " " +
            _tag("score " + feat.score + "/7", feat.score >= 5 ? "ok" : "warn") + "</div>";
        var rows = [
            ["ROI 内点数", n_cyl],
            ["主直立度 cos", feat.upright_cos.toFixed(3) + (feat.upright_cos >= DL.DETECT.min_upright_cos ? " ✓" : " ✗")],
            ["顶高 (z 范围)", feat.height_m.toFixed(2) + " m" +
                (feat.height_m >= DL.DETECT.max_height_standing_m ? " ✓站" : (feat.height_m >= DL.DETECT.min_height_m ? " ·弯" : " ·躺"))],
            ["躯干半径 r_xy", feat.bbox.r_xy.toFixed(2) + " m" + (feat.bbox.r_xy <= 0.45 ? " ✓人" : (feat.bbox.r_xy <= 0.60 ? " ·宽" : " ✗家具"))],
            ["PCA 主 vs 次", feat.pca.values.map(function (v) { return v.toFixed(2); }).join(" / ")],
            ["平滑位 (x,y)", "(" + sm.x.toFixed(2) + ", " + sm.y.toFixed(2) + ")"],
        ];
        els.featTable.tBodies[0].innerHTML = rows.map(function (r) {
            return "<tr><td>" + r[0] + "</td><td class='mono'>" + r[1] + "</td></tr>";
        }).join("");
    }

    // ---- 交互：点选 ROI -----------------------------------------------------------------
    function on_canvas_click(ev) {
        if (!S.pinArmed || !S.frames) return;
        S.pinArmed = false;
        els.pinModeBtn.textContent = "点选 ROI（或按 K 对准星）";
        var r = parseFloat(els.roiR.value);
        var vp = _viewport();
        var ndc = new THREE.Vector2(
            (ev.clientX / vp.w) * 2 - 1,
            -(ev.clientY / vp.h) * 2 + 1
        );
        var ray = new THREE.Raycaster();
        ray.setFromCamera(ndc, S.camera);
        var o = ray.ray.origin, d = ray.ray.direction;
        var fr = S.frames[S.idx];
        var slice = RL.strided_f32_copy(S.buf_f32, fr.start_pts, fr.count, RL.STRIDE_F32);
        var pick = RL.pick_point_on_ray([o.x, o.y, o.z], [d.x, d.y, d.z], slice, 0.6);
        var gnd = RL.ray_ground_intersect([o.x, o.y, o.z], [d.x, d.y, d.z]);
        var cx = pick ? pick.x : (gnd ? gnd[0] : null);
        var cy = pick ? pick.y : (gnd ? gnd[1] : null);
        if (cx == null) { status("点选失败：未命中点云/地面", true); return; }
        S.roi = { x: cx, y: cy, r: r };
        S.tracker.reset();
        els.roiInfo.textContent = "ROI (" + cx.toFixed(2) + "," + cy.toFixed(2) + ") r=" + r.toFixed(2);
        status("ROI 已锁定（K 或拖到别处重设）");
        set_idx(S.idx);
    }

    /* K 键：准星设 ROI（复用 pick_point_on_ray，等价于鼠标中心点击） */
    function pin_at_crosshair() {
        if (!S.frames) return;
        var r = parseFloat(els.roiR.value);
        var d = new THREE.Vector3(); S.camera.getWorldDirection(d);
        var fr = S.frames[S.idx];
        var slice = RL.strided_f32_copy(S.buf_f32, fr.start_pts, fr.count, RL.STRIDE_F32);
        var pick = RL.pick_point_on_ray([S.camera.position.x, S.camera.position.y, S.camera.position.z],
            [d.x, d.y, d.z], slice, 0.6);
        var gnd = RL.ray_ground_intersect([S.camera.position.x, S.camera.position.y, S.camera.position.z],
            [d.x, d.y, d.z]);
        var cx = pick ? pick.x : (gnd ? gnd[0] : null);
        var cy = pick ? pick.y : (gnd ? gnd[1] : null);
        if (cx == null) { status("准星处无点", true); return; }
        S.roi = { x: cx, y: cy, r: r };
        S.tracker.reset();
        els.roiInfo.textContent = "ROI (" + cx.toFixed(2) + "," + cy.toFixed(2) + ") r=" + r.toFixed(2) + "（准星）";
        set_idx(S.idx);
    }

    // ---- 绑定 --------------------------------------------------------------------------
    els.session.addEventListener("change", function () {
        if (els.session.value) load_sid(els.session.value);
    });
    els.pinModeBtn.addEventListener("click", function () {
        S.pinArmed = !S.pinArmed;
        els.pinModeBtn.textContent = S.pinArmed ? "点图面任意位置…（再点取消）" : "点选 ROI（或按 K 对准星）";
    });
    els.clearPinBtn.addEventListener("click", function () {
        S.roi = null; S.tracker.reset();
        els.roiInfo.textContent = "未锁定";
        els.poseBlock.innerHTML = "<span class='tag unknown'>—</span> 未锁定 ROI";
        els.featTable.tBodies[0].innerHTML = "";
        ["ringMesh", "ballMesh", "boxMesh", "axisLine"].forEach(function (k) { if (S[k]) S[k].visible = false; });
        set_idx(S.idx);
    });
    els.resetTrackBtn.addEventListener("click", function () { S.tracker.reset(); status("平滑已重置"); });
    els.pipeOn.addEventListener("change", build_static_background);
    els.roiR.addEventListener("input", function () { els.roiRVal.textContent = parseFloat(els.roiR.value).toFixed(2) + " m"; });

    window.addEventListener("keydown", function (ev) {
        if (ev.target && (ev.target.tagName === "INPUT" || ev.target.tagName === "SELECT") && ev.code !== "Space") return;
        if (ev.code === "Space") { play(); ev.preventDefault(); }
        else if (ev.code === "ArrowLeft") { play(false); set_idx(S.idx - 1); ev.preventDefault(); }
        else if (ev.code === "ArrowRight") { play(false); set_idx(S.idx + 1); ev.preventDefault(); }
        else if (ev.code === "KeyK") { pin_at_crosshair(); ev.preventDefault(); }
    });

    setup_scene();
    refresh_sessions();

    /* 深链 / 默认选目标会话：query sid= 或自动选第一个含 cap_；用户授权的
     * 会话 cap_20261002_223757 若在列表中则预选之。 */
    (function () {
        var want = new URLSearchParams(location.search).get("sid") || "cap_20261002_223757";
        var it = setInterval(function () {
            var sel = els.session;
            for (var i = 0; i < sel.options.length; i++) {
                if (sel.options[i].value === want) {
                    clearInterval(it);
                    sel.value = want;
                    load_sid(want);
                    return;
                }
            }
            if (sel.options.length > 1) { /* 列表已渲染但没找到 want：放弃预选，等用户选 */ clearInterval(it); }
        }, 150);
    })();
})();
