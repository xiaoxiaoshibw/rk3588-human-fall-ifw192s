# W03-R3 验收规范（Reference Static Map 阶段）

> 生效：2026-10-06（Asia/Shanghai）。来源：用户对 W03-R3.0 审计的评审判定
> （[判定记录](evidence/2026-10-06_hrw03_r3/11_user_verdict.md)、[R3.0 审计](evidence/2026-10-06_hrw03_r3/10_summary.md)）。
> 范围：W03-R3.1 / R3.2 / R3.3 与 W03 最终验收。**W03 未冻结**；每阶段独立授权、独立证据；
> 生产接入以本规范 §3 阶段门为准。本文件同时是 W03-R3 各轮工单/证据的引用基准（不复制多份判据）。

## 0. 口径（最高优先级，覆盖此前验收口径）

- **从 R3 开始，生产行为验收必须以 console 的 leveled pipeline 为唯一权威口径**：
  该 sid 最新 `recommended=="tls"` 的 job transform（`captures/leveled`）→ 原地 `R·p+t` →
  `denoise → build_static_map / pipeline_frame`。
- raw 口径只作算法诊断辅助；**不得再以 raw 的绝对 green 数量作为验收基准**
  （依据：223757 raw green=35 vs leveled green=132，R3.0 附录 A）。
- R2.6b 已完成的 raw 口径 AB 结论（split / new-green 的**相对**门）不因此失效。
- 每条证据必须记录：sid + 所用 transform job/transform_id + meta/bin SHA256 + 源码 SHA256。

## 1. R3.0 判定（已 PASS，2026-10-06 用户）

三条根因（机制计数见 R3.0 §3）：

1. **M1**：在线 occupancy 分母被监视对象遮挡污染（WD01 物 `occ(≥2)=0.593` 差 0.65 门 0.057）。
2. **M2**：每帧 ≥2 命中门 + 0.65/0.85 占用阈值让「每帧 1 点但长期稳定」的稀疏面归零
   （203349 `occ(≥1)` 中位 0.94 vs `occ(≥2)` 中位 0）。
3. **M3**：匹配半径 0.12 ≈ 体素半对角（0.1219），点到体素形心的距离量在边缘/邻格系统性漏掉
   （`d50=0.180`；半径扩到 0.20 的吸收率仍只有 0.21/0.40）。

## 2. 验收矩阵（金标）

### 2.1 负样本（必须拒绝）

| ID | 会话 / 位置（leveled） | 现状 | 预期（R3 完成后） |
|---|---|---|---|
| **WD01** Persistent upright static false human | `cap_20261002_223757` ≈ (3.50, -0.76)，h≈1.74m，n≈950，persistence 0.864，motion≈0.01m | ~101 行 track_confirmed 绿（f1–62 / f92–99 / f121–125 / f146–164） | green=0；purple=0；静态物被背景吸收；活动目标桶（5,3 / 6,-2 / 5,-1 / 5,2 / 6,3 等）保留；R2.6b `cleanup_split_delta=0` |
| **WD02** Sparse far-field static background | `cap_20261004_203349` 代表 (43,17) 桶 n≈778（及 41,-7 / 42,22 等） | 0 绿，但 300 行 NON_HUMAN candidate | foreground static candidate=0；无新 green；无新 purple |

WD01 截图口径：与审计数值 **visual correspondence highly consistent**（不宣称截图 coordinate-level verified）。

### 2.2 正样本（必须保留）

| ID | 姿态 | 要求 | 本地数据映射 |
|---|---|---|---|
| **HP01** | standing human | retain | 223757 活动目标帧段（站立/行走） |
| **HP02** | bending human | retain（与背景判据重叠最大，最关键） | 本地仅 `synth_bend_v1`（合成）；真人弯腰数据 BLOCKED，待 W04/采集授权 |
| **HP03** | lying / fall posture | retain | 223757 躺卧帧段（f92–99 / f121–125 一带活动目标） |

（映射为候选登记，R3 各轮基线测量时细化并固定帧号。）

### 2.3 共同门（每一轮 R3.x 验收都查）

- R2.6b `cleanup_split_delta = 0`（全帧）；
- 无新 green、无新 purple（对同口径当前基线）；
- 已有 HUMAN track 不得因后续静止被吸回背景（REFERENCE_STATIC > ONLINE_PERSISTENCE 优先级）；
- 人体保留率不低于 R2.6b 已交付水平。

## 3. 阶段门（顺序推进，禁止合并）

- **R3.1 Reference builder（离线，immutable）**：空场 session → leveling → XYZ 体素化 →
  `voxel ≥1 point → observed_this_frame=true` → `O_v = #observed 帧 / N_reference 帧` → 跨帧 persistence。
  输出体素 key / occupancy / 形心 / jit / 密度 / confidence；构建一次、运行只读；
  **不接 production**（不建 UI/透传/匹配）。
- **R3.2 Reference matching**：**第一件事 = leveled-reference → leveled-current 跨会话 match audit**
  （223757 current vs 203349 reference；Δroll≈2.58°、3m 处≈0.135m 风险实测）。
  未过 audit 不接 production；不足时备选「参考会话 transform 当 scene transform 同时用于两会话」，
  启用需用户拍板。融合语义：`background = reference_static OR online_static`（online 模型职责不动）。
- **R3.3 Voxel-surface matcher**：仅当 R3.2 证据支持后实施；方向为点→占用体素 AABB 距离
  （点落在占用格内 → d=0），替代「点到形心 < 半径」；具体半径/邻域策略由 R3.2 证据定。
- **W03 最终验收**：空场（墙/摆件/固定设备）0 candidate、0 confirmed；golden 中墙/摆件→background、
  人保留；WD01/WD02/HP01–03 全过。

## 4. 禁止清单（R3 阶段内）

- 不得下调在线 0.65 / 0.85 占用阈值来修静态残留（synth 弯腰人 `occ50≈0.58`，会开始吞人）；
- 不得仅扩大匹配半径（`m20` 吸收率 0.21/0.40，球半径不是主因）；
- 不得改动 R2.6b 清理逻辑；
- 不得用 online persistence（如 >0.8）做强删除；persistence 仅 diagnostic/confidence；
- 不得把 reference 直接接 production（须先过 R3.2 audit）。

## 5. 边界与待决

- `cap_20261004_203349`（10.5s）仅为**候选** reference；20–60s 正式空场录制/拉取需另行授权；
- scene transform fallback 为原则性备选，实际启用 = R3.2 证据 + 用户拍板；
- 参考图占用率门（v1 候选 `bg_ref_occ_min=0.5`）与匹配几何均**未标定**；最终标定在 W08 体系内进行；
- 采集 / 部署 / 设备操作默认 NOT_RUN / BLOCKED，除非当轮明确授权。
