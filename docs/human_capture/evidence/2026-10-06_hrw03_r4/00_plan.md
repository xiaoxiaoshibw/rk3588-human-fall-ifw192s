# W03-R3.1 Reference Background Builder（实施计划）

- 日期：2026-10-06（Asia/Shanghai）
- writer：OpenCode（DeepSeek v4.1 Flash，本会话）；ponytail 已加载（full，路径 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）。
- 性质：**离线构建 + 只读证据**。不改在线行为（`pipeline_frame` / `extract_foreground` / R2.6b 清理一行不动）；不采集、不部署、不 commit、不联网。
- 依据：用户对 W03-R3.0 审计的评审判定（[11_user_verdict.md](../2026-10-06_hrw03_r3/11_user_verdict.md)）与 [W03-R3 验收规范](../../W03_R3_ACCEPTANCE.md) §3 R3.1 条。

## 目标（用户原文口径）

> 从明确的空场 session 建立 immutable reference background。

流程（用户指定）：

```text
empty-scene frames → leveling → XYZ voxelization → per-frame binary occupancy
    （voxel 中 ≥1 point → observed_this_frame = true）
→ 跨帧 persistence → REFERENCE_STATIC_MAP
```

\[
O_v=\frac{\#\{\text{frames where voxel }v\text{ has ≥1 point}\}}{N_{\text{reference frames}}}
\]

关键差异（相对在线 `build_static_map`，R3.0 根因 M1）：

- 在线每帧命中门 `bg_hit_min_pts=2` 会把「每帧 1 点但长期稳定」的稀疏远场归零
  （203349 实测 `occ(≥1)` 中位 0.94 vs `occ(≥2)` 中位 0）；参考图改用 ≥1 门。
- 占用率分母 = 固定空场帧总数 N（无监视对象遮挡污染，R3.0 根因 M2）。

## 交付

1. `human_pipe_lib.js` additive：`build_reference_map(frames, opts)` + `reference_static_keys(ref, min_occ)`
   （PIPE 新增 `bg_ref_hit_min_pts=1`、`bg_ref_occ_min=0.5` 候选值）。
   每体素输出：key / occ / obs / 形心 / jit / pts_total / pts_per_frame / confidence(=occ, v1 诊断用)。
   **无在线写入路径**（构建一次、运行期只读；本文件不接入 console/web）。
2. 单测 3 例（≥1 门 vs 在线 ≥2 门的直接回归、persistence 抗噪与阈值、统计字段与工作空间裁剪）。
3. 本目录证据：在候选空场会话 `cap_20261004_203349`（console 同口径 leveled）上构建，
   统计占用率直方图 / 阈值扫描 / 与在线 map 对照 / 稀疏远场回收量 / 自吸收自检 / 复现 digest。

## 非目标（明确不做）

- 不接 production（不建 `human_detect.js` UI、不建 `pipeline_frame` 透传、不建双 map 匹配）——
  须先过 R3.2 跨会话 match audit（用户要求）。
- 不做点到体素 AABB 的 matcher（R3.3，仅当 R3.2 证据支持）。
- 不用 persistence 做强删除（仅 diagnostic/confidence）。
- 不采集新数据（正式 20–60s 空场录制需另行授权；203349 仅为候选 reference）。

## 复现

```bash
node 01_r31_reference_builder.js cap_20261004_203349   # 本目录，输出 02_r31_stats.json
cd ../../../../pc_apps/human_replay && node human_pipe_lib.test.js   # 单测（35 passed）
```
