# HFUS-D03 回传（BG-B A/B 分支）

> 本文件由临时主控（Claude Code，2026-10-11 晚）在接管后回传，证据与代码仍由 Codex 完成。
> 主控只验证、核对、落笔；未重跑可复用工程，未改任何 D03 代码。

| 项 | 值 |
|---|---|
| 工单 | HFUS-D03（BG-B 接入 A/B 对照，统一计划 v2 §5.1 「blocking D01 工程完成；负例不足不晋级」） |
| 验收表 | `docs/human_capture/HFUS_D03_ACCEPTANCE_V1.md` v1（SHA 见 `DISPATCH_MANIFEST.json`） |
| 证据目录 | `docs/human_capture/evidence/2026-10-11_hfus_d03_r1/` |
| 分支基线 | master @ 026e06303f60ed1bbe4ddc4d037836db68da6d27（接管时 unchanged） |
| 证据接管快照 | integration `TAKEOVER_SHA_2026-10-11.txt`（2400 文件） |
| ponytail | `C:/Users/30680/.codex/skills/ponytail/SKILL.md`（主控侧 `C:\\Users\\30680\\.claude\\skills\\ponytail\\SKILL.md`，同内容） |

---

## 逐条验收（D03-01..D03-07 + DEV/PHY）

| ID | 证据 | 判定 |
|---|---|---|
| D03-01 真实接入 | `CHECK_01.log`: `BG_B_CHECK_PASS missing_reference / unsupported_UNKNOWN / shared_PB / sensor_invalid`；A/B ledger 均含 B 链层（`foreground_b / cluster_b / classifier_b`）；B_SUMMARY 有 B 字段 exist 且非恒一 | **PASS（工程）** |
| D03-02 归因控制 | `BG_COVERAGE_PREREGISTRATION.md` 冻结参数（每4帧、occ≥0.5、voxel/radius、无 GT 调优）；`BG_B_CHECK_PASS`；A 模式与 D01 复算完全一致（见 D01 回传）；**WARN（工程留档缺口）**：sub_d03_verify 发现官方 ledger/summary 与 rerun **语义**完全一致、**字节**不一致，根因是官方产物由 `run_b.js` 老一版 SHA=`303acea5...` 写出（untracked、无 HEAD 版可还原），当前工作树 `run_b.js` SHA=`646aae91...` 多 4 个 ledger key + 6 个 SUMMARY 键（`schema_version/evaluation_version/segment/timestamp_s` + `input_sha256/gt_manifest_sha256/gt_binding_valid/gt_sha256/model_sha256/config`） — 属留档入版问题，D04/D06 推进前建议将 `run_b.js` 入版冻结 | **PASS（算法）/ WARN（工程留档）** |
| D03-03 参考 UNKNOWN | 预登记 3 条款：射线 FREE 不可证 → UNKNOWN；0.4m observed_reference_XY_neighborhood 支持；全参考缺失 BLOCKED。`CHECK_01.log` 验证 missing_reference / unsupported_UNKNOWN 分支 | **PASS** |
| D03-04 难帧证据 | `A_S6_f{128,187,188}_FLOW.json` + `B_S6_f{128,...}_FLOW.json` 共 6 FLOW JSON + 同名 SVG；f128 B 侧人体 15 点混簇已保留证据 | **PASS（证据落盘）** |
| D03-05 九会话 | `A_/B_<sid>.jsonl` 逐帧 ledger 18 个、`A_SUMMARY.json`+`B_SUMMARY.json`、`REGRESSION_COMPARISON_V2.json`、`EVENTS_V2.json`、`FINAL_MANIFEST_V2.json`（双 SHA）；schema hfus-strict-v2 + index hfus-index-v1 | **PASS（产出齐）** |
| D03-06 算法目标 | 见下方 gate 表。**S6 acceptedTP 66<67 FAIL；S1 legacy_FP 347>0 FAIL；near TP 213<256、FP 625>9 FAIL；p95 181.7ms>50ms FAIL；heap PASS** | **FAIL（算法不达标）** |
| D03-07 交接 | 本回传 + RUN_ATTEMPTS + TAKEOVER_LOG + snapshots；Scope 明确 | **PASS** |
| D03-DEV | 无授权 | **NOT_RUN** |
| D03-PHY | 缺充分证据与另行授权 | **BLOCKED** |

## D03-06 gate 逐项对照（来自 `REGRESSION_COMPARISON_V2.json`，主控复算）

