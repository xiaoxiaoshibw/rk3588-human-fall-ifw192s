# R3.8 最终自验提交（r3 safety cohort 修正）

2026-10-07，Codex 唯一 writer 已停写。**SUBMITTED / REWORK_REQUIRED，未 ACCEPTED**。本记录为本轮现行结果；`08_results_summary.md` 保留为 r2 过程记录，其 T38-05/S4 与“clean=0”结论由本记录覆盖，不回改历史证据。

## 修正及责任

r1/r2 harness 只累计 z≥0.3 的人窗 cohort，漏掉 P 前景中低于 0.3 m 的点，错误报告 clean 吸收 0/PASS。验收 05 的 clean 总吸收≤5 不允许裁剪这个低带；这是 **Codex 检查覆盖遗漏**，不是新增要求。r3 只补全统计 cohort，未改点云、变换、PIPE、matcher、pipeline 或阈值。所有 r1/r2 日志/失败保留。

## 最终逐 ID 结果

唯一验收表：R3.7 `06_test_matrix.md` v1；不复制/改变判据。T37-01/02/03/04/05/05b/06/07/08/09/10/11/12/13/14/15/16/17/18/19/21 均 PASS，逐 ID 见 `03_unit_results_r1.json`；T37-20 PASS，见 `04_shadow_results_r3.json`。

| ID | 最终状态 | 证据 |
|---|---|---|
| T38-01 | PASS | `05_r36_equivalence.log` 原 digest 全等、19/19；`09_artifact_recheck.json` B 最大矩阵/平移差 4.54e-9≤1e-6 |
| T38-02 | PASS | WD01 P=93,423，S=1,754，A=14,966 |
| T38-03 | PASS | WD02 P=159,247，S=24,508，A=104,742 |
| T38-04 | PASS（窗口指标） | f55 高带 2/1248；其余帧/全部带如实登记 |
| T38-05 | **FAIL** | clean 全部 P-foreground 人窗 cohort 共吸收 **31 点**，全部在 z<0.3 带；超过≤5 门。f63 低带 18/284，其他帧见 r3 JSON |
| T38-06 | **FAIL** | native delta=NaN（165 帧），P/S 新 green 61 行、新 purple 70 行，需 GT/逐簇归因 |
| T38-07 | PASS | wrong pair / rewritten reference→非可用状态；SAFE 全帧=P |
| T38-08 | PASS | ARTIFACT_TAMPERED / LEVELING_SHA_MISMATCH，SAFE=P；r1 EXDEV 用 temp copy 修正 |
| T38-09 | PASS | UNAVAILABLE/NO_ARTIFACT，完整输出 digest=P |
| T38-10 | PASS | 重复与 raw/wrong sid 错误码 |
| T38-11 | PASS | r3 S digest 与 r2/run2 相同：`58d9e20ba4176f551cd10970aebcc841ce812e9cbf8c4571c1ad22346a7697c0` |
| T38-12 | PASS | `04_fault_logs_r3.txt` 及 `04_shadow_run_r3.log` |

S1 PASS；S2 PASS；S3 PASS；**S4 FAIL**（并存真人 track/event GT 缺口）；S5 PASS；S6 PASS；**S7 FAIL**。T39/设备/物理/部署/采集 NOT_RUN。r3 shadow 实际 Node exit=1，已按预注册 STOP，不启动 R3.9。

## 收口证据与可审查边界

- 原始 P digest=`d83a784cfa83ae507faca63aed13870f0b0d5b406cb38eaaa2c8b6b9a6ad54fc`；临时故障分支完整计数/簇/track/event 与之相等。
- `08_native_metric_probe.json` 独立最小反例：簇数组 before/after 均 1 簇，native delta 仍 NaN；定位原共享 `human_pipe_lib.js` 的数组相减。这不证明实际发生 165 次分裂。当前代码冻结，不擅改。
- `07_scope_result.json` 对最初全部 4700 个文件（含未跟踪源码/证据/输入）复核，unexpected=[]；仅授权文档与观察到的外部 Console README 日期改动，外部改动保留。原 session/leveling/算法/历史证据 SHA 保持。
- `09_artifact_recheck.json` 新进程核三个 manifest SHA/artifact_id/当前代码 ID，与归档 B 差≤1e-6。
- 新源码 SHA：registration.js `19c1fced9dbeabdefbc20dc8666fec601e3da8a42de68dec2ccdf195865379f5`；registration_method.js `958f646ff41adbca7840a0a09ae6ba2ed87db7254b2d16f5365b64625caac141`；registration.test.js `637d86c56e788103d332caacc35c2ad84940ca003c0a42e04db9ef20b3c5c0ad`。
- ponytail 实读路径 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`，full；复用现有方法/未改 matcher/管线、stdlib、无新依赖。

## 集中返工/设计审查入口

1. 31 个近地点：分解工作空间裁剪/online/reference 吸收，人工区分地面残余与可见人体脚腿；不能把整窗口都冒称人体 GT，也不能忽略既有安全门。注册发生在 workspace 裁剪之前，R3.6 的 reference 查询证据不含这次完整分支重建，需审计此差别；不直接调整 ground 阈值或 B。
2. 原 pipeline 簇数统计缺陷：如另行允许，最小修复统计和回归；聚类/清理数学不改。
3. 新 green/purple：逐簇归因。P 无对应的 126 个确认行包含应去掉的 WD01 静态误报，不能全称人体漏检；GT 不足明确 BLOCKED。
4. gate=DEGRADED/SPARSE_CORRESPONDENCE（trimmed ratio 49.653%）：定义与 provisional 门审查，v1 不调低、不换解、不自动创建 v2。

这些结论是 writer 自验与诊断，未替代独立复审；提交后无其他活动 writer。
