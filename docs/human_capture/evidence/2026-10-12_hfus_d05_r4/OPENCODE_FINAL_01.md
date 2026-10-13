## HFUS-D05 R04 独立只读审核报告

**技能路径**：已完整读取 `C:\Users\30680\.codex\skills\ponytail\SKILL.md`（ponytail，full 生效）。
**审核范围**：`D:/Code/ldiar`，仅 read/glob/grep/list，无写文件/无 shell/无评测/无浏览器/未改 GT 模型源码。已读 brief V3 及指定全部证据、R02/R03 两轮 ACCEPTANCE 与 RESULTS/NEAR_REGRESSION、对比源码 `r04/{hook_unknown_fast,hook_split,run,trace,verify_parity,perf_bank,demo_server,demo.html,audit_cli,boundary_audit,check}.js/py`、旧 `d05/hook_unknown.js`、`r02/hook_split.js`、`r03/{hook_gate,run,check}.js`、`background/detector_b.js`、`human_replay/rf_person.js`。大 `points.bin`/全量 ledger 未读，依据 SHA、终端数据与逐帧 parity 判定。

### 一、关键事实核对
- **H1（GT-free 密集核心互斥守恒）**：`hook_split.js:30-31` 有 `point conservation`/`key exclusivity` 断言，`__main__` 自测；R02-05 PASS。成立。
- **H2（分类宽水平拒绝）**：原 69D 模型与参数未改（`hook_gate.js` monkey-patch，`model_sha=84edb5…` 原样）。家具诊断重叠 1→0、propagated 351→48，但 **near observed 184→179、accepted 186→181**（`FULL_FAST.log` 175429 acc tp=186 对照 gate 181）。→ **必须 FAIL，无回退假设被证伪**。
- **H3（A06 等价短路）**：`hook_unknown_fast.js:41/69` 仅当 `minLocal<=1` 跳过邻居网格，`minLocal>1` 仍走 `neighborCountFast`；`refSupport` 达 `minRef` 提前返回，消费者只判 `<minRef`，语义等价。`check.js` 120 组对拍 exit0。`verify_parity.py` 对 9 会话 **2605 帧逐点/候选/轨迹/strict/legacy 精确一致**（`PARITY.log` 全 EXACT_PARITY），且为 R04 新 ledger 与 R02 split ledger 各自实 SHA 的实跑，不是引用旧账。**H3 成立，但只是等价优化，不产生新真人收益。**
- **性能**：纯算法（无 instrumentation/IO/render，前 5 帧热身，九会话串行）p95 全部 <50ms（最大 47.17ms），p99 175553=50.29ms（非门）。注意 `FULL_FAST.log` 的 diagnostic p95 64–94ms 含 ledger shadow 且与 R03 analyzer 并行，已披露，不可当门值。Windows 未冒充板端（板端 NOT_RUN）。
- **边界**：`FINAL_TREE_SHA` head/branch 与基线一致（master/026e063…），errors/drift 空；`.claude/scheduled_tasks.lock` 消失已单列，未宣称全树冻结。消费资产 36 文件三方 SHA 绑定（`CONSUMED_ASSETS_BASELINE_BINDING` + `POST_SHA_CHECK`），模型/GT/输入未变。
- **GT**：S1–S8 PARTIAL reviewed 绑定，S9(180751) INVALID_BINDING 未修原 GT。
- **Demo**：`demo_server.py` 读保存顺序 ledger（`row()` 按 offset 读，不续票），frozen 取 **2026-10-11_hfus_d04_r1**（真 D04 非 D03）。demo_v2 已加入 `readySid` + `controls(false)` + `show()` 守卫（`demo_v2/demo.html:14,17,19,20`），V1 race 源码层面确已修复。

### 二、缺陷清单
**P1（阻断本轮"完成"签署，须补证后方可）**
1. **R04-05 真浏览器操作证据缺失**。`BROWSER_OPERATIONS.json`（标 "R04 Demo v2"）`operations`/`console` 均为空，仅 `DEMO_V2_*.jpg` 与 server log。九会话/步进/拖动/播放暂停/重置/同步/实际删除恢复/实际检出与 coasting/UNKNOWN/来源/SHA 门均无实操作记录。位置：`r04/BROWSER_OPERATIONS.json`、`BROWSER_V1_OPERATIONS.json`。复现：打开该文件即见空数组。源码修复可审，但该冻结要求 **NOT_RUN**。
2. **R04-06 最终独审未闭合**。目录仅有 `OPENCODE_FINAL_01.jsonl`，缺 `OPENCODE_FINAL_01_STATUS.json`/`_EXPORT.json`/`.md`；`DEFECT_HANDLING_PRE_AUDIT.md` 亦记旧 `OPENCODE_SOURCE_01` wrapper exit1。故最终指定模型审核仍 **NOT_RUN**（本次运行完成后由主控另裁定）。

