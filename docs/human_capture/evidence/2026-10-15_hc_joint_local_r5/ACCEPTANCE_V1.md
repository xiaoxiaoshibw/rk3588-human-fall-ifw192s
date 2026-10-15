# HC-JOINT-LOCAL-01 R5 唯一验收 v1（2026-10-15）

范围：错峰联合录制「停止后一次性拉回」失败修复（`_StagedFetch.pull` 由 subprocess 改为进程内官方
`fetch.process_session`）+ 重打 `dist/Console.exe`/`LiDAR_Console.zip` + 现场恢复 11:17 的 `cap_20261015_111738`。
判定基准：PASS 仅代表本机自验与冻结产物检查；冻结 exe 内真实「录制→拉回」整链与独立复审 **NOT_RUN**。

| ID | 验收点 | 结果 | 依据 |
|---|---|---|---|
| R5-01 | 根因（冻结）：`sys.executable -I fetch.py` 子进程 = 再启动一个 Console.exe，fetch.py 从未执行 | PASS | 用户日志子进程 stdout（`mode=SOURCE_BYPASS`、`human_replay 服务 …:51004`、`real fall replay unavailable`）与 `sys.executable` 语义对读 |
| R5-02 | 根因（源码）：py3.11+ `-I` 隐含 `-P`，脚本目录不进 sys.path，`fetch.py` 的 `import config` 必失败 | PASS | 本机实测 `python -I main.py` → `ModuleNotFoundError` |
| R5-03 | `pull()` 进程内 `runpy.run_path` 官方 fetch；异常/失败不抛、返回 `(None, None)` 且原因入 `self.log` | PASS | 源码审读 + `TESTS_joint_capture.log`（新增 2 用例） |
| R5-04 | `FETCH_DIR` 两分支解析：源码=`pc_apps/human_replay`；冻结=`_MEIPASS/human_replay` | PASS | `FETCH_DIR_RESOLUTION_PROBE.txt`；`BUILD.json` 的 `bundle_check` |
| R5-05 | 页面自定义「雷达板端服务」地址传导官方 fetch（原 subprocess 版忽略该选项） | PASS | 源码审读 `fetch['C'].BOARD_URL = self.board_url` |
| R5-06 | 回归：joint_capture 6/6、console 7/7、console_html 16/16、sessions+fetch 18/18 全部 exit 0 | PASS | `TESTS_*.log`、`TEST_EXIT_CODES.txt` |
| R5-07 | 源码 `--check-joint-capture` exit 0，`page_ok=true`，`page_version` 3/3 | PASS | `JOINT_PROBE_SOURCE.json` |
| R5-08 | 真实板端端到端拉回：`cap_20261015_111738`（186 帧）completed；板端 `ready→transferred` | PASS | `REAL_PULL_CAP_20261015_111738.json` |
| R5-09 | 拉回产物字节契约：`points.bin`=9,125,787 点×28B 整、frames=186、memmap 首帧 49,117 点可读 | PASS | 同上（`local_files`/`local_meta_summary`） |
| R5-10 | 重打 `dist/Console.exe`/`LiDAR_Console.zip`；冻结 `--check-joint-capture` **exit 0** | PASS | `BUILD.json`、`JOINT_PROBE_FROZEN.json`、`PROBE_EXIT_CODES.txt` |
| R5-11 | 冻结 `--check-startup`：replay/fall 服务起；real fall 因既有缺 `cap_20261013_094333` 未起 | BLOCKED（环境，既有） | `STARTUP_PROBE_FROZEN.json`（与 R4 同因，非本轮回归） |
| R5-12 | 冻结 exe 内真实「录制→拉回」整链 | NOT_RUN | 未采集（需板端+相机实录；用户可用重打版自测下次联合录制） |
| R5-13 | 板端源码/驱动/配置/旧会话/旧证据零改动；无 commit/push | PASS | 本轮仅 PC 侧 2 源码文件 + 文档；板端只有 fetch 既有状态机推进 |

## 未闭合与限制

- `--check-startup`/`--check-joint-capture` 目的文件用 `open(…, 'x')` 独占创建：重跑指向已存在文件会
  `FileExistsError`（用户此前看到的 traceback 即重跑检查；非录制缺陷，检查文件换新路径即可）。
- 相机仍不写盘：`camera.mjpeg` 恒 0 B 占位（现行设计，不在本轮）。
- 用户此前失败的 `joint_cap_20261015_111738` 已原地补全为可回放会话；板端该会话已 `transferred`。
- 冻结 exe 的真实拉回整链、独审、commit/push 均未做。
