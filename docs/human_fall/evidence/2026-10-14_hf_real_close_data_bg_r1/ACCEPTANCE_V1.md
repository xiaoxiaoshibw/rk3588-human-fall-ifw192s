# HF-CLOSE-01 / HF-DATA-01 / HF-BG-01 当前唯一补充验收 v1

登记日期2026-10-14，按本次用户实际授权；未发现既有同ID工单，计划中的建议ID在本轮登记，不回填历史。三工单共用本表，不复制已有r04 ST01–ST09或HR-RET-V2表。本表不改变其门槛。

作者Codex `/root`，只读独审 `/root/readonly_review`；未参与写入。技能实际路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md。

| 工单/检查ID | 冻结要求 | 本轮自验状态 | 证据 |
|---|---|---|---|
| HF-CLOSE-01 / CL01 | 当前HEAD、含untracked/ignored基线、实际源码/输入/加载版本绑定 | PASS（直接r04）；console仍r02，完整入口FAIL | BASELINE_BEFORE / CURRENT_VERSION_MANIFEST / FINAL_REPORT |
| CL02 | 逐条审计原ST01–ST09，raw/display、弱轴、prototype、因果/误删/空场限制分开 | PASS（审计）；r04全表未通过 | R04_AUDIT / TARGET_COUNTERFACTUAL / FINAL_REPORT |
| CL03 | 独立非writer审查r04与V2-14；r03 RS04不由writer关闭 | PASS（执行独审，有发现）；非全表PASS | INDEPENDENT_REVIEW |
| HF-DATA-01 / DT01 | 会话SHA、真实时间、源索引、坐标/ROI/标签及split统一manifest | PASS（8个BOUND部分标注）；S9 BLOCKED | UNIFIED_INPUT_MANIFEST |
| DT02 | S8双路、S9不强绑、未知不当背景；缺源有界查找、093958 DATA_BAD | PASS（拒绝与记录），语义资格BLOCKED | INPUT_MANIFEST / FINAL_REPORT |
| DT03 | 最小审阅工具，31 POINT与155 ROW分开；AI只能PROPOSED；读取/保存拒绝漂移 | PASS（软件与真实浏览器）；人工审核BLOCKED | REVIEW_QUEUE / browser_final / TEST_01 |
| HF-BG-01 / BG01 | 现行P/冻结参考/v2同源、因果、split分开、无行动永久背景 | 诊断PASS；生产现行P完整等价A/B BLOCKED | *_ab_manifest / BACKGROUND_METRICS |
| BG02 | 静立/低位/污染分别列分母，不以UNKNOWN作负类或精度 | FAIL（v2静立94.783% < 原95%，近地失败）；污染BLOCKED | metrics / AB_RETENTION_AND_UNKNOWN |
| BG03 | 可用输入真实重计算registration，绑定/几何/W03三个gate分开 | PASS（真实重计算）；新artifact REJECTED；W03 BLOCKED | REGISTRATION_REBUILD_RUN / ARTIFACT_STATES |
| BG04 | 独立HOLDOUT空场，候选/确认/事件分开，原正式loader规则保持 | 有限诊断PASS；正式V2资格BLOCKED | EMPTY_HOLDOUT / TEST_04–05 |
| S01 | Python -B -W error、相关边界/回归、真实浏览器、首尾保护核验 | PASS；首次工具错误保留 | TEST_RUNS / RUN_LOG / PRESERVATION_CHECK |
| X01 | 不生产启用、不HF06 confirmed、不部署采集训练、不Git写 | PASS | FINAL_REPORT / git diff及保护核验 |

当前总状态 **SUBMITTED / REVIEWED_WITH_FINDINGS / STOPPED**，不是ACCEPTED，不自动推进HF-INTEGRATE-01。

原唯一表：[r04 ST v1](../2026-10-13_hf_real_04_r1/ACCEPTANCE_V1.md)、[HR-RET-V2 v1](../../../human_capture/HRRETV2_ACCEPTANCE.md)，旧表不写。
