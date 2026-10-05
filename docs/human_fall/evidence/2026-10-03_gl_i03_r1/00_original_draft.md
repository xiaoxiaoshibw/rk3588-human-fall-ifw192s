# GL-I03 R1 工单 / 2026-10-03（路线3 之后的真实 fit 突破）

派工者：Claude Code（CLAUDE_STANDBY 顶替 Codex）。生产写者：唯一 OpenCode `opencode-go/deepseek-v4.1-flash`（default DB、无隔离库）。本工单 GL-I02 R1 路线3 收口之后的**主线唯一派工单**，前置 GL-I01 R1 PASS、GL-I02 R1 路线3 PASS/分层。整单**未 ACCEPTED**。

## 单口头号

**GL-I03**：通过**协议层重审**（Geometry config R5）让现场真实 163621 适配能与 GL-00 R4 冻结协议兼容，**不改 ground.py / calibration.py / capture_input.py / calibrate_sensors.py / prepare_capture_input.py / driver / webui / 生产 config**、**不重采集**、**不跨采集**。

## 背景与事实化动机

由 GL-I02 R1 路线3 收口证据 `evidence/2026-10-03_gl_i02_r1/codex_review_01/13_route3_closeout.md`：

- 现有 163621 capture 有 **89 frame_groups × ~1214 点/帧 ≈ 437 万点**
- draft 圈地 X ∈ [2.0, 3.0] Y ∈ [-1.0, 0.0] **已含 107,747 个 pooled index**（89 帧跨组）
- 但 `_balanced_sample(cell_m=0.2, max_pts_per_cell=4)` **把 10.7 万点压缩到只有 80 点**，低于 `min_inliers=100`
- 真实因：26° 下倾安装 + 1 m × 1 m fit bounds + 0.2m cell + 4pts/cell **该 cell 表结构没有足够高度 cell count 容下地板**
- **不是** `max_angle_rad` 的 task（正确 up_axis 26.28° 后**角度已合格**）；**不是** wrapper bug；**不是** GL-I01 GATE；**不是** GL-I02 wrapper 的 line

**核实数字**（同一轮独立评估）：

| cell_m | max_pts_per_cell | sampled | 满 RANSAC |
|---|---|---|---|
| **0.20 / 4 (protocol)** | 80 | <100 ✗ |
| **0.10 / 8** | 637 | ≥100 ✓ |
| **0.05 / 4** | 1,196 | ≥100 ✓ |
| **0.05 / 8** | **2,382** | **≥476 (0.2 f) ✓ 建议** |
| 0.02 / 8 | 4,399 | ≥880 ✓ |
| 0.01 / 8 | 4,905 | ≥981 ✓ |

选择 **cell_m=0.05 / max_pts_per_cell=8**（既满足 min_inliers 栅架构又能 densify 多高度层）。

## 工单范围（严格）

### 允许范围（白名单）

| 文件 | 允许 | 内容 |
|---|---|---|
| `src/human_fall_detection/config/geometry_constrained.yaml` **（新增为 R1 试验副本）** | 仅限新增一个本单**独立 config path** `config/geometry_constrained_gli03_r1.yaml`，不改原冻结 `geometry_constrained.yaml` | 用 `resolve_constrained_settings` 接受 parameters，slider `spatial_cell_m=0.05`、`max_points_per_cell=8`；**不动** `min_inliers` `min_fit_inlier_fraction` `max_angle_rad` `points_per_region_min` `independent_regions_min` 等协议冻结参数 |
| `src/human_fall_detection/scripts/evaluate_gli02_candidate.py` | 追加 `--constrained-config` 可选参数（R1 candidate 不接 R1 加 default,**只**在显式指定时读） | 仅加拉 line 与 `_load_constrained_settings(path)` helper；**复用 `load_config`/`resolve_constrained_settings`，不改 ground API** |
| `src/human_fall_detection/tests/test_gli03_candidate_override.py` | 新增测试文件 | 评定 R1 synthetic fixture 仍然所有 PASS 、默认 0.2/4 不被 accdent ENTLY trigger，默认不加 override 既采样注定 80 点 / `ground_points_insufficient` |
| `docs/human_fall/GLI03_*` | docs/工单 | 实施记录与协议说明 |
| `docs/human_fall/returns/GL-I03.md` | 追加回传统 | 同 RETURN_TEMPLATE |
| `docs/human_fall/evidence/2026-10-03_gl_i03_r1/*` | 证据 | 本单 evidence |

