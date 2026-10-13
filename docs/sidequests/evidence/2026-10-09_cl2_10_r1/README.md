# CL2-10 121647 TLS 残差因果调查

本工作项入口，唯一验收表 [00_SCOPE_AND_ACCEPTANCE.md](00_SCOPE_AND_ACCEPTANCE.md) v1；单变量预注册 [00_EXPERIMENT_PLAN.md](00_EXPERIMENT_PLAN.md)。当前用户新授权的是离线残差归因；旧提议的运行链路集成不是本轮。

STEP0 用 prepare.py 复核历史 manifest、原输入/报告/域/参数和执行源，复制 CL2-09C 隔离 runtime，不接生产。历史证据不覆盖；原始 bin 只读，固定 FIT/holdout 和原四 ROI。物理参数/表面身份未核验，名义26°和历史1.14m不当 GT。

必须先有可复现因果证据才可实现 shadow 修复；否则仅交付诊断、失败假设、候选设计及未闭合条件。所有局部多平面/重权重诊断的数值改善均不等于当前 raw TLS 修复或物理标定，50mm P95 原门不变。有效 TLS 与生产继续 BLOCKED；无 B2/B3、采集、发布、设备操作。

脚本输出采用 exclusive；复现应新建 revision，不能覆盖本目录。最终 FINAL_REPORT.md、01_root_cause.md、02_shadow_ab_results.json、03_regression_results.txt、04_independent_review.md、05_evidence_manifest.json 与实际 OpenCode 原始记录/CLUSTER-01 return 一起闭合。
