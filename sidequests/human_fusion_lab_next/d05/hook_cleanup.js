'use strict';
/* HFUS-D05 human-candidate-aware CLEANUP hook — 只 new 文件, 不改 human_pipe_lib/background。
 * 包装 engine.pipe.cleanup_isolated_fg：原版先算删除集合, 本 hook 对每个 would-be-removed 点
 * 在「原版保留集合」的语境下重判:
 *   R_connect  : 该点 link_xy_m(XY) 邻域内有 ≥min_anchor_pts 个保留 fg → 保留 (连体, 可能肢体/边缘)
 *   R_vertical : 该点 link_xy_m(XY) 邻域内保留 fg 的 z-span ≥min_vertical_span_m → 保留 (人体立柱)
 *                但若该点 z < furniture_z_max_m 且该局部 z-span < furniture_min_span_m → 不触发 (家具保护)
 * 判定顺序: 先 R_connect, 命中记 veto_by_connect; 否则 R_vertical, 命中记 veto_by_vertical;
 * 否则 removed。两规则不叠加, stats 记录首个命中动机。所有常量经 cfg 传入 (DEFAULTS 冻结)。
 * engine._cleanup_stats 由 run 循环按帧取走/复位（同 _split_log 惯例）, hook 自身只累加。
 * ponytail: O(N_removed × N_kept) 直扫, 典型 removed≪kept 可接受; 升级路径 XY grid 分桶。 */

const DEFAULTS = Object.freeze({
    link_xy_m: 0.45,
    min_anchor_pts: 10,
    min_vertical_span_m: 0.5,
    furniture_z_max_m: 0.35,
    furniture_min_span_m: 0.3,
});

function applyCleanupAware(engine, cfg) {
    cfg = Object.assign({}, DEFAULTS, cfg || {});
    const pipe = engine.pipe;
    const orig = pipe.cleanup_isolated_fg;
    const key_bg = pipe.key_bg;

    pipe.cleanup_isolated_fg = function (xyzi) {
        const r = orig.call(pipe, xyzi);
        if (!engine._cleanup_stats) engine._cleanup_stats = { veto_by_connect: 0, veto_by_vertical: 0, removed: 0 };
        const st = engine._cleanup_stats;
        const kept = r.xyzi;
        /* 1) kept 体素 key 集 + 列出 would-be-removed 点 */
        const keptSet = new Set();
        for (let j = 0; j < kept.length; j += 4) keptSet.add(key_bg(kept[j], kept[j + 1], kept[j + 2]));
        const removedPts = [];
        for (let i = 0; i < xyzi.length; i += 4) {
            if (!keptSet.has(key_bg(xyzi[i], xyzi[i + 1], xyzi[i + 2]))) {
                removedPts.push({ x: xyzi[i], y: xyzi[i + 1], z: xyzi[i + 2], v: xyzi[i + 3] });
            }
        }
        if (!removedPts.length) return r;
        /* 2) 逐点相对 kept 做一次 XY 邻域扫描, 收集 anchor 数与 z-span, 判定 rescue 动机 */
        const link2 = cfg.link_xy_m * cfg.link_xy_m;
        const rescued = [];
        let vConnect = 0, vVert = 0, nDrop = 0;
        for (let ri = 0; ri < removedPts.length; ri++) {
            const c = removedPts[ri];
            let n_anchor = 0, zmin = Infinity, zmax = -Infinity;
            for (let j = 0; j < kept.length; j += 4) {
                const dx = kept[j] - c.x, dy = kept[j + 1] - c.y;
                if (dx * dx + dy * dy > link2) continue;
                n_anchor++;
                const z = kept[j + 2]; if (z < zmin) zmin = z; if (z > zmax) zmax = z;
            }
            const span = n_anchor ? zmax - zmin : 0;
            if (n_anchor >= cfg.min_anchor_pts) { vConnect++; rescued.push(c); continue; }
            const furniture_like = (c.z < cfg.furniture_z_max_m) && (span < cfg.furniture_min_span_m);
            if (!furniture_like && span >= cfg.min_vertical_span_m) { vVert++; rescued.push(c); continue; }
            nDrop++;
        }
        st.veto_by_connect += vConnect; st.veto_by_vertical += vVert; st.removed += nDrop;
        if (!rescued.length) return r;
        /* 3) 按原始 xyzi 顺序重组 merged（放进去救援点原位）——下游 _fusion_a_chain 用 subset_indices
         *    要求 cleanup 输出保持「输入点级子序列」契约, 追加到尾部会破坏该契约。 */
        const rescuedKeys = new Set(rescued.map(p => key_bg(p.x, p.y, p.z)));
        const mergedArr = [];
        for (let i = 0; i < xyzi.length; i += 4) {
            const kk = key_bg(xyzi[i], xyzi[i + 1], xyzi[i + 2]);
            if (keptSet.has(kk) || rescuedKeys.has(kk)) mergedArr.push(xyzi[i], xyzi[i + 1], xyzi[i + 2], xyzi[i + 3]);
        }
        const merged = new Float32Array(mergedArr);
        const nAfter = merged.length / 4;
        return Object.assign({}, r, {
            xyzi: merged,
            fg_after_cleanup: nAfter,
            after: nAfter,
            actually_removed_points: r.fg_before_cleanup - nAfter,
            removed_points: r.fg_before_cleanup - nAfter,
            candidate_aware_rescue: { veto_by_connect: vConnect, veto_by_vertical: vVert, final_removed: nDrop },
        });
    };
    return Object.assign({ kind: 'candidate_aware_cleanup' }, cfg);
}

