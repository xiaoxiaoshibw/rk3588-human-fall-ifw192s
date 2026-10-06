/* LiDAR 工作站 · UI 轻量组件（与 ui.css 配套，无依赖）。
 * 只做展示层：toast 右上角统一反馈。不参与任何算法与数据逻辑。 */
(function (global) {
  "use strict";
  function stack() {
    var el = document.querySelector(".toast-stack");
    if (!el) {
      el = document.createElement("div");
      el.className = "toast-stack";
      document.body.appendChild(el);
    }
    return el;
  }
  /* UI.toast("Ground detected", {kind:"pass", sub:"TLS · 82.7%", ms:3500}) */
  function toast(msg, opt) {
    opt = opt || {};
    var t = document.createElement("div");
    t.className = "toast " + (opt.kind || "");
    t.textContent = msg;
    if (opt.sub) {
      var s = document.createElement("span");
      s.className = "t-sub";
      s.textContent = opt.sub;
      t.appendChild(s);
    }
    var kill = function () {
      if (!t.parentNode) return;
      t.classList.add("out");
      setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 200);
    };
    t.addEventListener("click", kill);
    stack().appendChild(t);
    if (opt.ms !== 0) setTimeout(kill, opt.ms || 3500);
    return t;
  }
  global.UI = { toast: toast };
})(window);
