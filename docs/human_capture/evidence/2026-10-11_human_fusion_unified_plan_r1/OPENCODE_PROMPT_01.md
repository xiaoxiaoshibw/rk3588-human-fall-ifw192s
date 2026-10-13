你是独立只读规划审查者。用户本轮直接授权：“归一开发进度，根据总结制定修改优化开发的计划算法架构，多轮仔细制定完善，然后opencode审核”。只审核，不实施或写任何文件；不得bash/task/网络/训练/GT更改/部署，不切model/provider/database/auth。指定opencode-go/deepseek-v4.1-flash / defaultDB。

先read D:/Code/ldiar/AGENTS.md，docs/human_capture/README.md当前第一节，docs/human_fall/WORKFLOW.md顶部和通用流程；读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md 并在意见中注明路径。

审核冻结提交：
- docs/human_capture/evidence/2026-10-11_human_fusion_unified_plan_r1/PLAN_SUBMITTED_01.md
- 同目录 ACCEPTANCE_SUBMITTED_01.md、SUBMISSION_01.json、ROUND_01_RECONCILIATION.md、ROUND_02_ARCHITECTURE.md、ROUND_03_ADVERSARIAL.md、SOURCE_CHECK_01.json。
- 当前工单 docs/human_capture/tickets/HUMAN-FUSION-UNIFIED-PLAN.md。

核证来源（请实际read关键源码和JSON，而非仅同意作者总结）：
1. docs/human_capture/evidence/2026-10-11_human_fusion_diagnosis_r1/REPORT.md 特别§3/5/6/10/12；late_review.json、historical_v2_recalculation.json。
2. CC 03_SUMMARY.md；V3 REPORT_FINAL.md，CANDIDATE_IMPROVE_S6.json；这两份历史报告有已被诊断纠正的归因，不能自动照抄。
3. sidequests/human_fusion_lab/v2_runtime.js、unique_tracker.js、detector.js、core/engine.js特别_fusion_a/b/organize/_tick；sidequests/human_fusion_lab_v3/v3_runtime.js、core/bg_groups.js；train.py和V3 tools/eval_controlled_comparison.py；生产pc_apps/human_core/engine.js相关union差异。

重点审查：
- 是否分清B背景mask与真实检测全链，f128混簇与点门、XGB候选域脆弱与未唯一证明位置记忆、PointNet中心化、GT分母、骨架proxy与真关节；是否V2 Unique重复建设。
- 候选级计数在classifier前；当前PB提前筛人与NON_HUMAN会更新Unique位置是否被contract处理；GT只能事后归因；BG-B真接共同入口后PB不能再次BG-A硬删除。
- 现有PIPE tracker管retention、Unique管最终输出；迁移是否隔离，是否把历史union anchor/score修改混入初轮。
- 旧distance confirmed数字与strict measured支持是否可重算；partial未标unmatched不误当FP；identity/长静止真值资格；点率/预测不得充检测TP；无有效负例不得晋级。
- D03工程FAIL仍允许D04/D05按冻结变体研究，D06联合晋级需同一次全链目标；是否有隐藏循环依赖/多变量/不可执行验收。
- 背景三态无raycast证据不伪称FREE；tinyPointNet正例比较不否定深度路线；预注册split不泄漏/不挑test，当前9会话只当开发回归。
- 稀疏n门/时窗/分类特征/追踪生命周期算法规划是否具体可执行，是否过度框架，是否存在逻辑缺陷或与源码不符。

输出中文完整独审报告：逐P01～P09给PASS/FAIL/NOT_RUN/BLOCKED；列可复现P0/P1/P2问题及文件位置/实际依据/最小修订建议，非要求的新功能另分建议；DEV01和D01 NOT_RUN、DEV02和PHY01 BLOCKED保持。你不需要执行算法，也不能把没有执行结果的算法指标当本规划FAIL。P02最终全树对账和P09审核处理在结束后才能完成可NOT_RUN，不因此虚称未实现。P08只能证明本次实际读审；不宣称系统ACCEPTED。最后明确规划裁定 READY/REWORK_REQUIRED/BLOCKED，末尾输出 REVIEW_COMPLETE。报告只输出stdout，编排者保存。
