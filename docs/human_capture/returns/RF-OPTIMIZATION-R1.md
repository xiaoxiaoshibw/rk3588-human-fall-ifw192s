# RF-OPTIMIZATION-R1 回传

## 2026-10-10 R1 作者回传

- 工单/轮次/执行者：RF-OPTIMIZATION-R1 / r1 / Codex唯一writer。
- 现行验收：[RF_OPTIMIZATION_R1_ACCEPTANCE.md v1](../RF_OPTIMIZATION_R1_ACCEPTANCE.md)，SHA见本轮提交manifest；每个ID定义只有此表。
- 实际执行：本机Python3.12.10、NumPy1.26.4、scikit-learn1.9.0；新evidence/workspace隔离代码和模型，未更换全局环境。指定OpenCode Go Flash只读审查另存原文。
- 状态：软件探索SUBMITTED；可用性/完整数据验收BLOCKED；设备/物理NOT_RUN；未ACCEPTED。
- 起始branch/HEAD：master / 347a5bf05ee82766436382f4fc3d1a8ed15c1132；共享dirty树，未commit/push/reset。
- ponytail SKILL.md实际读取：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。
- 范围内用户差异：只新增本单票/表/回传/证据和README前置登记；7755条原tracked+非忽略untracked均有起始SHA，忽略文件不冒充全覆盖。

## 集中诊断与根因覆盖

| 验收 | 根因/受影响入口 | 本轮处理 | 保留行为 |
|---|---|---|---|
| RFO-02 | v1整帧训练、候选消费；空场副本跨fold；schema/PCA/JS/强度不一致 | 全量审计，簇级重提、嵌套分组、18新维研究对照 | 旧源码、模型、历史成绩不改 |
| RFO-03/04 | 位置弱标签不能证明完整人簇/家具真值，消失候选不在训练集 | 源点索引SHA、逐候选review_queue；不足保留BLOCKED | 不写source:human、不自动补GT |
| RFO-05/07 | RF扩维未改善误判，GBDT位置捷径风险 | 实际三路+三组消融、permutation/PR/敏感性 | 不选生产冠军/外折阈值 |
| RFO-09 | 缺未见人员/家具/场景、姿态与远距独立标签 | 预注册资格门保留BLOCKED | R3/R4不启动 |

## 实际变更与逐条验收

完整文件用途、逐ID状态、日志/计数/命令、限制及保护变化：[08_AUTHOR_REPORT.md](../evidence/2026-10-10_rf_optimization_r1/08_AUTHOR_REPORT.md)。源码SHA见提交manifest；源数据SHA和候选绑定见prepared/provenance.json及bindings.json。3项综合实验检查 -B -W error、exit0；主训练run01与追加敏感性exit0。未跑不以测试总数替代。

RFO-01/02/05/07/11/12作者限定自验PASS；RFO-03/04/06/08/09 BLOCKED；RFO-10提交时等待实际独审结论，以后续追加记录为准；D01 NOT_RUN。完整外层模型FP：固定簇基线140，RF-v2/v3各128，GBDT12，FN各1；全为弱标签描述，不是可用性证明。

## 未闭合与限制

真实困难样本补充、逐点候选质量/漏候选/Track因果、新人员/新家具/场景及弯腰/遮挡/动态/4–6m资格未闭合。没有自动采集或生产切换权限，下一步应先补可靠人工标签和独立数据，再复验预注册资格。识别可用性不能靠本轮同房间高分宣布完成。

## 交给指定独立复审

只读OpenCode CLI `opencode-go/deepseek-v4.1-flash`，prompt04/raw05；读取源码与磁盘results、实际运行测试/独立计数及split核查。若发现FAIL由Codex修复后新编号复测/复审。外部同时改变console_test及sidequest三文件已经登记，不能回滚或称整树冻结未变。

## 2026-10-10 R1 独审、加固与复审追加

第一审10实际执行exit0，提出未来单类/空recall边界与口径建议；Codex加固后4项检查PASS（11，exit0），新run02三主对照+基线exit0，与run01的4956逐候选p/threshold/predicted/error和24折混淆/参数一致（16）。位置58维事后诊断也已完成，不使用外层选生产模型。两次OpenCode CLI原始流05/15、实际回文10/20，二审独立跑4检查、复算相同结果，当前软件无FAIL、加固闭合；RFO-10当前为PASS。旧报告提交时的NOT_RUN保持历史不改。

当前全表：RFO-01/02/05/07/10/11/12限定PASS；03/04/06/08/09 BLOCKED；D01 NOT_RUN；总体未ACCEPTED。唯一表v1 SHA与源码/研究工件记录在19，最终补充文档/SHA另记录；[当前收口](../evidence/2026-10-10_rf_optimization_r1/21_CLOSEOUT.md)为本轮结果入口。独审个别“真实正”措辞不构成人工GT，全部1239标签仍UNVERIFIED。真实困难样本补充/新人新景资格尚未闭合，R3/R4 NOT_RUN。
