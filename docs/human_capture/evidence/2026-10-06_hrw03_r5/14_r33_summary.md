# W03-R3.3 Voxel-AABB Matcher Controlled AB 结果（离线只读实验）

- 日期：2026-10-06（Asia/Shanghai）
- writer：OpenCode（DeepSeek v4.1 Flash，本会话）；ponytail 已加载（full，路径 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）。
- 性质：**离线 AB 实验，生产零改动**（不接 reference、不改 `human_pipe_lib.js` / `human_detect.*`、无 production 集成）；未采集、未部署、未 commit。
- 依据：用户 2026-10-06 对 R3.2 的评审判定（R3.2 = PASS；R3.3 先做 controlled AB；生产接入 NOT AUTHORIZED YET）；[W03-R3 验收规范](../../W03_R3_ACCEPTANCE.md) §3 R3.3 条；[10_r33_ab_plan.md](10_r33_ab_plan.md)。
- 自检（全 PASS）：ICP 复跑 == R3.2 存值（48 iters，roll 1.7476°/pitch −0.2818°/yaw −2.3924°，t [0.0182, 0.031, 0.0012]）；A 层 ALL none/center == 0.7796；D 层 f42 occ≥0.9 none/center == 0.8537、icp/center == 0.9906（三条与 R3.2 逐位一致）。

## 0. 一句话结论

**AABB（点到占用格盒距离 < 0.12 m）有独立于 registration 的收益，但收益几何 = 「格内角点（M3 本体）+ 格盒外 0.12 m 表面膨胀容差」两部分的叠加，且膨胀部分同时带来贴邻静态结构的人体保留代价。**
对 WD01：center(ICP) 0.994 → AABB **1.0000**（Δ+0.006，M3 本体贡献小——registration 是 WD01 的主因，与用户预判一致）。
对 WD02：ICP 0.9172 → 0.9678（Δ+0.0506）；known-static：ICP 0.9401 → 0.9724（Δ+0.0323，corr-enriched +0.0314）——**在 registration 固定的条件下，AABB 收益独立存在**。
保留量：干净站立/行走/躺卧人体 AABB 额外吸收仅 +0.35 ~ +2.33 pp（retention 97.7–99.4%）；贴邻静态物的人体额外 +23 pp（flagged 组，簇与静态物合并）。

## 1. 控制变量与口径（与 10_r33_ab_plan.md 一致）

| 项 | 值 |
|---|---|
| reference | `cap_20261004_203349` leveled → `build_reference_map`，occ≥0.5（3707 体素）；WD01 桥接另用 occ≥0.9（2956） |
| current | `cap_20261002_223757` leveled + denoised（165 帧，R3.2 同款抽稀 ≤3000 点/帧） |
| M0 center | `min over 3×3×3 占用格 of |p − 形心| < 0.12` |
| M1 aabb | `min over 3×3×3 占用格 of d(p, 格盒) < 0.12`（点落在占用格内 → d=0） |
| M1c contain（诊断） | `d(p, 格盒) == 0` |
| registration | `none`（各自 leveled）/ `tls`（R_direct=R_cur·R_refᵀ，辅助）/ `icp`（复跑 R3.2 解，CHECK 逐位一致） |
| 输入 SHA | 见 [12_r33_stats.json](12_r33_stats.json) `inputs`（含 `human_pipe_lib.js` SHA） |

## 2. 结果矩阵（coverage@0.12；HP = match，retention = 1 − match）

| Case | Center | AABB | Δ（AABB−Center） |
|---|---:|---:|---:|
| WD01 no-align（pooled，occ≥0.5） | 0.8567 | **1.0000** | +0.1433 |
| WD01 ICP（pooled） | 0.9940 | **1.0000** | +0.0060 |
| WD01 no-align（occ≥0.9 桥接 R3.2 口径） | 0.8497 | **1.0000** | +0.1503 |
| WD01 ICP（occ≥0.9 桥接） | 0.9933 | **1.0000** | +0.0067 |
| WD02 disks no-align | 0.1960 | 0.6158 | +0.4198 |
| WD02 disks ICP | 0.9172 | 0.9678 | +0.0506 |
| WD02 range>8 no-align | 0.3584 | 0.6020 | +0.2436 |
| WD02 range>8 ICP | 0.9393 | 0.9763 | +0.0370 |
| known-static no-align（n=342457） | 0.8172 | 0.9410 | +0.1238 |
| known-static ICP | 0.9401 | 0.9724 | **+0.0323** |
| known-static corr-enriched no-align（n=327344） | 0.8550 | 0.9845 | +0.1295 |
| known-static corr-enriched ICP | 0.9539 | 0.9853 | **+0.0314** |
| ALL no-align（n=520210，R3.2 A 层复现） | 0.7796 | 0.8969 | +0.1173 |
| ALL ICP | 0.8622 | 0.9165 | +0.0543 |
| HP01 stand（clean）no-align / ICP | 0.0033 / 0.0022 | 0.0081 / 0.0057 | +0.0048 / +0.0035 |
| HP01 walk（clean）no-align / ICP | 0.0000 / 0.0001 | 0.0102 / 0.0234 | +0.0102 / +0.0233 |
| HP01 near-furniture（**flagged**）no-align / ICP | 0.1698 / 0.1965 | 0.4217 / 0.4283 | +0.2519 / +0.2318 |
| HP03 lying no-align / ICP | 0.0124 / 0.0103 | 0.0248 / 0.0187 | +0.0124 / +0.0084 |
| HP02 bending | **NOT_RUN**（本地无真人弯腰数据；synth 不适用跨会话） | — | — |

