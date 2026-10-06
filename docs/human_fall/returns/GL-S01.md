# GL-S01 回传

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：GL-S01 / r1 / OpenCode（opencode-go/deepseek-v4.1-flash，本会话）/ 2026-10-05（Asia/Shanghai）。
- 验收表路径 / 版本 / SHA：`docs/human_fall/GLS01_ACCEPTANCE.md` / v1 / `15F2198A59A27A3C953BE6F9DFC929471FD4CF389D8F336937390CC217EB4E84`（提交时）。
- 执行方式 / 实际会话与模型：opencode Code Mode 单会话，模型 `opencode-go/deepseek-v4.1-flash`；无外部 CLI 派工。
- 状态：SUBMITTED；软件逐条自验结果见下；外部独立复审 NOT_RUN，不自行宣布 ACCEPTED。
- 起始 branch/HEAD / 工作树 / 范围差异 / SHA：`master` / `8676bb479d4ae35cf22075cfe70225cf2220572a`；工作树保持原有 dirty/untracked；变更前后 SHA 见 `evidence/2026-10-05_gl_s01_r1/00_scope_baseline.md`；`floor_detector.py` 未修改（`72CE790F...`）。
- ponytail：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（skill 工具加载，full）。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| 223757 被报"没有连续地面" | v1 用 25cm 连通组件同时承担地面身份与 ROI 可用性两个概念，薄层地面被障碍切碎时无法区分"身份失败"与"ROI 不足" | `leveling.run_job` auto 分支错误消息；validation 页面文案；操作者对采集/场景判断 | 新增 `floor_sheet.py` A/B 分层；auto 改调 v2 入口；失败语义三分 | v1 `detect_floor_regions` 与全部 B 层门冻结；v1 成功路径逐字返回 |
| 探针局部法向取列错误（error 列为最大特征向量） | eigh 特征向量矩阵列序理解错误 | 只读探针 01/06；若复制进生产会令干净格几乎为空 | 生产实现 `_clean_cells` 明确 `vectors[:, 0]`；回归 `test_clean_cell_normal_direction_regression` | 干净格定义与 v1 相同 |
| 探针小碎片误触发 gap 门 | gap 统计未区分显著碎片 | 只读探针 A 层判定 | 生产只统计显著碎片（≥0.25m²）对；回归 `test_small_satellite_fragment_ignored` | 大碎片间缺口仍被评估 |
| 桥接语义在探针中未经真实触发 | 探针四会话 `bridging_needed=False` | 正式路径不可证安全 | 合成 wall/void/宽缺口用例定界：走廊必须全观测 + 触面格比 ≥0.5 + 宽度 ≤4 格 | 未触发时零行为差异 |

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码SHA |
|---|---|---|---|
| `pc_apps/human_replay/floor_sheet.py` | 新建：A 层身份 + B 层支撑检查 + `detect_floor_regions_v2` | 本单新增 | `92D2ED105AC98FAAD68C2AD182DBC8A160DDBB08D4EE57AEA424CF3591CF6793` |
| `pc_apps/human_replay/floor_sheet_test.py` | 新建：12 项合成/边界/2 bug 回归 | 本单新增 | `0C6E311E652BBD833024237BB297F1823DEECFCBA79165D7FDFDFC40BB92A452` |
| `pc_apps/human_replay/leveling.py` | auto 分支改调 v2 入口；`code_files` 纳入 `floor_sheet.py` | 仅这两处；四区人工路径/数学不动 | `E01D5266B373EF89EACC214912B82E412EB06608B752243DE45C45769FAF264A` |
| `pc_apps/human_replay/validation.py` | `floor_identified` 接受 `lowest_floor_sheet_v2` | v1 分支不变 | `FF7A51478D2AC64BB7352CBC68CE30163662E7FDA2D65267EFAE000AAC2063D8` |
| `docs/human_fall/{WORKFLOW.md,tickets/INDEX.md,tickets/GL-S01_floor_sheet_v2.md,GLS01_ACCEPTANCE.md,returns/GL-S01.md}` | 流程与记录 | 新增条目 | 见各文件 |
| `docs/human_fall/evidence/2026-10-05_gl_s01_r1/` | 基线、golden 脚本与日志、全量回归日志、本回传引用 | 本单新增 | `00_scope_baseline.md` |

