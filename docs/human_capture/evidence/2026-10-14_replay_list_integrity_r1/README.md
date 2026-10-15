# 2026-10-14 会话回放列表数据完整性（REPLAY-LIST-INTEGRITY-01）

**用户要求**：把会话回放里「消失的数据」删掉；以后检测数据完整性，只展示 3588 和本机有的会话。

## 事实（改前实测）

板端 `:8766` 登记表 36 行，本机 `data\sessions` 9 段。逐行 `HEAD
/api/v1/sessions/<sid>/files/{meta.json,points.bin}` 实查：

| 分类 | 行数 | 说明 |
|------|------|------|
| 板端真有文件 | 2 | `cap_20261014_221808`、`cap_20261014_164522` |
| 板端 state=purged | 26 | FIFO 已删文件，登记表留墓碑 |
| 板端 state=transferred 但文件也没了 | 8 | 含 `131958/094333/094302/093958` 与 4 段八段动作会话 |
| 本机有副本 | 9 | 8-pack + 221808（其中 4 段板端 state=purged） |

即：**36 行里只有 10 行两端有真数据**，其余 26 行的数据早已消失；旧列表把它们当普通行
展示（点进去只会拉失败，正是「会话回放里消失的数据」）。

## 改动

`pc_apps/human_replay/human_replay_lib.py`

- 新增 `_board_files_present(sid)`：HEAD `meta.json` + `points.bin`，只读头不下正文；
  404/file_missing = 板端没有；板不可达返回 True（离线不能当作数据缺失，否则离线整屏被吞）。
- `/api/sessions`：板端行若本机没有副本，先按 `state=purged` 排除，再实查文件；两端都没有的
  不展示，并在响应里给计数 `hidden:{purged,missing}`。本机有副本的行照列。
- `_local_sessions`：meta 声明了 `point_layout.stride_bytes` 时，要求
  `(末帧 offset_points + count_points) × stride == points.bin 字节数`，半写/截断的会话不算
  「本机有的会话」（无 stride 字段的旧元数据不受影响，仍走原有 `size%28` 检查）。

`pc_apps/human_replay/panel.js`：列表状态行显示「已隐藏 N 条无数据登记」，让列表变短可解释。

**未改**板端 `capture_server`/`session_store`/FIFO（只用了它既有的 HEAD 与 DELETE 路由），
未改 console_gui / EXE，未改数据文件。

## 一次清理（用户指示「删去吧」）

26 行两端口径都无数据的登记（22 purged + 4 transferred-but-gone），先用既有
`DELETE /api/v1/sessions/<sid>` 逐行删除登记，删前把整份行数据 + 探针证据落到
`captures/deleted_board_registry_20261014.json`（仓库侧存证）。每行返回 `removed: []`
——物理上什么都没删（文件本就不在）。板端登记 36 → 10 行；保留下来的 8 行墓碑是
「本机有副本」的那 8 段（数据没消失，列表照常展示）。

## 验证（实跑）

| 项 | 结果 |
|----|------|
| 真板 `/api/sessions`（改后） | 10 行 = 9 本机 + `164522`；`hidden:{purged:0,missing:0}`；0.19s |
| 真板清理 | 36 → 10 行；26 行 DELETE 全 200，`removed: []` |
| `sessions_test.py` | 5 项 PASS（新增 `IntegrityFilterTest`：墓碑行隐藏、探针 False 隐藏、有本机副本照列、截断 bin 不进本地列表、hidden 计数） |
| `panel.test.js` / `human_replay_lib.test.js` | PASS / 45 项 PASS |
| `console_test.py` | 7 项 PASS |
| human_replay 全量 python | 92 项，1 ERROR = `leveling_auto_test` 缺旧会话 `cap_20261004_202456`（既有环境缺失，与本改动无关） |

## 边界

- `131958`/`094333` 板端文件也已被清（HEAD 404），所以「真人倒地回放」取不回数据，
  本机也没有副本——已从列表消失，不再显示成可点可拉的行。
- 本机 4 段（`082623/082717/082829/082906`）列表里 state 仍显示 `purged`：那是板端历史状态，
  数据在本机，可正常回放。
- 改的是源码副本；控制台走 `dist\console_passthrough.ini` → 源码旁路，**重启总控制台**即生效；
  若要固化进 EXE 需按 `pc_apps/console/make_release.py` 重建（本轮未做）。

技能：ponytail `C:/Users/30680/.config/opencode/skills/ponytail`——复用既有
`_local_sessions`/`_is_ready_for_load`、既有板端 HEAD/DELETE 路由、既有测试文件，
不新增配置层与脚本。
