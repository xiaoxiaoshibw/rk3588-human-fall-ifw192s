"use strict";
/* 给 v2_view 增加一层：空场模板 233658 原始点（denoise 后，54 帧并集，按目标点数抽稀）。
 * 区域=三段会话人位裁剪区的并集（x∈[0,4.2], y∈[-2.6,4.0], z∈[-0.15,2.4]）。
 * 输出 v2_view_refpts.js（Int16 毫米坐标 base64）。只读；wx 独占。 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const R = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));

const REF = "cap_20261007_233658", REFJOB = "3c793d7bda0f4ced86b20ac8076e7b0e";
const BOX = { x0: 0.0, x1: 4.2, y0: -2.6, y1: 4.0, z0: -0.15, z1: 2.4 };
const TARGET = 250000;

const refFrames = R.loadFrames(ROOT, REF, R.levelingBinding(ROOT, REF, REFJOB), true).frames;   /* denoised */
const pts = [];
for (const c0 of refFrames) for (let k = 0; k < c0.length; k += 4) {
    const x = c0[k], y = c0[k + 1], z = c0[k + 2];
    if (x < BOX.x0 || x > BOX.x1 || y < BOX.y0 || y > BOX.y1 || z < BOX.z0 || z > BOX.z1) continue;
    pts.push(x, y, z);
}
const nAll = pts.length / 3;
const stride = Math.max(1, Math.ceil(nAll / TARGET));
const n = Math.floor(nAll / stride);
const pos = new Int16Array(n * 3);
let j = 0;
for (let i = 0; i < nAll; i += stride) {
    pos[j * 3] = Math.round(pts[i * 3] * 1000); pos[j * 3 + 1] = Math.round(pts[i * 3 + 1] * 1000); pos[j * 3 + 2] = Math.round(pts[i * 3 + 2] * 1000);
    j++;
}
fs.writeFileSync(path.join(__dirname, "v2_view_refpts.js"),
    "window.RETV2_REFPT=" + JSON.stringify({ n, nAll, stride, pos: Buffer.from(pos.buffer, pos.byteOffset, pos.byteLength).toString("base64") }) + ";\n", { flag: "wx" });
console.log(`refpts: box 内 ${nAll} → 抽稀 ${stride}:1 → ${n}（写入 v2_view_refpts.js）`);
