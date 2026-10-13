/* detect_ui.js — HR-09 B1 检测面板: 按钮切换 + 背景包络装载 + HUD 显示.
 *
 * 只对 detect_overlay + replay 互相建立联系, 不重复实现逻辑.
 * 装载顺序: replay.js 里 S 已建 → detect_ui 拿 S.points.geometry.attributes.color 数组 → 挂 detect_overlay.
 */
"use strict";
/* global HUMAN_DETECT_OVERLAY, human_replay_lib */

(function () {
    var btn = document.getElementById("detectBtn");
    var topview = document.getElementById("detectTopView");
    var hud = document.getElementById("detectHud");
    if (!btn || !topview || !hud) return;

    var on = false;
    var bg_loaded = false;

    function show(v) {
        topview.style.display = v ? "block" : "none";
        hud.style.display = v ? "block" : "none";
        btn.textContent = v ? "人检:开" : "人检:关";
    }

    function load_bg() {
        /* 背景包络 JSON: 由 pc_apps/human_ml/dump_bg_envelope.py 一次导到
         * <本目录>/bg_envelope.json (静态文件, 由回放器自身 _serve_static 直接送) */
        return fetch("/bg_envelope.json")
            .then(function (r) { return r.ok ? r.text() : ""; })
            .catch(function () { return ""; });
    }

    btn.addEventListener("click", function () {
        on = !on;
        if (on) {
            /* B2-A-FIX-R1: 重开人检 = 状态重开; tracker_last_idx 复位防同帧跳过 */
            if (typeof HUMAN_DETECT_OVERLAY !== "undefined" && HUMAN_DETECT_OVERLAY) {
                HUMAN_DETECT_OVERLAY.reset();
                if (window.replay_internal && window.replay_internal.S) {
                    window.replay_internal.S.tracker_last_idx = -1;
                }
            }
            /* 延迟初始化: 等 replay_internal + 背景 JSON 都到位 */
            var try_init = function () {
                if (typeof window.replay_internal === "undefined" || !window.replay_internal.S) { setTimeout(try_init, 100); return; }
                var S = window.replay_internal.S;
                if (!S.geo || !S.colour) { setTimeout(try_init, 100); return; }
                HUMAN_DETECT_OVERLAY.init({
                    scene: S.scene,
                    bgEnvelopeJson: bg_loaded ? null : undefined,
                    topCanvas: topview,
                });
                HUMAN_DETECT_OVERLAY.attach_color(S.colour);
                /* 每帧 HUD 同步 */
                setInterval(function () {
                    if (!on) return;
                    hud.textContent = S.hud_extra || "无检测目标";
                }, 200);
                show(true);
            };
            load_bg().then(function (txt) {
                if (txt) {
                    try {
                        var bg = JSON.parse(txt);
                        HUMAN_DETECT_OVERLAY.init({ bgEnvelopeJson: bg });
                        bg_loaded = true;
                    } catch (e) { console.log("背景包络加载失败: " + e); }
                }
                try_init();
            });
        } else {
            show(false);
            hud.textContent = "";
        }
    });

    if (typeof HUMAN_DETECT_OVERLAY === "undefined") {
        console.error("detect_overlay.js 未加载");
        btn.disabled = true;
    }
})();
