'use strict';
// Debug: why did the r2 bounded click miss? Prints screenOf/box/click and the returned text.
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
  const v = await json('/json/version');
  const t = await json('/json/new?' + encodeURIComponent(PAGE), 'PUT');
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0; const pend = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
  const send = (method, params = {}) => new Promise(res => { const i = ++id; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  const ev = async e => { const m = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true }); const r = m.result; if (r && r.exceptionDetails) console.log('EVAL_ERR', JSON.stringify(r.exceptionDetails).slice(0,300)); return r ? r.result.value : undefined; };
  await send('Page.enable'); await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1500, height: 1100, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: PAGE });
  for (let i = 0; i < 160; i++) { await sleep(300); const ok = await ev('!!(window.__s3 && window.__s3.state && window.__s3.state.data)'); if (i%20===0) console.log('ready?',i,ok); if (ok) break; }
  await ev('__s3.loadFrame(271)'); await sleep(400);
  const size = await ev("(()=>{const a=document.getElementById('praw'),b=document.getElementById('ploc');return {aw:a.clientWidth,ah:a.clientHeight,bw:b.clientWidth,bh:b.clientHeight,n:__s3.state.data.raw.length/3,rows:__s3.state.data.rows,scrollY:window.scrollY}})()");
  console.log('size', JSON.stringify(size));
  const step = Math.max(1, Math.floor(size.n / 120));
  let idx = -1, best = 1e18, sa = null, sb = null;
  for (let i = 0; i < size.n; i += step) {
    const a = await ev(`__s3.screenOf('praw', ${i})`);
    const b = await ev(`__s3.screenOf('ploc', ${i})`);
    if (a[0] < 10 || a[0] > size.aw - 10 || a[1] < 10 || a[1] > size.ah - 10) continue;
    if (b[0] < 10 || b[0] > size.bw - 10 || b[1] < 10 || b[1] > size.bh - 10) continue;
    const d = (a[0] - size.aw / 2) ** 2 + (a[1] - size.ah / 2) ** 2;
    if (d < best) { best = d; idx = i; sa = a; sb = b; }
  }
  console.log('idx', idx, 'praw', JSON.stringify(sa), 'ploc', JSON.stringify(sb));
  const boxes = await ev("(()=>{const a=document.getElementById('praw').getBoundingClientRect(),b=document.getElementById('ploc').getBoundingClientRect();return {a:{x:a.x,y:a.y,w:a.width,h:a.height},b:{x:b.x,y:b.y,w:b.width,h:b.height}}})()");
  console.log('boxes', JSON.stringify(boxes));
  const click = async (x, y) => {
    await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
    await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
    await sleep(400);
  };
  await click(boxes.a.x + sa[0], boxes.a.y + sa[1]);
  console.log('after raw click sel=', await ev('__s3.state.sel'), 'text=', JSON.stringify((await ev("document.getElementById('point').textContent")).slice(0, 120)));
  await click(boxes.b.x + sb[0], boxes.b.y + sb[1]);
  console.log('after loc click sel=', await ev('__s3.state.sel'), 'text=', JSON.stringify((await ev("document.getElementById('point').textContent")).slice(0, 120)));
  console.log('nearest check', await ev("(()=>{const a=document.getElementById('praw').getBoundingClientRect();return 1})()"));
  ws.close(); process.exit(0);
})().catch(e => { console.error('FAIL', e.stack || e.message); process.exit(1); });
