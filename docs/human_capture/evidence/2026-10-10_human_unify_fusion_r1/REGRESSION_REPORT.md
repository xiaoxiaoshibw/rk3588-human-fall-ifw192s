# REGRESSION_REPORT — 既有回归状态 (FUSION 注入后)

2026-10-10。范围: `pc_apps/human_core/run_all_tests.js` (R2 的 96 项 7 suites) + `test_fusion_specific.js` (新 F2 专项 16 项)。

## 1. 既有 96 项功能回归 (R2 基线)

| 套件 | 项数 | 结果 | 证据 |
|---|---|---|---|
| schema | 13 | PASS | |
| data_loader | 16 | PASS | |
| engine_smoke | 9 | PASS | |
| replay_contract | 11 | PASS | |
| edge_cases | 14 | PASS | |
| model_compat | 12 | PASS | |
| rework (R01–R08) | 21 | PASS | 见工单 BASELINE_AUDIT.md §4 |
| **合计** | **96** | **PASS 96 / FAIL 0** | `run_all_tests.js` |

FUSION mode 加入后, `engine.js` `_validate_mode_cfg` 对 FUSION 独立分支校验; `_tick_base_b/_tick_pipechain` 行为未变。

## 2. FUSION 专项 (16 项) — F2 融合行为断言

| 项 | 结果 |
|---|---|
| FUSION 重 begin generation 递增 | PASS |
| 旧 generation tick 被严格拒绝 | PASS |
| strict 重复帧抛错 / lenient 记 duplicate_frame_ignored | PASS |
| frame_index 回退拒绝 | PASS |
| FusionTracker: 首 candidates 建 track | PASS |
| lost=1 仍 active / lost>max → active=false | PASS |
| 失联后重捕 → 新 FUS track_id (新代际) | PASS |
| CLS_DECISION.UNKNOWN 决策带宽 OPEN | PASS |
| retention.tracks 结构合法(无 retained-only-self-refresh) | PASS |
| 保留刷新守卫同 U3 (FG+CONFIRMED 才刷新) | PASS |
| report.fusion_track_ids 数组存在 | PASS |
| FUSION track_id 符合 FUS_t{seg}_{id} | PASS |
| report.pipe_track_ids 同步存在(审计用) | PASS |
| 旧 diag 未被新代际污染 | PASS |
| generation 隔离后 tick 拒绝 | PASS |

`node --max-old-space-size=2048 pc_apps/human_core/test_fusion_specific.js` → **16 PASS, 0 FAIL**

## 3. 生产 JS 回归

未跑 — 工单 §7 明示 FUSION 不接管 human_replay 生产主入口（页面由用户另行启用）；本工单代码只新增 `fusion.js`+engine tick 分支,不修改 `pc_apps/human_replay/*` 任何文件。`rf_person.js`/`human_pipe_lib.js`/`detect_overlay.js` SHA 见 `source_baseline_sha.txt` 未变。

## 4. A/B 逐帧生产对拍 (R2 已 PASS，FUSION 注入后需独立验证)

R2 CLOSEOUT: runs_03 9 会话 1,196 帧 A/B 对拍 PASS。FUSION 模式下**没有跑过** BASE_B↔原生产的对拍——FUSION 是新走法，不与 BASE_B 同输入同 PARITY 断言（设计目标不同）。`test_baseline_parity.js` 仍以 BASE_B 复现原 B 输出,与 FUSION 独立。

## 5. 结论

- **FUNCTIONAL_PASS**: ✅ 96+16=112 项功能断言全部 PASS, FUSION 不破坏任何既有行为
- **GT_EVALUATION_PASS**: ❌ BLOCKED — 9 会话全 UNKNOWN GT (0 段 HUMAN_VERIFIED)
- **PERFORMANCE_PASS**: ✅ 9/9 A/B/U3 P95<50ms 且 heap<1500MB (perf_profile_01); FUSION smoke 稳态 <50ms, 后续应在 F4 完成后独立门跑 FUSION P95
- **MODEL_PROMOTION_READY**: ❌ BLOCKED — 无 GT 无 RF v2 对照
- **PRODUCTION_RELEASE_READY**: ❌ BLOCKED — FUSION 仅示读演示、不替换生产主入口; WebUI 交付是 demo, 未授权切换

## 6. 证据

- `pc_apps/human_core/run_all_tests.js` & `test_fusion_specific.js` 完整 PASS 输出 (本次会话日志)
- `perf_profile_01/perf_profile.json`
- `source_baseline_sha.txt` (FUSION 注入后 SHA: `engine.js=bba61dd8…`, `fusion.js` 新文件)
- `runs_fusion/<sid>__<MODE>.json` 每路线 SHA 守卫 + 完整 run_meta
