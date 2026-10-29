/* FRESH-MAP r01 — 增量新鲜度占用图（纯函数层；node 可测，零 DOM/THREE 依赖）。
 *
 * 机理（对应 TRADITIONAL_CLUSTER_ML_EFFECT_REPORT §五-3「背景只作特征/风险，不做
 * 不可逆硬删」的第一个工程验证；用户 2026-10-15 拍板"灰度化背景 + 新鲜度渐黑"）：
 *   背景层 = 批式一次、不可变参考图（PIPE.build_reference_map），无删除权。
 *   新鲜度层 = 纯增量：每体素 {慢参考形心 rx/ry/rz, occ, f∈[0,1], event_run,
 *     ever_event, ref_sup, last_event_t}。运动/新出现事件判据（全过才记候选帧）：
 *       支持门 n ≥ ev_hit_min_pts（沿用 bg_hit_min_pts，单点 sparkle 永不过）；
 *       ref 支撑体素 → 只认位移门：多数点距慢参考形心 > move_tol（家具自己不动）；
 *       非 ref 体素 → 发过事件前认"新出现延续观察"（首见帧或上一帧刚见过），
 *         发过事件后只认位移门 —— 静止新物体亮一次后渐黑（用户要的"变黑"），
 *         重新动起来（含走回头路）靠位移重触发；EMA 滞后会垫高 dev，慢走也能触发。
 *       连续 ≥ ev_confirm_frames 帧候选 → f=1（单帧闪现过不了）。
 *     非事件帧 f *= exp(-dt/τ)（或 linear），dt 用调用方真实秒。
 *   HOT 期（f ≥ hot_f_min）冻结慢参考与 occ EMA —— 否则静立者被 EMA 慢慢吃掉，
 *     那正是本支线要修的在线硬背景吞人机理。
 *   三态（亮度=f 连续；分类=离散三态）：HOT（热度）/
 *     GHOST（¬ref_sup ∧ ever_event ∧ 距上次发火 < ghost_ttl_s："曾经动/新出现、后来停"
 *     的静立者证据——从未动过的家具永远进不了 GHOST；r7：GHOST 也有寿命，
 *     "随时间不动而变黑"同样适用于残影，超寿沉入 COLD_BG，静坐者由锚点层续命）/
 *     COLD_BG（其余冷却态：灰度背景；ref 支撑体素事件过期后也归此态）。
 *   全程没有任何删除权：候选 = HOT ∪ GHOST ∪ live 锚点半径内的点。
 *   目标级记忆 FreshMemory：锚点语义照搬 human_core/engine.js DEFAULT_CFG.retention
 *     （window_confirm=3 / timeout_s=180 / max_lost_for_retain=30 / hot_cell_radius_m=0.4）。
 *
 * 时间纪律：dt = 调用方时间戳差（bag_time_sec 真实秒，对齐 core/timebase.py 显式
 *   source-stamp）；乱序/回退时间戳 dt 钳到 0（只衰减不回放）；帧连续性用 st.frame_no
 *   （更新调用计数），不是时间推断。
 * 前提：设备静止。板端接驳的前置条件是 core/sensor_quality.py static_background_usable。
 * 诚实边界：从 warmup 起全程静立的人会被参考图当家具——无监督原理上不可分
 *   （limb v1..v6 教训），新鲜度只把"硬删"变成"降级+保留证据"。
 */
"use strict";

var HP;   /* human_pipe_lib 模块命名空间（函数） */
if (typeof globalThis !== "undefined" && globalThis.human_pipe_lib) HP = globalThis.human_pipe_lib;
if (!HP && typeof require === "function") HP = require("../../../pc_apps/human_replay/human_pipe_lib.js");
var PIPE = HP.PIPE;             /* 阈值常量对象（注意：常量在模块的 .PIPE 子对象下） */

