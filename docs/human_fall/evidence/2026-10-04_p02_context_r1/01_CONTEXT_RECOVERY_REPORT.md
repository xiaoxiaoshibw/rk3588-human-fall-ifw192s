# Development Resume Report / Context Recovery Report

2026-10-04（Asia/Shanghai）。本轮只恢复上下文、核对来源与落档；未修改生产源码、配置、旧证据、原始采集或正式外参。本报告不是独立代码验收，也不沿用旧工单的物理 BLOCKED 否定用户本次新的现场确认。

## 1. Repository State

- branch：`master`。
- HEAD：`73447d12ec1255643f6531e2d9e2287fb1481059`，标题“控制台修复 404 入口 + 回放页移除标注/剪辑死功能”。不同于 GL-C01 当时记录的 `cbd0be1...`。
- working tree：DIRTY，包含暂存、未暂存、删除、未跟踪及 ignored 数据；`src/human_fall_detection/` 整包仍未跟踪。已有差异不归因于本轮。
- `00_BASELINE.json`：4265 个文件条目，约 5.90 GB，包含 untracked/ignored，排除 `.git`；可读普通文件全部 SHA256，hash_errors=0，hash 期间检测到变更=0。Windows `src/CMakeLists.txt` 的 ReparsePoint 单独记录、不跟随、不替换。
- 全仓普通 `git diff --stat` 因 catkin ReparsePoint 报无法 hash；随后对显式排除 `src/CMakeLists.txt` 的 numstat 成功，暂存差异另存。首次取基线遇 Windows `os.readlink` ValueError，未产生文件；修正记录方式后才生成当前基线。
- 已读 AGENTS、WORKFLOW v2、DISPATCH、README、REVIEW_LOG、GL-B01/GL-N01/GL-C01 验收与回传/收口、GEOMETRY_CONTRACT、ground.py、ground_diagnostics.py、joint_leveling.py、nominal_leveling.py、相关 ROI 与来源记录。

**Repository evidence supersedes prompt context：软件进度按现有 B/N/C 收口记录恢复，不退回 GL-03 R3/403 历史状态；本次用户新确认的 A/B 物理结论另立来源，不被旧物理 pending 字段覆盖。**

| 工单 | 实际现行结果 | 限制 |
|---|---|---|
| GL-B01 v1 | R01–R06/S01/Q01–Q06 软件独审 PASS，SUBMITTED/STOPPED | P01 剩余源行/精度/SDK BLOCKED；D01 NOT_RUN |
| GL-N01 v1 | N01–N06/S01/Q01–Q06 软件独审 PASS，SUBMITTED/STOPPED | P01 独立物理 BLOCKED；D01 NOT_RUN；浏览器未完成 |
| GL-C01 v1 | C01–C07/Q01–Q05 作者自验 PASS；SUBMITTED/STOPPED | S01/Q06 独审 NOT_RUN，P01 BLOCKED，D01 NOT_RUN；真实共同 FIT-plane 质量 FAIL |

以上为已有记录的恢复，未把本轮读源码冒称指定 OpenCode 独立验收。当前源码是 ROS1/RK3588 fall 栈，ROS2 驱动构建分支并存；本次提示的 Orin/Ubuntu22.04/ROS2 是用户提供的目标背景，本轮未连接硬件验证，不自动迁移或改运行环境。

## 2. P02-A / P02-B Evidence

### P02-A correspondence

- Claim：physical ground ↔ #3 VAL ROI 的 A 空地面/B 放箱子/C 移除实验已 VERIFIED。
- Evidence：用户本次附件明确确认并给出 −2798 地板点、+712 箱顶点、窄区 median 257→154→257、A/C p5/p95 253/261、扰动约 (2.12,−0.01)m、#3 中心约 (1.97,−0.09)m、箱高与几何抬升均约 23cm。
- Alternative：这些数值仍未在本轮检索到带 session/ROI/source-row 的仓库分析产物；不能把元数据时间顺序当作 A/B/C 标签，不能由区域级对应直接宣布整个旧 rectangle 的每一行都是真地面。
- Verdict：**VERIFIED — user-attested field correspondence**；原始分析产物与 source-row 绑定尚未恢复。本轮未重新执行实验，也不要求重做实验。

### P02-B horizontal

