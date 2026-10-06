# W03-R3.2 Leveled Reference → Leveled Current 跨会话 Match Audit（只读）

- 日期：2026-10-06（Asia/Shanghai）
- writer：Claude（claude-k3，本会话）；ponytail（lite）已遵守：复用 R3.0/R3.1 loader 与生产 PL 函数；除了一个 Jacobi 伪逆小角度解（含探针 `_svd_probe.js` PASS）外零新数学。
- 性质：**只读审计，生产零改动**。未改 `human_pipe_lib.js` / `human_detect.*` / Tracker / leveling / console / web 板端；未接 reference 到 production；未采集、未部署、未 commit。
- 依据：[W03-R3 验收规范](../../W03_R3_ACCEPTANCE.md) §3 R3.2；[R3.0 审计](../2026-10-06_hrw03_r3/10_summary.md)；[R3.1 builder](../2026-10-06_hrw03_r4/04_summary.md)；用户 2026-10-06 评审（四层 + 决策树）。
- **修订记录（2026-10-06 用户评审后，OpenCode/DeepSeek v4.1 Flash 执行）**：用户判定 R3.2 PASS，但要求修正因果归因——(a) WD01 原始漏匹配的约 94% 可由刚体配准解释（0.854→0.991），alignment 已证明重要，不得写作「次要/影响有限」；(b) 全文残余 ~15% 含动态/无对应点，不能直接归因为 matcher geometry，须先限定 known-static correspondence set；(c) M3 的独立贡献由 R3.3 controlled AB（固定 reference/frame/registration，只换 center→AABB）定量；(d) ICP 的 roll/yaw 简并登记为 `registration solution non-unique / weakly observable`，不作为 blocker。§0/§4/§5/§6/§7/§8 已按此修订，测量数字全部未变。R3.3 证据见 [../2026-10-06_hrw03_r5/14_r33_summary.md](../2026-10-06_hrw03_r5/14_r33_summary.md)。

## 0. 一句话判定（2026-10-06 用户评审后修订）

**reference 本身已经能看到 WD01（coverage@0.12 = 0.86，无旋转）。** R3.0 的「bg_exact=0」是 **CURRENT 自己的 online map** 因 M1（监视对象遮挡）+ M2（≥2pts/frame 门）漏掉了 WD01；203349 reference 没有遮挡，WD01 完整出现在 reference 里。
**跨会话刚体残差 Δroll≈2.58° 已被证明是 material 的**：最佳 ICP 对齐把 WD01 f42 coverage 从 0.854 推到 **0.991**（漏匹配 14.6% → 0.9%，消掉约 **94%** 的原始漏匹配）；TLS-direct（2.582°）推到 0.929。alignment 不是次要修正。
**但全文残余 ~15%（0.75→0.85 之后）不能归因为 matcher geometry**：全文点集混有人体/遮挡/两会话间变化物/无对应点，必须先限定 **known-static correspondence set** 才能做归因。
**M3（半径 0.12 ≈ 体素半对角 0.1219）仍有独立几何依据**（WD01 d50=0.073 < 0.12 但 d95=0.169 的尾巴；A 层 exact 0.826 vs match 0.890 的构成），**但其独立贡献尚未证明**——由 R3.3 的 controlled AB（同 reference / 同 frame / 同 registration，只换 center→AABB）定量。

> 修订说明：本文件此前的结论（「alignment 影响有限 / 全文残余主因是 M3」）按用户 2026-10-06 评审修正为「alignment 已证明重要；M3 待 controlled AB 定量」。测量数字全部未变。

## 1. 输入与口径（每条证据都可独立验证）

| 项 | 值 |
|---|---|
| reference sid | `cap_20261004_203349`（102 帧空场） |
| reference TLS | job `c9712aca…`（pitch 26.993°、roll **-2.948°**、tz 1.317） |
| current sid | `cap_20261002_223757`（165 帧） |
| current TLS | job `6bc5aabf…`（pitch 26.467°、roll **-0.366°**、tz 1.323） |
| TLS 直接差 R_cur·R_ref^T | roll **+2.582°**、pitch -0.527°、yaw +0.003°（总角 2.635°） |
| 已知 Δroll 漂移 @ 3m | 0.1352 m（≈ 现行匹配半径 0.12 m） |
| 审计参考阈值 | `ref_occ_min = 0.5`（3707 体素入图；occ≥0.9：2956） |
| 匹配半径 | `bg_match_radius = 0.12 m`（**审计不改 matcher**） |
| 体素 | XY 0.15 m / Z 0.12 m（半对角 √(0.075²+0.075²+0.06²) ≈ **0.1219 m**） |
| 输入 SHA | 见 [07_r32_stats.json](07_r32_stats.json) `inputs` |
| 复现 | `node 06_r32_audit.js`（7.8 s） |

