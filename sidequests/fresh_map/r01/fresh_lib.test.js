// fresh_lib.js 单测（node 环境，零三方依赖）。运行：node fresh_lib.test.js
"use strict";
const F = require("./fresh_lib.js");
const P = require("../../../pc_apps/human_replay/human_pipe_lib.js");

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("ok  " + name); }
  catch (e) { failed++; console.log("FAIL " + name + "\n  " + e.stack); }
}
function ok(cond, msg) { if (!cond) throw new Error(msg || "断言失败"); }
function close(a, b, eps, msg) { if (!(Math.abs(a - b) <= eps)) throw new Error((msg || "近似失败") + " " + a + " vs " + b); }

function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) | 0;
    let z = Math.imul(a ^ (a >>> 15), 1 | a);
    z = (z + Math.imul(z ^ (z >>> 7), 61 | z)) ^ z;
    return ((z ^ (z >>> 14)) >>> 0) / 4294967296;
  };
}

/* 衣柜（ref 素材）：z 0.02..1.95 大柱 */
function wardrobe(cx, cy, n, seed) {
  const R = rng(seed || 3), o = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    o[i * 4] = cx + (R() - 0.5) * 0.9; o[i * 4 + 1] = cy + (R() - 0.5) * 0.65;
    o[i * 4 + 2] = 0.02 + R() * 1.93; o[i * 4 + 3] = 60;
  }
  return o;
}
/* 物体团块：以 (cx,cy,cz) 为心半径 ~0.2（跨数个体素，每格 ≥2 点） */
function blob(cx, cy, cz, n, seed, dx) {
  dx = dx || 0;
  const R = rng(seed || 9), o = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    o[i * 4] = cx + dx + (R() - 0.5) * 0.2; o[i * 4 + 1] = cy + (R() - 0.5) * 0.2;
    o[i * 4 + 2] = cz + (R() - 0.5) * 0.2; o[i * 4 + 3] = 90;
  }
  return o;
}
/* sparkle：m 个互不同体素的孤立单点（网格化散布保证不同格） */
function sparkle(m, seed) {
  const R = rng(seed || 77), o = [];
  for (let i = 0; i < m; i++) {
    o.push(2 + Math.floor(R() * 60) * 0.31, 2 + Math.floor(R() * 60) * 0.37,
           0.3 + Math.floor(R() * 20) * 0.29, 40);
  }
  return new Float32Array(o);
}
function cat(...arrs) {
  const n = arrs.reduce((s, a) => s + a.length, 0), o = new Float32Array(n);
  let c = 0; for (const a of arrs) { o.set(a, c); c += a.length; }
  return o;
}
/* 单体素点集：全部落在 cell floor(20/.15)=133, floor(20/.15)=133, floor(1/.12)=8 内 */
function cell_pts(cx, cy, cz, n, seed) {
  const R = rng(seed || 21), o = new Float32Array(n * 4);
  const vx = Math.floor(cx / P.PIPE.bg_voxel_xy) * P.PIPE.bg_voxel_xy,
        vy = Math.floor(cy / P.PIPE.bg_voxel_xy) * P.PIPE.bg_voxel_xy,
        vz = Math.floor(cz / P.PIPE.bg_voxel_z) * P.PIPE.bg_voxel_z;
  for (let i = 0; i < n; i++) {
    o[i * 4] = vx + 0.02 + R() * (P.PIPE.bg_voxel_xy - 0.04);
    o[i * 4 + 1] = vy + 0.02 + R() * (P.PIPE.bg_voxel_xy - 0.04);
    o[i * 4 + 2] = vz + 0.02 + R() * (P.PIPE.bg_voxel_z - 0.04);
    o[i * 4 + 3] = 90;
  }
  return o;
}
function refFromScene() {
  const fr = [];
  for (let i = 0; i < 10; i++) fr.push(P.denoise(wardrobe(5, 5, 400, 100 + i)));
  return F.build_reference(fr, {});
}
function mk(ref, opts) { return F.create_fresh_state(ref || refFromScene(), opts || {}); }
function at(i) { return i * 0.1; }   /* 10Hz 真实秒 */
function gv(st, x, y, z) { return st.voxels.get(P.key_bg(x, y, z)); }

