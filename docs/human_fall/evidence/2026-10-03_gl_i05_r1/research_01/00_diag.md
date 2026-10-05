# GL-I05 R1 写前诊断 / 2026-10-03

工作目录 D:/Code/ldiar，run_root=`docs/human_fall/evidence/2026-10-03_gl_i05_r1`。本单是**纯离线研究工单**：不新增/编辑任何 src 生产路径，所有研究实现/测试/报告仅在本目录（默认 `research_01/`）。先写诊断再写生产代码（WORKFLOW第2节设计前置默认化）。角色：Claude Code 顶替 Codex 唯一研究 writer；OpenCode Go Flash/defaultDB 为指定独立只读二审。ponytail 硬要求已在 `C:\Users\30680\.codex\skills\ponytail\SKILL.md` 完整读取。

## 1. 范围与裁剪声明（Q00）

验收表 `GLI05_ACCEPTANCE.md` v1 C01–C06、E01–E02、S01、B01–B02、D01–D02 与 Q01–Q10 全部保留。ROS 热 reload / GL02 锁定生命周期不适用（borrowing from 生产候选 artifact），但候选 pending→terminal、caller 原地修改、文件身份、cache 版本组合**不裁剪**。本单研究属于**新增研究契约终态**（TASK研究契约 rows），不替换 GL-I04 `seen_sequence_closed_single`，也不转 `ground.status`。

## 2. 入口、函数与赋值顺序映射（Q01/C02/C03/C05）

冻结 constrained 资格唯一入口 `core/ground.py: fit_ground_plane_constrained`。本单研究**不改它**，而是独立 oracle/有界原型研究同一**已见有限序列**（GL-I04已冻结：adaptive NPZ + GL-I02 draft + GL-I05 source），保证 source/selector/seed/抽样序列一致。调用链入口映射：

- **startup 合法 input**：`capture_input.load_adapted`（NPZ）、`evaluate_gli02_candidate._load_draft`（draft）、`_draft_region`（FIT/3 validation）、`gate_selection`（rows）、`_load_constrained_settings`（YAML → `resolve_constrained_settings`）。
- **抽样与 RNG 序列**：`ground_diagnostics.replay_sequence` 返回 `(sampled, rows, events)`，用同一个 `RandomState(seed)` 先 `_balanced_sample` 再逐 iteration `rng.choice(n,3,replace=False)`；I04 `search` 即复用此函数保证同序列。
- **资格门（每 draw）** `ground.py` lines 725–748：sample_separation → triangle_area → angle(up) → offset height gate → support_count on `fit_points` ≥ max(`min_inliers`, `min_fraction*n_fit`)。合格者即“raw hypothesis”。
- **精炼（每候选）** `ground.py` lines 767–795：inlier_mask on `fit_points`；若 < `min_inliers`/fraction 则 continue；centroid → eigh → ratio≥`min_planar_eigenvalue_ratio` 否则 continue；angle 再查；offset 再查 height gate；最后 `fit_index` 上 support_count 再查 ≥ max(`min_inliers`, ceil(min_fraction*len(fit_index)))。按 support 降序、按 `_angle_deg`/`offset` 去重（**sorted代表，非移动**）成 `competition`。
- **研究 replay（I04）**：`ground_diagnostics.replay_frozen_search` 用相同 `_balanced_sample`/gate，但做“lazy representative”candidate merge（`similar` 时取 support 更大者），与 production competition truncate **不同**——I05 不照抄，只记差异。`refine_hypothesis` 与 production refine 同门但独立约化函数。`search_prototype.search_events` 对 qualified event 调用 `refine`（在 experiment 里是 `refine_hypothesis`，在 synthetic fixture 里是恒等 Lambda），按支持率 envelope / candidate / trace budgets 处理。

关键区别（根因）：I04 的 terminal 检查是 `witnesses` 全两两 `similar`，这等价“W 中任意两者 similar”，即 **ALL**；而其中固定首锚 envelope 仅是一个**充分**（sufficient）证书，不充分则保留 `similarity_envelope_not_closed`、`retained_witness`。包络与 witness 列表都可以出现 over-warranted 未决。I04 没有 **NEAR-only** 判据，也没有把 distinct witness 按 `support_count ≥ 0.8*best` 分层：它把池内 distinct 与池外 distinct 同等处理（均记 `distinct_refined_witnesses`），既可能过严（把 independent good witness 误当竞争）也可能过松（I04 的 `oracle` 仅 ALL）。

