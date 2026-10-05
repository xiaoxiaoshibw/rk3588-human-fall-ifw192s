# GL-I05 R2 OpenCode 独立二审（同一验收 v1）— SECOND_REVIEW_SUBMITTED / STOPPED

状态：**SECOND_REVIEW_SUBMITTED / STOPPED**。只读审查；未改作者源码/验收/回传/状态/旧证据，未接入运行时不改生产，未启设备/采集/部署/网络。**结论：软件条目全部 PASS（建议），无新增 REWORK；B01/B02 BLOCKED、D01/D02 NOT_RUN，整单未 ACCEPTED（由 Codex 收口）。**

- 被审提交：`research_01/11_submission_manifest.json`（`master`/HEAD `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`；`active_ledger=experiment_results_identity_verified.json`，`active_spatial=spatial_02/source_review.html`）。
- 基线：`../00_before_baseline.json`、`../17_submitted_baseline.json`（2610 路径，2026-10-04T01:13:01+08:00）。
- native skill：`skill(name=ponytail)` 实际返回 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`。**未读取/扫描/哈希作者/Codex 的 `.codex` 技能目录**，未改 model/DB/auth/权限/全局配置。
- 会话/真实模型/exit：由编排者导出（`18_*` probe、`20_second_review.jsonl`），本审查不猜测、不代替。
- 首/尾 SHA：`cbd0be1c86a1051a9a5800dfb7263f842896e1e6`（`11_scope_diff` 末次复核 author 文件 0 变更；`12_end_state` 再证）。

## 1. 提交范围与 SHA（程序化，非人工目测）

| 检查 | 结果 | 证据 |
|---|---|---|
| manifest 76 文件 SHA | **76/76 匹配**，无缺 | `01_manifest_scope.json` |
| active ledger `implementation_sha256`（6 项，含两同名原型全路径+当前 core） | 0 不匹配 | `01_manifest_scope.json` |
| `old_new_implementation_sha`（R2 与 GL-I04 `search_prototype.py` 全路径） | 0 不匹配 | `01_manifest_scope.json` |
| 全树 2610 基线路径 | changed=0 / removed=0 / unreadable=0；`scope_clean=true` | `11_scope_diff.json` |
| 新增路径分类 | 63：均在本 run_root（编排/审查产物）、4 行政状态文件、或基线前已存在未跟踪资料；`unexpected_new=[]` | `11_scope_diff.json` |
| 生产冻结（R1 vs R2 基线 122 个 src/config 文件 + 当前离线） | 0 漂移；R1 423/2 回归可合法复用 | `09_frozen_compare.json` |
| `src/CMakeLists.txt` Windows 断链软链 | 以基线 `unreadable_winerror` 保留，未替换 | `11_scope_diff.json` |
| 末次 HEAD/manifest | `author_files_unchanged=true`，HEAD 一致 | `12_end_state.json` |

## 2. 独立脚本与结果（全部新写本目录，均 exit 0）

| 脚本/输出 | 覆盖 | 结果 |
|---|---|---|
| `01_manifest_scope.py` | 76 SHA、ledger/原型 SHA、scope、HEAD | 全通过 |
| `02_scalar_reference.py` | **独立 scalar** ALL/NEAR/BEST_ONLY+终态；0/4/8 全排列、0/6/12 链、middle-best、弱distinct dominant、.8 边界、top tie；**4000 随机对拍**；畸形 event/settings/法向拒 | 12/12 PASS，随机 0 失配 |
| `03_ledger_check.py` | 解析 3MB active ledger（不入上下文）：38 case、digest、5 阶段×3 重复、tracemalloc、计数恒等、归因、merge | 全通过 |
| `04_old_i04_fixture.py` | **实际 GL-I04 包络原型**同序列对照；0/4/8 反例；链 | 旧证序依赖 true；新/scalar 全闭合；链皆 unresolved |
| `05_spatial_parse.py` | 解析 28.8MB HTML payload vs 冻结侧车 | 全通过 |
| `05b_spatial_residual.py` | 页面残差公式 vs 冻结 `signed_residual_m` | 351255/351255 精确一致 |
| `06_js_consumer_independent.js` | 实际页面 JS：选面残差/点击/索引/frame/box/显示预算 | PASS（非真实 DPR） |
| `07_source_guards.py` | payload schema/frame/units/alias/duplicate/foreign/row/非finite/越界/独占输出拒 | 18/18 通过 |
| `08_frozen_and_audit.py` | 7 条录制 metadata SHA、无新录制、unknown 保持、Py3.8 AST、无 cache | 全通过 |
| `09_frozen_compare.py` | 生产冻结跨 R1/R2 | PASS |
| `10_conservation_qmatrix.py` | 决定性/调用者改动/dtype 平价/晚强 best/refine 拒/预算/cap/trace 快照/多重性/merge 顶 tie + Q 矩阵 | 全通过 |
| `11_scope_diff.py` | 全树 2610 路径 SHA diff | `scope_clean=true` |
| `12_end_state.py` | 末次 HEAD/manifest/author 不变 | PASS |

## 3. 逐条验收（C01–C06 / E01–E02 / S01 / B01–B02 / D01–D02）

| ID | 结果 | 触发/来源 | 实际 vs 预期 / 独立证据 | 最小返工 |
|---|---|---|---|---|
| **C01** | **PASS** | oracle 三指标/终态；TASK 研究契约 | BEST_ONLY 改为无向枚举（`oracle_analysis.py:109-110`）；4000 随机序列 + best 首/末 + tie + middle-best + .8 双边 + 0/4/8、0/6/12 手算全部与独立 scalar 一致；弱 distinct 只 dominant。R1 源序截断缺陷已消除 | — |
| **C02** | **PASS** | 同 source/selector/settings/seed/序列；旧原型对照；信任边界 | `oracle` 先 `resolve_constrained_settings`（NaN/Inf/bool/0/未知键拒）再逐 witness 校验有限单位法向/非负int support；`experiment.py:36-39,110` 同序列运行**实际 GL-I04 原型**并记 status/reasons；ledger 三 digest 相等。R1 两缺陷已修 | — |
| **C03** | **PASS** | events 计数闭合/原因归因 | 计数四恒等成立；`actual_near_pool_competition` 在 NEAR 失败时进入 reasons，独立核对“所有 NEAR 失败 case 都带该 reason”=0 例外；归因 actual 19/旧证不足 25/预算缺口 7 | — |
| **C04** | **PASS** | 有界实现 ≡ 同序列 oracle | 38/38 `oracle_match`、`closure_safe`；0/4/8 任意顺序闭合、0/6/12 链 unresolved；clean/低噪正例闭合不“永远拒”；无 misclose | — |
| **C05** | **PASS** | 预算/pending→terminal/晚到 | 四预算 0/边界/耗尽、candidate cap 1（两 distinct→unstored）、晚强 best、refine 全拒、source 2000 上限均 unresolved 且保留 reason；未处理不升格 | — |
| **C06** | **PASS** | 成本拆分/重复/内存/决策 | 每 case `cost_repeats` ≥3，含 sampling/raw/refine/decision/serialization；独立 `tracemalloc` 峰值且声明与计时分离；`cost_comparison_boundary` 明示阶段不同、不称端到端/板端加速；R1“46s”无制品，本轮不再沿用，由关闭日志/ledger 支撑 | — |
| **E01** | **PASS** | 逐 frame×box 源定位/显示/plane 来源/输出 | payload 89 frames（seq/ordinal 为 int 标量）/4 box/356 全统计/351255 行；records 与冻结侧车逐项（含顺序）一致、stats.count 一致、越界 0；display cap 仅影响绘制；approved plane 来源=`posthoc_PCA_all_approved_FIT_rows_not_physical`（**非**人工先验硬编码），up 仅输入先验；JS 按所选 plane 重算残差并有 click/索引；输出 `x`+新目录独占。R1 四缺陷已修 | — |
| **E02** | **PASS（软件边界）** | 有界录制资料 | 7 条 metadata SHA 匹配、无 2026-10-04 新录制；`recording_config_binding`/`extrinsic_from_to`/`measured_source_to_world_rotation` 均 unknown；9-30 日志明确不能绑定 10-02 录制；无新物理证据 | —（B02 仍 BLOCKED） |
| **S01** | **PASS** | 范围/单 writer/停写/二审 | 只新 run_root 研究/计划/回传/状态；生产与旧证据 0 漂移；Py3.8 AST 全通过、仅 stdlib+NumPy；真实 Go Flash/defaultDB 只读二审（本目录），session/model/exit 由编排导出 | — |
| **B01** | **BLOCKED** | GL-I04 继承 | 原 bag/layout 物理链不足，未升级 | 保持 |
| **B02** | **BLOCKED** | GL-I04 继承 | 录制 extrinsic/world-up/四 box 身份不足，全局图/研究搜索不能关闭 | 保持 |
| **D01** | **NOT_RUN** | 范围 | 设备/部署/新采集/网络/板端性能未执行 | 保持 |
| **D02** | **NOT_RUN** | 范围 | GL04 实际 DPR/正式页不由本单闭合 | 保持 |

## 4. 操作组合矩阵 Q01–Q10（聚合关联域，任一子域失败即整行 FAIL）

| Q | 结果 | 依据 |
|---|---|---|
| Q01 | **PASS** | 合法 settings/输入通过；缺 source/坏 schema/frame/units/alias/duplicate/foreign/row/非finite/越界/非法 settings 全拒；已有 out/输入目录拒（`07`、`02`） |
| Q02 | **PASS** | 同内容重跑决定性；caller 原地改点/settings 改变结果；float32↔float64 数值平价；无持久 cache 污染；manifest 独占 |
| Q03 | **PASS** | ALL/NEAR/BEST_ONLY×tie/弱distinct/链 middle-best/.8 边界 + 全/预算不足终态语义（`02`/`10`） |
| Q04 | **PASS** | 0/4/8 全排列全闭合；0/6/12 链/中间 best 不误闭合；旧锚包络序依赖反例（`02`/`04`） |
| Q05 | **PASS** | 36 synthetic（clean/noise8mm/high_noise35mm/weak/dual/close×3seed×2perm）+2 real；oracle、冻结 fit/replay、**实际旧 GL-I04 原型**同序列 digest 相等；R1 旧原型比较缺陷已补 |
| Q06 | **PASS** | 早弱/晚强 best/晚第二平面×全/早断/refine 0 或耗尽/candidate cap/trace/source 上限，均保守 unresolved（`10`） |
| Q07 | **PASS（N/A cache）** | 无 cache 实现（静态扫描 0 命中）；掩码 SHA/依赖表/unknown 于 `08_assets_audit.json`；不刺激缓存满/碰撞（不适用），保留未缓存正确对照 |
| Q08 | **PASS** | 逐 frame×4box、empty/alias/跨组/重复/坏 schema/units 拒；显示预算不改全统计；研究 plane 标签正确（`05`/`07`） |
| Q09 | **PASS** | approved/negative-X/FIT 法向研究分列；录制时间/旧零值/未知 extrinsic 不冒充身份；共享树新增/修改归因，graph 不判身份（`05`/`08`/`11`） |
| Q10 | **PASS** | 完整 manifest/关闭日志 hash/停写/fresh probe/只读二审；首尾 SHA 一致；服务失败不伪 PASS、不换 model/DB/auth |

## 5. 根因复核（R1 → R2）

| R1 根因 | R2 修复 | 独立确认 |
|---|---|---|
| BEST_ONLY 源序截断 | 无向对枚举 | `02` 4000 随机 + fixtures |
| oracle 信任边界缺失 | resolve settings + 单位法向/有限校验 | `02` 非法输入全拒 |
| 未跑 GL-I04 包络原型 | experiment import 全路径旧原型同序列 | `04` 序依赖反例、`03` 归因 |
| near 竞争未进 reasons | `actual_near_pool_competition` | `03`/`10` 0 例外 |
| 成本证据不足/“46s” | 5 阶段×3 重复+独立 tracemalloc，更正叙述 | `03`/`10` |
| 空间来源/残差/点击/覆盖 | 真 PCA 来源、按所选面重算、click/索引、独占输出 | `05`/`05b`/`06`/`07` |

**最小返工：无。** 未发现新的契约违反。

## 6. 声明与边界核验（任务特别要求项）

- **指标域**：oracle 用全 W；有界原型 pair 索引/count 与 top_tie_count 用精确签名代表集，全多重性保留在 `produced/merged_exact` 与逐事件 trace；只声称 holds/终态不变、**不声称 pair 数量相等**。实测 `cases_with_pair_count_diff=44`、holds 全一致、merge 安全独立复现（`03`/`10`）。
- **精确签名合并**：相同 normal/offset/support 合并，support 不同不合并；merge 后终态与全 W scalar 一致；重复顶 tie + 一个真实 distinct 仍 unresolved（`10`）。
- **0/4/8 归因**：旧固定锚包络序依赖失败（`similarity_envelope_not_closed`），同序列 scalar 与新原型全闭合——证明“证书不足”而非真实竞争（`04`）。
- **成本阶段**：冻结 fit 含原生 validation，research search 含全部合格精炼与精确 decision，序列化单独计，非端到端/板端加速（`03`/`10`）。
- **空间消费链**：`D` payload 与冻结侧车逐项一致；残差公式 `dot(xyz,normal)+offset_m` 与冻结 `signed_residual_m` 全量一致；JS 检查为 mocked DOM，`actual_browser_DPR=NOT_RUN`（`05`/`05b`/`06`）。
- **录制未知项**：config/extrinsic/rotation unknown 保持 unknown，未知永不升级为测得身份（`08`）。

## 7. 决策

- **软件研究：PASS（建议）** — C01–C06、E01、S01、Q01–Q10 均通过独立验证；B01/B02 保持 BLOCKED，D01/D02 保持 NOT_RUN；**整单未 ACCEPTED，验收表/状态由 Codex 收口**。
- 研究采用建议：独立 scalar 下 ALL/NEAR 三终态、预算缺口不升格、clean 正例闭合、无误闭合成立，可作为下一轮方法基础；`seen_dominant_pool_closed` 在真实数据未自然出现（仅 weak fixture），属分类观测事实而非缺陷。
- 停写。等待编排者收口；不进入下一单、不接入生产、不启动设备/采集/网络/GL-05。

— 00_review 完 —
