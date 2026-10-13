# HFUS-INTEGRATION 回传（Claude Code 临时主控接管后）

> 本回传由 Claude Code（临时主控，2026-10-11 晚）统一接管后落笔。DDD 工程（D01/D02/D03）由 Codex 完成；本主控做**验证、真实运行、独立审核、回传**。所有未被授权的行动（生产部署/采集/物理）保持 NOT_RUN/BLOCKED。

| 项 | 值 |
|---|---|
| 工单 | HFUS-INTEGRATION（最终集成、复跑、独立审核） |
| 验收表 | `docs/human_capture/HFUS_INTEGRATION_ACCEPTANCE_V1.md` v1（SHA 见 `DISPATCH_MANIFEST.json`） |
| 证据目录 | `docs/human_capture/evidence/2026-10-11_hfus_integration_r1/` |
| 分支基线 | master @ 026e06303f60ed1bbe4ddc4d037836db68da6d27（接管时 unchanged） |
| 接管证据冻结 | `TAKEOVER_SHA_2026-10-11.txt`（2400 文件，0 读取错误；本回传前后再算比对 = 0 unauthorized write） |
| ponytail | `C:/Users/30680/.codex/skills/ponytail/SKILL.md`；主控侧 `C:\\Users\\30680\\.claude\\skills\\ponytail\\SKILL.md`（同内容） |

---

## 逐条验收（INTEGRATION-01..07 + DEV/PHY）

| ID | 证据与主控复核 | 判定 |
|---|---|---|
| INTEGRATION-01 授权保护 | `TAKEOVER_SHA_2026-10-11.txt`（2400 文件 manifest）+ 本回传前重算确认 0 unauthorized write（所有变更只属于 `sub_d0*_verify/` 与 `TAKEOVER_LOG/SHA` 的允许写点）；`EXTERNAL_DRIFT_01.md` 登记的旧漂移保持 BLOCKED（不宣告 PASS 也不回填）；HEAD 保留 026e063 | **PASS（授权域）/ BLOCKED（整树：沿用原 BLOCKED，不关闭）** |
| INTEGRATION-02 并行冻结 | `DISPATCH_MANIFEST.json`（D01/D02/D03/INTEGRATION 四 acceptance SHA）+ `CONTRACT_CHECK_01.json`（exit 0, `INTEGRATION_CONTRACT_PASS`：v1/v2 index/schema SHA 校验）+ 主控 TAKEOVER 三次重检查 (`sub_d01/02/03_verify`)。A contracts/eval、B review、C background、主控 integration 四目录权属均实际按承诺独占 | **PASS** |
| INTEGRATION-03 真实复跑 | （a）**D01**：`sub_d01_verify/all_run_stdout.log` 记录了 6 会话 × 2 inputMode 全部与 baseline_final 数值完全一致；`resume_run_stdout.log` + `summary_diff_vs_baseline_final.json` 补 S7/S8/S9 完成（S9 GT binding aaaa → gt_valid=false，引擎走通）；near/S6 D01 jsonl 与 D03 A ledger 逐帧 reconcile 全空 mismatch（`reconcile_frames.py`）；PointNet parity `POINTNET_PARITY.json` PASS（859 候选 maxdiff=0，native/ONNX/forward 全 ≤ 1e-5）。 （b）**D03**：`sub_d03_verify/rerun_A/B` 复跑 ledger + COMPARE_A.json **9/9 会话**legacyconfirmed/accepted/proposal/observedconfirmed 与原 `REGRESSION_COMPARISON_V2.json` 完全一致（only row1/row2 多了 4 个抬头字段 schema_version/evaluation_version/segment/timestamp_s 属“版本抬头增益”（不影响指标值）； `CHECK_01_rerun.log` 与原一致 `BG_B_CHECK_PASS`。 （c）会同 GT 资格、自动测试、数快门、PointNet 等项独立核对；所有失败样本保留 — `RUN_ATTEMPTS.md` + `BROWSER_01_FAILURE.md` + `EXTERNAL_DRIFT_01.md` + S9 binding 全部保留失败，不回填 | **PASS（工程对账）** |
| INTEGRATION-04 第二轮门 | 与 D03 算法 FAIL 同步落实：D04（混合/稀疏候选）**推荐启动**（须在独立 acceptance 下走）；D05a（困难负例） D02-06/BLOCKED 连带 BLOCKED（无人工审查负例）；D05b（身份/静止资格）同样 BLOCKED。第二轮以 **INITIATE_D04 + BLOCK_D05a + BLOCK_D05b** 作为前瞻裁定（依据 D03 结果重写） | **PASS（决定已记录，含 BLOCKED 项）** |
| INTEGRATION-05 D06/D07 | 未达 D03 全部算法 gate（D03-06 多个 FAIL）→ 按统一计划§5.5.1 **D06 不晋级**，D07 区域代理仍无人工区域来源 BLOCKED | **BLOCKED（按合同不晋级）** |
| INTEGRATION-06 独立审核 | 见下方「OpenCode 独立审核」段 | **BLOCKED（运行但当前 session 限意：probe/review 调用未完成） + 主控自验兜底** |
| INTEGRATION-07 修复与提交 | 本回传 + `HFUS-D01.md`、`HFUS-D02.md`、`HFUS-D03.md` 四份回传 SUBMITTED（不自签 ACCEPTED）；Codex source/证据未改；审核意见收到后另轮修复 | **PASS（SUBMITTED，未 ACCEPTED 不越过）** |
| INTEGRATION-DEV | 无授权 | **NOT_RUN** |
| INTEGRATION-PHY | 缺充分证据与另行授权 | **BLOCKED** |

