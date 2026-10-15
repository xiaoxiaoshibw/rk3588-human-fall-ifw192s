# 2026-10-15 R7 联合录制雷达被拉两遍（同一份数据两个名字）

**触发**：用户直派「现在视频和雷达实时录制有 bug，雷达数据会被拉两遍但是名字不一样」，
并贴出会话回放面板的行（同一段录制出现两行，帧/时长完全相同）：

| 会话 | 时长 | 帧 | 远端 | 本地 |
|---|---|---|---|---|
| joint_cap_20261015_142730 | 17.8s | 173 | local-only | ✓ |
| 20261015_142730 | 17.8s | 173 | ✓已传 | ✓ |
| joint_cap_20261015_142227 | 12.6s | 123 | local-only | ✓ |
| 20261015_142227 | 12.6s | 123 | ✓已传 | — |
| joint_cap_20261015_111738 | 19.2s | 186 | local-only | ✓ |
| 20261015_111738 | 19.2s | 186 | ✓已传 | ✓ |

## 现象核对（只读本机数据 + 真板登记）

```
captures/remote/cap_20261015_142730/        meta.json 35345  points.bin 237,644,764
captures/remote/joint_cap_20261015_142730/  meta.json 41500  points.bin 237,644,764  ← 同一份雷达
captures/remote/cap_20261015_111738/        points.bin 255,522,036
captures/remote/joint_cap_20261015_111738/  points.bin 255,522,036
```

- 两个目录的 `points.bin` 字节数相同；meta 键集只差 `joint_recording`（联合拉回自己补的溯源块）。
- 目录写入时间：`joint_cap_20261015_142730` 14:27:57（联合拉回），`cap_20261015_142730`
  14:28:17（19 秒后再拉一遍）；`cap_20261015_111738` 14:32:30（11:17 录完约 3 小时后才出现）。
- 真板登记（只读 GET）：`cap_20261015_142730` / `cap_20261015_111738` `download_requested=true`
  `state=transferred`；`cap_20261015_142227` `download_requested` 为空 → 它的第二份确实没被拉。
  `download_requested` 只由 `/api/sync`（面板行点击）与板端 WebUI「触发下载」写，
  联合拉回走 `process_session` 不写它 → 第二份来自**面板行点击**这条拉回路径。

## 根因

同一段录制被安了两个名字：

- 联合录制（`pc_apps/console/joint_capture.py`）把拉回的会话落到 `output_root/joint_<板端sid>/`；
- 板端登记表与回页面板（`pc_apps/human_replay/human_replay_lib.py::_api_sessions`）都按
  **sid 本身**找本机副本：`local.get(sid)`。

于是 `local` 里只有 `joint_<sid>` → 板端行判为「本地无」→ 面板把它当没下过，点一下就
`/api/sync` 再拉一遍（改名为 `cap_<sid>`，默认根目录下就是 `captures/remote/<sid>/`）；
同时那个 `joint_<sid>` 目录被当成本地独有会话又列一行。用户看到的两行、两份 237 MB
即此。旁证：`/api/sync` 的短路条件是 `C.DEST_ROOT/<sid>/meta.json` 存在（`human_replay_lib.py:614`），
改名后天然命中，不再重拉。

R6 复盘已把这条登记为 **A6（面板 `cap_*` 与联合 `joint_*` 两条拉回编排并存）**未修；
本轮即 A6 的根因修复。

## 修复（PC 侧 5 文件，零新依赖、无新状态、不写板）

