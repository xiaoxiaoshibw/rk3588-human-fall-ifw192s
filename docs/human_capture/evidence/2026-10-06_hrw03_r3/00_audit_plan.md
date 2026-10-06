# W03-R3.0 Static Leakage Audit（只读审计方案）

- 日期：2026-10-06（Asia/Shanghai）
- 性质：**只读审计 + 统计 + 可视化**。不改生产代码、不改判定逻辑（`human_pipe_lib.js` / `human_detect.js` / `human_detect.html` 一行不动）、不采集、不部署、不 commit。
- 依据：用户 2026-10-06 指示（R2.6b 不回滚不继续调；下一步先做 R3.0 Static Leakage Audit，找出墙/静态物为什么穿过背景层）。
- ponytail：已加载（full），路径 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`。
- 关联：R2.6b 结论见 `../2026-10-06_hrw03_r2/07_r26b_summary.md`；R3 计划见 `../../W01_W09_FINAL_ALGORITHM_PLAN.md` 三、四节。

## 1. 代码事实（决定字段口径）

| 事实 | 出处 | 对 audit 的影响 |
|---|---|---|
| 前景匹配 = 点的 3×3×3 体素邻域内任一静态体素，其**全帧形心**距点 < 0.12m 才删 | `human_pipe_lib.js` `_bg_match` L220–231、`bg_match_radius=0.12` | 存活到最终 cluster 的点，按现行规则命中率**恒为 0**（构造性）。所以 hit ratio 必须**忽略距离**来测「map 是否存在」 |
| 背景 = 3D 体素两级（strong ≥0.85 / supported ≥0.65+抖动+邻域） | `build_static_map` L146–198 | 体素被删/被保留的第三种原因是占用率 <0.65 或抖动超限；需要逐帧占用复算 |
| 占用率算完即弃，map 只留 `{x,y,z,hits,tier}` | 同上 | `persistent_*` 字段由审计脚本按同一语义复算（动生产代码才对不上「只读」） |
| 聚类 XY-only（0.15m 柱、4 邻） | `cluster_voxels` L322–355 | 与背景的 3D 语义天然不同；本审计不评判该差异，只测 map 命中 |
| 浏览器载入时应用 TLS 配平；离线 AB 脚本跑 raw | `human_detect.js` L117–127；r2 证据 | 同一会话内 map 与点同坐标系，配平是整体刚体变换，比率不变 → 与 r2 证据同口径跑 raw |

## 2. 字段定义（每个最终 cluster，n≥60）

| 字段 | 定义 |
|---|---|
| `bg_exact_hit_ratio` | 簇内点中，**精确 3D 体素格**存在于静态 map（任意 tier）的比例（忽略距离） |
| `bg_nb_hit_ratio` | 簇内点中，3×3×3 邻域内存在 ≥1 个静态体素的比例（忽略距离） |
| `bg_miss_ratio` | `1 - bg_nb_hit_ratio`：邻域内连体素都没有 → map 覆盖空洞 |
| `bg_min_dist_m_p50/p95` | 对 nb 命中的点：点到邻域内静态体素形心的最小距离的分位数（恒 ≥0.12，因为 <0.12 的点已被删） |
| `match_r015_ratio` / `match_r020_ratio` | 若匹配半径放宽到 0.15/0.20m，本簇会被删掉的点比例（由 `bg_min_dist` 直接换算） |
| `persistent_voxel_ratio` | 点所在精确体素的**全帧占用率 ≥0.65** 的点比例（占用率 = 逐帧命中数/总帧数，每帧命中需 ≥2 点，与 builder 同语义）；另报 `occ_ge085_ratio` 与 `occ_p50` |
| `exact_tier_strong/supported` | 精确格存在时其 tier 的构成 |
| `centroid_xyz` / `bbox_xyz` | 簇心与轴向包围盒（点级 min/max） |
| `height/width/depth`、`pca_eig[3]`、`upcos` | 复用 `cluster_features` 输出 |
| `human_shape_status` / `joint_status` / `hard_label` / `track_confirmed` | 复用 `evidence_label` / `joint_status` / `classify_human` 现成输出 |
| `centroid_motion_xy_5f/20f` | 同一 `track_id` 上，当前帧簇心与 5/20 帧前簇心的 XY 距离（离线后处理，不进生产） |

> 注：`bg_nb_hit_ratio` 高 + `bg_min_dist` 集中略大于 0.12 → **map 有墙、匹配太严（量化/形心偏置）**；
> `bg_miss_ratio` 高 → **map 没建进去（空洞）**；两者都正常但 `persistent_voxel_ratio` 低 → **占用率/抖动门槛把它挡在背景外**。
> 所有字段均在 **console 同口径（TLS 配平后）** 计算；raw 口径的对照见 `10_summary.md` 附录 A。

## 3. 执行

- 脚本：`01_audit_static_leakage.js`（Node ≥18，复用 `human_replay_lib.js` / `human_pipe_lib.js` 导出纯函数，并逐字复刻生产 `_bg_match` 邻域语义与 builder 占用语义）。
- 口径：与 console 载入同序 —— 取 `captures/leveled` 中该 sid 最新 `recommended=="tls"` 的 job transform，先 `R·p+t` 再 `denoise/管线`（synth 无配平则 raw）；raw 对照仅作附录。
- 会话：`cap_20261002_223757`（golden，疑似图上墙簇）、`cap_20261004_203349`（空场对照）、`synth_bend_v1`（真人形召回对照）。
- 产物：`02_audit_results.jsonl`（逐帧逐簇）、`03_audit_stats.json`（分桶聚合）、`04_audit_run.log`（运行日志与自检）、`05_candidate_*.svg` / `09_case_*.svg`（逐点 map 命中状态可视化）、`06_query_buckets.js` + `06_query_all.log`（分桶表/绿色行/复刻自检）、`07_probe_shapes.js` + logs（raw 形状探针）、`08_trajectory.log`（raw 逐帧轨迹）、`10_summary.md`（结果与建议）。
- 自检（脚本内 assert/throw）：单帧复刻 vs `pipeline_frame` 必须 IDENTICAL；复刻 builder 的 strong|supported 集合必须等于生产 map 键集合；所有簇点 `dist<0.12` 命中数必须为 0（与现行匹配互斥）。

## 4. 不做的事

- 不修改任何阈值/判据/生产文件；不把 audit 字段接入 `pipeline_frame`（是否产品化留待用户对 R3.1 拍板）。
- 不采数（正式 20–60s 空场参考图另行授权）；不 commit。
