# 00 · Background / Reference Subtraction 只读审计（W03-R3 后续轮 · r6）

- 日期：2026-10-06（Asia/Shanghai）
- writer：OpenCode（DeepSeek v4.1 Flash）；ponytail 已加载（full，`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）。
- 性质：**只读审计 + 实验设计**（本轮交付 00–03 四份文档）。未改任何 production 文件；未采集/部署/commit/联网；未实现任何 shadow 工具。
- 口径：console leveled pipeline（`W03_R3_ACCEPTANCE.md` §0 唯一权威口径）。
- 输入冻结（详见 §5）：`human_pipe_lib.js` canonical SHA `5bce92a4…142b4`（== R3.1/R3.2/R3.3/CL-01 记录的输入内容）；raw 字节因**已登记的外部 EOL 改写事件**（CL-01 §收尾）为 `f580778c…`——只记录、不回改。

## 0. 状态对账（本工单要求 ↔ 既有证据 ↔ 现状）

> 本审计先对账、后补缺：R3.0–R3.3 与 CL-01（R3.4）已完成，本文件不重跑、不覆盖；只把"已答/未答"讲清楚，把未答项交接给 01–03。

| 工单要求 | 现状 | 证据位置 | 状态 |
|---|---|---|---|
| Reference 构造审计（单/多帧、体素、hit/occ、tier、temporal、leveling、跨会话、冻结、confidence） | 在线 builder + R3.1 builder 全部语义在 §1 逐行核对 | `r3/10_summary.md`、`r4/04_summary.md`、本文件 §1 | **DONE（本轮逐行核对）** |
| Matcher 审计（exact/nb/radius、XY-Z 同阈、一对一、dilation、confidence gate） | §2（逐行） | `r4/09`、`r5/14`、本文件 §2 | **DONE（本轮核对）** |
| Residual 数据路径 | §3 | `cl01/01_pipeline_audit.md`（聚类段）、本文件 §3 | **DONE** |
| 失真机制 A–E | §4（按证据分级） | `r3/10` §3、`r4/09`、`r5/14`、`cl01/03` | **大部分 DONE；标定类未决 → 03** |
| point/voxel residual attribution 工具 | **不存在** | — | **OPEN → 设计见 02** |
| f55/f155/f160 逐帧归因 | 分类/探针已有，逐点归因缺 | `cl01/03`、`r5/_probe_hp_cluster.log` | **部分 OPEN → 01/02** |
| Shadow A（production 复刻 + 自动等价） | center 语义已作为 R3.2/R3.3 基线；等价自检模式（CL-01 式）可复用，尚未正式立为门 | `r4/06`、`r5/11`、`cl01/09` | **部分 → 计划见 03** |
| Shadow B XY/Z 解耦 | **未做** | — | **OPEN → 03** |
| Shadow C radius/邻域 | 部分：center/contain/AABB 已测、半径 0.20 探针 | `r5/14`、`r3/10` §3 M4 | **部分 OPEN（阈值标定）→ 03** |
| Shadow D reference fusion / 阈值 | 部分：R3.1 阈值扫描；匹配融合 AB 未做 | `r4/04` §3.2 | **OPEN → 03** |
| Shadow E AABB | 点级完成（R3.3）；完整管线门（green/purple/split）未跑 | `r5/14` §5–6 | **部分 OPEN → 03** |
| 生产接入 | **NOT AUTHORIZED**（用户未授权） | `README.md` 顶部、`r5/14` §6 | — |
| POST_FILTER_ERROR（显示层） | 已登记，属证据/显示层 | `cl01/03` §4 | **独立工单；本阶段不碰** |

## 1. Reference / 背景构造（真实代码位置）

### 1.1 现役在线背景模型（当前唯一接在 production 路径上的「reference」）

构造器：`build_static_map(frames_xyzi, opts)` — `pc_apps/human_replay/human_pipe_lib.js` **L152–204**。
运行调用：`human_detect.js` `build_static_background()` **L219–242**（载入会话后一次；`pipeOn` 开关触发重建）。

| 问题 | 事实（代码位置） |
|---|---|
| 单帧还是多帧 | **多帧**：输入 = 载入会话**全部帧**（每帧先 `denoise`，L231–233），逐帧累计 hits；223757=165 帧、203349=102 帧 |
| 是否 voxelized / 尺寸 | 3D 整数键 `key_bg` L95–98；**XY 0.15 m / Z 0.12 m**（`bg_voxel_xy/bg_voxel_z` L34–35） |
| hit count | 每帧命中门 `bg_hit_min_pts=2`（L36；判定 L170）——**每帧 <2 点的体素该帧不计 observed** |
| occupancy | `occ = hits / nframes`（L182–183）——分母 = 会话**全帧数**，被遮挡帧照样计入（M1 根源，R3.0） |
| strong tier | `hits ≥ ceil(N·0.85)`（L37/L182/L186–187） |
| supported tier | `ceil(N·0.65) ≤ hits < strong 门` + Welford 抖动 RMS ≤0.05 m（L193–194）+ 26 邻域 strong ≥2（L38–40/L195–201）；与 strong 互斥（L192） |
| temporal fusion | **无**（逐帧独立计数；无衰减/权重/滑动窗） |
| 输出 | `Map<key,{x,y,z,hits,tier}>`，x/y/z = **全帧形心**（L187/L201）；occ/jitter/density 算完即弃（只留 tier） |
| reference 是否 leveling | builder 内**无**。载入时对全 buffer 一次性就地施加该会话最新 `recommended=="tls"` transform（`human_detect.js` L117–127；`leveling.py` L397 过滤） |
| 同一坐标系？ | **同会话**：reference（该会话在线 map）与 current 用同一 transform → 同一坐标系。**跨会话**（R3.1 reference，203349 → 223757）各自 transform → **不同坐标系**（R3.2 实测 Δroll=2.582°） |
| session 间 reference | 在线模型**无**；跨会话 artifact = R3.1 `build_reference_map`（§1.2） |
| 是否冻结 | 在线模型：载入时重建一次、会话内只读（`pipeline_frame` 不写 map）；R3.1 reference：设计即 immutable（代码注释 L206–216，无在线写入路径） |
| reference confidence | 在线：**无**（tier 即资格，匹配无置信门）。R3.1：`confidence = occ`（v1，仅诊断/融合候选，无删除权，L255–256） |

工作空间：z∈[0.10, 2.50]（`ground_keep_below_m/z_max_m` L31–32），drop_ground 缺省 true（L154）——**必须开**（否则地板被误判背景）。

### 1.2 R3.1 离线参考静态图（immutable calibration artifact；**未接线**）

构造器：`build_reference_map(frames_xyzi, opts)` **L217–261**；选择器：`reference_static_keys(ref, min_occ)` **L265–270**。

与在线 builder 的差异（用户 2026-10-06 评审指定，针对 M1/M2）：

- 每帧 observed 门 = `bg_ref_hit_min_pts = 1`（L43）——回收"每帧 1 点但长期稳定"的稀疏面；
- `occ = obs / nframes`（L250）——分母 = **无遮挡空场帧数**（不被监视对象污染）；
- 输出全字段：`key/occ/obs/形心/jit/pts_total/pts_per_frame/confidence`（L251–256）；
- `bg_ref_occ_min = 0.5` = v1 候选值（**未标定**，L46）。

既有证据（`r4/04`）：203349 参考体素 5286；occ≥0.5 → 3707（其中「每帧<2 点」稀疏面 1834；「occ≥0.5 且每帧<2 点且不在在线 map」= **1632**）；在线 map 2063 在 ≤0.8 阈值下 100% 被参考图覆盖；**同会话**自吸收 0.9987（上界参照，非跨会话证据）。

接线状态：`pipeline_frame` **不消费** reference（L723–785 只用 `ctx.static_keys`）；`human_detect.js` 不构建/不传 reference。当前 production 匹配 = **仅在线 map**。

### 1.3 消费链

`human_detect.js` `_run_pipe_frame()` L306–328 → `PL.pipeline_frame(slice, idx, S.pipe)` L311 → `extract_foreground(clean, ctx.static_keys)` L725 → `_bg_match` L292–303。

## 2. Matcher（current 点 → 背景；现役）

代码：`_bg_match(static_map, x, y, z)` **L292–303**（由 `extract_foreground` L282 调用）。

| 问题 | 事实 |
|---|---|
| exact voxel key？ | **否**。点先量化到自己所在 3D 格，再枚举邻域。 |
| 邻域 | **3×3×3 体素（±1 cell，固定）**（L296）。无 KD-tree、无全局最近邻。 |
| 距离 | 点到体素**全帧形心**的**各向同性欧氏距离**：`dx²+dy²+dz² < r²`，`r = bg_match_radius = 0.12 m`（L41/L293/L299–300）。 |
| XY / Z 是否同阈 | **是——同一个 r 绑定 XY 与 Z**（确认工单疑点；本阶段只记录，不改）。 |
| XY tolerance / Z tolerance | 无独立容差。 |
| AABB？ | 现役无。R3.3 已 shadow「点到占用格盒距离 <0.12」与「纯格内」两语义。 |
| nearest neighbor？ | 无（是"任一邻域体素在半径内"的存在性判定，非最近邻）。 |
| tier-specific 阈值 | **无**。strong/supported 在 map 内**同等**可匹配。 |
| 一个 reference voxel 消除多个 current point？ | **允许**。逐点独立、无状态；同一体素可吸收任意多点；无消费/配额。 |
| dilation / erosion | **无**形态学；±1 邻域仅为固定搜索扩张。 |
| confidence gate | **无**。 |
| 邻域充分性 | ±1 格跨度 0.15 m > 0.12 m：在"点→形心"语义下，±2 格及更远体的最近可能距离 ≥0.15 m，不可能命中 → ±1 充分（R3.2/R3.3 同结论）。 |
| 命中后果 | 从前景剔除（L282 `continue`），计入 `n_dropped`（L287–288/L763–764）。 |
| 已知几何近似 | 用"点→形心"而非"点→体素盒"；0.12 ≈ 体素半对角 0.1219（R3.0 M3；R3.2 d50=0.180；R3.3 已定量 AABB 独立收益）。 |

## 3. Residual 数据路径（逐段 + 代码行）

```
RAW points.bin（stride 7）
 → frame_slice + strided_f32_copy                     [human_replay_lib.js L14–53]
 → in-place TLS leveled transform（会话最新 tls job）  [human_detect.js L91–127]
 → 全帧背景建模（载入后一次）：denoise → build_static_map(drop_ground=true)   [L219–242]
 ────────────────────────────────────────────────
 每帧 pipeline_frame(slice, idx, ctx)                  [human_pipe_lib.js L723–785]
   denoise（有限点 + 0.35–25 m 距窗）                   [L107–116]        → n_denoise
   extract_foreground：
     z∈[0.10,2.50] 裁剪 + _bg_match(static_map)         [L277–289 / L292–303]
     → RESIDUAL = fg.fg_xyzi（点级）                                       → n_foreground / n_dropped
   cleanup_isolated_fg（R2.6b；唯一后置点级过滤）        [L323–391]
   voxelize（XY 0.15 柱）                                [L121–140]
   cluster_voxels（XY 4 邻 BFS；<3 体素丢弃）            [L394–427]
   evidence_postpass / cluster_features / classify / joint [L432–509 / L551–596]
   Tracker.tick（3/5 确认）/ fall_assess                 [L602–657 / L661–682]
 → clusters / tracks / events → UI overlay（颜色 = joint） [human_detect.js L346–398]
