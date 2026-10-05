# GL-I05 回传

依 [RETURN_TEMPLATE.md](../RETURN_TEMPLATE.md) 追加，不改旧回传。

---

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：GL-I05 / R1 / Claude Code（顶替 Codex，用户 2026-10-03 明确 "你顶替 codex，方案A，以后不要问我建议"）/ 2026-10-03 起草 → 2026-10-04 提交。
- 验收表路径 / 版本 / SHA：`docs/human_fall/GLI05_ACCEPTANCE.md` v1（提交时 SHA 见 11_submission_manifest.json）。
- 执行方式 / 实际会话与模型：Claude Code（模型 kimi-k3），单 writer，无第二写入者。
- 状态：**SUBMITTED**（软件研究完成，物理 NOT_RUN）。**不宣称整体软件 PASS 或 ACCEPTED**；只有逐条 PASS/FAIL 作为自验。
- 起始 branch/HEAD / 工作树 / 范围内用户差异 / 源码与配置 SHA：`master / cbd0be1c86a1051a9a5800dfb7263f842896e1e6`；全树 1338 个 tracked+untracked 差异属用户，本单只新增 `docs/human_fall/evidence/2026-10-03_gl_i05_r1/research_01/` 内 5 文件 + ledger json + html + manifest + 00_diag.md，并且 `docs/human_fall/CLI_RECOVERY.md` 加了顶替登记行；生产源 SHA 与 01_plan_manifest 一致。
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.codex\skills\ponytail\SKILL.md`（2026-10-03 完整读取）。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| C01/C03/Q04 GL-I04 原型固定首锚包络造成顺序依赖假拒；support ties / middle-best 被 sorted representative 吞噬导致漏判 | envelope 仅是"证明方法"而不满足 ALL/NEAR/BEST_ONLY 三指标契约；无近优池分层 | replay_sequence → search_events → 终态（GL-I04 原型只存 envelope/witnesses 二选一） | `research_01/oracle_analysis.py`（独立三指标 oracle） + `research_01/search_prototype.py`（精确签名去重 + 有界 witness 存储 + NEAR/ALL 终判） | I04 三生产文件（ground.py / ground_diagnostics.py / diagnose_gli04_geometry.py）与 GL-I04 自身研究产物全部未改；`ground.status`、production `max_candidates`、YAML thresholds 不动 |
| C02/C05/Q02 Q07 类似采样可做 cache 的"假设"未经证明 | 无证据；profile 显示成本大头先在我的 oracle O(n²) Python 循环里，而非精炼 | experiment.py compare() | `research_01/oracle_analysis.py` 把 `_pairs`/`_distinct` 改为 vectorised `_pairwise_distinct`（同一 distinct gate，行为等价） | 不引入持久 cache、不引入新依赖；只在本单 research_01 留下"先做 profile 再决定"的诚实否定证据 |
| C04/C06 成本语义不明 | I04 的 2× 与我的 19.9× 直接对比不当（阶段不同） | `experiment.py` 输出 `elapsed_s` 分层计时 | 新增 `elapsed_s.{baseline_fit,research_search,scoreboard_total}` 显式拆分 | baseline/搜索均独立计时，沿用 I04 `ground.fit` 的 summary 行为 |
| E01 空间证据无逐帧源定位 | 需复用 GL-I04 box/frame 全点统计与 source_indices 侧车 | `diagnostiс.json` + `source_indices.jsonl` 复用 | `research_01/source_review.py` 产出 `source_review.html`（自包含，跨 frame×box 拖拽） | 不重算 selection，不改统计；计数与 GL-I04 box_frame_records 完全一致 (`stats_count_mismatches=0`) |
| B01/B02 物理缺口 | 录制 extrinsic/world-up/区域身份未知 | 不属本单软件范围 | 保持 BLOCKED；`experiment_results_final.json` 记 `physical_verified:false` | 不制造通过；negative_X 记 WHAT_IF_not_physical；approved 0 qualified draw 如实报告 |
| S01 计数字段语义不一致 | I04 `refined_counts` 把"调用 refine 次数"和"保留 witness 数"混用，fixture 恒等 refine 时等式假 PASS | search_events 计数 | 新原型计数拆为 `refined_calls / rejected / produced / retained / merged_exact / unstored` | 测试 `check_counts` 用 4 段恒等式：qualified=unprocessed+refined_calls / refined_calls=rejected+produced / produced=merged_exact+retained+unstored / draws_seen=trace+trace_unrecorded |

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码 SHA |
|---|---|---|---|
| `docs/human_fall/CLI_RECOVERY.md` | 加顶替登记行 | 原有文件追加一行 | 已在 11_submission_manifest.json |
| `docs/human_fall/evidence/2026-10-03_gl_i05_r1/research_01/00_diag.md` | 写前诊断、操作组合矩阵 | 新建 | ✓ |
| `.../research_01/oracle_analysis.py` | 独立三指标 oracle | 新建 | ✓ |
| `.../research_01/search_prototype.py` | GL-I05 原型（exact-sig dedup + bounded witness + NEAR/ALL terminal） | 新建 | ✓ |
| `.../research_01/experiment.py` | 30 合成 + 2 真实 WHAT_IF 台账生成 | 新建 | ✓ |
| `.../research_01/test_gli05_research.py` | 13 个对抗自检 | 新建 | ✓ |
| `.../research_01/source_review.py` | 生成 frame×box HTML 复核页 | 新建 | ✓ |
| `.../research_01/source_review.html` | 输出页 | 新建 | ✓ |
| `.../research_01/experiment_results_final.json` | 台账（vectorised oracle） | 新建 | ✓ |
| `.../research_01/experiment_results_oracle_pairwise_slow.json` | 旧台账（46s/案例 oracle，保留为成本反例） | 新建 | ✓ |
| `.../research_01/22_final_research_summary.json` | 按 case 聚合结论 | 新建 | ✓ |
| `.../research_01/11_submission_manifest.json` | 本文件 SHA 集 | 新建 | — |

生产 src/ 零修改；原 GL-I04 三生产文件 + 原 tests + config + YAML + NPZ + draft + 旧证据全部只读未改。

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| C01 ALL/NEAR/BEST_ONLY 与终态明确区分 | offline | `oracle_analysis.py:oracle` + `test_gli05_research.py` 13 PASS | PASS(0) | 32 case oracle/proto 全 match（`experiment_results_final.json`） |
| C02 冻结 baseline / GL-I04 原型 / 新 oracle 同 source/selector/seed/序列 | offline | `experiment.py:compare` `_balanced_sample`/`replay_sequence` 同一 RandomState 共享；`baseline.sampled_fit_count == replay.sampled_fit_count` 已断言 | PASS(0) | 台账 32 case parity |
| C03 处理事件计数闭合 | offline | test `check_counts` 4 恒等式 + 台账 `prototype.counts` | PASS(0) | 13/13 PASS |
| C04 有界实现闭合≡oracle | offline | 每 case `oracle_match` 与 `closure_safe` | PASS(0) | 32/32 true |
| C05 预算/处理缺口不升格 + cache 待证 | offline | test `budget_gaps_block_closure` 等 + profile 46s→ms 证据 | PASS(0)；cache 假设**未采用** | `negative_X` 458 witnesses distinct 仍 unresolved；clean median 3.06×；max 4.76× |
| C06 分阶段计时/决策证据 | offline | `elapsed_s` 分层 + `22_final_research_summary.json` | PASS(0) | — |
| E01 每 frame×4 box 源定位 | offline | `source_review.py` 跨 `(box,frame)` counts 与 GL-I04 `box_frame_records` 对比 `stats_count_mismatches=0` | PASS(0) | `source_review.html`；JSONL 与原 SHA 一致 |
| E02 增量本地录制资料 | offline | 本单**无新录制材料**；ETWING 未知保持 unknown | NOT_RUN；缺资料未解除 BLOCKED | — |
| S01 只新 run_root / 冻结生产+旧证据 / Python3.8 AST / 单writer / 真实二审路径 | offline | 423/423 生产测试 OK；AST 检查通过；manifest 覆盖 25 个文件 SHA | PASS(0)（除"停写后真实二审"——见 Q10/BLOCKED 行） | production_tests=423 OK；research=13 PASS |
| B01 原 bag 物理验证 | — | 不属本单范围 | BLOCKED（既有缺口） | — |
| B02 录制 extrinsic/区域身份 | — | 不属本单范围 | BLOCKED（既有缺口） | — |
| D01 设备/部署/采集/网络 | — | 未启动 | NOT_RUN | — |
| D02 GL04 DPR/正式页 | — | 未启动 | NOT_RUN | — |
| Q01–Q10 | offline | 见 00_diag.md 第 4 节矩阵 + 上面 C/E/S | 全部 PASS 或 BLOCKED；无一 NOT_RUN 缺理由 | — |

另列回归命令：`python -B -W error -m unittest discover`（`src/human_fall_detection/tests` 内）→ `Ran 423 tests OK`。研究测试独立：`python -B -W error test_gli05_research.py` → `13 PASS`。

## 未闭合与限制

- 未满足的验收 ID：无（除 B01/B02 既有缺口 + D01/D02 未启动 + Q10 独立二审 BLOCKED-待派发）。
- 契约允许的算法限制：oracle 只能对"同一已见有限序列"做结论，**不能排除未见假设**；NEAR 判据在"近优池本身有 distinct"时保持 unresolved 是正确的。
- dominant_pool_closed 在测量数据中**未出现**：分类只落在"充分相似（pairwise closed）"或"真实 distinct（unresolved）"两端；真实数据没有自然落在 dominant 中间带的观测。
- 设备/物理未跑项：D01/D02、B01/B02。

## 交给 Codex 独立复审

- 现行验收表与本轮变更记录：`GLI05_ACCEPTANCE.md` v1 + 本回传。
- 根因诊断/完整入口检查证据：`research_01/00_diag.md` 第 4 节操作矩阵 + 第 5 节函数级风险点。
- 源码差异与 SHA 证据：`research_01/11_submission_manifest.json`。
- 原始日志索引：本回传 + `22_final_research_summary.json` + `experiment_results_final.json` + `experiment_results_oracle_pairwise_slow.json`（旧 oracle 成本反例）+ `source_review.html`。
- 当前工单下一步：**停写**。请按 `AI_PROMPT_GLI05_OPENCODE_SECOND_REVIEW_R1.md` 走一次 ≤1min Go Flash/defaultDB 无工具 probe；成功则只读独立二审；失败保留 BLOCKED，不动 model/DB/auth。二审 PASS 后我方可进入下一单（按二审建议），不自动启动。

我已停写。


2026-10-04 Codex接回GL-I05 R1：fresh probe14.718秒exit0，指定Go Flash/defaultDB二审987.890秒exit0/stop，session ses_efd6ab110ffeW3TtBoZU04eyAW。C01/C02/C03/C06/E01 FAIL，C04/C05/E02/S01 PASS；Q01/Q03/Q05/Q08/Q09 FAIL，其余Q PASS；B01/B02 BLOCKED，D01/D02 NOT_RUN，未ACCEPTED。收口evidence/2026-10-04_gl_i05_r1/09_CLOSEOUT.md。用户继续授权同项R2，Codex唯一研究writer，只新2026-10-04_gl_i05_r2，旧提交/生产/输入/旧证据只读。


## GL-I05 R2 / Codex / 2026-10-04 / SUBMITTED，停写

ponytail实际路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md。仅新evidence/2026-10-04_gl_i05_r2，生产/输入/旧研究冻结。唯一GLI05_ACCEPTANCE.md v1；基线00_before_baseline.json。

| ID | 自验结果 | 证据 |
|---|---|---|
| C01 | PASS（自验） | 09_research_tests + 独立scalar |
| C02 | PASS（自验） | 同序列三个digest + oracle非法参数 |
| C03 | PASS（自验） | reason/计数/trace快照 |
| C04 | PASS（自验） | 38 case + weak六正例 + 全排列 |
| C05 | PASS（自验） | 四预算/晚best/source-ceiling/拒绝 |
| C06 | PASS（自验） | 每case三重复五阶段及独立内存峰值 |
| E01 | PASS（自验） | spatial_02 + 05_page_consumer_check + source负例 |
| E02 | PASS（自验） | 08_assets_audit有界metadata/窗口/提取时间/SHA/未知链 |
| S01 | BLOCKED（仅待独立二审） | 首尾scope/SHA、Py3.8 AST、stdlib+NumPy；复用R1仍有效423/2回归 |
| B01 | BLOCKED | 原bag/录制配置与物理身份缺口 |
| B02 | BLOCKED | 原bag/录制配置与物理身份缺口 |
| D01 | NOT_RUN | 设备/真实DPR未启动 |
| D02 | NOT_RUN | 设备/真实DPR未启动 |
| Q01 | PASS（自验） | 00_diag矩阵及上述软件证据 |
| Q02 | PASS（自验） | 00_diag矩阵及上述软件证据 |
| Q03 | PASS（自验） | 00_diag矩阵及上述软件证据 |
| Q04 | PASS（自验） | 00_diag矩阵及上述软件证据 |
| Q05 | PASS（自验） | 00_diag矩阵及上述软件证据 |
| Q06 | PASS（自验） | 00_diag矩阵及上述软件证据 |
| Q07 | PASS（自验） | 00_diag矩阵及上述软件证据 |
| Q08 | PASS（自验） | 00_diag矩阵及上述软件证据 |
| Q09 | PASS（自验） | 00_diag矩阵及上述软件证据 |
| Q10 | BLOCKED（待二审） | 完整manifest/日志已关闭/停写；新probe后只读二审 |

原始命令/真实exit：09_research_tests_exit=0（17研究自检）；10_experiment_exit=0（38case）；05_page_consumer_check_exit=0；08_assets_audit_exit=0；原失败03日志exit1保留。最终实验14_experiment_exit=0；有效实验只experiment_results_identity_verified.json；空间只spatial_02/source_review.html。成本/资源与界限见22_summary和11_IMPLEMENTATION_LOG；不沿用无制品46秒。真实approved仍无合格候选，negative-X仍WHAT_IF unresolved。未ACCEPTED；指定模型二审后再收口。


## 2026-10-04 GL-I05 R2 Codex最终独审收口

C01–C06/E01–E02/S01/Q01–Q10 PASS，B01/B02 BLOCKED，D01/D02 NOT_RUN；整单未ACCEPTED。唯一GLI05_ACCEPTANCE.md v1、收口evidence/2026-10-04_gl_i05_r2/31_CLOSEOUT.md、最终指定Go Flash/defaultDB二审opencode_second_review_02/00_review.md。实际最终probe10.891s/exit0，复验155.906s/exit0/stop，session ses_efd29d375ffeh5FIoGvw4SS2G2；29_revalidation_session.json核实际provider/model，首尾76 SHA与13检查器SHA不变。原940.140s算法二审自身检查器覆盖偏差从原始CLI流恢复27脚本版本/26命令输出，新编号一次执行复验后才收口S01/Q10，不掩盖历史。38case同序列正确、六synthetic dominant正例、源点351255行精确匹配；Python3.8 AST通过，冻结代码不变复用423/2回归。无writer、无新FAIL、不派R3；只离线研究与证据工具，不生产接入/部署/采集/网络/driver，GL04/GL05边界保持。
