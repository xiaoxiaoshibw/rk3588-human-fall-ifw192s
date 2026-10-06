# W03-R2.6b 收口摘要（Topology-Preserving Cleanup）

- 日期：2026-10-06（Asia/Shanghai）｜writer：OpenCode（DeepSeek v4.1 Flash，本会话）
- ponytail：已加载（full，`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）
- 判定：**R2.6b PASS**（全部验收门满足；未进入 R3，未 commit，等待人工审阅）

## 1. 验收门（工单 §十）

| # | 门 | 结果 | 证据 |
|---|---|---|---|
| 1 | frame16 cleanup split = 0 | **PASS** | `06_frame16_regression.json`：R2.6 复刻 1204→1115+**87 点 CONFIRMED 碎片**（split=true）；R2.6b 1203 单簇（split=false），碎片消失 |
| 2 | 223757 cleanup-induced split = 0 | **PASS** | R2.6 17 帧 +1 簇 → R2.6b **0 帧**（vs R2 baseline 逐帧 `cl_r26b ≤ cl_r2`；内部 `cleanup_split_delta` 全 ≤0） |
| 3 | 223757 cleanup-induced new green = 0 | **PASS** | R2.6 14 帧新增绿 → R2.6b **0 帧**（无任何帧 `green_r26b > green_r2`） |
| 4 | synth_bend_v1 = 190/190 | **PASS** | 190/190 帧人簇保留 |
| 5 | synth retention ≥ R2.6 | **PASS** | min 0.9965 / p5 1.0 / median 1.0，与 R2.6 完全相同 |
| 6 | 203349 no new cluster/green/purple | **PASS** | 簇 1/0/1（R2/R2.6/R2.6b）、绿 0、紫 0；逐帧 `cl/green/cand_r26b ≤ r2` |
| 7 | 全部既有测试 PASS | **PASS** | 4 套件全绿（见 §3） |
| 8 | 全部新增拓扑测试 PASS | **PASS** | 新增 8 例全过 |

## 2. 三会话 AB（`03_r26b_ab.js`，raw 帧，与 R2.6 证据同口径）

| 会话 | 簇 r2/r26/r26b | 绿 r2/r26/r26b | 删除 r26→r26b | veto | split 帧 r26→r26b | 新绿帧 r26→r26b |
|---|---|---|---|---|---|---|
| cap_20261002_223757（165 帧） | 599 / 616 / **599** | 33 / 46 / **32** | 4205 → 3759 | 446 | 17 → **0** | 14 → **0** |
| synth_bend_v1（190 帧） | 190 / 190 / 190 | 0 / 0 / 0 | 2854 → 1904 | 950 | 0 → 0 | 0 → 0 |
| cap_20261004_203349（102 帧） | 1 / 0 / 1 | 0 / 0 / 0 | 3212 → 2943 | 269 | 0 → 0 | 0 → 0 |

223757 关键诊断：`fg median 2830`；实际删除 median 23 / p95 30 / max 33 点每帧；Case A 保活 cell 合计 886；人体保留率 min 0.9248（R2.6）→ **0.9975**（R2.6b）。

frame16 明细（`06_frame16_regression.json`）：R2 baseline 4 簇（主簇 1204）；R2.6 5 簇（1115 + 87 点 CONFIRMED_HUMAN 碎片）；**R2.6b 4 簇（主簇 1203，桥接点被 veto，无碎片）**。

## 3. 单元测试（`02_r26b_unit_tests.log`）

`human_pipe_lib.test.js` **32 passed, 0 failed**（旧 24 未改口径 + 新 8：度0删/叶子删/桥 veto/度3 veto/Case A 保活/snapshot 不级联/frame16 型不 split/分区守恒）。
`human_detect_lib.test.js` 11、`human_replay_lib.test.js` 45、`panel.test.js` 全过；`ALL_SUITES_EXIT_OK=True`。

## 4. 关键诊断（定义见 `01_r26b_implementation_notes.md`）

- `isolated_3d_candidates`（223757 合计）4205；`xy_topology_vetoed` 446；`actually_removed_points` 3759；`xy_cells_preserved_by_other_z` 886 cell。
- 不变式成立：`candidates == vetoed + removed_voxels`（每会话逐帧可复算）。
- `topology_regression` 标记在全部会话所有帧均为 false。

## 5. 已知边界 / 观察

1. **split=0 是结构性保证**（Case B degree≤1 不可能成为桥）+ 实测；**new green=0 只是实测门**（删点仍可能微移 bbox/PCA/证据阈值），本轮为 0，不宣称数学保证。
2. 223757 绿总数 33→32：仅 frame 146 一帧瞬态确认（R2 有 1 帧绿、R2.6b 无），无任何帧绿多于 baseline；属 vote/特征微移，未违反"不得新增绿"门。
3. 203349：R2.6b 保留原有 1 个灰簇（R2.6 曾将其删掉）。工单允许"能删灰簇可接受"但非必须；相对 R2 baseline 无新增结构（1 ≤ 1），判 PASS。
4. veto 保守性：223757 保留 446/4205 候选（≈10.6%）、synth 950/2854（33%）、空场 269/3212（8.4%）。以少量减噪换拓扑安全。
5. AB 跑 raw（未配平）帧（与 R2.6 证据一致）；workbench 载入时应用 TLS 配平，拓扑规则与坐标系无关。
6. 未动：`fall_assess`、PCA/HUMAN_SHAPE/joint_status、Tracker、3/5 确认、R2.1–R2.5 参数、leveling、板端。W03 未冻结；R3 未开始。

## 6. Evidence 索引

| 文件 | 内容 |
|---|---|
| `00_audit_and_plan.md` | 实施前只读审计与方案（用户已确认） |
| `01_r26b_implementation_notes.md` | 改动、算法、字段语义、复现命令 |
| `02_r26b_unit_tests.log` | 四套件原始输出 |
| `03_r26b_ab.js` / `03_r26b_ab_run.log` | AB 脚本与运行输出 |
| `04_r26b_ab_results.json` | 三会话汇总（含验收布尔） |
| `05_r26b_ab_results.jsonl` | 逐帧全量记录（165+190+102 行） |
| `06_frame16_regression.json` | frame16 三路径簇明细 |
| `07_r26b_summary.md` | 本文件 |

## 7. Git 状态

未 commit。working tree 变更（本工单）：`human_pipe_lib.js`、`human_pipe_lib.test.js`、`human_detect.js`、`human_detect.html`（M）+ `docs/human_capture/evidence/2026-10-06_hrw03_r2/`（新）；仓库其余脏项为既有用户/历史改动，未触碰。
