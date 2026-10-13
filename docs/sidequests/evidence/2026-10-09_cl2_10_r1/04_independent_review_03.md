Re-reading the updated root cause and the new cohort/numeric/CLI evidence.

# CL2-10 补审报告（第二轮 · 只读 · 同模型同会话）

审计对象：`E/`（`D:/Code/ldiar/docs/sidequests/evidence/2026-10-09_cl2_10_r1/`）
补审范围：`01_root_cause.md` 末尾两条补记、`04_cohort_integrity.json`、`inputs/cohort/03_normal_comparison.json`、`inputs/cohort/01_leveling_index.json`、`01_weighted_numeric_check.json`、`04_review_response.json`、`opencode_actual_model_02.json`、`04_opencode_raw_02_command.json`、`cli_effective_agent.stdout`、`opencode_permissions.json`。
方法：只读；未执行脚本、未重算 SHA、未运行数值管线。凡 `[UNKNOWN]` 表示我未亲自复算，不伪造执行。第一轮结论与 UNKNOWN 全部保留，不降低标准。

---

## 1. T100 provenance 措辞 —— 已关闭（文档级）

第一轮 §4.4 指出的 `candidate/floor_sheet.py=d0b3e3…` vs `frozen/floor_sheet.py=dd1b58…` vs 报告 `code_hashes.floor_sheet=dd1b58`（`inputs/cap_20261009_121647/report.json:168`）的混读风险，现已被显式澄清：

- `01_root_cause.md:120`：原报告 selector=dd1b58（本轮 frozen/）；`candidate/` 的 d0b3e3 是 09C；`baseline/` 的 066a81 是 09B；报告未用 09C 重新生成；本轮 TLS 诊断入口只调用 quality/estimators 与冻结四 ROI/源行，**不调用 selector**；09C selector 仅用于搜索回归。
- `04_cohort_integrity.json:60-62`：`report_selector_sha256: dd1b58…`、`copied_09C_selector_sha256: d0b3e3…`，provenance 明写“diagnostic TLS path … does not call floor_sheet”。
- 与我第一轮读到的三处 SHA（`04_source_summary.json:10/28/41`、`report.json:168`）**互相一致**。

**结论：T100 措辞收紧项在文档/记录层面 CLOSED。** 我未重算 SHA（`[UNKNOWN]`），但三来源交叉一致，不再存在“把 09C selector 误当报告生成器/生产已集成”的空间。

---

## 2. T108 集合缺口 —— 已关闭（结构/记录级）

新增 `inputs/cohort/` 把原先“外部文件定义 valid 集合、包内不可枚举”的缺口补齐：

- `04_cohort_integrity.json:29-52`：`historical_valid_cases`（10）==`executed_valid_cases`（10），且都等于 `candidate_capture_universe`（11）去掉目标 121647。
- 我把它与 `00_input_catalog.json`（11 会话，10 valid + 目标）及 `inputs/cohort/03_normal_comparison.json` 中的 `valid` 标志逐项核对：`114641/114709/114734/114754/114817/121622/121723/122616/122637/122700` 一致，121647 `valid:false`（`03_normal_comparison.json:1710`）与 `01_leveling_index.json:1167` 一致。
- `04_cohort_integrity.json:53-54`：`cohort_membership_matches_original_cluster_index:true`、`not_based_on_AB_outcomes:true`。
- 排除项显式且非“按结果剔除”：`:55-59` template_job `632eff1e…`（空场模板）与其它旧 capture “not claimed as tested”；`01_root_cause.md:122` 明确“并非全部 captures 中的任意旧作业”“不能冒称它们已做本轮试验”。

**结论：T108 集合缺口 CLOSED（不再扩大宣称；范围限定为 CL2-07 正常人体 / CLUSTER-01 cohort）。**
**残留 UNKNOWN**：两个 binding（`c80ce064…`、`9c4a92fa…`，`04_cohort_integrity.json:6/12`）我未重算 SHA；因只读无法执行，记录级接受。最终报告中应继续锚定“CL2-07 cohort”而非“全部 captures”。

---

## 3. 数值一致门区分 —— 准确（已算术核对）

`01_weighted_numeric_check.json:35-59`（目标）+ `01_root_cause.md:104-113`：

| 目标实验 | 记录 角差° | 记录 offset 差 m | 门 (1e-4°, 1e-6 m) | 固定 holdout | 我的核对 |
|---|---:|---:|---|---|---|
| D_ROI_EQUAL | 0.305710216 | 0.00568440672137 | **FAIL**（0.306≫1e-4；5.68e-3≫1e-6） | (144,'2') | 与补记表逐位一致 |
| D_FRAME_EQUAL | 0.000032082 | 7.10223655664e-07 | **PASS**（3.21e-5<1e-4；7.10e-7<1e-6） | (72,'2') | 与补记表逐位一致 |

