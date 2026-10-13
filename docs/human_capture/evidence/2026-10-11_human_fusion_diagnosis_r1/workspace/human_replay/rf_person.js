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

        /* PCA: 协方差对称 3x3. 与 python np.linalg.eigh 对齐。原三角闭式解在此 seed 上
         * 给 ev=[0.0821,0.0821,0.0033] 与 Python eigh [0.0909,0.0740,0.0042] 不符 — 闭式公式
         * 对 3x3 协方差数值不稳, 改为幂迭代 + 收缩 (PSD 适用), 一次性给出 ev 和 |V[2,k]|。
         * Python 端 frame_feature.py: w, V = np.linalg.eigh(cov); idx = argsort(-w); V = V[:, idx]. */
        var m11 = cxx, m12 = cxy, m13 = cxz, m22 = cyy, m23 = cyz, m33 = czz;
        var pca = (function () {
            function matvec(v) {
                return [m11*v[0]+m12*v[1]+m13*v[2],
                        m12*v[0]+m22*v[1]+m23*v[2],
                        m13*v[0]+m23*v[1]+m33*v[2]];
            }
            function dot(u, v) { return u[0]*v[0]+u[1]*v[1]+u[2]*v[2]; }
            function norm(v) { return Math.sqrt(dot(v,v)); }
            function deflate(v, u1, u2) {
                var d1 = dot(v,u1);
                var r = [v[0]-d1*u1[0], v[1]-d1*u1[1], v[2]-d1*u1[2]];
                if (u2) {
                    var d2 = dot(r,u2);
                    r = [r[0]-d2*u2[0], r[1]-d2*u2[1], r[2]-d2*u2[2]];
                }
                return r;
            }
            function power_iter(seed, u1, u2) {
                var v = seed.slice();
                if (u1) v = deflate(v, u1, u2);
                var nv = norm(v);
                if (nv < 1e-12) return null;
                v = [v[0]/nv, v[1]/nv, v[2]/nv];
                for (var it = 0; it < 100; it++) {
                    var w = matvec(v);
                    if (u1) w = deflate(w, u1, u2);
                    var nw = norm(w);
                    if (nw < 1e-12) return null;
                    var vn = [w[0]/nw, w[1]/nw, w[2]/nw];
                    var d = Math.abs(dot(vn, v));
                    v = vn;
                    if (d > 1 - 1e-9) break;
                }
                return { vec: v, lam: dot(v, matvec(v)) };
            }
            var eig1 = power_iter([1,0.5,0.3], null, null);
            if (!eig1) return { ev: [0,0,0], az: [0,0,0] };
            var eig2 = power_iter([0.3,1,0.5], eig1.vec, null);
            if (!eig2) return { ev: [eig1.lam, 0, 0], az: [Math.abs(eig1.vec[2]), 0, 0] };
            var u = eig1.vec, v2 = eig2.vec;
            var v3 = [u[1]*v2[2]-u[2]*v2[1],
                      u[2]*v2[0]-u[0]*v2[2],
                      u[0]*v2[1]-u[1]*v2[0]];
            var eig3 = { vec: v3, lam: dot(v3, matvec(v3)) };
            /* 特征值 ev 降序排列 (fv[32..34] = desc, 与 np.sort(w)[::-1] 一致).
             * 但 fv[37..39] 复刻 Python frame_feature.py 的实际行为:
             *   w_sorted_desc = np.sort(w)[::-1]; idx = np.argsort(-w_sorted_desc)
             *   argsort 作用于已降序的 w, 结果恒为 [0,1,2], V=V[:,idx] 等于不变,
             *   即 fv[37..39] 取的是 eigh 原始升序 (最小/中/最大) 特征值对应列的 z 分量。
             * 生产 rf_person_v1.json 在此固化顺序下训练, JS 必须复刻 (不是修 Python 排序链 bug)。 */
            var desc = [
                { lam: eig1.lam, az: Math.abs(eig1.vec[2]) },
                { lam: eig2.lam, az: Math.abs(eig2.vec[2]) },
                { lam: eig3.lam, az: Math.abs(eig3.vec[2]) }
            ].sort(function (a, b) { return b.lam - a.lam; });
            var asc = [
                { lam: eig1.lam, az: Math.abs(eig1.vec[2]) },
                { lam: eig2.lam, az: Math.abs(eig2.vec[2]) },
                { lam: eig3.lam, az: Math.abs(eig3.vec[2]) }
            ].sort(function (a, b) { return a.lam - b.lam; });
            return {
                ev: [desc[0].lam, desc[1].lam, desc[2].lam],
                az: [asc[0].az, asc[1].az, asc[2].az]
            };
        })();
        var ev = pca.ev;
        var axis_z = pca.az;

        /* 特征向量: 与 python np.linalg.eigh 对齐。协方差是 PSD, 用幂迭代 + 收缩求三个本征对。
         * Python 端 frame_feature.py: w, V = np.linalg.eigh(cov); idx = argsort(-w); V = V[:, idx];
         * fv[37..39] = abs(V[2, 0..2]) 即 主/次/三轴 列向量的 z 分量绝对值。
         * 3x3 PSD 幂迭代对最大/次大本征对收敛快 (max 100 iter, tol 1e-9), 第三轴取前两轴正交补。
         * 收敛失败 fallback 为 [0,0,0]。 */
        /* fv[41] r_xy_spread = std(||xy||₂), 与 Python np.std(np.sqrt(x²+y²)) 对齐 */
        var rxy_arr = new Array(n);
        var rxy_mean = 0;
        for (var i = 0; i < n; i++) {
            rxy_arr[i] = Math.sqrt(frame.x[i] * frame.x[i] + frame.y[i] * frame.y[i]);
            rxy_mean += rxy_arr[i];
        }
        rxy_mean /= n;
        var rxy = 0;
        for (var i = 0; i < n; i++) {
            var dr = rxy_arr[i] - rxy_mean;
            rxy += dr * dr;
        }
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
        fv[37] = axis_z[0]; fv[38] = axis_z[1]; fv[39] = axis_z[2];
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
