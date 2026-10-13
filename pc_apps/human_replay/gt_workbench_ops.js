/* gt_workbench_ops.js — GT 标注台的「会话/GT 元数据」操作层。
 * 设计：所有 fetch 序列、payload 组装、状态渲染都是纯函数（node 可测）；
 *       不进 gt_annotator.js 的 IIFE 画布起作用域。
 * 调用方式（浏览器）：GT_OPS.bind(ctx)，ctx = {S, render_frozen_section, hud_msg, save_draft, freeze}
 */
"use strict";

var GT_OPS = (function () {
    function _parse_reject(rj) {
        /* board_mode 403 or generic fail — 给出用户可读的降级解释 */
        var msg = (rj && rj.error) ? String(rj.error) : "HTTP 非 200";
        if (rj && rj.board_mode) {
            if (/改名|rename/i.test(msg)) return "板端模式下会话不可改名（只允许标注）";
            if (/录|record/i.test(msg)) return "板端模式下不能触发录制（请走 webui/human_capture）";
            if (/拉|sync|pull/i.test(msg)) return "板端模式下不能在本页执行拉取（板上 GT 就在原地）";
            return "板端模式禁用本操作（" + msg + "）";
        }
        if (/HTTP 409/.test(msg)) return "操作冲突（另一写者或已在途）：" + msg;
        if (/HTTP 404/.test(msg)) return "目标不存在：" + msg;
        return msg;
    }

    function _post(path, body) {
        return fetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body || {}),
        }).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (j) {
                if (!r.ok) { var e = new Error(j.error || ("HTTP " + r.status)); e._payload = j; throw e; }
                return j;
            });
        });
    }
    function _get(path) {
        return fetch(path).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (j) {
                if (!r.ok) { var e = new Error(j.error || ("HTTP " + r.status)); e._payload = j; throw e; }
                return j;
            });
        });
    }

    /* ---------- 会话改名 ---------- */
    function rename_session(sid, name) {
        sid = String(sid || "").trim();
        name = String(name || "").trim();
        if (!sid) return Promise.reject(new Error("sid 必填"));
        this._set_note("改名中…");
        var self = this;
        return _post("/api/rename", { sid: sid, name: name }).then(function (rj) {
            self._set_note(name ? ("已改名: " + name) : "已清除别名", false);
            return rj;
        }).catch(function (e) {
            self._set_note(_parse_reject(e._payload || { error: e.message }), true);
            throw e;
        });
    }

    /* ---------- GT 别名（draft / 冻结版） ---------- */
    function set_alias(sid, scope, version, name) {
        sid = String(sid || "").trim();
        scope = String(scope || "").trim();
        name = String(name || "").trim();
        if (!sid) return Promise.reject(new Error("sid 必填"));
        if (scope !== "draft" && scope !== "version") return Promise.reject(new Error("scope 非法"));
        var body = { sid: sid, scope: scope, name: name };
        if (scope === "version") body.version = String(version || "").trim();
        this._set_note("写别名…");
        var self = this;
        return _post("/api/gt/alias", body).then(function (rj) {
            self._set_note(name ? "别名已存" : "别名已清除", false);
            return rj;
        }).catch(function (e) {
            self._set_note(_parse_reject(e._payload || { error: e.message }), true);
            throw e;
        });
    }

    /* ---------- 从板端同步 GT 产物 ---------- */
    function pull_from_board() {
        this._set_note("请求板端 GT 同步…");
        var self = this;
        return _post("/api/gt/pull", {}).then(function () {
            self._set_note("拉取中…(轮询)");
            return _poll_pull_status.call(self, 0);
        }).catch(function (e) {
            self._set_note(_parse_reject(e._payload || { error: e.message }), true);
            throw e;
        });
    }

    function _poll_pull_status(attempt) {
        var self = this;
        attempt = attempt || 0;
        /* FIX-REVIEW-M5: 5min 上限。原 60s 对 9 会话 × ~78MB draft 远不够（每个 draft 都
         * 要拉回 + sha256），冲突也不浮现。10min 太宽，5min 是中间值。 */
        if (attempt > 600) {
            self._set_note("拉取超时（仍在跑，后台继续；下次打开再看 /api/gt/pull_status）", true);
            return Promise.resolve({ running: true, timeout: true });
        }
        return _get("/api/gt/pull_status").then(function (st) {
            if (st.running) {
                /* FIX-REVIEW-M3: 递归必须用 resolve/reject 双向传递，否则中间一次 GET 失败
                 * 会吞掉 rejection，外层 Promise 永不 settle。 */
                return new Promise(function (resolve, reject) {
                    self._set_timeout(function () {
                        _poll_pull_status.call(self, attempt + 1).then(resolve, reject);
                    }, 500);
                });
            }
            if (st.last_result === "ok") {
                var d = st.detail || {};
                var pulled = (d.pulled || []).length, skipped = (d.skipped || []).length;
                var confl = (d.conflicts || []).length;
                var msg = "同步完成: +" + pulled + " 跳过 " + skipped;
                if (confl) msg += " 冲突 " + confl + "（未覆盖，见 gt_gt_store/*.bak）";
                self._set_note(msg, confl > 0);
                self._after_pull_ok();
            } else if (st.last_result === "failed") {
                var err = st.last_error || "?";
                /* FIX-REVIEW-M4-L8：服务端把 conflict 也映射成 failed，要区分「板端 GT_V*
                 * 冲突（合法，不覆盖）」与「网络/IO 故障（需人工）」。conflict 时 detail
                 * 在 last_detail（即便 last_result=failed），把计数也报出来。 */
                var d2 = st.detail || {};
                var pulled2 = (d2.pulled || []).length, confl2 = (d2.conflicts || []).length;
                if (confl2 > 0 && /GT_V/.test(err)) {
                    self._set_note("拉取完成但 " + confl2 + " 处 GT_V* 冲突（板端不动本地）；"
                        + (pulled2 ? ("成功 +" + pulled2 + "；") : "") + err, true);
                } else {
                    self._set_note("拉取失败: " + err, true);
                }
            } else {
                self._set_note("拉取已结束（状态未知）", false);
            }
            return st;
        }).catch(function (e) {
            self._set_note(_parse_reject(e._payload || { error: e.message }), true);
            throw e;
        });
    }

    /* ---------- 录制 ---------- */
    function refresh_board_status() {
        var self = this;
        return _get("/api/board/status").then(function (st) {
            self._set_recording(st.current || null, st.current_created_iso || null, st);
            return st;
        }).catch(function (e) {
            var err = (e && e._payload && e._payload.error) ? String(e._payload.error) : "HTTP 失败";
            self._set_board_down(err);
            return null;
        });
    }

    function toggle_record() {
        var self = this;
        /* FIX-REVIEW-L6: in-flight 防双击重入（板端多会 409，但 UI 语义里应该屏蔽第二次点击）。 */
        if (self._rec_in_flight) return Promise.resolve(null);
        self._rec_in_flight = true;
        /* 先 GET 状态（板不在线 → _set_board_down）再 POST start/stop（403 走降级文案）。 */
        return _get("/api/board/status").catch(function (e) {
            self._set_board_down((e && e._payload && e._payload.error) || "板端不可达");
            throw e;
        }).then(function (st) {
            var is_rec = !!st.current;
            var path = is_rec ? "/api/board/record/stop" : "/api/board/record/start";
            return _post(path, {}).then(function () {
                if (is_rec) {
                    self._set_note("已停止录制", false);
                    self._set_recording(null, null, null);
                } else {
                    self._set_note("开始录制…(正在创建会话)", false);
                    /* 立即再刷一次板端状态，把在录 sid 写回 UI */
                    return refresh_board_status.call(self);
                }
            }).catch(function (e) {
                /* 403 board_mode → 降级文案；别走 _set_board_down（那只是 GET 失败的语义）。 */
                self._set_note(_parse_reject(e._payload || { error: e.message }), true);
                throw e;
            });
        }).then(function (r) { self._rec_in_flight = false; return r; },
                function (e) { self._rec_in_flight = false; throw e; });
    }

    /* ---------- 绑定到页面 ctx ---------- */
    /* ctx:
     *   els: {noteEl, renameInput, renameOk, renameCancel, aliasDraftBtn,
     *         aliasVersionRefresh, pullBtn, recBtn, frozenListEl, sessionInfoProvider}
     *   get_session_info() → S.session_info (晾干 display_name / version_aliases / frozen_versions)
     *   after_pull_ok()    → pull 完成后（比如刷新 sid_select / 重新拉本 sid 的 /api/gt/session）
     *   reload_session(sid)
     */
    function bind(ctx) {
        ctx._set_note = function (msg, is_err) {
            var el = ctx.els.noteEl;
            if (!el) return;
            el.textContent = msg || "";
            el.style.color = is_err ? "#f88" : "#8f8";
        };
        ctx._set_board_down = function (err) {
            var el = ctx.els.recBtn;
            if (el) { el.disabled = true; el.title = err || ""; }
            ctx._set_note("板端离线：" + (err || "?"), true);
        };
        ctx._set_recording = function (sid, created_iso, _st) {
            var el = ctx.els.recBtn;
            if (!el) return;
            el.disabled = false;
            if (sid) {
                el.textContent = "■ 停止录制";
                el.title = sid + (created_iso ? (" · 自 " + created_iso) : "");
            } else {
                el.textContent = "● 开始录制";
                el.title = "";
            }
        };
        ctx._set_timeout = function (fn, ms) {
            if (typeof setTimeout !== "undefined") return setTimeout(fn, ms);
            fn();
        };
        ctx._after_pull_ok = function () {
            if (typeof ctx.after_pull_ok === "function") ctx.after_pull_ok();
        };

        var rename_session_f = rename_session.bind(ctx);
        var set_alias_f = set_alias.bind(ctx);
        var pull_f = pull_from_board.bind(ctx);
        var toggle_record_f = toggle_record.bind(ctx);
        var refresh_board_status_f = refresh_board_status.bind(ctx);

        var els = ctx.els;
        if (els.renameOk) els.renameOk.addEventListener("click", function () {
            if (!ctx.get_session_info) return;
            var info = ctx.get_session_info();
            if (!info || !info.sid) { ctx._set_note("未载入会话", true); return; }
            var label = (els.renameInput && els.renameInput.value) || "";
            rename_session_f(info.sid, label).then(function () {
                if (typeof ctx.reload_session === "function") ctx.reload_session(info.sid);
            }).catch(function () {});
        });
        if (els.aliasDraftBtn) els.aliasDraftBtn.addEventListener("click", function () {
            var info = ctx.get_session_info && ctx.get_session_info();
            if (!info) return;
            var cur = info.draft_alias || "";
            var v = prompt("draft 显示名（空 = 清除）", cur);
            if (v == null) return;
            set_alias_f(info.sid, "draft", null, v).then(function () {
                info.draft_alias = v || null;
                if (typeof ctx.reload_session === "function") ctx.reload_session(info.sid);
            }).catch(function () {});
        });
        if (els.pullBtn) els.pullBtn.addEventListener("click", function () {
            pull_f().catch(function () {});
        });
        if (els.recBtn) els.recBtn.addEventListener("click", function () {
            toggle_record_f().catch(function () {});
        });
        if (ctx.els.frozenListEl && typeof ctx.set_alias_on_version === "function") {
            ctx.els.frozenListEl.addEventListener("click", function (ev) {
                var b = ev.target && ev.target.getAttribute && ev.target.getAttribute("data-alias-ver");
                if (!b) return;
                ctx.set_alias_on_version(b);
            });
        }

        /* 首启刷新录制状态一次（5s 后已由 gt_annotator 主循环替代） */
        if (ctx.auto_refresh_board !== false) {
            refresh_board_status_f().catch(function () {});
        }

        return {
            rename_session: rename_session_f,
            set_alias: set_alias_f,
            pull_from_board: pull_f,
            toggle_record: toggle_record_f,
            refresh_board_status: refresh_board_status_f,
        };
    }

    return {
        bind: bind,
        /* 导出纯函数便于 node 测试复用 */
        _internals: {
            parse_reject: _parse_reject,
            build_alias_body: function (sid, scope, version, name) {
                var b = { sid: sid, scope: scope, name: name };
                if (scope === "version") b.version = version;
                return b;
            },
        },
    };
})();
