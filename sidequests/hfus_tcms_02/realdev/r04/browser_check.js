'use strict';
// Real Edge (CDP) check: same-frame RAW/levelled views, z=0 grid, state causality, point lookup.
const fs = require('fs');
const http = require('http');
const path = require('path');

const PAGE_URL = process.argv[2];
const OUT = process.argv[3];
const CDP = process.argv[4] || 'http://127.0.0.1:9223';
const FRAMES = [0, 192, 193, 270, 271, 272, 300, 430, 439, 520, 750, 770, 779];
const sleep = ms => new Promise(r => setTimeout(r, ms));

function json(port, p, method = 'GET') {
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
  async eval(expression, awaitPromise = true) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise });
    if (r.exceptionDetails) throw new Error('EVAL: ' + JSON.stringify(r.exceptionDetails).slice(0, 600));
    return r.result.value;
  }
}

async function connect() {
  let target = null;
  for (let i = 0; i < 60; i++) {
    try {
      target = await json(0, '/json/new?' + encodeURIComponent(PAGE_URL), 'PUT');
      if (target && target.webSocketDebuggerUrl) break;
    } catch (e) {}
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
  await c.send('Emulation.setDeviceMetricsOverride', { width: 1500, height: 1100, deviceScaleFactor: 1, mobile: false });
  await c.send('Page.navigate', { url: PAGE_URL });
  for (let i = 0; i < 100; i++) {
    await sleep(250);
    const ok = await c.eval('!!(window.__s3 && window.__s3.state && window.__s3.state.data)').catch(() => false);
    if (ok) break;
  }
  const results = { url: PAGE_URL, engine: 'Microsoft Edge via CDP', frames: [], errors: [] };
  const shot = async name => {
    const r = await c.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(OUT, name), Buffer.from(r.data, 'base64'));
  };
  const clickAt = async (x, y) => {
    await c.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
    await c.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
  };
  const clickCanvas = async (which, idx) => {
    const s = await c.eval(`__s3.screenOf('${which}', ${idx})`);
    const box = await c.eval(`(()=>{const b=document.getElementById('${which}').getBoundingClientRect();
      return {x:b.x,y:b.y,w:b.width,h:b.height}})()`);
    const px = box.x + Math.min(s.w - 3, Math.max(3, s.x));
    const py = box.y + Math.min(s.h - 3, Math.max(3, s.y));
    await clickAt(px, py);
    await sleep(400);
    const txt = await c.eval("document.getElementById('point').textContent");
    try { return JSON.parse(txt); } catch (e) { return { parse_error: txt.slice(0, 200) }; }
  };
  results.meta = await c.eval("({state:__s3.meta.state, from:__s3.meta.state_from_fi, transform:__s3.meta.transform.coordinate_version, artifact:__s3.meta.transform.artifact_sha, m0:__s3.meta.m0.map_id, available_after:__s3.meta.m0.available_after_fi, temporal:__s3.meta.verification.temporal_pass, spatial:__s3.meta.verification.spatial_pass, prefix:__s3.meta.verification.prefix_pass, qualification:__s3.meta.qualification, failure:__s3.meta.failure})");
  results.state_line = await c.eval("document.getElementById('stateLine').textContent");
  results.transform_line = await c.eval("document.getElementById('transformLine').textContent");
  results.verification_text = await c.eval("document.getElementById('cand').textContent");
  for (const fi of FRAMES) {
    await c.eval('__s3.loadFrame(' + fi + ')');
    await sleep(300);
    const patchIdx = await c.eval('__s3.pickIndex(8)');
    const before = await c.eval('__s3.snapshot()');
    const praw = await clickCanvas('praw', patchIdx);
    const ploc = await clickCanvas('ploc', patchIdx);
    const stateTxt = await c.eval("document.getElementById('state').textContent");
    await c.eval("(()=>{const e=document.getElementById('camera'); e.value='top'; e.dispatchEvent(new Event('change')); return 1;})()");
    await sleep(250);
    const afterTop = await c.eval('__s3.snapshot()');
    await c.eval("(()=>{const e=document.getElementById('camera'); e.value='oblique'; e.dispatchEvent(new Event('change')); return 1;})()");
    await sleep(250);
    const afterBack = await c.eval('__s3.snapshot()');
    await shot('browser_f' + fi + '.png');
    results.frames.push({
      fi, state_text: stateTxt,
      online_state: await c.eval('__s3.state.data.state'),
      qualified: await c.eval('__s3.state.data.record.qualified'),
      map_exists: await c.eval('__s3.state.data.record.m0_exists'),
      raw_rows: await c.eval('__s3.state.data.rows'),
      raw_view_points: await c.eval('__s3.state.data.raw.length/3'),
      levelled_view_points: await c.eval('__s3.state.data.local.length/3'),
      point_raw_pane: praw, point_levelled_pane: ploc,
      camera_invariant: before === afterTop && before === afterBack,
      patch_index: patchIdx
    });
  }
  await c.eval('__s3.loadFrame(0)');
  await sleep(300);
  const btn = await c.eval("(()=>{const b=document.getElementById('pickbad').getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2}})()");
  await clickAt(btn.x, btn.y);
  await sleep(500);
  const invTxt = await c.eval("document.getElementById('point').textContent");
  try { results.invalid_row = JSON.parse(invTxt); } catch (e) { results.invalid_row = { parse_error: invTxt.slice(0, 200) }; }
  results.ui_errors = await c.eval("window.__s3 ? 'ok' : 'missing'");
  const hexOk = p => p && typeof p.raw28_hex === 'string' && p.raw28_hex.length === 56;
  results.summary = {
    frames_checked: results.frames.length,
    all_56_hex_raw_pane: results.frames.every(f => hexOk(f.point_raw_pane)),
    all_56_hex_levelled_pane: results.frames.every(f => hexOk(f.point_levelled_pane)),
    same_source_row_between_panes: results.frames.every(f => f.point_raw_pane.source_row === f.point_levelled_pane.source_row),
    coordinate_differs_raw_vs_levelled: results.frames.every(f =>
      JSON.stringify(f.point_raw_pane.raw_xyz) !== JSON.stringify(f.point_levelled_pane.local_xyz)),
    camera_invariant_all: results.frames.every(f => f.camera_invariant),
    states: results.frames.map(f => [f.fi, f.online_state]),
    invalid_row_query_ok: !!(results.invalid_row && results.invalid_row.raw28_hex && results.invalid_row.raw28_hex.length === 56 && results.invalid_row.valid === false)
  };
  fs.writeFileSync(path.join(OUT, 'BROWSER_RESULTS.json'), JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results.summary));
  c.ws.close();
}

main().catch(e => { console.error('FAIL', e.stack || e.message); process.exit(1); });