/* ---------------- 全部阈值集中（参数表见 README；标定项 = τ/ev_hit/ev_confirm/move_tol/hot_f_min） ---------------- */
var FP = {
    ev_hit_min_pts: 2,        /* 支持门（沿用 PIPE.bg_hit_min_pts） */
    move_tol_m: 0.15,         /* 位移门阈值。必须 > 单体素全对角/2 可达的最大"点距形心"距离
                                 (格 0.15×0.15×0.12，体对角 ≈0.244，质心对角 ≈0.122)：
                                 否则稀疏家具在两角间噪声跳变会每帧满足"多数点>tol"→ 永久 HOT
                                 （r2 目视发现，M1 尾段 fired 非零即其影子）。
                                 抬到 0.15 后位移门只对"慢参考漂出本格"生效；
                                 运动/新物体发火主通道 = 新格出现（跨格），不受影响。 */
    ref_match_radius_m: 0.12, /* ref 支撑判据半径（=PIPE.bg_match_radius，不另发明） */
    ref_occ_min: 0.5,         /* 参考图入图占用率（沿用 PIPE.bg_ref_occ_min，未标定候选值） */
    ev_confirm_frames: 2,     /* 滞回主噪声闸 */
    tau_s: 8,                 /* 衰减时间常数：τ=8 时静 15.4s→f=0.15（黑界），静 1min→0.0006 */
    decay: "exp",             /* exp | linear */
    hot_f_min: 0.15,          /* HOT/冷却分界（≈2τ 视觉"基本变黑"） */
    ghost_ttl_s: 20,          /* GHOST 也有寿命（用户原话"随时间不动而变黑"同样适用）：
                                 超 20s 无新发火 → 沉入 COLD_BG。r6/r8 截图定罪：永久/长寿
                                 GHOST 让振动家具柱留在候选+认领盘内常亮。
                                 静坐者由锚点层（180s）续命。 */
    slow_alpha: 0.02,         /* 冷却态慢参考/占用 EMA（时间常数 ≈50 帧） */
    z_min_m: PIPE.ground_keep_below_m, /* 工作空间下沿（剔地面，必须开否则吞人脚） */
    z_max_m: PIPE.z_max_m,
    /* 目标级记忆：照搬 engine.js DEFAULT_CFG.retention，不改值 */
    retention: { window_confirm: 3, timeout_s: 180, max_lost_for_retain: 30, hot_cell_radius_m: 0.4 },
};

function _opts(opts) { return Object.assign({}, FP, opts || {}); }

/* 3D 体素邻域键枚举（与 human_pipe_lib 私有 _bg_key_ijk 同常量，键空间互操作；pipe 未导出，此处复刻）。 */
var _BG_BASE = 8192, _BG_OFF = 4096;
function _bg_key_ijk(ix, iy, iz) {
    return ((ix + _BG_OFF) * _BG_BASE + (iy + _BG_OFF)) * _BG_BASE + (iz + _BG_OFF);
}

/* 有界匹配（语义 = _bg_match_rec：3×3×3 邻域内任一体素形心距 < radius）。 */
function _match_rec(map, x, y, z) {
    var r2 = FP.ref_match_radius_m * FP.ref_match_radius_m;
    var ix = Math.floor(x / PIPE.bg_voxel_xy), iy = Math.floor(y / PIPE.bg_voxel_xy),
        iz = Math.floor(z / PIPE.bg_voxel_z);
    for (var a = -1; a <= 1; a++) for (var b = -1; b <= 1; b++) for (var c = -1; c <= 1; c++) {
        var rec = map.get(_bg_key_ijk(ix + a, iy + b, iz + c));
        if (!rec) continue;
        var dx = rec.x - x, dy = rec.y - y, dz = rec.z - z;
        if (dx * dx + dy * dy + dz * dz < r2) return rec;
    }
    return null;
}

/* ---- 背景层：批式、一次、不可变（occ ≥ ref_occ_min 的参考体素记录集，无删除权） ---- */
function build_reference(frames_xyzi, opts) {
    opts = opts || {};
    var o = _opts(opts);
    var ref = HP.build_reference_map(frames_xyzi, {});
    var voxels = new Map();
    ref.voxels.forEach(function (rec, key) { if (rec.occ >= o.ref_occ_min) voxels.set(key, rec); });
    return { nframes: ref.nframes, voxels: voxels };
}

