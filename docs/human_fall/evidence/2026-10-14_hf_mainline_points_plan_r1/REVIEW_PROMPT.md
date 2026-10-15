# OpenCode 只读计划审核

用户明确要求多轮分析制定下一阶段计划并交给OpenCode审核。你是独立只读审核者，不是实现writer。本轮只审计划，不启动实现、不改任何仓库文件或历史状态、不联网查询、不调用子代理。所有结论输出到最终答复，由调用者原样保存。不要自行写审核报告。

先读取AGENTS.md、docs/human_fall/WORKFLOW.md、docs/human_capture/README.md和C:/Users/30680/.codex/skills/ponytail/SKILL.md（记录实际读取路径）。然后精读：

docs/human_fall/HF_MAINLINE_POINT_RETENTION_PLAN_20261014_V1.md

重点源证据：
- sidequests/human_fusion_lab_next/pointset/r01/research_actions.py、actions.py、core.py、config.yaml、config_actions.yaml
- sidequests/human_fusion_lab_next/real_fall/r04/background_ab.js、score_background_ab.py
- pc_apps/human_replay/human_pipe_lib.js
- docs/human_fall/evidence/2026-10-14_hf_mainline_leveling_r1/FINAL_REPORT.md
- docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r3/FINAL_REPORT.md
- docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/FINAL_REPORT.md
- docs/human_fall/evidence/2026-10-14_audit_r1/C01_claude_code_kimi_k3.md（不能盲信该审计因果断言）

无需读取points.bin或GT原始数据，不运行算法/测试/服务/命令、不请求写权限。仅使用read/glob/grep阅读源文件和计划；CLI permissions强制禁止写入和执行。

请从3个角度审核并给集中结论：
1. 根因事实与实验口径：JS/Python差异、KS1误归因、上游候选与R3边界、配准物理资格、源行/重复XYZ/终态账本。
2. 实验有效性与收益：单因素设计是否可实施、背景建图与提取高度如何隔离、GT泄漏/验证重用、已知标签及UNKNOWN/家具风险、门限是否会导致无法收口。
3. 工程落地与验收：现有工具复用、跨仓依赖、数据阻断局部化、输出保护、浏览器/因果回放、单一成品出口、范围授权是否准确。

最终格式：实际模型/会话身份（无法得知则UNKNOWN）、实际读取清单与技能路径、总体PLAN_PASS/PLAN_REVISE/PLAN_BLOCKED、按P1/P2/P3优先级列每个必要发现（精确文件/章节/源码行、证据、影响、最小修订建议）、无需修订的已核项、实现仍NOT_RUN的边界。审核通过仅代表计划，无权将工单ACCEPTED或批准生产晋级。请读完整计划，避免仅重复作者摘要。
