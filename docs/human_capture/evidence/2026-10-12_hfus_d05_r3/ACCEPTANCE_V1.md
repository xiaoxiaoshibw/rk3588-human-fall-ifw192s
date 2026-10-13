# HFUS-D05-R03 唯一验收 v1（2026-10-12，实验前登记）

当前用户直接授权 D05 持续离线返工；不是 D05a/D05b，不启动 D06/D07。主控唯一 writer；只读代理和指定 OpenCode 不写文件。实际读取 ponytail：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。新算法仅 `sidequests/human_fusion_lab_next/d05/r03/`，输出仅本新 evidence。起始全树15305文件 SHA 见 BASELINE_BEFORE.json；master/026e06303f60ed1bbe4ddc4d037836db68da6d27，非原子冻结。禁止 Git 写操作/生产/部署/采集/驱动/网络/ML；模型/GT/captures/历史证据只读。

## H2 单因素：候选分类宽水平拒绝

R02 split 的真实固定候选证据：家具 f0/f40 宽水平候选 p≈.868、radius≈.67、upcos≈.16；walkstop f75 真人 TP radius≈.478、upcos≈.975，不能单独 radius>.45 拒绝。仅当真实69D特征中 sqrt(2*(max(0,x26)+max(0,x29)))>.45 且 x39<.5，分类有效分数设0；原RF原始分数完整保留。x26/29 是 XY 协方差，x39 是最大主轴 abs(z)。阈值取原几何配置；不调模型、不读GT、不新增训练。A06和R02 split参数不变。候选原始点集的反事实判定先跑，再完整顺序管线实跑；拒绝可能通过跟踪反馈改变后续候选，不能把固定候选收益当全链成绩。

预期只能减少宽水平家具接受，直立碎片 f40 p≈.96 仍失败；遮挡截断人体可能回退。这是假设，失败时保留结果并停止扩大。S9 INVALID_BINDING，缺独立人工负例，晋级BLOCKED。观察是否严格真人TP无回退，不降低coverage>=.5/purity>=.8/legacy距离.75或p95<50ms。

| ID | 冻结要求 |
|---|---|
| R03-01 | 起止 branch/HEAD/status、tracked/untracked/ignored SHA，无法读/变化/越界单列 |
| R03-02 | 固定R02候选69D、原模型分数复算与拒绝依据；raw/effective/原因分列，GT不进入推理 |
| R03-03 | 唯一因素分类拒绝，R02 split其余参数与原始模型不变；源码、输入、GT、模型 SHA与实际exit |
| R03-04 | 九会话完整顺序ledger/SUMMARY，同口径D04/base/A06/R02split/R03gate比较，每会话strict与legacy、各来源分账；每个正式场景strict observed TP不减，家具已标纯度>=.8诊断接受减少。资格不足晋级BLOCKED；任何回退FAIL并披露 |
| R03-05 | 全已标失败逐层归因、候选删除/保留与跟踪反馈、observed/coast/ghost/ID指标；未标与S9 UNKNOWN，连续身份缺人工时BLOCKED |
| R03-06 | 真实三同步Demo，九会话和播放/步进/seek/重置/快捷跳转；原始分数与拒绝原因、实际点与净恢复、SHA校验、浏览器截图及同步实查 |
| R03-07 | 无竞争串行纯算法计时，预热5、读/render/instrumentation分开；原p95<50ms，各场景实报，板端NOT_RUN |
| R03-08 | 指定OpenCode opencode-go/deepseek-v4.1-flash只读独审，完整指令、实际模型与exit、缺陷处理记录 |
| R03-09 | 源码SHA、完整账本/片段索引、最小人工复核包、追加return；工程/算法/GT/生产独立裁定，不自行ACCEPTED |

原D05缺件和失败保留，R02最终报告继续按R02验收表收口；当前新轮唯一表为本v1。组合R03必须自身完整实跑，不拼接最优帧。
