# 独立只读审核 — HFUS-D05-R05（opencode-go/deepseek-v4.1-flash）

## 0. 指令符合性

- 已完整读取 `D:/Code/ldiar/AGENTS.md`、`docs/human_capture/README.md` 当前 R05 入口（第 1 行）、`OPENCODE_REVIEW_BRIEF_01.md`。
- 实际技能路径：**`C:/Users/30680/.codex/skills/ponytail/SKILL.md`**（已读取，存在）。
- 全程只读；未写文件、未跑评测、未触网/生产。`audit_cli.py:17` 的权限正是 `read/glob/grep/list`+ponytail 外部目录，只读约束成立。

## 1. 发动机依赖核对（重点）

确认**真实装载的是 `sidequests/human_fusion_lab_next/background/engine_b.js`，不是 `core/engine.js`**：

- `run.js:4-6,17` 只 require `background/detector_b`、`background/run_b`、`background/engine_b`；`detector_b.js:3,26` `require('./engine_b')` 并 `new E.UnifiedEngine({mode:'FUSION'})`。
- retention 银行确实在 `engine_b.js`：初始化 `begin_session`（`:110 this.retention={tracks:{}}`）、过期/回收（A 链 `:319-332`）、刷新（`:500-506`，仅 `foreground_source===FG && classifier_decision_auc===CONFIRMED_HUMAN` 才刷新，锚点存 PIPE 的 `t.x,t.y`）。
- 这直接**证伪原“retained 直接刷新银行”假设**（`engine_b.js:261-267` 注释 + `:500-502` 逻辑），与 `PRE_IMPLEMENTATION_CAUSAL_AUDIT.md` 一致。
- 两个 tracker 为 `pipe_ctx.tracker`(PIPE) 与 `fusion_ctx.tracker`(FusionTracker)，`trace.js`/`hook_bank_anchor.js` 均围绕它们与 `_fusion_a_chain/_fusion_b_chain/_tick_fusion` 打点，未误用 `core/engine.js`。

## 2. 主要事实逐条比对（均对得上）

- control/anchor 各 9 会话合计 **2605 帧**：`PARITY_SUMMARY.json:3`、`BANK_EVENT_SUMMARY_v2_*:4`。
- 两个真实 Node 进程 21200/10936 exit0：`FULL_CONTROL_EXIT.json:3`、`FULL_ANCHOR_EXIT.json:3`；18 ledger=5210 行。
- 42 赢 / 24 输：`WIN_LOSS_INDEX.json`（wins 42、losses 24）。
- far 67→84 = 27 赢 10 输：`COMPARISON.json` far `observed_confirmed.tp` 67→84；`WIN_LOSS_INDEX` far 赢 27/输 10，losses 尾部 f43–52。
- near 184→185（+1），保护帧 f220–224 全部 control tp=1→anchor tp=0：`COMPARISON.json` near `near_protected_frames`。
- far anchor 余 15 FN = 2 `7_ASSOCIATION_CONFIRMATION` + 13 `4_MIXED_COMPONENT`：`COMPARISON.json` far anchor `reasons`。
- 家具 FG 高分误接受仍在：`COMPARISON.json` furniture `furniture_diagnostic` human/accepted 1、propagated 351 两方相同。
- S9 `INVALID_BINDING`：`COMPARISON.json` 180751 `qualification`。
- perf：control 8/9 FAIL、anchor 6/9 FAIL：`PERFORMANCE_PURE.json` 与 `AUDIT_READY.md:23` 一致。
- 浏览器 23 行（26 操作 −3 loading）、`nine_near220_control` 实为 f51、`near220_*` 实为 f220、console[]：`BROWSER_VERIFICATION_V2.json`、`verify_browser_v2.py:26`。
- 树扫描：`BASELINE_BEFORE.json` = 15463 文件、master HEAD `026e…`、errors/drift/missing 空（`BOUNDARY_COMPARISON.json:171-174`，`.git` 排除 `boundary_audit.py:18`，`not_atomic:true` `:29`）。

结论：**交付对自身不利事实的披露是诚实、可核的**，未发现伪造 PASS 或把算法失败包装成通过。

## 3. 工程缺陷 P1/P2（含最小修复）

**P1-A（中心证据表述，建议按 P1 处理）— control 等价是“字段级”而非“账本字节级”。**
`verify_control.py:18` 的 `keys` 只比 21 个字段（**不含** R05 新增的 `bank_events`，见 `run.js:98`），所以每会话 `reference_ledger_sha256 != current_ledger_sha256`（如 175227 `7573…` vs `96c1…`，`PARITY_SUMMARY.json:9-11`）却仍 `status:"PASS"`。文件未在正文点明差异来源。读者极易把“PASS”读成整份 ledger 逐字节相等，从而误判或不信任。
最小修复：在 `verify_control.py:31` 的结果与 `PARITY_SUMMARY.json` 的 `limits` 中显式写 `field_parity:true`、`ledger_diff_reason:"R05 rows add bank_events diagnostics (run.js:98)"`。

