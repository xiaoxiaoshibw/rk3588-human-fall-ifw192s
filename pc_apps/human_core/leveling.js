/* leveling.js — 传感系 → leveled 变换。
 *
 * 两种注入方式（生产两条路线一致）：
 *  1) 外部 R/T （路线 B： 空场模板 TLS R+T，9+3 向量）
 *  2) meta.leveling 已应用（路线 A： 浏览器层已 leveled — 则不再变换）
 *
 * 本模块负责「拿到 leveled xyzi, Float32Array [x,y,z,i]*」。不透传 intensity
 * 之外的 metadata（ring/timestamp 留在 data_loader 的 raw 副本）。
 */
"use strict";

/* 9 元 R 行主序（与 detect_overlay.js R = flatten 3x3 一致） */
function apply_rt(x, y, z, R, T) {
    var lx = R[0] * x + R[1] * y + R[2] * z + T[0];
    var ly = R[3] * x + R[4] * y + R[5] * z + T[1];
    var lz = R[6] * x + R[7] * y + R[8] * z + T[2];
    return [lx, ly, lz];
}

/* 传感系 xyzi → leveled xyzi. 如果 already_leveled=true 直通拷。 */
function level_frame(xyzi, R, T, already_leveled) {
    var n = xyzi.length / 4;
    if (already_leveled) return xyzi.slice(0);
    var out = new Float32Array(n * 4);
    for (var k = 0; k < n; k++) {
        var o = k * 4;
        var l = apply_rt(xyzi[o], xyzi[o + 1], xyzi[o + 2], R, T);
        out[o] = l[0]; out[o + 1] = l[1]; out[o + 2] = l[2];
        out[o + 3] = xyzi[o + 3];           /* intensity 不变 */
    }
    return out;
}

/* meta 是否携带已生效的 leveling （与 detect_overlay 一致） */
function is_leveled_in_meta(meta) {
    return !!(meta && meta.leveling);
}

module.exports = {
    apply_rt: apply_rt,
    level_frame: level_frame,
    is_leveled_in_meta: is_leveled_in_meta,
};
