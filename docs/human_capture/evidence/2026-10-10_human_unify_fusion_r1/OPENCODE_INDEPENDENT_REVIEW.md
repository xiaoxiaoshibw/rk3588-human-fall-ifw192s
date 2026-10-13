# OPENCODE_INDEPENDENT_REVIEW — 独立审计圆润

2026-10-10。**实际跑** `opencode run -m opencode-go/deepseek-v4.1-flash --agent plan --format json` （调用同 R2 `run_opencode_review.py`, 只读 review), exit=0。
原始输出: `opencode_review_01.jsonl`（R2 路径的既有产物是对 R2 prompt 的既审, 本工单 prompt 见 `opencode_review_prompt_01.md`）。

## 审计内容全覆盖点

OpenCode 实际执行了:
- 读工单 docs + 生产 rf_person/human_pipe/detect_overlay + 融合 fusion.js + test_fusion_specific
- 实际跑 `run_all_tests.js` → exit=0 (7/7 96 断言)
- 独立重跑 A/B 对拍 (8/9 — 1 会话输入缺失) → exit=0
- 核对 SHA/守卫/报告一致性

## 审计点名认定 (PASS)

| 项 | OpenCode 判定 |
|---|---|
| R01–R08 全链功能修复 | PASS (软件) |
| 96 断言 | PASS (exit=0) |
| A/B 对拍 8/9 | PASS (1 会话输入缺失) |
| Q01 独审 | PASS |
| FUSION 注入不污染 BASE / R 件 | PASS (明确「该范围漂移不是 fusion 写入缺陷」) |

## 审计点名 BLOCKED / NOT_RUN (按 R2 语义）

| 项 | OpenCode 判定 |
|---|---|
| S01 | **BLOCKED** (当前实现与 R1 冻结 SHA 依序不匹配; 不是 fusion 代码缺陷, 是范围漂移) |
| S02 | **BLOCKED** (preservation_01/02 以记录外部改写、子本工单覆盖) |
| GT_EVALUATION | 无 GT 数据, 不可评估 |
| D01 (设备/物理/部署) | NOT_RUN |

## 治理观察 (缺陷)

OpenCode 发现:
1. **`captures/remote/cap_20261004_203135` 输入已消失** — R1 runs_03 里 9 会话该会话不在 `captures/remote/` (推测人为清除), 影响 `test_baseline_parity.js` exit=1, 但本工单未使用, F4 只用新 9 会话。
2. **R1 冻结 SHA 与当前树漂移**: `engine.js/runner.js` 被 FUSION 工单注入修改 (预期), OpenCode 明确「后续融合轮改写, 不是 fusion 写入缺陷」。本工单同启只负责 fusion 本身。
3. **`run_opencode_review.py` 未为 fusion 工单独立调起** — 本工单实际补写 `opencode_review_prompt_01.md`, 但上游调用打印 review 提示词还是 R2 路径 (该项是治理, 已在本目录重调).
4. **治理建议**: FUSION 工单未在 `docs/human_capture/tickets/` 登记。已在 FINAL_REPORT.md 补全交付清单填补。

## 本轮 FUSION 之外审计建议

- F3 (RF v2) 与 GT 冻结后需重跑一轮独审 (现无 GT, 无资格）。
- 设备/部署 (D01) 按工单 §8 明确 NOT_RUN。

结论: **无软件 FAIL, 整体依然是「FUSION 功能修复可提交复审」, 不主张 ACCEPTED。**
