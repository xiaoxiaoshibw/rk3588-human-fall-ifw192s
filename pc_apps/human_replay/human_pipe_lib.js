/* HR-W03 人体识别算法初代 — 纯函数层：node 可测，零 DOM/THREE 依赖。
 *
 * 链路（用户 2026-10-05 拍板；2026-10-06 W03-R2 小步升级）：Raw → Denoise(有限+距离窗) →
 * [Ground Leveling 已在载入时 apply] → 工作空间裁剪(z) → 3D 背景体素去除 →
 * XY 体素聚类 → 簇特征 → 硬门 × 证据联合判定 → 跟踪 + 时间确认 → Fall 判别
 *
 * 关键设计（对应 limb v1..v6 失败）：
 *   - 背景 = 3D 体素两级静态：strong 占用率 ≥0.85；supported ≥0.65 且逐帧形心
 *     抖动 ≤0.05m 且 26 邻域 strong ≥2（补遮挡/采样空洞）。静立 ≥85% 帧的人
 *     仍会被吞进背景（limb v5 同款已知边界，UI 提示；不是 bug）。
 *   - 工作空间裁剪：z ∈ [0.10, 2.50]，顶棚/吊柜上沿不进前景/背景（不叫去噪）。
 *   - 聚类只保「候选前景」，不做硬「是人」；UI 颜色 = 联合判定（硬门 × 证据）：
 *     绿 = CONFIRMED_HUMAN（硬门过 + HUMAN_SHAPE + 3/5 帧时间确认），
 *     紫 = HUMAN_CANDIDATE，灰 = NON_HUMAN。
 *   - Fall 判别双条件缺一不可：主直立度崩到 <0.45 且 身高<0.9m 持续不回升；
 *     弯腰 (upcos≥0.55 + 身高 1.0~1.5 + 回站) 不触发。
 *
 * 记忆/吞吐预算：165 帧 × 4.9w 点；体素化单遍 O(N)，只存累加器
 * (n, Σx, Σy, Σz, Σxx, Σyy, Σzz, Σxy, Σxz, Σyz, zmin, zmax)，零点留存。
 */
"use strict";

/* ---------------- 全部阈值集中 ---------------- */
var PIPE = {
    /* 1 · Denoise（有限 + 距离窗；工作空间裁剪见 z_max_m） */
    range_min_m: 0.35,       /* 自车杂散圈 */
    range_max_m: 25.0,
    voxel_m: 0.15,           /* 聚类统一体素边长（XY 柱） */
    /* 2 · 工作空间裁剪（已配平系 z=0=地板；配平离线，不在本链路） */
    ground_keep_below_m: 0.10, /* z < 此值视为地面/脚面杂散，剔除 */
    z_max_m: 2.50,             /* z > 此值（顶棚/吊柜上沿）不进前景/背景 */
    /* 3 · 背景建模（3D 体素两级静态；离线跑全帧一次） */
    bg_voxel_xy: 0.15,
    bg_voxel_z: 0.12,
    bg_hit_min_pts: 2,        /* 每帧命中该体素至少这么多点（抗离群单点） */
    bg_occ_strong: 0.85,      /* 强静态：全帧占用率 ≥ 此值 */
    bg_occ_supported: 0.65,   /* 邻域支持静态：占用率 ≥ 此值 + 抖动/邻域门 */
    bg_jitter_max: 0.05,      /* 逐帧形心 RMS 抖动上限（m） */
    bg_neighbor_min: 2,       /* 26 邻域内 strong 体素数下限 */
    bg_match_radius: 0.12,    /* 前景匹配半径：点到静态体素全帧形心的距离 */
    /* 4 · 聚类 */
    cluster_min_voxels: 3,    /* 候选簇最小体素数（≈0.34m 直排） */
    cluster_neighbor_hops: 1, /* XY 4 邻 BFS */
    /* 5 · 人体候选判定（基于簇协方差 + 高度带） */
    human_n_min: 60,
    human_height_min: 0.90,
    human_height_max: 2.30,
    human_width_max: 0.70,   /* 2σ 人体躯干半径上限 — 肩/胸宽 0.35m × 2σ */
    human_radius_max: 0.45,  /* 2σ 体素径向 quantile 上限 — 更鲁棒的衣柜判据 */
    human_upcos_min: 0.50,   /* 主扩散方向直立度下限 */
    /* 5b · 证据层（逐高度带结构 — 与 HR-07 全局统计不同维度）：
     * 衣柜/盒体：每带 σ_xy 恒定 (spread_cv≈0)、XY 平面强各向异性（正面=平面 aniso≫4）
     * 人：腿细躯宽头小 → spread_cv≥0.18；体积形 → aniso≤3 */
    band_edges: [0, .3, .6, .9, 1.2, 1.5, 1.8, 2.2, 3.0],
    ev_band_min_pts_abs: 15,     /* 带最少点数才入证据 */
    ev_band_min_pts_frac: 0.04,  /* 或占簇点数比例 */
    ev_bands_min: 3,             /* 至少多少带才评价 spread_cv */
    ev_spread_cv_person: 0.18,   /* σ_xy 随高度变化率 ≥ 此值 → 人形结构 */
    ev_spread_cv_box: 0.15,      /* ≤ 此值 → 均匀体特征 */
    ev_aniso_box: 4.0,           /* XY 各向异性 ≥ 此值 → 平面/盒特征（不依赖 cv） */
    ev_aniso_box_soft: 2.5,      /* cv 低时再叠加较软 aniso 门 */
    ev_aniso_person: 3.0,        /* 人形各向异性上限 */
    /* 5d · 联合判定时间确认（防瞬时闪绿） */
    human_confirm_window: 5,     /* 滑窗帧数 */
    human_confirm_votes: 3,      /* 窗内 CONFIRMED_HUMAN 票数下限 */
    human_confirm_min_age: 3,    /* track 最小年龄（帧） */
    /* 6 · 跟踪 */
    track_gate_xy_m: 0.75,   /* 贪心最近邻分配门 */
    track_lost_max: 8,       /* 帧，超该值 track 关闭 */
    ema_alpha: 0.35,
    /* 7 · Fall 判别（秒单位由调用方换帧数：fps≈10） */
    fall_upcos_max: 0.45,    /* 主直立度崩什侠値（躺平 ~0.05） */
    fall_height_max: 0.90,
    fall_sustain_frames: 10, /* 持续 1s 才算躺，过滤坐姿/蹲姿一过性 */
    fall_recover_frames: 5,  /* 回站侦测窗：躺后 N 帧回站 → 取消 Fall */
};

