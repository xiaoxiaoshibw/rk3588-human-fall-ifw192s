I'll begin by reading the mandated skill file first, as instructed, using its absolute path.

Skill read succeeded — read access is functional. Continuing with the acceptance table and scope document.

Now the patch and version manifest.

Now the test selector and candidate core source.

Now the frozen baseline to compare verbatim behavior.

Now the regression logs and probe/benchmark harness scripts.

Now the probe and benchmark harnesses.

Now the benchmark harness.

Let me list the evidence directory to check for files referenced by the harnesses (prepare.py, 01_baseline.json).

Directory enumeration is blocked by policy (only explicit paths are whitelisted). Note: `prepare.py` and `01_baseline.json` referenced by the harnesses are not whitelisted. Continuing with specific files.

Now comparing caller `leveling.py` (frozen vs candidate) for B05/B06 identity/purity.

Comparing the sheet test in frozen vs candidate, and checking the TLS/quality module that gates 121647.

Now the v3 ROI test (checks 15 cm fallback behavior) and the quality/gate module used by 121647.

# CL2-09B 独立只读审计报告

审计员：OpenCode 指定模型 `opencode-go/deepseek-v4.1-flash`（只读）。
方法：仅用 read 逐个读取提示中绝对路径文件；未写文件、未执行 shell/数值、未派子任务、未访问网络。全部结论基于源码与证据文本比对；凡需执行 SHA/数值而未在本会话执行者，一律 UNKNOWN。日志属作者执行证据，本报告不冒称重跑。

读取状态：首轮首个合法 skill 读取（`PONYTAIL_SKILL.md`）成功，随后全部列名文件读取成功；目录枚举被策略拒绝（仅显式路径白名单），因此 `prepare.py`、`01_baseline.json`、外部 job 目录等未被授权读取，构成本轮证据边界。

---

## 一、逐项审计 B01–B08

### B01 冻结 source/input/历史 SHA；执行用冻结副本
**判定：UNKNOWN（证据不可核）**
- `candidate_version.json:2-6` 只给两个不透明摘要 `source_sha256=066a81…`、`frozen_sha256=dd1b58…`，**无文件→摘要映射**，无法确认覆盖哪些文件，也无 main 全树（含 untracked/ignored）起止 SHA。
- `session_probe.py:5,10-11` 依赖 `prepare.py` 与 `01_baseline.json`（内含 `input_files` 摘要表），二者均不在白名单/证据集中；`session_probe.py:11` 的 `assert sha(p)==digest` 无法被独立复核。
- 本会话未执行 SHA（禁止），故输入/历史完整性 = UNKNOWN。

### B02 5 格反例修复；三原门不降低
**判定：代码层结构成立，执行证据 UNKNOWN**
- 反例定义见 `test_selector.py:22-29`：`keys=[(0,0),(0,4),(0,8),(0,12),(2,6)]`，断�言 `old`（frozen）失败、candidate 成功且 `condition≥.1`、`min_sep_m≥.5`、`independent==4`、可行四元组数==4。
- 修复路径 `candidate/floor_sheet.py:242-267`：旧成功早退（`242-244`）；旧失败后先做完全共线快速否定（`245-251`），再对**全部** `combinations(range(n),4)` 枚举並在可行集最大化 `min_sep`（`255-266`）。三原门在 `describe`（`237-238`）逐字复用 frozen `frozen/floor_sheet.py:236-237`，`SHEET_PROFILE` 的 `.50/.10`（candidate `32`）与 frozen `32` 完全一致，`PROFILE["cell_m"]=.25`（`floor_detector.py:9`）未改。
- **反例检索**：完全共线剪枝只删除“真正共线”组合，而共线集合的协方差秩 1、最小奇异值为 0，`condition=0<.1`，属必然不可行，不构成“误删合格组合”；整数叉积精确（键为单元索引，`|coord|≤100 ⇒ |index|≤400`，int64 无溢出风险）。未见误删合格解。
- **证据缺口**：`test_selector.py` 未自固定候选路径（`test_selector.py:5` `from floor_sheet import …` 依赖调用时 `sys.path`），且**没有任何保存的 test_selector 运行日志**（见 B05）。故此条无法以执行证据确认，判定 UNKNOWN（结构成立）。

