/* cdp_e2e.js — HUMAN-FUSION-UNIFY-R1 / STEP 4 真实浏览器端到端（无第三方库）。
 * 依赖：本机 Chrome 以 --remote-debugging-port 启动；demo server 已在 DEMO_PORT 运行。
 * 实现最小 RFC6455 客户端 + CDP 子集（Page/Runtime），驱动 demo.html 并采集异常。
 * 运行：node cdp_e2e.js [chromePort=9223] [demoPort=8798]   （exit 0 = 全绿）
 */
"use strict";
const http = require("http"), net = require("net"), crypto = require("crypto"), fs = require("fs"), path = require("path");
const CDP_PORT = Number(process.argv[2] || 9223), DEMO = "http://127.0.0.1:" + (process.argv[3] || 8798);
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

(async()=>{
 const dest=path.resolve(__dirname,'../../docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1');
 const targets=await httpJson('GET','/json/list');
 const target=targets.find(t=>t.type==='page'&&t.webSocketDebuggerUrl);if(!target)throw Error('No Chrome target');
 const ws=new WS(target.webSocketDebuggerUrl);await ws.connect();const cdp=new CDP(ws);
 await cdp.call('Page.enable');await cdp.call('Runtime.enable');
 cdp.on('Runtime.exceptionThrown',p=>errors.push(p.exceptionDetails.exception?.description||p.exceptionDetails.text));
 await cdp.call('Emulation.setDeviceMetricsOverride',{width:1600,height:1080,deviceScaleFactor:1,mobile:false});
 const show=async(sid,model,index)=>{await cdp.call('Page.navigate',{url:DEMO+'/?sid='+sid+'&model='+model+'&index='+index});await cdp.waitFor('typeof frame!=="undefined"&&frame&&frame.sid==="'+sid+'"&&frame.index==='+index+'&&!busy',60000,'frame '+index);};
 const tag=process.argv[4]||'02';
 const screen=async name=>{const r=await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(dest,name+'_'+tag+'.png'),Buffer.from(r.data,'base64'));};
 await show('cap_20261010_175429','xgb69_candidate',20);
 ok('nine real sessions',await cdp.eval("$('session').options.length===9"));
 ok('three synchronized canvases',await cdp.eval("['view','viewTop','viewSide'].every(id=>$(id).width>0&&$(id).height>0)"));
 ok('same candidate four finite scores',await cdp.eval('frame.candidates.length>0&&frame.candidates.every(c=>Object.keys(c.scores).length===4&&Object.values(c.scores).every(Number.isFinite))'));
 ok('uncalibrated banner',await cdp.eval("$('status').textContent.includes('UNCALIBRATED')"));
 await cdp.eval("$('proxy').checked=true;draw();inspect(frame.candidates[0]);$('focus').click();");await screen('SUCCESS_NEAR_F20');
 await cdp.eval("$('next').click()");await cdp.waitFor('frame.index===21&&!busy',30000);ok('single step',true);
 await cdp.eval("$('seek').value=5;$('seek').dispatchEvent(new Event('input'))");await cdp.waitFor('frame.index===5&&!busy',30000);ok('backwards seek',true);
 await cdp.eval("$('play').click()");await cdp.waitFor('frame.index>=7&&!busy',30000);await cdp.eval("$('play').click()");await new Promise(r=>setTimeout(r,300));const pause=await cdp.eval('index');await new Promise(r=>setTimeout(r,400));ok('pause does not advance',await cdp.eval('index')===pause);
 await cdp.eval("$('reset').click()");await cdp.waitFor('frame.index===0&&!busy',30000);ok('reset frame and track history',await cdp.eval('index===0&&selected===null&&history.size<=frame.tracks.length'));
 await cdp.eval("marked=frame.candidates[0].indices.slice(0,10);$('actor').value='P1';$('saveAnn').click()");
 ok('manual draft binds actual frame and raw indices',await cdp.eval("annotations.get(frame.sid+':'+frame.index)[0].raw_point_indices.length===10&&annotations.get(frame.sid+':'+frame.index)[0].session_sha256.points===frame.input_sha256.points"));
 await cdp.eval("$('clearAnn').click()");ok('undo draft',await cdp.eval('annotations.size===0'));
 await cdp.eval("$('fg').checked=true;$('raw').checked=false;draw()");await screen('FOREGROUND_F0');ok('foreground layer real indices',await cdp.eval('frame.foreground.length>0&&frame.foreground.every(i=>i>=0&&i<frame.n_points)'));
 await show('cap_20261010_175227','rf51_baseline',20);await cdp.eval('inspect(frame.candidates[0])');await screen('FURNITURE_RF51_F20');ok('furniture false positive localized',await cdp.eval("frame.events.includes('FURNITURE_FALSE_POSITIVE')"));
 await show('cap_20261010_180751','xgb69_candidate',0);await screen('S9_UNKNOWN_F0');ok('S9 never treats placeholder SHA as trusted',await cdp.eval("frame.gt_status==='UNKNOWN'&&frame.gt.length===0"));
 const cases=JSON.parse(fs.readFileSync(path.join(dest,'CASES.json')));const miss=cases.find(c=>c.kind==='PERSON_MISS'&&c.model==='xgb69_candidate');if(miss){await show(miss.sid,miss.model,miss.index);await cdp.eval("$('focus').click()");await screen('PERSON_MISS_F'+miss.index);ok('actual missed person screenshot',await cdp.eval("frame.events.includes('PERSON_MISS')"));}
 const sessions=await cdp.eval("Array.from($('session').options).map(o=>({sid:o.value,label:o.textContent}))");
 for(const s of sessions){await cdp.eval("$('session').value='"+s.sid+"';change()");await cdp.waitFor('frame.sid==="'+s.sid+'"&&frame.index===0&&!busy',60000,'session switch');ok('real session switch '+s.sid,await cdp.eval('cloud.length===frame.n_points*4'));await screen('SESSION_'+s.sid+'_F0');}
 await show('cap_20261010_175429','xgb69_candidate',20);
 ok('no runtime exceptions',errors.length===0,JSON.stringify(errors));
 fs.writeFileSync(path.join(dest,'BROWSER_CHECK_'+tag+'.json'),JSON.stringify({checks,errors,status:checks.every(c=>c.pass)?'PASS':'FAIL',url:DEMO},null,2));ws.sock.end();
 if(checks.some(c=>!c.pass))process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
