Reading the review response first, then the newly whitelisted evidence, in order.

Now the source/snapshot bindings and manifest.

Now the B07 CLI facts.

已按要求先读 `08_REVIEW_RESPONSE.md`，再逐一读取新具名证据（`test_selector.py`、`run_tests.py`、05/06 command、06 verbose stderr、`benchmark_no_feasible.py`/`04_benchmark_no_feasible.json`、`01_baseline.json`、`prepare.py`、`09_integrity.json`、`source_summary.json`、`snapshot_bindings.json`、`submission_manifest.json`、`input_snapshot/{report,meta,manifest}.json`、`extra_fixture_bindings.json`、`validation_fixture_binding.json`、CLI/opencode 事实）。本轮仍只读、同指定模型、未写文件、未执行 shell/数值、未派子任务。目录枚举仍被策略拒绝；未被授权的 opencode 首个审记录、`cli_help.stderr`、`06_opencode_review*.md` 等不在白名单，故不以“未读到”推断不存在——凡本会话未亲自复算者一律标 UNKNOWN，与“真正代码 FAIL”分开。

---

# CL2-09B 独立只读审计报告（补充审查版）

## 0. 本轮回合的关键新增事实

| 事实 | 证据 | 对前轮的改变 |
|---|---|---|
| 选择器有专属具名运行 | `candidate_regression_06.stderr:1-31,73-75` | 前轮“test_selector 无运行日志”缺口**已闭合** |
| 合并运行含选择器、带 `-W error` | `candidate_regression_05_command.json:2-20`、`..._06_command.json:2-23` | 前轮“未证 -W error/未含选择器”**已闭合** |
| 候选源码 SHA 与补丁自校验 | `06_command.json:22-23` `test_sha256=f395…`、`candidate_sha256=066a81…`；`run_tests.py:20,22` | 候选版本可核对 |
| 非共线无可行项完整枚举实测 | `benchmark_no_feasible.py:9-24`、`04_benchmark_no_feasible.json` | 前轮“最坏路径未测”**已补测** |
| 输入 report/meta 副本入证据 | `snapshot_bindings.json`、`input_snapshot/*` | 121647 证据**自包含** |
| 完整性/来源 SHA 绑定 | `09_integrity.json:1499-1562`、`source_summary.json:83-136` | B01/B08 证据**基本闭合** |
| 实际 CLI/权限事实 | `cli_version.stdout`、`cli_models.stdout:5`、`opencode_actual_model_02.json`、`05_opencode_raw_output_02_command.json`、`opencode_permissions.json`、`cli_effective_agent_02.stdout` | B07 **有 CLI 运行事实** |

---

## 1. 逐项 B01–B08

### B01 冻结 source/input/历史 SHA；main 上下文
- **代码/逻辑判定：PASS（结构闭合）**。`prepare.py:26-48` 建立 `main_HEAD`/`main_branch`/`main_status`、`main_all_files=inventory(R)`（含 untracked/ignored，仅排除 `.git`，`prepare.py:14-23`）、`source_bindings`、`historical_files`、`input_files`。`source_summary.json:6-81` 给出 origin(=cl208audit)→frozen 逐文件 SHA；`source_summary.json:83-89` 绑定 `audit_inputs/cap_20261009_121647/{meta,points.bin}` 与 job `{report,manifest,domain.npz}`。`09_integrity.json:1469-1497` 复核 input 五件，全 `match:true`；`:1560` `main_HEAD_after=347a5bf0…` 与起点一致。
- **反例检索**：`prepare.py:40-41` 断言 live main `pc_apps/human_replay/floor_sheet.py` == frozen，`09_integrity.json:1547` `current_main_floor_sheet_unchanged:true`；`09_integrity.json:1548-1558` 如实记录运行期两个**无关** overlay 文件发生变化（main 是脏的），未掩盖。
- **UNKNOWN（执行）**：本会话未执行任何 SHA，全部为作者复算；`01_baseline.json` 的 `main_all_files` 超 50KB 我在本会话只读到开头（`main_HEAD/main_status/首段摘要`），其**全量上下文清单**我未逐条核完。
- **最小修复**：无需改码；若要独立可核，交付一个由审阅方本地 `sha256` 复核 `01_baseline`/`09_integrity` 的输出即可（当前属执行层 UNKNOWN）。

