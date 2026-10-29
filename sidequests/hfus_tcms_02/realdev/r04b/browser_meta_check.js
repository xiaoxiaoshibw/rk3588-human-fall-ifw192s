'use strict';
// S3 r2 D1 closure: bounded browser re-check. It embeds the real browser identity from CDP
// /json/version and re-verifies the point lookup on three frames. The full 13-frame functional
// proof stays in the sealed r1 BROWSER_RESULTS.json; this file must not be read as a replacement.
const fs = require('fs');
const http = require('http');
const path = require('path');

const PAGE_URL = process.argv[2];
const OUT = process.argv[3];
const CDP = process.argv[4] || 'http://127.0.0.1:9224';
const FRAMES = [0, 271, 779];
const sleep = ms => new Promise(r => setTimeout(r, ms));

function json(p, method = 'GET') {
  return new Promise((res, rej) => {
    const u = new URL(CDP + p);
    const req = http.request({ hostname: u.hostname, port: u.port, path: u.pathname + u.search, method }, r => {
      let b = '';
      r.on('data', d => b += d);
      r.on('end', () => { try { res(JSON.parse(b)); } catch (e) { rej(new Error(b.slice(0, 300))); } });
    });
    req.on('error', rej);
    req.end();
  });
}

class CDPClient {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map();
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.id && this.pending.has(m.id)) {
        const { res, rej } = this.pending.get(m.id);
        this.pending.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      }
    };
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((res, rej) => { this.pending.set(id, { res, rej }); this.ws.send(JSON.stringify({ id, method, params })); });
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error('EVAL: ' + JSON.stringify(r.exceptionDetails).slice(0, 500));
    return r.result.value;
  }
  race(promise, ms, label) {
    return Promise.race([promise, new Promise((_, rej) => setTimeout(() => rej(new Error('TIMEOUT ' + label)), ms))]);
  }
}

const CHEAP_PICK = `(() => {
  const ca = document.getElementById('praw'), cb = document.getElementById('ploc');
  return { aw: ca.clientWidth, ah: ca.clientHeight, bw: cb.clientWidth, bh: cb.clientHeight,
           n: window.__s3.state.data.raw.length / 3 };
})()`;

