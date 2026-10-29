'use strict';
// Probe: why did fi=271 pick a different row in the two panes? Real mouse events, same page.
const fs = require('fs');
const http = require('http');
const PAGE_URL = process.argv[2];
const OUT = process.argv[3];
const CDP = process.argv[4] || 'http://127.0.0.1:9223';
const sleep = ms => new Promise(r => setTimeout(r, ms));

function json(p, method = 'GET') {
  return new Promise((res, rej) => {
    const u = new URL(CDP + p);
    const req = http.request({ hostname: u.hostname, port: u.port, path: u.pathname + u.search, method }, r => {
      let b = '';
      r.on('data', d => b += d);
      r.on('end', () => { try { res(JSON.parse(b)); } catch (e) { rej(new Error(b.slice(0, 200))); } });
    });
    req.on('error', rej);
    req.end();
  });
}
class C {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map();
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.id && this.pending.has(m.id)) {
        const { res, rej } = this.pending.get(m.id); this.pending.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      }
    };
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((res, rej) => { this.pending.set(id, { res, rej }); this.ws.send(JSON.stringify({ id, method, params })); });
  }
  async eval(e) {
    const r = await this.send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error('EVAL ' + JSON.stringify(r.exceptionDetails).slice(0, 400));
    return r.result.value;
  }
}
(async () => {
  const t = await json('/json/new?' + encodeURIComponent(PAGE_URL), 'PUT');
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  const c = new C(ws);
  await c.send('Page.enable'); await c.send('Runtime.enable');
  await c.send('Emulation.setDeviceMetricsOverride', { width: 1500, height: 1100, deviceScaleFactor: 1, mobile: false });
  await c.send('Page.navigate', { url: PAGE_URL });
  for (let i = 0; i < 80; i++) { await sleep(250); if (await c.eval('!!(window.__s3 && __s3.state.data)').catch(() => false)) break; }
  const out = [];
  for (const fi of [271]) {
    await c.eval('__s3.loadFrame(' + fi + ')'); await sleep(400);
    const idx = await c.eval('__s3.pickIndex(8)');
    const sa = await c.eval(`__s3.screenOf('praw', ${idx})`);
    const sb = await c.eval(`__s3.screenOf('ploc', ${idx})`);
    const rows = await c.eval(`[__s3.state.data.rowsArr[${idx}], __s3.state.data.rowsArr.length]`);
    const click = async (canvas, s) => {
      const box = await c.eval(`(()=>{const b=document.getElementById('${canvas}').getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height}})()`);
      const px = box.x + Math.min(s.w - 3, Math.max(3, s.x));
      const py = box.y + Math.min(s.h - 3, Math.max(3, s.y));
      await c.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: px, y: py, button: 'left', clickCount: 1 });
      await c.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: px, y: py, button: 'left', clickCount: 1 });
      await sleep(450);
      const sel = await c.eval('__s3.state.sel');
      const txt = await c.eval("document.getElementById('point').textContent");
      let info = null; try { info = JSON.parse(txt); } catch (e) {}
      return { box, px, py, sel, row: info && info.source_row, idx_in_array: sel };
    };
    const a = await click('praw', sa);
    const b = await click('ploc', sb);
    out.push({ fi, idx, expected_row: rows[0], shown: rows[1], screen_raw: sa, screen_loc: sb, raw: a, loc: b });
  }
  fs.writeFileSync(OUT + '\\diag_pick.json', JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out));
  ws.close();
})().catch(e => { console.error('FAIL', e.stack || e.message); process.exit(1); });
