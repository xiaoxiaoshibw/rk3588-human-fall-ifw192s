# 离线配平算法全流程（auto 模式）

2026-10-05 定稿。对应代码：`pc_apps/human_replay/`（GL-S02 后基线：`floor_detector.py` 72CE790F、`floor_sheet.py` 92D2ED10、`floor_roi.py` 1D144E57、`leveling.py` 3C3A8819、`validation.py` 469FFF14，SHA256 前 16 位）。

## 主链路

\[
\boxed{
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
\text{全点 / 逐区 / 留帧质量门}
\rightarrow
\text{三法一致性对照}
\rightarrow
\text{推荐 TLS + 全帧产物落盘}
}
\]

## 逐级展开

### 1. 名义姿态 R₀
`leveling.run_job` → `rotation(pitch, roll)`。用户给名义 pitch=26°、roll=0°，生成初始显示系；其 z 轴作为平面法向的**方向锚点**，消除法向符号歧义。

### 2. 平面发现（粗分割）
`floor_sheet._discover_planes`。源点按 10cm 体素取质心（只去传感器近密远稀的密度偏置，不动最终拟合）→ 最多 6 轮 RANSAC 剥平面：inlier 带 ±8cm、|n_z| ≥0.94、offset ∈ [0.8, 1.8]m → 取 **offset 最大者（最低面）** 为地面假设。

### 3. A 层·地面片身份确认
`floor_sheet._sheet_metrics`（v1 成功时直接跳过整条 A/B）。±3cm 薄层 → 5cm 多帧占据栅格（≥10 点/格、≥20 帧见到、≥30% 帧命中）→ 连通分量 → 有界接触桥接（缺口 ≤4 格、触面格比 ≥50%、走廊全观测）→ 五门：最低性（比次低面低 ≥5cm）、主导性（体素占比 ≥30%）、连通性（有效面积 ≥0.5m² 且覆盖 ≥50%）、缺口可解释、时间稳定（p05 ≥0.30）。

### 4. B 层·洁净 ROI 四区
`floor_sheet._roi_metrics` / `floor_roi.fine_boxes + _select_four`。

- 25cm 洁净格：整格厚度 ≤0.18m、局部法向 ≥0.94、局部 RMS ≤2.5cm、贴面 0.08/0.18、**每个 fit 帧 ≥30 点**；一个高点整格作废，不裁剪点。
- 四区契约：互不重叠、两两间距 ≥0.5m、独立数=4、条件数 ≥0.1。
- **粒度回退（GL-S02）**：25cm 可行集为空时，在 A 层已确认的同一 sheet 上改 15cm 盒；纯度门逐字相同，仅每帧点数按面积折算到 ≥20（即下游留帧每区下限）。可行集内按（max RMS 升 → mean RMS 升 → 条件降 → 间距降）字典序选最优；RMS 只作排序，不作新门。
- 失败语义三分：身份失败 → `floor_regions_invalid`；双粒度 ROI 不足 → `INSUFFICIENT_CLEAN_ROI_SUPPORT`；通过 → kind `lowest_floor_sheet_v3_fine_roi`（`full_height_preserved=true`、`uses_manual_reference=false`）。

### 5. 冻结域与留出帧
`leveling.freeze_domain`。全部源行按 R₀ 转 display 系打区号 1–4（重叠报错）；末尾三个 ordinal（(n−1)/3、2(n−1)/3、n−1）帧整体留出作独立验证帧，**永不进估计器**；拟合域限 80~2,000,000 点、每区 ≥20 点；全高度源行保留、无残差裁剪、不抽稀（超限显式拒绝）。

### 6. 同域三法估计
`leveling_quality.compare` → `leveling_estimators`。TLS、SVD、RANSAC（种子 20261001、861 次迭代，raw 无 refinement）在**同一个冻结域**上各自解 (n, d)，方向由锚点矫正。

### 7. 质量门
`leveling_quality.statistics`：

| 门 | 阈值 | 拒绝码 |
|---|---|---|
| 域退化 | λ₂/λ₃ ≥0.01、切向跨度 ≥0.1m | `GL_DEGENERATE_DOMAIN` |
| 姿态合理 | |pitch| ≤75°、|roll| ≤45°、offset >0 | `GL_IMPLAUSIBLE_POSE` |
| 全点质量 | RMS ≤3cm、P95 ≤5cm、support ≥80% | `GL_FULL_DOMAIN_QUALITY` |
| 逐区质量 | 同上四区逐一 | `GL_REGION_QUALITY` |
| 留帧质量 | 三个留出帧 full+逐区同门 | `GL_HOLDOUT_QUALITY` |

### 8. 三法一致性
`compare` 尾部 pairwise：TLS↔SVD 法向差 ≤0.0001°、offset 差 ≤1e-6m；RANSAC↔最小二乘法向夹角 ≤2°、offset 差 ≤3cm。

### 9. 推荐与产物
`leveling.export_dataset`。三法全 valid 且一致性通过 → `recommended=tls`；每个 valid 方法导出 28B 全帧点云（**源行原样复制，只替换 XYZ**，帧序/行号/opaque 字节不动）+ `transform.json`（`scope: offline_display_only`，`physical_verified/extrinsics_verified/runtime_eligible` 三 false）+ `meta.json` + `dataset.zip`；任何一步 FAIL → 该法无产物，报告保留拒绝原因。

## 关键不变量

- **身份 / 支撑 / 估计三概念解耦**：A 层证明"这就是地面"，B 层证明"能挑出四个可用 ROI"，估计层在同一冻结域三法互证。v1 把前两者混在"25cm 连通组件"一个概念里，是碎片化地面被冤枉的根因（GL-S01 解耦）；25cm 格粗导致干净格不足时回退 15cm（GL-S02）。
- **全程无残差淘汰**：ROI 内全高度点、拟合域全部源行都进估计器；质量靠留出帧验证，不靠把难点丢掉。holdout FAIL 会真实暴露（如 GL-C01 的留帧 P95）。
- **只读离线**：产物显式标 `offline_display_only`，不进运行时、不作物理标定、不碰采集与部署。
