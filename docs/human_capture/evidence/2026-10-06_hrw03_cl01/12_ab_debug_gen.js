/* CL-01 · 12_ab_debug_gen.js — 生成 12_ab_debug.html（离线、零依赖 canvas）。
 * 读取 12_ab_debug_data.json（逐点 compId/标记）+ 11_ab_real_frame_results.json（统计/下游）。
 * 用法：node 12_ab_debug_gen.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const HERE = __dirname;

const dbg = JSON.parse(fs.readFileSync(path.join(HERE, "12_ab_debug_data.json"), "utf8"));
const res = JSON.parse(fs.readFileSync(path.join(HERE, "11_ab_real_frame_results.json"), "utf8"));
const framesMeta = {}, detailMeta = {};
for (const fr of res.frames) framesMeta[fr.fi] = fr;
for (const d of res.detail) detailMeta[d.fi] = d;

const payload = { d_star: dbg.d_star, note: dbg.note, frames: [] };
for (const f of dbg.frames) {
    const variants = {};
    for (const vn of Object.keys(f.variants)) {
        const dk = vn === "D*" ? dbg.d_star : vn;
        const dv = (detailMeta[f.fi] && detailMeta[f.fi].variants[dk]) || null;
        const st = (framesMeta[f.fi] && framesMeta[f.fi].v[dk]) || null;
        variants[vn] = { ids: f.variants[vn], comps: f.comps[vn] || [], stats: st, detail: dv };
    }
    payload.frames.push({ fi: f.fi, kind: f.kind, proxy: f.proxy, points: f.points,
        ref: f.ref, tall: f.tall, proxyFlag: f.proxyFlag, variants: variants });
}

const html = `<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>CL-01 connectivity AB debug — ${dbg.d_star}</title>
<style>
  body { background:#101114; color:#c9ccd2; font:12px/1.45 "Segoe UI", sans-serif; margin:0; }
  header { padding:8px 12px; border-bottom:1px solid #2a2d33; position:sticky; top:0; background:#101114ee; z-index:5; }
  h1 { font-size:14px; margin:0 0 6px 0; font-weight:600; }
  button { background:#1c1f24; color:#c9ccd2; border:1px solid #33373e; border-radius:3px; padding:2px 8px; margin:1px; cursor:pointer; font-size:11px; }
  button.on { background:#2b4a6f; border-color:#3d6ea8; color:#fff; }
  #wrap { display:flex; }
  #grid { flex:1 1 auto; display:grid; grid-template-columns:1fr 1fr; grid-template-rows:1fr 1fr; gap:4px; padding:4px; }
  .cell { position:relative; background:#0b0c0e; border:1px solid #26292f; border-radius:4px; min-height:0; }
  .cell canvas { position:absolute; inset:0; width:100%; height:100%; }
  .ctag { position:absolute; left:6px; top:4px; font-weight:700; font-size:13px; color:#e7e9ee; text-shadow:0 1px 2px #000; pointer-events:none; }
  .cinfo { position:absolute; left:6px; bottom:4px; right:6px; font-size:10px; color:#9aa0aa; text-shadow:0 1px 2px #000; pointer-events:none; white-space:nowrap; overflow:hidden; }
  #side { width:340px; flex:0 0 auto; border-left:1px solid #2a2d33; padding:8px 10px; overflow:auto; height:calc(100vh - 58px); box-sizing:border-box; }
  #side h2 { font-size:12px; margin:10px 0 4px 0; color:#9fb3d1; }
  table { border-collapse:collapse; width:100%; }
  td, th { border:1px solid #26292f; padding:2px 4px; font-size:11px; text-align:left; }
  th { color:#9fb3d1; font-weight:600; }
  .mono { font-family:Consolas, monospace; }
  .muted { color:#7d838d; }
  .sw { display:inline-block; width:9px; height:9px; margin-right:3px; vertical-align:-1px; }
  #sel { background:#15181c; border:1px solid #2a2d33; border-radius:4px; padding:6px 8px; min-height:70px; }
</style>
</head>
<body>
<header>
  <h1>CL-01 connectivity shadow AB — 同帧 2×2 对照（A / B / C / ${dbg.d_star}） · production 零改动</h1>
  <div id="frames"></div>
  <div style="margin-top:3px">
    视图: <span id="views"></span>
    &nbsp;着色: <span id="colors"></span>
    &nbsp;<span class="muted">点击画布上的点选中 component；青色框 = 该 variant 的 person component；白框 = 选中 component；暗灰点 = &lt;3 节点（被 min_voxels 丢弃）</span>
  </div>
</header>
<div id="wrap">
  <div id="grid"></div>
  <div id="side">
    <h2>选中 component</h2>
    <div id="sel" class="mono muted">在任一画布点击点云…</div>
    <h2>本帧统计（来自 11_ab_real_frame_results.json）</h2>
    <div id="stats"></div>
    <h2>图例</h2>
    <div class="muted">着色“标记”: <span class="sw" style="background:#4a7bd0"></span>ref-static (ref&lt;0.12)
      <span class="sw" style="background:#3fae72;margin-left:8px"></span>tall (z&gt;1.45)
      <span class="sw" style="background:#d0a75a;margin-left:8px"></span>proxy cylinder</div>
  </div>
</div>
<script>
const DATA = ${JSON.stringify(payload)};

const FRAME_NOTES = { 10:"static-residual-only（f10）", 30:"static-residual-only（f30）", 55:"merged 人+静态（f55）",
  63:"clean walk（f63）", 80:"clean stand（f80）", 92:"clean lying（f92）", 146:"clean walk（f146）",
  150:"merged near-furniture（f150）", 155:"merged near-furniture（f155）", 160:"merged near-furniture（f160）" };
const VAR_ORDER = ["A","B","C","D*"];
let state = { fi: DATA.frames[0].fi, view: "xy", color: "comp", sel: {} };

const fEl = document.getElementById("frames");
DATA.frames.forEach((f, i) => {
  const b = document.createElement("button");
  b.textContent = "f" + f.fi + " · " + FRAME_NOTES[f.fi];
  b.onclick = () => { state.fi = f.fi; state.sel = {}; render(); };
  b.dataset.fi = f.fi; fEl.appendChild(b);
});
const vEl = document.getElementById("views");
[["xy","俯视 XY"],["xz","侧视 XZ"],["iso","ISO"]].forEach(([k, name]) => {
  const b = document.createElement("button"); b.textContent = name; b.dataset.view = k;
  b.onclick = () => { state.view = k; render(); }; vEl.appendChild(b);
});
const cEl = document.getElementById("colors");
[["comp","component"],["flags","标记"],["acomp","A 分区对照"]].forEach(([k, name]) => {
  const b = document.createElement("button"); b.textContent = name; b.dataset.color = k;
  b.onclick = () => { state.color = k; render(); }; cEl.appendChild(b);
});

const grid = document.getElementById("grid");
const cells = {};
VAR_ORDER.forEach(vn => {
  const d = document.createElement("div"); d.className = "cell";
  const c = document.createElement("canvas"); c.width = 300; c.height = 300;
  const tag = document.createElement("div"); tag.className = "ctag"; tag.textContent = vn;
  const info = document.createElement("div"); info.className = "cinfo";
  d.appendChild(c); d.appendChild(tag); d.appendChild(info); grid.appendChild(d);
  cells[vn] = { canvas: c, info: info };
  c.addEventListener("click", ev => pick(vn, ev));
});

function frame() { return DATA.frames.find(f => f.fi === state.fi); }
function fit(canvas, pts, view) {
  let mn = [1e9,1e9], mx = [-1e9,-1e9];
  for (let i = 0; i < pts.length; i++) {
    const p = proj(pts[i][0], pts[i][1], pts[i][2], view);
    if (p[0] < mn[0]) mn[0] = p[0]; if (p[0] > mx[0]) mx[0] = p[0];
    if (p[1] < mn[1]) mn[1] = p[1]; if (p[1] > mx[1]) mx[1] = p[1];
  }
  const w = mx[0]-mn[0] || 1, h = mx[1]-mn[1] || 1;
  const s = Math.min((canvas.width-20)/w, (canvas.height-20)/h);
  return { s: s, ox: (canvas.width - w*s)/2 - mn[0]*s, oy: (canvas.height - h*s)/2 - mn[1]*s, mn: mn };
}
function proj(x, y, z, view) {
  if (view === "xz") return [x, -z];
  if (view === "iso") return [(x - y) * 0.866, (x + y) * 0.5 - z];
  return [x, y];
}
function projPt(f, x, y, z, view) { return proj(x, y, z, view); }

const PAL = ["#e0655a","#5aa9e6","#7fd06b","#e6c05a","#b57ee0","#5ad0c2","#e08ab5","#8fa0e0","#c2b06a","#6ac28a","#d08a5a","#95b8d8"];
function compColor(id) { return PAL[((id % PAL.length) + PAL.length) % PAL.length]; }

function render() {
  const f = frame();
  document.querySelectorAll("#frames button").forEach(b => b.classList.toggle("on", +b.dataset.fi === state.fi));
  document.querySelectorAll("#views button").forEach(b => b.classList.toggle("on", b.dataset.view === state.view));
  document.querySelectorAll("#colors button").forEach(b => b.classList.toggle("on", b.dataset.color === state.color));
  for (const vn of VAR_ORDER) {
    const v = f.variants[vn]; if (!v) continue;
    const ctx = cells[vn].canvas.getContext("2d");
    const fitv = fit(cells[vn].canvas, f.points, state.view);
    ctx.clearRect(0, 0, 3000, 3000);
    const sel = state.sel[vn];
    const ids = v.ids, pts = f.points;
    const compSet = new Set(v.comps.map(c => c.id));
    const aIds = f.variants.A ? f.variants.A.ids : null;
    for (let i = 0; i < pts.length; i++) {
      const cid = ids[i];
      let col;
      if (state.color === "flags") {
        const rf = f.ref.charCodeAt(i) === 49, tl = f.tall.charCodeAt(i) === 49, px = f.proxyFlag.charCodeAt(i) === 49;
        col = tl ? "#3fae72" : rf ? "#4a7bd0" : px ? "#d0a75a" : "#4c5058";
      } else if (state.color === "acomp" && aIds) {
        col = compColor(aIds[i]);
      } else {
        col = compSet.has(cid) ? compColor(cid) : "#3a3d43";
      }
      if (sel !== undefined && cid !== sel && compSet.has(cid)) {
        ctx.globalAlpha = 0.18;
      } else ctx.globalAlpha = 1;
      const p = projPt(f, pts[i][0], pts[i][1], pts[i][2], state.view);
      ctx.fillStyle = col;
      ctx.fillRect(fitv.ox + p[0]*fitv.s, fitv.oy + p[1]*fitv.s, 2, 2);
    }
    ctx.globalAlpha = 1;
    /* person comp 青色框 + 选中白框 */
    const personRow = (v.detail && v.detail.person_raw >= 0) ? v.comps.find(c => c.id === v.detail.person_raw) : null;
    for (const [row, col] of [[personRow, "#3ad0c8"], [sel !== undefined ? v.comps.find(c => c.id === sel) : null, "#ffffff"]]) {
      if (!row || !row.bbox) continue;
      ctx.strokeStyle = col; ctx.lineWidth = 1.2; ctx.setLineDash(col === "#ffffff" ? [] : [4,3]);
      const [x0,x1,y0,y1,z0,z1] = row.bbox;
      for (const [ax,ay,az,bx,by,bz] of [
        [x0,y0,z0,x1,y0,z0],[x1,y0,z0,x1,y1,z0],[x1,y1,z0,x0,y1,z0],[x0,y1,z0,x0,y0,z0],
        [x0,y0,z1,x1,y0,z1],[x1,y0,z1,x1,y1,z1],[x1,y1,z1,x0,y1,z1],[x0,y1,z1,x0,y0,z1],
        [x0,y0,z0,x0,y0,z1],[x1,y0,z0,x1,y0,z1],[x1,y1,z0,x1,y1,z1],[x0,y1,z0,x0,y1,z1]]) {
        const qA = projPt(f, ax, ay, az, state.view), qB = projPt(f, bx, by, bz, state.view);
        ctx.beginPath(); ctx.moveTo(fitv.ox + qA[0]*fitv.s, fitv.oy + qA[1]*fitv.s);
        ctx.lineTo(fitv.ox + qB[0]*fitv.s, fitv.oy + qB[1]*fitv.s); ctx.stroke();
      }
      ctx.setLineDash([]);
    }
    const d = v.detail || {};
    cells[vn].info.textContent = "raw " + (d.raw ?? "?") + " · filt " + (d.filtered ?? "?") + " · frag " + (d.frag ?? "?")
      + " · sel# " + (sel === undefined ? "—" : sel)
      + " · person proxy=" + (d.person_raw !== undefined && d.person_raw >= 0 && d.person_points !== undefined ? d.person_points : "—")
      + " · retention " + (d.retention !== null && d.retention !== undefined ? d.retention : "—")
      + (d.diff ? " · A→split " + d.diff.splits + "(" + d.diff.split_pts + "pts)" : "");
  }
  renderSide();
}

