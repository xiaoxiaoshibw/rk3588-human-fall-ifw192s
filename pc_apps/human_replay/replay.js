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
    };

    var els = {};
    ["pickBtn", "dirInput", "status", "hud", "playBtn", "speedSel", "loopChk",
     "slider", "frameInfo", "metaBox"].forEach(function (id) { els[id] = document.getElementById(id); });

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
        metaFile.text().then(function (txt) {
            S.meta = JSON.parse(txt);
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
        });
    }

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

    function paint_colours() {
        var lo = S.range.lo, hi = S.range.hi;
        var src = S.buf_f32, dst = S.colour;
        for (var p = 0; p < S.total_pts; p++) {
            var g = L.intensity_to_gray(src[p * L.STRIDE_F32 + 3], lo, hi);
            var d = p * 3;
            dst[d] = g; dst[d + 1] = g; dst[d + 2] = g;
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
        S.scene.add(new THREE.AxesHelper(1.2));                    // 雷达原点三轴
        var grid = new THREE.GridHelper(40, 40, 0x335533, 0x223322); // 1m 网格
        grid.rotation.x = Math.PI / 2;                              // XY 地面(z-up)
        S.scene.add(grid);
        var originBall = new THREE.Mesh(
            new THREE.SphereGeometry(0.09, 12, 12),
            new THREE.MeshBasicMaterial({ color: 0x66ccff }));
        S.scene.add(originBall);

        S.controls = new THREE.OrbitControls(S.camera, S.renderer.domElement);
        reset_cam();
        window.addEventListener("resize", on_resize);
        S.last_ts = performance.now();
        requestAnimationFrame(tick);
    }

    function reset_cam() { // 从雷达后上方看前方(z-up)
        S.camera.up.set(0, 0, 1);
        S.camera.position.set(-3.5, -4, 2.8);
        S.controls.target.set(2.5, 0, 0.6);
        S.controls.update();
    }

    function on_resize() {
        S.camera.aspect = window.innerWidth / window.innerHeight;
        S.camera.updateProjectionMatrix();
        S.renderer.setSize(window.innerWidth, window.innerHeight);
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
        S.controls.update();
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
    els.slider.addEventListener("input", function () {
        play(false);
        set_idx(parseInt(els.slider.value, 10));
    });
    window.addEventListener("keydown", function (ev) {
        if (ev.target && (ev.target.tagName === "INPUT" || ev.target.tagName === "SELECT")
            && ev.code !== "Space") { return; }
        if (ev.code === "Space") { play(); ev.preventDefault(); }
        else if (ev.code === "ArrowLeft") { step(ev.shiftKey ? -10 : -1); ev.preventDefault(); }
        else if (ev.code === "ArrowRight") { step(ev.shiftKey ? 10 : 1); ev.preventDefault(); }
    });

    // ---- 下拉速度档（lib 常量） ---------------------------------------------------------
    L.PLAYBACK_SPEEDS.forEach(function (v) {
        var o = document.createElement("option");
        o.value = String(v); o.textContent = v + "×";
        if (v === 1) o.selected = true;
        els.speedSel.appendChild(o);
    });

    setup_scene();
})();
