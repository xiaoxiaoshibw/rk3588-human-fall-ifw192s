"use strict";
const canvas = document.getElementById('view');
const ctx = canvas.getContext('2d');
const pointEl = document.getElementById('point');
const calRows = document.getElementById('calRows');
const trackLine = document.getElementById('trackLine');
const stateLine = document.getElementById('stateLine');
const transformLine = document.getElementById('transformLine');
const frameRange = document.getElementById('frame');
const frameNo = document.getElementById('frameNo');
const cameraSelect = document.getElementById('camera');

const S = {
  meta: null, frame: null, fi: 0, camera: 'top', dpr: 1,
  points: [], projected: [], selected: null, ready: false
};

function fmt(v, digits = 4) {
  return v === null || v === undefined || Number.isNaN(v) ? '—' : Number(v).toFixed(digits);
}
function edgeName(e) { return e[0] + '→' + e[1]; }

function resize() {
  S.dpr = window.devicePixelRatio || 1;
  const r = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.round(r.width * S.dpr));
  canvas.height = Math.max(1, Math.round(r.height * S.dpr));
  draw();
}
window.addEventListener('resize', resize);

function project(p) {
  if (!p) return [0, 0];
  if (S.camera === 'side') return [p[0], p[2]];
  if (S.camera === 'oblique') return [p[0] + 0.28 * p[1], p[2] + 0.12 * p[1]];
  return [p[0], p[1]];
}

function bounds() {
  if (!S.points.length) return {minx:-2, maxx:2, miny:-2, maxy:2};
  let xs = [], ys = [];
  for (const p of S.points) {
    const q = project(p);
    xs.push(q[0]); ys.push(q[1]);
  }
  const tr = S.frame && S.frame.best_track;
  if (tr) for (const n of Object.values(tr.nodes || {})) {
    const xyz = n.display_xyz || n.xyz;
    if (xyz) { const q = project(xyz); xs.push(q[0]); ys.push(q[1]); }
  }
  xs.sort((a,b)=>a-b); ys.sort((a,b)=>a-b);
  const q = (a, f) => a.length ? a[Math.min(a.length-1, Math.max(0, Math.floor(a.length*f)))] : 0;
  let minx=q(xs,.02), maxx=q(xs,.98), miny=q(ys,.02), maxy=q(ys,.98);
  if (maxx-minx < .5) { minx-=.25; maxx+=.25; }
  if (maxy-miny < .5) { miny-=.25; maxy+=.25; }
  const padx=(maxx-minx)*.08, pady=(maxy-miny)*.08;
  return {minx:minx-padx,maxx:maxx+padx,miny:miny-pady,maxy:maxy+pady};
}

function worldToScreen(p, b) {
  const r = canvas.getBoundingClientRect();
  const sx = r.width / (b.maxx-b.minx);
  const sy = r.height / (b.maxy-b.miny);
  const scale = Math.min(sx, sy);
  const ox = (r.width - (b.maxx-b.minx)*scale)/2;
  const oy = (r.height - (b.maxy-b.miny)*scale)/2;
  return [ox + (p[0]-b.minx)*scale, r.height - oy - (p[1]-b.miny)*scale];
}

function draw() {
  const r = canvas.getBoundingClientRect();
  ctx.setTransform(S.dpr,0,0,S.dpr,0,0);
  ctx.clearRect(0,0,r.width,r.height);
  ctx.fillStyle='#05080c'; ctx.fillRect(0,0,r.width,r.height);
  const b = bounds();
  ctx.strokeStyle='#162432'; ctx.lineWidth=1;
  for (let i=0;i<=10;i++) {
    const x = b.minx + (b.maxx-b.minx)*i/10;
    const y = b.miny + (b.maxy-b.miny)*i/10;
    const p1=worldToScreen([x,b.miny],b), p2=worldToScreen([x,b.maxy],b);
    const p3=worldToScreen([b.minx,y],b), p4=worldToScreen([b.maxx,y],b);
    ctx.beginPath();ctx.moveTo(p1[0],p1[1]);ctx.lineTo(p2[0],p2[1]);ctx.stroke();
    ctx.beginPath();ctx.moveTo(p3[0],p3[1]);ctx.lineTo(p4[0],p4[1]);ctx.stroke();
  }
  S.projected = S.points.map((p, i) => {
    const q = worldToScreen(project([p[0],p[1],p[2]]), b);
    return {i, x:q[0], y:q[1], row:p[3]};
  });
  ctx.fillStyle='#4f788d';
  for (const q of S.projected) {
    ctx.fillRect(q.x, q.y, 1.4, 1.4);
  }
  const tr = S.frame && S.frame.best_track;
  if (tr) {
    const nodePos = {};
    for (const [name, n] of Object.entries(tr.nodes || {})) {
      const xyz = n.display_xyz || n.xyz;
      if (!xyz) continue;
      nodePos[name] = worldToScreen(project(xyz), b);
    }
    ctx.strokeStyle='#49e3a1'; ctx.lineWidth=2;
    for (const e of (tr.display_edges || [])) {
      const a=nodePos[e[0]], c=nodePos[e[1]];
      if (!a || !c) continue;
      ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(c[0],c[1]);ctx.stroke();
    }
    for (const [name, q] of Object.entries(nodePos)) {
      ctx.fillStyle='#ffd166';
      ctx.beginPath();ctx.arc(q[0],q[1],3.2,0,Math.PI*2);ctx.fill();
      ctx.fillStyle='#d8e2ea'; ctx.font='10px monospace'; ctx.fillText(name,q[0]+5,q[1]-4);
    }
  }
  if (S.selected) {
    const q = worldToScreen(project(S.selected), b);
    ctx.strokeStyle='#ff6b6b';ctx.lineWidth=2;ctx.beginPath();ctx.arc(q[0],q[1],7,0,Math.PI*2);ctx.stroke();
  }
}