输入输出/单位：与 v1 相同（源点公尺、display 系名义 R、帧序不重排）；v2 只在检测入口内计算，不改导出/报告数学。

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | 结果 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| A1 合成回归（12 项） | synthetic | `python -B -W error -m unittest discover -s pc_apps/human_replay -p floor_sheet_test.py -v` | PASS（12/12，exit 0） | `04_all_replay_tests.log`；源 `0C6E311E...` |
| A2 223757 golden | offline 真实 capture | `python -B docs/human_fall/evidence/2026-10-05_gl_s01_r1/01_golden_v2_check.py` | PASS（`INSUFFICIENT_CLEAN_ROI_SUPPORT: clean_cells=6 independent=0 min_sep_m=0.354 condition=0.162`；v1 仍 `floor_regions_invalid`） | `02_golden_v2.log`（`A9EB0C33...`）/`03_golden_v2.json`（`4A79B385...`） |
| A3 三会话不回归 | offline 真实 capture | 同上 + `leveling_test.py` | PASS（三个 sid 的 v2 逐字返回 v1 regions/candidate，kind=`lowest_connected_floor_v1`；HTTP auto 路径 OK） | 同上 + `04_all_replay_tests.log` |
| B1 B 层门不降 | 源码/测试 | `floor_sheet.py` 直接引用 `floor_detector.PROFILE`；SHA 对照 | PASS（`floor_detector.py`=`72CE790F...` 未变；四区门常数与测试断言在 `floor_sheet.py`/`floor_sheet_test.py`） | `00_scope_baseline.md` |
| B2 桥接边界 | synthetic | `floor_sheet_test.py` 3 项桥接用例 | PASS（wall 触面 explained 合并 ≥0.5m²；void/宽缺口/稀疏杂点 unexplained） | `04_all_replay_tests.log` |
| C1 语义三分 | synthetic + offline | 测试 + golden | PASS（A fail→`floor_regions_invalid: floor identity failed`；B fail→`INSUFFICIENT_CLEAN_ROI_SUPPORT`；双过→kind v2） | 同上 |
| C2 消费者与全回归 | offline | `python -B -W error -m unittest discover -s pc_apps/human_replay -p "*_test.py" -v` | PASS（33 项全 OK，exit 0） | `04_all_replay_tests.log`（`B953D9A4...`） |
| C3 审计字段 | 源码/测试 | `leveling.py` code_files；v2 candidate 字段 | PASS | 见变更表 SHA |
| S01 流程 | — | 本回传 + evidence | PASS 作者流程；外部独审 NOT_RUN | 本文件 |
| D01 设备/物理 | device | 未运行 | NOT_RUN | — |

回归范围：`floor_sheet_test`(12) + `floor_detector_test`(3) + `leveling_test`(4) + `validation_test`(2) + `leveling_auto_test`/`sessions_test` 等共 33 项全过；未改冻结资产/captures/旧证据。

## 未闭合与限制

- **错误面残余风险（已知）**：地面完全不可见、最低候选面是带内大台面时，A 层无法仅凭几何区分；现由最低面/高度带（0.8–1.8m）/主导性门兜底，阈值为 provisional，未做专门反例标定。合成用例③只覆盖"多块台面 + 空缺口"，不覆盖"单块大台面冒充地面"。
- **桥接在真实数据未触发**：四个会话 `bridging_needed=False`；桥接安全性目前只有合成证据。正式启用条件（走廊全观测/触面格比/宽度≤4格）已在代码与测试固化。
- **UI kind 未扩展**：`leveling.js` 客户端的 `lowest_connected_floor_v1` 判断未加 v2；backend `floor_identified` 已支持，验证模式四个固定会话永不触发 v2 成功。如需 UI 完整支持，另开小改。
- **223757 仍拒绝**（正确）；采集侧建议（静止、地面无遮挡）不变。
- 设备/物理/部署/采集 NOT_RUN。

## 交给 Codex 独立复审

