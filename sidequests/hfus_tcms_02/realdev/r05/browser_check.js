'use strict';
// S4 real-browser check: band colouring, per-frame decomposition, tail reasons, point lookup.
// Bounded: one deterministic display index per frame (no pixel-search loop) plus real mouse events.
const fs = require('fs');
const http = require('http');
const path = require('path');
const PAGE_URL = process.argv[2];
const OUT = process.argv[3];
const CDP = process.argv[4] || 'http://127.0.0.1:9224';
const FRAMES = [0, 270, 271, 765, 779];
const sleep = ms => new Promise(r => setTimeout(r, ms));

function json(p, method = 'GET') {
  return new Promise((res, rej) => {
    const u = new URL(CDP + p);
    const req = http.request({ hostname: u.hostname, port: u.port, path: u.pathname + u.search, method }, r => {
      let b = ''; r.on('data', d => b += d);
      r.on('end', () => { try { res(JSON.parse(b)); } catch (e) { rej(new Error(b.slice(0, 300))); } });
    });
    req.on('error', rej); req.end();
  });
}
class C {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.p = new Map();
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.id && this.p.has(m.id)) { const { res, rej } = this.p.get(m.id); this.p.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
    };
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((res, rej) => { this.p.set(id, { res, rej }); this.ws.send(JSON.stringify({ id, method, params })); });
  }
  async eval(e) {
    const r = await this.send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error('EVAL ' + JSON.stringify(r.exceptionDetails).slice(0, 400));
    return r.result.value;
  }
}

(async () => {
  const version = await json('/json/version');
  let target = null;
  for (let i = 0; i < 60; i++) {
    try { target = await json('/json/new?' + encodeURIComponent(PAGE_URL), 'PUT'); if (target && target.webSocketDebuggerUrl) break; } catch (e) {}
    await sleep(250);
  }
  if (!target) throw new Error('no CDP target');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  const c = new C(ws);
  await c.send('Page.enable'); await c.send('Runtime.enable');
  await c.send('Emulation.setDeviceMetricsOverride', { width: 1500, height: 1150, deviceScaleFactor: 1, mobile: false });
  await c.send('Page.navigate', { url: PAGE_URL });
  let ready = false;
  for (let i = 0; i < 120; i++) { await sleep(250); ready = await c.eval('!!(window.__s4 && window.__s4.state.data)').catch(() => false); if (ready) break; }
  if (!ready) throw new Error('page not ready');
  const out = {
    item: 'HFUS-TCMS-02-REALDEV-02-S04', url: PAGE_URL,
    browser: { version: version.Browser, protocol_version: version['Protocol-Version'], user_agent: version['User-Agent'],
               source: 'CDP /json/version' },
    input_method: 'CDP Input.dispatchMouseEvent inside the real browser; not a physical mouse',
    frames: []
  };
  out.meta = await c.eval("({tail:__s4.meta.tail, tail_zero:__s4.meta.tail_zero, m0:__s4.meta.m0, transform:__s4.meta.transform_id, contact:__s4.meta.contact.rule})");
  out.tail_panel = await c.eval("document.getElementById('tail').textContent");
  const click = async (x, y) => {
    await c.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
    await c.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
    await sleep(450);
  };
  for (const fi of FRAMES) {
    await c.eval('__s4.loadFrame(' + fi + ')');
    await sleep(300);
    const size = await c.eval("(()=>{const ca=document.getElementById('p3');return {n:__s4.state.data.raw.length/3,w:ca.clientWidth,h:ca.clientHeight}})()");
    const idx = Math.min(size.n - 1, Math.max(0, Math.floor(size.n / 2)));
    const s = await c.eval(`__s4.screenOf(${idx}, 'p3')`);
    const box = await c.eval("(()=>{const b=document.getElementById('p3').getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height}})()");
    const px = box.x + Math.min(box.w - 3, Math.max(3, s.x));
    const py = box.y + Math.min(box.h - 3, Math.max(3, s.y));
    const before = await c.eval('__s4.snapshot()');
    await click(px, py);
    const pointInfo = await c.eval("document.getElementById('point').textContent");
    let point = null;
    try { point = JSON.parse(pointInfo); } catch (e) { point = { parse_error: pointInfo.slice(0, 120) }; }
    // real click on a CONTACT-band point through the deterministic API, then verify the band label
    const contactIdx = await c.eval('__s4.firstBand(1)');
    const contactPoint = contactIdx >= 0 ? await c.eval(`__s4.selectPoint(${contactIdx})`) : null;
    const stateText = await c.eval("document.getElementById('state').textContent");
    await c.eval("(()=>{const e=document.getElementById('camera'); e.value='top'; e.dispatchEvent(new Event('change')); return 1;})()");
    await sleep(250);
    const after = await c.eval('__s4.snapshot()');
    await c.eval("(()=>{const e=document.getElementById('camera'); e.value='oblique'; e.dispatchEvent(new Event('change')); return 1;})()");
    const shot = await c.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(OUT, 's4_browser_f' + fi + '.png'), Buffer.from(shot.data, 'base64'));
    out.frames.push({
      fi, state: await c.eval('__s4.state.data.state'),
      rows: await c.eval('__s4.state.data.rows'),
      decomp: await c.eval('__s4.state.data.record.decomp'),
      bands: await c.eval('__s4.state.data.record.bands'),
      candidates: await c.eval('__s4.state.data.record.candidates'),
      real_click: { at: [px, py], element_from_point: await c.eval(`(()=>{const e=document.elementFromPoint(${px},${py});return e?e.tagName:'none'})()`),
                    selected_index: await c.eval('__s4.state.sel') },
      point, contact_point: contactPoint, state_panel: stateText,
      camera_invariant: before === after
    });
  }
  await c.eval('__s4.loadFrame(0)');
  await sleep(300);
  const btn = await c.eval("(()=>{const b=document.getElementById('pickbad').getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2}})()");
  await click(btn.x, btn.y);
  const inv = await c.eval("document.getElementById('point').textContent");
  try { out.invalid_row = JSON.parse(inv); } catch (e) { out.invalid_row = { parse_error: inv.slice(0, 160) }; }
  const hexOk = p => p && typeof p.raw28_hex === 'string' && p.raw28_hex.length === 56;
  out.summary = {
    browser_version_embedded: out.browser.version === version.Browser,
    frames: out.frames.map(f => f.fi),
    all_points_56_hex: out.frames.every(f => hexOk(f.point)),
    all_contact_points_56_hex: out.frames.every(f => hexOk(f.contact_point)),
    contact_band_labelled: out.frames.every(f => f.contact_point && f.contact_point.band === 'CONTACT'),
    decomp_present: out.frames.every(f => f.decomp && 'watertight' in f.decomp),
    real_click_delivered: out.frames.every(f => f.real_click.element_from_point === 'CANVAS'),
    camera_invariant_all: out.frames.every(f => f.camera_invariant),
    invalid_row_query_ok: !!(out.invalid_row && out.invalid_row.raw28_hex && out.invalid_row.raw28_hex.length === 56 && out.invalid_row.valid === false),
    tail_zero_visible: Array.isArray(out.meta.tail_zero) && out.meta.tail_zero.length > 0,
    states: out.frames.map(f => [f.fi, f.state])
  };
  fs.writeFileSync(path.join(OUT, 'BROWSER_RESULTS.json'), JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out.summary));
  ws.close();
  process.exit(0);
})().catch(e => { console.error('FAIL', e.stack || e.message); process.exit(1); });
