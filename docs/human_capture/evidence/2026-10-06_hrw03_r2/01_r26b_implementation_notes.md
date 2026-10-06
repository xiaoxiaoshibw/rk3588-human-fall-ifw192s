# W03-R2.6b 实现说明（Topology-Preserving Cleanup）

- 日期：2026-10-06（Asia/Shanghai）
- 范围：只修 R2.6 的 topology regression；未动 R3 / W04+ / fall_assess / PCA / HUMAN_SHAPE / joint_status / Tracker / 3/5 确认 / R2.1–R2.5 参数 / leveling / 板端。
- writer：OpenCode（DeepSeek v4.1 Flash，本会话）；ponytail 已加载（full，路径 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）。

## 1. 修改文件与 SHA256（完成后）

| 文件 | SHA256 | 改动 |
|---|---|---|
| `pc_apps/human_replay/human_pipe_lib.js` | 30c257b798cb88f5c97c9151859e1f2fa2f2357005802c58daef5b910df96b66 | `cleanup_isolated_fg` 重写为 R2.6b；`pipeline_frame` 诊断扩展；头注释 |
| `pc_apps/human_replay/human_pipe_lib.test.js` | 0d3991c2ea5878dca4a37b0abfdc2ea063f507ae6f2059deb3efb40513d2eb46 | 新增 R2.6b-A…G + 分区守恒共 8 个测试；旧 24 例未改口径 |
| `pc_apps/human_replay/human_detect.js` | 555685b5899e196779f403a8a2a26b24670e3eaa8bb42347041f9857d7e250c0 | 面板新诊断行（候选/veto/删除/other-z 保活/簇前后/回归标记） |
| `pc_apps/human_replay/human_detect.html` | 62bf91268460353fabaf5d936949f830a54e680fc4e7f586c1e65961181cad37 | 新增 `pipeCleanup` 行；边界文案更新为 R2.6b 规则 |

未改：`human_detect_lib.js`、`human_replay_lib.js`、`human_replay_lib.py`、`leveling*`、webui/、板端、captures/ 输入。

## 2. 算法（与工单 §三–§五逐条对应）

1. **XYZ candidate（保留 R2.6 判据）**：3D 体素点数 ≤1 且 26 邻域内无任何前景 3D 体素 → 只标记 `isolated_3d_candidate`，**不立即删除**。
2. **snapshot**：单遍点扫描同时建 3D 占用表（`counts3d`）、每 3D 体素→XY 键（`vox_xy`）、XY 占用表（`xy_counts`，`key_vox` 0.15 m 网格）。全部判断只读 snapshot；禁止边删边重算。
3. **XYZ→XY 多对一**：同 XY cell 的 candidate 按 **cell 整体**判定（同 cell 多 candidate 不再逐个级联）：
   - **Case A**：cell 在删除全部 candidate 后仍被其他（非 candidate）前景点占用 → SAFE REMOVE（XY node 保留）。
   - **Case B**：cell 的 occupancy 全是 candidate（删后 node 消失）→ 查 original XY 图中该 node 的 **4 邻域 degree**（与 `cluster_voxels` 同款邻接、同款键解析）：
     - degree ≥2 → VETO，KEEP 该 cell 全部 candidate；
     - degree ≤1 → REMOVE（度≤1 node 不可能连接两个其余非空分量 → 结构性保证不 split）。
4. **single-pass 应用**：全部判定收进删除集合后一次性删点；不递归、不传播。
5. **零新增参数**：复用 `key_vox`/`voxelize`/`cluster_voxels` 语义与 `key_bg`；未引入 cleanup_xy_radius/grid 等近似参数。

### 诊断字段语义（cleanup 返回）

| 字段 | 语义 |
|---|---|
| `fg_before_cleanup` / `fg_after_cleanup` | 清理前后前景点数 |
| `isolated_3d_candidates` | 被标记的 candidate **3D 体素数** |
| `xy_topology_vetoed` | 因 Case B degree≥2 被保留的 candidate **3D 体素数** |
| `xy_cells_preserved_by_other_z` | Case A 保活的 **XY cell 数**（去重） |
| `actually_removed_points` / `actually_removed_voxels` | 实际删除点数 / 体素数（candidate 体素恒单点 → 两者相等） |
| `before/after/removed_points/removed_voxels/fg_voxels` | 兼容别名（= 实际删除量；R2.6 旧测试未改口径） |

不变式：`isolated_3d_candidates == xy_topology_vetoed + actually_removed_voxels`（单测已钉）。

### pipeline_frame 每帧诊断（工单 §七）

`fg_before_cleanup / fg_after_cleanup / isolated_3d_candidates / xy_topology_vetoed / xy_cells_preserved_by_other_z / actually_removed_points / actually_removed_voxels / clusters_before_cleanup / clusters_after_cleanup / cleanup_split_delta / topology_regression(=delta>0)`。

兼容字段保留：`iso_removed_points / iso_removed_ratio / iso_removed_voxels`（**语义变更说明**：R2.6 时代等于全部 candidate；R2.6b 起等于 veto 后的实际删除量，因此自然变小）。

## 3. 测试

`node human_pipe_lib.test.js`：**32 passed, 0 failed**（旧 24 例未改 + 新增 8 例）。
新增：A 度0删 / B 叶子度1删 / C 桥度2 veto / D 度3 veto / E 同 cell 其他 z 保活（Case A） / F snapshot 不级联（q1-q2-q3） / G frame16 型长簇不 split / 混合场景分区守恒。

## 4. 复现命令

```bash
# 单测（pc_apps/human_replay 下）
node human_pipe_lib.test.js
node human_detect_lib.test.js
node human_replay_lib.test.js
node panel.test.js

# 三会话 AB（仓库根）
node docs/human_capture/evidence/2026-10-06_hrw03_r2/03_r26b_ab.js \
     cap_20261002_223757 synth_bend_v1 cap_20261004_203349
```

AB 在 **raw（未配平）帧** 上运行，与 R2.6 证据同口径；workbench 载入时才应用 TLS 配平。R2.6 对照列为脚本内复刻（旧算法），生产列为 `pipeline_frame`。
