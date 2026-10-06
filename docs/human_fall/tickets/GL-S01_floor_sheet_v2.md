# GL-S01 地面身份层 lowest_floor_sheet_v2

2026-10-05 用户明确授权：「可以开单。…边界就锁成：lowest_floor_sheet_v2：只新增地面身份层，不降低、不重写 B 层 ROI 质量契约。」唯一验收表 [GLS01_ACCEPTANCE.md](../GLS01_ACCEPTANCE.md) v1；本单 writer 为 OpenCode（opencode-go/deepseek-v4.1-flash，本会话），后续独审按 WORKFLOW 由 Codex 只读复审。

## 背景与依据

- GL-V01 r2 的三个在范围会话已三法全过；唯一范围外失败 223757 经只读诊断（`evidence/2026-10-05_gl_floor_diag_r1/`）归因为：地面身份基本成立（最低面 1.2934m、薄层 7.06m²、覆盖 0.94、时序 p05 0.77），但干净 25cm 格仅 6 个、分两簇，缺 4 个分散 ROI。失败原因是 **ROI 支撑不足**，不是"没有连续地面"。
- 只读探针证明 A/B 分层有效：A 层（薄层 + 5cm 多帧占用 + 连通 + 有界触面桥接）与 B 层（v1 干净格门不降 + 四区分散）解耦后，223757 得到 A=PASS / B=FAIL / `INSUFFICIENT_CLEAN_ROI_SUPPORT`，三个正常会话不受影响。
- 探针同时暴露并修正了两个实现级问题：局部法向特征向量取列错误、无关小碎片误触发 gap 门；本单将其纳入合成回归，防止重构复发。

## 范围（只这些）

`pc_apps/human_replay/` 内：

- 新建 `floor_sheet.py`：A 层身份（`RANSAC 面 → ±ε 薄层 → 5cm 多帧占用 → 连通 → 有界触面桥接`）+ 解耦后的 B 层四区支撑检查 + `detect_floor_regions_v2` 入口（v1 成功时逐字返回 v1 结果，仅 v1 `floor_regions_invalid` 时接管）。
- 改 `leveling.py`：auto 分支改调 v2 入口；`code_files` 纳入 `floor_sheet.py` SHA；不改四区人工路径语义。
- 改 `validation.py`：`floor_identified` 接受 `lowest_floor_sheet_v2`，v1 分支不变。
- 新建 `floor_sheet_test.py`：合成回归 + 两个 bug 回归。
- evidence：`docs/human_fall/evidence/2026-10-05_gl_s01_r1/`。

不做：不修改 `floor_detector.py`（v1 语义冻结）；不降低 B 层任何门；不改 driver/webui/annotator/captures/旧证据；不重打包 console exe；设备/物理/采集 NOT_RUN。

## 失败语义（本单固定）

- A 层不通过 → `floor_regions_invalid: floor identity failed (...)`（保留 v1 前缀，既有断言兼容）。
- A 通过、B 不足 → `INSUFFICIENT_CLEAN_ROI_SUPPORT: ...`。
- A 通过、B 通过 → 返回 regions + `kind = "lowest_floor_sheet_v2"` 的候选，`uses_manual_reference=false`、`full_height_preserved=true`。
- 触面桥接仅在合成用例 2/3/6 证明边界安全后才进入正式路径；条件：显著碎片 ≥0.25m²、缺口 ≤4 格、缺口占用格需触面证据（接触格比 ≥0.5 且 ≥1 触面格）、仅当最大片 <0.5m² 时才需要桥接。

## 验收

按 [GLS01_ACCEPTANCE.md](../GLS01_ACCEPTANCE.md) v1 固定 ID A1–A3/B1–B2/C1–C3/S01/D01。