/* ---------- 事件判据 ---------- */

t("单点 sparkle 永不发火（支持门 n≥2）", () => {
  const st = mk();
  for (let i = 0; i < 30; i++) {
    const rep = F.fresh_update(st, sparkle(60, 500 + i), at(i));
    ok(rep.n_event_fired === 0, "frame " + i + " fired=" + rep.n_event_fired);
  }
  st.voxels.forEach(v => ok(!v.ever_event, "存在 ever_event 体素"));
});

t("新出现物体连续 2 帧才发火（滞回）", () => {
  const st = mk();
  let rep = F.fresh_update(st, blob(20, 20, 1.0, 40, 1), at(0));
  ok(rep.n_event_fired === 0, "首帧不应发火");
  rep = F.fresh_update(st, blob(20, 20, 1.0, 40, 2), at(1));
  ok(rep.n_event_fired >= 1, "第 2 帧应发火 fired=" + rep.n_event_fired);
});

t("闪现型 sparkle（隔空帧重现）不发火", () => {
  const st = mk();
  for (let i = 0; i < 12; i++) {
    const fr = (i % 2 === 0) ? blob(21, 21, 1.0, 40, 300 + i) : new Float32Array(0);
    F.fresh_update(st, fr, at(i));
  }
  st.voxels.forEach(v => ok(!v.ever_event, "隔帧出现不应累计发火"));
});

t("静止新物体：亮一次 → 渐黑 → GHOST（ttl 内点仍进候选）→ 超寿沉入背景", () => {
  const st = mk();
  F.fresh_update(st, blob(20, 20, 1.0, 40, 1), at(0));
  const rep2 = F.fresh_update(st, blob(20, 20, 1.0, 40, 2), at(1));
  ok(rep2.n_event_fired >= 1, "应发火");
  const v = gv(st, 20, 20, 1.0);
  ok(v.f === 1 && v.ever_event, "发火后 f=1");
  for (let i = 2; i < 100; i++) F.fresh_update(st, blob(20, 20, 1.0, 40, 1000 + i), at(i));
  close(v.f, Math.exp(-9.8 / F.FP.tau_s), 1e-3, "发火于 t=0.1，至 9.9s 共衰减 9.8s");
  ok(F.voxel_state(st, P.key_bg(20, 20, 1.0)) === "HOT", "10s 时仍 HOT");
  for (let i = 100; i < 170; i++) F.fresh_update(st, blob(20, 20, 1.0, 40, 2000 + i), at(i));
  ok(v.f < F.FP.hot_f_min, "17s 应已冷却 f=" + v.f);
  ok(F.voxel_state(st, P.key_bg(20, 20, 1.0)) === "GHOST", "ttl 内应 GHOST");
  const cand = F.candidate_xyzi(st, blob(20, 20, 1.0, 40, 7), null);
  ok(cand.length / 4 > 0, "GHOST 点必须仍在候选集");
  /* r7.1：GHOST 有寿命（ttl=20s）——超寿沉入 COLD_BG；身份由锚点层（ever_event 证据）保留 */
  for (let i = 170; i < 400; i++) F.fresh_update(st, blob(20, 20, 1.0, 40, 3000 + i), at(i));
  ok(F.voxel_state(st, P.key_bg(20, 20, 1.0)) === "COLD_BG", "超 ttl 应沉入 COLD_BG");
  ok(v.ever_event && !v.ref_sup, "证据位仍在（锚点续命语义 r7.1）");
  ok(F.candidate_xyzi(st, blob(20, 20, 1.0, 40, 8), null).length === 0, "超寿无锚点时不进候选");
});

