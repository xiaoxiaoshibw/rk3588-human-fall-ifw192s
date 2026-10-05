/* HR-W02 离线人体识别工作台 — 纯函数层：node 可测，零 DOM/THREE 依赖。
 *
 * 数据流假设（与 limb 支线根本教训对齐）：
 *   - 输入点云坐标**已经在 ground_offline_display 系**（配平后 z=0 是地板）。
 *     本文件不做二次配平；配平 transform 由浏览器层在加载时应用（leveled_latest），
 *     之后的候选/姿态判定都基于「z↑=离地面高度」这个 foundation。
 *   - 肢体支线 6 代算法锁家具（沙发 ≈ 高柜 ≈ 直立人 on z-range/xy-density/PCA 维度
 *     完全同形）→ 本工作台不尝试「全自动找所有人」。它给用户一个 **pin ROI** + 几何
 *     特征面板，让「这是人不是家具」由人眼裁决，几何只负责在 ROI 里量测躯干/头部/
 *     顶点姿态，跨帧 temporal 平滑。它回答的是「这个人此刻是什么姿态」，不是「人在哪」。
 *
 * 分层：所有阈值/几何/PCA 在本文件，node 直接测；human_detect.js 只做 Three.js 渲染。
 */
"use strict";

/* 与 human_replay_lib 的 28B/点契约一致；这里只消费 strided_f32_copy 拍平出的
 * [x,y,z,intensity]* 帧段（已应用 leveled transform）。 */

/* ---------------- 人形探测默认阈值（全部集中，node 可断言） ---------------- */
var DETECT = {
    /* 地面以上带：低于 Shin 的点是脚/地面噪声，高于 头顶带 的天花板剔除 */
    z_min_human: 0.20,      /* 脚踝以下忽略 */
    z_max_human: 2.20,      /* 高于 2.2m 的（吊柜/天花）剔除 */
    /* ROI 内人形本质几何门：直立度 / 顶高 / 厚度 */
    min_height_m: 0.90,     /* 拟合人形最小「躯干 z-range」。低于即非站立姿态 */
    max_height_standing_m: 1.55, /* 站立成年人身高下限（弯腰≈1.0-1.4 落此下） */
    max_width_m: 1.20,      /* 人躯干任何横向 PCA 范数不应超 1.2m（> 家具/墙） */
    min_upright_cos: 0.55,  /* 主扩散方向与 z 余弦下限：<此值即主躺/横 */
    /* 时间平滑：EMA α 越小越稳；>0.5 响应过快 */
    ema_alpha: 0.30,
    /* 跟丢：连续丢失 N 帧则放弃锁定（超过则认为此人已离场/重定） */
    max_lost_frames: 5,
};

/* 仅取 ROI 内 + 人形 z-带 的点。返回计数 n 与新 Float32Array（便于往复）。
 * xyzi: 拍平的 [x,y,z,i]*；roi = {x,y,r}（以 (x,y) 为心、半径 r 的圆柱）。
 * z0/z1 是 z 带下限/上限（默认用 DETECT.z_min/max）。 */
function points_in_cylinder(xyzi, roi, z0, z1) {
    z0 = (z0 == null) ? DETECT.z_min_human : z0;
    z1 = (z1 == null) ? DETECT.z_max_human : z1;
    var r2 = roi.r * roi.r, out = [];
    for (var k = 0; k < xyzi.length; k += 4) {
        var dx = xyzi[k] - roi.x, dy = xyzi[k + 1] - roi.y, z = xyzi[k + 2];
        if (z < z0 || z > z1) continue;
        if (dx * dx + dy * dy <= r2) out.push(xyzi[k], xyzi[k + 1], z, xyzi[k + 3]);
    }
    return new Float32Array(out);
}

