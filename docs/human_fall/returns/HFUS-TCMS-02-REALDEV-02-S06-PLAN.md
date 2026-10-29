# HFUS-TCMS-02-REALDEV-02-S06 计划回传（仅计划）

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HFUS-TCMS-02-REALDEV-02-S06 / 计划 r1 / 本会话 DSH agent（唯一文档 writer）/ 2026-10-18 01:1x (+08:00)。
- 验收表路径 / 版本 / SHA：`docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s06_plan_r1/PLAN_ACCEPTANCE_V1.md` v1（P01–P09，SHA 见文件本身）。
- 执行方式 / 模型：本机离线单会话；模型按环境声明 deepseek-flash，未切换。
- 状态：**SUBMITTED（仅计划）**；S06 实施 **NOT_RUN**，Codex 正式复审 **NOT_RUN**。
- 起始 branch/HEAD：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`（与既有封存一致；本轮未重算全量基线）。
- ponytail 实际路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`；策略：RESEARCH（覆盖/漂移根因）+ ENGINEERING（前景变体与交付）。

## 集中诊断与根因覆盖

| 缺口 | 事实来源（本轮核对） | 计划中的处置 |
|---|---|---|
| 尾段 21 帧无骨架 | `RUN_R4/frames.jsonl`：f758 有 6 节点，f759–779 全 0 / `skeleton_available=false` | S06-A 近地前景变体（预注册），S06-B 全段重跑 |
| 107/490 ACTION 帧无候选 | `REAL_EVALUATION.json`：383 有候选、107 空；尾段 21 帧已定位，其余 ~86 帧当前不可查询 | S06-D 从 npz ledger 重建逐帧 `candidate_rows` 并合计=107 |
| 标定覆盖面不足 | 12 条边中 10 条曾 CALIBRATED、2 条从未；163 次 DRIFT_RESET 无根因分类 | S06-C 逐次分类 + 逐边支撑分析 + 至多一个预注册修法 |
| 数字不一致 | `REAL_EVALUATION` max cross-window std `0.012365 m` vs `FRAME_SUMMARY` `0.019529 m` | S06-E 对账并写入交付索引 v2 |

## 实际变更

| 文件 | 用途 | 与用户原差异的区分 |
|---|---|---|
| `docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s06_plan_r1/PLAN_V1.md` | 计划正文（S06-A–E） | 全新目录，未改任何旧文件 |
| `…/PLAN_ACCEPTANCE_V1.md` | 计划验收 P01–P09 | 同上 |
| `…/PLAN_CHECK.md` | 计划自检（含"本轮核对 vs 只引用"） | 同上 |
| `…/INPUT_BASELINE.json` | 五个封存件 + 源 + 9 个复用文件的 SHA | 同上 |
| `sidequests/hfus_tcms_02/realdev/r09/append_plan.py` | 二进制 LF 追加 WORKFLOW/REVIEW 并校验 | 同上（新源码目录第一件文件，后续实施在此） |

未改 data/、旧证据、配置、模型、GT；无 Git 写。

## 逐条验收

| ID | 自验 | 说明 |
|---|---|---|
| P01 承接与封存 SHA | PASS | 五件 SHA 见 `INPUT_BASELINE.json`；承认五项 Codex 复审 NOT_RUN |
| P02 三个缺口有事实来源 | PASS | 见上表，均来自本轮直接读数 |
| P03 近地变体先写后跑、单点语义变化 | PASS | 计划 §4 给出规则与"不变项"清单 |
| P04 两道预注册自检、不通过即停 | PASS | 空场 ≤main+2pp；745–779 ≥60% 帧有 ≥30 行候选 |
| P05 禁预测填充、双分母并列 | PASS | 计划 §5 |
| P06 漂移分类合计=163、逐边结论、至多一个修法 | PASS | 计划 §6 |
| P07 107 空帧合计=107、与 SK02 字段对齐 | PASS | 计划 §7 |
| P08 预算/停止/排除/决策点 | PASS | 计划 §9–§10 |
| P09 本轮只写文档 | PASS | 未跑数据、未改源码/旧证据 |

## 未闭合与限制

- S06 未实施：本回传只登记计划；实施须用户实际派发并另立唯一验收表。
- 计划中已知的**证据缺陷**：`RUN_R4/frames.jsonl` 的 `candidate_summaries` 为空 → 107 空帧中非尾段部分当前不可查询，S06-D 必须先补字段再结论。
- SK02 两份 max std 不一致（0.012365 vs 0.019529），S06-E 对账；在解释前不得引用其中任一作为"最终"数字。
- 解剖关节/左右身份/物理高度/人体身份/效果/独立 D 仍 UNKNOWN/BLOCKED；无 GT。
- 需用户输入才能推进的事项：一帧种子、少量关节标注、多视角或高密度采集、外部参数化模型或训练授权（任一）。

## 交给 Codex 独立复审

- 计划入口：`docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s06_plan_r1/PLAN_V1.md` 与 `PLAN_ACCEPTANCE_V1.md`。
- 现状入口：`docs/human_fall/evidence/2026-10-18_hfus_human_skeleton_02_r1/ACCEPTANCE_V2.md`、`REPORT.md`、`FINAL_SEAL.json`。
- 复审重点：近地变体是否只有一处语义变化、两道自检是否足以防止"为了尾段牺牲空场"；漂移分类是否可复核；107 空帧重建是否会用预测填充；两份 std 数字如何对账。
- 下一步：若复审认可计划，再由用户派发 S06 实施；本项不自动开工、不自动进入 S07。
