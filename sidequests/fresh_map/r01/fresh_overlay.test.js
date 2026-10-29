// fresh_overlay.js 冒烟测（node，假 S 对象走真管线；浏览器交互面由目视验收覆盖）
// 运行：node fresh_overlay.test.js
"use strict";
const fs = require("fs");
globalThis.human_pipe_lib = require("../../../pc_apps/human_replay/human_pipe_lib.js");
globalThis.fresh_map_lib = require("./fresh_lib.js");
globalThis.human_replay_lib = require("../../../pc_apps/human_replay/human_replay_lib.js");
new Function(fs.readFileSync("./fresh_overlay.js", "utf8"))();

const P = globalThis.human_pipe_lib, FRESH = globalThis.FRESH_INTERNAL;
let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("ok  " + name); }
  catch (e) { failed++; console.log("FAIL " + name + "\n  " + e.stack); }
}
function ok(cond, msg) { if (!cond) throw new Error(msg || "断言失败"); }

function rng(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6D2B79F5) | 0; let z = Math.imul(a ^ (a >>> 15), 1 | a);
    z = (z + Math.imul(z ^ (z >>> 7), 61 | z)) ^ z; return ((z ^ (z >>> 14)) >>> 0) / 4294967296; };
}
function wardrobePts(n, seed) {
  const R = rng(seed), o = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    o[i * 4] = 5 + (R() - 0.5) * 0.9; o[i * 4 + 1] = 5 + (R() - 0.5) * 0.65;
    o[i * 4 + 2] = 0.02 + R() * 1.9; o[i * 4 + 3] = 60;
  }
  return P.denoise(o);
}
/* 人形柱：XY ~0.3m（跨 3 柱过 cluster_min_voxels）高 1.3m（过 classify_human 门） */
function personPts(n, seed) {
  const R = rng(seed), o = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    o[i * 4] = 10 + (R() - 0.5) * 0.3; o[i * 4 + 1] = 10 + (R() - 0.5) * 0.3;
    o[i * 4 + 2] = 0.3 + R() * 1.3; o[i * 4 + 3] = 90;
  }
  return P.denoise(o);
}

const NPC = 160, BGC = 40, NF = 420;
/* 参考图 = 衣柜空场（致密：8 帧 ×600 点） */
FRESH.set_ref_frames([0, 1, 2, 3, 4, 5, 6, 7].map((_, i) => wardrobePts(600, 500 + i)), "test-ref");

const total = (NPC + BGC) * NF;
const buf = new Float32Array(total * 7);
const frames = [];
let off = 0;
const wfr = wardrobePts(BGC, 900), pfr = personPts(NPC, 1000);   /* 完全静止的人 = 固定点云 */
for (let i = 0; i < NF; i++) {
  for (let k = 0; k < NPC; k++) {
    const o = (off + k) * 7;
    buf[o] = pfr[k * 4]; buf[o + 1] = pfr[k * 4 + 1]; buf[o + 2] = pfr[k * 4 + 2]; buf[o + 3] = pfr[k * 4 + 3];
  }
  for (let k = 0; k < BGC; k++) {
    const o = (off + NPC + k) * 7;
    buf[o] = wfr[k * 4]; buf[o + 1] = wfr[k * 4 + 1]; buf[o + 2] = wfr[k * 4 + 2]; buf[o + 3] = wfr[k * 4 + 3];
  }
  frames.push({ offset_points: off, count_points: NPC + BGC, bag_time_sec: i * 0.1 });
  off += NPC + BGC;
}
const meta = { session_id: "synth", point_stride_bytes: 28, leveling: { note: "test-leveled" }, frames };
const colorArr = new Float32Array(total * 3);
const S = { meta, idx: 0, session_gen: 0, buf_f32: buf, geo: { attributes: { color: { needsUpdate: false } } } };
const OV = globalThis.HUMAN_DETECT_OVERLAY;
S.session_gen = OV.notify_session();
OV.attach_color({ array: colorArr });   /* 兼容形态 1：BufferAttribute */
OV.set_leveled_in_s(true);