t("r7 锚点证据门：ev=false 簇不建锚、不续命（防自吞）", () => {
  const mem = F.FreshMemory();
  const r = F.mem_tick(mem, [{ cx: 1, cy: 1, cz: 1, n: 50, ev: false }], 0, 0);
  ok(r.n_total === 0, "无证据簇不得建锚");
  F.mem_tick(mem, [{ cx: 1, cy: 1, cz: 1, n: 50, ev: true }], 0, 0);
  F.mem_tick(mem, [{ cx: 1, cy: 1, cz: 1, n: 50, ev: true }], 1, 0.1);
  F.mem_tick(mem, [{ cx: 1, cy: 1, cz: 1, n: 50, ev: true }], 2, 0.2);
  ok(F.mem_live(mem).length === 1, "有证据 3 连应 live");
  F.mem_tick(mem, [{ cx: 1, cy: 1, cz: 1, n: 50, ev: false }], 3, 0.3);
  ok(F.mem_live(mem)[0].confirmations === 3, "无证据帧不得续命（confirmations 停在最后证据帧）");
  for (let i = 4; i <= 33; i++) F.mem_tick(mem, [], i, i * 0.1);
  ok(F.mem_live(mem).length === 0 && mem.anchors.length === 0, "断证据超 max_lost_for_retain 到期清除");
});

t("走回头路：旧位 GHOST 不重亮但保住候选，新位置照常发火", () => {
  const st = mk();
  for (let i = 0; i < 160; i++) F.fresh_update(st, blob(20, 20, 1.0, 40, i), at(i));   /* ttl 内 */
  ok(F.voxel_state(st, P.key_bg(20, 20, 1.0)) === "GHOST", "先成 GHOST");
  /* 移到 0.5m 外（不同体素）：新格 2 帧发火 */
  let rep = F.fresh_update(st, blob(20.5, 20, 1.0, 40, 41), at(160));
  rep = F.fresh_update(st, blob(20.5, 20, 1.0, 40, 42), at(161));
  ok(rep.n_event_fired >= 1, "新位置应发火");
  /* 旧 GHOST 格上若还有点（比如脚），候选集仍收（不靠 HOT） */
  const cand = F.candidate_xyzi(st, blob(20, 20, 1.0, 40, 9), null);
  ok(cand.length / 4 > 0, "GHOST 旧位点应仍是候选");
});

t("HOT 期慢参考/占用 EMA 冻结，冷却后恢复吸收", () => {
  const st = mk();
  st.o.move_tol_m = 1.0;                     /* 白盒：位移门不可达，隔离出 EMA 行为本身 */
  F.fresh_update(st, blob(20, 20, 1.0, 40, 1), at(0));
  F.fresh_update(st, blob(20, 20, 1.0, 40, 2), at(1));
  const v = gv(st, 20, 20, 1.0);
  v.f = 1; v.event_run = 0;                  /* 白盒：确保 HOT（刚已发火，ever_event 已 true） */
  v.rx -= 0.03; v.ry += 0.03; v.rz -= 0.03;  /* 慢参考与当前形心失配，只有冻结才能保持不动 */
  const rx0 = v.rx, ry0 = v.ry, rz0 = v.rz;
  for (let i = 2; i < 10; i++) {
    F.fresh_update(st, blob(20, 20, 1.0, 40, 50 + i), at(i));
    ok(v.f >= F.FP.hot_f_min, "应仍 HOT");
    ok(v.rx === rx0 && v.ry === ry0 && v.rz === rz0, "HOT 期慢参考被改动（=静立吞人机理）");
  }
  v.f = 0.1;                                 /* 白盒冷却 */
  for (let i = 10; i < 40; i++) F.fresh_update(st, blob(20, 20, 1.0, 40, 90 + i), at(i));
  ok(Math.abs(v.rx - rx0) > 0.005, "冷却后慢参考应向当前形心吸收 got=" + (v.rx - rx0));
});

t("ref 支撑体素：静止永不发火；冷却态归 COLD_BG 而非 GHOST", () => {
  const st = mk();
  F.fresh_update(st, blob(20, 20, 1.0, 40, 1), at(0));
  const key = P.key_bg(20, 20, 1.0), v = st.voxels.get(key);
  v.ref_sup = true;                              /* 白盒：模拟人坐上椅面（与家具融合位） */
  v.ever_event = false; v.event_run = 0; v.f = 0;
  for (let i = 1; i < 31; i++) F.fresh_update(st, blob(20, 20, 1.0, 40, 200 + i), at(i));
  ok(!v.ever_event, "ref 支撑静止体素不应发火");
  ok(F.voxel_state(st, key) === "COLD_BG", "应 COLD_BG");
  v.ever_event = true;                           /* 白盒：即便曾发过事，ref 支撑优先 COLD_BG */
  ok(F.voxel_state(st, key) === "COLD_BG", "ref_sup+ever_event 仍须 COLD_BG（state 分支次序）");
});

