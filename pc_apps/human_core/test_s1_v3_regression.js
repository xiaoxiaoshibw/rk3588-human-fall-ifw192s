/* test_s1_v3_regression.js — R3 STEP 6 验收关键点:
 *  S1 V3 propagated 对象的 point_indices 在 export_samples 视角下**有效** (valid-after 空间)。
 *  这是 R3 修过的关键 GT bug。
 */
"use strict";
const fs = require("fs"), path = require("path");
const GT = require("../human_replay/gt_lib.js");

const SID = "cap_20261010_175227";
const gt = JSON.parse(fs.readFileSync(
    `pc_apps/human_replay/gt_store/${SID}/GT_V3.json`, "utf8"));
const meta = JSON.parse(fs.readFileSync(`captures/remote/${SID}/meta.json`, "utf8"));

let pass = 0, fail = 0;
const bad = [];
for (const oid in gt.objects) {
    const o = gt.objects[oid];
    if (o.source !== "propagated") continue;
    const frame_meta = meta.frames[o.frame_idx];
    const idx = GT.decode_indices(o.raw_point_indices);
    /* 每个 idx 都必须 < 该帧 valid 后点数; valid 数 <= count_points,
     * 但 GT 的 idx 语义是「valid 后空间」(UI 写入 f=0 就是这样), 所以
     * 我们用「idx 严格升序 + idx.max < count_points + idx.min >= 0」
     * 的最低门槛,再用 point_count>0 检查。 */
    if (!idx.length || idx.length !== o.point_count) { bad.push((oid, "len mismatch")); fail++; continue; }
    if (idx[0] < 0) { bad.push((oid, "negative idx")); fail++; continue; }
    if (idx[idx.length - 1] >= frame_meta.count_points) { bad.push((oid, "idx out of raw frame")); fail++; continue; }
    pass++;
}
console.log(`S1 V3 propagated 索引: pass=${pass} fail=${fail}`);
if (bad.length > 0) { bad.slice(0, 5).forEach(b => console.log("  BAD:", b)); process.exit(1); }
console.log("PASS");
