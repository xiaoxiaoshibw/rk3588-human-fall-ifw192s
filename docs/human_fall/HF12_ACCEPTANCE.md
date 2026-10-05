# HF-12 感知链前置滤波降噪 / v1

2026-10-05 用户明确授权“好的定制工单并且开发”。writer：OpenCode（`opencode-go/deepseek-v4.1-flash`，本会话）。本表为唯一现行验收表；表中 PASS/FAIL 为作者自验，外部独立复审与设备/实机另行安排，不自行宣布 ACCEPTED。作者自验轮次：R1，见 `returns/HF-12.md`。

| ID | 可观察要求 | 覆盖/证据 | 当前结果 |
|---|---|---|---|
| H01 | 位置与顺序：denoise 在有限值/`max_points` 抽稀/距离带之后、高度带/背景/聚类之前；`denoise_enabled=false`（含默认）时不启用，输出除新增 `settings`/`quality.denoise` 键外与改前一致；core 默认关闭。 | 新增测试（默认=显式关闭逐字节相等）；`00_diag.md` M01 | PASS 作者自验（测试 16/16，exit 0） |
| H02 | 算法：孤立点删除、密集簇保留；跨体素相邻点相互支持；`min_neighbors=1` 全保留；确定性；空云/单点边界。 | 合成测试 `denoise_mask` + 快照 | PASS 作者自验（含超网格回退路径；探针三半径与旧循环逐点相等） |
| H03 | 参数与兼容：`denoise_enabled` 非 bool、`denoise_radius_m` 非正/非有限、`denoise_min_neighbors` 布尔/非整数/小于 1 均拒绝；未知键仍拒绝；旧快照 `settings` 回灌可解析。 | `resolve_settings` 负例测试 | PASS 作者自验 |
| H04 | 顺序不变量：降噪先于高度带与背景扣除（下方点可作上方点的邻居；背景点在扣除前参与支撑）；有/无地面时降噪计数一致。 | 合成测试（`00_diag.md` M03/M04） | PASS 作者自验 |
| H05 | 快照：schema_version=1、`validate_snapshot` 通过、`dumps_strict` 无 NaN 且两次运行一致；`evidence_indices` 仍映射原始输入点云。 | 测试 | PASS 作者自验 |
| H06 | 质量块：`quality.denoise` 六字段齐全且与实测计数一致；关闭时 dropped=0；`perception.yaml` 启用配置经 `load_config`+`resolve_settings` 解析为 true/0.1/2。 | 测试 + 配置 | PASS 作者自验（320/300/20 计数；配置 true/0.1/2） |
| R01 | 回归：`python -B -W error -m unittest discover -s src/human_fall_detection/tests` 全过；改前/改后同入口对照；无无关文件改动。 | 改前 488 OK / 改后 504 OK（=488+16），均 exit 0；`git status` 仅本单 6 路径 | PASS 作者自验 |
| S01 | 流程：ponytail（full）已加载并记录路径；基线/SHA、命令与退出码、日志齐备；不 commit/push/reset；不越界（不改配平/跟踪/网页/驱动/旧证据）。 | `returns/HF-12.md`、`evidence/2026-10-05_hf12_r1/` | PASS 作者自验（外部独审 NOT_RUN） |
| D01 | 设备/实机/物理/部署/采集 | 本单只离线软件，不以合成 PASS 代替 | NOT_RUN |

## 变更记录

- v1 2026-10-05 建立（HF-12 首次授权；范围=感知链 `build_snapshot` 前置孤立点去噪 + `perception.yaml` 启用 + 集中测试）。
- v1 结果同步 2026-10-05：H01–H06/R01/S01 填作者自验 PASS，D01 NOT_RUN；未改任何判据。开发中发现的 v1 键打包缺陷与性能问题保留在 `evidence/2026-10-05_hf12_r1/06_v1_defect_repro.*`。
