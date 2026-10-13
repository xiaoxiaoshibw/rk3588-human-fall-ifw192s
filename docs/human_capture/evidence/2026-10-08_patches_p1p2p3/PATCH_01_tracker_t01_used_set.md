# 补丁 01 · BUG-R40-T01：Tracker 同帧多簇复用同一 track（used-set 守卫）

> 根因登记：`../2026-10-07_hrw03_r40_research_r1/07_research_and_minimal_plan_r2.md` §4「BUG-R40-T01」；
> 补丁方案：`../2026-10-07_hrw03_r40_research_r1/08_bug_and_patch_design.md`「BUG-R40-T01」。
> 性质：**审查/派发用最小补丁草案，未 commit、未应用到 master**。生产修改需独立授权。
> 最小改动：仅在 `tick()` 内新增一个本帧 `used` Set；不动最近邻贪心、EMA、`track_gate_xy_m=0.75`、`ema_alpha=0.35`、`track_lost_max=8`、簇输入顺序。

## 现状缺陷（已复现）

`Tracker.tick()` 里对**本帧**候选循环时，每找到一个最近 track 就立即 `EMA` 更新它、并允许**下一候选**再次命中同一个 track（包括本帧刚新建、刚被前一候选 EMA 过的 track）。后果：同帧 3 个簇可给同一 track `votes.push(0/1/1/1)`、`pose_history` 重复采样。

- 合成复现（R40 r2）：年龄 3 时同帧 3 个 CONFIRMED_HUMAN 簇在 0.75 m 内全部命中 track1，`votes=[0,0,1,1,1]` → 中第 3 簇单帧即 `track_confirmed=true`。这**不是**「同帧 3/5 时间窗」语义，是同一观测被记 3 票。
- 真实帧（R40 r2）S/f46：S0(n633)、S1(n49) 两个候选都分到 track3；S0 命中距离 0.07036 m，S1 命中刚被 EMA 移动过的同一 track（此时距离 0.66665 m）。

## 完整替换代码（human_pipe_lib.js）

把现有 `Tracker.prototype.tick` （当前 598–657 行）整体替换为下版：

```js
/* ---- 7 · 跟踪：贪心最近邻 + EMA + lost。一人一条 Track ----
 * 每条 Track：{id, x,y,z,height,upcos,label, n, lost, born_idx, pose_history[]}
 * pose_history 给 fall 判。*/
function Tracker() { this.next_id = 1; this.tracks = []; }
Tracker.prototype.tick = function (frame_idx, clusters) {
    var gate2 = PIPE.track_gate_xy_m * PIPE.track_gate_xy_m;
    /* BUG-R40-T01 守卫：本帧已分配 track id，禁止本帧后续候选再命中。 */
    var used = {};
    for (var ci = 0; ci < clusters.length; ci++) {
        var f = clusters[ci];
        if (!f.ok) continue;
        var best = null, best_d2 = gate2;
        for (var ti = 0; ti < this.tracks.length; ti++) {
            var t = this.tracks[ti];
            if (!t.active) continue;
            if (used[t.id]) continue;          /* ← 唯一新增约束 */
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
        used[best.id] = true;                /* ← 本帧标记：新建/命中同帧唯一 */
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
```

## 有意未改（R40 明确边界，不在本补丁里改）

- 不引入 Hungarian/全局匹配（停止条件要求先到那个复杂度就退设计）；
- 不改簇输入顺序（仍按 point/voxel Map 插入顺序 → BFS 决定）；
- 不改 `track_gate_xy_m`、`ema_alpha`、`track_lost_max`；
- 不改 `votes` 结构/语义（那是 T02 的事，与本补丁独立）；
- 不改 lost 计数的语义（仍旧每条每帧至多 +1）。

## 配对回归（见同目录 `tests/PATCH_01_tracker_t01.test.js`）

断言：同帧 3 簇距 ≤0.75 m 时各自独立 track、每 track 每帧至多 1 vote / 1 pose_history 样本；单人连续轨迹行为不变。