## 3. 新研究契约的几何定义（Q03/Q04）

固定源/selector/seed/抽样序列产生的“已见有限序列”经过资格/精炼门后的精炼见证多重集合 **W**（support_count 可重复）。GL-I05 新增三个独立判别，**沿用 I04 的 distinct 门**：角度>10°或 offset差>.05m=distinct，similar=其否（非等价关系）。best_support S=max support_count；近优池 **C={w∈W: support_count≥0.8*S}**。

| 判别 | 检查域 | 数学性质 | 研究终态影响 |
|---|---|---|---|
| **ALL** | W 中任意两 w_i,w_j | pairwise similar（对偶：任何 distinct 对出现即非 ALL） | seen_pairwise_closed |
| **NEAR** | C 内所有两两（含最高支持 ties） | 近优池任意两者 similar（不完整证书/缺口仍 unresolved） | seen_dominant_pool_closed |
| **BEST_ONLY** | best/tie vs C\best | 仅作对照暴露漏判，永远不用于闭合 | 无终态 |

记 **T** 为“任意 distinct 对属于 C×C”的事件。

终态规则（无任何**处理/证明/预算缺口**为前提；含 pending→terminal）：

- `seen_pairwise_closed` ⟺ W 非空 ∧ ALL 成立（即 W 内全两两 similar）。I04 原型在恰好这里**过严**（0/4/8°全相似集合首相锚 + 顺序可能 leaving 未证）。
- `seen_dominant_pool_closed` ⟺ W 非空 ∧ NEAR 成立 ∧ ALL 不成立（T 或 W\C 有 witness 与 C 中者 distinct，但 C 池内仍全 similar）。这是既有 distinct 已披露、但近优池仍闭合的状态；**不可称“所有候选唯一”**。
- `unresolved` ⟺ W 空 ∨ NEAR 不成立 ∨ 任何缺口/预算不足/证书失效。

旧 I04 的 32 条 trace 中 **8 条 best-to-near distinct=0 但近优池内 distinct>0**（high_noise seed7 best434/near422/池内33），证明“只查 best”漏判；同时 ALL 常为 false，证明“只查 ALL”过严。I04 high_noise_seed7 在旧 oracle 下 **unresolved**，在本单 NEAR 定义下也仍 unresolved（34 distinct 对在池内）——但**不是因为 best 有竞争者**，而是因为 top tie 与下一层 witness 间的链断裂被包络/代表排序误吞。因此必须独立 oracle + 归因，不能靠 best-only 或修复 envelope 单独解决。

## 4. 操作组合矩阵（WF-CODEX-R1 / R4 前置）

