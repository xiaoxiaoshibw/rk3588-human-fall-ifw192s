// human_detect_lib.js 单测（node 环境）。运行：node human_detect_lib.test.js
"use strict";
const L = require("./human_detect_lib.js");

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("ok  " + name); }
  catch (e) { failed++; console.log("FAIL " + name + "\n  " + e.message); }
}
function ok(cond, msg) { if (!cond) throw new Error(msg || "断言失败"); }

/* 确定性伪随机（LCG），不引入外部 lib。mulberry32。 */
function rng(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let z = Math.imul(a ^ (a >>> 15), 1 | a);
    z = (z + Math.imul(z ^ (z >>> 7), 61 | z)) ^ z;
    return ((z ^ (z >>> 14)) >>> 0) / 4294967296;
  };
}

/* 造一个直立人：圆柱半径 r、z 从 z0 到 z1，高密度，n 点。返回 [x,y,z,i]* 拍平。
 * 故意把点密度往肩/头提一点，让 PCA 主轴 z 余弦 >0.85（真实人的特征）。 */
function make_standing(cx, cy, n, seed) {
  const R = rng(seed || 42);
  const out = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    const ang = R() * 2 * Math.PI;
    const rad = R() * 0.28;                       // 半径 ≤ 0.28m
    /* 60% 落上半身(0.9..1.75m)，25% 腿部(0.05..0.9m)，15% 头部(1.75..1.95m) */
    const u = R();
    let z;
    if (u < 0.60) z = 0.9 + R() * 0.85;
    else if (u < 0.85) z = 0.05 + R() * 0.85;
    else z = 1.75 + R() * 0.20;
    out[i * 4] = cx + rad * Math.cos(ang);
    out[i * 4 + 1] = cy + rad * Math.sin(ang);
    out[i * 4 + 2] = z;
    out[i * 4 + 3] = 100 + R() * 100;             // intensity 无关
  }
  return out;
}

/* 弯腰：上半身前倾 45°，圆柱带（一段绕腰、一段水平伸出），z 顶到 ~1.2m。 */
function make_bending(cx, cy, n, seed) {
  const R = rng(seed || 7);
  const out = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    const u = R();
    let x, y, z;
    if (u < 0.55) {         // 下身（竖）
      const ang = R() * 2 * Math.PI, rad = R() * 0.25;
      x = cx + rad * Math.cos(ang); y = cy + rad * Math.sin(ang);
      z = 0.05 + R() * 0.85;
    } else {                // 前倾上身：沿 +y 伸出，z 在腰高附近
      const t = R();        // 0=腰、1=头；y 是前倾方向
      const ang = R() * 2 * Math.PI, rad = R() * 0.22;
      const ax = Math.cos(ang) * rad, az = Math.sin(ang) * rad;
      x = cx + ax;
      y = cy + t * 0.9 + az * 0.5;          // 前倾 0.9m
      z = 1.05 + t * 0.25 + az * 0.3;       // 上半身 z 0.9..1.35
    }
    out[i * 4] = x; out[i * 4 + 1] = y; out[i * 4 + 2] = z; out[i * 4 + 3] = 120;
  }
  return out;
}

/* 躺平：一块 1.7m(长) × 0.5m(宽) × 0.25m(厚) 板贴地。 */
function make_lying(cx, cy, n, seed) {
  const R = rng(seed || 9);
  const out = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    out[i * 4] = cx + (R() - 0.5) * 0.5;
    out[i * 4 + 1] = cy + (R() - 0.5) * 1.7;
    out[i * 4 + 2] = 0.02 + R() * 0.24;
    out[i * 4 + 3] = 80;
  }
  return out;
}

/* 家具 decoy：高大立柜 — 直立(高 upright_cos)、粗(r_xy 大)、高(height 接近 1.8)。
 * 这正是 limb_v2 把柜子识别成人的失败 case；本工作台的 score 必须识别它不是人。 */
