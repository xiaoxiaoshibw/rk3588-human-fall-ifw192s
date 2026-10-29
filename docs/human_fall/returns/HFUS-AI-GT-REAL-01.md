
## 2026-10-18 HFUS-AI-GT-REAL-01 / r1 本轮信息

- 执行者：Codex唯一writer；本机PowerShell/Python3.12离线。ENGINEERING工具适配+RESEARCH真实效果诊断；研究完整性和证据保留优先。
- 实际会话/模型：本会话Codex，供应端精确版本未独立核验；本轮未作为标注者，实际盲标/跨模型调用者为无，不以自报身份填真值。
- 状态：交付SUBMITTED，真实点级效果BLOCKED，非ACCEPTED；设备/物理/独立复审NOT_RUN。逐ID不等于整体软件或人体效果通过。
- 唯一验收：[ACCEPTANCE_V1.md](../evidence/2026-10-18_hfus_ai_gt_real_01_r1/ACCEPTANCE_V1.md)，v1，SHA 83eb1b1edef57fdea2afb24d5ca234873d36ea9321b6bcae08cd689ce0fcc241。
- 起始branch master / HEAD c9c4ee421cb0c8a3e4590b8f5730828b093c759a；脏树含未跟踪文件全部保留。190576文件、67,046,806,009字节SHA基线见BASELINE.json；363相关绑定见FREEZE.json；旧S07/S07F的159/105清单一致。
- ponytail实际读取路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）。scientific-toolkit及matplotlib参考也已读取，路径见PROTOCOL_V1.md。
- 新证据：[本轮目录](../evidence/2026-10-18_hfus_ai_gt_real_01_r1/README.md)；输入/源码/产物SHA见INPUT_BINDINGS.json、FREEZE.json、MANIFEST.json；最终封存FINAL_SEAL.json。

## 集中诊断与根因覆盖

|缺陷/ID|根因或缺口|入口/状态转换|修复位置|保留行为|
|---|---|---|---|---|
|RG02–05|旧工具仅二维/单源行目标，无成员/覆盖/点级包络|点级正式GT准入BLOCKED，未调用模型|CAPABILITY_GAP.md给补充方案，未改旧工具协议|不把中心换点标签，不填模拟GT|
|RG06|连接145测量/0标定；轻晃极值横向符号锚切换|f340→341主轴dot0.999683，横向dot−0.999386，A/B源行支撑随符号交换|仅证据内源行诊断，无算法修复|冻结门、动作、失败窗口、区域非关节|
|RG01/08|故意保留的脏树及旧封存须保护|全基线SHA、结束范围检查、冻结输入再SHA|新证据和允许文档追加|无清理恢复、Git写、数据GT写|

## 实际变更

|文件/范围|用途与修改|与用户原差异区分|源码SHA|
|---|---|---|---|
|新evidence下diagnose.py / test_diagnose.py|复用只读Source/冻结ledger，输出诊断与边界检查，不运行抽取器|全新文件|FREEZE.json、MANIFEST.json|
|orientation_diagnostic.py|预注册极值的基向量/源行机制；不输出新候选|全新文件，运行前补充登记|ORIENTATION_REGISTRATION.json|
|协议/验收/报告/材料/日志/清单/复现脚本|冻结范围、UNKNOWN、全帧非语义诊断及交付|全新目录|MANIFEST.json|
|WORKFLOW.md / 本return|前置新索引 / 末尾追加|旧原文字节保留|SCOPE_FINAL.json|

RAW/innolidar米、device相对秒；0-based local/global/28-byte身份映射。仅cap_20261018_110029的S07F绑定，另一会话排除。阶段为用户近似提示，不当完整动作GT；新中性图只作准备，投影视口与覆盖限制见RENDER_QA.md。

## 逐条验收