/* 体素键（XY 柱）：聚类/证据层复用。 */
var _V_INV = 1 / PIPE.voxel_m;
function key_vox(x, y) {
    return Math.floor(x * _V_INV) + "," + Math.floor(y * _V_INV);
}

/* 背景 3D 体素键（整数编码，供 26 邻域枚举）。 */
var _BG_BASE = 8192, _BG_OFF = 4096;
function _bg_key_ijk(ix, iy, iz) {
    return ((ix + _BG_OFF) * _BG_BASE + (iy + _BG_OFF)) * _BG_BASE + (iz + _BG_OFF);
}
function key_bg(x, y, z) {
    return _bg_key_ijk(Math.floor(x / PIPE.bg_voxel_xy), Math.floor(y / PIPE.bg_voxel_xy),
                       Math.floor(z / PIPE.bg_voxel_z));
}
function _bg_decode(key) {
    var iz = key % _BG_BASE; key = (key - iz) / _BG_BASE;
    var iy = key % _BG_BASE;
    return [(key - iy) / _BG_BASE - _BG_OFF, iy - _BG_OFF, iz - _BG_OFF];
}

/* ---- 1· 去噪：有限点 + 距离窗 + 换 column 体素键 ----
 * 返回新 Float32Array[x,y,z,i]*；调用方零拷贝消费。 */
function denoise(xyzi) {
    var out = [], rmin2 = PIPE.range_min_m * PIPE.range_min_m, rmax2 = PIPE.range_max_m * PIPE.range_max_m;
    for (var k = 0; k < xyzi.length; k += 4) {
        var x = xyzi[k], y = xyzi[k + 1], z = xyzi[k + 2], i = xyzi[k + 3];
        var r2 = x * x + y * y + z * z;
        if (!isFinite(r2) || r2 < rmin2 || r2 > rmax2) continue;
        out.push(x, y, z, i);
    }
    return new Float32Array(out);
}

/* ---- 2· 体素化（XY 柱）+ 协方差累加器 ----
 * vox = Map<"ix,iy", {n,sx,sy,sz,sxx,syy,szz,sxy,sxz,syz,zmin,zmax}>;
 * key 是体素中心坐标索引（ix = Math.floor(x / voxel_m)）。 */
function voxelize(xyzi) {
    var vox = new Map();
    var inv = 1 / PIPE.voxel_m;
    for (var k = 0; k < xyzi.length; k += 4) {
        var x = xyzi[k], y = xyzi[k + 1], z = xyzi[k + 2];
        var key = Math.floor(x * inv) + "," + Math.floor(y * inv);
        var a = vox.get(key);
        if (!a) {
            a = { n: 0, sx: 0, sy: 0, sz: 0, sxx: 0, syy: 0, szz: 0,
                  sxy: 0, sxz: 0, syz: 0, zmin: z, zmax: z };
            vox.set(key, a);
        }
        a.n++; a.sx += x; a.sy += y; a.sz += z;
        a.sxx += x * x; a.syy += y * y; a.szz += z * z;
        a.sxy += x * y; a.sxz += x * z; a.syz += y * z;
        if (z < a.zmin) a.zmin = z;
        if (z > a.zmax) a.zmax = z;
    }
    return vox;
}

/* ---- 3· 背景建模：3D 体素两级静态（强 / 邻域支持）----
 * 输入 frames_xyzi: 一个数组，每项是一帧的 Float32Array[x,y,z,i]（已 denoise）。
 * 每帧命中 = 该体素当帧点数 ≥ bg_hit_min_pts（抗离群单点）；
 * strong    = 全帧占用率 ≥ bg_occ_strong；
 * supported = 占用率 ≥ bg_occ_supported，且逐帧形心 RMS 抖动 ≤ bg_jitter_max，
 *             且 26 邻域内 strong 体素数 ≥ bg_neighbor_min（补遮挡/采样空洞）。
 * opts.drop_ground（缺省 true）先剔 z < ground_keep_below_m 再计占用——
 *   **必须开**：否则地板每根柱全帧都有点 → 整片地板被误判背景，人被吞脚。
 * 工作空间上沿 z_max_m 同步裁剪。
 * 返回 Map<key, {x,y,z,hits,tier}>；x/y/z 为全帧形心（前景匹配用）。 */
