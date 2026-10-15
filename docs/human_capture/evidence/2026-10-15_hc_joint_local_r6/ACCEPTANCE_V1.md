# HC-JOINT-LOCAL-01 R6 唯一验收 v1（2026-10-15）

范围：R5 复盘发现 A1/A2/A3/A4/A7/A8 的逐项整改 + 重打 `Console.exe`/`LiDAR_Console.zip`。
A5（板端 IP/端口硬编码散落）、A6（双拉回编排并存）本轮**不修**，理由见 README「未修项」。
判定基准：PASS 仅代表本机自验与冻结产物检查；冻结 exe 内真实「录制→拉回」整链与独立复审 **NOT_RUN**。

| ID | 验收点 | 结果 | 依据 |
|---|---|---|---|
| R6-01 | （A4）`--check-joint-capture` 新增 `joint_fetch_ok`（`load_fetch` 加载 + `process_session` 可调用，不触网），并纳入退出码 | PASS | 源码探针 `JOINT_PROBE_SOURCE.json`（`joint_fetch_ok:true`，exit 0） |
| R6-02 | （A2）拉回用的官方 fetch 目录与回放页同源：`console_gui._replay_dir()` 解析一次、经 `fetch_dir` 传入；joint_capture 保留缺省回退 | PASS | `R6_DIFF.patch`；单测显式/缺省两分支 |
| R6-03 | （A3）落盘工件 `joint.json` 补终态：completed/failed + `finished_iso`/`radar_frames`/`bytes`/`error`；写失败不影响会话数据 | PASS | `TESTS_joint_capture.log`（成功/失败两断言）+ 真实 E2E `joint_json.state=completed` |
| R6-04 | （A1）`human_limb` 冻结守卫：冻结形态 import 即明确 SystemExit；源码运行不受影响 | PASS | 双向探针（源码 import OK；`sys.frozen=True` → 守卫消息） |
| R6-05 | （A7）`human_replay_lib.py` 删除未使用的 `import subprocess` 残留 | PASS | `R6_DIFF.patch` + 套件回归 |
| R6-06 | （A8）`--check-*` 报告文件已存在 → 可读提示 + exit 2（原为 FileExistsError traceback） | PASS | `CHECK_REPORT_EXISTS_BEHAVIOR.txt`（实测 exit=2） |
| R6-07 | 回归：joint_capture **7/7**（+1 新）、console 7/7、console_html 16/16、sessions+fetch 18/18 全 exit 0 | PASS | `TESTS_*.log`、`TEST_EXIT_CODES.txt` |
| R6-08 | 真实端到端复核（板端打桩 + 真实 fetch 只读复制 → 临时目录）：completed；`points.bin`=255,522,036B 整；板端状态机未动 | PASS | `REAL_E2E_TMP_R6.json`（exit 0，临时目录已清理） |
| R6-09 | 重打 `dist/Console.exe`/`LiDAR_Console.zip`（含返工 stage2）；冻结 `--check-joint-capture` exit 0 且 `joint_fetch_ok=true` | PASS | `BUILD.json`（终版 exe 193,807,707B/B2457635…）、`JOINT_PROBE_FROZEN.json`、`PROBE_EXIT_CODES.txt` |
| R6-13 | 审查发现共享文件 `console_gui.py` 被并行工作流持续写入（13:00:25/13:07:57/13:17:52 三次）：写 #1 落 stage1 构建窗口 → 判定不可复现、返工；写 #2 由 stage2 产物正确冻结；写 #3 不追入产物（该工作流自管打包）。终态 exe/zip 内部自洽；R6 三处 hunk 全版本保持且冻结探针行为验证 | PASS（返工完成） | README「审查、返工与并行写入时间线」；`FINAL_FACTS.json`、`PARALLEL_CONSOLE_GUI_ZIP_vs_TREE.diff`、`*_stage1.json` |
| R6-10 | 冻结 `--check-startup`：replay/fall 起；real fall 因既有缺 `cap_20261013_094333` 未起 | BLOCKED（环境，既有） | `STARTUP_PROBE_FROZEN.json` / `PROBE_EXIT_CODES.txt` |
| R6-11 | 冻结 exe 内真实「录制→拉回」整链 | NOT_RUN | 未采集（需板端+相机实录） |
| R6-12 | 板端/驱动/配置/旧会话/旧证据零改动；无 commit/push | PASS | 本轮仅 PC 侧 5 源码文件 + 文档；板端全程只读（E2E 走 transferred 只读复制） |

## 未闭合与限制

- A5/A6 未修（见 README）；冻结链路与独审未做。
- 检查报告 exit 码语义：0=通过，1=功能失败，2=报告文件不可写（已存在）。
