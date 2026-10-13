# 外部全网深度补扫 r2（2026-10-08）

> 性质：只读研究备忘（r2）。**非验收、非证据轮、不修改任何生产/测试/配置/数据，不 commit**；仅新增本目录。
> 基线：同 `2026-10-07_hrw03_r39_closeout` 锁定 HEAD；工作树保持原有 dirty，本轮未动任何既有文件。
> 与 r1 的分工：r1（`../2026-10-07_hrw03_external_research_r1`）已覆盖背景静态图 / 聚类 / tracker / 地面 4 条线 13 个仓库。r2 **不回扫**，只补 r1 未覆盖方向：跌倒检测实现全景、俯装/半球型 LiDAR、2D-vs-3D 人员检测、zone 监测、自适应聚类移植。
> 检索方式：本会话沙箱无直连，经本机既有代理 `127.0.0.1:10808` 只读 GET；GitHub REST v3 + arXiv Atom API；2026-10-08。链接当日均 200。
> 搜索页 API 当日返回 400（`WebSearch` 整体不可用），故全程改走结构化接口：GitHub topic 标签路由 + free-text 查询 + arXiv Atom，`curl -sL` 跟随 301。

## 1. 结论摘要（先看这栏）

| 问题 | 全网答案 | 对我们的含义 |
|---|---|---|
| 有没有“LiDAR 3D 点云跌倒检测”可白嫖的高星开源实现？ | **基本没有**。`topic:fall-detection` 前排全是 pose/camera（AlphaPose ST-GCN 868★、OpenPifPaf 435★）或 mmWave 雷达 notebook；唯一的 `MIP_3D_LiDAR_Fall_Detection` 是 2★ MATLAB，`teguh43ananda/Lidar-Based-Fall-Detection` 是 0★ Livox Mid-360 个人 notebook。 | 证明我们“自走几何规则 + 不开 ML 支线”非孤例。无需引库，无“别人都做好了”的后顾之忧。 |
| edge / 嵌入式（树莓派 / RK3588 级）单 LiDAR 人员检测现成栈？ | **没有活跃高星实现**。搜 `pwcet` / `edge-lidar-people-detection` / `lidar-people-detection` 均无匹配生产级仓库。`Lyr3x/Roode` 是 VL53L1X ToF 单点门磁式人数计（168★），非点云。 | 我们的“板上实时、stdlib+numpy、零 OpenCV/RKNN”在当前生态里是空白位，正好占位。 |
| 有没有人用了**和我们 IFW192S 同拓扑**（半球/俯装/固定 indoor 3D）？ | **有，且是 2024-11 新 SOTA**：Uni Bonn 的 **OSDome-64 半球 FoV**（≈180°，与我们 240° 同族非车规扫描），做人分割 + 动作分类（走/挥手/坐），代码+数据公开。 | 直接同构对手方；其“球面投影 + position encoding → Mask/DETR 分割”路线是 W06 之外的另一条已验证路线（若未来允许 lightweight 模型）。 |

## 2. 新增高匹配目标（r1 未覆盖，按借用价值降序）

### 2.1 半球/俯装 LiDAR 人员分割与动作分类 —— 最贴近我们的传感器拓扑
- **论文**：[arXiv 2411.11151] *Person Segmentation and Action Classification for Multi-Channel Hemisphere Field of View Lidar*（Uni Bonn，S. Seliunina，R. Memmesheimer，S. Behnke；2024-11）。
- 传感器 **Ouster OSDome-64**（半球 ≈180° FoV），与我们 **IFW192S 240° 非重复扫描**同属“非车规、无 scan-line 结构”的对端。
- 方法：球面投影多通道图 + Mask+DINO 分割；动作三分类 walking / waving / sitting。**代码、权重、OSDome-64 人体数据集均公开**（见论文页）。
- **借用点**：证实“半球型固定 3D LiDAR 的 indoor 人体分割 + 粗动作标签”是被验证的路径；其 distance-sliced / 球面投影对“远密近疏”非均匀点的处理，与 W04 标准化输出、`registration.js` 参考帧的表征可互参。

### 2.2 俯装 crane LiDAR 3D 人框跟踪 —— “从上面看”对“靠墙/弯腰”域偏移
- [arXiv 2603.04938] *Person Detection and Tracking from an Overhead Crane LiDAR*（2026-03）。工业室内 crane 顶装。明言该视角对 KITTI 类车规训练集有强 domain-shift，需自建 overhead 数据集；tracking 用 **AB3DMOT / SimpleTrack**（r1 已收 AB3DMOT）。
- **借用点**：俯装“下视”拓扑对躺/坐/弯腰比侧装更稳定；佐证我们 W06 姿态分类“不硬猜主轴”的保守设计合理。

