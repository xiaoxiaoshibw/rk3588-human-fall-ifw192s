# 跌倒检测设计哲学（Design Philosophy）

> 波降噪 → 地面配平 → 去除地面 → 去除静态背景 → 前景候选 → 聚类 → 人体判定 → 跟踪 → 跌倒识别

**Git 仓库**

- **`origin`**: `git@github.com:xiaoxiaoshibw/rk3588-human-fall-ifw192s.git`（主开发，本方仓库）
- **`upstream`**: `https://github.com/innolidar/inno_driver_ws.git`（上游 InnoLiDAR 驱动工作区）

本文覆盖整个离线配平与地面链路——激光雷达点云几何处理 + 地面估计/分割 + 鲁棒参数估计方向。对应代码：`pc_apps/human_replay/`（GL-S02 后基线：`floor_detector.py` 72CE790F、`floor_sheet.py` 92D2ED10、`floor_roi.py` 1D144E57、`leveling.py` 3C3A8819、`validation.py` 469FFF14，SHA256 前 16 位）与 `src/human_fall_detection/core/`（HF-02~06）。

> **公式渲染说明**：GitHub 不渲染 `$$...$$` 也不渲染 `\boxed`，本文用 ` ```math ` fenced block（GitHub 原生支持）；Typora 如需 `boxed` 请开 MathJax。

## 设计原则

每条原则注明"来源教训（from）→ 落实机制（at）"。

**1. 地面拓扑连续性 ≠ 配平 ROI 可用性。**
from 223757：A 层 7.06m² 薄层连通性完好，但 25cm 只有 6 个洁净格——身份成立而可用性不成立。
at A/B 两层分离，身份失败与可用性失败给出不同的拒绝码（`floor_regions_invalid` / `INSUFFICIENT_CLEAN_ROI_SUPPORT`），不再用一条模糊错误掩盖。

**2. 地面身份判定与参数估计必须解耦。**
from v1 把"连通组件"同时承担两件事，碎片化地面被整体误判为"没有地面"（GL-S01 根因）。
at `floor_sheet`（身份）与 `freeze_domain/compare`（估计）是两个独立阶段，中间用冻结的四区作契约；估计侧永远消费算法 ROI，不反过来影响身份。

**3. 最低面 ≠ 地面，更平更连续 ≠ 更真实。**
from 桌面/台面同样水平且可能更低更平。
at 候选面必须同时过高度带 [0.8, 1.8]m、最低性（比次低面低 ≥5cm）、主导性（体素占比 ≥30%）等五门才称"地面"。已知限制：单块大台面冒充地面的反例未专门标定，阈值 provisional（见 GL-S01 回传）。

**4. 缺口必须有物理证据才能桥接。**
from 探针中小碎片垃圾点差点把"空缺口"判成"可桥接"。
at 走廊必须全观测、有接触点（≤5cm 贴面）、触面格比 ≥50%、宽度 ≤4 格，四者缺一不桥；合成 wall（可桥）/ void（不可桥）对例固化在测试里。

**5. 多帧稳定性优先于单帧偶然连通。**
from 单帧里扫过的桌腿/人脚会在 2D 栅格上制造"偶然连通"假象。
at 5cm 占据格须 ≥20 帧见到且 ≥30% 帧命中；sheet 时间稳定性 p05 ≥0.30；ROI 洁净格要求**每个 fit 帧**均有足量点。

**6. ROI 数量 ≠ 几何信息量，必须检查空间散布与条件数。**
from 四个相邻 ROI 在数值上等同于一个大 ROI，无法约束平面姿态。
at 四区契约：互不重叠、两两间距 ≥0.5m、独立数=4、条件数 ≥0.1；估计侧另有域退化门（λ₂/λ₃ ≥0.01、切向跨度 ≥0.1m）。

**7. A 层确认身份，B 层确认可用性，A 且 B 才允许锁定。**
from 要么全过要么全拒的粗放判定让操作者无法区分"场景问题"和"算法问题"。
at 只在双过时产出 kind（v1 / v2 / v3_fine_roi）与四区；任何单门失败都走显式拒绝码并保留诊断字段，不产生半成品 ROI。

**8. 系统不仅要给出结果，还必须能够解释为什么接受、为什么拒绝。**
from GL 系列迭代中每条拒绝都被追问过理由。
at `basis` 字段文字说明接受依据；`reject_reasons` 落报告（七种 GL_* 码）；candidate 携带 sheet/roi 全量审计字段；报告记 code_id（code_files SHA）、domain_id、源 binding SHA——任何结果可以回溯到当时的确切代码与数据。

**9. 可行性 ≠ 最优性：选择器必须看见候选项自身质量。**（v1.1 新增）
from GL-S02 选择器 bug：`_select_four` 只优化几何散布，从 34 个净盒里挑中了残差最高（0.023m）的盒，而穷举 C(34,4) 证明存在 max 单盒残差 0.0127 且三法全过的组合。质量门拒的是我选错的输入，不是数据。
at 可行集（全部既有门逐字通过）内按（max RMS 升 → mean RMS 升 → 条件数降 → 间距降）字典序选最优；质量只作排序，不作新增门。

**10. 诚实优先于可用：宁缺毋假。**
from GL-I01/I03 反复出现的"68.7% 支持率=pure floor"幻想、68°几乎垂直的面被当地面交出来。
at 拒绝比通过便宜：每个不通过必须落到 explicit reason code（见附表），unknown/unverified 永不填造成的数字；所有 artifact 的 `physical_verified / extrinsics_verified / runtime_eligible` 三 false；凡无 on-site 证据的状态一律 `unknown`，不用同名 frame_id 就编一个 identity 出来。

**11. 一块地面只由一份冻结证据回答，证据永远带出处。**
from GL-E01 不法统计把"V01 物理/多帧证据、V02 系统误差、V03 几何异常"三种性质不同的证据混在一个百分比里。
at `capture_input.load_adapted` 产出的帧组 manifest 绑定 meta/bin SHA + 逐帧确定性 group id；任何统计都来自这份冻结证据，不允许多文件拼接或 online 修正。

**12. 证明身份这一步必须污染-proof：禁止 fit/validation overlap。**
from GL-I03 `ground_frame_group_leakage` bug——同样的点既参与拟合又参与验证，验证无意义。
at `fit_ground_constrained` 把拟合与验证按 frame group 切分；`REASON_OVERLAP` / `REASON_GROUP_LEAKAGE` 是合法拒绝，而不是"差一点"。

**13. Sampling 必须 spatially balanced，多时多候选而不是单候选侥幸。**
from IFW192S 近密远疏，单纯均匀抽点会让远端几乎进不了拟合集；ICP 局部吸引力让单 candidate 收敛到邻近错误解。
at 20cm 格内每格 ≤4 点（fit 5000 / holdout 10000 cap）；多去重 candidate（≥3 合法 candidate 必须 distinct 10°法向 / 5cm offset），`ground_competition_unresolved` 防接近竞争面被静默吞掉。

**14. 高度/跌倒证据只能来自 verified ground，缺了它一律 uncalibrated。**
from `height_min_m = -0.3` 之类 gate 若作用在"未确认地面身份的点"上，会把桌子腿当躯干、把地面矮墩当人。
at `lidar_candidates.ground_plane_basis + ground_frame_eligible`；`coordinate.horizontal_basis` 只有"ground_tangent"或"raw_xy_uncalibrated"两种，从不在缺地面的帧上假装 z=0；`auto AABB/trusted ROI support_polygon` 一律 `None + no_trusted_support_outline_available`，不让自动 ROI 升级为支撑证明。

**15. 预测不是观测，时间必须 device source。**
from 早版 tracking 把预测位再喂给特征上界，预测链路自证跌倒。
at `association.py`/`tracking.py`：预测/遮挡标志永不进 feature history；`occlusion_timeout_s` / `lost_timeout_s` 是 elapsed 真实时间而不是帧数；`fall_state` 只用 device source seconds，哪怕 1.7Hz slab 是帧粒度。
at 预测只在 `position_predicted` 通道里，从不覆盖 `position_measured`。

**16. 想要 CONFIRMED 必须有 operator stance baseline，且初始躺姿不算。**
from 验真实场景里一位本来就躺着的人若持有别次站立基线，会触发"下到低位"误判。
at `fall_state.STATE_CONFIRMED` 先决条件 = 有效 baseline + 从同目标的 measured peak 量起的 measured descent + sustained low posture；`initially-lying with stored stance baseline` 固定只到 `low_posture_unclassified`，绝不确认。
at 默认 `mode_verified=false / allow_confirmed=false`，机器上能到的最高状态是 `suspected`。

**17. 链路间的更换一气呵成，不能半断：同一 clock epoch，缺了一段整段视为 invalid。**
from `bag_time、header stamp、receive 时钟`混用导致同源两帧 dt 错误，`descending_rate=+2.31 m/s` 一类伪证据。
at `timebase.ClockEpochResolver`：单一 source_stamp_s 或 receive_s 一条线；clock epoch 变化只触发一次 reset，不把"旧时间差"刷进 fall 证据； negative dt 走 lost，不走 0dt 关联。

**18. 消费端必须能跟不可知和平共处：未知值保留，null 比错值好。**
from GL-02/03 binding 错时常把 reference 坐标映射错了还继续报数。
at `build_snapshot` 在 binding 失败时把 `reference_*`、`coordinate.ground_derived_id` 等字段填 `None` 而不是报错；`_resolve_reference_transform` 有独立 reason；`_coordinate_ground_projection` 只信任 `validate_ground_derived` 的结果，否则不投影。

**19. 即使 PASS 也不自动晋级物理：software candidate，不做设备姿态宣告。**
from 十次软件 PASS 也无法代替一次现场测量。
at `derive_ground_calibration` 只产 CAD/几何参数版本（content hash），不claim物理；`nominal_leveling` 只根据声明 pitch/height 给刚性旋转而不是 ground fit；任何验收表 `device/物理/采集/部署` 一律 `NOT_RUN`，从未名义上跨过。

---

## 链路 A — 离线配平主链路（生产在用，GL-W01 工作台 & console exe）

```math
\text{名义姿态 } R_0
\rightarrow
\text{体素去偏 + 多平面 RANSAC 粗分割}
\rightarrow
\text{A 层·地面片身份确认}
\rightarrow
\text{B 层·洁净 ROI 四区选择（25cm→15cm 回退）}
\rightarrow
\text{冻结域 + 三帧独立留出}
\rightarrow
\text{同域 TLS / SVD / RANSAC 三法估计}
\rightarrow
\text{全点/逐区/留帧质量门}
\rightarrow
\text{三法一致性对照}
\rightarrow
\text{推荐 TLS + 全帧产物落盘}
```

### A 逐级展开（括号为代码出处与门值）

**A1. 名义姿态 R₀**（`leveling.run_job` → `rotation(pitch, roll)`）
用户给名义 pitch=26°/roll=0°，生成初始显示系；其 z 轴作为后续平面法向的**方向锚点**，消除法向符号歧义。→ 原则 8。

**A2. 平面发现（粗分割）**（`floor_sheet._discover_planes`）
源点按 10cm 体素取质心（只去传感器近密远稀的密度偏置，不动最终拟合）→ 最多 6 轮 RANSAC 剥平面：inlier 带 ±8cm、|n_z|≥0.94、offset∈[0.8,1.8]m → 取 **offset 最大者（最低面）** 为地面假设。→ 原则 3。

**A3. A 层·身份确认**（`floor_sheet._sheet_metrics`，v1 成功时直接跳过整条 A/B）
±3cm 薄层 → 5cm 多帧占据栅格（≥10 点/格、≥20 帧见到、≥30% 帧命中）→ 连通分量 → 有界接触桥接（缺口 ≤4 格、触面格比 ≥50%）→ 五门：最低性（≥5cm）、主导性（≥30%）、连通性（≥0.5m² 且覆盖 ≥50%）、缺口可解释、时间稳定（p05 ≥0.30）。→ 原则 1/3/4/5。

**A4. B 层·ROI 四区**（`floor_sheet._roi_metrics` / `floor_roi.fine_boxes + _select_four`）

- 25cm 洁净格：整格厚度 ≤0.18m、法向 ≥0.94、局部 RMS ≤2.5cm、贴面 0.08/0.18、**每个 fit 帧 ≥30 点**；一个高点整格作废，不裁剪点；
- 四区契约：互不重叠、两两间距 ≥0.5m、独立数=4、条件数 ≥0.1；
- **粒度回退（GL-S02）**：25cm 可行集为空时，在 A 层已确认的同一 sheet 上改 15cm 盒，纯度门逐字相同，每帧点数按面积折算到 ≥20（= 下游留帧每区下限）；可行集内按（max RMS 升, mean RMS 升, 条件降, 间距降）挑最优——RMS 只排序、不作新门；
- 失败语义三分：身份失败 → `floor_regions_invalid`；双粒度 ROI 不足 → `INSUFFICIENT_CLEAN_ROI_SUPPORT`；通过 → kind `lowest_floor_sheet_v3_fine_roi`（`full_height_preserved=true`、`uses_manual_reference=false`）。→ 原则 1/5/6/7/9。

**A5. 冻结域**（`leveling.freeze_domain`）
全部源行转 display 系打区号 1–4（重叠报错）；末尾三个 ordinal（(n−1)/3、2(n−1)/3、n−1）帧整体留出，**永不进估计器**；拟合域限 80~2,000,000 点、每区 ≥20 点；全高度源行保留、无残差裁剪、不抽稀（超限显式拒绝）。→ 原则 2/5。

**A6. 同域三法估计**（`leveling_quality.compare` → `leveling_estimators`）
TLS、SVD、RANSAC（种子 20261001、861 次迭代，raw 无 refinement）在**同一个冻结域**上各自解 (n, d)，方向由锚点矫正。→ 原则 2。

**A7. 质量门**（`leveling_quality.statistics`）

| 门 | 阈值 | 拒绝码 |
|---|---|---|
| 域退化 | λ₂/λ₃ ≥0.01、切向跨度 ≥0.1m | `GL_DEGENERATE_DOMAIN` |
| 姿态合理 | \|pitch\| ≤75°、\|roll\| ≤45°、offset >0 | `GL_IMPLAUSIBLE_POSE` |
| 全点质量 | RMS ≤3cm、P95 ≤5cm、support ≥80% | `GL_FULL_DOMAIN_QUALITY` |
| 逐区质量 | 同上，四区逐一 | `GL_REGION_QUALITY` |
| 留帧质量 | 三个留出帧 full+逐区同门 | `GL_HOLDOUT_QUALITY` |

→ 原则 5/6/8。留帧质量门是"用训练侧没见过的数据验证"，GL-C01 的 P95 超标就是这样暴露出来的。

**A8. 三法一致性**（`compare` 尾部 pairwise）
TLS↔SVD：法向差 ≤0.0001°、offset 差 ≤1e-6m（同为最小二乘应几乎重合）；RANSAC↔最小二乘：法向夹角 ≤2°、offset 差 ≤3cm。→ 原则 8。

**A9. 推荐与产物**（`leveling.export_dataset`）
三法全 valid 且一致性通过 → `recommended=tls`；每个 valid 方法导出 28B 全帧点云（**源行原样复制、只替换 XYZ**，帧序/行号/opaque 字节不动）+ `transform.json`（`scope: offline_display_only`，`physical/extrinsics/runtime` 三 false）+ `meta.json` + `dataset.zip`；任何一步 FAIL → 该法无产物，报告保留拒绝原因。→ 原则 7/8。

---

## 链路 B — HF-03 单帧地面估计（机头单帧 RANSAC，设备感知输入）

```math
\text{(N,3) 源点}
\rightarrow
\text{几何范围过滤（[1.0,30.0]m）＋封顶抽稀（<=100k）}
\rightarrow
\text{多起点多候选 RANSAC（150 迭代，inlier ≥100，占比 ≥20%）}
\rightarrow
\text{候选一致性：best vs alt 差 <10° 或 <5cm 才消歧}
\rightarrow
\text{薄 SVD 精化（inlier 协方差本征向量）}
\rightarrow
\text{留出帧验证（30%，≥20 点，支持率 ≥50%，RMS ≤0.12m）}
\rightarrow
\text{状态三意（valid / orientation_unverified / invalid）}
```

### B 逐级展开（`core/ground.py` 的 `fit_ground_plane` 路径，HF-03 legacy）

**B1. 输入与范围**（`validate_ground_plane` / `resolve_settings`）
有限点 (N,3) 严格校验，range ∈ [1.0, 30.0] m、封顶 100k。→ 原则 11。

**B2. 多点采样 + 多候选**（`fit_ground_plane`）
同种子（`seed=20261001`）多假设 RANSAC，`min_inliers=100`、`min_inlier_fraction=0.2`；min_inlier_fraction 防"少数点跑赢"。→ 原则 12/13。

**B3. candidate competition**（内置去重）
回收 ≤3 distinct candidate（法向差 ≥10° 或 offset 差 ≥5cm），若差异在窗口内则视为 unresolved competition；`_COMPETITION_CANDIDATE_CAP=8` 是为了让"调低 max_candidates 不能掩盖近邻 competition"。→ 原则 12/13。

**B4. thin SVD refine**
inlier 协方差做 `full_matrices=False` SVD，只保留最小奇异向量。→ 原则 2（估计/身份分离）。

**B5. holdout 验证**
30% 留出，`min_holdout_points=20`，必须 `min_holdout_support=0.5` 且 `max_holdout_rms_m=0.12`。`ground_holdout_insufficient`（支撑不足）与 `ground_holdout_failed`（支撑+残差失败）分开。→ 原则 5/6。

**B6. 状态语义**
- `valid`：可用于 HF-05 关联/特征；
- `orientation_unverified`：找到水平主面但其朝向不可证与地面一致，例如几乎垂直的墙面被当成地面（`ground_orientation_ambiguous`）；
- `invalid`（或各种 reason code）一律 `None` 返回，从不拿"将就的"往前走。

→ 原则 3/7/17。

---

## 链路 C — GL-01 约束地面（离线研究 branch：AGL-A~I 前置；当前 NOT_RUN 到设备）

```math
\text{(N,3) 源点 + frame-group manifest}
\rightarrow
\text{显式 height prior（sensor 高 ∈ [0.8,1.8]m）+ up-axis prior}
\rightarrow
\text{空间均衡采样（20cm 格≤4点）＋去重多候选 RANSAC}
\rightarrow
\text{样本三点约束（间隔 ≥5cm、面积 ≥0.0025m²、法向夹角 ≤15°）}
\rightarrow
\text{SVD refine}
\rightarrow
\text{GC 区域残差（≥3 独立区，≤0.03m RMS, ≤0.05m P95, ≥80% support）}
\rightarrow
\text{状态有效 + reason code 可拒绝}
```

### C 逐级展开（`core/ground.py` 的 `fit_ground_constrained` 路径）

**C1. 输入必须带 frame-group**：点要么来自 `capture_input.load_adapted`，要么外部 caller 显式给出同长度 `groups` 向量；`ground_frame_group_leakage` 永远拒绝共享 group 的 fit/validation。→ 原则 11。

**C2. 显式 priors**：`sensor_height ∈ [0.8,1.8]m`、`up_axis` 明示（默认 z+），up 与 height 两个先验都不能在 caller 处放宽；`max_angle_rad=0.2618`（=15°）限制世界 up 与拟合 normal 夹角。→ 原则 3。

**C3. 空间均衡采样**：`spatial_cell_m=0.20`、`max_points_per_cell=4`、`fit_point_cap=5000` / `holdout_point_cap=10000`；IFW192S 的角度密度偏置在这一步直接抵掉。→ 原则 13。

**C4. 多样本三点约束**：RANSAC 迭代 `ransac_iterations=861`、硬帽 2000；每个样本要求 `min_sample_separation_m=0.05m`、`min_sample_triangle_area_m2=0.0025m²`，防三点挤在一条线；样本法向必须与当前 normal 夹角 ≤15°。→ 原则 12/13。

**C5. 去重多候选**：`max_candidates=3`，差异为法向 ≥10° 或 offset ≥5cm；若两个候选同时过窗口，结果为 `ground_competition_unresolved`；保留的 competition 证据帽为 8，防止缩 `max_candidates` 掩盖近邻面。→ 原则 12/13。

**C6. 简 SVD refine**：同 B4，但结果由 `GC region gate` 判定，不是直接接受。

**C7. ground_consistency（GC）区验**：四维指标—— `untruncated_rms_max_m=0.03m`、`abs_residual_p95_max_m=0.05m`、`support_fraction_min=0.8`、`independent_regions_min=3 / points_per_region_min=20`；同时 `normal_change_max_deg=2°` 与 `offset_change_max_m=0.03m` 限制 refine 前后漂移。全部门不能放宽（`_MIN_INLIERS_FLOOR=100`、`_POINTS_PER_REGION_FLOOR=20`、`_INDEPENDENT_REGIONS_FLOOR=3`、`_MAX_CANDIDATES_CEIL=3`、 `_HARD_CAP_CEIL=2000`、eigenvalue 比 ∈ (0,1]）——降低这些不是合法过法。→ 原则 5/6/8/19。

**当前状态**：`fit_ground_constrained` 只在离线研究 / GL-I01~I06 evidence 里自验，WORKFLOW 明确"AGL-A~I NOT_RUN、机头当前 TLS/SVD PASS、RANSAC 与一致性 FAIL"——这条链路尚未替代 A。

---

## 链路 D — HF-05 关联 + HF-06 特征 / 跌倒状态（单目标锁 → 观测历史 → 状态机）

$$
\boxed{
\text{candidate 快照（lidar_candidates.build_snapshot）}
\rightarrow
\text{operator pick 一 track}
\rightarrow
\text{constant-velocity predict（单 clock, dt 在 device seconds）}
\rightarrow
\text{association 距离门 + 速度门 + 大小门 + 歧义显式}
\rightarrow
\text{measured/predicted/occluded 观测，预测不造特征}
\rightarrow
\text{bounded feature history（≥15 valid samples，稳定 3s）}
\rightarrow
\text{stance baseline（可选）}
\rightarrow
\text{fall_state 7-state machine（verified 才允许 confirmed）}
\rightarrow
\text{event publish（无 duplicated fall event id）}
}
$$

### D 逐级展开（`core/lidar_candidates` + `association.py` + `tracking.py` + `features.py` + `fall_state.py` + `node_runtime.py`）

**D1. candidate snapshot**（`build_snapshot`）：见上文 28 步细节；`sufficient_points` 是其唯一 entry gate，semantic 永远 unknown，直到 operator 说哪个 candidate 是人 → `selection.py` 记 selection_version；**semantic human label 绝不 auto**。→ 原则 7。

**D2. target selection**（`TargetTracker.select`）：由 operator 或显式 test fixture（auto_select=True 明确标注 fixture-only）触发；lost/ambiguous 后**不自动 re-acquire**，必须再次 explicit pick 才能继续；selection_version++。→ 原则 7/16。

**D3. 时间轴**：`source_stamp_s`（device 时间）或 receive_s，只走一条线；任何负 dt 不是 0dt 而是 lost；`time_epoch` 是 in-process reset barrier，跨 epoch 的 baseline 不能复用。→ 原则 17。

**D4. association**（`association.py`）：
- 距离门 ≤0.8m；
- 速度门 ≤2.5 m/s；
- 尺寸门 ≤3.0 倍 ratio；
- ambiguity margin 0.2m，两个近 candidate 或两个 track 争一个 candidate 一律 `ambiguous`；`associate_tracks` 返回 explicit reason（`ambiguous` / `merge`），绝不静默分配到一边。
→ 原则 5/6/15。
- occluded_timeout 1.5s，lost_timeout 3.0s；`occluded/lost` 状态下预测照走，但**预测位不算 fall observation**。→ 原则 15。

**D5. features**（`features.py`）：ground-relative height quantiles、水平 extent、PCA verticality、近地时长、下降速率——全部基于 measured observation 序列；predicted/occluded 永不推进 history；**no anatomical centroid、no skeleton**。→ 原则 15。

**D6. stance baseline**（`baseline.py`）：必须 3s、≥15 samples、point_count ≥60、position spread ≤0.25m；初态 lying 或低于 0.8m 高 explicitly failed、不存假 baseline；operator intent 不能绕过质量门。baseline 绑定 session/track/epoch/selection/calibration，任何 mismatch 一律 not_applies。→ 原则 16。

**D7. fall state**（`fall_state.py`）7 state：`unknown / upright / descending / low_posture_unclassified / suspected / confirmed / recovering`；下降 evidence = measured drop from recent measured peak + measured descent rate； sustained low posture ≥3.0s（K05 值）；`confirmed` 必须 `(mode_verified=true and allow_confirmed=true)`，默认只到 `suspected`。event reset 原则：新 event 只有真正 recovery 或 context reset 后才算新 episode，重复 publish fall event 是 bug 而非"继续报警"。→ 原则 8/10/16。

**D8. publish**（`node_runtime.py`）：`human_fall_node.py` 按 bounded latest-frame queue + 单 worker，处理纯 NumPy；fall event append 到 local JSONL log，输出只读——不发布控制命令。已知限制在 docstring 明示："active lying and a fall may be geometrically indistinguishable，slow slides may be missed；不隐藏"。→ 原则 8/10。

**其它跨链**：`sensor_quality.py` / `nominal_leveling.py` / `joint_leveling.py` / `capture_input.py` / `ground_region_review.py` / `ground_evidence.py` —— 全部"只读、验证、出 reason、永不写/不拟合"，是 A/B/C 链路的取证旁路；任一环节 `physical_verified / extrinsics_verified / runtime_eligible` 三 false。→ 原则 19。

---

## 不变量与 Insight

`✶ Insight ─────────────────────────────────────`
- 跨链路不变量：
  1) **身份/可用性/估计** 三分（原则 1/2/7/12），同时适用于 A（A 层 vs B 层 vs three methods）、B（主轴身份 vs候选确认 vs SVD refine vs holdout）、C（prior 身份 vs candidate vs GC gate）。
  2) **全程无残差淘汰**（原则 5/15/16）：ROI 内全高度点、fit 域全部源行都进估计器；holdout / GC 才能真实暴露。
  3) **reason code 优先**：任何不通过必须落在明确 code（`floor_regions_invalid` / `INSUFFICIENT_CLEAN_ROI_SUPPORT` / `GL_*` / `ground_*` / `ambiguous` / `merge` / `low_posture_unclassified` / `ground_competition_unresolved`），不写"貌似接近"的自由文本。
  4) **默认值即不可下调的协议**（`_MIN_INLIERS_FLOOR`、`_POINTS_PER_REGION_FLOOR`、confirmed 默认关、各个 `_HARD_CAP_CEIL`）；把它们当"可调参"来通过验收会被 resolve_settings 显式拒绝。
- 各链路当前商用状态：A 生产在用（GL-W01 + console exe），B/C 与 HF-06 的 confirmed 在 WORKFLOW.md 里明示 NOT_RUN/FAIL——文档各节已如实标注；验证表 `device/物理/采集/部署` 永远 `NOT_RUN`，直到显式授权。

`─────────────────────────────────────────────────`

## 附录：拒绝码速查（节选自源码）

| 链路 | code | 意义 |
|---|---|---|
| A | `floor_not_found` / `floor_regions_invalid` | 身份失败 |
| A | `INSUFFICIENT_CLEAN_ROI_SUPPORT` | A 过 B 不够 |
| A | `GL_DEGENERATE_DOMAIN` / `GL_IMPLAUSIBLE_POSE` / `GL_FULL_DOMAIN_QUALITY` / `GL_REGION_QUALITY` / `GL_HOLDOUT_QUALITY` / `GL_NUMERICAL_INVALID` | 三法报告 |
| B | `ground_points_insufficient` / `ground_not_found` / `ground_orientation_ambiguous` / `ground_above_sensor` / `ground_holdout_insufficient` / `ground_holdout_failed` | fit_ground_plane |
| C | `ground_degenerate` / `ground_validation_insufficient` / `ground_validation_failed` / `ground_fit_validation_overlap` / `ground_frame_group_leakage` / `ground_metadata_invalid` / `ground_competition_unresolved` | fit_ground_constrained |
| D | `candidates: quality.reasons=["ground_unavailable"]` | 缺地面时 |
| D | `association: ambiguous / merge` | 双候选或双 track 争一个 |
| D | `fall: low_posture_unclassified` | 初次 lying 不视为 fall |

| 原则 | 直接来源教训 | 证据位置 |
|---|---|---|
| 1 / 2 / 7 | 223757 被报"没有连续地面"（v1 概念耦合） | `evidence/2026-10-05_gl_floor_diag_r1/`、GLS01 回传 |
| 3 | 台面伪地面风险；大台面反例未标定（已知限制） | GLS01 回传"未闭合与限制" |
| 4 | 探针碎片点误触发 gap 门；桥接真实数据未触发过 | `floor_sheet_test` wall/void/卫星碎片用例 |
| 5 | 探针局部法向取错 eigh 列（最大向量当最小）→ 干净格几乎为空 | `test_clean_cell_normal_direction_regression` |
| 6 | 6 格两簇：间距 0.354m / 独立 0 / 条件 0.162 三类不足 | `evidence/.../gl_s01_r1/03_golden_v2.json` |
| 9 | 选择器只看散布不看候选残差，挑中最差盒 | `evidence/.../gl_s02_r1/10_r2_rootcause_probe.json`、GLS02 回传 |
| 8 | 每条拒绝都被要求给出可复现解释 | 各 returns/*.md 与 reject_reasons 字段 |
| 10 | GL-I03 反复出现的 68.7% support 现象 | `evidence/2026-10-03_gl_i03_r1/` |
| 11 | GL-E01 证据拼接、GL-C01 rolling-fit 污染 | `evidence/2026-10-04_mainline_evidence_r1/` |
| 12 | `ground_frame_group_leakage` 与 competition hidden 系列 | `core/ground.py` 测试 |
| 13 | IFW192S 近密远疏、RANSAC 单点对齐失败 | `IFW192S 光机几何事实` 记忆、B/C chain 代码 |
| 14 | `ground z=0` 在未配平场景中不可用 | `lidar_candidates` docstring |
| 15 | feature history 含 predicted 位置导致 descending=+2.31 m/s | HF-04/05 回归与 `association.py`/`tracking.py` docstring |
| 16 | verify human 姿态误判学 | `fall_state.py` docstring |
| 17 | 双时基/负 dt 事件 | `timebase.py` / `tracking.py` docstring |
| 18 | GL-03 G01/G03/G04/G05 binding 失败 | `core/lidar_candidates` docstring 与 GL-03 反例 |
| 19 | software PASS vs physical PASS 反复割裂 | `derive_ground_calibration` / `nominal_leveling` docstring、WORKFLOW 各验收表 |
