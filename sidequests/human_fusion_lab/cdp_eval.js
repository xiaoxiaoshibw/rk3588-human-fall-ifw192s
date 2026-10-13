/* cdp_eval.js — 对已存在 target 求值的最小可复用探针（规避 Chrome154 /json/new=500）。
 * 用法：node cdp_eval.js <cdpPort> <targetUrlSubstr> <jsExpr> [loops] [intervalMs]
 */
"use strict";
const http = require("http"), net = require("net"), crypto = require("crypto");
const CDP = +process.argv[2], SUB = process.argv[3], EXPR = process.argv[4];
const LOOPS = +(process.argv[5] || 1), GAP = +(process.argv[6] || 1000);
function httpJson(m, p) { return new Promise((res, rej) => { const r = http.request({ host: "127.0.0.1", port: CDP, path: p, method: m }, x => { let d = ""; x.on("data", c => d += c); x.on("end", () => { try { res(JSON.parse(d)); } catch (e) { rej(new Error(d.slice(0, 300))); } }); }); r.on("error", rej); r.end(); }); }
class WS { constructor(u) { const m = /^ws:\/\/([^:/]+):(\d+)(\/.*)$/.exec(u); this.host = m[1]; this.port = +m[2]; this.path = m[3]; this.buf = Buffer.alloc(0); this.frag = []; this.onmsg = () => { }; } connect() { return new Promise((res, rej) => { const key = crypto.randomBytes(16).toString("base64"); this.sock = net.connect(this.port, this.host, () => this.sock.write("GET " + this.path + " HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: " + key + "\r\nSec-WebSocket-Version: 13\r\n\r\n")); let sh = false, acc = Buffer.alloc(0); this.sock.on("data", c => { acc = Buffer.concat([acc, c]); if (!sh) { const i = acc.indexOf("\r\n\r\n"); if (i < 0) return; if (!/^HTTP\/1\.1 101/.test(acc.slice(0, i).toString())) return rej(new Error(acc.slice(0, i).toString().split("\r\n")[0])); sh = true; this.buf = acc.slice(i + 4); this._d(); res(); } else { this.buf = Buffer.concat([this.buf, c]); this._d(); } }); this.sock.on("error", rej); }); } _d() { for (;;) { if (this.buf.length < 2) return; const b = this.buf[0], fin = !!(b & 0x80), op = b & 15; let l = this.buf[1] & 127, o = 2; if (l === 126) { if (this.buf.length < 4) return; l = this.buf.readUInt16BE(2); o = 4; } if (this.buf.length < o + l) return; const p = this.buf.slice(o, o + l); this.buf = this.buf.slice(o + l); if (op === 9) { const mk = crypto.randomBytes(4), pp = Buffer.alloc(p.length), h = Buffer.from([0x8A, 0x80 | p.length]); for (let i = 0; i < p.length; i++)pp[i] = p[i] ^ mk[i & 3]; this.sock.write(Buffer.concat([h, mk, pp])); } else if (op === 8) continue; else { this.frag.push(p); if (fin) { this.onmsg(Buffer.concat(this.frag).toString()); this.frag = []; } } } } send(s) { const p = Buffer.from(s), mk = crypto.randomBytes(4); let h; if (p.length < 126) h = Buffer.from([0x81, 0x80 | p.length]); else if (p.length < 65536) { h = Buffer.alloc(4); h[0] = 0x81; h[1] = 0xFE; h.writeUInt16BE(p.length, 2); } else { h = Buffer.alloc(10); h[0] = 0x81; h[1] = 0xFF; h.writeBigUInt64BE(BigInt(p.length), 2); } const m = Buffer.alloc(p.length); for (let i = 0; i < p.length; i++)m[i] = p[i] ^ mk[i & 3]; this.sock.write(Buffer.concat([h, mk, m])); } }
(async () => {
    const list = await httpJson("GET", "/json/list");
    const t = list.find(x => x.type === "page" && x.url.includes(SUB) && x.webSocketDebuggerUrl);
    if (!t) { console.error("NO_TARGET " + SUB + " :: " + list.map(x => x.url).join(" | ")); process.exit(2); }
    console.log("TARGET " + t.url);
    const ws = new WS(t.webSocketDebuggerUrl); await ws.connect();
    let id = 0; const pend = new Map(); const evs = [];
    ws.onmsg = s => { const m = JSON.parse(s); if (m.id && pend.has(m.id)) { const p = pend.get(m.id); pend.delete(m.id); p(m); } else if (m.method && (m.method === "Runtime.exceptionThrown" || (m.method === "Runtime.consoleAPICalled" && m.params.type === "error"))) { if (m.method === "Runtime.exceptionThrown") evs.push("EXC " + (m.params.exceptionDetails.exception && m.params.exceptionDetails.exception.description || m.params.exceptionDetails.text)); else evs.push("CERR " + m.params.args.map(a => a.value !== undefined ? a.value : a.description).join(",")); } };
    const call = (method, params) => new Promise((res, rej) => { const i = ++id; pend.set(i, r => r.error ? rej(new Error(r.error.message)) : res(r.result)); ws.send(JSON.stringify({ id: i, method, params })); });
    await call("Runtime.enable", {});
    for (let k = 0; k < LOOPS; k++) {
        if (k) await new Promise(r => setTimeout(r, GAP));
        try { const r = await call("Runtime.evaluate", { expression: EXPR, returnByValue: true, awaitPromise: true }); console.log("EVAL[" + k + "]", JSON.stringify(r.value !== undefined ? r.value : r)); }
        catch (e) { console.log("EVAL[" + k + "] ERR", e.message); }
    }
    console.log("PAGE_ERRORS", JSON.stringify(evs));
    process.exit(0);
})().catch(e => { console.error("FATAL", e.message); process.exit(1); });