t("τ 衰减表值（exp 与 linear）", () => {
  const fire = (st) => {
    F.fresh_update(st, blob(20, 20, 1.0, 40, 1), 0);
    F.fresh_update(st, blob(20, 20, 1.0, 40, 2), 1);   // t=1s 发火
  };
  const s1 = mk(); fire(s1);
  const v1 = gv(s1, 20, 20, 1.0);
  F.fresh_update(s1, new Float32Array(0), 9);          // +8s = 一τ
  close(v1.f, Math.exp(-1), 1e-9, "exp 一τ");
  const s2 = mk(null, { decay: "linear" }); fire(s2);
  const v2 = gv(s2, 20, 20, 1.0);
  F.fresh_update(s2, new Float32Array(0), 5);          // +4s = 半τ
  close(v2.f, 0.5, 1e-9, "linear 半τ");
  F.fresh_update(s2, new Float32Array(0), 9);
  close(v2.f, 0, 1e-9, "linear 到期归零");
});

t("乱序/回退时间戳钳零不回放；decay_only 只衰减", () => {
  const st = mk();
  F.fresh_update(st, blob(20, 20, 1.0, 40, 1), 10);
  F.fresh_update(st, blob(20, 20, 1.0, 40, 2), 11);
  const v = gv(st, 20, 20, 1.0);
  F.fresh_update(st, new Float32Array(0), 10.5);  // 时间回退：dt 钳 0
  ok(v.f === 1, "回退不应衰减 f=" + v.f);
  ok(st.t === 11, "回退不应倒退主时钟");
  F.fresh_decay_only(st, 19);                      // +8s
  close(v.f, Math.exp(-1), 1e-9, "decay_only 一τ");
  F.fresh_decay_only(st, 2);                       // 再回退不动
  close(v.f, Math.exp(-1), 1e-9, "回退 decay_only 不应再衰减");
});

t("工作空间带外点不建体素（剔地面护人脚/裁顶棚）", () => {
  const st = mk();
  const R = rng(1), low = new Float32Array(40 * 4), high = new Float32Array(40 * 4);
  for (let i = 0; i < 40; i++) {
    low[i * 4] = 20 + (R() - 0.5) * 0.2; low[i * 4 + 1] = 20 + (R() - 0.5) * 0.2;
    low[i * 4 + 2] = 0.05 + (R() - 0.5) * 0.02; low[i * 4 + 3] = 50;      // z<0.07 全带外
    high[i * 4] = 21 + (R() - 0.5) * 0.2; high[i * 4 + 1] = 21 + (R() - 0.5) * 0.2;
    high[i * 4 + 2] = 2.7 + (R() - 0.5) * 0.1; high[i * 4 + 3] = 50;      // z>2.6 全带外
  }
  F.fresh_update(st, cat(low, high), 0);
  F.fresh_update(st, cat(low, high), 1);
  ok(st.voxels.size === 0, "z 带外不应产生体素 got=" + st.voxels.size);
  ok(F.point_state(st, 20, 20, 0.05) === "OUT_OF_BAND", "带外点态");
});

/* ---------- 背景层 / 候选过滤 ---------- */

t("build_reference：occ 阈值过滤 + 衣柜位 ref 支撑判定", () => {
  const ref = refFromScene();
  ok(ref.voxels.size > 0, "参考图非空");
  const st = mk(ref);
  F.fresh_update(st, P.denoise(wardrobe(5, 5, 300, 11)), 0);
  let any_sup = false;
  st.voxels.forEach(v => { if (v.ref_sup) any_sup = true; });
  ok(any_sup, "衣柜体素应被参考图支撑");
  let fired = 0;
  st.voxels.forEach(v => { if (v.ever_event) fired++; });
  ok(fired === 0, "ref 支撑背景不应发火");
});