### B02 5 格反例修复；三原门不降
- **代码/逻辑判定：PASS**。修复在 `candidate/floor_sheet.py:242-266`：旧成功早退（`:242-244`）；旧失败先真共线快速否定（`:245-251`）；再对全部 `itertools.combinations(range(n),4)` 枚举并在可行集最大化 `min_sep`（`:255-266`）。三原门逐字复用 frozen（`candidate:237-238` vs `frozen:236-237`）；`SHEET_PROFILE` 的 `.50/.10` 与 `cell_m=.25` 未改（`candidate/floor_sheet.py:32`、`floor_detector.py:9`）。
- **执行证据**：`candidate_regression_06.stderr:6` `test_known_five_cell_false_rejection ... ok`，`Ran 35 tests ... OK`（`:73-75`）。
- **反例检索**：共线剪枝只删真共线组合（协方差秩 1 ⇒ `condition=0`，必不合格）；整数叉积精确且键幅度 `|index|≤400`，int64 无溢出 → **未发现误删合格解**。
- **判定**：无代码 FAIL；执行层为本会话未复算 = UNKNOWN（证据一致）。

### B03 原成功逐字保留；无可行仍拒绝；并列可复验
- **代码/逻辑判定：PASS**。`describe`（`candidate/floor_sheet.py:229-240`）与 frozen 返回尾（`frozen/floor_sheet.py:229-239`）为同一批表达式；旧成功原样返回且 >24 不重排名（`:242-244`）；无可行时 `winner` 初值 `previous`（`:254,267`）返回旧失败 dict。
- **并列策略**：新增 `test_selector.py:81-85` 断言 `selected==[[0,0],[0,4],[0,8],[2,6]]` 且反序输入一致；对应兜底 `separation <= winner_sep`（`:262`）保留最先组合。`:87-90` 断言重复 key 不挤掉有效四元组。均 `06.stderr:8,3 ... ok`。
- **反例检索**：会话真实数据 `03_session121647.json:49-98` `original_selector==candidate_selector`，`:99` `ROI_unchanged:true`。**未见 dict 分歧反例**。
- **判定**：无代码 FAIL；执行层 UNKNOWN（作者运行，本会话未复算）。

### B04 ≤24 与 >24 失败路径；完整搜索；最坏 O(n4) 成本与实测
- **代码/逻辑判定：PASS**。≤24 旧路径本已全枚举仅评单点；>24 旧贪心失败后进入同一全枚举（`candidate:255-266`）。
- **新增实测**：`benchmark_no_feasible.py:11-23` 构造“非共线但无可行四元组”场景（`(8(k-n//2),0)` 加 `(0,1)`），`assert not result['ok'] and quartets_visited==math.comb(n,4)`（`:23`）证明**全枚举走到**。`04_benchmark_no_feasible.json`：n=25 `quartets=12650/svd=1772/0.147s`；n=60 `487635/30857/4.430s`；n=100 `3921225/152097/38.99s`。scope（`:97`）声明“含 mock 计数开销、board NOT_RUN、未声明无条件最坏上界”。
- **诚实性**：`04_benchmark.json:245` 与 `benchmark_no_feasible.py:27` 均未假称板端时延。**前轮“最坏未测”缺口已补**。
- **限制（非 FAIL）**：实测仅到 n=100；`svd_calls≪quartets` 说明 `sep<.5m` 预筛有效，但**无可行时**仍需 O(n⁴) 遍历（计数已证）；更大 n 不可用于板端/生产 → `candidate_version.json:5` `production_integrated:false` 与此一致。
- **判定**：无代码 FAIL；性能为**已知限制**；执行层 UNKNOWN（作者运行）。

### B05 直接入口/v2/v3 调用者回归；v1 verbatim；py3.8；-W error
- **代码/逻辑判定：PASS**。v2 入口首行直接 `return detect_floor_regions(...)`（`candidate/floor_sheet.py:273`）；`source_summary.json:7-35`/`09_integrity.json:1503-1546` 证明**仅 `floor_sheet.py` 变**（`candidate_only_changed_files:["floor_sheet.py"]`），`floor_detector.py`/`floor_roi.py`/`leveling.py`/`validation.py`/estimators 与 frozen **同 SHA**；`_select_four`(15cm) 未改。
- **v3 路由边界**：新增 `test_selector.py:92-111` 以打桩强制 v2 走修复路径，并令 `fine_boxes` 抛错，断言 v3 返回 `lowest_floor_sheet_v2` 且 regions 为 0.25m——即“v3 采用修复后 v2 四区、不落 15cm”。`06.stderr:10 ... ok`。
- **执行证据**：`candidate_regression_06_command.json:2-23` argv=`python -X utf8 -B -W error -m unittest -v test_selector floor_detector_test floor_sheet_test floor_roi_test leveling_test`，`cwd` 与 `PYTHONPATH=candidate;frozen;E` 明列，`exit_code:0`，`test_sha256=f395…`、`candidate_sha256=066a81…`；`06.stderr:73-75` `Ran 35 tests ... OK`（含选择器 10 项具名，`:1-10`）。
- **反例/缺口**：py3.8 仅 `test_selector.py:78-79` 语法解析，**板端 3.8 运行 NOT_RUN**；`-W error` 是 py3.12 本地语义。
- **判定**：无代码 FAIL；执行层 UNKNOWN（作者运行，本会话未复算）。