/* 已排序 float 数组的分位（重复实现以隔离 human_replay_lib 依赖）。 */
function qtile(sorted, q) {
    if (!sorted.length) return NaN;
    var idx = q * (sorted.length - 1);
    var lo = Math.floor(idx), hi = Math.ceil(idx);
    if (lo === hi) return sorted[lo];
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

/* 3x3 对称阵特征分解（Jacobi 迭代，25 轮收敛；3x3 用最稳妥算法，不引入 linalg 库）。
 * 返回 {values:[3] desc, vectors:[3][3]}（vectors 列向量组）。对 3x3 这个规模
 * 手写 Jacobi 比上很多现成 Eig 更快、更可控——也是 limb_lib.py 的同款选择。 */
function _eig3_sym(m) {
    /* m: [[a,b,c],[b,d,e],[c,e,f]] */
    var a = [[m[0][0], m[0][1], m[0][2]],
             [m[1][0], m[1][1], m[1][2]],
             [m[2][0], m[2][1], m[2][2]]];
    var v = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    for (var it = 0; it < 25; it++) {
        /* 找最大非对角元素 */
        var p = 0, q = 1, mx = Math.abs(a[0][1]);
        if (Math.abs(a[0][2]) > mx) { mx = Math.abs(a[0][2]); p = 0; q = 2; }
        if (Math.abs(a[1][2]) > mx) { mx = Math.abs(a[1][2]); p = 1; q = 2; }
        if (mx < 1e-12) break;
        var app = a[p][p], aqq = a[q][q], apq = a[p][q];
        var theta = 0.5 * Math.atan2(2 * apq, aqq - app);
        var c = Math.cos(theta), s = Math.sin(theta);
        for (var k = 0; k < 3; k++) {
            var akp = a[k][p], akq = a[k][q];
            a[k][p] = c * akp - s * akq;
            a[k][q] = s * akp + c * akq;
        }
        for (var k2 = 0; k2 < 3; k2++) {
            var apk = a[p][k2], aqk = a[q][k2];
            a[p][k2] = c * apk - s * aqk;
            a[q][k2] = s * apk + c * aqk;
        }
        for (var k3 = 0; k3 < 3; k3++) {
            var vkp = v[k3][p], vkq = v[k3][q];
            v[k3][p] = c * vkp - s * vkq;
            v[k3][q] = s * vkp + c * vkq;
        }
    }
    var vals = [a[0][0], a[1][1], a[2][2]];
    /* 降序 idx */
    var order = [0, 1, 2].sort(function (i, j) { return vals[j] - vals[i]; });
    return {
        values: [vals[order[0]], vals[order[1]], vals[order[2]]],
        vectors: [
            [v[0][order[0]], v[1][order[0]], v[2][order[0]]],
            [v[0][order[1]], v[1][order[1]], v[2][order[1]]],
            [v[0][order[2]], v[1][order[2]], v[2][order[2]]],
        ],
    };
}

/* 单帧人形几何特征。输入 cyl = points_in_cylinder 结果（Float32Array [x,y,z,i]*），
 * （z= 已 leveled 高度）。返回 feats 对象或 {ok:false, reason}（点太少/退化时）。
 *
 * 每个量的物理含义（全部从同一 covariance 推出，零额外扫帧）：
 *   n           — 有效点数
 *   bbox        — {cx,cy,z0,z1, r_xy}  包围圆柱（axis=xy, range z0..z1, 即身高）
 *   pca         — {values, axis0_z, axis1_z, axis2_z}  主轴三向量的 z 余弦
 *   upright_cos — max(|axis_k|·z) 主轴中「最直立」那条；≈1 直立，≈0 平躺
 *   height_m    — z1 - z0（≈身高，立姿≈1.7-1.9；弯腰≈0.9-1.3；坐/躺≈0.3-0.8）
 *   z_spread    — z 与 xy 半径大 std（倾斜程度的直观替代量）
 *   pose        — "standing" | "bending" | "lying" | "unknown"（用 DETECT 门断言）
 */
function frame_human_features(cyl) {
    var n = cyl.length / 4;
    if (n < 12) return { ok: false, reason: "点太少(<%d)".replace("%d", String(12)), n: n };
    var i, sxx = 0, syy = 0, szz = 0, sxy = 0, sxz = 0, syz = 0;
    var sx = 0, sy = 0, szz2 = 0;
    var zs = [];
    for (i = 0; i < n; i++) {
        var x = cyl[i * 4], y = cyl[i * 4 + 1], z = cyl[i * 4 + 2];
        sx += x; sy += y; szz2 += z;
        sxx += x * x; syy += y * y; szz += z * z;
        sxy += x * y; sxz += x * z; syz += y * z;
        zs.push(z);
    }
    var mx = sx / n, my = sy / n, mz = szz2 / n;
    /* covariance */
    var cxx = sxx / n - mx * mx, cyy = syy / n - my * my, czz = szz / n - mz * mz;
    var cxy = sxy / n - mx * my, cxz = sxz / n - mx * mz, cyz = syz / n - my * mz;
    var eig = _eig3_sym([[cxx, cxy, cxz], [cxy, cyy, cyz], [cxz, cyz, czz]]);
    var ax0z = eig.vectors[0][2], ax1z = eig.vectors[1][2], ax2z = eig.vectors[2][2];
    /* 主轴 z 余弦：取**主扩散方向**(eig0，最大方差)与竖直 z 的夹角余弦绝对值。
     * 关键教训：不能取 max(|ax_k,z|) —— 对任何形状，3 条正交轴里必有一条近 z，
     * 取 max 恒≈1 会把躺平误判直立。直立 = 人的**最长方向**是竖的。 */
    var upcos = Math.abs(ax0z);

    /* r_xy：以**自形心**为轴的 2%/98% 分位半径 —— 不能用 hypot(x,y)，那含
     * 传感器到人的绝对位置偏移，会把远处的人撑出假「躯干粗」。 */
    var radc = [];
    for (i = 0; i < n; i++) radc.push(Math.hypot(cyl[i * 4] - mx, cyl[i * 4 + 1] - my));
    radc.sort(function (a, b) { return a - b; });
    var rxy = qtile(radc, 0.98);
    zs.sort(function (a, b) { return a - b; });
    var z0 = qtile(zs, 0.02), z1 = qtile(zs, 0.98);
    var height = z1 - z0;

    /* pose：三态在 (upcos, height) 平面线性可分，用两条铰接线即可：
     *   - 主扩散方向是否直立 (upcos ≥0.55)。躺平 upcos≈0.05，线 0.55 宽档。
     *   - 顶高是否达站立 (height ≥1.55)。站立成人 1.6-1.95，弯腰 1.0-1.4，门 1.55 居中。
     * standing = upcos≥门 且 身高≥1.55 且 躯干不超标
     * bending  = upcos≥门 但 1.55>身高≥0.9
     * lying    = upcos<门（主扩散横向）且 身高<0.9m
     * unknown  = 其它（躯干超宽 / upcos 高但几何异常 → 留给 score 判家具）*/
    var pose = "unknown";
    if (upcos >= DETECT.min_upright_cos) {
        if (height >= DETECT.max_height_standing_m && rxy <= DETECT.max_width_m) pose = "standing";
        else if (height >= DETECT.min_height_m) pose = "bending";
    } else {
        if (height < DETECT.min_height_m) pose = "lying";
    }

    /* 「人 vs 家具」信号得分：
     *  - upcos<0.55（主扩散横向）→ 直立项不给分：精确的躺平数据 upcos≈0.05，
     *    会给分的判定是「受测者主轴是否竖直」，不是有无任何一条近 z 的轴。
     *  - r_xy（真躯干半径，≤0.45 是人）<  判别衣柜/沙发的关键尺寸 —— 之前误用绝对
     *    hypot(x,y) 会把远处的人也撑成家具半径，现在是从形心算。
     *  - 身高在 1.3..2.1m 区间是站立成人典型；家具也常见，但配合 rxy 联合判。 */
    var score = 0;
    if (upcos >= 0.80) score += 2;
    else if (upcos >= 0.60) score += 1;
    else if (upcos >= 0.55) { /* 门边：不加 */ }
    if (height >= 1.30 && height <= 2.10) score += 2;
    else if (height >= 0.90 && height <= 2.30) score += 1;
    if (rxy <= 0.45) score += 2;
    else if (rxy <= 0.60) score += 1;
    if (n >= 60) score += 1;
    var is_human_like = score >= 5;

    return {
        ok: true, n: n, score: score, is_human_like: is_human_like,
        bbox: { cx: mx, cy: my, cz: mz, z0: z0, z1: z1, r_xy: rxy },
        cov: { xx: cxx, yy: cyy, zz: czz, xy: cxy, xz: cxz, yz: cyz },
        pca: { values: eig.values, axis0_z: ax0z, axis1_z: ax1z, axis2_z: ax2z,
               axis0: eig.vectors[0], axis1: eig.vectors[1], axis2: eig.vectors[2] },
        upright_cos: upcos, height_m: height,
        pose: pose,
        reason: null,
    };
}

/* 跨帧 EMA 平滑器（复刻 limb_lib.Smooth 的最简版：EMA + 突变保护 + 跟丢重置）。
 * 保护：当 raw 与 smoothed 相距超过 0.5m（突变），直接采纳 raw（不追滑）。
 * 丢失：push(null) 增 lost 计数；超过 max_lost_frames 则 reset。 */
function EmaTracker(alpha) {
    this.alpha = (alpha == null) ? DETECT.ema_alpha : alpha;
    this.smoothed = null;   /* {x,y,z,upcos,height,pose} */
    this.lost = 0;
}
EmaTracker.prototype.push = function (feat) {
    if (!feat || !feat.ok) {
        this.lost++;
        if (this.lost > DETECT.max_lost_frames) this.reset();
        return this.smoothed;
    }
    this.lost = 0;
    var cur = {
        x: feat.bbox.cx, y: feat.bbox.cy, z: feat.bbox.z1,
        upcos: feat.upright_cos, height: feat.height_m, pose: feat.pose,
        score: feat.score, is_human_like: feat.is_human_like, n: feat.n,
    };
    if (!this.smoothed) { this.smoothed = cur; return this.smoothed; }
    var dx = cur.x - this.smoothed.x, dy = cur.y - this.smoothed.y;
    if (Math.hypot(dx, dy) > 0.5) { this.smoothed = cur; return this.smoothed; }  /* 突变跳变 */
    var a = this.alpha;
    this.smoothed = {
        x: this.smoothed.x + a * dx,
        y: this.smoothed.y + a * dy,
        z: this.smoothed.z + a * (cur.z - this.smoothed.z),
        upcos: this.smoothed.upcos + a * (cur.upcos - this.smoothed.upcos),
        height: this.smoothed.height + a * (cur.height - this.smoothed.height),
        pose: cur.pose,      /* 姿态离散量不平滑，直接采纳最新 */
        score: cur.score, is_human_like: cur.is_human_like, n: cur.n,
    };
    return this.smoothed;
};
EmaTracker.prototype.reset = function () { this.smoothed = null; this.lost = 0; };

/* 从 smoothed 状态生成一个 axis-aligned 人体 bbox（Three BoxGeometry 友好的形状），
 * 返回 {center:[3], size:[3]}；size 用默认人形宽 0.5/0.5，长度=height_m。 */
function smoothed_to_box(sm) {
    if (!sm) return null;
    return {
        center: [sm.x, sm.y, sm.z / 2],
        size: [0.5, 0.5, Math.max(sm.z, 0.3)],
    };
}

/* node 测试导出 */
var _api = {
    DETECT: DETECT,
    points_in_cylinder: points_in_cylinder,
    frame_human_features: frame_human_features,
    qtile: qtile,
    EmaTracker: EmaTracker,
    smoothed_to_box: smoothed_to_box,
    _eig3_sym: _eig3_sym,
};
if (typeof module !== "undefined" && module.exports) { module.exports = _api; }
if (typeof globalThis !== "undefined") { globalThis.human_detect_lib = _api; }
