// human_pipe_lib.js 单测（node 环境，零三方依赖）。运行：node human_pipe_lib.test.js
"use strict";
const L = require("./human_pipe_lib.js");

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("ok  " + name); }
  catch (e) { failed++; console.log("FAIL " + name + "\n  " + e.message); }
}
function ok(cond, msg) { if (!cond) throw new Error(msg || "断言失败"); }

function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) | 0;
    let z = Math.imul(a ^ (a >>> 15), 1 | a);
    z = (z + Math.imul(z ^ (z >>> 7), 61 | z)) ^ z;
    return ((z ^ (z >>> 14)) >>> 0) / 4294967296;
  };
}

/* 合成：站立人 —— 窄圆柱 z0..1.85 */
function standing(cx, cy, n, seed) {
  const R = rng(seed || 1);
  const o = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    const a = R() * 2 * Math.PI, rad = 0.12 + R() * 0.16;
    o[i * 4]     = cx + rad * Math.cos(a);
    o[i * 4 + 1] = cy + rad * Math.sin(a);
    o[i * 4 + 2] = 0.02 + R() * 1.83;
    o[i * 4 + 3] = 100 + R() * 50;
  }
  return o;
}
/* 躺人 —— 平展 1.7 长沿 y, z 偏安 0.15 */
function lying(cx, cy, n, seed) {
  const R = rng(seed || 2);
  const o = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    o[i * 4]     = cx + (R() - 0.5) * 0.45;
    o[i * 4 + 1] = cy + (R() - 0.5) * 1.7;
    o[i * 4 + 2] = 0.10 + R() * 0.30;
    o[i * 4 + 3] = 80;
  }
  return o;
}
/* 高柜 —— 直立大柱，宽近 1m，与 limb v2 失败 case 同款 */
function wardrobe(cx, cy, n, seed) {
  const R = rng(seed || 3);
  const o = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    o[i * 4]     = cx + (R() - 0.5) * 0.9;
    o[i * 4 + 1] = cy + (R() - 0.5) * 0.65;
    o[i * 4 + 2] = 0.02 + R() * 1.95;
    o[i * 4 + 3] = 60 + R() * 40;
  }
  return o;
}
/* 沙发 —— 低宽平台（< 0.9m 高） */
function sofa(cx, cy, n, seed) {
  const R = rng(seed || 4);
  const o = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    o[i * 4]     = cx + (R() - 0.5) * 1.6;
    o[i * 4 + 1] = cy + (R() - 0.5) * 0.7;
    o[i * 4 + 2] = 0.10 + R() * 0.55;
    o[i * 4 + 3] = 50;
  }
  return o;
}
/* 地板大片 */
function floor_patch(cx, cy, n, seed) {
  const R = rng(seed || 5);
  const o = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    o[i * 4]     = cx + (R() - 0.5) * 4;
    o[i * 4 + 1] = cy + (R() - 0.5) * 4;
    o[i * 4 + 2] = (R() - 0.5) * 0.04;
    o[i * 4 + 3] = 30;
  }
  return o;
}
/* 以体素中心为心的小点团：jitter 控制形心抖动，点保证落在同一 3D 体素内 */
function blob(cx, cy, cz, n, jitter, seed) {
  const R = rng(seed || 7);
  const o = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    o[i * 4]     = cx + (R() - 0.5) * jitter;
    o[i * 4 + 1] = cy + (R() - 0.5) * jitter;
    o[i * 4 + 2] = cz + (R() - 0.5) * jitter;
    o[i * 4 + 3] = 80;
  }
  return o;
}
/* 指定 3D 体素 (ix,iy,iz) 内的 n 个点（体素中心 ±0.02，保证同格） */
function voxPts(ix, iy, iz, n) {
  const cx = (ix + 0.5) * L.PIPE.bg_voxel_xy, cy = (iy + 0.5) * L.PIPE.bg_voxel_xy,
        cz = (iz + 0.5) * L.PIPE.bg_voxel_z;
  const R = rng(ix * 131 + iy * 17 + iz + n);
  const o = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    o[i * 4]     = cx + (R() - 0.5) * 0.04;
    o[i * 4 + 1] = cy + (R() - 0.5) * 0.04;
    o[i * 4 + 2] = cz + (R() - 0.5) * 0.04;
    o[i * 4 + 3] = 80;
  }
  return o;
}
function concat_bufs() {
  let total = 0;
  for (const b of arguments) total += b.length;
  const out = new Float32Array(total);
  let offset = 0;
  for (const b of arguments) { out.set(b, offset); offset += b.length; }
  return out;
}

