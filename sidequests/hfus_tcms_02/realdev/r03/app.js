'use strict';
const S = { meta: null, fi: 0, data: null, sel: -1, selBin: null, camera: 'oblique', zoom: 70, showOld: false, showCand: true };
const $ = id => document.getElementById(id);
const b64f32 = s => new Float32Array(Uint8Array.from(atob(s), c => c.charCodeAt(0)).buffer);
const b64i32 = s => new Int32Array(Uint8Array.from(atob(s), c => c.charCodeAt(0)).buffer);
const b64u8 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));

async function get(url) { const r = await fetch(url); const j = await r.json(); if (j.error) throw new Error(j.message); return j; }

function planeLocal(n, R, t) {
  const nl = [R[0][0]*n[0]+R[0][1]*n[1]+R[0][2]*n[2], R[1][0]*n[0]+R[1][1]*n[1]+R[1][2]*n[2], R[2][0]*n[0]+R[2][1]*n[1]+R[2][2]*n[2]];
  const dl = n[0]*0 + 0; // placeholder replaced below
  return { n: nl, d: 0 };
}
function planeLocalExact(n, R, t, d) {
  const nl = [R[0][0]*n[0]+R[0][1]*n[1]+R[0][2]*n[2], R[1][0]*n[0]+R[1][1]*n[1]+R[1][2]*n[2], R[2][0]*n[0]+R[2][1]*n[1]+R[2][2]*n[2]];
  const dl = d - (nl[0]*t[0] + nl[1]*t[1] + nl[2]*t[2]);
  return { n: nl, d: dl };
}

function cameraBasis() {
  const yaw = S.camera === 'side' ? 0 : S.camera === 'front' ? Math.PI/2 : -0.9;
  const pitch = S.camera === 'top' ? Math.PI/2 : S.camera === 'oblique' ? 0.85 : 0;
  return { yaw, pitch };
}
function project(u, v, h, scale, cx, cy) {
  const { yaw, pitch } = cameraBasis();
  const cyaw = Math.cos(yaw), syaw = Math.sin(yaw);
  let x = u*cyaw - v*syaw, y = u*syaw + v*cyaw, z = h;
  const cp = Math.cos(pitch), sp = Math.sin(pitch);
  let y2 = y*cp - z*sp, z2 = y*sp + z*cp;
  return [cx + x*scale, cy - z2*scale, y2];
}

function fitScale(pts) {
  let minx = 1e9, maxx = -1e9, miny = 1e9, maxy = -1e9;
  const { yaw, pitch } = cameraBasis();
  const cyaw = Math.cos(yaw), syaw = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  for (let i = 0; i < pts.length; i += 3) {
    const u = pts[i], v = pts[i+1], h = pts[i+2];
    if (u < 0.5 || u > 2.4 || v < -0.2 || v > 2.2 || h < -1 || h > 2) continue;
    const x = u*cyaw - v*syaw, y = u*syaw + v*cyaw;
    const y2 = y*cp - h*sp, z2 = y*sp + h*cp;
    if (x < minx) minx = x; if (x > maxx) maxx = x;
    if (z2 < miny) miny = z2; if (z2 > maxy) maxy = z2;
  }
  const w = Math.max(maxx-minx, 0.5), hh = Math.max(maxy-miny, 0.5);
  return { scale: Math.min(900/w, 700/hh) * (S.zoom/70), cx0: (minx+maxx)/2, cy0: (miny+maxy)/2 };
}