function renderSide() {
  const f = frame();
  const rows = [];
  rows.push("<table><tr><th>variant</th><th>raw</th><th>filt</th><th>frag&lt;3</th><th>disc pts</th><th>split(A)</th><th>merge(A)</th><th>person n</th><th>ret</th></tr>");
  for (const vn of VAR_ORDER) {
    const v = f.variants[vn]; if (!v) continue;
    const d = v.detail || {};
    rows.push("<tr><td><b>" + vn + "</b></td><td>" + (d.raw ?? "?") + "</td><td>" + (d.filtered ?? "?") + "</td><td>" + (d.frag ?? "?")
      + "</td><td>" + (d.discarded ?? "?") + "</td><td>" + (d.diff ? d.diff.splits : (vn==="A"?0:"?")) + "</td><td>"
      + (d.diff ? d.diff.merges : (vn==="A"?0:"?")) + "</td><td>" + (d.person_points ?? "—") + "</td><td>" + (d.retention ?? "—") + "</td></tr>");
  }
  rows.push("</table>");
  const dA = (f.variants.A && f.variants.A.detail) || {};
  if (dA.contact) rows.push("<div class='muted'>A contact edges(tall跨边)=" + dA.contact.edges + " (cross " + dA.contact.cross + ")"
    + (dA.cut && !dA.cut.skipped ? " · A person/large comp cuts=" + dA.cut.cut_count + "/" + dA.cut.V + " bf=" + dA.cut.bridge_fraction : "") + "</div>");
  document.getElementById("stats").innerHTML = rows.join("");
}

