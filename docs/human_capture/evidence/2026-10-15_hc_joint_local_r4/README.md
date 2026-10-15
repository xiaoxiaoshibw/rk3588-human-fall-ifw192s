# 2026-10-15 联合录制拉回完成自动打开回放（HC-JOINT-LOCAL-01 R4）

**用户指令**：「下载完自动弹出加载界面，下载完之后结束」；确认落点为"联合录制：拉回完成后自动打开回放载入该会话"。

## 范围与基线

- writer：OpenCode CLI（`opencode-go/deepseek-v4.1-flash`）；ponytail 实际路径
  `C:/Users/30680/.config/opencode/skills/ponytail`（skill 工具加载，full 强度）。
- 基线：master，HEAD `c21c443b0befe559e08283edb0efc2af02dcc6b8`。起始工作树已脏：
  console/human_replay 多文件为前几轮未提交改动；`docs/` 下一批归档清理删除为既有状态
  （10-14 23:38 基线快照 `2026-10-14_hfus_next_development_plan_r1/GIT_STATUS_BEFORE.txt` 已带 ` D`），
  非本轮产物。本轮终态见 `GIT_STATUS_AFTER.txt`，本轮 diff 见 `ROUND4_DIFF.patch`（对 HEAD，含前几轮累积改动）。
- 只改本机 PC 侧 6 个文件；板端/服务/数据/模型/GT/旧证据零改动。未 commit/push。

## 行为变化（现状 → 本轮）

- 原：拉回完成后只显示「已保存到本机（可回放）」，需用户自己切到「会话回放」点行载入。
- 现：拉回完成（`state` 刚进入 `completed` 的那一刻，只触发一次）→ 联合录制页向壳页发
  `{type:'joint-completed', sid:'joint_<板端sid>'}` → `console.html` 校验
  `e.origin === captureBase`（只认本实例联合录制服务）+ sid 白名单 → 强制打开「会话回放」并以
  `?sid=` 载入该会话（已开过回放也重载换会话）→ 流程结束。
- 联合页独立新窗口打开（非嵌入控制台）时不发送（无处可跳）。
- `human_replay/index.html` 新增 `?sid=` 消费（与 `session_selection.js` 在 human_detect/human_track 同型）：
  无 `?sid` 的既有入口行为不变。

## 改动文件（本轮，sha256）

| 文件 | 改动点 | sha256 |
|---|---|---|
| `pc_apps/console/joint_capture.html` | `notify_completed`（parent 判定 + sid 白名单 + postMessage）；`render` 在 completed 迁移处触发；页脚文案 | 47D3860440C7AB1B2A9B2E5250F6EE8BEE30CD9FD72A7016583051260D3577E1 |
| `pc_apps/console/console.html` | message 监听（origin/type/sid 校验）；`pendingSid`；`load()` 对 0 号应用追加 `?sid=`；卡片 desc | 114894FBA872FE4AC424A8D16782A3DD62046ECC2E50F2AC7A0E640B094837FF |
| `pc_apps/human_replay/index.html` | 尾部小脚本消费 `?sid` → `__load_session_sid` | C8A1CC3D14B56A325C2089C78BEAFA4F97EF534E04D70A4C05F5648BA0EEE829 |
| `pc_apps/console/console_gui.py` | `--check-joint-capture` 增 `page_version` 内嵌契约（联合页/壳页/回放页），exit 需 page_ok+3 项全 true | 1B06085DA92E4ECE4B4AA228B8B33B8D9E93C2959381C8135DE609C91251A4C0 |
| `pc_apps/console/console_html.test.js` | DOM 替身加 `addEventListener`/`window` 自引用；新增 3 用例 | C019BF86BB9F4CDAC81E092A85859F0F99B0C1528B664E150BB765CFA4A5F939 |
| `pc_apps/console/README.txt` | 联合段与入口行补"拉回完成后自动打开回放" | A08FB922D51A3A6A3ECAAAD51569DADDC1DD3303AE0A5DC48F413E055CF8EF44 |

## 验证（本机离线；设备实录 NOT_RUN）

