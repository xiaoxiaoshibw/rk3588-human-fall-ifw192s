# RF-OPTIMIZATION-R1 当前收口

**离线研究 SUBMITTED / 当前软件独审无 FAIL；识别可用性 BLOCKED，R3/R4 NOT_RUN，未 ACCEPTED。**

已执行51维真实定义/数据/泄漏/JS差异审计，1239源候选全向量重现，18新几何特征、RF-v2/v3与HistGBDT、嵌套会话调参/阈值、留出permutation/相关性/实际删列消融、PR图、位置敏感性、本机性能、困难候选人工复核材料，以及指定OpenCode两次实际独审。加固单类选参和空recall汇总，4项检查PASS；run02与run01公共四路线的4956预测和24折混淆/参数/阈值完全一致。

| 当前主对照 | 维度 | 弱标签Precision | 弱标签Recall | 弱标签FP/FN |
|---|---|---|---|---|
| RF-v2 | 51 | .8772 | .9989 | 128/1 |
| RF-v3 | 69 | .8772 | .9989 | 128/1 |
| HistGBDT | 69 | .9870 | .9989 | 12/1 |

这是同房间六静态会话、自动位置弱标签的折间描述统计，各折阈值不同，不是生产阈值成绩。RF扩维未改善计数；GBDT删除显式XY/距离代理后FP增到34，仍需可靠GT跨场景对照，不能直接替换生产。GBDT优势主因未定。两会话零负例；数据不支持真实识别precision/recall与生产资格。

当前逐ID状态：RFO-01/02/05/07/10/11/12限定软件/研究PASS；RFO-03/04/06/08/09 BLOCKED；D01 NOT_RUN。源点绑定/嵌套划分/本机基准的子检查通过，不覆盖完整因果归因、新困难人工样本、新人/家具/姿态/远距资格。未触发采集/部署/主链融合/生产模型更新/HR-09激活。

独审原文：[第一审](10_OPENCODE_REVIEW01.md) / [修复后二审](20_OPENCODE_REVIEW02.md)。第二审独立实际跑4项检查，复算run01↔run02，结论“无当前软件FAIL，加固已闭合”，资格仍BLOCKED。原文个别用词“真实正样本”在本单应统一理解为**历史弱正标签**，未获得人工GT签核；[17切片澄清](17_SLICE_CLARIFICATION.md)记录该候选23弱负+1弱正，不偷换真值。

文档：[完整审计](01_AUDIT.md)、[作者首轮报告](08_AUTHOR_REPORT.md)、[加固记录](13_REPAIR_NOTES.md)、[逐候选比较](16_repair_comparison.json)、[提交SHA](19_submission_manifest.json)。图：[逐会话PR](workspace/run01/pr_session_curves.png)、[候选复核视图](workspace/run01/review_cases.png)。人工复核JSON保留label/signature为空，源帧seq/rank/点索引SHA可追溯；需结合全帧上下文签核，不能只看局部视图定GT。

下一步是完成失败候选的可靠人工标签与质量标签，并补齐独立人员/家具/场景及姿态距离数据，冻结新验证集后复验RFO-09。缺证据前保持实验分类器定位。该数据工作未完成，不能把R1/R2整单报告为已达可用水平；本轮不自动采集。

保护范围见06：RF实现/模型、背景包络、六源点云和C1证据未发现变更；共享树中console_test及另一sidequest三文件有外部变化，已记录且未回滚，不宣称整树冻结。起始与结束HEAD均347a5bf05ee82766436382f4fc3d1a8ed15c1132，未commit/push。ponytail实际路径为C:/Users/30680/.codex/skills/ponytail/SKILL.md。
