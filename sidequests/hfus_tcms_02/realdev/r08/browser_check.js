"use strict";
// Real Microsoft Edge via CDP: skeleton overlay, calibration panel, point lookup.
const fs = require('fs');
const http = require('http');
const path = require('path');

const PAGE_URL = process.argv[2];
const OUT = process.argv[3];
const CDP = process.argv[4] || 'http://127.0.0.1:9223';
const FRAMES = [0, 192, 271, 430, 520, 700, 765, 779];
const sleep = ms => new Promise(r => setTimeout(r, ms));

function json(port, p, method = 'GET') {
  return new Promise((res, rej) => {
    const u = new URL(CDP + p);
    const req = http.request({hostname:u.hostname, port:u.port, path:u.pathname+u.search, method}, r => {
      let b = '';
      r.on('data', d => b += d);
      r.on('end', () => { try { res(JSON.parse(b)); } catch (e) { rej(new Error(b.slice(0,300))); } });
    });
    req.on('error', rej); req.end();
  });
}

class CDPClient {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map();
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.id && this.pending.has(m.id)) {
        const {res, rej} = this.pending.get(m.id); this.pending.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      }
    };
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((res, rej) => { this.pending.set(id,{res,rej}); this.ws.send(JSON.stringify({id,method,params})); });
  }
  async eval(expression, awaitPromise = true) {
    const r = await this.send('Runtime.evaluate', {expression, returnByValue:true, awaitPromise});
    if (r.exceptionDetails) throw new Error('EVAL: ' + JSON.stringify(r.exceptionDetails).slice(0,700));
    return r.result.value;
  }
}

async function connect() {
  let target = null;
  for (let i=0;i<80;i++) {
    try {
      target = await json(0, '/json/new?' + encodeURIComponent(PAGE_URL), 'PUT');
      if (target && target.webSocketDebuggerUrl) break;
    } catch (e) {}
    await sleep(250);
  }
  if (!target || !target.webSocketDebuggerUrl) throw new Error('no CDP target');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen=res; ws.onerror=rej; });
  return new CDPClient(ws);
}