| 项 | 结果 | 日志 |
|---|---|---|
| `console_html.test.js`（pc_apps/console） | **15 PASS**（12 旧 + 3 新：消息→开回放带 `?sid`、非法来源/类型/sid 忽略、"三处合同一致"） | `TESTS_console_html.log` |
| `joint_capture_test.py` | **4 PASS** | `TESTS_joint_capture.log` |
| `console_test.py` | **7 PASS** | `TESTS_console_py.log` |
| human_replay node：`human_replay_lib` / `panel` / `human_detect_lib` / `human_pipe_lib` / `human_track_static` | **45 / 1 / 11 / 38 / 7 PASS** | `TESTS_human_replay_lib.log`、`TESTS_panel.log`、`TESTS_human_detect_lib.log`、`TESTS_human_pipe_lib.log`、`TESTS_human_track_static.log` |
| `python -B -W error -m unittest sessions_test fetch_lib_test` | **18 PASS** | `TESTS_sessions_fetch.log` |
| 源码 `console_gui.py --check-joint-capture` | **exit 0**，`page_ok=true`，`page_version={joint_page,console_shell,replay_page}=true` | `JOINT_PROBE_SOURCE.json` |
| 冻结 `dist/Console.exe --check-joint-capture` | **exit 0**，同上（内嵌副本合同齐） | `JOINT_PROBE_FROZEN.json` |
| 冻结 `dist/Console.exe --check-startup` | replay/fall(点集) 服务起；**real fall 未起 = 既有缺数据**（`captures\remote\cap_20261013_094333\meta.json` 缺；源码同测复现，见 `STARTUP_PROBE_SOURCE.json`，非本轮回归） | `STARTUP_PROBE_FROZEN.json` |
| 端到端真实录制（录一段→自动跳转回放） | **NOT_RUN**（未动板端、未触发录制；可用重打版自测） | — |

## 重打包（staging_console 法）

| 产物 | 字节 | sha256 | 时间 |
|---|---|---|---|
| `dist/Console.exe` | 63,068,261 | 03E424FBBFE7FEE17564C237F05ADFB4EF0472A2C2397891C9B66C0C96B9B424 | 2026-10-15 00:32:52 |
| `dist/Console_Pointset.exe` | 63,067,883 | 7479107B9FFD82F276EA18FADE0DE6D2ECB57BDF547720DA3C8D31CC67CC298C | 2026-10-15 00:35:01 |
| `dist/LiDAR_Console.zip`（make_release） | 125,861,355 | C4F00572276E6C02B350971E5034C38B5E7AA4D1255759AB314A94B21F116234 | 2026-10-15 00:38:29 |

- 旧 exe 备份：`Console.exe.bak-20261015` / `Console_Pointset.exe.bak-20261015`（63,064,416 / 63,063,441，即 10-14 17:16 版）；`.bak-20261014`（189MB，UPX 前）保留。
- 旧 `LiDAR_Console.zip`（292MB）里包的是 UPX 前的 189MB 旧 exe；本次与 dist 对齐重生成（125.9MB）。
- `LiDAR_Console_Pointset.zip` 未刷新（属 HFUS-POINTSET 自己的发布物，且其上次刷新早于 17:16 重打，本轮不改动它）。
- 构建输入=仓库当前源码：staging 镜像后逐文件哈希核对一致（`console.html` 114894FB…、`joint_capture.html` 47D38604…、`human_replay/index.html` C8A1CC3D… 两侧相同）。
- 构建步骤：`tmp_gl_diag/staging_console/{console,human_replay}` 同步（robocopy /MIR /XD __pycache__ gt_store，exit1=有文件复制成功）→ `python -m PyInstaller --noconfirm Console.spec` → `ConsolePointset.spec` → 安装到 `pc_apps/console/dist`。
- 本机 dist 有 `console_passthrough.ini`（源码旁路→仓库 human_replay）：冻结探针的 `replay_page` 检查读的是该运行档解析结果。

## 已知限制

- **自定义保存目录**不在回放服务 `DEST_ROOT`（`captures\remote`）下时，自动载入会 404（回放状态栏可见失败原因）；默认目录不受影响。
- "弹出"实现为控制台内切换到「会话回放」页载入（pywebview 吞顶层 `window.open`，内嵌切换是可靠路径），非独立新窗口。
- 真人倒地回放仍缺原始 `cap_20261013_094333` / `cap_20261013_131958`（既有缺口，与本轮无关）。

## 技能与实际用法（ponytail）

- 复用原生能力，零新依赖：`postMessage`（跨 iframe 通信）+ URL 查询串（`?sid=`，沿用 repo 内 `session_selection` 同型）+ 既有 `__load_session_sid` 载入接口与 `/api/file` 白名单。
- 未新增配置项/框架/接口；删除优先：不改 joint_capture.py、不动 fetch/状态机。
- 已知天花板一处已就地标注（`ponytail:` 注释：自定义目录场景，见 index.html）。
