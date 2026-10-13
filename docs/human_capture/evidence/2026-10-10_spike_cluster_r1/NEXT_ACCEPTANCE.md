# NEXT_ACCEPTANCE.md — CLUSTER-ADAPTIVE-R2 验收表草案

日期: 2026-10-10
状态: **PLAN_DESIGN** (不构成实施授权; 不集成生产)

本草案定义 "如果想再推一步自适应聚类 (R2)" 的完整验收标准。**当前工时补充: R2 主线不主张立即重启**——按 spike r1 结论, 应先补 GT / 立一项以真实问题驱动的 ticket.

## A. 先决先块 (必选)

并不是关 R2 本身, 而是**让 R2 有意义再被推**:

| # | 内容 | 判定 |
|---|---|---|
| A1 | 立一个 "走-停-走" GT ticket (source:human, r_xy 覆盖 0.8 / 1.5 / 2.5 / 4.0m) | 不做新采集, R2 裁剪为 UNKNOWN |
| A2 | 立一个 "弯腰/低姿态" GT ticket (source:human, 含 0.6 / 1.5 / 2.5m) | 同上 |
| A3 | 柜位 prob 0.87 的 GT 文档化 — 柜位是否同一物理柜? | 让 PASS 的域定语化, 避免误标 |
| A4 | 可选: 远距 GT (r_xy > 3m) | 能 pgy 原 / 贴墙 的 site 内测 |

## B. R2 验收表 (25 CAP; 通过标准 PV)

只有当 §A 中至少 A1 落地后, R2 才能启动, 与 R1 主轴 e 分支:

### B1. 距离自适应 (B) per se

| CAP-ID | 描述 | Pass 标准 | 数据 |
|---|---|---|---|
| R2-B-01 | 走-停-走 154007 动态 GT 中, B 优于 A 至少一项域 (hit / sf / sfu_density) | ≥ 一个显著域 (Wilson by-run 1.0 vs 0.8) | 现有 |
| R2-B-02 | 走-停-走域 B 不再降低任何域 (cab / person_sticky) | 无显著退化 | 现有 |
| R2-B-03 | 弯腰 GT 中 B vs A 至少 person_sf ≥ 30% 改善 | ≥ 一个显著 | 需新采 |
| R2-B-04 | 远距 GT (r_xy>3m) 中 B vs A 至少 hit ≥ 10% (p50 10% → 验证自适应半径在高 r 效用) | ≥ 10% | 需新采 |
| R2-B-05 | B 在不同 r 收益单调 r > 3m 才显著 (不提供 r < 1.5m 收益) | 证机制合法而非产物噪 | 需新采 |

### B2. z-band 防并簇 (C) per se

| CAP-ID | 描述 | Pass 标准 |
|---|---|---|
| R2-C-01 | 柜 vs 人 zmax 不同带场景 (122616 / 122637) C cab≤0 复现 | cab=0% |
| R2-C-02 | 柜 vs 人 zmax 同带场景 (121622) C 不被指责劣化 (cab ≥ A 但仍 hit=100, 低 <=A+10%) | 退化可控 |
| R2-C-03 | C 不把人拆成多簇 (PER=1) 站立 ≥ 95% | PER≥3 帧 ≤5% |
| R2-C-04 | C 的 zband 区域在确切拉开人+柜 (d_c=0.3 与 d_p=0.55 的异 zband 对) | 实体复现 |
| R2-C-05 | C 的 subcell 地图与空闲容装置耦合 (稀疏点 z 处在带带边) | 不占未建模带 |

### B3. 不变性-性能一收

| CAP-ID | 描述 | Pass 标准 |
|---|---|---|
| R2-P-01 | A 基线 12 段站立回归 (SHA 冻结, IoU=1.000) PASS | 不下线 |
| R2-P-02 | 生产 detect_overlay.js / rf_person.js / bg_envelope.json SHA 不变 | 合规 |
| R2-P-03 | find_clusters 耗时 P95 < A 的 3 倍 | 10Hz 板端可行 |
| R2-P-04 | 板端 RK3588 实机性能 (stdlib+NumPy, 无 scipy) | 实则 P95 < 100ms (10Hz) |

### B4. 一致性-审计

| CAP-ID | 描述 | Pass 标准 |
|---|---|---|
| R2-A-01 | OpenCode Go DeepSeek-v4-Flash / Claude Sonnet 双审计 通过 | 两审计无一 FAIL |
| R2-A-02 | provenance 在 params_frozen.json / calibrate_k.py 严一致 | 审. |

## C. R2 关键技术决策 (草案)

下表在 §B 走通后才启动:

| 项 | 默认意向 | 触发改变 |
|---|---|---|
| zband 数量 | 5 带 (v1) → 稀疏带 3 带 (粗) | C1/C2/C3 的失败案例分析 |
| eps 形式 | `eps(r) = max(eps_min, k*r + b)` | 走动向非线性带 (p90 p95 分枝有证据) 推同 |
| 对称门 | symmetric=True | 观察 122616/637 桥接再评 |
| min_points | 30 (现意) | 有 GT 硬停回归门 (≤ PER=1 站立 ≥95% 不降) |
| bridge_policy | point-band (v2) | 考察跨带频率 才可降 (Hi-F 重) |

## D. 复用现有 spike 接缝

- 脚本: eval_cluster.py / summarize_eval.py 不重写, 仅 strip 由 GT_ANCHORS 上新会话支撑
- data flow: R2 采集的新会话 → ai_labels (auto/models) → eval_frames 过 spike pipeline → SUMMARY 由本模板评估
- 输入接口: spike r1 所有 R/T, bg, 常量冻结在 baseline.json, R2 会话同意使用

## E. 排他事项 (R2 明确不做)

- 可证据: 新 RF 训练. R2 在 51.0 维冻结, 所有对 adj 凝蔑领
- 走产: Py 两侧可由生产不变

## F. 建议工时 / 优先

- §A 采集前准备: ~1 天 (配平 + 13 个锚)
- §A 采集 / 逐段用 3-5 分钟: ~2 小时 × n_session
- §B1-B4 跑评估: 不及 spike r1 (主要省); 不超 1 天
- **触发条件**: A1 落地后, 由任何人打开工单俱出.

## G. 与本 spike 的关系

- R1 是 **UNKNOWN** — 它意味着顺 "距离自适应可能不是正确方案"
- R2 存在的预设: 在 A1/A2 等采集了真问题的 GT 后, 重新提请验证 "在那个新 GT 上是否值得". 若新 GT 的标签词使 "自适应"成为对的问题方案 (例如 r>3m 碎) 则 R2 接着前进
- **本草案立者不强制任何一件具延动作** — 它是预留产物, 不预排期同项目主轴; 是否启用 由 HUMAN_RECOGNITION_NEXT_STAGE_PLAN 按捕获 STAT 冷启.