t("PIPE 阈值物理合理", () => {
  ok(L.PIPE.voxel_m > 0.05 && L.PIPE.voxel_m <= 0.25, "voxel 0.05..0.25m 是合理人体粒度");
  ok(L.PIPE.bg_occ_strong >= 0.8, "强静态须高占用率才成立");
  ok(L.PIPE.bg_occ_supported < L.PIPE.bg_occ_strong, "支持静态门须低于强静态门");
  ok(L.PIPE.bg_match_radius > 0 && L.PIPE.bg_match_radius < L.PIPE.bg_voxel_xy,
     "背景匹配半径须小于体素边长");
  ok(L.PIPE.z_max_m > L.PIPE.human_height_max, "工作空间上沿须高于人上限");
  ok(L.PIPE.fall_upcos_max < L.PIPE.human_upcos_min, "fall 崩侠门须低于人直立门");
  ok(L.PIPE.ground_keep_below_m < 0.15, "地面剔除不能吃到脚踝");
});

t("denoise: 距窗 + 有限点过滤", () => {
  const valid = standing(3, 1, 100, 1);
  const out = L.denoise(valid);
  ok(out.length === valid.length, "合法点全保");
  const bad = new Float32Array(8);
  bad.set([0.01, 0, 0, 0, NaN, 0, 0, 0]);
  ok(L.denoise(bad).length === 0, "过近/NaN 全弹回");
});

t("voxelize: 协方差累加器逐帧单遍、体素键聚合", () => {
  const v = L.voxelize(standing(2, 1, 300, 1));
  ok(v.size > 0, "有体素");
  let sum_n = 0, sum_sx = 0;
  v.forEach(a => { sum_n += a.n; sum_sx += a.sx; });
  ok(Math.abs(sum_sx / sum_n - 2) < 0.3, "簇形心 x ≈ 2, 实 " + (sum_sx / sum_n).toFixed(2));
});

t("build_static_map: 家具在 N 帧全占用 → 进背景；动人不进", () => {
  // 5 帧：家具衣柜从来不动；人只在帧 3,4 出现（点团加密保证每帧命中门 ≥2）
  const frames = [];
  for (let f = 0; f < 5; f++) {
    let arr = concat_bufs(wardrobe(4, 0, 6000, 10 + f));
    if (f >= 3) arr = concat_bufs(arr, standing(1, -1, 3000, 100 + f));
    frames.push(arr);
  }
  const sm = L.build_static_map(frames);
  ok(sm.size > 0, "至少有背景体素");
  // 衣柜中心 (4,0,1.0) 应被打中（5/5 帧占用 ≥ 0.85 → strong）
  ok(sm.has(L.key_bg(4, 0, 1.0)), "衣柜体素应被标成强静态背景");
  ok(sm.get(L.key_bg(4, 0, 1.0)).tier === "strong", "衣柜体素应为 strong 级");
  // 人只有 2/5 帧 → 不应是背景
  ok(!sm.has(L.key_bg(1, -1, 1.0)), "人体素只有 2/5 帧 → 不应是背景");
});