t("候选过滤：背景静止点不入候选，HOT 点入候选", () => {
  const wfr = P.denoise(wardrobe(5, 5, 300, 11));
  const ref = F.build_reference(new Array(10).fill(wfr), {});   /* ref 与背景帧同源：所有背景格 occ=1 */
  const st = mk(ref);
  for (let i = 0; i < 300; i++) F.fresh_update(st, wfr, at(i));
  ok(F.candidate_xyzi(st, wfr, null).length === 0, "静止背景不应进候选");
  F.fresh_update(st, cat(wfr, blob(20, 20, 1.0, 40, 1)), at(300));
  const rep = F.fresh_update(st, cat(wfr, blob(20, 20, 1.0, 40, 2)), at(301));
  ok(rep.n_event_fired >= 1, "新物体应发火");
  const cand = F.candidate_xyzi(st, cat(wfr, blob(20, 20, 1.0, 40, 3)), null);
  ok(cand.length / 4 >= 20, "HOT 点应进候选 got=" + cand.length / 4);
});

/* ---------- 目标级记忆 ---------- */

t("FreshMemory：连续确认转 live；断连重置；双时钟到期", () => {
  const mem = F.FreshMemory();
  const cl = [{ cx: 1, cy: 1, cz: 1, n: 50 }];
  let r = F.mem_tick(mem, cl, 0, 0); ok(r.n_live === 0, "首帧不 live");
  r = F.mem_tick(mem, cl, 1, 0.1); ok(r.n_live === 0, "2 连不 live");
  r = F.mem_tick(mem, cl, 2, 0.2); ok(r.n_live === 1, "3 连 live");
  r = F.mem_tick(mem, cl, 4, 0.4); ok(r.n_live === 0, "断帧重置 confirmations");
  F.mem_tick(mem, cl, 5, 0.5); F.mem_tick(mem, cl, 6, 0.6);
  r = F.mem_tick(mem, [], 7, 180.7); ok(r.n_total === 0, "timeout_s 到期清除");
  const m2 = F.FreshMemory();
  for (let i = 0; i < 3; i++) F.mem_tick(m2, cl, i, i * 0.1);
  const r2 = F.mem_tick(m2, [], 40, 4.0); ok(r2.n_total === 0, "max_lost_for_retain 到期清除");
});

t("live 锚点半径内 COLD_BG 点仍被保住（track 层兜底）", () => {
  const st = mk(); const mem = F.FreshMemory();
  const cp = cell_pts(20, 20, 1.0, 30, 5);
  for (let i = 0; i < 3; i++) F.mem_tick(mem, [{ cx: 20.02, cy: 20.02, cz: 1.0, n: 30 }], i, at(i));
  ok(F.mem_live(mem).length === 1, "锚点应 live");
  F.fresh_update(st, cp, at(3));
  F.fresh_update(st, cp, at(4));
  ok(st.voxels.size === 1, "单格点集只建一个体素 got=" + st.voxels.size);
  const v = gv(st, 20, 20, 1.0);
  ok(v && v.ever_event, "应已发火");
  v.f = 0.05; v.ref_sup = true;                 /* 白盒：强制成 COLD_BG */
  const cand = F.candidate_xyzi(st, cp, mem);
  ok(cand.length / 4 >= 25, "锚点半径内 COLD_BG 点应被保住 got=" + cand.length / 4);
  ok(F.candidate_xyzi(st, cp, null).length === 0, "无锚点时 COLD_BG 不该进候选");
});

t("heat_rgb 单调、范围合法", () => {
  let prev = -1;
  for (let f = 0; f <= 1.0001; f += 0.1) {
    const [r, g, b] = F.heat_rgb(f);
    ok(r >= prev - 1e-12, "红通道单调");
    ok([r, g, b].every(c => c >= 0 && c <= 1.001), "范围合法");
    prev = r;
  }
});

console.log("\n" + passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);
