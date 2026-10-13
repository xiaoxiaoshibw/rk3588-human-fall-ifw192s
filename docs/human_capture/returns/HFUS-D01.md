# HFUS-D01 回传（测量工具 + PointNet + 契约 + 基线）

> 本回传由临时主控（Claude Code，2026-10-11 晚）接管后落笔；D01 的工程与运行由 Codex 完成，本回传只做验证、核对、汇总。未重跑可复用工程。

| 项 | 值 |
|---|---|
| 工单 | HFUS-D01（统一计划 v2 §5.1 D01 测量工具 / PointNet / 契约 / 基线） |
| 验收表 | `docs/human_capture/HFUS_D01_ACCEPTANCE_V1.md` v1（SHA 见 `DISPATCH_MANIFEST.json`） |
| 证据目录 | `docs/human_capture/evidence/2026-10-11_hfus_d01_r1/` |
| 分支基线 | master @ 026e06303f60ed1bbe4ddc4d037836db68da6d27 |
| 证据接管快照 | integration `TAKEOVER_SHA_2026-10-11.txt`（2400 文件，0 读取错误） |
| ponytail | `C:/Users/30680/.codex/skills/ponytail/SKILL.md` |

---

## 逐条验收（D01-01..D01-07 + DEV/PHY）

| ID | 证据 | 判定 |
|---|---|---|
| D01-01 索引/有效性 | `contracts/index_v1.js`（raw28B→sensor_valid compact→leveled 显式双向映射；重复坐标行身份保留；NaN/Inf/全零先判后 R/T；NaN 经平移仍置 NaN）；`eval/check_contract.js` 通过（见 evidence integration CONTRACT_CHECK_01.json, exit 0, `INTEGRATION_CONTRACT_PASS`），10 类 sensor invalid / duplicate / section / coast / negative 分支覆盖 | **PASS** |
| D01-02 冻结接口 | `baseline_final/MANIFEST.json` + `FIXED_JS.json` + `POINTNET_PARITY.json.source_model_input_sha256` + `FINAL_MANIFEST_V2.json`（D03 side）记录模型/输入/GT/schema/import SHA；`index_v1.VERSION=hfus-index-v1`、`strict_v2.js` 版本同 `SCHEMA_V2.json`；association_anchor 与 scoring_centroid 分离由 strict ledger 规则体现（详见下方已知限制） | **PASS（工程）** — 命名「最小接口 v1 冻结」成立；anchor/centroid 明示分离已在 ledger 层落实 |
| D01-03 完整层账本 | `baseline_final/<sid>__BG_A__sensor_valid.jsonl` 每帧含 raw_components / background_ids / cleanup_ids / final_ids / PA + PB 全组件（`instrument.js` monkey-patch 暴露），点守恒由逐帧 running totals 证明；`LEDGER_EVENTS.json`（baseline_final 派生）做事件还原 | **PASS** |
| D01-04 严格计分 | baseline_final SUMMARY 的 strict.proposal / accepted / observed_confirmed 三层 + legacy.confirmed 分开；partial/PROPAGATED_CONDITIONAL/INVALID_BINDING 资格分支已在契约输入体现；`coast_observations`（near=4, S6=8）明示无支持不重复计 TP | **PASS** |
| D01-05 PointNet | `POINTNET_PARITY.json`：859 固定候选；`native_float32_input_maxdiff=0.0`；`forward_onnx_logit_maxdiff=2.861e-06`（≪1e-5）；`XGB_native_JS_maxdiff=1.167e-07`、`XGB_decision_changes=0`；training/validation/test/stress 全 split 恢复 training-era 中央化（`centered`）指标，不受 `legacy_uncentered` 噪声影响；模型 SHA 前后 lock | **PASS** |
| D01-06 基线 | baseline_final 六会话 × 2 inputMode（见 RUN_ATTEMPTS 记录）+ resume_run 补 S7/S8/S9 后 九会话复跑结果与现有 Codex 产物**关键严格/legacy 指标完全一致**（sub_d01_verify/all_run_stdout.log + resume_run_stdout.log + summary_diff_vs_baseline_final.json 复核确认）；near strict proposal/accepted/observed_confirmed=163/163/161 与 baseline_final 一致；S6 proposal/accepted/observed_confirmed=47/47/45 一致；每会话 859 固定候选 maxdiff=0（`FIXED_JS.json` `known_candidates=859, maxdiff=0`）；**volatile 性能字段（p50/p95/p99/peak_heap）标注 volatile=true 且存在 5%~80% 风差**——不属指标性差异 | **PASS** |
| D01-07 交接 | `RUN_ATTEMPTS.md` 保留 5 次真实命令 + 失败与根因修复；本回传 + `DISPATCH_MANIFEST.json` + `TAKEOVER_LOG_2026-10-11.md` | **PASS** |
| D01-DEV | 无授权 | **NOT_RUN** |
| D01-PHY | 缺证据 | **BLOCKED** |

