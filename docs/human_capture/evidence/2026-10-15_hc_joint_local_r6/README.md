# 2026-10-15 R5 复盘整改与重打（HC-JOINT-LOCAL-01 R6）

**触发**：用户"是不是代码架构问题，深入排查审查" → R5 复盘给出 A1–A8；随后用户"逐个修复然后审查 返工 打包 没问题就不返工"。

## 本轮整改（按复盘编号）

| # | 级别 | 位置 | 修复 | 证据 |
|---|---|---|---|---|
| A1 | 高（隐患） | `pc_apps/human_limb/limb_server.py` | 冻结守卫：`sys.frozen` 时 import 即 `SystemExit` 明确报错（原模式会在打包后静默起错进程）；源码运行不受影响 | 双向探针（源码 import OK / `sys.frozen=True` → 守卫退出） |
| A2 | 中 | `console_gui.py` + `joint_capture.py` | 拉回目录单源化：`_start_joint_capture_server` 用 `_replay_dir()` 的解析结果经 `fetch_dir=` 传入；`joint_capture.load_fetch(fetch_dir)` 成为唯一加载器（pull 与探针共用）；缺省仍按源码/`_MEIPASS` 回退 | `R6_DIFF.patch`；单测两分支 |
| A3 | 中 | `joint_capture.py::Recorder._run` | `joint.json` 补终态：`completed/failed` + `finished_iso/radar_frames/bytes/error`；写失败仅跳过（不影响已落盘会话数据） | 单测成功/失败双断言；真实 E2E |
| A4 | 中 | `console_gui.py --check-joint-capture` | 新增 `joint_fetch_ok` 探针（`load_fetch` 加载 + `process_session` 可调用，不触网）并纳入 exit 条件——**这类集成点 bug 下次重打即被拦** | `JOINT_PROBE_SOURCE.json`、重打后冻结探针 |
| A7 | 低 | `human_replay_lib.py` | 删除未使用的 `import subprocess` 残留 | `R6_DIFF.patch` |
| A8 | 低 | `console_gui.py` | `--check-*` 报告文件已存在 → 可读提示 + exit 2（原 FileExistsError traceback）；新增 `_write_check_report` 助手共用 | `CHECK_REPORT_EXISTS_BEHAVIOR.txt` |

## 未修项与理由

- **A5（板 IP/端口硬编码散落 5+ 处）**：修法是"注入机制"（console_gui 组装 shell_url 时下发默认值或统一读 config），涉及 4+ 文件与页面协议，按用户"没问题就不返工"原则本轮不动，留作专门轮次。
- **A6（面板 `cap_*` 与联合 `joint_*` 两条拉回编排并存）**：行为已正确且 R5 已文档化差异；整并需要新状态迁移，不动。

## 验证（本机；冻结整链与独审 NOT_RUN）

| 项 | 结果 | 日志 |
|---|---|---|
| `joint_capture_test.py` | **7 PASS**（+1：`load_fetch` 显式目录） | `TESTS_joint_capture.log` |
| `console_test.py` | **7 PASS** | `TESTS_console_py.log` |
| `console_html.test.js` | **16 PASS** | `TESTS_console_html.log` |
| sessions+fetch（python） | **18 PASS** | `TESTS_sessions_fetch.log` |
| 源码 `console_gui.py --check-joint-capture` | exit 0；`page_version` 3/3；**`joint_fetch_ok: true`** | `JOINT_PROBE_SOURCE.json` |
| 检查报告重复指旧文件（A8） | 可读提示 + **exit 2**（无 traceback） | `CHECK_REPORT_EXISTS_BEHAVIOR.txt` |
| human_limb 冻结守卫双向探针 | 源码 import OK；冻结形态明确退出 | 见 ACCEPTANCE R6-04 |
| 真实端到端（打桩板端 + 真实 fetch 只读复制 → 临时目录，跑完清理） | **completed**；`joint.json` 终态；`points.bin` 255,522,036B 整；板端状态机未动 | `REAL_E2E_TMP_R6.json` |
| 重打后冻结 `--check-joint-capture` | **exit 0**；`page_version` 3/3；**`joint_fetch_ok: true`** | `JOINT_PROBE_FROZEN.json` / `PROBE_EXIT_CODES.txt` |
| 重打后冻结 `--check-startup` | exit 1（既有缺 `cap_20261013_094333`，非本轮） | `STARTUP_PROBE_FROZEN.json` |

