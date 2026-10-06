# 02 · Point/Voxel Residual Attribution 设计（r6 · shadow-only，零 production contract 变更）

- 日期：2026-10-06；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full。
- 性质：**设计文档**。本轮不实现；实现须在用户批准本设计后进行，且实现物全部放在本 evidence 目录。
- 目的：让「最终错误候选」可以逐点/逐簇回答：**这个点在背景层的哪一步、因为什么，变成了错误前景**。对应工单 §七。
- 硬边界：所有 reason 标签、统计、脚本仅存在于离线 shadow；**不进入 production contract**（不改 `human_pipe_lib.js` 的 PIPE/函数签名/输出字段，不改 `human_detect.*`，不新增运行时参数）。

## 1. 问题与输出物

对固定配置（会话 / leveled transform / registration / map 组 / matcher）：

1. 对每个 **residual 点**（`extract_foreground` 保留点，即 `fg.fg_xyzi` 成员）输出一个 shadow-only reason；
2. 对每个 focal 簇（f55/f155/f160/f150/f10/f30/WD01/WD02/HP 全部）输出 reason 直方图 + **background-stage error share**；
3. 对全 165 帧输出聚合分布与 shell/edge 计数。

## 2. 输入、口径与冻结

| 项 | 值 |
|---|---|
| current | `cap_20261002_223757`（165 帧），leveled job `6bc5aabf…`（同 console 口径） |
| reference | `cap_20261004_203349`（102 帧），leveled job `c9712aca…`（R3.1 artifact） |
| 载入 | `human_replay_lib.js`：`frame_slice` + `strided_f32_copy`（只读复用） |
| 去噪 | `PL.denoise`（生产函数，只读复用） |
| 在线 map | **stats-preserving 复刻**（见 §4.1）+ 生产 `PL.build_static_map` 用于等价校验 |
| reference map | `PL.build_reference_map`（已含全统计，直接复用） |
| registration | `{none, tls, icp}` 三档（复用 R3.2 的 TLS-direct / ICP 解；ICP 定义为**固定实验条件**，不是"真值"） |
| SHA | 每次运行记录 raw+canonical 源码 SHA、4 个输入文件 SHA、transform job/id（沿用 00 §5） |

## 3. Reason 标签体系（shadow-only）

标签集合沿用工单 §七并精确定义。判定对象：单个 residual 点 `p`，在给定的 map 组 `M`（`online` / `ref` / `fused = ref ∪ online`）与阈值下求：

```
d(p, v)   = ||p − centroid(v)||            （现状语义：点→形心）
box_d(p,v)= 点到占用格盒的欧氏距离          （AABB 语义；诊断用）
±1(p)     = p 所在 3D 格 + 26 邻域（与生产 _bg_match 同域）
```

判定顺序（互斥、决定性；同一遍即可完成）：

| # | 条件 | 标签 | 含意 |
|---|---|---|---|
| 0 | `M` 内存在 v∈±1(p) 且 d<r | **（不应发生）** | 一致性自检失败——计入 `self_check_violations` |
| 1a | `M` 内存在 v∈±1(p) 且 d≥r，且 `sqrt(dx²+dy²)<r_xy` 且 `|dz|≥r_z` | `XY_MATCH_Z_FAIL` | 平面内已贴合、高度漂移超门（z 漂移占优） |
| 1b | `M` 内存在 v∈±1(p) 且 d≥r，且 `|dz|<r_z` 且 `sqrt(dx²+dy²)≥r_xy` | `Z_MATCH_XY_FAIL` | 高度已贴合、平面漂移超门（xy 漂移占优） |
| 1c | `M` 内存在 v∈±1(p) 且 d≥r，其余（两轴都超） | `DISTANCE_OVER_GATE` | 距离超门（不分轴） |
| 2 | ±1(p) 内无选中体素：reference 统计在 ±1(p) 有记录且 `0<occ≤occ_min` | `REFERENCE_HOLE` | 参考图看到了但按 occ 门没收（含稀疏面/低占面） |
| 3 | 否则：online 统计在 ±1(p) 有记录（`hits≥1`）但未达 tier 门 | `TIER_REJECT` | 在线看到了但没进 strong/supported（M2 类） |
| 4 | 否则：两套统计在 ±1(p) 都无任何记录 | `NO_REFERENCE_NEIGHBOR` | 两套背景都从未见过它（新结构/变化物/动态） |
| 5 | 其余（工作空间边界、恰在门限、统计不可用等） | `UNKNOWN` | 无法归因 |

说明：

- `r_xy / r_z`：当分析"解耦配置"时取配置值；分析现行 production（单一 r=0.12）时取 `r_xy=r_z=0.12`（此时 1a/1b 仍然是**诊断子标签**，仅用于量化 XY vs Z 分量，不改变判定）。
- 标签按**判别来源**可再细分维度 `src ∈ {ref, online, fused}`（同一条 residual 在 ref-only / online-only / fused 三个视角各判一次；供"责任归谁"矩阵）。
- 所有标签只写进本目录 JSON/JSONL，**不写回生产数据结构**。