function build_static_map(frames_xyzi, opts) {
    opts = opts || {};
    var drop_ground = opts.drop_ground !== false;   /* 缺省 true：默认剔地面 */
    var nframes = frames_xyzi.length;
    var stats = new Map(), per = new Map();
    for (var f = 0; f < nframes; f++) {
        per.clear();
        var frame = frames_xyzi[f];
        for (var k = 0; k < frame.length; k += 4) {
            var z = frame[k + 2];
            if (drop_ground && z < PIPE.ground_keep_below_m) continue;  /* 贴地点先剔 */
            if (z > PIPE.z_max_m) continue;                             /* 工作空间上沿 */
            var key = key_bg(frame[k], frame[k + 1], z);
            var a = per.get(key);
            if (!a) { a = { n: 0, sx: 0, sy: 0, sz: 0 }; per.set(key, a); }
            a.n++; a.sx += frame[k]; a.sy += frame[k + 1]; a.sz += z;
        }
        per.forEach(function (a, key) {
            if (a.n < PIPE.bg_hit_min_pts) return;                     /* 每帧命中门 */
            var s = stats.get(key);
            if (!s) { s = { hits: 0, cx: 0, cy: 0, cz: 0, mx: 0, my: 0, mz: 0 }; stats.set(key, s); }
            s.hits++;
            /* Welford：逐帧形心均值 + 偏差平方和（抖动 = sqrt(m2/hits)） */
            var px = a.sx / a.n, py = a.sy / a.n, pz = a.sz / a.n;
            var dx = px - s.cx, dy = py - s.cy, dz = pz - s.cz;
            s.cx += dx / s.hits; s.mx += dx * (px - s.cx);
            s.cy += dy / s.hits; s.my += dy * (py - s.cy);
            s.cz += dz / s.hits; s.mz += dz * (pz - s.cz);
        });
    }
    var thr_strong = Math.ceil(nframes * PIPE.bg_occ_strong);
    var thr_sup = Math.ceil(nframes * PIPE.bg_occ_supported);
    var out = new Map(), strong = new Set();
    stats.forEach(function (s, key) {
        if (s.hits >= thr_strong) {
            out.set(key, { x: s.cx, y: s.cy, z: s.cz, hits: s.hits, tier: "strong" });
            strong.add(key);
        }
    });
    stats.forEach(function (s, key) {
        if (s.hits < thr_sup || s.hits >= thr_strong) return;
        var jit = Math.sqrt(Math.max(s.mx, s.my, s.mz) / s.hits);
        if (jit > PIPE.bg_jitter_max) return;
        var nb = 0, ij = _bg_decode(key);
        for (var a = -1; a <= 1 && nb < PIPE.bg_neighbor_min; a++)
            for (var b = -1; b <= 1 && nb < PIPE.bg_neighbor_min; b++)
                for (var c = -1; c <= 1 && nb < PIPE.bg_neighbor_min; c++)
                    if ((a || b || c) && strong.has(_bg_key_ijk(ij[0] + a, ij[1] + b, ij[2] + c))) nb++;
        if (nb >= PIPE.bg_neighbor_min)
            out.set(key, { x: s.cx, y: s.cy, z: s.cz, hits: s.hits, tier: "supported" });
    });
    return out;
}

/* ---- 4· 前景 = 点级(工作空间裁剪 + 有界背景匹配)后再体素化 ----
 * 工作空间：z ∈ [ground_keep_below_m, z_max_m]（顶棚/吊柜上沿不进后续）。
 * 背景匹配：点的 3×3×3 体素邻域内任一静态体素，其全帧形心距点 < bg_match_radius
 * 即删——比「是否恰好落进同一整数格」更抗量化/配平抖动。
 * 返回 { vox_fg, n_fg, n_dropped, fg_xyzi } — fg_xyzi 是剔净后的点(每帧新分配 Float32Array)。 */
function extract_foreground(xyzi, static_map) {
    var out = [], n_in = xyzi.length / 4;
    for (var k = 0; k < xyzi.length; k += 4) {
        var x = xyzi[k], y = xyzi[k + 1], z = xyzi[k + 2], i = xyzi[k + 3];
        if (z < PIPE.ground_keep_below_m || z > PIPE.z_max_m) continue;  /* 工作空间裁剪 */
        if (static_map && _bg_match(static_map, x, y, z)) continue;      /* 有界背景匹配 */
        out.push(x, y, z, i);
    }
    var fg_xyzi = new Float32Array(out);
    var vox_fg = voxelize(fg_xyzi);
    return { vox_fg: vox_fg, n_fg: fg_xyzi.length / 4, n_dropped: n_in - fg_xyzi.length / 4,
             fg_xyzi: fg_xyzi };
}

