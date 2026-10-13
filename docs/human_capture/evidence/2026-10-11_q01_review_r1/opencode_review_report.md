# Q01 独立审查报告 — HUMAN-FUSION-UNIFY-R2 / R5-R8

审查者：`opencode-go/deepseek-v4.1-flash`（独立，不复用作者结论）
工作区：`sidequests/human_fusion_lab`（只读消费；未改动任何 `pc_apps/`、`src/`）
时间：2026-10-11
方法：源码静态审查 + 本机独立复跑（Node 直调 detector / 真实 Chrome CDP 端到端 / HTTP API 边界探测）

## 0. 复跑环境与命令（本报告一手证据）

| 项 | 值 |
|---|---|
| Node | 本机（Windows），`node` 直跑 |
| Chrome | 154.0.8037.99，`--headless=new --remote-debugging-port=9223` |
| 干净 demo server | `node server.js 8799`（避开 8797 陈旧进程） |
| E2E | 副本 `cdp_e2e.js 9223 8799`（不覆盖 lab 内证据文件） |
| 几何探针 | 独立脚本直调 `createDetector` 跑真实会话（未写回 lab） |

关键独立复跑结果：
- `node test_geometry_consistency.js` → **PASS，mismatch=0**（合成 30 帧）。
- 真实会话 `cap_20261010_175429`（S3，258 帧）几何探针：
  - `geometry(post)`：带 track_id 候选 **651**，`CONFIRMED_HUMAN=0`，**candidate 级 mismatch=0**，`track_confirmed=true` **0**；
  - 但**显示 `_tracks.human_confirmed` 与底层 `FusionTracker` 内部状态分歧 635 / 806 帧**（内部 confirmed=775，显示 confirmed=0）。
  - 对照 `rf51_baseline`：651 候选，`mismatch=12`（均为 track 投票未满 3 票的**合法预热期**），内部/显示分歧 0。
- 真实 Chrome E2E：**E01–E09 全 10/10 PASS，exit 0**（对 8799 干净 server 与 8797 陈旧 server 各跑一次，均 10/10）。
- HTTP API 边界：干净 server `geometry` @ S8 idx30 → 候选 `decision=HUMAN_CANDIDATE,track_confirmed=false`，track `human_confirmed=false`（自洽）；陈旧 8797 server 同请求 → `track_confirmed=true`（**旧未修行为**，见 F-04）。

## 1. 九个必审问题逐条裁决

