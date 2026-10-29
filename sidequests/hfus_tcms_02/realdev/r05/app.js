'use strict';
const S = { meta: null, fi: 0, data: null, sel: -1, camera: 'oblique', zoom: 70 };
const $ = id => document.getElementById(id);
const b64f32 = s => new Float32Array(Uint8Array.from(atob(s), c => c.charCodeAt(0)).buffer);
const b64i32 = s => new Int32Array(Uint8Array.from(atob(s), c => c.charCodeAt(0)).buffer);
const b64u8 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));

async function get(url) { const r = await fetch(url); const j = await r.json(); if (j.error) throw new Error(j.message); return j; }

function cameraBasis() {
  const yaw = S.camera === 'side' ? 0 : S.camera === 'front' ? Math.PI / 2 : -0.9;
  const pitch = S.camera === 'top' ? Math.PI / 2 : S.camera === 'oblique' ? 0.85 : 0;
  return { yaw, pitch };
}
function project(u, v, h, scale, cx, cy) {
  const { yaw, pitch } = cameraBasis();
  const cyaw = Math.cos(yaw), syaw = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  const x = u * cyaw - v * syaw, y = u * syaw + v * cyaw;
  const y2 = y * cp - h * sp, z2 = y * sp + h * cp;
  return [cx + x * scale, cy - z2 * scale];
}
function paneBounds(pts) {
  const { yaw, pitch } = cameraBasis();
  const cyaw = Math.cos(yaw), syaw = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  const xs = [], ys = [];
  for (let i = 0; i < pts.length / 3; i++) {
    const u = pts[3 * i], v = pts[3 * i + 1], h = pts[3 * i + 2];
    if (!isFinite(u) || !isFinite(v) || !isFinite(h)) continue;
    const x = u * cyaw - v * syaw, y = u * syaw + v * cyaw;
    xs.push(x); ys.push(y * cp - h * sp);
  }
  if (!xs.length) return { cx0: 0, cy0: 0, scale: 200 };
  xs.sort((a, b) => a - b); ys.sort((a, b) => a - b);
  const q = (a, f) => a[Math.min(a.length - 1, Math.max(0, Math.floor(f * (a.length - 1))))];
  const x0 = q(xs, 0.01), x1 = q(xs, 0.99), y0 = q(ys, 0.01), y1 = q(ys, 0.99);
  return { cx0: (x0 + x1) / 2, cy0: (y0 + y1) / 2, scale: Math.min(760 / Math.max(x1 - x0, 0.6), 620 / Math.max(y1 - y0, 0.6)) };
}
function geometry(canvas) {
  const a = paneBounds(S.data.raw), b = paneBounds(S.data.local);
  const scale = Math.min(a.scale, b.scale) * (S.zoom / 70);
  const f = canvas.id === 'p3' ? b : a;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  return { scale, cx: W / 2 - f.cx0 * scale, cy: H / 2 + 20 - f.cy0 * scale, W, H };
}
function draw(canvas) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W * dpr; canvas.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = '#080d13'; ctx.fillRect(0, 0, W, H);
  if (!S.data) return;
  const g = geometry(canvas), loco = canvas.id === 'p3';
  ctx.strokeStyle = '#2c4a63'; ctx.lineWidth = 0.6;
  for (let a = 0.2; a <= 2.6; a += 0.4) {
    const p1 = project(a, -0.4, 0, g.scale, g.cx, g.cy), p2 = project(a, 2.4, 0, g.scale, g.cx, g.cy);
    ctx.beginPath(); ctx.moveTo(p1[0], p1[1]); ctx.lineTo(p2[0], p2[1]); ctx.stroke();
  }
  for (let b = -0.4; b <= 2.4; b += 0.4) {
    const p1 = project(0.2, b, 0, g.scale, g.cx, g.cy), p2 = project(2.6, b, 0, g.scale, g.cx, g.cy);
    ctx.beginPath(); ctx.moveTo(p1[0], p1[1]); ctx.lineTo(p2[0], p2[1]); ctx.stroke();
  }
  ctx.fillStyle = loco ? '#8fb3d9' : '#7f93a8'; ctx.font = '12px ui-monospace';
  ctx.fillText(loco ? 'S3_LOCAL · z=0 为已验证平面' : 'RAW · 未配平', 10, 18);
  const pts = loco ? S.data.local : S.data.raw;
  const cols = ['#6b7c8f', '#5ce68a', '#ffb74d', '#8f9aa8'];
  for (let i = 0; i < pts.length / 3; i++) {
    const a = project(pts[3 * i], pts[3 * i + 1], pts[3 * i + 2], g.scale, g.cx, g.cy);
    if (a[0] < -20 || a[0] > W + 20 || a[1] < -20 || a[1] > H + 20) continue;
    const band = S.data.band[i];
    ctx.fillStyle = i === S.sel ? '#c060ff' : cols[band];
    ctx.globalAlpha = i === S.sel ? 1 : (band === 1 || band === 2 ? 0.95 : 0.3);
    ctx.fillRect(a[0] - 1.2, a[1] - 1.2, i === S.sel ? 5 : 2.4, i === S.sel ? 5 : 2.4);
  }
  ctx.globalAlpha = 1;
}
function bandLine(b) {
  return 'CONTACT=' + b.contact.rows + '（其中 M0 背景 ' + b.contact.bg + '，候选 ' + b.contact.candidate + '）'
    + '  NEAR=' + b.near_ground.rows + '（bg ' + b.near_ground.bg + '，候选 ' + b.near_ground.candidate + '）'
    + '  CLEAR=' + b.clear.rows;
}
function stateText() {
  const d = S.data, r = d.record;
  const m = S.meta;
  const lines = [
    '帧 ' + S.fi + '  t=' + d.time_s.toFixed(3) + 's  state=' + d.state,
    'rows=' + d.rows + ' valid=' + d.valid + ' invalid=' + d.invalid,
    '候选=' + r.candidates + ' 候选成员行=' + r.decomp.candidate_members + ' 背景行=' + r.decomp.bg +
      ' 种子行=' + r.decomp.seeds + ' 拒绝行=' + r.decomp.rejected_total + ' 余项=' + r.decomp.leftover,
    '分解配平: ' + (r.decomp.watertight ? 'valid = bg + members + rejected（余项 0）' : '不配平！见 TAIL/F430'),
    '拒绝原因: ' + (Object.keys(r.decomp.rejected_by_reason).length
      ? Object.entries(r.decomp.rejected_by_reason).map(([k, v]) => k + '=' + v).join(' ') : '无'),
    '分带: ' + bandLine(r.bands),
    'labels: ' + Object.entries(d.labels).map(([k, v]) => k + '=' + v).join(' '),
    'transform_id: ' + d.transform_id + '  map_id: ' + (r.map_id || '-'),
    '尾段零候选帧: ' + m.tail_zero.join(',')
  ];
  $('state').textContent = lines.join('\n');
  $('status').textContent = '帧 ' + S.fi + ' 显示 ' + (d.raw.length / 3) + ' 点 / 本帧 ' + d.rows + ' 行（显示抽样，分母不抽样）';
}
function renderMeta() {
  const m = S.meta;
  $('metaLine').textContent = m.item + ' · ' + m.geometry + ' · transform ' + m.transform_id.slice(0, 16) +
    '… · M0 ' + m.m0.map_id.slice(0, 12) + '… (' + m.m0.surfaces + ' 面 / ' + m.m0.support + ' 支持行)';
  let s = '尾段（745–779）: 帧 ' + m.tail.frames + '，零候选 ' + m.tail.zero + '；contact 行 ' + m.tail.contact_rows +
    '，其中 M0 背景 ' + m.tail.contact_bg + '（' + (100 * m.tail.contact_bg / Math.max(1, m.tail.contact_rows)).toFixed(2) + '%）\n';
  s += '每帧配平: ' + (m.tail.all_watertight ? '全部余项 0' : '存在不配平帧') + '\n\n零候选帧逐帧原因:\n';
  for (const [fi, v] of Object.entries(m.tail_reasons)) {
    s += fi + ': seeds=' + v.seeds + ' contact=' + v.contact_rows + '/bg' + v.contact_bg +
      ' near=' + v.near_rows + ' → ' + v.reason + '\n';
  }
  s += '\nf430–449: 零候选 ' + (m.f430.zero.length ? m.f430.zero.join(',') : '无') + '；配平 ' + (m.f430.all_watertight ? '是' : '否') + '\n';
  s += 'A/B/C/D 定义: ' + JSON.stringify(m.abcd) + '\n';
  s += '接触带定义: contact ' + JSON.stringify(m.contact.contact_band_m) + ' / near ' + JSON.stringify(m.contact.near_ground_band_m) +
    '；' + m.contact.rule;
  $('tail').textContent = s;
}
async function loadFrame(fi) {
  $('status').textContent = '加载帧 ' + fi + ' …';
  const d = await get('/api/frame?fi=' + fi);
  d.raw = b64f32(d.raw); d.local = b64f32(d.local); d.band = b64u8(d.band); d.rowsArr = b64i32(d.rows_b64);
  S.data = d; S.fi = fi; S.sel = -1;
  $('fi').value = fi;
  draw($('p3')); draw($('praw')); stateText();
  return d;
}
function depth(canvas, mx, my) {
  const g = geometry(canvas), loco = canvas.id === 'p3';
  const pts = loco ? S.data.local : S.data.raw;
  let best = -1, bd = 1e9;
  for (let i = 0; i < pts.length / 3; i++) {
    const a = project(pts[3 * i], pts[3 * i + 1], pts[3 * i + 2], g.scale, g.cx, g.cy);
    const dd = (a[0] - mx) ** 2 + (a[1] - my) ** 2;
    if (dd < bd) { bd = dd; best = i; }
  }
  return bd <= 144 ? best : -1;
}
async function selectPoint(i) {
  const row = S.data.rowsArr[i];
  S.sel = i;
  const p = await get('/api/point?fi=' + S.fi + '&row=' + row);
  $('point').textContent = JSON.stringify(p, null, 1);
  draw($('p3')); draw($('praw'));
  return p;
}
async function selectFirstInvalid() {
  const info = await get('/api/firstinvalid?fi=' + S.fi);
  if (info.row === null) {
    $('point').textContent = JSON.stringify(info, null, 1);
    return info;
  }
  const p = await get('/api/point?fi=' + S.fi + '&row=' + info.row);
  $('point').textContent = JSON.stringify(p, null, 1);
  return p;
}
async function boot() {
  S.meta = await get('/api/meta');
  renderMeta();
  const q = new URLSearchParams(location.search);
  await loadFrame(q.has('fi') ? parseInt(q.get('fi')) : 0);
  const screenOf = (i, canvas) => {
    const c = $(canvas || 'p3');
    const g = geometry(c);
    const pts = c.id === 'p3' ? S.data.local : S.data.raw;
    const a = project(pts[3 * i], pts[3 * i + 1], pts[3 * i + 2], g.scale, g.cx, g.cy);
    return { x: a[0], y: a[1], w: c.clientWidth, h: c.clientHeight };
  };
  window.__s4 = {
    state: S, meta: S.meta, loadFrame, selectPoint, selectFirstInvalid, screenOf,
    snapshot: () => JSON.stringify([Array.from(S.data.raw), Array.from(S.data.local), Array.from(S.data.rowsArr)]),
    setCamera: m => { S.camera = m; draw($('p3')); draw($('praw')); },
    firstBand: b => { for (let i = 0; i < S.data.band.length; i++) if (S.data.band[i] === b) return i; return -1; }
  };
}
$('load').onclick = () => loadFrame(Math.max(0, Math.min(779, parseInt($('fi').value) || 0)));
$('prev').onclick = () => loadFrame(Math.max(0, S.fi - 1));
$('next').onclick = () => loadFrame(Math.min(779, S.fi + 1));
$('tail765').onclick = () => loadFrame(765);
$('tail779').onclick = () => loadFrame(779);
$('pickbad').onclick = () => selectFirstInvalid();
$('camera').onchange = e => { S.camera = e.target.value; draw($('p3')); draw($('praw')); };
$('zoom').oninput = e => { S.zoom = +e.target.value; draw($('p3')); draw($('praw')); };
for (const id of ['p3', 'praw']) {
  $(id).onclick = e => {
    if (!S.data) return;
    const r = e.target.getBoundingClientRect();
    const i = depth($(id), e.clientX - r.left, e.clientY - r.top);
    if (i >= 0) selectPoint(i);
  };
}
boot().catch(e => { $('status').textContent = 'ERROR ' + e.message; });