function playTo(n) { for (let i = 0; i <= n; i++) { S.idx = i; OV.on_frame(S); } }
function segColors(i, from, to) {
  const out = [];
  for (let k = from; k < to; k++) {
    const b = (frames[i].offset_points + k) * 3;
    out.push([colorArr[b], colorArr[b + 1], colorArr[b + 2]]);
  }
  return out;
}
const dimCyan = c => c[0] < 0.20 && c[1] > 0.12 && c[1] < 0.6;   /* 未认领 HOT = 暗青证据 */
const bright = c => c[0] > 0.9;                             /* 认领 HOT = 热白对象 */
const claimBlue = c => c[2] > 0.7 && c[0] < 0.4;            /* 认领 GHOST = 亮青蓝 */

t("r4 分层：刚发火只有淡青证据（未被认领），背景不冒充对象", () => {
  playTo(2);   /* evconf3：第 3 帧（idx2）才发火 */
  const dim = segColors(2, 0, NPC).filter(dimCyan).length;
  ok(dim >= NPC * 0.5, "人点淡青证据 got " + dim + "/" + NPC);
  const white = segColors(2, 0, NPC).filter(bright).length;
  ok(white === 0, "3 帧人形确认前不许亮白 got " + white);
  const bgWhite = segColors(2, NPC, NPC + BGC).filter(bright).length;
  ok(bgWhite === 0, "背景绝不亮白 got " + bgWhite);
});

t("3 帧过人形门+确认后升级亮白（对象认领）", () => {
  playTo(6);
  const white = segColors(6, 0, NPC).filter(bright).length;
  ok(white >= NPC * 0.5, "人形锚点认领应亮白 got " + white + "/" + NPC);
  ok(FRESH.mem().anchors.length >= 1, "应有锚点");
});

t("静止 40s（超 GHOST ttl）：身份由锚点保有——弱蓝'人还在这'、HOT 归零、点不删", () => {
  playTo(399);
  const dim = segColors(399, 0, NPC).filter(c => c[2] > 0.2 && c[0] < 0.1).length;
  ok(dim >= NPC * 0.5, "超寿认领=弱蓝 got " + dim + "/" + NPC);
  const rep = FRESH.lastRep();
  ok(rep.n_hot === 0, "HOT 应归零 got " + rep.n_hot);
  ok(rep.n_ghost === 0, "GHOST 应已超寿沉入背景 got " + rep.n_ghost);
});

t("reset 后新人出现：淡青→过人形门→亮白（evconf3 时序）", () => {
  OV.reset();
  const pb = personPts(NPC, 4242);   /* 固定点云站在 (11,11) */
  for (let i = 0; i < NF; i++) {
    const base = frames[i].offset_points;
    for (let k = 0; k < NPC; k++) {
      const o = (base + k) * 7;
      buf[o] = pb[k * 4] + 1; buf[o + 1] = pb[k * 4 + 1] + 1;
    }
  }
  playTo(2);
  ok(segColors(2, 0, NPC).filter(bright).length === 0, "刚发火不该立刻亮白（证据≠对象）");
  playTo(8);
  ok(segColors(8, 0, NPC).filter(bright).length >= NPC * 0.5, "过门+确认后亮白");
});

t("矮趴散碎簇（桌角型）永远过不了人形门 → 不会亮白", () => {
  OV.reset();
  const R = rng(11), tab = new Float32Array(NPC * 4);   /* 固定矮平台：0.8m 宽 × 0.3m 高 */
  for (let i = 0; i < NPC; i++) {
    tab[i * 4] = 12 + (R() - 0.5) * 0.8; tab[i * 4 + 1] = 12 + (R() - 0.5) * 0.8;
    tab[i * 4 + 2] = 0.15 + R() * 0.3; tab[i * 4 + 3] = 50;
  }
  for (let i = 0; i < NF; i++) {
    const base = frames[i].offset_points;
    for (let k = 0; k < NPC; k++) {
      const o = (base + k) * 7;
      buf[o] = tab[k * 4]; buf[o + 1] = tab[k * 4 + 1]; buf[o + 2] = tab[k * 4 + 2]; buf[o + 3] = tab[k * 4 + 3];
    }
  }
  playTo(10);
  const st_now = FRESH.state();
  let fired = 0; st_now.voxels.forEach(v => { if (v.ever_event) fired++; });
  ok(fired > 0, "前提：桌角确实在发火（否则测试无意义）fired=" + fired);
  ok(segColors(10, 0, NPC).filter(bright).length === 0, "桌角型簇不许亮白");
  ok(FRESH.mem().anchors.length === 0, "桌角型簇不许进人形锚点 got " + FRESH.mem().anchors.length);
});