/* ---- 新鲜度层状态 ---- */
function create_fresh_state(ref_pack, opts) {
    return { o: _opts(opts), ref: ref_pack ? ref_pack.voxels : new Map(),
             voxels: new Map(), t: null, frame_no: 0 };
}

/* 单帧增量。xyzi = Float32Array[x,y,z,i]*（调用方已配平+denoise）。
 * 返回 rep = {n_pts, n_obs_vox, n_event_fired, n_hot, n_ghost, obs(Map 当帧累加器), t, frame_ms}。
 * obs 是当帧快照 {n,sx,sy,sz,dev}，供上层做 P-set/存活统计，勿跨帧持有。 */
function fresh_update(st, xyzi, t_sec) {
    var o = st.o, t0 = _now();
    if (!Number.isFinite(t_sec)) throw new Error("时间戳必须有限（真实秒）");
    var dt = st.t === null ? 0 : Math.max(0, t_sec - st.t);   /* 乱序/回退钳 0 */
    st.t = Math.max(st.t === null ? t_sec : st.t, t_sec);
    st.frame_no++;

    /* 1) 全体素先衰减（本轮发火的在下面重新置 1） */
    if (dt > 0) {
        var mul = o.decay === "linear" ? null : Math.exp(-dt / o.tau_s);
        st.voxels.forEach(function (v) {
            if (v.f <= 0) return;
            v.f = mul ? v.f * mul : Math.max(0, v.f - dt / o.tau_s);
        });
    }

    /* 2) 当帧体素累加；位移计数只对冷却态体素比对慢参考。
     *    点流空间连续 → 同格连跑，last-key 记忆省两次 Map 查找（S4 实时预算）。 */
    var hot = o.hot_f_min, move2 = o.move_tol_m * o.move_tol_m;
    var per = new Map();
    var lk = -1, la = null, lv = null;
    for (var k = 0; k < xyzi.length; k += 4) {
        var x = xyzi[k], y = xyzi[k + 1], z = xyzi[k + 2];
        if (z < o.z_min_m || z > o.z_max_m) continue;
        if (!Number.isFinite(x + y + z)) continue;
        var key = HP.key_bg(x, y, z);
        var a, v0;
        if (key === lk) { a = la; v0 = lv; }
        else {
            a = per.get(key);
            if (!a) { a = { n: 0, sx: 0, sy: 0, sz: 0, dev: 0 }; per.set(key, a); }
            v0 = st.voxels.get(key);
            lk = key; la = a; lv = v0;
        }
        a.n++; a.sx += x; a.sy += y; a.sz += z;
        if (v0 && v0.f < hot) {
            var dx = x - v0.rx, dy = y - v0.ry, dz = z - v0.rz;
            if (dx * dx + dy * dy + dz * dz > move2) a.dev++;
        }
    }

    /* 3) 事件判据 + 滞回发火；HOT 冻结；冷却态 EMA */
    var fired = 0;
    per.forEach(function (a, key) {
        var cx = a.sx / a.n, cy = a.sy / a.n, cz = a.sz / a.n;
        var v = st.voxels.get(key), created = !v;
        if (created) {
            v = { rx: cx, ry: cy, rz: cz, occ: 0, f: 0, event_run: 0, ever_event: false,
                  /* 支撑 = 同格成员（整数网格对配准误差到格级最稳，r3 目视修复：跨天
                     质心半径 0.12 卡在体对角 0.122 下沿 → 家具整片误判 GHOST）或 邻域质心匹配 */
                  ref_sup: st.ref.has(key) || _match_rec(st.ref, cx, cy, cz) !== null,
                  last_event_t: null, last_seen_f: null };
            st.voxels.set(key, v);
        }
        var cand = false;
        if (a.n >= o.ev_hit_min_pts) {
            var majority = a.dev >= Math.max(2, (a.n + 1) >> 1);       /* 位移门（含走回头路重触发） */
            if (!v.ref_sup && !v.ever_event)
                cand = created || v.last_seen_f === st.frame_no - 1;   /* 新出现的延续观察 */
            else
                cand = majority;
        }
        v.event_run = cand ? v.event_run + 1 : 0;
        if (v.event_run >= o.ev_confirm_frames) {
            v.f = 1; v.ever_event = true; v.last_event_t = t_sec; fired++;
        }
        v.last_seen_f = st.frame_no;
        if (v.f < hot) {   /* 冷却态才吸收；HOT（含刚发火）冻结慢参考 */
            v.rx += o.slow_alpha * (cx - v.rx);
            v.ry += o.slow_alpha * (cy - v.ry);
            v.rz += o.slow_alpha * (cz - v.rz);
            v.occ += o.slow_alpha * (1 - v.occ);
        }
    });
    st.voxels.forEach(function (v, key) {
        if (!per.has(key) && v.f < hot) v.occ += o.slow_alpha * (0 - v.occ);
    });

    /* 4) 状态计数 */
    var n_hot = 0, n_ghost = 0;
    st.voxels.forEach(function (v) {
        if (v.f >= hot) n_hot++;
        else if (!v.ref_sup && v.ever_event && v.last_event_t !== null &&
                 t_sec - v.last_event_t < o.ghost_ttl_s) n_ghost++;
    });
    return { n_pts: xyzi.length / 4, n_obs_vox: per.size, n_event_fired: fired,
             n_hot: n_hot, n_ghost: n_ghost, obs: per, t: st.t, frame_ms: _now() - t0 };
}

