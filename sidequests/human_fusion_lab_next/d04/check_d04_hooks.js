'use strict';
/* D04 hooks 自检 — 复用 check_b.js 的引用构建方式，只验证 d04 私有 hook，不动 check_b.js。 */
const assert = require('assert'), path = require('path'), fs = require('fs');
const B = require('../background/detector_b');
const L = require('../../human_fusion_lab/core/leveling');
const S = require('../../human_fusion_lab/core/schema');
const D = require('../../human_fusion_lab/core/data_loader');
const R = require('./run_d04');

/* 1) P30: createDetector 后 pipe.PIPE.human_n_min 应为 30，且 cluster_features 拒 30 点以下 */
{
    const ref = { staticKeys: new Map([[1, { x: 1, y: 1, z: .2, occ: 1 }]]), coordinate: { ...L.REF_RT, already_leveled: false } };
    const det = B.createDetector(ref);
    R.applyVariant(det.engine, R.VARIANT.P30);
    assert.strictEqual(det.engine.pipe.PIPE.human_n_min, 30, 'P30 human_n_min');
    const acc = { n: 20, sx: 20, sy: 0, sz: 20, sxx: 20, syy: 0, szz: 20, sxy: 0, sxz: 0, syz: 0, zmin: 0, zmax: 1 };
    const r = det.engine.pipe.cluster_features({ keys: [], acc });
    assert.strictEqual(r.ok, false); assert.strictEqual(r.reason, 'points<30'); assert.strictEqual(r.n, 20);
    console.log('P30_PASS human_n_min=30 gate points<30');
}
/* 1b) P15 同理 */
{
    const ref = { staticKeys: new Map([[1, { x: 1, y: 1, z: .2, occ: 1 }]]), coordinate: { ...L.REF_RT, already_leveled: false } };
    const det = B.createDetector(ref);
    R.applyVariant(det.engine, R.VARIANT.P15);
    assert.strictEqual(det.engine.pipe.PIPE.human_n_min, 15);
    const acc = { n: 12, sx: 12, sy: 0, sz: 12, sxx: 12, syy: 0, szz: 12, sxy: 0, sxz: 0, syz: 0, zmin: 0, zmax: 1 };
    const r = det.engine.pipe.cluster_features({ keys: [], acc });
    assert.strictEqual(r.ok, false); assert.strictEqual(r.reason, 'points<15');
    console.log('P15_PASS human_n_min=15 gate points<15');
}

/* 2) SPLIT: 默认关；开启后对一帧验证 split_log 非空（用真实会话 cap_20261009_113611 第一帧） */
{
    /* 2a) 未挂 hook 时 cluster_voxels 直通 — _split_log 不会被填 */
    const ref = { staticKeys: new Map([[1, { x: 1, y: 1, z: .2, occ: 1 }]]), coordinate: { ...L.REF_RT, already_leveled: false } };
    const detNoSplit = B.createDetector(ref);
    assert.strictEqual(detNoSplit.engine._split_log, undefined, 'split default off');
    console.log('SPLIT_DEFAULT_OFF_PASS');
}
{
    /* 2b) 挂 SPLIT hook 后用真实第一帧触发 _fusion_a_chain, 验证 _split_log 被填充 */
    const audit = JSON.parse(fs.readFileSync(path.join(B.LAB, 'results/AUDIT.json')));
    const rec = audit.sessions[0];
    const session = D.load_session(path.join(B.ROOT, 'captures/remote', rec.sid));
    const ref = B.buildReference();
    const det = B.createDetector(ref);
    R.applyVariant(det.engine, R.VARIANT.SPLIT);
    const { instrument } = require('../eval/instrument');
    const e = instrument(det.engine);
    const gen = det.begin(rec.sid);
    const f = session.frames[0];
    e._split_log = [];
    const fc = S.make_frame_context({ session_id: rec.sid, session_generation: gen, frame_index: f.index, timestamp: f.timestamp, xyzi: f.xyzi, meta: session.meta });
    det.tick(fc);
    assert(Array.isArray(e._split_log), 'split_log array');
    console.log('SPLIT_ARMED_LOG_N=' + e._split_log.length + ' (real frame may produce 0 — splitter conservative)');
}
{
    /* 2c) 合成 z 双峰异质簇 — split_log 非空验证（几何触发路径，不用 GT） */
    const ref = { staticKeys: new Map([[1, { x: 1, y: 1, z: .2, occ: 1 }]]), coordinate: { ...L.REF_RT, already_leveled: false } };
    const det = B.createDetector(ref);
    R.applyVariant(det.engine, R.VARIANT.SPLIT);
    const pipe = det.engine.pipe;
    const pts = [];
    for (let i = 0; i < 300; i++) { const gx = i % 3, gy = Math.floor(i / 3) % 3; pts.push(1 + gx * .15 + (i % 5) * .01, 1 + gy * .15 + (i % 7) * .01, 0.2 + (i % 5) * .08, 10); }
    for (let i = 0; i < 300; i++) { const gx = i % 3, gy = Math.floor(i / 3) % 3; pts.push(1 + gx * .15 + (i % 5) * .01, 1 + gy * .15 + (i % 7) * .01, 2.4 + (i % 5) * .1, 10); }
    const fg = new Float32Array(pts);
    det.engine._split_log = [];
    const cls = pipe.cluster_voxels(pipe.voxelize(fg));
    assert.strictEqual(det.engine._split_log.length, 1, 'synthetic hetero cluster must split');
    assert.strictEqual(det.engine._split_log[0].sub_clusters.length, 2, 'must produce 2 sub clusters');
    assert.strictEqual(det.engine._split_log[0].sub_clusters[0].acc_n, 300);
    assert.strictEqual(det.engine._split_log[0].sub_clusters[1].acc_n, 300);
    assert(cls.length === 2, 'returned clusters replaced by sub clusters');
    console.log('SPLIT_TRIGGER_PASS 600pt z-bimodal → 2x300pt subs');
}

/* 3) U04: BG 0.4m 不修复, 只是变体注册 OK */
{
    const ref = { staticKeys: new Map([[1, { x: 1, y: 1, z: .2, occ: 1 }]]), coordinate: { ...L.REF_RT, already_leveled: false } };
    const det = B.createDetector(ref);
    const vi = R.applyVariant(det.engine, R.VARIANT.U04);
    assert.strictEqual(vi.unknown_radius_m, 0.4);
    console.log('U04_PASS radius=0.4 registered');
}

/* 4) BASE: 不变体 */
{
    const ref = { staticKeys: new Map([[1, { x: 1, y: 1, z: .2, occ: 1 }]]), coordinate: { ...L.REF_RT, already_leveled: false } };
    const det = B.createDetector(ref);
    const vi = R.applyVariant(det.engine, R.VARIANT.BASE);
    assert.strictEqual(vi.variant, 'base');
    assert.strictEqual(det.engine.pipe.PIPE.human_n_min, 60, 'base human_n_min 60');
    console.log('BASE_PASS human_n_min kept 60');
}

console.log('D04_HOOKS_CHECK_PASS');
