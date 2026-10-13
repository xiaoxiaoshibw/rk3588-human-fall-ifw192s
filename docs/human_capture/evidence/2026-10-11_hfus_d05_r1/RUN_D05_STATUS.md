# HFUS-D05 阶段进度快照（预登记后，回归完前）

> 2026-10-11 主控接管。授权正文：`docs/human_capture/tickets/HFUS-D05.md`；预登记：`BASELINE_D05.md`；SHA：`BASELINE_SHAS.json`。

## 已交付/在跑

| 项 | 状态 |
|---|---|
| 授权接收 + 工单登记 | ✅ `tickets/HFUS-D05.md` |
| 预登记冻结（变体/口径/降级条件）| ✅ `BASELINE_D05.md`；SHA `BASELINE_SHAS.json`（58 文件） |
| ponytail skill | ✅ 主控 + Agent A/B/C 均已加载并记录使用 |
| 逐点阶段归因探针 | ✅ `eval/baseline.js` 实跑 8 会话，落 `baseline_probe/PROBE_SUMMARY.json` + 8 份 `PROBE_<sid>.json`（真实逐点数据，见下表） |
| Agent A（UNKNOWN 自适应重判）| ✅ `d05/hook_unknown.js` 交付（自检 PASS）；已按其代理回传 + 补 `ponytail` 标记的网格桶优化（去 O(N²) 直扫），避免把 p95 拉到不可接受 |
| Agent B（候选感知 CLEANUP）| ✅ `d05/hook_cleanup.js` 交付（3 场景自检 PASS）；首轮全链路烟测触发「cleanup 输出必须保持输入子序列」契约 (`engine_b.js:34`) — 已修：按原始 xyzi 顺序原位合并救援点，自检仍 PASS，三会烟测通过 |
| Agent C（时序前景恢复）| ✅ `d05/hook_temporal.js` 交付（自检 PASS 覆盖 gap 重置 / still 注射 / begin_session 复位）；三会烟测通过 |
| D05 runner | ✅ `d05/run_d05.js`（base 引用 D04，不重复跑；S9 永远 exploration-only） |
| 烟测 | A06 / B / C 各三会（家具/near/静人）真实链路全通 |

## 实测探针结果（GT PERSON，source=="human"，覆盖 8 正式会话）

| sid | activity | GT 点 | BG keep | cleanup keep | 成分 | 主导丢失原因 |
|---|---|---|---|---|---|---|
| 175429 | S3-walk-x-near | 286822 | **43.1%** | 43.1% | 67.7% | no_ref_XY_support_UNKNOWN 149937 / bg_match 4253 |
| 175553 | S3-walk-y-far | 561361 | **94.9%** | 94.9% | 96.5% | no_ref_XY_support 6312 |
| 175804 | S4-walk-stop-walk | 13327 | **43.1%** | 43.1% | 63.7% | no_ref_XY_support 7194 |
| 175943 | S5-turn-in-place | 8841 | **0.3%** | 0.3% | 0.3% | no_ref_XY_support 8552 |
| 180235 | S6-occlusion | 27268 | **80.7%** | 80.7% | 89.2% | no_ref_XY_support 3141 / bg_match 1492 |
| 180337 | S7-far-5m | 24361 | **25.4%** | 25.4% | 74.7% | no_ref_XY_support 16986 |
| 180557 | S8-still-retention-long | 57045 | **69.3%** | 69.3% | 92.8% | no_ref_XY_support 16356 |
| 175227 | S1-empty-with-furniture | 0（家具场景无 PERSON 真 GT 点） | — | — | — | 历史 FP 高、复评重点 |

结论（题书 §1 的根因答案）：
- UNKNOWN XY 支撑是**唯一主要损失源**（靠 no_reference_XY_support_UNKNOWN 杀掉 43.1–99.7% GT 人在 5/8 会话上）。
- cleanup 在现行所有会话中**零额外删除**（cleanup keep = BG keep），与 D04 「cleanup 误删孤零零但属人体的有效点」的假说**相反**；cleanup 只作为「随后接得上」的保护器存在。
- 家具（bg_voxel_match 到家具点）与远端稀疏复合效应在 near/S5/S7 明显。

## 队列中（后台）

- 九会话全量：`a03`（重跑拿归一化输出行，原跑已完成且 ledger 完整）、`b`、`a06`、`c`、`abc`。预计按序落 `runs/<variant>/`，然后 `make_regression.js` → `REGRESSION_FINAL.json` → `demo_d05.html` → `returns/HFUS-D05.md`。

## 边界与未闭合

- 保留脏工作树；不 commit/push；不动 D04/生产/旧证据；S9 永远只 exploration。
- 不可能 / 未授权/未完成的事一律 NOT_RUN/BLOCKED，不包装成 PASS。
- 下一步在全部变体跑完后给「成功/失败案例帧 + 家具误检变化 + P50/P95 + 逐层损失归因」的完整账。
