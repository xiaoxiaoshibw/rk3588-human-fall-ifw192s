# HF-12 独立复审 / H01–H06、R01、S01 软件范围 PASS

- 工单 / 轮次 / 唯一验收表：`tickets/HF-12_point_denoise.md` / R1 / `HF12_ACCEPTANCE.md` v1，SHA256 `962981B9…F73E`（本会话重算一致）。
- 复审者 / 角色：OpenCode `opencode-go/deepseek-v4.1-flash` 复审会话（2026-10-05 用户明确“你负责独立复审”）。**本会话未参与 HF-12 的实现与自验**；全部结论来自本会话独立复跑与只读审查（HEAD 基线 blob、当前工作树、作者证据抽查与关键脚本复跑）。
- 独立性说明：审者模型/提供方与写者相同（OpenCode Go Flash），但为独立会话；作者日志仅作对照、不作通过依据。是否满足项目独立性要求由用户/Codex 裁定，此处如实记录。
- 结论：**H01–H06 / R01 / S01 独立复审 PASS，无软件返工项；D01（设备/实机/物理/部署/采集）维持 NOT_RUN；不自行宣布整单 ACCEPTED。**
- 环境与基线：Windows Python 3.12.10 / NumPy 1.26.4（桌面）；`HEAD 0d5ab42…` 未变、无暂存内容；基线 `01_baseline.txt` 的改前源码 SHA 经验证等于 HEAD blob（lidar_candidates `447E4003…`、perception `70C8F04B…`）。板端 Python 3.8.10 / NumPy 1.17.4 未复跑；新增代码只用 1.17 已有 API（静态检查）。

## 逐条独立复核

| ID | 本会话复跑/审查（证据） | 结果 |
|---|---|---|
| H01 | 默认关闭（含 ground+background+NaN+超距+抽稀夹具）输出与 HEAD 版本剥离 `settings.denoise_*` / `quality.denoise` 后逐 JSON 相等；关闭质量块为 no-op；代码顺序 距离带(682–684)→denoise(694–702)→高度带(708–714)→背景(716–719)→聚类(721–722)。`05_review_boundaries.*` | PASS |
| H02 | 稠密路径 4 个半径与暴力体素计数逐点相等；打包回退（30 m 跨度 / r=0.01）与暴力相等；跨体素互撑、单点、min=1、空云、确定性。同上 | PASS |
| H03 | 0 / NaN / bool / 小数 / 未知键拒绝；np.int64 接受；改前 settings 回灌。同上 | PASS |
| H04 | 独立数值夹具：高度带下方点先作支撑后被剔、背景点先作支撑后被扣（顺序若相反则结果应为 0 候选，反例成立）。同上 | PASS |
| H05 | `validate_snapshot`、两次构建严格 JSON 相等、无 NaN/Infinity；`evidence_indices` 回映原始输入；预览 `validSnapshot` 只校验固定键（`webui/human_fall_preview/human_fall_lib.js:105-115`）。同上 | PASS |
| H06 | `quality.denoise` 计数与重算掩码一致；关闭 dropped=0；`perception.yaml` 解析为 enabled/0.1/2。同上 | PASS |
| R01 | 新增 16/16 OK；全量 504/504 OK（作者改前 488 OK 为对照）；两被审文件 `git diff` 仅意图内 hunk（`01b_diff_tracked_files.txt`）。`02`/`03` | PASS |
| S01 | 基线/命令/退出码/探针/失败复现齐备；8 个最终产物 SHA256 本会话重算与 `07_sha_after.txt` FINAL 快照逐一相等；`06_v1_defect_repro` 复跑复现 [6,6,3]/[T,T,T]。`01`/`04`/`06` | PASS |
| D01 | 未部署、未采集、未上板、未改驱动/网络。 | NOT_RUN（维持） |

## 观察（非阻断）

1. 体素计数是精确半径邻域的超集：半径内邻居不会漏计；相邻体素内实际超过半径的点可能被计入（如 0.19 m @ r=0.1；轴向 <2r、对角更大）。已在代码 docstring 与工单/回传明示，现场调参需知道该粗粒度上界。
2. 极小半径（如 1e-6 m）通过 `resolve_settings`，但运行到 `build_snapshot` 会触发 `radius_m too small for the point extent`（有界回退 2^20 上限）。工程默认 0.1 与合理配置不受影响；保留为已知限制即可。
3. `denoise_radius_m=True→1.0`、`None→TypeError`：与既有 `_POSITIVE` 键同一转换/校验风格，非本单新增问题。
4. 复审期间共享树存在 GL-S02 等外部并发变化（如 `returns/GL-S02.md`）；非 HF-12 操作，保留不归因。HF-12 自身产物在复审时刻哈希与提交一致，未被外部改动。

## 边界与限制

- 合成探针非真实噪声；板端/真实数据效果仍属 D01 NOT_RUN。计时受本机负载影响（本次 9.6 ms/帧 vs 作者 7.0 ms，机器/负载差异），不作为性能验收；确定性计数与作者证据逐项一致。
- 作者 00–07 证据为抽查 + 关键脚本完整复跑，不是原始字节级全审计。
- 本次复审未修改任何生产代码、测试、验收表、回传与旧证据；新增仅本目录。

## 复审证据索引

- `00_review.md`（本文件）
- `01_scope_hashes.txt`、`01b_diff_tracked_files.txt`：HEAD/状态/范围/哈希/diff
- `02_tests_hf12.txt`：新测试 16/16
- `03_tests_full.txt`：全量 504/504
- `04_probe_rerun.txt`：探针复跑（计数与作者逐项一致）
- `05_review_boundaries.py` / `05_review_boundaries.txt`：30 项独立边界检查
- `06_v1_repro_rerun.txt`：v1 缺陷复现复跑
- `_head_lidar_candidates.py`：HEAD 基线 blob（供复核）
