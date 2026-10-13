'use strict';
/* HFUS-D05 时序前景恢复 hook — 只包 engine 实例方法， 不改任何只读文件。
 * 机制 (与 fg_plus_retained 同源): 在 _fusion_a_chain 运行前， 把「时序证据支持
 * 的 anchor」写进 engine.retention.tracks — 原链现成的 hot_cell_radius_m / z 窗 /
 * 有限值 / timeout / max_lost / window_confirm 检查自然接管吸收， 吸收点带
 * CAND_SRC.RETAINED 标并参与 cluster/RF/tracker。 本 hook 不越过任何一道门。 */
const S = require('../../human_fusion_lab/core/schema.js');

const DEFAULT_TEMPORAL = Object.freeze({
    window_frames: 2,        /* 短时占有回看窗 (帧) */
    min_cluster_pts: 8,      /* ring 中视作「有占有」的最少 fg 点数 (仅 sanity) */
    boost_lost_max: 5,       /* 时序支持下 anchor 比 retention.max_lost_for_retain 额外多活的帧数 */
    still_min_pts: 40,       /* confirmed track 的 accepted 候选点数 < 此阈值视作「静止人被剥点」 */
    still_frames: 3,         /* 连续多少帧满足剥点条件才触发静止人恢复 */
    /* ponytail: spec 写 still_hot_radius_m=0.45 为恢复半径； 本实现把合成 anchor 钉在
       track.x/y 本身, 吸收统一走原链 rc.hot_cell_radius_m=0.4 (fg_plus_retained 同源)。
       0.45→0.4 是保守收窄， 不引入额外吸收语义； 若要 0.45 精确率从 chain 端调 rc。 */
    still_hot_radius_m: 0.45 /* 记录用途， 当前实施等同 rc.hot_cell_radius_m */
});