### B03 原成功结果逐字保留；无可行仍拒绝；排序/并列可复验
**判定：UNKNOWN（结构上等价，无执行证据）**
- 逐字性核验：frozen 成功返回体 `frozen/floor_sheet.py:229-239` 与 candidate `describe`（`candidate/floor_sheet.py:229-240`）为**同一批表达式**（`keys[list(index)].astype("f8")`、`min_sep=separation*cell_m`、同一 `dist/independent`、同一 `svd`/`condition`、同一返回字典键序）。`candidate/floor_sheet.py:242-244` 在 `previous["ok"]` 时原样返回，且 >24 旧贪心成功后不重排名（`243`）。
- 无可行时 `winner` 初值为 `previous`，兜底遍历无命中即返回旧失败 dict（`254,267`），保持拒绝，见 `frozen/floor_sheet.py:210-212` 一致。
- 排序/并列：`keys` 内部 `sorted`（`208`），输入顺序不敏感；兜底以 `separation <= winner_sep` 跳过（`262`）实现“取最大间距、并列保留最先组合”的确定策略。
- **未见 dict 分歧反例**（浮点运算序列相同，故按位一致）。但缺少针对该等价性的运行日志，判定 UNKNOWN。

### B04 ≤24 与 >24 失败路径；完整搜索；最坏 O(n4) 成本与实测规模；不假称板端 PASS
**判定：UNKNOWN / 部分证据不完整**
- ≤24：frozen 本就遍历 C(n,4) 但只评“最大间距那一个”，candidate 在旧失败后补全（`candidate/floor_sheet.py:255-266`）。>24：旧贪心失败后同样全枚举，故“失败后完全搜索可行四区”在结构上成立。
- 实测规模见 `04_benchmark.json`：size 5 line 0.00045s、size 100 failed_with_feasible 34.2086s；`platform` 明确 `board NOT_RUN`，`scope` 明确“no runtime/board latency assertion”（`benchmark.py:14`）——诚实，未假称板端时延。
- **反例/缺口**：`benchmark.py:8-9` 的 `line` 场景完全共线，会命中 `245-251` 快速否定，0.0003s，**根本未进入 O(n4) 兜底**；因此已测的“最坏”只是 `failed_with_feasible`（能命中可行解，通常较早锁定），而**真正最坏情形——非共线、无任何可行四元组、大规模**——完全没有测量。此时 `winner_sep` 长期为 -1，`describe`（含 SVD）会对每个 `sep≥.5` 组合调用，接近 C(n,4) 次 SVD。故“完整搜索的最坏离线成本”只被声明、未被实测，判定 UNKNOWN。

### B05 直接入口及 v2/v3 调用者回归；v1 成功 verbatim；身份/purity 不变；Py3.8、-W error
**判定：UNKNOWN（存在具体证据缺口）**
- 语法：`test_selector.py:75-77` 以 `feature_version=(3,8)` 解析 `candidate/floor_sheet.py`，存在。
- 调用者源码未变：逐行比对 `candidate/floor_detector.py` 与 `frozen/floor_detector.py`（PROFILE 身份门/阈值全同）、`candidate/floor_roi.py` 与 `frozen/floor_roi.py`（15cm `_select_four` `frozen/floor_roi.py:86-147` 逐字相同）、`candidate/leveling.py` 与 `frozen/leveling.py`（auto 仍走 `detect_floor_regions_v3`，`243-245`）、`candidate/leveling_quality.py`、`candidate/validation.py`、`candidate/floor_sheet_test.py` 与 frozen 对应文件——未发现改动。
- **v1 成功 verbatim**：`candidate/floor_sheet.py:273` 直接 `return detect_floor_regions(...)`；`floor_sheet_test.py:203-208`、`floor_roi_test.py:58-61` 存在断言但无运行日志。
- **回归日志问题**：`candidate_regression.stderr:3-18`（import error）、`_02.stderr:1-134`（tempdir `PermissionError`）、`_03.stderr:1-58`（socket `WinError 10013`）、`_04.stderr:52-60`（服务端 `ModuleNotFoundError: validation`）均为**环境失败**；仅 `_05.stderr:34-38` 为 `OK (Ran 32 tests)`。
- **具体缺口**：①`candidate_regression_*.stderr` 无命令行/PYTHONPATH，无法证明覆盖了 v2/v3/15cm；②**没有 test_selector（7 个选择器用例）与 floor_roi_test 的运行日志**，而二者正是 B02/B03/B04/B06 的判据；③日志未体现 `-W error`，acceptance/`AGENTS.md` 要求的 `-W error` = 未证。判定 UNKNOWN。