| gate | 目标 | B 实测 | 判定 |
|---|---|---|---|
| S6 legacy accepted TP | ≥67/71 | 66 | **FAIL**（差 1） |
| S6 legacy confirmed TP | ≥64/71 | 65 | PASS |
| S1 legacy FP | =0 | 347 | **FAIL** |
| near legacy confirmed TP | ≥256 /258 | 213 | **FAIL** |
| near legacy confirmed FP | ≤9 | 625 | **FAIL** |
| f187/f188 proposal 正确 | 逐点正确 | B ledger 有记录，但 p≈0 拒绝（见 FLOW json），**无效 proposal** | **FAIL** |
| strict 有资格场景不回退 | 指标不劣于 D01 strict | near/far/S4 各层 strict TP 显著下降（A 侧一致 → B 侧劣化） | **FAIL** |
| p95 | ≤50 ms | B 最大 181.7、A 144.1（含 instrumentation） | **FAIL** |
| heap | ≤1500 MB | B 最大 524.8 A 354.8 | PASS |

## 九会话 A/B 关键指标表（主控从 REGRESSION_COMPARISON_V2 抽出）

session 用 sid 尾 6 位。每层为 TP/FP/FN/unmatched_unknown。

| sid | A legacy_confirmed | A strict_observed | B legacy_confirmed | B strict_observed | 结论 |
|---|---|---|---|---|---|
| 175227 S1 | 0/0/0/0 | 0/0/0/0 | 0/**347**/0/0 | 0/0/0/329 | **B 严重劣化**，347 legacy FP |
| 175429 near | 256/9/2/0 | 161/0/97/104 | 213/**625**/45/0 | 111/0/147/705 | **B 劣化**，FP×69 |
| 175553 far | 97/93/2/0 | 36/0/63/154 | 95/104/4/0 | 14/0/85/181 | B TP-2 / FP+11 |
| 175804 S4 | 10/8/1/0 | 6/0/5/12 | 9/17/2/0 | 3/0/8/23 | B 劣化 |
| 175943 S5 | 5/0/1/0 | 5/0/1/0 | 0/6/6/0 | 0/0/6/6 | **B 全漏** |
| 180235 S6 | 61/1/10/0 | 45/0/26/17 | 65/93/6/0 | 7/0/64/147 | B strict 剧跌但 legacy TP+4 |
| 180337 S7 | 11/1/1/0 | 11/0/1/1 | 11/9/1/0 | 5/0/7/14 | B 劣化 |
| 180557 S8 | 51/0/2/0 | 51/0/2/0 | 51/115/2/0 | 51/0/2/112 | TP=51 但 FP+115 |
| 180751 S9 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | GT 绑定 aaaa 占位 → 全部 UNKNOWN（预期） |

## 主控发现并核对的事实（非原始工作）

1. **near legacy 256/9/2 与 strict 161/258 差异是显式的**（D01 baseline_final near SUMMARY）：严格合同使用一对一 + accepted+current support + coverage≥0.50/purity≥0.80，coast 不重复记 detection，故 strict TP 显著低于 legacy 计分。该差异不是“漏报”，是严格语义的直接效应。
2. **S6 confirmed 61→65 是同一 ledger 内 BG-A→BG-B 快照差**（A_SUMMARY legacy_confirmed=61、B_SUMMARY legacy_confirmed=65），但不是统一计划 §2.1 的「61→65」叙述（历史计数口径与该叙述渊源不同，见 §2.1 表头 fixed V2 run）。主控判定：「65」可复现于本轮 B 本次跑；同 ledger A=61 是 frozen 双链对照。
3. **B 在 near/far/S1/S4/S7 等 7/9 会话各层 TP 下降或 FP 上升**。已授权 Directed Fix 的 UNKNOWN 邻域约束没有改善 near（B TP 213 < A TP 256），说明该约束在当前邻域支持门槛下没有救下新增 UNKNOWN 候选。**根因（经 FLOW 逐点核对后定调，主控负责）**：BG-B 额外放行的 UNKNOWN 点在 f128/f187/f188 表现为 GT 人体成分的 cleanup 删除被 B 版 mask 放大（A 侧已删 94-96.5%，B 侧同类组件继续受 `points<60 / points<30 / voxels<3` 硬门丢弃），同时家具 UNKNOWN 成分被放行下游、XGB69 在 B 四百余点家具候选上自信误分 → near/S1/S8 家具 FP 大幅上升，而 S6 稀疏人体收益被 B mask/cleanup 抢先吞掉。**BG-B 当前形态损害净质量；不是 B 无效，是 B 在当前 XGB/硬门组合下对净分负贡献。**这是 D04 要解决的问题，不是本轮修复对象（按统一计划 §5.5.1 保留 B 为研究副本）。
4. **S8 persons=53 fp=115 但 S9 persons=0**：S9 GT_V2 session_sha256.points='aaaa…' 占位 → 全部对象 INVALID_BINDING，故 D03 显示 0 输出但未跑实质推理（各候选0）。这符合 D02 登记，不需要“补”。
5. **engine 热层时间（p95 105~182ms）含 diagnostic instrumentation**（scope 自述；不含 read/render），且默认 Windows Node 24 单进程。生产接入仍须 dedicated perf run，按跳过分支 p50 复核（见 D01 本地 perf 记录 82.7~89.9ms）。
6. **S5 会话 B 全 TP=0 + legacy_FP=6 + unmatched_unknown=19**：B 严格与 legacy 都漏，而 A 侧能 TP=5。判断证据不足（仅 6 persons），先记录不作为升级样本。

