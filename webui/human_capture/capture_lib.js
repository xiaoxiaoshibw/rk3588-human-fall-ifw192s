/* human_capture 控制页的纯函数库——node 可测试。
 * 不依赖 DOM/fetch；UI 层在 capture.js。 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.HCLIB = factory();
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var STATE_BADGE_CLASS = {
    recording:   "badge recording rec",
    extracting:  "badge extracting",
    ready:       "badge ready",
    transferring:"badge transferring",
    transferred: "badge transferred",
    failed:      "badge failed",
    purged:      "badge purged"
  };

  var STATE_LABEL = {
    recording:   "录制中",
    extracting:  "抽取中",
    ready:       "就绪",
    transferring:"下载中",
    transferred: "已下载",
    failed:      "失败",
    purged:      "已清理"
  };

  function fmtBytes(n) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    var units = ["B", "KB", "MB", "GB"];
    var v = n, i = 0;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return (i === 0 ? v : v.toFixed(v < 10 ? 2 : 1)) + " " + units[i];
  }

  function fmtDuration(sec) {
    if (sec === null || sec === undefined || isNaN(sec)) return "—";
    if (sec < 60) return sec.toFixed(1) + "s";
    var m = Math.floor(sec / 60), s = Math.round(sec % 60);
    return m + "m" + (s < 10 ? "0" : "") + s + "s";
  }

  function fmtElapsed(sec) {
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60);
    if (h) return h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function stateBadgeHtml(state) {
    var cls = STATE_BADGE_CLASS[state] || "badge";
    var label = STATE_LABEL[state] || state || "?";
    return '<span class="' + cls + '">' + label + "</span>";
  }

  function stateLabel(state) {
    return STATE_LABEL[state] || state || "?";
  }

  /* 会话按 created_iso 倒序（新在前）。容忍字段缺失。*/
  function sortSessionsDesc(sessions) {
    return (sessions || []).slice().sort(function (a, b) {
      var ca = (a && a.created_iso) || "", cb = (b && b.created_iso) || "";
      return ca < cb ? 1 : ca > cb ? -1 : 0;
    });
  }

  /* 判断某会话是否能"触发下载"：ready 且未 transferred 且未 requested。*/
  function canRequestDownload(s) {
    return !!(s && s.state === "ready" && !s.transferred && !s.download_requested);
  }

  /* elapsed 计算：从 created_iso 到现在。返回秒（number）。*/
  function elapsedSec(createdIso, nowMs) {
    if (!createdIso) return 0;
    var t = Date.parse(createdIso);
    if (isNaN(t)) return 0;
    var now = nowMs !== undefined ? nowMs : Date.now();
    return Math.max(0, (now - t) / 1000);
  }

  return {
    fmtBytes: fmtBytes,
    fmtDuration: fmtDuration,
    fmtElapsed: fmtElapsed,
    stateBadgeHtml: stateBadgeHtml,
    stateLabel: stateLabel,
    sortSessionsDesc: sortSessionsDesc,
    canRequestDownload: canRequestDownload,
    elapsedSec: elapsedSec,
    STATE_BADGE_CLASS: STATE_BADGE_CLASS,
    STATE_LABEL: STATE_LABEL
  };
}));