- Claim：同一块物理地面不同方向的 iPhone 水平仪均显示 0°。
- Evidence：本次用户附件直接确认。
- Alternative：显示分辨率、设备系统偏差、地面局部代表性没有定量误差界；显示 0°不证明精确 0.000°。
- Verdict：**VERIFIED — consumer-level physical measurement / user-attested**。本轮未找到专项截图/照片或带测量位置绑定的旧记录；不因此撤销用户确认，不编造测量不确定度。

附件原文保留为 `02_USER_REQUEST.txt`。其冻结数学、M0/M1/M2 与 refit-RMS 不可观结论按本次明确指令保留；仓库未检索到命名 P0-01/P0-01R1 的独立 Jacobian/SVD 产物，故不声称本轮复现过它们。

## 3. Current Ground Data

三个新 session 本地存在、`innolidar`、canonical stride=28、元数据点数×stride 与实际 bin 长度完全一致，实际 meta/bin SHA 在 `03_SESSION_INVENTORY.json`。

| session | frames / ordinal | points | seq inclusive | A/B/C 身份 |
|---|---|---:|---|---|
| cap_20261004_202456 | 91 / 0–90 | 4470632 | 1765974–1766064 | UNKNOWN（仅推测 A） |
| cap_20261004_203135 | 113 / 0–112 | 5551289 | 1769819–1769931 | UNKNOWN（仅推测 B） |
| cap_20261004_203349 | 102 / 0–101 | 5011069 | 1771114–1771215 | UNKNOWN（仅推测 C） |

source_bag SHA 目前只是各 meta 中的声明，本轮未读远端原 bag，不标原 bag 链 independently verified。有效点/最终选点数尚未计算，因为 confirmed selection 规则尚未绑定；表中 points 是原始存储行数。

### #3 VAL 存在多版本，不能凭编号复用

- `.../2026-10-04_gl_e02_prompt_r1/pointcloud_v1/annotated_pointcloud_v7.meta.json` / `render_roi_v7.py`：旧 99 帧 source 的 #3 为 X[1.8,2.4]、Y[−0.5,0.5]。
- 同目录 `annotated_pointcloud_v11.meta.json` / `render_roi_v11.py`：旧 #3 改为显示系 X[1.9,2.4]、Y[−0.5,0.5]，R=Ry(+26°)、tz=1.34；图中先用 |Z|<.15 显示地板带。这是历史可视化规则，不能自动作为新 confirmed ground 的选择门。
- GL-C01 的 `pick_03` 是 FIT，不是 #3 VAL，X[1.918,2.415]、Y[−0.964,0.087]；只绑定 cap_20261002_233210 的 frame0、528 行。
- 本次用户报告 #3 VAL 中心约 (1.97,−0.09)m，不等于上述 rectangle 几何中心；也可能是选中点质心。本轮尚不能确定是哪一个版本，不能假定其相同。

已有 GL-C01 `frozen_joint_ground_selection` 不等于 `confirmed_ground_point_set`：它明确标注 `assumed_scene_ROI_not_exhaustive_human_labels`，来自旧 cap233210/99 帧，FIT=frame0/528，VAL=frame33/890、frame66/276、frame98/624。没有 A/C 标签，没有本次实验的行级绑定。

## 4. Existing Plane Tools

| 工具 | 实际行为 | 是否满足新 same-point-set 条件 |
|---|---|---|
| ground.py `fit_ground_plane` | range/cap、FIT/holdout split、RANSAC、inlier SVD 精修 | 不能直接用于三方法同域比较；内部重分域 |
| ground.py `fit_ground_plane_constrained` | 显式 fit_indices、prior/offset gate、balanced sampling、RANSAC、inlier covariance-eigh 精修、共同 FIT plane 验证 | 不能未经说明直接复用为纯 estimator 对照 |
| ground_diagnostics.py `pca_plane` | 对给定点的中心化 covariance-eigh，单位 n/d、指定 up 符号；即正交 TLS | 可在确认冻结域后复用数值原语 |
| joint_leveling.py `solve_joint_leveling` | 单 FIT TLS → Rx@Ry 闭式 pitch/roll/tz → 同 plane 验证 | 已有姿态解与验证；只接受旧 schema，资格始终 false |
| tmp_gl_diag/plane_vs_validation.py | RANSAC 有 1.2≤d≤1.7 gate，inlier eigh 精修，放大 ROI，旧89帧 | 诊断历史，不是新 confirmed-set 对照 |