## 难帧 f128/f187/f188（A 侧分层 flow）

由 sub_d01_verify 对 D03 FLOW JSON 解读：

| frame | raw | valid | fg | cleanup | retained (added) | classifier a/b→out | final d.candidates | 根因层 | GT Person 点 fate |
|---|---:|---:|---:|---:|---|---|---:|---|---|
| f128 | 49133 | 38341 | 670 | 651 | 651/**added=0** | PA 1/31、PB 1/55 → classifier 1→0 | 1 (a_128_4, prob=0.0117 NON_HUMAN, gt_overlap=0) | **cleanup + hard gate** | cleanup 删 15/33；18 点进 pa_component_12/pb_component_1 gate_fail；strict prop FN=1 |
| f187 | 49131 | 38349 | 639 | 622 | 622/**added=0** | PA 0/31、PB 2/53 → classifier 2→0 | 0 | **cleanup（96.5% GT 被删）** | 251/260 GT 非法；9 点进 pa17/pa18/pb8/pb25 均 gate_fail |
| f188 | 49129 | 38347 | 675 | 659 | 659/**added=0** | PA 2/26、PB 0/49 → classifier 2→0 | 2 (a_188_1 prob=0.0117 / a_188_5 prob=0.0029, 均 NON_HUMAN, gt_overlap=0) | **cleanup（94.0%）** | 252/268 GT 被删；16 点进 pa14/pb4/pb12 均 gate_fail |

统一计划 §5.1 三陈述：

| 陈述 | 判定 | 证据 |
|---|---|---|
| f128 人体 15 点进大簇 | **REJECT（A 侧）** | 15 点 cleanup=False/final_fg=False 未入组件；进大簇 pa_component_6 的 gt_overlap=0。陈述只在 B 侧成立，不能外推 A 侧 |
| f187/f188 前分类缺参考删除 | **CONFIRM** | retained added=0；cleanup 各删 96.5%/94.0% |
| PB 不成"人"不进入 d.candidates | **CONFIRM** | f187 PB classifier_b in=2 out=0；S6 全 ledger 496 顶层候选源 A=470/A+B=1/B=25，25 个 B 源全 CONFIRMED_HUMAN；near 481 候选 A=479/B=1/A+B=1 — 没通过"人"门的 PB 从不进 d.candidates |

**B 侧对照**：`B_S6_f{128,187,188}_FLOW.json` / SVG 同样逐点落盘；B 方向侦测器在以上三帧也走相同的 cleanup 硬门路径，不过在 B 侧没有把 GT 人体并入顶层候选的能力（与 A 方向同根因，只是 top-level coverage=0 候选存在）。sub_d03_verify 深挖后补充的 B 方向细节：S1 空场中 `legacy_accepted fp=355`、`legacy_confirmed fp=347`，严格分账 `observed_confirmed.unmatched_unknown=329`；ledger `B_cap_20261010_175227.jsonl` f2 存在 `a_2_2 src=A prob=0.960 pts=152`、`a_2_4 src=A prob=0.868 pts=269`、`b_2_0 src=B prob=0.740` 候选，全部指向空场家具 raw 行。**即 B 方向 legacy 大幅 FP 来自「家具 UNKNOWN 邻域门放行 + track_confirmed trigger + legacy 不认 UNKNOWN」的**；Five analysis 通过「BG_COVERAGE_PREREGISTRATION §3/§4」推得 `detector_b.js select()` 的 0.4m `columns` 邻域判决 = `no_bg_match_supported_XY_UNKNOWN` 放行 / `no_reference_XY_support_UNKNOWN` 剔除，0.4m 借用 retention hot_cell_radius_m、未按 GT 调优。

**D04 应对**：保留既有 cleanup/retention 不动，针对 B 域预登记「混合簇拆分 + 稀疏点门 60→30→15」两轴，专打 voxels<3/points<60/points<30 硬门在 B 域生成超小候选的复杂度 + 家具 UNKNOWN 放行策略（0.4m 邻域判决）一起复评。

## D03 交接完备性

- 命令模板完整（见 integration/map + 上文「真实可复跑命令」段），经 sub_d03_verify/ rerun_A/rerun_B 复跑 COMPARE_A.json 九会话 metric 完全一致（仅 ledger.jsonl 多 4 个版本抬头字段：schema_version/evaluation_version/segment/timestamp_s — 属引擎自动增量，不影响指标）。
- 两 ledger（A/B）各九会话齐全；SUMMARY + REGRESSION_COMPARISON_V2 + EVENTS_V2 + FINAL_MANIFEST_V2 均落盘并一致。
- 设备/物理 NOT_RUN/BLOCKED （D03-DEV/D03-PHY 保持）。
- 难帧 SVG + FLOW JSON 视觉证据已就绪（A/B × f128/187/188 各 6 件）。

## 未跑/未验尽（诚实记录）

- 没有重新完整执行 nine-session engine（可复用已有证据，主控接管理由）。
- 没有独立运行 `node sidequests/human_fusion_lab_next/background/check_b.js` 与逐字节 ledger sha 对比 —— 已委托 sub_d03_verify 并行复核，其结果若与该回传不一致以 live 复核为准并追加修订段。
- PointNet native/XGB-native parity 已在 D01 POINTNET_PARITY.json PASS；D03 的 B 链未额外重跑 PointNet。
- 浏览器 review 属于 D02 范围，不在本回传。

## 失败样本索引（最小集）

- near strict proposal FN=95（同 D01，见 D01 逐帧 `_FAILURES.json`），B 严格 proposal FN=144
- S6 strict proposal FN=63 / accepted FN=63（B）；S6 f187/f188 具体帧流量见 FLOW json
- S1 B legacy FP=347 legacy_confirmed 全部 unmatched_unknown=329（S1 strict_observed）

## 判定

- **工程接通：可交付（SUBMITTED）**。BG-B 真实接入、归因控制、UNKNOWN 参考处理均已落盘并复核一致；九会话 ledger/summary/manifest 齐。
- **算法目标：FAIL**。D03-06 八个 gate 中五个 FAIL（S6 acceptedTP、S1 FP、near TP、near FP、strict 不回退）；f187/f188 实际分类仍拒；p95 超时。
- **授权顺延**：按统一计划 v2 §5.5.1，D03 算法 FAIL 时保留 B 为研究副本，推荐第二轮分支轴 D04（候选/稀疏）与 D05a（困难负例），不建议直接 D06 组合。

## 真实可复跑命令（主控记录）

D03 的输入已在 INPUT_LOCK / FINAL_MANIFEST_V2 冻结。以下命令经主控 sub_d03_verify（`rerun_A` + `rerun_B`）复核：九会话 ledger metric 与本证据完全一致；ledger **行级** 仅在第 1、2 行多 4 个版本抬头字段（schema_version / evaluation_version / segment / timestamp_s），属引擎内部增量——：对数值 zero-effect。

```bash
# 1) BG-B 分支契约自检
node sidequests/human_fusion_lab_next/background/check_b.js
#   stdout: BG_B_CHECK_PASS missing_reference / unsupported_UNKNOWN / shared_PB / sensor_invalid

# 2) 九会话 A/B 双跑（run_b.js 为每会话一个 ledger，mode A/B）
node sidequests/human_fusion_lab_next/background/run_b.js A <A_dir>
node sidequests/human_fusion_lab_next/background/run_b.js B <B_dir>

# 3) 汇总 / 比较 / 事件
node sidequests/human_fusion_lab_next/background/summarize_b.js <A_dir>
```

run_b.js 同时写每张 ledger jsonl（`<mode>_<sid>.jsonl`）与 `<mode>_SUMMARY.json`，并在共用 outdir 里生成 S6 难帧 `A_S6_f{128,187,188}.{svg,FLOW.json}`。summarize_b 读 A/B 两个 SUMMARY，输出 `REGRESSION_COMPARISON_V2.json / EVENTS_V2.json / FINAL_MANIFEST_V2.json`（当前 top-level REGRESSION_COMPARISON.json / EVENTS.json / FINAL_MANIFEST.json 是运行更早一版的记录；**V2 是当前计算成果的唯一当前版本**）。D03 工程的 SHA 冻结在 `FINAL_MANIFEST_V2.json` 与本接管快照 `TAKEOVER_SHA_2026-10-11.txt`。

## 主控签字（不含 ACCEPTED）

状态：**SUBMITTED / FAILED-ON-ALG-GATES**。代码与证据不动；主控仅按事实回传。难帧 f128/f187/f188 A/B 分层 flow 对齐见上表；B 方向不存在任一难帧把 GT 人体并入顶层候选的范例。独立 OpenCode 审核与 INTEGRATION 回传另见。
