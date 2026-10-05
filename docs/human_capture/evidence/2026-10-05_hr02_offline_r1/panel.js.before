/* HR-02 侧栏：会话面板 + 内置录制控制台。
 * 依赖 human_replay_lib.py 本地服务（/api/*）。非本服务环境自动禁用（如 file:// 双击）。
 */
"use strict";

(function () {
    var panel = document.getElementById("panel");
    var els = {};
    ["sessionsBtn", "panelClose", "sessBody", "sessEmpty", "boardStatus",
     "recBtn", "recSid", "boardMeta", "refreshBtn", "syncBtn", "browseBtn",
     "delBtn", "syncNote", "panelStatus"].forEach(function (id) {
         els[id] = document.getElementById(id);
    });

    if (!els.sessionsBtn) return;

    // 当前选中 sid
    var selected_sid = null;

    function setNote(msg, is_err) {
        els.syncNote.textContent = msg || "";
        els.syncNote.style.color = is_err ? "#f88" : "#ffcc80";
    }

    function api(path, method, body) {
        return fetch(path, {
            method: method || "GET",
            headers: body ? { "Content-Type": "application/json" } : undefined,
            body: body ? JSON.stringify(body) : undefined,
        }).then(function (r) {
            if (!r.ok) return r.json().catch(function () { return {}; }).then(function (j) {
                throw new Error(j.error || ("HTTP " + r.status));
            });
            return r.json();
        });
    }

    // ---------- 板端状态 + 控制台 ----------
    function refresh_board() {
        api("/api/board/status").then(function (st) {
            if (st.error) {
                els.boardStatus.textContent = "板端: " + st.error;
                els.boardStatus.style.color = "#f88";
                els.recBtn.disabled = true;
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
                els.recSid.textContent = st.current;
            } else {
                els.recBtn.textContent = "● 开始录制";
                els.recBtn.classList.remove("recording");
                els.recSid.textContent = "";
            }
            els.boardMeta.textContent = "";
        }).catch(function (e) {
            els.boardStatus.textContent = "板端: " + e.message;
            els.boardStatus.style.color = "#f88";
            els.recBtn.disabled = true;
        });
    }

    els.recBtn.addEventListener("click", function () {
        var going = els.recBtn.classList.contains("recording");
        var path = going ? "/api/board/record/stop" : "/api/board/record/start";
        els.recBtn.disabled = true;
        api(path, "POST").then(function (r) {
            setNote(r.session_id ? ("会话 " + r.session_id + (going ? " 收尾中" : " 起录")) : okText(r));
            refresh_board();
            setTimeout(refresh_sessions, 1200);
        }).catch(function (e) {
            setNote("控制台失败: " + e.message, true);
            refresh_board();
        });
    });

    function okText(r) { return r.ok ? "ok" : JSON.stringify(r); }

    // ---------- 会话列表 ----------
    function render_sessions(list) {
        els.sessBody.innerHTML = "";
        if (!list || !list.length) {
            els.sessEmpty.style.display = "block";
            return;
        }
        els.sessEmpty.style.display = "none";
        list.forEach(function (s) {
            var tr = document.createElement("tr");
            if (s.sid === selected_sid) tr.classList.add("sel");
            tr.dataset.sid = s.sid;
            var dur = (s.duration_sec != null) ? s.duration_sec.toFixed(1) + "s" : "—";
            var frames = (s.frames != null) ? s.frames : "—";
            tr.innerHTML =
                "<td title=\"" + s.sid + "\">" + s.sid.replace(/^cap_/, "") + "</td>" +
                "<td>" + dur + "</td>" +
                "<td>" + frames + "</td>" +
                "<td class=\"" + (s.transferred || s.download_requested ? "ok" : "dim") + "\">" +
                  (s.transferred ? "✓已传" : s.download_requested ? "待拉" : s.state || "—") + "</td>" +
                "<td class=\"" + (s.local ? "ok" : "dim") + "\">" + (s.local ? "✓" : "—") + "</td>";
            tr.addEventListener("click", function () {
                els.sessBody.querySelectorAll("tr").forEach(function (x) { x.classList.remove("sel"); });
                tr.classList.add("sel");
                selected_sid = s.sid;
                if (s.local) {
                    load_by_sid(s.sid);
                } else {
                    setNote("本地未拉取 — 点「同步选中」");
                }
            });
            els.sessBody.appendChild(tr);
        });
    }

    function refresh_sessions() {
        els.panelStatus && (els.panelStatus.textContent = "加载中…");
        api("/api/sessions").then(function (r) {
            render_sessions(r.sessions || []);
            if (els.panelStatus) {
                els.panelStatus.textContent = r.board_error ? ("板端: " + r.board_error) : "";
            }
        }).catch(function (e) {
            if (els.panelStatus) els.panelStatus.textContent = e.message;
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

    // ---------- 同步 ----------
    els.syncBtn.addEventListener("click", function () {
        if (!selected_sid) { setNote("先在列表里点一行", true); return; }
        setNote("同步中（大文件 ~分钟）…");
        api("/api/sync", "POST", { sid: selected_sid }).then(function (r) {
            setNote(r.note || "已起同步，轮询 /api/sessions 等 local=✓");
            poll_until_local(selected_sid, 0);
        }).catch(function (e) {
            setNote("同步失败: " + e.message, true);
        });
    });

    function poll_until_local(sid, tries) {
        if (tries > 60) { setNote("同步超时（5 分钟）— 看 fetch.py 输出", true); return; }
        setTimeout(function () {
            api("/api/sessions").then(function (r) {
                render_sessions(r.sessions || []);
                var s = (r.sessions || []).find(function (x) { return x.sid === sid; });
                if (s && s.local) {
                    setNote("✓ 同步完成，点列表载人");
                    return refresh_sessions();
                }
                poll_until_local(sid, tries + 1);
            });
        }, 5000);
    }

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
        }
    });
    els.panelClose.addEventListener("click", function () { panel.classList.remove("open"); });
    els.refreshBtn.addEventListener("click", refresh_sessions);
})();