### 严格 prohibition

- **不改** `ground.py` / `calibration.py`（GL-00 R4 协议 mathematical code）
- **不改** 原 `geometry_constrained.yaml`（冻结协议；新增 concurrent config only）
- **不改** `capture_input.py` / `prepare_capture_input.py` / GL-I01 / GL-I02 文件代码
- **不改** driver / webui / 正式页 / `captures/remote/` / `pc_apps/` / `human_capture/` / `sidequests/` / `human_replay/`
- **不改** ground 数学 / provider / model / DB / git 状态
- **不**重新capture、不新 collection、不使 wrapper 走 legacy path、不手 empty slipped draft
- **vel `geometry_constrained.yaml` 冻剂**（正如现行协议明确不允许改变 gate、不是 REGRESSION）

### 行为要求

1. wrapper 默认不走 override；用户传 `--constrained-config` path 才**显式**接受 settings override
2. 文件作为 **`config/geometry_constrained_gli03_r1.yaml`**独立的新 protocol 变体（可逆 revert 即删除）
3. synthetic fixture 与 real capture 严格分开；R1 fit 根本不做真实 fit——只声明协议问题与 synthetic 可行性
4. 重新量证 不久足，**禁止**的档案 修改 protocol 约束违规路径

## 统一验收表 GL-I03 v1

| ID | 要求 | 预期 | 结果 |
|---|---|---|---|
| K01 | `evaluate_gli02_candidate.py` 追加 `--constrained-config` 可选参数，**默认 not set**则使用冻结协议；设置时读 `geomtry_constrained_gli03_r1.yaml` | 默认行为全等价 GL-I02 R1 | NOT_RUN |
| K02 | `config/geometry_constrained_gli03_r1.yaml` 新增独立 config（可复制 baseline `geometry_constrained.yaml` 后仅改 `spatial_cell_m=0.05`、`max_points_per_cell=8`） | 文件+内容可查，config YAML 语法 fire，SHA recorded | NOT_RUN |
| K03 | 非 override 运行时, 网上一切 GL-I02 R1 results 依然重复（synthetic fit 结果不 marked 清晰度， GL-I01 24 探针 / 62 / 402 全 PASS ） | 真 default 程序采样仅 80 / ground_points_insufficient | NOT_RUN |
| K04 | 用 override 运行真实 163621 draft → **应采样 ≥2382 点**，`ground.status` 可为 valid / orientation_unverified，artifact `status.ground=candidate` 打开手工候选 artifact；`physical_verified=false`、synthetic_fixture layer 分离保持 | 运行 exit 0、artifact candidate → evidence | NOT_RUN |
| K05 | override YAML 不改 `min_inliers`、`min_fit_inlier_fraction`、`max_angle_rad`、`validatio regions threshold_values` 等 GL-00 R4 冻结协议参数 | 文件 diff（冻结 GL-I02 R1 SHA与新 GL-I03 SHA 明确分开） | NOT_RUN |
| K06 | White-list 严格：`evaluate_gli02_candidate.py`、`tests/test_gli03_candidate_override.py`、`config/geometry_constrained_gli03_r1.yaml`、`docs/human_fall/GLI03_*`、`returns/GL-I03.md`、本单 evidence；GL-I01/GL-I02 production SHA 不变 | diff/SHA 对照 | NOT_RUN |
| B01 | 原袋 width/height/original_count | source 层 | BLOCKED（维持） |
| D01 | 真实物理、设备、板端、性能、GL05、部署、采集、网络 | 未始动、未授权 | NOT_RUN |
| D02 | GL04 真实 DPR / 正式页 | 不属本单 | NOT_RUN |

