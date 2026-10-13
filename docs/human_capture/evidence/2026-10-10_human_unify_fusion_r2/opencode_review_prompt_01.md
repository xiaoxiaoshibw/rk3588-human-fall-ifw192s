# HUMAN-UNIFY-FUSION R2 指定只读独审

你是独立审查者，模型opencode-go/deepseek-v4.1-flash。Codex唯一writer已停止源码写入。只读，不改任何文件，不commit/push/deploy，不跑gt_server/e2e/标注器测试（会污染真实GT）。不启动其它写入者。不用bash Unix命令，本机Windows PowerShell；命令加-NoProfile。

先读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md 并在结论声明路径。
唯一验收表 docs/human_capture/HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md；范围：
- pc_apps/human_ml/frozen_gt.py / train_person_rf_v2.py / test_frozen_gt.py
- pc_apps/human_core/evaluate_fusion_gt.js / test_fusion_gt.js
- 本轮evidence/2026-10-10_human_unify_fusion_r2/ 的00_diag、01_external_gt_change、train_02、runs_03、四份报告及TRACK_EPISODE_EVALUATION.json。

R1 FINAL_REPORT §3+用户交接 §4+母验收表为要求。用户明确本轮S1家具训练覆盖旧S1只能val/test规则，不以此判实现FAIL；但缺独立家具及跨演员/场景仍BLOCKED推广。

逐F3-GT/SPLIT/TRAIN/KEEP、F4-RUN/PARITY/GT/S9/PERF、S01/S02/Q01/D01给PASS/FAIL/BLOCKED/NOT_RUN：验证代码边界与完整输出SHA来源，集中全部缺陷，不只报告第一条。重点：
1. manifest最后非e2e版本、实际GT/会话SHA、raw→compact、重复同点对象去重、UNKNOWN/抽帧、S9测试污染隔离；外部S1GT移走/S9V2消失不能伪称当前九会话GT通过。
2. train/val/test会话不交叉，0.55阈值冻结，v1/feature/rf契约不改。train_02 1726样本=1216家具+510人；S6 v2 62/71是回退；只离线加载candidate不生产切换。
3. 72完整session-mode-model runs、2605原帧每模式；FUSION/B逐帧原输入/配平/模型/包络SHA守卫，异算法不要求候选/track完全相等。共有同点集概率差如实FAIL。
4. XY一对一最大匹配、precision已标完整真人协议假设、空帧/未标帧不充负例、S9源无效BLOCKED；候选与当前track分开、ID switch不越未知帧；FP/hour观测暴露口径不是全段事件率。
5. P50/P95/P99预热5帧及heap/RSS口径；实际FAIL不可删除；模型GT ROI精度不冒充管线泛化。

可独立跑 node pc_apps/human_core/test_fusion_gt.js 与 python -B -W error pc_apps/human_ml/test_frozen_gt.py；其它昂贵或会改GT的测试不跑。可只读抽查runs_03/SUMMARY.json和具体run，避免一次dump全量输出。

输出精简逐ID表、独立命令/exit、实现FAIL的具体触发及要求来源、GT/外部变化BLOCKED单列、五判定建议。不能仅作者测试通过就宣布独审PASS。不要写文件，结论只输出到终端供调用者记录。
