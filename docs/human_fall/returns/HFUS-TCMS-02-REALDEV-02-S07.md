# HFUS-TCMS-02-REALDEV-02-S07 回传

## 本轮信息

- 工单/轮次/执行者/日期：HFUS-TCMS-02-REALDEV-02-S07 / r1 / Codex唯一代码writer / 2026-10-18。
- 当前唯一验收：[ACCEPTANCE_V1.md](../evidence/2026-10-18_hfus_tcms_02_s07_r1/ACCEPTANCE_V1.md)，SHA `07da5ceda8e8eee2eb89c2d17b8e682b32542c8b1d9e2e45b225baefb3386288`。
- 策略：关联契约ENGINEERING；前景、区域、效果RESEARCH。读取实际Ponytail：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`；Scientific Toolkit：`C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md`，按需读取其matplotlib参考。科学验证/证据完整性优先。
- 执行方式：Windows Python3.12离线复用开发录制；Codex模型具体ID未向本任务工具暴露，不猜测。OpenCode指定模型`opencode-go/deepseek-v4.1-flash`，R1已由Go v2会话导出核实，仅read/glob/grep；完整R1和ASCII补核状态见本轮证据。
- 状态：SUBMITTED，非ACCEPTED。研究效果S07-06 FAIL，停止推广；设备/物理NOT_RUN；无GT关节精度/人体效果BLOCKED；纯度/召回UNKNOWN。
- 起始branch/HEAD：master / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`。刻意脏树保留；完成全树190644文件SHA，含未跟踪/ignored非data文件，排除Git内部、data和reparse遍历；BASELINE_ALL记录status/size/mtime/SHA。范围外并行主题新增文档原样保留并披露，不能声称整树无其他变化。
- 输入meta/points字节及SHA见INPUTS.json；旧源码/配置SHA见EXECUTION_BINDINGS.json；实际命令运行前源码SHA/退出/耗时见各*_RUN.json，最终源码快照及SHA见EXECUTED_SOURCE与FINAL_SEAL。

## 集中诊断与根因覆盖

|缺陷/ID|根因|调用者/消费者与状态|隔离修复或研究位置|保留行为|
|---|---|---|---|---|
|S07-02 关联交叉歧义|冻结实现最终只过滤track歧义，candidate可同时出现在matches与ambiguous；仅标最近两候选还会漏第三个近等价选择|core/tracking.py单锁定目标、r08/wire.py多轨迹；新测量/创建与测量钟/TTL|r11/association.py复用旧门/评分，关闭歧义测量/创建并重建互斥分类；replay.py完整生命周期|旧core/旧wire保持冻结；距离/速度/尺寸门不改|
|S07-02 过期状态|旧wire先预过滤，LOST分支不可达|旧轨迹静默脱离active|r11 expire先记LOST再移出；歧义/失配不刷新last_measurement|生产与旧wire的静默过期缺陷已记录但未修；只修隔离接线|
|S07-04 前景残留|固定ROI在无人时仍有背景支持|新386帧RAW ROI输入|前50空帧冻结参考，6cm门，后50空帧负对照，不更新|不称旧S3完整M0、自动人体身份或人体召回|
|S07-05 中线/区域失败|改善前景后旧中线仍跨度1.1–1.3m、横轴偏PCA2约49–62度|当前帧estimate，原0.8m门拒绝|唯一主平面/窄核/远端区域变体；原门不放宽|没有EMA、预测、补点、逐帧挑人|
|S07-06 候选仍失败|OUTER_A选择两个沿主轴相隔约0.85m的支持群；点数3/6→4/3→2/6使中位数换群|f190/191/192源行；横轴点积>0.996|只做源行失败诊断，不再加变体或修法|区域骨架非关节；不把跳变称雷达噪声|

## 实际变更