async function main() {
  const version = await json('/json/version');
  let target = null;
  for (let i = 0; i < 60; i++) {
    try { target = await json('/json/new?' + encodeURIComponent(PAGE_URL), 'PUT'); if (target && target.webSocketDebuggerUrl) break; } catch (e) {}
    await sleep(250);
  }
  if (!target) throw new Error('no CDP target');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  const c = new CDPClient(ws);
  await c.send('Page.enable');
  await c.send('Runtime.enable');
  await c.send('Emulation.setDeviceMetricsOverride', { width: 1500, height: 1100, deviceScaleFactor: 1, mobile: false });
  await c.send('Page.navigate', { url: PAGE_URL });
  let ready = false;
  for (let i = 0; i < 100; i++) { await sleep(250); ready = await c.eval('!!(window.__s3 && window.__s3.state.data)').catch(() => false); if (ready) break; }
  if (!ready) throw new Error('page did not become ready');
  const out = {
    purpose: 'close review finding D1 (embed the real browser identity and the input method)',
    scope_note: 'three-frame confirmation only; the sealed r1 BROWSER_RESULTS.json remains the 13-frame functional proof',
    url: PAGE_URL,
    page_title: await c.eval('document.title'),
    browser: { version: version.Browser, protocol_version: version['Protocol-Version'],
               user_agent: version['User-Agent'], v8: version['V8-Version'],
               source: 'CDP /json/version of this browser instance' },
    input_method: 'CDP Input.dispatchMouseEvent mousePressed/mouseReleased inside the real browser; not a physical mouse',
    frames: []
  };
  for (const fi of FRAMES) {
    await c.race(c.eval('__s3.loadFrame(' + fi + ')'), 60000, 'loadFrame ' + fi);
    await sleep(300);
    // Deterministic point lookup: same display index in both panes, so both panes must return the
    // same source row. Pixel-quantised mouse picking is proven in the sealed r1 run; here one real
    // canvas click is still dispatched and recorded only as event-delivery evidence.
    const size = await c.eval(CHEAP_PICK);
    const idx = Math.min(size.n - 1, Math.max(0, Math.floor(size.n / 2)));
    const s = await c.eval(`__s3.screenOf('praw', ${idx})`);
    const box = await c.eval("(()=>{const b=document.getElementById('praw').getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height}})()");
    const px = box.x + Math.min(box.w - 3, Math.max(3, s.x));
    const py = box.y + Math.min(box.h - 3, Math.max(3, s.y));
    await c.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: px, y: py, button: 'left', clickCount: 1 });
    await c.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: px, y: py, button: 'left', clickCount: 1 });
    await sleep(450);
    const real_click = {
      at: [px, py], expected_index: idx,
      element_from_point: await c.eval(`(()=>{const e=document.elementFromPoint(${px},${py});return e?e.tagName:'none'})()`),
      selected_index_after_click: await c.eval('__s3.state.sel')
    };
    const rawPick = await c.eval(`__s3.selectPoint(${idx})`);
    const before = await c.eval('__s3.snapshot()');
    await c.eval("(()=>{const e=document.getElementById('camera'); e.value='top'; e.dispatchEvent(new Event('change')); return 1;})()");
    await sleep(250);
    const after = await c.eval('__s3.snapshot()');
    await c.eval("(()=>{const e=document.getElementById('camera'); e.value='oblique'; e.dispatchEvent(new Event('change')); return 1;})()");
    const shot = await c.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(OUT, 'browser_r2_f' + fi + '.png'), Buffer.from(shot.data, 'base64'));
    const row_for_index = await c.eval(`__s3.state.data.rowsArr[${idx}]`);
    out.frames.push({ fi, online_state: await c.eval('__s3.state.data.state'),
                      rows: await c.eval('__s3.state.data.rows'),
                      real_canvas_click: real_click,
                      display_index: idx, expected_row: row_for_index,
                      point: rawPick,
                      point_row_matches_index: !!(rawPick && rawPick.source_row === row_for_index),
                      camera_invariant: before === after });
  }
  await c.eval('__s3.loadFrame(0)');
  await sleep(300);
  const btn = await c.eval("(()=>{const b=document.getElementById('pickbad').getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2}})()");
  await c.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: btn.x, y: btn.y, button: 'left', clickCount: 1 });
  await c.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: btn.x, y: btn.y, button: 'left', clickCount: 1 });
  await sleep(500);
  const inv = await c.eval("document.getElementById('point').textContent");
  try { out.invalid_row = JSON.parse(inv); } catch (e) { out.invalid_row = { parse_error: inv.slice(0, 160) }; }
  const hexOk = p => p && typeof p.raw28_hex === 'string' && p.raw28_hex.length === 56;
  out.summary = {
    browser_version_embedded: !!version.Browser && out.browser.version === version.Browser,
    frames_checked: out.frames.length,
    all_points_56_hex: out.frames.every(f => hexOk(f.point)),
    all_points_valid: out.frames.every(f => f.point && f.point.valid === true),
    point_rows_match_display_index: out.frames.every(f => f.point_row_matches_index),
    coordinate_differs_raw_vs_levelled: out.frames.every(f => f.point &&
      JSON.stringify(f.point.raw_xyz) !== JSON.stringify(f.point.local_xyz)),
    real_canvas_click_delivered: out.frames.every(f => f.real_canvas_click.element_from_point === 'CANVAS'),
    camera_invariant_all: out.frames.every(f => f.camera_invariant),
    invalid_row_query_ok: !!(out.invalid_row && out.invalid_row.raw28_hex && out.invalid_row.raw28_hex.length === 56 && out.invalid_row.valid === false),
    states: out.frames.map(f => [f.fi, f.online_state])
  };
  fs.writeFileSync(path.join(OUT, 'BROWSER_RESULTS_R2.json'), JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out.summary));
  c.ws.close();
  process.exit(0);
}

main().catch(e => { console.error('FAIL', e.stack || e.message); process.exit(1); });