| # | 问题 | 裁决 | 理由（最小复现） |
|---|---|---|---|
| 1 | SESSION 适配 vs master `session_selection.js` 语义等价 | **PASS** | 差分对拍（含 `null/undefined/''/合法/非法/clip 后缀`）：`sid` 选择 8/8 完全一致；`valid_sid` 正则、过滤、dedup、desc 排序逐行同律。差异仅：措辞（"本地最新会话" vs "最新有效会话"）、`undefined` 被适配层当作非显式（master 仅在 `===null` 时非显式，且 `URLSearchParams.get` 不会返回 undefined，实际入口不可达）、以及有意的 SHA 特化。复现：`q01_choose_diff.js`。 |
| 2 | SHA 守卫能否阻止失效/损坏会话成为默认（非仅标黄） | **PASS** | 用真实 AUDIT 行复现：`default_sid=cap_20261010_180557`，`sha_mismatch_sids=["cap_20261010_180751"]`（S9 的 declared points SHA 为占位 `aaaa…`）。`server.js:8` 装载时再哈希磁盘，磁盘变更即 `throw`，非静默默认。 |
| 3 | `geometry(post)` 是否污染/错配 RF 决策与 tracker 状态 | **部分（PASS 候选级 / 残留 P2）** | candidate 级已自洽（mismatch=0），但覆盖只改**显示**：底层 `FusionTracker` 内部票仍按 RF 投票，覆盖后 `d._tracks` 被强制 `human_confirmed=false`，S3 上 635/806 帧显示与内部不一致；且几何门（`classify_human` 只发 `HUMAN_CANDIDATE`/`NON_HUMAN`，`human_pipe_lib.js:624`）从不产出 `CONFIRMED_HUMAN` → 几何 detector 永不确认任何 track。详见 F-02。 |
| 4 | 覆盖后 `track_confirmed`/`human_confirmed` 是否与最终 `classifier_decision` 一致 | **PASS** | 修复后按构造一致：`detector.js:23` 令 `track_confirmed=(dec===CONFIRMED_HUMAN)`，`detector.js:24` 同步 `_tracks`。真实 S3 实测 candidate 级 mismatch=0。注意该不变量对普通 detector **不成立**（rf51_baseline 12 例合法预热差），仅对 geometry 成立，见 F-03。 |
| 5 | 6 个 detector 同一 Proposal 输入/输出契约 | **PASS** | `DEMO_CONFIG.detectors` 6 项（xgb69_candidate/rf51_baseline/rf51_candidate/rf69_candidate/xgb69_unique/geometry）全部走同一 `UnifiedEngine({mode:'FUSION'})`+`schema.make_frame_context`；69 维=51+`extra()`；`MODEL_PARITY` 6 模型×200 样本 max_err=9.18e-8，缺模型回退 PASS。 |
| 6 | seek/rewind/session/model 切换是否清除旧 tracker/history/generation | **PASS** | `server.js:9` 后退即 `det.begin(sid)`、`last=-1` 前缀重建；`demo.html:19` `change()` 清 `history`、`index=0`、`epoch++`。E05 实测 generation 1→2、E05b counter 归零。 |
| 7 | `/api/frame`、DOM、GT、candidate、track 索引对齐 | **PASS** | `recorded.frames[i].index===i`（`export.js:23` 按 `s.frames` 顺序推入），`server.js:12` 同索引取 `session.frames[index]`/`recorded.frames[index]`；E04 中段候选 `indices` 齐备，E08 点检含 `point_indices_preview`；R5 2605 帧 raw indices/count/bbox 一致。 |
| 8 | R7 是否真正按独立会话分组、有无 train/val/test 泄漏 | **PASS（残留 UNKNOWN）** | `AUDIT.splits` 为 4/1/2/1/1 共 9 会话、互斥覆盖全部 9（`audit.py:19-20` 断言唯一）；train.py 仅用 `splits.train` 拟合，UNKNOWN 标签不入训。无会话级泄漏。残留：holdout 为 `RETROSPECTIVE_SESSION_HOLDOUT`，跨场景/陌生人员前瞻 UNKNOWN。详见 F-07。 |
| 9 | R8 各层损失是否真实、UNKNOWN 是否被计入成功 | **PASS（残留 UNKNOWN）** | `attribution.js` 的 `DISPLAY` 是字符串 `'UNKNOWN'`（非 0，不计入任何 PASS 指标），`loss_counts` 为 RAW/BG/PROPOSAL/CLASSIFIER/TRACKER/NONE 真实分层计数，`unknown_frames` 单列；`train.py` 过滤 `label===null`；`evaluate_fusion_gt` 跳过含 UNKNOWN 类与不确定区间。详见 F-08。 |

## 2. 作者候选 P0（geometry 98.7% 错位）独立复核结论

**原 P0 真实存在，当前已修复到"候选级 0 错位"**，但复核发现修复是**显示层自洽**而非语义闭环：

1. 修复前：`tick` 内 tracker 已按 RF 决策投票，插件事后改 `classifier_decision`，`track_confirmed` 未同步 → UI 同屏两套真值。此点确为真实界面/契约缺陷（影响 C05、R602）。
2. 修复后（`detector.js:18-25`）：显式同步 `c.track_confirmed` 与 `d._tracks[*].human_confirmed`，并用 `track_semantics='overridden_by_geometry_posthoc'` 标注。实测候选级 mismatch=0，**达标**。
3. 残留（F-02，P2）：覆盖只作用于返回值，**不改底层 `FusionTracker` 内部状态**；且几何门从不产出 `CONFIRMED_HUMAN`，于是所有被覆盖的 track 被强制 `human_confirmed=false`。S3 实测内部 confirmed 775 / 显示 confirmed 0，分歧 635/806。后果：`geometry` detector 下 UI 永不画紫色确认轨迹、`gt_diff.tracks` 恒为 0。该行为与"研究型后处理对照"标签一致，但**不得当作纯几何生产基线**。

