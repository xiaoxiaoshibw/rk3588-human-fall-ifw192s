# 2026-10-15 联合录制拉回失败修复（HC-JOINT-LOCAL-01 R5）

**用户反馈**：错峰联合录制 26.41 s / 186 帧（相机预览中、雷达 0.0 MB），停止后页面报
「fetch 拉回失败；板端会话 `cap_20261015_111738` 仍为 ready，可在回页面板重试」；
本机 `data/sessions/joint_cap_20261015_111738` 只有 `joint.json` + 空 `camera.mjpeg`。

## 根因（`pc_apps/console/joint_capture.py::_StagedFetch.pull`，R2 提交 `6ecc3a2` 引入，其后各版 exe 必然失败）

原实现：`subprocess.run([sys.executable, '-I', FETCH_SCRIPT, '--sid', sid, '--dest', staging])`。

1. **冻结 exe 路径**：`sys.executable` 就是 `dist/Console.exe` 自身。子进程等价于又开一个总控制台
   （用户日志的子进程 stdout：`resolved root=D:\Code\ldiar\pc_apps\human_replay`、`mode=SOURCE_BYPASS`、
   `human_replay 服务 http://127.0.0.1:51004/（随控制台退出）`、`real fall replay unavailable …`），
   `fetch.py` 从未执行 → staging 无文件 → `pull()` 返回 `(None, None)` → 页面报「fetch 拉回失败」。
   子进程 exit=0 且 stdout 看似"正常启动"，所以失败信息里没有可读的 fetch 错误。
2. **源码运行路径**：本机 Python 3.12 的 `-I` 隐含 `-P`，脚本目录不进 `sys.path`；
   实测 `python -I main.py` 引同目录 `sibling` 即 `ModuleNotFoundError`，
   即 `fetch.py` 的 `import config as C` 同样直接失败——py3.11+ 下源码方式也永远拉不到。
3. 旁注：修改期间本机文件锁窗口内该文件尾部出现过一次杂散残行（写盘竞态，已清理并
   `py_compile`/全测试复验），与本缺陷无关，不归因。

## 修复（复用官方 fetch.py 本体，零新依赖）

- `pull()` 改为**同进程** `runpy.run_path(<FETCH_DIR>/fetch.py)` 调 `process_session(sid, staging, log=self.log.append)`：
  官方 SHA/布局校验、板端状态机（ready→transferring→transferred）、失败回退全部原样沿用；
  任何异常捕获入 `self.log`，不把会话卡死。
- `FETCH_DIR` 两分支解析：源码运行 = 平级 `pc_apps/human_replay`；
  冻结运行 = `_MEIPASS/human_replay`（Console.spec datas 内嵌副本，与 console_gui `_replay_dir()` 的 PACKAGED 档同址）。
- `_StagedFetch(root, board.base)`：页面上「雷达板端服务」自定义地址现在会传导给官方 fetch
  （原 subprocess 版本忽略该选项）。
- 删除 `subprocess` 依赖；`joint_capture_test.py` 新增 `StagedFetchTest` 两用例，
  钉死「必须进程内跑官方 `process_session`、失败返回 `(None, None)` 且留日志」。

## 改动文件（本轮，sha256）

| 文件 | 改动点 | sha256 |
|---|---|---|
| `pc_apps/console/joint_capture.py` | imports `subprocess`→`runpy`；`FETCH_DIR` 冻结/源码解析；`_StagedFetch` 重写为进程内官方 fetch；`board_url` 传导 | 71B7ADB81D7C91E2DB8BBC76C4A7777784272B214F76616FF8C9B8CB107C484B |
| `pc_apps/console/joint_capture_test.py` | `_FakeFetch` 签名同步；新增 `StagedFetchTest` 2 用例 | F8F8B74ED31FE87659E8BA3E7D4FC0A3A2FFF6C7DDE4A00F4931886A4F839B00 |

差异文件：`R5_DIFF.patch`（对 HEAD，包含此前几轮未提交的累积 hunk；本轮 hunk 见上表两文件）。

## 验证（本机；设备实录 NOT_RUN）