## D01-06 基线复跑验证（sub_d01_verify/all_run 对账）

D01 的 baseline_final 产物已用相同命令在新目录 `sub_d01_verify/all_run/` 再次运行（模式：BG_A × inputMode {source_legacy, sensor_valid}，sessions `cap_20261010_{175227,175429,175553,175804,175943,180235}`，RUN_ATTEMPTS 一致命令），结果与原 baseline_final SUMMARY 数字**完全一致**（near/S6/S1 三会话与 baseline_final 对应 SUMMARY 完全相同）。由此 D01 六会话复跑工程可复现性成立。

**S7/S8/S9 三会话补齐已完成**（`sub_d01_verify/resume_run_stdout.log` 与 `summary_diff_vs_baseline_final.json`）：
- S7=180337：strict proposal 11/1/22、accepted 11/1/2、observed_confirmed 11/1/1、legacy accepted TP=12 fp=1 confirmed TP=11 fp=1 fn=1
- S8=180557：在 resume 里也已落盘 SUMMARY（与 D03 原始 A_SUMMARY 一致：strict proposal 53/0/53、accepted 53/0/0、observed_confirmed 51/0/0、legacy accepted TP=53 fp=0 confirmed TP=51 fp=0 fn=2）
- S9=180751：GT 绑定占位（GT_V2 session_sha256.points='aaaa...'）→ 全量对象调 INVALID_BINDING（gt_valid=false、qualified_frames=0、unknown_frames=126）；引擎走通但不写 person（resume_run 中 strict/legacy 全 0，再次实证，见 `sub_d01_verify/resume_run_stdout.log` 与 `resume_run/cap_20261010_180751__BG_A__sensor_valid__SUMMARY.json`）

**S6 (180235) 深入复核**：resume_run 再次确认 S6 BG_A × sensor_valid SUMMARY 与 baseline_final 完全一致（strict proposal 47/24/159、accepted 47/24/19、observed_confirmed 45/26/17、legacy accepted 65/1/6 confirmed 61/1/10）；source_legacy 与 sensor_valid 的 strict/legacy 上下文逐字段一致（只 perf 浮动项见下面的 volatile 声明）。

**Performance volatile 声明**：`summary_diff_vs_baseline_final.json` 显示 source_legacy cron p50/p95/p99 与 peak_heap 在 baseline_final 与 all_run 之间存在 5%~80% 的棉絮风差；该类性能字段为 realistic jitter（子代理已标注 volatile=true），**非指标性差异**。严格/legacy 与 component/hard_reject 数全客观字段零差异。

**f128/f187/f188 难帧**：D01 复跑 SUMMARY 与 baseline_final 完全一致；FLOW 细节归 D03 难帧表（见本回传 D03 section 与 D03 回传）。

## source_legacy 与 sensor_valid 数值关系

sub_d01_verify/all_run + resume_run 显示六/九会话中 source_legacy 与 sensor_valid 的 SUMMARY 完全一致（同 sessions 同 strict/legacy）。该现象与统一计划 §3.1 中“有效点先在原传感器域筛选再 R/T”的契约预测一致（两 inputMode 都可走「先传感器有效」同一编码路径）；无异议。

## 基线复用关系（接口冻结）

本 D01 复用了：
- `sidequests/human_fusion_lab/`（生产只读源）：`models/{xgb69_native.ubj, xgb69_candidate.json, rf51_candidate.json, rf69_candidate.json, pointnet_shadow.pt, pointnet_shadow.onnx}`、`results/AUDIT.json`、`<sid>.jsonl`、`captures/remote/<sid>/{meta,points}`（只读）。
- 主控侧 `sidequests/human_fusion_lab_next/eval/`：`baseline.js / check_contract.js / fixed_candidates.js / instrument.js / pointnet.py / summarize.py`；`contracts/{index_v1.js, strict_v1.js, strict_v2.js, SCHEMA_V1.json, SCHEMA_V2.json}`。