/* 有界背景匹配：只查 3×3×3 体素邻域（邻域跨度 ≥ 匹配半径，两格远不可能命中）。 */
function _bg_match(static_map, x, y, z) {
    var r2 = PIPE.bg_match_radius * PIPE.bg_match_radius;
    var ix = Math.floor(x / PIPE.bg_voxel_xy), iy = Math.floor(y / PIPE.bg_voxel_xy),
        iz = Math.floor(z / PIPE.bg_voxel_z);
    for (var a = -1; a <= 1; a++) for (var b = -1; b <= 1; b++) for (var c = -1; c <= 1; c++) {
        var rec = static_map.get(_bg_key_ijk(ix + a, iy + b, iz + c));
        if (!rec) continue;
        var dx = rec.x - x, dy = rec.y - y, dz = rec.z - z;
        if (dx * dx + dy * dy + dz * dz < r2) return true;
    }
    return false;
}

/* ---- 4b· 保守孤立前景清理（R2.6）----
 * 单遍快照语义：先按清理前的 3D 前景体素图算出全部删除集合，再一次性删点；
 * 不递归、不多轮、不传播（删掉的体素不参与第二轮邻域判定）。
 * 规则（严格）：voxel 点数 ≤1 且 26 邻域内不存在任何前景 voxel → 删该 voxel 的点；
 * 其余全保留。只判断「邻域是否存在前景 voxel」，不设邻居点数阈值。
 * 复用背景 3D 体素栅格（bg_voxel_xy/z），不新增参数；不是 SOR/ROR/形态学。
 * 返回 { xyzi, before, after, removed_points, removed_voxels, fg_voxels }。 */
function cleanup_isolated_fg(xyzi) {
    var before = xyzi.length / 4;
    var counts = new Map();
    var i;
    for (i = 0; i < xyzi.length; i += 4) {
        var key = key_bg(xyzi[i], xyzi[i + 1], xyzi[i + 2]);
        counts.set(key, (counts.get(key) || 0) + 1);
    }
    var doomed = new Set();
    counts.forEach(function (n, key) {
        if (n > 1) return;                              /* 多点体素永不删 */
        var ij = _bg_decode(key);
        for (var a = -1; a <= 1; a++) for (var b = -1; b <= 1; b++) for (var c = -1; c <= 1; c++) {
            if (!a && !b && !c) continue;
            if (counts.has(_bg_key_ijk(ij[0] + a, ij[1] + b, ij[2] + c))) return;  /* 有前景邻居 → 保留 */
        }
        doomed.add(key);
    });
    if (!doomed.size) return { xyzi: xyzi, before: before, after: before,
                               removed_points: 0, removed_voxels: 0, fg_voxels: counts.size };
    var out = [];
    for (i = 0; i < xyzi.length; i += 4) {
        if (doomed.has(key_bg(xyzi[i], xyzi[i + 1], xyzi[i + 2]))) continue;
        out.push(xyzi[i], xyzi[i + 1], xyzi[i + 2], xyzi[i + 3]);
    }
    return { xyzi: new Float32Array(out), before: before, after: out.length / 4,
             removed_points: before - out.length / 4, removed_voxels: doomed.size,
             fg_voxels: counts.size };
}

/* ---- 5· 聚类：XY 4 邻 BFS 连通体素团 ---- */
function cluster_voxels(vox_fg) {
    var remaining = new Set(vox_fg.keys());
    var clusters = [];
    while (remaining.size) {
        var seed_iter = remaining.values(); var seed = seed_iter.next().value;
        var queue = [seed]; remaining.delete(seed);
        var keys = [seed];
        var acc = null;
        while (queue.length) {
            var cur = queue.pop();
            var a = vox_fg.get(cur);
            if (!acc) { acc = { n: a.n, sx: a.sx, sy: a.sy, sz: a.sz,
                                sxx: a.sxx, syy: a.syy, szz: a.szz,
                                sxy: a.sxy, sxz: a.sxz, syz: a.syz,
                                zmin: a.zmin, zmax: a.zmax }; }
            else {
                acc.n += a.n; acc.sx += a.sx; acc.sy += a.sy; acc.sz += a.sz;
                acc.sxx += a.sxx; acc.syy += a.syy; acc.szz += a.szz;
                acc.sxy += a.sxy; acc.sxz += a.sxz; acc.syz += a.syz;
                if (a.zmin < acc.zmin) acc.zmin = a.zmin;
                if (a.zmax > acc.zmax) acc.zmax = a.zmax;
            }
            var ij = cur.split(","), ix = +ij[0], iy = +ij[1];
            var nb = [(ix - 1) + "," + iy, (ix + 1) + "," + iy,
                      ix + "," + (iy - 1), ix + "," + (iy + 1)];
            for (var t = 0; t < 4; t++) {
                if (remaining.has(nb[t])) { remaining.delete(nb[t]); queue.push(nb[t]); keys.push(nb[t]); }
            }
        }
        clusters.push({ keys: keys, acc: acc });
    }
    /* 只保尺寸足够的候选，其余视为散点 */
    return clusters.filter(function (c) { return c.keys.length >= PIPE.cluster_min_voxels; });
}

/* ---- 5b · 证据后处理：聚类 → 逐高度带矩（第二遍，点级） ----
 * 输入原帧点（已 denoise）+ clusters（key 集合 + acc）。
 * 返回 {clusters_extra: [ {anisotropy_xy, spread_cv, band_width_counts, band_spreads} ]} */
