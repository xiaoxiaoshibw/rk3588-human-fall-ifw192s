# HFUS-D05 实验预登记与基线冻结（UNKNOWN/CLEANUP/时序重构）

日期 2026-10-11。主控（Claude Code）持用户 D05 连续实施授权（「现有 HUMAN-FUSION 隔离开发目录实施、运行、测试并交付 D05」）启动。本文件在**任何 A/B/C 变体跑数之前**冻结；D04 口径与只读边界全部继承。

## 0. 授权与 ponytail

- 用户授权正文：见 `docs/human_capture/tickets/HFUS-D05.md`（本工单目录，当日登记）。
- ponytail skill：主控已加载 `C:\Users\30680\.claude\skills\ponytail\SKILL.md`；Agent A/B/C（写生产代码者）必须先加载 ponytail 再动工，回传记录使用路径，否则被拒收。
- 工作所有权（隔离、禁止并发覆盖同一文件）：
  - 主控：接口冻结（本文件）、归因探针、评测/组合/Demo/回归/证据/return。
  - Agent A：UNKNOWN 自适应邻域重判决（select 层）。
  - Agent B：人体候选感知 CLEANUP（cleanup 层）。
  - Agent C：时序前景恢复（retained/时序层）。
- 只读（不变）：`background/{engine_b,detector_b,run_b}.js`、`contracts/*`、`eval/instrument.js`、`eval/baseline.js`、`captures/`、GT、模型 `xgb69_candidate.json`、D01–D04 全部 evidence、sidequests 旧方法（human_fusion_lab*/v3 只读消费）。
- 新代码一律落在 `sidequests/human_fusion_lab_next/d05/`（新目录，不动 d04/）。

## 1. 预冻结输入（跑数前钉 SHA）

- `background/{run_b.js, detector_b.js, engine_b.js}`、`contracts/{index_v1.js, strict_v2.js, SCHEMA_V2.json}`、`eval/instrument.js`、`eval/baseline.js`（新增，见 §2）。
- 九会话输入 + 参考 `captures/remote/cap_20261009_113611` + 模型 `sidequests/human_fusion_lab/models/xgb69_candidate.json`。
- `sidequests/human_fusion_lab/results/AUDIT.json`（GT 绑定资格裁决源）。
- 全部 SHA 落盘 `BASELINE_SHAS.json`（本目录，随本文件同时生成）。

## 2. 变更（相对 D04，唯一无副作用接口增量）

- **`eval/instrument.js` 不动**（原 SHA 保持）。其 `_ledger.background_ids` 在本instrument 语义下 = 传入 cleanup 的 **A 链 FG 点集（BG 判定后，记 bg_kept）**；`_ledger.cleanup_ids` = cleanup 输出点集（记 cleanup_kept）。两者均沿用既有「leveled 长度子序列 → 原始行索引」映射，不落新文件、不改函数。
- 新增 `eval/baseline.js`：**元信息探针**，只读消费 base ledger（D04 runs/base `D04_base_cap_*.jsonl`）+ instrument。逐会话重建 detector，仅重放 GT 帧，输出逐点 stage：<bg 原始 keep 原因 / bg_kept / cleanup_kept / final_ids / 每成分 membership / 候选 membership>。诊断用途，不改管线、不参与打分。ledger 缺逐点 bg 原始判决（原来是直方图）→ 探针重新计算 select/reasons，**逐点真值用 GT 对象覆盖记账**，禁用做最终晋级输入（晋级仅以 §5 冻结口径为准）。

## 3. 实验变体（冻结；替换式开关，互不为依赖除非 combo）

baseline = D04 `base` 现行 ledger（**不重跑**，引用 SHA，防「baseline 漂移」）。

D05 现行管道分账（先行探针实测，写入 §6）：

| 阶段 | 账 | 说明 |
|---|---|---|
| RAW→BG | `bg.reasons` 直方图 | `no_reference_XY_support_UNKNOWN` 只占总点 <1%；**GT 域内该原因比例由探针实测** |
| BG→CLEANUP | cleanup in/out + GT 覆盖率 | 家具场景大部损失发生处（探针确认 175429 32.3%） |
| CLEANUP→PROPOSAL | cluster_min_voxels=3 门 | PA/PB 成分成分层 |
| PROPOSAL→CLASSIFIER | RF 阈 0.55 / 候选阈 0.35 | |
| TRACKER | observed_confirmed 需当帧 accepted 支撑 + confirmed |