### B06 121647 原 ROI/TLS/门控不变；不换区；TLS 仍 BLOCKED；不放行
- **代码/逻辑判定：PASS**。旧成功早退使 121647 不进入兜底（B03）；门控文件未改（B05 SHA 一致）；放行仅 `recommended=="tls"`（`leveling.py:397`），TLS 无效则不放行。
- **输入自包含证据**：`input_snapshot/report.json` 显示 `auto_candidate.kind="lowest_floor_sheet_v2"`（`:42`）、`code_hashes.floor_sheet.py=dd1b58…`（`:168`，即**frozen**）、`roi.clean_cells=11/min_sep=0.9014/independent=4/condition=0.4941`（`:93-98`）、`estimators.tls.valid=false, reject_reasons=["GL_HOLDOUT_QUALITY"]`（`:219-222`）、holdout 72 region2 `status:FAIL, p95=0.050291869…`（`:315-321`）、`ransac.valid=false`（`:653`）、`consensus="NO_RECOMMENDATION", recommended=null`（`:899-901`）。该 p95 与 `03_session121647.json:117` `ROI2_ordinal72.p95_m` 逐位一致，且 `:122` `effective_TLS:"BLOCKED"`、`:123-124` `new_TLS_estimation=false/new_export=false`。
- **反例检索**：`03_session121647.json:74-98` candidate 与 original 完全一致、`:99` ROI 不变、`session_probe.py:31-39` 用旧 `_clean_cells` 复算并断言 `legacy==candidate`、holdout 72 FAIL、TLS 无效；**未见替代放行数据或换区**。
- **UNKNOWN（执行）**：上述全为作者执行；本会话未重跑；且 `session_probe.py:44` 的 `"BLOCKED"` 是标签，实际约束来自 `:39,:44` 对 report 的 assert。因 report/meta 已入证据，结论自洽，但仍属作者复算。
- **最小修复**：无需改码；若需独立可核，审阅方对 `input_snapshot/report.json` 复述 `recommended=null` 即可。

### B07 OpenCode 指定模型真实只读独审
- **代码/逻辑判定：PASS（CLI 事实齐备）**。`cli_version.stdout`=`1.18.35`；`cli_models.stdout:5` 含 `opencode-go/deepseek-v4.1-flash`；`opencode_actual_model_02.json:2-8` `models=["opencode-go/deepseek-v4.1-flash"]`、`session=ses_edfc…`、`CLI_version=1.18.35`、`exit_code=0`；`05_opencode_raw_output_02_command.json:2-8` argv=`opencode run --pure --agent cl209baudit --format json --model opencode-go/deepseek-v4.1-flash '<prompt>'`、`exit_code=0`；`opencode_permissions.json:2-15` 仅 `read:true`，其余工具 `false`；`cli_effective_agent_02.stdout:2-8,1530-1560` 生效 agent=`cl209baudit`，`*`→deny、`read *`→deny、逐文件 allow、`external_directory`→deny。
- **反例/限制（非 FAIL）**：①这是**作者保存的 CLI 事实**，我未亲自复算 CLI；②`--pure` 语义与 `cli_help.stdout` 为空（help 实际在未授权的 `cli_help.stderr`），**help 文本本会话不可读** = UNKNOWN；③“模型真实身份”由 `opencode_actual_model_02.json` 声明，我无法在本会话内自证。
- **判定**：无代码 FAIL；执行/权限层 UNKNOWN（作者证据）。

### B08 证据 manifest 与起止 SHA；append-only return；不自行 ACCEPTED
- **代码/逻辑判定：PASS（前置闭合）**。`submission_manifest.json` 列全文件 SHA（含 candidate/frozen/CLI/input_snapshot），`:148` 自述“Pre-supplement file closure；Final CLI/return/full seal 为后续记录，本 manifest 永不覆盖”；`09_integrity.json:1499,1547,1561` `isolated_full_tree_unchanged=true`、`current_main_floor_sheet_unchanged=true`、`return_append_only=true`；`prepare.py:48-49` 记录 `return_before_sha256` 并落 `return_before.bin`；`09_integrity.json:1562` 明确“只有不可变隔离输入授权本次运行，非整树冻结”。
- **诚实性**：**未冒称最终 seal 已完成**（用户亦确认最终 return/完整 seal 在我结束后追加）。
- **UNKNOWN（执行/未完成）**：最终 return/seal 尚未生成；首个 OpenCode 审记录（`06_opencode_review*.md`）不在白名单，本会话不可读。
- **判定**：无代码 FAIL；执行/收尾层 UNKNOWN。

