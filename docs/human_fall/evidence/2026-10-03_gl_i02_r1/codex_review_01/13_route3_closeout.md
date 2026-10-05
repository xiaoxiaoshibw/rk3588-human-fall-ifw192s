# GL-I02 R1 路线3 收口决议 / 2026-10-03

顶替者：Claude Code（CLAUDE_STANDBY）。本文件按用户 **路线 3** 决议，把 GL-I02 R1 在**协议-场景矛盾**处冻结真实 fit，不推 R2 协议改动、不进 production、不改 ground/calibration.py。下文按事实逐条记录。

## 1. 走通到"ground_points_insufficient" 的全部事实链

### 1.1 协议数学（拆分）

- `ground.py:153-157` — `sensor_height_m = offset`，并要求 `offset > 0`。`n · p + d = 0` 中 **`d` 是"法向 n 下的传感器高度"**，因此 normal 必须**指向传感器**（地板在 -n 方向），offset 才是正的"真实高度"。
- `ground.py:738-739` — RANSAC 中：`if normal @ up < 0: normal = -normal`，把法向**朝与 up 同向**翻转。`offset = -normal · p0` 由此物理上等于"传感器与地板的有符号距离"（沿 up 反方向）。
- `ground.py:743` — `height_low <= offset <= height_high`，本单 `sensor_height_interval_m = [1.2, 1.7]`。
- `ground.py:413` — GL-00 R4 协议强制：`min_inliers >= 100`（below threshold is REFUSED，不是软错误）。
- `ground.py:413-419` — `min_points_per_region >= 20`、`independent_regions_min >= 3`。

### 1.2 真实数据事实

- GL-I01 R1 adapted NPZ：89 frame_groups × ~1214 点/帧（点频按 frame 裁切）。
- 单帧 `~1214` 点 - `valid_index` 过滤 - 单个 fit_group - `_balanced_sample` 空间 cell max 4 点 → **sampled_fit_count ≈ 80**（< min_inliers=100）。
- cross-frame pooling不被 `gate_selection`/`resolve_group` 支持（GL-I01 设计门明确禁止 self alias/cross-group 影响 frame identity）。
- 独立 direct call `fit_ground_plane_constrained`（无 wrapper）：
  - `fit_index=1214`、`min_inliers=100` — **sampled ≈ 80 < 100**，reason=**`ground_points_insufficient`**。
- 数学证明已收性：本真实数据 fit 在**现协议+单 frame_group**下**数学上不可行**，不构成实现 bug。

### 1.3 不停轮的所有 up_axis 与区域探索（本独立复审）

- 错误假设 1：`up_axis=[0,0,-1]`（"Z 朝下地板"）— 协议数学翻转 conflict，RANSAC 角度 / offset 双向 mismatch。
- 错误假设 2：`up_axis=[sin26°,0,cos26°]`（本单 final 选择，用户确认）— 角度对 (2.7°)，**但** GL-00 R4 协议 gate `min_inliers=100` 就截住，**不是 angle fault**。
- 真实 fit deferred 原因：协议假设 **fit_index 远大于 100×0.2/fit_point 数**，而数据每帧仅 ~1214 且 `_balanced_sample` 抽样后只剩 ~80。

## 2. 路线3 决策的边界动作（用户选中项）

**用户已经明确选路线3**：真实 fit **NOT_RUN** 在 GL-I02 R1，本单 closed。不放进产品，只留 evidence。

- **不改** `src/human_fall_detection/core/ground.py`、`calibration.py`
- **不改** `src/human_fall_detection/scripts/calibrate_sensors.py`（含 adapted route）、`prepare_capture_input.py`
- **不改** 任何生产 config YAML
- **不改** GL-00 R4 冻结协议（`geometry_constrained.yaml` `min_inliers / min_fit_inlier_fraction / fit_point_cap`）
- **不变** 真实 163621 capture / `captures/remote/` SHA（meta `675c23de…`，bin `b81797f9…`，与 GL-I02 R1 复审结尾一致）

