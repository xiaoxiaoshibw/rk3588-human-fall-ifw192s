# ROI Selector A/B Probe — 范围与冻结基线

2026-10-06。本轮是 **P3 只读旁路 probe**：零生产改动，只为「是否值得改 v1 selector」取证。

## 不做的事（边界）

不改 `floor_detector.py` / `floor_sheet.py` / `floor_roi.py` / `leveling.py` / `leveling_quality.py` /
`validation.py` / 任何既有 test。不改任何算法参数。不重写 GL-S01/S02。不 commit 生产改动。

唯一新增：`tools/roi_ab_probe.py`（旁路脚本，不进 production call graph）+ 本 evidence 目录。

## 冻结基线（审计上轮确认，本轮 SHA 实测复核）

| 文件 | SHA256 前16 | 状态 |
|---|---|---|
| floor_detector.py | 72ce790f656faf60 | 冻结（GL-S02 B2） |
| floor_sheet.py | 92d2ed105ac98faa | 冻结（GL-S02 B2） |
| floor_roi.py | 1d144e57851a00bc | GL-S02 基线 |
| leveling.py | 3c3a88196cfd9851 | GL-S02 基线 |
| leveling_quality.py | （GL-S02 同代） | 冻结门语义 |

## 生产链路事实（上轮已确认，不重新审计）

- auto 入口：`leveling.run_job(mode="auto")` → `floor_roi.detect_floor_regions_v3()`。
- v1 = `floor_detector.detect_floor_regions`（四象限最近格贪心选 4 格）。
- v2 = `floor_sheet.detect_floor_regions_v2`（A 身份层 + B 25cm 洁净格）。
- v3 = `floor_roi` 15cm fine ROI + `_select_four`（sep/cond 门 + low-RMS 排序）。
- CURRENT 语义一律由当前代码重跑得到；`captures/leveled/` 磁盘旧 job 的 `kind=None`
  是早于 v3 落盘的产物，仅作对照，不作 CURRENT 来源。

## Golden 会话（4 个，全部 `captures/remote/` 在场）

| sid | 帧数 | 走哪层 | 名义 pitch/roll（取自已保存 job 报告） |
|---|---|---|---|
| cap_20261004_202456 | 91 | v1 | 26.0 / 0.0 |
| cap_20261004_203135 | 113 | v1 | 26.0 / 0.0 |
| cap_20261004_203349 | 102 | v1 | 26.0 / 0.0 |
| cap_20261002_223757 | 165 | v3（control） | 26.0 / 0.0 |

前三个是本轮 A/B 主体；223757 仅作 non-regression control（生产仍走 v3，不强迫走 v1）。

## 运行环境

Windows 本机 `python 3.12.10` + `numpy 1.26.4`。报告 JSON 须 `utf-8` 读取（Windows 默认 GBK 会炸中文）。