口径：与 console 同序——各自 TLS transform → apply_Rt → denoise →（reference: R3.1 builder / current: 在线 build_static_map）。

## 2. A 层：基础匹配（0.12 m 规则不变，按区域分组）

| 区域 | n | exact | nb | match | d50 | d95 | dmax |
|---|---:|---:|---:|---:|---:|---:|---:|
| **WD01**（窗口 c=(3.50,-0.76) half=0.50，跨全部 165 帧） | 17485 | 0.826 | 1.000 | 0.890 | 0.070 | 0.152 | 0.328 |
| NEAR（range 3–8 m） | 67865 | 0.589 | 0.951 | 0.644 | 0.091 | 0.216 | 0.401 |
| MID | 397457 | 0.462 | 0.921 | 0.837 | 0.047 | 0.149 | 0.415 |
| **FAR**（>5 m，含 WD02 类稀疏远场） | 37403 | 0.267 | 0.691 | **0.369** | **0.113** | 0.263 | 0.404 |
| ALL | 520210 | 0.476 | 0.911 | **0.780** | 0.057 | 0.181 | 0.415 |

**读法**：
- 全场（ALL）match 0.78，邻域命中 0.91，说明 reference **基本覆盖**了 current 静态面，只有 ~10% 点完全无对应区（多为 current 会话独有的人体/物体）。
- **WD01 match 0.89 不是 R3.0 名面的 0**——R3.0 的「bg_nb=0.351」是 CURRENT online map 的命中率，不是 reference。
- **FAR（range>5m）是唯一真差的组**：match 0.37、d50=0.113（已贴半径上限）、d95=0.263。这对应 R3.1 知道的事实：203349 的远场体素（occ<0.5 的 580 个）没入图； occ≥0.5 的远场体素点稀，d50 自然到大距离段。

## 3. B 层：距离误差空间分布（每桶 match / d50 / d95，诊断 angle vs translation）

### by_range
```
0-1 m:   match 0.992  d50 0.006   <- 传感器极近边（自我视图）
1-2 m:   match 0.863  d50 0.067
2-3 m:   match 0.797  d50 0.081
3-4 m:   match 0.739  d50 0.084
4-6 m:   match 0.560  d50 0.104
6-8 m:   match 0.161  d50 0.217   <- 剧烈恶化
8+ m:    match 0.535  d50 0.113   <- 多为粗 wall / 玻璃（异常回升是因为 203349 里 occ<0.5 的杂点已经入图）
```
**形态：d50 随 range 单调上升 → 角度残差特征**。
**但**：在 0-4 m 范围内（当前房间主工作区）match 仍 0.74–0.99，说明 2.58° Δroll 在「典型房间尺度」内的实际影响 < 0.12m 半径的容差——旋转残差是**远场**的主要问题，不是近场。

### by_x / by_y / by_z / by_azimuth
- 沿 **+y 方向**（y∈1–6）match 强烈衰减（0.10–0.66），与 2.58° roll 绕 x 轴旋转时 +y 位移最大的几何一致。
- **by_z**：z=1–1.5 段 match 0.91（其中 d50=0.006 与 0–1m range 段同型，是另一处自我视图）；z≥1.5 衰减到 0.66、0.60。
- **by_azimuth**：仅在 [-90°,0°] 扇区较好（0.85–0.96），[0°,90°] 显著差（0.63–0.93）——与 TLS 直接差的几乎纯 roll（yaw 仅 0.003°）一致，roll 残差呈现强 azimuth 各向异性。

**结论**：跨会话残差的几何形态 = **roll 主、translation 极小（ICP 估计 t≈0.03 m ≈ 1/4 体素）**。

## 4. C 层：ICP 跨会话刚体残差估计（只读）

