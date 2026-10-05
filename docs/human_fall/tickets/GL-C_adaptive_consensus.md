# GL-C：三估计器一致性仲裁 / 计划工单 v1

状态：PLANNED / IMPLEMENTATION_NOT_RUN；前置A/B软件验收，后续明确启动。来源：[最终计划§7](../ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md)、[接口契约§5](../ADAPTIVE_GROUND_LEVELING_CONTRACT.md)、[WORKFLOW](../WORKFLOW.md)。本文件唯一验收表v1。

## 目标与范围

新增consensus模块，所有三pairwise角/d/pitch/roll差、支持簇/家族、GOOD/DEGRADED/BAD、明确选择/score cap。TLS/SVD是LS同一家族，不用假独立多数。n≈−n先与d同步规范化；无法确定符号invalid。固定选择规则，不平均三平面、不改变输入/阈值。

前置操作矩阵：3/3有效、每一个estimator单独invalid、每一种pair agreement、3-way split、非传递链、角/offset门上下/相等边界、同域/错域、法向正负、结果先后/过期残留、LS-only × 有/无last_good资格。C只给candidate_allowed，不直接应用。

## 唯一验收表 v1

| ID | 要求、触发/负例与预期 | 检查/证据入口 | 当前结果 |
|---|---|---|---|
| AGL-C-01 | 三pairwise指标与独立夹角/offset scalar oracle一致；翻n/d不误180°；不同frame/domain/units/weights禁止比较 | analytic vectors + identity mismatch | NOT_RUN |
| AGL-C-02 | 3valid且全部GOOD门→GOOD；2/3或3仅DEGRADED门→DEGRADED；无一致簇/硬fail→BAD；边界语义唯一 | complete agreement graph matrix | NOT_RUN |
| AGL-C-03 | TLS≈SVD、RANSAC分歧或invalid：DEGRADED但LS-only不bootstrap/更新；RANSAC+LS支持可给受限candidate；numerical故障不可隐藏 | family-aware majority/consumer eligibility | NOT_RUN |
| AGL-C-04 | A≈B/B≈C/A远C非传递链不全部并为GOOD；order/tie确定；没有方向/唯一支持时保守BAD；不调门消失败 | nontransitive/tie/permutation cases | NOT_RUN |
| AGL-C-05 | final confidence cap/selected estimator/支持簇/原因完整；新旧frame/epoch不能混三结果；当前.74136°在候选good .5门下明确非GOOD | P02 current fixture + stale-result cases | NOT_RUN |
| AGL-C-S01 | 当前模块只候选不committransform；按WF单writer、pony_tail/diag/回归/manifest/停写/独审，旧物理字段不改 | source scope and review | NOT_RUN |

## 交付

consensus模块/完整状态组合检查与diagnostics fixture；证据`<date>_agl_c_rN`，回传`GL-C.md`。无共识是可解释拒绝，不能为完成编造GOOD。C过关后D另行启动。