function evidence_postpass(xyzi, clusters) {
    /* key → cluster_idx 查表 */
    var key2cid = new Map();
    for (var c = 0; c < clusters.length; c++)
        for (var k = 0; k < clusters[c].keys.length; k++)
            key2cid.set(clusters[c].keys[k], c);
    var NB = PIPE.band_edges.length - 1;   /* 带数 */
    var accum = [];
    for (var c2 = 0; c2 < clusters.length; c2++) {
        accum.push({ band_n: new Float32Array(NB),
                     band_sx: new Float64Array(NB), band_sy: new Float64Array(NB),
                     band_sxx: new Float64Array(NB), band_syy: new Float64Array(NB),
                     band_sxy: new Float64Array(NB) });
    }
    for (var k2 = 0; k2 < xyzi.length; k2 += 4) {
        var x = xyzi[k2], y = xyzi[k2 + 1], z = xyzi[k2 + 2];
        var cid = key2cid.get(key_vox(x, y));
        if (cid === undefined) continue;
        /* 二分带：z → band idx */
        var bi = 0;
        /* edges 短所以线性扫；9 级 */
        while (bi < NB - 1 && z >= PIPE.band_edges[bi + 1]) bi++;
        var A = accum[cid];
        A.band_n[bi]++; A.band_sx[bi] += x; A.band_sy[bi] += y;
        A.band_sxx[bi] += x * x; A.band_syy[bi] += y * y; A.band_sxy[bi] += x * y;
    }
    var extras = [];
    for (var c3 = 0; c3 < clusters.length; c3++) {
        var A2 = accum[c3];
        var bn = A2.band_n;
        var total = 0;
        for (var j = 0; j < NB; j++) total += bn[j];
        var min_per_band = Math.max(PIPE.ev_band_min_pts_abs,
                                    total * PIPE.ev_band_min_pts_frac);
        var spreads = [], covered = 0;
        for (var j2 = 0; j2 < NB; j2++) {
            if (bn[j2] < min_per_band) continue;
            covered++;
            var mx = A2.band_sx[j2] / bn[j2], my = A2.band_sy[j2] / bn[j2];
            var cxx = A2.band_sxx[j2] / bn[j2] - mx * mx;
            var cyy = A2.band_syy[j2] / bn[j2] - my * my;
            /* σ_xy 对体素量化有柱柱尺规限制 — 在极细肢节处可能近 0.15 (voxel)：clamp 到 1e-6 防除零 */
            var sig = Math.sqrt(Math.max(1e-6, cxx) + Math.max(1e-6, cyy));
            spreads.push(sig);
        }
        /* spread_cv = std(spread) / mean(spread) */
        var spread_cv = null;
        if (covered >= PIPE.ev_bands_min) {
            var m = 0; for (var j3 = 0; j3 < spreads.length; j3++) m += spreads[j3];
            m /= spreads.length;
            var sd = 0; for (var j4 = 0; j4 < spreads.length; j4++) sd += (spreads[j4] - m) * (spreads[j4] - m);
            sd = Math.sqrt(sd / spreads.length);
            spread_cv = m > 1e-9 ? sd / m : 0;
        }
        /* anisotropy (XY λmax/λmin)：簇 acc 的 xy 2x2 本征值 */
        var aniso = null;
        if (total > 0) {
            var A3 = clusters[c3].acc;
            var cxx2 = A3.sxx / A3.n - (A3.sx / A3.n) * (A3.sx / A3.n);
            var cyy2 = A3.syy / A3.n - (A3.sy / A3.n) * (A3.sy / A3.n);
            var cxy2 = A3.sxy / A3.n - (A3.sx / A3.n) * (A3.sy / A3.n);
            var tr = cxx2 + cyy2, det = cxx2 * cyy2 - cxy2 * cxy2;
            var disc = Math.sqrt(Math.max(0, tr * tr - 4 * det));
            var lam1 = (tr + disc) / 2, lam2 = (tr - disc) / 2;
            if (lam2 > 1e-12) aniso = lam1 / lam2;
        }
        extras.push({
            anisotropy_xy: aniso,

            spread_cv: spread_cv,
            band_width_counts: Array.prototype.slice.call(bn),
            band_spreads: spreads,
            total_pts: total,
            covered_bands: covered,
        });
    }
    return { clusters_extra: extras };
}

/* ---- 5c · 证据标签（几何只发证据，不做人/家具裁决） ----
 * 决策树以 spread_cv 为主（均匀体恒 ~0，人体腿细躯宽 → 高），aniso 为辅证。
 * 标签语言仍严厉：「均匀/人形结构」不是「衣柜/人」。 */
