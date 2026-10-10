# HUMAN-UNIFY-R1 · 07 独立审计发现（07_review_findings.md）

审计员：OpenCode CLI（独立，未参与本轮实现）
审计日期：2026-10-10
基线：`HEAD=347a5bf`，`branch=master`，Node v24.14.0，Windows 11
审计方式：所有数字均本机重算/重跑，不采信 07_review_prompt.md 或既有报告中的数字。

---

## 复算关键数字（本机实跑）

命令：`python - <<EOF ... 读 runs/<sid>/<sid>__<MODE>.json 的 session_summary EOF`

```
cap_20261009_113611 BASE_A frames_with_furniture_cand=203 expected=203 [OK]
cap_20261007_154007 BASE_B n_tracks_confirmed=6        expected=6   [OK]
cap_20261009_114641 U3     n_tracks_confirmed=5        expected=5   [OK]
```

会话帧数：`113611=203 帧`、`114641=177 帧`（与报告一致）。
`5 个 runs/*/manifest.json` 里记录的 `sha256_16` 与磁盘文件重算值 **全部一致（0 mismatch）**。

---

## VERIFIED（审计员亲自跑过且通过）

1. **任务项 2 · 生产文件未被本轮修改** — `VERIFIED`
   - `02_source_sha/prod_sha256.json` 记录的 19 个生产文件：本机重算 SHA-256 **19/19 全部一致**。
   - mtime 检查：`human_pipe_lib.js`、`detect_overlay.js`、`rf_person.js`、`rf_person_v1.json` 均为 2026-10-09，**无 2026-10-10 16:xx（本轮时段）改动**。
   - `find pc_apps/human_replay -newermt "2026-10-10 16:00"` → 空。今日被改的只有 `session_selection.js/.test.js`(12:44–12:46) 与 `human_detect.js`(13:31)，均早于本轮开工（16:12），属用户其它任务；`git status` 中 28 个 `human_replay` M 项与此点一致。

2. **任务项 1 · engine.js 真实复用 human_pipe_lib（非 stub）** — `VERIFIED`
   - `pc_apps/human_core/engine.js:18-19` 直接 `require("../human_replay/human_pipe_lib.js")` 与 `rf_person.js`。
   - 路线 A 全链确实调用 pipe 实现：`denoise / extract_foreground / cleanup_isolated_fg / voxelize / cluster_voxels / evidence_postpass / cluster_features / classify_human / evidence_label / joint_status / Tracker / fall_assess`（engine.js:301-454），无自造桩。
   - `grep -E "throw.*not implemented|TODO|FIXME" pc_apps/human_core/*.js` → **无匹配**。

3. **任务项 10 · 隔离环境复现** — `VERIFIED`
   - `node --max-old-space-size=2048 pc_apps/human_core/run_all_tests.js` → **`6/6 suites pass`**。
   - 逐 suite 复跑计数与 `05_REGRESSION_REPORT.md` 一致：schema 11 / data_loader 16 / engine_smoke 9 / replay_contract 9 / edge_cases 14 / model_compat 12。

4. **任务项 5 · begin_session 状态重置** — `VERIFIED`
   - `engine.js:120-131` 在 (换 sid / loop_back / pipe_ctx 为空 / tracker 有 track) 时执行 `this._seen_frames.clear(); this.retention = new RetentionState(); this.pipe_ctx = { static_keys:null, tracker:new pipe.Tracker(), fusion:null }`，tracker/retention/seen_frames 三者齐清。
   - `test_replay_contract.js:38-74`（换会话隔离 + 回退重放不抛）与 `test_edge_cases.js` 覆盖，实跑 PASS。

5. **任务项 6 · 28B 帧切片正确 + 测试覆盖** — `VERIFIED`
   - `data_loader.js:85` `start_b = f.offset_points*STRIDE`；`:89/:91` 取 `n*STRIDE`（`n=f.count_points`）。`_slice_frame_xyzi_fast` 按 stride=7 个 f32 取前 4（x,y,z,intensity），正确。
   - `test_data_loader.js:40-41` 第二帧 `offset_points=2`，断言 `frames[1].xyzi[0]===100.0`、`[4]===-1.0`（第 76-77 行），**偏移×28 与 计数×28 均被覆盖**；实跑 16/16 PASS。
   - 缺口（非 FAIL）：未覆盖非 4B 对齐 fallback 分支；属可接受缺口。

6. **任务项 8 · 三个重点数字与落盘 json 对得上** — `VERIFIED`（但见下方 FAIL-1 的报告级不一致）
   - 203 / 6 / 5 三个数字本机复算全部 `[OK]`。

7. **任务项 3 · 未把 ai_labels.json 当 HUMAN_VERIFIED 使用** — `VERIFIED`（安全性成立；但报告措辞失实，见 FAIL-4）
   - `grep -rn "ai_labels" pc_apps/human_core/` → 仅 `schema.js:14` 一句注释，**无任何代码读取 ai_labels**。
   - 落盘 json `run_meta.gt_level` 全为 `UNKNOWN`，`prf.measurable=false`，未输出 P/R/F1。