**P2-B — `hook_bank_anchor.js:22` 用 `throw` 表示不变式失败。**
一旦出现“银行刷新但同 internal_track 无 ≥阈值 FG 证明候选”，整段 9 会话全跑**中途中止**、只剩半截 ledger，且把“数据反例”伪装成崩溃（易被登记成环境故障）。本次未触发，但不利于反例收集。
最小修复：改为 `unproven_refresh++` 并记录，全跑结束后由分析器断言该计数为 0（或仅 strict 模式 throw）。

**P2-C — 硬编码阈值。** `analyze_bank_events_v2.py:50`（及 v1 `analyze_bank_events.py:50`）写死 `chosen['prob'] >= .55`；应从 `session['config']['rf51_threshold']` 取，避免配置日后变动时断言口径漂移。当前值一致，无错误结果。

**P2-D — 事件标签秒 TTL 漏记（已知）。** `hook_bank_anchor.js:51` 的 `created_or_reentered` 只看帧 TTL；秒 TTL 过期后同 ID 重建会漏记。`DIAGNOSTIC_DEFECT_01.md` 已披露，`analyze_bank_events_v2.py:28-34` 用派生账补证，raw 未覆盖——符合“不称原运行已修复”。

**P2-E — 浏览器验证器弱解析。** `verify_browser_v2.py:21` 用 `\bf(\d+)\b` 从 `rawInfo/baseInfo/curInfo` 反查帧号；这些串含 `f40 … final=…` 等多数字，正则解析脆弱（本轮通过）。建议改读结构化帧号。

**P2-F — Demo 跳转隐性耦合。** `demo_server.py:92` 把 R04 fast 的 `CASE_INDEX` 改名 `control` 并入 cases，`demo.html:38` 的“下一收益/失败”据此跳转；依赖 control≡R04 fast 逐帧等价才正确。当前成立，但属隐性假设。

**核对无误项（非缺陷）**：`demo_server.py:108` 与 `demo.html:21` 以 **28B/点**读取 `captures/remote/*/points.bin`，与 `core/data_loader.js:15 STRIDE=28` 一致（`README.md` §2 的 16B 描述是过时文档，不构成本轮源码缺陷）；未发现 GT 泄漏进推理（`analysis_v2/analyze.py` 文档串、`hook` 只用当前帧 `args[0]` 与 `bank_before`、`run.js` 在 `tick` 后才算 GT）。

## 4. 分开裁定

- **工程材料**：**PASS（可审查，未 ACCEPTED）**。真实退出/日志/SHA/树扫描/只读独审链完整；control 逐帧字段等价事实成立。存在 P1-A 表述歧义与若干 P2 加固项，但不阻断审查。**注意：此刻不得用旧 R04 审核认定 R05 完成**；最终报告/return/独审/浏览器记录在扫描后追加，须另行 SHA 单独回传。
- **算法**：**FAIL，不晋级**。H4 注册收益门 FAIL：near 保护帧 f220–224 全部 TP→FN 未抵消；far +17 TP 属收益但不能抵消 near 回退。**far >0.4m 的有害重锚反例仍在**（`BANK_EVENT_SUMMARY_v2_anchor.json:46` far max_displacement 0.5047m）。下一轮“仅当旧 EMA 超出 0.4m 恢复半径才修正”的假设**尚未运行（`AUDIT_READY.md:43`）→ NOT_RUN**，不得给其任何成果结论。
- **GT 资格**：**BLOCKED**。S9 `INVALID_BINDING`、未标帧 `UNKNOWN`、缺独立人工负例分组；`H4 FG 证明 ≠ 真人`，家具高分为工程误接受诊断，不构成泛化/负例资格。最小人工复核需求与阻断见 `MINIMAL_HUMAN_REVIEW.md`，未变。
- **生产接入**：**BLOCKED / NOT_RUN**。板端/物理/部署/采集/驱动网络未运行；性能为 Windows 离线纯算法，不冒充板端；模型/生产链未动。

## 5. 总评

工程交付**忠于事实、自报 FAIL**，无伪造 PASS；控制组等价、fit 与证据链可核。但算法目标未达、GT 与生产未获资格，且存在 P1-A 中心证据表述歧义与若干 P2 加固项。**本次不予 ACCEPTED**；下一轮条件修正与 far 有害更新反例均须先登记、再运行、后裁定。

REVIEW_COMPLETE