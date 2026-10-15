# 2026-10-15 两个总控制台合并（console merge r1）

**用户指令**：「两个总控制台合并一下」。

## 合并前（实测）

| 对象 | 状态 |
|---|---|
| 桌面 | `总控制台.lnk` → `dist\Console.exe`（desc=LiDAR Console）；`总控制台 (点集).lnk` → `dist\Console_Pointset.exe`（wd=dist、无 desc） |
| dist | `Console.exe` 63,068,261B；`Console_Pointset.exe` 63,067,883B（两 spec 除 name/头部注释外逐行一致，内容仅内嵌名不同） |
| 引用 | `ConsolePointset.spec`、`make_release.py`（3 处）、`README.txt`（构建与源码段）、`README_POINTSET.txt`（第 3 行） |

## 合并后

- **桌面**：只保留 `总控制台.lnk` → `dist\Console.exe`（已用 `make_console_shortcut.py` 重建，desc=LiDAR Console）；删除 `总控制台 (点集).lnk`。
- **dist**：删除 `Console_Pointset.exe`；备份 `Console_Pointset.exe.bak-20261015`（63,063,441B）/`.bak-20261014` 保留。
- **仓库**：删除 `ConsolePointset.spec`；`make_release.py` 改为单 exe 打包（去掉 2 个 FILES 条目 + docstring 更新）；`README.txt` 构建段改单 exe 口径；`README_POINTSET.txt` 顶部加合并说明。
- **`LiDAR_Console.zip` 重生成**：63.2 MB（32 条目；`Console.exe` + `Console.spec` + 源码；无任何 Console_Pointset 残留）。随后按用户“打包zip”复跑并逐成员对账，最终 sha256 `86CB4D68FFC98A7CC43A5F51A7AF70F53B793ECADDA39FDC65D2E945578BA1C7`（63,202,953B），见下“打包复核”节。
- **保留为历史**：`dist\LiDAR_Console_Pointset.zip`（2026-10-14 点集专版，148MB）与其说明 `README_POINTSET.txt`（已标历史）；各 `*.bak-*` 备份。

## 验证

| 项 | 结果 |
|---|---|
| 桌面 .lnk 枚举（按目标匹配 ldiar console） | 仅 1 条 → `dist\Console.exe`，目标存在 |
| dist 列表 | `Console.exe` + 备份 ×4 + `LiDAR_Console.zip`(63.2MB) + `LiDAR_Console_Pointset.zip` + ini |
| `python -B make_release.py` | 实跑成功，输出 63.2 MB |
| zip 条目实查 | `exe/spec:` 仅 `Console.exe`、`源码/Console.spec`；大文件仅 Console.exe(63,068,261) |
| `ConsolePointset.spec` | 已从仓库目录移除 |

## 边界与说明

- **未改动**：`Console.exe` 本体（即 R4 版本，探针已过，未重打）、`LiDAR_Console_Pointset.zip`、点集证据/板端/数据；未 commit/push。
- 被删的都可快速重建：`ConsolePointset.spec` = 复制 `Console.spec` 改 name；快捷方式 = `make_console_shortcut.py` 或手工；`Console_Pointset.exe` = 按 spec 重打。
- 技能：ponytail（`C:/Users/30680/.config/opencode/skills/ponytail`），用法＝删除优先（合=删冗余）、复用既有 `make_console_shortcut.py`/`make_release.py` 通道，零新增脚本/配置。

## 打包复核（2026-10-15，用户“打包zip”）

- 复跑 `python -B make_release.py` 后逐成员对账（`verify_zip.py` → `ZIP_VERIFY.log`）：
  `make_release.FILES` **27/27** 项与仓库当前文件 sha256 一致；`members=32`；`pointset_entries=[]`；**VERDICT: PASS**。
- 最终产物：`pc_apps\console\dist\LiDAR_Console.zip`，63,202,953 字节，
  sha256 `86CB4D68FFC98A7CC43A5F51A7AF70F53B793ECADDA39FDC65D2E945578BA1C7`。
- 备注：两次重打包字节数一致、哈希不同——zip 的 5 个目录条目（`LiDAR_Console/`、`captures/`、`captures/remote/`、
  `源码/human_replay/`、`源码/human_ml/`，`writestr` 写入）时间戳取打包时刻，属非字节确定性；
  内容完整性以逐成员 sha256 对账为准（PASS）。
