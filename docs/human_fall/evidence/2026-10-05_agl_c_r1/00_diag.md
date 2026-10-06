# GL-C R1 实现前集中诊断（摘要）

来源：契约 §5、计划 §7、GL-C 工单（唯一验收表 v1，SHA 216fcdd2…）。范围：新增 `core/adaptive_ground/consensus.py` + 集中检查；不改 A/B 既有语义（只读消费）。

## 设计边界

- 输入：三估计器 estimates（A 记录）+ 同 domain + 每成员质量摘要 {valid, confidence, reasons}（由 `quality_summary(report)` 从 B 报告转换）；输出 ConsensusReport：pairwise（角/offset/pitch/roll 差）、家族/支持簇、GOOD/DEGRADED/BAD、selected、confidence cap、update_candidate_allowed、原因。
- 家族：tls/svd=ls、ransac=robust。GOOD 需 3 个成员质量有效 + TLS/SVD 数值自检 OK + 全部 pair GOOD 门；DEGRADED=唯一最大一致簇（size≥2，degraded 门）；多个不同最大簇（非传递/竞争）→ 保守 BAD；无一致簇 → BAD。
- 不平均三平面、不改输入/阈值、不给 FINAL 资格；LS-only 默认 update=false（flag 驱动，默认关）；跨家族慢更新默认关（degraded_updates_enabled=false）。
- 反规范化：pairwise 前对每个成员再做 canonical（翻转 n/d 同步、⊥anchor 判 GL_NORMAL_INVALID），所以 n≈−n 不会误判 180°。

## 操作矩阵映射

| 组合 | 行为 | 测试 |
|---|---|---|
| 3/3 有效且全 GOOD | GOOD；selected=tls；update=true；confidence=min(成员) | C-02（真实 A+B 管线） |
| 单成员 invalid（质量或数值） | 该成员不入簇；剩余唯一对 → DEGRADED；全 invalid → BAD | C-02/C-03 |
| LS 对好、RANSAC 远 | 唯一簇 {tls,svd} → DEGRADED、families=[ls]、update=false、reason GL_ROBUST_DIVERGENCE | C-03 |
| TLS/SVD 数值不一致 | numeric_check_ok=false、GL_NUMERICAL_DISAGREEMENT 可见；不能 GOOD | C-03 |
| 跨家族 RANSAC+LS 受限候选 | degraded_updates_enabled=true 时 update=true | C-03 |
| 3 仅 degraded 门 | 三角唯一簇 → DEGRADED | C-02 |
| 边界 .4999/.5001/1.4999/1.5001 | ≤ 含等号；超门 CONFLICT | C-02 |
| 非传递 A≈B、B≈C、A-C 远 | 两个不同最大簇 → BAD（不并三） | C-04 |
| 顺序/插入序 | 固定 ESTIMATOR_ORDER，重排输出逐位相同 | C-04 |
| 错域/错帧/错 units/过期 | validate 绑定后拒（raise） | C-01/C-05 |
| 当前 .74136° | good .5 门下明确非 GOOD（真实 P02 fixture） | C-05 |
| cap/selected/reasons | GOOD cap=1；DEGRADED ≤.7；BAD=0；selected 先质量后固定 tie-break | C-05 |

## 保留/不做

- last_good 资格归 GL-D（C 只给 candidate/update 标志）；不实现时间滤波、不建议 profile 改阈值；P02 历史 FAIL 不追改。
