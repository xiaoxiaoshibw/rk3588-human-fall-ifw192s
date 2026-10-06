# 03 · Shadow A/B/C/D/E 实验计划（r6 · 先设计、后实现；本轮不实现）

- 日期：2026-10-06；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full。
- 性质：**实验设计**。production 默认只读；本文件不实现任何算法。实现前提 = 用户批准本设计 + `02` 归因工具先行产出。
- 不变量：不改 connectivity（CL-01 `NO_CHANGE` 结论有效）；不碰 UI / `POST_FILTER_ERROR`（独立工单）；不采集/部署/commit；本轮不重开 R3.0–R3.3/CL-01 结论。

## 1. 目的与判定原则

把背景层修复从「有证据」推进到「可判定」：

1. A 逐帧等价生产（强制门 G0）；
2. B/C/D 只在 `02` 归因证据支持时才实现（**禁止机械全量实现**，工单 §八）；
3. 全部变体在**完整管线**上过 W03 验收门（WD01/WD02/HP01-03 + split/新绿紫/merge/碎片），才可能有资格进入 production proposal；
4. 任一变体只有同时满足工单 §十 五条判据（静态 residual↓、false candidate↓、retention 不明显↓、无新 object-level merge、不依赖 connectivity 修改）才有资格；否则 `NO_CHANGE`。

## 2. 前置条件（Step 0，未完成不得开跑）

- `02` 归因工具交付并通过其 §4.3 全部自检；
- `05/06/07` 产出（reason 分布、error-share、shell 计数）→ 用结果**条件化** B/C/D（见 §4 各变体的"触发条件"）；
- 归因若回答 GQ=「错误不在背景层主导」→ **停止本计划并上报**（改走显示/证据层或其它方向，不硬做 matcher）。

## 3. 控制变量（全部固定）

| 项 | 固定值 |
|---|---|
| current 会话 / 帧 | `cap_20261002_223757` 全 165 帧 |
| reference | `cap_20261004_203349`（R3.1 artifact，occ 候选值标注） |
| leveled transform | 各会话最新 `tls` job（`6bc5aabf…` / `c9712aca…`；每次运行记录 id+SHA） |
| registration 臂 | `{none, tls-direct, icp}`；**主对照 = icp（隔离 matcher 增益）与 none（最坏情形）**；ICP 为固定实验条件，非真值 |
| denoise / 裁剪 | 生产 `PL.denoise`；z∈[0.10,2.50]；drop_ground=true |
| online map | 生产 `PL.build_static_map` 原样（0.65/0.85/≥2 门一律不动——禁止项） |
| cleanup / 聚类 / 候选 / 显示规则 | 全部不动（R2.6b、XY4、joint_status、Tracker、fall 不动） |
| 评价帧集 | 全 165 帧聚合 + focal 帧（f10/f30/f55/f150/f155/f160 + WD01 f2/f42 + WD02 代表 + HP 全部） |
| 合成回归 | `synth_bend_v1`（仅 retention/回归参考；不用于跨会话结论） |

## 4. 变体定义

### A — production 复刻（强制；G0 等价门）

- 语义：online-only map；`±1` 邻域；点到形心各向同性距离 `< 0.12`；XY/Z 同阈；命中即删。
- 实现：shadow 侧独立实现 + **逐点等价对比**生产 `PL.extract_foreground`（165 帧 + 合成 micro-cases：恰在门限、跨格边界、±1 边界、z 裁剪边界）。
- **G0 门：0 mismatch**。A 不过门 → 全部结果作废、STOP。

### B — XY/Z 解耦（**条件触发**）

