'use strict';
/* HFUS-D05 UNKNOWN 自适应邻域重判 hook — 只 monkey-patch 当次 engine 实例, 不改任何文件。
 * 用更粗半径 cfg.r (0.3/0.6) 对被 0.4m 刚性门所杀的 UNKNOWN 点重判:
 * 同时满足 (a) cfg.r 内参考列质心数 >= min_ref_support 且 (b) 该点在 extract-foreground 邻域
 * 内要么单帧孤立 (无 link_xy_m 邻居), 要么局部密度 >= min_local_pts -> 再收纳; 否则保留拒绝。 */
function applyUnknown(engine, cfg) {
    const r = cfg.r === 0.3 || cfg.r === 0.6 ? cfg.r : 0.3;
    const link = cfg.link_xy_m == null ? 0.3 : cfg.link_xy_m;
    const minRef = cfg.min_ref_support == null ? 1 : cfg.min_ref_support;
    const minLocal = cfg.min_local_pts == null ? 1 : cfg.min_local_pts;
    const r2 = r * r, link2 = link * link, linkCellPad = Math.ceil(link / 0.15);
    engine._unknown_hook_stats = { re_admitted: 0, still_rejected: 0 };
    const stats = engine._unknown_hook_stats;
    const origSelect = engine._bgB.select;
    const bgB = engine._bgB;
    const rejectReason = 'no_reference_XY_support_UNKNOWN_r' + r;

    /* 单点 (a): cfg.r 内参考列质心数 (按 0.15m 列格方形邻域扫)。 */
    function refSupport(lv, idx, columns) {
        const x = lv[idx * 4], y = lv[idx * 4 + 1];
        const ix = Math.floor(x / 0.15), iy = Math.floor(y / 0.15);
        const pad = Math.ceil(r / 0.15);
        let hit = 0;
        for (let a = -pad; a <= pad; a++) for (let b = -pad; b <= pad; b++) {
            const list = columns.get((ix + a) + ',' + (iy + b));
            if (list) for (const c of list) {
                const dx = c.x - x, dy = c.y - y;
                if (dx * dx + dy * dy <= r2) hit++;
            }
        }
        return hit;
    }

    bgB.select = function (lv, pipe, keys) {
        const out = origSelect(lv, pipe, keys);
        const columns = bgB.columns;
        const n = lv.length / 4;
        /* extract-foreground 候选集 = bare_keep (groupB 后, 刚性 0.4m 门前) — 邻域判断的密度空间。 */
        const candIdx = [], candXY = [];
        for (let k = 0; k < n; k++) if (out.bare_keep[k]) { candIdx.push(k); candXY.push(lv[k * 4], lv[k * 4 + 1]); }
        /* 候选集网格桶 (0.3m cell) — 代替「每被拒点 × 全候选」O(N²)。 */
        const cell = 0.3, pad = Math.ceil(link / cell), grid = new Map();
        for (let i = 0; i < candIdx.length; i++) {
            const gk = Math.floor(candXY[i * 2] / cell) + ',' + Math.floor(candXY[i * 2 + 1] / cell);
            if (!grid.has(gk)) grid.set(gk, []);
            grid.get(gk).push(i);
        }
        function neighborCountFast(x, y, selfXYy, selfIdx) {
            const gx = Math.floor(x / cell), gy = Math.floor(selfXYy / cell);
            let cnt = 0;
            for (let a = -pad; a <= pad; a++) for (let b = -pad; b <= pad; b++) {
                const arr = grid.get((gx + a) + ',' + (gy + b));
                if (!arr) continue;
                for (const i of arr) {
                    if (candIdx[i] === selfIdx) continue;
                    const dx = candXY[i * 2] - x, dy = candXY[i * 2 + 1] - selfXYy;
                    if (dx * dx + dy * dy <= link2) cnt++;
                }
            }
            return cnt;
        }
        for (let k = 0; k < n; k++) {
            if (out.keep[k] || out.reasons[k] !== 'no_reference_XY_support_UNKNOWN') continue;
            const z = lv[k * 4 + 2];
            /* z<=0.1 低点不重收 (按非人/地面级保留拒绝), 只换账标签。 */
            if (z <= 0.1) { out.reasons[k] = rejectReason + '_zlow'; stats.still_rejected++; continue; }
            if (refSupport(lv, k, columns) < minRef) { out.reasons[k] = rejectReason; stats.still_rejected++; continue; }
            const nb = neighborCountFast(lv[k * 4], lv[k * 4 + 1], lv[k * 4 + 1], k);
            if (nb === 0 || nb >= minLocal) { out.keep[k] = 1; out.reasons[k] = 'adaptive_r' + r + '_readmit'; stats.re_admitted++; }
            else { out.reasons[k] = rejectReason; stats.still_rejected++; }
        }
        /* states 从 reasons 重算 (readmit 的点理由变了, 仍是 UNKNOWN 层语义)。 */
        out.states = out.reasons.map(rr => rr === 'bg_voxel_match' ? 'OCCUPIED' : 'UNKNOWN');
        return out;
    };
    return { kind: 'adaptive_unknown', r: r, link_xy_m: link, min_ref_support: minRef, min_local_pts: minLocal };
}

module.exports = { applyUnknown };

if (require.main === module) {
    /* __main__ 自测: 最小假 engine._bgB — 刚性 0.4m 门杀点, hook 在 r=0.6 下重收孤立点。 */
    const assert = require('assert');
    // 参考列质心: (1.0, 1.0) 处 1 个。待判点: (1.5, 1.0) 距质心 0.5m -> 0.4 门杀, r=0.6 应重收 (孤立);
    // 另一点 (2.0, 1.0) 距 1.0m 无支撑 -> 仍拒; 一点 z=0.05 低点不管支持也拒。
    const columns = new Map();
    columns.set(Math.floor(1.0 / 0.15) + ',' + Math.floor(1.0 / 0.15), [{ x: 1.0, y: 1.0 }]);
    const lv = new Float32Array([1.5, 1.0, 1.0, 0, 2.0, 1.0, 1.0, 0, 1.5, 1.0, 0.05, 0]);
    const reasons = ['no_reference_XY_support_UNKNOWN', 'no_reference_XY_support_UNKNOWN', 'no_reference_XY_support_UNKNOWN'];
    const engine = {
        _bgB: {
            columns,
            select(lvv) {
                return { keep: new Uint8Array(lvv.length / 4), bare_keep: new Uint8Array(lvv.length / 4).fill(1), reasons: reasons.slice(), states: [] };
            },
        },
    };
    const vi = applyUnknown(engine, { r: 0.6 });
    assert.equal(vi.kind, 'adaptive_unknown');
    assert.equal(vi.r, 0.6);
    const out = engine._bgB.select(lv, null, null);
    assert.equal(out.keep[0], 1);                 // 0.5m 内 1 质心 + 无 link 邻居 (孤立) -> 重收
    assert.equal(out.reasons[0], 'adaptive_r0.6_readmit');
    assert.equal(out.keep[1], 0);                 // 无参考支撑 -> 仍拒
    assert.equal(out.keep[2], 0);                 // z<=0.1 -> 仍拒
    assert.equal(engine._unknown_hook_stats.re_admitted, 1);
    assert.equal(engine._unknown_hook_stats.still_rejected, 2);
    assert.equal(out.states.length, 3);
    console.log('HOOK_UNKNOWN_SELFTEST_PASS');
}