8. **任务项 9 · test_perf.js 是真跑不是编数字** — `VERIFIED`（附脆弱性说明）
   - `test_perf.js:29-55` 真实 `D.load_session` 加载 `captures/remote/*` 并逐帧 `engine.tick`，`pct()` 实算 P50/P95，无硬编码。
   - 本机跑两次：并发负载下曾 `8/9`（dynamic U3 P95=77ms > 50），机器空闲第二次 **`9/9 PASS`**（dynamic U3 P50=35.67/P95=43.49）。断言阈值 `P95<50`（test_perf.js:69）对 U3 动态场景余量很小，负载敏感。

9. **任务项 7 上半 · BASE_A ≡ U1 完全等价** — `VERIFIED`
   - 落盘 config 仅 `mode` 不同（其余字段逐一相同，见 runs 内 `config`）。
   - 9 会话逐项对比 `frames_with_person_cand` / `frames_with_furniture_cand` / `n_tracks_confirmed` **完全一致**。

10. **任务项 7 下半 · U3 不使用 REF** — `VERIFIED`
    - `U3` 走 `_tick_pipechain`，其 `cfg.background="online"`；`load_ref_envelope()` 只在 `_tick_base_b`（engine.js:206）被调用，路线 A 分支从不调用。落盘 `config.background` 亦为 `online`。

---

## PLAUSIBLE（代码逻辑合理，但未做端到端独立验证）

- **BASE_B ≡ 生产路线 B（以重写代替复用）** — `detect_overlay.js` 从未被 `human_core` require；路线 B 是在 `engine.js:201-296` **内联手写**（`denoise` 复用 pipe，但 `find_hot`、5cm 网格聚类、RF 打分、associate 关联为本地重写）。报告 04 §2/§6 断言"BASE_B 逐帧与 detect_overlay 同语义"属**声明**，本审计未逐帧对拍 `detect_overlay.js`，故只能判 PLAUSIBLE。
- **任务项 4 · 训练/验证按段而非按帧** — `train_person_rf.py:87-101` 用 leave-one-**session**-out（fold 单位为整段会话），未见按帧切分。但本模型由 `2026-10-10_rf_optimization_r1` 产出（`model_source=rf_person_v1.joblib`），其"验证"为**位置弱标签**（见该轮 `21_CLOSEOUT.md`），非人工 GT；且空场负样本去重后被复制并跨 fold（`train_person_rf.py:47-57, 89-93`），存在空场负向量同现 train/test 的轻微泄漏，仅影响空场 fold 负类，不影响段隔离结论。本轮**未重训模型**。

---

## FAIL（失实 / 证据与报告不符 / 框架错误）

### FAIL-1 · 03/04 报告的 U3 结论与落盘 runs 及源码互相矛盾（证据不可信）
- `03_PIPELINE_DIAGNOSTICS.md:39` 写 "U3 pf=83 但 confirmed=0"; `:48` 表 "U3 | 177 | 0 | 0"; `:84` "（未修）U3 classifier=rf51 没改 joint 语义 → confirmed=0"。
- `04_AB_COMPARISON.md:54` "154007 U3 | 37 | 0"; `:101` "U3 ... **BLOCKED**"。
- 实际落盘 runs（本机复算）：
  ```
  cap_20261007_154007 U3 n_tracks_confirmed=25   (报告称 0)
  cap_20261009_114641 U3 n_tracks_confirmed=5    (报告称 0)
  cap_20261009_113611 U3 n_tracks_confirmed=12
  ```
- 且源码 `engine.js:395-399` **已含** "把 rf 决策写回 f.joint" 的修复（注释原话 "导致 U3 confirmed=0 假死"），报告称"未修"。
- 复算命令：
  ```bash
  node -e "const d=require('./docs/human_capture/evidence/2026-10-10_human_unify_r1/runs/cap_20261007_154007/cap_20261007_154007__U3.json');console.log(d.session_summary.n_tracks_confirmed)"  # 25
  grep -n "f.joint = (prob >= this.cfg.rf51_threshold)" pc_apps/human_core/engine.js  # 命中 line 399
  ```
- 影响：03/04 是引擎修改前的旧稿，未随 16:33 重跑同步；证据包自相矛盾，不能作为本轮 U3 结论的可靠记录。

### FAIL-2 · A/B 对比框架错误：把路线 B 与路线 A 当作"仅差 REF + rf51"
- `04_AB_COMPARISON.md:109` "REF envelope 未注入 U3: U3 应继承 REF 的 fg 抽除" —— 这是错误建议。`U3` 是**路线 A**（online 背景 + 0.15m 体素 + 几何门 + 3/5 票 tracker + retention），`BASE_B` 是**路线 B**（REF 包络 + 5cm 网格 + RF + age-only）。两者差异是**整条管道**（背景/聚类/时序/跟踪器/分类器全部不同），不是"REF_envelope + rf51"两个旋钮。U3 **正确地**不使用 REF（见 VERIFIED-10）。
- 因此 04 §2/§3/§7 的 BASE_B↔U3 对照不是受控单变量 A/B，其"U3 BLOCKED/故障"表述建立在错误归因上。