function evidence_label(extra) {
    if (!extra) return { label: "EVIDENCE_NONE", evidence: [] };
    var ev = [];
    if (extra.anisotropy_xy !== null) ev.push("aniso=" + extra.anisotropy_xy.toFixed(2));
    if (extra.spread_cv !== null) ev.push("spread_cv=" + extra.spread_cv.toFixed(2));

    /* 主判：spread_cv ≥ person 门 → HUMAN_SHAPE；≤ box 门或 aniso 强盒 → SOLID_UNIFORM */
    if (extra.spread_cv !== null && extra.spread_cv >= PIPE.ev_spread_cv_person) {
        ev.push("spread_cv ≥ " + PIPE.ev_spread_cv_person + " → 体幅随高度变化（人形结构）");
        return { label: "HUMAN_SHAPE", evidence: ev };
    }
    if (extra.spread_cv !== null && extra.spread_cv <= PIPE.ev_spread_cv_box) {
        /* 低 cv 是均匀体强证 — aniso 只用来化 AMBIGUOUS，不能反低 cv */
        ev.push("spread_cv " + extra.spread_cv.toFixed(2) + " ≤ " + PIPE.ev_spread_cv_box + " → 体幅均匀（盒/柱特征）");
        return { label: "SOLID_UNIFORM", evidence: ev };
    }
    /* spread_cv 无法判定 (带数不足 / 中区间) → 看 aniso */
    if (extra.anisotropy_xy !== null && extra.anisotropy_xy >= PIPE.ev_aniso_box) {
        ev.push("aniso ≥ " + PIPE.ev_aniso_box + " → XY 强各向异性（平面/盒特征）");
        return { label: "SOLID_UNIFORM", evidence: ev };
    }
    return { label: "AMBIGUOUS", evidence: ev };
}

/* ---- 5d · 联合判定：硬门 × 证据 → UI 三态 ----
 * CONFIRMED_HUMAN = 硬门过 且 证据 HUMAN_SHAPE；
 * NON_HUMAN       = 硬门不过 或 证据 SOLID_UNIFORM；
 * 其余（含证据缺失） = HUMAN_CANDIDATE。 */
function joint_status(f) {
    var gates = f.label === "HUMAN_CANDIDATE";
    var ev = (f.evidence_tag && f.evidence_tag.label) || "EVIDENCE_NONE";
    if (gates && ev === "HUMAN_SHAPE") return "CONFIRMED_HUMAN";
    if (!gates || ev === "SOLID_UNIFORM") return "NON_HUMAN";
    return "HUMAN_CANDIDATE";
}

/* ---- 6· 簇 → 特征 + 人/非人裁决票 ---- */
function cluster_features(cl) {
    var a = cl.acc, n = a.n;
    if (n < PIPE.human_n_min) return { ok: false, reason: "points<" + PIPE.human_n_min, n: n };
    var mx = a.sx / n, my = a.sy / n, mz = a.sz / n;
    var cxx = a.sxx / n - mx * mx, cyy = a.syy / n - my * my, czz = a.szz / n - mz * mz;
    var cxy = a.sxy / n - mx * my, cxz = a.sxz / n - mx * mz, cyz = a.syz / n - my * mz;
    var eig = _eig3([[cxx, cxy, cxz], [cxy, cyy, cyz], [cxz, cyz, czz]]);
    var upcos = Math.abs(eig.vectors[0][2]);
    /* 体素边长0.15 → zmax 已含体素天花板；width/depth 以各 95% 分位代替全扩展使离群不抖 */
    var height = a.zmax - a.zmin;
    return {
        ok: true, n: n,
        cx: mx, cy: my, cz: mz,
        zmin: a.zmin, zmax: a.zmax, height_m: height,
        upcos: upcos,
        cov: { xx: cxx, yy: cyy, zz: czz, xy: cxy, xz: cxz, yz: cyz },
        eig: eig,
        /* 簇 XY 全扩展 (用 PCA 平面主轴的平方根反推，防离群体素撑大) */
        width_m: 2 * Math.sqrt(Math.max(0, cxx)),
        depth_m: 2 * Math.sqrt(Math.max(0, cyy)),
        spread_m: Math.sqrt(eig.values[0]),
        /* 躯干半径：2σ 倒影到 xy — 衣柜 ≈0.75±0.2 超门；人 ≈0.3 */
        radius_m: Math.sqrt(2 * (Math.max(0, cxx) + Math.max(0, cyy))),
    };
}

/* 簇 → {label, confidence, reasons[]}。硬门逐条出票。
 *
 * HR-07 limb 硬核教训：纯几何分不出衣柜 vs 直立人 —— 除非有跨帧/外部标签，
 * 这里一律不误信 HUMAN：只发 **HUMAN_CANDIDATE**（像人），并记录证据；
 * 真正的 HUMAN 承认由上层（跟踪 + 用户/OOB 标说）定。 */
function classify_human(f) {
    if (!f.ok) return { label: "NON_HUMAN", confidence: 0, reasons: [f.reason] };
    var reasons = [];
    if (f.height_m < PIPE.human_height_min || f.height_m > PIPE.human_height_max)
        reasons.push("身高 " + f.height_m.toFixed(2) + "m 不在 [" + PIPE.human_height_min + "," + PIPE.human_height_max + "]");
    if (f.width_m > PIPE.human_width_max || f.depth_m > PIPE.human_width_max)
        reasons.push("宽/深(" + PIPE.human_width_max + "m 2σ): " + f.width_m.toFixed(2) + "/" + f.depth_m.toFixed(2) + "m");
    if (f.radius_m > PIPE.human_radius_max)
        reasons.push("躯干半径(" + PIPE.human_radius_max + "m 2σ): " + f.radius_m.toFixed(2) + "m");
    if (f.upcos < PIPE.human_upcos_min)
        reasons.push("主直立度 " + f.upcos.toFixed(2) + " < " + PIPE.human_upcos_min);
    var gates_passed = 4 - reasons.length;
    var label = reasons.length === 0 ? "HUMAN_CANDIDATE" : "NON_HUMAN";
    return { label: label, confidence: gates_passed / 4, reasons: reasons };
}

