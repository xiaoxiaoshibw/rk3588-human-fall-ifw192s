# HFUS-D05-R05 指定只读补审02（opencode-go/deepseek-v4.1-flash）

## 0. 指令符合性
- 已完整读取本指令、`D:/Code/ldiar/AGENTS.md`、`docs/human_capture/README.md` 当前 R05 入口（第 1 行）、`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。
- 实际技能路径：**`C:/Users/30680/.codex/skills/ponytail/SKILL.md`**（存在，已读）。
- 全程只读（read/glob/grep）；未写文件、未执行评测、未触网/代理/生产。`finalize_records.py` 仅阅读，未运行；`OPENCODE_FINAL_02_STATUS.json` 与 `r06/` 目录确认不存在，`ACCEPTANCE_FINAL.json`/`FINAL_REPORT.md` 未生成，`returns/HFUS-D05.md` 未追加 R05。

## 1. P1-A 补审裁定：**已由 PARITY_SUMMARY_V2 明确修正（闭合）**
- `PARITY_SUMMARY_V2.json:94-98` 显式写 `field_parity:true`、`ledger_byte_parity:false`、`compared_field_count:22`、`ledger_diff_reason:"R05 rows add bank_events diagnostics…"`，并保留原 `PARITY_SUMMARY.json` 不变（`original_summary_sha_provenance`）。
- `fields` 恰为 **22** 项（`:69-92`），与 `verify_control.py:18` 的 `keys` **逐项相同**；原 `PARITY_SUMMARY.json` 每会话仍 `status:"PASS"` 而 `reference_ledger_sha256 != current_ledger_sha256`（如 `PARITY_SUMMARY_V2.json:9-10` 175227 `7573…` vs `96c1…`）。故“PASS = 字段级等价，非账本整文件字节相等”已被点明。独审01把字段数写成“21”，`REVIEW_DEFECT_HANDLING.md:5` 已更正为 22 并按实际列表为准。
- 残余（非阻断）：`PARITY_SUMMARY_V2.json` 无生成脚本，`TOOLING_SOURCES_V4.json` 未纳入该文件（grep 全仓无 `PARITY_SUMMARY_V2` 生成器），属人工补正声明；建议把其自身 SHA 并入工具清单。原冻结源/账未改写，符合“不覆盖旧账”。

## 2. 关键事实复核（均对得上，未见伪造 PASS）
- 补审01：`OPENCODE_FINAL_01_STATUS.json` pid15472、exit0、export_exit0、`actual_models:["opencode-go/deepseek-v4.1-flash"]`、readonly、tools `["read"]`、skill_read/complete_text=true → **PASS**。
- 双全程真实 exit0：`FULL_CONTROL_EXIT.json` pid21200 / `FULL_ANCHOR_EXIT.json` pid10936 均 exit_code 0；9+9 会话 = 2605 帧（`PARITY_SUMMARY_V2.json:3`，`COMPARISON.json` 304+258+464+239+202+238+251+523+126=2605）。
- 42 赢/24 输，far 27/10：`WIN_LOSS_INDEX.json` 计数一致；near 220–224 五个保护帧 control tp=1→anchor tp=0（`COMPARISON.json:173-363`）；far anchor 余 15FN = 2×`7_ASSOCIATION_CONFIRMATION` + 13×`4_MIXED_COMPONENT`（`:646-650`）——**不是无候选**，与旧 brief 一致。
- 算法门：`COMPARISON.json:1527` `algorithm_registered_gate":"FAIL"`（`analyze.py:105` 逻辑：near_ok=False → FAIL）；S9 `INVALID_BINDING`（`:1450`）。
- 性能：`PERFORMANCE_PURE.json` control 8/9 FAIL（仅 still PASS）、anchor 6/9 FAIL（walk/occl/still PASS）→ 与 brief/`AUDIT_READY.md:23` 一致，**实际 FAIL**。
- 浏览器：`BROWSER_VERIFICATION_V2.json` 23 行、9 会话、`console:[]`、3 pending 排除；`nine_near220_control` 实为 f51，正式 f220 两行（control/anchor）按实际帧核（`verify_browser_v2.py:26`）。regex `\bf(\d+)\b` 不匹配 `final`，本轮无误；独立代理 `READONLY_AGENTS_FINAL.md` 重复核实。
- 边界：`BOUNDARY_COMPARISON.json` baseline 15463、head `026e…`、errors/drift/missing 空、`not_atomic:true`、`added_outside_scope` 恰 **42** 项（HFUS-RD-01）；V2 纠正文件均在扫描之后生成，`later_own_records` 已声明需独立增量 SHA。
- 人工包越界：原 `MINIMAL_HUMAN_REVIEW.md:10` 写“175804 f233–243”，该会话 239 帧最大 238；`MINIMAL_HUMAN_REVIEW_V2.md:10,17` 裁为 **f233–238**，原包保留 → 真实缺陷已一致修正。
- raw 秒 TTL 标签：`hook_bank_anchor.js:51` 仅看帧 TTL，`DIAGNOSTIC_DEFECT_01.md` 披露，`analyze_bank_events_v2.py:28-34` 按帧/秒 TTL 派生补证，未称 raw 已修。
- P2-B/P2-C/P2-E/P2-F：`hook_bank_anchor.js:22,46` 保持 fail-fast throw；`analyze_bank_events_v2.py:50` 硬编码 `.55`（本轮冻结配置一致）；`demo_v2/README.md:5`（及 `demo/README.md:5`）明示 control 导航由精确 parity 派生。均按 `REVIEW_DEFECT_HANDLING.md` 处理，未过度改写冻结源。