- 早先正文 `01_root_cause.md:71`“两个正权重实验…不满足 raw TLS/SVD 数值一致契约”属于过宽；`补记:106` 明确“算法身份 ≠ 数值门”，并用上表纠正：帧等权**通过**数值门、ROI 等权**未通过**。
- 但**两者都不是修复**：帧等权仍因 72/ROI2 P95=50.292>50 失败，ROI 等权既超门又在 144/ROI2 失败（`01_weighted_numeric_check.json:41-58`）。故“非现行 raw 算法身份”不蕴含“必超容差”，此前表述确被误概化。
- `01_weighted_numeric_check.json:190` nuance 句与补记一致；`04_review_response.json:5` `weighted_numeric_statement_qualified:true`。

**结论：数值门区分 ACCURATE；AB 数值未变，仅追加纠正，符合“不覆盖历史证据”。**

---

## 4. T110 CLI/model/权限/exit —— 记录已开放（记录级）

- `opencode_actual_model_02.json`：model `opencode-go/deepseek-v4.1-flash`（与本会话上下文一致）、session `ses_eded7a292ffe2Lq0YBvy3Wax56`、`last_finish:stop`、`exit_code:0`、`export_exit_code:0`、CLI 1.18.35。
- `04_opencode_raw_02_command.json`：`argv` 为 `bash -c "opencode run --pure --agent cl210audit --format json --model opencode-go/deepseek-v4.1-flash '<prompt>'"`，cwd=E/，`exit_code:0`，`permissions_unchanged:true`；引号已正确闭合（对应用户所述第一轮 shell 引号 exit 2 已被新会话替代）。
- `cli_effective_agent.stdout` + `opencode_permissions.json`：`read:true`，`bash/edit/write/glob/grep/task/webfetch/websearch/skill:false`，`question/plan_enter/plan_exit:deny`，且只读白名单为逐文件精确路径。我在第一轮遇到的 `read … action:deny` 与该配置完全吻合，**反证 guard 真实且只读**。
- 注：`opencode_permissions.json:17-121` 的 allowed 列表是第一轮快照，未含本轮新增文件；新文件由补审的 exact read 白名单开放（我已成功读取，运行时生效）。此为配置时点差异，非逻辑缺陷。

**结论：T110 从 `[UNKNOWN]` 提升为“记录级可核”。** 我未亲自执行 CLI/校验 SHA/导出，故仍不判 PASS，只记“raw argv/model/session/exit/权限证据已齐备，待最终 manifest 封存”。

---

## 5. 是否仍有未解决逻辑 FAIL

在新增证据中未发现逻辑 FAIL。逐一自查：

1. cohort 三个集合（universe 11 / historical_valid 10 / executed_valid 10）计数与成员一致。
2. `03_normal_comparison.json` 与 `01_leveling_index.json` 对 121647 的 valid/recommended 状态一致（false/null）。
3. 数值门表与 `01_weighted_numeric_check.json` 逐位一致；门阈值取自 `report.profile`（1e-4°/1e-6 m），判读无误。
4. `04_review_response.json` 的 `new_algorithm_code:false`、`gates_or_inputs_changed:false` 与全局证据一致。
5. provenance 的 dd1b58/d0b3e3/066a81 三版分配与 `report.json`/`04_source_summary.json` 一致。

**唯一文档性提示（非 FAIL）**：正文 `01_root_cause.md:71` 的过宽措辞仍在原位，仅由末尾补记覆盖。因证据不可覆盖属正确做法，但最终报告/return 应显式引用补记，避免读者只读正文误判。此为建议，不改本轮裁定。

---

## 6. 总体裁定（不降低标准）

| 项 | 补审后 |
|---|---|
| T100 措辞 | **CLOSED**（文档级；SHA 重算 `[UNKNOWN]`） |
| T108 集合 | **CLOSED**（结构/记录级，限 CL2-07 cohort；binding SHA 重算 `[UNKNOWN]`） |
| 数值门区分 | **准确**（帧等权 PASS 门、ROI 等权 FAIL 门；两者均非修复） |
| T110 | 记录级可核（原始 CLI/model/session/exit/权限已开放）；不判 PASS |
| 未解决逻辑 FAIL | **无** |
| TLS01 | **BLOCKED**（50mm 门不变） |
| E01 | **BLOCKED** |
| D01 | **NOT_RUN** |
| T107 修复资格 | **不具备** |

**目标失败未变**：72/ROI2 P95=50.291869>50 → `GL_HOLDOUT_QUALITY`；帧等权过数值门但 72 留出仍失败；ROI 等权既超门又 144 留出失败；无满足“原单平面 + 原门 + 全留出改善”的候选；物理表面/几何 GT 仍缺（`report.json:157-159 ground_confirmed:false`）。

**结论：总体维持 BLOCKED，无算法修复资格。** 两个独审动作项已在文档/记录层面关闭，但 SHA 字节级复核与最终 manifest/return 封存仍未完成（本会话及新增文件的只读证据已就绪，尚未封存）。

**保留的第一轮 UNKNOWN**：外部历史 manifest SHA 重算；逐帧 X 梯度/corrX 未复算；T110 我未亲自执行；本轮两个 cohort binding SHA 未复算。
**标准不变**：无物理 GT 不得解锁 TLS01；离线数值改善不等于修复；不覆盖历史证据。

AUDIT_COMPLETE