**P2（证据卫生/导航风险，非算法正确性阻断）**
3. **跨轮 R03 证据在 R04 期间被改写**。`BOUNDARY_COMPARISON` 第三段（基线 r04）`changed_in_scope` 含 `r03/ANALYSIS.log`、`r03/analysis_v1/FAILURE_LEDGER.jsonl`、`r03/analysis_v1/FRAME_COMPARISON.jsonl`、`r03/demo.html`。与 `FULL_FAST_EXIT` 记的"R03 analyzer 并行"一致，但违反"不覆盖旧证据"精神，且 R04 计时与 R03 分析并发。复现：对比第三段基线。建议重取这些文件新 SHA 并避免分析器与计时并发。
4. **主 README 指向旧 V1（带 race）Demo**。`r04/README.md:8` 与 `MINIMAL_HUMAN_REVIEW_PACKAGE.current_demo` 仍写 `--port 8914`/`…:8914/`（即未修 race 的 `r04/demo.html`），`DEMO_LISTENER.json` 显示 8914 仍被 22608 占用；最终 Demo 在 `demo_v2/` 8915。复现：按 README 打开 8914 会得到旧 UI。建议单一入口。

**P3（可读性/健壮性）**
5. Demo 第 2 窗用 D04 frozen 候选 + R02 base stages（`demo_server.py:101-102` 断言候选相等后替换 stages）；若两轮点索引编号有差异会错位，建议注明依据。
6. `verify_parity.py:34-36` 的 CASE_INDEX 由历史分析拼接并把 split 改标 fast，属派生索引，非重算。
7. `hook_unknown_fast.js:12` `linkCellPad` 未用；`check.js` 固定 LCG、n=150 的 120 例覆盖有限（有 2605 帧 parity 兜底，可接受）。

### 三、三张冻结验收表状态建议（不自行 ACCEPTED）
- **R02**：01/02/03/04/05 PASS；**06 BLOCKED**（家具独立负例不足）；**07 BLOCKED**（连续身份/退出参照不足）；**08 FAIL**（R02 viewer 异步缺陷在 R02 表内保留）；**09 FAIL**（far 55.693/5m 170.302ms）；10/11 NOT_RUN。
- **R03**：01/02/03 PASS；**04 FAIL**（H2 near 184→179 回退）；**05 BLOCKED**；**06 NOT_RUN**（v2 真操作待记录）；**07 FAIL**（far 51.598 等 >50ms）；08/09 NOT_RUN。
- **R04**：01 PASS；02 PASS（120 反例 exit0）；03 PASS（2605 帧精确 parity）；04 PASS（纯 perf p95<50，板端 NOT_RUN）；**05 NOT_RUN**（见 P1-1）；**06 NOT_RUN**（见 P1-2）；**07 NOT_RUN**（return 待追加）。

### 四、四类裁定
- **工程**：离线工具链、实跑、逐帧对拍、纯性能门基本齐备，**可继续**；但 R04-05 真浏览器证据缺失、README 指向旧 V1、跨轮 R03 证据被改动，**当前不足以签署"本轮工程完成"**，需补证与统一入口。
- **算法**：**不通过**。H1 部分收益（far 20→67、走停走 9→10），H2 被证伪失败，剩余 far 32FN、occl 61FN、turn 2FN、家具高分自维持/ghost 未解。
- **GT**：**BLOCKED**（缺独立已审负例、连续未标身份、退出参照、S9 绑定）。
- **生产**：**BLOCKED/NOT_RUN**（未部署，板端未测）。

**结论**：本轮为**真实离线返工 + 等价优化**，工程返回基本可信、无 H3 造假；但存在 P1 证据缺口，**不构成 ACCEPTED**，其缺失与算法剩余真实 FAIL 须分离记录。以上不替代主控最终裁定，不自行升级任何 ID。

REVIEW_COMPLETE