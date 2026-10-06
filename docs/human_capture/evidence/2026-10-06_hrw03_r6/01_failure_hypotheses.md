# 01 · f55 / f155 / f160 等失败帧的 Residual Failure Hypotheses（r6 · 设计输入）

- 日期：2026-10-06；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full。
- 性质：**假设清单 + 逐条验证/证伪方法**。不实现、不改 production。每条假设都给出「支持证据 → 验证方法 → 证伪条件」，验证手段落在 `02_attribution_design.md` 的工具与 `03_shadow_ab_plan.md` 的实验上。
- 数据来源：`r5/_probe_hp_cluster.log`（点级探针）、`cl01/03_failure_taxonomy.md`（簇级归类）、`r4/09_r32_summary.md`、`r5/14_r33_summary.md`、`r3/10_summary.md`。
- 重要口径：本文所有「static / person」都是 **proxy**（reference 匹配或登记位置），不是逐点 GT；no-ICP 口径会系统性低估匹配（registration 残差），逐条验证必须以固定 registration（none/tls/icp 三档）对照。

## 0. 关键帧事实表（基线，全部数字可追溯到上述证据）

点级探针（`r5/_probe_hp_cluster.log`；reference = 203349 occ≥0.5；center = 现行 center 匹配命中点数；aabbOnly = AABB 额外吸收点数；miss = 两者都未匹配）：

| 帧 | 簇 n | 质心 (x,y) | h / upcos | center | aabbOnly | miss | CL-01 ref 比 | 归类 |
|---|---:|---|---|---:|---:|---:|---:|---|
| f10 | 1564 | (1.45,0.87) | 1.18 / 0.09 | 1365 | 195 | 4 | 0.873 | STATIC_RESIDUAL（无站立人） |
| f30 | 1487 | (1.42,0.81) | 1.24 / 0.93 | 1355 | 132 | 0 | 0.911 | STATIC_FALSE_HUMAN |
| **f55** | 3190 | (1.47,0.64) | 1.73 / 0.83 | 621 | 1175 | 1394 | 0.195 | 真人+静态合并（宽接触） |
| f63 | 2874 | (1.41,0.06) | 1.74 / 1.00 | 0 | 91 | 2783 | 0.0 | 干净行走（good） |
| f65 / f146 | 2716 / 3296 | — | ~1.7 / ≥0.99 | 0 / 0 | 0 / 0 | 全 miss | ~0 | 干净行走（good） |
| f150 | 4203 | (1.46,0.30) | 1.72 / 0.53 | 95 | 248 | 3860 | 0.023（低层 d50=0.209） | 真人+低层结构 |
| **f155** | 3558 | (1.57,0.65) | 1.74 / 0.82 | 611 | 1375 | 1572 | 0.172 | 真人+结构残留 |
| **f160** | 2429 | (1.60,0.78) | 1.45 / 0.99 | 1024 | 944 | 461 | 0.422（低层 46%） | 真人+结构残留（证据最强） |
| f80/85/90（站位线） | 2499/2798/2471 | (1.52,-0.36) | 1.7→1.1 / ≥0.77 | 0 / 4 / 22 | 0 / 5 / 32 | 全 miss | ~0.01 | 干净站立（good） |
| f92/95/99/123 | 2361-2589 | (1.52,-0.4x) | 躺 / 0.6-0.97 | 26/55/23/17 | 21/34/51/15 | 全 miss | ~0.01 | 躺卧（good） |

z 带细目（关键）：

- **f55**：miss = {0–0.3:63, 0.3–0.8:243, 0.8–1.2:31, 1.2–1.8:**1038**, 1.8+:19}（1.2–1.8 是**人体的点**，正确留前景）；aabbOnly = {0–0.3:65, 0.3–0.8:287, 0.8–1.2:**623**, 1.2–1.8:**200**}（1.2–1.8 的 200 = AABB 多吃到的人体点）。
- **f160**：miss = {0–0.3:8, 0.3–0.8:50, 0.8–1.2:53, 1.2–1.8:**350**}（静态残留在低带 ~111 点；350 是人）；aabbOnly = {0–0.3:95, 0.3–0.8:145, 0.8–1.2:570, 1.2–1.8:134}。
- 全部 good 帧：center≈0、aabbOnly≤3.2%、人点几乎 100% 留前景（f63 例外仅 91 点 AABB 吸收 = 3.2%）。

