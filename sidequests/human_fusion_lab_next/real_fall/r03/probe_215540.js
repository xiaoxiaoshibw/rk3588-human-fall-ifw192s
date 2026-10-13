"use strict";
/**
 * HF-REAL-03 任务3：215540 静立吞人定量画像（v2 融合规则下按部位删/存对照）。
 * 复用 fusion_v2_ab_r1 同一份 loader/registration/PIPE，只追加按身高分组的部位统计与 mask 渲染（用 gnuplot/无图形库 => 只输出 JSON + 自制 SVG）。
 * ponytail：单脚本，不写 reusable lib。
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const R  = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));
const M  = require(path.join(ROOT, "pc_apps/human_replay/registration_method.js"));

const OUT = path.resolve(__dirname, "out");
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

const SID = "cap_20261007_215540", JOB = "21666bec7e7b44b2bdbbaa790bf4501b";
const REF_SID = "cap_20261007_233658", REF_JOB = "3c793d7bda0f4ced86b20ac8076e7b0e";
const CENTER = [2.10, -0.57], RADIUS = 0.55, ZLO = 0.10, ZHI = 2.30;
const BANDS = [ ["legs", 0.10, 0.70], ["torso", 0.70, 1.30], ["shoulders", 1.30, 1.60], ["head", 1.60, 2.00] ];

function leveling(root, sid, job) {
  try { return R.levelingBinding(root, sid, job); }
  catch (e) {
    const dir = path.join(root, "captures/leveled", job);
    const tf = JSON.parse(fs.readFileSync(path.join(dir, "tls/transform.json"), "utf8"));
    return { tf };
  }
}

// 参考层 233658 已不在本机/板上（板上仅有 215540），registration JSON 因背景参考漂移而 STALE。
// 但 online 静态背景本身就是吞人主责；改用 P 臂（online-only）呈现"被吞部位"。
const sl = leveling(ROOT, SID, JOB);
const rawFrames = R.loadFrames(ROOT, SID, sl).frames;
const clouds = rawFrames;   // leveling 已含在 leveled session buffer，无需 registration

const clean = clouds.map(PL.denoise);
const online = PL.build_static_map(clean);
const center = CENTER;   // union 臂 center 与本段水平面坐标一致（fusion_v2_ab 实测）
const refkeys = null;    // 不需要参考层
const refHits = () => null;

const MATCH_R2 = PL.PIPE.bg_match_radius ** 2, BGB = 8192, BGO = 4096;
const bgKey = (ix, iy, iz) => ((ix + BGO) * BGB + (iy + BGO)) * BGB + (iz + BGO);
function match(map, x, y, z) {
  const ix = Math.floor(x / PL.PIPE.bg_voxel_xy), iy = Math.floor(y / PL.PIPE.bg_voxel_xy), iz = Math.floor(z / PL.PIPE.bg_voxel_z);
  for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
    const rec = map.get(bgKey(ix + a, iy + b, iz + c));
    if (!rec) continue;
    const dx = rec.x - x, dy = rec.y - y, dz = rec.z - z;
    if (dx * dx + dy * dy + dz * dz < MATCH_R2) return rec;
  }
  return null;
}

const onlineVox = online;   // build_static_map 直接返回 Map<key,{x,y,z,hits,tier}>
const perBand = {}; BANDS.forEach(([b]) => perBand[b] = { survived: 0, removed: 0 });
const mask = [];            // [x,y,z,survived]
const frameStats = [];

const voxOfRec = (v) => ({ x: v.x, y: v.y, z: v.z });

for (let fi = 0; fi < clean.length; fi++) {
  const c = clean[fi];
  let inRegion = 0, survived = 0;
  for (let k = 0; k < c.length; k += 4) {
    const x = c[k], y = c[k + 1], z = c[k + 2];
    const inPerson = (x - center[0]) ** 2 + (y - center[1]) ** 2 <= RADIUS * RADIUS && z >= ZLO && z <= ZHI;
    if (!inPerson) continue;
    inRegion++;
    const onHit = match(onlineVox, x, y, z);
    // P 臂：仅在线静态背景命中即删（删=被吞），不命中即存（存=前景点）
    const kept = !onHit;
    const band = BANDS.find(([, lo, hi]) => z >= lo && z < hi);
    if (kept) { survived++; if (band) perBand[band[0]].survived++; }
    else if (band) perBand[band[0]].removed++;
    mask.push([x, y, z, kept ? 1 : 0]);
  }
  frameStats.push({ fi, inRegion, survived });
}

const totalS = Object.values(perBand).reduce((a, d) => a + d.survived, 0);
const totalR = Object.values(perBand).reduce((a, d) => a + d.removed, 0);

// 写 JSON
fs.writeFileSync(path.join(OUT, "215540_frame_stats.json"), JSON.stringify({
  sid: SID, ref_sid: REF_SID,
  center, radius: RADIUS, zRange: [ZLO, ZHI],
  bands: BANDS.map(([band, lo, hi]) => ({ band, zlo: lo, zhi: hi })),
  per_band: perBand,
  total: { survived: totalS, removed: totalR },
  frameStats,
  note: "kept = v2 rule: refHit || (onHit && refSup); removed = else",
}, null, 1));

// 同时只把 mask (x,y,z,surv) 导出 JSON，供 Python matplotlib 渲染 —— SVG 二进制到 PNG 无合适的本地转换器。
fs.writeFileSync(path.join(OUT, "215540_mask.json"), JSON.stringify(mask));

// 简易 SVG mask 渲染（top + side）
function svg(points, ax0, ax1, name) {
  const W = 700, H = 500, PAD = 40;
  const xs = points.map(p => p[ax0]), ys = points.map(p => p[ax1]);
  const xmin = Math.min(...xs), xmax = Math.max(...xs);
  const ymin = Math.min(...ys), ymax = Math.max(...ys);
  const sx = x => PAD + (x - xmin) * (W - 2 * PAD) / Math.max(1e-6, xmax - xmin);
  const sy = y => H - PAD - (y - ymin) * (H - 2 * PAD) / Math.max(1e-6, ymax - ymin);
  const colSurv = "#20a592", colRem = "#d64541";
  let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}"><rect width="100%" height="100%" fill="#f4f4f4"/>`;
  for (const [x, y, z, st] of points) {
    s += `<circle cx="${sx(eval(ax0 === 0 ? 'x' : ax0 === 1 ? 'y' : 'z')).toFixed(1)}" cy="${sy(eval(ax1 === 0 ? 'x' : ax1 === 1 ? 'y' : 'z')).toFixed(1)}" r="1.5" fill="${st ? colSurv : colRem}" fill-opacity="${st ? 0.6 : 0.4}"/>`;
  }
  s += `<text x="${PAD}" y="${PAD - 10}" font-size="13">${name} — green=survived, red=removed (v2). total=${points.length}</text></svg>`;
  return s;
}

fs.writeFileSync(path.join(OUT, "215540_mask_top.svg"),  svg(mask, 0, 1, `${SID} top-view`));
fs.writeFileSync(path.join(OUT, "215540_mask_side.svg"), svg(mask, 0, 2, `${SID} side-view`));

console.log(JSON.stringify({
  sid: SID, frames: clean.length, inRegionTotal: totalS + totalR,
  survivedV2: totalS, removedV2: totalR,
  per_band: perBand,
  out_json: "215540_frame_stats.json",
  out_svgs: ["215540_mask_top.svg", "215540_mask_side.svg"],
}, null, 1));