function draw3D() {
  const c = $('p3'), ctx = c.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const W = c.clientWidth, H = c.clientHeight;
  c.width = W*dpr; c.height = H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.fillStyle = '#080d13'; ctx.fillRect(0,0,W,H);
  if (!S.data) return;
  const loc = S.data.local, n = loc.length/3;
  const v = fitScale(loc), scale = v.scale, cx = W/2 - v.cx0*scale, cy = H/2 + 30 - v.cy0*scale;
  const cols = ['#6b7c8f','#4fc3f7','#ffb74d','#ba68c8','#81c784','#e57373','#fff176'];
  // h=0 grid over audit region
  const g0 = 0.0;
  ctx.strokeStyle = '#2c4a63'; ctx.lineWidth = 0.6;
  for (let u = 0.5; u <= 2.2; u += 0.4) {
    const a = project(u, 0.05, g0, scale, cx, cy), b = project(u, 1.95, g0, scale, cx, cy);
    ctx.beginPath(); ctx.moveTo(a[0],a[1]); ctx.lineTo(b[0],b[1]); ctx.stroke();
  }
  for (let v = 0.05; v <= 1.95; v += 0.4) {
    const a = project(0.5, v, g0, scale, cx, cy), b = project(2.2, v, g0, scale, cx, cy);
    ctx.beginPath(); ctx.moveTo(a[0],a[1]); ctx.lineTo(b[0],b[1]); ctx.stroke();
  }
  // candidate / old plane wireframe
  const planes = [];
  if (S.showCand && S.meta.best) planes.push({ p: planeLocalExact(S.meta.best.n, S.meta.R, S.meta.t, S.meta.best.d), color: '#ff9800' });
  if (S.showOld && S.meta.old) planes.push({ p: planeLocalExact(S.meta.old.n, S.meta.R, S.meta.t, S.meta.old.d), color: '#26c6da' });
  for (const pl of planes) {
    const p = pl.p, nz = p.n[2];
    if (Math.abs(nz) < 0.2) continue;
    ctx.strokeStyle = pl.color; ctx.lineWidth = 1.1;
    for (let u = 0.5; u <= 2.2; u += 0.4) {
      const v0 = 0.05, v1 = 1.95;
      const h0 = -(p.n[0]*u + p.n[1]*v0 + p.d)/nz, h1 = -(p.n[0]*u + p.n[1]*v1 + p.d)/nz;
      const a = project(u, v0, h0, scale, cx, cy), b = project(u, v1, h1, scale, cx, cy);
      ctx.beginPath(); ctx.moveTo(a[0],a[1]); ctx.lineTo(b[0],b[1]); ctx.stroke();
    }
    for (let v = 0.05; v <= 1.95; v += 0.4) {
      const u0 = 0.5, u1 = 2.2;
      const h0 = -(p.n[0]*u0 + p.n[1]*v + p.d)/nz, h1 = -(p.n[0]*u1 + p.n[1]*v + p.d)/nz;
      const a = project(u0, v, h0, scale, cx, cy), b = project(u1, v, h1, scale, cx, cy);
      ctx.beginPath(); ctx.moveTo(a[0],a[1]); ctx.lineTo(b[0],b[1]); ctx.stroke();
    }
  }
  // patch rectangles
  for (let i = 0; i < S.data.patches.length; i++) {
    const r = S.data.patches[i].rect_uv;
    ctx.strokeStyle = cols[(i+1)%cols.length]; ctx.lineWidth = 1.4;
    const pts = [[r[0],r[2]],[r[1],r[2]],[r[1],r[3]],[r[0],r[3]]];
    ctx.beginPath();
    pts.forEach((q,k) => { const a = project(q[0], q[1], 0, scale, cx, cy); k ? ctx.lineTo(a[0],a[1]) : ctx.moveTo(a[0],a[1]); });
    ctx.closePath(); ctx.stroke();
  }
  // points
  for (let i = 0; i < n; i++) {
    const u = loc[3*i], v = loc[3*i+1], h = loc[3*i+2];
    const a = project(u, v, h, scale, cx, cy);
    if (a[0] < -20 || a[0] > W+20 || a[1] < -20 || a[1] > H+20) continue;
    const pid = S.data.patch[i];
    ctx.fillStyle = i === S.sel ? '#66ff99' : (pid ? cols[pid % cols.length] : '#5b6b7c');
    ctx.globalAlpha = i === S.sel ? 1 : (pid ? 0.85 : 0.35);
    ctx.fillRect(a[0]-1.2, a[1]-1.2, i === S.sel ? 4.5 : 2.4, i === S.sel ? 4.5 : 2.4);
  }
  ctx.globalAlpha = 1;
  ctx.fillStyle = '#cfe0ef'; ctx.font = '12px ui-monospace';
  ctx.fillText('h=0 网格（历史候选系）', 10, 18);
  ctx.fillText('橙色：候选平面  ' + (S.meta.best ? S.meta.best.id : '-'), 10, 34);
  if (S.showOld) ctx.fillText('青色：旧TLS平面', 10, 50);
}