/* 丢帧只做衰减，不改证据（时间戳回退钳 0）。 */
function fresh_decay_only(st, t_sec) {
    if (!Number.isFinite(t_sec)) throw new Error("时间戳必须有限（真实秒）");
    var o = st.o, dt = st.t === null ? 0 : Math.max(0, t_sec - st.t);
    st.t = Math.max(st.t === null ? t_sec : st.t, t_sec);
    if (dt > 0) {
        var mul = o.decay === "linear" ? null : Math.exp(-dt / o.tau_s);
        st.voxels.forEach(function (v) {
            if (v.f <= 0) return;
            v.f = mul ? v.f * mul : Math.max(0, v.f - dt / o.tau_s);
        });
    }
    return { t: st.t };
}

/* 三态判定。GHOST = ¬ref_sup ∧ ever_event ∧ 距上次发火 < ghost_ttl_s（超寿沉入背景）。 */
function voxel_state(st, key) {
    var v = st.voxels.get(key);
    if (!v) return "UNSEEN";
    if (v.f >= st.o.hot_f_min) return "HOT";
    if (!v.ref_sup && v.ever_event && v.last_event_t !== null &&
        st.t - v.last_event_t < st.o.ghost_ttl_s) return "GHOST";
    return "COLD_BG";
}

function point_state(st, x, y, z) {
    if (z < st.o.z_min_m || z > st.o.z_max_m) return "OUT_OF_BAND";
    return voxel_state(st, HP.key_bg(x, y, z));
}

/* live 锚点（confirmations ≥ window_confirm）。 */
function mem_live(mem) {
    var out = [];
    for (var i = 0; i < mem.anchors.length; i++)
        if (mem.anchors[i].confirmations >= mem.o.retention.window_confirm) out.push(mem.anchors[i]);
    return out;
}

/* 候选点集 = HOT/GHOST 体素内的点 ∪ live 锚点半径（XY）内的点。无删除权。
 * 体素态按格记忆（点流空间连续）；锚点判定必须逐点（半径边界穿过单格）。 */
