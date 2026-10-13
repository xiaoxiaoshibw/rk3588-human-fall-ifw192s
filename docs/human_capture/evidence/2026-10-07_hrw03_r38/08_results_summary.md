# HR-W03 R3.8 自验提交与停止点

2026-10-07，Codex 唯一 writer；SUBMITTED / REWORK_REQUIRED，未 ACCEPTED。用户“继续推进主线”授权范围见 [工单](../../tickets/HR-W03-R38.md)。ponytail 实读路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full）。

## 交付与冻结

新增 `pc_apps/human_replay/registration_method.js`（R3.6 冻结方法提取）、`registration.js`（离线 writer/loader/gate/应用防护）、`registration.test.js`。生产调用入口未接入。新 artifact：`captures/registration/cap_20261002_223757__to__cap_20261004_203349/`；artifact_id `ae5c8f4c021e91665c9e23cedd66730122d5f0552fd794de86a9b5f99e7a5e66`。全部旧 session/leveling/历史证据只读；没有 commit/push/部署/采集。

R1 再审：PASS，`01_r1_reaudit.js` / JSON；TLS-direct 计入后平移限 0.20/0.15 正确。原数学 m3/Jacobi/fineStatic/ppICP/normalResiduals/PP_SCHED 原样提取；fixedICP 默认日程不变，增加明确诊断初值入口；诊断 ppICP refit 只出质量指标，不替换 B。writer 两侧 job 显式绑定，加载校验 session SHA、job/transform_id/三 SHA、refmap digest、代码 ID、gate 快照；故障数据只改临时副本。

## 逐 ID 结果（唯一基准仍为 R3.7 06 v1）

`03_unit_results_r1.json` 覆盖 T37-01/02/03/04/05/05b/06/07/08/09/10/11/12/13/14/15/16/17/18/19/21，各 PASS；T37-20 实测方向在 `04_shadow_results_r2.json`，PASS。共 22 个 ID（原文“21 项”未计额外 05b，数量不替代验收）。

| ID | 状态 | 原始证据 |
|---|---|---|
| T38-01 | PASS | `05_r36_equivalence.log`，原工具 `--digest-only` 本轮实际退出 0；digest 完全等于 `23830edefcb28f04774e328af64abce014dfeff35df75462f8a6f68d68eb3357`，19 自检全过；B canonical 对账由 writer 采用同一默认 fixedICP |
| T38-02 | PASS | WD01 P=93,423、S=1,754、A=14,966；S≤0.5A 且≤P |
| T38-03 | PASS | WD02 P=159,247、S=24,508、A=104,742；S≤0.5A 且≤P |
| T38-04 | PASS（窗口指标） | f55 高带吸收 2/1248=0.160%；f150/155/160 高带 0/154、71/1409、40/475；混合带完整登记 |
| T38-05 | PASS | 10 帧 clean P-foreground 人窗 cohort 总吸收 0 |
| T38-06 | FAIL | 165 帧 native `cleanup_split_delta` 都为 NaN（JSON=null）；几何对应检查新增 green 61 行、purple 70 行；不将它们直接称为误报 |
| T38-07 | PASS | wrong source / rewritten reference identity 被拒；SAFE 全帧 digest=P |
| T38-08 | PASS（r2） | 字节篡改 ARTIFACT_TAMPERED；复制 leveling 后篡改 LEVELING_SHA_MISMATCH；SAFE=P。r1 跨 C/D 盘硬链接 EXDEV 的环境失败保留，r2 改复制 |
| T38-09 | PASS | no artifact UNAVAILABLE；SAFE=P，完整计数/簇/track/event digest 同一 |
| T38-10 | PASS | duplicate、raw/wrong sid 两错误码触发 |
| T38-11 | PASS | S 两次 digest `58d9e20ba4176f551cd10970aebcc841ce812e9cbf8c4571c1ad22346a7697c0` |
| T38-12 | PASS | `04_fault_logs_r2.txt`；DEGRADED/失败原因与质量/变换日志显式输出 |

新增单元命令退出 0。原 `human_pipe_lib.test.js` 35/0、`human_replay_lib.test.js` 45/0，退出 0；既有回归未揭露 native 全链统计字段的类型错误。shadow r1/r2 都退出 1，最终保留真实 T38-06 FAIL，不因其他测试过就宣布收口。

## S1–S7

S1 PASS；S2 PASS；S3 PASS；S4 **BLOCKED**（clean/f55 通过，真人 track/event GT 不足）；S5 PASS；S6 PASS；S7 **FAIL**。R3.9/T39、设备/物理/部署/采集一律 NOT_RUN。

## 当前质量门与 PROVISIONAL 复核

5938/11959=0.4965298102，inlier_ratio band=WARN，loader=DEGRADED，原因 SPARSE_CORRESPONDENCE。fit/holdout p50=14.522/11.088 mm，coverage=0.78499，max_sector_share=0.41916，condition=104.27199，eig_ratio=0.0095903。方向同对应集前向 0.014522 m、逆用 0.116701 m。

六项 provisional 已有实测：n_correspondence/coverage/sector 与 geometry 有余量（geometry pass 门约 96×余量，超过设计的 3×），但 inlier_ratio 距 0.50 pass 门不足。**v1 常量不改，不能为结果翻转把 0.50 调低**；未取得生产可消费的冻结放行。所有 physical_verified/extrinsics_verified/runtime_eligible 仍 false。

## 集中阻断与下一步

1. **T38-06 / S7**：原 `human_pipe_lib.js` L738 对两个簇数组做减法，不是长度相减，native metric 变 NaN；这不是证据证明实际发生 165 次分裂，而是共同门的报告值无效。本单 PIPE/管线代码冻结，因此不擅改共享库。下一返工应单独许可最小“簇数统计”修复、补真实整链回归；无需调 matcher/聚类数学。
2. **T38-06 / S7**：S/P 新增确认需逐簇归因，可能含召回改善、家具残块、坐标变换/簇变化，不可全部当误报或全部当人体。保存全部输出。
3. **S4**：P 已确认但 S 无对应的 126 行中包含有意去掉的 WD01 静态误报（示例 P_track=2，XY≈3.50,-0.76）。它们不等于 126 个人体漏检；缺少真人轨迹 GT 时不宣布“人体不丢”。
4. **DEGRADED**：生产放行需对预注册支撑定义/trimmed ratio 作设计审查；不自动开 v2、不重调 ICP。

以上集中结果是 writer 自验，不冒称独立复审或 ACCEPTED；按预注册 STOP 停在 R3.8，不启动 R3.9。人体识别后续计划已登记 [`HUMAN_RECOGNITION_NEXT_STAGE_PLAN.md`](../../HUMAN_RECOGNITION_NEXT_STAGE_PLAN.md)。
