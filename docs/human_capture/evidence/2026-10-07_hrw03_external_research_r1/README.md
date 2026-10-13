# HR-W03 外部方案研究备忘（R41 对照页问题 ↔ GitHub/文献现成解法）

> 性质：OpenCode 研究纪要（r1）。**非验收、非证据轮、不修改任何生产/测试/配置/数据**，不 commit。
> 目的：用户 2026-10-07 查看 R41 对照页（`../2026-10-07_hrw03_r41_comparison_r1/comparison.html`）后，要求"联网搜索 / 去 Git 上找解决方法"并整理给 Codex 编排引用。本文只做「已证问题 → 外部现成方案 → 最小落点」映射，**不改变 R40 §6 的 P0–P6 判据与停止条件**。
> 基线：master / HEAD `cfbb80c57508be1a0435fdb92260f698dc763934`；工作树保持原 dirty（含 R39–R41 与其他会话变化），本文只新增本目录，未动 README / returns / 既有证据。
> ponytail 实读：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（full）。用法：复用既有编号与 R40 补丁草案/外部项目 README，仅做映射；不建议引入运行时依赖、不做重构。
> 检索方式：本会话沙箱无直连，经本机既有代理只读 GET；GitHub API + 仓库页 + arXiv 摘要页；2026-10-07。链接均已验证可达；star 数为当日快照。

## 1. R41 对照页症状 ↔ 已证根因（承接 R39/R40，非新结论）

R41 绑定：R39 固定输出（`06_shadow_results.json` / `01_absorbed_points.json` / `03_confirmation_attribution_r2.json` / 153 帧 viewer），artifact `ae5c8f4c…`，session `cap_20261002_223757`，165 帧 / 31 点，`source:"diagnostic"`。

| R41 案例 | 现象（页面原文摘要） | 现行归因（R39/R40 已证） | 关联 ID |
|---|---|---|---|
| f17 | P 候选 1523 点 → S 无可分类簇（1407 reference 删除 + 20 crop + 31 online + 2 cleanup，另 63 点未成可分类簇） | REFERENCE_ABSORPTION；真人/静态物/混合 UNKNOWN | T38-06/S7 行 |
| f55 | P0 3190 → S0 1987 + S1 454（共享 1977/354） | 去粘连 vs 同一人体碎裂，GT 未闭合 | T38-06/S7 |
| f63 | 干净窗口 18 点：17 点越 z=0.10 裁剪界、1 点 reference 命中 | 两面拟合差 1.353–24.565mm（倾斜 1.770153°）；参照契约待 GT | T38-05/S4 |
| f65 / f105 / f146 | 点保留（或几乎全保留）但确认票变化 | T01 同帧 track 复用；T02 票不按帧过期 | BUG-R40-T01/T02 |
| f102 | P2 的 22 点（占 S0 约 0.76%）并入即记 merge | any-shared-point 边定义；GT 未闭合 | T38-06/S7 |
| f151 | 仅重分箱、无删点即 merge；半径 0.263→0.827m，硬门失败 | 固定 XY 4 邻网格不保持拓扑（与背景删除无关） | 聚类算法性质（P5） |

页面指标：WD01 −98.1%、WD02 −84.6%（背景收益）；31 点损失；gate 49.65% < 50%（历史 DEGRADED / 当前 STALE）。

## 2. 外部现成方案（链接已验证，2026-10-07）

### 2.1 静态背景 / 动态点去除（含"静立人被吞"设计边界）