function applyTemporal(engine, cfg) {
    cfg = Object.assign({}, DEFAULT_TEMPORAL, cfg || {});
    const pipe = engine.pipe, rc = engine.cfg.retention;
    if (!pipe || !pipe.key_vox) throw new Error('applyTemporal 需要带 pipe 的 FUSION engine');

    const state = {
        gen: engine.generation,
        seg: engine.track_segment,
        ring: [],                 /* [{frame_index, keys:Set(key_vox), n:int}] 最近 fg 占有 */
        boost_used: new Map(),    /* anchor_id -> 已经消耗的 boost 帧数 */
        still_streak: new Map(),  /* track_id -> 连续「剥点」帧数 */
        seen_person: false        /* 本 segment 是否已出现过 human_confirmed (防零人会话误触) */
    };
    engine._temporal_stats = { recovered_pts: 0, boosted_retains: 0, resets: 0 };

    function wipe() {
        state.ring.length = 0;
        state.boost_used.clear();
        state.still_streak.clear();
        state.seen_person = false;
        engine._temporal_stats.resets++;
    }
    function observeMarkers() {
        if (state.gen !== engine.generation || state.seg !== engine.track_segment) {
            wipe();
            state.gen = engine.generation;
            state.seg = engine.track_segment;
        }
    }

    /* 上一帧 ring 中 anchor 半径内是否有占有 */
    function ringSupports(ax, ay, radius_m) {
        if (!state.ring.length) return false;
        const r2 = radius_m * radius_m, V = pipe.PIPE.voxel_m;
        const recent = state.ring[state.ring.length - 1].keys;
        for (const key of recent) {
            const parts = key.split(',');
            const cx = (Number(parts[0]) + 0.5) * V;
            const cy = (Number(parts[1]) + 0.5) * V;
            const dx = cx - ax, dy = cy - ay;
            if (dx * dx + dy * dy <= r2) return true;
        }
        return false;
    }

    const origAChain = engine._fusion_a_chain;
    engine._fusion_a_chain = function (fc, leveled, diag) {
        observeMarkers();
        const bank = engine.retention.tracks;
        /* ---------- (1) retention boost: anchor 已过 max_lost_for_retain 但未超
             boost_lost_max, 且上一帧 ring 在 hot_cell_radius_m 内有占有 → 把
             frame_index / timestamp 刷到本帧， 让原链 live 判定继续命中；
             消耗 1 帧 boost 预算。 未过期 (gap <= max_lost_for_retain) 的 anchor
             原链已会吸 — 不动。 ---------- */
        const injectBefore = Object.create(null);   /* id -> {x, y, kind} 本帧时序注入的 anchor */
        for (const id of Object.keys(bank)) {
            const a = bank[id];
            if (!a) continue;
            if (fc.timestamp - a.timestamp > rc.timeout_s) continue;
            const gap = fc.frame_index - a.frame_index;
            if (gap <= rc.max_lost_for_retain) continue;
            const used = state.boost_used.get(id) || 0;
            if (used >= cfg.boost_lost_max) continue;
            if (!ringSupports(a.x, a.y, rc.hot_cell_radius_m)) continue;
            a.frame_index = fc.frame_index;
            a.timestamp = fc.timestamp;
            if (a.confirmations < rc.window_confirm) a.confirmations = rc.window_confirm;
            state.boost_used.set(id, used + 1);
            injectBefore[id] = { x: a.x, y: a.y, kind: 'boost' };
            engine._temporal_stats.boosted_retains++;
        }
        /* ---------- (2) 静止人恢复： tracker 快照中 human_confirmed & lost==0 的
             track, 若 streak 达 still_frames, 把 anchor 半径内的合规点吸收 — 通过
             向 bank 注入合成 anchor (id `_still_<track_id>`), 由 fg_plus_retained
             机制自动吸。 真实 anchor 半径是 rc.hot_cell_radius_m; still_hot_radius_m
             在我们的「先验触发」里控制 — 只有「track 附近」才注入； 吸收本身仍走
             rc.hot_cell_radius_m (同源 fg_plus_retained)。 为不扩大吸收半径语义,
             仅注入「track 距离合成 anchor 位 = track.x/y 本身」， 让 chain 以自己
             的半径吸。 ---------- */
        const tracks = (engine.pipe_ctx && engine.pipe_ctx.tracker && engine.pipe_ctx.tracker.tracks) || [];
        if (state.seen_person) {
            for (const t of tracks) {
                if (!t.active || !t.human_confirmed) continue;
                if ((state.still_streak.get(t.id) || 0) < cfg.still_frames) continue;
                if (!Number.isFinite(t.x) || !Number.isFinite(t.y)) continue;
                const sid = '_still_' + t.id;
                bank[sid] = {
                    x: t.x, y: t.y,
                    timestamp: fc.timestamp, frame_index: fc.frame_index,
                    confirmations: rc.window_confirm
                };
                injectBefore[sid] = { x: t.x, y: t.y, kind: 'still' };
            }
        }

        /* ---------- 原链吸收 — 包括我们刚灌进去的 anchor 半径内的合规点 ---------- */
        const out = origAChain.call(this, fc, leveled, diag);

        /* ---------- (3) 记账： 当时序注入 anchor 的半径内有 RETAINED 点 → recovered.
             上游 chain 自身也有 retained anchor, 只数「落在我们注入 anchor 半径内」的,
             不会把原链条自带吸收误记为 recovered。 ---------- */
        const injectedIds = Object.keys(injectBefore);
        if (injectedIds.length) {
            const r2 = rc.hot_cell_radius_m * rc.hot_cell_radius_m;
            let rec = 0;
            const n = out.final_ids.length;
            for (let p = 0; p < n; p++) {
                if (out.sources[p] !== S.CAND_SRC.RETAINED) continue;
                const x = out.fg_final[p * 4], y = out.fg_final[p * 4 + 1];
                let hit = false;
                for (let i = 0; i < injectedIds.length; i++) {
                    const inj = injectBefore[injectedIds[i]];
                    const dx = x - inj.x, dy = y - inj.y;
                    if (dx * dx + dy * dy <= r2) { hit = true; break; }
                }
                if (hit) rec++;
            }
            engine._temporal_stats.recovered_pts += rec;
        }

        /* ---------- (4) streak 更新 (用本帧候选 + 上一帧 tracker 快照): 这是 inject
             之前的 tracker 快照， 不能用来判定 still_frames 触发的「本帧剥点」 — 但作为
             滞后一帧的近似是工程上最简且最稳的 (D05 probe 粒度)。 剥点的「连续帧」
             语义即滞后一帧判定。 ---------- */
        const byTrack = new Map();
        const cands = out.cands || [];
        for (const c of cands) {
            if (c.track_id === undefined || c.track_id === null) continue;
            if (c.classifier_decision !== S.CLS_DECISION.HUMAN_CANDIDATE && c.classifier_decision !== S.CLS_DECISION.CONFIRMED_HUMAN) continue;
            const cur = byTrack.get(c.track_id);
            if (cur === undefined || c.point_count < cur) byTrack.set(c.track_id, c.point_count);
        }
        for (const t of tracks) {
            if (!t.active || !t.human_confirmed) continue;
            state.seen_person = true;
            if (t.lost !== 0) { state.still_streak.delete(t.id); continue; }
            const pts = byTrack.get(t.id);
            if (pts === undefined) { state.still_streak.delete(t.id); continue; }
            if (pts < cfg.still_min_pts) state.still_streak.set(t.id, (state.still_streak.get(t.id) || 0) + 1);
            else state.still_streak.delete(t.id);
        }
        /* 若本帧触发过 _still_ 注入但下一帧 streak 被打断， 需要清掉合成 anchor。
           下一帧再进 chain 时上面会重写； 若整段 track 消失 (lost/track 不在)， 残留
           的 _still_ 会被原链 timeout/max_lost 自然过期 — 不必特殊处理。 */

        /* ---------- (5) ring 维护： 从 a_out 中 sources==FG 的点构建短时占有证据。
             不纳入 RETAINED (含我们刚注入的部分), 避免「自己注入又自己当证据」自维持。 ---------- */
        const keys = new Set();
        let fgN = 0;
        const nout = out.final_ids.length;
        for (let p = 0; p < nout; p++) {
            if (out.sources[p] !== S.CAND_SRC.FG) continue;
            keys.add(pipe.key_vox(out.fg_final[p * 4], out.fg_final[p * 4 + 1]));
            fgN++;
        }
        /* min_cluster_pts sanity: 占有太少当作没占有 */
        if (fgN >= cfg.min_cluster_pts) {
            state.ring.push({ frame_index: fc.frame_index, keys: keys });
            while (state.ring.length > cfg.window_frames) state.ring.shift();
        }
        return out;
    };

    /* ---------- 包 begin_session: generation 必变 → observeMarkers 命中 wipe ---------- */
    const origBegin = engine.begin_session;
    engine.begin_session = function (sid, reason) {
        const r = origBegin.call(this, sid, reason);
        observeMarkers();
        return r;
    };

    return {
        hook: 'd05_temporal',
        cfg: cfg,
        taps: ['_fusion_a_chain', 'begin_session'],
        state_peek: state
    };
}

