# GL-I05 R2 OpenCode 独立二审（同一验收 v1，不可变证据复验）— SECOND_REVIEW_SUBMITTED / STOPPED

状态：**SECOND_REVIEW_SUBMITTED / STOPPED**。只读复验；未写/改任何 checker 脚本，未改作者源码/验收/回传/状态/旧证据，未接入运行时，未启设备/采集/部署/网络，未改 model/DB/auth/权限/全局配置。**结论：软件条目全部 PASS（建议），无新增 REWORK；B01/B02 BLOCKED、D01/D02 NOT_RUN，整单仍未 ACCEPTED（由 Codex 收口）。**

- 被审提交：`research_01/11_submission_manifest.json`（`master`/HEAD `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`；`active_ledger=experiment_results_identity_verified.json`，`active_spatial=spatial_02/source_review.html`）。作者/代码/manifest 自 R2 提交后未变。
- 基线：`../00_before_baseline.json`、`../17_submitted_baseline.json`。
- native skill：`skill(name=ponytail)` 实际返回基目录 `C:\Users\30680\.config\opencode\skills\ponytail`，文件 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`。**未读取/扫描/哈希作者或 Codex 的 `.codex` 技能目录**。
- 前一 Go 会话（CLI 元数据，非本报告猜测）：`20_second_review_meta.json` = model `opencode-go/deepseek-v4.1-flash`、db `default`、session `ses_efd3cf9eaffeanm7dK1RLUGDvQ`、exit 0、940.140s、timed_out false。本次复验 CLI 会话/model/长跑 exit 由编排者 Codex 导出提供，本报告不猜测。
- 作者 SHA（首/尾）：`cbd0be1c86a1051a9a5800dfb7263f842896e1e6`；`12_end_state` 证 `head_match=true`、`manifest_mismatch_after_review=[]`、`author_files_unchanged=true`。

## 0. 先前的证据保全偏差与本轮纠偏（历史保留，不抹除）

- 上一 Go 会话（940.140s/exit0，软件 C01–C06/E01–E02/S01/Q01–Q10 曾建议 PASS）**在 `opencode_second_review_01/` 内编辑并重跑了自己的 checker 脚本、复用同一输出名**，违反“检查脚本一次定稿、输出不可覆盖”的明确保全指令。**该偏差真实发生过**，本报告不暗示其未曾发生，也不回改 `00_review.md`。
- Codex 从已关闭的追加式 `20_second_review.jsonl` 中恢复出 **27 个脚本版本 + 26 条命令输出** 到 `24_review_history_final/`；**原始记录与其中错误的 checker 结果（reviewer fixture/field 错误，非作者失败）保留在原处，未删/未归一化**。
- 本轮把“最后一次修正后的 checker 字节”**一次性**复制到 `opencode_second_review_02/`（并在独立的 `24_check_validation/` 预检 13 条命令全 exit0）。算法不需要返工；需要复验的是**程序性证据**。本报告即为该不可变复验。

## 1. 不可变执行证明（`execution_manifest.json`）

- 执行且仅执行一次：`python -B docs/human_fall/evidence/2026-10-04_gl_i05_r2/25_run_review_checks.py`；目录内无既有 JSON/`execution_manifest.json`，runner 拒绝重跑/覆盖。输出：`all_exit_zero=true`、`checker_bytes_unchanged=true`、`commands=13`。
- 运行前后 checker SHA 相等（`start_sha==end_sha`），并与 `24_revalidation_precheck.json` 的 `sha256` 逐项一致：

| checker | SHA256（同一 `start==end`） |
|---|---|
| 01_manifest_scope.py | `59a8c15772811f5a387f89af2a388eaf7d93220c6bd5e2802ea5148aea456d50` |
| 02_scalar_reference.py | `522824e3e607b343375afafa2597eb21649cc230d2c30d74e557472282a1532e` |
| 03_ledger_check.py | `525992d44cc1b2c88a817c1c1c9df9001382d316973c583501259c9c40dea44c` |
| 04_old_i04_fixture.py | `d3f0c053cc68c71e01ff7b4a4f8b4818fddc500e30411bb35b263f29a0de7dd9` |
| 05_spatial_parse.py | `d3e257824cd7745dfd8654726da18ada117a233198eeb03b5a7afb94cfd3529c` |
| 05b_spatial_residual.py | `06cc5c9eb0eaedc7df03a5209881a883a947959324f0140fbad8ead610129f38` |
| 06_js_consumer_independent.js | `0f0eb89485e274015595970e428d067ce1625ca1f57adb02ea81c15f145f4366` |
| 07_source_guards.py | `11e8d79238de95afa78c0bd2cbf2726f53666ca05cf6853c7456a9ca27654007` |
| 08_frozen_and_audit.py | `d72a83568a7b745e3ae83bac95c23f5291001618eb88c2a91b5f6b1c9fd67202` |
| 09_frozen_compare.py | `a69c4914e6faa60e59b2c49403e88da7303af137a15abee9bc195c0beab6b315` |
| 10_conservation_qmatrix.py | `4257f0beb7464a9f90693a9d59159678f1e6a9dc2d2deec8148f0fc03639f9f4` |
| 11_scope_diff.py | `585ff77aa7a7a9e53415ec96bae9bbf0f8f7c678fbd9ccea8aa30337218eb5fa` |
| 12_end_state.py | `1b81992ee1b181059ea5979f389b31725fac381d76e240247581aa05c242bb80` |

## 2. 独立检查结果（本目录全部新产物；`opencode_second_review_02/*.json`）

| 脚本 | 覆盖 | 关键布尔/失配表 | 结果 |
|---|---|---|---|
| `01_manifest_scope.json` | 76 SHA、ledger/原型 SHA、scope、HEAD | `manifest_all_match=true`、`manifest_sha_mismatch=[]`、`manifest_missing=[]`、`ledger_impl_mismatch=[]`、`old_new_sha_mismatch=[]`、`frozen_core_and_old_evidence_unchanged=true`、`unexpected_changes=[]`、`head_match=true` | PASS |
| `02_scalar_reference.json` | 独立 scalar：ALL/NEAR/BEST_ONLY×终态；0/4/8 全排列、0/6/12 链、middle-best、弱distinct、.8 边界/tie；4000 随机；畸形拒 | 12/12 `ok=true`，`random_mismatch=[]`，`prototype_terminal_equals_scalar.detail=[]`，`near_competition_reason_present.detail=[]` | PASS |
| `03_ledger_check.json` | 3MB active ledger 解析（不入上下文）：38 case、digest、5 阶段×3、计数恒等、归因、merge | `synthetic_cases=36`、`real_cases=2`；`all_oracle_match/all_closure_safe/all_sequence_digest_equal/all_have_5_stages_3_repeats/all_peak_positive_separate/all_counts_identity/all_old_i04_seq_match=true`；`attribution_counts={actual:19, old_cert:25, budget_gap:7}`；`weak_dominant_cases=6`；`all_metric_holds_agree=true`；`metric_holds_mismatch=[]`；`cases_with_pair_count_diff=44`；`merge_safety_ok=true`、`merge_safety_detail=[]`；`active_ledger_matches_manifest=true` | PASS |
| `04_old_i04_fixture.json` | 实际 GL-I04 包络原型 / 0/4/8 反例 / 链 | `old_order_dependent=true`、`new_all_closed=true`、`scalar_all_closed=true`、链三方皆 `unresolved`；随机序对照 `same=145/diff=55`（旧原型序依赖的预期后果） | PASS |
| `05_spatial_parse.json` | 28.8MB HTML payload vs 冻结侧车 | `frame_count=89`、`stats_keys=356`、`records_content_match/order_match/stats_count_match=true`、`jsonl_total_rows=351255`、`frames_match_diag/frame_groups_match/bounds_match_draft=true`、`xyz_outside_box=0`、`plane_physical_false=true`、`approved_origin_is_prior_label=false`、`recording_extrinsic=unknown`、`physical_verified=false` | PASS |
| `05b_spatial_residual.json` | 页面残差公式 vs 冻结 `signed_residual_m` | `exact_matches=351255/351255`、`mismatches=0`、`max_abs_diff=6.66e-16`、`convention_confirmed=true` | PASS |
| `06_js_consumer_independent.json` | 实际页面 JS（vm）选面残差/点击/索引/frame/box/显示预算 | `status=pass`、`actual_js=true`、`residuals_differ=true`、`index_lookup_ok/click_lookup_ok/display_cap_only_visual/frame_switch_ok/box_switch_ok=true`；`actual_browser_DPR=NOT_RUN`（不冒称真实 DPR） | PASS |
| `07_source_guards.json` | schema/frame/units/alias/duplicate/foreign/row/非finite/越界/独占输出/坏 budget 拒 | 21/21 `checks=true`，`all_ok=true` | PASS |
| `08_frozen_and_audit.json` | 7 条录制 metadata SHA、无新录制、unknown 保持、Py3.8 AST、无 cache | `record_sha_mismatch=[]`、`all_records_present_matching=true`、`captures_modified_on_or_after_20261004=[]`、`unknowns_retained/rotation_unknown/config_binding_unknown=true`、`no_cache_implemented=true`、`py38_ast_ok=true`；`physical_flags={B01:BLOCKED,B02:BLOCKED,D01:NOT_RUN,D02:NOT_RUN}` | PASS |
| `09_frozen_compare.json` | 生产冻结跨 R1/R2 | `r1_prod_files=122`、`r2_prod_files=122`、`prod_changed_between_baselines=[]`、`current_tree_prod_mismatch=[]`、`production_frozen_ok=true` | PASS |
| `10_conservation_qmatrix.json` | 决定性/调用者改/dtype 平价/晚强 best/refine 拒/预算/cap/trace/多重性/merge 顶 tie + Q 矩阵 | 13/13 `ok=true`，`all_ok=true`，`Q01…Q10=true`，`near_competition_reason_present.detail=[]` | PASS |
| `11_scope_diff.json` | 全树 2610 路径 diff | `changed_existing=[]`、`removed=[]`、`unreadable=[]`、`unexpected_new=[]`、`admin_changes_outside_run_root=[]`、`scope_clean=true` | PASS |
| `12_end_state.json` | 末次 HEAD/manifest/author | `head_match=true`、`manifest_mismatch_after_review=[]`、`author_files_unchanged=true` | PASS |

## 3. 逐条验收（C01–C06 / E01–E02 / S01 / B01–B02 / D01–D02）

| ID | 结果 | 独立证据（本目录） |
|---|---|---|
| **C01** | **PASS** | `02`：12/12 + 4000 随机 0 失配，ALL/NEAR/BEST_ONLY 与三终态、middle-best、弱distinct、.8 边界/tie 全通过 |
| **C02** | **PASS** | `02` 畸形/非法 settings 拒；`03` 三 digest 相等、原生 fit 与研究判断分离；`01` ledger/原型 SHA |
| **C03** | **PASS** | `03` 计数四恒等、归因 actual 19/旧证不足 25/预算缺口 7、`metric_holds_mismatch=[]` |
| **C04** | **PASS** | `03` 38/38 `all_oracle_match`+`all_closure_safe`；`04` 0/4/8 任意序闭合、0/6/12 链 unresolved，无误闭合 |
| **C05** | **PASS** | `10` 预算 0/边界/耗尽、cap、晚强 best、refine 全拒、source 上限均 unresolved 且保留 reason |
| **C06** | **PASS** | `03` 每 case 5 阶段×≥3 重复、独立 tracemalloc 峰值分离；阶段界限见 summary（非端到端/板端） |
| **E01** | **PASS** | `05` 89 frame×四box、356 统计、351255 行、records/stats 全匹配、越界 0、plane 来源为 posthoc PCA（非人工先验）、`physical=false`；`05b` 残差 351255/351255 精确一致；`06` 实际 JS 交互；`07` 输出独占/非法拒 |
| **E02** | **PASS（软件边界）** | `08` 7 条 metadata SHA 匹配、无 2026-10-04 新录制；`config_binding`/`rotation` unknown 保持 unknown；9-30 日志不冒充 10-02 录制。**B02 随之仍 BLOCKED，不因 E02 软件 PASS 而解** |
| **S01** | **PASS** | `01`/`09`/`11`：只新 run_root，2610 路径 `scope_clean=true`，生产冻结 122/122；Py3.8 AST 通过、仅 stdlib+NumPy（`08`）；真实 Go Flash/defaultDB 只读二审（本目录）；首/尾 SHA 一致（`12`） |
| **B01** | **BLOCKED** | GL-I04 继承：原 bag/layout 物理链不足，`08` 如实分层，未升级 |
| **B02** | **BLOCKED** | GL-I04 继承：录制 extrinsic/world-up/四 box 身份不足；研究搜索/局部图不关闭 |
| **D01** | **NOT_RUN** | 范围：设备/部署/新采集/网络/板端性能未执行 |
| **D02** | **NOT_RUN** | 范围：GL04 实际 DPR/正式页不由本单闭合 |

**两处前报告标签更正（保留旧报告，不改写）**：
1. `cases_with_pair_count_diff=44` 指**指标域对比**（oracle 全 W 与有界原型代表集的 pair 计数差）出现在 44 处，**并非 44 个 case**；本单共 **38 case**（`03`：synthetic 36 + real 2）。句意是“计数不声称相等，holds/终态不变”，不是 44 个案例异常。
2. **E02 软件 PASS 须显式**：录制资料定界/unknown 保持/证据表软件边界成立（`08`），但其物理身份结论不成立——B02 仍 BLOCKED。
3. **无真实数据 dominant 正例**：`seen_dominant_pool_closed` 的 6 个正例全部来自 **weak synthetic**（`03` `weak_dominant_cases=6`）；两个 real case（approved / negative_X）状态均 `unresolved`（`22_final_research_summary.real_cost`），属分类观测事实，非缺陷。

## 4. 操作组合矩阵 Q01–Q10（聚合关联域）

| Q | 结果 | 依据 |
|---|---|---|
| Q01 | **PASS** | `07`（21/21 拒）+`02`（非法 settings/畸形拒）+`01`（已有 out/输入目录拒） |
| Q02 | **PASS** | `10`（决定性/调用者原地改/`dtype_parity_float32_vs_float64`）+`11`（manifest 独占、无越界新路径） |
| Q03 | **PASS** | `02`+`10`（ALL/NEAR/BEST_ONLY×tie/弱distinct/middle-best/.8 边界 + 终态语义） |
| Q04 | **PASS** | `02`（全排列）+`04`（旧锚包络序依赖反例、链不误闭合） |
| Q05 | **PASS** | `03`（36 synthetic×seed×perm + 2 real；oracle/冻结 fit/replay/旧原型同序列 digest）+`04` |
| Q06 | **PASS** | `10`（早弱/晚强 best/晚第二平面/预算/cap/trace/source 上限，保守 unresolved） |
| Q07 | **PASS（N/A cache）** | `08` `no_cache_implemented=true`；掩码/依赖审计在 `research_01/08_assets_audit.json`；不适用 cache 满/碰撞，保留未缓存对照 |
| Q08 | **PASS** | `05`（逐 frame×4box/empty/alias/跨组/重复/坏 schema/units）+`07`（显示预算不改全统计、研究 plane 标签） |
| Q09 | **PASS** | `05`（approved/negative-X/FIT 法向分列；时间/旧零值/未知 extrinsic 不冒充身份）+`08`+`11` |
| Q10 | **PASS** | `execution_manifest`（13 命令 exit0、checker 字节不变）+`12`（首尾 SHA 一致）+ 一次只读复验 |

## 5. 冻结、回归与复用

- 生产冻结：`09` 122 文件跨 R1/R2 `prod_changed_between_baselines=[]`，`current_tree_prod_mismatch=[]`；`01` `frozen_core_and_old_evidence_unchanged=true`。
- 回归复用：`01` 记录 `../2026-10-04_gl_i05_r1/05_checks_meta.json: 423 fall / 2 follow exit0`，且冻结 src/config/tests 未变（`09`/`01` 佐证），故合法复用，不重复跑作者测试。
- 旧 I04 对照：`04` 实际 GL-I04 包络原型序依赖（0/4/8 部分序 unresolved），同序列 scalar/新原型全闭合，归因为“证书不足”而非真实竞争。

## 6. 限制与决策

- 限制：`06` 为 vm/mocked DOM，`actual_browser_DPR=NOT_RUN`；`05` 参考平面为 posthoc/WHAT_IF，`physical_verified=false`；tracemalloc 峰值非进程 RSS，阶段不同不称端到端/板端加速。
- 决策：**软件研究 PASS（建议）**——C01–C06/E01–E02/S01/Q01–Q10 经**不可变、一次执行、首尾 checker SHA 一致**的独立复验全部通过；无新增 REWORK。**B01/B02 BLOCKED、D01/D02 NOT_RUN，整单仍未 ACCEPTED**，验收表与状态由 Codex 收口。
- 仅在本不可变复验之后，Codex 方可收口 **S01/Q10** 的证据；本报告不抹除、也不无视此前 `opencode_second_review_01/` 的证据保全偏差与 `24_review_history_final/` 的恢复史。
- 停写。不进入下一单、不接入生产、不启动设备/采集/网络/GL-05。

— 00_review 完 —
