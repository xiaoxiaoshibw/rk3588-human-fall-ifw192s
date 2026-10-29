# HFUS-AI-GT-PROTOCOL-02 回传

## 2026-10-18 r1 开工

- 用户授权：本聊天“开始开发opencode审核”，实施上轮选项3，不接真实会话。
- 唯一writer：Codex本会话；实际模型标识未从运行时独立取得，不伪报。审核OpenCode指定模型只读。
- 策略：ENGINEERING（定义/渲染辅助/评分与溯源契约），标注改善无证据，NOT_RUN。
- 实际ponytail路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md（已读）。
- 唯一验收：../evidence/2026-10-18_hfus_ai_gt_protocol_v2_r1/ACCEPTANCE_V1.md；状态进行中。
- 起始branch/HEAD/用户原差异与修改前索引：同目录PREWRITE_BASELINE.json；全树扫描原件BASELINE_BEFORE.json与先冻结值合成BASELINE_EFFECTIVE_BEFORE.json，方法在最终范围记录说明。
- 源码计划仅新tools/ai_gt/ai_gt_v2.py、test_ai_gt_v2.py、protocol_v2.json；旧v1保持。

## 2026-10-18 r1 交付（SUBMITTED；范围核验BLOCKED）

- 执行者：Codex本会话唯一writer；OpenCode仅只读审核，实际模型从session导出核验为opencode-go/deepseek-v4.1-flash。
- 策略ENGINEERING；实际ponytail路径C:/Users/30680/.codex/skills/ponytail/SKILL.md，已读取。
- 唯一验收v1：../evidence/2026-10-18_hfus_ai_gt_protocol_v2_r1/ACCEPTANCE_V1.md；SHA256 `7e53a2ca469d14313eb3fe311600e06951e9c1b2fa5835bb60d8dd7abc6bb87b`。
- 起始master/HEAD `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`，用户原差异见PREWRITE_BASELINE.json；完整库存与组合方法见BASELINE_BEFORE/AFTER、BASELINE_EFFECTIVE_BEFORE.json。Git HEAD不变，无Git写。

### 集中诊断、实际变更与SHA

根因是视觉中点、三维均值投影与二维投影后均值混用；新v2明确mean(project(X_i))，按有限、相机前方、画面内源行等权，重叠行分别计数。v1原定义、源码和证据保留；不将改定义宣称为标注改善。
复用v1投影/射线/统计与合成几何；新入口仅合成render/score。网格统一25px、100px刻度、固定光心十字；目标坐标不参与辅助线。半开距离分档、漏检/分母单列、空档null；30cm观测值不是上限。新输出拒覆盖、拒data/captures，评分先核验SHA与输入再写目录。

| 本轮新文件 | 用途 | SHA256 |
|---|---|---|
| tools/ai_gt/ai_gt_v2.py | v2合成入口 | de0c4d8de89243b7959dd2518f2057b5dee6e17160b9a8e66dee00a71e5b1046 |
| tools/ai_gt/test_ai_gt_v2.py | 契约与边界检查 | 1e4831ea3f29ac1d9fef048de6fe20c4f9869ef7ef905a2b13d4ee5bfb204d9c |
| tools/ai_gt/protocol_v2.json | 冻结运行参数，与证据副本字节一致 | a093daf9ef1d6307fbc2764dcd84b768c9b3d04976f3b012106ee199d1f31ae1 |

文档/协议/运行日志只写本轮新证据目录；WORKFLOW前置、REVIEW_LOG末尾追加，旧字节保留。源文件与用户原差异区分：上述三件在PREWRITE记录均为不存在；旧v1的31件MANIFEST逐件SHA相同。全体产物最终SHA见MANIFEST.json。

### 逐条验收（作者自验）

| ID | 层级/结果 | 命令、检查与证据 |
|---|---|---|
| V2-01 | offline BLOCKED（全树范围） | v1/索引原件PASS；SCOPE_FINAL/SCOPE_DRIFT记录457个tmp_gl_diag范围外路径消失，原因待核实 |
| V2-02 | synthetic PASS，exit0 | TEST_V2.log；CODEX_CHECK.json相机坐标独立手算；投影/非法/不可见/密度 |
| V2-03 | synthetic PASS，exit0 | 近场实图检查；REPRODUCTION_CHECK.json独立CLI的24图逐字节一致 |
| V2-04 | synthetic PASS，exit0/负例2 | 24/18人/6空场/6近家具/每档6人；REJECT_HOLDOUT_RUN拒绝保留种子 |
| V2-05 | synthetic PASS，exit0 | oracle18TP/6TN、max0px；注入5px回读5px；FN/FP与全FN边界见TEST_V2.log |
| V2-06 | synthetic PASS，exit0 | 半开边界、n_person/n_tp、空档null；协议和报告明确不外推 |
| V2-07 | synthetic PASS，exit0 | suite/source/protocol/picks绑定；未知/重复/缺项/半null/NaN/越界拒绝；低优先级限制见REVIEW_DISPOSITION |
| V2-08 | offline PASS，exit0/负例2 | TEST_V1.log 11项、TEST_V2.log 8项均-B -W error；输出保护/覆盖拒绝 |
| V2-09 | static PASS，exit0 | OPENCODE_REVIEW_STATUS：指定模型/任务与技能读取/权限/源码不变，71次只读调用；独立执行NOT_RUN |
| V2-10 | offline BLOCKED（全树范围） | 全部记录已提交，但457范围外变化原因未核实；不能报零范围差异 |