t("extract_foreground: 工作空间 + 背景匹配后，前景只剩人附近区域", () => {
  // 房间（地板 + 两个高柜）3 帧建背景；人只在待测帧出现
  const room = [];
  for (let f = 0; f < 3; f++)
    room.push(concat_bufs(floor_patch(0, 0, 6000, f),
                          wardrobe(4, 0, 10000, 10 + f), wardrobe(5, 2, 10000, 20 + f)));
  const sm = L.build_static_map(room);
  ok(sm.size > 0, "房间背景非空");
  const scene = concat_bufs(floor_patch(0, 0, 6000, 5),
                            wardrobe(4, 0, 10000, 10), wardrobe(5, 2, 10000, 20),
                            standing(1, -1, 3000, 100));
  const fg = L.extract_foreground(scene, sm);
  // 前景应≈人(3000) ±背景匹配残差；地板/柜体应被削掉大部分
  ok(fg.n_fg > 2400 && fg.n_fg < 4000, "前景点数应聚焦人体(~3000), 实 " + fg.n_fg);
  ok(fg.n_dropped > 25000, "地板+背景应削掉 25000+, 实 " + fg.n_dropped);
  // 人所在体素不是背景（人只出现在待测帧）
  ok(!sm.has(L.key_bg(1, -1, 1.0)), "人不应是背景");
});

t("classify: 站立人 → HUMAN_CANDIDATE（几何只能「像人」，不拖黑 HUMAN）", () => {
  const frame = standing(1.5, -0.5, 300, 1);
  const fg = L.extract_foreground(frame, null);
  const cl = L.cluster_voxels(fg.vox_fg);
  ok(cl.length >= 1, "至少一个簇");
  const feats = cl.map(L.cluster_features).filter(f => f.ok).sort((a, b) => b.n - a.n);
  ok(feats.length > 0, "有 ok 簇");
  const judge = L.classify_human(feats[0]);
  ok(judge.label === "HUMAN_CANDIDATE", "站立人应发 HUMAN_CANDIDATE, 实 " + judge.label);
  ok(judge.confidence >= 0.95, "置信度应高, 实 " + judge.confidence);
});

t("classify 衣柜: 仅靠几何也即HUMAN_CANDIDATE（同 limb 教训：沙发≈衣柜≈直立人）", () => {
  const frame = wardrobe(3, 1, 300, 3);
  const fg = L.extract_foreground(frame, null);
  const cl = L.cluster_voxels(fg.vox_fg);
  const feats = cl.map(L.cluster_features).filter(f => f.ok).sort((a, b) => b.n - a.n);
  ok(feats.length > 0, "有候选");
  const judge = L.classify_human(feats[0]);
  /* limb 六代算法都锁衣柜 — 本工作台决不说「这是人」，同理也不能说「这不是人」；
   * 只发“像人” HUMAN_CANDIDATE，裁权交给跟踪跨帧 + 用户 pin。 */
  ok(judge.label === "HUMAN_CANDIDATE", "衣柜应发 HUMAN_CANDIDATE（几何不分衣柜）, 实 " + judge.label);
});

t("classify 沙发: NON_HUMAN 因身高不足", () => {
  const frame = sofa(3, 1, 300, 4);
  const fg = L.extract_foreground(frame, null);
  const cl = L.cluster_voxels(fg.vox_fg);
  const feats = cl.map(L.cluster_features).filter(f => f.ok).sort((a, b) => b.n - a.n);
  if (feats.length === 0) { /* 沙发可能整簇被判无效 ——也接受 */ return; }
  const judge = L.classify_human(feats[0]);
  ok(judge.label === "NON_HUMAN", "沙发应 NON_HUMAN");
});

t("Tracker: 单人跨帧保持 ID + EMA 平滑 + lost 关闭", () => {
  const tr = new L.Tracker();
  for (let f = 0; f < 12; f++) {
    const frame = standing(2 + f * 0.05, -1, 200, 100 + f);
    const fg = L.extract_foreground(frame, null);
    const cl = L.cluster_voxels(fg.vox_fg);
    const feats = cl.map(L.cluster_features).filter(f2 => f2.ok);
    tr.tick(f, feats);
  }
  ok(tr.tracks.length >= 1, "至少一条 track");
  const active = tr.tracks.filter(x => x.active);
  ok(active.length >= 1, "追踪保持活跃");
  ok(active[0].x > 2 && active[0].x < 2.8, "EMA 沿击中 x 移轴, 实 " + active[0].x.toFixed(2));
  // 掩 12 帧不 tick → lost 自然超门 → active=false
  for (let f = 12; f < 12 + L.PIPE.track_lost_max + 2; f++) tr.tick(f, []);
  ok(!active[0].active, "连续 lost 应关闭 track");
});

