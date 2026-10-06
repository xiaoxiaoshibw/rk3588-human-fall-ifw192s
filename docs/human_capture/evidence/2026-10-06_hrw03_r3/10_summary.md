# W03-R3.0 Static Leakage Audit 结果（console 同口径：TLS 配平后）

- 日期：2026-10-06（Asia/Shanghai）
- writer：OpenCode（DeepSeek v4.1 Flash，本会话）；ponytail 已加载（full，`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）。
- 性质：**只读审计**。未改任何生产文件（SHA 见 §7）；未采集、未部署、未 commit、未联网。
- 口径：与 console 载入路径同序 —— 先取该 sid 最新 `recommended=="tls"` 的 job transform（`captures/leveled`）原地 `R·p+t`，再 `denoise → build_static_map / pipeline_frame`。223757 用 job `6bc5aabf…`（pitch 26.467°, roll -0.366°, tz 1.323），203349 用 job `c9712aca…`（pitch 26.993°, roll -2.948°, tz 1.317）；synth 无配平（raw）。
- 自检：单帧复刻 vs `pipeline_frame` = **IDENTICAL**（三会话）；复刻 builder 的 `strong|supported` 集合 == 生产 map 键集合（1720 / 2063 / 294）；全部存活簇点按现行匹配规则命中 = 0（互斥自检）。

## 0. 一句话结论

静态物穿背景层不是 R2.6b 能处理的类别。223757（console 配平口径）里最刺眼的绿色静态目标是
**配平系 (3.50, -0.76)、直立约 1.74m、~950 点、完全静止**的物体；它之所以从未进背景图，是三条机制叠加：

1. **占用率分母被监视对象自己污染**：受试者 f63–145 恰好站在/躺在传感器→该物的视线上，把它的“可观测帧”砍到 61%，`occ(≥2)=0.593`，差 0.057 进不了 supported 门（0.65）；
2. **每帧 ≥2 命中门 + 0.65/0.85 占用阈值**让“每帧 1 点但长期稳定”的稀疏面直接归零（203349 空场：`occ(≥1)` 中位 0.94，`occ(≥2)` 中位 0）；
3. **匹配半径 0.12 ≈ 体素半对角（0.1219）**：`nb=0.351`、`d50=0.180`，边缘/邻格点结构性地匹配不上。

该物随后仅在“几何像人”（直立 1.74m + HUMAN_SHAPE）这一层通过了硬门与 3/5 确认 → 绿色框。用户对现象的判断与数据一致：**问题在背景层，不是 PCA/清理层**。

## 1. 三会话总览（leveled）

| 会话 | 帧 | map（strong/supported） | cluster 行 | track_confirmed 行 | 备注 |
|---|---|---|---|---|---|
| `cap_20261002_223757`（golden） | 165 | 1720 (1480/240) | 884 | **132** | 其中静态物 ~100 行 + 活动目标 ~32 行 |
| `cap_20261004_203349`（空场） | 102 | 2063 (1885/178) | 300 | 0 | 全部 NON_HUMAN（无绿色），但静态残留 104 行 |
| `synth_bend_v1`（合成，raw） | 190 | 294 (294/0) | 190 | 0 | 人形召回对照 |

## 2. Golden 静态物（疑似用户截图中的绿色目标，待确认）

代表帧 f42 ci1：`c=(3.494,-0.764,0.726) h=1.736 w=0.319 d=0.516 n=957 upcos=0.983 eig=[0.176,0.078,0.010] joint=CONFIRMED_HUMAN`。

**用户点名要看的三个值（跨 115 行中位）**：

| 字段 | 值 | 读法 |
|---|---|---|
| `bg_exact_hit_ratio` | **0.000** | 精确格命中为 0：map 里根本没有它自己的格 |
| `bg_neighbor_hit_ratio` | **0.351** | 35% 的点在 3×3×3 邻域里能看到 map 体素（但全部 >0.12m，`d50=0.180`、`d95=0.285`） |
| `persistent_voxel_ratio` | **0.864** | 86% 的点所在格占用率 ≥0.50（长期存在）——它不是噪声，是长期静态物 |

补充：`bg_miss_ratio=0.645`；`occ(≥2)=0.593 / occ(≥1)=0.612`；失败原因分解 `occ_low=0.692 / no_strong_nb=0.307 / jitter=0`；
`centroid_motion_5f≈0.001–0.012`（完全静止）；`bg_match_r020_ratio`（半径 0.20 可吸收份额）整体有限。

**绿色覆盖时间线（track_confirmed 行，共 ~101 行）**：

| 帧段 | 状态 | 说明 |
|---|---|---|
| f1–62 | 全绿（n≈950） | 受试者站在 (1.5,0.85)，不挡视线 |
| f63–66 | 缩小 901→536 | 受试者横穿 (0,0)→(3.5,-0.76) 的视线（x≈1.4 处 y≈-0.30） |
| f67–91 | 无簇（被挡） | 受试者正站在视线上 |
| f92–99 / f121–125 | 碎片绿（n 144–316） | 受试者躺在视线上，上半部余量漏出 |
| f146–147、f150–164 | 恢复绿 | 受试者起身离开 |

可视化：`09_case_cap_20261002_223757_f2_ci1.svg`（物体出现即绿）、`09_case_cap_20261002_223757_f42_ci1.svg`、`05_candidate_cap_20261002_223757_f42.svg`（自动 top 候选同物）、`09_case_cap_20261002_223757_f104_ci1.svg`（活动目标对照）。

**同类近阈值静态**（未变绿但持续残留）：`8,5` 桶（n≈650、87 帧、`pv=0.916`、`occ50=0.636`、`occ_low=0.772`）与 `20,-1` 桶（n≈97、70 帧、`occ50=0.642`）——同样是“占用率差一点进不去 + 距离 0.12 外”的组合。

## 3. 机制分解（带计数）

| 机制 | 证据 | 计数 |
|---|---|---|
| M1 占用率 / 每帧 ≥2 命中门 | 203349 空场 `occ(≥1)` 中位 0.94 vs `occ(≥2)` 中位 **0**；例：`43,17` n=778 `occ1=0.96/occ=0`；`41,-7` n=72 `occ1=0.90/occ=0` | 223757 `why_occ_low≥0.9`：**449/884 行**；203349：**213/300 行** |
| M2 遮挡污染分母（人把自己监视物挡掉） | golden 物 `occ1=0.612` ≈ 未遮挡帧份额；受试者 f63–145 站/躺在其视线上 | 见 §2 时间线 |
| M3 supported 的 strong 邻域门 | golden 物 `no_strong_nb=0.307`；另一近阈值物（`14,-2` 等）同族 | `why_no_strong_nb≥0.5`：60 行（223757） |
| M4 匹配半径 vs 形心/体素半对角 | `d50=0.18`（>0.12）处 `nb=0.35`；空场 `nb` 0.44–0.92 处 `d50≈0.15–0.16` | 半径 0.20 吸收率中位：静态行 **0.206**（223757）/ **0.397**（203349）→ 单加半径不够 |
| M5 jitter | `why_jitter≥0.5` | **0 行**（两会话）——不是抖动问题 |
| M6 为什么变绿 | 物体直立 1.74m 过全部硬门 + HUMAN_SHAPE + 3/5 确认；根因在背景层 | golden 物 101 行绿 |

## 4. 人体保留边界（R3 不能伤到）

- 活动目标行：`occ50` 0.07–0.40、`miss≈1`、`centroid_motion_5f` 0.03–0.53 —— 与静态物（`occ1≈0.61`、`m5≈0.01`）分离明确。
- `synth_bend_v1`：弯腰的人自身体素 `occ50≈0.58–0.59`（差 0.65 门 0.06）→ **在线把占用阈值降到 0.55–0.60 会开始吞人**；这支持用户方向：不要只调在线阈值，要修“分母”（空场参考图）。

## 5. 候选 golden negative 登记（WD01 / WD02，待用户确认）

- **WD01（223757 静态物）**：配平系 `(3.50,-0.76)`、h≈1.74m、n≈950、静止；代表帧 f2 / f42 / f150。
  - 现状：f1–62、f92–99、f121–125、f146–164 track_confirmed 绿（~101 行）；其余帧 NON_HUMAN/候选。
  - R3 验收要求：修复后该处 **green/purple 行 = 0**；活动目标桶（5,3 / 6,-2 / 5,-1 / 5,2 / 6,3 等）保留；R2.6b split 仍 = 0。
- **WD02（203349 空场稀疏远场）**：如 `43,17`（n=778）、`41,-7`（n=72）、`42,22`（n=603）等。
  - 现状：0 绿，但 300 行 NON_HUMAN candidate。
  - R3 验收要求：空场 candidate 行 → 0（当前 300）；track_confirmed 保持 0。

> 注：用户截图“右侧绿色框住的目标”若在时间上对应 f63–145 以外的帧，且形状是直立 1.74m 结构，则即 WD01；若为其他帧/坐标，请给 sid+帧号，按同一字段表补登。

## 6. 对 R3.1 / R3.2 的直接建议（全部有本轮数据支撑）

1. **Reference static map 是同时覆盖 M1+M2 的正解**（与用户计划一致）：空场采集里 golden 物可见份额≈100%，`occ`≈1，无论阈值口径都会进图；“被监视的人遮挡自己家家具”这一结构性缺陷只能靠“无人参考图”消除。
2. **参考图 builder 的占用口径要显式定死**：空场实测 `occ(≥1)` 中位 0.94 vs `occ(≥2)` 中位 0——若沿用生产 `bg_hit_min_pts=2`，参考图会把大量稀疏远场表面继续漏掉；建议参考图用 ≥1 命中/可观测帧为分母（或另设校准参数）。
3. **匹配层升级顺序**：先在固定参考图上做 `exact → 有限邻域` 两档，再考虑“点到占用格（AABB/邻域面）”距离替代“点到形心”（现半径 0.12 ≈ 体素半对角，0.12–0.20 间的边缘点系统性漏掉；`m20` 中位吸收率 0.21/0.40 说明单加半径不够）。
4. **R3.2 前置必测（r2 审计 §4 已挂起）**：223757 与 203349 的 TLS 参数差 Δroll≈2.58°（|y|=3m 处 ≈0.13m，已到匹配半径量级）→ 先实测跨会话 reference match ratio（leveled 对 leveled）；不足时启用“参考会话 transform 当 scene transform”备选（需用户拍板）。
5. **冻结与只读保持**：Reference Map = calibration artifact，构建一次、运行只读（用户计划 §六）；本审计所有脚本只读，不接运行时。
6. **验收口径统一为 console（配平后）**：见附录 A——raw 口径 green 35 vs leveled 132，R2.6b 的证据是 raw 口径（相对比较有效），但 R3 的绝对验收必须用 leveled。

## 7. 未改生产 + SHA + 复现

生产文件 SHA256（== R2.6b 交付时，未动）：

| 文件 | SHA256 |
|---|---|
| `pc_apps/human_replay/human_pipe_lib.js` | 30c257b798cb88f5c97c9151859e1f2fa2f2357005802c58daef5b910df96b66 |
| `pc_apps/human_replay/human_pipe_lib.test.js` | 0d3991c2ea5878dca4a37b0abfdc2ea063f507ae6f2059deb3efb40513d2eb46 |
| `pc_apps/human_replay/human_detect.js` | 555685b5899e196779f403a8a2a26b24670e3eaa8bb42347041f9857d7e250c0 |
| `pc_apps/human_replay/human_detect.html` | 62bf91268460353fabaf5d936949f830a54e680fc4e7f586c1e65961181cad37 |

复现（本目录）：

```bash
node 01_audit_static_leakage.js cap_20261002_223757 cap_20261004_203349 synth_bend_v1
node 06_query_buckets.js cap_20261002_223757      # 分桶表 + 绿色行明细 + 复刻自检
node 07_probe_shapes.js cap_20261002_223757 5.01 -1.04 0.35 5 70   # raw 形状探针（附录 A）
```

证据文件：`00_audit_plan.md`、`01_audit_static_leakage.js`、`02_audit_results.jsonl`（1374 行）、`03_audit_stats.json`、
`04_audit_run.log`、`05_candidate_*.svg`、`06_query_buckets.js`、`06_query_all.log`、`07_probe_shapes.js` + 2 logs、
`08_trajectory.log`（raw 逐帧轨迹）、`09_case_*.svg`、本文件。

## 附录 A：raw vs leveled（口径警示）

| 口径 | 223757 map | cluster 行 | track_confirmed 行 | golden 物状态 |
|---|---|---|---|---|
| raw（r2 AB 口径） | 1083 (879/204) | 599 | 35 | h≈1.96、几乎不绿（NON_HUMAN 为主） |
| **leveled（console 口径）** | 1720 (1480/240) | 884 | **132** | h≈1.74、101 行绿 |

- 配平把 z 轴对齐重力后，高度/宽深/upcos 等特征与真值同序，人形门与占用统计都变化显著 → R3 验收必须用 leveled；
  defense：r2 的 AB 相对比较（split/new-green 门）不因此失效，但绝对绿数不对应 console。
- `leveling` transform 的 scope 为 `offline_display_only`（`runtime_eligible=false`）——本审计按 console 展示口径复刻，不改动该边界。
- raw 形状探针（`07_*.log`）用于目标识别（窗口存在性/形状），编号与坐标均为 raw 系，勿与 §2 坐标混用。

## 边界 / 未做

- 未采集新数据（正式 20–60s 空场参考录制需另行授权）；未部署、未 commit、未联网。
- 未改动 `human_pipe_lib.js` / `human_detect.*` / Tracker / PCA / joint_status / R2.6b cleanup / leveling / web板端。
- “截图中的绿色框是否即 WD01”待用户确认；若否，按 §5 注补登。