（TLS-direct 列与 per-frame WD01、d0/d1 分位、contain 列见 [13_r33_run.log](13_r33_run.log) / [12_r33_stats.json](12_r33_stats.json)。）

## 3. 判读（按用户给定的两条检查 + 独立收益要求）

1. **「WD01 ICP + AABB」= 1.0000（≥0.999）**，且 **WD02 显著提升**（ICP +0.0506；no-align +0.42）→ 按用户规则：**AABB 有独立收益**。
2. **独立于 ICP 的收益**：known-static（registration 固定为 ICP）Δ=+0.0323，corr-enriched Δ=+0.0314；ALL Δ=+0.0543 —— 不是只靠 ICP 提升。✓
3. **M3 本体（格内角点）对 WD01 贡献小**：Δ(ICP)=+0.0060（WD01 主因是 registration，与用户 R3.2 评审一致）。
4. **AABB 语义必须是「盒距离 < r」而不是「纯格内」**：M1c containment 在多数集合**弱于** center（WD01 0.8132 vs 0.8567；known-static 0.3936 vs 0.8172；ALL 0.4764 vs 0.7796）——因为 box 距离 ≤ 形心距恒成立（盒包含形心），AABB(r) 是 center(r) 的**严格超集**，其增益 = 格内角点（d=0 部分）+ 盒外 ≤0.12 m 的表面膨胀容差。
5. **膨胀容差同时吃掉部分 registration 残差**：no-align 下 AABB 在 known-static 上 0.9410 ≈ ICP 下 center 0.9401；但**远场不能替代 registration**（WD02 range>8 no-align AABB 0.6020 << center+ICP 0.9393）。
6. **保留代价剖面**：干净人体（周围 ≥1 m 无静态结构）AABB 额外吸收 +0.35~+2.33 pp；贴邻静态物（f150/155/160，簇与静态物合并/贴邻）额外 +23 pp。**R3.3 若入 production，retention 必须在完整管线（green/purple/split 门）上测——本轮未做、未授权。**

## 4. HP 分段与探针发现（`_probe_hp_cluster.js`）

- **f10/30/55 的簇与 (1.45,0.85) 处静态物（~1.2 m 高，reference 内密集）≈90% 合并**：matched 点在各帧几乎恒同（44/433/827 vs 43/428/820），不是人体吸收，**不进 retention 口径**。
- **HP01 stand（f80/85/90）**：站在视线上 (1.52,−0.40)，簇纯人（w 0.18–0.28 m），reference 附近无任何结构 → 两种 matcher 吸收率 0.2–0.8%，retention ≥99.2%。
- **HP01 walk（f63/65/146）**：穿越行走，簇纯人（h 1.69–1.78、upcos≈1.0）→ center 0%，AABB 1.0–2.3%，retention ≥97.7%。
- **HP01 near-furniture（f150/155/160，flagged）**：回程经过 (1.45,0.85) 静态物旁，簇与静态结构合并/贴邻——AABB 吸收 0.43，**只作最坏贴邻参考**（几何上人进入静态物 0.12 m 邻域被吸收，与 online map 若把该物当背景时的行为同型）。
- **HP03 lying（f92/95/99/123）**：躺在 (1.52,−0.40)，reference 附近无结构 → AABB 吸收 1.9–2.5%，retention ≥97.5%。

## 5. 对 R3.3 设计的含义（供用户判定）

- 若采用 **AABB 距离 < 0.12**：WD01/WD02/known-static 全覆盖显著提升、干净人体保留；代价是贴邻静态结构的人体点被吸收更多（最坏 +23 pp），且语义上等于把背景**膨胀 0.12 m**（比 center 更宽）。
- 若采用**纯 containment**：不推荐——多数集合弱于现行 center。
- registration 与 AABB **不是互斥**：远场仍需 registration（或更大容差），AABB 解决的是「格内/贴边」的几何漏匹配。
- **未决**：AABB 半径（0.12 vs 更小，如 0.06/0.08）与邻域策略的标定；生产门（WD01 green=0 / WD02 candidate→0 / HP01–03 retain / split=0 / 无新 green/purple）需在完整管线 shadow 中测，本轮 NOT_RUN / 未授权。

## 6. 边界 / 未做 / 已知限制

- 生产零改动；未接 reference；未采集/部署/commit；未动 Tracker / R2.6b / leveling / web。
- HP02（弯腰）NOT_RUN（无本地真人数据）；HP01 near-furniture 组为 flagged（簇合并），不作为纯 retention 依据。
- known-static 为「受试者双盘（r=1.2 m）排除」的近似静态集，非逐点对应真值；corr-enriched 变体已并列报告。
- 全矩阵在同一抽稀点集（≤3000 点/帧）上计算；coverage@0.12 判定与全搜索等价（±1 格充分性沿用 R3.2 证明）。

## 7. 复现

```bash
node 11_r33_ab.js                  # → 12_r33_stats.json + 13_r33_run.log（~9.5 s）
node _probe_hp_cluster.js          # → _probe_hp_cluster.log（HP 分段探针）
```

证据文件：`10_r33_ab_plan.md`（计划）、`11_r33_ab.js`（AB 脚本）、`12_r33_stats.json`、`13_r33_run.log`、`_probe_hp_cluster.js` + `_probe_hp_cluster.log`、本文件。
