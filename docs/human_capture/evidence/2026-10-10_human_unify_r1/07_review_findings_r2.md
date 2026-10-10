# HUMAN-UNIFY-R1 · 07 复审发现 R2（07_review_findings_r2.md）

复审员：OpenCode CLI（独立，未参与实现）
复审日期：2026-10-10
环境：Windows 11，Node **v24.14.0**，`HEAD=347a5bf`，`grep` 命中 `pc_apps/human_core/`（本轮工件）
方式：**不采信报告里任何数字**，全部本机重跑/复算（命令见各节）。

---

## 0 · 复审基线（本机实跑）

```bash
node --max-old-space-size=2048 pc_apps/human_core/run_all_tests.js   # → 6/6 suites pass
```
逐 suite：schema **13** / data_loader 16 / engine_smoke 9 / replay_contract 9 / edge_cases 14 / model_compat 12（均 0 FAIL）。
生产文件 SHA：`02_source_sha/prod_sha256.json` 19 个文件本机重算 **19/19 一致**（本轮仍未动生产源）。

---

## 1 · 第一轮 4 FAIL + 2 注意 逐项终审

### FAIL-1 · 03/04 报告与落盘数据失同步 → **FIXED**（附小残留）

本机复算 9 会话 × 5 模式全部 `session_summary`：

| 会话 | U3 pf | U3 confirmed | 03/04 报告 |
|---|---|---|---|
| cap_20261009_113611 | 203 | 12 | 203 / 12 ✅ |
| cap_20261007_154007 | 83 | 25 | 83 / 25 ✅ |
| cap_20261009_114641 | 177 | 5 | 177 / 5 ✅ |

- `03_PIPELINE_DIAGNOSTICS.md` §2.1~2.4 五模式 × 四会话表 **逐格与落盘一致**（BASE_A/B、U1/U2/U3 的 pf/ff/confirmed 全部对上）。
- `04_AB_COMPARISON.md` §1 九个会话 × 模式的 pf/ff/tracks/confirmed **逐格一致**（含 203135 U3 113/46/17/4、143945 U3 108/19/32/23 等）。
- `03:84` 已把 "confirmed=0" 明确标注为 "（修前状态）…engine.js:399（已修）"，与源码一致。
- 复算命令：
  ```bash
  python - <<'EOF'
  import json
  d=json.load(open('docs/human_capture/evidence/2026-10-10_human_unify_r1/runs/cap_20261007_154007/cap_20261007_154007__U3.json',encoding='utf-8'))
  print(d['session_summary']['n_tracks_confirmed'])  # 25（报告曾写 0）
  EOF
  ```

**残留（非 FAIL）**：`04` 表格的 `ms/f` 列多数对不上当前落盘——113611 U2 报告 13.2 / 实测 **17.22**，U3 报告 15.0 / 实测 16.25；154007 A 报告 15.4 / 实测 16.45。`ms/f` 受负载影响大，且报告未给采集窗口，属可复现但未对齐项；**计数（关键结论）已对齐**。

### FAIL-2 · A/B 框架错误：把 U3 当 "BASE_B + REF" → **PARTIAL**

- `04_AB_COMPARISON.md:53-55` 已新增 §2.4 "**U3 ≠ BASE_B + REF**"，明确 "U3 内部仍走 online 背景，只把分类器换成 rf51，不应期望复用 REF envelope"。本机核对 `engine.js:190-191`（U3→`_tick_pipechain`）、`:206`（`load_ref_envelope` 只在 `_tick_base_b`），**U3 确实不碰 REF**，修正正确。
- **但同一错误建议仍在两处留存**，与 04 自相矛盾：
  - `05_REGRESSION_REPORT.md:54` "U3 … 需 REF envelope 注入 U3 的 fg"
  - `08_INTEGRATION_READINESS.md:21` "U3 … 需 REF envelope 注入"
  - `grep -rn "REF envelope 注入"` → 命中 05/08。修正未传播，读者仍会被误导。

### FAIL-3 · 06 性能数字不可复现 → **PARTIAL（核心未解）**

