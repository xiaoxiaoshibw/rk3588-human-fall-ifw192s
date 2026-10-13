# RF-OPTIMIZATION-R1 独审修复复核（第二审，只读）

ponytail 使用路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（skill 仍激活，full）。仅读/运行：`-B` 无 pycache（已验 `no_pycache`）、未编辑、未装依赖、未改生产、未派 subagent。

## 1. 测试
`python -B -W error -m unittest discover -s . -p test_research.py -v` → **Ran 4 tests, OK, exit=0**，含新增 `test_single_class_score_and_missing_recall`。与 `11_tests_repair01.log` 4/4 一致。

## 2. 加固核对（源码）
- 单类折不进入选参均值：`experiment.py:99-103`（仅 `len(unique(y[va]))==2` 才 append；无两类折即 `raise`）；OOF 仍填充供阈值（:98,:106），与“单类只报告、记录 validation_classes”一致。**PASS**
- 空值保护：`optional_mean`（:66-68）用于 `session_macro_recall`（:201），全 None 返回 None。**PASS**
- 口径：`duplicate_audit_scope`（:152，显式声明只覆盖 round6 精确全维、不排除近重复/同人同景）、`stand_weak` `coverage_note`（:184）。**PASS**

## 3. run01 ↔ run02 独立对比（run02 已完成，非 NOT_RUN）
- 公共 4 路线（baseline51/rf_v2/rf_v3/gbdt）**逐折混淆全等、params 全等**；逐候选 `p` max|Δ|=0.0、threshold max|Δ|=0.0、predicted 差异 0、error 差异 0。
- run02 仅 4 路线、4956=4×1239 条预测（消融未重跑，符合 repair notes）。
- 结论：加固在本数据上为**结果中性**（所有内层验证折恰为两类），印证 repair notes“预计不改变本次选参”，实测确认。

## 4. 对第一审的错误更正
1. **撤回**“`present_class_score` 单类恒返回 1.0”。实算 `y=[1,1], pred=[0,1]` → **0.5**（单类时为该类自身召回，非恒 1）。第一审该主张错误，`test_single_class_score_and_missing_recall` 佐证。
2. **降级**“GBDT 高 precision 主要由逐折阈值不稳定驱动”为**未验证推断**：无冻结同阈值配对/因果实验；仅能确认各折阈值跨度大（0.05–0.95）、FP 集中单会话、删位置特征会改变 GBDT 结果，主因**未定**。
3. **更正** 121622 `range_2_4` 切片：实为 **23 负 + 1 正**（非“全负”）；该负例 `recall=0.0`（1 个真实正样本被漏）、`precision=None`（无预测正）、`specificity=1.0`。故此处 `recall=0.0` **正确**，`None` 只适用于真正零正样本切片；repair notes 第 14 行“应 None”对本切片不成立。

## 5. 当前是否存在软件 FAIL / 修复未闭合
**无当前软件 FAIL，加固已闭合。** 第一审所列 5 项中：1（单类选参）、2（None 保护）、4（判重口径）、5（stand_weak 口径）已修/已声明；3（GBDT 各特征组消融未进冻结网格）仍属**下一轮数据合同预注册**事项，非本轮缺陷。GBDT 消融与近重复判定留待下轮，未伪造预注册。

## 6. 保持不变
数据阻塞（无独立 `source:human`、无未见人员/家具/场景、姿态与距离分层不足、两会话零负例、FP 单会话集中）与 **RFO-09 BLOCKED** 不因软件加固解除；**R3 不放行**，R3/R4 维持 NOT_RUN。本轮只确认软件修复闭合，不改变可用性结论。