- source = reference occ≥0.9 体素形心（2956 个）；target = current 在线 strong 体素形心（1480 个）
- 一致门 0.25 m、Jacobi 伪逆小角度解（探针 PASS，err=9.6e-7 rad）
- **48 迭代收敛，incRot < 0.002°，rms 收敛于 0.1102 m**

| 估计量 | 值 | 对照 |
|---|---|---|
| **roll** | **+1.748°** | TLS 直接差 +2.582°（同号，量稍小） |
| **pitch** | -0.282° | TLS -0.527°（同号，量半） |
| **yaw** | **-2.392°** | TLS 0.003°（**ICP 把 roll 部分"分解"到 yaw；小角度下 roll+yaw 在 XY 平面效应简并**） |
| t | (0.018, 0.031, 0.001) m | 极小（~1/5 体素） |
| 总角 | 2.976° | TLS 总角 2.635°（同量级、稍大） |

**真相还原**：ICP 找到一个数学上更优的局部解（roll+yaw 组合 ≈ 与 TLS 直接差等效但不同方向）；不能简单说「ICP 错了」，因为它在 match 上确实更优（见下）。

### before / after 对照（全文 match@0.12）

| 变换 | 全文 match | 全文 d50 | WD01 f42 cov@0.12 | WD01 f42 d50 |
|---|---:|---:|---:|---:|
| 不变（both leveled） | 0.7485 | 0.0656 | 0.860 | 0.0715 |
| **TLS-direct**（roll 2.58°, pitch -0.53, yaw 0） | 0.7719 (+0.023) | 0.0643 | 0.929 (+0.07) | 0.070 |
| **ICP 估计**（roll 1.75, pitch -0.28, yaw -2.39） | **0.8526 (+0.10)** | **0.0472** | **~0.99 (+0.13)** | **0.050** |

**注意（修订）**：对 WD01，registration 解释了原始漏匹配的约 94%（14.6% → 0.9%，0.854→0.991）；TLS-direct 与 ICP 都显著改善。R3.0 名面的「WD01 bg_exact=0」确实不是 reference 的锅（无旋转已吸收 86%），但 **「剩余 14.6% 的主要修复量来自 registration」**，不能写作「alignment 只是 optional 加成」。ICP 的 roll/yaw 分解与 TLS 直接差不一致，登记为 `registration solution non-unique / weakly observable`（若未来 registration 入 production 再处理；不影响本轮结论）。

## 5. D 层：WD01 定点验证（R3.0 f42 ci1 的 957 个簇点 → reference 最近邻距离分布）

WD01 簇点用 R3.0 完全同款管道提取（leveled → CURRENT 在线 map → extract_foreground → cluster_voxels → 取窗口内最大簇的 keys 反查点集）。

| 帧 | n | before cov@0.12 | before d50 | before d95 | after cov@0.12 | after d50 | after d95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| f2 | 948 | 0.852 | 0.073 | 0.167 | **0.996** | **0.050** | **0.088** |
| f42 | 957 | 0.854 | 0.073 | 0.169 | **0.991** | **0.050** | **0.088** |
| f150 | 949 | 0.843 | 0.072 | 0.168 | **0.994** | **0.051** | **0.088** |

| Reference 侧 WD01 覆盖（203349 内） | occ=1.0 持续 102/102 帧 | R3.1 §3.2 已记录：示例 (10.07,-1.57,1.64) 远场类似物 occ=1.0；WD01 对应位置 occ≥0.9 |
|---|---|---|
| 已确认 reference 存在 WD01 静态物 | **是**（coverage@0.12 baseline 0.86，reference 不是「根本没看到」） |

### 数值矛盾调和（关键证据）

| 值 | 数值 | 表面矛盾 | 真因 |
|---|---:|---|---|
| before cov@0.12 | 0.86 | 既然 d50=0.073 < 0.12，为什么不是 ~1.0？ | d50 是**有 nb 的点**的中位数；14% 漏匹配的点是**有 nb 但 d∈[0.12, 0.20]** 的尾巴（d95=0.169）。这正是 M3 的另一半证据。 |
| TLS-direct vs ICP 增益差异 | +0.02 vs +0.10（全文）；WD01 +0.07 vs +0.13 | 都是 2.58° 级别的旋转，为什么差 5×？ | ICP 找到了「roll+yaw 简并解」，它在数据上更贴；TLS-direct 是纯 sensor 几何。两者都说明 registration 真实存在，且对 WD01 是主要修复量（修订后口径）。 |
| 全文残余 ~15% 的归因 | 全文 match 0.75→0.85 | 残余主要是 matcher 几何吗？ | **未证明**。全文含动态/无对应点，不能直接归因；须在 known-static correspondence set 上做 controlled AB（R3.3）。 |

