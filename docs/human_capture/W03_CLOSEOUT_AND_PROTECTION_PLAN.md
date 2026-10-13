# W03 收口 + Track 感知保护 · 当前阶段计划（草案 v1）

- 状态：**PLAN_DRAFT（登记用）**。制定：2026-10-08（Asia/Shanghai），OpenCode（`opencode-go/deepseek-v4.1-flash`，本会话）。
- 性质：**不构成任何实施 / 采集 / 部署授权**；各项以用户/编排方后续授权与各自唯一验收表为准。
- 依据：用户 2026-10-08「针对当前情况开始制定计划」+ 外部建议《Track-first + Track-aware Background》+ R39/R40/R41、HR-RET-V2、语义层 S-A+、补丁包 P1/P2/P3 现有工件。
- ponytail：实读 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（full）。本计划按「复用既有机制与已设计补丁优先、不新增依赖、新机制先设计后实施、默认关闭」筛选；明确延期非必要项（见 §4c）。
- 关系：不改变 W03 现行唯一验收表（R3.7 `06_test_matrix.md` v1）与既有工单状态；index/登记按惯例由编排方处理（本文件未动 README/returns/既有证据）。

## 1. 现状快照（事实，带出处）

| 事项 | 状态 | 出处 |
|---|---|---|
| W03 总体 | **REWORK_REQUIRED**，未冻结；T38-05/06、S4/S7 FAIL；gate 5938/11959=49.65%<50%（历史 DEGRADED、当前 artifact STALE / 全帧 SAFE=P） | `evidence/2026-10-07_hrw03_r39_closeout/08_final_closeout.md` |
| 人工 GT | **未做**；31 点 → 38 帧优先 → 155 行 + 12 拓扑帧；viewer 与清单元数据已备 | `evidence/2026-10-07_hrw03_r39_closeout/09_point_review.html`、`09_gt_pending.json` |
| 缺陷补丁 P1/P2/P3 | 已设计、测试就绪（先错后对），**未应用**；停止条件/回归要求明确 | `evidence/2026-10-08_patches_p1p2p3/README.md` |
| HR-RET-V2（融合 v2 生产接入） | inc1 交付自验 PASS；**inc2 待做**（消费侧旗标/加载路径/浏览器节点验证）+ 独立复审 | `tickets/HR-RET-V2.md`、`HRRETV2_ACCEPTANCE.md` |
| 静立保留（离线证据） | v2 人保留 99.9–100%；WD01 99.3%、WD02 ≥REF；代价=非人泄漏 2.1–2.5k 点/帧（公开） | `evidence/2026-10-08_fusion_v2_ab_r1/README.md` |
| 静立吞人根因 | ① 静态图构建只看占用率、无人体语义（`build_static_map`/`build_reference_map`）；② S 链删除=参考∪在线（静立人被在线自建模整块删） | `STILL_PERSON_RETENTION_PLAN.md` §1、`FUSION_PRIORITY_RULE_DRAFT.md` §1 |
| 连续性（闪烁） | R39 绿框 97→45 帧；归因=T01/T02 票语义 + 拓扑拆合 + reference absorption + 近地 31 点 | `evidence/2026-10-07_hrw03_r39_closeout/`、R40 §4 |
| 语义分类层 | S-A+ 离线完成：留出集逐帧 0 假 HUMAN、正样本 4/4；阈值冻结 v1 | `evidence/2026-10-08_human_semantic_sa_r2/README.md` |
| 采集 | 已授权；板端 2026-10-08 不可达 → **BLOCKED**；协议草案就绪 | `CAPTURE_PROTOCOL_DRAFT.md` |
| 外部研究 | r1（背景/聚类/tracker/地面）、r2（自适应聚类等）为研究备忘；明确不改 R40 判据 | `evidence/2026-10-07_hrw03_external_research_r1/`、`evidence/2026-10-08_external_research_r2/` |
| W04–W09 / ML | 未启动；HR-07/08 永久关闭、HR-09 封存（等用户激活语） | `HUMAN_RECOGNITION_NEXT_STAGE_PLAN.md` §7、`tickets/INDEX.md` |

