# W03-R3.3 Voxel-AABB Matcher Controlled AB（离线只读实验）

- 日期：2026-10-06（Asia/Shanghai）
- writer：OpenCode（DeepSeek v4.1 Flash，本会话）；ponytail 已加载（full，路径 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）。
- 性质：**离线 AB 实验，生产零改动**（不接 reference、不改 `human_pipe_lib.js` / `human_detect.*`、不做 production 集成）；未采集、未部署、未 commit。
- 依据：用户 2026-10-06 对 R3.2 的评审判定（R3.2 = PASS；R3.3 先做 controlled AB；生产接入 NOT AUTHORIZED YET）；[W03-R3 验收规范](../../W03_R3_ACCEPTANCE.md) §3 R3.3 条。

## 唯一问题

> 在**固定相同 registration**条件下，把 center-distance 换成 AABB-distance，究竟额外改善多少？

不回答生产门（green/purple/split），不宣称 M3 是剩余主因。

## 控制变量（全部固定）

| 项 | 固定为 |
|---|---|
| reference | `cap_20261004_203349` leveled + denoised → `build_reference_map`，occ≥0.5 入图（3707 体素；WD01 桥接表另用 occ≥0.9） |
| current | `cap_20261002_223757` leveled + denoised（165 帧，同 R3.2） |
| 邻域 | 3×3×3（±1 格，r=0.12 下与全搜索等价，证明见 R3.2） |
| 半径 | 0.12 m（两 matcher 同一阈值，apples-to-apples） |
| registration | 3 个条件：`none`（各自 leveled）/ `tls`（R_direct = R_cur·R_refᵀ，辅助）/ `icp`（复跑 R3.2 ICP 得 R,t，先 CHECK 复现） |

## 只变的量（matcher 几何）

- **M0 center**：`min over 占用格 of |p − 形心| < 0.12`
- **M1 aabb**：`min over 占用格 of d(p, cell AABB) < 0.12`（点落在占用格内 → d=0）
- 附带诊断 **M1c contain**：`d(p, cell AABB) == 0`（只作对照，不进主矩阵）

## 测试集

| 集 | 定义 | 期望方向 |
|---|---|---|
| WD01 | f2/f42/f150 的 WD01 簇点（R3.0 同款管道提取，pooled + 每帧） | coverage ↑ |
| WD02 | 三个代表区（0.25m 桶 43,17 / 41,-7 / 42,22 的 leveled 坐标）半径 1.5m 圆盘并集；另报 range>8m | coverage ↑ |
| known-static | 全部 current 抽稀点 − 受试者活动双盘（(1.45,0.85) 与 (1.52,−0.40)，r=1.2m，覆盖 R3.0 轨迹全程）；另报 corr-enriched（no-align 下 ref nb ≤0.5m） | coverage ↑ 且收益须独立于 ICP |
| HP01 stand（clean） | 帧 [80,85,90] 受试者簇（站立在视线上，周围 ≥1m 无静态结构） | retention = 1−match 不下降 |
| HP01 walk（clean） | 帧 [63,65,146] 受试者簇（行走穿越） | retention 不下降 |
| HP01 near-furniture（flagged） | 帧 [150,155,160]（回程贴邻 (1.45,0.85) 静态物，簇合并） | 只作最坏贴邻参考 |
| HP03 | 帧 [92,95,99,123] 受试者簇（躺卧） | retention 不下降 |
| HP02 | 本地无真人弯腰数据（synth 不适用跨会话） | NOT_RUN |

（f10/30/55 的簇与 (1.45,0.85) 静态物 ≈90% 合并，不进 retention 口径——`_probe_hp_cluster.js` 实测。）

## 判读（用户给定）

- 若 `WD01 ICP: center 0.991 → AABB 0.993`：M3 对 WD01 几乎没价值，主因是 registration。
- 若 `WD01 ICP: AABB ≥ 0.999` 且 WD02 也显著提升：AABB 有独立收益。
- **AABB 的收益必须在 known-static 点集上独立存在，而不是只靠 ICP 提升。**

## 产出

- `11_r33_ab.js`（只读脚本）、`12_r33_stats.json`、`13_r33_run.log`、`14_r33_summary.md`（矩阵 + 判定建议）。