- 触发条件（来自 02）：`DISTANCE_OVER_GATE` 中 `XY_MATCH_Z_FAIL` / `Z_MATCH_XY_FAIL` 任一侧占比 ≥20%（轴不对称），或 K1/K4 证伪指向某一轴。
- 语义：`(dx²+dy² < r_xy²) AND (|dz| < r_z)`；邻域仍 ±1。
- 参数来源（**不得拍脑袋**）：用 02 的 `05/06` 在 known-static（固定 ICP）上的轴向残差分位；候选网格锚定体素尺度 —— `r_xy ∈ {0.06, 0.09, 0.12}`（≈半格/0.6 格/半对角）、`r_z ∈ {0.06, 0.12, 0.15}` ∪ 分位数 p50/p90；网格**先锁定并写入 run log** 再跑。
- 目的：分辨 residual 主要来自水平采样漂移还是高度漂移（工单 §八 B）。

### C — AABB 阈值标定（R3.3 的续跑；**条件触发**）

- 触发条件：K1/K4 中 shell 带（d∈[0.12,0.24]）占比显著（≥15% known-static 失配点）或 R3.3 结论需标定。
- 语义：`min over ±1 占用格 of d(p, 格盒) < t`；`t ∈ {0.06, 0.09, 0.12}`（0.12=R3.3 已测；0.06/0.09=半格/0.75 格锚点）。
- **纯 containment（格内）不再作为候选**（R3.3 已证弱于 center；仅保留诊断臂）。
- 选型判据：known-static（固定 ICP）coverage↑ × near-furniture 吸收代价↓ 的权衡曲线；标定结果写入 run log。

### D — Reference fusion / 阈值（**条件触发**）

- 触发条件：`REFERENCE_HOLE` + `TIER_REJECT`（参考侧/在线漏建）占比显著（≥20% static 失配点），或 K2/K5 成立。
- 语义：`background = ref(occ ≥ occ_min) ∪ online`；`occ_min ∈ {0.2, 0.3, 0.5(v1), 0.8, 1.0}`。
- 约束：不动在线 0.65/0.85/≥2 门；`REFERENCE_STATIC > ONLINE_PERSISTENCE`（已有 HUMAN track 不得因后续静止被吸回背景，`W03_R3_ACCEPTANCE` §2.3）；persistence 只作 diagnostic。
- 评分同 C：静态吸收率 vs HP retention。

### E — 组装 + 完整管线门（唯一可进入 proposal 的门）

- 内容：A + （过门的 B/C/D 组合）；registration 取 icp 与 none 两臂分报。
- 在**完整管线**（denoise→背景→cleanup→聚类→证据→joint→Tracker，全部生产逻辑）上跑全部指标与门（§5–§6）。
- 只有 E 过全部门，才允许写「production proposal 建议」；**接入本身 = 另行授权**（且届时需 console 重打包等独立步骤）。

## 5. 指标（定义见 `02` §5；两层 + 关键帧）

**Residual 层**：residual point count；static residual point count；HP retention（clean / near-furniture 分组）；reference hit rate；unmatched reason distribution（全帧/簇/点）；shell/edge/bulk 计数。

**Candidate 层**：false human candidate（静态 proxy 簇通过候选/确认）；static false-confirm（WD01 行数、detail 静态误确认数）；human retention（HP 逐帧簇级）；split（逐帧簇数差，CL-01 同口径）；merge（CL-01 事件/点数口径）；fragment count（<3 体素）；dropped points（vs A 基线，人/静态分开）。

**关键帧逐帧**：f55 / f155 / f160 / f150 / f10 / f30 / WD01(f2/f42) / WD02 / HP(f63·f65·f146·f80·f85·f90·f92·f95·f99·f123)。

## 6. PASS / FAIL 门

