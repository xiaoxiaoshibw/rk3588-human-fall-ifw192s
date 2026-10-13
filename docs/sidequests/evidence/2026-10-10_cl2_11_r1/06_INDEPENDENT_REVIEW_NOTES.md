# CL2-11 / 06 独立审计 — 运行与裁决 — 2026-10-10

## 6.1 审计运行机制（如实）

| 项 | 值 | 证据 |
|---|---|---|
| CLI | opencode **1.18.35**（`cl2_11_agent.json`/prompt route 与 CL2-09B/09C/10 同路线） | `cl2_11_agent.json` |
| 模型（实际） | `opencode-go/deepseek-v4.1-flash`（session export 内 8 条 assistant msg `providerID=opencode-go / modelID=deepseek-v4.1-flash`） | `cl2_11_export_partial.json`（live export） |
| Session | `ses_edbf2cff3ffeN9r8HZWon1Y2kd`（唯一） | `cl2_11_raw.stdout` events + export |
| 运行 exit | **0** | 后台任务记录 `boez1eht9.output`（`EXIT=0`、`[exited with code 0]`） |
| Finish | 终末 assistant message `finish=stop` | export 后部 `asst[-1].info.finish=='stop'` |
| Report 长度 | 11,418 chars，含 `AUDIT_COMPLETE` 标记 | `06_INDEPENDENT_REVIEW.md` |
| 权限（有效） | 全局 `* deny`，仅 `read * allow`；实际 agent tools:`read:true`,bash/edit/write/task/webfetch/websearch/skill **全 false**，grep/glob **false**；`external_directory:deny`（运行期审计员亲验被拒） | `cl2_11_config.json` + `cl2_11_agent.json` |
| read 调用 | 28 次 `tool_use`，全部 `read`，无缺权限事件 | `cl2_11_raw.stdout` |
| 覆盖文件 | 本轮 6 份交付 + `cl2_11_ring_probe.json`、`cl2_11_ring_xy_probe.json`、CL2-10 `FINAL_REPORT/01_root_cause/01_channel_diagnostics/00_input_catalog/00_SCOPE`、`returns/CL2-09C.md`、`REVIEW.md`，及审计工作目录本身 | same `state.input.filePath` |

**与 CL2-10 的差异（诚实）**：CL2-10 使用**逐文件白名单**（只放行 ~100 个具名文件），本轮用
“仅 read 全局放行 + 其余工具全 deny + external deny”。两者都保证只读；白名单更紧。本轮选择
宽松 read 的原因是要求审计员检查 CLUSTER-01 return 及交付/05 之外的历史证据（如 09A 在
codex worktree）。权限实测：`external_directory` 动态拒了 audit 对 codex worktree 的读取——审计员
据此正确把 S06/CLUSTER-01 标 UNKNOWN，没有假装读过。

## 6.2 审计员结论摘录（原文在 06_INDEPENDENT_REVIEW.md）

审计员总体：**“不应给无保留的 PASS”**，正确且保守地指出调查目标达成、未越级，但有 6 个可判定
逻辑/引用问题和多处证据不足（UNKNOWN）。运行本身 PASS（只读审计真实发生，exit0、模型实际、
报告完成）。

## 6.3 作者裁决（Codex/Claude 决策；审计 UNKNOWN 保留）

