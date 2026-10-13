# Q01 独立审查 — HUMAN-FUSION-UNIFY-R2（作者+独立审查者对照）

2026-10-11 · 审查物：`sidequests/human_fusion_lab/` · 验收表：`docs/human_capture/HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md`、`HUMAN_FUSION_R5_R8_ACCEPTANCE_V1.md`。

## 审查者矩阵

| 审查者 | 角色 | 方法 | 产物 |
|---|---|---|---|
| Claude Code | 作者侧独立实测复核（非自验 PASS） | 静态审查 + 合成/真实会话最小复现（node 直调 detector）、真实 Chrome CDP E2E、HTTP API 边界探测 | `Q01_FINDINGS.json`（作者视角汇总）、`Q01_FIX_REPORT.md`、`Q01_BROWSER_E2E.json` |
| `opencode-go/deepseek-v4.1-flash` | **真正的独立审查者**（不复用作者结论；后台被杀后以前台重启完成） | 独立静态审查 + hook `FusionTracker.tick` 复现 tracker 决策源 + 干净 server 8799 独立 E2E + HTTP 边界 | [`opencode_review_report.md`](./opencode_review_report.md)、[`opencode_findings.json`](./opencode_findings.json) |

**独立审查状态：COMPLETED（非 NOT_RUN）**。OpenCode 不同意"作者已修好"的部分增补了 3 条 P2/P3（F-02/F-04/F-05），其中 F-04（8797 陈旧进程污染证据）导致我复跑并升级了浏览器 E2E 证据到干净环境。

## 九问裁决（作者 ⇄ OpenCode）

| # | 问题 | 作者裁决 | OpenCode 裁决 | 最终 |
|---|---|---|---|---|
| 1 | SESSION vs master 契约 | PASS | PASS（8/8 sid 选择一致，差异仅措辞/`undefined` 不可达） | **PASS** |
| 2 | SHA 守卫阻默认 | PASS | PASS（S09 占位 SHA 暴露 + load 时再哈希阻断） | **PASS** |
| 3 | geometry(post) RF 污染 | P0 实证 | 候选级 PASS + 残留 P2 | **FIXED + 残留 P2** |
| 4 | 几何覆盖后 track/决策一致 | 修复后 PASS | 修复后按构造一致（候选级） | **PASS（候选级）** |
| 5 | 6 detector 同契约 | PASS | PASS（max_err 9.18e-8，缺模型回退） | **PASS** |
| 6 | seek/rewind/switch 清状态 | PASS | PASS（前缀重建、E05 generation 递增、E05b counter 归零） | **PASS** |
| 7 | 索引/帧号一致 | PASS | PASS（R5 2605 帧对拍、recorded.frames[i].index===i） | **PASS** |
| 8 | R7 独立会话分组/泄漏 | PASS | PASS（9 会话互斥 4/1/2/1/1、fit 仅 train、UNKNOWN 不入训） | **PASS（残留 UNKNOWN）** |
| 9 | R8 层次损失真实/UNKNOWN 计入成功 | PASS | PASS（DISPLAY='UNKNOWN' 不计分、unknown_frames 单列、label===null 不入训） | **PASS（残留 UNKNOWN）** |

## P0 复核（作者 98.7% 错位声明）

- **作者实测**：修复前 8 合格会话、6520 带 track_id 候选中 **6436（98.7%）** `track_confirmed` ≠ 最终 `classifier_decision`；合成最小复现 30 帧 28 错位。
- **OpenCode 独立复核**：hook `FusionTracker.tick` 证实 tracker 输入是 `CONFIRMED_HUMAN`（engine/RF），detector 事后覆盖为 `HUMAN_CANDIDATE`——根因同作者；修复后候选级 mismatch=0。
- **结论**：原 P0 **真实存在**（影响 C05/R602），当前修复到候选级自洽；残留 P2（显示轨迹与内部 tracker 分歧、geometry 永不确认）已接受为研究型后处理对照语义。

## 关键独立发现（作者未列出，OpenCode 增补）

| ID | 严重度 | 发现 | 处置 |
|---|---|---|---|
| Q01R-02 / Q01-F02-residual | P2 | 修复是显示层自洽，底层 `FusionTracker` 内部仍按 RF 投票；几何门从不产出 `CONFIRMED_HUMAN` → geometry 永不确认轨迹、UI 不画紫色确认轨迹、`gt_diff.tracks` 恒 0。 | **接受为研究型后处理对照**（won't-fix；不改冻结 engine）。作者全量复验：geometry@S3 `gt_diff.tracks.tp=0/fn=1`，对照 rf51 tp=1。 |
| Q01R-04 / Q01-F04 | P2 | 127.0.0.1:**8797** 陈旧未修复 server（PID 15076）仍监听，`cdp_e2e.js` 默认端口正是 8797 —— 任何复用者可能命中间接旧代码。 | **已修**：kill 15076；干净 8799 重跑 E2E；Q01_BROWSER_E2E 证据升级为干净环境结论。 |
| Q01R-05 / Q01-F05 | P3 | geometry 审计标记（`_rf_decision`/`track_semantics`）未透出 API。 | **已修**：`server.js` 透出；干净 8799 复验 `track_semantics=overridden_by_geometry_posthoc` + `rf_decision` 对照值。 |

## 最终明确回答（作者与 OpenCode 一致）

- **(a) geometry(post) 的 track/决策错位是否真缺陷？** —— 原缺陷**真实**（UI 同屏两套真值，影响 C05/R602）。当前修复使候选级自洽（mismatch=0），可判 P0 已关闭；残留 P2 使 geometry 仅限研究型后处理对照，不得作纯几何生产基线。
- **(b) R7 是否存在泄漏？** —— **会话级无泄漏**（9 会话互斥 4/1/2/1/1、fit 仅 train、UNKNOWN 不入训）；前瞻跨场景/陌生人员泛化 **UNKNOWN**（RETROSPECTIVE_SESSION_HOLDOUT）。
- **(c) R8 是否把 UNKNOWN 当成功？** —— **未计入**（DISPLAY='UNKNOWN' 字符串不计分、unknown_frames 单列、label===null 不入训、评估跳过 UNKNOWN 类）；DISPLAY 层真人损失 **UNKNOWN**。
- **(d) 生产接入是否继续 BLOCKED？** —— **继续 BLOCKED**（geometry 仅研究对照、R7 回顾性、R8 DISPLAY UNKNOWN、RKNN/NPU/RK3588 未实测、S9 GT 不符、本轮无生产链授权改动）。

## 证据清单

- 作者：`Q01_FINDINGS.json`、`Q01_FIX_REPORT.md`、`Q01_BROWSER_E2E.json`、`test_geometry_consistency.js`（新增）、`run_unify_tests.js` 8/8
- 独立审查：`opencode_review_report.md`、`opencode_findings.json`、`opencode_run.log`（真实调用日志）
- 过程日志：`opencode_run.log`（第一次后台被杀，技术中断未产出）、`opencode_run2.log`（前台重启后产物）