## 1. 总问题（GQ = 工单唯一核心问题）

> **GQ：最终错误人体候选中，有多少错误在 background/reference subtraction 阶段已经形成？**

可操作化（逐候选簇）：`background-stage error share = 簇内「背景层未匹配、且属于静态/已存在结构」的点占比`（用 02 的 reason 标签 + known-static proxy 计算）；对照 `true-person share`（登记位置/参考图无关的活性点）。f10/f30 的现数据给出参考点：静态比 0.87–0.91（几乎全部错误形成于背景层）；f63 为 0（错误不在背景层）。

- **验证方法**：02 工具对 8 个 focal 簇 + 全部 detail 帧输出标签分布。
- **证伪 GQ 的形态**：若失败簇的未匹配点以「真人点」为主（如 f63 那样 miss=人），或标签以 `NO_REFERENCE_NEIGHBOR`（两套背景都从未见过）压倒性为主且空间上=移动物/新结构 → 背景层不是主要错误源。

## 2. 假设清单（K1–K6）

### K1 — registration residual 是背景层失配的主因（WD01 族；f55/f150/f155/f160 的低层结构同样受影响）

- **支持**：WD01 no-align 0.854 → ICP 0.991（消 ~94%）；TLS-direct 0.929；Δroll 2.582°→3 m 处 0.135 m；远场 6–8 m match 0.161（`r4/09`）。
- **验证（02/03）**：同 reference/同帧，只切 registration {none,tls,icp}：DISTANCE_OVER_GATE 与 shell 带（d∈[0.12,0.24]）的点应在 ICP 下大幅转为命中；WD01 残余 ≤1%。
- **证伪**：ICP 下 WD01/f160 静态点仍 >2% 失配，且 label 集中 `REFERENCE_HOLE` → registration 不是主因（改指 E/K5）。

### K2 — 在线 map 漏建（M1 遮挡分母 + M2 ≥2 门）解释 f10/f30/f2/f42 的纯静态簇（一整个错误候选在背景层形成）

- **支持**：f10/f30 ref 比 0.87/0.91；f30 全硬门+HUMAN_SHAPE → CONFIRMED；WD01 occ(≥2)=0.593 差 0.65 门 0.057；203349 `occ(≥1)`中位 0.94 vs `occ(≥2)`中位 0（`r3/10`）。
- **验证**：融合 reference（D 变体）后 f10/f30 静态点应几乎全部被吸收（同会话自吸收 0.9987 是上界）；online-only 归因应显示这两簇标签以「在线未见/未达 ≥2 门」为主。
- **证伪**：fusion 后仍残留 `DISTANCE_OVER_GATE` 主体 → 匹配几何/registration 在限制，而非 map 覆盖。

### K3 — f55 族（含 f150）的合并是「真人 + 贴邻家具残留」；其静态部分是 online-miss(K2) + registration(K1) 的组合；**物理贴邻**决定即使背景完美也可能保持宽接触

- **支持**：f55 低带未匹配 ~337 点（0–1.2）；aabbOnly 在 1.2–1.8 多吸收 200 人体点（贴邻代价）；CL-01：宽接触 / cut removal 后大分量仍存续、oracle probe 后仍存续；r5 §4：f10/30/55 与 (1.45,0.85) 静态物 ~90% 合并。
- **验证**：f55 在 {none,icp}×{center,AABB} 四组的低带吸收率与残余 shell 计数；再进完整管线看簇是否自然分离（person vs 残留块）。若 icp+AABB 后低带未匹配 ≤~1%（~30 点）且仍合并 → 支持「贴邻主导」。
- **证伪**：icp+AABB 后低带未匹配残量高（>5%）且标签为 DISTANCE_OVER_GATE → 匹配几何仍可改进，K3 的「贴邻不可分」结论不成立。

### K4 — f155/f160 的静态残余 = 结构边界 shell（registration + 采样量化）；f160 参考证据最强，应最先被融合吸收

