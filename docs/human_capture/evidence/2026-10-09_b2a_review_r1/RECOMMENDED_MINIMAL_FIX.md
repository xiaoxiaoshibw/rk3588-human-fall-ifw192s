# 最小修复建议（本轮仅建议，不实施；需单独授权与验收表）

每条独立、最小、附验收断言与影响半径。**不改 RF 模型 / 阈值 / MIN_AGE / TTL / 门 / z 带 / bg_envelope / 生产 human_pipe_lib.js / 融合层 v2。**

## FIX-1（P0）associate 同帧多簇绑同一 track —— 本帧认领集

**缺陷**：`detect_overlay.js:195-226` 无「本帧已认领」集 → 两簇绑同一 track，`age++` 两次、`cx/cy` 覆写。

**最小修复（伪码）**：
```js
function associate(clusters, fps) {
    var alive = new Set();
    var claimed = {};   // 本帧已被某簇认领的 track_id
    for (var c = 0; c < clusters.length; c++) {
        var cl = clusters[c], best = null, best_d = TRACK_GATE_M;
        for (var t = 0; t < last.tracks.length; t++) {
            var tr = last.tracks[t];
            if (claimed[tr.id]) continue;              // ← 唯一新增：已被认领则跳过
            var d = Math.hypot(cl.cx - tr.cx, cl.cy - tr.cy);
            if (d < best_d) { best_d = d; best = tr; }
        }
        if (best) { best.cx=cl.cx; ...; best.age++; claimed[best.id]=1; cl.track_id=best.id; }
        else { /* 新建 track, 不变 */ }
        alive.add(cl.track_id);
    }
    /* miss++ 段不变 */
}
```
- **行为变化**：同帧第二簇若唯一候选 track 已被认领，则退为"新建 track"（而非共享）。`age` 每帧至多 +1。
- **验收断言**：CE1 重跑 → `tr.age===2`（非 3）、`tr.cx` 保留先绑簇 A 或按最近者，不再被后簇无条件覆写；CE2 → 两簇 `track_id` 不同。
- **影响半径**：仅 track 存活/计数；RF 与聚类不动。
- **风险**：柜位裂簇会从"共享 1 track"变为"裂成 2 track"，**track 总数短期上升**——这是正确反映真实簇结构，需在 release note 标注。

## FIX-2（P0/P1）删除或修正 `is_stable` HUD 分组 —— 停止把关联状态当分类器

**缺陷**：`is_stable(miss===0)` 对 `shown` 恒 true（Q3），`weak` 死代码；且 `miss===0` 不能区分连续误检家具（CE3）。

**两条路线（选一，倾向 A）**：

**A. 删除弱分组（推荐，最诚实）**：HUD 只显示 `人 N 个 (track ...)`（confirmed 列表），不再尝试用关联状态冒充"人 vs 非人"。删除 `is_stable`/`stable`/`weak` 分支与 `stat_count`。
- 验收：HUD 文案回退到 dedup 后的 confirmed 列表；无「低稳定候选」字样。
- 依据：分类判别只能来自 RF；关联状态无权冒充。**用户裁定"不能为去柜子牺牲人检"也反对用 miss 卡人。**

**B. 若要保留弱分组**：`is_stable` 改为基于**历史**而非当前帧——如近 K=30 帧 miss 计数 `miss_hist`（在 associate 维护，`miss++`/`命中` 入窗），`is_stable = (近K帧 miss 占比 < 阈值)`。真皮稳 1.0，间歇柜位 run 中位 1 帧→占比低。但**这接近 TRACK_MIN_AGE 加强版，与"不改 MIN_AGE"边界需谨慎**，需用户点头。

## FIX-3（P1）reset 单点根因 —— 在 `replay.js load()` 入口调 reset

**缺陷**：reset 只清 detect_overlay.last，管不到 replay.js rAF/滑块/step/`?sid=`/panel.load_by_sid；index.html 切会话未接 reset。

**最小修复**：在 `replay.js` 的 `load()`/`__load_session_sid` 入口（应用 leveling 之前）单点调用 `HUMAN_DETECT_OVERLAY.reset()`，而非散在各 UI 按钮。同时 reset 内清 `S.hud_extra=""` 并重刷 colorBuf（清残留红点）。
- **验收断言**：
  1. session A 跑 5 track → `__load_session_sid(B)` → B 首帧 track id=1（覆盖 CE6）；
  2. reset 后 replay `set_idx` 再触发 on_frame → track 从 id=1 起且不复用 A 的旧 id；
  3. index.html（panel.load_by_sid）与 human_track.html（sessSel.change + `?sid=`）两条路径**共用** replay.js 入口 reset，无遗漏。
- **可选加固**：给 `S` 加 `session_gen` 计数，`on_frame` 校验 `S.session_gen !== last.gen` 则先 reset——防异步旧帧污染。

## FIX-4（P2，可选）grid_key 负 key 反解 —— 漫水邻域负数正确性

**缺陷**：`gx*4096+gy` 对负 gy 非单射（量程内不碰撞，但 `Math.floor(cur/4096), cur%4096` 反解负 key 错误，负 y 区邻域缺失）。

**最小修复**：key 改字符串 `` `${gx},${gy}` ``（或 `gy` 加偏移常量 `+4096` 保持数值键）。
- 验收：负 y 区两点相邻 cell 能被漫水正确并入同一簇；正 y 区回归不变。
- 影响：仅聚类邻域完整性；不改变簇数量级（负 y 区当前邻域本就不完整）。

---

## 修复与复审的关系
- **必须先做**：FIX-1（关联缺陷隔离）、FIX-2（删除/修正 is_stable 语义失效）、FIX-3（reset 根因）。三者是 P0/P1 与 C 训练前置。
- **FIX-4 可选**：非阻塞，建议与 FIX-1 同轮回归。
- **完成 FIX-1/2/3 + 回归（counterexamples 7 组全转 PASS 方向翻转 + detect_overlay.test.js 全过 + Shadow 复跑不变）后**，方可复审并裁定进入 C 难负样本训练。
- 本轮**不实施**任何 FIX；以上仅为建议稿。