| 行 | 输入/状态组合 | 关联ID | 检查项与预期（映射函数） |
|---|---|---|---|
| Q01 | startup 合法 input/oldledger/config 身份；缺 source/坏 schema/frame/units/非法 settings；已有 out/输入目录拒 | C02/E01/S01 | `load_adapted` 拒绝非 adapted NPZ；`_load_draft` 拒绝非 dict；`_load_constrained_settings` 只收 ground_constrained mapping；新 run_root 写前 `if exists → fail`（用 exclusive open `x`）。 |
| Q02 | 同内容重跑/同路径异内容/新路径/caller 原地修改 points/settings/report；源码/settings 版本改变；无旧 cache 污染与覆盖 | C02/C05/S01 | 实验中 caller 在第一次 run 后**原地改** `points[0]`/`settings`/`report` dict 再跑；研究不同 run_root 命名、修改后 sequence SHA 改变就必须视为不同序列（不可复用旧 ledger）；penetration：默认排除二级 run cache 回写。 |
| Q03 | ALL×NEAR×BEST_ONLY × best tie/弱 distinct/链中间 best/0.8 边界；完整与 budget 不足终态语义 | C01/C03/C04/C05 | 手算：支持率 .8 两侧 `support_ratio=.8`（equal）与 `.8-ε`；best ties（多个并列 S）；0-6-12°链（中间 6° best 若被代表吞则 distinct 漏判）；budget 未耗尽有缺口/耗尽导致 pending → unresolved。 |
| Q04 | 0/4/8°全相似集合 ×所有首锚/顺序；0/6/12°真正链 ×middle-best/排序/代表更新，distinct 不能吞 | C01/C03/C04 | 固定 3 平面 normals（角度端点）、所有 `itertools.permutations` 输入；I04 envelope 在 0/4/8° 首锚 4° 时给 over-warranted unresolved（过严）；新 NEAR 判别必须按池内容 not first-anchor 判别；中间 best（`middle_best`）在 sorted representative 下被吞的关键反例。 |
| Q05 | 清洁/8mm/35mm/weakdistinct/close/double ×3seed/原序/置换/同 run 重复；oracle 与旧原型/冻结 baseline 对照 | C02/C04/C06 | `experiment.scene` 生成同 5 kind × 3 seed × 2 permute；oracle（无 trace 存储，仅同序列闭包计算） vs I04 `search` vs production baseline（`fit_ground_plane_constrained`）三对照；同路径重跑必须 byte 一致（除计时字段）。 |
| Q06 | early弱/late强 best/late第二平面 × 完整/早断/精炼0或耗尽/候选 cap/trace/证明预算 | C03/C04/C05 | fixture late strong（`[plane(1.)]*40 + [plane(1.14)]`）设置各 budget=0/1 → unresolved 且 counts 恒等式闭合；预算耗尽状态下支持更大 late best 出现不能把 status 升回 closed。 |
| Q07 | 相同 inlier mask /不同 mask/只 hash 相同但成员不同 × up/height/fit_rows/sample/settings/source/实现变化 × cache 满 | C02/C05/C06 | 若做精炼复用，缓存键必须 hash **实际成员字节**（fit_rows/抽样 arrays），不能只 hash normal；同 normal 不同 mask 不能命中；源码实现 SHA 变化不能命中；cache 满允许 fallback 到真精炼、记录 refuse。无 cache 也接受（记否定证据）。 |
| Q08 | 每 frame×四 box×empty/边界/alias/跨组×显示预算/研究 plane 标签；原映射/全统计不变 | E01/E02/S01 | `observe_boxes` 不动；研究如果做空间产物，仅逐 frame/box 独立展示 + source XYZ row/ordinal/seq 标定；显示 budget 不改 statistics（display_rows 仅视图）。negative-X 或 WHAT_IF plane 写 `origin:posthoc_PCA/WHAT_IF`/`physical:false`。 |
| Q09 | approved/negative-X/FIT 研究 ×原录制时间/旧零值/未知 extrinsic；无法由图/候选判身份；共享树新增/修改分归因 | C02/E01/E02/S01/B01/B02 | E01 复用既有 89 帧 4 box 全统计，不 pool fit；E02 只核 GL-I04 之后新增或此前明确漏检的本地录制材料（本单默认**无**），extrinsic/world-up 缺失仍 BLOCKED，不重复全历史，不远程采集。不凭 FIT 残差筛 validation 制造通过。 |
| Q10 | 提交/关闭日志/完整 manifest/停写 → 一次 ≤1min 指定 model/default DB 无工具 probe → 只读二审；失败保留；返工先明确单 writer 交接 | S01 | 收尾先关闭 stdout/log 再算 SHA；manifest 自身与正在写日志排除自哈希；无二审前停写；服务失败不冒充二审。 |

## 5. 函数级风险点（预审）