|ID|类别/入口|结果/退出|日志/对应SHA|
|---|---|---|---|
|RG01|offline|PASS；软件命令0，真实标注NOT_RUN|BASELINE.json / FREEZE.json / INPUT_BINDINGS.json；190576文件SHA基线，363冻结绑定，旧159+105清单一致；FREEZE/CHECKS|
|RG02|offline|PASS；软件命令0，真实标注NOT_RUN|CAPABILITY_GAP.md；已核实只有目标/二维/单行标签，无点级成员与覆盖；FREEZE/CHECKS|
|RG03|offline|BLOCKED；软件命令0，真实标注NOT_RUN|真实盲标NOT_RUN；点级通道缺失，无实际标注模型调用；仅材料准备；FREEZE/CHECKS|
|RG04|offline|BLOCKED；软件命令0，真实标注NOT_RUN|真实跨模型/分歧/仲裁/点级包络/audit NOT_RUN；未伪造；FREEZE/CHECKS|
|RG05|offline|BLOCKED；软件命令0，真实标注NOT_RUN|METRICS.json / STAGES.json；TP/FP/FN/纯度/召回UNKNOWN，标签覆盖0；FREEZE/CHECKS|
|RG06|offline|BLOCKED；软件命令0，真实标注NOT_RUN|REPORT.md / CASES.json / ORIENTATION_DIAGNOSIS.json；几何软件诊断已完成，分阶段语义错误及关联UNKNOWN；FREEZE/CHECKS|
|RG07|offline|PASS；软件命令0，真实标注NOT_RUN|README.md / CHECKS.json / MAPPING_CHECK.json；19旧+3边界测试exit0、386帧核对、18固定/35案例，保留失败；FREEZE/CHECKS|
|RG08|offline|PASS；软件命令0，真实标注NOT_RUN|SCOPE_PRE_APPEND.json / SCOPE_FINAL.json；无范围外变化/冻结漂移，仅新证据+文档追加；FREEZE/CHECKS|


回归：既有工具19项、新边界3项均-B -W error exit0；386帧源行/节点重算误差0；258基向量对的3次负点积全部保留；四帧源掩码与冻结输出一致，代数反向A==原B。实际命令见CHECKS.json，日志原文保留。交付工具脚本准备曾有一次语法错误、未执行任何文件写入，保留于DELIVERY_PREPARATION_FAILED.log；不影响已冻结诊断。交付v1还发生Windows默认GBK读取UTF-8基线的exit1；失败源码deliver_failed_v1.py及DELIVER_V1_FAILED.log保留，修复为显式UTF-8，已生成RESULTS按内容核对复用，未覆盖。历史失败只读保留。

## 未闭合与限制

- RG03/04：缺逐点成员通道/3D反查与点级包络、独立真实盲标/跨模分歧/仲裁/审查；解除方案见CAPABILITY_GAP.md，旧中心包络不可借用。
- RG05/06：TP/FP/FN/纯度/召回及语义错误关联UNKNOWN；18固定帧仅准备、0标签覆盖，不能宣称全会话人体结果。当前哪里误取/漏取未知。
- 已证实几何支撑机制不等于人体语义因果：f340→341侧别符号锚切换；张开f174→175无该翻转，不统一归因。共同节点冻结FAIL保留；TOP_REGION同帧有效相邻仅4对另表。连接UPPER_A/OUTER_A支撑嵌套，145有效帧均交叠，非解剖骨长。
- 下一项先补点级GT条件；若在已知工程故障中排序，证据支持区域侧别/连接支撑定义机制专项先行。前景修正需GT支持；不自动开工下一项。
- 已见开发数据、非独立测试；无事后效果阈值。设备/物理/部署NOT_RUN，S07F原8/10与NO_PROMOTION不改；无Git写/采集部署训练/下载模型/HR09/驱动网络变更。

## 交给Codex独立复审

- 现行唯一验收、逐ID、报告、复现：本新目录ACCEPTANCE_V1.md、RESULTS.json、REPORT.md、README.md。
- 根因与样本：run_r1/CASES.json、TIMELINE.csv、STAGES.json、COMMON_PAIRED.json、diagnostic_cases/、neutral_preparation/、ORIENTATION_DIAGNOSIS.json。
- 源码/输入/范围/产物SHA：BASELINE.json、INPUT_BINDINGS.json、FREEZE.json、SCOPE_PRE_APPEND.json、SCOPE_FINAL.json、MANIFEST.json、FINAL_SEAL.json。
- 原始日志：TEST_AI_GT.log、TEST_DIAGNOSE.log、RUN_DIAGNOSE.log、ORIENTATION.log、CHECKS.json、DELIVERY_PREPARATION_FAILED.log。真实模型调用/盲标/分歧记录不存在，明确NOT_RUN，不造空标签。
- 当前下一步：按缺口补齐点级正式证据能力；本次不等于冻结门通过、晋级或板端部署授权。
