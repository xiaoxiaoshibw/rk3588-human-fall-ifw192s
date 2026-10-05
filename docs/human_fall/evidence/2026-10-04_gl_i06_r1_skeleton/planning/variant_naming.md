# GL-I06 R1 skeleton / variant_naming（草案，NOT_RUN）

2026-10-04。variant_id 命名规则草案。规则来源：GROUND_LEVELING_ALGORITHM_DESIGN.md §3（算法路线）与 §5（每轮单因素、独立 variant_id）。本草案等于是「建议字面值 + 语义 + 设计条款映射」，实施单冻结前不是契约。

## 总规则

1. variant_id 是「账本区间 + 精炼域」的复合标识；同精炼域里参数不同 = 不同 variant；精炼域换了（sampled 域 → 全 FIT 直接精炼）必须另立 variant（设计 §3 精炼主路线：「全FIT直接精炼另variant」）。
2. 每 variant 预先固定 K 与全部超参；运行中途改参数 = 新 variant，不允许原地改 ID。
3. 已审概念（冻结基线、旧已审变体、既有竞争判据）保持原名并在 metadata 标明 frozen；任何 v2/新定义必须另版本审查，不在旧 ID 下悄悄扩大（设计 §3 竞争完整性：「新定义必须另版本审查」）。
4. R1 ring 现有 K2/K3 字样与 Codex 已实施路线重名属事实；本草案若不重排，实施单须显式声明「同名 variant 复用既有提交、仅补账本环」——该复用决定由 Codex 出具，本草案不代做。

## Variant 表（草案）

| variant_id | 语义草案 | 对应设计 §3 行 | 关系 |
|---|---|---|---|
| `frozen_baseline` | 冻结基线：现有均衡采样 + 固定 seed/预算竞争链 + 一次 TLS 精炼，照原样运行，只挂账本 | §2 复用的基线 + §3 精炼主路线「保留一次TLS基线」、§5 R0「冻结 fitter」 | 对照锚；该 ID 已冻结。盛产 W_raw 与 W_refined 供 oracle 对拍 |
| `tls_k1` | 有界猴子精炼 K=1（默认冻结果干，与 baseline 同行为，显式分配采样+门控记录） | §3 精炼主路线「每variant预先固定K=1/2/3」 | K 系列基线；K 完成不稳定时记 refinement_nonconverged |
| `tls_k2` | 有界猴子精炼 K=2：统一作用于每个合格 seed 的 2 轮「同一均衡 sampled cloud 重选内点→TLS→全FIT重算支持」 | §3 精炼主路线 K=2 + §5 R1「2/3轮有界TLS」 | 仅当 R0 有精炼偏差证据才进入；超过 K 未完成记预算缺口或 refinement_nonconverged，不静默回退前 K 的「成功」（§3 末） |
| `tls_k3` | K=3，规则同 `tls_k2` | §3 精炼主路线 K=3 | 同上 |
| `full_fit_refine` | 全 FIT 直接精炼（精炼域换为完整 FIT，不再只在均衡 sampled cloud 内重选） | §3 精炼主路线「全FIT直接精炼另variant」 | 精炼域不同，严禁与 tls_k* 混账本；Q03 关联 |
| `tls_prior_variant_005_8` | 已审0.05/8变体的显式选择版本（仅当调用方显式指定才入场，不改默认） | §3 输入与采样行「已审0.05/8变体仅显式选择，不改默认」 | 历史已审，仅账本化，不改判据 |
| `irls_huber` | Huber 加权 TLS / IRES：仅当已证混杂尾部使普通 TLS 有偏才进入；迭代/权重/尺度估计先定版，零尺度回退拒绝 | §3 鲁棒尾部处理「只有已证混杂尾部使普通TLS有偏，再比较Huber型/IRES」 | RESERVED，条件门未触发；建议 ID 预留 |

注：设计 §3「鲁棒尾部处理」行说的「零尺度回退拒绝、有效支持不足拒绝」体现在账本 `refine_reject` 的 reason 键（见 `rejection_ledger_schema.md`）。

## 命名与 ultracode 审计

- 同一 case 同一 variant 的重跑（多 seed、多置换）不改变 variant_id；seed / permutation / replicate 记在 case / ledger metadata，不记名。
- 「同 W 数学但不同 caller / 同 ID 异内容」属 Q01 负例域，靠元数据 SHA 区分，不靠改名。
- 新增 variant 必须先在实施单承认其设计条款映射，再开盘；禁止为涂全表 PASS 加条件位曲线（设计 §6：采用/否定都要有据）。