|文件组|用途|与用户既有差异区分|提交源码SHA|
|---|---|---|---|
|sidequests/hfus_tcms_02/realdev/r11/association.py、replay.py|隔离契约/生命周期修复与780帧合法基线|新目录，旧core/旧r08不修改|各RUN及FINAL_SEAL|
|r11/experiment.py、regions.py|固定背景/四组386帧消融/唯一候选|不修改旧提取、配置、数据或旧证据|各RUN/VERIFY及FINAL_SEAL|
|r11/test_s07.py、test_regions.py、test_statistics.py、verify.py|合成边界、分母、源行和状态核验|新测试，不以总数代验收|各RUN及FINAL_SEAL|
|r11其余工具|注册/机制/失败诊断/对账/图/报告/OpenCode记录/封存|仅本轮工具，未另建生产跟踪框架|各RUN及FINAL_SEAL|
|本轮s07_r1证据、WORKFLOW/REVIEW_LOG/S07回传|证据交付和索引|历史字节保留，追加/前置，不回填旧报告|MANIFEST、DOCUMENT_APPEND、SCOPE_CHECK|

源行global_row与byte=global_row*28绑定，RAW坐标以m计，3D人口std/连续位移以mm报告；新区域只用于本会话RAW ROI/合成契约，不能用于旧780帧S3坐标。原780帧只改关联与显式过期状态，原变换/候选行/estimate/标定复用；不采用S06 envelope。

## 逐条作者自验

|ID/入口|方式|实际运行和证据|状态/退出|源SHA|
|---|---|---|---|---|
|S07-01|离线登记|register.py→BASELINE_ALL/INPUTS/PROTOCOL_V1/REGISTRATION|PASS；完成注册后才实验；首次串行扫描中止记录保留|注册/输入绑定|
|S07-02|synthetic+780逐帧|FROZEN_REPRO预期exit1；UNIT exit0；VERIFY exit0，780帧互斥完备、歧义测量/创建0、显式TTL84次|PASS|相应*_RUN.json|
|S07-03|offline780|REPLAY、ASSOCIATION_COMPARISON均exit0；全780行diff|PASS：317/490→315/490，候选383；轨迹67→84；唯一曾标定边10→8；漂移163→131|相应*_RUN.json|
|S07-04|offline386|FOREGROUND exit0、ledger/counts、全部固定窗口|PASS为证据完成；纯度/召回UNKNOWN|相应*_RUN.json|
|S07-05|synthetic+offline386|RAW_OLD/FG_OLD/RAW_NEW/FG_NEW exit0；REGIONS_UNIT首轮exit1后R2 exit0；MECHANISM首轮exit1后R2 exit0；STATISTICS exit0|PASS为对照/机制/边界交付，不表示算法有效|各RUN，旧失败源码重建与运行前SHA完全一致|
|S07-06|冻结研究门|CONCLUDE exit0；EFFECT_GATE/全部逐节点分母与当前标定边|FAIL：OUTER_A900mm>100mm，其他跳变回归，只有5条边达75/151而门为6条|CONCLUDE_RUN，不改门、不重跑新候选|
|S07-07|交付+独审|R1完整OpenCode原文及Go v2实际模型审计；ASCII补核/最终范围/封存|完成状态在下方最终追加段；独立执行NOT_RUN|审核前后SHA/完整输出/退出状态|

核心旧HF05回归30测试exit0；新关联5测试、统计4测试、新区域R2 5测试exit0，均`python -B -W error`。这些是运行记录，不等于工单ACCEPTED。四组每个有效节点从原始支持行重算，旧区域最大误差4.44e-16m、新区域0；全部窗口统计从逐帧记录重建一致。

## 未闭合与限制