- **支持**：f160 center 0.422（低层 46%）、miss 低带仅 ~111 点；f155 center 0.172；AABB 额外吸收 1375/944 点（其中高带 = 人体代价）；两类标签预期集中在盒边缘。
- **验证**：对 f155/f160 未匹配静态代理点做 d 直方图（0–0.12/0.12–0.24/>0.24）+ 体素边缘位置分层；ICP 应把 0.12–0.24 带显著压到 ~0；检查参考图对应格 occ（是否 REFERENCE_HOLE）。
- **证伪**：ICP 后 shell 带不降、或未匹配点以 >0.24 m 的 bulk 为主 → 不是边界 shell，而是参考图缺块/移动结构。

### K5 — WD02 远场稀疏面：参考覆盖缺口（occ<0.5 未入图 + 每帧 1 点级稀疏）+ 半径，在 ICP+AABB 后应基本消解；remainder 才算采样极限

- **支持**：FAR match 0.369（no-align）、d50 0.113；580 个 occ<0.5 远场体素未入图；R3.3 WD02 disks：ICP 0.917→AABB 0.968。
- **验证**：occ_min 扫描（D 变体）× 固定 ICP × {center,AABB}；目标 disks/range>8 覆盖 ≥0.95 且不伤 HP 保留。
- **证伪**：occ_min 0.2–0.3 且 AABB 下仍 <0.90 → 远场受采样/网格化限制（formally: reference 侧已尽力，须更大容差或放弃远场静态吸收）。

### K6 — 干净人体帧的 point-level retention 余量很薄（clean aabbOnly ≤3.2%），任何放宽必须在 near-furniture 组（f150/155/160）上单独计量代价

- **支持**：f63 aabbOnly 91/2874=3.2%；f65/f146/f80 =0%；f92/95/99/123 ≤2.5%（`r5` §4：97.5–99.4% retention）；near-furniture 组 +23pp（flagged，簇与静态物合并）。
- **验证**：03 的 retention 指标在完整管线（green/purple/split 门）上测；near-furniture 组单列报告，不作为纯 retention 依据但必须记录最坏吸收。
- **证伪**：任一候选变体导致 clean 组 retention <97.5% 或产生新静态误确认 → 该变体淘汰（不是「保留率不明显下降」可解释的范围）。

## 3. 假设 ↔ 验证矩阵（汇总）

| 假设 | 02 工具输出 | 03 实验 | 证伪条件（STOP） |
|---|---|---|---|
| K1 registration | 标签在 none/tls/icp 间的迁移矩阵；shell 带计数 | B/C 的 ICP 固定臂 | ICP 后静态失配仍 >2% 且 REFERENCE_HOLE 主导 |
| K2 online-miss | 在线侧 TIER_REJECT/未见 占比 | D 融合（occ_min 扫描） | 融合后仍 DISTANCE_OVER_GATE 主体 |
| K3 f55 贴邻 | f55 低带/高带四组吸收与残壳 | 完整管线簇分离观测 | ICP+AABB 后低带残量 >5% 且几何可解释 |
| K4 f155/f160 shell | d 直方图 + 边缘分层 + occ 查询 | C（AABB 阈值标定）+ ICP | shell 带不降 / bulk 为主 |
| K5 WD02 远场 | 远场标签分布（含 occ<0.5 统计侧） | D+AABB（固定 ICP） | <0.90 覆盖且无参数可救 |
| K6 retention | clean/near-furniture 分组的吸收率 | 03 全部变体的保留门 | 任何变体 clean <97.5% 或新增静态误确认 |
| GQ 总问题 | 逐簇 error-share 表（f10/f30/f55/f150/f155/f160/f63/f80/f92…） | 全部 | 失败簇未匹配点以真人为主 |

## 4. 边界 / 未做

- 本文件是设计输入，不是结论；所有数字沿用既有证据，未新跑实验。
- proxy ≠ GT（reference 匹配 / 登记位置）；no-ICP 绝对值会低估，验证一律三档 registration 对照。
- HP02（真人弯腰）= BLOCKED（无本地数据）；正式空场 = BLOCKED（待授权）。
- 未改 production；未动 connectivity / UI / Tracker / leveling。
