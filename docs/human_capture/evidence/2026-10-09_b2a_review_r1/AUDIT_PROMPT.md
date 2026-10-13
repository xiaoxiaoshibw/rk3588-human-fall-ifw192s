# 独立审计任务（只读，禁止改任何文件）

你是独立审计员。审计 LiDAR 人检 HUD 的一次显示层小修。你的结论将被记录，不得迎合。

## 审计对象（只读这 4 个文件）
- `D:/Code/ldiar/pc_apps/human_replay/detect_overlay.js`
- `D:/Code/ldiar/pc_apps/human_replay/detect_overlay.test.js`
- `D:/Code/ldiar/pc_apps/human_replay/human_track.html`
- `D:/Code/ldiar/pc_apps/human_replay/detect_ui.js`

参考（只读）：`D:/Code/ldiar/pc_apps/human_replay/replay.js` 的 `set_idx()`(行 471 附近) 与 `human_pipe_lib.js`（生产链，本次改动不应触碰它）。

## 已知反例结果（供核对，不得轻信请独立复核）
1. CE1: `associate()` 同一帧两个 cluster 可绑同一 track → `age` 同帧两++，`cx/cy/zmax/n` 被后簇覆写。
2. CE2: 因此同帧两簇共享 `track_id`；HUD 的 `_shown_ids` dedup 只掩盖、不改底层共享。
3. CE3: 连续误检的柜子 5 帧 → `miss===0` → `is_stable()`=true → HUD 归「人」。`miss===0` 只证明当前帧关联命中，不证明是真人。
4. CE4: 真人漏 1 帧 → `is_stable`=false → 降「低稳定候选」；回帧立刻升回 → 同一 track 在两组间闪烁。
5. CE5: `reset()` 只清 `last`+sprite，管不到 replay.js 的 rAF；同 session 内 reset 后若 `set_idx` 再触发 `on_frame`，状态会复活。
6. CE6: 跨会话切换 + reset → id 从 1 起（此项验证通过，属「已确认修复」）。
7. CE7: 同屏稳定 track 与间歇 track 能拆开分组。

## 你要回答的 8 个问题（逐条给 CONFIRMED / REFUTED / PARTIAL + 行号依据 + 一句理由）
Q1 同帧多簇绑同一 track 是真实缺陷吗？`age` 重复 + `cx` 覆写是否发生？
Q2 `shown` 的 `_shown_ids` dedup 是根治还是显示层规避？
Q3 `is_stable()(miss===0)` 作为「人 vs 低稳定候选」分组依据，语义是否成立？它能否区分「连续误检的家具」与「真人」？
Q4 真人短暂漏检会导致 HUD 分组闪烁吗？代价可接受吗？
Q5 `reset()` 是否完整覆盖了跨会话污染路径？还有哪些路径能绕过它污染状态？（重点检查 replay.js `set_idx` 是否会被滑块/step/循环/异步在 reset 后再次触发 on_frame）
Q6 两处 UI 调用点(`human_track.html` sessSel.change + btn; `detect_ui.js` btn)是否覆盖了全部用户切会话/重开路径？index.html 是否有人检入口却**没有**接 reset？
Q7 本次 diff 是否触碰了 RF 阈值(0.55)/TRACK_MIN_AGE(3)/TTL(15)/门(1.0m)/z 带/bg_envelope/生产 human_pipe_lib.js？给出逐参数核对。
Q8 你独立发现的、上面反例没覆盖的其它缺陷（最少列 0 条，最多 4 条；每条给行号+触发条件+影响）。

## 输出格式（严格遵守，≤ 800 字正文）
```
VERDICT_OVERLAY_HUD: PASS|FAIL|BLOCKED
VERDICT_RESET: PASS|FAIL|BLOCKED
VERDICT_TRACK_ASSOC: PASS|FAIL|BLOCKED
VERDICT_ALLOW_C: YES|NO|BLOCKED
Q1..Q8: 逐条 CONFIRMED/REFUTED/PARTIAL + 依据
MINIMAL_FIX: 对确认的生产级缺陷, 给最小修复建议(伪码即可, 不实施)
NEW_DEFECTS: 逐条或 「none」
```
不要修改、重写、润色任何源码或测试。不要运行会破坏环境状态的命令。只读与推理。