## 3. 额外独立发现

- **F-04（P2，证据完整性）**：`127.0.0.1:8797` 存在**陈旧未修复 server 进程（PID 15076）**仍在监听。对它的 `/api/frame?...model=geometry` 返回 `decision=HUMAN_CANDIDATE` 却 `track_confirmed=true`（修复前行为）。`start_demo.cmd` 用 8791，`cdp_e2e.js` 默认 demo 端口恰为 8797 —— 任何复用 8797 的复跑都可能命中间接旧代码。**必须核对端口/进程后再采信 API 证据**。
- **F-05（P3）**：`_rf_decision`、`track_semantics` 等审计标记只在 detector 对象上，`server.js:14` 未透出到 `/api/frame`；UI 仅靠 detector 名 `geometry(post)` 传达"后处理对照"语义。
- **F-06（P3，信息）**：`session_adapter.choose` 把 `undefined` 当非显式（master 只在 `===null` 时非显式），措辞亦不同；不影响真实入口（`URLSearchParams.get` 只会给 `null|string`）。

## 4. 最终明确回答

**(a) geometry(post) 的 track/决策错位是否真缺陷？**
是——原缺陷为真（UI 同屏展示互相矛盾的 `classifier_decision` 与 `track_confirmed`，影响 C05/R602）。当前修复使**候选级**自洽（mismatch=0），可判该 P0 已关闭。但残留 P2：显示轨迹不再忠实反映底层 tracker（S3 635/806 分歧）、几何永不确认 track；故 geometry 只能作为**显式标注的研究型后处理对照**，不得作为纯几何生产基线，也不应用于对外结论。

**(b) R7 泄漏？**
未发现 train/val/test/stress 会话级泄漏：9 会话互斥划分（4/1/2/1/1），拟合仅用 train，UNKNOWN 不入训。但 holdout 为回顾性（历史测试会话曾被人查看），跨场景/陌生人员前瞻泛化仍 **UNKNOWN**。

**(c) R8 UNKNOWN 处理？**
未把 UNKNOWN 计入成功：DISPLAY 层显式为 `'UNKNOWN'` 不计分，`unknown_frames` 单列，候选级 `label===null` 不入训，评估跳过未标/UNKNOWN 类帧。可接受；DISPLAY 层真人损失仍为 **UNKNOWN**（无物理 GT）。

**(d) 生产接入是否继续 BLOCKED？**
**继续 BLOCKED。** 依据：geometry 仅研究型后处理对照；R7 回顾性 holdout、跨场景/人员 UNKNOWN；R8 DISPLAY 真人损失 UNKNOWN；RKNN/NPU/RK3588 未实测（`NOT_RUN/UNKNOWN`）；S9 GT 绑定不符 `BLOCKED`；本轮无生产链授权改动。多项 BLOCKED/UNKNOWN 未清零。

## 5. 与作者结论的差异（独立价值）

| 作者结论 | 本审查结论 |
|---|---|
| Q01-F01 "CONFIRMED → FIXED" | 候选级 **AGREE（fixed）**；但补充 P2 残留：显示轨迹与内部 tracker 分歧 635/806，geometry 永不确认，须保持 research-only。 |
| Q01-F02 "E2E FIXED 10/10" | **AGREE**，且**独立复跑验证**（重跑 cdp_e2e.js 于干净与旧 server 均 10/10）。同时揭示 8797 陈旧进程会污染 API 证据（F-04）。 |
| Q01-F08/F09 "R7/R8 PASS" | **AGREE（会话级无泄漏/UNKNOWN 未计成功）**；残留前瞻与 DISPLAY UNKNOWN 照旧。 |
| 作者 Q01_FINDINGS summary "pass 7 / blocked 1 / unknown 0" | 大体一致；本审查额外增列 3 条 P2/P3（F-02/F-04/F-05），并把 F-02 从未列→列为残留 P2。 |
