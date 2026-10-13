# HUMAN-FUSION-DIAG 回传

## R1 · 2026-10-11 · Codex

### 本轮信息

- 工单：HUMAN-FUSION-DIAG R1，只读审计/联网研究/隔离离线验证。
- 唯一验收表：[ACCEPTANCE v1](../evidence/2026-10-11_human_fusion_diagnosis_r1/ACCEPTANCE.md)，SHA随最后复核记录。
- 状态：**SUBMITTED**；不自行宣布整体软件PASS、生产识别PASS或工单ACCEPTED。
- 起始：master / 026e06303f60ed1bbe4ddc4d037836db68da6d27；故意dirty，含untracked的9588路径基线，结束漂移另记录。
- 实际执行：Windows Python3.12 `-B -W error` / Node；冻结研究副本；RF51、XGB69两次S6前缀，XGB69+Unique三会话单变量A/B。未执行Claude/OpenCode/子agent派工。
- ponytail实际路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`；paper-lookup实际路径：`C:/Users/30680/.codex/skills/scientific-toolkit-skill/references/scientific-skills/paper-lookup/SKILL.md`。

### 集中诊断与根因覆盖

| ID | 根因/入口 | 实际处理 | 保留行为与范围 |
|---|---|---|---|
| A02/A06 | 有资格数据覆盖不足、heldout无负例、早期负向量复制跨fold | 直接meta/bin/GT/源码核验，列真实覆盖与评测契约 | UNKNOWN不变负例；不修改GT/训练 |
| A03 | A/B共享缺参考硬删除、点门/连通性、confirmation反馈retention | 冻结副本逐点阶段probe；缺参考全部放行反事实 | 原生产链不改；FAIL保留，不集成 |
| A04/A07 | 历史局部成果被外推、研究与主链版本差、tracker/显示契约 | 阅读实际源/日志/截图，历史V2输出重算 | 不回填旧PASS/FAIL；不称本轮浏览器通过 |
| A05/A06 | 候选/语义/运动/姿态任务混用 | 作者论文/实际源码联网，列兼容边界与三路线 | 没有跑外部模型/数据；CPU不替代board |

### 实际变更

新建 `docs/human_capture/evidence/2026-10-11_human_fusion_diagnosis_r1/` 的报告、任务书、研究下载、基线、诊断脚本/JSON/日志及18依赖副本；新增本回传。变更只属本轮新审计产物；生产/当前GT/captures/背景/模型/历史证据无本轮编辑。副本中反事实改动仅 `engine_keep_unknown.js` 及其专用入口，不替换主链。

### 逐条验收（自验，不等于系统验收）

| ID | 方式/证据 | 结果 |
|---|---|---|
| A01 | tracked+untracked SHA before/after、单独input/copy核验 | 结束核验待填；本轮新增范围已明确 |
| A02 | data_audit.py / data_audit.json / candidate_data_audit.json / person_geometry.json | **PASS** 调查项，exit0；814/2605 qualified、510 PERSON；S9资格BLOCKED、人工语义充分性UNKNOWN |
| A03 | `node .../s6_stage_probe.js` / JSON/log，476 ticks | **PASS** 定位项，exit0；并非修复PASS |
| A03扩展 | `node .../missing_reference_ab.js` / JSON/log，1600 ticks | 执行与原基线一致性 **PASS** exit0；全放行算法 **FAIL**，S1trackFP740、S6candidate无净召回增益 |
| A04 | REPORT第7节、实际历史源/日志/裁定 | **PASS** 调查项，分已解决/部分/尚未/未知，保留历史纠正和失败 |
| A05 | web检索/作者源码；research_fetch.py exit0、Crossref、research_supplement r2 exit0 | **PASS** 调查项；原supplement exit1与错误DOIlookup保留，未冒充外部复现 |
| A06 | REPORT第1/9/10节、CLAUDE_TASKBOOK.md | **PASS**，五根因/三路线/五量化实验/任务书；未来实验未执行 |
| A07 | actual runtime/Unique/engine、两张真实旧截图、historical_v2_recalculation.json | **PASS** 调查项；历史18记录重算≠新浏览器测试，S9/pose仍UNKNOWN |
| D01 | user明确禁止新采集/部署；本轮无此操作 | **NOT_RUN** |
| G01 | 独立negative/人物场景、连续身份、真实姿态/跌倒数据不足 | **BLOCKED / UNKNOWN**，不能据调查通过宣布可靠识别 |

命令均从repo root在新目录运行；详细实现/路径/日志/SHA见 [完整报告](../evidence/2026-10-11_human_fusion_diagnosis_r1/REPORT.md) 与 [完整性记录](../evidence/2026-10-11_human_fusion_diagnosis_r1/INTEGRITY.md)。未修改生产代码，未重复跑与本轮诊断无关的全部旧测试。

### 未闭合与交付

S6缺参考keys的构图/量化/物理来源未知；全放行新增漏检机制未单独归因；新负例审核、S9实际身份GT、长静止连续GT、陌生家具/人物泛化、关节/跌倒/ADL、board性能与物理结论均未闭合。下一步应按任务书先做候选账本/数据审核包，再做三态参考与稀疏候选，XGB控制变量保留；任何生产接入、部署、采集、HF里程碑由另一个当前指令授权。

交给独立复审的材料：唯一ACCEPTANCE v1、REPORT、全部新probe/A/B日志、snapshot/input/baseline SHA、研究manifest、具体Claude任务。当前状态SUBMITTED，等待独立复审；不启动后续开发。

### R1 结束核验与并行新增证据补充（同一验收表v1）

- 验收表SHA256：`38aac3cf33124fa69777c442d3a0bff5d1cb257a0f192aed5584c2cbfddbb94c`。
- A01：**整体BLOCKED**，工作期间26已有路径内容变化、2元数据变化、56新增（1为本回传、55为其他外部产物）；HEAD不变。本审计没有改这些文件；36输入和18隔离副本/对应live源SHA均不变，输入保护自验PASS。
- A04/A07补充：只读核最新V3/骨架源+JSON，18份V2终端计数无漂移；报告第12节分版，不把B图层保留率当B全链修复。V3文档GT分母、f128归因与实际JSON存在冲突；归因脚本RF/tracker占位、GT orphan属oracle，不能用作终端验收。
- 新执行 `python -B -W error .../late_readonly_review.py` exit0：859条已知固定候选PointNet中心化/未中心化推理，恢复正确test58/stress39，定位V3遗漏预处理；608条B家具XGB复评FP595/TN13。无训练、生产修复或外部模型运行。
- 后段输入33份稳定快照：[late_snapshot_manifest.json](../evidence/2026-10-11_human_fusion_diagnosis_r1/late_snapshot_manifest.json)，详细结果 [late_review.json](../evidence/2026-10-11_human_fusion_diagnosis_r1/late_review.json)。这使数据/候选域与评测契约根因更强，G01依旧BLOCKED/UNKNOWN，D01依旧NOT_RUN。
- A02–A07调查交付仍PASS（自验）；缺陷修复/可靠识别未完成；SUBMITTED，不自行ACCEPTED。任务书已补充“先修V3评测/统计、真正接B隔离链、加B家具压力”的下一步。

最终文档自验：`python -B -W error .../final_document_check.py` exit0，126个本地链接有效、51个冻结副本不变。[记录](../evidence/2026-10-11_human_fusion_diagnosis_r1/final_document_check.json)。完成版REPORT SHA256：`94196f0f007d9b24414c165eb7527ba4fc8e767faf8c5de1c9d08c935078760e`；ACCEPTANCE v1 SHA不变。最终A01=BLOCKED（外部漂移），A02–A07=PASS（调查自验），D01=NOT_RUN，G01=BLOCKED/UNKNOWN。交付只读调查与离线证据，不是可靠识别验收。