## 3. 剩余工程缺陷（均非阻断“可审交付”，给文件/行号+最小改正）
1. **P3-a（证据不自洽）** `BOUNDARY_AND_PERFORMANCE_SUPPLEMENT.md:5` 写“PID23768/30468/32080”，但引用的 `OUTSIDE_PROCESSES_1155.json` 仅列 **23768、32080**（无 30468）。最小改正：改文为快照实际 2 个 PID，或补入含 30468 的快照。不影响“性能 FAIL / 环境资格 BLOCKED”结论。
2. **P3-b（工具溯源缺口）** `PARITY_SUMMARY_V2.json` 无生成脚本、未进 `TOOLING_SOURCES_V4.json`。最小改正：新增最小生成/校验脚本，或将其 SHA 登记入工具清单。
3. **P3-c（历史文档漂移，非本轮源缺陷）** `docs/human_capture/README.md` §2 仍写 `stride_points:4`/16B，实际 `core/data_loader.js` `STRIDE=28`、`run.js` 按 28B/点读取。独审01已指出仍待更正；建议在 HC 入口加注，勿改本轮源码。
4. **P3-d（收口指引）** `finalize_records.py:37-45` 生成的 FINAL_REPORT 未显式引用 `PARITY_SUMMARY_V2.json` 与 `REVIEW_DEFECT_HANDLING.md`。最小增强：在 FINAL_REPORT/`CURRENT_DELIVERY_INDEX.md` 指向该二文件，使 P1-A 更正可被读者发现。

未定位到支撑“R06 before=15635 文件”的任何仓内产物（无 `r06/` 目录、无新 baseline 文件）；该陈述属下一轮范围外叙事，本轮 finalize 只需 `OPENCODE_FINAL_02_STATUS.json`，不构成 R05 交付阻断。

## 4. 四类裁定（测试数量与工程材料 PASS 均不等于算法/人工接受；全程未 ACCEPTED）
| 类别 | 裁定 | 依据 |
|---|---|---|
| **工程材料** | **PASS（可审查交付，未 ACCEPTED）** | 真实退出/日志/SHA/树扫描/只读独审链完整；P1-A 已由 V2 明确闭合；P2/P3 为加固项，不阻断审查。 |
| **算法** | **FAIL（不晋级）** | H4 注册收益门 FAIL：near f220–224 五帧全 TP→FN 未抵消；far +17 TP 不足以抵消；far 有害重锚反例仍在（far41 偏移 .41064m > .4）；下一轮条件修正 **NOT_RUN**，不得给其成果结论。 |
| **GT 资格** | **BLOCKED** | S9 `INVALID_BINDING`、未标帧 UNKNOWN、缺独立人工负例分组；H4 的 FG 证明 ≠ 真人。 |
| **生产接入** | **BLOCKED / NOT_RUN** | 板端/物理/部署/采集/驱动网络均未运行；性能仅 Windows 离线；模型/生产链未动，性能环境资格另 BLOCKED。 |

补审处理已闭合（P1-A 明确修正、人工包越界一致裁正、raw TTL 以 v2 派生且未冒充已修、性能 FAIL 与竞争资格 BLOCKED 表述分开）。工程材料可审交付通过；**绝不 ACCEPTED**；不启 D06/D07，R06 仅为离线返工编号。

REVIEW_COMPLETE