async function loadMeta() {
  S.meta = await (await fetch('/api/meta')).json();
  stateLine.textContent = 'frames=' + S.meta.summary.frame_count + '  rows=' + S.meta.summary.totals.rows +
    '  read_only_unchanged=' + S.meta.summary.read_only_unchanged +
    '  candidate-coverage=' + fmt(S.meta.calibration_gate.candidate_action_six_fraction,3) +
    '  primary=' + (S.meta.primary_track || '—');
  transformLine.textContent = 'transform=' + S.meta.meta.transform_id + '  m0=' + S.meta.meta.m0_map_id +
    '  protocol=' + S.meta.meta.protocol_sha;
}

function renderFrame() {
  const f = S.frame;
  if (!f) return;
  stateLine.textContent = 'frame=' + f.fi + '  t=' + fmt(f.relative_s,3) + 's  phase=' + f.record.phase +
    '  qualified=' + f.record.qualified + '  rows=' + f.rows + '  valid=' + f.valid_rows +
    '  candidates=' + f.record.candidate_summaries.length;
  const tr = f.best_track;
  if (!tr) {
    trackLine.textContent = 'no skeleton at this frame (candidate unavailable or insufficient support)';
    calRows.innerHTML = '<tr><td colspan="5">no measurement</td></tr>';
  } else {
    trackLine.textContent = 'track=' + tr.track_id + '  identity=UNKNOWN  candidate=' + tr.candidate_id +
      '  valid_nodes=' + tr.valid_nodes + '  edges=' + tr.edge_count + '  rows=' + tr.candidate_rows;
    const rows = [];
    for (const e of (tr.edges || [])) {
      rows.push('<tr><td>' + edgeName(e.edge) + '</td><td class="state ' + e.state + '">' + e.state +
        '</td><td>' + fmt(e.mean) + '</td><td>' + fmt(e.sigma) + '</td><td>' + e.n + '</td></tr>');
    }
    calRows.innerHTML = rows.join('');
  }
  pointEl.textContent = 'click a point';
  S.selected = null;
  draw();
}

async function loadFrame(fi) {
  S.fi = Math.max(0, Math.min(779, Number(fi)));
  frameRange.value = String(S.fi); frameNo.value = String(S.fi);
  S.frame = await (await fetch('/api/frame?fi=' + S.fi)).json();
  S.points = S.frame.points || [];
  renderFrame();
  return S.frame;
}

async function pickAt(x, y) {
  if (!S.projected.length) return null;
  let best = null, bestD = 14;
  for (const q of S.projected) {
    const d = Math.hypot(q.x-x, q.y-y);
    if (d < bestD) { bestD = d; best = q; }
  }
  if (!best) return null;
  const p = S.points[best.i];
  S.selected = [p[0],p[1],p[2]];
  draw();
  const data = await (await fetch('/api/point?fi=' + S.fi + '&row=' + best.row)).json();
  pointEl.textContent = JSON.stringify(data, null, 2);
  return data;
}

canvas.addEventListener('click', ev => {
  const r = canvas.getBoundingClientRect();
  pickAt(ev.clientX-r.left, ev.clientY-r.top).catch(err => pointEl.textContent = String(err));
});
frameRange.addEventListener('input', () => loadFrame(frameRange.value));
frameNo.addEventListener('change', () => loadFrame(frameNo.value));
document.getElementById('prev').onclick = () => loadFrame(S.fi-1);
document.getElementById('next').onclick = () => loadFrame(S.fi+1);
cameraSelect.onchange = () => { S.camera = cameraSelect.value; draw(); };

window.__skel = {
  get ready() { return S.ready; },
  get state() { return S; },
  loadFrame,
  camera(mode) { S.camera = mode; cameraSelect.value = mode; draw(); return this.snapshot(); },
  pickIndex(i) {
    const q = S.projected[Math.max(0, Math.min(S.projected.length-1, i))];
    return q ? {x:q.x,y:q.y,row:q.row} : null;
  },
  screenOf(i) { return this.pickIndex(i); },
  visibleIndex() {
    const r = canvas.getBoundingClientRect();
    for (let i=0;i<S.projected.length;i++) {
      const q = S.projected[i];
      if (q.x > 12 && q.x < r.width-12 && q.y > 12 && q.y < r.height-12) return i;
    }
    return S.projected.length ? 0 : -1;
  },
  snapshot() {
    const tr = S.frame && S.frame.best_track;
    const nodeSig = tr ? Object.entries(tr.nodes || {}).map(([k,n]) => [k,n.xyz]).join('|') : '';
    const p = S.points[0] || [null,null,null,null];
    return {
      fi: S.fi, camera: S.camera,
      transform_id: S.frame && S.frame.transform_id,
      point_count: S.points.length,
      first_point: p,
      skeleton_edges: tr ? (tr.display_edges || []).length : 0,
      valid_nodes: tr ? tr.valid_nodes : 0,
      coordinate_digest: JSON.stringify([S.frame && S.frame.transform_id, S.fi, p[0], p[1], p[2], p[3], nodeSig])
    };
  },
  pickInvalid() {
    const row = S.frame && S.frame.invalid_row_examples && S.frame.invalid_row_examples[0];
    if (row === undefined) return null;
    return fetch('/api/point?fi=' + S.fi + '&row=' + row).then(r => r.json()).then(data => {
      pointEl.textContent = JSON.stringify(data, null, 2);
      return data;
    });
  }
};

(async function main() {
  await loadMeta();
  await loadFrame(0);
  S.ready = true;
  resize();
})().catch(err => { stateLine.textContent = 'ERROR ' + err; });
