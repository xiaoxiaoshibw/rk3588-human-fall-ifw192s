# GL-I06 R1 skeleton / oracle_design（独立 oracle 设计草案，NOT_RUN）

2026-10-04。独立 oracle 的设计草案。关联验收条目：A03（ALL/NEAR/BEST_ONLY 独立 oracle；ties/中间best/非传递链/late不能吞；精确合并多重性/指标域明示）、Q02 / Q03 / Q04。oracle 是检查器，不是地面真值；它的判定不代替验收 PASS。

## 0. 定位

- **独立于实现写**：oracle 不引用任何实现模块；输入是账本 JSON + 各 variant 完整 W 序列 + 标量指标，输出逐 case 判定。
- **标量输入**：oracle 只接标量（n/d/support/J/覆盖/角度/面积/距离/支持差）与整数计数，不接残差全数组；全数据留在 evidence 旁什文件。这与「标量 GT 误差对比」的团队概念一致。
- **不洗语义**：oracle 不带「启晀 ties」「给 late best 放行」「把链两端合一」这类静默规则；看到 ties 就留 ties，看到链就留链，看到 late 就把 late 作为合法见证。

## 1. 输入 / 输出接口（草案）

```
input:
  - ledger_json (per case, per variant)
  - W_refined_full (sequence of witness scalars: n, d, support, J_area, J_summary, coverage_area)
  - all_near_best_only_snapshot (oracle 自己計算)
  - budget_kind / remaining (from ledger.stages.budget_unprocessed)
output:
  - run_root/xxx_oracle_01/{case_id}_{variant_id}.json
    { "ok": bool, "violations": [...], "checked_stages": [...], "status": "closed" | "unresolved" }
```

`violations` 逐条引用验收 ID（A02/A03/Q02/Q03/Q04）与具体事件索引；`status` 默认 `unresolved`，只在 oracle 真正干闭一切后才 `closed`。主线不能拿 oracle 的 `closed` 直接当 ground.valid。

## 2. 三域分开判（A03）

oracle 独立重新計算三个域，不接受实现侧给的合并结果：

| 域 | oracle 判定口径（草案） | 常见误闭合 |
|---|---|---|
| ALL | W_refined 中所有精炼后见证全体 | 把 NEAR/BEST 干成 ALL；或者实现侧合并后 oracle 不独立重算而照抄 |
| NEAR | `support >= 0.8 * best_support`，`best_support = max(Support across FULL W)`；ties 保留；J 只能同 support 排序、不升穷的降支持（设计 §3 候选评分行；A05） | 用 J 小但 support 底下来的强行 best -> 改 NEAR 锚点；丢掉 `support == best_support` 的另外 ties |
| BEST_ONLY | `support == best_support` 的见证全体（可能多个）；只作为报告域，不作为合并输入 | 把 BEST_ONLY 当成唯一，丢掉其它 NEAR；或在 BEST_ONLY 上干相似传递把 distinct 洗掉 |

实现侧有合并逻辑（精确签名去重，多重性在 trace 保存）时，oracle 分别检查：
- 合并前后集合的标量多重性一致（合并不造新数学对象）。
- 合并后 ALL/NEAR/BEST_ONLY 与 oracle 独立计算全等（排序后逐项对比，含 support / n / d / J / coverage）。
- 多重性 metadata（`merge_sig` / `multiplicity`）与 trace 互证。

## 3. 硬反例族（Q02 / Q03 / Q04 预冻结反例目录草案）

| 族 | 输入模式 | oracle 必须拒绝的误闭合 |
|---|---|---|
| 全相似同位 | 三个平面 n 两两 < 10°、d 两两 < 0.05 m | 不得合三为一；NEAR 保留全部 ties |
| 非传递链 | A∼B、B∼C、A≁C（角度/距离超门） | 不得因 B 存在把 A 与 C 合 |
| ties 满 support | 多个 witness support 同 max | BEST_ONLY 域全体保留；不随机选 |
| 中间 best | 最大 support 在中间区，两侧 NEAR distinct | 不得把两侧丢进 best 的合并域 |
| 弱 distinct | 角度 / 距离在 10° / 0.05 m 边缘（Q04） | 不因为有 J 更小的 best 而被合 |
| 晚强 best / 晚 distinct | 预算未耗尽但后来才出现的 best / distinct | 不得被「先代表后合并」提前吞 |
| 预算 0 / 边界 / 不足 | budget_kind 越界或只剩 0 | 事件必须走 `budget_unprocessed`，terminal 一律 unresolved |

加的与 Q03 相关：精炼轮内 cycle / later_round_violated_prior → `refine_reject`，oracle 必须看到 unresolved，不允许静默回退到前 K「成功」状态。

## 4. 标量 GT 误差对比（合成分支）

- synthetic 案例 oracle 按冻结 GT（法向角 °、偏移 m）计算误差；真实 approved 案例 / WHAT_IF 只在 WHAT_IF 分支记录观察误差，仍 physical=false（B01），不进入 GT 误差对比。
- 最差独立区域（A06）在 oracle 侧按「独立 frame_group ≠ FIT 组」重算 coverage/RMS/P95，与实现侧分列；oracle 不拿实现侧按 FIT 区域的挑选结果。
- 三个 validation frame_group 相互不同且不等于 FIT（设计 §5 独立验证行）；oracle 每次都读带 SHA 的输入不见验证源的混入。

## 5. 运行与权威（草案）

- oracle 自己三重复（replicate ≥ 3），与其余成本台账分开（A07）。
- oracle 结果并入 evidence run_root 台账，但不改 GLI06 v1 表中任何状态；状态改写只属于独审。
- oracle 报告「RO 账本计数与 W 域对拍一致」不等于「数据从物理上正确」；该区分在 SUMMARY 中明示（设计 §6）。