| 文件 | 改动 |
|---|---|
| `pc_apps/console/joint_capture.py` | 会话目录名 `joint_<sid>` → `<sid>`（与板端登记/面板同名同源）；`sid` 只允许 `[A-Za-z0-9_-]{1,100}`，异常即失败不落路径；模块 docstring 记录约定 |
| `pc_apps/console/joint_capture.html` | `notify_completed` 的 sid 兜底去掉 `'joint_' +` 前缀；页面说明补「目录名 = 板端会话号，拉回后该行直接显示本地 ✓」 |
| `pc_apps/console/joint_capture_test.py` | 钉死新合同：目录名 == sid、且输出根下**不得再出现** `joint_*` 目录；新增异常 sid 用例（不拉回、不落文件） |
| `pc_apps/console/README.txt` | 入口说明改为 `captures\remote\<板端会话号>\` |
| `pc_apps/console/console_html.test.js` | 联合完成消息示例 sid 由 `joint_cap_*` 改回 `cap_*`（真实形态） |

不改：板端、驱动、`fetch.py` 校验/状态机、数据格式、模型/GT、旧证据；`human_replay` 代码零改动
（面板本来就按 sid 找，是本方命名不合）。

## 验证

| 项 | 结果 | 证据 |
|---|---|---|
| 面板行对照（隔离临时根 + 真板 GET，只读） | 改名前：`cap_20261015_142227` `local=false` + `joint_cap_20261015_142227` `local-only` 两行；改名后：一行 `local=true` | `PANEL_ROWS_BEFORE.json`、`PANEL_ROWS_AFTER.json`（`panel_row_probe.py`） |
| `joint_capture_test.py` | **8 PASS**（含新 2 项） | `TESTS_joint_capture.log` |
| `console_html.test.js`（node） | **17 PASS** | `TESTS_console_html.log` |
| `console_test.py` | **7 PASS** | `TESTS_console_py.log` |
| 源码 `--check-joint-capture` 内嵌合同 | NOT_RUN（首轮重打前） | — |
| 真机改后新录一段 → 面板一行 | NOT_RUN（须用户实际录一段） | — |

探针只做 GET（真板 `/api/v1/sessions` + HEAD 文件存在性），临时根在 `%TEMP%`，
未向 `captures/`/`data/` 写任何字节。

## 重打与生效（重打后补记）

`dist/Console.exe` 与 `dist/LiDAR_Console.zip` 已重打（用户选定「重打 EXE/ZIP 并重启控制台」）：

| 项 | 结果 | 证据 |
|---|---|---|
| PyInstaller（stage2，终版） | exit 0；`Console.exe` **193,812,397 B / 2E275737…** | `PYINSTALLER_R7_stage2.log` |
| `--check-joint-capture`（冻结） | **exit 0**；`page_ok=true`、`page_version` 3/3、`joint_fetch_ok=true` | `JOINT_PROBE_FROZEN.json`、`TEST_EXIT_CODES.txt` |
| `--check-startup`（冻结） | exit 1，`real fall replay did not start`——R4/R5/R6 冻结探针逐字同一失败（既有，非本轮回归） | `STARTUP_PROBE_FROZEN.json`、`STARTUP_PROBE_FROZEN_stage1.json` 等 |
| `LiDAR_Console.zip` | **151,042,810 B / 44A9711F…**；`Console.exe`/`joint_capture.py`/`joint_capture.html`/`console_gui.py`/`console.html`/`README.txt` 等 zip 内副本与树逐文件同哈希 | `BUILD.json`、`MAKE_RELEASE.log` |
| 构建窗口噪声 | 首轮重打（`…_r7_stage1`，193,810,755 B）落在并行写入窗口内：PyInstaller 运行中 14:48:32 另一路工作流落了「相机落盘」新版本 → 该轮 exe 与树不一致，弃用（备份 `dist/Console.exe.bak-20261015_r7_stage1`，探针留 `*_stage1.json`）；stage2 前 45 s 抽样确认输入稳定，构建窗口前后输入哈希一致 | `BUILD_BEFORE.json`、`BUILD.json` |
| 重启总控制台 | `Console.exe` pid 41648 起、8901 监听；本机联合录制服务 `/api/status` `state=idle`、`output_root=D:\Code\ldiar\data\sessions`（= `captures\remote` 联结目标，与面板 `C.DEST_ROOT` 同一物理目录） | `RESTART_CHECK.txt` |

## 合并后复验（R8「相机写盘」特性并入后）

R7 改名/守卫与并行工作流的相机落盘特性落在同一段 `_run`：合并后终态
`joint_capture.py = 1FCF83A0…`（含 R7 的 `out_dir = root / sid` 与 sid 守卫 + R8 的
`camera.mjpeg`/`camera_frames.jsonl`/`/api/camera`）。原 14:43 的回归日志按「不覆盖旧证据」
保留，另跑一轮：

| 项 | 结果 | 证据 |
|---|---|---|
| `joint_capture_test`（合并后，10 项） | **10 PASS** | `TESTS_JOINT_CAPTURE_POST_MERGE.log` |
| `console_html.test.js`（合并后） | **17 PASS** | `TESTS_CONSOLE_HTML_POST_MERGE.log` |
| `console_test.py`（合并后） | **7 PASS** | `TESTS_CONSOLE_PY_POST_MERGE.log` |
| 运行中的冻结 exe：R7+R8 代码是否真的在 exe 内 | `/api/camera` 回会话专属 404、`/api/bogus` 回通用 `not found`（路由确在）；页面同时含 R7/R8 文案 | `RUNNING_EXE_PROBE.txt`（`running_exe_probe.py`，纯 stdlib 只读 GET） |
| 总控制台 | 15:02 重启，joint 服务 port 56067、`state=idle`、`output_root=D:\Code\ldiar\data\sessions`（= `captures\remote` 联结目标，与面板 `C.DEST_ROOT` 同物理目录） | 同上 |

（14:59 起过一次实例，15:00 前退出——原因未知（可能被并行工作流或用户关闭），未取到它的探针；
15:02 重起后完成上表探针，exe 哈希即发布版本 `2E275737…`。）

## 限制与未做

- 真机改后新录一段（面板应只一行）**未做**：需用户实际录一段，属现场验收，本轮不冒称。
- **现场 3 组已存在的重名副本**（`cap_...` vs `joint_cap_...`：142730、111738 各两份，
  142227 只有 `joint_` 一份）未动：`captures/`/`data/` 是数据不是工作区，删/移需 sid+字节+sha256
  清单与用户明确确认。处置建议见下。
- 相机在本轮并入的并行改动里改为落盘（`camera.mjpeg` + `camera_frames.jsonl`），该特性由另一
  工作流实现与自验，本轮只保证自己的改名/守卫在合并后仍成立（源码级 + 8→10 项测试）。
- 独立复审 / 板端 / 设备 NOT_RUN；未 commit/push/部署。

## 处置建议（待用户点头）

1. 重打 `Console.exe`/`LiDAR_Console.zip` 并重启总控制台 → 之后新录的联合会话只有一个名字。
2. 已存在的重名副本：删 `cap_20261015_142730`、`cap_20261015_111738` 两个目录即可（
   `joint_` 目录里那份带 `joint.json`/`camera.mjpeg`，是联合会话本体），或反过来删 `joint_` 两份
   并把会话改名——两者数据同源，删前出清单。

## 并行写入观察（如实记录）

本轮编辑期间 `pc_apps/console/joint_capture.py` 被另一路工作流在 14:38:46 与 14:40:29 两次写入
（14:38:46 版把相机帧写入 `camera.mjpeg` + `camera_frames.jsonl`，14:40:29 版撤回）。本轮改动
在上述写入中保留下来；入库文件 SHA 见 `FILE_SHAS.json`，本轮改动片段另存 `R7_CHANGE_HUNKS.txt`
以便被覆盖时回填。技能路径 `C:/Users/30680/.config/opencode/skills/ponytail`（skill 工具加载，full）。