### FAIL-3 · 性能报告 06 §1/§2 数值不可复现
- `06_PERFORMANCE_REPORT.md:12-14` dynamic U3 `P50=23.88 P95=29.20 max=37.63`；本机两跑分别 `P50=53.61/P95=77.01` 与 `P50=35.67/P95=43.49`，均明显更高。
- `:37-45` frame0 层间 `total=55.91`；落盘 `runs/cap_20261007_154007/…__BASE_A.json` `frames[0].total_ms=29.71`，对不上。
- 结论：test_perf 是真跑，但 06 的数字是特定负载下的快照，**未标注机器状态且当前不可复现**；"全部 9/9 PASS"（06:68）在负载下会翻成 8/9。属"证据与复算不符"（程度轻于 FAIL-1）。

### FAIL-4 · 07_review_prompt 关于 PSEUDO 标注的描述不成立
- prompt 第 3 条称"我们在 `schema.gt_attestation` 和 `runner.js` 明确标记 PSEUDO"。
- 实际 `schema.js:148-153` `gt_attestation` 只返回 `HUMAN_UNVERIFIED`（有 human_annotations）或 `UNKNOWN`，**永不返回 `PSEUDO_LABEL`**（该枚举 `schema.js:14` 定义但无引用）；`runner.js` 亦无 PSEUDO 分支，落盘 `gt_level` 全为 `UNKNOWN`。
- 这不构成误用（安全性质仍满足），但报告对自身实现的描述失实。

---

## 其它需注意（非 FAIL，但削弱"统一核心"主张）

- `01_ARCHITECTURE_PLAN.md:8-24` 规划的 `background.js / candidates.js / clustering.js / classifiers.js / retention.js / tracking.js / diagnostics.js / replay_contract.js / attestations.js` **一个都不存在**；实际是单文件 `engine.js`（517 行）。计划与交付不符，公共核心实为"A 薄封装 + B 内联重写"。
- U3 在空场 `113611` `person_cand=203, furn=0, confirmed=12`：RF 把瞬态家具判为人并确认，是本轮自身披露的已知缺陷（`04:31`、`05:20`、`06:60`），确证 RF 模型在无家具负例下不可用于生产语义；本轮定位它"BLOCKED"是诚实的，但说明"统一升级"轴实际未成功。
- `05_REGRESSION_REPORT.md:13` 把 `test_perf.js` 计入 73 项测试矩阵，但 `run_all_tests.js:6-13` 的 6 个 suite **不含 test_perf**；即"6 suite PASS"与"73 项"不是同一集合，读者易误读。

---

## 审计项结论速览

| # | 审计项 | 结论 |
|---|---|---|
| 1 | 真实公共核心（非 stub） | VERIFIED（A 真复用；B 为重写，见 PLAUSIBLE） |
| 2 | 生产文件不变 | VERIFIED |
| 3 | ai_labels 不当作 HUMAN_VERIFIED | VERIFIED（但 PSEUDO 标注描述失实 = FAIL-4） |
| 4 | 训练/验证按段隔离 | PLAUSIBLE（段级隔离成立；弱标签+空场负复制小泄漏） |
| 5 | begin_session 全面重置 | VERIFIED |
| 6 | 28B 切片正确 + 覆盖 | VERIFIED |
| 7 | A/B 配置公平 | BASE_A≡U1 VERIFIED；BASE_B↔U3 归因错误 = FAIL-2 |
| 8 | 统计与原始数据一致 | 三数字 VERIFIED；报告级矛盾 = FAIL-1 |
| 9 | 性能数据实测 | 真跑 VERIFIED；06 数值不可复现 = FAIL-3 |
| 10 | 隔离环境 6 suite PASS | VERIFIED |

---

## 总评

**REWORK**

代码工件本身是真实的、可隔离复现的（6/6 suite，production SHA 全等，280 个落盘 run 可复算），任务项 2/5/6/8（三数字）/9（真跑）/10 成立。但**证据层不可信**：`03/04` 是引擎修复前的旧稿，与落盘 runs 及 `engine.js:399` 直接矛盾（FAIL-1）；A/B 对比把两条完整管道当成"差两个旋钮"（FAIL-2）；性能报告数值当前不可复现（FAIL-3）；对自身 PSEUDO 标注的描述失实（FAIL-4）。加之作者自评 U3 BLOCKED / U2 WEAK / U6 NOT_RUN，统一升级轴并未成功。

建议：不必推翻 `pc_apps/human_core/` 代码；但需 (a) 用当前引擎重跑并重写 03/04，使其与 runs 一致，(b) 修正 04 的 BASE_B↔U3 归因（U3 不应注入 REF），(c) 在 06 标注机器状态与复现窗口，(d) 修正 PSEUDO 描述，(e) 明确 `run_all_tests` 与报告测试矩阵的集合差异。修正后可再次独审收口。
