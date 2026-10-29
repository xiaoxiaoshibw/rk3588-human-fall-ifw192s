'use strict';
const S = { meta: null, fi: 0, data: null, sel: -1, camera: 'oblique', zoom: 70 };
const $ = id => document.getElementById(id);
const b64f32 = s => new Float32Array(Uint8Array.from(atob(s), c => c.charCodeAt(0)).buffer);
const b64i32 = s => new Int32Array(Uint8Array.from(atob(s), c => c.charCodeAt(0)).buffer);
const b64u8 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));

async function get(url) {
  const r = await fetch(url);
  const j = await r.json();
  if (j.error) throw new Error(j.message);
  return j;
}

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
  return [cx + x * scale, cy - z2 * scale, y2];
}

// Both panes share one metres-per-pixel factor (the smaller of the two fits) and each pane is
// centred on its own cloud, so the RAW/levelled comparison is scale-honest and a camera switch
// can never change a coordinate.
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
  const q = (arr, f) => arr[Math.min(arr.length - 1, Math.max(0, Math.floor(f * (arr.length - 1))))];
  const x0 = q(xs, 0.01), x1 = q(xs, 0.99), y0 = q(ys, 0.01), y1 = q(ys, 0.99);
  const w = Math.max(x1 - x0, 0.6), hh = Math.max(y1 - y0, 0.6);
  return { cx0: (x0 + x1) / 2, cy0: (y0 + y1) / 2, scale: Math.min(760 / w, 620 / hh) };
}

function geometry(canvas) {
  const a = paneBounds(S.data.raw), b = paneBounds(S.data.local);
  const scale = Math.min(a.scale, b.scale) * (S.zoom / 70);
  const f = canvas.id === 'ploc' ? b : a;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  return { scale, cx: W / 2 - f.cx0 * scale, cy: H / 2 + 20 - f.cy0 * scale, W, H };
}

function draw(canvas) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W * dpr; canvas.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = '#080d13'; ctx.fillRect(0, 0, W, H);
  if (!S.data) return;
  const g = geometry(canvas);
  const loco = canvas.id === 'ploc';
  const gridZ = 0.0;
  ctx.strokeStyle = '#2c4a63'; ctx.lineWidth = 0.6;
  for (let a = 0.2; a <= 2.6; a += 0.4) {
    const p1 = project(a, -0.4, gridZ, g.scale, g.cx, g.cy);
    const p2 = project(a, 2.4, gridZ, g.scale, g.cx, g.cy);
    ctx.beginPath(); ctx.moveTo(p1[0], p1[1]); ctx.lineTo(p2[0], p2[1]); ctx.stroke();
  }
  for (let b = -0.4; b <= 2.4; b += 0.4) {
    const p1 = project(0.2, b, gridZ, g.scale, g.cx, g.cy);
    const p2 = project(2.6, b, gridZ, g.scale, g.cx, g.cy);
    ctx.beginPath(); ctx.moveTo(p1[0], p1[1]); ctx.lineTo(p2[0], p2[1]); ctx.stroke();
  }
  if (loco) {
    ctx.strokeStyle = '#ff9800'; ctx.lineWidth = 1.2;
    const o = project(1.5, 1.0, 0, g.scale, g.cx, g.cy);
    const tip = project(1.5, 1.0, 0.6, g.scale, g.cx, g.cy);
    ctx.beginPath(); ctx.moveTo(o[0], o[1]); ctx.lineTo(tip[0], tip[1]); ctx.stroke();
    ctx.beginPath(); ctx.arc(o[0], o[1], 3, 0, 6.29); ctx.stroke();
    ctx.fillStyle = '#ff9800'; ctx.font = '12px ui-monospace';
    ctx.fillText('z=0 候选平面 / +z 法向', 10, 18);
  } else {
    ctx.fillStyle = '#8fb3d9'; ctx.font = '12px ui-monospace';
    ctx.fillText('RAW 坐标（未配平，倾斜未校正）', 10, 18);
  }
  const pts = loco ? S.data.local : S.data.raw;
  const cols = ['#6b7c8f', '#4fc3f7', '#ffb74d', '#ba68c8'];
  for (let i = 0; i < pts.length / 3; i++) {
    const a = project(pts[3 * i], pts[3 * i + 1], pts[3 * i + 2], g.scale, g.cx, g.cy);
    if (a[0] < -20 || a[0] > W + 20 || a[1] < -20 || a[1] > H + 20) continue;
    const pid = S.data.patch[i];
    ctx.fillStyle = i === S.sel ? '#66ff99' : (pid ? cols[pid] : '#5b6b7c');
    ctx.globalAlpha = i === S.sel ? 1 : (pid ? 0.9 : 0.32);
    ctx.fillRect(a[0] - 1.2, a[1] - 1.2, i === S.sel ? 5 : 2.4, i === S.sel ? 5 : 2.4);
  }
  ctx.globalAlpha = 1;
  if (S.data.patchNames) {
    ctx.fillStyle = '#a9bccf'; ctx.font = '11px ui-monospace';
    const p = S.data.patchNames;
    ctx.fillText('验证片 ' + p.map((x, k) => (k + 1) + '=' + x.id + ' ' + x.per_frame_median + '/帧').join('  '), 10, H - 10);
  }
}

