# HFUS-RF-EVAL-01 回传

## 2026-10-16 R1 / 开发计划 / PLAN_SUBMITTED

用户授权：「好的制定开发计划」。本轮仅计划；执行者Codex，本机直接编写文档，无训练或实施CLI。沿用独立公开数据侧链，不接管HF/GL/其他HC/HR工单。

- [计划入口](../evidence/2026-10-16_hfus_rf_eval_plan_r1/CURRENT.md)
- [开发计划 v1](../evidence/2026-10-16_hfus_rf_eval_plan_r1/PLAN_V1.md)
- [唯一拟实施验收 v1 / EV01–EV14](../evidence/2026-10-16_hfus_rf_eval_plan_r1/ACCEPTANCE_V1.md)

基线 master/c9c4ee421cb0c8a3e4590b8f5730828b093c759a，dirty和未跟踪保留；范围输入SHA/缺件与全量状态分别在BASELINE.json、STATUS_BEFORE.txt。ponytail实际读取 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full）。

集中诊断：原训练器、点云adapter、候选/manifest/标签账本、run4工件和三ZIP在原路径缺失（逐项见快照），原因未确认，不恢复或重建。EV01 BLOCKED；EV02–EV14实现NOT_RUN。分数源审查沿用TRAIN-AI01 R2发现：候选子集口径不等于完整检测效果、PointNet模型/Adam跨折复用。

实际变更仅新计划包、本回传及README新增计划索引。计划明确冻结B0/RF参数及标签，补全候选OOF评分、最大基数一对一匹配、完整GT分母和UNKNOWN语义、目标错误回放、资源帽及停写后独立复审。无生产源码/数据/模型/旧证据写入，无训练、设备、下载、采集、部署、Git提交推送；数据门未解锁。本文不作为实施或下一阶段授权。

验证：文档相对链接、EV编号和协议要求静态核对；没有运行算法测试、独立复审或真实数据实验，不冒称PLAN_PASS或工单ACCEPTED。后续明确开工后先核输入门，缺件时仅推进独立合成软件测试并报告真实效果BLOCKED。
