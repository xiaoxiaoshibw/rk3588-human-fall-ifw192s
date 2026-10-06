# GL-D R1 实现前集中诊断（摘要）

来源：契约 §6、计划 §5/§8、GL-D 工单（唯一表 v1，SHA 2a7bb9c8…）。范围：`temporal.py`（纯数值滤波）+ `controller.py`（六状态事务）+ 集中检查；不改 A/B/C 语义。

## 状态与判据

| 状态 | 进入/行为 |
|---|---|
| INIT | 无 last_good；首个合法帧 → ACQUIRING；BAD 不造 transform |
| ACQUIRING | 连续 N_acquire distinct GOOD + 最短 cohort 时长 → 原子提交（median）→ STABLE；`GL_ACQUIRING`；jump≥5° 重置连续 |
| STABLE | GOOD：≤max_step 直接限速更新；(max_step, raw_jump) 进入 pending_rebase 窗口（N_recover+时长确认后限速追踪）；≥5°→GL_ANGLE_JUMP→HOLD；|Δd|≥.05→GL_OFFSET_JUMP→HOLD |
| DEGRADED | 可信降级共识：默认只保持；update_candidate&degraded_ema_alpha 慢更新（仍限速）；GOOD 恢复走 RECOVERING 窗口 |
| HOLD | BAD/低分/跳变/时间无效/gap/重复 → R/t 与 revision 逐位不变；首个 GOOD → RECOVERING（不提交） |
| RECOVERING | N_recover distinct GOOD + 时长 → 限速提交 → STABLE；第 1/N−1 帧不得应用；bad/gap/重复 → HOLD |
| 任意 | epoch 不兼容 → INIT（清 pending/last_good，controller_epoch+1）；manual freeze 锁存，unfreeze 仍走恢复 |

## 时间/滤波

- dt 来自受审同流 source stamp（≤0 拒、>max_gap 断流）；rate = min(逐轴步, 组合角步, rate×dt)；offset 独立步/速率；EMA 仅吃 validated 候选；bad/gap/重复不进窗口、不污染 EMA。
- age：on_tick 不造帧（frame=None + tick_index）；超 max_hold_age_s → fresh/eligible=false，显示数值保持。

## 操作矩阵映射（工单）

| 组合 | 行为 | 测试 |
|---|---|---|
| 六态 × GOOD/DEGRADED/BAD × last_good 有/无 | 见状态表；无 last_good 不伪 identity | D-01/03/05 |
| no-input tick/重复/乱序/dt0/gap | 拒/清 pending/HOLD；tick 不造帧 | D-03/04/06 |
| reload/epoch/caller mutation | epoch 变更 → INIT；结构性错误 raise；无半应用 | D-05 |
| 单尖峰/持续小变化/5–20° | 单尖峰→HOLD；≤2° 窗口确认后限速追踪；≥5° jump→HOLD（不被 EMA 吞） | D-03/04 |
| bad 穿插/恢复窗口 | 第 1/N−1 不应用、bad/gap/dup 重置 | D-04 |
| freeze/disable（lock） | 锁存、不下发更新；unfreeze→恢复 | D-05 |
| 事件/可重放 | 每事件含 frame/time/old-new/reason/IDs/action；确定性重放 | D-06 |

## 保留/不做

- 不接触旧 GroundMonitor latch（其状态不在本模块，D 不自动清）；不实现 transform 应用（E）、不接 runtime；没有有效 dt 不猜 FPS。
