# HUMAN-FUSION-UNIFY-R2 —— Q01 独立审查简报（给审查者）

你是独立审查者。不要复用我（作者 Claude）的结论；请阅读以下来源码与证据，自己形成判断并输出真实缺陷清单。裁决只允许 PASS / FAIL / BLOCKED / UNKNOWN，且任何 FAIL 必须给最小复现路径。

## 范围（本地隔离研究区，无生产写权限）
- 目录：`sidequests/human_fusion_lab/`
- 不允许修改：任何 `pc_apps/`、`src/`、部署/板端/生产识别链文件。

## 必读源码（本轮新增/修改）
- `session_adapter.js`、`server.js` —— SESSION 契约归一与 SHA 守卫
- `detector.js`、`static_path.js`、`unique_tracker.js` —— 6 个可切换 detector 的接口/回退/后处理
- `core/engine.js`、`core/schema.js`、`core/fusion.js`、`core/evaluate_fusion_gt.js`、`core/leveling.js`、`core/data_loader.js`
- `evaluate.js`、`train.py`、`audit.py`、`attribution.js` —— R7 分组/泄漏审查、R8 归因
- `cdp_e2e.js`、`test_session_contract.js`、`test_models.js`、`test_r5.js`、`run_unify_tests.js`
- `demo.html` —— 浏览器 UI 与深链/回退

## 必读证据
- `sidequests/human_fusion_lab/results/AUDIT.json`（分组/冻结/资格声明）
- `sidequests/human_fusion_lab/results/UNIFY_REGRESSION.json`、`R5_TEST.json`、`MODEL_PARITY.json`、`TRAIN_REPORT.json`、`ATTRIBUTION.json`、`REPLAY_COMPARISON.json`、`DEMO_BROWSER_E2E.json`、`LAB_E2E_UNIFY.json`

## 验收表（自验 SUBMITTED、未 ACCEPTED）
- `docs/human_capture/HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md`（C01–C11、Q01、D01）
- `docs/human_capture/HUMAN_FUSION_R5_R8_ACCEPTANCE_V1.md`（B01–R804、Q01、D01、P01）

## 必须重点审查的 9 个问题
1. SESSION 适配是否与 `pc_apps/human_replay/session_selection.js` 的 master 契约一致（不仅是测试镜像，而是语义等价）。
2. SHA 守卫是否能阻止失效/损坏会话成为默认（而不仅是标黄）。
3. `detector.js` 的 `geometry(post)` 是否污染/错配 RF 决策与 tracker 状态。
4. 几何决策覆盖后，tracker 的 `human_confirmed`/`track_confirmed` 是否与最终 `classifier_decision` 一致（响应体里 demo.html 直接展示）。
5. 6 个 detector 是否遵循同一 Proposal 输入与输出契约（schema、字段、单位、阈值语义）。
6. seek / rewind / session switch / model switch 是否彻底清除旧 tracker、history、generation 状态。
7. `/api/frame`、DOM、GT、candidate、track 的索引与帧号是否一致（尤其 `recorded.frames[index]` 对 session.frames 的对齐）。
8. R7 是否真正按“独立会话”分组、是否存在 train/val/test/stress 泄漏；`evaluate.js`/`train.py` 的 split 是否可信。
9. R8 各层损失是否由真实数据支持；UNKNOWN 是否被错误计入成功（尤其 `attribution.js` 的 `DISPLAY:'UNKNOWN'` 与 `RAW/BG/PROPOSAL` 归类）。

## 我已实测发现的一个候选 P0（请你独立复核，别照抄）
- `detector.js` 的 `geometry(post)` 在 tick 后改写 `_candidates[*].classifier_decision`，但 tracker（engine 内或 `unique_tracker.js`）在此之前已按原 RF 决策投票。实测 8 个合格会话 5232 帧、6520 个带 track_id 的候选中，**6436 个（98.7%）** 的 `track_confirmed` 与 `classifier_decision==='CONFIRMED_HUMAN'` 不一致。请复核这是否为真实界面/契约缺陷，以及它影响几号验收条目。

## 已知且不再是缺陷（请勿重复报告）
- instance 级 tracker 换装（`unique_tracker.install`）实测**未**污染 prototype；模型切换不会"运行后再切 tracker 失效"。该方向我不认定为 bug。
- `DEMO_BROWSER_E2E.json` 状态为 FAIL、E01–E09 阻塞。作者已定位为 CDP 表达式上下文问题并准备独立修复；你只需验证修复后的 `Q01_BROWSER_E2E.json` 是否真的全绿。

## 输出契约（Q01）
把以下文件写到 `docs/human_capture/evidence/2026-10-11_q01_review_r1/`：
- `opencode_review_report.md`：你的独立结论（逐条问题给 PASS/FAIL/BLOCKED/UNKNOWN + 理由 + 最小复现）。
- `opencode_findings.json`：机器可读问题清单（id、severity、file、line、verdict、repro、accepted_or_rejected）。
- 在结尾明确：geometry(post) 差异、R7 泄漏、R8 UNKNOWN 处理、生产接入是否应继续 BLOCKED。
