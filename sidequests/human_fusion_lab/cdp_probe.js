/* cdp_probe.js — 定位 headless 导航/求值卡点的最小探针。 */
"use strict";
const http = require("http"), net = require("net"), crypto = require("crypto");
const CDP_PORT = Number(process.argv[2] || 9223), DEMO = "http://127.0.0.1:" + (process.argv[3] || 8797);
function httpJson(method, p) { return new Promise((res, rej) => { const r = http.request({ host: "127.0.0.1", port: CDP_PORT, path: p, method }, x => { let d = ""; x.on("data", c => d += c); x.on("end", () => { try { res(JSON.parse(d)); } catch (e) { rej(new Error(d.slice(0, 200))); } }); }); r.on("error", rej); r.end(); }); }
function frameHead(op, plen, mask) { const h = Buffer.from([0x80 | op, 0x80 | (plen < 126 ? plen : 126)]); return h; }
class WS { constructor(u) { const m = /^ws:\/\/([^:/]+):(\d+)(\/.*)$/.exec(u); this.host = m[1]; this.port = +m[2]; this.path = m[3]; this.buf = Buffer.alloc(0); this.frag = []; this.onmsg = () => { }; } connect() { return new Promise((res, rej) => { const key = crypto.randomBytes(16).toString("base64"); this.sock = net.connect(this.port, this.host, () => this.sock.write("GET " + this.path + " HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: " + key + "\r\nSec-WebSocket-Version: 13\r\n\r\n")); let sh = false, acc = Buffer.alloc(0); this.sock.on("data", c => { acc = Buffer.concat([acc, c]); if (!sh) { const i = acc.indexOf("\r\n\r\n"); if (i < 0) return; const hd = acc.slice(0, i).toString(); if (!/^HTTP\/1\.1 101/.test(hd)) return rej(new Error(hd.split("\r\n")[0])); sh = true; this.buf = acc.slice(i + 4); this._d(); res(); } else { this.buf = Buffer.concat([this.buf, c]); this._d(); } }); this.sock.on("error", rej); }); } _d() { for (;;) { if (this.buf.length < 2) return; const b = this.buf[0], fin = !!(b & 0x80), op = b & 15; let l = this.buf[1] & 127, o = 2; if (l === 126) { if (this.buf.length < 4) return; l = this.buf.readUInt16BE(2); o = 4; } if (this.buf.length < o + l) return; const p = this.buf.slice(o, o + l); this.buf = this.buf.slice(o + l); if (op === 9) { this.sock.write(frameHead(10, p.length), () => {}); } else if (op === 8) continue; else { this.frag.push(p); if (fin) { this.onmsg(Buffer.concat(this.frag).toString()); this.frag = []; } } } } send(s) { const p = Buffer.from(s), mk = crypto.randomBytes(4); let h; if (p.length < 126) { h = Buffer.from([0x81, 0x80 | p.length]); } else if (p.length < 65536) { h = Buffer.alloc(4); h[0] = 0x81; h[1] = 0xFE; h.writeUInt16BE(p.length, 2); } else { h = Buffer.alloc(10); h[0] = 0x81; h[1] = 0xFF; h.writeBigUInt64BE(BigInt(p.length), 2); } const m = Buffer.alloc(p.length); for (let i = 0; i < p.length; i++) m[i] = p[i] ^ mk[i & 3]; this.sock.write(Buffer.concat([h, mk, m])); } }
(async () => {
    const t = await httpJson("PUT", "/json/new?about:blank");
    const ws = new WS(t.webSocketDebuggerUrl); await ws.connect();
    let id = 0; const pend = new Map(); ws.onmsg = s => { const m = JSON.parse(s); if (m.id && pend.has(m.id)) { const p = pend.get(m.id); pend.delete(m.id); p(m); } };
    const call = (method, params) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
    await call("Runtime.enable", {}); await call("Page.enable", {});
    console.log("[probe] navigate→", DEMO + "/");
    const nav = await call("Page.navigate", { url: DEMO + "/" });
    console.log("[probe] navigate ret", JSON.stringify(nav.result || nav.error || nav));
    for (let k = 0; k < 12; k++) {
        await new Promise(r => setTimeout(r, 1500));
        const ev = await call("Runtime.evaluate", { expression: "JSON.stringify({rs:document.readyState,hasFrame:typeof frame,frameSet:(typeof frame!=='undefined'&&!!frame),sid:(typeof frame!=='undefined'&&frame?frame.sid:null),status:document.getElementById('status')?document.getElementById('status').textContent.slice(0,60):null})", returnByValue: true });
        console.log("[probe]", k, JSON.stringify(ev.result && ev.result.value));
        if (ev.result && ev.result.value && JSON.parse(ev.result.value).frameSet) break;
    }
    await httpJson("GET", "/json/close/" + t.id).catch(() => {});
    process.exit(0);
})().catch(e => { console.error("PROBE_FATAL", e.message); process.exit(1); });