## 4. 实现结构（设计；全部离线 Node，零三方依赖）

### 4.1 stats-preserving 在线 map 复刻（唯一必须新写的构建件）

`build_static_map` 现解释放后即弃 occ/jitter（00 §1.1）。归因需要：

- 每体素：`hits`、Welford 形心与抖动、`occ = hits/nframes`、tier（strong/supported/无）；
- 当 frame observed 门 = 2（与生产一致）；drop_ground/z 裁剪一致；
- **等价性门**：对两会话逐体素校验 `键集合`、`tier`、`形心` 与 `PL.build_static_map` **完全一致**（0 mismatch；形心 bitwise 或 <1e-9），否则 STOP。

reference 侧直接用 `PL.build_reference_map`（已含 occ/obs/jit/pts）。

### 4.2 匹配器求值器（shadow only）

- `A`: 直接调用生产函数（`_bg_match` 语义经 `PL.extract_foreground` 验证），逐点 keep/drop；
- `AABB(t)`、`decoupled(r_xy,r_z)`: 本目录纯函数（与 03 的变体定义一致）；
- 每个 residual 点同时求 `d_min`、`box_d_min`（最近占用格）。

### 4.3 自检（每次运行强制）

1. 复刻在线 map == 生产 map（§4.1 门）；
2. 逐帧守恒：`matched + residual + z_crop == denoised`（逐点位图核对，0 mismatch）；
3. A 语义 == `PL.extract_foreground` 输出（逐点，0 mismatch；CL-01 式等价自检先例）；
4. label 分区计数 == residual 计数；`self_check_violations == 0`；
5. 确定性：同输入两跑 digest 相等（样参 `r4/04` digest）。

### 4.4 输出（全部落 `evidence/2026-10-06_hrw03_r6/`）

| 产物 | 内容 |
|---|---|
| `05_attr_summary.json` | 全 165 帧 × 配置：residual 数、reason 直方图、shell/adjacent/bulk 计数、d 分位 |
| `06_attr_clusters.json` | focal 簇：reason 直方图、error-share、person/static proxy 拆分、z 带细目 |
| `07_attr_points_f<X>.jsonl` | 仅 focal 帧（f10/f30/f55/f150/f155/f160/f2/f42/f63/f80/f85/f90/f92/f95/f99/f123 + WD02 代表帧）逐点记录：`{f,x,y,z,reason,sub,src,d_min,box_d,v_occ/hits,cluster_id}` |
| `08_attr_run.log` / SHA 记录 | 运行日志 + 全部 SHA |

（编号延续本目录文件序；具体脚本名实现时定。ponytail：默认**不**产出点级全量 dump——只有 focal 帧；全帧只给聚合。）

## 5. 指标定义（供 03 复用，本工具负责产出）

| 指标 | 定义 |
|---|---|
| residual point count | 每帧 `fg.fg_xyzi` 点数（pre-cleanup） |
| static residual | residual ∩ known-static correspondence set（沿用 R3.3 §1 方法：受试者双盘 r=1.2 m 排除 + 固定 reference/frame/registration；同时报 corr-enriched 变体） |
| retention | 每帧 HP proxy 簇点在 residual 中的保留率（clean 组与 near-furniture 组分开） |
| reference hit rate | known-static 点 coverage@r（= 1 − static miss 比例）；分 range/方位复算 |
| unmatched reason distribution | §3 标签直方图（点级 + 簇级 + 全帧） |
| shell / edge residual | `shell_band`：`d_min ∈ [r, 2r]`；`adjacent_cell`：±1(p) 内有选中体素；`bulk`：≥2 格外无体素。三者互斥计数 |
| background-stage error share | 簇内「residual ∧ known-static」点占比（= GQ 的量化回答） |

## 6. 限制（必须随结果一起报告）

- proxy ≠ 逐点 GT；no-ICP 绝对值系统性低估（一律三档 registration 报告）。
- `REFERENCE_HOLE` 依赖参考图统计（候选 10.5 s；正式空场未录，BLOCKED）。
- 标签对**多因重合**点只能给主因（决策顺序），`UNKNOWN` 兜底；不宣称因果唯一。
- 评估在 PC Node 口径；非板端运行环境（本阶段无板端部署）。
- 显示层 `POST_FILTER_ERROR` 不在本工具范围；retention 一律在**簇级**计量，不用显示颜色。

## 7. 与 03 的衔接

本工具产出直接喂给 `03_shadow_ab_plan.md`：B 的轴参数来源、C 的阈值标定、D 的 occ_min 取舍、K1–K6 的证伪判定，全部引用 `05/06/07` 的字段；在归因结果出来前**不实现任何 matcher 变体**。