t("attach_color 契约对账：replay.js 实传裸数组（r8 定案的回归锚，置末避免污染时序）", () => {
  const probe = new Float32Array(colorArr.length);
  OV.attach_color(probe);               /* 裸数组 = replay L235 真实形态 */
  S.idx = 0; OV.on_frame(S);
  let nonblack = 0;
  const f = frames[0];
  for (let k = 0; k < f.count_points; k++) if (probe[(f.offset_points + k) * 3 + 1] !== 0) nonblack++;
  ok(nonblack > 0, "裸数组形态下 _paint 必须写色（静默跳过=r8 事故）");
  OV.attach_color({ array: colorArr });
});

t("站立确认→倒地→静卧40s保持身份；reset后同一低姿不建身份", () => {
  OV.reset();
  function writePose(first, last, low) {
    for (let i = first; i <= last; i++) for (let k = 0; k < NPC; k++) {
      const o = (frames[i].offset_points + k) * 7;
      const x = pfr[k * 4], y = pfr[k * 4 + 1], z = pfr[k * 4 + 2];
      buf[o] = low ? 10 + (z - 0.95) * 0.7 : x;
      buf[o + 1] = y; buf[o + 2] = low ? 0.38 + (x - 10) : z;
    }
  }
  writePose(0, 9, false); writePose(10, NF - 1, true);
  playTo(9);
  const parent = FRESH.mem().anchors.find(a => a.confirmations >= 3);
  ok(parent, "站立先确认");
  for (let i = 10; i < NF; i++) { S.idx = i; OV.on_frame(S); }
  ok(FRESH.mem().anchors.includes(parent) && parent.frame_index === NF - 1, "同一锚点持续续接");
  ok(segColors(NF - 1, 0, NPC).filter(claimBlue).length >= NPC * 0.5, "超HOT/GHOST期限低姿仍有可见蓝色");
  ok(segColors(NF - 1, NPC, NPC + BGC).every(c => c[0] < 0.1 && c[2] < 0.2), "家具不被低姿认领点亮");
  OV.reset();
  for (let i = 10; i < 30; i++) { S.idx = i; OV.on_frame(S); }
  ok(FRESH.mem().anchors.length === 0, "没有站立历史的低姿不能新建身份");
});

t("低姿续接拒绝远处、过期、背景证据不足和双向歧义", () => {
  const a = { x:10, y:10, frame_index:30, timestamp:3, confirmations:3, standing_z:1, standing_height:1.5 };
  const row = { f: {ok:true, cx:10, cy:10, cz:0.4, height_m:0.4, zmax:0.6, radius_m:0.3, n:100},
    evidenceN:100, keys:[] };
  FRESH.mem().anchors = [a];
  const match = (rows, live=[a], idx=31, t=3.1) => FRESH.continuations(rows, live, [], idx, t);
  ok(match([row]).length === 1, "前提：唯一近邻接受");
  ok(FRESH.continuations([row], [a], [{cx:10,cy:10}], 31, 3.1).length === 0,
    "同一身份已有站姿候选时不接另一个低姿簇");
  ok(match([{...row, f:{...row.f,cx:12}}]).length === 0, "远处拒接");
  ok(match([row], [a], 51, 5.1).length === 0, "超过2s/20帧拒接");
  ok(match([row], [a], 31, 6).length === 0, "真实时间过期拒接");
  ok(match([row], [a], 30, 3).length === 0, "重复/逆序帧拒接");
  ok(match([{...row,evidenceN:1}]).length === 0, "不凭少量振动证据续接背景簇");
  ok(match([{...row,f:{...row.f,cz:0.9}}]).length === 0, "没有重心下降不能当低姿续接");
  a.standing_height = 0.5;
  ok(match([row]).length === 0, "没有形态降低不能续接");
  a.standing_height = 1.5;
  ok(match([row,{...row}]).length === 0, "一个锚点邻近两个低姿簇拒接");
  const b = {...a,x:10.1}; FRESH.mem().anchors.push(b);
  ok(match([row],[a,b]).length === 0, "一个簇邻近两个身份拒接");
  ok(match([row],[a]).length === 0, "附近未确认锚点同样拒绝身份竞争");
  OV.reset(); ok(FRESH.mem() === null, "reset清除身份");
});

console.log("\n" + passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);
