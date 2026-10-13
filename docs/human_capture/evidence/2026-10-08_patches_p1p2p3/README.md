# 补丁集 P1+P2+P3（BUG-R40-I01 / T01 / T02）— 审查/派发用最小修改草案

> 性质：**代码审查/派发（dispatch）包**。所有补丁均未应用到 master、未跑真机回归、未 commit。
> 根据：三个 defect 都已在 `../2026-10-07_hrw03_r40_research_r1/08_bug_and_patch_design.md` 登记，含根因、最小复现、方案、回归要求、停止条件；本目录是**该方案的完整可运行形式**。
> 冻结参数一律不动：`human_confirm_window=5` / `human_confirm_votes=3` / `human_confirm_min_age=3` / `track_gate_xy_m=0.75` / `track_lost_max=8` / `ema_alpha=0.35` / `ground_keep_below_m=0.10` / `z_max_m=2.50` / 聚类半径 `voxel_m=0.15`。

## 文件清单

| 文件 | 作用 |
|---|---|
| `PATCH_01_tracker_t01_used_set.md` | 修 Tracker 同帧多簇复用同一 track：每 tick 内新增 `used` set；完整替换代码 + 回归要求 |
| `PATCH_02_tracker_t02_frame_window.md` | 修确认票按观测、不按帧开窗：votes 改 `{f,v}`+帧过期 + 空帧写 0 + 单调 frame 保护；完整代码 |
| `PATCH_03_registration_i01_invalid_xyz.md` | 修 raw→变换入口处无效零/非有限 XYZ 仍被平移：唯一共享入口 `transformBuffer` 加 guard；完整代码 |
| `tests/PATCH_01_tracker_t01.test.js` | T01 回归：同帧 3 簇必须 3 track、不叠加票、单人 3 帧仍确认 |
| `tests/PATCH_02_tracker_t02.test.js` | T02 回归：gap 不确认、连续 3/5 不变、短间隔旧票过期、重复/倒退 frame 抛错 |
| `tests/PATCH_03_registration_i01.test.js` | I01 回归：全零保留、非 finite 保留、单分量 0 不误判、有效点变换精确不变、多记录次序不变 |

## 依赖顺序

1. **PATCH_01** 独立可实施（T01 同帧唯一）；先做。
2. **PATCH_02** 依赖 PATCH_01（T02 的「同帧 » 每 track 至多 1 票」是 T01 set 保证的）；叠加。
3. **PATCH_03** 与 Tracker 线无关，独立可实施；但注意：修后会改变 `loadFrames()` 的输出分布（原先到 denoise 丢弃的 `[0,0,0,..]` 现在到 denoise 会走错别的非 finite 分支也丢弃），可能影响已检出的 registration artifact measurements —— **不能绕开 R40 「旧 artifact 继续 STALE、不得拿新分母换旧 gate PASS」 的停止条件**。

## 现状明确的非目标（根据 R40 与冻结状态）

- 不启动 W04、不采新会话、不部署；
- 不改 registration gate 定义，不重起名 `inlier_ratio`；
- 不改聚类（grid → 距离连通）那是 P5 且在 GT 之前；
- 不改 background / leveling / PIPE 数值；
- 不为 cover 当前 pair 重跑 `registration.load`：49.65% < 50% 保留 DEGRADED。

## 测试运行

从 `pc_apps/human_replay/` 目录：

```bash
node ../../docs/human_capture/evidence/2026-10-08_patches_p1p2p3/tests/PATCH_01_tracker_t01.test.js
node ../../docs/human_capture/evidence/2026-10-08_patches_p1p2p3/tests/PATCH_02_tracker_t02.test.js
node ../../docs/human_capture/evidence/2026-10-08_patches_p1p2p3/tests/PATCH_03_registration_i01.test.js
```

预期输出均为 `PASS`。**补丁未应用到 master 前跑这些测试会 FAIL**（这正是它们的存在意义：先错后对）；应用后全部应通过。

## 派发建议

按 R40 要求的授权顺序：先独立授权（P1/P2/P3 任一），允许 OpenCode CLI `opencode-go/deepseek-v4.1-flash` 在这些文件上加 guard 并跑上述测试；任一测试失败即按 R40「stop condition」退回设计，不得调 frozen 参数凑过。
