'use strict';
const http = require('http');
const PAGE = process.argv[2];
const CDP = process.argv[3] || 'http://127.0.0.1:9224';
const sleep = ms => new Promise(r => setTimeout(r, ms));
function json(p, method = 'GET') {
  return new Promise((res, rej) => {
    const u = new URL(CDP + p);
    const req = http.request({ hostname: u.hostname, port: u.port, path: u.pathname + u.search, method }, r => {
      let b = ''; r.on('data', d => b += d);
      r.on('end', () => { try { res(JSON.parse(b)); } catch (e) { rej(new Error(b.slice(0, 200))); } });
    });
    req.on('error', rej); req.end();
  });
}
(async () => {
  const t = await json('/json/new?' + encodeURIComponent(PAGE), 'PUT');
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0; const pend = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
  const send = (method, params = {}) => new Promise(res => { const i = ++id; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  const ev = async e => { const m = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true }); const r = m.result; if (r && r.exceptionDetails) console.log('EVAL_ERR', JSON.stringify(r.exceptionDetails).slice(0, 200)); return r ? r.result.value : undefined; };
  await send('Page.enable'); await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1500, height: 1100, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: PAGE });
  for (let i = 0; i < 120; i++) { await sleep(300); if (await ev('!!(window.__s3 && window.__s3.state.data)')) break; }
  await ev('__s3.loadFrame(271)'); await sleep(400);
  for (const i of [0, 100, 1000, 5000]) {
    console.log('screenOf praw', i, JSON.stringify(await ev(`__s3.screenOf('praw', ${i})`)));
    console.log('screenOf ploc', i, JSON.stringify(await ev(`__s3.screenOf('ploc', ${i})`)));
  }
  const rect = await ev("(()=>{const c=document.getElementById('ploc');const r=c.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,scrollY:window.scrollY,dpr:window.devicePixelRatio}})()");
  console.log('rect', JSON.stringify(rect));
  const s = await ev("__s3.screenOf('ploc', 1000)");
  const px = rect.x + Math.max(3, Math.min(rect.w - 3, s.x));
  const py = rect.y + Math.max(3, Math.min(rect.h - 3, s.y));
  console.log('click at', px, py, 'for s', JSON.stringify(s));
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: px, y: py });
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: px, y: py, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: px, y: py, button: 'left', clickCount: 1 });
  await sleep(600);
  console.log('sel', await ev('__s3.state.sel'));
  console.log('text', JSON.stringify((await ev("document.getElementById('point').textContent")).slice(0, 100)));
  console.log('elementFromPoint', await ev(`(()=>{const e=document.elementFromPoint(${px},${py});return e?e.tagName+'#'+e.id:'none'})()`));
  ws.close(); process.exit(0);
})().catch(e => { console.error('FAIL', e.stack || e.message); process.exit(1); });
