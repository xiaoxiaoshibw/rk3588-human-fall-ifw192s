# 总控制台 exe 重新打包（R2.6b 入包）

- 日期：2026-10-06 15:18–15:29（Asia/Shanghai）
- 触发：用户确认"现在重新打包"，把 R2.6b 打进总控制台（`dist\Console.exe` + `LiDAR_Console.zip`）。
- 范围：仅打包与验证；未改任何源码；未 commit。

## 过程

1. 备份旧 exe（12:52 构建）：`pc_apps/console/dist/Console_backup_20261006_1518.exe`。
2. 首次 PyInstaller 直打被拒：总控制台正在运行（2 个 `Console` 进程占用 exe，WinError 5）。
3. 先构建到临时目录：`python -m PyInstaller --noconfirm --distpath dist_r26b Console.spec`（exit 0，15:22:30 完成）。
4. 用户确认关闭运行中的控制台 → `Stop-Process` → `Move-Item dist_r26b\Console.exe dist\Console.exe` → `python -B make_release.py`。

## 产物与哈希

| 产物 | 时间 | SHA256 |
|---|---|---|
| `pc_apps/console/dist/Console.exe` | 2026-10-06 15:22:30 | `414e64cd90ef9cdd1b141307710f2568053a483e542e2daf9739fe5360d26e18` |
| `pc_apps/console/dist/LiDAR_Console.zip` | 2026-10-06 15:28:06 | `81205e338bd8448fc3eaff442c5d4471021804cd766f7a9b11d2c791b8745f24` |
| 备份 `Console_backup_20261006_1518.exe` | 旧 12:52 构建 | — |

桌面快捷方式 `总控制台.lnk` → `D:\Code\ldiar\pc_apps\console\dist\Console.exe`（原地更新，无需改）。

## 内嵌内容验证（PyInstaller CArchiveReader 直读 exe 归档）

| 内嵌文件 | 命中标记 |
|---|---|
| `human_replay/human_pipe_lib.js` | `R2.6b`、`xy_topology_vetoed`、`actually_removed_points` ✓ |
| `human_replay/human_detect.js` | `R2.6b`、`pipeCleanup`、`xy_topology_vetoed` ✓ |
| `human_replay/human_detect.html` | `pipeCleanup`（新诊断行）✓ |

控制台自测：`node console_html.test.js` 10 passed / exit 0；`python -B console_test.py` 4 tests OK / exit 0。

## 说明

- exe 以 datas 形式内嵌 `human_replay/` 快照，源码改动必须重打才会生效；本次打包后旧实例被关闭，重新打开总控制台即为 R2.6b（人体识别页新增「孤立清理 / 拓扑」诊断行）。
- 源码方式运行（`open_console.bat` / `python console_gui.py`）不受影响，同样已是 R2.6b。
