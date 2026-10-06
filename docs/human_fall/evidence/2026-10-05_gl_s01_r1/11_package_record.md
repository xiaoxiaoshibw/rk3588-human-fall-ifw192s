# GL-S01 附加：打包切换记录（r1b）

- 日期：2026-10-05；用户授权"好的开始，注意保留后路"。
- 目标：把含 `lowest_floor_sheet_v2` 的源码装进打包版总控，旧版与回退路径保留。

## 构建

- 命令（在 `pc_apps/console/`）：`python -m PyInstaller --noconfirm --distpath dist\gl_s01 --workpath build\gl_s01 Console.spec`
- PyInstaller 6.21.0 / Python 3.12.10；全新目录，不覆盖任何既有 `dist/*`。
- 产物：`pc_apps/console/dist/gl_s01/Console.exe`，64,479,136 B，
  SHA256 `6974C88F270A9F2A57EEB439F0EB5D63419610D1658D288E9D113E5F386B0497`。
- 打包内容核对：`build\gl_s01\Console\Analysis-00.toc` 含 `human_replay\floor_sheet.py`（True）与 `floor_detector.py`（True）。

## 打包版端到端验证（真实 HTTP，服务由新 exe 自己启动）

- 启动 `dist\gl_s01\Console.exe`（onefile 父/子进程 41904/35032），服务监听 127.0.0.1:8901（当时旧实例已退出）。
- `08_packaged_verify.py 8901` 结果 3/3 PASS：
  - validation sessions 路由列出四个会话（含 223757）；
  - auto run 受理；
  - 223757 稳定失败于 `INSUFFICIENT_CLEAN_ROI_SUPPORT: clean_cells=6 independent=0 min_sep_m=0.354 condition=0.162`。
- 失败 job `54202faa5b9f4534b6fd58e6e93f8739` 未生成任何 `captures/leveled` 目录；测试实例随后停止，8901 释放。
- 产物：`08_packaged_verify.py`、`09_packaged_verify.json`、`10_packaged_verify.log`。

## 切换与回退

- 桌面 `总控制台.lnk`：切换前 -> `dist\gl_v01_floor_r2\Console.exe`；切换后 -> `dist\gl_s01\Console.exe`（工作目录同步）。
- 切换前快捷方式副本：`dist\gl_s01\总控制台_rollback_gl_v01_floor_r2.lnk`。
- 回退说明：`dist\gl_s01\ROLLBACK.txt`（覆盖快捷方式或 PowerShell 重指回 `gl_v01_floor_r2`）。
- 旧构建目录 `dist\gl_v01_floor_r2`、`dist\gl_v01`、`dist\gl_w01`、`dist\Console.exe`、`dist\hr02_offline` 均未改动。

## 追加：标准目标 `dist\Console.exe` 同步重打包（同日 20:23，用户"打包进exe新算法"）

- 备份旧 exe：`dist\Console_backup_20261005_1906.exe`（19:06 构建，64,472,571 B）。
- 构建：`python -m PyInstaller --noconfirm --clean Console.spec`（默认 `dist`/`build`）。
- 产物：`dist\Console.exe`，64,491,764 B，SHA256 `DE9F13E41ABA2C548E3843CA529131C11ABC17044989FCDACAA82D3735E5C9E3`；`build\Console\Analysis-00.toc` 含 `human_replay\floor_sheet.py`（True）。
- 打包版实测 3/3 PASS（服务 127.0.0.1:8901，job `a3b66a397b124150b554f1189be5d545`）：会话列表含 223757；auto 受理；223757 稳定 `INSUFFICIENT_CLEAN_ROI_SUPPORT: clean_cells=6 independent=0 min_sep_m=0.354 condition=0.162`；未生成 `captures/leveled` 目录；实例已停，8901 释放。
- 产物：`12_canonical_verify.json`、`13_canonical_verify.log`。
- 桌面快捷方式保持指向 `dist\gl_s01\Console.exe`（同为 v2）；`dist\LiDAR_Console.zip` 发布包未重打（如需发布版另跑 `make_release.py`）。