t("evidence: 衣柜/均匀盒体 → SOLID_UNIFORM / 立体人 → HUMAN_SHAPE (HR-07 five-dim one-evidence 反切)", () => {
  // 衣柜：盒体宽度一致，垂直轴向 → 各带 σ_xy 近似恒定 + XY 强各向异性
  const wd = wardrobe(3, 1, 600, 40);
  const fg_w = L.extract_foreground(wd, null);
  const cl_w = L.cluster_voxels(fg_w.vox_fg);
  // production 口径：证据层输入是剔净后的 fg_xyzi，不是含地板的原帧
  const extra_w = L.evidence_postpass(fg_w.fg_xyzi, cl_w).clusters_extra[0];
  // 高柜宽度 ≈0.75x 0.47y → aniso > 2；spread_cv 应 ≈0 （体素体素宽度始终一致）
  const tag_w = L.evidence_label(extra_w);
  ok(tag_w.label === "SOLID_UNIFORM" || extra_w.anisotropy_xy >= L.PIPE.ev_aniso_box_soft,
     "衣柜应记 SOLID_UNIFORM 或 aniso ≥ soft 门: " + JSON.stringify(tag_w) + " extra=" + JSON.stringify(extra_w));
  // 立体人：按 limb/2m 高强度带设计 — 腿细躯宽头小 → spread_cv 显著 ≥ 门
  const R = rng(60);
  const n = 2200; const pts = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    const u = R();
    let x, y, z;
    /* 腿 0-0.9：半径 0.075 */
    if (u < 0.28) { const a = R() * 7; x = 1.0 - 0.10 + (R() - 0.5) * 0.15; y = -1 + (R() - 0.5) * 0.15; z = R() * 0.9; }
    /* 躯干 0.9-1.6：半径 0.23 × 0.16 (非完全圆筒) */
    else if (u < 0.88) { const a = R() * 7, r = R(); x = 1.0 + (r - 0.5) * 0.46; y = -1 + (r - 0.5) * 0.32; z = 0.9 + R() * 0.7; }
    /* 头 1.6-1.85：半径 0.12 */
    else { const a = R() * 7, r = R(); x = 1.0 + (r - 0.5) * 0.24; y = -1 + (r - 0.5) * 0.24; z = 1.6 + R() * 0.25; }
    pts[i * 4] = x; pts[i * 4 + 1] = y; pts[i * 4 + 2] = z; pts[i * 4 + 3] = 80;
  }
  const fg_h = L.extract_foreground(pts, null);
  const cl_h = L.cluster_voxels(fg_h.vox_fg);
  const extra_h = L.evidence_postpass(fg_h.fg_xyzi, cl_h).clusters_extra[0];
  const tag_h = L.evidence_label(extra_h);
  ok(extra_h.covered_bands >= L.PIPE.ev_bands_min, "人形 covered_bands ≥ min, 实 " + extra_h.covered_bands);
  ok(extra_h.spread_cv >= L.PIPE.ev_spread_cv_person,
     "人形 spread_cv ≥ " + L.PIPE.ev_spread_cv_person + ", 实 " + extra_h.spread_cv +
     " covered=" + extra_h.covered_bands + " spreads=" + JSON.stringify(extra_h.band_spreads.map(v => +v.toFixed(2))));
  ok(tag_h.label !== "SOLID_UNIFORM", "立体人不应 SOLID_UNIFORM, 实 " + tag_h.label);
});

