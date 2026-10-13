# 补丁 02 · BUG-R40-T02：确认票按「观测」而非「帧」开窗（帧索引 + 帧过期）

> 根因登记：`../2026-10-07_hrw03_r40_research_r1/07_research_and_minimal_plan_r2.md` §4「BUG-R40-T02」；
> 方案：`../2026-10-07_hrw03_r40_research_r1/08_bug_and_patch_design.md`「BUG-R40-T02」。
> 依赖：**先实施补丁 01（同帧唯一 track）**，再叠加本补丁。min_age/votes/window/lost 全部不动。
> 性质：审查/派发用最小补丁草案，未 commit。

## 现状缺陷（已复现）

`best.votes` 只是「每次有候选命中就 push 0/1」的观测数组；空帧只在 lost 计数循环 `lost++`，**不会写 0，也不会把旧正票过期**，因此「最近 5 帧 ≥ 3 票」事实上是「最近 5 个观测 ≥ 3 票」。

- 合成复现（R40 r2）：f0 正、f1 正、f2–f8 空、f9 正 → `track_confirmed=true`；但最近 5 帧只有 f9 一帧正。
- 真实帧（R40 r2）S/track4 观测帧 `[53,55,56,61]`、票 `[0,1,1,1]` 在 f61 被计为确认，而 f57–f61 这五帧只有 f61 一票。

## 完整替换代码（human_pipe_lib.js，叠加在补丁 01 之后）

仅 `tick()` 内的时间确认段变化；其余（fall 判、pipeline、Fall 阈值）完全不动：

```js
Tracker.prototype.tick = function (frame_idx, clusters) {
    var gate2 = PIPE.track_gate_xy_m * PIPE.track_gate_xy_m;
    var used = {};                                                /* PATCH_01 */
    for (var ci = 0; ci < clusters.length; ci++) {
        var f = clusters[ci];
        if (!f.ok) continue;
        /* BUG-R40-T02：同 frame_idx 重复调用 tick 非法（避免历史票被未来重写）。 */
        if (this.last_frame !== undefined && frame_idx <= this.last_frame) {
            throw new Error("ERR_TICK_NON_MONOTONIC_FRAME " + frame_idx + " <= " + this.last_frame);
        }
        /* 找本帧最近未用 track */
        var best = null, best_d2 = gate2;
        for (var ti = 0; ti < this.tracks.length; ti++) {
            var t = this.tracks[ti];
            if (!t.active) continue;
            if (used[t.id]) continue;
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
        used[best.id] = true;
        best.last_seen = frame_idx;
        /* 5d 时间确认：最近 human_confirm_window 个**帧**内 ≥ human_confirm_votes 帧
         * CONFIRMED_HUMAN，且 track 年龄 ≥ min_age */
        var vote = (f.joint === "CONFIRMED_HUMAN") ? 1 : 0;
        var votes = best.votes || (best.votes = []);
        votes.push({ f: frame_idx, v: vote });                    /* PATCH_02：带帧戳 */
        /* 丢弃已过期观测：只统计 [frame_idx-window+1, frame_idx] */
        var cutoff = frame_idx - PIPE.human_confirm_window + 1;
        while (votes.length && votes[0].f < cutoff) votes.shift();
        var vs = 0;
        for (var vi = 0; vi < votes.length; vi++) vs += votes[vi].v;
        best.human_confirmed = vs >= PIPE.human_confirm_votes
            && (frame_idx - best.born_idx + 1) >= PIPE.human_confirm_min_age;
        f.track_id = best.id;
        f.track_confirmed = best.human_confirmed;
        var hx = best.pose_history || (best.pose_history = []);
        hx.push({ f: frame_idx, upcos: best.upcos, height: best.height });
        if (hx.length > 120) hx.shift();
    }
    /* BUG-R40-T02：本帧无候选命中的活跃 track，显式补 0 票（帧戳不重复由 used/set 保证）。 */
    for (var tm = 0; tm < this.tracks.length; tm++) {
        var tmpt = this.tracks[tm];
        if (!tmpt.active || used[tmpt.id] || tmpt.last_seen === frame_idx) continue;
        /* tmpt.last_seen !== frame_idx 由 lost 循环接管；这里给「本帧无候选但还在窗口内」的 track 立案 0 票。*/
        var missed = tmpt.votes || (tmpt.votes = []);
        missed.push({ f: frame_idx, v: 0 });
        var cut = frame_idx - PIPE.human_confirm_window + 1;
        while (missed.length && missed[0].f < cut) missed.shift();
    }
    /* lost 计数（原语义不动） */
    for (var ti2 = 0; ti2 < this.tracks.length; ti2++) {
        var t2 = this.tracks[ti2];
        if (!t2.active) continue;
        if (t2.last_seen !== frame_idx) {
            t2.lost++;
            if (t2.lost > PIPE.track_lost_max) t2.active = false;
        }
    }
    this.last_frame = frame_idx;                                  /* PATCH_02 */
};
```

## 语义回归（总账）

| 旧行为（bug） | 新行为 | 是否仍是 frozen 参数语义 |
|---|---|---|
| window=5 观测的 0/1 数组 | window=5 **帧** 的 `{f,v}` 数组；空帧显式 0 票 | 是：只把语义钉回 R40 「最近 5 帧 ≥3 票」的声明 |
| 空帧不写票 | 空帧补 0 票 | 是：不改变 `human_confirm_votes=3`/`min_age=3` |
| 同 frame 重复 `tick` 可能重写未来票 | 显式 ERR_TICK_NON_MONOTONIC_FRAME | 是：与 R40 「不进未来票/不以掩代修」一致 |
| seek/重置 → 继续旧票 | 由调用者创建新 Tracker（已有 `_run_pipe_frame` 每次新建；浏览器 `human_detect.js` 每次新会话同样） | 是：不触及 Fall，只约束入口 |

## 有意未改

- 不改 `fall_assess` / `pose_history` 内容（历史保留 120 帧，Fall 另走存活条件）；
- 不改 lost 从「last_seen 现现帧」升级（保留 R40 原有 lost++ 语义）；
- 不改 PIPE 任何数值；
- 不引入新模块/新依赖。

## 配对回归（`tests/PATCH_02_tracker_t02.test.js`）

断言：gap 序列不确认；连续 3/5 帧不变；同帧重复 `tick` 抛错；倒退 `tick` 抛错。