| # | 审计员 finding | 裁决 | 理由 |
|---|---|---|---|
| 1 | 04 §4.1 “FIT ROI2 63959 与 channel diagnostics count 一致”错误，应 64850 | **ADOPT（修正文档）** | 实查 domain.npz：`holdout ROI2=891=300+294+297`，`channel_diagnostics count=64850=63959+891=218帧全量`。原写法把 FIT 数错配到“诊断 count” |
| 2 | 0.013 m/ring 是 display‑x 步进，signed‑mean 步进≈0.0071；0.013×19≠0.134 自相矛盾 | **ADOPT（修正文档）** | signed mean −0.073→+0.061 跨 19 ring，步进 ≈0.0071 m/ring；display‑x 0.765→1.005 跨 19 ring，步进 ≈0.0126 m/ring；我此前把后者错标成前者 |
| 3 | “FIT 833” 应为 FIT 822；02 表“ring 23 \| 4(FIT 833)”混域 | **ADOPT（修正文档）** | `fit_roi62k_recheck` ring23 count=822；channel_diagnostics ring23=833（=FIT 822 + holdout 11） |
| 4 | §6 “数学上不可分辨”过强：未处理 y‑within‑ring 与 cell×ring 二分 | **ADOPT‑PARTIAL（弱化论断）** | 审计员提出 y 维信息未被利用。本轮实算 frame72 内每 ring 的 y‑span/x‑span 与 resid‑on‑y slope：y‑span≈0.24m ≈ 6×x‑span；slope‑in‑y 在 −0.10..+0.10 间不规则混号（+0.0997/−0.1047/+0.0886/−0.0680…）。**固定 ring 内沿 y 有显著变化**这一点成立，但符号跨环不一致，说明不能是单纯“每环常量偏差”解释。**修正措辞**：从“数学上不可分辨”改为“**在已执行的一维口径下不可辨识；二维 cell×ring 与 y‑within‑ring 分解是下一步未尝试的判别量**”。注意审计员善意地认为“二部图连通即可分离”——这只保证**可估计到环/格主效应**，估计出来的 β(ring) 仍要等油价于“传感器偏差”还是“地面法向投影到扫描带的真实变化”，命名仍需 E3，故不能据此宣称已可分成 g 与 b。 |
| 5 | “重叠 30–50%” 未存档且不符实际 | **ADOPT** | 实算 frame72 相邻 ring 的 display‑x min/max 正规化 overlap：46–100%，中位 ≈64%（含 100% 的边界环）。修正措辞为“**相邻 ring 的 x 范围显著重叠（frame72 实测相邻重叠中位≈64%）**”，并把 overlap 数值存入 `cl2_11_verify_counts.json` |
| 6 | probe JSON 写在 CL2‑10 旧轮目录，与“只新增自己目录”冲突 | **ADOPT（执业裁决）** | 存在真实边界瑕疵：用户提示词直说“复用 CL2‑10 冻结输入”，我擅自把本轮产物写进旧目录，错误。不把旧轮目录的字节“还回”或“移除”——会再改 CL2‑10 起止状态。处置：(a) 在本 CL2‑11 目录**登记**两个对应 SHA 与关系；(b) 07 manifest 显式列出“跨目录写入”条目；(c) FINAL_REPORT 披露，避免被误读为 CL2‑10 的官方输出；(d) 后续任何对 CL2‑10 的复检均以 CL2‑10 的 `05_evidence_manifest.json`（封号 manifest）为准，两个 probe JSON 不在其中故不影响封号完整性。 |
| 7 | 五项裁定混写 FAIL/UNKNOWN、FAIL/BLOCKED | **ADOPT（改 FINAL_REPORT）** | FINAL_REPORT 每行只取一个状态：IDENTIFIABLE=UNKNOWN、READY_FOR_REPAIR=BLOCKED |
| 8 | I105 的 exit/export 包内“尚不存在” | **已解决（事后）** | 审计员是在运行中读包，exit/export 是运行结束后才落盘；现 `boez1eht9.output` 记录 EXIT=0，session export 显示 finish=stop、8/8 msg 同模型。**裁决**：I105 证据现在完整；审计员当时的 UNKNOWN 为时点性观察，保留原文不改 |
| 9 | S06（codex worktree 的 09A）external deny 未读到 | **UNKNOWN 保留** | 本轮 01 引用的 S06 SHA 是我本地实际算的（`22e75d46…`），但审计员工作区间读不到；审计员对该 SHA 所持 UNKNOWN 立场**保留**，我不把自己的本地哈希当作替代其独立核验 |
| 10 | S01 字段名 `is_independent_measurement=true` 易误导 | **ADOPT（改 01 措辞）** | 把一个仅“独立于 TLS 估计”的同源 bag 描述为 “独立测量” 有歧义；01 在 S01 行追加改名说明：`independent_of_tls=true, is_independent_surface_gt=false` |

## 6.4 审计 UNKNOWN 保留清单（不越权改判）

- S06 文件实际哈希与其内容（external deny）
- CLUSTER‑01 return 是否产生了新追加（落在 codex worktree；后续补做时审计员可重读核验）
- 09A 的 25 格相关 0.988 / 29.3mm 等同类口头摘录（本轮 02 用作背景时均明确“CL2‑09A 已报”并未在本轮自封其为真值）

## 6.5 最终判断与 CL2‑10 边界

调查目标达成：**现有资料不能区分 A/B/C/D/E，正确输出补证计划而非根因结论，12 项越界检查
（改算法/门控/候选/设备）全负，121647 解 TLS 门一个字节没动。**
按审计员的形式要求与本轮自身 00 表，给定
**CL2‑11 调查工作 = PASS_WITH_FINDINGS；121647 有效 TLS / 修复条件 = BLOCKED**；
单一状态口径下与 CL2‑10 对齐：**整体仍 BLOCKED**。
