/* human_capture 控制页的 UI 层（DOM/fetch/poll），lib 函数来自 capture_lib.js。
 * 注意：跨端口 fetch 8090→8766，capture_server 已开 Access-Control-Allow-Origin:* */
(function () {
  "use strict";
  var L = window.HCLIB;
  var API_BASE = "http://" + (location.hostname || "192.168.3.125") + ":8766";
  var app = {
    status: null, sessions: [], currentRecording: null, serverUp: false,
    srvLastErr: "", recLastErr: "", sessLastErr: ""
  };

  function $(id) { return document.getElementById(id); }
  function setErr(elId, msg) { $(elId).textContent = msg || ""; }

  // ---------- 视图 ----------
  function renderHeader() {
    var s = app.status || {};
    $("rosDot").className = "dot" + (s.ros === "up" ? " on" : (s.ros === "down" ? "" : " warn"));
    $("rosVal").textContent = s.ros === "up" ? "在线" : (s.ros === "down" ? "离线" : "未知");
    $("srvDot").className = "dot" + (app.serverUp ? " on" : "");
    $("srvVal").textContent = app.serverUp ? "在线" : "离线";
    $("diskVal").textContent = s.disk_free_mb !== undefined ? (s.disk_free_mb / 1024).toFixed(1) : "--";
    $("totalVal").textContent = s.sessions_total !== undefined ? String(s.sessions_total) : "0";
    $("recVal").textContent = s.recording ? "录制中" : "未";
  }

  function renderRecorder() {
    var wrap = $("currentRecWrap");
    var btnS = $("btnStart"), btnT = $("btnStop");
    var cur = app.currentRecording;
    if (!cur) {
      wrap.innerHTML = '<div class="empty">当前无录制</div>';
      btnS.disabled = !app.serverUp || btnS.disabled && btnS.dataset.cooldown === "1";
      btnT.disabled = true;
      delete btnS.dataset.cooldown;
      return;
    }
    var elapsed = L.elapsedSec(cur.created_iso);
    wrap.innerHTML =
      '<div class="current-rec">' +
      '<span class="badge recording rec">录制中</span>' +
      '<span class="elapsed">' + L.fmtElapsed(elapsed) + '</span>' +
      '<span class="sid">' + cur.session_id + '</span>' +
      "</div>";
    btnS.disabled = true;
    btnT.disabled = false;
  }

  function renderSessions() {
    var body = $("sessBody");
    var sessions = L.sortSessionsDesc(app.sessions);
    if (!sessions.length) {
      body.innerHTML = '<tr><td colspan="9" class="empty">暂无会话</td></tr>';
      return;
    }
    body.innerHTML = sessions.map(function (s) {
      var canDl = L.canRequestDownload(s);
      var dlCell = canDl
        ? '<button data-sid="' + s.session_id + '" class="js-dl">请求下载</button>'
        : (s.download_requested ? "已请求" : (s.transferred ? "—" : "—"));
      return "<tr>" +
        "<td>" + s.session_id + "</td>" +
        "<td>" + L.stateBadgeHtml(s.state) + "</td>" +
        "<td>" + L.fmtDuration(s.duration_sec) + "</td>" +
        "<td>" + (s.frame_count === null || s.frame_count === undefined ? "—" : s.frame_count) + "</td>" +
        "<td>" + L.fmtBytes(s.size_bytes) + "</td>" +
        "<td>" + (s.transferred ? "✓" : "—") + "</td>" +
        "<td>" + (s.download_requested ? "✓" : "—") + "</td>" +
        "<td>" + (s.created_iso || "").replace("T", " ").slice(0, 19) + "</td>" +
        "<td>" + dlCell + "</td>" +
        "</tr>";
    }).join("");
    body.querySelectorAll(".js-dl").forEach(function (btn) {
      btn.addEventListener("click", function () { requestDownload(btn.dataset.sid, btn); });
    });
  }

  // ---------- 数据拉取 ----------
  function fetchJson(path, opts) {
    return fetch(API_BASE + path, opts).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  function pollStatus() {
    fetchJson("/api/v1/status").then(function (s) {
      app.status = s; app.serverUp = true;
      setErr("recErr", "");
      renderHeader();
      // status 说没在录就把 currentRecording 清了
      if (!s.recording) app.currentRecording = null;
      renderRecorder();
    }).catch(function (e) {
      app.serverUp = false; app.status = null;
      app.recLastErr = String(e);
      setErr("recErr", "服务不可达: " + e);
      renderHeader(); renderRecorder();
    });
  }

  function pollSessions() {
    fetchJson("/api/v1/sessions").then(function (d) {
      app.sessions = d.sessions || [];
      setErr("sessErr", "");
      renderSessions();
    }).catch(function (e) {
      setErr("sessErr", "会话拉取失败: " + e);
    });
  }

  function pollCurrent() {
    if (!app.status || !app.status.recording) return;
    fetchJson("/api/v1/record/current").then(function (cur) {
      app.currentRecording = cur;
      renderRecorder();
    }).catch(function () { /* 静 */ });
  }

  // ---------- 动作 ----------
  function startRecord() {
    var btn = $("btnStart");
    btn.disabled = true; btn.dataset.cooldown = "1";
    setErr("recErr", "");
    fetchJson("/api/v1/record/start", { method: "POST" }).then(function () {
      pollStatus();
      setTimeout(function () { btn.dataset.cooldown = ""; renderRecorder(); }, 1500);
    }).catch(function (e) {
      setErr("recErr", "起录失败: " + e);
      btn.disabled = false; delete btn.dataset.cooldown;
    });
  }

  function stopRecord() {
    var btn = $("btnStop");
    btn.disabled = true;
    setErr("recErr", "");
    fetchJson("/api/v1/record/stop", { method: "POST" }).then(function () {
      pollStatus(); pollSessions();
      setTimeout(function () { btn.disabled = false; renderRecorder(); }, 1000);
    }).catch(function (e) {
      setErr("recErr", "停止失败: " + e);
      btn.disabled = false;
    });
  }

  function requestDownload(sid, btn) {
    if (btn) btn.disabled = true;
    fetchJson("/api/v1/sessions/" + encodeURIComponent(sid), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ extra: { download_requested: true } })
    }).then(function () {
      pollSessions();
    }).catch(function (e) {
      setErr("sessErr", "请求下载失败: " + e);
      if (btn) btn.disabled = false;
    });
  }

  // ---------- 启动 ----------
  function main() {
    $("btnStart").addEventListener("click", startRecord);
    $("btnStop").addEventListener("click", stopRecord);
    pollStatus(); pollSessions();
    setInterval(pollStatus, 1000);
    setInterval(pollSessions, 2000);
    setInterval(pollCurrent, 1000);
    // elapsed 每秒本地走表（即便 server 慢）
    setInterval(function () {
      if (app.currentRecording) renderRecorder();
    }, 1000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", main);
  else main();
}());
