/* HR-02 回放器浏览器层：仅此文件 import THREE。
 * 数据流: meta.json+points.bin → frame_slice → 一次性灌满 BufferGeometry →
 *         切帧只动 drawRange（零每帧分配）。
 * 坐标: 板端 IFW192S 雷达坐标系 x-forward/y-left/z-up；Three 里直接用，无语义变换，
 *       仅把 axes/grid 摆成 z-up 视角(相机初始位俯视前方)。
 */
"use strict";
/* global THREE, human_replay_lib */

(function () {
    var L = human_replay_lib;

    // ---- state ----------------------------------------------------------------
    var S = {
        meta: null, frames: null, total_pts: 0,
        buf_f32: null,            // 整个点区 Float32Array(total*7)
        geo: null, points: null,
        colour: null,             // Float32Array(total*3) 灰度按分位窗
        renderer: null, scene: null, camera: null, controls: null,
        idx: 0, playing: false, speed: 1, fps: 10, acc: 0, last_ts: 0,
        range: { lo: 0, hi: 1 },
        // 飞行相机（我的世界旁观者式）：F/ESC 进出，WASD+空格/Shift+鼠标指针锁定。
        // speed_mult 由滚轮调（FLY_WHEEL_JUST：滚轮=调速，不缩放）。
        fly: null,   // {keys:{}, yaw, pitch, speed_mult, on}
        // ---- HR-04 ----
        grid: null, grid_fine: null, axes: null, originBall: null,
        view_name: "persp",        // 当前视图预设名（7/1/3/0/home 同步）
        cam_persp: null,           // 备用 persp camera（视图切换保留视野）
        mouse_xy_ground: null,     // 鼠标在地面 z=0 上的投影 [x,y]
        snap_pt: null,             // P 键拾取快照 {x,y,z,i,seq}
        measure: { p1: null, line: null },  // M 标尺状态
        refs: {},                  // 参照物 Group map
        drag_person: null,         // 拖拽中状态
        aux_state: {},             // checkbox 状态（localStorage 持久化）
    };

    var els = {};
    var _els_missing = [];
    ["pickBtn", "dirInput", "status", "hud", "playBtn", "speedSel", "loopChk",
     "slider", "frameInfo", "metaBox", "lutSel", "flyHud",
     "trimBox", "trimInfo", "trimCmd", "metaToggle", "trimToggle",
     "resetBtn", "frontBtn", "topBtn", "sideBtn", "perspBtn",
     "auxBtn", "refBtn", "auxMenu", "refMenu", "coordHud",
     "auxGrid", "auxGridFine", "auxAxes", "auxOrigin",
     "refPersonStand", "refPersonLying", "refDoor21", "refDoor17",
     "trimStartBtn", "trimEndBtn", "trimClearBtn", "trimCopyBtn"]
        .forEach(function (id) {
            var el = document.getElementById(id);
            if (!el) _els_missing.push(id);
            els[id] = el;
        });
    if (_els_missing.length) {
        console.error("els 缺元素: " + _els_missing.join(","));
    }

    /* metaBox / trimBox 默认折叠，右上角 ⓘ/✂ 按钮切换 — 避免用户关心点云时竖着两块面板。
     * 折叠状态看着像隐藏，但 meta 是诊断信息、trim 是剪辑工具，平时不碍视线。 */
    if (els.metaToggle) els.metaToggle.addEventListener("click", function () {
        els.metaBox.classList.toggle("open");
        els.metaToggle.textContent = els.metaBox.classList.contains("open") ? "ⓘ meta ×" : "ⓘ meta";
    });
    if (els.trimToggle) els.trimToggle.addEventListener("click", function () {
        els.trimBox.classList.toggle("open");
        els.trimToggle.textContent = els.trimBox.classList.contains("open") ? "✂ trim ×" : "✂ trim";
    });

    /* ---- 飞行模式（我的世界旁观者式） -------------------------------------------------------
     * F 切入（从当前 controls 视线无缝续接 yaw/pitch），ESC 或再按 F 退回轨道模式。
     * 指针锁定后鼠标直接控视角；WASD 沿视线(含俯仰)平移，空格/Shift 走世界+Z。
     * 模式独立变量集中在 S.fly，切换不动 controls 状态，退出可无感回轨道。 */
    function fly_enter() {
        /* 从轨道位姿续接：yaw/pitch 从实际视线反推，保留现有 up (roll)，进入零跳变。
         * up 在飞行期间不动 — fly_apply_pose 只用 fwd 调 lookAt，up 保持 roll；
         * 退出时把 up 恢复为进入时刻的值，与 Trackball 上次同步时一致。 */
        var d = new THREE.Vector3();
        S.camera.getWorldDirection(d);
        var ng = L.fly_aim_from_dir([d.x, d.y, d.z]);
        /* 钳 pitch 进 FLY_PITCH_LIMIT：相机从 Orbit/Trackball 极端俯视切飞行时，
         * 若不钳，第一帧 fly_apply_pose 时 lookAt(up=+Z) 会因 fwd 近齐 up 走入奇异分支
         * 把位姿"弹"成某一确定朝向 —— 用户看到的就是飞行切入瞬间抬头突变。 */
        if (ng[1] > L.FLY_PITCH_LIMIT) ng[1] = L.FLY_PITCH_LIMIT;
        else if (ng[1] < -L.FLY_PITCH_LIMIT) ng[1] = -L.FLY_PITCH_LIMIT;
        S.fly = { keys: {}, yaw: ng[0], pitch: ng[1], speed_mult: 1, on: true,
                  saved_up: S.camera.up.clone() };
        S.controls.enabled = false;
        if (S.renderer.domElement.requestPointerLock) S.renderer.domElement.requestPointerLock();
        if (els.flyHud) els.flyHud.style.display = "block";
        /* 进入瞬间不动 up、不重设姿态：轨道 quaternion 本身已是目标姿态。 */
    }
    function fly_exit() {
        if (!S.fly) return;
        /* Trackball/OrbitControls 内部把 camera.up 当作 roll 锚点；退出恢复 roll，才能让
         * Trackball._eye 重新建立且不反弹。*/
        S.camera.up.copy(S.fly.saved_up);
        S.fly.on = false; S.fly = null;
        if (document.exitPointerLock) document.exitPointerLock();
        if (els.flyHud) els.flyHud.style.display = "none";
        fly_sync_to_controls();
        S.controls.enabled = true;
    }
    /* 退出时把飞行位姿写回 controls.target：摆在相机正前方 1m，下次进轨道视角不跳变。
     * 注意：不要在这里 controls.update() —— Trackball 会按内部 _eye 重写位姿，
     * 触发"突变"的就是这一步。锚点只记录，update 交给 tick() 常态调用。 */
    function fly_sync_to_controls() {
        var c = S.camera, t = S.controls.target;
        var d = new THREE.Vector3();
        c.getWorldDirection(d);
        t.copy(c.position).addScaledVector(d, 1);
    }
    function fly_tick(dt) {
        var f = S.fly;
        if (!f || !f.on) return;
        var ax = L.fly_axes(f.yaw, f.pitch);
        var v = L.FLY_SPEED_MPS * f.speed_mult * dt;
        var mv = [0, 0, 0];
        if (f.keys.KeyW) { mv[0] += ax.fwd[0]; mv[1] += ax.fwd[1]; mv[2] += ax.fwd[2]; }
        if (f.keys.KeyS) { mv[0] -= ax.fwd[0]; mv[1] -= ax.fwd[1]; mv[2] -= ax.fwd[2]; }
        if (f.keys.KeyD) { mv[0] += ax.right[0]; mv[1] += ax.right[1]; }
        if (f.keys.KeyA) { mv[0] -= ax.right[0]; mv[1] -= ax.right[1]; }
        if (f.keys.Space) mv[2] += 1;
        if (f.keys.ShiftLeft || f.keys.ShiftRight) mv[2] -= 1;
        var mlen = Math.hypot(mv[0], mv[1], mv[2]);
        if (mlen > 0) {
            var s = v / mlen;
            S.camera.position.x += mv[0] * s;
            S.camera.position.y += mv[1] * s;
            S.camera.position.z += mv[2] * s;
            /* 同步 target 在相机前方，避免退出飞行时 controls 拉回旧锚点。 */
            fly_sync_to_controls();
        }
        /* 每帧都落实姿态：用户不按移动键、只动鼠标时，yaw/pitch 也要随帧生效；
         * 原来只在 mlen>0 或 mousemove 事件发生时才 lookAt，"只看不动"视角不会更新。 */
        fly_apply_pose();
    }
    function fly_on_mouse(ev) {
        if (!S.fly || !S.fly.on) return;
        var ng = L.fly_aim(S.fly.yaw, S.fly.pitch, ev.movementX || 0, ev.movementY || 0, L.FLY_MOUSE_SENS);
        S.fly.yaw = ng[0]; S.fly.pitch = ng[1];
        fly_apply_pose();
    }
    /* 把 (yaw,pitch) 落到相机位姿：up 临时置 (0,0,1) 防翻转，lookAt(位置 + fwd)。
     * 飞行期间 pitch 被钳在 ±85°，fwd 与 (0,0,1) 夹角 ≥5°，lookAt 永远走非奇异分支。
     * MC/旁观者模式：roll 锁零（横平竖直）、pitch 不过 ±85° 就不会翻转。 */
    function fly_apply_pose() {
        var ax = L.fly_axes(S.fly.yaw, S.fly.pitch);
        var p = S.camera.position;
        S.camera.up.set(0, 0, 1);   /* 飞行期间锁零 roll，多余旋转一律由 lookAt 清除 */
        S.camera.lookAt(p.x + ax.fwd[0], p.y + ax.fwd[1], p.z + ax.fwd[2]);
    }
    document.addEventListener("pointerlockchange", function () {
        /* 用户按 ESC(浏览器原生退出指针锁) → 同步退出飞行，保证 S.fly 状态一致。 */
        if (!document.pointerLockElement && S.fly && S.fly.on) fly_exit();
        /* create_view 后等真正 unlock：此刻才把 controls.enabled 放回来。 */
        if (!document.pointerLockElement && S.controls_pending_enable_after_unlock) {
            S.controls_pending_enable_after_unlock = false;
            S.controls.enabled = true;
        }
    });
    window.addEventListener("mousemove", function (ev) {
        if (document.pointerLockElement === (S.renderer && S.renderer.domElement)) fly_on_mouse(ev);
    });
    window.addEventListener("wheel", function (ev) {
        if (!S.fly || !S.fly.on) return;
        ev.preventDefault();
        var m = S.fly.speed_mult * (ev.deltaY < 0 ? 1.25 : 0.8);
        S.fly.speed_mult = Math.min(8, Math.max(0.1, m));
    }, { passive: false });

    function status(msg, is_err) {
        els.status.textContent = msg;
        els.status.style.color = is_err ? "#f66" : "#8f8";
    }

    // ---- 载入 ------------------------------------------------------------------
    els.pickBtn.addEventListener("click", function () { els.dirInput.click(); });
    els.dirInput.addEventListener("change", function (ev) {
        var files = Array.from(ev.target.files || []);
        var metaF = files.find(function (f) { return f.name === "meta.json"; });
        var binF = files.find(function (f) { return f.name === "points.bin"; });
        if (!metaF || !binF) { status("目录里需同时有 meta.json 和 points.bin", true); return; }
        load(metaF, binF);
    });

    function load(metaFile, binFile) {
        status("载入 meta…");
        return metaFile.text().then(function (txt) {
            S.meta = JSON.parse(txt);
            trim_clear();
            return binFile.arrayBuffer();
        }).then(function (buf) {
            status("解析点云…");
            var t0 = performance.now();
            if (buf.byteLength % L.STRIDE_BYTES !== 0) {
                throw new Error("points.bin 大小不是 " + L.STRIDE_BYTES + " 的整数倍: " + buf.byteLength);
            }
            S.buf_f32 = new Float32Array(buf);
            S.total_pts = buf.byteLength / L.STRIDE_BYTES;
            S.frames = L.frame_slice(S.meta);
            S.fps = L.default_fps(S.meta);
            /* 滑块范围随会话长度：原 <input max="0"> 导致 value 被裁判为中 0，
             * 播放时 set_idx 赋 value 被浏览器截到 0 → 时间轴永远不滑。 */
            els.slider.max = String(Math.max(0, S.frames.length - 1));

            build_geometry();
            S.range = compute_range();
            paint_colours();
            els.metaBox.textContent = JSON.stringify({
                sid: S.meta.session_id, frames: S.frames.length,
                total_points: S.total_pts, fps: S.fps,
                duration: S.meta.duration_sec,
                intensity_range: S.range,
            }, null, 1);
            status("就绪 (" + Math.round(performance.now() - t0) + "ms)");
            set_idx(0);
            play(true);
        }).catch(function (e) {
            status("失败: " + e.message, true);
            console.error(e);
            throw e;
        });
    }

    // 侧栏按 sid 调：从本服务直接拿 meta/bin，不走 webkitdirectory
    window.__load_session_sid = function (sid) {
        return load(
            { name: "meta.json",   text: function () { return fetch("/api/file?sid=" + encodeURIComponent(sid) + "&name=meta.json").then(function (r) { if (!r.ok) throw new Error("meta HTTP " + r.status); return r.text(); }); } },
            { name: "points.bin",  arrayBuffer: function () { return fetch("/api/file?sid=" + encodeURIComponent(sid) + "&name=points.bin").then(function (r) { if (!r.ok) throw new Error("bin HTTP " + r.status); return r.arrayBuffer(); }); } }
        );
    };

    // 一次性灌满全量 geometry（position 7 槽位/点；切帧只动 drawRange）。
    // 1.42M 点 × 12B ≈ 17MB GPU buffer，正经独显/核显都吃得下。
    function build_geometry() {
        if (S.points) { S.scene.remove(S.points); S.geo.dispose(); }
        var pos = new Float32Array(S.total_pts * 3);
        S.colour = new Float32Array(S.total_pts * 3);
        var src = S.buf_f32;
        for (var p = 0; p < S.total_pts; p++) {
            var s = p * L.STRIDE_F32, d = p * 3;
            pos[d] = src[s]; pos[d + 1] = src[s + 1]; pos[d + 2] = src[s + 2];
        }
        S.geo = new THREE.BufferGeometry();
        S.geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        S.geo.setAttribute("color", new THREE.BufferAttribute(S.colour, 3));
        var mat = new THREE.PointsMaterial({ size: 0.03, vertexColors: true, sizeAttenuation: true });
        S.points = new THREE.Points(S.geo, mat);
        S.points.frustumCulled = false;
        S.scene.add(S.points);
    }

    // 强度分位窗：对本会话每帧各取抽稀样本（lib 已封装 1/16 抽点）
    function compute_range() {
        var frames4 = [];
        for (var i = 0; i < S.frames.length; i++) {
            var f = S.frames[i];
            frames4.push(L.strided_f32_copy(S.buf_f32, f.start_pts, Math.min(f.count, 4096), L.STRIDE_F32));
        }
        return L.pick_intensity_range(frames4);
    }

    // 三档着色：lut/亮到白（默认）、lut2/亮到黄（高亮不腻）、gray/纯灰度
    var LUTS = {
        lut: [[0,0,0],[0.35,0.12,0.35],[0,0.55,0.60],[0.35,0.90,0.65],[1,1,1]],
        lut2: [[0,0,0],[0.10,0.20,0.50],[0,0.50,0.70],[0.80,0.60,0.20],[1,0.92,0.35]],
        gray: null,  // 特殊路径
    };

    function intensity_rgb(t, lut) {
        if (t <= 0) return lut[0];
        if (t >= 1) return lut[lut.length - 1];
        var x = t * (lut.length - 1), i = Math.floor(x), f = x - i;
        var a = lut[i], b = lut[i + 1];
        return [a[0] + (b[0] - a[0]) * f,
                a[1] + (b[1] - a[1]) * f,
                a[2] + (b[2] - a[2]) * f];
    }

    function paint_colours() {
        var lo = S.range.lo, hi = S.range.hi;
        var src = S.buf_f32, dst = S.colour;
        var mode = els.lutSel ? els.lutSel.value : "lut";
        for (var p = 0; p < S.total_pts; p++) {
            var t = L.intensity_to_gray(src[p * L.STRIDE_F32 + 3], lo, hi);
            var r, g, b;
            if (mode === "gray") { r = g = b = t; }
            else {
                var rgb = intensity_rgb(t, LUTS[mode] || LUTS.lut);
                r = rgb[0]; g = rgb[1]; b = rgb[2];
            }
            var d = p * 3;
            dst[d] = r; dst[d + 1] = g; dst[d + 2] = b;
        }
        S.geo.attributes.color.needsUpdate = true;
    }

    // ---- 渲染场景 -----------------------------------------------------------------
    function setup_scene() {
        var w = window.innerWidth, h = window.innerHeight;
        S.renderer = new THREE.WebGLRenderer({ antialias: true });
        S.renderer.setSize(w, h);
        S.renderer.setClearColor(0x101416);
        document.getElementById("view").appendChild(S.renderer.domElement);

        S.scene = new THREE.Scene();
        S.camera = new THREE.PerspectiveCamera(62, w / h, 0.05, 400);
        S.cam_persp = S.camera;
        S.axes = new THREE.AxesHelper(1.2);                          // 雷达原点三轴
        S.scene.add(S.axes);
        S.grid = new THREE.GridHelper(40, 40, 0x335533, 0x223322); // 1m 网格
        S.grid.rotation.x = Math.PI / 2;                              // 从 XZ → XY 平面（z-up 对齐）
        S.scene.add(S.grid);
        S.grid_fine = new THREE.GridHelper(40, 400, 0x244024, 0x182818);  // 0.1m 细格
        S.grid_fine.rotation.x = Math.PI / 2;
        S.grid_fine.visible = false;  // 默认关
        S.scene.add(S.grid_fine);
        S.originBall = new THREE.Mesh(
            new THREE.SphereGeometry(0.09, 12, 12),
            new THREE.MeshBasicMaterial({ color: 0x66ccff }));
        S.scene.add(S.originBall);

        // 自由轨迹球: 无极点,任意方向无限旋转（用户要的"不卡住"轨道）
        if (typeof THREE.TrackballControls === "function") {
            S.controls = new THREE.TrackballControls(S.camera, S.renderer.domElement);
            S.controls.rotateSpeed = 1.8;
            S.controls.zoomSpeed = 1.4;
            S.controls.panSpeed = 0.7;
            S.controls.noZoom = false;
            S.controls.noPan = false;
            S.controls.staticMoving = true;
            S.controls.dynamicDampingFactor = 0.3;
        } else {
            S.controls = new THREE.OrbitControls(S.camera, S.renderer.domElement);
        }
        (function () {
            /* 启动恢复上次的视图预设；本地记忆坏掉(home key 被删)就回默认 home */
            var v = ls_get_raw("view_preset", "home");
            try { apply_view_preset(v); } catch (e) { apply_view_preset("home"); }
        })();
        window.addEventListener("resize", on_resize);
        S.last_ts = performance.now();
        requestAnimationFrame(tick);
    }

    /* 雷达极坐标视角预设：pos_dir=相机离开雷达的方向(单位向量)、pos_dist=距离。
     * 这两个预设与 reset_cam 分离 — 因为 reset_cam 只在首次 setup_scene 时跑。 */
    var VIEW_RESET = { pos: [ -3.5, -4, 2.8 ], tgt: [ 2.5, 0, 0.6 ] };   // 雷达后上方看前方（原默认）
    /* 正视图：从雷达正后方向前方（+X 方向）平视 — 第二人称开车视角。
     * 相机放在雷达后方 6m、高 1.6m（人眼高度），看雷达前方 5m 处。 */
    var VIEW_FRONT = { pos: [ -6, 0, 1.6 ], tgt: [ 5, 0, 1.0 ] };

    function reset_cam() {
        /* Home 归位：回到 VIEW_RESET 且投影=透视 */
        apply_view_preset("home");
    }
    function front_cam() {
        /* T/正视按钮：切到雷达正后前向（HR-04 之前的历史预设，保 61° 透视） */
        create_view(VIEW_FRONT);
    }

    /* HR-04: 7/1/3/0/Home 视图预设应用。persp 保持并复用 S.cam_persp；ortho 每
     * 次新建（简单不做缓存——切换低频）。TrackballControls.object 同步重绑。 */
    function apply_view_preset(name) {
        var p = L.view_preset(name);
        if (p.proj === "ortho") {
            var hw = p.ortho_half_w, hh = p.ortho_half_h;
            var newCam = new THREE.OrthographicCamera(-hw, hw, -hh, hh, 0.1, 200);
            /* top 视图屏幕横=x、纵=-y；front 屏幕横=y、纵=z；side 屏幕横=-x、纵=z */
        } else {
            /* 透视：往 S.cam_persp 写新位姿，避免重建改 controls */
            var newCam = S.cam_persp;
        }
        /* 飞行态接管 pointer lock：切视图必须先退飞行 */
        if (S.fly && S.fly.on) fly_exit();
        S.camera = newCam;
        if (S.controls) {
            S.controls.object = newCam;
            if (p.proj === "ortho") newCam.zoom = 1;
        }
        newCam.up.set(p.up[0], p.up[1], p.up[2]);
        newCam.position.set(p.pos[0], p.pos[1], p.pos[2]);
        S.controls.target.set(p.tgt[0], p.tgt[1], p.tgt[2]);
        newCam.lookAt(p.tgt[0], p.tgt[1], p.tgt[2]);
        S.controls.update();
        S.view_name = name;
        /* 视图名作为字符串直接写 LS，不走 ls_set 的布尔化通道 */
        try { localStorage.setItem(L.LS_PREFIX + "view_preset", name); } catch (e) {}
        hud_refresh_view_label();
    }

    function hud_refresh_view_label() {
        /* 在 #hud 尾部贴一个「视图」段；只在 HUD 更新时顺带覆写。 */
        if (!els.hud) return;
        var sp2 = document.getElementById("viewLabel");
        if (!sp2) {
            sp2 = document.createElement("span");
            sp2.id = "viewLabel";
            sp2.style.color = "#aef";
            els.hud.appendChild(document.createTextNode("　"));
            els.hud.appendChild(sp2);
        }
        sp2.textContent = "[" + S.view_name + (S.camera && S.camera.isOrthographicCamera ? "/ortho" : "/persp") + "]";
    }

    /* 应用一个视角预设：退出飞行（pointer lock 异步解锁），然后**立即**摆位 + update。
     * 注意：fly_exit 同步把 S.controls.enabled=true，pointer lock async 解锁期间用户
     * 立即拖鼠标时 Trackball 用 pageX/Y — 锁内 pageX/Y 不更新，Trackball 看起来"拖不动"。
     * 修复：在真正 unlock 之前把 controls.enabled 保持 false，pointerlockchange 时重置。*/
    function create_view(v) {
        var was_flying = !!(S.fly && S.fly.on);
        if (was_flying) {
            /* 同步退出飞行 + 暂时把 controls 锁住，等 pointerlockchange 真正解锁后再放。 */
            fly_exit();
            S.controls.enabled = false;   /* fly_exit 会 set true — 覆盖之 */
            S.controls_pending_enable_after_unlock = true;
        }
        S.camera.up.set(0, 0, 1);
        S.camera.position.set(v.pos[0], v.pos[1], v.pos[2]);
        S.controls.target.set(v.tgt[0], v.tgt[1], v.tgt[2]);
        S.controls.update();
    }

    function on_resize() {
        var w = window.innerWidth, h = window.innerHeight;
        if (S.camera.isOrthographicCamera) {
            /* 正交：保 half_w 不变，按纵横比调 half_h（可视区域永远够宽） */
            var half_w = L.ORTHO_HALF_W, half_h = half_w * (h / w);
            S.camera.left = -half_w; S.camera.right = half_w;
            S.camera.top = half_h; S.camera.bottom = -half_h;
        } else {
            S.camera.aspect = w / h;
        }
        S.camera.updateProjectionMatrix();
        S.renderer.setSize(w, h);
    }

    // ---- 播放/寻址 ------------------------------------------------------------------
    function set_idx(i) {
        var n = S.frames ? S.frames.length : 0;
        if (!n) return;
        S.idx = Math.min(Math.max(i, 0), n - 1);
        var f = S.frames[S.idx];
        S.geo.setDrawRange(f.start_pts, f.count);
        els.slider.value = S.idx;
        var t = (f.bag_time_sec != null) ? L.format_hhmmss(f.bag_time_sec - S.frames[0].bag_time_sec) : "--:--";
        els.hud.textContent =
            "帧 " + (S.idx + 1) + "/" + n +
            "  seq=" + f.seq +
            "  t=" + t +
            "  点=" + f.count +
            "  " + S.fps + "Hz×" + S.speed;
        hud_refresh_view_label();
        els.frameInfo.textContent = "stamp=" + f.stamp_sec + "." +
            String(f.stamp_nanosec).padStart(9, "0");
    }

    function play(on) {
        if (!S.frames) return;
        S.playing = on == null ? !S.playing : !!on;
        els.playBtn.textContent = S.playing ? "⏸" : "▶";
    }

    function tick(now) {
        requestAnimationFrame(tick);
        var dt = (now - S.last_ts) / 1000;
        S.last_ts = now;
        fly_tick(Math.min(dt, 0.1));   /* 大跳帧(切后台回来)限幅，防止瞬移 */
        if (S.playing && S.frames && S.frames.length) {
            S.acc += dt * S.speed;
            var step = 1 / S.fps;
            while (S.acc >= step) {
                S.acc -= step;
                var nxt = S.idx + 1;
                if (nxt >= S.frames.length) {
                    if (els.loopChk.checked) { nxt = 0; } else { play(false); break; }
                }
                set_idx(nxt);
            }
        }
        /* 飞行态跳过 controls.update()：Trackball 会按内部 _eye/_lastRotation 重写相机
         * 位姿（含 roll），抹掉我们 lookAt 的结果 ——"突变"就是这里撞击的。 */
        if (!S.fly || !S.fly.on) S.controls.update();
        S.renderer.render(S.scene, S.camera);
    }

    function step(d) {
        play(false);
        set_idx(S.idx + d);
    }

    // ---- 输入 -----------------------------------------------------------------------
    els.playBtn.addEventListener("click", function () { play(); });
    els.speedSel.addEventListener("change", function () {
        S.speed = parseFloat(els.speedSel.value);
        set_idx(S.idx);
    });
    if (els.resetBtn) els.resetBtn.addEventListener("click", reset_cam);
    if (els.frontBtn) els.frontBtn.addEventListener("click", front_cam);
    if (els.topBtn) els.topBtn.addEventListener("click", function () { apply_view_preset("top"); });
    if (els.sideBtn) els.sideBtn.addEventListener("click", function () { apply_view_preset("side"); });
    if (els.perspBtn) els.perspBtn.addEventListener("click", function () { apply_view_preset("persp"); });

    /* ---- HR-04 aux/refs 菜单 + localStorage ---- */
    function ls_get(k, def) {
        try { var v = localStorage.getItem(L.LS_PREFIX + k); return v == null ? def : v === "1"; }
        catch (e) { return def; }
    }
    function ls_get_raw(k, def) {
        try { var v = localStorage.getItem(L.LS_PREFIX + k); return v == null ? def : v; }
        catch (e) { return def; }
    }
    function ls_set(k, v) {
        try { localStorage.setItem(L.LS_PREFIX + k, v ? "1" : "0"); } catch (e) {}
    }

    /* aux：4 个显隐开关 */
    var AUX = [
        { id: "auxGrid",      key: "aux_grid",       obj: function () { return S.grid; },       def: true },
        { id: "auxGridFine",  key: "aux_grid_fine",  obj: function () { return S.grid_fine; },  def: false },
        { id: "auxAxes",      key: "aux_axes",       obj: function () { return S.axes; },       def: true },
        { id: "auxOrigin",    key: "aux_origin",     obj: function () { return S.originBall; }, def: true },
    ];
    function aux_apply(a, on) {
        var o = a.obj(); if (o) o.visible = on;
        els[a.id].checked = on;
        ls_set(a.key, on);
    }
    AUX.forEach(function (a) {
        els[a.id].addEventListener("change", function () { aux_apply(a, els[a.id].checked); });
    });
    /* 首批应用（读 localStorage） */
    function aux_init_from_ls() {
        AUX.forEach(function (a) { aux_apply(a, ls_get(a.key, a.def)); });
    }

    /* refs：4 个参照物 */
    function ref_material() {
        return new THREE.MeshBasicMaterial({
            color: 0x888888, transparent: true, opacity: 0.25, wireframe: true,
        });
    }
    function ref_box(sx, sy, sz) {
        var m = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), ref_material());
        /* 包围盒几何 center 默认在原点，地面支撑要沿 z 提半个尺寸 */
        m.position.z = sz / 2;
        return m;
    }
    var REFS = [
        { id: "refPersonStand", key: "ref_person_stand", build: function () {
            var g = new THREE.Group();
            g.add(ref_box(0.5, 0.4, 1.8));
            /* 头：0.2m 的球，头顶 1.8m */
            var head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 12), ref_material());
            head.position.z = 1.8 + 0.11;
            g.add(head);
            return g;
        }},
        { id: "refPersonLying", key: "ref_person_lying", build: function () {
            var g = new THREE.Group();
            g.add(ref_box(0.4, 1.8, 0.4));   /* 横躺：沿 y 轴延伸 */
            var head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 12), ref_material());
            head.position.set(0, 0.9 + 0.11, 0.2);
            g.add(head);
            return g;
        }},
        { id: "refDoor21", key: "ref_door_21", build: function () {
            /* 门框：宽 1m 高 2.1m，两柱+一梁 */
            var g = new THREE.Group();
            var post = ref_box(0.05, 0.05, 2.1);
            post.position.set(-0.5, 0, 1.05); g.add(post);
            var post2 = ref_box(0.05, 0.05, 2.1);
            post2.position.set(0.5, 0, 1.05); g.add(post2);
            var beam = new THREE.Mesh(new THREE.BoxGeometry(1.05, 0.05, 0.05), ref_material());
            beam.position.set(0, 0, 2.1); g.add(beam);
            return g;
        }},
        { id: "refDoor17", key: "ref_door_17", build: function () {
            var g = new THREE.Group();
            var post = ref_box(0.05, 0.05, 1.7);
            post.position.set(-0.5, 0, 0.85); g.add(post);
            var post2 = ref_box(0.05, 0.05, 1.7);
            post2.position.set(0.5, 0, 0.85); g.add(post2);
            var beam = new THREE.Mesh(new THREE.BoxGeometry(1.05, 0.05, 0.05), ref_material());
            beam.position.set(0, 0, 1.7); g.add(beam);
            return g;
        }},
    ];
    function ref_toggle(r, on) {
        if (on && !S.refs[r.key]) {
            var g = r.build();
            g.position.set(3, 0, 0);   /* 默认放在雷达前 3m */
            S.scene.add(g);
            S.refs[r.key] = g;
        } else if (!on && S.refs[r.key]) {
            S.scene.remove(S.refs[r.key]);
            delete S.refs[r.key];
        }
        els[r.id].checked = on;
        ls_set(r.key, on);
    }
    REFS.forEach(function (r) {
        els[r.id].addEventListener("change", function () { ref_toggle(r, els[r.id].checked); });
    });
    function refs_init_from_ls() {
        REFS.forEach(function (r) { ref_toggle(r, ls_get(r.key, false)); });
    }

    /* aux/refs 菜单展开按钮 */
    if (els.auxBtn) els.auxBtn.addEventListener("click", function () {
        els.auxMenu.classList.toggle("open");
        els.refMenu.classList.remove("open");
    });
    if (els.refBtn) els.refBtn.addEventListener("click", function () {
        els.refMenu.classList.toggle("open");
        els.auxMenu.classList.remove("open");
    });

    /* 人形拖拽：standing person 被点击且左键保持，沿地面拖 */
    var _drag_raycaster = new THREE.Raycaster();
    function bind_person_drag() {
        if (!S.renderer) return;
        S.renderer.domElement.addEventListener("mousedown", function (ev) {
            if (ev.button !== 0 || !S.refs.ref_person_stand) return;
            var ndc = new THREE.Vector2(
                (ev.clientX / window.innerWidth) * 2 - 1,
                -(ev.clientY / window.innerHeight) * 2 + 1
            );
            _drag_raycaster.setFromCamera(ndc, S.camera);
            var hits = _drag_raycaster.intersectObject(S.refs.ref_person_stand, true);
            if (hits.length > 0) {
                S.drag_person = S.refs.ref_person_stand;
                if (S.controls) S.controls.enabled = false;
                ev.preventDefault();
            }
        });
        window.addEventListener("mouseup", function () {
            /* 拖人形结束还原 controls：annotate 期间 controls.enabled 由 ann_toggle_mode 控制为 false，
             * 这里只在非 annotate 时才还原 — 否则 annotate 左键画框/拖gizmo 后相机又被启回，再按左键又旋转。
             * 用 typeof ANN 守卫：HR-04 listener 注册时 ANN 还没声明（var hoist），运行时 ANN.mode 一定在。 */
            if (S.drag_person) {
                S.drag_person = null;
                if (S.controls && ANN.mode === "view") S.controls.enabled = true;
            }
        });
    }
    if (els.lutSel) {
        els.lutSel.addEventListener("change", function () { if (S.geo) paint_colours(); });
    }
    els.slider.addEventListener("input", function () {
        play(false);
        set_idx(parseInt(els.slider.value, 10));
    });
    window.addEventListener("keydown", function (ev) {
        if (ev.target && (ev.target.tagName === "INPUT" || ev.target.tagName === "SELECT")
            && ev.code !== "Space") { return; }
        /* 飞行态吃掉所有相机键，轨道键(空格/方向键)此时让位 */
        if (S.fly && S.fly.on) {
            if (ev.code === "KeyF") { fly_exit(); ev.preventDefault(); }
            else if (ev.code === "Escape") { fly_exit(); }
            else if (ev.code === "KeyR") { reset_cam(); ev.preventDefault(); }   /* 飞行中 R = 一键复位 */
            else if (ev.code === "KeyT") { front_cam(); ev.preventDefault(); }   /* 飞行中 T = 正视图 */
            else if (["KeyW", "KeyA", "KeyS", "KeyD", "Space", "ShiftLeft", "ShiftRight"].indexOf(ev.code) >= 0) {
                S.fly.keys[ev.code] = true;
                ev.preventDefault();
            }
            return;
        }
        if (ev.code === "Space") { play(); ev.preventDefault(); }
        else if (ev.code === "ArrowLeft") { step(ev.shiftKey ? -10 : -1); ev.preventDefault(); }
        else if (ev.code === "ArrowRight") { step(ev.shiftKey ? 10 : 1); ev.preventDefault(); }
        else if (ev.code === "KeyF") { fly_enter(); ev.preventDefault(); }
        else if (ev.code === "KeyR") { reset_cam(); ev.preventDefault(); }
        else if (ev.code === "KeyT") { front_cam(); ev.preventDefault(); }
        /* ---- HR-04 新键（都只轨道态生效，飞行时语义错位） ---- */
        else if (ev.code === "Digit7") { apply_view_preset("top"); ev.preventDefault(); }
        else if (ev.code === "Digit1") { apply_view_preset("front"); ev.preventDefault(); }
        else if (ev.code === "Digit3") { apply_view_preset("side"); ev.preventDefault(); }
        else if (ev.code === "Digit0") { apply_view_preset("persp"); ev.preventDefault(); }
        else if (ev.code === "Home") { reset_cam(); ev.preventDefault(); }
        else if (ev.code === "KeyP") { snap_nearest_at_cursor(); ev.preventDefault(); }
        else if (ev.code === "KeyM") { measure_step(); ev.preventDefault(); }
    });

    /* ---- HR-04 坐标读数 + P/M 逻辑 ---- */
    var _raycaster = new THREE.Raycaster();

    /* 鼠标 NDC → 相机射线 → 平面 z=0 交点 [x,y]。无交点返 null。 */
    function cursor_ground_xy(ev) {
        if (!S.camera || !S.renderer) return null;
        var ndc = new THREE.Vector2(
            (ev.clientX / window.innerWidth) * 2 - 1,
            -(ev.clientY / window.innerHeight) * 2 + 1
        );
        _raycaster.setFromCamera(ndc, S.camera);
        var o = _raycaster.ray.origin, d = _raycaster.ray.direction;
        return L.ray_ground_intersect([o.x, o.y, o.z], [d.x, d.y, d.z]);
    }

    window.addEventListener("mousemove", function (ev) {
        if (!S.camera) return;
        var g = cursor_ground_xy(ev);
        S.mouse_xy_ground = g;
        if (els.coordHud) {
            els.coordHud.textContent = g
                ? ("(x,y): " + g[0].toFixed(2) + ", " + g[1].toFixed(2))
                : "(x,y): —";
        }
        /* 拖拽人形 */
        if (S.drag_person && g) {
            S.drag_person.position.x = g[0];
            S.drag_person.position.y = g[1];
        }
    });

    /* P 键：快照当前光标下最近点 */
    function snap_nearest_at_cursor() {
        if (!S.frames || !S.mouse_xy_ground) { status("先移动鼠标", true); return; }
        var f = S.frames[S.idx];
        var slice = L.strided_f32_copy(S.buf_f32, f.start_pts, f.count, L.STRIDE_F32);
        var r = L.find_nearest_xy(slice, S.mouse_xy_ground[0], S.mouse_xy_ground[1]);
        if (!r) { status("点云空", true); return; }
        S.snap_pt = { x: r.x, y: r.y, z: r.z, i: r.i, seq: f.seq, d_xy: r.d_xy };
        status("快照 seq=" + r.seq + " (" + r.x.toFixed(2) + ", " + r.y.toFixed(2) +
            ", " + r.z.toFixed(2) + ")  i=" + r.i.toFixed(0) +
            "  (距光标 " + r.d_xy.toFixed(2) + "m)", false);
        /* 高亮标记：复用 snap 的小球，生命周期到下次 P */
        if (!S._snap_marker) {
            S._snap_marker = new THREE.Mesh(
                new THREE.SphereGeometry(0.12, 12, 12),
                new THREE.MeshBasicMaterial({ color: 0xffeb3b }));
            S.scene.add(S._snap_marker);
        }
        S._snap_marker.position.set(r.x, r.y, r.z);
        S._snap_marker.visible = true;
    }

    /* M 键：标尺 三态（无尺→起首尺→出尺→清尺） */
    function measure_step() {
        /* 第三态：已出线，清 */
        if (S.measure.line) {
            measure_clear();
            status("标尺已清除", false);
            return;
        }
        /* 第二态：有 p1，出尺 */
        if (S.measure.p1 && S.mouse_xy_ground) {
            var p1 = S.measure.p1.slice(), p2 = S.mouse_xy_ground.slice();
            p1[2] = 0; p2[2] = 0;
            var d = L.measure_dist(p1, p2);
            measure_render(p1, p2, d);
            status("距离 " + L.measure_format(d) +
                "  (p1=" + p1[0].toFixed(2) + "," + p1[1].toFixed(2) +
                "  p2=" + p2[0].toFixed(2) + "," + p2[1].toFixed(2) + ")", false);
            S.measure.p1 = null;
            return;
        }
        /* 第一态：起首尺 */
        if (!S.mouse_xy_ground) { status("先移动鼠标到地面", true); return; }
        S.measure.p1 = S.mouse_xy_ground.slice();
        status("标尺: 起点 (" + S.measure.p1[0].toFixed(2) + ", " + S.measure.p1[1].toFixed(2) +
            ")，移动鼠标后按 M 定终点", false);
    }

    function measure_render(p1, p2, d) {
        measure_clear_line_only();
        var g = new THREE.Group();
        var geo = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(p1[0], p1[1], p1[2]),
            new THREE.Vector3(p2[0], p2[1], p2[2]),
        ]);
        var line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: 0xff5252, linewidth: 2 }));
        g.add(line);
        [p1, p2].forEach(function (p) {
            var ball = new THREE.Mesh(
                new THREE.SphereGeometry(0.08, 12, 12),
                new THREE.MeshBasicMaterial({ color: 0xff5252 }));
            ball.position.set(p[0], p[1], p[2]);
            g.add(ball);
        });
        /* 距离标签：Sprite 文字（canvas 转 texture） */
        var label = make_text_sprite(L.measure_format(d));
        label.position.set((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, 0.5);
        g.add(label);
        S.scene.add(g);
        S.measure.line = g;
    }
    function measure_clear_line_only() {
        if (S.measure.line) {
            S.scene.remove(S.measure.line);
            S.measure.line = null;
        }
    }
    function measure_clear() {
        measure_clear_line_only();
        S.measure.p1 = null;
    }

    /* 文字标签：canvas → Sprite。62 字符是经验帧宽，能装下 "99.99m"。 */
    function make_text_sprite(text) {
        var c = document.createElement("canvas");
        c.width = 256; c.height = 64;
        var ctx = c.getContext("2d");
        ctx.fillStyle = "rgba(0,0,0,0.7)"; ctx.fillRect(0, 0, c.width, c.height);
        ctx.font = "bold 32px Consolas";
        ctx.fillStyle = "#ffeb3b"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(text, 128, 32);
        var tex = new THREE.CanvasTexture(c);
        var mat = new THREE.SpriteMaterial({ map: tex, transparent: true });
        var sp = new THREE.Sprite(mat);
        sp.scale.set(2, 0.5, 1);
        return sp;
    }
    window.addEventListener("keyup", function (ev) {
        if (S.fly && S.fly.on) delete S.fly.keys[ev.code];
    });

    // ---- 剪辑面板（HR-03）：选 seq 区间 → 生成 trim.js 命令给用户跑 ---------------------
    // UI 不落盘（浏览器安全模型禁止）；trim.js 是唯一权威切片。
    var TRIM = { s_idx: null, e_idx: null };

    function trim_seq_of(idx) { return S.frames ? S.frames[idx].seq : null; }

    function trim_refresh_ui() {
        var s = TRIM.s_idx, e = TRIM.e_idx;
        /* 不再按 has_meta 强制展开：用户自己点 ✂ 按钮决定 (默认折叠不挡视野) */
        if (!S.meta) return;
        if (s == null && e == null) {
            els.trimInfo.textContent = "未选区间";
            els.trimCmd.value = "";
            return;
        }
        var s_seq = s != null ? trim_seq_of(s) : null;
        var e_seq = e != null ? trim_seq_of(e) : null;
        var lo_seq = (s_seq != null && e_seq != null) ? Math.min(s_seq, e_seq) : null;
        var hi_seq = (s_seq != null && e_seq != null) ? Math.max(s_seq, e_seq) : null;
        els.trimInfo.textContent =
            "起点 " + (s_seq != null ? s_seq : "—") +
            "  终点 " + (e_seq != null ? e_seq : "—") +
            ((s_seq != null && e_seq != null) ?
                ("  区间 [" + lo_seq + ".." + hi_seq + "] " +
                 (hi_seq - lo_seq + 1) + " 帧") : "");
        if (s_seq != null && e_seq != null) {
            var sid = S.meta.session_id;
            var src_dir = "D:\\Code\\ldiar\\captures\\remote\\" + sid;
            els.trimCmd.value = L.trim_command_string(src_dir, lo_seq, hi_seq,
                "D:\\Code\\ldiar\\pc_apps\\human_replay");
        } else {
            els.trimCmd.value = "(还差一端，先把当前帧标成 " +
                (s_seq == null ? "起点" : "终点") + ")";
        }
    }

    function trim_clear() {
        TRIM.s_idx = null; TRIM.e_idx = null;
        if (els.trimBox) trim_refresh_ui();
    }

    if (els.trimStartBtn) {
        els.trimStartBtn.addEventListener("click", function () {
            TRIM.s_idx = S.idx; trim_refresh_ui();
        });
        els.trimEndBtn.addEventListener("click", function () {
            TRIM.e_idx = S.idx; trim_refresh_ui();
        });
        els.trimClearBtn.addEventListener("click", trim_clear);
        els.trimCopyBtn.addEventListener("click", function () {
            var t = els.trimCmd.value;
            if (!t || t.startsWith("(")) return;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(t).then(function () {
                    status("剪辑命令已复制", false);
                }).catch(function () { trim_legacy_copy(t); });
            } else { trim_legacy_copy(t); }
        });
    }
    function trim_legacy_copy(text) {
        els.trimCmd.select();
        els.trimCmd.setSelectionRange(0, text.length);
        try { document.execCommand("copy"); status("剪辑命令已复制(legacy)", false); }
        catch (e) { status("复制失败,请手动 Ctrl+C", true); }
    }

    // ---- 下拉速度档（lib 常量） ---------------------------------------------------------
    L.PLAYBACK_SPEEDS.forEach(function (v) {
        var o = document.createElement("option");
        o.value = String(v); o.textContent = v + "×";
        if (v === 1) o.selected = true;
        els.speedSel.appendChild(o);
    });

    setup_scene();
    aux_init_from_ls();
    refs_init_from_ls();
    /* 绑定在 setup_scene 之后执行（S.renderer 才有值） */
    bind_person_drag();

    /* ================= HR-05 标注编辑层 ================= */

    var ANN = {
        mode: "view",           // view | annotate
        draw: null,             // {p0: [x,y], p1: [x,y]} 拖拽中
        selected: null,         // annotation object
        gizmoMode: "translate", // translate | rotate | scale
        axisLock: null,         // x | y | z
        ctrl: false,
        undo: null,             // lib undo_stack_new()
        clipboard: null,        // {label, size, yaw, center_offset}
        annotations: {},        // seq -> [{id, label, center, size, yaw, fixed, mesh}]
        nextId: 1,
        tc: null,               // TransformControls
        annPanel: null,
    };

    // ---- 工具 ----
    function ann_new_id() { return "ann_" + String(ANN.nextId++).padStart(3, "0"); }
    function ann_status(msg) { status(msg, false); }

    /* 模式徽章：挂在 <body>，不被 els.hud.textContent="..." 抹掉；annotate/view 一按 B 立刻可见。
     * 之前的实现走 els.viewLabel (永远 undefined → dead code)，用户按 B 完全看不到任何痕迹
     * 以为是按键没响应 — 这是 HR-05 视觉反馈漏洞。 */
    function ann_ensure_badge() {
        var b = document.getElementById("annModeBadge");
        if (b) return b;
        b = document.createElement("div");
        b.id = "annModeBadge";
        b.style.cssText = "position:absolute;top:8px;left:50%;transform:translateX(-50%);padding:3px 12px;border-radius:3px;font:12px Consolas,monospace;pointer-events:none;z-index:12;";
        document.body.appendChild(b);
        return b;
    }
    function ann_badge_refresh() {
        var b = ann_ensure_badge();
        if (ANN.mode === "annotate") {
            b.textContent = "● 标注模式 (B/V 切换 · 左键画框 · W/R/T gizmo · Enter 定稿)";
            b.style.background = "rgba(120,30,30,.85)";
            b.style.color = "#ffd6d6";
            b.style.border = "1px solid #a33";
        } else {
            b.textContent = "○ 查看模式 (按 B 进标注)";
            b.style.background = "rgba(0,0,0,.55)";
            b.style.color = "#cfd8dc";
            b.style.border = "1px solid #37474f";
        }
    }
    function ann_toggle_mode() {
        ANN.mode = ANN.mode === "annotate" ? "view" : "annotate";
        /* 进 annotate 时直接整禁 controls（不只 enableRotate）——否则左键拖画框时 Orbit/Trackball
         * 会抢先吃事件去 pan/rotate，用户看到「按住左键在旋转视角」。
         * 滚轮缩放也禁，想要缩放先按 B 退回 view。trade-off 接受：annotate 模式期间相机锁死。 */
        if (S.controls) S.controls.enabled = ANN.mode === "view";
        ann_badge_refresh();
        ann_crosshair_refresh();
        hud_refresh_view_label();
        if (ANN.mode !== "annotate") ann_clear_draw();
    }
    function ann_set_mode(m) { if (ANN.mode !== m) ann_toggle_mode(); }

    // ---- 画框 ----
    function ann_on_mousedown(e) {
        if (e.button !== 0 || ANN.mode !== "annotate" || !S.frames) return;
        /* 记录屏幕起点 — mouseup 决定是「点放」还是「拖矩形」。位移 <5px 算点放。*/
        ANN.draw = { p0: null, p1: null, sx: e.clientX, sy: e.clientY };
        S.controls.enabled = false;
        e.preventDefault();
    }
    function ann_on_mousemove(e) {
        if (!ANN.draw) return;
        /* 屏幕位移一旦超 5px 就升级成拖矩形：p0 此时才逆投影到地面，
         * 这样 1px 的鼠标抖动不会把"点放"毁成"超小矩形"。*/
        if (!ANN.draw.p1_locked) {
            var dx = e.clientX - ANN.draw.sx, dy = e.clientY - ANN.draw.sy;
            if (dx * dx + dy * dy >= 25) ANN.draw.p1_locked = true;
        }
        if (ANN.draw.p1_locked) {
            var g0 = cursor_ground_xy({ clientX: ANN.draw.sx, clientY: ANN.draw.sy });
            var g1 = cursor_ground_xy(e);
            if (g0) ANN.draw.p0 = g0;
            if (g1) ANN.draw.p1 = g1;
        }
    }
    function ann_on_mouseup(e) {
        if (e.button !== 0 || !ANN.draw) return;
        var d = ANN.draw;
        ANN.draw = null;
        /* annotate 模式下 controls.enabled 应保持 false（ann_toggle_mode 设的）；这里只在 view 时才还原，
         * 否则左键画完框松手瞬间 controls 会被启回，下一次拖动又跑去旋转视角。 */
        if (S.controls && ANN.mode === "view") S.controls.enabled = true;
        /* 区分点放 vs 拖矩形：p1_locked = 屏位移 ≥5px */
        if (!d.p1_locked) { ann_place_at_cursor(e); return; }
        if (!d.p0 || !d.p1) { ann_status("矩形两点无交点"); return; }
        var w = Math.abs(d.p1[0] - d.p0[0]), h = Math.abs(d.p1[1] - d.p0[1]);
        if (w < 0.1 || h < 0.1) { ann_status("矩形太小"); return; }
        var f = S.frames[S.idx];
        var slice = L.strided_f32_copy(S.buf_f32, f.start_pts, f.count, L.STRIDE_F32);
        var box = L.bbox_from_ground_rect(d.p0, d.p1, slice);
        var a = {
            id: ann_new_id(), label: "person",
            center: box.center, size: box.size, yaw: box.yaw,
            zmin: box.zmin, zmax: box.zmax,
            fixed: false, mesh: null,
        };
        if (!ANN.annotations[f.seq]) ANN.annotations[f.seq] = [];
        ANN.annotations[f.seq].push(a);
        ann_render_one(a, f.seq);
        ANN.undo = L.undo_stack_push(ANN.undo || L.undo_stack_new(), { op: "add", seq: f.seq, ann: a });
        ANN.selected = a;
        ann_gizmo_attach(a);
        ann_panel_write(a);
        ann_draft_save();
        ann_status("框 " + a.id + " 已创建 " + a.size[0].toFixed(2) + "×" + a.size[1].toFixed(2) + "×" + a.size[2].toFixed(2));
    }
    function ann_clear_draw() {
        /* 同步 mouseup 的守卫：annotate 模式下不动 controls.enabled */
        if (ANN.draw) { ANN.draw = null; if (S.controls && ANN.mode === "view") S.controls.enabled = true; }
    }

    /* ---- 准星放框（「Minecraft」交互） --------------------------------------
     * 光标逆投影 → 射线 → 找最近点云点（垂直距离 ≤0.5m）→ 拿不到就用射线∩z=0 → 放默认人形框。
     * 连击 200ms 门闸防误触；同 frame 半径 0.3m 内已有框时拒放。*/
    var ann_click_throttle = L.make_click_throttle(200);

    function ann_spawn_box(box, f) {
        var a = {
            id: ann_new_id(), label: "person",
            center: box.center, size: box.size, yaw: box.yaw,
            zmin: box.zmin, zmax: box.zmax,
            fixed: false, mesh: null,
        };
        if (!ANN.annotations[f.seq]) ANN.annotations[f.seq] = [];
        ANN.annotations[f.seq].push(a);
        ann_render_one(a, f.seq);
        ANN.undo = L.undo_stack_push(ANN.undo || L.undo_stack_new(), { op: "add", seq: f.seq, ann: a });
        ANN.selected = a;
        ann_gizmo_attach(a);
        ann_panel_write(a);
        ann_draft_save();
        return a;
    }
    function ann_place_at_cursor(e) {
        if (!ann_click_throttle()) { ann_status("太快了"); return; }
        if (!S.frames) return;
        var f = S.frames[S.idx];
        var slice = L.strided_f32_copy(S.buf_f32, f.start_pts, f.count, L.STRIDE_F32);
        var ndc = new THREE.Vector2(
            (e.clientX / window.innerWidth) * 2 - 1,
            -(e.clientY / window.innerHeight) * 2 + 1
        );
        _raycaster.setFromCamera(ndc, S.camera);
        var o = _raycaster.ray.origin, dr = _raycaster.ray.direction;
        var origin = [o.x, o.y, o.z], dir = [dr.x, dr.y, dr.z];
        var pick = L.pick_point_on_ray(origin, dir, slice, 0.5);
        var ground_xy = pick ? null : L.ray_ground_intersect(origin, dir);
        var box = L.human_box_from_pick(pick, ground_xy);
        if (!box) { ann_status("准星既未指到点云也未指到地面"); return; }
        /* 半径 0.3m 内已有框 → 拒放 */
        var arr = ANN.annotations[f.seq] || [];
        for (var i = 0; i < arr.length; i++) {
            var dx = arr[i].center[0] - box.center[0], dy = arr[i].center[1] - box.center[1];
            if (dx * dx + dy * dy < 0.09) { ann_status("靠太近 — 附近已有框 " + arr[i].id); return; }
        }
        var a = ann_spawn_box(box, f);
        ann_status("准星放框 " + a.id + " @(" + a.center[0].toFixed(2) + "," + a.center[1].toFixed(2) + ")" +
                   (pick ? " [点]" : " [地面]"));
    }

    /* 屏幕中心准星：annotate 模式亮，view 模式藏。鼠标移上去不拾事件。*/
    function ann_ensure_crosshair() {
        var c = document.getElementById("annCrosshair");
        if (c) return c;
        c = document.createElement("div");
        c.id = "annCrosshair";
        c.style.cssText =
            "position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);" +
            "width:24px;height:24px;pointer-events:none;z-index:13;display:none;";
        c.innerHTML =
            '<div style="position:absolute;left:50%;top:0;bottom:0;width:2px;margin-left:-1px;background:#fff;opacity:.7"></div>' +
            '<div style="position:absolute;top:50%;left:0;right:0;height:2px;margin-top:-1px;background:#fff;opacity:.7"></div>';
        document.body.appendChild(c);
        return c;
    }
    function ann_crosshair_refresh() {
        var c = ann_ensure_crosshair();
        c.style.display = ANN.mode === "annotate" ? "block" : "none";
    }

    // ---- gizmo ----
    function ann_gizmo_attach(a) {
        if (!a || !a.mesh) return;
        if (ANN.tc) { ANN.tc.detach(); S.scene.remove(ANN.tc); }
        ANN.tc = new THREE.TransformControls(S.camera, S.renderer.domElement);
        ANN.tc.setMode(ANN.gizmoMode);
        ANN.tc.attach(a.mesh);
        S.scene.add(ANN.tc);
        ANN.tc.addEventListener("dragging-changed", function (ev) {
            /* annotate 模式整体禁用 controls（ann_toggle_mode 负责），只在 view 模式且 gizmo 不在拖时才还原。
             * 否则 gizmo 拖完一瞬间 controls.enabled=true，下一次左键又跑去旋转视角。*/
            if (S.controls) S.controls.enabled = ANN.mode === "view" ? !ev.value : false;
            if (!ev.value) {
                ann_mesh_to_obj(a, a.mesh);
                ann_panel_write(a);
                ann_draft_save();
                ANN.undo = L.undo_stack_push(ANN.undo || L.undo_stack_new(), { op: "edit", seq: f_seq_of(a), ann: a });
            }
        });
        ann_gizmo_set_mode(ANN.gizmoMode);
    }
    /* annotate 模式下 controls 被禁 → 用户没了缩放/平移手段，看得清远处人形都难。
     * 这里直接给正交相机加 wheel zoom（改 camera.zoom） + 中键 pan（改 tgt/pos），
     * 与 controls 完全解耦 — 这部分独立于 OrbitControls/TrackballControls。 */
    function ann_ortho_wheel(ev) {
        if (ANN.mode !== "annotate") return;
        if (!S.camera || !S.camera.isOrthographicCamera) return;
        ev.preventDefault();
        var f = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
        S.camera.zoom = Math.min(16, Math.max(0.25, S.camera.zoom * f));
        S.camera.updateProjectionMatrix();
    }
    function ann_ortho_pan_start(ev) {
        if (ANN.mode !== "annotate" || ev.button !== 1) return;   /* 中键 pan */
        if (!S.camera || !S.camera.isOrthographicCamera) return;
        ev.preventDefault();
        ANN.pan0 = { x: ev.clientX, y: ev.clientY, cx: S.camera.position.x, cy: S.camera.position.y,
                     tx: S.controls.target.x, ty: S.controls.target.y };
    }
    function ann_ortho_pan_move(ev) {
        if (!ANN.pan0) return;
        /* 像素 → 世界距离：屏幕像素 / (canvas.height * zoom) = world unit (ortho) */
        var h = S.renderer.domElement.clientHeight, z = S.camera.zoom || 1;
        var hh = (S.camera.top - S.camera.bottom) / 2;
        var world_per_px = (hh * 2) / (h * z);
        var dx_px = ev.clientX - ANN.pan0.x, dy_px = ev.clientY - ANN.pan0.y;
        /* top 视图：屏幕 x 对应世界 x（相机 up=+X 沿世界 x），屏幕 y 对应世界 -y */
        var dx = -dx_px * world_per_px, dy = dy_px * world_per_px;
        S.camera.position.x = ANN.pan0.cx + dx;
        S.camera.position.y = ANN.pan0.cy + dy;
        S.controls.target.x = ANN.pan0.tx + dx;
        S.controls.target.y = ANN.pan0.ty + dy;
    }
    function ann_ortho_pan_end(ev) { if (ANN.pan0) ANN.pan0 = null; }

    function ann_gizmo_detach() {
        if (ANN.tc) { ANN.tc.detach(); S.scene.remove(ANN.tc); ANN.tc = null; }
    }
    function ann_gizmo_set_mode(m) {
        ANN.gizmoMode = m;
        if (ANN.tc) ANN.tc.setMode(m);
        var el = document.getElementById("annGizmoMode"); if (el) el.textContent = m;
    }
    function ann_mesh_to_obj(a, mesh) {
        a.center = [mesh.position.x, mesh.position.y, mesh.position.z];
        /* BoxGeometry 的 size 是构造时烤进顶点里的（mesh.scale 默认 1），
         * gizmo 缩放改的是 mesh.scale —— a.size = 原 size × scale。
         * 旧版 a.size = mesh.scale 把 (1,1,1) 塞回 a.size，下次 render_one 用 (1,1,1) 重建 → 框消失/跑偏。*/
        a.size = [
            a.size[0] * mesh.scale.x,
            a.size[1] * mesh.scale.y,
            a.size[2] * mesh.scale.z,
        ];
        a.yaw = mesh.rotation.z;
        /* 烘焙 scale 进 a.size 后，把 mesh.scale 还原为 1，避免下次 render 重复叠加 */
        mesh.scale.set(1, 1, 1);
    }
    function f_seq_of(a) {
        for (var s in ANN.annotations) {
            if (ANN.annotations[s].indexOf(a) >= 0) return Number(s);
        }
        return S.frames[S.idx].seq;
    }

    // ---- 渲染 ----
    function ann_render_one(a, seq) {
        if (a.mesh) S.scene.remove(a.mesh);
        var geo = new THREE.BoxGeometry(a.size[0], a.size[1], a.size[2]);
        var mat = new THREE.MeshBasicMaterial({
            color: a.fixed ? 0xff5252 : 0xff9c9c,
            transparent: true, opacity: a.fixed ? 0.35 : 0.15, wireframe: true,
        });
        var mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(a.center[0], a.center[1], a.center[2]);
        mesh.rotation.z = a.yaw;
        S.scene.add(mesh);
        a.mesh = mesh;
        if (ann_current_seq() === seq) ann_show_others(seq);
    }
    function ann_show_others(cur_seq) {
        for (var s in ANN.annotations) {
            ANN.annotations[s].forEach(function (aa) {
                if (aa.mesh) aa.mesh.visible = Number(s) === cur_seq;
            });
        }
    }
    function ann_render_frame() {
        var cur = ann_current_seq();
        if (!ANN.annotations[cur]) return;
        ANN.annotations[cur].forEach(function (a) {
            if (!a.mesh) ann_render_one(a, cur);
        });
        ann_show_others(cur);
    }

    // ---- 面板 / 选择 / 编辑 ----
    function ann_ensure_panel() {
        if (ANN.annPanel) return ANN.annPanel;
        var p = document.createElement("div"); p.id = "annPanel";
        p.style.cssText = "position:absolute;right:8px;top:46px;background:rgba(0,0,0,.6);padding:8px;border-radius:4px;font-size:11px;color:#cfd8dc;display:none;z-index:11;";
        p.innerHTML = '<b>标注</b> <span id="annId">—</span> <span id="annGizmoMode" style="color:#aef">translate</span><button id="annSaveBtn" style="margin-left:6px">保存</button><br>'
            + 'id <span id="annIdFull">—</span> '
            + 'label <input id="annLabel" size="6" value="person">'
            + ' fixed <input id="annFixed" type="checkbox" disabled><br>'
            + 'cx <input id="annCx" size="5"> cy <input id="annCy" size="5"> cz <input id="annCz" size="5"><br>'
            + 'sx <input id="annSx" size="5"> sy <input id="annSy" size="5"> sz <input id="annSz" size="5"><br>'
            + 'yaw <input id="annYaw" size="6">'
            + '<div style="margin-top:4px;color:#78909c">W/R/T=gizmo移/旋/缩 X/Y/Z=轴锁 Ctrl=捕捉 Enter=定稿 Del=删 Ctrl+Z/C/V=撤/复/粘</div>';
        document.body.appendChild(p);
        ANN.annPanel = p;
        p.addEventListener("change", function (ev) {
            if (!ANN.selected) return;
            var t = ev.target;
            function num(id) { return parseFloat(document.getElementById(id).value); }
            var cx = num("annCx"), cy = num("annCy"), cz = num("annCz"),
                sx = num("annSx"), sy = num("annSy"), sz = num("annSz"),
                yaw = num("annYaw");
            var test = { center: [cx, cy, cz], size: [sx, sy, sz], yaw: yaw };
            var v = L.annotation_validate_box(test);
            if (v !== true) { status("非法输入: " + v, true); ann_panel_write(ANN.selected); return; }
            ANN.selected.center = [cx, cy, cz];
            ANN.selected.size = [sx, sy, sz];
            ANN.selected.yaw = yaw;
            ANN.selected.label = document.getElementById("annLabel").value || "person";
            ann_render_one(ANN.selected, f_seq_of(ANN.selected));
            ann_panel_write(ANN.selected);
            ann_draft_save();
            ANN.undo = L.undo_stack_push(ANN.undo || L.undo_stack_new(), { op: "edit", seq: f_seq_of(ANN.selected), ann: ANN.selected });
        });
        p.querySelector("#annSaveBtn").addEventListener("click", ann_save);
        return p;
    }
    function ann_panel_write(a) {
        ann_ensure_panel();
        ANN.annPanel.style.display = a ? "block" : "none";
        if (!a) return;
        document.getElementById("annId").textContent = a.id;
        document.getElementById("annIdFull").textContent = a.id;
        document.getElementById("annLabel").value = a.label;
        document.getElementById("annFixed").checked = a.fixed;
        document.getElementById("annCx").value = a.center[0].toFixed(2);
        document.getElementById("annCy").value = a.center[1].toFixed(2);
        document.getElementById("annCz").value = a.center[2].toFixed(2);
        document.getElementById("annSx").value = a.size[0].toFixed(2);
        document.getElementById("annSy").value = a.size[1].toFixed(2);
        document.getElementById("annSz").value = a.size[2].toFixed(2);
        document.getElementById("annYaw").value = a.yaw.toFixed(3);
    }

    function ann_finalize() {
        if (!ANN.selected || ANN.selected.fixed) return;
        ANN.selected.fixed = true;
        ann_render_one(ANN.selected, f_seq_of(ANN.selected));
        ann_gizmo_detach();
        ann_panel_write(ANN.selected);
        ANN.undo = L.undo_stack_push(ANN.undo || L.undo_stack_new(), { op: "finalize", seq: f_seq_of(ANN.selected), ann: ANN.selected });
        ann_draft_save();
    }
    function ann_delete_selected() {
        if (!ANN.selected) return;
        if (!confirm("删除标注 " + ANN.selected.id + " ?")) return;
        var seq = f_seq_of(ANN.selected);
        var arr = ANN.annotations[seq];
        var i = arr.indexOf(ANN.selected);
        if (i >= 0) arr.splice(i, 1);
        if (ANN.selected.mesh) S.scene.remove(ANN.selected.mesh);
        ANN.undo = L.undo_stack_push(ANN.undo || L.undo_stack_new(), { op: "del", seq: seq, ann: ANN.selected });
        ANN.selected = null;
        ann_panel_write(null);
        ann_gizmo_detach();
        ann_show_others(seq);
        ann_draft_save();
    }
    function ann_undo() {
        if (!ANN.undo) { ANN.undo = L.undo_stack_new(); return; }
        var p = L.undo_stack_pop(ANN.undo);
        if (!p.entry) return;
        ANN.undo = p.new_stack;
        var e = p.entry, seq = e.seq, a = e.ann;
        if (e.op === "add" || e.op === "finalize") {
            var arr = ANN.annotations[seq], i = arr ? arr.indexOf(a) : -1;
            if (i >= 0) arr.splice(i, 1);
            if (a.mesh) S.scene.remove(a.mesh);
            if (ANN.selected === a) { ANN.selected = null; ann_panel_write(null); ann_gizmo_detach(); }
        } else if (e.op === "del") {
            ANN.annotations[seq] = ANN.annotations[seq] || [];
            ANN.annotations[seq].push(a);
            ann_render_one(a, seq);
        } else if (e.op === "edit") {
            // v1 edit undo no-op
        }
        ann_show_others(seq);
        ann_draft_save();
    }
    function ann_copy() {
        if (!ANN.selected) return;
        var a = ANN.selected;
        ANN.clipboard = { label: a.label, size: a.size.slice(), yaw: a.yaw, center_offset: a.center.slice() };
    }
    function ann_paste() {
        if (!ANN.clipboard) return;
        var seq = ann_current_seq();
        var a = { id: ann_new_id(), label: ANN.clipboard.label, center: ANN.clipboard.center_offset.slice(), size: ANN.clipboard.size.slice(), yaw: ANN.clipboard.yaw, fixed: false, mesh: null };
        ANN.annotations[seq] = ANN.annotations[seq] || [];
        ANN.annotations[seq].push(a);
        ann_render_one(a, seq);
        ANN.selected = a;
        ann_gizmo_attach(a);
        ann_panel_write(a);
        ANN.undo = L.undo_stack_push(ANN.undo || L.undo_stack_new(), { op: "add", seq: seq, ann: a });
        ann_draft_save();
    }
    function ann_esc_step() {
        if (ANN.tc) { ann_gizmo_detach(); return; }
        if (ANN.selected) { ANN.selected = null; ann_panel_write(null); return; }
        if (ANN.mode === "annotate") ann_set_mode("view");
    }

    // ---- 持久化 / 保存 ----
    function ann_sid() { return S.meta && S.meta.session_id; }
    function ann_current_seq() { return S.frames ? S.frames[S.idx].seq : null; }
    function ann_draft_save() {
        var sid = ann_sid(); if (!sid) return;
        ls_set("annotations." + sid, JSON.stringify(ANN.annotations));
    }
    function ann_draft_load() {
        var sid = ann_sid(); if (!sid) return;
        var raw = ls_get_raw("annotations." + sid, null);
        if (!raw) return;
        try {
            var data = JSON.parse(raw);
            ANN.annotations = {};
            for (var s in data) {
                ANN.annotations[Number(s)] = data[s].map(function (a) {
                    a.mesh = null; return a;
                });
            }
            ann_render_frame();
        } catch (e) { ANN.annotations = {}; }
    }
    function ann_save() {
        var sid = ann_sid(); if (!sid) return;
        var flat = L.annotation_serialize(ANN.annotations, S.meta, false);
        if (!flat.length) { ann_status("无已定稿框"); return; }
        fetch("/api/save_annotations", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sid: sid, annotations: flat }),
        })
            .then(function (r) { return r.json(); })
            .then(function (res) {
                if (!res.ok) throw new Error(res.error || "unknown");
                ann_status("已保存 " + res.count + " 条标注");
                ls_set("annotations." + sid, "");
            })
            .catch(function (e) { status("保存失败: " + e.message, true); });
    }

    // ---- 切帧 / 键盘 / 监听 ----
    var _set_idx_raw = set_idx;
    set_idx = function (i) {
        if (typeof i === "number" && ANN.mode === "annotate" && S.frames && S.frames.length) {
            var cur_seq = S.frames[S.idx].seq, arr = ANN.annotations[cur_seq] || [];
            /* 旧实现：切帧时弹确认窗「确定离开？未定稿框会被丢弃」——
             * 模态 confirm 打断播放/拖slider/键盘 step，且按"取消"会被 set_idx 再次触发，
             * 看起来就是浏览器卡死。改成：自动把未定稿框在当前帧定稿（fixed=true），
             * 并发一条 status 提示，用户想真删可以 Delete 显式删。*/
            if (arr.some(function (a) { return !a.fixed; }) && i !== S.idx) {
                arr.forEach(function (a) {
                    if (!a.fixed) {
                        a.fixed = true;
                        if (a.mesh) ann_render_one(a, cur_seq);   /* 重新着色成定稿色 */
                    }
                });
                ANN.selected = null; ann_gizmo_detach(); ann_panel_write(null);
                ann_draft_save();
                ann_status("已自动定稿本帧 " + arr.length + " 框");
            }
        }
        _set_idx_raw(i);
        ann_render_frame();
    };

    function ann_axis_lock(ax) {
        if (!ANN.tc) return;
        ANN.axisLock = ax;
        if (ax === "x") { ANN.tc.showX = true; ANN.tc.showY = false; ANN.tc.showZ = false; var d = ANN.tc.dragging; if (d) { } }
        else if (ax === "y") { ANN.tc.showX = false; ANN.tc.showY = true; ANN.tc.showZ = false; }
        else if (ax === "z") { ANN.tc.showX = false; ANN.tc.showY = false; ANN.tc.showZ = true; }
        else { ANN.tc.showX = true; ANN.tc.showY = true; ANN.tc.showZ = true; }
    }
    function ann_snap_update() {
        if (!ANN.tc) return;
        ANN.tc.translationSnap = ANN.ctrl ? 0.1 : null;
        ANN.tc.rotationSnap = ANN.ctrl ? Math.PI / 36 : null;
        ANN.tc.scaleSnap = ANN.ctrl ? 0.05 : null;
    }

    window.addEventListener("keydown", function (ev) {
        if (ev.target && (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA")) return;
        if (S.fly && S.fly.on) return;
        if (ANN.mode === "annotate") {
            if (ev.code === "KeyB") { ann_toggle_mode(); ev.preventDefault(); return; }
            if (ev.code === "KeyW" && ANN.selected) { ann_gizmo_set_mode("translate"); ev.preventDefault(); return; }
            if (ev.code === "KeyR" && ANN.selected) { ann_gizmo_set_mode("rotate"); ev.preventDefault(); return; }
            if (ev.code === "KeyT" && ANN.selected) { ann_gizmo_set_mode("scale"); ev.preventDefault(); return; }
            if (ev.code === "Enter" && ANN.selected) { ann_finalize(); ev.preventDefault(); return; }
            if ((ev.code === "Delete" || ev.code === "Backspace") && ANN.selected) { ann_delete_selected(); ev.preventDefault(); return; }
            if (ev.code === "KeyC" && ev.ctrlKey && ANN.selected) { ann_copy(); ev.preventDefault(); return; }
            if (ev.code === "KeyV" && ev.ctrlKey && ANN.clipboard) { ann_paste(); ev.preventDefault(); return; }
            if (ev.code === "KeyZ" && ev.ctrlKey) { ann_undo(); ev.preventDefault(); return; }
            if (ev.code === "Escape") { ann_esc_step(); ev.preventDefault(); return; }
        }
        if (ev.code === "KeyB" && ANN.mode === "view") { ann_toggle_mode(); ev.preventDefault(); return; }
    });
    window.addEventListener("keydown", function (ev) { if (ANN.mode !== "annotate") return;
        if (ev.code === "KeyX") { ann_axis_lock("x"); ev.preventDefault(); }
        else if (ev.code === "KeyY") { ann_axis_lock("y"); ev.preventDefault(); }
        else if (ev.code === "KeyZ" && !ev.ctrlKey) { ann_axis_lock("z"); ev.preventDefault(); } });
    window.addEventListener("keyup", function (ev) { if (ANN.mode !== "annotate") return;
        if (ev.code === "KeyX" || ev.code === "KeyY" || ev.code === "KeyZ") ann_axis_lock(null); });
    window.addEventListener("keydown", function (ev) {
        if (ev.ctrlKey) { ANN.ctrl = true; ann_snap_update(); }
        if (ANN.mode !== "annotate") return;
        /* 单 listener 做 X/Y/Z 轴锁：上面已经注册了，这里只做 Ctrl 快照 */
    });
    window.addEventListener("keyup", function (ev) { if (ev.code === "ControlLeft" || ev.code === "ControlRight") { ANN.ctrl = false; ann_snap_update(); } });
    window.addEventListener("mousedown", ann_on_mousedown);
    window.addEventListener("mousemove", ann_on_mousemove);
    window.addEventListener("mouseup", ann_on_mouseup);
    /* annotate 模式正交缩放/平移 — 与 controls 解耦，直接动 camera/target */
    window.addEventListener("wheel", ann_ortho_wheel, { passive: false });
    window.addEventListener("mousedown", ann_ortho_pan_start);
    window.addEventListener("mousemove", ann_ortho_pan_move);
    window.addEventListener("mouseup", ann_ortho_pan_end);

    /* 初始就亮徽标 + 准星占位（view 态）：让用户知道「按 B 进标注」是注定的不是赌运气 */
    ann_badge_refresh();
    ann_crosshair_refresh();

    // 恢复草稿
    if (typeof window.__load_session_sid === "function") {
        var _orig_load = window.__load_session_sid;
        window.__load_session_sid = function (sid) {
            return _orig_load(sid).then(function (r) { ann_draft_load(); return r; });
        };
    }
})();