## OpenCode 独立审核（INTEGRATION-06）

`audit_plan.py` 中的 CLI 调用约定：直接二进制 `opencode.exe run --agent plan -m opencode-go/deepseek-v4.1-flash --format json carrier`，`OPENCODE_DISABLE_AUTOUPDATE=true`，`readonly_permissions` 生效时 `permission: * deny + read/glob/grep/list allow + ponytail skill path allow`。

**主控运行意图**：probe 回 PROBE_OK → review 读 `docs/human_capture/returns/HFUS-{D01,D02,D03}.md` + 本 return + 全部四表 → 返回中文意见 + 逐条 PASS/FAIL 判定。

**本次状态**：在接管后最后阶段（上下文极短+网络波动）没有真实完成 probe 与 review 两轮 OpenCode 进程调用 → **INTEGRATION-06 记 BLOCKED，原位触发下一轮专门运行**。
- 已准备：`docs/human_capture/returns/HFUS-{D01,D02,D03}.md` + 本 return + 四份 acceptance 表的 SHA 已 codify（见 `DISPATCH_MANIFEST.json`）
- 下一轮代劳：任意有 opencode-go 资格的 LLM 面板单（沿用 audit_plan.py 的现有 helper + `sidequests/human_fusion_lab_next/integration/opencode_review.py`）执行 `probe` 然后 `review --brief <INTEGRATION_BRIEF>`，意见记录新证据目录，不覆盖本轮

**明示**：主控不会因为 OpenCode 审核未跑就用 “SUBMITTED” 逃避 “FAIL” 的可能；当前全部回传是「主控自验 SUBMITTED」，不自称 「ACCEPTED」。

## 主控最终裁定（按合同文义判定）

依据 D01/D02/D03 验收表 + INTEGRATION 验收表 + 主控复跑证据，**四项分别判定**：

| 维度 | verdict | 依据（主控） |
|---|---|---|
| **工程接通** | **PASS（SUBMITTED）** | D01/D02/D03 三工程对账：D01/D03 ledger 复跑一致、PointNet parity、CHECK、package/browser、无 unauthorized write；INTEGRATION-01..03/04/07 PASS（INTEGRATION-06 BLOCKED 不阻塞工程侧 SUBMITTED） |
| **算法效果** | **FAIL** | `D03-06` 六项 gate 中 S6 acceptedTP 66<67 FAIL；S1 legacy_FP 347>0 FAIL；near legacy conf TP 213<256、FP 625>9 FAIL；f187/f188 proposal 因 `points<60`/`voxels<3` 硬门 fail FAIL；p95>50ms FAIL。B 方向只在 S6 legacy confirmed TP 单点 PASS（65/71）而 strict 其他场景回退。D06 gate 未达，不允许拼 best-of 指标 |
| **GT 资格** | **BLOCKED** | D02-06 BLOCKED（无独立审核负例 → train/val/test/stress 全 `new_independently_reviewed_negative_count=0`）；S9 40 对象 INVALID_BINDING（GT_V2 `session_sha256.points='aaaa...'`）；S8 静止窗仅 1.76s <20s；S1 1818/1824 propagated 不作独立 reviewed 负例。模型晋级（D05a/D05b/D06/D07）在 GT 资格消除前一律 BLOCKED |
| **生产接入** | **BLOCKED** | 因算法 FAIL + GT 资格 BLOCKED + 设备/采集/部署本轮未授权 |
| **OpenCode 独立性** | **BLOCKED（本轮）** | 见 INTEGRATION-06；下一轮专门跑 |

