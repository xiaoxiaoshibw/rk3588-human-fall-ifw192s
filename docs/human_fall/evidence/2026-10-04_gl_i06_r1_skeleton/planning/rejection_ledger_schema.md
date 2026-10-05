# GL-I06 R1 skeleton / rejection_ledger_schema（JSON schema 草案，NOT_RUN）

2026-10-04。逐关卡拒绝账本的 JSON schema 草案。目标验收条目：A02（逐阶段拒绝账本：先验/采样退化/支持/精炼/实际见证竞争/预算；reason 汇总不替代真实计数）、Q02（账本挂钩 all/near/best_only 与预算缺口）。本草案只定义结构与约束，不生成任何实例。

## 0. 总约束（先于字段）

- **真实计数原则**：任何关卡必须同时保存 `count`（整数，events 数组长度）与 `events`（逐事件明细，含 reason）。`reason_histogram` 是从 events 派生的**汇总副本**，不是计数来源；检查时必须存在至少一条无害断言 `count == len(events)`，且 reason_histogram 的计数总和 == count。「reason 汇总不能替代真实计数」——A02 第一接受判据。
- **拒而不闭合**：任何关卡不会把 event 标成 `closed`；事件只在 oracle / 独立验证侧关闭，账本侧一律 `unresolved` 或 `rejected`。
- **单点拒绝**：同一 event 只在首次拒绝它的关卡出现一次；拒绝后不再流入下一关卡（`rejected` 项）。
- **可比性元数据**：`source_sha / settings_sha / selector_sha / seed / raw_sequence_sha` 必录，是 A01 对拍的介质。

## 1. 顶层结构（draft 口径，JSON Schema draft-07 骨架）

```json
{
  "$id": "bias_ledger_01",
  "variant_id": "frozen_baseline",
  "case_id": "wall_noise_19_soft",
  "seed": 19,
  "permutation_index": 3,
  "replicate": 1,
  "source_sha": "<sha256>",
  "fit_row_sha": "<sha256>",
  "settings_sha": "<sha256>",
  "selector_sha": "<sha256>",
  "raw_sequence_sha": "<sha256>",
  "domain_a_shas": { "W_raw_sha": "<sha256>", "W_refined_sha": "<sha256>" },
  "stages": {
    "prior_reject":        { "count": 0, "events": [], "reason_histogram": {} },
    "sample_degenerate":   { "count": 0, "events": [], "reason_histogram": {} },
    "support_reject":      { "count": 0, "events": [], "reason_histogram": {} },
    "refine_reject":       { "count": 0, "events": [], "reason_histogram": {} },
    "witness_competition": { "count": 0, "events": [], "reason_histogram": {} },
    "budget_unprocessed":  { "count": 0, "events": [], "reason_histogram": {} }
  },
  "final_metrics": { "best_support": 0, "W_refined_len": 0 },
  "terminal_status": "unresolved"
}
```

字段语义（草案，冻结前可调）：

- **`stages.*.count`**：该关卡 reject 事件的整数计数（必须是 `events` 长度）。
- **`stages.*.events[]`**：逐事件。每个 event 至少含 `seed_id / rejected_at_stage / reason / detail`；detail 中支持差度量（如 support / under_gate / angle_deg / area_m2）直接来自计算，不经 reason 字符串二次翻译。
- **`stages.*.reason_histogram`**：`{ "<reason>": <int>, ... }`，对所有 `events.reason` 的分组计数。只作审计，不作调节。
- **`budget_unprocessed`**：总 LO 预算在陈余 seed/轮未执行时使用的关卡；与 `refine_reject` 中的「精炼完成但不收敛 unresolved」严格分列（设计 §3 / AI 提示 Q03）。前者是资源缺口，后者是处理完成不收敛；两者都不得 closed。
- **`terminal_status`**：账本本身不写 `closed`；出现预算缺口或精炼未收敛一律 `unresolved`。

## 2. 各关卡 reason 键集合（草案，非穷举，实施单冻结）

| 关卡 | 主要 reason 键 | 详情键（示例） |
|---|---|---|
| `prior_reject` | `angle_out_of_range` / `height_out_of_range` / `normal_flipped`（法向綯反，但仅记录，不改符号舀成功） / `prior_missing` | `angle_deg` / `height_m` / `gate_lower` / `gate_upper` |
| `sample_degenerate` | `min_separation` / `triangle_area_too_small` / `collinear` / `too_few_points` | `min_pair_dist_m` / `area_m2` |
| `support_reject` | `support_under_min` / `inlier_count_under_min` | `support_count` / `min_required` |
| `refine_reject` | `tls_nonconverged` / `cycle_detected` / `later_round_violated_prior` / `zero_scale` / `nan_residual` / `too_few_effective` / `proposal_degenerate` | `round` / `residual_before` / `residual_after` |
| `witness_competition` | `tie_kept` / `chain_pen_glyph` / `near_distinct_left_unresolved` / `best_only_rejected`（应用竞争门但保留 ties 的异常） | `support_a` / `support_b` / `angle_deg_ab` / `dist_m_ab` |
| `budget_unprocessed` | `seed_budget_exhausted` / `lo_budget_exhausted` / `candidate_cap_hit` / `serialization_or_trace_cap_hit` | `budget_kind` / `remaining` |

「旧代表动作」类事件（代表保留/合并）若需要，也在 `witness_competition` 关卡入记，并在 detail 中取 `merge_sig` / `multiplicity` 子段（与 A03 的「精确合并多重性」直接关联）。

## 3. 校验规则（草案）

- `stages.*.count == len(stages.*.events)`（所有关卡）。
- `sum(stages.*.reason_histogram.*) == stages.*.count`。
- 存在任一 `budget_unprocessed.count > 0` 或任一 `refine_reject.events[].reason in {tls_nonconverged, cycle_detected, later_round_violated_prior}` 时，`terminal_status` 必须为 `unresolved`（不靠 reason 字样机械检查，而靠事件入口检查）。
- `raw_sequence_sha` 与 `W_raw_sha` 可不同（raw 是序列 hash，W 是精炼域 hash），但各域之间必须能还原可追認的对拍路径。
- 账本自身不存放残差全高清/每点数组；这些走 oracle 侧或 evidence run_root 附什文件，账本只存标量和 SHA 指向。

## 4. 与既有契约的关系（引用，不改写）

- A02 的「先验/采样退化/支持/精炼/实际见证竞争/预算」六分关卡名与本文顶部 `stages` 键一一对应；名字不走开新赛道。
- AI 提示 Q02 中「预算 0/边界/不足」由 `budget_unprocessed.reason` 的 `seed_budget_exhausted / lo_budget_exhausted / candidate_cap_hit` 与 detail.budget_kind 覆盖。
- 该 schema 草案不重写 GL-I05 / GL-I06 既有账本 schema；是 shadow 计划中的候选定义，冻结前不与任何已提交账本混用。
