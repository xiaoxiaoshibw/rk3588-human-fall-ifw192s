/* HR-02 侧栏：会话面板 + 内置录制控制台。
 * 依赖 human_replay_lib.py 本地服务（/api/*）。非本服务环境自动禁用（如 file:// 双击）。
 */
"use strict";

(function () {
    var panel = document.getElementById("panel");
    var els = {};
    ["sessionsBtn", "panelClose", "sessBody", "sessEmpty", "boardStatus",
     "recBtn", "recSid", "boardMeta", "refreshBtn", "syncBtn", "recoverBtn", "recoverRow",
     "browseBtn", "renameBtn", "renameRow", "renameInput", "renameOk", "renameCancel",
     "delBtn", "syncNote", "panelStatus"].forEach(function (id) {
         els[id] = document.getElementById(id);
    });

    if (!els.sessionsBtn) return;

    // 当前选中 sid
    var selected_sid = null;
    var refresh_version = 0;
    var pending_load_sid = null;   // 正在同步且完成后要自动载入的 sid
    var sessions_by_sid = {};      // 最近一次渲染的行数据（改名预填 / local 判定）
    var rename_sid = null;         // 改名行打开时锁定的会话（之后点别的行不改错人）
    var rec_sid = null;            // 当前录制会话（板端 current）
    var rec_created_iso = null;    // 录制开始时间（板端 created_iso，用于已录时长）
    var board_timer = null;        // 面板打开期间的 1s 走表 / 5s 刷板端定时器
    var recover_sid = null;        // 上次同步失败可「退回重试」的会话

    function esc(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }

    function setNote(msg, is_err) {
        els.syncNote.textContent = msg || "";
        els.syncNote.style.color = is_err ? "#f88" : "#ffcc80";
    }

    // ---------- 录制中显示（本地走表；每 5s 拉一次板端状态） ----------
    function fmt_rec_elapsed(sec) {
        sec = Math.max(0, Math.floor(sec || 0));
        var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
        function pad(x) { return (x < 10 ? "0" : "") + x; }
        return h ? h + ":" + pad(m) + ":" + pad(s) : pad(m) + ":" + pad(s);
    }

    function render_rec() {
        if (!rec_sid) { els.recSid.textContent = ""; return; }
        var t = rec_created_iso ? Date.parse(rec_created_iso) : NaN;
        els.recSid.textContent = rec_sid + (isNaN(t) ? " · 已录 --:--"
            : " · 已录 " + fmt_rec_elapsed((Date.now() - t) / 1000));
    }

    function toggle_recover() {
        if (recover_sid) els.recoverRow.classList.add("open");
        else els.recoverRow.classList.remove("open");
    }

    function stop_board_timer() {
        if (board_timer) { clearTimeout(board_timer); board_timer = null; }
    }

    function start_board_timer() {
        stop_board_timer();
        var ticks = 0;
        (function loop() {
            board_timer = setTimeout(function () {
                if (!panel.classList.contains("open")) { stop_board_timer(); return; }
                render_rec();                            // 本地走表，不发请求
                if (++ticks % 5 === 0) refresh_board();  // 每 5s 刷板端状态
                loop();
            }, 1000);
        })();
    }

    function api(path, method, body) {
        // GET 超时只影响读状态；录制/同步等写请求仍等待实际结果。
        var controller = (!method || method === "GET") ? new AbortController() : null;
        var timer = controller ? setTimeout(function () { controller.abort(); }, 6000) : null;
        return fetch(path, {
            method: method || "GET",
            headers: body ? { "Content-Type": "application/json" } : undefined,
            body: body ? JSON.stringify(body) : undefined,
            signal: controller ? controller.signal : undefined,
        }).then(function (r) {
            if (!r.ok) return r.json().catch(function () { return {}; }).then(function (j) {
                throw new Error(j.error || ("HTTP " + r.status));
            });
            return r.json();
        }).then(function (r) {
            clearTimeout(timer);
            return r;
        }, function (e) {
            clearTimeout(timer);
            if (e.name === "AbortError") throw new Error("请求超时");
            throw e;
        });
    }

    // ---------- 板端状态 + 控制台 ----------
    function refresh_board() {
        api("/api/board/status").then(function (st) {
            if (st.error) {
                els.boardStatus.textContent = "板端离线，可回放本地会话";
                els.boardStatus.title = st.error;
                els.boardStatus.style.color = "#f88";
                els.recBtn.disabled = true;
                rec_sid = null; rec_created_iso = null; render_rec();
                return;
            }
            var ros = st.ros === "up";
            els.boardStatus.textContent = "板端 ROS: " + (ros ? "● up" : "○ down") +
                "  盘余:" + st.disk_free_mb + "MB  会话:" + st.sessions_total;
            els.boardStatus.style.color = ros ? "#8f8" : "#fa0";
            els.recBtn.disabled = !ros;
            if (st.current) {
                els.recBtn.textContent = "■ 停止录制";
                els.recBtn.classList.add("recording");
                rec_sid = st.current;
                rec_created_iso = st.current_created_iso || null;
                render_rec();
            } else {
                els.recBtn.textContent = "● 开始录制";
                els.recBtn.classList.remove("recording");
                rec_sid = null; rec_created_iso = null; render_rec();
            }
            els.boardMeta.textContent = "";
        }).catch(function (e) {
            els.boardStatus.textContent = "板端离线，可回放本地会话";
            els.boardStatus.title = e.message;
            els.boardStatus.style.color = "#f88";
            els.recBtn.disabled = true;
            rec_sid = null; rec_created_iso = null; render_rec();
        });
    }

    els.recBtn.addEventListener("click", function () {
        var going = els.recBtn.classList.contains("recording");
        var path = going ? "/api/board/record/stop" : "/api/board/record/start";
        els.recBtn.disabled = true;
        api(path, "POST").then(function (r) {
            setNote(r.session_id ? ("会话 " + r.session_id + (going ? " 收尾中" : " 起录")) : okText(r));
            if (going) {
                // 停止：板端 SIGINT 收尾最长 15s（grace）+ 5s（kill）；
                // 期间 refresh_board() 还会看到 current=该 sid，把按钮又切回「停止录制」。
                // 轮询 /api/board/status 直到 current 真的消失，再切按钮文字。
                poll_until_stopped(0);
            } else {
                refresh_board();
                setTimeout(refresh_sessions, 1200);
            }
        }).catch(function (e) {
            setNote("控制台失败: " + e.message, true);
            refresh_board();
        });
    });

    function poll_until_stopped(tries) {
        // 20s 上限：sigint_grace_sec=15 + sigterm_kill_sec=5 的最坏和。
        if (tries > 20) { refresh_board(); setTimeout(refresh_sessions, 1200); return; }
        setTimeout(function () {
            api("/api/board/status").then(function (st) {
                if (st.current) {
                    els.recBtn.textContent = "■ 收尾中…";
                    els.recBtn.disabled = true;  // 收尾期间禁再点，防重复 SIGINT 把 _watch 弄乱
                    poll_until_stopped(tries + 1);
                } else {
                    // 真的停了：一次性刷按钮 + 会话列表
                    refresh_board();
                    setTimeout(refresh_sessions, 1200);
                }
            }).catch(function () {
                poll_until_stopped(tries + 1);
            });
        }, 1000);
    }

    function okText(r) { return r.ok ? "ok" : JSON.stringify(r); }

    // ---------- 会话列表 ----------
    function render_sessions(list) {
        els.sessBody.innerHTML = "";
        sessions_by_sid = {};
        if (!list || !list.length) {
            els.sessEmpty.style.display = "block";
            return;
        }
        els.sessEmpty.style.display = "none";
        list.forEach(function (s) {
            sessions_by_sid[s.sid] = s;
            var tr = document.createElement("tr");
            if (s.sid === selected_sid) tr.classList.add("sel");
            tr.dataset.sid = s.sid;
            var dur = (s.duration_sec != null) ? s.duration_sec.toFixed(1) + "s" : "—";
            var frames = (s.frames != null) ? s.frames : "—";
            var label = s.name ? esc(s.name) : esc(s.sid.replace(/^cap_/, ""));
            tr.innerHTML =
                "<td title=\"" + esc(s.sid) + "\">" + label + "</td>" +
                "<td>" + dur + "</td>" +
                "<td>" + frames + "</td>" +
                "<td class=\"" + (s.transferred || s.download_requested ? "ok" : "dim") + "\">" +
                  (s.transferred ? "✓已传" : s.state === "transferring" ? "下载中" :
                   s.download_requested ? "待拉" : s.state || "—") + "</td>" +
                "<td class=\"" + (s.local ? "ok" : "dim") + "\">" + (s.local ? "✓" : "—") + "</td>";
            tr.addEventListener("click", function () {
                els.sessBody.querySelectorAll("tr").forEach(function (x) { x.classList.remove("sel"); });
                tr.classList.add("sel");
                selected_sid = s.sid;
                els.renameRow.classList.remove("open");   // 换选中即收起改名行
                if (s.local) {
                    load_by_sid(s.sid);
                } else {
                    // 未下载 = 一键开工：点一下就同步，完成后自动载入（板端 transferred 也能拉）
                    setNote("本地未拉取 — 自动同步…");
                    start_sync(s.sid);
                }
            });
            els.sessBody.appendChild(tr);
        });
    }

    function refresh_sessions() {
        var version = ++refresh_version;
        els.panelStatus && (els.panelStatus.textContent = "加载本地…");
        api("/api/sessions?scope=local").then(function (r) {
            if (version !== refresh_version) return;
            render_sessions(r.sessions || []);
            if (els.panelStatus) els.panelStatus.textContent = "本地可用，检查板端…";
            return api("/api/sessions").then(function (remote) {
                if (version !== refresh_version) return;
                if (!remote.board_error) render_sessions(remote.sessions || []);
                // 数据完整性过滤留下的计数：告诉用户「列表变短」不是丢数据，是登记表里的空壳
                var hid = remote.hidden ? (remote.hidden.purged || 0) + (remote.hidden.missing || 0) : 0;
                if (els.panelStatus) els.panelStatus.textContent = remote.board_error
                    ? "离线 · 本地会话" : (hid ? "已隐藏 " + hid + " 条无数据登记" : "");
            }).catch(function () {
                if (version === refresh_version && els.panelStatus)
                    els.panelStatus.textContent = "离线 · 本地会话";
            });
        }).catch(function (e) {
            if (version !== refresh_version) return;
            if (els.panelStatus) {
                els.panelStatus.textContent = "本地列表失败: " + e.message;
            }
        });
    }

    // ---------- 载入指定 sid（同 server 上 /api/file?sid=…） ----------
    function load_by_sid(sid) {
        if (!window.__load_session_sid) {
            setNote("回放器未注册 sid 载入接口", true);
            return;
        }
        setNote("载入 " + sid + "…");
        window.__load_session_sid(sid).then(function () {
            setNote("已载入 " + sid);
        }).catch(function (e) {
            setNote("载入失败: " + e.message, true);
        });
    }

    // ---------- 同步（下载板端会话；完成自动载入） ----------
    function start_sync(sid) {
        recover_sid = null;
        toggle_recover();
        setNote("同步中（大文件 ~分钟）…");
        api("/api/sync", "POST", { sid: sid }).then(function (r) {
            pending_load_sid = sid;
            setNote(r.note || "已起同步，轮询 /api/sessions 等 local=✓");
            poll_until_local(sid, 0);
        }).catch(function (e) {
            setNote("同步失败: " + e.message, true);
        });
    }

    els.syncBtn.addEventListener("click", function () {
        if (!selected_sid) { setNote("先在列表里点一行", true); return; }
        start_sync(selected_sid);
    });

    els.recoverBtn.addEventListener("click", function () {
        if (!recover_sid) { return; }
        var sid = recover_sid;
        els.recoverBtn.disabled = true;
        setNote("退回就绪，重新同步 " + sid + "…");
        api("/api/recover", "POST", { sid: sid }).then(function () {
            els.recoverBtn.disabled = false;
            start_sync(sid);
        }).catch(function (e) {
            els.recoverBtn.disabled = false;
            setNote("退回失败: " + e.message, true);
        });
    });

    function finish_sync(sid, err, recoverable) {
        var want_load = pending_load_sid === sid;
        if (want_load) pending_load_sid = null;
        recover_sid = (err && recoverable) ? sid : null;
        toggle_recover();
        if (err) {
            setNote("同步失败: " + err, true);
            return refresh_sessions();
        }
        if (want_load) {
            setNote("✓ 同步完成，自动载入");
            load_by_sid(sid);
        } else {
            setNote("✓ 同步完成，点列表载人");
        }
        refresh_sessions();
    }

    function poll_until_local(sid, tries) {
        if (tries > 60) { pending_load_sid = null; setNote("同步超时（5 分钟）— 看 fetch.py 输出", true); return; }
        setTimeout(function () {
            // 同时查 sessions（拿 local 标记）+ sync_status（拿最终结局）。
            // 后端 _worker 退出时会显式写 last_result="ok"/"failed"，前端只看这个，
            // 不用靠 local=true 间接猜。
            Promise.all([
                api("/api/sessions").catch(function () { return null; }),
                api("/api/sync_status").catch(function () { return null; }),
            ]).then(function (rs) {
                var sr = rs[0], ss = rs[1];
                var done_for_us = ss && ss.last_sid === sid && ss.last_result !== null && !ss.running;
                if (done_for_us) {
                    return finish_sync(sid, ss.last_result === "ok" ? null : (ss.last_error || "未知"),
                        !!(ss.recoverable && ss.recover_sid === sid));
                }
                if (sr) {
                    render_sessions(sr.sessions || []);
                    var s = (sr.sessions || []).find(function (x) { return x.sid === sid; });
                    if (s && s.local) {
                        // 兜底：sync_status 短暂丢包但 sessions 已显示 local —— 信 sessions
                        return finish_sync(sid, null);
                    }
                }
                poll_until_local(sid, tries + 1);
            });
        }, 5000);
    }

    // ---------- 改名（本地别名：sid/目录/板端都不动，只写 meta.name） ----------
    function rename_save() {
        if (!rename_sid) { return; }
        var name = els.renameInput.value.trim();
        els.renameOk.disabled = true;
        api("/api/rename", "POST", { sid: rename_sid, name: name }).then(function () {
            els.renameOk.disabled = false;
            els.renameRow.classList.remove("open");
            rename_sid = null;
            setNote(name ? ("已命名：" + name) : "已恢复默认名称");
            refresh_sessions();
        }).catch(function (e) {
            els.renameOk.disabled = false;
            setNote("改名失败: " + e.message, true);
        });
    }

    els.renameBtn.addEventListener("click", function () {
        if (!selected_sid) { setNote("先在列表里点一行", true); return; }
        var s = sessions_by_sid[selected_sid];
        if (!s || !s.local) {
            setNote("该会话还没下载到本地 — 先点它自动同步，完成后再改名", true);
            return;
        }
        rename_sid = selected_sid;
        els.renameRow.classList.add("open");
        els.renameInput.value = s.name || "";
        if (els.renameInput.focus) els.renameInput.focus();
    });
    els.renameOk.addEventListener("click", rename_save);
    els.renameCancel.addEventListener("click", function () {
        els.renameRow.classList.remove("open");
        rename_sid = null;
    });
    els.renameInput.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") { ev.preventDefault(); rename_save(); }
        else if (ev.key === "Escape") { els.renameRow.classList.remove("open"); }
    });

    // ---------- 删除（本地 + 板端） ----------
    els.delBtn.addEventListener("click", function () {
        if (!selected_sid) { setNote("先在列表里点一行", true); return; }
        var sid = selected_sid;
        var row = els.sessBody.querySelector("tr[data-sid=\"" + sid + "\"]");
        var loc = row ? !!row.querySelector("td:nth-child(5).ok") : false;
        var scope;
        if (loc) {
            scope = window.confirm(
                "确认删除会话 " + sid + "？\n" +
                "包括：本地目录 + 板端登记和文件（bag/meta/bin）。\n" +
                "「确定」= 删两侧；「取消」= 只删本地。") ? "both" : "local";
        } else {
            scope = window.confirm("删除板端会话 " + sid + "（含其 bag/meta/bin）？")
                ? "board" : "";
        }
        if (!scope) { setNote("已取消"); return; }
        if (scope !== "local" && !window.confirm(
            "此操作不可撤销（文件会被 rm），最后确认一次删除？")) {
            setNote("二次确认已取消"); return;
        }
        els.delBtn.disabled = true;
        setNote("删除中…");
        api("/api/delete", "POST", { sid: sid, scope: scope }).then(function (r) {
            els.delBtn.disabled = false;
            var board = r.board || {};
            var btxt = board.removed ? ("板端已删 " + board.removed.length + " 项")
                                     : (board.skipped || board.error || "板端未动");
            if (board.busy || (board.error && /busy|录制|传输/.test(board.error))) {
                setNote("板端正忙（录制/传输中），不可删——先停", true);
                return;
            }
            setNote("已删除 " + sid + "  [本地:" + (r.local || "-") + "  " + btxt + "]");
            if (selected_sid === sid) selected_sid = null;
            refresh_sessions();
        }).catch(function (e) {
            els.delBtn.disabled = false;
            setNote("删除失败: " + e.message, true);
        });
    });

    // ---------- 手动选（Tk） ----------
    els.browseBtn.addEventListener("click", function () {
        setNote("弹手动选目录…");
        api("/api/load", "POST").then(function (r) {
            if (!r.ok) { setNote(r.error || "取消", true); return; }
            selected_sid = r.sid;
            load_by_sid(r.sid);
            refresh_sessions();
        }).catch(function (e) { setNote("手动选失败: " + e.message, true); });
    });

    // ---------- 开关面板 ----------
    els.sessionsBtn.addEventListener("click", function () {
        panel.classList.toggle("open");
        if (panel.classList.contains("open")) {
            refresh_board();
            refresh_sessions();
            start_board_timer();
        } else {
            stop_board_timer();
        }
    });
    els.panelClose.addEventListener("click", function () {
        panel.classList.remove("open");
        stop_board_timer();
    });
    els.refreshBtn.addEventListener("click", refresh_sessions);
})();