module.exports = { applyCleanupAware, DEFAULTS };

/* ----------------- self-test ----------------- */
if (require.main === module) {
    const assert = require('assert');
    /* mock pipe：极简 cleanup — "3D 半径 r3 内无邻居 → 删", 足够造出 would-be-removed 点 */
    function makeMock(r3) {
        const rr = (r3 == null ? 1.0 : r3) ** 2;
        return {
            key_bg: (x, y, z) => Math.round(x * 100) + ',' + Math.round(y * 100) + ',' + Math.round(z * 100),
            cleanup_isolated_fg: function (xyzi) {
                const n = xyzi.length / 4, out = [];
                for (let i = 0; i < n; i++) {
                    let ok = false;
                    for (let j = 0; j < n; j++) {
                        if (i === j) continue;
                        const dx = xyzi[i * 4] - xyzi[j * 4], dy = xyzi[i * 4 + 1] - xyzi[j * 4 + 1], dz = xyzi[i * 4 + 2] - xyzi[j * 4 + 2];
                        if (dx * dx + dy * dy + dz * dz < rr) { ok = true; break; }
                    }
                    if (ok) out.push(xyzi[i * 4], xyzi[i * 4 + 1], xyzi[i * 4 + 2], xyzi[i * 4 + 3]);
                }
                return { xyzi: new Float32Array(out), fg_before_cleanup: n, fg_after_cleanup: out.length / 4,
                         after: out.length / 4, actually_removed_points: n - out.length / 4, removed_points: n - out.length / 4 };
            },
        };
    }

    /* 场景 1 (connect): 87 点人体立柱 (29 z-slices × 3 pts) + 体顶上方 1.2m 的边缘点 (XY 0.40m 内, 3D>1m 被 mock 删)
     *   → 87 个 anchor ≥ min_anchor_pts(10) → R_connect 救回; 另加远处真孤立噪点 (10,10) → 必删 */
    {
        const engine = { pipe: makeMock() };
        applyCleanupAware(engine, {});
        const pts = [];
        for (let zi = 0; zi < 29; zi++) for (let k = 0; k < 3; k++) pts.push(0.05 * k, 0.05 * (k % 2), 0.1 * zi, 10);
        pts.push(0.40, 0, 4.0, 10);      /* 边缘: XY 距体列 ≤0.40, dz 1.2 → 3D>1 → mock 删, hook 救 */
        pts.push(10, 10, 1.7, 10);       /* 真孤立: 无邻居 → 删 */
        const r = engine.pipe.cleanup_isolated_fg(new Float32Array(pts));
        assert.strictEqual(r.xyzi.length / 4, 88, 'S1 kept 87 body + 1 rescued edge');
        assert.strictEqual(engine._cleanup_stats.veto_by_connect, 1);
        assert.strictEqual(engine._cleanup_stats.veto_by_vertical, 0);
        assert.strictEqual(engine._cleanup_stats.removed, 1);
        console.log('S1_CONNECT_PASS', JSON.stringify(engine._cleanup_stats));
    }
    /* 场景 2 (vertical-only): 8 点细杆 z 0.1..1.5 (anchor 8 < 10 → connect 不救), 边缘点 z=2.6 被 mock 删
     *   → 杆 z-span 1.4 ≥ 0.5, c.z 2.6 ≥ 0.35 (非家具) → R_vertical 救回 */
    {
        const engine = { pipe: makeMock() };
        applyCleanupAware(engine, {});
        const pts = [];
        for (let k = 0; k < 8; k++) pts.push(0, 0, 0.1 + 0.2 * k, 10);
        pts.push(0.40, 0, 2.6, 10);      /* dz to top = 1.1 → 3D ≈1.17 > 1 → mock 删, vertical 救 */
        const r = engine.pipe.cleanup_isolated_fg(new Float32Array(pts));
        assert.strictEqual(r.xyzi.length / 4, 9, 'S2 kept 8 pole + 1 rescued');
        assert.strictEqual(engine._cleanup_stats.veto_by_connect, 0);
        assert.strictEqual(engine._cleanup_stats.veto_by_vertical, 1);
        assert.strictEqual(engine._cleanup_stats.removed, 0);
        console.log('S2_VERTICAL_PASS', JSON.stringify(engine._cleanup_stats));
    }
    /* 场景 3 (furniture guard): 覆盖 cfg 使 vertical 阈值 0.2 < furniture_min_span 0.3, 验证家具样例被 guard 拦下
     *   膝高平板 9 点 z 0.75..0.99 (span 0.24 ∈ [0.2, 0.3)); mock 半径 0.5 → 板内部自洽保留。
     *   低候选 (0.45, 0, 0.05): XY≤0.45 看到板 anchor, c.z<0.35 且 span<0.3 → guard 拦 vertical, n<10 拦 connect → 删
     *   高候选 (0, 0, 1.7): c.z≥furniture_z_max → guard 不管, span 0.24≥0.2 → vertical 救 */
    {
        const engine = { pipe: makeMock(0.5) };
        applyCleanupAware(engine, { min_vertical_span_m: 0.2 });
        const pts = [];
        for (let k = 0; k < 9; k++) pts.push(0.02 * (k % 3), 0.02 * (k % 2), 0.75 + 0.03 * k, 10);
        pts.push(0.45, 0, 0.05, 10);     /* 地板矮墩 (家具样): 3D≥0.81>0.5 被 mock 删, guard 拦救 → removed */
        pts.push(0, 0, 1.7, 10);         /* 板上方高位点: 3D≥0.71>0.5 被 mock 删, z≥0.35 绕过 guard → vertical 救 */
        const r = engine.pipe.cleanup_isolated_fg(new Float32Array(pts));
        assert.strictEqual(r.xyzi.length / 4, 10, 'S3 kept 9 plate + 1 high rescued, furniture edge dropped');
        assert.strictEqual(engine._cleanup_stats.veto_by_connect, 0);
        assert.strictEqual(engine._cleanup_stats.veto_by_vertical, 1);
        assert.strictEqual(engine._cleanup_stats.removed, 1);
        console.log('S3_FURNITURE_GUARD_PASS', JSON.stringify(engine._cleanup_stats));
    }
    console.log('HOOK_CLEANUP_SELFTEST_PASS');
}