## N矩阵（预期 path ）

| 行 | 输入×消费者 | 关联 ID | 结果 |
|---|---|---|---|
| P01 | default run → synthetic adapted NPZ → 未改协议采样 80 → ground_points_insufficient ⟹ exit 2 | K03 | NOT_RUN |
| P02 | default run → synthetic adapted NPZ + default protocol 保持 GL-I02 R1 结果 PASS | K01/K03 | NOT_RUN |
| P03 | 加 `--constrained-config` + 独立 config → synthetic fit → sampled 2382+ → artifact valid | K04 | NOT_RUN |
| P04 | real 163621 + override → sampled 2382+ → fit candidate / orientation_unverified / wrong / ambiguous | K04 | NOT_RUN |
| P05 | override YAML 内容 audit vs 冻结 config | K05 | NOT_RUN |
| P06 | wrapper SHA 变动 + GL-I01/GL-I02 production SHA 不变 + White-list | K06 | NOT_RUN |

## 派工约束

- **两阶段**：00_diag 顶多停（列出范围/样度层/`_balanced_sample` 具体作用点/与 `_constrained_failure` 走势），设计门 Codex/Claude 裁决后实施
- **Ponytail**：实际读 SKILL.md（整条），最小新增；优先用既有默认提供的 `load_config`/`resolve_constrained_settings` helper
- **单 writer**；不 commit/push/reset/checkout/clean；不动 git / model / DB / global
- **Top restore** 需超时贴：本单 **NOT** 允许 生产协议变动 `geometry_constrained.yaml`；override 是 NEW 独立文件
- 超处白名单即 settle STOP

## 回传统 requirements

按 `RETURN_TEMPLATE.md`、`returns/GL-I03.md`：

- `synthetic offline + real 163621` 全部业主权威 evidence;真 fit 之余 `ground_points_insufficient`、`sampled_fit_count`、`min_inliers`、`min_fit_inlier_fraction`、 sweep cell_m/max_pts_per_cell 最小示
- 派工 SHA cmd+exit
- 定位 refine stage(晚判 / rotation 还是 cross-frame pooling 提前提供）

## 晚判 responsibility

1. **explicit wrap 加 `--constrained-config`**：默认改为 GL-I03 R1 设置，不怕默认 不改 / 不影响 GL-I02 R1 wrapper 性能
2. **legacy config 复用**：sbatch 旁路只用 `load_config` + `resolve_constrained_settings` 与 ground 的 blockage 与 `fit_ground_plane_constrained`
3. **GL-00 R4 protocol 不动**：`min_inliers`、`min_fit_inlier_fraction`、`max_angle_rad`、`points_per_region_min`、`independent_regions_min`、`untruncated_rms_max_m`、`abs_residual_p95_max_m`、`support_fraction_min`、`normal_change_max_deg`、`offset_change_max_m` 在本工单一律不动
4. **真实 fit 为实验性 candidate**：**不进** GL02 lifecycle，不写 production calibration storage，不 deployment

## 停止返工标志

- sampled_fit_count **未达** min_inliers（默认 0.2/4 仍未定 80 vs 100) 在不改协议下**不死 research** → 直接 R2（进一步评估 spatial tuning 范围）
- 进入 ground.py/calibration.py/新 telemetry 修改 → REWORK
- 随意下载 capture 他源数据 → REWORK

## 本单 de facto assumption

- 用户 / Codex 已批准 override protocol 作为 **变体协议** 走 不影响冻结协议
- approval `spatial_cell_m=0.05` `max_points_per_cell=8` 为 GL-I03 R1 limit

READY_FOR_IMPLEMENTATION（after diag → design gate）
