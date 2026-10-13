"use strict";
/* v2 效果查看器：数据来自 v2_view_data_*.js / v2_view_refvox.js（make_v2_view.js 生成）。
 * 类别：0=两臂都留 1=参考命中（v2 删） 2=在线∧参考支持（两臂都删） 3=在线-only（P 删、v2 救回） 4=预剔除。 */
(function () {
    const MODES = {
        input: { label: "原始（含人）", colors: { 0: 0xbfc7cf, 1: 0xbfc7cf, 2: 0xbfc7cf, 3: 0xbfc7cf, 4: 0xbfc7cf, 5: 0xbfc7cf, 6: 0xbfc7cf, 7: 0xbfc7cf } },
        p: { label: "① 现状 P（仅在线）", colors: { 0: 0x8fd0ff, 1: 0x8fd0ff, 2: 0x3a3f47, 3: 0xff4d5e, 4: 0x4a4f58, 5: 0xff4d5e, 6: 0xff4d5e, 7: 0xd07878 } },
        v2: { label: "② v2（参考 ∨ 在线∧参考支持）", colors: { 0: 0x8fd0ff, 1: 0x2b2f36, 2: 0x2b2f36, 3: 0x51e3a5, 4: 0x4a4f58, 5: 0xe0b050, 6: 0x5d6b4f, 7: 0x59636b } },
        diff: { label: "③ 救回高亮", colors: { 0: 0x343a42, 1: 0x2b2f36, 2: 0x2b2f36, 3: 0x51e3a5, 4: 0x22262b, 5: 0xe0b050, 6: 0x5d6b4f, 7: 0x59636b } },
    };
    const state = { sid: null, fi: 0, mode: "v2" };

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
    if (window.RETV2_REFVOX) {
        const a = new Float32Array(window.RETV2_REFVOX.length * 3);
        window.RETV2_REFVOX.forEach((p, i) => { a[i * 3] = p[0]; a[i * 3 + 1] = p[1]; a[i * 3 + 2] = p[2]; });
        refObj.geometry.setAttribute("position", new THREE.BufferAttribute(a, 3));
        scene.add(refObj);
    }
    refObj.visible = false;
    const refPtsObj = new THREE.Points(new THREE.BufferGeometry(),
        new THREE.PointsMaterial({ size: 1.6, sizeAttenuation: false, color: 0x4f7d63, transparent: true, opacity: 0.85 }));
    if (window.RETV2_REFPT) {
        const u = b64ToU8(window.RETV2_REFPT.pos);
        const i16 = new Int16Array(u.buffer, u.byteOffset, u.byteLength >> 1);
        const n = window.RETV2_REFPT.n;
        const a = new Float32Array(n * 3);
        for (let i = 0; i < n * 3; i++) a[i] = i16[i] / 1000;
        refPtsObj.geometry.setAttribute("position", new THREE.BufferAttribute(a, 3));
        scene.add(refPtsObj);
    }
    refPtsObj.visible = true;   /* 模板原始点默认开（回答问题用；可关） */

    function b64ToU8(b64) { const bin = atob(b64), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
    function b64ToI16(b64) { const u = b64ToU8(b64); return new Int16Array(u.buffer, u.byteOffset, u.byteLength >> 1); }

    function buildFrame() {
        const S = window.RETV2_VIEW[state.sid], F = S.frames[state.fi];
        const i16 = b64ToI16(F.pos), cls = b64ToU8(F.cls), n = F.n;
        const pos = new Float32Array(n * 3);
        for (let i = 0; i < n * 3; i++) pos[i] = i16[i] / 1000;
        const g = new THREE.BufferGeometry();
        g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(n * 3), 3));
        points.geometry.dispose();
        points.geometry = g;
        state.cls = cls; state.pos = pos; state.center = S.center; state.radius = S.radius; state.zrange = S.z; state.row = F.row;
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
        const { cls, pos, center, radius, zrange, row } = state;
        const all = {}, per = {};
        let flag = 0;
        const r2 = radius * radius;
        for (let i = 0; i < cls.length; i++) {
            all[cls[i]] = (all[cls[i]] || 0) + 1;
            const dx = pos[i * 3] - center[0], dy = pos[i * 3 + 1] - center[1], z = pos[i * 3 + 2];
            if (dx * dx + dy * dy <= r2 && z >= zrange[0] && z <= zrange[1]) { flag++; per[cls[i]] = (per[cls[i]] || 0) + 1; }
        }
        const c = k => per[k] || 0, a = k => all[k] || 0;
        const pct = v => flag ? (100 * v / flag).toFixed(1) + "%" : "—";
        const rAll = c(3) + c(5) + c(6) + c(7);
        const pKeep = c(0) + c(1), v2Keep = c(0) + rAll;
        const pr = row && row.person;
        const pLine = row ? `<b>v2 链（该帧）</b>：人簇 ${pr ? "<b style='color:#51e3a5'>" + pr.label + "/" + pr.joint + (pr.confirmed ? " ✓确认" : "") + "</b>" : "<span class='dim'>无</span>"}` +
            `；簇 确认×${row.clusters.CONFIRMED_HUMAN || 0} 候选×${row.clusters.HUMAN_CANDIDATE || 0} 非人×${row.clusters.NON_HUMAN || 0}` +
            `<br>　前景 ${row.n_fg} 点；在线-only 保留 ${row.kept} 点<br>` : "";
        document.getElementById("stats").innerHTML =
            `<b>显示点（本帧裁剪区）</b>：${cls.length}（统一抽稀；比例不变）<br>` +
            `<b>人体区（圆柱 r=${radius}m）</b>：原始 <b>${flag}</b><br>` +
            `　P（现状·仅在线）保留：${pKeep}（${pct(pKeep)}）<br>` +
            `　v2 保留：<b style="color:#51e3a5">${v2Keep}</b>（${pct(v2Keep)}）<br>` +
            `　其中救回（P 删 → v2 留）：<b>${rAll}</b>（${pct(rAll)}）——人通道 <b style="color:#51e3a5">${c(3)}</b>｜几何候选 <b style="color:#e0b050">${c(5)}</b>｜链判非人 <b style="color:#8a9a78">${c(6)}</b>｜未成簇 ${c(7)}<br>` +
            `　参考层补删（P 留 → v2 删）：${c(1)}｜两臂都删：${c(2)}｜预剔除：${c(4)}<br>` +
            `<span class="dim">全裁剪区：留 ${a(0)}｜参考删 ${a(1)}｜在线+支持 ${a(2)}｜救回(人/候选/非人/未簇) ${a(3)}/${a(5)}/${a(6)}/${a(7)}｜预剔 ${a(4)}</span><br>` + pLine;
    }

    /* UI */
    const sel = document.getElementById("session");
    Object.keys(window.RETV2_VIEW).forEach(k => sel.add(new Option(k.replace("cap_20261007_", "…"), k)));
    state.sid = sel.value;
    const frameInput = document.getElementById("frame");
    function syncFrameRange() { const S = window.RETV2_VIEW[state.sid]; frameInput.max = S.frames.length - 1; frameInput.value = 0; state.fi = 0; }
    sel.onchange = () => { state.sid = sel.value; syncFrameRange(); buildFrame(); };
    frameInput.oninput = () => { state.fi = +frameInput.value; buildFrame(); };
    const desc = {
        input: "原始输入（配平后，含人）：所有点同色。人应清晰可见（站在箱子前方 ≈(2.1,−0.5)）。",
        p: "① 现状 P（仅在线图）：静立人被在线自建模为背景，红 = P 误删（含人主体与其它在线持久物）。",
        v2: "② v2 = 参考 ∨ (在线 ∧ 参考支持)：空场模板里没有的东西不得仅凭在线删。救回点按链判定分色：亮绿=人通道（确认）｜橙=几何候选｜暗橄榄=链判非人（家具泄漏，如桌子）｜灰绿=未成簇。",
        diff: "③ 救回高亮：同上分色，其余压暗。",
    };
    document.querySelectorAll("input[name=mode]").forEach(r => r.onchange = () => { state.mode = r.value; applyColors(); updateStats(); document.getElementById("modeDesc").textContent = desc[state.mode]; });
    document.getElementById("modeDesc").textContent = desc[state.mode];
    document.getElementById("refvox").onchange = e => { refObj.visible = e.target.checked; };
    document.getElementById("refpts").onchange = e => { refPtsObj.visible = e.target.checked; };
    document.getElementById("home").onclick = () => { const S = window.RETV2_VIEW[state.sid]; camera.position.set(S.center[0] - 2.4, S.center[1] - 2.6, 2.6); controls.target.set(S.center[0], S.center[1], 0.9); controls.update(); };
    window.addEventListener("resize", () => { const el = document.getElementById("view"); renderer.setSize(el.clientWidth, el.clientHeight, false); camera.aspect = el.clientWidth / el.clientHeight; camera.updateProjectionMatrix(); });

    const el = document.getElementById("view");
    renderer.setSize(el.clientWidth, el.clientHeight, false);
    camera.aspect = el.clientWidth / el.clientHeight;
    camera.updateProjectionMatrix();
    const S0 = window.RETV2_VIEW[state.sid];
    camera.position.set(S0.center[0] - 2.4, S0.center[1] - 2.6, 2.6);
    syncFrameRange(); buildFrame();
    (function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();
})();