本机连跑 `test_perf.js` 两次：

| session/mode | 06 §1 报告 P50/P95 | 复算① P50/P95 | 复算② P50/P95 |
|---|---|---|---|
| dynamic U3 | 23.88 / 29.20 | 36.96 / 46.50 | 36.63 / 49.51 |
| empty U3 | 9.48 / 12.49 | 19.26 / 28.00 | 12.28 / 15.77 |
| standing U3 | 8.77 / 11.97 | 14.74 / 20.05 | 13.13 / 19.16 |
| empty BASE_A | 8.96 / 12.84 | 12.76 / 24.18 | 11.51 / 14.99 |

- U3 相关数字与报告差 **1.5~2×**，远超报告 §2 自称的 "JIT warm-up ±30%"。§1 具体数字**仍不可复现**。
- 重写后的 §2 反而断言 "§1 数字为实测可参考值"，此断言与实测矛盾。
- 唯一好转：原 "frame0 `total=55.91`" 的原文已从 06 删除（`grep 55.91` 仅命中旧 `07_review_findings.md`）。
- 验收阈值本身成立：两次复算 P95<50 / heap<1500 均 **9/9 PASS**，但 dynamic U3 两次 P95=46.5/49.5，距 50ms 门极近（第一轮曾在负载下 77ms 翻 8/9）。
- 复算命令：`node --max-old-space-size=2048 pc_apps/human_core/test_perf.js`

### FAIL-4 · schema.gt_attestation 不检测 PSEUDO_LABEL → **代码 FIXED / 证据 PARTIAL**

- `schema.js:149-170` 现已读 `ai_labels.json` 并返回 `PSEUDO_LABEL`（带 disclaimer）；`runner.js:118` `prf.level = gt.level`。
- `test_schema.js:53-63` 新增 2 条断言（PSEUDO + disclaimer），实跑 **schema 13 PASS**（第一轮为 11）。
- 验证 `cap_20261009_114641` 五模式落盘：全部 `prf.level=PSEUDO_LABEL`、`gt_level=PSEUDO_LABEL` ✅（prompt 命令 #3 通过）。
- **但证据未统一重跑**：`114709 / 114817 / 121622` 同样带 `ai_labels.json`  
  （`find captures -name ai_labels.json` → 12 个，其中 11 个 HR09），落盘却仍为 `UNKNOWN`：
  - `114709`：仅 `BASE_A`=`PSEUDO_LABEL`，`BASE_B/U1/U2/U3`=`UNKNOWN`（`manifest.generated_iso=08:45:20`，但四文件 `started_iso=08:30:29`，**manifest 未列这四个文件**）
  - `114817 / 121622`：五模式全 `UNKNOWN`（生成于 08:30，早于修复）
  - 时间戳分布：08:30 一批 / 08:33-08:45 一批——runs 为**分次生成的混合体**，非单一重跑。
- 因此 "runner 落盘对 HR09 会话为 PSEUDO_LABEL" 仅对 114641 成立，其余 3 个 HR09 会话证据陈旧。

### 注意-5 · 01 文件列表 → **FIXED**（附小残留）

- `01_ARCHITECTURE_PLAN.md:8-23` 已重写为实际清单，并新增 "**审计说明**" 解释 ponytail 简化为 7 文件、BASE_B 内嵌。`ls pc_apps/human_core/*.js | wc -l` → **13**（6 非测试 + 7 测试）。
- 残留：01、08 均写 "test_*.js × 6"，实际 **7** 个（含 `test_perf.js`）；01 §4/§5/§6 仍出现不存在的 `classifiers.js` / `tracking.js` / `replay_contract.js` 与 `core.create_engine` / `core.load_session` API（`runner.js` 只导出 `run_mode`）。属规划文本残留，不影响交付。

### 注意-6 · BASE_B 为内联重写而非 require detect_overlay → **FIXED**

- `grep -rn "detect_overlay" pc_apps/human_core/` → 仅 3 处**注释**，**无 require**；`engine.js:201-296` 内联手写 5cm 网格/RF/关联。01 审计说明 + 04 已如实声明 "内嵌实现、语义等价，非 require"。声明与代码一致。

