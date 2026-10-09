/* human_track_static.test.js — human_track.html 静态契约验证.
 *
 * 测 hard requirements:
 *   R1 静态 HTML 中任何 id 不得重复 (如 playBtn, 任何 <button id=>)
 *   R2 replay.js 所需的所有 els id 在 HTML 中必须存在 (否则启动即 NPE)
 *   R3 处理 playBtnTop → playBtn 的转发脚本:
 *      不得改 replay.js, 不得改 id (动态也不行)
 */
"use strict";

var fs = require("fs");
var path = require("path");

var HTML = fs.readFileSync(path.join(__dirname, "human_track.html"), "utf-8");
var PLAY = fs.readFileSync(path.join(__dirname, "replay.js"), "utf-8");

function assert(cond, msg) {
    if (!cond) { console.log("FAIL: " + msg); process.exit(1); }
    console.log("PASS: " + msg);
}

// R1: 所有 id= 全局唯一
(function () {
    var ids = {};
    var dup = [];
    var re = /\bid="([^"]+)"/g, m;
    while ((m = re.exec(HTML)) !== null) {
        if (ids[m[1]]) dup.push(m[1]);
        ids[m[1]] = 1;
    }
    assert(dup.length === 0, "R1: HTML 中无重复 id" + (dup.length ? " (dup: " + dup.join(",") + ")" : ""));
})();

// R2: replay.js 要求的所有 id 在 HTML 里存在
(function () {
    // 从 replay.js 里 els 数组直接抠出来
    var m = PLAY.match(/\["pickBtn"[\s\S]*?"trimCopyBtn"\]/);
    assert(m, "R2 prelim: replay.js els 数组 pattern ok");
    var arr = eval(m[0]);
    var missing = arr.filter(function (id) { return !new RegExp('id="' + id + '"').test(HTML); });
    assert(missing.length === 0, "R2: replay.js 要求的所有 els id 在 HTML 里存在" + (missing.length ? " (missing: " + missing.join(",") + ")" : ""));
})();

// R3: 转发脚本不读不改 replay.js 的 id (不存在动态改名)
(function () {
    // 顶栏触发器只在 relay block 里存在
    var relay = HTML.match(/顶栏播放按钮[\s\S]*?\}\)\(\);/);
    assert(relay, "R3: relay block 存在");
    var body = relay[0];
    // 禁止动态改 id
    assert(!/\.id\s*=/.test(body), "R3: relay 脚本不得动态修改任何元素的 id 属性");
    // 必须存在播放按钮关联
    assert(/getElementById\("playBtnTop"\)/.test(body), "R3: relay 必须读 playBtnTop");
    assert(/getElementById\("playBtn"\)/.test(body), "R3: replay playBtn id 必须保留作为 relay target");
})();

console.log("ALL STATIC CONTRACT PASS");
