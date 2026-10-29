/* REPLAY-FRESH-01: 同一回放页显式切换；重载用于还原整段颜色并从头建立时序。 */
(function () {
    "use strict";
    var q = new URLSearchParams(location.search), active = q.get("highlight") === "1";
    var toggle = document.getElementById("highlightSwitch"), hud = document.getElementById("freshHud");
    var controls = document.getElementById("freshControls"), modeSelect = document.getElementById("perceptionMode");
    var refSelect = document.getElementById("freshReference");
    var details = document.getElementById("perceptionDetails");
    var mode = q.get("perception") || "xy";
    var invalidMode = !["legacy", "metric3d", "xy"].includes(mode);
    if (invalidMode) mode = "xy";
    var selectedRef = q.get("ref") || "cap_20261014_221808";
    if (controls) controls.hidden = !active;
    if (details) details.hidden = !active || mode === "legacy";
    window.FRESH_VIEW_ACTIVE = active;
    toggle.checked = active;
    function reload() {
        var u = new URL(location.href), S = window.replay_internal && window.replay_internal.S;
        if (S && S.meta && S.load_source === "manual") {
            toggle.checked = active;
            if (modeSelect) modeSelect.value = mode;
            if (refSelect) refSelect.value = selectedRef;
            hud.hidden = false; hud.style.color = "#ffbf75";
            hud.textContent = "当前会话来自本地目录。请先在左侧选择服务中的同一会话，再切换显示方案，避免重载丢失目录。";
            return;
        }
        u.searchParams.set("highlight", toggle.checked ? "1" : "0");
        if (modeSelect) u.searchParams.set("perception", modeSelect.value);
        if (refSelect) u.searchParams.set("ref", refSelect.value);
        if (S && S.meta && /^[A-Za-z0-9_-]{1,100}$/.test(S.meta.session_id))
            u.searchParams.set("sid", S.meta.session_id);
        u.searchParams.delete("freeze");
        location.assign(u.toString());
    }
    if (modeSelect) { modeSelect.value = mode; modeSelect.addEventListener("change", reload); }
    if (refSelect) {
        if (/^[A-Za-z0-9_-]{1,100}$/.test(selectedRef) && !Array.from(refSelect.options).some(function(o){return o.value===selectedRef;})) {
            var op = document.createElement("option"); op.value = selectedRef; op.textContent = selectedRef; refSelect.appendChild(op);
        }
        refSelect.value = selectedRef; refSelect.addEventListener("change", reload);
    }
    toggle.addEventListener("change", reload);
    if (!active) { window.FRESH_VIEW_READY = Promise.resolve(true); return; }
    var detect = document.getElementById("detectBtn");
    detect.hidden = true; detect.disabled = true;
    var lut = document.getElementById("lutSel");
    lut.disabled = true; lut.title = "关闭人物高亮后可调整原始着色";
    hud.hidden = false;
    hud.textContent = "人物高亮：正在载入空场参考…";
    var ref = q.get("ref") || "cap_20261014_221808", ready = false;
    var overlay = window.FRESH_OVERLAY, originalFrame = overlay.on_frame;
    /* 参考没到时不允许回退到本会话warmup，避免悄悄把人学成背景。 */
    var hook = Object.assign({}, overlay, {
        on_frame: function (S) { if (ready) originalFrame(S); },
        notify_session: function () {
            var d = window.human_replay_lib.DEFAULT_LEVEL_TRANSFORM;
            overlay.set_transform(d.R, d.t);
            return overlay.notify_session();
        }
    });
    window.HUMAN_DETECT_OVERLAY = hook;
    function file(name) {
        function request() {
            return fetch("/api/file?sid=" + encodeURIComponent(ref) + "&name=" + name).then(function (r) {
                if (!r.ok) throw new Error("参考文件缺失（HTTP " + r.status + "）");
                return r;
            });
        }
        return { name:name, text:function () { return request().then(function (r) { return r.text(); }); },
            arrayBuffer:function () { return request().then(function (r) { return r.arrayBuffer(); }); } };
    }
    window.FRESH_VIEW_READY = Promise.resolve().then(function () {
        if (invalidMode) throw new Error("感知版本无效，请从方案菜单重新选择");
        if (typeof overlay.set_mode === "function") overlay.set_mode(mode);
        if (!/^[A-Za-z0-9_-]{1,100}$/.test(ref)) throw new Error("空场会话名无效");
        return window.FRESH_SET_REF([file("meta.json"), file("points.bin")]);
    }).then(function () {
        ready = true;
        hud.textContent = "人物高亮就绪 · 空场 " + ref + " · 正在等待会话";
        var ri = window.replay_internal;
        if (ri && ri.S && ri.S.geo) {
            overlay.reset(); ri.S.tracker_last_idx = -1; ri.set_idx(0);
        }
        return true;
    }).catch(function (e) {
        ready = false;
        hud.style.color = "#ff8080";
        hud.textContent = "人物高亮未启用：" + e.message + "；可关闭开关查看原始点云";
        return false;
    });
})();
