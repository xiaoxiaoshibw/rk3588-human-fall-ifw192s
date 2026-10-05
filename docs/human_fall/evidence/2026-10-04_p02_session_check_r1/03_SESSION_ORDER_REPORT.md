# 三个 session 的 A/B/C 顺序核验

结论：**HIGH-CONFIDENCE INFERENCE — 点云支持 `202456 → 203135 → 203349` 分别对应 A baseline / B 扰动 / C 恢复。** 元数据没有操作标签，因此数据一致性与操作者现场标签分开。用户当前消息原文在00记录；没有把其中“是否”自动改写成明确现场肯定。

## Claim / Evidence / Alternative / Verdict

Claim：中间会话有局部低位点遮挡，第三会话恢复第一会话的分布。

Evidence：只读全部91/113/102帧，在预定历史显示变换Ry(+26°)、tz1.34和旧v11 XY区域X[1.9,2.4]、Y[-.5,.5]、固定Z[-.1,.1]窗口，得到：

| session / proposed state | mean points/frame | median | p5 / p95 | std |
|---|---:|---:|---|---:|
| 202456 / A | 483.076923 | 483 | 478 / 489 | 3.156124 |
| 203135 / B | 404.814159 | 405 | 400 / 409 | 2.845735 |
| 203349 / C | 482.725490 | 483 | 478 / 488 | 3.328890 |

B-A平均-78.262764点/帧，C-A仅-0.351433点/帧。变化明显大于帧内波动。注意这不是用户原实验的窄箱ROI，不能强求复现257→154→257，也不冒称原#3源行绑定已闭合。

该旧ROI中固定Z[.15,.35]窗口均约63–64点/帧，**没有明确新增抬高点**。因此第一窗口单独只证明中间减少/首尾恢复，不能单独声称箱顶+23cm已复现。

随后独立保存较宽固定视域5cm voxel的全部帧均值对照02，逐voxel比较B与(A+C)/2。在周边X[1.7,2.6]、Y[-.6,.6]中，低位voxel存在A/C约5点/帧而B=0；新增voxel如显示坐标(1.725,-.175,.225)m在A/C为0、B约1.956点/帧，另有Z=.075的侧面变化。扰动跨过旧ROI的X=1.9边界，因此只在旧ROI内找箱顶不充分。

Alternative：场景其他物体也有改变；较宽域某些高voxel在B/C同时存在而A没有。02的混合变化质心及其高度差不是箱顶高度测量，不拿它替代用户原23cm证据。相同遮挡/恢复模式也可由其他物体产生；仅元数据不能得知操作者的动作名称。

Verdict：数据强力支持用户提示中顺序，未发现反序证据。P02-A此前用户现场确认保持VERIFIED，本次核验作为额外数据一致性证据。实验精确ROI/source-row身份仍UNKNOWN，P02-C未因此自动PASS。

## 范围 / 验证

- 未修改生产源码/配置/原capture/旧证据；只本新目录两个NumPy+stdlib诊断脚本与结果，按ponytail最小范围。
- 两命令 `python -B -W error check_sessions.py`、`python -B -W error check_voxel_changes.py` 都exit0；01/02为独占新文件，禁止覆盖重跑。
- 04包含三个frame0的独立struct.unpack逐点标量检查，与NumPy stride解码/旋转/窗口点数完全匹配；三个bin SHA首尾一致，既有fall源码SHA无漂移。
- 环境Python3.12.10/NumPy1.26.4；这是本地离线核验，不是板端环境验收或OpenCode独审。
- 技能：C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md；C:/Users/30680/.codex/skills/ponytail/SKILL.md。
- 初次取git-status默认GBK产生UnicodeDecodeError，显式UTF8修正后生成00；无原数据写入。脚本ROOT在运行前修正parents索引，未产生错误分析文件。

P02-C仍BLOCKED：需把实际实验#3 ROI与A/C源行绑定。P02-D/E NOT_RUN；未算外参、未设备/采集/部署，P1-01仍NO。没有重新设计或要求重做任何物理实验。
