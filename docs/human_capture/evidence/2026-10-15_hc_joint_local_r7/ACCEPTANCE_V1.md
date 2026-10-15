# HC-JOINT-LOCAL-01 R7 唯一验收表 v1（2026-10-15）

范围：联合录制本机会话命名与面板拉回编排的单一身份（R6 复盘 A6 的根因修复）。
只判本轮 PC 侧命名/守卫/文案/测试与面板行为对照；EXE 生效、真机改后新录、现场数据处置、
独立复审各自单列。

| ID | 判据 | 结果 | 证据 |
|---|---|---|---|
| R7-01 | 根因可复现：同一段录制在面板出现「板端行 local=false + 本地 local-only 行」两行 | **PASS** | `PANEL_ROWS_BEFORE.json`、README 现象核对 |
| R7-02 | 本机会话目录名 = 板端 sid（与面板 `local.get(sid)` 同一键）；输出根不再出现 `joint_*` | **PASS** | `joint_capture.py::_run`；`joint_capture_test.py` 目录名/无 `joint_*` 双断言 |
| R7-03 | 板端 sid 越界（非 `[A-Za-z0-9_-]{1,100}`）立即失败：不落任何路径、不发起拉回 | **PASS** | `test_unexpected_board_sid_is_rejected_without_writing` |
| R7-04 | 改名后面板同一 sid 只一行且 `local=true`（隔离临时根 + 真板只读 GET） | **PASS** | `PANEL_ROWS_AFTER.json` |
| R7-05 | 回归：`joint_capture_test` 8、`console_html.test.js` 17、`console_test.py` 7，全 exit 0 | **PASS** | `TESTS_joint_capture.log`、`TESTS_console_html.log`、`TESTS_console_py.log` |
| R7-06 | 文案一致：联合页/README 说明目录名=板端会话号；页内 `joint-completed` 消息 sid 无 `joint_` 前缀 | **PASS** | `joint_capture.html`、`README.txt`、`console_html.test.js` |
| R7-07 | 冻结 `Console.exe`/`LiDAR_Console.zip` 重打；冻结 `--check-joint-capture` exit 0（`page_ok`+`page_version` 3/3+`joint_fetch_ok`）；重打后 zip 内源码副本与树逐文件同哈希 | **PASS** | `BUILD.json`、`BUILD_BEFORE.json`、`JOINT_PROBE_FROZEN.json`、`TEST_EXIT_CODES.txt`、`MAKE_RELEASE.log`、`PYINSTALLER_R7_stage2.log` |
| R7-08 | 真机：改后新录一段 → 面板单行、无第二份目录 | **NOT_RUN**（须用户实际录一段；重打已完成并已重启总控制台） | — |
| R7-09 | 现场已存在重名副本（142730/111738 各两份、142227 一份 joint_）处置 | **BLOCKED**（需 sid+字节+sha256 清单 + 用户明确确认） | README「限制与未做」 |
| R7-10 | 独立复审（只读） | **NOT_RUN** | — |
| R7-11 | 重打后重启总控制台：本机联合录制服务在线、idle、输出根 = 面板同一物理目录 | **PASS** | `RESTART_CHECK.txt`（Console.exe pid 41648，8901 监听，`/api/status` state=idle、output_root=`D:\Code\ldiar\data\sessions`= `captures\remote` 联结目标） |
| R7-12 | 合并后复验（并行工作流的相机落盘并入）：源码 10/17/7 全 exit 0；运行中的冻结 exe 内 R7+R8 代码可观测（`/api/camera` 会话专属 404 vs `/api/bogus` 通用 `not found`；页面含两轮文案） | **PASS** | `TESTS_*_POST_MERGE.log`、`RUNNING_EXE_PROBE.txt`、`running_exe_probe.py` |

判定：R7-01～R7-07、R7-11、R7-12 PASS，R7-08/R7-10 NOT_RUN，R7-09 BLOCKED；**SUBMITTED，未 ACCEPTED**。
R7-05 的 14:43 日志为 R7 当轮记录（不覆盖）；合并后另有 `*_POST_MERGE` 一轮。
未改板端/驱动/`fetch.py`/数据格式/模型/GT/旧证据，未 commit/push/部署/采集。