/* ---- 7 · 跟踪：贪心最近邻 + EMA + lost。一人一条 Track ----
 * 每条 Track：{id, x,y,z,height,upcos,label, n, lost, born_idx, pose_history[]}
 * pose_history 给 fall 判。*/
function Tracker() { this.next_id = 1; this.tracks = []; }
Tracker.prototype.tick = function (frame_idx, clusters) {
    var gate2 = PIPE.track_gate_xy_m * PIPE.track_gate_xy_m;
    for (var ci = 0; ci < clusters.length; ci++) {
        var f = clusters[ci];
        if (!f.ok) continue;
        var best = null, best_d2 = gate2;
        for (var ti = 0; ti < this.tracks.length; ti++) {
            var t = this.tracks[ti];
            if (!t.active) continue;
            var dx = t.x - f.cx, dy = t.y - f.cy, d2 = dx * dx + dy * dy;
            if (d2 < best_d2) { best_d2 = d2; best = t; }
        }
        var smp = { x: f.cx, y: f.cy, z: f.cz, height: f.height_m, upcos: f.upcos,
                    label: f.label, n: f.n };
        if (best) {
            var al = PIPE.ema_alpha;
            best.x += al * (smp.x - best.x); best.y += al * (smp.y - best.y);
            best.z += al * (smp.z - best.z);
            best.height += al * (smp.height - best.height);
            best.upcos += al * (smp.upcos - best.upcos);
            best.label = smp.label; best.n = smp.n;
            best.lost = 0;
        } else {
            best = { id: this.next_id++, active: true, born_idx: frame_idx,
                     x: smp.x, y: smp.y, z: smp.z, height: smp.height, upcos: smp.upcos,
                     label: smp.label, n: smp.n, lost: 0 };
            this.tracks.push(best);
        }
        best.last_seen = frame_idx;
        /* 5d 时间确认：最近 human_confirm_window 帧内 ≥ human_confirm_votes 帧
         * CONFIRMED_HUMAN，且 track 年龄 ≥ min_age 才确认（防瞬时闪绿）。 */
        var vote = (f.joint === "CONFIRMED_HUMAN") ? 1 : 0;
        var votes = best.votes || (best.votes = []);
        votes.push(vote);
        if (votes.length > PIPE.human_confirm_window) votes.shift();
        var vs = 0;
        for (var vi = 0; vi < votes.length; vi++) vs += votes[vi];
        best.human_confirmed = vs >= PIPE.human_confirm_votes
            && (frame_idx - best.born_idx + 1) >= PIPE.human_confirm_min_age;
        f.track_id = best.id;
        f.track_confirmed = best.human_confirmed;
        /* pose history 采样上证凑出 Fall 判断的时态 */
        var hx = best.pose_history || (best.pose_history = []);
        hx.push({ f: frame_idx, upcos: best.upcos, height: best.height });
        if (hx.length > 120) hx.shift();
    }
    /* lost 计数 */
    for (var ti2 = 0; ti2 < this.tracks.length; ti2++) {
        var t2 = this.tracks[ti2];
        if (!t2.active) continue;
        if (t2.last_seen !== frame_idx) {
            t2.lost++;
            if (t2.lost > PIPE.track_lost_max) t2.active = false;
        }
    }
};

/* ---- 8 · Fall 判别（对一条 track 迄今的 pose_history） ----
 * 返回 null 或 {type:"fall", from_idx, to_idx, reason}。弯腰不触发（upcos≥门/不持续/回站）。 */
function fall_assess(track) {
    var hx = track.pose_history;
    if (!hx || hx.length < 10) return null;
    /* 找最近一段连续「躺」窗：upcos < 门 且 height < 门 */
    var i = hx.length - 1;
    while (i >= 0 && hx[i].upcos < PIPE.fall_upcos_max && hx[i].height < PIPE.fall_height_max) i--;
    var sustain = hx.length - 1 - i;   /* 尾部连续躺的帧数 */
    if (i < 0 && sustain >= PIPE.fall_sustain_frames) {
        /* 从头躺起——无 Before 对照，无法判断是否 Fall；不触发。 */
        return null;
    }
    if (sustain < PIPE.fall_sustain_frames) return null;
    /* 此前必须有「站立期」：从窗向前找 upcos ≥ 门 + height ≥ 身高下限 */
    for (var j = i; j >= 0; j--) {
        if (hx[j].upcos >= PIPE.human_upcos_min && hx[j].height >= PIPE.human_height_min) {
            return { type: "fall", from_idx: hx[j].f, to_idx: hx[hx.length - 1].f,
                     reason: "站立→躺平 (upcos " + hx[j].upcos.toFixed(2) + "→" + hx[hx.length - 1].upcos.toFixed(2)
                           + ", 身高 " + hx[j].height.toFixed(2) + "→" + hx[hx.length - 1].height.toFixed(2) + "m)" };
        }
    }
    return null;
}