### E01 / D01
- `00_SCOPE_AND_ACCEPTANCE.md:17-18`：E01（接生产/发布/部署）=**BLOCKED**、D01（设备/物理/采集/B2/B3）=**NOT_RUN**；`candidate_version.json:5` `production_integrated:false`、`09_integrity.json:1499` 隔离树未变。**维持。**

---

## 2. 主动反例检索汇总（更新）

| 关注点 | 结论 | 依据 |
|---|---|---|
| 原成功完整 dict 逐字保留？ | 代码层 YES；执行 UNKNOWN | `candidate:229-244` = `frozen:229-239`；`03_session121647.json:49-98`；无分歧反例 |
| 小候选失败后搜全可行四元组？ | 代码层 YES | `:255-266` 全 `combinations`；`06.stderr:6` |
| 大候选失败后搜全可行四元组？ | 代码层 YES + 计数实测 | `:255-266`；`benchmark_no_feasible.py:23` 断言 `quartets==C(n,4)` |
| 叉积共线剪枝/数值/重复 key 误删合格解？ | 否 | 只删真共线（`condition=0`）；整数精确、`|index|≤400` 无溢出；`06.stderr:3,8` |
| 原间距/独立/条件门不变？ | YES | `candidate:237-238`=`frozen:236-237`；profile 未改（`09_integrity.json:1503-1546`） |
| v2/v3/15cm 行为范围诚实？ | YES（已声明联动） | `08_REVIEW_RESPONSE.md:9` 明说 v2 修复后 v3 不再落 15cm；`test_selector.py:92-111` 覆盖 |
| 源码 SHA 版本诚实？ | 结构 YES；执行 UNKNOWN | `candidate_version.json:2-4`；`06_command.json:22-23`；`source_summary.json:91-133` |
| 121647 TLS/ROI 保持 BLOCKED？ | YES（自包含）；执行 UNKNOWN | `input_snapshot/report.json:219-222,899-901`；`03_session121647.json:99,122` |
| 最坏 O(n4) 限制交付/生产？ | 是（已声明、已实测至 n=100） | `04_benchmark_no_feasible.json`；`benchmark_no_feasible.py:27`；`production_integrated:false` |
| 输入/历史完整性未亲自执行 SHA？ | UNKNOWN | 见 B01/B08 |

---

## 3. 分类结论：真正代码 FAIL 与 UNKNOWN 分开

**真正代码 FAIL：无。** 未在 candidate 源码、门控、v2/v3/15cm 路由、兜底搜索中发现逻辑缺陷；前轮所列覆盖缺口（选择器无日志、-W error 未证、最坏路径未测、输入副本缺失、B07 无 CLI 事实）**除下列执行层外均已由新证据闭合**。

**UNKNOWN（作者执行/权限/文档，未经本会话复算）：**
1. 全部 SHA 完整性（B01/B08）——我未本地执行 `sha256`。
2. `01_baseline.json` 的 `main_all_files` 全量上下文（本会话读取被 50KB 截断，仅读到表头与首段）。
3. B07 的 CLI/权限事实——作者保存，我未复算；`--pure` 语义与 `cli_help.stderr`（未授权）不可读。
4. 板端 Python 3.8 运行与真实板端时延——NOT_RUN，仅本地 3.12 + 3.8 语法解析。
5. 首轮 OpenCode 审文本（`06_opencode_review*.md`）与最终 seal/return——未授权/未完成。

**限制（非 FAIL，需保留）：**
- 兜底仅在“旧失败”时进入；无可行大 n 仍为 O(n⁴)（n=100 实测 38.99s，含 mock 开销），**不适合未授权的板端/生产接入**。
- v2 修复会改变 v3 有效触达（部分原 15cm 场景改由 v2 25cm 承接）；121647 因 v2 旧已成功而不受影响。
- 性能与数值均为作者执行证据，本报告不冒称重跑。

**范围内最小修复/补证建议：** 无需改动 candidate 源码或 patch。仅需在最终 return/seal 中补：①本地独立 `sha256` 复核输出（B01/B08）；②`--help`/`--pure` 说明与最终 session/seal 记录（B07/B08）；③（可选）追加 n≥150 无可行项实测以界定生产风险边界。

---

## 4. 处理范围声明
- 本轮仅隔离 candidate，不接生产；原 profile 阈值未改；未要求通过降门控/换 ROI 使 121647 放行；121647 有效 TLS 仍 BLOCKED。
- 本报告所有 PASS 均为“读码 + 作者证据一致”，凡未经本会话复算者标 UNKNOWN。

AUDIT_COMPLETE