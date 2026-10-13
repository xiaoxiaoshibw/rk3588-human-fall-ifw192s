I'll read the required skill and evidence files.

# HFUS-D05 R04 独立只读补审报告（P1/P2 闭合核验）

**实际技能路径**：已完整读取 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`（ponytail，full 生效；本次为只读补审，未写代码，按其“先读全再动手”执行）。
**审查范围**：`D:/Code/ldiar`，仅 read/glob/grep/list；未写文件、未执行 shell/评测、未操作浏览器、未改 GT/模型/源。已读 `2026-10-12_hfus_d05_r4` 下 `OPENCODE_FINAL_01.md`、`OPENCODE_FINAL_01_STATUS/EXPORT.json`、`FINAL_REVIEW_DEFECT_HANDLING.md`、`BROWSER_EXPORT_FAILURE.md`、`BROWSER_OPERATIONS_V3.json`（全 19 条实 DOM）、`BROWSER_FULL_VERIFICATION.json`、`BROWSER_NINE_VERIFICATION.json`、`CURRENT_DELIVERY_INDEX.md`、`MINIMAL_HUMAN_REVIEW_PACKAGE_V2.json`、`GROWTH_PROVENANCE.json`、`FINAL_REPORT.md`、`ACCEPTANCE_V1/FINAL.json`、`PARITY_SUMMARY.json`、`PERFORMANCE_PURE.json`、`FULL_FAST_EXIT.json`、`BOUNDARY_COMPARISON.json`、`TOOLING_SOURCES_V3.json`；`demo_v2/{README.md,demo.html}`、旧 `r04/README.md`、`docs/human_capture/README.md` 顶部、`returns/HFUS-D05.md` 本轮段落。大 ledger/points.bin 未读，依 SHA/逐帧账与 DOM 实物判定。

## 一、P1/P2 逐项闭合状态

**P1-1 空浏览器账 → 已补实物（闭合，限只读证据）**
`BROWSER_OPERATIONS_V3.json` 现为真实完整 DOM：19 条操作（9 个 `nine_*` 会话 + `current_far80`/`final_far80_loaded` + `play_pause`/`step_back`/`reset`/`seek_end(f522)`/`mouse_drag_329`/`shortcut_f238_loaded`/`success_index(f75)`/`failure_index(f0)`），与 `BROWSER_FULL_VERIFICATION.loaded_rows=19`、`nine_sessions` 九项完全对应。每条含 base/current/raw 三窗文本、`sid`/`frame`/timestamp 及 `sha`（每变体 `ledger_sha256` + 输入 meta/points SHA + `model_sha256=84edb5…`），三窗 frame/时间戳一致，`console=[]`；状态串为 `SHA_VERIFIED · sid · f · t · 三窗同步 · 资格`。空数组旧件 `BROWSER_OPERATIONS.json` 保留为失败史（`BROWSER_EXPORT_FAILURE.md` 有成因）。→ 前次空账缺失已消除。
*残留（非阻断）*：仅 `play_pause` 一条，DOM 记的是“播放”后态，未单独留“暂停”态；真实删除/恢复以 `BG实际删除=/cleanup实际删除=/retained=` 字段体现。属粒度问题，不撤该项。

**P1-2 最终独审未闭合 → 已闭合流程（补审由本次承担）**
`OPENCODE_FINAL_01_STATUS.json`：`exit_code=0`、`requested_model=opencode-go/deepseek-v4.1-flash`、`actual_models` 同名、`tools=[glob,grep,read]`、`skill_read/instruction_read/complete_text=true`、`export_exit=0`；`OPENCODE_FINAL_01_EXPORT.json` 的 `model.providerID=opencode-go/id=deepseek-v4.1-flash`，与旧 `OPENCODE_SOURCE_01` wrapper exit1 分离。前次只缺自身状态文件的缺口已补。→ P1-2 流程闭合；R04-06 的“补审”即由本报告承接，但**本次自述不作为完成证据，最终由主控裁定**。

**P2-3 跨轮 R03 证据在 R04 基线后被改 → 已披露并限定（非阻断）**
`BOUNDARY_COMPARISON` 第三段（基线 r04，15338 文件）`changed_in_scope` 含 `r03/ANALYSIS.log`、`r03/analysis_v1/FAILURE_LEDGER.jsonl`、`r03/analysis_v1/FRAME_COMPARISON.jsonl`、`r03/demo.html`；`GROWTH_PROVENANCE` 给 R03 分析进程 1791736839.9→1791737030.3，与 R04 基线扫描 1791736751.2→1791736919.6 真重叠，`FULL_FAST_EXIT` 亦记 `instrumentation 初段与 R03 analyzer 并行`，并保存四文件最终 SHA。判定：系同一 open(x) 进程仍在追加新生成文件、非覆盖已完成历史、非重跑；已加载算法源 SHA 未动，纯 perf 在 parity/analysis 结束后串行。→ 属并发/证据卫生管理限制，如实披露，**不阻断交付**；不得据此宣称全树冻结。

**P2-4 导航仍指旧 8914 → 当前入口已修（闭合）**
`CURRENT_DELIVERY_INDEX.md`、`docs/human_capture/README.md` 顶部、`MINIMAL_HUMAN_REVIEW_PACKAGE_V2.current_demo`、`demo_v2/README.md` 均指 **8915**；`TOOLING_SOURCES_V3` 已列入 `demo_v2/*`。旧 `r04/README.md:8` 仍留 `--port 8914`（未修 race 的旧 UI）与空导出件，作为历史保留、不作当前证据。→ 当前导航唯一化完成。
*残留（非阻断）*：仓库内旧 `r04/README.md` 若被误读仍会指向 8914；建议加一行“已废弃，见 CURRENT_DELIVERY_INDEX”，但不属阻断。

**P3（5/6/7）**：baseline 诊断 stages 是同输入/同映射 SHA 的新 base 派生（非 D04 原生字段，已声明）；`verify_parity.py` 为派生 fast 索引且有 2605 实账兜底；120 反例有限、`linkCellPad` 未用。均已披露，保留为非阻断可读性项。

## 二、是否仍有阻断“工程交付”的缺陷

以现有实物核验：R04 实跑 `FULL_FAST_EXIT exit_code=0`；`PARITY_SUMMARY` 九会话 `status=PASS`、`frames` 逐行为 304/258/464/239/202/238/251/523/126 = **合计 2605**（非 23445），逐帧字段全员/状态精确 parity；`PERFORMANCE_PURE` 九场 `p95` 全 <50ms（最大 47.17ms），`p99` far=50.294ms 保留；模型 SHA 全程 `84edb5…`；边界 head/branch 未变、`errors/drift` 空、外部 lock 消失单列。P1-1 实物已到位、P1-2 流程闭合、P2-3 已披露、P2-4 当前导航已修。

**结论：整改后的“当前包”未见仍阻断工程交付的缺陷**（本报告只读核验了文件实物，未重跑浏览器/评测；浏览器结论基于内部自洽的真实逐帧 DOM+SHA）。真实证据不足项已明确：无。

需主控纠正的记录瑕疵（非阻断）：`FINAL_REPORT.md:96` 与 `returns/HFUS-D05.md:193` 的“9×2605”措辞会被误读为 23445 帧，应以 `PARITY_SUMMARY.frames=2605` 及九会话逐行数为准——brief 已声明主控将追加纠正。

## 三、三类区分（不自行 ACCEPTED）

- **当前包（可信、可继续）**：R04 等价优化源码、九会话 2605 帧新账与逐帧 parity、纯 perf、真浏览器 V3 DOM/截图与 SHA 校验、当前唯一入口 8915、人工包 V2。工程交付基本齐备。
- **历史缺件/失败史（保留、不作当前证据）**：空 `BROWSER_OPERATIONS.json`、旧 8914 `r04/README.md` 与 V1 race viewer、旧 `OPENCODE_SOURCE_01` wrapper exit1、R02/R03 各自 FAIL/BLOCKED。未抹除即为正确。
- **算法真实 FAIL / GT / 生产（非代码缺陷）**：H2 near `184→179`（accepted `186→181`）回退确凿，家具诊断改善不抵消；far 32FN、occl 61FN、turn 2FN、家具高分自维持/ghost 未解；far legacy FP 105→188、occl legacy TP 65→64 保留。GT BLOCKED（缺独立已审负例/连续身份/退出参照，S9 永久 `INVALID_BINDING`）；生产 BLOCKED，设备/板端 NOT_RUN。

## 四、四类裁定（建议，非 ACCEPTED）
- **工程**：可继续/基本闭合，唯余“9×2605”措辞纠正与旧 README 提示两处非阻断项。
- **算法**：FAIL（H3 仅为等价优化、不产生新真人收益；H2 无回退假设被证伪）。
- **GT**：BLOCKED。**生产**：BLOCKED（部署/采集/物理 NOT_RUN）。

以上不替代主控最终裁定，不自行升级任何 ID。本次为只读补审，未重跑多 GB 评测，未新增/修改任何文件。

REVIEW_COMPLETE