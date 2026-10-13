本次是完整、独立、只读的 HUMAN-FUSION-UNIFIED-PLAN v2 规划审核，用户直接要求多轮制定算法架构后由OpenCode审核。只能read/glob/grep/list，禁止写文件/bash/task/联网工具，不实施算法，不切provider/model/defaultDB/auth。指定opencode-go/deepseek-v4.1-flash。stdout输出报告即可。

首先实际read C:/Users/30680/.codex/skills/ponytail/SKILL.md，不能凭声明说已经读过；然后读取D:/Code/ldiar/AGENTS.md、docs/human_capture/README.md顶部、docs/human_fall/WORKFLOW.md当前边界。当前唯一授权是规划/只读审核。

证据根目录D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_human_fusion_unified_plan_r1/。核心提交PLAN_SUBMITTED_02.md（v2）、ACCEPTANCE_SUBMITTED_02.md（v1）、SUBMISSION_02.json、SOURCE_CHECK_02.json、ROUND_01_RECONCILIATION.md、ROUND_02_ARCHITECTURE.md、ROUND_03_ADVERSARIAL.md。首次真实审核参考OPENCODE_REVIEW_01.md、意见处理REVIEW_RESPONSE_01.md、新传输纠正DISPATCH_INTEGRITY_03.md。

重要：前两次cmd包装器截断多行提示词，只收到第一行，session export已证。原READY保留作参考，不能替代本次完整审核。现在同安装opencode.exe直接传参数，编排者结束后核你实际收到的提示词完整性和model。本次请直接审当前文件，避免读取自己的活动jsonl、巨大baseline或旧W01路线，勿照抄前次不正确意见。

必须独立读的源码/JSON：
1. sidequests/human_fusion_lab/v2_runtime.js、unique_tracker.js、detector.js；v2强制Unique已完成，NON_HUMAN关联可更新旧轨迹位置，所以新strict定义要求当帧accepted成员支持。
2. sidequests/human_fusion_lab/core/engine.js 第290～530行：PA/PB共同背景硬门、PB分类前过滤、union公开成员、PIPE tracker→retention bank→下一帧当前RAW补回，以及最后Unique输出。主链pc_apps/human_core/engine.js对应union差异。
3. sidequests/human_fusion_lab_v3/v3_runtime.js 第30～55行和core/bg_groups.js：super.frame先出旧链，B只mask；BG-B无匹配不证明FREE，只有ray/coverage证据可称FREE。
4. sidequests/human_fusion_lab/train.py:55，与V3 tools/eval_controlled_comparison.py对应未中心化。诊断evidence/2026-10-11_human_fusion_diagnosis_r1/late_review.json关键PointNet A/B、B家具FP595/608、V3 f128 covered_by_clusters15/orphan0；若大JSON可read精确段或SOURCE_CHECK_02简表。
5. 诊断REPORT.md §3/§6/§12。GT不完整、没有val/test/stress negatives、S9草稿非GT；新工具不能自签human。

逐项审查规划是否实际可执行：
- 归一结论和数字有源；v2补全S1+7人体会话总510 PERSON、504/127/6、491/112/19；S9UNKNOWN不入合计。SOURCE_CHECK_01实际有9会话，首次“只有4”判断错误。
- retention是PIPE结果更新bank（engine501～510），再bank读入RAW点（322～336）；首次“PIPE不影响FUSION retention”错误。v2图retention返回PA/PB提案，不直接union。bank不是第三tracker；最终对齐后置单独消融。
- B真接PA/PB共同入口，PB不再次envelope删除；提案在classifier前计数，GT仅事后评价，f128混簇不能只看人体点数断言n门；稀疏/0.2与0.5秒时窗不借未来或伪造测量。
- actual有序pointset/count/bbox/Float32/preprocess契约；anchor与scoring_centroid明确，模型/候选/tracker独立实验，无多变量因果假称。
- partial unmatched不当真实FP；legacy与strict重新基线；无候选FN不消失；coast不计检测TP/骨架；长静止/双人身份要连续人工真值。
- D03工程接通与算法收益分开，失败的冻结候选域可供D04/D05a研究；D02人工未审不阻工具工程但阻模型晋级；D06联合目标同一次全链满足，避免循环依赖与拼最优成绩。
- v2统一物理PHY01；后续算法DEV01 NOT_RUN、人工DEV02 BLOCKED、设备D01 NOT_RUN、PHY01 BLOCKED；规划READY不是系统ACCEPTED。

中文完整意见，逐P01～P09报PASS/FAIL/NOT_RUN/BLOCKED；P02最后整树对账和P09最终收口尚待完成可NOT_RUN。列阻断缺陷与非阻断建议（严重性、文件位置、实际依据、最小修订）；不把本轮未实施的算法指标当规划FAIL。明确前次两条事实误判复核结论、实际技能读取路径。最终裁定READY/REWORK_REQUIRED/BLOCKED，末尾输出 REVIEW_COMPLETE。不改任何文件。