t("fall_assess: 直→躺 判 fall / 弯腰不判 / 恢复取消", () => {
  const tr = new L.Tracker();
  // 阶段 A: 站立 10 帧
  for (let f = 0; f < 10; f++)
    tr.tick(f, [{ ok: true, cx: 2, cy: -1, cz: 1.0, height_m: 1.80, upcos: 0.95, label: "HUMAN", n: 200 }]);
  // 阶段 B: 躺 20 帧
  for (let f = 10; f < 30; f++)
    tr.tick(f, [{ ok: true, cx: 2, cy: -1, cz: 0.3, height_m: 0.30, upcos: 0.10, label: "NON_HUMAN", n: 200 }]);
  const active = tr.tracks.filter(x => x.active)[0];
  const ev = L.fall_assess(active);
  ok(ev && ev.type === "fall", "直→躺 应报 fall, 实 " + JSON.stringify(ev));

  // 重置：在帧 35 人回站
  for (let f = 30; f < 45; f++)
    tr.tick(f, [{ ok: true, cx: 2, cy: -1, cz: 1.0, height_m: 1.80, upcos: 0.95, label: "HUMAN", n: 200 }]);
  const ev2 = L.fall_assess(active);
  ok(ev2 === null, "回站后不应报 fall, 实 " + JSON.stringify(ev2));

  // 重置 tracker 测试弯腰：立→弯腰(upcos高,height中) → 不触发
  const tr2 = new L.Tracker();
  for (let f = 0; f < 10; f++)
    tr2.tick(f, [{ ok: true, cx: 2, cy: -1, cz: 1.0, height_m: 1.80, upcos: 0.95, label: "HUMAN", n: 200 }]);
  for (let f = 10; f < 25; f++)
    tr2.tick(f, [{ ok: true, cx: 2, cy: -1, cz: 0.7, height_m: 1.20, upcos: 0.75, label: "HUMAN", n: 200 }]);
  const active2 = tr2.tracks.filter(x => x.active)[0];
  ok(L.fall_assess(active2) === null, "弯腰不应报 fall");
});

t("pipeline_frame: 全链路返回结构完整", () => {
  const scene = concat_bufs(
    floor_patch(0, 0, 400, 5),
    wardrobe(5, 2, 220, 10),
    standing(1.5, -1, 250, 100)
  );
  const ctx = { static_keys: null, tracker: new L.Tracker() };
  const r = L.pipeline_frame(scene, 0, ctx);
  ok(typeof r.n_in === "number" && r.n_in === scene.length / 4, "n_in 对源点数");
  ok(r.n_foreground > 0, "前景非零");
  ok(Array.isArray(r.clusters) && Array.isArray(r.tracks) && Array.isArray(r.events),
     "clusters/tracks/events 均为数组");
});

t("【根因回归】build_static_map 必须先剔地面: 地板上的人不被当地板吞", () => {
  // 5 帧全有大片地板（加密到目标体素每帧必然占用）+ 同一固定位置站人
  const frames = [];
  for (let f = 0; f < 5; f++)
    frames.push(concat_bufs(floor_patch(0, 0, 10000, f), standing(1.5, -1, 3000, 100 + f)));
  // 缺省调用（新调用方的实际路径）也必须剔 —— 缺省 true 是防再踩本体, 不能只测显式传参
  const sk = L.build_static_map(frames);
  ok(!sk.has(L.key_bg(0.5, 0.5, 0)), "缺省剔地面后地板体素不应是背景（否则人被吞）");
  // 静止者：剔地面后躯干 z>0.10 仍 5/5 占用 → 会吞人。这正是 limb v5 已知边界
  // （静立全程的人被背景吞掉），UI 已提示、不是 bug。这里钉死此刻行为=吞人。
  ok(sk.has(L.key_bg(1.5, -1, 1.0)), "剔地面后,静止人躯干体素仍会当背景吞(limb v5 已知边界)");
  // 开关反向：显式关掉 = 旧病态（地板全帧占用 → 地板全进背景）, 钉死开关语义
  const sk_off = L.build_static_map(frames, { drop_ground: false });
  ok(sk_off.has(L.key_bg(0.5, 0.5, 0)), "drop_ground:false 时地板体素应进背景（开关语义）");
});
t("【根因回归】extract_foreground 点级剔地面后, 人簇内无贴地板点", () => {
  const scene = concat_bufs(floor_patch(0, 0, 400, 5), standing(1.5, -1, 300, 100));
  const fg = L.extract_foreground(scene, null);
  // 剔净后不再含 z<0.10 点
  let min_z = 1e9;
  for (let k = 0; k < fg.fg_xyzi.length; k += 4) if (fg.fg_xyzi[k + 2] < min_z) min_z = fg.fg_xyzi[k + 2];
  ok(min_z >= L.PIPE.ground_keep_below_m - 1e-9,
     "前景内最低点应 ≥ ground_keep_below_m(点级剔), 实 " + min_z.toFixed(3));
  // 剔后前景主要是人 (300±身体杂散), 原柱级剔除会把人柱的地板点也算作前景
  ok(fg.n_fg >= 250 && fg.n_fg <= 320, "前景点数聚焦人体(~300), 实 " + fg.n_fg);
});