| 变体 | 替换点 | 预登记假设（跑前钉） |
|---|---|---|
| `d05_base` | 无（=D04_base ledger 引用） | 现状记录 |
| `d05_a03` | A：UNKNOWN 邻域半径 0.3m | GT 远端/边缘点保留变化 ≤ base +5pt；若 GT 保留无改善即停 |
| `d05_a06` | A：UNKNOWN 邻域半径 0.6m | 同上 |
| `d05_b` | B：候选感知 cleanup（预先用 PA 成分 + GT-free 形态支持 veto cleanup 对疑似人体连通点的删除） | 175429 GT 保留 ≥ base+15pt；S1 FP 不增超 +50 |
| `d05_c` | C：时序前景恢复（邻帧占据一致 → 补回当前帧被删点 + 静人持续热区） | 静人（S8/S6）覆盖率涨；S1 不新增 FP>+50 |
| `d05_abc` | A06+B+C 按序组合 | 单变体出现信号后再跑，**单变体全无信号则不盲组**（D04 同原则） |

A/B/C 均为 hook 在同一 `createDetector` 返回的实例上（同 D04 monkey-patch 风格），不改任何只读文件；每变体自带 `variant_info` 落 SUMMARY。

## 4. 统一口径（严格一致，不混账）

- 输入、索引、评分与 D04 同：legacy（候选阈 0.35 / 距离 0.75m）+ strict（observed_confirmed / accepted / proposal，coverage≥0.5 & purity≥0.8 匹配）双轨；near 的 legacy 256/258 vs strict 差异保留。
- 逐会话汇报，不给总平均。GT 参会规则（冻结）：
  - `eligible && review_status==='reviewed' && session_sha256 同时有 meta+points 且与输入 SHA 全等` → 正式分（S1,S3-near,S3-far,S4,S5,S6,S7,S8 八会话）。
  - **S9（cap_20261010_180751）INVALID_BINDING（缺 meta 键）→ 不参与正式打分**，仅输出「探索行」单列，不进任何晋级判定。
  - GT 对象 `source==='human'` 才作为真人点真值记账；`source!=='human'`（auto/propagated 未人工审核）只进探索列。人工未审核区域一律 UNKNOWN 资格。
- FAIL 样本逐帧落盘（frame_index + 层 + 候选/轨迹 id）。

## 5. 降级/晋级条件（跑前冻结）

- 任何变体若使任一正式资格会话的 strict 合格指标在统计上净退化（净 TP↓ 且无对应 FP↓ 补偿），记该变体 **不可晋级**，保留实测但不推荐组合。
- `d05_abc` 只在「至少一个单变体在其目标会话上有净收益且无悔退化」时运行；否则本轮 `d05_abc` NOT_RUN，明示原因。
- 失败也要如实留账：算法 FAIL 不包装成 PASS。

## 6. 预登记最小落盘

| 文件 | 含义 |
|---|---|
| `baseline_probe/<sid>.jsonl` | 逐点 stage 归因（探针）+ `PROBE_SUMMARY.json` |
| `runs/<variant>/D05_<variant>_<sid>.jsonl` + `_SUMMARY.json` | 同 D04 ledger schema + variant_info（含替换点参数） |
| `AB_<variant>_vs_base.json`（每变体） | 逐会话逐指标差分 + 家具误检变化 |
| `REGRESSION_FINAL.json` | 变体 × 会话 × strict/legacy/perf 合并 |
| `MANIFEST_DEMO.json` | demo 输入 SHA 捆绑（demo 页面做打开校验） |
| demo：`sidequests/human_fusion_lab_next/d05/demo_d05.html` | 三窗同步真点云视图（复用 three.js r127 + fusion_lab_v3 demo），可切 A/B/C/base |

## 7. 不承诺（诚实）

- A 的 0.3/0.6 是「预登记邻域」，**不宣称**该半径找到了物理最优；0.3/0.6 无信号则 A 方向判定为「该轴无效」并明示。
- C 的时序恢复不能自证「一定会救回静人」；S1 仅含家具不得因时序而新增确认人（防自维持）。
- GT 资格本轮不因 D05 有任何推进；S9 继续 INVALID_BINDING。