---

## 2 · 复审额外发现（非第一轮项，但影响收口）

1. **测试矩阵数字自相矛盾**（新增/未同步）：
   - 实跑 schema = **13**，但 `05_REGRESSION_REPORT.md:7` 仍写 `test_schema.js 11`；`08:10` 写 "13/13 schema tests"。**05 与 08 互相矛盾，05 陈旧**。
   - 05 合计 "73" 按 (11+16+9+9+14+12+2=73) 计入 `test_perf`，而 `run_all_tests.js:6-13` 的 6 suite **不含 test_perf**；按当前计数 "73" 恰好等于 6 suite 之和（13+16+9+9+14+12）。集合口径仍含混。
2. **04 §2.2 "U2 = BASE_A" 与自身表格矛盾**：本机逐会话比对，U2 在 `143945`（A=70/108/31/3 vs U2=72/108/30/2）与 `154007`（conf 1 vs 0）**≠ BASE_A**；但 U1≡BASE_A 九会话全部成立。
3. `08:11` 仍断言 "9 会话 × 5 模式 BASE_A = 生产 A, BASE_B = 生产 B"。BASE_A≡A 已证；BASE_B 与 `detect_overlay` 的逐帧等价仍只是**声明**（04/05/08 均未做对拍），只能判 PLAUSIBLE。
4. `02_DATA_AND_GT_AUDIT.md:70` 引用 `sessions_sha.json` 标注为 "下一轮生成"，当前不存在（可接受，但报告指向缺失产物）。

---

## 3 · 审计项速览（R2）

| 第一轮项 | 本轮结论 | 依据 |
|---|---|---|
| FAIL-1 03/04 与落盘失同步 | **FIXED**（ms/f 列小残留） | 9 会话计数逐格复算一致 |
| FAIL-2 U3 = BASE_B + REF 归因 | **PARTIAL** | 04 已改；05:54、08:21 仍留错误建议 |
| FAIL-3 06 性能不可复现 | **PARTIAL** | §1 数字仍差 1.5~2×，§2 断言失实 |
| FAIL-4 PSEUDO_LABEL 未检测 | **代码 FIXED / 证据 PARTIAL** | schema+test+114641 成立；114709/114817/121622 陈旧 |
| 注意-5 01 文件列表 | **FIXED**（×6 应为 ×7） | 已重写 + 审计说明 |
| 注意-6 BASE_B 内联 | **FIXED** | 无 require detect_overlay，已如实声明 |

---

## 4 · 终审

**REWORK**

代码工件可信且未回退（6/6 suite、生产 SHA 19/19 未动、9 会话×5 模式计数全部可复算），FAIL-1 与 FAIL-4 的**代码/文档根因**已修，注意-5/6 已闭合。但仍不放行，因为**证据层未收口**：

- FAIL-3 的**性能数字仍不可复现**，且新 §2 反将不可复现数字声明为 "可参考" —— 这是本轮唯一实质未解项。
- FAIL-2 的修正只落在 04，`05`/`08` 仍保留 "REF envelope 注入 U3" 错误建议；FAIL-4 的证据 runs 仅 114641 重跑，114709/114817/121622 陈旧、114709 manifest 与文件批次不一致；05 测试矩阵 (schema 11) 陈旧并与 08 (13) 冲突。

收口最小清单：
1. 用当前引擎**统一重跑全部 9 会话 × 5 模式**（生成时间同批），刷新 `05` 测试矩阵（schema=13、并明确 run_all_tests 与含 perf 的 "73" 集合口径）。
2. `06` 要么给出可复现窗口/机器状态并重测 §1，要么直接删除 §1 具体数字、只保留阈值结论。
3. 删除/改写 `05:54`、`08:21` 的 "REF envelope 注入 U3"（与 04 §2.4 保持一致）。
4. `04 §2.2` 改为 "U2 ≈ BASE_A（除 143945/154007 confirmed 退化）"，勿写 "= BASE_A"。

修正后可再独审。当前**不建议 SHIP**。
