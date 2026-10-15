# 2026-10-15 CONSOLE-GROUP-DB-01 R2 首页「归档」区（现在用不到的算法页收起）

**触发（用户直派）**：「现在用不到的算法可以归档」——承接 R1 的首页分栏归类。

**口径（本轮采用，先说清楚）**：归档 = **首页层面的收纳**——研究/算法页收进启动页最下面的
「归档」区，**默认折叠**，点标题展开/收起；页面、URL、代码、exe 内嵌副本一个都没少，
删除动作零（数据目录一个字节未动）。如果要的是「把源码/页面文件搬进 archive 目录」那种
真归档（会动 `pc_apps/human_replay/*.html`、exe datas、make_release 清单），另开一轮，本轮没做。

## 改了什么（3 文件，其中 1 个仅文案）

| 文件 | 改动 |
|---|---|
| `pc_apps/console/console.html` | APPS 新增 `archived` 标记：`算法验证 / 人体识别 / 人检锁定 / 骨架与倒地检测 / 真人倒地回放 / 小目标跟踪 / 逐源标注与学习对照`（7 条）默认归档；渲染拆出 `make_card()`，可见区只渲染 `!archived`，末尾追加 `.group.archived` 一栏（`button.gtoggle` 标题写「归档 · N 项（现在用不到的研究/算法页；点开显示）」+ `cards[hidden]` 折叠容器，点击切换并按状态改文案）；CSS 加 `[hidden]` 兜底与归档栏分隔线、`gtoggle` 样式 |
| `pc_apps/console/console_html.test.js` | 分栏用例改为「可见栏 = 有可见卡片的组」；新增归档用例：归档区在最后一栏、卡片数 = `archived` 标记数、**默认折叠**、点标题展开/再点收起、可见+归档 = APPS 全部、在用的 5 个入口不得被归档、归档卡点击仍进对应页（索引/URL 不变） |
| `pc_apps/console/README.txt` | 入口清单按新口径重写：可见 = 采集录制/回放与标注/板端与平台/数据管理；归档附 6 项清单与「删掉 `archived:true` 即可回到可见区」 |

`APPS` 索引、URL、`?sid` 自动载入（`APPS[0]`=会话回放）、`?hash` 深链全部不变；
归档只在渲染层生效，`open(i)` 对归档项照常工作。

## 验证（本机；只读）

| 项 | 结果 | 证据 |
|---|---|---|
| `console_html.test.js` | **20 PASS**（+1 归档用例，分栏用例同步改口径） | `TESTS_console_html.log` |
| `console_test.py` | 7 OK | `TESTS_console_py.log` |
| `joint_capture_test.py` | 10 OK（回归） | `TESTS_joint_capture.log` |
| `sessions_test.py` | 7 OK（回归，R1 的清单接口） | `TESTS_sessions.log` |
| 重打 + 重启 + 冻结探针 | `Console.exe` 193,818,509B / `6C9C65E4…`（备份 `.bak-20261015_before_archive`）、`LiDAR_Console.zip` 151,052,851B / `25ACD3EC…`，zip 内源码副本与树逐文件同哈希；重启后壳页 17,290B **含归档区（`group archived` + `gtoggle`）且 `archived:true` 出现 7 次**；冻结 :8901 数据库页 200、`/api/manifest` 出 points.bin 237,644,764B 且 sha256 与独立计算一致 | `FROZEN_PROBE.json`、`FILE_SHAS.json`、`DB_PROBE.json`、`PYINSTALLER.log`、`MAKE_RELEASE.log` |

## 限制

- 归档项仍内嵌在 exe 里（约等于多几百字节），只是首页不占版面；用户若要彻底不在 exe 内，
  需改 `Console.spec` datas / `make_release.py` 清单，属另一次授权。
- 真机浏览器里点一下「归档」标题展开/收起 NOT_RUN（Node 替身已判 `hidden` 状态与点击回调）。
- 归档默认集合是**我的判断**（7 项都属「研究/原型/验证」页，且当前在用链是录制→回放→标注→数据管理）。
  要调整就是把某条 `archived:true` 删掉或加上——一行一处，改完需重打 exe 才生效。
- 独立复审 NOT_RUN。
