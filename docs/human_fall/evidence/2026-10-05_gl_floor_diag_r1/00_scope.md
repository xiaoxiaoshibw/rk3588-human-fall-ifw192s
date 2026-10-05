# 223757 自动找地面失败 · 只读诊断 r1（范围与基线）

- 日期：2026-10-05（Asia/Shanghai）。
- 用户指令：对“我们的算法怎么优化”回复中的 P1（只读诊断 223757）明确“好的开始”。本单仅诊断，不写生产代码/测试/配置/状态，不改 `captures/`、旧 evidence、`pc_apps/human_replay/`。
- 对象：`cap_20261002_223757` 在 GL-V01 r2 中被脚本误随动态 SESSIONS 列表执行时失败（范围外，保留原错误记录）：`floor_regions_invalid: no connected unobstructed floor component; [{'offset_m': 1.2933695427321978, 'clean_floor_cells': 6}, {'offset_m': 1.0753702012470485, 'clean_floor_cells': 0}, {'offset_m': 0.8625756196676303, 'clean_floor_cells': 0}]`。
- 目标：分解失败原因（每格被哪条门拒绝、最低面 6 格的空间分布、近失格），判断是“检测器缺陷”还是“场景无可用的连续可见地面→正确显式拒绝”。不调门、不生成配平产物、不评分三估计器。
- 方法：按 `floor_detector.detect_floor_regions` 的同一常量与顺序，在独立脚本中复刻带计数的检测流程（直接 import 其 `PROFILE`/`components`，不修改源文件）。参数与 r2 运行一致：pitch=26.0、roll=0.0、FIT 帧排除 `{(n-1)//3, 2*(n-1)//3, n-1}`。

## 基线（2026-10-05 未改）

- branch/HEAD：`master` / `8676bb479d4ae35cf22075cfe70225cf2220572a`；工作树保持原有 dirty/untracked（未增删）。
- 相关文件 SHA256：
  - `pc_apps/human_replay/floor_detector.py` = `72CE790F656FAF60A5122BCE550073412945A1A4C18D9B6195BA29928CE9B06A`
  - `pc_apps/human_replay/leveling.py` = `4B3FAAFB2EFD688B3FF3AC00F247AEDBFB676573754C25AD3CBF6E4BF942EBDC`
  - `docs/human_fall/evidence/2026-10-05_gl_v01_r2/04_auto_sessions.py` = `3A02A2ACFACC3D372E82D953132B68FE96E7F15BD2C746E350175D77E013FB85`
  - `captures/remote/cap_20261002_223757/meta.json` = `71915D5181B8FC409D83A8E1650671801D2D50CF09EF4A3832D43B51EC3F4CA8`
  - `captures/remote/cap_20261002_223757/points.bin` = `8AFB660B7BF0631462D4CDE6F82BD89884B2E83ACEA1DA25C07316C87B5FBB37`
- ponytail：已按全局规则加载 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（skill 工具，强度 full）。使用路径：只读复刻、最少新增文件（1 脚本 + 本范围文件 + 运行产物），不引依赖、不改生产、不建抽象。

## 产物

| 文件 | 内容 |
|---|---|
| `01_diag_223757.py` | 只读诊断脚本（复刻检测并逐格计数） |
| `02_diag.log` | 运行摘要（stdout 落盘） |
| `03_diag.json` | 机器可读明细（平面/格/近失/连通域） |
| `04_summary.md` | 结论与归因（人工撰写） |

## 边界

- 不涉及设备/采集/部署/网络/driver；不使用留出帧做统计之外的事（本诊断只读全部 FIT 帧，不改变任何选择规则）。
- 失败为显式拒绝语义，本诊断不构成对 GL-V01 验收或 223757 可用性的新结论；D01 仍 NOT_RUN。