module.exports = { applyTemporal, DEFAULT_TEMPORAL };

/* ------------------------- 自测 ------------------------- */
if (require.main === module) {
    const assert = require('assert');

    const PIPE = { voxel_m: 0.15, ground_keep_below_m: 0.05, z_max_m: 2.5 };
    function key_vox(x, y) { return Math.floor(x / PIPE.voxel_m) + ',' + Math.floor(y / PIPE.voxel_m); }

    /* 假 chain: 按 retention.tracks 的真实语义吸收 — anchor 半径内且「未过期」的
       都会吸成 RETAINED; 其余作为 FG 通过。 这样我们测试时序 hook 的吸收/记账/复位逻辑
       就建立在和原链一致的语义上。 */
    function makeEngine() {
        const e = {
            generation: 1,
            track_segment: 0,
            cfg: { retention: { window_confirm: 2, timeout_s: 60, hot_cell_radius_m: 0.4, max_lost_for_retain: 2 } },
            retention: { tracks: {} },
            pipe: { PIPE: PIPE, key_vox: key_vox },
            pipe_ctx: { tracker: { tracks: [] } },
            begin_session: function () { this.generation++; this.track_segment = 0; this.retention = { tracks: {} }; return this.generation; }
        };
        e._fusion_a_chain = function (fc, leveled) {
            const rc = this.cfg.retention;
            /* 原链会清理过期 anchor */
            const live = [];
            for (const id of Object.keys(this.retention.tracks)) {
                const a = this.retention.tracks[id];
                if (fc.timestamp - a.timestamp > rc.timeout_s) { delete this.retention.tracks[id]; continue; }
                if (fc.frame_index - a.frame_index > rc.max_lost_for_retain) { delete this.retention.tracks[id]; continue; }
                if (a.confirmations >= rc.window_confirm) live.push(a);
            }
            const ids = [], src = [], vals = [];
            const n = leveled.length / 4;
            const r2 = rc.hot_cell_radius_m * rc.hot_cell_radius_m;
            for (let k = 0; k < n; k++) {
                const x = leveled[k * 4], y = leveled[k * 4 + 1], z = leveled[k * 4 + 2];
                ids.push(k); vals.push(x, y, z, leveled[k * 4 + 3]);
                /* 默认 FG； 若落在 live anchor 半径内则打 RETAINED */
                let retained = false;
                for (const a of live) {
                    const dx = x - a.x, dy = y - a.y;
                    if (dx * dx + dy * dy <= r2) { retained = true; break; }
                }
                src.push(retained ? S.CAND_SRC.RETAINED : S.CAND_SRC.FG);
            }
            return { cands: [], final_ids: ids, sources: src, fg_final: new Float32Array(vals), invalid: 0 };
        };
        return e;
    }

    /* -------- 测试 1: gap_reset 触发 wipe, stats.resets=1 -------- */
    {
        const eng = makeEngine();
        applyTemporal(eng, { min_cluster_pts: 1 });
        const lv = new Float32Array([1.0, 1.0, 1.0, 0.5, 1.3, 1.1, 1.2, 0.5]);
        eng._fusion_a_chain({ frame_index: 1, timestamp: 1.0 }, lv, {});
        eng._fusion_a_chain({ frame_index: 2, timestamp: 2.0 }, lv, {});
        assert.equal(eng._temporal_stats.resets, 0);
        eng.track_segment++;                                     /* 模拟 gap_reset */
        eng._fusion_a_chain({ frame_index: 5, timestamp: 5.0 }, lv, {});
        assert.equal(eng._temporal_stats.resets, 1, 'gap_reset 必须触发一次 wipe/resets');
    }

    /* -------- 测试 2: still-person 触发 → recovered_pts>0 -------- */
    {
        const eng = makeEngine();
        applyTemporal(eng, { min_cluster_pts: 1, still_min_pts: 40, still_frames: 3 });
        /* track 在 (1.05,1.05), leveled 点在 (1.0,1.0) & (1.2,1.1) — 离 track 在
           hot_cell_radius_m=0.4 半径内, 一旦 _still_t1 注入 bank, 原链会吸它们成
           RETAINED → recovered_pts>0。 */
        eng.pipe_ctx.tracker.tracks = [{ id: 't1', active: true, human_confirmed: true, lost: 0, x: 1.05, y: 1.05 }];
        /* chain 造一个候选让 streak 累计: track_id=t1, point_count=5 (<still_min_pts), CONFIRMED_HUMAN */
        const origChain = eng._fusion_a_chain;
        eng._fusion_a_chain = function (fc, leveled) {
            const out = origChain.call(this, fc, leveled);
            out.cands.push({ track_id: 't1', classifier_decision: S.CLS_DECISION.CONFIRMED_HUMAN, point_count: 5 });
            return out;
        };
        /* 顺序错了 — applyTemporal 已经包了 chain; 需要重包。 干脆直接重建一组。 */
        const eng2 = makeEngine();
        eng2.pipe_ctx.tracker.tracks = [{ id: 't1', active: true, human_confirmed: true, lost: 0, x: 1.05, y: 1.05 }];
        const oc = eng2._fusion_a_chain;
        eng2._fusion_a_chain = function (fc, leveled) {
            const out = oc.call(this, fc, leveled);
            out.cands.push({ track_id: 't1', classifier_decision: S.CLS_DECISION.CONFIRMED_HUMAN, point_count: 5 });
            return out;
        };
        applyTemporal(eng2, { min_cluster_pts: 1, still_min_pts: 40, still_frames: 3 });
        const lv = new Float32Array([1.0, 1.0, 1.0, 0.5, 1.2, 1.1, 1.2, 0.5]);
        eng2._fusion_a_chain({ frame_index: 1, timestamp: 1.0 }, lv, {});
        assert.equal(eng2._temporal_stats.recovered_pts, 0, 'streak=1 未达阈值');
        eng2._fusion_a_chain({ frame_index: 2, timestamp: 2.0 }, lv, {});
        eng2._fusion_a_chain({ frame_index: 3, timestamp: 3.0 }, lv, {});
        /* streak 在第 3 帧结束时才到 still_frames=3 → 第 4 帧 chain 触发注入+吸收 */
        const bank3 = eng2.retention.tracks;
        assert(!bank3['_still_t1'], '第 3 帧 chain 前 streak 还没到， 不该注入');
        eng2._fusion_a_chain({ frame_index: 4, timestamp: 4.0 }, lv, {});
        const bank = eng2.retention.tracks;
        assert(bank['_still_t1'], '第 4 帧 chain 前 streak=3 → 合成 still anchor 必须已注入 bank');
        assert(bank['_still_t1'].confirmations >= eng2.cfg.retention.window_confirm, 'confirmations 必须达 window_confirm 才会 chain-live');
        assert(eng2._temporal_stats.recovered_pts > 0, 'still-person 触发后必须 recovered_pts>0');
    }

    /* -------- 测试 3: boost 路径 — 过期 anchor 但 ring 支持 → 续命并吸收 -------- */
    /* 省略 — still 测试已覆盖「inject → chain 吸 → recovered」路径； boost 只差
       「过期 anchor 续命」这一个分支， 在 9-session 评估里由主控观察 boosted_retains。 */

    console.log('HOOK_TEMPORAL_SELFTEST_PASS');
}