## 2. 目标与不变量

### 2.1 目标（本计划期）

1. **W03 可收口**：GT 闭合 + 缺陷修复后全链复跑 + 安全门语义清楚，达到"可冻结/需继续返工"的明确判断。
2. **保留**：静立/低动人体（含"从 0 帧静立"）不再被背景吸回；进候选/确认，或给出明确 UNKNOWN。
3. **连续性**：修掉已知票语义缺陷（T01/T02）造成的闪烁；确认不依赖单帧（3/5 语义按帧成立）。
4. **新机制只登记 + 设计先行**：Track 感知保护默认关闭；无模板场景与聚类拓扑不抢跑。

### 2.2 不变量（冻结，一律不动）

`0.65/0.85`、`0.12m`、`occ≥0.5`、`voxel_m=0.15`、`3/5`（window/votes/min_age）、`0.75m`、`lost_max=8`、`EMA 0.35`、z 带（`0.10/2.50`）等全部不动；未启旗标时 **P 路径逐位不变**；不上 ML；W04–W09 不启动；不部署、不连板（采集单独走 §3 阶段 C）。

## 3. 工作包与顺序

### 阶段 A · 现在可做（逐项授权）

| WP | 内容 | 前置 | 产出 / 验收要点 | 授权状态 |
|---|---|---|---|---|
| **WP1 · 人工 GT（P0）** | 按清单标注：31 点 → 38 帧优先 → 155 行 + 12 拓扑帧；`review_gt.js` 校验；新 evidence 轮复跑 | viewer/清单已备 | 人工 sidecar（P/S 语义 + person_id）；GT 不自动绕过 gate | 人工排期（用户/标注人） |
| **WP2 · 补丁落地（P1/P2/P3）** | PATCH_01（T01 同帧唯一）→ PATCH_02（T02 按帧计票，依赖 01）；PATCH_03（I01 无效 XYZ）独立 | 补丁包测试就绪 | 补丁测试全过 + 既有套件 + P 路径约束；旧 artifact 继续 STALE、不得换分母 | **待授权**（建议 01+02 一组、03 一组） |
| **WP3 · HR-RET-V2 inc2** | 消费侧旗标（默认关；仅 VALID 走 v2）+ 加载路径 + 浏览器/节点验证 + digest 回归 + 独立复审 | 现行 HR-RET-V2 授权（已含 inc2） | V2-11/12/14（含 V2-07）PASS；独立复审逐条 | **已授权、待做** |
| **WP4 · 全链复跑** | WP1+WP2 后固定链重跑（v2 旗标关；可选开=shadow 另列）；更新 T37/T38、归因与连续性指标 | WP1、WP2 | 新 evidence 轮（不覆盖旧轮）；W03 冻结判断输入 | 新轮授权 |

### 阶段 B · GT 后决策/实施（方案已在 R40 §6）

| WP | 内容 | 依赖 | 说明 |
|---|---|---|---|
| **WP5 · P4 高度参照安全** | 31 点归属哪种面语义；source-height 显式贯通，或保持 reference 约定 | WP1 | 若证实脚腿损失且无法在冻结范围内安全处理 → 保留 SAFE=P；不为凑数改坐标 |
| **WP6 · P5 聚类拓扑** | (a) 距离连通 vs (b) 坐标一致性，二选一或分单 | WP1 | 「不改聚类（grid → 距离连通）那是 P5 且在 GT 之前」；不改阈值/人体门；r2 adaptive 实现仅备选 |
| **WP7 · Track 感知保护（新机制）** | 设计 → 离线 A/B →（授权后）实施 | 设计可先行；A/B 离线不依赖 GT；进最终验收需 GT | 见 §4 |
| **WP8 · gate 契约/支撑设计** | 双覆盖命名、独立依据；50%/60% 数值保留 | 前序 | 文档级；不放宽门、不发布 profile、不换解/挑样本 |

### 阶段 C · 另行授权（登记）

