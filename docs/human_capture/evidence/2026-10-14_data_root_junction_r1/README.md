# 2026-10-14 数据目录分离（DATA-ROOT-JUNCTION-01）

**用户要求**：总控制台引用的数据和下载的数据放到单独的项目数据文件夹，与 AI 在仓库里生成的
工作数据分开，防止误删（起因：2026-10-14 `captures/remote` 被清空后又重新下载
`radar_sessions_8pack_2026-10-13.zip`）。

**用户拍板**：数据根 `D:\Code\ldiar\data`；控制台用目录联接（junction）指向，不改代码不重建 EXE；
8-pack 只解压不留 zip；`captures/leveled`、`captures/registration` 一起搬。

## 现状

```
D:\Code\ldiar\data\                     ← 数据本体（.gitignore 忽略）
  sessions\      18 文件 / 2.82 GB     ← 原 captures\remote
  leveled\      222 文件 / 9.61 GB     ← 原 captures\leveled（含 gt_store_backup）
  registration\  16 文件               ← 原 captures\registration
  downloads\     radar_sessions_8pack_2026-10-13.manifest.json（存档）
  README_数据目录说明.md

D:\Code\ldiar\captures\remote        -> junction -> data\sessions
D:\Code\ldiar\captures\leveled       -> junction -> data\leveled
D:\Code\ldiar\captures\registration  -> junction -> data\registration
```

对外路径不变：`config.py` 的 `DEST_ROOT`、`console_gui._frozen_capture_root()`、点云页
`captures/remote/<sid>/points.bin` 全部照旧，读写实际落在 `data\`。

## 验证（本次实跑）

| 项 | 结果 |
|----|------|
| 8-pack 逐文件核对（zip vs 落盘） | 16 文件 / 2,657,818,909 字节，mismatch 0 |
| zip 删除后压缩包 | 已删（同目录包装层一并删），C: 释放 2.29 GB |
| `pc_apps/console/console_test.py` | 7 tests OK，exit 0 |
| `pc_apps/human_replay/sessions_test.py` | 4 tests OK，exit 0 |
| 冻结 `Console.exe --check-startup` | replay/fall 服务起（55656/55657）；`ok=false`，`real fall replay did not start`（既有缺口，见下） |
| junction 读 | `cap_20261013_083254` meta+points memmap 读通；leveled job 读通 |
| junction 写 | 运行中的控制台 22:18 落 `cap_20261014_221808`（374.3 MB）到 `data\sessions` |
| 点云服务 8954 `/api/catalog` | 9 段；8 段 actions 帧正常；`cap_20261013_131958` 返 400 |
| `git status` | 无 `data/` 条目（已被忽略） |

## 仍然缺的原始数据（不是本次改动造成）

`captures/remote` 现在只有 8 段 + 1 段新录；下列**原始**会话本机没有，只能从板端 staging
（FIFO 10，注意可能在清）或外部备份取回：

- `cap_20261013_131958`（点云八段页空场参考、`real_fall/r04` REF）、
  `cap_20261013_094333`（真人倒地回放 SID）→ 这两段缺，所以 `真人倒地回放` 起不来。
- `cap_20261013_093958`（CAM-HOT 等历史引用）。
- legacy 九会话 `cap_20261010_175227 / 175429 / 175553 / 175804 / 175943 / 180235 / 180337 / 180557 / 180751`。

`data\leveled\<job>\{ransac,svd,tls}\points.bin` 是**配平变换后**的点云，不能替代原始副本。

## 改了哪些文件

- `.gitignore`：新增 `/data/`（数据不是工作区，勿 `git add`）。
- `AGENTS.md`：workflow 规则加 `data/` 保护条；Repository 段注明 `captures/` 三个子目录是 junction。
- 新增 `data/README_数据目录说明.md`、本证据目录。
- **未改** `console_gui.py` / `human_replay` / 任何 EXE；无 Git 提交推送；无板端/部署/采集操作。

## 技能路径

writer = opencode CLI（`opencode-go/deepseek-v4.1-flash`）；ponytail =
`C:/Users/30680/.config/opencode/skills/ponytail`。用法：先复用既有路径契约（`config.py`
`DEST_ROOT`、`_frozen_capture_root`）→ 用 junction 而非改代码重建 EXE；复用既有 `.gitignore` /
`AGENTS.md` 规则通道，不新增配置层；验证只留既有测试 + 冻结 EXE 启动检查 + junction 读写实测。

机读状态见 `STATE.json`。