function drawImage() {
  const c = $('img'), ctx = c.getContext('2d');
  const W = c.clientWidth, H = c.clientHeight;
  c.width = W; c.height = H;
  ctx.fillStyle = '#05080c'; ctx.fillRect(0,0,W,H);
  if (!S.data || !S.data.pic) return;
  const img = b64f32(S.data.pic.nearest), w = 512, h = 256;
  const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
  const cx2 = cv.getContext('2d'); const im = cx2.createImageData(w, h);
  let mn = 0.4, mx = 12;
  for (let i = 0; i < w*h; i++) {
    const r = img[i];
    let rr, gg, bb;
    if (!isFinite(r)) { rr = 12; gg = 16; bb = 22; }
    else {
      const t = Math.min(1, Math.max(0, (r-mn)/(mx-mn)));
      rr = 30 + 225*t; gg = 40 + 140*(1-Math.abs(t-0.5)*2); bb = 120 - 90*t;
    }
    im.data[4*i] = rr; im.data[4*i+1] = gg; im.data[4*i+2] = bb; im.data[4*i+3] = 255;
  }
  cx2.putImageData(im, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(cv, 0, 0, W, H);
  if (S.selBin) {
    const [ia, ie] = S.selBin;
    ctx.strokeStyle = '#66ff99'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc((ia+0.5)/1024*W, (511.5-ie)/512*H, 6, 0, 6.29); ctx.stroke();
  }
}

function renderCand() {
  const m = S.meta, b = m.best, o = m.old;
  const fmt = p => p ? [p.patch, p.count, p.rms_m.toFixed(4), p.support_rate.toFixed(3)].join('  ') : '';
  let s = 'candidate: ' + b.id + '  [' + b.status + ']\n';
  s += 'n=' + b.n.map(x=>x.toFixed(6)).join(', ') + '  d=' + b.d.toFixed(6) + ' m\n';
  s += 'FIT patches:\n' + b.fit_patch.map(fmt).join('\n') + '\n';
  s += 'VAL patches:\n' + b.val_patch.map(fmt).join('\n') + '\n';
  if (o) {
    s += '\nold TLS: fit ' + o.fit_pass + '/4, val ' + o.val_pass + '/3, n=' + o.n.map(x=>x.toFixed(5)).join(',') + ' d=' + o.d.toFixed(5) + '\n';
    s += o.val_patch.map(fmt).join('\n');
  }
  s += '\nstate=CANDIDATE_PLANE_PREVIEW / OFFLINE_REVIEW; ground identity NOT_CONFIRMED';
  $('cand').textContent = s;
}

async function loadFrame(fi) {
  $('status').textContent = '加载帧 ' + fi + ' …';
  S.data = await get('/api/frame?fi=' + fi);
  S.data.pic.nearest = S.data.pic.nearest;
  S.data.raw = b64f32(S.data.raw); S.data.local = b64f32(S.data.local);
  S.data.patches = S.meta.patches;
  S.data.nrows = S.data.rows; S.data.rowsArr = b64i32(S.data.rows_b64); S.data.patch = b64u8(S.data.patch);
  S.fi = fi; S.sel = -1; S.selBin = null;
  $('fi').value = fi;
  const n = S.data.raw.length/3;
  $('status').textContent = '帧 ' + fi + '  t=' + S.data.time_s.toFixed(3) + 's  显示 ' + n + ' 点 / 本帧 ' + S.data.nrows + ' 行（显示抽样，计算与分母不抽样）';
  draw3D(); drawImage();
}

function nearestPoint(mx, my) {
  const c = $('p3'); const rc = c.getBoundingClientRect(); const W = rc.width, H = rc.height;
  const loc = S.data.local, n = loc.length/3;
  const v = fitScale(loc), scale = v.scale, cx = W/2 - v.cx0*scale, cy = H/2 + 30 - v.cy0*scale;
  let best = -1, bd = 1e9;
  for (let i = 0; i < n; i++) {
    const a = project(loc[3*i], loc[3*i+1], loc[3*i+2], scale, cx, cy);
    const d = (a[0]-mx)**2 + (a[1]-my)**2;
    if (d < bd) { bd = d; best = i; }
  }
  return bd <= 100 ? best : -1;
}

async function selectPoint(i) {
  const row = S.data.rowsArr[i];
  S.sel = i;
  const p = await get('/api/point?fi=' + S.fi + '&row=' + row);
  $('point').textContent = JSON.stringify(p, null, 1);
  const raw = [S.data.raw[3*i], S.data.raw[3*i+1], S.data.raw[3*i+2]];
  const az = Math.atan2(raw[1], raw[0]), el = Math.atan2(raw[2], Math.hypot(raw[0], raw[1]));
  S.selBin = [Math.min(1023, Math.floor((az+Math.PI)/(2*Math.PI)*1024)), Math.min(511, Math.floor((el+Math.PI/2)/Math.PI*512))];
  draw3D(); drawImage();
  return p;
}

async function selectBin(ia, ie) {
  S.selBin = [ia, ie];
  const b = await get('/api/bin?fi=' + S.fi + '&ia=' + ia + '&ie=' + ie);
  $('bin').textContent = JSON.stringify(b, null, 1);
  const raw = S.data.raw, n = raw.length/3;
  let hit = -1;
  for (let i = 0; i < n; i++) {
    const az = Math.atan2(raw[3*i+1], raw[3*i]), el = Math.atan2(raw[3*i+2], Math.hypot(raw[3*i], raw[3*i+1]));
    const a = Math.min(1023, Math.floor((az+Math.PI)/(2*Math.PI)*1024));
    const e = Math.min(511, Math.floor((el+Math.PI/2)/Math.PI*512));
    if (a === ia && e === ie) { hit = i; break; }
  }
  if (hit >= 0) S.sel = hit; else S.sel = -1;
  draw3D(); drawImage();
  return b;
}

async function boot() {
  S.meta = await get('/api/meta');
  $('cand').textContent = 'loading';
  renderCand();
  const q = new URLSearchParams(location.search);
  const fi = q.has('fi') ? parseInt(q.get('fi')) : 0;
  await loadFrame(fi);
  const screenOf = i => {
    const loc = S.data.local, c = $('p3'), rc = c.getBoundingClientRect();
    const v = fitScale(loc), scale = v.scale;
    const cx = rc.width/2 - v.cx0*scale, cy = rc.height/2 + 30 - v.cy0*scale;
    const a = project(loc[3*i], loc[3*i+1], loc[3*i+2], scale, cx, cy);
    return { x: a[0], y: a[1], w: rc.width, h: rc.height };
  };
  const binPixel = (ia, ie) => {
    const c = $('img'), r = c.getBoundingClientRect();
    return { x: (ia+0.5)/1024*r.width, y: (1-(ie+0.5)/512)*r.height, w: r.width, h: r.height };
  };
  const firstBin = () => {
    const a = b64f32(S.data.pic.nearest);
    for (let i = 0; i < a.length; i++) if (isFinite(a[i])) {
      const x = i % 512, y = Math.floor(i / 512);
      return [x * 2, (255 - y) * 2];
    }
    return [512, 256];
  };
  window.__s2 = { state: S, loadFrame, selectPoint, selectBin, screenOf, binPixel, firstBin,
    setCamera: m => { S.camera = m; draw3D(); }, meta: S.meta };
}

$('load').onclick = () => loadFrame(Math.max(0, Math.min(779, parseInt($('fi').value)||0)));
$('prev').onclick = () => loadFrame(Math.max(0, S.fi-1));
$('next').onclick = () => loadFrame(Math.min(779, S.fi+1));
$('camera').onchange = e => { S.camera = e.target.value; draw3D(); };
$('zoom').oninput = e => { S.zoom = +e.target.value; draw3D(); };
$('showOld').onchange = e => { S.showOld = e.target.checked; draw3D(); };
$('showCand').onchange = e => { S.showCand = e.target.checked; draw3D(); };
$('p3').onclick = e => {
  if (!S.data) return;
  const r = e.target.getBoundingClientRect();
  const i = nearestPoint(e.clientX - r.left, e.clientY - r.top);
  if (i >= 0) selectPoint(i);
};
$('img').onclick = e => {
  if (!S.data) return;
  const r = e.target.getBoundingClientRect();
  const ia = Math.max(0, Math.min(1023, Math.floor((e.clientX - r.left)/r.width*1024)));
  const ie = Math.max(0, Math.min(511, 511 - Math.floor((e.clientY - r.top)/r.height*512)));
  selectBin(ia, ie);
};
boot().catch(e => { $('status').textContent = 'ERROR ' + e.message; });