原始失败保留：TEST_V2_INITIAL为画外点夹具期望错误，换为画内点后通过；CONTRACT_INITIAL_ERROR为Windows中文stderr解码问题，harness改-X utf8并续跑。之后新增--out新目录完整重跑，reproduction_r2全部命令exit符合预期；历史日志不改。

### 审核、限制与未闭合

OpenCode正式审核578.14s、exit0、0阻断/0FAIL；实际opencode-go/deepseek-v4.1-flash，read/glob/grep共71调用，技能路径/请求读取/审核前后源码SHA核验通过。9项非阻断观察逐项处理：F4复现入口、F8跨进程24图、F9解析检查已补；F1常量交叉校验/F2额外文件检查列后续，F3 kind只作输入声明、GT资格恒false；首次超时原始传输缺失如实记录。审核后生产源码无变化。

两份全树库存分别191371/191822件，均0读取错误、0读取中变动。它们重叠扫描：名为AFTER的并行库存较早完成，含tmp_gl_diag的457件；名为BEFORE的串行库存较晚完成，和当前文件系统均无这些路径。无其它范围外差异。归因未核实，本轮未执行删除/移动/清理，也未恢复这些文件；已询问用户是否为并行清理。解除条件：核实并记录该变化来源，保留原始清单。

模型盲标效果、保留种子、交叉模型复标、真实会话label、purity/recall、正式GT、设备/物理全部NOT_RUN。合成oracle/注入误差不冒充盲标；标注改善没有结论。未改数据/GT/旧v1证据、未部署/采集/训练/驱动网络，不推进S08/S09。

### 独立复审交接

当前验收与逐ID见ACCEPTANCE_V1.md/RESULTS.json；根因及操作矩阵00_DIAG.md；完整审核及原始传输OPENCODE_REVIEW.md/.jsonl/_EXPORT.json/_STATUS.json；源码与输入SHA在AUTHOR_CHECK、CODEX_CHECK与MANIFEST；范围457件清单在SCOPE_DRIFT。当前为SUBMITTED（范围BLOCKED），非ACCEPTED；不自动下一阶段。

## 2026-10-18 r2 用户确认范围来源（SUBMITTED；范围阻塞解除）

- 用户本聊天直接答复“是，已知的并行清理”；只解释tmp_gl_diag/457件差异来源，确认原文见../evidence/2026-10-18_hfus_ai_gt_protocol_v2_r2/SCOPE_RESOLUTION.json。
- 策略ENGINEERING，仅来源/索引/状态收口；唯一writer Codex；实际已读ponytail路径C:/Users/30680/.codex/skills/ponytail/SKILL.md。
- 唯一验收仍r1/ACCEPTANCE_V1.md，SHA `7e53a2ca469d14313eb3fe311600e06951e9c1b2fa5835bb60d8dd7abc6bb87b`。当前逐ID与报告改由r2/RESULTS.json、r2/REPORT.md承接；r1结果保留为历史，不改判据/旧证据。
- 起始branch/HEAD、三个可追加文档修改前原文/SHA、沿用的全树基线、r1的145件不可变条目逐件复核见r2/BASELINE.json。生产源码SHA未变，r1记录的测试/复现/OpenCode只读审核继续适用，本轮未重跑数值实验。

| ID | 当前结果 | 依据 |
|---|---|---|
| V2-01 | PASS | r1原件/源码保存证据 + r2用户确认457件为已知并行清理 |
| V2-02 | PASS | 沿用r1投影/输入边界/独立解析检查，源码SHA相同 |
| V2-03 | PASS | 沿用r1中性渲染与24图跨进程一致性 |
| V2-04 | PASS | 沿用r1套件计数/保留种子拒绝记录 |
| V2-05 | PASS | 沿用r1 oracle/5px/混淆矩阵契约记录 |
| V2-06 | PASS | 沿用r1半开分档/分母/空档/使用边界 |
| V2-07 | PASS | 沿用r1绑定/非法输入检查及非阻断限制 |
| V2-08 | PASS | 沿用r1保护检查与8项v2/11项v1回归 |
| V2-09 | PASS | 沿用r1实际指定模型/只读审核/源码SHA核验；独立执行NOT_RUN |
| V2-10 | PASS | r2来源确认、当前结果、报告、索引回传与MANIFEST齐全；来源未明阻塞解除 |

实际观察差异仍457件，不称零范围差异；未解释范围差异0。原始快照、SCOPE_FINAL的pass=false、BLOCKED结果、清单和审核原字节保留。本轮没有恢复、删除、移动文件或改生产源码、数据、GT、旧证据，没有Git写/采集部署训练或下一阶段操作。
模型盲标/保留集/跨模型/真实会话/正式GT/设备物理仍NOT_RUN；来源确认不增加效果结论或自动授权下一阶段。当前SUBMITTED、非ACCEPTED。最终SHA与复核见r2/MANIFEST.json、r2/CHECK.json。