t("工作空间裁剪: z>z_max_m 不进前景/背景（不叫去噪）", () => {
  const pts = new Float32Array([2, 0, 3.0, 50, 2.05, 0, 3.0, 50, 2, 0, 2.4, 50, 2.05, 0, 2.4, 50]);
  const fg = L.extract_foreground(pts, null);
  ok(fg.n_fg === 2, "2.4m 保留、3.0m 剔除, 实 " + fg.n_fg);
  const sm = L.build_static_map([pts, pts]);
  ok(!sm.has(L.key_bg(2, 0, 3.0)), "高于 z_max 的点不进背景");
  ok(sm.has(L.key_bg(2, 0, 2.4)), "工作空间内的点照常参与背景");
});

t("背景两级(R2.2/R2.3): 强静态 / 邻域支持 / 孤立不补 / 抖动超限不补", () => {
  const NF = 10;
  const frames = [];
  for (let f = 0; f < NF; f++) {
    const bufs = [
      blob(4.575, 0.075, 1.02, 8, 0.08, 1),   // strong A (30,0,8)
      blob(4.725, 0.075, 0.90, 8, 0.08, 2),   // strong B (31,0,7)
      blob(4.575, 0.375, 1.02, 8, 0.08, 3),   // strong C (30,2,8)
      blob(4.725, 0.375, 0.90, 8, 0.08, 4),   // strong D (31,2,7)
    ];
    if (f < 7) {
      bufs.push(blob(4.725, 0.075, 1.02, 8, 0.08, 10 + f));       // 邻域支持的弱静态
      bufs.push(blob(1.575, 1.575, 1.02, 8, 0.08, 30 + f));       // 孤立弱静态（无 strong 邻域）
      const dx = (f % 2) ? 0.055 : -0.055;                         // 形心抖动 > 0.05
      bufs.push(blob(4.725 + dx, 0.375, 1.02, 8, 0.04, 50 + f));   // 抖动超限（有邻域）
    }
    frames.push(concat_bufs.apply(null, bufs));
  }
  const sm = L.build_static_map(frames);
  const a = sm.get(L.key_bg(4.575, 0.075, 1.02));
  ok(a && a.tier === "strong", "10/10 帧 → strong, 实 " + JSON.stringify(a));
  const sup = sm.get(L.key_bg(4.725, 0.075, 1.02));
  ok(sup && sup.tier === "supported", "7/10 帧 + 邻域 strong≥2 → supported, 实 " + JSON.stringify(sup));
  ok(!sm.has(L.key_bg(1.575, 1.575, 1.02)), "孤立弱静态（无 strong 邻域）不应进背景");
  ok(!sm.has(L.key_bg(4.725, 0.375, 1.02)), "形心抖动 > 0.05 的弱静态不应进背景");
});

t("joint_status: 硬门 × 证据 → 绿/紫/灰 三态", () => {
  const g = (label, ev) => L.joint_status({ label: label, evidence_tag: { label: ev } });
  ok(g("HUMAN_CANDIDATE", "HUMAN_SHAPE") === "CONFIRMED_HUMAN", "硬门过+人形 → 绿");
  ok(g("HUMAN_CANDIDATE", "AMBIGUOUS") === "HUMAN_CANDIDATE", "硬门过+模糊 → 紫");
  ok(g("HUMAN_CANDIDATE", "EVIDENCE_NONE") === "HUMAN_CANDIDATE", "硬门过+无证据 → 紫");
  ok(g("HUMAN_CANDIDATE", "SOLID_UNIFORM") === "NON_HUMAN", "均匀体 → 灰");
  ok(g("NON_HUMAN", "HUMAN_SHAPE") === "NON_HUMAN", "硬门不过 → 灰（证据不能翻案）");
});

