'use strict';
const fs = require('fs');
const http = require('http');
const path = require('path');

const PAGE_URL = process.argv[2];
const OUT = process.argv[3];
const CDP = process.argv[4] || 'http://127.0.0.1:9223';
const sleep = ms => new Promise(r => setTimeout(r, ms));

function json(port, p, method = 'GET') {
  return new Promise((res, rej) => {
    const u = new URL(CDP + p);
    const req = http.request({ hostname: u.hostname, port: u.port, path: u.pathname + u.search, method }, r => {
      let b = ''; r.on('data', d => b += d); r.on('end', () => { try { res(JSON.parse(b)); } catch (e) { rej(new Error(b.slice(0, 300))); } });
    });
    req.on('error', rej); req.end();
  });
}

class CDPClient {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map(); this.events = [];
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.id && this.pending.has(m.id)) {
        const { res, rej } = this.pending.get(m.id); this.pending.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      } else if (m.method) this.events.push(m);
    };
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((res, rej) => { this.pending.set(id, { res, rej }); this.ws.send(JSON.stringify({ id, method, params })); });
  }
  async eval(expression, awaitPromise = true) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise });
    if (r.exceptionDetails) throw new Error('EVAL: ' + JSON.stringify(r.exceptionDetails).slice(0, 500));
    return r.result.value;
  }
}

async function connect() {
  let target = null;
  for (let i = 0; i < 40; i++) {
    try { target = await json(0, '/json/new?' + encodeURIComponent(PAGE_URL), 'PUT'); if (target && target.webSocketDebuggerUrl) break; } catch (e) {}
    await sleep(250);
  }
  if (!target || !target.webSocketDebuggerUrl) throw new Error('no CDP target');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  return new CDPClient(ws);
}

async function main() {
  const c = await connect();
  await c.send('Page.enable');
  await c.send('Runtime.enable');
  await c.send('Emulation.setDeviceMetricsOverride', { width: 1400, height: 1000, deviceScaleFactor: 1, mobile: false });
  await c.send('Page.navigate', { url: PAGE_URL });
  for (let i = 0; i < 80; i++) {
    await sleep(250);
    const ok = await c.eval('!!(window.__s2 && window.__s2.state && window.__s2.state.data)').catch(() => false);
    if (ok) break;
  }
  const results = { url: PAGE_URL, frames: [], errors: [] };
  const shot = async name => {
    const r = await c.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(OUT, name), Buffer.from(r.data, 'base64'));
  };
  const pointInfo = () => c.eval("document.getElementById('point').textContent");
  const binInfo = () => c.eval("document.getElementById('bin').textContent");
  const click = async (sel, x, y) => {
    const r = await c.eval(`(()=>{const b=document.getElementById('${sel}').getBoundingClientRect();return {x:b.x,y:b.y}})()`);
    const px = r.x + x, py = r.y + y;
    await c.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: px, y: py, button: 'left', clickCount: 1 });
    await c.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: px, y: py, button: 'left', clickCount: 1 });
  };
  for (const fi of [0, 100, 192, 193, 230, 270]) {
    await c.eval('__s2.loadFrame(' + fi + ')');
    await sleep(300);
    const info = await c.eval("({fi:__s2.state.fi, nrows:__s2.state.data.nrows, valid:__s2.state.data.valid, shown:__s2.state.data.raw.length/3, candidate:__s2.meta.best.id})");
    // real click on a point inside a patch (prefer patch point)
    const idx = await c.eval("(()=>{const p=__s2.state.data.patch; for(let i=0;i<p.length;i++) if(p[i]) return i; return 0;})()");
    const s = await c.eval('__s2.screenOf(' + idx + ')');
    await click('p3', Math.min(s.w - 2, Math.max(2, s.x)), Math.min(s.h - 2, Math.max(2, s.y)));
    await sleep(500);
    const pi = await pointInfo();
    let pt = null; try { pt = JSON.parse(pi); } catch (e) {}
    // real click on distance image bin
    const fb = await (await fetch(new URL(PAGE_URL).origin + '/api/firstbin?fi=' + fi)).json();
    const bp = await c.eval('__s2.binPixel(' + fb.ia + ',' + fb.ie + ')');
    results.frames_bin = results.frames_bin || []; results.frames_bin.push({ fi, bin: fb });
    await click('img', Math.min(bp.w - 2, Math.max(2, bp.x)), Math.min(bp.h - 2, Math.max(2, bp.y)));
    await sleep(500);
    const bi = await binInfo();
    let bn = null; try { bn = JSON.parse(bi); } catch (e) {}
    // camera switch must not change coordinates
    const before = await c.eval('JSON.stringify([__s2.state.data.local.slice(0,12), Array.from(__s2.state.data.rowsArr.slice(0,4))])');
    await c.eval("(()=>{const e=document.getElementById('camera'); e.value='top'; e.dispatchEvent(new Event('change')); return 1;})()");
    await sleep(200);
    const after = await c.eval('JSON.stringify([__s2.state.data.local.slice(0,12), Array.from(__s2.state.data.rowsArr.slice(0,4))])');
    await shot('browser_f' + fi + '.png');
    results.frames.push({ fi, info, point: pt, bin: bn, camera_invariant: before === after, point_index: idx });
  }
  results.ui_errors = await c.eval("window.__s2 ? 'ok' : 'missing'");
  fs.writeFileSync(path.join(OUT, 'BROWSER_RESULTS.json'), JSON.stringify(results, null, 2));
  console.log(JSON.stringify({ ok: true, frames: results.frames.map(f => ({ fi: f.fi, point_ok: !!(f.point && f.point.raw28_hex && f.point.raw28_hex.length === 56), bin_ok: !!(f.bin && f.bin.count >= 0), cam: f.camera_invariant })) }));
  c.ws.close();
}
main().catch(e => { console.error('FAIL', e.stack || e.message); process.exit(1); });
