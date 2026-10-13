# 00 · R9 Reference Coverage Attribution 范围 / 非目标（SHADOW-ONLY）

- 日期：2026-10-06；writer：claude-k3（本会话）；ponytail full。
- **唯一目标**：把 E-1 站点残块中 **1035 / 1875（55.2%）NO_REF_VOXEL** 的丢失层从猜测变成可量化归因——
  是 **reference acquisition（raw 未观测）**、**reference builder admission（observed 但被 gate 拒）**，
  还是 **registration / spatial correspondence（5 cm 查询半径找不到）**。
- **冻结前置（不重开）**：
  1. E-1 verdict **E-NOT-CONFIRMED**（`2026-10-06_hrw03_r8_e1/08_final_attribution.md`）——
     mobility / temporal filter 假设已关闭，本轮**不重开 mobility hypothesis**；
  2. 上一轮 931/937「reference 可吸收率」只对应当时定义的 residual 点集，
     **不重新解释为「站点残块整体被 reference 污染」**；
  3. registration = R3.2/11_r33 存档 + r7 CHECK PASS 的固定 ICP 解（不重新估计，见 `01_frozen_inputs.md`）；
  4. B/C/D 层既有结论（registration residual 主因 / matcher 小收益 / connectivity NO_CHANGE）沿用，不重复实验。
- **非目标**：
  - 修改 production matcher / builder / `bg_ref_occ_min` / registration / ICP / voxel size / radius /
    online map / leveling / ROI / human detection 主链 —— 一律禁止；
  - commit / deploy；
  - 提出或实现任何 temporal mobility filter。
- **唯一变量** = 「NO_REF_VOXEL 的归因查询域」：从 E-1 的「universe（occ≥0.5）5 cm 最近邻」
  扩到「ref 全 candidate（5286）/ ref 全 k×3×3×3 raw cell / ref 逐帧 raw 点（多档半径）」，
  其余（输入、变换、窗口、voxel 语义、builder 语义）全部锁定。
- **实现语言**：Node 24（与 E-1 同一 loader/纯函数/matcher 语义层；Python 端无现成等价器）。
  `.py` 扩展名沿用 E-1 工单登记的 data contract，`node 03_ref_coverage_probe.py` 运行。