## 3. J01 真正走向（本独立复审层）

| 该条款 | 本独立复审结论 |
|---|---|
| `J01` 真实 163621 → candidate artifact | **NOT_RUN**（路线3 协议-场景冲突冻结，非代码 bug） |
| `J01` 合成 candidate 路径 | **PASS**（7-frame synthetic fixture adapted NPZ → candidate artifact valid，`status.ground=candidate`） |
| `J02` capture 只读 + 命名空间 | **PASS**（meta/bin SHA 与基线一致，唯一写点 wrapper 输出） |
| `J03` synthetic/real strict 分离 | **PASS**（`input.source=synthetic_fixture` / `capture_export`、独立命名空间） |
| `J04` draft 人工决断、不自动 fallback | **PASS**（T2/T6 加独立 N2/N4） |
| `J05` 仅调用 GL-I01 R1 public API、严格 reject | **PASS**（N1 legacy exit 2、N2 overlap exit 2、N3 fit-leak exit 2、N4 empty-fit exit 2） |
| `J06` 白名单、GL-I01 四文件 SHA 不变 | **PASS**（wrapper 唯一新生产 + tests/docs/returns） |

综合：GL-I02 R1 **协议层** 软件条项（J01-J06/N01-N07）全 PASS。**真实物理层** D01 NOT_RUN，真实 candidate 拟合先 deferred（不走 R2、现场协议 freeze 等）。

## 4. 下一步候选（按用户"每条完成都规划"，待用户点哪一项再下来工单）

| 候选 | 什么会动 | 意义 |
|---|---|---|
| GL-I03 "采集-合成混编真实 fit" | 仅证据与分析 | 单 frame_group 的物理存根实质：89 帧 0.002Hz × 89 帧 总 3.5s 製读采样限制。已存在一份 405k 点真实 capture，需要扩大历史时间窗到 ~5分钟，这样单 frame 仍 ~1200，但 `fit_indices` 可以基"**内容不重复**" proto 号跨 frame 组选；不动 ground / wrapper；只在 draft 原团人工手写 |
| GL-I03 "重新审 geometry_constrained.yaml" | GL-00 R5 协议评审（非本 wrapper） | 把 `min_inliers=100` 改为 ~30（真实 frame_group ~1200enough）或 opening cross-frame pooling ；**不是** GL-I02 该做；按计划 B/C 重替协议 |
| GL-04 DPR 浏览器验证 | GL04 R8+ | 与本单完全独立，浏览器真实 DPR 是另一主线阻塞 |
| GL-05 设备/部署 | 另工单 | 没授权 |
| **不派单，今天到此** | - | 合理 option |

## 5. 用户人工决断的填写要求（已满足）

- `up_axis = [0.438371, 0, 0.898794]`（用户确认，雷达 Z 倾斜朝地板 26°）— 已写进 `filled_real_draft.json`
- `sensor_height_interval_m = [1.2, 1.7]` — 已确认
- `fit_region` / 3 `validation_regions` 都用户审定 — `filled_real_draft.json` 中已 SOLID
- draft `status = pending_human_review` — 维持

## 6. 该状态被锁住的物理原因（用户应告知）

- 不可 AC 原因：1 frame ~1214 点 vs min_inliers=100. **增加采样时间可让单帧点数增多**（5分钟录制 → ~30k/帧）；那不是"绕道"而是**真实协议条件要求**。这意味着：**不要把"GL-I02 R1 还没 fited"理解为"代码错了"**。

## 7. 我下轮做啥

- 更新 GLI02_ACCEPTANCE.md 结果列（J01 synthetic PASS / real NOT_RUN，其五六 PASS，B01/D01/D02 分层不变）
- REVIEW_LOG 追加 GL-I02 R1 路线3 收口段
- returns/GL-I02.md 中本回传部分独立复审分析
- 不自动寄出 R2 （真实 fit）工单。
- 等用户回：今天到此、加路线 1（ cross-frame pooling +更 长record）、改 min_inliers、或先另单 GL-04 4 DPR。