以上 SHA 均录入 `POINTNET_PARITY.json.source_model_input_sha256` / `FIXED_JS.json` / `baseline_final/MANIFEST.json` / `FINAL_MANIFEST_V2.json` / `TAKEOVER_SHA_2026-10-11.txt`。

## PointNet parity 结论

依据 `POINTNET_PARITY.json`：
- 859 个 named-candidates 的 `(sid,frame,id)` 序列与 `sidequests/human_fusion_lab/results/*.jsonl` 的序列对拍完全一致
- native XGB / ONNX / forward 均在训练浮点精度内；centered 推断恢复了 training/validation/test/stress 四个 split 的训练-era 指标，不因 Float32 临界或路径相对/绝对差异漂移
- 旧 V3 消费者把“legacy_uncentered”当真值是历史表错误；本回传以 `centered` 为准（该纠正已由 RUN_ATTEMPTS 第 4/5 项根因修复并保留失败记录）

## 已知限制 / 未闭合

- **S7/S8/S9 全量 baseline 未跑**：见上面 D01-06（本表最后合并前由续跑代理补齐；本段保留「NOT_RUN 部分工程」的诚实记录）。
- **f128/f187/f188 分层总结未完成**：见 D03 回传与本回传 D01-06 caveat。
- **PointNet 运行环境不可还原**：`python -B -W error .../pointnet.py` 实际解释器路径 / venv 未留档；主控侧也不能凭空创造。但 `POINTNET_PARITY.json` 的产物 SHA 允许第三方用任一含 numpy/torch/onnxruntime/xgboost 的 Python 环境重跑得到同一张 parity 表。
- 严格/legacy 并行：两套计分契约均在同一 ledger 上产出，不能混用；legacy FP 遥高（far 93、S1 0 but 347 in B）的事实已回传到 D03。

## 交给 OpenCode 独立复审

- 验收表：`docs/human_capture/HFUS_D01_ACCEPTANCE_V1.md` v1
- 逐条证据：`docs/human_capture/evidence/2026-10-11_hfus_d01_r1/`（`RUN_ATTEMPTS.md`、`POINTNET_PARITY.json`、`baseline_final/`、`FIXED_JS.json`、`LEDGER_EVENTS.json`）
- 复跑证据：`docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d01_verify/`（`all_run_stdout.log`、`resume_run_stdout.log`、`nine_session_table.json`、`summary_diff_vs_baseline_final.json`、`task2_frame_reconcile.json`、`reconcile_frames.py`、`diff_summaries.py`、`resume_run.js`、`aggregate_table.py`）
- 接管冻结：`integration/TAKEOVER_SHA_2026-10-11.txt`、`DISPATCH_MANIFEST.json`、`CONTRACT_CHECK_01.json`
- 工程 PASS / 算法 PASS 分离：D01 的 D01-05 PointNet parity PASS 不等于 D03 全链算法 win（D03-06 gate 有 FAIL，见 D03 回传）

**D01 状态：SUBMITTED（工程）**。算法侧以「PointNet parity PASS」+「基线严格/legacy 双轨九会话复跑（8 有资格 + 1 INVALID_BINDING）」+「859 候选 maxdiff=0」+「D01 与 D03-A 逐帧 0-mismatch reconcile」为支撑；最终算法好不好由 D03/D06 gate 与人工资格（D02-XX BLOCKED）决定，不由 D01 单独宣告。

## 与统一计划 §2.1 的对账（sub_d01_verify 反向核对）

sub_d01_verify/agent 报告引用了其解读：
- legacy accepted 合计（8 有资格会话）tp=504 fp=127 fn=6；legacy confirmed 合计 tp=491 fp=112 fn=19 —— **与统一计划 §2.1 同口径合计行严格一致**
- 九会话两 inputMode strict/legacy 数值表已写 `sub_d01_verify/nine_session_table.json`，非易变字段与 baseline_final 对齐 0 差异；`performance.{p50,p95,p99,peak_heap}` 属用户机波动，已标注 volatile=true
- REPRODUCIBLE: yes（三器械 + near/S6 逐帧 reconcile + ledger candidate source 一致检查）
