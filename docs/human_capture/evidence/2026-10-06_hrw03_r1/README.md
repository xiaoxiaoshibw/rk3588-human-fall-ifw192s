# HR-W03 R2 小步升级（2026-10-06）

用户 2026-10-06 拍板的 W03-R2 计划落地：**只动人体聚类链路，不碰 PCA/Tracker 关联/Fall 主逻辑，HR-W02 完全未动。**

- 执行：OpenCode（DeepSeek v4.1 Flash）；ponytail skill 已加载（full 强度，路径
  `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）。
- 范围：`pc_apps/human_replay/{human_pipe_lib.js, human_pipe_lib.test.js, human_detect.js, human_detect.html}`
  + 本证据目录。`fall_assess` 一行未改；`human_detect_lib.js`（HR-W02）未改。
- 基线：`cap_20261002_223757`（控制台「人体识别」默认会话，静态房间 + 活动目标）；
  召回对照：`synth_bend_v1`（合成人）；回归：`cap_20261004_203349`（空场）。

## 分级改动与实测

| 阶段 | 改动 | 位置 | 实测（223757，165 帧） |
|---|---|---|---|
| 基线（R1） | XY 柱 @0.95，无工作空间 | — | 簇 1231；zmin>2.2 的簇 605；身高>2.3 的簇 282；前景 6413 点/帧 |
| R2.1 | 工作空间裁剪 z∈[0.10, 2.50]（不叫去噪） | `PIPE.z_max_m`；`extract_foreground`/`build_static_map` | zmin>2.2 → **0**；身高>2.3 → **0** |
| R2.2 | XY 柱 → **3D 体素**（0.15/0.12m），每帧命中须 ≥2 点，strong ≥0.85 | `build_static_map`、`key_bg` | 静态体素 1083（strong 879 / supported 204）；前景 6413 → **3017 点/帧** |
| R2.3 | **supported** 弱静态：占用 ≥0.65 + 逐帧形心 RMS 抖动 ≤0.05m + 26 邻域 strong ≥2；前景用**有界匹配半径 0.12m**（点到静态形心，3×3×3 邻域） | `build_static_map`、`_bg_match` | 总簇 1231 → **599**（每帧中位 4） |
| R2.4 | **联合判定**：绿=硬门过+HUMAN_SHAPE；紫=硬门过+其余证据；灰=硬门不过或 SOLID_UNIFORM | `joint_status`；`human_detect.js` 配色/面板 | 证据 HUMAN_SHAPE 282 → 联合确认 **64**（旧口径 282 全绿） |
| R2.5 | **3/5 帧时间确认**（窗口 5 票 3，track 年龄 ≥3）才 human_confirmed；绿框须 track 确认 | `Tracker.tick` 投票；UI 绿门 | 绿（track 确认）**33**；track 列表显示「确认」标记 |
| 最后 | 孤立前景清理 | **未做**（按用户计划放最后） | — |

召回/回归对照：

| 会话 | 结果 |
|---|---|
| `synth_bend_v1`（合成人） | 190/190 帧人簇保留（supported=0 未吞人）；联合判定为 NON_HUMAN（几何不发硬判，符合既有口径） |
| `cap_20261004_203349`（空场） | 全 102 帧共 1 个簇（旧 0）；无 >2.2m 簇 |

测试：`node human_pipe_lib.test.js` **18 passed**（含新增：工作空间裁剪 / 两级静态 / joint_status / 3-5 帧确认）；
`human_detect_lib.test.js` 11、`human_replay_lib.test.js` 45、`panel.test.js` 全过。

## 参数（PIPE，全部集中）

```js
ground_keep_below_m: 0.10, z_max_m: 2.50,
bg_voxel_xy: 0.15, bg_voxel_z: 0.12, bg_hit_min_pts: 2,
bg_occ_strong: 0.85, bg_occ_supported: 0.65,
bg_jitter_max: 0.05, bg_neighbor_min: 2, bg_match_radius: 0.12,
human_confirm_window: 5, human_confirm_votes: 3, human_confirm_min_age: 3
```

`bg_hit_min_pts=2` 已用真实会话验证：静态房间仍建出 879 个 strong 体素（雷达密度足够）。

## 已知边界 / 下一步

- 静立 ≥85% 帧的人仍会被吞进背景（原 ≥95% 边界收紧了）；Fall 相关消费未改。
- 599 个残留簇 = 占用 <0.65 或抖动超限的断续点/慢动物体 + 活动目标；按计划下一步是
  **孤立前景清理（保守版：体素 ≤1 点且 26 邻域无前景体素才丢）**，然后才考虑更激进的召回/误报标定。
- 阈值 0.65/0.05/0.12 是工程起点，未经 ROC 标定；正式标定需带标注会话。

## R2.6 保守孤立前景清理（2026-10-06）

**算法**（`human_pipe_lib.js` `cleanup_isolated_fg`，前景 → 聚类之间）：

- 单遍快照语义：先按清理前的 3D 前景体素图算出全部删除集合，再一次性删点；
  不递归、不多轮、不传播（删掉的体素不参与第二轮邻域判定）。
- 规则（严格）：voxel 点数 ≤1 **且** 26 邻域内不存在任何前景 voxel → 删该 voxel 的点；
  只判断「邻域是否存在前景 voxel」，不设邻居点数阈值；其余全保留。
- 复用背景 3D 体素栅格（0.15/0.12m），不新增参数；不是 SOR/ROR/形态学。
- `pipeline_frame` 返回新增每帧诊断：`fg_after_cleanup / iso_removed_points /
  iso_removed_ratio / fg_voxels / iso_removed_voxels`（`n_foreground` 保持清理前语义）。
- 未动：`fall_assess`、PCA/特征、HUMAN_SHAPE 判据、`joint_status`、Tracker 关联/EMA、
  3/5 确认、HR-W02、R2.1–R2.5 参数与算法。

**单测**：`human_pipe_lib.test.js` 24 passed（新增 6：独立单点删 / 面邻保留 / 对角邻保留 /
两相邻单点都保留 / A-B-主体链+远处孤立点 single-pass 不传播 / 多点孤立不删）。
其余套件：`human_detect_lib` 11、`human_replay_lib` 45、`panel` 全过。

### AB 三组（`ab_r26.js`，before=纯函数复刻 R2，after=生产 pipeline_frame）

| 会话 | removed total | 每帧 median/p95/max | clusters before→after | green before→after | candidate | gray |
|---|---|---|---|---|---|---|
| `cap_20261002_223757`（golden） | 4205 | 25 / 33 / 37 | 599 → **616** | 33 → **46** | 67→68 | 499→502 |
| `synth_bend_v1`（召回） | 2854 | 15 / 15 / 16 | 190 → 190 | 0→0 | 0→0 | 190→190 |
| `cap_20261004_203349`（空场） | 3212 | 31 / 38 / 44 | 1 → 0 | 0→0 | 0→0 | 1→0 |

- 删除量级：golden 每帧约 25 点（≈前景 0.8%）；`removed_voxels` 与删除点数相等
  （规则只删 ≤1 点体素）。
- **synth 人体召回**：190/190 帧人簇保留；人簇点数 median 291→291，
  retention min 0.9965 / p5 1.0 / median 1.0 —— 无轮廓削薄。
- **空场**：无新 cluster、无新 green/purple（唯一 1 个 gray 簇被清掉）。

### 关键发现：golden 上不是纯清点，候选结构被改变

- 17/165 帧各 **+1 簇**（无任何帧减少），其中 14 帧各 +1 绿。
- 实检 frame 16：before `(3.54,-0.79) n=1204` → after 变为 `(3.43,-0.77) n=1115`
  **+ 新簇 `(4.99,-1.04) n=87 h=1.22 CONFIRMED_HUMAN`**（`inspect_split.js`）。
- 机制：清理按 **3D 体素**判孤立，而聚类按 **XY 4 邻连通**——某个孤立 3D 点若恰好是
  XY 图上的桥接格（左右 XY 邻居的点在别的 z 层，不构成 3D 邻域），删除它会把长簇一分为二，
  碎片可能过人体硬门 + HUMAN_SHAPE 变成绿。
- 按工单验收优先级（人体召回 > 候选几何完整 > 减噪 > 减簇）：召回与空场安全，
  但"候选几何完整"项出现实测结构变化证据，是否接受该副作用交审阅裁定。

### R2.6 产物

- `ab_r26.js` + `ab_r26_results.json` / `ab_r26_results.jsonl`（三会话全量 per-frame）
- `inspect_split.js`（单帧 before/after 簇对照，分裂实例）

## 本目录产物

- `diag_static_residual.js` / `sweep_bg_ratio.js` / `sim_fix.js` / `diag_3d_occ.js` / `diag_candidate_fix.js`：
  诊断与参数扫描（只读，跑在 captures/remote 会话上）。
- `analyze_223757.py` / `analyze_fix085.py`：残留簇形态分析。
- `ab_r2.js` + `ab_r2_results.jsonl`：R2 构建的三会话全链路对照。
- 各 `*_diag.json` / `*_fix_*.json` / `sweep_*.json`：原始测量数据。