function stateText() {
  const d = S.data, rec = d.record;
  const lines = [
    '帧 ' + S.fi + '  t=' + d.time_s.toFixed(3) + 's',
    'online_state: ' + d.state + '   (' + d.state_reason[0] + ')',
    '说明: ' + d.state_reason[1],
    'qualified_M0: ' + rec.qualified + '   map_exists: ' + d.record.m0_exists,
    'rows=' + d.rows + ' valid=' + d.valid + ' invalid=' + d.invalid,
    'candidates=' + rec.candidates + ' 候选成员行=' + rec.candidate_rows + '  track=' + rec.track.state,
    'labels: ' + Object.entries(d.labels).map(([k, v]) => k + '=' + v).join(' '),
    'map_id: ' + (rec.map_id || '-'),
    'transform_id: ' + d.transform_id,
    'coordinate_version: ' + d.coordinate_version,
    '失败原因: ' + (S.meta.failure || '无（验证门全部通过；地面身份/物理高度仍 BLOCKED）')
  ];
  $('state').textContent = lines.join('\n');
  $('status').textContent = '帧 ' + S.fi + ' t=' + d.time_s.toFixed(3) + 's  显示 ' + (d.raw.length / 3) +
    ' 点 / 本帧 ' + d.rows + ' 行（显示抽样；计算与分母不抽样）';
}

function renderMeta() {
  const m = S.meta;
  $('stateLine').textContent = 'state: ' + m.state + '（271 起生效: ' + m.state_from_fi + '）  mode: ' + m.mode;
  $('transformLine').textContent = 'transform: ' + m.transform.coordinate_version + '  t=(' +
    m.transform.t.map(x => x.toFixed(6)).join(', ') + ')  R[2]=(' + m.transform.R[2].map(x => x.toFixed(6)).join(', ') + ')';
  const v = m.verification, d = m.domains, m0 = m.m0;
  let s = 'candidate: ' + m.candidate.id + '  n=(' + m.candidate.n.map(x => x.toFixed(6)).join(', ') +
    ') d=' + m.candidate.d.toFixed(6) + ' m  [' + m.candidate.status + ']\n';
  s += '变换 artifact SHA: ' + m.transform.artifact_sha.slice(0, 16) + '…  qualification: ' +
    JSON.stringify(m.qualification) + '\n';
  s += 'M0: map_id=' + m0.map_id.slice(0, 16) + '… surfaces=' + m0.surfaces + ' eligible=' + m0.eligible_surfaces +
    ' voxel=' + m0.voxel_m + 'm tau=' + m0.tau_m + 'm support_rows=' + m0.support_rows +
    ' build_end_fi=' + m0.build_end_fi + ' available_after_fi=' + m0.available_after_fi + '\n';
  s += '新域 SHA: ' + d.domains_sha.slice(0, 16) + '…  门槛: RMS≤' + (v.gates.rms_m * 100) + 'cm P95≤' +
    (v.gates.p95_abs_m * 100) + 'cm 支持≥' + (v.gates.support_rate * 100) + '% ≥' + v.gates.min_points +
    ' 行 展开≥' + (v.gates.spread_min_m * 100) + 'cm\n';
  s += '\n片\t行\tRMS cm\tP95 cm\t支持率\t通过\n';
  for (const k in v.spatial) {
    const p = v.spatial[k];
    s += k + '\t' + p.count + '\t' + (p.rms_m * 100).toFixed(2) + '\t' + (p.p95_abs_m * 100).toFixed(2) + '\t' +
      (p.support_rate * 100).toFixed(1) + '%\t' + p.PASS + '\n';
  }
  s += '空间通过 ' + v.spatial_pass + '/3（需 ≥2）  时间 ' + (v.temporal_pass * 100).toFixed(1) + '%（需 ≥95%）  前缀 ' +
    v.prefix_pass + '/' + v.prefix_frames + '\n';
  s += '噪声参照（只解释不改门）: ' + Object.entries(v.noise).map(([k, x]) =>
    k + ' σ=' + (x.cross_frame_median_std_m * 1000).toFixed(2) + 'mm').join('  ') + '\n';
  s += '分母: rows=' + m.conservation.rows + ' valid=' + m.conservation.valid + ' invalid=' + m.conservation.invalid +
    '  守恒=' + m.conservation.PASS + '\n';
  s += '对照（不参与本段变换）: ' + m.controls.map(c => c.id + ' n=(' + c.n.map(x => x.toFixed(3)).join(',') +
    ') d=' + c.d.toFixed(4)).join('   ') + '\n';
  s += 'state=' + m.state + '; 地面身份 NOT_CONFIRMED；物理高度/独立 D 未验证';
  $('cand').textContent = s;
}

