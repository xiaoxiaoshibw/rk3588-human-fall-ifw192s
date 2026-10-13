# B2a 后续 · 显示层修复 + Shadow 能力项 · 设计稿 v1

状态：**PLAN_DESIGN**（不构成实施授权；本轮无生产改动）。
证据：`evidence/2026-10-09_b2a_shadow_r1/`（README 为本稿唯一事实来源）。

## 1. 显示层两项小修（独立、低风险、可单测）

### 1.1 `reset()` 导出（修跨会话 uid 混串）

- **缺陷**：`detect_overlay.js` `last = { t_id_next: 1, tracks: [], frame_no: 0 }` 与 `labelSprites` 均为模块级常驻；`init()` 只覆盖 BG/topCanvas/rf/sceneRef，不清状态。多会话连放时 track id 单调累计（截图 #8/#11 来源），场景挂旧 sprite。
- **方案**：导出 `reset()`——`last.t_id_next=1; last.tracks.length=0; last.frame_no=0;` 遍历 `labelSprites` 调 `remove_label`；调用点：`human_track.html` 会话 `change` 事件、以及 `detect_ui.js` 按钮重新打开时。
- **验收（Shadow 单测即可）**：`detect_overlay.test.js` 增用例——init→跑 5 帧→reset→`last.t_id_next===1 && tracks.length===0` 且 sprite 表空。生产值不变。

### 1.2 HUD "低稳定候选"标注（修"人 2 个"歧义）

- **缺陷**：HUD `人 N 个 (track …)` 把 22% 成簇率的柜位与 98% 成簇率的真人同权计数。
- **方案**：`hud_extra` 标注降级——track 级维护滑窗 `assoc_rate = 近 30 帧命中数/30`，display 分两组：`人 N`（assoc_rate≥0.5）与 `候选 M?`（assoc_rate<0.5 但 confirmed）。不改 shown 判据、不改 associate，纯展示。
- **验收**：女中 121622 段重放（Shadow 已可复现）：HUD 显示 "人 1 个 (#1) 候选 2? (#2/#3)"，帧数对齐 flicker_analysis.json。

## 2. 接入 Shadow 能力项（进 SILENT_REGION_MEMORY_DRAFT / C，不在本稿实施）

| 项 | 归属 | 判据 |
|---|---|---|
| 间歇成簇率并入簇特征 | C 训练 | 柜位 vs 真人 run 中位/gap 最长作 52+ 维特征候选 |
| L1 建区双条件（参考命中 + 30% 连续性罩） | SILENT_REGION §6:S1–S2 | 静立 6 段人 cell 0 入 L1 |
| 柜位稳定段（男中 92%/男近 100%）处理 | C 难负样本 | 本批 raw/*.clusters.jsonl 即标注底 |

## 3. 本稿明确不做

- 不动 RF_THRESHOLD、`TRACK_MIN_AGE`、TTL、TRACK_GATE_M、z 带、连通参数、bg_envelope 生成链。
- 不动 `human_pipe_lib.js`（生产链 P）任何函数与 `human_confirm_min_age`。
- 不实施 SILENT_REGION L1；不接 C 训练；不改融合层 v2 语义（HR-RET-V2 维持既有判定）。
- 截图 "track #8/#11" 的 uid 溯源按源码证据归档；未在浏览器现场复现（非阻塞 Caveat，§1.1 落地后此类歧义自然消失）。