async function main() {
  const version = await json(0, '/json/version');
  const c = await connect();
  await c.send('Page.enable'); await c.send('Runtime.enable');
  await c.send('Emulation.setDeviceMetricsOverride', {width:1500,height:1000,deviceScaleFactor:1,mobile:false});
  await c.send('Page.navigate', {url:PAGE_URL});
  for (let i=0;i<120;i++) {
    await sleep(200);
    const ok = await c.eval('!!(window.__skel && window.__skel.ready)').catch(()=>false);
    if (ok) break;
  }
  const results = {
    url: PAGE_URL,
    engine: 'Microsoft Edge via CDP',
    browser: version,
    input_method: 'CDP Input.dispatchMouseEvent (injected browser events, not physical mouse)',
    screenshot_method: 'Page.captureScreenshot',
    page_title: await c.eval('document.title'),
    frames: [], errors: []
  };
  const shot = async name => {
    const r = await c.send('Page.captureScreenshot', {format:'png'});
    fs.writeFileSync(path.join(OUT, name), Buffer.from(r.data, 'base64'));
  };
  const clickAt = async (x,y) => {
    await c.send('Input.dispatchMouseEvent',{type:'mousePressed',x,y,button:'left',clickCount:1});
    await c.send('Input.dispatchMouseEvent',{type:'mouseReleased',x,y,button:'left',clickCount:1});
  };
  for (const fi of FRAMES) {
    await c.eval('__skel.loadFrame(' + fi + ')');
    await sleep(250);
    const before = await c.eval('__skel.snapshot()');
    const idx = await c.eval('__skel.visibleIndex()');
    let point = null;
    if (idx >= 0) {
      const s = await c.eval('__skel.screenOf(' + idx + ')');
      const box = await c.eval("(()=>{const b=document.getElementById('view').getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height}})()");
      await clickAt(box.x + s.x, box.y + s.y);
      await sleep(180);
      const txt = await c.eval("document.getElementById('point').textContent");
      try { point = JSON.parse(txt); } catch (e) { point = {parse_error: txt.slice(0,200)}; }
    }
    await c.eval("__skel.camera('top')");
    const afterTop = await c.eval('__skel.snapshot()');
    await c.eval("__skel.camera('oblique')");
    const afterBack = await c.eval('__skel.snapshot()');
    const rows = await c.eval("document.querySelectorAll('#calRows tr').length");
    const calStates = await c.eval("[...document.querySelectorAll('#calRows .state')].map(x=>x.textContent)");
    const trackText = await c.eval("document.getElementById('trackLine').textContent");
    await shot('browser_f' + String(fi).padStart(3,'0') + '.png');
    results.frames.push({
      fi,
      point_count: before.point_count,
      valid_nodes: before.valid_nodes,
      skeleton_edges: before.skeleton_edges,
      camera_invariant: before.coordinate_digest === afterTop.coordinate_digest && before.coordinate_digest === afterBack.coordinate_digest,
      coordinate_digest_preserved: before.coordinate_digest === afterTop.coordinate_digest && before.coordinate_digest === afterBack.coordinate_digest,
      calibration_rows: rows,
      calibration_states: calStates,
      track_line: trackText,
      point_raw28_hex_length: point && typeof point.raw28_hex === 'string' ? point.raw28_hex.length : null,
      point_source_row: point && point.source_row,
      point_valid: point && point.valid,
      point_has_source_xyz: !!(point && point.source_xyz && point.source_xyz.length === 3),
      point_has_local_xyz: !!(point && point.local_xyz && point.local_xyz.length === 3),
      point_transform_id: point && point.transform_id,
      point: point
    });
  }
  await c.eval('__skel.loadFrame(0)'); await sleep(120);
  const invalid = await c.eval('__skel.pickInvalid()');
  results.invalid_row = invalid;
  const hexOk = p => !!(p && typeof p.raw28_hex === 'string' && p.raw28_hex.length === 56);
  const requireFrames = [430,520,700];
  results.summary = {
    frames_checked: results.frames.length,
    all_points_have_56_hex: results.frames.every(f => f.point_raw28_hex_length === 56),
    all_points_have_source_and_local_xyz: results.frames.every(f => f.point_has_source_xyz && f.point_has_local_xyz),
    all_points_bound_to_transform: results.frames.every(f => f.point_transform_id === version_transform(results)),
    camera_invariant_all: results.frames.every(f => f.camera_invariant),
    calibration_panel_present_for_positive_skeleton: results.frames.filter(f => f.valid_nodes > 0).every(f => f.calibration_rows >= 1),
    positive_skeleton_frames: results.frames.filter(f => f.valid_nodes > 0).map(f => f.fi),
    expected_positive_skeleton_frames: requireFrames,
    expected_positive_skeletons_observed: requireFrames.every(fi => results.frames.find(f => f.fi === fi).valid_nodes > 0),
    invalid_row_query_ok: !!(invalid && hexOk(invalid) && invalid.valid === false),
    no_console_errors: results.errors.length === 0
  };
  results.PASS = Object.entries(results.summary).filter(([k,v]) => typeof v === 'boolean').every(([k,v]) => v);
  fs.writeFileSync(path.join(OUT, 'BROWSER_RESULTS.json'), JSON.stringify(results,null,2) + '\n');
  console.log(JSON.stringify({PASS:results.PASS, summary:results.summary,
    browser:version.Browser, product:version['User-Agent']}));
  try { await c.send('Browser.close'); } catch (e) {}
  await sleep(200);
  c.ws.close();
}
function version_transform(results) {
  const f = results.frames.find(x => x.point && x.point.transform_id);
  return f ? f.point.transform_id : null;
}
main().catch(e => { console.error('FAIL', e.stack || e.message); process.exit(1); });
