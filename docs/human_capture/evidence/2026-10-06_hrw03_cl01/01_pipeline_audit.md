# 01 · 生产聚类调用链审计（READ-ONLY，production 零改动）

> 本文件只记录**当前代码事实**（2026-10-06 审计开始时的 `human_pipe_lib.js`）：
> 文件、函数、行号、输入、输出、参数、connectivity 语义、membership 影响。
> 全部行号对应当前 SHA `5bce92a4…142b4`。不写结论性的“应该怎样”，不实现实验变体。

## 0. 审计对象与调用方

| 对象 | 说明 |
|---|---|
| 算法核心 | `pc_apps/human_replay/human_pipe_lib.js`（810 行，纯函数，零 DOM/THREE 依赖） |
| 生产调用方（唯一在线路径） | `pc_apps/human_replay/human_detect.js`（console「人体识别」页 `human_detect.html` 的浏览器层） |
| console 装载方式 | `pc_apps/console/console_gui.py` 以 `127.0.0.1:8901` 同进程 serve `pc_apps/human_replay`；`console.html` 链接 `human_detect.html?sid=cap_20261002_223757` |
| 其他调用方 | 全部为离线脚本/单测：`human_pipe_lib.test.js`、`evidence/2026-10-06_hrw03_r{1,2,3,4,5}/*.js`。`webui/`、板端代码**无**引用（已 grep 验证） |
| 同目录易混淆件 | `human_detect_lib.js`（HR-W02 pin-ROI 检测器，无聚类）；`human_replay_lib.js`（加载/回放工具，无聚类） |

## 1. 生产在线调用链（human_detect.js → human_pipe_lib.js）

```
点云载入 (load_sid:71)
  → leveled_latest 取 TLS transform（117–127）→ 原地 R·p+t（apply_Rt:92–101）→ S.buf_f32
  → build_static_background:219（一次性）
      每帧 denoise（231–233）→ build_static_map(ded,{drop_ground:true})（235）→ S.pipe.static_keys
  → set_idx:245 → run_detect:281 → _run_pipe_frame:306
      slice = strided_f32_copy(当前帧原始点，已 leveled，未 denoise)（310）
      → PL.pipeline_frame(slice, S.idx, S.pipe)（311）
  → _render_pipe_overlays:346（每簇 solid+wire box）/ _render_pipe_panel:367（计数面板）
```

### 1.1 `pipeline_frame`（human_pipe_lib.js:723–785）逐步表

