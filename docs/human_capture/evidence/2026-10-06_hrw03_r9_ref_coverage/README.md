# HR-W03 R9 · Reference Coverage Attribution（SHADOW-ONLY）

- 日期：2026-10-06；writer：claude-k3；ponytail full。
- 前置：E-1（`2026-10-06_hrw03_r8_e1`）= **E-NOT-CONFIRMED**，mobility hypothesis 已冻结关闭。
- 本阶段：**SHADOW-ONLY / READ-ONLY / ZERO PRODUCTION CHANGE**。不重开 mobility、不改任何 production。
- digest：`ef6e1c2c191c6e30…`（5/5 确定性 PASS）。

## 最终判定：**REGISTRATION/SPATIAL-CONFIRMED**

站点残块 1035 个 NO_REF_VOXEL 的丢失层 = **空间对应 / 体素量化层**（C2+C3=97.6%），
**不是** reference acquisition（C0=0）、**不是** builder admission（C1=2.4% 且全部 occ<0.45）。

→ **NO PRODUCTION CHANGE**；`bg_ref_occ_min` A/B **不值得**（降阈救回 0 点）；
下一步指向 matcher 空间容差 / 邻域查询（下一轮、另行立工单），非 builder 阈值、非 ICP 重估。

## 文件

| 文件 | 内容 |
|---|---|
| `00_scope.md` | 范围 / 非目标 / 冻结前置 / 唯一变量 |
| `01_frozen_inputs.md` | 冻结输入 / 变换 / builder 参数 / 窗口 / 唯一变量声明 |
| `02_attribution_design.md` | **PREREGISTERED**：attribution chain、builder 12 问、C0..C7 taxonomy、spatial 分档、verdict 规则、§14 答题清单 |
| `03_ref_coverage_probe.py` | probe（Node 24 实现；`.py` 为工单 data contract，`node 03_ref_coverage_probe.py`） |
| `04_raw_support_results.json` | 逐点 raw support + 类别 + digest + 输入/变换 SHA |
| `05_builder_attribution.json` | builder 归因汇总（point/unique-voxel/obs 三口径）+ C1 直方图 + 控制区 |
| `06_spatial_offset_analysis.json` | 5/10/15/20/30 cm cumulative NN（universe/refCandidate/refRaw × point/voxel 权重） |
| `07_controls.md` | 控制区 sanity：站点 vs WD01/WD02/STATION_ZONE 同一 failure mode |
| `08_determinism.md` | 确定性（5/5 digest）/ 守恒（point/voxel/obs）/ 复用等价门 |
| `09_final_attribution.md` | **最终归因**：判定、§14 十问逐项回答、禁令逐条核验 |
