# R3 跟踪器 / 几何一致性核对 —— 最终权威结论（三次迭代后）

2026-10-11 · writer: CC（只读诊断，无链源改动）。运行器 `sidequests/human_fusion_lab/run_r3_diagnostics.js`。九会话真实驱动数据 2605 帧。本文件历经三轮自我纠错，以下为**最终定论**，替代任何中间草稿。

## 定论（当前 master 代码，逐帧实测）

### 1) geometry(post) 轨迹确认 —— Q01 的"失效"当前已不存在

用 **Q01 完全相同的口径与相同会话规模**（8 个合格会话、**6520** 个带 track_id 候选）：
- **mismatch = 0**（Q01 声称 6436/6520 = 98.7%）。

根因：`detector.js:13-17` 有 Q01 周期的补丁，tick 后把几何决策回写 `candidate.track_confirmed` 并同步受影响 track 的 `human_confirmed`。**当前 master 的 geometry(post) 已是"已修补"状态。** 98.7% 是补丁**之前**的测量。
- 阴性对照：绕过该补丁时检测器在合成例上正确计数，证明 0 是真测量非检测器失效。
- **残余设计债（非活动 bug）**：几何决定仍在 tracker 按 RF 投票**之后**覆盖（`track_semantics:'overridden_by_geometry_posthoc'`）。改成"tracker 前同源投票"属设计改进，当前无失败测试可支撑，**不做无的放矢改动**。

### 2) 重复 ID —— 真实缺陷，最终复现 R5–R8 的 21 次；修复=采用 unique tracker

最终修正诊断（直接读 `diag._candidates` 的真实 fusion 候选）逐帧实测，按模型汇总同帧重复 ID **帧数**：

| 模型（默认 FusionTracker） | 同帧重复 ID 帧数 |
|---|---:|
| rf51_baseline | **21**（与 R5–R8 完全一致，复现） |
| rf51_candidate | 54 |
| xgb69_candidate | 25 |
| **一对一 UniqueTracker（对照）** | **0** |

- 根因（`core/fusion.js:37-77` FusionTracker.tick）：贪婪单绑——每个 fusion 候选各自"找最近活跃轨道绑定"，**无全局一对一**。两质心同落一轨 0.75m 门内时**共享同一 track_id**（阴性对照已强制复现 `FUS_t0_1` 出现两次）。
- 我此前基于 V2 包裹（v2_runtime 强制换 UniqueTracker）报的"默认 0 重复"**不适用于裸默认 tracker**；裸跑下重复 ID 真实存在且量级如上。
- **修复 = 把 FusionTracker 的贪婪单绑改为全局匈牙利一对一赋值**（`unique_tracker.js` 已实现匈牙利式唯一赋值 + 每轨每帧一票 + 失配清票，单元通过；本 runner 实测九会话 dupID 全 0）。**这是用户"修重复 ID"的有效修法，修在 tracker 关联层而非显示层。** 需在 S9 双人 / 遮挡上验证不劣化召回。

### 3) 确认票违反 —— 不存在（我前两轮为诊断器自身 bug）

- 最终以**真实 `FusionTracker.votes`**（取自 `fusion_ctx.tracker.tracks`，非剥离投影 `diag._tracks`）复算：**voteViol = 0**。
- 教训：`diag._tracks`（`engine.js:520`）是只挑字段的投影、**不含 votes**；早前我读它得 `votes=undefined` 误报"确认票大量违反"。FusionTracker 的 3/5/3 投票逻辑本身**自洽正确**。

### 4) ID 闪烁 —— 当前数据 0

- 逐帧 candidate→track_id 连续性检查：全模型全会话 **0 次同 candidate 相邻帧换 ID**。

## 因此修正后的真实优先级

用户交办的"修重复 ID 和确认票"，核实后：
- **确认票**：无需修（自洽）。
- **重复 ID**：机制真实，需**采用 unique tracker 的匈牙利一对一**并在能触发的数据（S9 双人 / 遮挡）上验证。这是唯一实质 tracker 工作。

真正未闭合的大项（按用户顺序）：
1. 逐帧漏检/误检可视化（俯/侧/3D 多视图）。
2. BG/PROPOSAL/CLASSIFIER 漏检归因（R8 已有定性，需互补可视化）。
3. 算法优化（48 正 + 1430 负候选、会话分组冻结无泄漏；目标：S1 原 RF 604 FP、S3 远走 FN65、S6 遮挡 FN）。
4. GT 标注+复核入口、S9 重绑（覆盖率真实见 AUDIT）。
5. 骨架：fusion 已确认人簇→skeleton.py 打通，先躯干可观测性。

## 证据指针
- `run_r3_diagnostics.js`（修正版）、本目录六张截图、`sidequests/human_fusion_lab/results/`。
- 阴性对照命令与输出已在上文执行记录中（FusionTracker 强制共享 ID / 几何补丁绕过）。
- D01/P01 NOT_RUN/BLOCKED；本轮零生产改动、零链源改动。