| 项 | 结果 | 日志/证据 |
|---|---|---|
| `joint_capture_test.py`（pc_apps/console） | **6 PASS, exit 0**（4 旧 + 2 新） | `TESTS_joint_capture.log` |
| `console_test.py` | **7 PASS, exit 0** | `TESTS_console_py.log` |
| `console_html.test.js` | **16 PASS 0 fail, exit 0** | `TESTS_console_html.log` |
| `python -m unittest sessions_test fetch_lib_test` | **18 PASS, exit 0** | `TESTS_sessions_fetch.log` |
| `FETCH_DIR` 两分支解析：源码=`pc_apps/human_replay`；模拟冻结(`sys._MEIPASS`)=`<_MEIPASS>/human_replay` | PASS | `FETCH_DIR_RESOLUTION_PROBE.txt` |
| 源码 `console_gui.py --check-joint-capture` | **exit 0**，`page_ok=true`，`page_version` 3/3 | `JOINT_PROBE_SOURCE.json` |
| **真实板端端到端拉回**：修复版 `_StagedFetch`/`Recorder`（板端控制词打桩，fetch 走真网络）拉回 11:17 的 `cap_20261015_111738` | **completed**：186 帧、`points.bin` 255,522,036 B（9,125,787 点 ×28 B 整）、板端 `ready→transferred` | `REAL_PULL_CAP_20261015_111738.json` |
| 重打 `dist/Console.exe` 后 `--check-joint-capture`（冻结） | **exit 0**，`page_ok=true`，`page_version` 3/3；同轮 `--check-startup` exit 1（既有缺 `cap_20261013_094333`，与 R4 同因） | `JOINT_PROBE_FROZEN.json`、`PROBE_EXIT_CODES.txt` |

## 现场恢复（用户本次丢失的录制）

- `Recorder`（修复版）全流程跑通：`joint_cap_20261015_111738/{meta.json, points.bin, camera.mjpeg, joint.json}`，
  `meta.joint_recording={mode: staged_capture, board_session_id: cap_20261015_111738}`；
  首帧 memmap 抽查 49,117 点，会话可直接在「会话回放」打开。
- 板端会话因官方 fetch 推进为 `transferred`（文件仍在板上 FIFO 内，符合既有语义）。
- 该会话为新空场类数据，不影响任何旧会话/证据；`data/` 仅补全该会话目录（`joint.json`/`camera.mjpeg` 占位由 Recorder 以同形状重写，无其它文件被删改）。

## 重打包（须重启控制台后生效）

| 产物 | 字节 | sha256 | 时间 |
|---|---|---|---|
| `dist/Console.exe` | 193,806,359 | DDC5501A…FB4C | 2026-10-15 11:33:33 |
| `dist/LiDAR_Console.zip` | 151,031,729 | 06D79D0E…9AF7 | 2026-10-15 11:34:52 |
| 旧 exe 备份 `dist/Console.exe.bak-20261015_before_jointfetch` | 193,805,996 | 0BA4AAE4…94CE | 11:07 版（含本缺陷） |

- 构建：`python -m PyInstaller --noconfirm Console.spec`（cwd=`pc_apps/console`，就地）+ `python -B make_release.py`；
  PyInstaller 日志含 `Building because … joint_capture.py changed`；zip 内 `源码/joint_capture.py` 与仓库同哈希。
- 冻结 exe 内 `human_replay\fetch.py`（datas）在 `pyi-archive_viewer -l` 可见 → `_MEIPASS/human_replay` 解析链闭合（见 `BUILD.json`）。
- 用户侧：关闭并重开总控制台（`joint_capture` 模块在 exe 内嵌，`console_passthrough.ini` 的源码旁路只覆盖 human_replay）。

## 已知限制 / 未跑项

- 冻结 exe 内的真实「录制→拉回」整链 **NOT_RUN**（需板端+相机实录；用户可用重打版自测下一次联合录制）。
- 冻结 `--check-startup` 仍因既有缺 `cap_20261013_094333`/`131958` 在 real-fall 档不通过（R4 已记录，非本轮）。
- `--check-startup` 目的文件用 `open(..., 'x')` 独占创建：重复指到已存在文件会
  `FileExistsError`（用户此前看到的那条 traceback 即重跑检查所致，非录制缺陷）。
- 相机始终没有写入（`camera.mjpeg` 恒 0 B 占位），属现行设计，不在本轮。
- 未 commit/push；板端源码/驱动/配置零改动。
