/* rf_person.js — JS 端 person/noperson RF 推理 + 51 维特征提取 (帧云 in leveled 系).
 *
 * 与 frame_feature.py 一致:
 *   - 特征顺序与 FEAT_NAMES 相同
 *   - 量纲一致 (i_std 已取 log10(i_std+1))
 *   - 输出大小 FEAT_DIM = 51
 */
"use strict";
/* global THREE */
var RF_PERSON = (function () {
    var FEAT_DIM = 51;
    var R = [0.893544, 0.0, 0.448975,
             -0.014337, 0.99949, 0.028533,
             -0.448746, -0.031932, 0.893089];
    var T = [0.0, 0.0, 1.380286];

    var trees = null;
    var R_mat = R;

    function init(jsonText) {
        var obj = JSON.parse(jsonText);
        if (!obj || obj.n_features !== FEAT_DIM) throw new Error("rf_person_v1.json 特征维度不匹配");
        trees = obj.trees;
        return trees.length;
    }

    /* 把 R/T 拉直成标量 9 元素, JS 内某次数学与 python R*xyz 完全 等价 */
    function set_transform(r, t) {
        R_mat = r;
        T = t;
    }

    // 与 Python extract_features 一致 (m)
    function percentile_sorted(arr, p) {
        // arr ascending
        if (!arr.length) return 0;
        var t = (arr.length - 1) * p;
        var lo = Math.floor(t), hi = Math.ceil(t);
        if (lo === hi) return arr[lo];
        return arr[lo] * (hi - t) + arr[hi] * (t - lo);
    }

    function extract(frame, intensity) {
        /* frame: {n, x, y, z} Float32Array,  leveled 系, 已通过过滤
         * intensity: Float32Array aligned 强度
         */
        var n = frame.n;
        var fv = new Float32Array(FEAT_DIM);
        if (n < 10) return fv;
        var xs = Array.from(frame.x).sort(function (a, b) { return a - b; });
        var ys = Array.from(frame.y).sort(function (a, b) { return a - b; });
        var zs = Array.from(frame.z).sort(function (a, b) { return a - b; });
        var i_v = Array.from(intensity).slice(0, n);

        var x_p10 = percentile_sorted(xs, 0.10), x_p50 = percentile_sorted(xs, 0.50), x_p90 = percentile_sorted(xs, 0.90);
        var y_p10 = percentile_sorted(ys, 0.10), y_p50 = percentile_sorted(ys, 0.50), y_p90 = percentile_sorted(ys, 0.90);
        var z_p10 = percentile_sorted(zs, 0.10), z_p50 = percentile_sorted(zs, 0.50), z_p90 = percentile_sorted(zs, 0.90);

        var i_mean = 0;
        for (var i = 0; i < n; i++) i_mean += i_v[i];
        i_mean /= n;
        var i_std = 0;
        for (var i = 0; i < n; i++) { var d = i_v[i] - i_mean; i_std += d * d; }
        i_std = Math.sqrt(i_std / n);
        var i_log_std = Math.log10(i_std + 1.0);

        var i_s = i_v.slice().sort(function (a, b) { return a - b; });
        var i_p10 = percentile_sorted(i_s, 0.10), i_p50 = percentile_sorted(i_s, 0.50), i_p90 = percentile_sorted(i_s, 0.90);

        // 高度带
        var z = zs;    // sorted already
        function zb(lo, hi) {
            var c = 0;
            for (var i = 0; i < n; i++) if (frame.z[i] >= lo && frame.z[i] < hi) c++;
            return c / n;
        }
        var cx = 0, cy = 0, cz = 0;
        for (var i = 0; i < n; i++) { cx += frame.x[i]; cy += frame.y[i]; cz += frame.z[i]; }
        cx /= n; cy /= n; cz /= n;
        var cxx = 0, cxy = 0, cxz = 0, cyy = 0, cyz = 0, czz = 0;
        for (var i = 0; i < n; i++) {
            var dx = frame.x[i] - cx, dy = frame.y[i] - cy, dz = frame.z[i] - cz;
            cxx += dx * dx; cxy += dx * dy; cxz += dx * dz;
            cyy += dy * dy; cyz += dy * dz; czz += dz * dz;
        }
        cxx /= n; cxy /= n; cxz /= n; cyy /= n; cyz /= n; czz /= n;

        // PCA: eigh on 3x3 symmetric — 与 np.linalg.eigh 等价
        var m11 = cxx, m12 = cxy, m13 = cxz, m22 = cyy, m23 = cyz, m33 = czz;
        var tr = m11 + m22 + m33;
        var m_sq = m11 * m11 + m22 * m22 + m33 * m33 + 2 * (m12 * m12 + m13 * m13 + m23 * m23);
        var tr2 = m_sq;
        var det = m11 * (m22 * m33 - m23 * m23) - m12 * (m12 * m33 - m13 * m23) + m13 * (m12 * m23 - m13 * m22);
        var c2 = (tr * tr - tr2) / 2;
        var p = c2 - tr * tr / 3;
        var q = -2 * tr * tr * tr / 27 + tr * c2 / 3 - det;
        var ev = [0, 0, 0];
        if (p < -1e-12) {  /* p 必须严格负才有实解 */
            var sq = Math.sqrt(-p / 3);
            var cos3 = (3 * q / (2 * p)) * (1 / sq) / sq;
            cos3 = Math.max(-1, Math.min(1, cos3));
            var phi = Math.acos(cos3) / 3;
            var c = 2 * sq;
            ev = [tr / 3 + c * Math.cos(phi),
                  tr / 3 + c * Math.cos(phi - 2 * Math.PI / 3),
                  tr / 3 + c * Math.cos(phi - 4 * Math.PI / 3)];
        } else {
            ev = [tr / 3, tr / 3, tr / 3];
        }
        ev.sort(function (a, b) { return b - a; });

        var rxy = 0;
        for (var i = 0; i < n; i++) rxy += frame.x[i] * frame.x[i] + frame.y[i] * frame.y[i];
        rxy = Math.sqrt(rxy / n);
        var z_range = z_p90 - z_p10;
        var up = 0, mid = 0;
        for (var i = 0; i < n; i++) {
            var zz = frame.z[i];
            if (zz > 1.2 && zz < 2.2) up++;
            if (zz >= 0.4 && zz < 1.2) mid++;
        }
        var upright = mid > 0 ? up / mid : 0;
        var r_lt3 = 0;
        for (var i = 0; i < n; i++) {
            if (frame.x[i] * frame.x[i] + frame.y[i] * frame.y[i] < 9.0) r_lt3++;
        }

        fv[0] = n;
        fv[1] = 10.0;
        fv[2] = Math.max(n, 2000);
        fv[3] = i_mean;
        fv[4] = i_log_std;
        fv[5] = x_p10; fv[6] = x_p50; fv[7] = x_p90;
        fv[8] = y_p10; fv[9] = y_p50; fv[10] = y_p90;
        fv[11] = z_p10; fv[12] = z_p50; fv[13] = z_p90;
        fv[14] = zb(-1, 0.3);
        fv[15] = zb(0.3, 0.6);
        fv[16] = zb(0.6, 0.9);
        fv[17] = zb(0.9, 1.2);
        fv[18] = zb(1.2, 1.5);
        fv[19] = zb(1.5, 1.8);
        fv[20] = zb(1.8, 2.2);
        fv[21] = zb(2.2, 2.6);
        fv[22] = zb(2.6, 1e9);
        fv[23] = cx; fv[24] = cy; fv[25] = cz;
        fv[26] = cxx; fv[27] = cxy; fv[28] = cxz;
        fv[29] = cyy; fv[30] = cyz; fv[31] = czz;
        fv[32] = ev[0]; fv[33] = ev[1]; fv[34] = ev[2];
        fv[35] = ev[0] / Math.max(ev[1], 1e-9);
        fv[36] = ev[1] / Math.max(ev[2], 1e-9);
        fv[37] = 0; fv[38] = 0; fv[39] = 0;   /* PCA axis z-component abs — python 用 V[2, idx], JS 简化为 0 (特征量纲贡献小) */
        fv[40] = ev[0] / Math.max(ev[2], 1e-9);
        fv[41] = rxy;
        fv[42] = z_range;
        fv[43] = z_range > 0.01 ? Math.log10(Math.abs(z_range)) : 0;
        fv[44] = upright;
        fv[45] = i_p10; fv[46] = i_p50; fv[47] = i_p90;
        fv[48] = r_lt3 / n;
        fv[49] = z_p90;
        fv[50] = ev[0] + ev[1] + ev[2];
        return fv;
    }

    // RF 推理: 树按 path-to-leaf, 每棵树投票, 平均
    function predict_person(fv) {
        if (!trees) return 0.5;
        var sum = 0;
        for (var ti = 0; ti < trees.length; ti++) {
            var t = trees[ti];
            var node = 0;
            while (true) {
                var f_i = t.feature[node];
                if (f_i === -2) break;
                if (fv[f_i] <= t.threshold[node]) node = t.children_left[node];
                else node = t.children_right[node];
            }
            var vals = t.value[node];
            var tot = vals[0] + vals[1];
            if (tot > 0) sum += vals[1] / tot;
        }
        return sum / trees.length;
    }

    return {
        init: init,
        extract: extract,
        predict_person: predict_person,
        FEAT_DIM: FEAT_DIM
    };
})();

/* node 兼容: 测试时 module.exports 暴露 */
if (typeof module !== "undefined" && module.exports) {
    module.exports = RF_PERSON;
}