| 项目 | 机制 | 借用点 / 边界 |
|---|---|---|
| [KTH-RPL/dufomap](https://github.com/KTH-RPL/dufomap)（RA-L'24，352★；arXiv 2403.01449；`pip install dufomap`，声明支持 Py≥3.8 Windows/Linux） | ray casting 识别"被完整观测为空"的区域；曾看空区域里出现东西必是动态；同一参数跨传感器 | 把"占用率 ≥0.85 = 背景"升级为"**被看空过就不是静态**"；单静态传感器离线可行（原点固定，ray 代价低）。这是"静立吞人"的设计边界对手方 |
| [gisbi-kim/removert](https://github.com/gisbi-kim/removert)（IROS'20，653★） | remove-then-revert：多分辨率 range image 先删动态点、再回敛误删 | f17 类"大比例删除"的**误删回敛**思路；代价与判定量需另评估 |
| [LimHyungTae/ERASOR](https://github.com/LimHyungTae/ERASOR)（RA-L'21，523★）、[url-kaist/ERASOR2](https://github.com/url-kaist/ERASOR2)（RSS'23，210★） | pseudo-occupancy 描述子 + 区域地面分割；ERASOR2 增加实例感知 | 实例感知对"人-物粘连"有参考；同为离线静态图路线 |
| [ethz-asl/dynablox](https://github.com/ethz-asl/dynablox)（RA-L'23，604★） | 在线保守自由空间 carving；不假设物体外观 | "保守自由空间"用于抗过删/欠删；在线语义与我们的离线 shadow 口径不同，机制借用为主 |
| [PRBonn/dynamic-point-removal](https://github.com/PRBonn/dynamic-point-removal)（43★） | 地面分割 + 静态图生成 | 基线对照 |
| [rsasaki0109/dynamic-3d-object-removal](https://github.com/rsasaki0109/dynamic-3d-object-removal)（94★） | 纯 numpy / CPU，**含浏览器 JS playground**；temporal / range / fusion 三法（AV2 审计：删 66.3% 动态、保 97.4% 静态） | 与"浏览器 JS + 零依赖"约束最接近的实现参考；注意它是**地图清理**不是人识别，只借思想 |

物理极限（建议写入契约/UI）：录制全程一动不动、且所在空间从未被看空过的人，纯几何法不可分——不是 bug。

与既有 R3.x 路线的关系：**空场参考图 = visibility 思路的特例**（更简单，但需空场记录/跨会话 registration）；visibility/ever-free 不需要空场，用同段录像的"曾看空"证据通用化。两者都直击"静立吞人"。

### 2.2 聚类（split / merge）

| 来源 | 机制 | 借用点 |
|---|---|---|
| [PCL Euclidean Cluster Extraction 教程](https://pointclouds.org/documentation/tutorials/cluster_extraction.html) | BFS + 半径搜索，**点间距连通**，无 floor() 分箱邻接 | 把连通判据从"4 邻格相邻"换成"点/质心距 ≤ ~0.2–0.3m"（或 8 邻域 + 对角距离校验）；复用现有 BFS/累加器，无新依赖 |
| DBSCAN / HDBSCAN | 密度聚类 | 更重、需参数标定；浏览器零依赖约束下暂不建议 |

备选（改动更小，仅对照口径）：P/S 都在同一坐标系聚类、再变换结果对账，把"重分箱"变量从对照里消掉；生产语义仍建议距离连通。**GT 先行，不改人体门/半径阈值。**

### 2.3 Tracker / 确认票

| 来源 | 机制 | 借用点 |
|---|---|---|
| [abewley/sort](https://github.com/abewley/sort)（4385★）、[ifzhang/ByteTrack](https://github.com/ifzhang/ByteTrack)、[xinshuoweng/AB3DMOT](https://github.com/xinshuoweng/AB3DMOT)（1846★） | 每帧一对一 assignment + hits/age/time_since_update 生命周期 | 与 R40 T01/T02 最小方案完全同构；两处 guard 即可，**不引库** |
| [koide3/hdl_people_tracking](https://github.com/koide3/hdl_people_tracking)（324★） | 3D LiDAR 行人聚类 + 跟踪完整参考 | W03/W04 行人链路对照 |

### 2.4 地面 / 输入有效性

- [url-kaist/patchwork-plusplus](https://github.com/url-kaist/patchwork-plusplus)（IROS'22，1103★）：成熟地面分割；但 f63 是"两配平参照系"问题（P4），非地面分割器可修。
- I01（无效零 XYZ）：通用惯例 = 有效性掩码在变换前 guard；R40 方案已足够，无外部依赖。

## 3. 对回 R40 §6（P0–P6）与新增建议

- **P1 / P2 / P3**：外部工程惯例与 R40 方案一致，无需修改方案；按原前置/回归/停止条件各立小单。
- **P5（聚类拓扑）**：GT 后二选一或分两单——（a）距离连通性；（b）聚类坐标系一致性。不改 3/5、0.75m、8 帧、半径与人体门。
- **新增 N1（背景可见性 / ever-free）**：直击"静立吞人"边界与 f17 类过删的裁决依据；需新工单 + GT + 独立授权，建议 W03 收口后 / W04 前评估。机制借用（非移植）。
- **新增 N2（可选对照工具）**：用 DUFOMap `pip` 离线生成一套"权威静态图"作对照证据（非生产依赖），辅助裁决 f17 类删除是否过度；板端 Py 3.8 兼容性其 README 已声明。
- **不建议**：放宽 50%/60% 门；调 PIPE 阈值凑 PASS；引入运行时依赖；跳过 GT。

## 4. 边界与合规

- 本文不构成任何生产修改授权；一切补丁仍按 R40 §6 前置/回归/停止条件执行。
- 检索为一次快照；论文仅读摘要与 README，结论限于机制层面，需要时由 Codex 深读原文。
- 本轮未动 README / returns / 既有证据（对并发 writer 友好）；如需登记索引，由 Codex 按轮次惯例链接本文。

## 5. 检索清单（可复核）

- GitHub API：`search/repositories?q=dynamic+point+removal+lidar`、`removert`、`ERASOR`、`dufomap`、`dynablox`、`patchwork++`；repo 详情：`gisbi-kim/removert`、`KTH-RPL/dufomap`、`ethz-asl/dynablox`、`LimHyungTae/ERASOR`、`url-kaist/ERASOR2`、`PRBonn/dynamic-point-removal`、`rsasaki0109/dynamic-3d-object-removal`、`url-kaist/patchwork-plusplus`、`koide3/hdl_people_tracking`、`abewley/sort`、`ifzhang/ByteTrack`、`xinshuoweng/AB3DMOT`。
- arXiv 摘要：`2403.01449`（DUFOMap）、`2304.10049`（Dynablox）。
- 链接状态：2026-10-07 全部 GET 验证可达（HTTP 200；PCL 教程页 200）。

## 6. 补记（2026-10-07 同轮）：用户症状口径与只读连贯性复算

用户原话：**"现在无法连贯的框定人体的动作"**。口径落点 = 跨帧人体确认框的**存在性/成员**不连贯（不是跟丢换人）。

对 R39 固定输出（`../2026-10-07_hrw03_r39_closeout/06_shadow_results.json`、`03_confirmation_attribution_r2.json`）只读复算，不改任何文件：

| 指标（165 帧） | P（旧方案） | S（新方案） |
|---|---|---|
| UI 绿框出现帧数（joint==CONFIRMED_HUMAN 且 track_confirmed） | 97 | 45 |
| 主线 track 最长连续确认段 | track2: 66 帧连续；track39: 19 帧连续；track1: 共 30 帧 / 最长仅 6 | track4: 共 57 帧 / **最长仅 16**；track3: 10 / 4 |
| 分支内跨帧绿框身份跳变 | 0 | 0（相邻绿框帧共享 track id） |

- 非静态框变化行 **155 条，分布 97/165 帧**（另 102 条为 WD01 静态期望移除）：new_green 61 / new_purple 70 / disappeared 24；r2 归因计：HUMAN_CANDIDATE_GAIN 97、TRACK_ID_REASSIGNMENT 27、CLUSTER_TOPOLOGY_CHANGE 17、REFERENCE_ABSORPTION 8、HUMAN_CANDIDATE_LOSS 6。其中 disappeared 24 = reference absorption 8 + reassignment 6 + candidate loss 6 + topology 4。
- 拓扑拆合 12 帧：f46/53/55/56/61/152/153/159/160/164 split + f102/151 merge（f151 仅重分箱、无删点即 merge）。
- 结论：观感"框不住人" = ① 确认闪烁（T02 票按观测计数 + T01 同帧复用 + 拆合改变证据票）② 成员拆合（固定 XY 4 邻网格）③ 框整体消失（reference absorption 等）④ 近地 31 点（P4）。对应修复面：P2/P3 → P5 → N1/P4；真人身份判定仍归 P0 GT。
- 边界：P/S track 号不互认；以上为各分支内部的框口径，非真人身份；GT 未闭合前只作诊断数字。若 Codex 后续需要，可把"最长连续确认段"列为观察指标（不新增验收门）。