- 本轮候选效果FAIL并停止推广。FG_NEW保持CHEST/OUTER_A151/151，但OUTER_A仍900mm跳变；RAW_NEW OUTER_A的12mm std不可挑出宣称成功，同组LOWER_A仍524mm跳变且含背景。
- 无GT：区域不是解剖关节，人体身份、纯度/召回、关节精度、纯雷达噪声及泛化结论均不可推出。两段均REUSED_DEVELOPMENT，非独立测试。
- None跳变不能当稳定通过；预注册判门实现的理论宽松处已披露，本轮实际效果FAIL，不为其后调门/补预测/隐藏缺测。所有节点有效分母和null保留。
- 第一次被中止基线扫描的执行时源码SHA未记录，明确UNRECORDED；不冒称事后重建封存。后续完整基线排他写、实际候选源码SHA完整。
- Go首轮中文工具读取有编码失真；原请求/输出/旧元数据解析失败都保留，ASCII等价说明补核与v2会话模型审计另列。审查中的边数/RAW_OLD对象混淆等误读有原文及处置，不覆盖原审查。
- 当前图为`MEASURED_TIME_SERIES_R2.png`和`*_CASES_R2.png`；仅固定全源帧横轴，JUMP_CASES两版数值相同。FOREGROUND_COUNTS只按帧计数，窗口以PROTOCOL_V1索引切片，标签/指标在各SUMMARY。
- 不部署、不采集、不Git写、不删/移动data、不改驱动网络、不训练/下载模型、不启动HR09。设备/物理NOT_RUN。源输入/冻结旧代码/配置另行全SHA复核；并行其他主题文档只记录，不归入本轮。

## 交给独立复审与交付入口

本轮证据目录`docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s07_r1/`。当前验收、AUTHOR_REPORT及ADDENDUM、逐帧ASSOCIATION_DIFF、四组FRAMES/SUMMARY/VERIFY、原始行LEDGER、JUMP_CASES_R2、源行失败诊断、每命令日志、OpenCode两轮请求/原文/实际模型/状态、最终逐ID与HANDOFF/封存均保留。

本轮下一步仅完成以下审核收尾和封存；效果FAIL不授权生产集成或新算法里程碑。


## 2026-10-18 S07 开发、自验及OpenCode审核交付

- 工单HFUS-TCMS-02-REALDEV-02-S07，Codex唯一writer，SUBMITTED，非ACCEPTED。关联ENGINEERING；前景/区域/效果RESEARCH。
- 实际技能C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md；matplotlib参考。
- 唯一验收[ACCEPTANCE_V1](../evidence/2026-10-18_hfus_tcms_02_s07_r1/ACCEPTANCE_V1.md)，SHA 07da5ceda8e8eee2eb89c2d17b8e682b32542c8b1d9e2e45b225baefb3386288。
- 逐ID：{"S07-01": "PASS", "S07-02": "PASS", "S07-03": "PASS", "S07-04": "PASS", "S07-05": "PASS", "S07-06": "FAIL", "S07-07": "PASS"}。S07-06效果FAIL；停止推广；无GT关节精度/人体效果BLOCKED，纯度/召回UNKNOWN。
- 根因/调用者/生命周期与全部真实变更、实验、环境、命令、失败、源码SHA、全窗口结果：[作者报告](../evidence/2026-10-18_hfus_tcms_02_s07_r1/AUTHOR_REPORT.md)。代码仅r11，复用旧关联门/候选账本/提取/标定，新增歧义封堵及LOST状态；前景冻结背景与唯一主平面区域变体。旧317/490不改，非法更新不保数。
- OpenCode实际['opencode-go/deepseek-v4.1-flash']，exit0，753.719s，仅静态，独立执行NOT_RUN；前后源码SHA相同True。完整请求/输出/退出/处置见本轮OPENCODE_REVIEW*与REVIEW_DISPOSITION。
- 输入两段均已用开发诊断，不是独立测试。仅离线区域骨架，不冒称解剖关节；无Git写/数据删除/部署/采集/驱动网络修改/训练/模型下载/HR09。设备/物理NOT_RUN。
- 可复现与证据索引见HANDOFF.md；范围核验SCOPE_CHECK.json，源码快照EXECUTED_SOURCE，MANIFEST和FINAL_SEAL；历史文档追加/前置，历史原字节保留。
