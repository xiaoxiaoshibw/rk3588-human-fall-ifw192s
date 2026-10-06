## 2026-10-05 GL-D R1 / OpenCode / SUBMITTED

# GL-D R1 回传（时间稳定/六状态/安全保持；实现者自述）

状态 SUBMITTED。按用户「一次性做下去」指示，自验后直接进入 GL-E。指定独审待批量进行。

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：GL-D（AGL-D-01..06）/ R1 / OpenCode CLI（模型自报 opencode-go/deepseek-v4.1-flash）/ 2026-10-05。
- 验收表：`tickets/GL-D_adaptive_temporal.md` v1，SHA256=2a7bb9c8ab2cdc2dcbebd44ebbe36ccd114e4064e87e34901272bbf03e3cc37b。
- 起始 branch/HEAD：master / 开工时 8676bb479…；实施期间出现**外部提交** 0d5ab424…（非本 writer；未执行任何 git 写命令）；提交时 HEAD=0d5ab42。
- ponytail 路径：`C:\Users\30680\.config\opencode\skills\ponytail`（复用 digest/display_rotation/限速原语；无新依赖；两小模块+单测试）。
- 证据：`evidence/2026-10-05_agl_d_r1/`。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| D 自检① | BAD 清空 pending 后，ACQUIRING/RECOVERING 重进 append 未回填 pending_start_s → duration 计算 TypeError | 采集/恢复连续窗口 | `controller.py` 两处 append 后回填 start（若 None） | 正常路径行为不变；坏帧后窗口重建从当前帧重新计时 |
| D 自检②（测试构造） | 外部 epoch 变更后测试帧未同步 epoch；时间戳回跳 | 测试时间线 | 测试修正（控制器正确拒绝并记 GL_TIME_INVALID/GL_CONFIG_CHANGED，未放宽产品语义） | 产品代码不变 |

其余为规划内新增；操作矩阵见 00_diag.md。

## 实际变更

| 文件 | 用途 | SHA256 |
|---|---|---|
| `core/adaptive_ground/temporal.py` | 新增：配置/median/EMA/逐轴+组合角+rate 限速/offset 限速 | 59b34139c3c7707c9f438eb7ec7c5098242f35c234fe4afae322b1cdbdbb9941 |
| `core/adaptive_ground/controller.py` | 新增：六状态事务/last_good/age/freeze/事件 | db3d65503b9c2cc608796916aa9200b18307c9c4e9c7e717b6b904c18ab31960 |
| `tests/test_agl_d_controller.py` | 新增 7 用例 | bb8a2d9a083c05da19e9136c6b68dfc08966f99b47348b7e309c037c255fffc3 |

## 逐条验收（自验）

| ID | 结果 | 证据要点 |
|---|---|---|
| AGL-D-01 | PASS | INIT 无 identity；前 9 帧无 applied；第 10 帧+时长满足才 STABLE 原子提交（rev1）；BAD 打断 pending；dt=0.05 下 10 帧不满 0.8s 不提交、第 17 帧提交 |
| AGL-D-02 | PASS | 只喂 validated；BAD 不污染；30 帧追踪步长 ≤ rate×dt(0.1)；limit_step 独立 oracle（dt .05→≤.05；dt .3→≤.25）；offset 步 ≤ .002 且移动 |
| AGL-D-03 | PASS | BAD/8° 跳变/offset 突变 → HOLD 且 last_good/revision 逐位不变；无 last_good 的 BAD 不伪造；tick age>2s → fresh/eligible=false、数值保持；age 内 fresh=true |
| AGL-D-04 | PASS | HOLD→RECOVERING 首帧不提交、第 N−1 不提交、第 10 帧+时长提交（rev2）；bad/gap/duplicate 均重置为 HOLD；+1.5° 进 pending_rebase 窗口，确认后限速追踪到 <0.02°（每步≤0.1）；+6° 直接 GL_ANGLE_JUMP，不被 EMA 吞 |
| AGL-D-05 | PASS | epoch 变更 → INIT、controller_epoch+1、revision 单调保留、旧 last_good 不跨版本；freeze 锁存期间输入不下发（GL_MANUAL_FREEZE）、unfreeze→RECOVERING 再经窗口回 STABLE；无 last_good 的 unfreeze→INIT |
| AGL-D-06 | PASS | 每事件字段集固定含 frame/time/old-new/reason/revision/epoch/action；tick 无伪造帧（frame=None+tick_index）；决策与事件 JSON 安全；双控制器同时间线逐位重放一致 |
| AGL-D-S01 | 流程完成（自验）；独审 NOT_RUN | 配置 13 负例全拒（含 alias 相等）；stdlib+NumPy；未引入 Kalman/IRLS |

回归：专项 7/OK/exit0；全量 483/OK/exit0（476+7）；冻结 10 blob=基线。

## 未闭合与限制

- 指定独审待批量；不伪报。
- 旧 GroundMonitor 的 recalibration latch 不在本模块，D 不接触、不自动清（保持既有语义）。
- 阈值（N/α/步长/rate/age）为测试显式配置（DRAFT）；GL-F 冻结 profile。
- pending_rebase 窗口语义按「确认后限速追踪」实现（窗口 = recover_frames + 最短时长）；2° 与 5° 之间同样要求窗口确认，≥5° 拒绝。
- 下一步：GL-E（transform/离线应用）由本轮连续开发继续。

## 交给复审

- 证据：00_baseline、00_diag、10_test_agl_d_log、11_regression_after_d、30_scope_check。
- 源码差异与 SHA：见上表；外部提交情况见 30。