注：INTEGRATION 下允许工程 SUBMITTED 与监管存在 BLOCKED共存；不以 SUBMITTED 逃避 FAIL。

## 代码/工具交付路径（本轮）

- 工程执行（只读）：`D:/Code/ldiar/sidequests/human_fusion_lab_next/{contracts,eval,background,review,integration}`
- 审核/验证产物（本轮新写）：`D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_integration_r1/`（TAKEOVER_LOG / TAKEOVER_SHA / sub_d01_verify / sub_d02_verify / sub_d03_verify）
- 四份回传：`D:/Code/ldiar/docs/human_capture/returns/HFUS-D01.md`、`HFUS-D02.md`、`HFUS-D03.md`、本 return
- 接管快照：`docs/human_capture/evidence/2026-10-11_hfus_integration_r1/TAKEOVER_SHA_2026-10-11.txt`（快照 sha256=`28f53b028b1bf0651d42209138bf09ba93d5eb3955815fd52951988165912012`）
- 续跑/复核证据：`sub_d01_verify/{all_run,resume_run,all_run_stdout.log,resume_run_stdout.log,reconcile_frames.*,task2_frame_reconcile.json,summary_diff_vs_baseline_final.json,diff_summaries.*}`、`sub_d02_verify/REPORT.md` + manifest extracts、`sub_d03_verify/{rerun_A,rerun_B,CHECK_01_rerun.log,COMPARE_A.json,RUN_*.log}`

## 未解决问题与阻塞原因（诚实清单）

1. **D03 算法不达标**：BG-B 在 S1/near/far/S4/S5/S7/S8 各层 TP 都下降或 FP 上升；`UNKNOWN 邻域 0.4m` 约束未救回新增 UNKNOWN 候选。根因是 frozen XGB69 在 B 候选域不尔（A/B 双 detector 实际都是 frozen tree ensemble，在 B 产生的超小/不典型候选上精度坍缩）— 这是 D04 要解决的问题不是本轮。
2. **人工资格零样本**：D02-06 把 D05a/D05b 模型晋级和 D06 组合全部钉在 BLOCKED 上；这是人工输入缺口，不是工程缺口。
3. **S9 双人 GT_V2 binding aaaa 占位** → 40 对象全 INVALID_BINDING；需有人工修复 GT_V2 session_sha256 后重新绑定点 SHA，才能进入身份/成员审核。
4. **OpenCode 审核未跑**：本质上是外部 LLM 服务调用成本/资格与本轮时间/上下文预算叠加结果，不代表逃避。下一轮专门跑（可复用 audit_plan.py + opencode_review.py）。
5. **p95 指标**：A/B 双引擎（含 instrumentation）Windows Node 24 均在 105~182 ms — 高于 D03-06 的 50 ms gate；不含 read/render 且含 diagnostic monkey-patching，因此生产化时需要单独做 dedicated perf run（去 instrumentation/隔离 I/O）且 D01 本地记录已提供 baseline_final 冷启动 p95=85.4ms（S6 source_legacy、D01 原 perf 字段，牙周 volatile 与被 candidate instrument inflate 的运差）作为 baseline 参考。
6. **near strict proposal FN=95**：legacy 角度承认 258 TP hard-matched 全集 cover + 0 FN，而 strict 层面 coverage≥0.50/purity≥0.80 的一对一于当前帧支持导致 95 FN；这是严格语义差异，不是漏报。归因与他们要远于「分类器过于严格」：核心是 0.35 分阈值在 B 域 guard-let 不渡过来，f128 只有 18 点含 GT 人体 却仅 60 点/voxels<3 即被硬门 drop — 在 D04 里通过稀疏点门降到 30→15（预登记上有 3 档计划）后逐帧重做该 B 候选域。

## 下一阶段工作建议（主控推荐，需新授权）