t("Tracker 时间确认(R2.5): 3/5 帧 CONFIRMED_HUMAN 且 age≥3 才 human_confirmed", () => {
  const tr = new L.Tracker();
  const mk = j => [{ ok: true, cx: 2, cy: -1, cz: 1.0, height_m: 1.80, upcos: 0.95,
                     label: "HUMAN_CANDIDATE", n: 200, joint: j }];
  tr.tick(0, mk("CONFIRMED_HUMAN"));
  ok(tr.tracks[0].human_confirmed === false, "1 帧不够");
  tr.tick(1, mk("NON_HUMAN"));
  tr.tick(2, mk("CONFIRMED_HUMAN"));
  ok(tr.tracks[0].human_confirmed === false, "2/5 票不够");
  const c3 = mk("CONFIRMED_HUMAN");
  tr.tick(3, c3);
  ok(tr.tracks[0].human_confirmed === true, "3/5 票 + age≥3 应确认");
  ok(c3[0].track_confirmed === true && c3[0].track_id === tr.tracks[0].id, "簇应带 track 确认状态");
  for (let f = 4; f < 10; f++) tr.tick(f, mk("NON_HUMAN"));
  ok(tr.tracks[0].human_confirmed === false, "连续非确认应滑出窗口回落");
});

t("R2.6 孤立清理: 独立单点体素 → 删除", () => {
  const r = L.cleanup_isolated_fg(voxPts(10, 10, 10, 1));
  ok(r.after === 0 && r.removed_points === 1 && r.removed_voxels === 1,
     "单点孤立体素应删, 实 after=" + r.after + " removed=" + r.removed_points);
});

t("R2.6 孤立清理: 单点体素旁有前景体素（面邻） → 保留", () => {
  const pts = concat_bufs(voxPts(10, 10, 10, 1), voxPts(11, 10, 10, 3));
  const r = L.cleanup_isolated_fg(pts);
  ok(r.after === 4 && r.removed_points === 0, "有面邻前景体素应保留, 实 removed=" + r.removed_points);
});

t("R2.6 孤立清理: 对角邻（26 邻域）也算前景邻居 → 保留", () => {
  const pts = concat_bufs(voxPts(10, 10, 10, 1), voxPts(11, 11, 11, 1));
  const r = L.cleanup_isolated_fg(pts);
  ok(r.after === 2 && r.removed_points === 0, "对角邻居应保留, 实 removed=" + r.removed_points);
});

t("R2.6 孤立清理: 两个相邻单点体素 → 都保留", () => {
  const pts = concat_bufs(voxPts(10, 10, 10, 1), voxPts(11, 10, 10, 1));
  const r = L.cleanup_isolated_fg(pts);
  ok(r.after === 2 && r.removed_points === 0, "互为邻居应都保留, 实 removed=" + r.removed_points);
});

t("R2.6 孤立清理: single-pass 语义（A-B-主体链 + 远处孤立点，不连锁删除）", () => {
  // 远处孤立点 C(1 点) 应删；A(1)-B(1)-主体(3) 链上全部保留（快照判定，不第二轮传播）
  const pts = concat_bufs(voxPts(12, 10, 10, 3), voxPts(11, 10, 10, 1),
                          voxPts(10, 10, 10, 1), voxPts(30, 30, 30, 1));
  const r = L.cleanup_isolated_fg(pts);
  ok(r.removed_points === 1 && r.removed_voxels === 1 && r.after === 5,
     "只删远处孤立点，链上不传播, 实 removed=" + r.removed_points + " after=" + r.after);
});

t("R2.6 孤立清理: 多点孤立体素（≥2 点） → 不删除", () => {
  const r = L.cleanup_isolated_fg(voxPts(10, 10, 10, 2));
  ok(r.after === 2 && r.removed_points === 0, "多点体素不删, 实 removed=" + r.removed_points);
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