/* ---- 工具：复用 human_detect_lib 的 Jacobi 3x3 eig（同源） ---- */
function _eig3(m) {
    var a = [[m[0][0], m[0][1], m[0][2]], [m[1][0], m[1][1], m[1][2]], [m[2][0], m[2][1], m[2][2]]];
    var v = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    for (var it = 0; it < 25; it++) {
        var p = 0, q = 1, mx = Math.abs(a[0][1]);
        if (Math.abs(a[0][2]) > mx) { mx = Math.abs(a[0][2]); p = 0; q = 2; }
        if (Math.abs(a[1][2]) > mx) { mx = Math.abs(a[1][2]); p = 1; q = 2; }
        if (mx < 1e-12) break;
        var app = a[p][p], aqq = a[q][q], apq = a[p][q];
        var theta = 0.5 * Math.atan2(2 * apq, aqq - app);
        var c = Math.cos(theta), s = Math.sin(theta);
        for (var k = 0; k < 3; k++) {
            var akp = a[k][p], akq = a[k][q];
            a[k][p] = c * akp - s * akq; a[k][q] = s * akp + c * akq;
        }
        for (var k2 = 0; k2 < 3; k2++) {
            var apk = a[p][k2], aqk = a[q][k2];
            a[p][k2] = c * apk - s * aqk; a[q][k2] = s * apk + c * aqk;
        }
        for (var k3 = 0; k3 < 3; k3++) {
            var vkp = v[k3][p], vkq = v[k3][q];
            v[k3][p] = c * vkp - s * vkq; v[k3][q] = s * vkp + c * vkq;
        }
    }
    var vals = [a[0][0], a[1][1], a[2][2]];
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

/* ---- 一帧全链（供节点测试 + 浏览器层调用） ----
 * ctx = {static_keys: Map, tracker: Tracker} ；frame_idx 用于 Tracking/Fall。 */
function pipeline_frame(xyzi, frame_idx, ctx) {
    var clean = denoise(xyzi);
    var fg = extract_foreground(clean, ctx.static_keys);
    /* R2.6：前景 → 聚类之间，保守孤立前景清理（单遍快照语义） */
    var iso = cleanup_isolated_fg(fg.fg_xyzi);
    var fg_pts = iso.xyzi;
    var clusters_raw = (iso.removed_points > 0)
        ? cluster_voxels(voxelize(iso.xyzi))
        : cluster_voxels(fg.vox_fg);
    /* 5b 证据后处理：第二遍点级扫描 — 喂清理后的真簇点,
     * 否则地板/背景点又被计数进簇,污染逐带 spread_cv/aniso */
    var ev_pack = evidence_postpass(fg_pts, clusters_raw);
    var clusters = [];
    for (var i = 0; i < clusters_raw.length; i++) {
        var f = cluster_features(clusters_raw[i]);
        if (!f.ok) continue;
        var c = classify_human(f);
        f.label = c.label; f.confidence = c.confidence; f.reasons = c.reasons;
        /* 证据挂断面：spread_cv / aniso / 证据标签 */
        var extra = ev_pack.clusters_extra[i];
        f.evidence = extra;
        f.evidence_tag = evidence_label(extra);
        f.joint = joint_status(f);
        clusters.push(f);
    }
    ctx.tracker.tick(frame_idx, clusters);
    var events = [];
    for (var ti = 0; ti < ctx.tracker.tracks.length; ti++) {
        var tr = ctx.tracker.tracks[ti];
        if (!tr.active) continue;
        var ev = fall_assess(tr);
        if (ev) events.push(Object.assign({ track_id: tr.id }, ev));
    }
    return { n_in: xyzi.length / 4, n_denoise: clean.length / 4,
             n_foreground: fg.n_fg, n_dropped: fg.n_dropped,
             /* R2.6 诊断：孤立清理前/后与删除量 */
             fg_after_cleanup: iso.after,
             iso_removed_points: iso.removed_points,
             iso_removed_ratio: iso.before ? iso.removed_points / iso.before : 0,
             fg_voxels: iso.fg_voxels,
             iso_removed_voxels: iso.removed_voxels,
             clusters: clusters,
             tracks: ctx.tracker.tracks.filter(function (t) { return t.active; }),
             events: events };
}

var _api = {
    PIPE: PIPE,
    denoise: denoise,
    voxelize: voxelize,
    key_vox: key_vox,
    key_bg: key_bg,
    build_static_map: build_static_map,
    extract_foreground: extract_foreground,
    cleanup_isolated_fg: cleanup_isolated_fg,
    cluster_voxels: cluster_voxels,
    cluster_features: cluster_features,
    classify_human: classify_human,
    evidence_postpass: evidence_postpass,
    evidence_label: evidence_label,
    joint_status: joint_status,
    Tracker: Tracker,
    fall_assess: fall_assess,
    pipeline_frame: pipeline_frame,
    _eig3: _eig3,
};
if (typeof module !== "undefined" && module.exports) { module.exports = _api; }
if (typeof globalThis !== "undefined") { globalThis.human_pipe_lib = _api; }
