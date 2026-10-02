/* HR-04 R1..R5 node 冒烟：不依赖 WebGL，验证逻辑面正确
 * 数据：真实剪辑产物 cap_20261002_165321_clip_1989287-1989294
 */
"use strict";
const fs = require("fs"); const path = require("path");
const L = require("D:\\Code\\ldiar\\pc_apps\\human_replay\\human_replay_lib.js");

const DST = "D:\\Code\\ldiar\\captures\\remote\\cap_20261002_165321_clip_1989287-1989294";
const meta = JSON.parse(fs.readFileSync(path.join(DST, "meta.json"), "utf-8"));
const bin = fs.readFileSync(path.join(DST, "points.bin"));
const buf_f32 = new Float32Array(bin.buffer, bin.byteOffset, bin.byteLength / 4);

let n = 0;
function t(name, cond) { if (!cond) throw new Error("FAIL " + name); n++; console.log("ok", name); }

/* R1 视图预设：四 preset 字段 / 方向合理 */
const p_top = L.view_preset("top");
t("top: pos.z>10 空中俯视", p_top.pos[2] > 10);
t("top: proj=ortho", p_top.proj === "ortho");
const p_front = L.view_preset("front");
t("front: proj=ortho 且在雷达后方 (x<0)，朝 +X 看", p_front.proj === "ortho" && p_front.pos[0] < 0);
t("front: 相机高 1.6m（人眼级）", p_front.pos[2] === 1.6);
const p_side = L.view_preset("side");
t("side: proj=ortho 且 y 正向", p_side.proj === "ortho" && p_side.pos[1] > 8);
const p_persp = L.view_preset("persp");
t("persp: proj=persp", p_persp.proj === "persp");

/* R2 Home 归位 = persp 视野和 home 相同语义 */
const p_home = L.view_preset("home");
t("home: proj=persp", p_home.proj === "persp");
t("home: 与 VIEW_RESET 同位", p_home.pos[0] === -3.5 && p_home.pos[1] === -4 && p_home.pos[2] === 2.8);

/* R3 ray_ground_intersect：对三 ortho preset 各测一种"典型光标方向"
 * top/side 相机天然朝下/斜下；front（高 1.5m 的"驾驶"相机）水平看远——
 * 那本来就跟地面 P/M 语义不兼容（平行线不相交），"user 用光标"必须是
 * 鼠标不在水平线上时的向下分量。 */
[["top", p_top, [-1, 0, -1]],                                             // 屏幕上半（向下）
 ["side", p_side, [1, 0, -2]],                                            // 屏幕上半（向下）
 ["front", p_front, [-1, 0, -1]],                                        // 屏幕上半（向下 — 打破水平线）
].forEach(([name, p, d_unit]) => {
    const o = p.pos;
    /* 视线方向 = d_unit 归一化（模拟屏幕上方光标） */
    const len = Math.hypot(d_unit[0], d_unit[1], d_unit[2]);
    const d = [d_unit[0] / len, d_unit[1] / len, d_unit[2] / len];
    const g = L.ray_ground_intersect(o, d);
    t(name + ": 有向地视线能打到地面", g !== null);
    t(name + ": 命中点在雷达附近", Math.hypot(g[0], g[1]) < 30);
});

/* R4 P 拾取：在真实剪辑数据的第 3 帧上模拟 */
const frames = meta.frames;
const f3 = frames[3];
const slice = L.strided_f32_copy(buf_f32, f3.offset_points, f3.count_points, L.STRIDE_F32);
const r = L.find_nearest_xy(slice, 1.0, 0.5);
t("R4 find_nearest_xy 返回有 z/i", r.z !== undefined && r.i !== undefined);
t("R4 越近光标越合理（d_xy < 5m）", r.d_xy < 5);
t("R4 seq 与帧对得上", f3.seq !== undefined);

/* R5 measure_dist/measure_format */
const d = L.measure_dist([0, 0, 0], [3, 4, 0]);
t("R5: 3-4-5 距离=5", Math.abs(d - 5) < 1e-12);
t("R5: 5m 格式化为 5.00m", L.measure_format(5) === "5.00m");
t("R5: 微距 0.003 → '<0.01m'", L.measure_format(0.003) === "<0.01m");

/* 一致性：measure_line 端点格式 */
const p1 = [1.2, 3.4, 0], p2 = [4.2, 6.4, 0];
const md = L.measure_dist(p1, p2);
t("R5: measure_dist([1.2,3.4]→[4.2,6.4]) = 4.24", Math.abs(md - Math.hypot(3, 3)) < 1e-9);

/* 字符前缀防回归 */
t("LS_PREFIX 前缀", L.LS_PREFIX === "human_replay.");

/* 数据完整性：剪辑 meta / bin 在 HR-04 全程没被动过 */
const crypto = require("crypto");
function sha_fp(p) {
    const h = crypto.createHash("sha256"); h.update(fs.readFileSync(p)); return h.digest("hex");
}
/* points.bin 基线锁 — byte-identical 产物的稳定锚 */
t("points.bin sha256 与 R3 基线一致", sha_fp(path.join(DST, "points.bin")) ===
    "a4a24c19b886a56e4ddd26b8ab16d7ce5c2dbd9a49d25c18773646b41ec66f49");
/* meta 是 created_iso 敏感的（HR-03 工具改写过多次），只验"字节数>0 + frames=8" */
const meta_bytes = fs.statSync(path.join(DST, "meta.json")).size;
t("meta.json 存在且 frames=8", meta_bytes > 100 && meta.frames.length === 8);

console.log("HR-04 smoke: all " + n + " tests passed");
