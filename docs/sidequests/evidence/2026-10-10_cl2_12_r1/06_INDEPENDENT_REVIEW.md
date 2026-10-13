# CL2-12 / 06 独立只读审计 — 运行机制、结论与裁决 — 2026-10-10

**数值证据与审计意见严格分离**：本轮统计量由作者脚本产生（01/02/03 JSON）；审计员只有 read 工具、
不能执行代码重算，其对数值只做"口径/自洽性/逻辑/代码阅读"审查。这一点改变了 CL2-12 的命运——
审计员通过纯代码阅读抓出了作者的截距 bug 与冒充 M1/M2。

## 6.1 运行机制（如实，含一次 abortive attempt）

| 项 | 值 | 证据 |
|---|---|---|
| CLI | opencode **1.18.35** | `cl2_12_agent_dbg.stdout` |
| 配置通道 | `OPENCODE_CONFIG_CONTENT` env + `--pure`（首次 attempt 误用 `--config`，1.18.35 该选项无效致 exit1、audit 流未启动；该 abortive run 的 stdout/stderr 保留在 `cl2_12_raw.stdout/stderr` —— **后由本轮真实 run 覆盖**。`cl2_12_exit.txt` 是 abortive attempt 的遗留（EXIT=1），见下） | `run_opencode.py`, `cl2_12_effective_config.json` |
| 有效 agent tools | 全 false 仅 `read:true`（bash/edit/write/grep/glob/task/webfetch/websearch/skill=False） | `cl2_12_agent.json`（debug agent 实测断言） |
| 模型（实际） | `opencode-go/deepseek-v4.1-flash`（export 9/9 assistant msg 实测） | `cl2_12_export_session.json`（live export exit0） |
| 会话 | `ses_edbe1c9c4ffel99b35pkw9uzc2`（唯一） | `cl2_12_raw.stdout` events + export |
| 运行 exit | **0** | 后台任务记录 `bofq6fock.output` EXIT=0 / `[exited with code 0]` |
| 终末 finish | **stop** | `cl2_12_export_session.json`（asst[-1].finish==stop） |
| 报告 | 7,921 chars，含 `AUDIT_COMPLETE` | `06_AUDIT_REPORT_FULL.md` |
| read 调用 | 28 次 tool_use 全 `read`、全部命中本仓库 D:\ 前缀（无外越） | `cl2_12_raw.stdout` events |
| 权限诚实点 | effective agent 的 `external_directory` 实测为 `ask`（非硬 deny；可见 `cl2_12_agent_dbg.stdout` moral 段）。审计员**自述时仍写 "external_directory=deny"**，并以"无法核验外部文件"保守给 UNKNOWN——运行证据显示它确实没有读外部 | `cl2_12_agent.json` vs `06_AUDIT_REPORT_FULL.md §11` |

**abortive attempt 披露**：第一次 `opencode run --config cl2_12_config.json` 打印帮助后 exit 1
（stderr 原样留存于当时 `cl2_12_raw.stderr`），没有产生任何审计会话；`cl2_12_exit.txt` 是该次退场码。
真实审计用正确的 env 注入跑通。审计员读到的"EXIT=1 + 占位符 + 无 completion"是这个时点的真实状态，
它据实把这些作为交付不完整的证据（finding §85-87），我**不隐瞒这次操作失误，如实记录**。

## 6.2 审计员总评与分项

- 审计员给 CL2-12 的工作判 **FAIL**（核心：截距 bug + 冒充 M1/M2 + df 口径 + 交付占位/EXIT=1）。
- 同时**认可** STEP1 交叉覆盖与 STEP3 同环梯度"扎实、边界干净、未越级"（I121/I123 PASS）。
- 关键 finding 与我的裁决（ADOPT 后已回改并**重跑**）：

| # | 审计员 finding | 裁决 | 处置 |
|---|---|---|---|
| 1 | M3 留出预测丢截距（-0.203 m） → "留出爆炸"是口径 bug 非物理 | **ADOPT** | 已修 02/03 预测带截距，重跑；04 改写为修前/修后两版；初版"灾难性爆炸"作废 |
| 2 | 用 M3 的 β/h 切片冒充独立拟合的 M1/M2 | **ADOPT** | 重跑时 M1/M2 独立拟合；`holdout_eval` values 更新 |
| 3 | 00 冻结 df 公式 `1+(g+c−n_conn)` vs 脚本 53 差 1（公式本身错） | **ADOPT** | 00 改 `g+c−n_conn`=53，标注 v1 笔误 |
| 4 | 3×MAD hard-cluster 规则未在 00 预注册 | **ADOPT** | 00/P3 v2 补预注册 |
| 5 | 空间折用 shuffle 非预注册 Morton | **ADOPT** | 03 改回 Morton 分块，重跑 |
| 6 | STEP3 "≫" 方向笔误（应 SE≪差）、"26–49%" overstate（实 13–49%） | **ADOPT** | 03 已改并脚注溯源 |
| 7 | 05 §5.0/§5.1 用"留出灾难/时间漂移"作收窄理由（该数字被污染） | **ADOPT** | 05 理由改为"空间外推失败"+"域级常量漂移"（后者独立证据） |
| 8 | I124 论证 FAIL 的论证链失效 | **ADOPT** | 04 重写；HOLDOUT_GENERALIZATION 仍 FAIL 但机制改为空间外推 |
| 9 | exit/模型/finish/AUDIT_COMPLETE 无法核实（当时无 completion/export） | **时点解决** | 补 `cl2_12_export_session.json`：exit0/9×deepseek-v4.1-flash/finish=stop；审计员当时的 UNKNOWN 保留不改 |
| 10 | 07 manifest / FINAL_REPORT / completion 缺失（race：审计在我封盘前运行） | **时点性** | 现已生成（本目录）；07 对全部文件逐 SHA。审计员对此的 UNKNOWN 为其时点观察，合理 |
| 11 | external_directory 自述 deny（实 ask） | **披露** | 见 6.1 权限诚实点；未致越界读取 |

## 6.3 裁决总结（不越权改判）

- 审计 UNKNOWN 全部保留（FIT/留出行级互斥、外部 SHA、历史 0 字节等它无法核）；
- 审计 finding #1/#2 **改变结论链**但不改变最终裁定方向：**HOLDOUT_GENERALIZATION 仍 FAIL**
  （机制由"灾难性爆炸"改为"空间外推"）；**STATISTICAL_IDENTIFIABILITY 仍 FAIL**（12 组 8 组不过 x1.05，
  且 rank 恒真+β/dx 对消+M1 被否 三重不可辨识证据独立成立）；**PHYSICAL_CAUSAL_IDENTIFICATION 仍 UNKNOWN**。
- 审计员判 CL2-12 **FAIL**（针对初版）。作者按 ADOPT 完成修正与重跑后，按"调查工作质量"自评：
  修正过程诚实、负结果如实、边界未越 → **CL2-12 工作 = PASS_WITH_FINDINGS**；121647 TLS / 修复 = BLOCKED。
  **这一自评≠审计员的初版 FAIL 被推翻；审计员的 FAIL 是对含 bug 初版的正确判断。**