变更文件 SHA256：见 `FILE_SHAS.json`（含并行工作流 hunk 说明）；差异 `R6_DIFF.patch`（对 HEAD，含前几轮未提交累积；生成于并行改动前，最终差异见「审查与返工」节）。
备注：编辑期间 `joint_capture.py` 两次出现写入竞态残片（尾部杂散行），均已字节级清理、`py_compile` + 全测试复验 + 双读 SHA 稳定后才入库；终态哈希即 `FILE_SHAS.json`。

## 审查、返工与并行写入时间线

审查发现：`console_gui.py` 现哈希 ≠ `FILE_SHAS` 快照 → 逐层定位，确认为**并行工作流在共享文件上的持续写入**（learn 扩展 hook：`sidequests/human_fusion_lab_next/learn/r01`，由 `CURRENT.json` 存在性门控；当前不存在 → 停用态；其 handler 定义已接受全部新参数）。时间线：

| 时点 | 事件 | 处置 |
|---|---|---|
| 12:5x | 本 R6 三处 hunk 写入完毕（console_gui 29801E12…/20411B） | 基线快照 |
| 13:00:25 | 并行写 #1（19682E84…，manifest/index 参数） | 落在 stage1（13:02）构建窗口内 → **判定 stage1 不可复现、弃用** |
| 13:07:57 | 并行写 #2（D42315EA…，LEARN_RUN_ID/learn_run/4 参 handler） | PKG 阶段（13:09–13:11）读取 → 随 stage2 exe 与 zip 冻结 |
| 13:07–13:11 | **返工重打 stage2**（PyInstaller + make_release） | exe=B2457635…；冻结双探针全绿 |
| 13:17:52 | 并行写 #3（E3FAC7D9…/22533B） | **未入本轮产物**；属该工作流自管打包 |

- 复核：`console_test` 在并行各版本均 7/7 通过（`REWORK_CONSOLE_TEST_after_parallel_edit.log`）；源码双探针不变；`--check-startup` 中 `_start_fall_server` 照常启动（`fall_port` 有效）。
- 判定终局：写 #1 触发返工（stage1→stage2）；写 #2 已被 stage2 产物正确冻结；写 #3 之后的迭代**不再追入本轮产物**（避免递归追逐/半成品入包），该工作流的后续打包由其自身负责。stage3（13:15）PyInstaller 因缓存命中为空转（无新 exe），仅重生成 zip（源码条目同 stage2 冻结版）。
- 归档：stage1 探针 `*_stage1.json`、stage1 exe `bak-20261015_r6_stage1`、终态 exe 副本 `bak-20261015_r6_stage2`、zip-vs-树差异 `PARALLEL_CONSOLE_GUI_ZIP_vs_TREE.diff`（38 行）、`FINAL_FACTS.json`。

## 重打包（stage2 exe + 13:15 重生成 zip = 终态）

| 产物 | 字节 | sha256 | 时间 |
|---|---|---|---|
| `dist/Console.exe`（终态） | 193,807,707 | B2457635…D688BD | 2026-10-15 13:11:09 |
| `dist/LiDAR_Console.zip`（终态） | 151,034,726 | 495B8901…D232CB | 13:15:17（重生成） |
| `dist/Console.exe.bak-20261015_r6_stage2` | 193,807,707 | B2457635…D688BD | 终态 exe 副本 |
| `dist/Console.exe.bak-20261015_r6_stage1` | 193,805,296 | F5BD3D53…56EC9C | 13:02:42（首次重打，竞态弃用） |
| `dist/Console.exe.bak-20261015_before_r6` | 193,806,359 | DDC5501A…67FB4C | 11:33:33（R5 版） |

- 构建日志：stage2 含 `Building because … console_gui.py changed`；`PYINSTALLER_EXIT=0`、`RELEASE_EXIT=0`；stage3（13:15）PyInstaller 空转、make_release 重生成 zip。
- zip 内 `源码/joint_capture.py` 与树头同哈希；`源码/console_gui.py` 为构建冻结版（13:07:57），与树头 13:17:52 并行迭代的差异见 `PARALLEL_CONSOLE_GUI_ZIP_vs_TREE.diff`。
- 生效方式：关闭并重开总控制台（`joint_capture`/`console_gui` 都在 exe 内嵌）。

## 已知限制

- A5/A6 未修（见上）；冻结 exe 内真实「录制→拉回」整链 NOT_RUN。
- `--check-*` 报告 exit 码语义：0=通过、1=功能失败、2=报告文件不可写（已存在）。
- 相机仍不写盘（`camera.mjpeg` 恒 0B 占位，现行设计）；未 commit/push。
