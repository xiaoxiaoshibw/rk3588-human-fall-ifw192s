"use strict";
/* 静立人保留效果查看器：数据来自 view_data_*.js / view_refvox.js（make_retention_view.js 生成）。 */
(function () {
    const MODES = {
        input: { label: "原始（含人）", colors: { 0: 0xbfc7cf, 1: 0xbfc7cf, 2: 0xbfc7cf, 3: 0xbfc7cf, 4: 0xbfc7cf } },
        ref: { label: "① 空场模板层", colors: { 0: 0x8fd0ff, 1: 0x2b2f36, 2: 0x8fd0ff, 3: 0x8fd0ff, 4: 0x4a4f58 } },
        final: { label: "② 参考+在线（现状）", colors: { 0: 0x8fd0ff, 1: 0x2b2f36, 2: 0xff4d5e, 3: 0xffb950, 4: 0x4a4f58 } },
        diff: { label: "③ 在线误删高亮", colors: { 0: 0x51e3a5, 1: 0x33363c, 2: 0xff4d5e, 3: 0x33363c, 4: 0x33363c } },
    };
    const state = { sid: null, fi: 0, mode: "final" };

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d1117);
    const camera = new THREE.PerspectiveCamera(55, 1, 0.05, 200);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    document.getElementById("view").appendChild(renderer.domElement);
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.dampingFactor = 0.12;

    const points = new THREE.Points(new THREE.BufferGeometry(),
        new THREE.PointsMaterial({ size: 2.4, sizeAttenuation: false, vertexColors: true }));
    scene.add(points);
    const refObj = new THREE.Points(new THREE.BufferGeometry(),
        new THREE.PointsMaterial({ size: 1.8, sizeAttenuation: false, color: 0x2ecc71, transparent: true, opacity: 0.5 }));
    if (window.RETENTION_REFVOX) {
        const a = new Float32Array(window.RETENTION_REFVOX.length * 3);
        window.RETENTION_REFVOX.forEach((p, i) => { a[i * 3] = p[0]; a[i * 3 + 1] = p[1]; a[i * 3 + 2] = p[2]; });
        refObj.geometry.setAttribute("position", new THREE.BufferAttribute(a, 3));
        scene.add(refObj);
    }
    refObj.visible = false;

    function b64ToU8(b64) { const bin = atob(b64), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
    function b64ToI16(b64) { const u = b64ToU8(b64); return new Int16Array(u.buffer, u.byteOffset, u.byteLength >> 1); }

    function buildFrame() {
        const S = window.RETENTION_VIEW[state.sid], F = S.frames[state.fi];
        const i16 = b64ToI16(F.pos), cls = b64ToU8(F.cls), n = F.n;
        const pos = new Float32Array(n * 3);
        for (let i = 0; i < n * 3; i++) pos[i] = i16[i] / 1000;
        const g = new THREE.BufferGeometry();
        g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(n * 3), 3));
        points.geometry.dispose();
        points.geometry = g;
        state.cls = cls; state.pos = pos; state.center = S.center; state.radius = S.radius; state.zrange = S.z;
        controls.target.set(S.center[0], S.center[1], 0.9);
        controls.update();
        applyColors();
        updateStats();
        document.getElementById("frameLabel").textContent = `frame ${F.i} / ${S.nf - 1}`;
    }
    function applyColors() {
        const colAttr = points.geometry.getAttribute("color");
        const map = MODES[state.mode].colors, c = new THREE.Color();
        for (let i = 0; i < state.cls.length; i++) {
            c.setHex(map[state.cls[i]] || 0x808080);
            colAttr.setXYZ(i, c.r, c.g, c.b);
        }
        colAttr.needsUpdate = true;
    }
    function updateStats() {
        const { cls, pos, center, radius, zrange } = state;
        const all = [0, 0, 0, 0, 0], per = [0, 0, 0, 0, 0];
        let flag = 0;
        const r2 = radius * radius;
        for (let i = 0; i < cls.length; i++) {
            all[cls[i]]++;
            const dx = pos[i * 3] - center[0], dy = pos[i * 3 + 1] - center[1], z = pos[i * 3 + 2];
            if (dx * dx + dy * dy <= r2 && z >= zrange[0] && z <= zrange[1]) { flag++; per[cls[i]]++; }
        }
        const pct = v => flag ? (100 * v / flag).toFixed(1) + "%" : "—";
        const refKeep = per[0] + per[2] + per[3];
        document.getElementById("stats").innerHTML =
            `<b>显示点（本帧裁剪区）</b>：${cls.length}（统一抽稀；比例不变）<br>` +
            `<b>人体区（圆柱 r=${radius}m）</b>：原始 <b>${flag}</b><br>` +
            `　模板层保留：<b style="color:#8fd0ff">${refKeep}</b>（${pct(refKeep)}）<br>` +
            `　现状最终保留：<b style="color:#8fd0ff">${per[0]}</b>（${pct(per[0])}）<br>` +
            `　被在线层删除：<b style="color:#ff4d5e">${per[2]}</b>（${pct(per[2])}）<br>` +
            `　被模板误删：${per[1]}（${pct(per[1])}）｜cleanup：${per[3]}｜预剔除：${per[4]}<br>` +
            `<span class="dim">全裁剪区：保留 ${all[0]}｜模板删 ${all[1]}｜在线删 ${all[2]}｜cleanup ${all[3]}｜预剔 ${all[4]}</span>`;
    }

    /* UI */
    const sel = document.getElementById("session");
    Object.keys(window.RETENTION_VIEW).forEach(k => sel.add(new Option(k.replace("cap_20261007_", "…"), k)));
    state.sid = sel.value;
    const frameInput = document.getElementById("frame");
    function syncFrameRange() { const S = window.RETENTION_VIEW[state.sid]; frameInput.max = S.frames.length - 1; frameInput.value = 0; state.fi = 0; }
    sel.onchange = () => { state.sid = sel.value; syncFrameRange(); buildFrame(); };
    frameInput.oninput = () => { state.fi = +frameInput.value; buildFrame(); };
    document.querySelectorAll("input[name=mode]").forEach(r => r.onchange = () => { state.mode = r.value; applyColors(); updateStats(); document.getElementById("modeDesc").textContent = desc[state.mode]; });
    const desc = {
        input: "原始输入（配平后，含人）：所有点同色。人应清晰可见（站在箱子前方 ≈(2.1,−0.5)）。",
        ref: "① 只应用空场模板：模板（233658 空场）里没有的东西不许删——人被完整保留（亮蓝）；静态家具变暗。",
        final: "② 现状 = 模板 ∪ 在线（并集）：在线层把 6 秒静立的人自建模为背景，再次删除——人变成红色。这就是「静立吞人」。",
        diff: "③ 高亮：绿 = 最终保留；红 = 被在线层删除（静立人被误删的主体）；其余压暗。",
    };
    document.getElementById("modeDesc").textContent = desc[state.mode];
    document.getElementById("refvox").onchange = e => { refObj.visible = e.target.checked; };
    document.getElementById("home").onclick = () => { const S = window.RETENTION_VIEW[state.sid]; camera.position.set(S.center[0] - 2.4, S.center[1] - 2.6, 2.6); controls.target.set(S.center[0], S.center[1], 0.9); controls.update(); };
    window.addEventListener("resize", () => { const el = document.getElementById("view"); renderer.setSize(el.clientWidth, el.clientHeight, false); camera.aspect = el.clientWidth / el.clientHeight; camera.updateProjectionMatrix(); });

    const el = document.getElementById("view");
    renderer.setSize(el.clientWidth, el.clientHeight, false);
    camera.aspect = el.clientWidth / el.clientHeight;
    camera.updateProjectionMatrix();
    const S0 = window.RETENTION_VIEW[state.sid];
    camera.position.set(S0.center[0] - 2.4, S0.center[1] - 2.6, 2.6);
    syncFrameRange(); buildFrame();
    (function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();
})();