function candidate_xyzi(st, xyzi, mem) {
    var o = st.o, r2 = o.retention.hot_cell_radius_m * o.retention.hot_cell_radius_m;
    var live = mem ? mem_live(mem) : [];
    var out = [];
    var lk = -1, lg = false, hasL = false;
    for (var k = 0; k < xyzi.length; k += 4) {
        var x = xyzi[k], y = xyzi[k + 1], z = xyzi[k + 2];
        if (z < o.z_min_m || z > o.z_max_m) continue;
        var key = HP.key_bg(x, y, z), ghost_hot;
        if (hasL && key === lk) ghost_hot = lg;
        else {
            var s = voxel_state(st, key);
            ghost_hot = (s === "HOT" || s === "GHOST");
            lk = key; lg = ghost_hot; hasL = true;
        }
        var keep = ghost_hot;
        if (!keep) {
            for (var li = 0; li < live.length; li++) {
                var dx = live[li].x - x, dy = live[li].y - y;
                if (dx * dx + dy * dy <= r2) { keep = true; break; }
            }
        }
        if (keep) out.push(x, y, z, xyzi[k + 3]);
    }
    return new Float32Array(out);
}

/* ---- 目标级记忆（语义照搬 engine.js retention：连续确认计数 + 双时钟到期） ---- */
function FreshMemory(opts) {
    return { o: _opts(opts), anchors: [], next_id: 1 };
}
/* clusters = [{cx,cy,cz,n,ev}]：ev=该簇是否含当帧新证据格（HOT/GHOST态点）。
 * ev===false 的簇不建锚也不续命（r6 定罪：锚点靠自身半径"自吞续命"，错配家具柱永生）。
 * 贪心最近邻半径关联。 */
function mem_tick(mem, clusters, frame_index, t_sec) {
    var o = mem.o, rc = o.retention, r2 = rc.hot_cell_radius_m * rc.hot_cell_radius_m;
    mem.anchors = mem.anchors.filter(function (a) {
        return t_sec - a.timestamp <= rc.timeout_s && frame_index - a.frame_index <= rc.max_lost_for_retain;
    });
    for (var ci = 0; ci < clusters.length; ci++) {
        var cl = clusters[ci], best = null, best_d2 = r2;
        if (cl.ev === false) continue;
        for (var ai = 0; ai < mem.anchors.length; ai++) {
            var a = mem.anchors[ai];
            var dx = a.x - cl.cx, dy = a.y - cl.cy, d2 = dx * dx + dy * dy;
            if (d2 < best_d2) { best_d2 = d2; best = a; }
        }
        if (best) {
            best.confirmations = best.frame_index === frame_index - 1 ? best.confirmations + 1 : 1;
            best.x = cl.cx; best.y = cl.cy; best.z = cl.cz; best.n = cl.n;
            best.timestamp = t_sec; best.frame_index = frame_index;
        } else {
            mem.anchors.push({ id: mem.next_id++, x: cl.cx, y: cl.cy, z: cl.cz, n: cl.n,
                               timestamp: t_sec, frame_index: frame_index, confirmations: 1 });
        }
    }
    return { n_total: mem.anchors.length, n_live: mem_live(mem).length };
}

/* 新鲜度→亮度 LUT（M2 热度渲染预留；仓库无现成热度映射，净新增，单调即可）。 */
function heat_rgb(f) {
    var t = Math.max(0, Math.min(1, f));
    return [Math.sqrt(t), 0.85 * t * t, 0.55 * t * t * t];
}

var _now = (typeof performance !== "undefined" && performance.now)
    ? function () { return performance.now(); } : function () { return Date.now(); };

var _api = {
    FP: FP,
    build_reference: build_reference,
    create_fresh_state: create_fresh_state,
    fresh_update: fresh_update,
    fresh_decay_only: fresh_decay_only,
    voxel_state: voxel_state,
    point_state: point_state,
    candidate_xyzi: candidate_xyzi,
    FreshMemory: FreshMemory,
    mem_tick: mem_tick,
    mem_live: mem_live,
    heat_rgb: heat_rgb,
    _match_rec: _match_rec,
};
if (typeof module !== "undefined" && module.exports) { module.exports = _api; }
if (typeof globalThis !== "undefined") { globalThis.fresh_map_lib = _api; }