未找到以新 A/C confirmed rows 为统一输入的 RANSAC/TLS/SVD 对照产物。**TLS 与中心化 SVD 是同一正交最小二乘问题的两种数值实现，不能宣称三种独立物理证据。** 后续需要同时保留共同输入 SHA/源行、RANSAC 实际支持与最终拟合域、所有方法对全冻结域的 RMS/P95/MAD，禁止悄悄各自改选择域。

坐标契约已核：列向量 source→ground 的 `p_G=R p_S+t`；现有联合解 R=Rx(roll)@Ry(pitch)、yaw=0、tx=ty=0，R 第三行为 n_S，pitch=atan2(−nx,nz)、roll=asin(ny)、tz=d_S。须检查 Rn≈[0,0,1]、proper rotation 与变换后 z=n·p+d；不使用 d/nz 或 refit-RMS 外参目标。

## 5. Historical 1.315 vs 1.594 Discrepancy

- VERIFIED：`2026-10-01_gl00_r4/21_support_summary.json` 中 d=1.3156328201293945m，pool162337、fit_zone16952、spatial_holdout9806、export8000 capped，明确不是独立场地验证。
- VERIFIED：实际 RANSAC/旧诊断包含 sampling、inlier 选择、offset prior，而全域 TLS/SVD 数值原语使用全部给定行；不同域可以解释结果分歧。
- HIGH-CONFIDENCE INFERENCE：历史分歧首先属于 point-domain / plane-association / extraction inconsistency，不能当作同一个 ground 的 estimator 误差 27cm。
- UNKNOWN：没有恢复到“d=1.594m”的精确 SVD 运行、输入行 SHA、normalization、权重与筛选配置。旧 `14_current_planes.json` 中匹配的 1.5941529 是某 plane 的 **AABB y_max**，不是该 SVD plane offset，不能拿它作佐证。
- Verdict：根因正式闭合等待真正 SAME-POINT-SET 对照；当前不宣称 estimator implementation 已坏或已经排除 bug。

GL-C01 的 26.3143101922° / −0.6120612045° / 1.3231366999m 是旧单 FIT 候选。共同 FIT plane 对 VAL 的 P95=.050762/.057539/.037627m，前两区 FAIL 保留；这既不推翻新的区域物理 correspondence，也不能代替新 A/C estimator consensus。

## 6. Current Blocker（唯一主要项）

**P02-C 的“已确认物理区域 → 明确 A/C session 与精确 ROI/source rows”的来源绑定缺口。**

| 本次阶段 | 本轮结果 | 原因 |
|---|---|---|
| P02-A | VERIFIED（用户现场确认） | 原始量化分析文件待绑定，未撤销结论 |
| P02-B | VERIFIED（消费级用户现场测量） | 无精确倾角/仪器误差承诺 |
| P02-C | BLOCKED | 未能无歧义选择并冻结 confirmed A/C rows |
| P02-D | NOT_RUN | 必须依赖 C，同域 RANSAC/TLS/SVD 尚未执行 |
| P02-E | NOT_RUN | C/D 未闭合，不输出新物理外参候选 |
| P1-01 | NO | 唯一最小缺口首先是 C 的来源绑定 |

这里 P02 阶段 ID 来自用户本次任务分解，并非擅自替换 GL-C01 唯一验收表；旧工单软件结果不追改。设备动作均 `NOT_RUN — requires physical field operation`，本轮未连接、采集、部署或修改设备。

## 7. Immediate Next Action（一个）

**补齐并冻结 A/C 与 #3 VAL 的 source selection manifest。** 已通过文本问题询问三个新 session 是否依次 A/B/C，以及实际 A/B/C 分析文件和 #3 VAL ROI 的保存位置。缺失的是数据定位，不是重复申请采集/部署授权。

绑定到位后在新证据目录冻结 frame 范围、ROI坐标系/参数、边界排除、finite/nonzero、非地面结构规则、A/C来源与点数/源行/输入SHA；排除 B。选择规则先于 estimator，不按待估 n/d 残差裁剪。然后同域比较、逐帧 spread 与前向变换验证；消费级水平误差独立陈述，不无证据 RSS、不把系统 unknown offset 高斯化。当前不启用正式 extrinsic 或 GL03/04/05 后续接入。

本轮无需生产代码 Change Proposal：尚未到必须改源码的步骤，没有新算法/优化器/采样变体实现。后续确需代码时先提交具体最小 Change Proposal，遵守单 writer 与 ponytail。