### 2.3 adaptive-range / curved-voxel 聚类 —— 治“远疏散、近聚密”
- **C-ARC** [arXiv 2606.18948]：Continuous-Adaptive Range Clustering for **Non-Repetitive** LiDAR。目标传感器与我们同源（Livox Risley 棱镜）。核心：滑动窗口上的 **persistent dual-graph**，把高频点插入与按需取簇解耦——正是“非重复扫描没有明确帧边界/scan-line 索引”的痛点解法。2026-06。
- **repo**：[`xmba15/curved_voxel_clustering`](https://github.com/xmba15/curved_voxel_clustering)：Curved-Voxel Clustering 点云分割；topics `curved-voxel / point-cloud-clustering`。把 voxel 按距离弯曲以吸收角分辨率随距离的稀疏化。
- **借用点（r1 聚类线的补刀）**：r1 建议把“4 邻格相邻”改成“点距/质心 ≤ 阈值”。C-ARC/curved-voxel 提供**形式化的“距离自适应连通半径”**两条现成实现，GT 之后若仍想保留网格结构可作为 (a) 方案的替代实现参考，比手写阈值更物理。

### 2.4 纯 Python 移植：`uchiyamalab/depth_clustering_py`
- 将 r1 AND 本目录此前已列的 `PRBonn/depth_clustering` 官方移植到 Python（NumPy+numba+opencv；pip 可装；Python ≥3.8 / numpy ≥1.23）。
- **借用点**：r1 已收 C++ 原版；这里给“离线对照工具”一个**免编译、Py≥3.8 可跑**的实现，W05 前若要用深度图 cluster 做三方对照证据可省一次 C++ 编译；注意其 ground-remover 部分与我们 `z<0.10` 剔除语义不同，只作诊断参考。

### 2.5 2D vs 3D LiDAR 人员决策的量化结论 —— 支撑“3D 必要”
- [arXiv 2106.11239] *2D vs. 3D LiDAR-based Person Detection on Mobile Robots*（Jia / Hermans / Leibe）。在 JackRabbot 上对比 DR-SPAAM（2D）vs CenterPoint（3D）。
- **借用点**：给出距离-clutter-定位精度三维度对照；为“为什么不只用 2D 平面（其无法区分躺/站/弯腰高度信息）”提供文献依据——直接回应 W06 需 z 信息的架构选择。

### 2.6 2D-LiDAR SLAM 中带“纯几何人员跟踪器” —— 室内动态过滤先例
- [arXiv 2204.08163] *Mapping While Following: 2D LiDAR SLAM in Indoor Dynamic Environments with a Person Tracker*（Ye 等）。三段式：**people tracking → filtering（剔动态） → following**。纯几何、无 ML，正面对“有人走动时如何剔动态点”的同一问题。
- **借用点**：虽 2D，但提供了与 r1 `removert/ERASOR/dynablox` 正交的“tracking-first 动态剔除”范式，是我们 offline shadow 与 background 构建之间可互参的轻量路线。

## 3. 与既有路线的对位关系（不改验收标准）

| 我们当前状态 | r2 新证据能给的支撑 |
|---|---|
| r1 N1 ever-free / visibility | C-ARC 的滑动窗口 dual-graph 是“无需空场、利用同段录像曾看空证据”的形式化实现，可作 N1 的具体算法选型参考。 |
| P5 聚类拓扑（r1 R39 f151 仅重分箱即 merge） | curved-voxel / C-ARC 给出“距离自适应连通”实现，是“距离连通”方案之外的工程替代。 |
| W06 姿态（UPRIGHT/BEND/…） | 2411.11151 的动作三分类在半球 LiDAR 验证可行；俯装 crane 论文给“上视对低姿态更稳”的证据。 |
| “edge 无现成库”担忧 | 检索确认该生态位在当前开源界空缺，我们的板端 numpy 实现不落后。 |

## 4. 反向证据 / 不建议

- 不建议直接引入 `depth_clustering_py` 为生产依赖（其 ground-remover 与我们冻结的 `z<0.10` 语义不同，仅建议离线对照用途）。
- 不建议追 `mvig-sjtu/AlphaPose` 或任何相机 fall-detection pipeline（与我们无 RGB、隐私-优先约束冲突，且 memory 已记录 limb+ML 支线永久关闭——除非用户亲口说“开工 HR-09”）。
- 不建议为该轮检索改变任何 R40 P0–P6 判据、gate 阈值或冻结状态。

## 5. 检索清单（可复核）

- GitHub REST `search/repositories`：topic 标签路由 12 个（`people-tracking`, `people-detection`, `human-tracking`, `lidar-detection`, `fall-detection`, `3d-people-tracking`, `person-re-identification`, `depth-clustering`, `point-cloud-clustering`, `pedestrian-detection`, `elderly-care`, `indoor-positioning`）；free-text：`fall detection lidar` / `human fall point cloud` / `point cloud fall detection` / `person tracking 3d lidar sparse` / `lidar elderly monitoring` / `hdl people tracking` / `lidar person tracking kalman` / `elderly fall point cloud` / `pwcet` / `lidar-people-detection` 等。
- arXiv Atom：按 id 拉摘要 `2606.18948`, `2603.04938`, `2411.11239`→`2411.11151`, `2204.08163`, `2106.11239`；按 query 扫 `lidar AND fall detection`、`3D person detection single solid-state lidar`、`sparse point cloud clustering pedestrian`、`density adaptive clustering lidar`、`background subtraction 3D point cloud indoor`、`people counting ceiling lidar`、`top-view lidar human`、`2D lidar people tracking indoor`、`vertical scanning lidar person`。
- 链接全部 2026-10-08 GET 200；`WebSearch` API 当日 400，改走上述结构化接口。

## 6. 落地建议（优先级降序，均需用户另行授权）

1. **可立项 N3（无代码、仅文献+对照）**：精读 2411.11151（OSDome-64 hemisphere），评估其动作三分类对 W06 的可启式参考，仅离线跑其公开数据/代码，不接生产。
2. **可复用（属 r1 N1 范围）**：把 C-ARC 的滑动窗口 dual-graph 作为“ever-free/visibility”落地的具体算法选型之一，与 r1 DUFOMap 并列供 P5/N1 裁决参考。
3. **对照工具扩展**：在已有 r1 N2（DUFOMap 权威静态图）之外，可用 `depth_clustering_py`（pip、免编译）补一份深度图聚类三方对照证据。
4. **无需新单**：2106.11239 / 2204.08163 只作 W06 架构与 background 剔除的文献依据，写进设计文档即可。