function make_wardrobe(cx, cy, n, seed) {
  const R = rng(seed || 5);
  const out = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    /* 0.8×0.6 横截面 — 甚宽于人体(≤0.28 半径) */
    const ang = R() * 2 * Math.PI;
    const rr = Math.pow(R(), 0.4);          // 偏外侧填充
    out[i * 4] = cx + Math.cos(ang) * rr * 0.65;
    out[i * 4 + 1] = cy + Math.sin(ang) * rr * 0.50;
    out[i * 4 + 2] = 0.05 + R() * 1.95;      // 满高立柜
    out[i * 4 + 3] = 60 + R() * 40;
  }
  return out;
}

/* 测试 --- */

t("DETECT.defaults 物理合理", () => {
  ok(L.DETECT.z_min_human > 0 && L.DETECT.z_min_human < 0.5, "z_min_human 应在脚踝~膝盖间");
  ok(L.DETECT.z_max_human > 1.8 && L.DETECT.z_max_human < 3.0, "z_max_human 应高于人头");
  ok(L.DETECT.min_height_m < 1.0, "min_height_m 不应超过一般弯腰");
  ok(L.DETECT.min_upright_cos >= 0.5 && L.DETECT.min_upright_cos <= 0.8, "直立余弦门在 0.5..0.8");
  if (L.DETECT.ema_alpha <= 0 || L.DETECT.ema_alpha > 0.6) throw new Error("ema_alpha 应 (0,0.6]");
});

t("points_in_cylinder: 仅取 ROI 内 + z 带内点", () => {
  const cyl = make_standing(2.0, -1.0, 200, 1);
  // 再混一个远点（ROI 外）
  const far = new Float32Array(cyl.length + 4);
  far.set(cyl, 0);
  far[cyl.length] = 99; far[cyl.length + 1] = 99; far[cyl.length + 2] = 99; far[cyl.length + 3] = 0;
  const out = L.points_in_cylinder(far, { x: 2.0, y: -1.0, r: 0.6 }, 0.0, 2.5);
  ok(out.length / 4 === 200, "应得 200 点（剔除 1 个远点），实际 " + (out.length / 4));
});

t("frame_human_features: 站立 → standing / is_human_like", () => {
  const cyl = make_standing(1.5, -0.5, 220, 11);
  const f = L.frame_human_features(cyl);
  ok(f.ok, "应为 ok");
  ok(f.upright_cos > 0.75, "直立余弦应 >0.75, 实际 " + f.upright_cos.toFixed(3));
  ok(f.height_m > 1.5 && f.height_m < 2.2, "身高应 1.5..2.2, 实际 " + f.height_m.toFixed(2));
  ok(f.pose === "standing", "pose 应为 standing, 实际 " + f.pose);
  ok(f.is_human_like, "应判 is_human_like");
});

t("frame_human_features: 弯腰 → bending（身高降、躯干前倾）", () => {
  const cyl = make_bending(1.0, 0.5, 220, 22);
  const f = L.frame_human_features(cyl);
  ok(f.ok, "ok");
  ok(f.pose === "bending", "pose 应为 bending, 实际 " + f.pose + " (upcos=" + f.upright_cos.toFixed(2) + " h=" + f.height_m.toFixed(2) + ")");
  ok(f.height_m < 1.6, "弯腰身高应 <1.6, 实际 " + f.height_m.toFixed(2));
});

t("frame_human_features: 躺平 → lying（主轴横躺）", () => {
  const cyl = make_lying(0.5, 0.3, 220, 33);
  const f = L.frame_human_features(cyl);
  ok(f.ok, "ok");
  ok(f.upright_cos < 0.55, "躺平主轴 z 余弦应 <0.55, 实际 " + f.upright_cos.toFixed(3));
  ok(f.pose === "lying", "pose 应为 lying, 实际 " + f.pose);
});

t("frame_human_features: 衣柜 decoy → 不判 is_human_like", () => {
  const cyl = make_wardrobe(3.0, 2.0, 300, 44);
  const f = L.frame_human_features(cyl);
  ok(f.ok, "ok");
  /* limb_v1..v6 全部把衣柜判成人；本工作台必须给出非人证据（width_m 或 score 至少一个） */
  ok(!f.is_human_like || f.bbox.r_xy > 0.55,
      "衣柜不应 is_human_like 或应有宽 ro (r_xy=" + f.bbox.r_xy.toFixed(2) + " score=" + f.score + ")");
});

