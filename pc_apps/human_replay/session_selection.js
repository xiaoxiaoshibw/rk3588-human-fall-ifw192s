/* 本地完整会话入口；不参与配平、检测或跟踪算法。 */
"use strict";
var SESSION_SELECTION = (function () {
    function valid_sid(sid) { return typeof sid === "string" && /^[A-Za-z0-9_-]{1,100}$/.test(sid); }
    function choose(list, query) {
        var seen = new Set();
        list = list.filter(function (s) {
            if (!valid_sid(s.sid) || s.local === false || s.error || !(s.frames > 0) || seen.has(s.sid)) return false;
            seen.add(s.sid); return true;
        }).sort(function (a, b) { return a.sid < b.sid ? 1 : a.sid > b.sid ? -1 : 0; });
        var explicit = query !== null;
        var found = valid_sid(query) && list.some(function (s) { return s.sid === query; });
        var sid = found ? query : (list[0] && list[0].sid) || "";
        var message = explicit && !found ? "指定 sid 不合法或本地不可用：" + (query || "（空）") + "。" : "";
        message += sid ? (explicit && !found ? "已回退到本地最新会话：" + sid : "") : "没有本地完整可用会话（需 meta.json + points.bin）；请先同步。";
        return { list: list, sid: sid, message: message };
    }
    function start(opts) {
        var select = opts.select, notice = opts.notice;
        select.disabled = true;
        function load(sid) {
            select.value = sid;
            return Promise.resolve().then(function () { return opts.load(sid); }).catch(function (e) {
                notice.textContent = "会话 " + sid + " 载入失败：" + e.message + "；请重试或选择其他本地会话。";
            });
        }
        select.addEventListener("change", function () {
            if (!select.value) return;
            notice.textContent = "";
            return load(select.value);
        });
        return fetch(opts.url).then(function (r) {
            if (!r.ok) throw new Error("HTTP " + r.status);
            return r.json();
        }).then(function (data) {
            var list = Array.isArray(data) ? data : data.sessions;
            if (!Array.isArray(list)) throw new Error("会话列表格式错误");
            var picked = choose(list, new URLSearchParams(location.search).get("sid"));
            select.innerHTML = '<option value="">— 选本地会话 —</option>';
            picked.list.forEach(function (s) {
                var option = document.createElement("option");
                option.value = s.sid;
                option.textContent = (s.name || s.sid) + " · " + s.frames + "帧";
                select.appendChild(option);
            });
            notice.textContent = picked.message;
            select.disabled = !picked.list.length;
            if (picked.sid) return load(picked.sid);
        }).catch(function (e) {
            notice.textContent = "本地会话发现失败：" + e.message + "；请刷新重试。";
        });
    }
    return { choose: choose, start: start };
})();
if (typeof module !== "undefined") module.exports = SESSION_SELECTION;