- `ground.py:725-748` 资格门与 `ground_diagnostics.replay_sequence` 完全一致（`min_sample_separation`/area/angle/height/support），但 `_balanced_sample` 依赖同一 `RandomState`：研究 replay 必须**严格沿用** `sampler, rows, events = replay_sequence(...)`，不能自己再 seed 一次或用不同 RNG 调用顺序——I04 `search` 已照办。
- `ground.py:767-795` refine 用 **fit_index** 上的 support_count；`ground_diagnostics.refine_hypothesis` 也用 `fit_rows` 上 support，但 production 使用 `fit_index`（长度可能不同）：研究应让 oracle 使用同一 `fit_rows` 与 refine 逻辑，或明确其差异（I04 experiment 的 oracle 不 refine，仅公证类似性，等同 fixture 恒等 refine，但现实里 refine 可能 reject，因此**新单必须做 reject 侧实验**——I04 仅在 `search_events`/example 中测 `refine→None`）。
- I04 `check_counts` 对已 refined witness 的恒等式 `qualified == refined + unprocessed` 和 `refined == rejected + retained + merged_exact + merged_certified + unstored` 在 fixture（恒等 refine）下成立；但在真实 `refine_hypothesis` 中 `refined` 计数只含由 qualified 进入 refine 的事件（拒绝也在 refined 计数内？——查实：I04 `search_events` 中 `counts["refined"] += 1` 是**调用 refine 的次数**，无论成功失败；`record["refined"]` 才是结果。因此恒等式 `refined == rejected + retained + ...` 成立（每调用必归属其中一类）。但 production 语义不同：production 的 `refined.append` 仅在成功时。研究终态定义中的“精炼见证”“拒绝”“保留”必须按 I05 新字典，不能沿用 production 命名——GL-I05 oracle 应显式记录 refined/rejected/retained 独立计数，避免像 I04 fixture 中那样互等导致测试假 PASS。
- envelope 的 0/4/8° 全相似集合在**某些首锚顺序**下为 over-warranted unresolved：例如三平面 normals 与 up 各夹 0°/4°/8°、in-offset 相似，若首锚是 4° 平面，则 0°/8° 二者都“距离首锚 ≤5°半径”、“offset span≤0.05m”，包络闭合即 merged_certified；如果首锚是 0°，则 8°在首锚 8°界内仍 ≤5°半径不符（`≤ distinct_normal_deg/2`=5°），invalid，需 retain → envelope 保持，出现 `similarity_envelope_not_closed` + `retained_witness` → unresolved。I04 已记录此 order 依赖。NEAR 判据应不依赖 envelope 首锚，直接检查近优池内两两关系，避免假拒。

## 6. 决策（由 writer 按 TASK 直接定，不回问）

1. **只补近优池判据，不改 I04 envelope/代表**：新建 `oracle_analysis.py`（无 trace 存储的同序列 ALL/NEAR/BEST_ONLY 纯函数 oracle）+ `search_prototype.py`（执行 GL-I05 `search_events`/`search`，含 NEAR terminal 检查与归因、显示 distinct 域；不沿用 I04 envelope 作为闭合资格，仅保留并算作 proof_merge）。`test_gli05_research.py` 对抗 fixture。
2. **暂不引入持久 cache；单 run 研究内做小规模 in-memory 去重**（Q02–Q07）：仅定义依赖键（fit_rows 内容 SHA、sampled 内容 SHA、up/height/settings 内容 SHA、实现 SHA）再测量命中/未命中/冲突；证明不能支持则删除 Q07 相关代码并留否定证据，保住无缓存正确实现。
3. **本源审视产物**（E01）：`source_review.py` 只读采用原 I04 diagnostic.json + source_indices.jsonl 做逐 frame/box HTML 查看，不改统计；新增本地录制材料默认无，B01/B02 保持 BLOCKED。
4. 所有冻结 ground/math/runtime/config/driver/HR/旧证据只读。python3.8 兼容（只用 stdlib+NumPy；`math.prod`不用，类型提示延后 `from __future__ import annotations`）。

## 7. 回传与停写计划

实现后：00_diag.md（本文件）→ `oracle_analysis.py`/`search_prototype.py`/`experiment.py`/`test_gli05_research.py`/`source_review.py`（如确需）→ `22_final_research_summary.json` → 手写复核 → `11_submission_manifest.json`（关闭日志后 hash）。按 `RETURN_TEMPLATE.md` 在 `returns/GL-I05.md` 追加 SUBMITTED/BLOCKED。停写后才给 OpenCode probe ≤1min 与只读二审。

— 00_diag 完，可进入实现阶段 —
