# 离线配平算法全流程（auto 模式）
单独给 Typora 的版本。开启主题对 MathJax `boxed{}` 的支持（默认已支持），或先把 `\boxed` 换成 `\fbox`（详见文末备选）。

## 主链路
$$
\boxed{
\text{名义姿态 } R_0
\rightarrow
\text{体素去偏 + 多平面 RANSAC 粗分割}
\rightarrow
\text{A 层·地面片身份确认}
\rightarrow
\text{B 层·洁净 ROI 四区选择 (25cm\to15cm 回退)}
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
$$

## 逐级展开
**1. 名义姿态** `leveling.run_job` 调 `rotation(pitch, roll)`：用户给名义 26°/0°，生成初始 display 系；其 z 轴是后续平面法向的**方向锚点**。

**2. 平面发现** `floor_sheet._discover_planes`：10cm 体素只取质心去密度偏置 → RANSAC ≤6 轮剥平面（band ±8cm、|n_z|≥0.94、offset∈[0.8,1.8]m）→ 选 offset 最大（最低）者。

**3. A 层身份** `floor_sheet._sheet_metrics`：±3cm 薄层 → 5cm 占据栅格（≥10 点/格、≥20 帧、≥30% 命中）→ 连通分量 → 桥接（gap ≤4 格、触面格比 ≥50%）→ 五门：最低/主导（≥30%）/连通（≥0.5m²且≥50%覆盖）/gap/时间（p05≥0.30）。

**4. B 层 ROI** `floor_roi.fine_boxes + _select_four`：
- 纯度（厚度≤0.18m、法向≥0.94、RMS≤2.5cm/25cm 与 15cm 逐字、贴面 0.08/0.18）；
- 选四区：不重叠、间距≥0.5m、独立=4、条件数≥0.1；
- 25cm 失败且 A 层通过 → 同一 sheet 用 15cm（点数按面积折算 ≥20）；
- 可行集内按 `(max_rms, mean_rms, -condition, -separation)` 排序选最优，rms 仅排序非门。

**5. 冻结域** `leveling.freeze_domain`：display 系打区号、末尾三 ordinal 整帧留出（不进估计器）、80~2M 点/区 ≥20、全高度无抽稀。

**6. 三法估计** `compare`：同一冻结域上 TLS/SVD/RANSAC（种子 20261001、861 iter）各自出 (n,d)，锚点定向。

**7. 质量门** `statistics`：lambda2/lambda3≥0.01、|pitch|≤75°/|roll|≤45°、full+per-region+3 holdout 帧的 RMS≤3cm/P95≤5cm/support≥80%。

**8. 一致性** TLS↔SVD：Δn≤0.0001°、Δd≤1µm；RANSAC↔LS：Δn≤2°、Δd≤3cm。

**9. 产物** 三法 valid → `recommended=tls`；每法导出 28B 全帧点云（原行复制只换 XYZ）+ transform/meta/zip，标记 `offline_display_only` 与 `physical/extrinsics/runtime=false`。

---
**若你的 Typora 主题不支持 `boxed`**：把上面的 `\boxed{... \rightarrow ...}` 改成：

```latex
\fbox{\parbox{\linewidth}{\centering 名义姿态 R₀ → …… → 全帧产物落盘}}
```
或者干脆把 `\[ \boxed{ ... } \]` 整个换成普通卡片式表格，我同样可以生成。