async function loadFrame(fi) {
  $('status').textContent = '加载帧 ' + fi + ' …';
  const d = await get('/api/frame?fi=' + fi);
  d.raw = b64f32(d.raw); d.local = b64f32(d.local);
  d.rowsArr = b64i32(d.rows_b64); d.patch = b64u8(d.patch);
  d.patchNames = S.meta.domains.patches;
  S.data = d; S.fi = fi; S.sel = -1;
  $('fi').value = fi;
  draw($('praw')); draw($('ploc'));
  stateText();
  return d;
}

function nearest(canvas, mx, my) {
  const g = geometry(canvas);
  const loco = canvas.id === 'ploc';
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
  draw($('praw')); draw($('ploc'));
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
  S.sel = -1;
  draw($('praw')); draw($('ploc'));
  return p;
}

async function boot() {
  S.meta = await get('/api/meta');
  renderMeta();
  const q = new URLSearchParams(location.search);
  const fi = q.has('fi') ? parseInt(q.get('fi')) : 0;
  await loadFrame(fi);
  const screenOf = (which, i) => {
    const c = $(which === 'ploc' ? 'ploc' : 'praw');
    const g = geometry(c);
    const pts = which === 'ploc' ? S.data.local : S.data.raw;
    const a = project(pts[3 * i], pts[3 * i + 1], pts[3 * i + 2], g.scale, g.cx, g.cy);
    return { x: a[0], y: a[1], w: c.clientWidth, h: c.clientHeight };
  };
  window.__s3 = {
    state: S, meta: S.meta, loadFrame, selectPoint, selectFirstInvalid, screenOf,
    setCamera: m => { S.camera = m; draw($('praw')); draw($('ploc')); },
    snapshot: () => JSON.stringify([Array.from(S.data.raw), Array.from(S.data.local), Array.from(S.data.rowsArr)]),
    patchIndex: () => { for (let i = 0; i < S.data.patch.length; i++) if (S.data.patch[i]) return i; return 0; },
    // a display point whose projection is comfortably inside BOTH panes and is the nearest point to
    // its own projection in both panes, so one real click per pane lands on the same source row
    pickIndex: (margin = 8) => {
      const ca = $('praw'), cb = $('ploc');
      const ga = geometry(ca), gb = geometry(cb);
      const pos = (i, g, c) => {
        const pts = c === ca ? S.data.raw : S.data.local;
        return project(pts[3 * i], pts[3 * i + 1], pts[3 * i + 2], g.scale, g.cx, g.cy);
      };
      const inside = (i, g, c) => {
        const a = pos(i, g, c);
        return a[0] > margin && a[0] < c.clientWidth - margin && a[1] > margin && a[1] < c.clientHeight - margin;
      };
      const order = [];
      for (let i = 0; i < S.data.patch.length; i++) if (S.data.patch[i]) order.push(i);
      for (let i = 0; i < S.data.raw.length / 3; i += 3) order.push(i);
      // real mouse events are quantised to integer pixels, so the chosen point needs >= 3 px of
      // separation from its neighbours in both panes; otherwise a 1 px shift can pick another row
      const separation = (i, g, c) => {
        const pts = c === ca ? S.data.raw : S.data.local;
        const p = pos(i, g, c);
        let second = 1e9;
        for (let k = 0; k < pts.length / 3; k++) {
          if (k === i) continue;
          const a = project(pts[3 * k], pts[3 * k + 1], pts[3 * k + 2], g.scale, g.cx, g.cy);
          const dd = Math.sqrt((a[0] - p[0]) ** 2 + (a[1] - p[1]) ** 2);
          if (dd < second) second = dd;
        }
        return second;
      };
      for (const i of order) {
        if (!inside(i, ga, ca) || !inside(i, gb, cb)) continue;
        const a = pos(i, ga, ca), b = pos(i, gb, cb);
        if (nearest(ca, a[0], a[1]) !== i || nearest(cb, b[0], b[1]) !== i) continue;
        if (separation(i, ga, ca) < 3 || separation(i, gb, cb) < 3) continue;
        return i;
      }
      return -1;
    }
  };
}

$('load').onclick = () => loadFrame(Math.max(0, Math.min(779, parseInt($('fi').value) || 0)));
$('prev').onclick = () => loadFrame(Math.max(0, S.fi - 1));
$('next').onclick = () => loadFrame(Math.min(779, S.fi + 1));
$('camera').onchange = e => { S.camera = e.target.value; draw($('praw')); draw($('ploc')); };
$('zoom').oninput = e => { S.zoom = +e.target.value; draw($('praw')); draw($('ploc')); };
$('pickbad').onclick = () => selectFirstInvalid();
for (const id of ['praw', 'ploc']) {
  $(id).onclick = e => {
    if (!S.data) return;
    const r = e.target.getBoundingClientRect();
    const i = nearest($(id), e.clientX - r.left, e.clientY - r.top);
    if (i >= 0) selectPoint(i);
  };
}
boot().catch(e => { $('status').textContent = 'ERROR ' + e.message; });