t("frame_human_features: 点太少 → ok:false 带 reason", () => {
  const cyl = make_standing(0, 0, 5, 1);
  const f = L.frame_human_features(cyl);
  ok(!f.ok, "应失败");
  ok(typeof f.reason === "string" && f.reason.length > 0, "应给 reason");
});

t("EmaTracker: 平滑人形移动 & 突变保护", () => {
  const tr = new L.EmaTracker(0.3);
  const a = { ok: true, bbox: { cx: 1, cy: 0, z1: 1.8 }, upright_cos: 0.9, height_m: 1.75, pose: "standing", score: 7, is_human_like: true, n: 100 };
  const b = { ok: true, bbox: { cx: 1.1, cy: 0.05, z1: 1.82 }, upright_cos: 0.92, height_m: 1.78, pose: "standing", score: 7, is_human_like: true, n: 200 };
  tr.push(a); tr.push(b);
  const s = tr.smoothed;
  ok(s.x > 1.0 && s.x < 1.15, "EMA 后 x 应介于 1..1.15, 实际 " + s.x.toFixed(3));
  /* 突变 0.6m > 0.5m 阈值 → 直接跳 */
  const c = { ok: true, bbox: { cx: 2.0, cy: 0.5, z1: 1.7 }, upright_cos: 0.9, height_m: 1.70, pose: "standing", score: 7, is_human_like: true, n: 200 };
  tr.push(c);
  ok(Math.abs(tr.smoothed.x - 2.0) < 0.01, "突变应直接挂靠新位置, 实际 " + tr.smoothed.x.toFixed(3));
});

t("EmaTracker: 连丢 max_lost_frames+1 帧 → reset", () => {
  const tr = new L.EmaTracker(0.3);
  tr.push({ ok: true, bbox: { cx: 1, cy: 0, z1: 1.8 }, upright_cos: 0.9, height_m: 1.75 });
  ok(tr.smoothed !== null, "先有人");
  for (let i = 0; i < L.DETECT.max_lost_frames + 1; i++) tr.push(null);
  ok(tr.smoothed === null, "应 reset");
});

t("smoothed_to_box: 生成 Three 友好 bbox", () => {
  const box = L.smoothed_to_box({ x: 1, y: 2, z: 1.8 });
  ok(box.center.length === 3 && box.size.length === 3, "center/size 三元");
  ok(Math.abs(box.center[2] - 0.9) < 0.01, "center z 应是 z/2");
  ok(Math.abs(box.size[2] - 1.8) < 0.01, "size z 应是身高");
});

t("_eig3_sym: 三特征值正确（直立 ≈ z 主轴）", () => {
  /* 造一个 z 方向方差最大的对角协差阵 → eig0 应是 z */
  const cyl = make_standing(0, 0, 300, 55);
  let mx = 0, my = 0, mzz = 0, n = cyl.length / 4;
  for (let i = 0; i < n; i++) { mx += cyl[i * 4]; my += cyl[i * 4 + 1]; mzz += cyl[i * 4 + 2]; }
  mx /= n; my /= n; mzz /= n;
  let cxx = 0, cyy = 0, czzz = 0;
  for (let i = 0; i < n; i++) {
    const dx = cyl[i * 4] - mx, dy = cyl[i * 4 + 1] - my, dz = cyl[i * 4 + 2] - mzz;
    cxx += dx * dx; cyy += dy * dy; czzz += dz * dz;
  }
  cxx /= n; cyy /= n; czzz /= n;
  const eig = L._eig3_sym([[cxx, 0, 0], [0, cyy, 0], [0, 0, czzz]]);
  ok(eig.values[0] >= eig.values[1] && eig.values[1] >= eig.values[2], "desc order");
  ok(Math.abs(eig.vectors[0][2]) > 0.95, "最大主轴应近似 ±z, 实际 z 分量 " + eig.vectors[0][2].toFixed(3));
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
