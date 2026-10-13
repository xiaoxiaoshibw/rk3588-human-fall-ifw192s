/* dom_extract.js — 从 --dump-dom 产物提取 demo 加载证据（规避 bash 转义）。 */
"use strict";
const fs = require("fs");
const file = process.argv[2];
const d = fs.readFileSync(file, "utf8");
/* 剥离 <script>/<style> —— error 判定只看渲染后可见 DOM，不扫内嵌源码文本。 */
const view = d.replace(/<script[\s\S]*?<\/script>/g, " ").replace(/<style[\s\S]*?<\/style>/g, " ");
const grab = re => { const m = d.match(re); return m ? m[1] : null; };
const out = {
    bytes: d.length,
    title: grab(/<title>([^<]*)<\/title>/),
    counter: grab(/id="counter"[^>]*>([^<]*)</),
    session_option_values: [...d.matchAll(/<option value="(cap_[^"]*)"/g)].map(m => m[1]),
    session_option_labels: [...d.matchAll(/<option value="cap_[^"]*"[^>]*>([^<]*)<\/option>/g)].map(m => m[1].slice(0, 44)),
    xgb_default_option: /xgb69_candidate/.test(d),
    status: (grab(/id="status"[^>]*>([\s\S]*?)<\/div>/) || "").replace(/\s+/g, " ").slice(0, 160),
    rows_count: (view.match(/<tr>/g) || []).length,
    detail: (grab(/id="detail"[^>]*>([\s\S]*?)<\/p>/) || "").slice(0, 80),
    error_marker: /错误：\S|发现失败：\S|载入失败：\S|会话发现失败\S/.test(view),
};
console.log(JSON.stringify(out, null, 2));
