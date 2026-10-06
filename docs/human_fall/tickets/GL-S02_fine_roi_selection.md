# GL-S02 细粒度 ROI（lowest_floor_sheet_v3_fine_roi）

2026-10-05 用户授权："很好的开始修法"。依据：GL-S01 只读探针证明 223757 在 15cm 粒度下有 37 个干净候选、最优四区间距 0.936m/独立 4/条件数 0.208，全部现有 B 层门原样通过；问题在 25cm 粒度过粗，不在门。唯一验收表 [GLS02_ACCEPTANCE.md](../GLS02_ACCEPTANCE.md) v1；writer OpenCode（opencode-go/deepseek-v4.1-flash，本会话）。

## 背景与目标

- 现状：v2 把 6 个 25cm 干净格（两簇）判为 `INSUFFICIENT_CLEAN_ROI_SUPPORT`；地面身份（A 层 7m² 薄层）已确认，只是 ROI 粒度吃不下碎片化地面。
- 目标：A 层不动，B 层在 25cm 不够时改用 **15cm ROI 盒**，用同一套纯度门（整盒厚度/法向/RMS/每帧点数）与**完全相同的间距/独立/条件数契约**；不改任何门限、不放宽全高度契约。
- 223757 的预期从"拒绝"改为"通过"，且必须三法全过；三个在范围会话行为逐字不变。

## 范围（只这些）

`pc_apps/human_replay/`：

- 新建 `floor_roi.py`：`detect_floor_regions_v3`（先走 v1/v2；仅当 v2 报 `INSUFFICIENT_CLEAN_ROI_SUPPORT` 时启用细粒度 ROI）；`FINE_PROFILE`；15cm 盒纯度与四区选择。
- 改 `leveling.py`：auto 入口改调 v3；`code_files` 纳入 `floor_roi.py`。
- 改 `validation.py`：`floor_identified` 接受 v3 kind。
- 新建 `floor_roi_test.py`。
- 不改：`floor_detector.py`、`floor_sheet.py`（v1/v2 冻结）、B 层任何阈值、webui/captures/旧证据。

## 契约

- 细粒度参数：网格 0.15m；每帧点数 ≥20（= 下游每区留帧下限，保证 holdout 门）；厚度 ≤0.18m、`|n_z|≥0.94`、RMS≤2.5cm、贴面 0.08/0.18 —— 与 25cm 门逐字相同（只把"每帧点数"从 30 按面积折算并抬到 holdout 下限 20）。
- 四区：互不重叠、两两间距 ≥0.5m、独立数=4、条件数 ≥0.1。
- 失败语义：A 失败→`floor_regions_invalid`；A 过但 25cm 与 15cm 都不足→`INSUFFICIENT_CLEAN_ROI_SUPPORT`（含两种粒度计数）。
- 成功 kind：`lowest_floor_sheet_v3_fine_roi`；`full_height_preserved=true`、`uses_manual_reference=false`。

## 验收

[GLS02_ACCEPTANCE.md](../GLS02_ACCEPTANCE.md) v1，ID A1–A4/B1–B2/C1–C3/S01/D01。