### B06 121647 原 ROI/TLS/门控不变；原选择不换区；有效 TLS 仍 BLOCKED；不生成替代放行
**判定：UNKNOWN（外部依赖缺失，未见放行数据）**
- `03_session121647.json:49-98`：`original_selector` 与 `candidate_selector` 同为 `{ok:true, selected:[[1,4],[3,-1],[5,5],[8,7]], min_sep_m:0.9014, condition:0.4941, independent:4}`；`ROI_unchanged:true`（`99`）；`effective_TLS:"BLOCKED"`（`122`）、`new_TLS_estimation:false`、`new_export:false`（`123-124`）。与 B06 要求一致。
- 机制核验：`candidate/floor_sheet.py:242-244` 在旧成功时逐字早退，故 121647 不进入兜底、不换区；`leveling_quality.py:79-84,103-107` 的 TLS 有效门（全点/逐区/留帧 PASS + TLS/SVD 数值一致）未改；`levels.py`/`leveling.py` 的放行仅 `recommended=="tls"`（`leveling.py:397-405`），TLS 无效则不放行。
- **反例/缺口**：`session_probe.py:12-13` 读取的是**外部 job 报告**（`…/artifacts/leveling/389dc570…/report.json`）与外部 `audit_inputs/cap_20261009_121647`，均不在证据白名单；`session_probe.py:44` 的 `"effective_TLS='BLOCKED'"` 是**硬编码字符串**，其真实约束仅来自 `39`、`44` 的 assert（对上述外部文件）。因此“TLS 仍 BLOCKED、ROI 不变”无法在本证据集内独立闭合，且本会话未重跑 → UNKNOWN。**未发现任何替代放行数据**（`new_export:false`、`production_integrated:false`）。

### B07 OpenCode 指定模型真实只读独审证据
**判定：FAIL（证据缺失）**
- 验收表要求保存 version/help/模型、有效权限、argv/stdout/stderr/exit、实际 session 身份（`00_SCOPE_AND_ACCEPTANCE.md:15`）。所列文件及本候选目录中**不存在任何 OpenCode 版本/模型/权限/session 记录**。本会话自身无法证明“模型真实身份”，故 B07 FAIL（无法核验）。

### B08 证据 manifest 与起止 SHA 复核；append-only return；保留原失败；不自行 ACCEPTED
**判定：UNKNOWN**
- 存在失败日志留存（`candidate_regression.stderr` 及 `_02/_03/_04` 未被覆盖，符合“原日志/失败全部保留”）。
- 但**无证据 manifest、无 return 追加文件、无起止 SHA 记录**；`candidate_version.json` 仅为局部声明（`production_integrated:false`、`profile_thresholds_unchanged:true`），非可核 manifest。`00_SCOPE_AND_ACCEPTANCE.md:5` 称“回传追加 CLUSTER-01”，证据集中无该回传。判定 UNKNOWN。

### E01 / D01
- `00_SCOPE_AND_ACCEPTANCE.md:17-18`：E01 接入生产/发布 Console/部署 = BLOCKED（未授权）；D01 设备/物理/采集/B2/B3 = NOT_RUN。与 `candidate_version.json:5` `production_integrated:false` 一致。**维持 BLOCKED / NOT_RUN。**

---

## 二、主动反例检索汇总

| 关注点 | 结论 | 依据/反例 |
|---|---|---|
| 原成功完整 dict 逐字保留？ | 结构上 YES；执行证据 UNKNOWN | `candidate/floor_sheet.py:229-244` 与 `frozen/floor_sheet.py:229-239` 表达式相同；未见分歧反例 |
| 小候选失败后搜全可行四元组？ | 结构 YES | `255-266` 全 `combinations`；≤24 旧路径本已全枚举 |
| 大候选失败后搜全可行四元组？ | 结构 YES | >24 旧贪心失败后进入同一全枚举；`254,267` 无解返回旧失败 |
| 叉积共线剪枝误删合格组合？ | 否 | `250-251/258` 仅否定真共线；共线 `condition=0` 必不合格 |
| 数值/重复 key 误删合格组合？ | 否（理论无溢出） | 整数键精确；重复键间距=0 必不合格；`|index|≤400` int64 安全 |
| 原间距/独立/条件门不变？ | YES | `candidate/floor_sheet.py:237-238` = `frozen:236-237`；`SHEET_PROFILE` .50/.10 未改 |
| v2/v3/15cm 行为范围诚实？ | 部分 | v3/15cm 源码逐字未改；但 v2 修复会使**原先落到 15cm 的某些场景改由 v2 直接成功**，v3 有效触达范围实际扩大/收缩，文档只声明“v3 自身实现不变”，未声明此联动 |
| 源码 SHA 版本诚实？ | UNKNOWN | `candidate_version.json` 摘要不可映射、不可核 |
| 121647 TLS/ROI 保持 BLOCKED？ | 证据内一致；因外部依赖 UNKNOWN | `03_session121647.json:74-124`；`session_probe.py:12-13,44` 依赖外部文件与硬编码标签 |
| 最坏 O(n4) 限制交付/生产？ | YES（已声明） | `benchmark.py:14`、`candidate_version.json:5`；但最坏（非共线无解）未实测 |
| 输入/历史完整性（未执行 SHA） | UNKNOWN | 见 B01/B08 |

