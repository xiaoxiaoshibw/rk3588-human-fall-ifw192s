# Q01 修复报告 — HUMAN-FUSION-UNIFY-R2 缺陷闭环

2026-10-11 · writer: Claude Code · ISOLATED 研究轮（唯一 writer=Claude）· 仅改 `sidequests/human_fusion_lab/` 隔离代码及测试，未触碰 `pc_apps/`、`src/`、部署/板端/生产识别链。

## 修复范围与根因

| ID | 严重度 | 缺陷 | 根因 | 修复（最小 diff） | 复测 |
|---|---|---|---|---|---|
| Q01-F01 | **P0** | geometry(post) 决策/track 状态错位 | `detector.js` 在 `tick` 后覆盖 `classifier_decision`，但 tracker（`engine`/`unique_tracker.js` 在 `tick` 内部）在此之前已按被覆盖前的 RF 决策投票；`_tracks.human_confirmed` 与候选 `track_confirmed` 未同步重写，UI 同屏两套矛盾真值（作者实测 6520/6520 带 track_id 候选中 6436（98.7%）错位；OpenCode hook `FusionTracker.tick` 复现 `in_dec=CONFIRMED_HUMAN` → override 后 `tc` 与 `dec` 不一致）。 | `detector.js` geometry 分支：覆盖 decision 后同步重写 `c.track_confirmed` 与 `_tracks` 中对应 track 的 `human_confirmed`；保留 `_rf_decision` 供对照；detector 元数据 `track_semantics='overridden_by_geometry_posthoc'`。 | `test_geometry_consistency.js`（红→绿）；作者全量复验 mismatch=0（6520/6520，0.00%）；`run_unify_tests.js` 8/8 PASS；干净 8799 server E2E 10/10；OpenCode 独立复验候选级 mismatch=0。 |
| Q01-F02 (P1) | **P1** | 真实浏览器交互 E2E 从未通过（`DEMO_BROWSER_E2E.json` status=FAIL, fatal="first frame timeout"） | (a) `cdp_e2e.js` 等待条件 `window.frame!==undefined` 永假——`demo.html` 用 `let frame`（不产生 window 属性；`Object.prototype.hasOwnProperty.call(window,'frame')=false` 但 `typeof frame==='object'`）。(b) `demo.html` 非法 sid 的回退提示在 `update()` 第一行被 `'正在回放…'` 覆盖，用户看不到"回退"。 | (a) `cdp_e2e.js` 全部 8 处 `window.frame` → `typeof frame!=='undefined' && frame`（读裸 declarative binding，不改页面）。(b) `demo.html` 引入 `pendingFallbackNote`，回退提示追加到最终 status（不覆盖）。 | `cdp_e2e.js` E01–E09 **10/10 PASS, exit 0**（先对 8797、再对干净 8799 各一次）；`Q01_BROWSER_E2E.json` status=PASS, checks_pass=10/10。 |
| Q01-F04 | **P2** | 陈旧 server 进程污染 API/E2E 证据（OpenCode 独立发现） | `127.0.0.1:8797` 有未修复 server（PID 15076）监听，返回修复前行为；`cdp_e2e.js` 默认端口恰为 8797。 | kill PID 15076；干净 8799 + 修复代码重跑 E2E；`Q01_BROWSER_E2E.json` 更新为干净环境结论（`evidence_hygiene` 字段如实记录）。 | 干净 8799 E2E 10/10 PASS；geometry@S8 实测 candidate 级 `track_confirmed=false` 与 `HUMAN_CANDIDATE` 自洽（修复生效）。 |
| Q01-F05 | **P3** | geometry 审计标记未透出 API（OpenCode 增量） | `_rf_decision`/`track_semantics` 只在 detector 对象上，`server.js` 未透出，外部审计者无法通过 API 区分 geometry 的对照语义。 | `server.js` `/api/frame` 响应加 `track_semantics`（默认 `'native'`，geometry 透出 `'overridden_by_geometry_posthoc'`）；候选若有 `_rf_decision` 则透出为 `rf_decision`。 | 干净 8799 复验：`track_semantics=overridden_by_geometry_posthoc`、候选 `rf_decision=CONFIRMED_HUMAN`（对照值）均透出。 |

## 接受为残留（won't-fix，已记录并标注）

| ID | 严重度 | 残留 | 处置理由 |
|---|---|---|---|
| Q01-F02-residual (Q01R-02) | **P2** | geometry(post) 显示 `_tracks` 与底层 `FusionTracker` 内部状态分歧（S3 内部 confirmed=775 vs 显示=0，分歧 635/806）；几何门从不产出 `CONFIRMED_HUMAN` → geometry 永不确认任何轨迹、`gt_diff.tracks` 恒 0。 | engine `FusionTracker` 在 `tick` 内吃被覆盖前的决策投票，detector 事后覆盖无法回溯已发生投票；**若不修改冻结 engine 则无法既覆盖决策又让 tracker 用覆盖后决策**——本轮授权不改动 `core/engine.js`（冻结模块）。geometry(post) 被显式标记为**研究型后处理对照**：不确认任何轨迹、轨迹层结论仅限候选级分类分布对照、不用于召回/确认结论、不进入生产基线。 |

## 隔离边界复核

- 仅写入 `sidequests/human_fusion_lab/`：`detector.js`、`cdp_e2e.js`、`demo.html`、`server.js`、`test_geometry_consistency.js`（新）、`run_unify_tests.js`。
- `core/engine.js`、`core/fusion.js`、`core/schema.js`、human_replay/、models/、results/ 原始证据未改（results 仅 `DEMO_BROWSER_E2E.json`/`UNIFY_REGRESSION.json` 被复跑自然刷新）。
- `pc_apps/`、`src/`、`webui/`、部署/板端/生产识别链 **零改动**（`git status` M 全为上一轮 Codex 遗留，本轮未触碰）。

## 回归与复测矩阵

| 套件 | 结果 | 环境 |
|---|---|---|
| `run_unify_tests.js` | **8/8 PASS**（新增 `lab geometry(post) 决策/track 一致性`） | node v24.14.0 |
| 新增 `test_geometry_consistency.js` | **PASS**（合成 30/30 mismatch=0） | — |
| 作者全量 geometry mismatch | **0 / 6520（0.00%）** | 8 合格会话、5232 帧 |
| `cdp_e2e.js` E01–E09 | **10/10 PASS, exit 0** | 干净 8799 server + Chrome 154 |
| OpenCode 独立复跑 E2E | **10/10 PASS** | 干净 8799 与 8797 各一次（8797 时为陈旧进程） |

## 与 R2 验收表的变更

- **C08** PASS 证据升级：从 `--dump-dom`（LAB_E2E_UNIFY）升级为真实交互 CDP（Q01_BROWSER_E2E，干净环境 10/10）；覆盖任务二的六算法/seek/session/回退/异常/候选轨迹一致性。
- **C05** 语义收紧：geometry(post) 不再是"决策覆盖但 tracker 不一致"的模糊态，而是显式研究型后处理对照，候选级自洽、轨迹级明确不确认。
- **Q01** SUBMITTED 态已具备独立复核（OpenCode）+ 真实修复 + 复测闭环。