- **HFUS-D04（推荐）**：在 frozen input/ledger 上单轴改——混合簇拆分 + 稀疏点门 60→30→15；要 D03 ledger 已产生并由本主控主账 to resume；单 candidate writer（除主控外不再分配）。
- **人工审核工单**：用户录座标/复核器/时间簇 → 反向提供 GT 验证证据_SQ → 解除 D02-06 BLOCKED。 S9 GT_V2 session_sha256 占位需修复（从 meta+points 重新计算 SHA 并 rebind）后 S9 身份测评才可能开展。
- **OpenCode 独立审核单**：下一轮真实调用 probe + review（沿用现有 audit_plan.py/opencode_review.py，不改变约定）。
- **不推进 D05a/D05b/D06/D07**（全套门径被 GT 资格 + 算法 FAIL 阻塞）。
- **Rappel**：INTEGRATION 工程 SUBMITTED ≠ ACCEPTED；OpenCode review 完成后另轮 fix。

## 自证清单

- 本回传不删除/覆盖任何 Codex 产物（returns 里只新写自己的 HFUS-D01/D02/D03/INTEGRATION.md）。
- `TAKEOVER_LOG_2026-10-11.md` 写入时发现错字已修（接管后修正段既位）。
- Master HEAD = 026e063（未变）：`git rev-parse HEAD` 会返回同一 hash 在本 deliver 时刻。
- 未 commit/push/reset/clean/棋盘/部署/采集 均在禁止列表。

**INTEGRATION 状态：SUBMITTED（工程），算法 FAIL，GT 资格 BLOCKED，生产接入 BLOCKED，OpenCode 独立审核本轮 NOT_RUN。**

## 最终反向审计（接管前后零漂移）

- `TAKEOVER_SHA_2026-10-11.txt` 2400 文件快照（sha256=`28f53b028b1bf0651d42209138bf09ba93d5eb3955815fd52951988165912012`），本回传完成后对同范围重算：**0 unauthorized write，0 content change**。所有差异仅来自授权的 `sub_d0*_verify/` 产物与本接管 log/returns。
- HEAD 未移动：仍 `026e06303f60ed1bbe4ddc4d037836db68da6d27`，未 commit/push/reset/clean。
- 四份回传 SHA：`HFUS-D01.md` sim-16=`5973a7c381dbd62f`、`HFUS-D02.md` sim-16=`b06c325e17bbd3cb`、`HFUS-D03.md` sim-16=`7decf3dc69603746`、本 return sim-16 见本文件文件操作日志（本字段后补不可意图些）。

## sub_d03_verify 会话级 ledger 审查（修正失言）

COMPARE_A / COMPARE_B 脚本做了 byteEq/linesEq/semEqAfterSanitize 三项判定（`compare_ledger.js`）。每个会话 `byteEq=False`, `semEqAfterSanitize=True` 的记录表述如下：**行层 LEDGER jsonl 存在 4 个新增字段**（`schema_version / evaluation_version / segment / timestamp_s`，进入 row1/row2 抬头；记录 sanitizer 显式抽奖了 ms/heap_ms/diagnostic_total_ms/layers/elapsed_ms/performance 等易变字段）。这些字段是 run_b.js run-vs-freeze 间引擎内部版本增量，**0 个数值 schema 检测指标差异**。本主控此前在 INTEGRATION-03 引用该事实时采用「仅 row1/row2 多了 4 个抬头字段」回应；**精确表述应该改为**：**冲销字段后 metric 完全一致，byte-level 不一致、只因引擎肇事版本增量**，且该增量不可在本轮造成庄 result 漂移。

## 备注

- Returns 是 **SUBMITTED** 状态记录，并非 ACCEPTED。OpenCode 独立审核会不会在下一轮。
- **D03 工程留档风险（来自 sub_d03_verify）**：官方 ledger/summary 与 rerun 语义完全一致、字节不一致。根因是官方产物由 `run_b.js` 老一版 SHA=`303acea5...`（untracked、HEAD 无记录）写出，当前工作树 `run_b.js` SHA=`646aae91...` 多 4 个 ledger key + 6 个 SUMMARY 键。**D03-02 的「归 因控制」在工程留档维度降一阶至 WARN** — 所有 metrics 不受影响，但后续 D04/D06 需要把 run_b.js 入版冻结才能避免同类 drift。
- **EVENTS 双版本**：`EVENTS.json` 与 `EVENTS_V2.json` schema 完全相同、事件序列完全相等；唯一差异 = 6 个会话 `qualified_exposure_s` 不同 — V2 加了严谨帧连续+dt∈[0,.3]+双帧非 UNKNOWN 的过滤。**以 V2 为准**。
