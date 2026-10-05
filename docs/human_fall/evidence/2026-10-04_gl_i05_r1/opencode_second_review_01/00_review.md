# GL-I05 R1 OpenCode独立二审（R1）— SECOND_REVIEW_SUBMITTED / STOPPED

状态：**SECOND_REVIEW_SUBMITTED / STOPPED**。只读审查，未修改任何作者/验收/状态/src/tests/config/UI/input/旧证据文件，未接入原型，未启动设备/采集/部署/网络。**整体判定：REWORK（软件研究不可 ACCEPTED）**；建议的下一轮为 R2 最小返工（见末尾）。

- 角色/约束：唯一写入者只在本目录 `docs/human_fall/evidence/2026-10-04_gl_i05_r1/opencode_second_review_01/` 新建脚本与输出；作者停写、无第二写者。
- 被审提交：`docs/human_fall/evidence/2026-10-03_gl_i05_r1/research_01/11_submission_manifest.json`（作者 Claude Code 顶替，`master`/HEAD `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`）。
- 基线：`../00_before_baseline.json`（2026-10-04T00:23:41+08:00，2507 文件）。
- native skill：`skill(name=ponytail)` 实际返回基目录 `C:\Users\30680\.config\opencode\skills\ponytail`，即 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`。**未读取/扫描/哈希外部 Codex 技能目录**，未改 model/DB/auth/权限/全局配置。
- 会话/真实模型：本目录脚本由 OpenCode Go Flash/defaultDB 历史会话执行；会话 id/model/exit 以编排者日志与 `03_second_review.jsonl`/`01_probe_session.json` 导出为准，**本审查不猜测、不称接口为 interactive**。
- 首/尾 SHA：HEAD 审查前=`cbd0be1c86a1051a9a5800dfb7263f842896e1e6`（`08_last_manifest_verify.json` 再审仍同）；`git branch`=`master`。作者 manifest head 与之一致。

## 1. 提交范围与 SHA 核验（first/last）

| 检查 | 结果 | 证据 |
|---|---|---|
| manifest 27 文件 SHA，首次核验 | 26/27 匹配；仅 `docs/human_fall/CLI_RECOVERY.md` 不匹配 | `01_manifest_verify.json`（manifest_entries=27, sha_mismatch=1） |
| `CLI_RECOVERY.md` 差异性质 | **行政交接异动**：manifest 值 `086791…`，当前=基线 `2ba2148…`，差额为 2026-10-04 “恢复登记”行；非代码/数据 | `05b_full_tree_diff.json`（modified=0）、`08_last_manifest_verify.json`（cli_admin_only=true） |
| manifest 27 文件 SHA，末次核验（作者文件非行政排除） | 0 不匹配 | `08_last_manifest_verify.json`（author_file_mismatch_excluding_admin=[]） |
| 全树 tracked+untracked 与基线比对 | modified=0, removed=0；新增 33（本审查输出 + 编排者 2026-10-04 目录文件），`git ls-files --exclude-standard` 宇宙 2540 | `05b_full_tree_diff.json` |
| `src/CMakeLists.txt` Windows 断链软链 | 以 `unreadable_winerror` 表示，未修复/未替换 | `05b_full_tree_diff.json` |
| 生产回归 / 研究自检 | `Ran 423 tests … OK`；研究 13/13 PASS | `06_author_production_suite.txt`, `06_author_research_tests.txt` |
| 最近本地 capture mtime | 2026-10-03T23:51（`captures/remote/synth_bend_v1`，早于基线），2026-10-04 起 0 新增 | `05b_full_tree_diff.json` |

结论：作者提交文件在审查前后均**字节不变**，唯一 manifest 偏差是已登记的行政交接行；生产/冻结资产/旧证据未漂移。

## 2. 独立证据脚本与结果（全部写在本目录；命令均 exit 0）

| 脚本 / 输出 | 覆盖 | 结果 |
|---|---|---|
| `01_manifest_verify.py/.json` | manifest/基线 SHA | 见上 |
| `02_independent_oracle.py/.json` | 独立 scalar ALL/NEAR/BEST_ONLY + 手算 fixture + 4000 随机对拍 + 300 原型对拍 + 畸形/非有限 + 最强首/末顺序 + 0.8 边界 | 43/46（3 个为**我**的标签笔误，已由 02b 更正） |
| `02b_corrections.py/.json` | 更正标签；复现 genuine BEST_ONLY 缺陷；扫描 ledger | 4/5；**ledger BEST_ONLY 不一致 3 例** |
| `03_ledger_and_budget.py/.json` | 32 case 覆盖；独立重算全部 witness 的三指标；计数恒等式；重复确定性；内存峰值；分阶段计时 | 12/13（唯一不匹配 = BEST_ONLY 缺陷案例） |
| `04_source_review_validate.py/.json` | 沙箱重生成 source view（不改作者输出）；payload/plane 身份/点查找/计数/覆盖行为 | 20/21（1 个为**我**的 `[]==0` 笔误） |
| `04b_source_review_correction.py/.json` | 更正上述标签 | 2/2 |
| `05_full_tree_and_recording.py/.json` | 全树（含 gitignored）初扫 | 初版（含范围误判，见 05b） |
| `05b_full_tree_diff.py/.json` | 与基线同宇宙全树 diff + 本地录制材料审计 | modified=0/removed=0/新增仅审查+编排产物 |
| `06_author_production_suite.txt`, `06_author_research_tests.txt` | 作者回归 | 423 OK / 13 PASS |
| `07_budget_trace_ast.py/.json` | 缺口语义 fixture；trace 逐事件映射；baseline/replay parity；Py3.8 AST；no-cache 审计；成本 | 18/21（2 为**我**的 fixture/字段笔误，1 为真实成本证据缺口） |
| `07b_cost_corrections.py/.json` | 更正 fixture（budget=min(512,unique+8)）；slow-vs-final 计时审计 | 5/6（1 为**我**的链式比较笔误） |
| `07c_staged_timing_check.py/.json` | 更正值：分阶段计时仅 final 台账 | 1/1 |
| `08_last_manifest_verify.py/.json` | 末次 SHA + 真实 case 证据 | 作者差异 0；approved 0 qualified；negative_X 458 witness/best1209/near-distinct2187 |
| `09_trust_boundary_and_identity.py/.json` | 直接调用 oracle 的非有限 settings/非单位法向；approved plane 来源；source view 点读/残差 | 10/11（1 FAIL=真实：不按所选 plane 重算残差） |
| `10_comparison_and_reasons.py/.json` | 是否比较 GL-I04 包络原型；reasons 归因 | 3/6（3 FAIL=真实缺口） |

注：`02`/`04`/`07` 中若干 FAIL 是**本审查脚本自身的标签/字段笔误**（scalar 期望写反、`[]==0`、`budget` 过小、`prototype.elapsed_s` 字段位置、链式比较），已分别以 `02b`/`04b`/`07b`/`07c` 新编号输出更正，未覆盖旧输出。更正后作者实现与独立 oracle 在这些点上**一致**。

## 3. 逐条验收（C01–C06 / E01–E02 / S01 / B01–B02 / D01–D02）

| ID | 结果 | 触发/来源 | 实际 vs 预期 / 根因 | 最小返工 |
|---|---|---|---|---|
| **C01** | **FAIL** | `oracle_analysis.oracle` BEST_ONLY（`oracle_analysis.py:100-106`）；TASK研究契约 | 预期 BEST_ONLY 检查所有 best/tie 与近优候选；实际 `if anchor >= other: continue` 依源顺序去重，当 best 索引大于某近优成员索引时**漏掉该 distinct 对**。手算 `[1.2@450, 1.0@500]`：独立 BEST_ONLY 得 `(0,1)` distinct、`holds=False`，作者 `holds=True`。ledger 中 `close_seed7_permuteTrue` 记录 `holds=true/count=0` 而独立 `count=1`；`close_seed7_permuteFalse` 记 2 vs 8；`negative_X` 记 44 vs 113。ALL/NEAR/终态**不受影响**（BEST_ONLY 不作闭合门） | 无向枚举：`for i<j` 判 `(i in top and j in near) or (j in top and i in near)`，或对 ordered 对去重。回归对应 3 例 |
| **C02** | **FAIL** | `experiment.py` imports；`oracle_analysis._validate_witness` / `oracle` | 预期同 source/selector/settings/seed/见序列比较冻结 baseline + **GL-I04 原型** + 新原型/oracle，且非有限参数拒。实际 `experiment.compare` 只比 `fit_ground_plane_constrained`（冻结 fit）与 `replay_frozen_search`（I04 replay），**未运行 GL-I04 包络研究原型**（存在 `…/gl_i04_r1/research_01/search_prototype.py`，接口同为 `search(points,fit_rows,up,height,settings,**budgets)`）；且直接 `oracle(witnesses, settings)` 接受 `distinct_normal_deg=NaN`（两正交法向被误标 `seen_pairwise_closed`）与零/非单位法向。`resolve_constrained_settings` 路径安全，但 oracle 作为“独立参照”无 settings/法向信任边界 | 在 experiment 中 import 并同序列运行 I04 原型，记录其 status/reasons 作保守性反例；`oracle`/`_validate_witness` 校验 settings 有限性与 `|normal|≈1`（或在 `_pairwise_distinct` 归一化），非法即 raise |
| **C03** | **FAIL** | `search_prototype.search_events` `reasons`（`search_prototype.py:42-101`）；ledger | 计数恒等式全部成立（qualified=unprocessed+refined_calls；refined_calls=rejected+produced；produced=merged_exact+retained+unstored；draws_seen=trace+trace_unrecorded；peak_stored≤budget）。但**“实际 near-distinct”未进入 `reasons`**：20 个 unresolved 中 12 例（dual/high_noise 等）`NEAR.distinct_pair_count>0` 而 `reasons=[]`，仅存于 metrics；无“仅证书不足”归因（新原型已弃包络，此桶为空属设计选择）。预期按原因区分“实际竞争/证明不足/未处理” | 在 terminal 归因中加入 `actual_near_pool_competition`（或 `close_competition`）reason；保留预算/未处理 reason |
| **C04** | **PASS** | `search_prototype` vs 独立 scalar（02/03）；顺序/链/tie | 有界原型终态与独立 oracle 在全部 32 case 一致；0/4/8°全相似任意顺序/最强首末均 `seen_pairwise_closed`；0/6/12°链留 unresolved；clean/noise 正例闭合、未“永远拒”；无 misclose（`closure_safe` 一致） | — |
| **C05** | **PASS** | 缺口 fixture（07）；ledger counts | iteration/refine/trace/candidate 预算 0/边界/耗尽均 `unresolved`；晚到强 best 在 gap 后不能升格；candidate_budget=1 的 distinct 第二 witness `unstored` → unresolved；`check_counts` 恒等 | —（归因问题归 C03） |
| **C06** | **FAIL** | `experiment.py` ledger；`22_final_research_summary.json`；return/00_diag | 预期成本拆分 sampling/raw/refine/decision/serialization、多次本机重复与固定 case 汇总、内存峰值可核查。实际只有 `elapsed_s.{baseline_fit,research_search,scoreboard_total}` 三分桶；ledger 无 repeats 汇总、无内存峰值；仅测试内 in-memory repeat 断言。另：return/00_diag 述“46s/案例 oracle”，但保留的 slow 台账最大 `prototype.elapsed_s` 仅 15.98s（negative_X），46s **在制品中不可复现**；可复现的是 synthetic `prototype.elapsed_s` 中位 0.970s→0.135s（矢量化的定性证据）。无 cache 的**否定证据成立**（5 文件无任何 cache 标记） | 加入采样/raw/refine/decision/serialization 分桶、≥3 次重复汇总、`tracemalloc` 峰值；更正“46s”表述或保存对应 profile 原件 |
| **E01** | **FAIL** | `source_review.py`；`04_*`/`09_*` | 逐 frame×4box 全统计**正确**：重生成 HTML 与作者提交**字节一致**；356 键、`stats_count_mismatches=[]`、`jsonl_total_rows=351255`、`displayed_total=13882`、89 帧、点查找键 `box\nframe_group`、显示行含 XYZ。但：(a) `approved` 面板 plane 用 I04 `posthoc_plane`（origin 实为 `posthoc_PCA_all_approved_FIT_rows_not_physical`，等于 FIT PCA，与人工先验 up_axis 相差 **52.28°**），`source_review.py` 却硬编码标签 `approved_prior_from_human_draft` → **来源误标**；(b) 切换 plane 只改信息栏，色带仍用存储残差 `color(r[6])`，不按所选 plane 重算；(c) 无 click/mousemove 点读取 handler（`row/seq/残差` 仅批量嵌入）；(d) 生成器 `write_text` 直接覆盖既有 HTML（非独占 `x`） | 用真实环/先验分标签（approved 应先验，posthoc 另列）；按所选 plane 用 source XYZ 重算显示残差；加点击/索引读取；输出用独占创建或新 root |
| **E02** | **PASS（软件边界）** | `05b_full_tree_diff.json`；`09_*`；ledger | 独立有界审计：`captures/`、`ML/` 均 gitignored，未入基线宇宙；72 个本地 capture 文件最新 mtime 2026-10-03T23:51（GL-I04 后无新增 fall 录制），2026-10-04 起 0 新增；无 extrinsic/world-up 身份 → 无新物理证据。作者标 NOT_RUN；本审查确认“无新材料、B02 不解”成立 | —（物理身份 B02 仍 BLOCKED） |
| **S01** | **PASS** | `05b`/`08`；回归 | 只新 run_root 研究/计划/回传；生产 src/tests/config/原 NPZ/draft/GL-I04/UI/HR/旧证据只读（modified=0）；Py3.8 AST 全部通过；仅 stdlib+NumPy（import 白名单通过）；423/423 + 13/13；real 指定 Go Flash/defaultDB 只读二审（本目录） | —（真实 session/model 由编排者导出） |
| **B01** | **BLOCKED** | GL-I04 继承 | 原 bag/layout 物理链不足，未升级 | 保持 BLOCKED |
| **B02** | **BLOCKED** | GL-I04 继承 | 录制 extrinsic/world-up/四 box 地面身份不足；本地图/研究搜索不能关闭 | 保持 BLOCKED |
| **D01** | **NOT_RUN** | 范围 | 设备/部署/新采集/网络/板端性能未执行（ledger `board_run=false`） | 保持 NOT_RUN |
| **D02** | **NOT_RUN** | 范围 | GL04 实际 DPR/正式页不由本单闭合 | 保持 NOT_RUN |

## 4. 操作组合矩阵 Q01–Q10

| Q | 结果 | 说明（证据） |
|---|---|---|
| Q01 | PASS | 原型入口 `resolve_constrained_settings` 拒 NaN/Inf/零/越界/未知键/bool seed（02）；oracle 直接调用的信任缺口归 C02 |
| Q02 | PASS | 无状态；caller 原地改会改变序列 digest（作者 `test_caller_mutation_between_runs_forces_new_sequence`）；ledger `open("x")` 独占创建；无 cache 污染 |
| Q03 | **FAIL** | 见 C01 BEST_ONLY 索引不对称；ALL/NEAR/tie/链/0.8 边界本身正确 |
| Q04 | PASS | 0/4/8°全排列（最强首/末）闭合；0/6/12°链与 middle-best 不误闭合（02 order_probe、作者 tests） |
| Q05 | PASS | 30 synthetic（5 类×3 seed×2 置换）+ 2 real；与冻结 baseline parity、replay digest、重复 run 一致（03/07） |
| Q06 | PASS | 四预算 0/边界/耗尽；晚强 best/晚第二平面不能升格（07） |
| Q07 | PASS（N/A cache） | 5 文件无 cache 实现；slow 台账为否定证据、未缓存实现正确；按验收“不要求为验收新增 cache” |
| Q08 | **FAIL** | 逐 frame/四 box/显示预算/计数正确；但“研究 plane 标签”对 approved 误标（同 E01a） |
| Q09 | **FAIL** | 无物理身份宣称、树差异已归因；但 approved posthoc plane 被标为人工先验（同 E01a） |
| Q10 | PASS | manifest/停写/probe 制品存在；首尾 SHA 一致；真实 session/model 由编排者导出（本审查不猜） |

## 5. 集中根因 / 最小返工 / 决策

根因族：
1. **BEST_ONLY 无向对枚举被源顺序截断**（`oracle_analysis.py:100-106`）→ C01/Q03。
2. **oracle 信任边界缺失**：不校验 settings 有限性、不校验法向单位性（`_validate_witness`）→ C02/部分 Q01。
3. **缺少同序列 GL-I04 包络原型对照**：`experiment.py` 只比冻结 fit 与 diagnostic replay → C02。
4. **归因不完整**：真实 near-pool 竞争未进 `reasons`，无“仅证书不足”桶 → C03。
5. **成本证据不足**：无 sampling/raw/refine/decision/serialization 分桶、无重复汇总/内存峰值；“46s”无法在制品复现 → C06。
6. **空间产物来源/交互契约**：approved posthoc PCA 误标人工先验、切换 plane 不重算残差、无点读取、生成器覆盖旧 HTML → E01/Q08/Q09。

最小返工（R2，单 writer，新 run_root 如 `evidence/2026-10-04_gl_i05_r2/research_01/`，复制 R1 五脚本后按根因最小修；不覆盖 R1）：
- 修 BEST_ONLY 无向枚举；加回归覆盖 best 首/末+ties。
- oracle/`_validate_witness` 校验 settings 有限性与法向单位（或归一化），补负例。
- experiment 同序列运行 I04 包络原型并记录其 status/reasons 作保守性反例。
- terminal 增 `actual_near_pool_competition` reason。
- 补分阶段成本/重复/内存峰值，更正“46s”叙述或保存 profile。
- source view 正确来源标签 + 按所选 plane 重算残差 + 点读取 + 独占输出。

**决策**：本单软件研究**REWORK**（C01/C02/C03/C06/E01 及 Q03/Q08/Q09 FAIL）；C04/C05/E02/S01 软件 PASS；B01/B02 保持 BLOCKED，D01/D02 保持 NOT_RUN。独审 PASS 前不进入下一单、不接入生产原型、不启动设备/采集/网络/GL-05；验收表/状态/ACCEPTED 由编排者决定，本审查不改。

**研究采用建议**：核心 LLM 无关的闭包语义（ALL/NEAR 三终态、预算缺口不升格、clean 正例闭合、无 misclose）在独立 scalar 对照下成立，可作为下一轮方法基础；但离线报告契约（BEST_ONLY 诊断、成本拆分、空间来源）需按上表修复后才可推荐接入范围。BEST_ONLY 缺陷不影响终态安全，属诊断可解释性缺陷。

— 00_review 完；停写，等待编排者交接 —