| 门 | 判据 | 基线参照 |
|---|---|---|
| **G0** | A 逐点 == 生产（165 帧 + micro-cases，0 mismatch） | — |
| **G1a** | known-static（固定 ICP）coverage ≥ **0.97** | R3.3 AABB=0.9724；center=0.9401 |
| **G1b** | 完整管线：WD01 `track_confirmed` 行 = **0**；WD02 静态 candidate 行 = **0**（当前 300 NON_HUMAN/104 静态行） | `W03_R3_ACCEPTANCE` §2.1 |
| **G2** | 无新 green、无新 purple（全帧 vs 当前 leveled 基线）；静态误确认 ≤ 基线（detail A=1） | §2.3 |
| **G3** | clean HP（走/立/躺）逐帧 retention ≥ **97.5%**；near-furniture（f150/155/160 flagged）单列报告；HP02 NOT_RUN/BLOCKED | R3.3 最坏 97.5% |
| **G4** | split delta = 0（全帧）；object-level merge ≤ 基线；fragment ≤ 基线；人点 dropped ≤ 2.5% | CL-01 口径 |
| **G5** | 结果在固定 registration 下成立；不依赖任何 connectivity 修改；生产管线零改动 | 用户 §十 条 5 |

**决策**：E 同时过 G0+G1b+G2+G3+G4（G1a 支持性）+ G5 → 有资格写 proposal 建议（仍待用户拍板）；任一 FAIL → 该变体 `REJECT`/`NO_CHANGE`。**禁止单案例晋级**（用户 §12.12）。

## 7. 执行顺序与停止规则

```
Step 0  02 工具 + 归因（本计划的第一步授权单元）
Step 1  A 等价门（G0）—— 不过即 STOP
Step 2  B/C/D：按 §4 触发条件逐项判定「做/不做」，做则先锁参数再跑
Step 3  E 组装 + 完整管线门（G1b–G4）
Step 4  汇总报告 + 用户决策（proposal 与否；接入另行授权）
```

- 任一变体 G3 或 G4 FAIL → 立即淘汰，不继续调参救案（防漂亮案例调参）。
- G1a FAIL 的变体不得进入 Step 3。
- 归因显示背景层非主导 → STOP 并上报（§2）。

## 8. Provenance / 工程纪律（逐条对应工单 §十二）

1. 先审计（00）→ 2. 先计划（01–03）→ 3. production 只读 → 4. 不碰 connectivity → 5. 不覆盖旧 evidence（全部产物落 `evidence/2026-10-06_hrw03_r6/`，编号 04+）→ 6. 新 evidence 目录 → 7/8. 每次运行记录 **raw + canonical** SHA（源码 + 4 输入 + transform job）→ 9. EOL 只记录不回改 → 10. A 等价门强制 → 11. 全部结论带定量证据 → 12. 单案例不晋级。
- 运行环境：Windows + Node（离线）；相对耗时仅用于变体间比较，非板端口径。

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| ICP euler 简并（roll↔yaw non-unique） | ICP 仅作固定实验条件；真值讨论用 TLS-direct；不作"安装偏差"结论 |
| near-furniture 人体吸收（R3.3 最坏 +23pp，flagged） | G3 单列 + 逐帧报告；必要时把"静态物附近的人"列为用户决策项，不自动晋级 |
| proxy ≠ 逐点 GT | 沿用已知代理方法并三档 registration；结论写明 proxy 边界 |
| 候选 reference 仅 10.5 s | 标注为候选；正式 20–60 s 空场 BLOCKED，待授权 |
| HP02（真人弯腰）无数据 | NOT_RUN/BLOCKED；不以 synth 冒充 |
| 全帧聚类的 merge/split 口径漂移 | 固定 CL-01 的定义与脚本模式复算基线 |
| 若接入：console exe 打包 | 属未来接入步骤，另行授权（R2.6b 有先例 `r2/08`） |

## 10. 本计划明确不做

- 不做 connectivity 任何变体（XY4/XY8/XYZ26/G 已裁决）；
- 不修 UI / `POST_FILTER_ERROR`（独立工单）；
- 不改在线 0.65/0.85 阈值、不改 R2.6b、不改 leveling、不采集、不部署、不 commit；
- 不把 reference 直接接 production（须先过本计划门 + 用户授权）。
