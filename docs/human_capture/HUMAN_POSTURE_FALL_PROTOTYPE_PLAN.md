# 人体姿态与跌倒离线原型（W06/W07 起步）

版本 v1 · 2026-10-11（Asia/Shanghai）。状态 **PLAN_ONLY / 未实现任何算法**。承接用户优先级纠偏：P2 骨架被 GT 阻断后，本项目必须存在一条**不依赖完整骨架的姿态基线**，避免完全停滞；同时不伪造召回率、不把高度降低直接当跌倒。

## 1. 当前真实缺口

| 项 | 状态 | 证据 |
|---|---|---|
| 站立/坐/蹲/躺/跌倒实现 | **0 行代码** | 子代理 Q5：`pc_apps/human_ml` 仅 person/noperson，`auto_person_label.py` 只有 `stand|none` 标志 |
| 九会话人体动作真值 | **0 帧** | `cap_20261010_*` 全部只有 object 类 GT，无 stand/sit/squat/lie/fall 标签 |
| 骨架（HEAD/TORSO/PELVIS/四肢）真实输出 | 0 个有效节点（336 簇 UNKNOWN） | HR-SKELETON-OFFLINE R1–R3 BLOCKED |
| 现有检测链可提供的人体特征 | **已实现且 PASS**：3D bounding box、z-extent、XY-span、点数、Centroid XY/Z、点数时序、候选置信度、track 长度 | `human_fusion_lab/core/…`、Demo V2 同候选四分数表 |

**结论：可以立刻启动纯几何姿态原型**（仅用现有稳定输出），不等待骨架 GT；同时**必须**补一份人工姿态 GT 采集清单。

## 2. 两条并行路线（明确分离，互不冒充）

| 路线 | 输入 | 能拿到的 | 锁死 |
|---|---|---|---|
| **骨架姿态（W05→W06）** | SKO 解锁后的真实 5–7 节点 | 头/躯干/骨盆空间关系、跌倒姿态夹角 | BLOCKED 于人工 GT（S9 + 站立会话 3 帧） |
| **几何姿态原型（独立，先启动）** | 当前已稳定输出的 bbox / extent / centroid / track / 时序 | 站立 vs 躺下的 z-extent 阈值、坐下时质心下沉、跌倒过程的快速 z-collapse、跌倒后静止躺地 | **不需要骨架**，但召回率/准确率仍待人工动作 GT 验证 |

两条路线的结果分别记账；几何路线 PASS 不能被升格为“骨架姿态通过”，反之亦然。

## 3. 几何姿态原型（POC）范围 v0.1

只新增 `sidequests/human_fusion_lab/posture/`（不污染 fusion 基线、不改生产）。读取 `/api/frame` 已返回的 confirmed track 的 bbox/extent/centroid 时序，做：

| 状态 | 最小可行判据（暂不报准确率，只出原型） |
|---|---|
| STAND | 对象 bbox z-extent ≥ `H_STAND`（约 1.2 m）且近 1 s 内未坍塌；配合点数与宽高比 |
| SIT / SQUAT | z-extent 处于 `H_SIT_LOW…H_SIT_HIGH`；质心 z 较其自身 track 早期基线下沉 `>Δz` |
| LIE | z-extent < `H_LIE`（约 0.35 m）且 X 或 Y span 显著大于 Z span（主轴水平） |
| FALL 动作 | 在 FALL 事件前 `FALL_WINDOW_MS` 内出现 z-extent 快速跌落 + 质心 z 下降速率超阈值；**不允许只凭高度降低判跌倒** |
| FALLEN 持续 | LIE 条件持续 ≥ `STILL_HOLD_S`，且 XY 质心位移 < 阈值 |

所有阈值先按量纲以占位区间写入 `posture/thresholds_v0.json`，并标注 **PLACEHOLDER_UNVERIFIED**；任何指标只在拿到了人工动作 GT 之后报告。

## 4. 人工姿态 GT 数据缺口（本轮明确列出）

要获得任何召回/精确数字，**必须**由人工补齐。走与 S9 GT 完全相同的 `gt_annotator.html` 工具：

- [ ] **S9**（`cap_20261010_180751`，双人交叉）：修复 f1 索引复制 + 重选点；同时给两 person_id 标注每帧 STAND/WALK 状态。
- [ ] **站立/行走**（已具备 object GT）：`cap_20261010_175429`（S3-near 走）逐少量代表帧指定 STAND，用作原型阈值 sanity 锚点。
- [ ] **坐 / 蹲**：现九会话**完全没有**，需新增采集会话（当前用户指令禁止主动采集；列入未来采集请求）。
- [ ] **躺 + 跌倒**：现九会话**完全没有**。安全室内跌倒采集（仰卧/俯卧、快倒/慢倒、跌倒后 5 s 持续）也是新采集，不自动启动。
- [ ] **家具**：已有（566 个已知样本，但全来自同一空场 ROI，新家具泛化仍 UNKNOWN）。

在这些帧出现有效人工动作 GT 之前，`POSTURE_ALL_METRICS = UNKNOWN`，禁止落地任何 P/R/F1 数字。

## 5. 与现有产物的接线（增量不重建）

- **Demo V2 展示**：新加 `posture` 图例层（站立/坐/躺/跌倒候选色），读 `/api/frame` 里新加的 `posture` 字段。**V1 不改。**
- **案例定位**：`CASES.json` 增补 `POSTURE_AMBIGUOUS`、`FALL_CANDIDATE` 两类，仅当算法主动声明时列出，不让 UNKNOWN 被错记为成功案例。
- **回归**：`run_unify_tests.js` 增加姿态契约测试（占位阈值、UNKNOWN 计数、把 GT 缺失一律置 UNKNOWN 而非误判负类）。
- **骨架联动**：SKO 解锁后，把骨架主轴夹角作为**另一独立特征**加入 posture 输入，不替换几何原型，供 AB 对照。

## 6. 不做的事（防越界）

- 不部署、不接入生产、不改 `pc_apps/human_replay` 默认 tracker、不碰冻结权重。
- 不凭 z-extent 自动把对象框写成“FALL 已识别”；FALL 必须同时满足时序坍塌与持续躺地两个条件，且本轮只算“候选事件”而不是结论。
- 不从 W06 跨到 W07 完整状态机；本计划只交付 POC 原型 + 数据需求清单。

## 7. 下一轮实际起手（依赖排序）

1. **若用户完成 S9 + 一站立帧 GT**：跑 P2 骨架工具线，产出真实节点（解锁 SKO-04/09/14），同时把同一 GT 赋给姿态原型作阈值 sanity check。
2. **不等 GT**：实现 `sidequests/human_fusion_lab/posture/` v0.1 + UNKNOWN 计数 + thresholds_v0 占位 + Demo V2 图例，让用户能在已知会话上**离线肉眼观察** STAND vs LIE 切换效果。
3. **采集授权**：若用户批准追加室内坐/蹲/躺/跌倒采集，按 `CAPTURE_PROTOCOL_DRAFT.md` 走（不自动执行）。

> 本文件为计划与数据需求清单；无算法指标，任何“召回/精确”数字都需真实动作 GT 才能产出。