---

## 三、测试覆盖漏洞（具体）

1. **选择器专项无运行日志**：`test_selector.py`（B02/B03/B04 的唯一判据）不在任一 `candidate_regression*.stderr` 中；`_05.stderr` 只显示 `OK (Ran 32 tests)`，无法证明含这 7 个用例。
2. **`test_selector.py` 未自固定被测实现**（`test_selector.py:5-9`）：无 `sys.path` 插入，target 依赖调用方式，无法从文件本身复现“测的是 candidate”。
3. **大 n 可行性 oracle 覆盖窄**：`test_selector.py:51-60` 只对 size 4–10 做完整 oracle；size>24 仅 `test_large_greedy_failure_has_feasible_alternative`（`31-35`）一个构造例，无随机 25–60 语料对 oracle。
4. **最坏性能未测**：见 B04，`line` 场景走快速否定，未覆盖“非共线且无可行解”的大 n 兜底。
5. **`-W error` 无证据**：acceptance/`AGENTS.md` 要求，但日志与脚本均未体现。
6. **重复 key / 并列策略**：无专门用例（虽经分析不产生误判），`合格组合并列`策略未单独断言。
7. **v2/v3 联动**：候选未新增“v2 修复后 v3 不再进入 15cm”的对照用例；`floor_roi_test.py:18-22` 仅覆盖一个 v2 仍失败的场景。

---

## 四、范围内最小修复 / 补证建议（不越本轮边界）

1. **补 B07**：单独保存 OpenCode 版本/模型 id/`--help`、生效权限、argv、stdout/stderr、exit code 与 session 身份文件（不改代码）。
2. **补 B05/B02/B03**：把 `test_selector.py` 运行命令与 stdout/stderr、退出码落盘，并加 `python -W error`；在 `test_selector.py` 顶部固定 `sys.path[:0]=[candidate, frozen]`。
3. **补 B04 最坏实测**：追加“非共线、无可行四元组”的 size=25/60/100 用例，记录秒数与组合/SVD 调用量，避免仅测“能命中”路径。
4. **补 B01/B08**：生成可核 manifest（文件→SHA、main 含 untracked/ignored 起止 SHA、输入 `01_baseline.json`、`prepare.py`），并在 return 中 append-only 记录。
5. **补 B06 自包含**：将 121647 的 job `report.json`、`meta.json` SHA 与 `01_baseline.json` 纳入本轮证据，或明确标注“外部依赖，UNKNOWN”，避免硬编码 `effective_TLS` 标签充当证据。
6. **行为联动声明**：在 acceptance 中补一行：修复 v2 会改变 v3 的有效触达范围（原先 15cm 承接的部分场景改由 v2 承接），121647 因 v2 旧已成功而不受影响。**不得**为放行 121647 而降门控或换 ROI。

---

## 五、限制声明

- 本报告为只读文本审计；**未执行任何数值、SHA、测试或性能测量**，日志/JSON 均为作者执行证据。
- 目录枚举被拒，`prepare.py`、`01_baseline.json`、外部 job/输入目录不可读，构成不可消除的 UNKNOWN 边界。
- 未逐字节哈希全部候选副本；已逐行比对的关键模块（floor_detector、floor_roi、leveling、leveling_quality、validation、floor_sheet_test）一致，其余副本身份 = UNKNOWN。
- `production_integrated:false`、E01=BLOCKED、D01=NOT_RUN 在本轮维持。

AUDIT_COMPLETE