## 6. 决策树走向（2026-10-06 修订）

```
                 cross-session match audit
                           │
              ┌────────────┴────────────┐
       alignment 后明显恢复        alignment 后仍差
              │                         │
              ▼                         ▼
   优先修 session alignment       检查 matcher geometry
   （本案 WD01: 0.854→0.991 ✓，     （本案全文残余未闭合 →
    消掉 ~94% 原始漏匹配）            R3.3 controlled AB 定量）
```

**结论（修订）**：alignment 已被证明是重要贡献者（WD01 漏匹配 14.6% → 0.9%）；R3.3 的合法性来自 M3 的独立几何依据（exact 0.826 vs match 0.890、d95=0.169 尾巴、半径 ≈ 半对角），但 **M3 的独立收益必须由 R3.3 的 controlled AB（固定 reference/frame/registration，只换 matcher）定量**，不能用全文残余率预先归因。生产接入未授权。

## 7. 对 R3.3 的建议参数（基于本轮证据）

| 参数 | 当前值 | 建议候选 | 证据 |
|---|---|---|---|
| 匹配几何 | 点-形心距 < 0.12 | **点在占用体素 AABB 内 → d=0**（不再依赖形心） | D 层 d95=0.17 尾巴 ≈ 体素半对角；改 AABB 后尾巴长度 ≈ 0（f42 cov 0.86→0.99 增益中的大部分是 matcher 几何本身） |
| 邻域搜索 | 3×3×3 | 保留 3×3×3（支持跨体素边界点） | 现行邻域逻辑本身没问题 |
| Registration（R3.3 内为固定条件；独立补丁 R3.4 另议） | 无 | TLS-direct / ICP-fixed 作为 AB 的注册条件（no-align / ICP × center / AABB 四组） | WD01 0.854→0.991（ICP）；全文 +0.10 |

> R3.3 实测补充（2026-10-06）：纯「点在占用格内」（containment）语义在多数集合上弱于 center；有效的 AABB 语义是「点到占用格盒距离 < 0.12 m」（点落在格内 → d=0 只是其中一部分）。详见 [r5 summary](../2026-10-06_hrw03_r5/14_r33_summary.md)。

## 8. 边界 / 未做 / 已知限制

- **ICP 解的 yaw=-2.39° 与 TLS 的 yaw=0.003° 不一致**：是数值简并，不要拿 ICP 的 euler 直接当「会话真实安装偏差」。研究真安装姿态应该用 TLS 直接差（已在 sanity check 文件里给出）。
- 归因修订：alignment 对 WD01 消掉 ~94% 原始漏匹配（0.854→0.991）；全文残余 ~15% 的 matcher 归因未闭合，由 R3.3 controlled AB 处理（见 [../2026-10-06_hrw03_r5/14_r33_summary.md](../2026-10-06_hrw03_r5/14_r33_summary.md)）。
- `_svd_probe.js` 的 Jacobi 探针只验证了纯 roll=2° 单方向；简并情形下 roll+yaw 组合在 ICP 内部换到哪个具体方向是任意的，这是设计行为，不是 bug。
- 未采集新数据；未部署；未改 matcher 半径；R3.2 未做 AABB matcher（该 AB 实验在 R3.3/r5 完成）；未动 HUMAN_SHAPE / Tracker / leveling。

## 9. 复现

```bash
# 正式审计
node 06_r32_audit.js                          # → 07_r32_stats.json + 08_r32_run.log
# Jacobi 探针（已通过）
node _svd_probe.js
# TLS 直接差 sanity check（已通过；给出与 ICP 对照的独立视角）
node _sanity_tls_direct.js
```

证据文件：`05_r32_audit_plan.md`（计划）、`06_r32_audit.js`（审计）、`07_r32_stats.json`、`08_r32_run.log`、`_svd_probe.js`（探针）、`_sanity_tls_direct.js`、本文件。