| # | 步骤 | 文件:行 | 输入 | 输出 | 参数 | 改变 membership? |
|---|---|---|---|---|---|---|
| 1 | `denoise` | lib:107–116（调用 724） | 原始帧 `Float32Array[x,y,z,i]` | 新数组 | `range_min_m=0.35`, `range_max_m=25` | **是**（剔有限值/距离窗外点） |
| 2 | `extract_foreground` | lib:277–289（调用 725） | denoise 后点 + `static_keys` | `{vox_fg, n_fg, fg_xyzi}` | z∈[`ground_keep_below_m=0.10`, `z_max_m=2.50`]；`_bg_match` 半径 `bg_match_radius=0.12` | **是**（z 裁剪 + 背景点删除） |
| 2a | `_bg_match` | lib:292–303 | 点 (x,y,z) + 静态图 | bool | 3×3×3 背景体素邻域；**点到体素全帧形心**欧氏距离 < 0.12 | 是（点级删除） |
| 2b | `voxelize` | lib:121–140（调用 286） | `fg_xyzi` | `Map<"ix,iy", acc>` | `voxel_m=0.15`，key = `floor(x/0.15)+","+floor(y/0.15)`（**仅 X/Y**） | 是（定义体素域 C） |
| 3 | `cleanup_isolated_fg` | lib:323–391（调用 727） | `fg.fg_xyzi` | `{xyzi, 诊断字段…}` | 3D 体素（`key_bg`）孤立判据 + XY 4 邻拓扑保护（同款 `key_vox` 4 邻） | **是**（单遍快照批量删点；桥接/度≥2 veto） |
| 4 | `cluster_voxels` | lib:394–427（调用 731/734） | `vox_fg`（或清理后重新 `voxelize`） | 簇数组 `[{keys, acc}]` | `cluster_min_voxels=3`（<3 体素丢弃）；邻接见 §2 | **是**（定义连通分量 + 小簇过滤） |
| 4b | 诊断：`clusters_before/after` | lib:729–736 | 清理前/后体素图 | **数组**（非计数，见 §4 缺陷） | — | 否（仅诊断） |
| 5 | `evidence_postpass` | lib:432–509（调用 741） | 清理后点 + 簇 | `clusters_extra[]`（逐高度带统计） | `band_edges` 8 带；点→簇查表 `key_vox(x,y)` | 否（只统计） |
| 6 | `cluster_features` | lib:551–575（调用 744） | 簇 acc | `{ok, cx…radius_m}` | `human_n_min=60`：**n<60 → ok:false → 该簇从 `r.clusters` 消失** | 否（几何不变；候选列表过滤） |
| 7 | `classify_human` | lib:582–596（调用 746） | 特征 | `{label, confidence, reasons}` | 硬门：height∈[0.90,2.30]、width/depth≤0.70、radius≤0.45、upcos≥0.50 | 否（标签） |
| 8 | `evidence_label` / `joint_status` | lib:514–536 / 542–548（调用 751–752） | extra / f | HUMAN_SHAPE / SOLID_UNIFORM / AMBIGUOUS；三态 joint | `ev_spread_cv_person=0.18` 等 | 否（标签） |
| 9 | `Tracker.tick` | lib:602–657（调用 755） | 簇 | track 分配/EMA/时间票 | `track_gate_xy_m=0.75`；3/5 票 | 否（跨帧关联） |
| 10 | `fall_assess` | lib:661–682（调用 760） | track 历史 | 事件 | fall 阈值 | 否 |
| 11 | 渲染 `_render_pipe_overlays` | human_detect.js:346–365 | `r.clusters` | THREE box（solid+wire） | 盒尺寸 `max(0.2, 2*width_m) × max(0.2, 2*depth_m) × max(0.2, height_m)`；位置 `(cx, cy, zmin+height/2)` | 否（**只画 ok 簇**；小簇/短簇画不出来） |

## 2. Connectivity 语义（代码事实，逐条回答）

1. **voxel key 实际包含哪些轴**：聚类链 `voxelize`（121–140）/`key_vox`（86–88）都只做 `floor(x/0.15), floor(y/0.15)` —— **仅 X/Y**。Z 只进累加器（`zmin/zmax/szz`），不进 key。
2. **cluster graph 在哪些维度连边**：`cluster_voxels`（394–427）BFS 邻居（416–421）：
   `(ix-1,iy), (ix+1,iy), (ix,iy-1), (ix,iy+1)` —— **XY 4 邻（von Neumann），Z 完全不参与连边**。
3. **是 4/8/6/18/26 还是自定义**：4 邻。非 8、非 26。26 邻只出现在**背景 builder**（`bg_neighbor_min`，196–199）与 **cleanup 候选判定**（339–341），均不属于 cluster 连通。
4. **是否忽略 Z**：是。XY 柱体素意味着同 XY 不同 Z 的结构**天然属于同一 voxel、必然同簇**（synthetic Case A 证明）；相邻 XY 柱体素无论 Z 差多远都直接连边（synthetic Case C 证明）。
5. **radius-based 邻接**：无。聚类无任何距离参数（`bg_match_radius` 只属于背景 matcher，逐点删除用，与聚类无关）。
6. **morphological expansion**：无。
7. **小簇合并**：无。方向相反——`cluster_min_voxels=3`（426）把小簇**丢弃**（不并入邻居）。
8. **cluster post-merge**：无。
9. **candidate 阶段再次合并**：无。`cluster_features/classify_human/evidence_*` 都是**单簇纯函数**，输出标签；`Tracker` 只做跨帧关联，不做合并。
10. **AABB 角色**：生产前台只有 **center matcher**（`_bg_match` 点到静态体素**形心**距离）；AABB 只存在于 R3.3 离线实验脚本（`11_r33_ab.js`），**不在生产路径**。WebUI 的盒是显示框（由 2σ 尺度拼出，见 §1 第 11 步），**不参与 membership**。
11. **死参数**：`PIPE.cluster_neighbor_hops`（49）声明后**全仓无读取**（已 grep），BFS 硬编码 1 跳；调大它不会有任何效果。
12. **共用的 4 邻语义**：`cleanup_isolated_fg` 的 XY 拓扑保护（lines 360–368）**复刻**聚类 4 邻 degree —— 两者必须同步理解（清理把“链上叶子”删掉，但度≥2 的桥接 cell 会 veto 保活）。