```

关键事实：

1. **residual 的判定点是 `extract_foreground` 的逐点删除步**；cluster/candidate 层的一切"错误前景"若追源头，只能是：①匹配失败（几何/阈值/邻域）；②map 里没有该结构（建造门/阈值/遮挡污染）；③registration/采样差使坐标不重合。
2. residual 进聚类前**只经过 R2.6b cleanup**（单遍、可证不 split、不新增结构；`r2/07`）；无 SOR/ROR/半径滤波。
3. 现有诊断只有总量：`n_in → n_denoise → n_foreground（削 n_dropped）`（L763–769）；**`n_dropped` 未拆分「z 裁剪 vs 背景命中」**——归因工具需补（见 02）。

## 4. 失真机制（按证据强度排序；工单 A–E 映射）

1. **A. registration residual = PROVEN（最强）**
   - 两会话各自 TLS：Δroll **2.582°**、Δpitch −0.527°、Δyaw 0.003°；3 m 处 roll 位移 **0.135 m > 0.12 匹配半径**（`r4/09` §1）。
   - WD01：no-align cov 0.854 → **ICP 0.991**（消掉约 **94%** 漏匹配）；TLS-direct 0.929；远场 6–8 m match 0.161（`r4/09` §3/§4）。
   - 代码侧机制：两份点云经**不同**会话 transform（§1.1）；leveling 只保证各自水平（`leveling.py` L200–203：`offline_display_only`、`physical_verified=false`、`runtime_eligible=false`）。
2. **B. sampling / 匹配几何 = PROVEN（独立于 A，量级较小）**
   - M3：0.12 ≈ 半对角；邻域点 d50=0.180；半径扩到 0.20 的额外吸收率中位仅 0.206/0.397（`r3/10` §3）。
   - R3.3 controlled AB（固定 registration）：known-static ICP Δ+0.0323 / corr-enriched +0.0314 / ALL +0.0543（`r5/14` §2）。
3. **C. occlusion / visibility = PROVEN（在线 map 侧）**
   - M1：WD01 分母被自身遮挡污染，`occ(≥2)=0.593 < 0.65` 门差 0.057（`r3/10` §2，含 f63–145 时间线）。
   - 反向（reference 被挡、current 暴露）：reference 只给"删除权"，不存在"reference 缺失→前景"的路径 → 行为中性。
   - 处置方向：R3.1 空场分母 = 按构造消除（用户已拍板）。
4. **D. leveling-induced = CONFIRMED 机制（被 A 吸收计量）**
   - reference 与 current **各自**拟合地面（per-session TLS）；"两边都水平"≠"同一世界系"（Δroll 2.58° 即残差体现）。
   - ICP 复跑出现 roll↔yaw 简并（roll 1.75° + yaw −2.39°），登记 `registration solution non-unique / weakly observable`（`r4/09` §8）——不要把 ICP euler 当"真实安装偏差"。
5. **E. reference quality = PARTIAL**
   - 稀疏面/远场：M2「每帧 ≥2 点」门让 `occ(≥1)` 中位 0.94 的稀疏面 `occ(≥2)` 中位 0（`r3/10` §3）；R3.1 ≥1 门已回收 1632 体素。
   - 远场仍弱：FAR match 0.369、d50 0.113 贴半径上限；580 个 occ<0.5 远场体素未入图（`r4/09` §2、`r4/04` §3.2）。
   - 人体污染：建造前提=空场，已排除；但候选 reference 仅 10.5 s，正式 20–60 s 空场**未录**（BLOCKED，待授权）。
   - 未充分利用：supported tier（在线）与参考图中层 occ 在匹配时**无差异门**。

**未决（→ 02/03）**：shell/edge 残差的逐点构成；XY vs Z 漂移分量占比；AABB 阈值标定；远场「纳入更低 occ / 更宽容差」的取舍；融合优先级与 retention 的完整管线表现；POST_FILTER_ERROR（显示层，另立工单）。

## 5. Provenance / SHA（本审计时点，全部可复算）

### 5.1 源码（raw = 现行字节；canonical = CRLF→LF 归一）

| 文件 | raw SHA256 | canonical SHA256 | 备注 |
|---|---|---|---|
| `pc_apps/human_replay/human_pipe_lib.js` | `f580778c366767529d74d17af8ff2ecba4a22728dcd9fc06743e74d510a4dc83` | `5bce92a433e58d537c05bfd36f516077f94e80bf351a94aae8efad46b04142b4` | canonical == R3.1/R3.2/R3.3/CL-01 记录输入 |
| `pc_apps/human_replay/human_pipe_lib.test.js` | `dfd8a4c49cd27a7192161a88e4c097f052225674a4137eaea3e6c6f399ba9449` | `0dc981540e0a51d85e634c1a95284d1e19c065e80ff9bf379a991d7edf349cc5` | 实测现状；35/35 通过。r4 表简写 `0d3991c2…49cc5` = R2.6b 版头（`0d3991c2…d2eb46`，见 r2/r3）与本实测 canonical 尾的混排，无法逐位复核；登记为 r4 记录问题，**不涉及 `human_pipe_lib.js`**（本工单关键 SHA 全部逐位一致） |
| `pc_apps/human_replay/human_detect.js` | `45d1305577e53dee79887b454e291c3904ae753c07f69984269310e2b6ad6307` | `555685b5899e196779f403a8a2a26b24670e3eaa8bb42347041f9857d7e250c0` | == r3/r4 记录 |
| `pc_apps/human_replay/human_detect.html` | `9d89589d2a6e5e3f3fa7e0972fe7775cf6b9df40641cf9fbb7dab73d19cb5a6f` | `62bf91268460353fabaf5d936949f830a54e680fc4e7f586c1e65961181cad37` | == r3/r4 记录 |

- 4 文件 + CL-01 所列其余文件 mtime = `2026-10-06T13:15:11Z`（= 21:15:11 +08:00）→ **即 CL-01 已登记的外部 EOL 批量改写事件**；截至本审计**无更新的改写**。按工单规则：只记录，不回改。
- 测试现状（只读复核）：`human_pipe_lib.test.js` **35/35**；`human_detect_lib.test.js` 11/11；`human_replay_lib.test.js` 45/45。

### 5.2 会话输入（只读；与 CL-01/R3.1 记录逐位一致）

| 会话 | meta.json SHA256 | points.bin SHA256 | 用途 |
|---|---|---|---|
| `cap_20261002_223757`（165 帧） | `71915d5181b8fc409d83a8e1650671801d2d50cf09ef4a3832d43b51ec3f4ca8` | `8afb660b7bf0631462d4cde6f82bd89884b2e83acea1da25c07316c87b5fbb37` | current（WD01/HP01-03/f10·f30·f55） |
| `cap_20261004_203349`（102 帧） | `c3b55d1e11ed8a043bd3645af7ed07e920024c05f3cb48b15d523405edd38392` | `2ed3fc60d99b3a2f42e0951835ad847fae2f490859e487b167fbccb1b5f10323` | reference（R3.1 artifact 源） |

### 5.3 Transforms / git

- 223757 tls job `6bc5aabf8f0041ffa961758b4e84da94`（2026-10-06 10:43）；203349 tls job `c9712acad48c4fb7a78cb119c08d4cdb`（transform_id `5d8fd5c0…`，2026-10-05 17:29）。
- git HEAD：`d8efabaf1201847c960e5f522aaeb6e7eee049b4`（本审计实测）。CL-01 基线为 `e79b1301…`；两者差值 = 一次 Console 源码旁路提交（仅 `pc_apps/console/console_gui.py` + `console_passthrough.ini.example`，95 行插入）——**human_replay 管线未被该提交触碰**（SHA 已证）。
- 生产文件仍为未提交工作树改动（M）；本审计不做任何 git 操作。

## 6. 未做 / 边界

- 未实现任何 shadow/attribution 脚本；未跑新实验；未采集；未部署；未 commit；未改 EOL。
- 未重开 R3.0–R3.3 / CL-01 结论；未动 connectivity / UI / Tracker / R2.6b / leveling。
- 正式 20–60 s 空场参考录制 = **BLOCKED**（需另行授权）。
- HP02（真人弯腰）本地无数据 = **BLOCKED**（synth 不适用跨会话）。
- 后续步骤：`01_failure_hypotheses.md`（假设与验证法）→ `02_attribution_design.md`（归因工具设计）→ `03_shadow_ab_plan.md`（下一轮 shadow 实验设计）。**本文件完成即停，等评审。**