- 现行验收表与本轮变更记录：`GLS01_ACCEPTANCE.md`（`15F2198A...`）；本回传。
- 根因诊断/完整入口检查证据：`evidence/2026-10-05_gl_floor_diag_r1/`（只读探针）与 `evidence/2026-10-05_gl_s01_r1/`（golden + 全量回归）。
- 源码差异与 SHA 证据：`00_scope_baseline.md`（前后 SHA；`floor_detector.py` 未变）。
- 原始日志索引：`02_golden_v2.log`、`03_golden_v2.json`、`04_all_replay_tests.log`。
- 当前工单下一步：外部只读复审；复审后按结论决定是否补"单块大台面"反例与 UI kind 小改。

## 补充验证 r1a：源码版总控服务端（2026-10-05，用户要求先不动打包）

- 方法：按 `console_gui.py` 相同入口 `runpy` 加载 `pc_apps/human_replay/human_replay_lib.py`，`Handler` 绑临时端口（不动 8901、不动任何 dist/快捷方式），走真实 validation HTTP 路由。
- 结果（4/4 PASS）：`/api/validation/sessions` 四个会话在线；`/api/validation/latest?sid=…203349` 存盘结果恢复且 `floor_identified=true`；`/api/validation/run` auto 受理；223757 job 稳定失败于 `INSUFFICIENT_CLEAN_ROI_SUPPORT: clean_cells=6 independent=0 min_sep_m=0.354 condition=0.162`，且**未产生任何 `captures/leveled/<job>` 目录**（job `e6870d59a6a749348829a4480e543afc` 经查不存在）。
- 结论：源码版总控的"算法验证"已实际运行 v2；打包 exe 仍为旧快照（本单未重打包，结论不变）。
- 产物：`evidence/2026-10-05_gl_s01_r1/05_source_service_verify.py`、`06_source_service_verify.log`、`07_source_service_verify.json`。

## 补充验证 r1b：打包切换（2026-10-05，用户授权"好的开始，注意保留后路"）

- 新构建：`pc_apps/console/dist/gl_s01/Console.exe`（PyInstaller 6.21.0，全新目录，未覆盖任何既有 dist），SHA256 `6974C88F270A9F2A57EEB439F0EB5D63419610D1658D288E9D113E5F386B0497`；`Analysis-00.toc` 确认含 `human_replay/floor_sheet.py` 与 `floor_detector.py`。
- 打包版真实 HTTP 验证 3/3 PASS（服务由新 exe 自己启动）：validation sessions 含四会话；auto run 受理；223757 稳定 `INSUFFICIENT_CLEAN_ROI_SUPPORT: clean_cells=6 independent=0 min_sep_m=0.354 condition=0.162`；失败 job `54202faa...` 未生成任何 `captures/leveled` 目录。
- 切换与回退：桌面 `总控制台.lnk` 由 `dist\gl_v01_floor_r2\Console.exe` 切到 `dist\gl_s01\Console.exe`；切换前快捷方式副本 `dist\gl_s01\总控制台_rollback_gl_v01_floor_r2.lnk`；回退命令见 `dist\gl_s01\ROLLBACK.txt`；`gl_v01_floor_r2/gl_v01/gl_w01/hr02_offline/dist\Console.exe` 全部未改动。
- 产物：`08_packaged_verify.py`、`09_packaged_verify.json`、`10_packaged_verify.log`、`11_package_record.md`。

## 补充验证 r1c：标准目标 dist\Console.exe 同步（2026-10-05，用户"打包进exe新算法"）

- 旧 `dist\Console.exe`（19:06 构建）备份为 `dist\Console_backup_20261005_1906.exe`；
- 以当前源码重打包 `dist\Console.exe`（SHA256 `DE9F13E41ABA2C548E3843CA529131C11ABC17044989FCDACAA82D3735E5C9E3`），TOC 含 `floor_sheet.py`；
- 打包版实测 3/3 PASS：223757 稳定 `INSUFFICIENT_CLEAN_ROI_SUPPORT: clean_cells=6 independent=0 min_sep_m=0.354 condition=0.162`，无产物落盘；
- 桌面快捷方式保持 `dist\gl_s01`（v2）；回退可用 canonical 备份或 `gl_v01_floor_r2`；
- 产物：`12_canonical_verify.json`、`13_canonical_verify.log`、`11_package_record.md` 追加段。
