# HF-MAINLINE-POINTS-01 已实现版本只读审核

你是本轮指定独立审核者，模型请求opencode-go/deepseek-v4.1-flash。只读，不执行命令、不运行测试/服务、不写任何文件、不读取points.bin原录制、不调用子代理、不改变默认/GT/正式门/生产。结论直接输出，由调用者原样落盘，不自行写报告。

先读AGENTS.md、docs/human_fall/WORKFLOW.md、docs/human_capture/README.md和C:/Users/30680/.codex/skills/ponytail/SKILL.md，记录实际读取路径。本轮用户已明确授权按docs/human_fall/HF_MAINLINE_POINT_RETENTION_PLAN_20261014_V3.md完成实现、真实数据/页面/全帧/失败返工与本审核；旧“仅计划授权”条目已被本用户当前明确实现授权覆盖。不把物理GT作为研究启动门，也不把UNKNOWN当人体。

唯一作者交付：docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1/CURRENT_DELIVERY_INDEX.md、FINAL_REPORT.md、ACCEPTANCE_V1.md。按计划PR01–12、PR07a/b/c逐项查；不要用单测总数代替验收。原审/原失败永不覆盖。

优先核查：
- sidequests/human_fusion_lab_next/pointset/r01/research_retention.py、config_research_retention.json、test_retention.py
- tools/hf_mainline_points/verify_retention.py、qualify_ledger.py、freeze_candidate.py、js_diagnose.js、enrich_js.js、score_js.py、summarize_retention.py
- 原actions/core/research_actions/experiment_r3/experiment_actions只读算法复用；server/app/index仅本轮保留与查询接入。共享页面scene_change由另一会话同期写入，外部变更保存EXTERNAL_PAGE_CHANGE.json及*.external_scene_observed，不是本轮算法，也不应被本作者回滚。单writer指本保留算法。
- SOURCE_BINDINGS/DEPENDENCY_BINDINGS、BASELINE_REPRODUCTION、LEDGER_CODEBOOK/QUALIFIED_LEDGER、REFERENCE_RISK_MANIFEST、FROZEN_CASES/FROZEN_EXPERIMENT_V3、REGRESSION_RUNS、API_CHECK/BROWSER_CHECK、PRESERVATION_REHASH及原日志
- sidequests/human_fusion_lab_next/pointset/r01/action_research_retention/run_01/FROZEN_CONFIG.json、FROZEN_SOURCE.json、SUMMARY.json、ANALYSIS.json、ALL_FRAME_VERIFICATION.json；不要读取几GB全部源数组，以代码+冻结汇总审查，必要时读几帧候选JSON
- JS_METRICS.json、js_02/cap_20261010_180557/MANIFEST.json、同目录ledger_v2/LEDGER_CODEBOOK.json；JS旧基线固定C_V2_DIAGNOSTIC，S8 53帧57045标签；Python/JS/家具门分开
- 计划CONTEXT_HOLDOUT_V2.json：80帧及前5帧上下文排除选择，历史已见，属于1966子集，不称独立新测试。

请集中审核实际代码与作者结论：源行守恒/重复XYZ、实际first reason与反事实及候选资格追加层、bounded causal reset/换ID/时间倒退/gap、只用当前真实background_removed/原ROI、R3旧FG契约、独立FIT风险是否诚实无鉴别力、代码/冻结/输出覆盖保护、标签仅评分、空场/新增退化/最差帧、真实浏览器多视角与完整导出、R1默认、JS模型口径/高度2×2、跨仓绑定、作者是否夸大PASS。

输出格式：实际会话/身份可得才填；完整读取清单和技能路径；总体REVIEW_PASS/REVIEW_WITH_FINDINGS/REVIEW_BLOCKED（不ACCEPTED）；按P1/P2/P3列必要发现，精确文件行/证据/影响/最小修复；非阻断限制单列；逐PR状态建议。不得代作者关闭物理/完整人体/生产门，原失败结论必须保留。


最终当前事实（优先于早先清单）：主候选为run_02护栏combined/feedback，旧run_01六臂为消融与失败保留。须读research_retention_guard.py、config_research_retention_guard.json、verify_retention_v2.py、run_02/ALL_FRAME_VERIFICATION.json、run_02/ANALYSIS.json、REWORK_02_FROZEN.json与GUARD_VERIFICATION。80帧及全回归已在护栏返工中重用，作者标REUSED_REGRESSION，不是新独立测试。JS最终身份依据verify_js_identity.js与JS_ORDINAL_IDENTITY_PROOF.json，原坐标匹配仅等价验证。

最终额外阻断：captures/remote为空，八动作与131958共18个meta/points缺失，见FINAL_SOURCE_AVAILABILITY、BROWSER_CHECK、API_CHECK_SOURCE_MISSING。此前API_CHECK_FINAL有真实原字节PASS但不能冒充当前可用；现在查询明确MISSING_ORIGINAL_SOURCE/opaque=null，冻结账本可查/实际完整下载49130条可用，原录制复跑BLOCKED。作者未删除、不归因、不生成替代原数据。请审查作者是否仍有夸大或不一致，不要求猜测恢复丢失原录制。端口为IPv6回环http://[::1]:8944，IPv4另有PLANE服务未停止。

首轮CLI因--file数组吞掉末尾message而启动失败，无审者结论；原日志保留。本次修正参数分隔后实际审核。