function pick(vn, ev) {
  const f = frame(), v = f.variants[vn];
  const rect = cells[vn].canvas.getBoundingClientRect();
  const mx = (ev.clientX - rect.left) * (cells[vn].canvas.width / rect.width);
  const my = (ev.clientY - rect.top) * (cells[vn].canvas.height / rect.height);
  const fitv = fit(cells[vn].canvas, f.points, state.view);
  let best = null, bestD = 14*14;
  const ids = v.ids, pts = f.points;
  for (let i = 0; i < pts.length; i++) {
    const p = projPt(f, pts[i][0], pts[i][1], pts[i][2], state.view);
    const dx = fitv.ox + p[0]*fitv.s - mx, dy = fitv.oy + p[1]*fitv.s - my;
    const d2 = dx*dx + dy*dy;
    if (d2 < bestD) { bestD = d2; best = i; }
  }
  if (best === null) return;
  const cid = ids[best];
  state.sel[vn] = cid;
  const row = v.comps.find(c => c.id === cid);
  const aId = f.variants.A ? f.variants.A.ids[best] : -1;
  const xs = Object.values(state.sel);
  const el = document.getElementById("sel");
  el.classList.remove("muted");
  el.innerHTML = "<b>" + vn + " · component #" + cid + "</b><br>"
    + (row ? ("n=" + row.n + " · nodes=" + row.nodes + " · bbox=" + JSON.stringify(row.bbox)
        + "<br>label=" + row.label + " / " + row.ev + " / " + row.joint + " · ref=" + row.ref
        + " · upper=" + row.up) : "<span class='muted'>&lt;3 节点（被 min_voxels 丢弃；无下游行）</span>")
    + "<br>该点 A 分区 = #" + aId
    + (v.detail && v.detail.diff && v.detail.diff.detail ? "<br><span class='muted'>A→split 事件: " + JSON.stringify(v.detail.diff.detail.slice(0,2)) + "</span>" : "");
  render();
}
render();
</script>
</body>
</html>
`;
fs.writeFileSync(path.join(HERE, "12_ab_debug.html"), html);
console.log("[debug] wrote 12_ab_debug.html  (" + html.length + " bytes)");
