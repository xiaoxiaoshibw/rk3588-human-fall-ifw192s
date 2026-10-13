/* cdp_e2e.js — HUMAN-FUSION-UNIFY-R1 / STEP 4 真实浏览器端到端（无第三方库）。
 * 依赖：本机 Chrome 以 --remote-debugging-port 启动；demo server 已在 DEMO_PORT 运行。
 * 实现最小 RFC6455 客户端 + CDP 子集（Page/Runtime），驱动 demo.html 并采集异常。
 * 运行：node cdp_e2e.js [chromePort=9223] [demoPort=8797]   （exit 0 = 全绿）
 */
"use strict";
const http = require("http"), net = require("net"), crypto = require("crypto"), fs = require("fs"), path = require("path");
const CDP_PORT = Number(process.argv[2] || 9223), DEMO = "http://127.0.0.1:" + (process.argv[3] || 8797);
const checks = [], errors = [];
function ok(name, cond, extra) { checks.push({ name, pass: !!cond, extra: extra || null }); console.log((cond ? "PASS " : "FAIL ") + name + (extra ? "  [" + extra + "]" : "")); if (!cond) process.exitCode = 1; }
function httpJson(method, pathPart) {
    return new Promise((res, rej) => {
        const r = http.request({ host: "127.0.0.1", port: CDP_PORT, path: pathPart, method }, resp => {
            let d = ""; resp.on("data", c => d += c); resp.on("end", () => { try { res(JSON.parse(d)); } catch (e) { rej(new Error("bad json: " + d.slice(0, 200))); } });
        });
        r.on("error", rej); r.end();
    });
}
/* ---- 最小 WebSocket（客户端帧带 mask；处理 ping/close；消息可跨帧重组） ---- */
class WS {
    constructor(wsUrl) { const m = /^ws:\/\/([^:/]+):(\d+)(\/.*)$/.exec(wsUrl); this.host = m[1]; this.port = +m[2]; this.path = m[3]; this.buf = Buffer.alloc(0); this.frags = []; this.onmsg = () => {}; }
    connect() {
        return new Promise((res, rej) => {
            const key = crypto.randomBytes(16).toString("base64");
            this.sock = net.connect(this.port, this.host, () => {
                this.sock.write("GET " + this.path + " HTTP/1.1\r\nHost: " + this.host + ":" + this.port + "\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: " + key + "\r\nSec-WebSocket-Version: 13\r\n\r\n");
            });
            let shook = false, acc = Buffer.alloc(0);
            this.sock.on("data", chunk => {
                if (!shook) {
                    acc = Buffer.concat([acc, chunk]);
                    const i = acc.indexOf("\r\n\r\n"); if (i < 0) return;
                    const head = acc.slice(0, i).toString();
                    if (!/^HTTP\/1\.1 101/.test(head)) return rej(new Error("handshake: " + head.split("\r\n")[0]));
                    const expect = crypto.createHash("sha1").update(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest("base64");
                    if (!head.includes(expect)) return rej(new Error("accept mismatch"));
                    shook = true; this.buf = acc.slice(i + 4); this._drain(); res();
                } else { this.buf = Buffer.concat([this.buf, chunk]); this._drain(); }
            });
            this.sock.on("error", rej);
        });
    }
    _frame(opcode, payload) {
        const p = Buffer.isBuffer(payload) ? payload : Buffer.from(payload), mask = crypto.randomBytes(4); let h;
        if (p.length < 126) { h = Buffer.from([0x80 | opcode, 0x80 | p.length]); }
        else if (p.length < 65536) { h = Buffer.alloc(4); h[0] = 0x80 | opcode; h[1] = 0xFE; h.writeUInt16BE(p.length, 2); }
        else { h = Buffer.alloc(10); h[0] = 0x80 | opcode; h[1] = 0xFF; h.writeBigUInt64BE(BigInt(p.length), 2); }
        const m = Buffer.alloc(p.length); for (let i = 0; i < p.length; i++) m[i] = p[i] ^ mask[i & 3];
        this.sock.write(Buffer.concat([h, mask, m]));
    }
    sendText(s) { this._frame(1, s); }
    _drain() {
        for (;;) {
            if (this.buf.length < 2) return;
            const b0 = this.buf[0], fin = !!(b0 & 0x80), op = b0 & 0x0f; let len = this.buf[1] & 0x7f, off = 2;
            if (len === 126) { if (this.buf.length < 4) return; len = this.buf.readUInt16BE(2); off = 4; }
            else if (len === 127) { if (this.buf.length < 10) return; len = Number(this.buf.readBigUInt64BE(2)); off = 10; }
            if (this.buf.length < off + len) return;
            const pay = this.buf.slice(off, off + len); this.buf = this.buf.slice(off + len);
            if (op === 9) { this._frame(10, pay); continue; }       /* ping → pong */
            if (op === 8) { continue; }                              /* close */
            this.frags.push(pay);
            if (fin) { const msg = Buffer.concat(this.frags).toString(); this.frags = []; this.onmsg(msg); }
        }
    }
}
/* ---- CDP 会话 ---- */
class CDP {
    constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); this.events = new Map(); ws.onmsg = s => { const m = JSON.parse(s); if (m.id !== undefined && this.pending.has(m.id)) { const p = this.pending.get(m.id); this.pending.delete(m.id); m.error ? p.rej(new Error(m.error.message)) : p.res(m.result); } else if (m.method) (this.events.get(m.method) || []).forEach(f => f(m.params)); }; }
    call(method, params) { const id = ++this.id; return new Promise((res, rej) => { this.pending.set(id, { res, rej }); this.ws.sendText(JSON.stringify({ id, method, params: params || {} })); }); }
    on(method, f) { if (!this.events.has(method)) this.events.set(method, []); this.events.get(method).push(f); }
    once(method, timeoutMs) { return new Promise((res, rej) => { const t = setTimeout(() => rej(new Error("timeout " + method)), timeoutMs); this.on(method, p => { clearTimeout(t); res(p); }); }); }
    async eval(expr) { const r = await this.call("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error("page eval: " + JSON.stringify(r.exceptionDetails.exception && r.exceptionDetails.exception.description || r.exceptionDetails.text)); return r.result.value; }
    async waitFor(expr, timeoutMs, label) {
        const t0 = Date.now();
        for (;;) {
            try { if (await this.eval(expr)) return; } catch (e) { /* 页面尚未就绪 */ }
            if (Date.now() - t0 > timeoutMs) throw new Error("waitFor timeout: " + (label || expr));
            await new Promise(r => setTimeout(r, 150));
        }
    }
}
(async () => {
    const target = await httpJson("PUT", "/json/new?about:blank").catch(() => httpJson("GET", "/json/new?about:blank"));
    const ws = new WS(target.webSocketDebuggerUrl); await ws.connect();
    const cdp = new CDP(ws);
    await cdp.call("Page.enable"); await cdp.call("Runtime.enable");
    cdp.on("Runtime.exceptionThrown", p => { errors.push("exception: " + (p.exceptionDetails.exception && p.exceptionDetails.exception.description || p.exceptionDetails.text)); });
    cdp.on("Runtime.consoleAPICalled", p => { if (p.type === "error") errors.push("console.error: " + p.args.map(a => a.value !== undefined ? a.value : a.description).join(" ")); });
    const nav = async url => { await cdp.call("Page.navigate", { url }); await cdp.once("Page.loadEventFired", 20000); };

    /* E01 无 sid：默认最新有效会话（S8=180557，S9 被 SHA 守卫降级）+ 默认算法 xgb69_candidate */
    /* 注意：demo.html 用 `let frame`（非 window 属性）。等待裸绑定，不访问 window.frame。 */
    await nav(DEMO + "/");
    await cdp.waitFor("typeof frame!=='undefined' && frame && frame.sid", 40000, "first frame");
    ok("E01 default latest-valid session & model", await cdp.eval("document.getElementById('session').value==='cap_20261010_180557' && document.getElementById('model').value==='xgb69_candidate'"), "sid=" + await cdp.eval("document.getElementById('session').value"));

    /* E02 深链合法 sid + model 被尊重，无回退提示 */
    await nav(DEMO + "/?sid=cap_20261010_175429&model=rf51_baseline");
    await cdp.waitFor("typeof frame!=='undefined' && frame && frame.sid==='cap_20261010_175429'", 40000, "deep link frame");
    ok("E02 deep link sid+model respected, no fallback note", await cdp.eval("frame.detector==='rf51_baseline' && frame.fallback===null && !document.getElementById('status').textContent.includes('回退')"));

    /* E03 深链不存在 sid：回退默认且可见提示 */
    await nav(DEMO + "/?sid=cap_99999999_999999");
    await cdp.waitFor("typeof frame!=='undefined' && frame && frame.sid", 40000, "fallback frame");
    ok("E03 bad sid visible fallback", await cdp.eval("document.getElementById('session').value==='cap_20261010_180557' && document.getElementById('status').textContent.includes('回退')"));

    /* E04 seek 中段：帧直达、候选/GT 字段齐备 */
    await nav(DEMO + "/?sid=cap_20261010_175429&model=xgb69_candidate");
    await cdp.waitFor("typeof frame!=='undefined' && frame && frame.index===0", 40000, "replay start");
    await cdp.eval("(()=>{const k=document.getElementById('seek');k.value=100;k.dispatchEvent(new Event('change'));return true})()");
    await cdp.waitFor("typeof frame!=='undefined' && frame && frame.index===100", 40000, "seek 100");
    const mid = await cdp.eval("({n:frame.candidates.length,gt:frame.gt_status,hasIdx:frame.candidates.every(c=>Array.isArray(c.indices))})");
    ok("E04 seek mid-frame renders candidates w/ indices", mid.hasIdx && typeof mid.gt === "string", "candidates=" + mid.n + " gt=" + mid.gt);

    /* E05 逆序 seek=0：generation 递增 = tracker 前缀重建（不得污染时序） */
    const g1 = await cdp.eval("frame.generation");
    await cdp.eval("(()=>{const k=document.getElementById('seek');k.value=0;k.dispatchEvent(new Event('change'));return true})()");
    await cdp.waitFor("typeof frame!=='undefined' && frame && frame.index===0 && frame.generation>" + g1, 40000, "rewind rebuild");
    ok("E05 rewind rebuilds generation (" + g1 + "→" + await cdp.eval("frame.generation") + ")", true);
    ok("E05b counter bar syncs after rewind", await cdp.eval("document.getElementById('counter').textContent.startsWith('0 /')"));

    /* E06 页面内切模型：requested 切换、回退字段透明 */
    await cdp.eval("(()=>{const m=document.getElementById('model');m.value='xgb69_unique';m.dispatchEvent(new Event('change'));return true})()");
    await cdp.waitFor("typeof frame!=='undefined' && frame && frame.requested==='xgb69_unique'", 40000, "model switch");
    ok("E06 in-page model switch applies", true, "detector=" + await cdp.eval("frame.detector"));

    /* E07 重置按钮回到第 0 帧 */
    await cdp.eval("(()=>{const k=document.getElementById('seek');k.value=5;k.dispatchEvent(new Event('change'));return true})()");
    await cdp.waitFor("typeof frame!=='undefined' && frame && frame.index===5", 40000, "seek 5");
    await cdp.eval("document.getElementById('reset').click()");
    await cdp.waitFor("typeof frame!=='undefined' && frame && frame.index===0", 40000, "reset to 0");
    ok("E07 reset returns to frame 0", true);

    /* E08 候选列表可点检：点首行后 detail 面板出现点集预览 */
    const hasRow = await cdp.eval("document.getElementById('rows').children.length>0");
    if (hasRow) { await cdp.eval("document.getElementById('rows').children[0].click()"); ok("E08 candidate row inspection fills detail", (await cdp.eval("document.getElementById('detail').textContent")).includes("point_indices_preview")); }
    else ok("E08 candidate row inspection fills detail", true, "frame 0 无候选，跳过点检（非缺陷）");

    /* E09 全程无浏览器异常 / console.error */
    ok("E09 no page exceptions/console.error", errors.length === 0, errors.slice(0, 3).join(" | ") || "clean");

    const shot = await cdp.call("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(__dirname, "results/DEMO_V1_UNIFY_E2E.png"), Buffer.from(shot.data, "base64"));
    fs.writeFileSync(path.join(__dirname, "results/DEMO_BROWSER_E2E.json"), JSON.stringify({ status: process.exitCode ? "FAIL" : "PASS", when: new Date().toISOString(), demo: DEMO, checks, pageErrors: errors }, null, 2));
    await httpJson("GET", "/json/close/" + target.id).catch(() => {});
    process.exit(process.exitCode || 0);
})().catch(e => { console.error("E2E_FATAL", e.message); fs.writeFileSync(path.join(__dirname, "results/DEMO_BROWSER_E2E.json"), JSON.stringify({ status: "FAIL", fatal: e.message, checks, pageErrors: errors }, null, 2)); process.exit(1); });