| WP | 内容 |
|---|---|
| WP9 · 语义分类层接入路径 | 正式工单 + 唯一验收表（H01–H08 草案）+ 独立复审 + 接入评审（默认关） |
| WP10 · 采集 | 板端恢复后照 `CAPTURE_PROTOCOL_DRAFT.md` 执行（正式空场 20–60s、姿态、先动后静）→ 解锁 HP02 与保护验证数据 |
| WP11 · N1 ever-free / 背景无关提案 | r1 机制：无空场模板场景；需新工单 + GT + 授权 |
| WP12 · W04 起 | W03 冻结后才进入（W04 = Track 点云标准化） |

## 4. WP7 · Track 感知保护 · 设计要点

来源：外部建议《Track-first + Track-aware Background》+ W03 冻结条件「**已确认人体静止后不吸回背景**」（`HUMAN_RECOGNITION_NEXT_STAGE_PLAN.md` §2.4）。

- **a · 删除层（已有草案，复用）**：`FUSION_PRIORITY_RULE_DRAFT.md` §3.3 S1b —— 已确认轨道足迹对**在线删除**豁免 K 帧（建议 K=8，有界、含糊即撤销；默认关）。仅当 v2 主规则 A/B 显示"贴靠家具损失"不可接受时启用。
- **b · 学习层（新增，本计划核心增量）**：确认人体区域**禁止写入在线静态图**、**禁止 tentative→strong 提升**——补 P 场景（无 reference）与根因修复；"no human history"作为提升门候选。需设计草案 + 离线 A/B（受益/不回归/代价三集沿用 v2 范式）。
- **c · 明确延期（避免过度设计）**：外部建议的"track 分数融合（0.4/0.25/0.2/0.15 权重）"与"退出迟滞"暂不做——等 WP2/WP3/WP4 复跑证明仍有残差闪烁，再做**最小状态机**设计（现状已有：进 3/5、出 lost_max=8）。不扩 bbox+margin 保护区（除非代价量化，对齐 v2"代价集"范式）。

## 5. 外部建议对位表（收录，便查）

| 建议 | 对位 |
|---|---|
| ① Human Protection Zone（确认 track 禁入背景） | **WP7b（学习层新增）+ WP7a（S1b 已有草案）**；同时是 W03 冻结条件之一 |
| ② 判定从 frame 级升级 track 级 | 部分已有（3/5 票 + 位置 EMA）；残留闪烁先由 **WP2** 修；分数融合延期 |
| ③ 迟滞状态机（进严出宽） | 已有进 3/5、出 8；退出迟滞待 WP4 证据再定（§4c） |
| ④ 背景候选 = persistent ∧ no human ∧ no motion | **WP7b** 的提升门候选 |
| ⑤ 两层背景 | 本质已有：reference（冻结）+ online（滚动）；提升门并入 WP7b |
| ⑥ 时序人体统计 | 语义层 **WP9**（S-A 已按"逐帧簇窗口 + 短窗聚合"设计） |
| ⑦ 信息极限 + 背景无关 proposal | **WP11（N1）**；物理极限已记录（r1 备忘，建议写进契约） |

## 6. 决策点（需用户/编排方）

| # | 决策 | 建议 |
|---|---|---|
| D1 | WP2 补丁授权（整包/分包） | 建议 PATCH_01+02 一组（同链路、先1后2）、PATCH_03 独立 |
| D2 | WP3 inc2 续做 | 已授权，可直接开工（writer：OpenCode） |
| D3 | WP1 GT 排期 | 关键路径最长，越早越好 |
| D4 | WP7 设计草案时间 | 建议与 WP2/WP3 并行（设计不依赖它们）；A/B 执行另授权 |
| D5 | 板端恢复后采集 | 协议已备，等在线 |

## 7. 边界

- 本文件为草案；实施以授权工单与唯一验收表为准。
- 未写/未动：README、returns、既有 evidence、生产代码、captures。
- 设备/物理/部署：NOT_RUN 不变。

## 8. 更改记录

- v1（2026-10-08）：初次制定；整合 R39–R41、HR-RET-V2、S-A+、P1–P3 补丁包现状与外部建议对位。