## 3. 四套体素域（A/B/C/D）—— 不是同一套坐标

| 域 | 键函数 | 网格 | 维度 | 消费方 | 作用 |
|---|---|---|---|---|---|
| **A 背景体素（在线）** | `key_bg`（95–98） | XY 0.15 × Z **0.12** | 3D | `build_static_map`（152）、`_bg_match`（292）、cleanup 候选 3D 计数（328–341） | 背景占用率/匹配 |
| **B 参考体素（R3.1，离线）** | `key_bg`（同 A） | 同 A | 3D | `build_reference_map`（217）、`reference_static_keys`（265） | 空场参考图（**未接在线**） |
| **C 聚类体素** | `voxelize`/`key_vox`（86–88, 121–140） | XY **0.15 柱（无 Z 层）** | **2D** | `cluster_voxels`（394）、`evidence_postpass`（448）、cleanup XY degree（360–368） | 连通分量 / 逐带证据查表 |
| **D 显示** | 无体素 | — | — | `_render_pipe_overlays`（346） | 原始点云 + 逐簇近似盒（不参与任何判定） |

> 关键差异：**A 是 3D（Z=0.12），C 是 2D 柱（无 Z）**。B 与 A 同网格但本赛季只离线构建。任何“背景 residual 与聚类”的归因必须区分 A 产生的残留点与 C 的连边规则，两者不是同一个参数体系。

## 4. 诊断字段缺陷（本审计发现，仅记录不改）

- `cleanup_split_delta`（738）：`clusters_after - clusters_before` 是**数组相减**。实测：簇非空时 = `NaN`；全空时 = `0`。`topology_regression`（776）= `NaN > 0` = 恒 `false`。
- `clusters_before_cleanup/after_cleanup`（773–774）返回的是**簇对象数组**而非计数；`human_detect.js:375` 直接字符串拼接，UI 实际显示 `[object Object]→[object Object]`（实测 `String([{}])`）。
- 影响面：**仅诊断/UI 文本**。R2.6b 的验收是由证据脚本自己的 `clustersOf()` 复刻簇数（`ca.length > cb.length`）判定的，不依赖该字段；但 `03_r26b_ab.js:143` 的 `internalSplit`（`r.cleanup_split_delta > 0`）在此缺陷下**永远为空**，该条检查是空转。
- 本工单只读，不修；修复建议留待后续授权工单（改 `clusters_*_cleanup` 为 `.length`、或返回数组成员数）。

## 5. 对本轮的直接含义

- f10/f30/f55 的“人+静态物≈90% 合并”在 cluster 层面的机制候选有两类，且**互不排斥**：
  (a) **背景残留**：A 域的 center matcher 没删干净（R3.3 已量化），残留点进入前景；
  (b) **XY-only 4 邻**：即使前景点都“正确”，只要人和家具在 XY 上的 0.15 柱相邻（或存在单点桥），C 域必然并成一个簇；且同 XY 不同 Z 永远同簇（VERTICAL_ALIAS）。
- 后续 synthetic（04）+ 真实帧 lineage（05/06）+ 桥接分析（07）就是要分别量化 (a)/(b) 各自贡献。
