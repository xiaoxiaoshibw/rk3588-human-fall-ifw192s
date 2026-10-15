# 2026-10-15 CONSOLE-GROUP-DB-01 总控制台首页分栏归类 + 会话数据库模块（含分级删除）

**触发（用户直派）**：「然后在总控制台把这些模块收纳归类，再加入一个数据库模块支持删除功能。」
两处决定经用户选择：数据库模块 = **会话库总表 + 分级删除**；归类方式 = **分栏分组标题**。

## 改了什么（PC 侧 5 文件 + 2 新文件）

| 文件 | 改动 |
|---|---|
| `pc_apps/console/console.html` | APPS 每条加 `group`；新增 `GROUPS`（采集录制 / 回放与标注 / 检测与研究 / 板端与平台 / 数据管理）；首页按栏渲染（栏标题 + 栏内 cards 网格，未知 group 落「其他」栏兜底）；新增「会话数据库」卡片指向 `replayBase + "/sessions_db.html"`；CSS `#grid` 改 block + `.group/.gtitle/.cards` |
| `pc_apps/console/console_html.test.js` | DOM 替身加 `children/appendChild`、每次装载清卡片树；+2 用例：分栏不丢不重且栏序 = GROUPS（每卡必须有合法 group，禁止「其他」栏）、数据库入口用本实例端口且 `APPS[0]` 仍是会话回放 |
| `pc_apps/human_replay/human_replay_lib.py` | 新增 `_dir_manifest()` + `GET /api/manifest?sid=`：本机会话逐文件 `name/bytes/sha256` + 板端登记行；sid 白名单 400；手写 sha256 分块读，只读不删 |
| `pc_apps/human_replay/sessions_db.html`（新） | 会话数据库页：总表（会话/时间/时长/帧/大小/板端/本机）+ 总览（行数、本机个数与合计字节、已隐藏无数据登记）+ 行内「清单 / 删本机 / 删板端 / 删两侧」 |
| `pc_apps/human_replay/sessions_test.py` | +2 用例（`ManifestTest`）：本机文件逐个哈希 + 只读校验（文件仍在）；sid 越界 400、本机缺失、板端 404/不可达分支 |
| `pc_apps/console/README.txt` | 入口清单改为分栏版（补上小目标跟踪、会话数据库），说明删除纪律 |
| `pc_apps/console/make_release.py` | 未改（`../human_replay` 整目录已在 Console.spec datas 内嵌，zip 里 human_replay 源码副本沿用原清单） |

未改：板端 `src/human_capture/**`、`fetch.py`、`joint_capture.*`、`index.html`/`panel.js`/`gt_*`、模型、GT、`captures/`/`data/`（本轮**零删除**）。

## 删除纪律（沿用 2026-10-14 用户要求）

页面点删除 → 先取清单（`/api/manifest`：文件数、总字节、主文件 sha256）→ 弹窗把 sid/文件数/字节/
sha256 前缀写明 → 人工确认 → 才 `POST /api/delete`（scope=local|board|both，已有接口，未改）。
弹窗另提示「确认该会话没有正在录制/拉回」。本机无副本/板端 404/板端 409 忙碌各分支沿用既回报文案。

## 验证（本机；真数据 + 真板，只读）

| 项 | 结果 | 证据 |
|---|---|---|
| `console_html.test.js` | **19 PASS**（+2） | `TESTS_console_html.log` |
| `console_test.py` | 7 OK | `TESTS_console_py.log` |
| `sessions_test.py` | **7 OK**（+2 清单用例；含 sha256 与独立计算一致、只读不放行删除） | `TESTS_sessions.log` |
| `joint_capture_test.py` | 10 OK（回归，本轮未改该文件） | `TESTS_joint_capture.log` |
| `fetch_lib_test.py` | 13 OK（回归） | `TESTS_fetch.log` |
| 会话数据库端到端（真 `captures/remote` + 真板，只读） | 页面 200；`/api/manifest?sid=cap_20261015_142730` → meta.json 35,345B + points.bin 237,644,764B，**points.bin sha256 与独立计算逐位一致**；板端行 transferred/173 帧；文件仍在 | `DB_PROBE.json`（`db_probe.py`） |
| 重打 + 冻结 exe 行为探针 | `Console.exe` 193,819,286B / `33D53CF5…`、`LiDAR_Console.zip` 151,051,879B / `E2D0BD89…`；zip 内源码副本与树逐文件同哈希；重打后重启，壳页（pywebview 两端口）15,434B **含 GROUPS / 分栏 CSS / 会话数据库卡片 / 数据管理栏**；冻结 :8901 `sessions_db.html` 200（9,294B，含 manifest/delete 调用）且 `/api/manifest` 正常出 sha256 | `FROZEN_PROBE.json`（`frozen_probe.py`）、`FILE_SHAS.json`、`PYINSTALLER.log`、`MAKE_RELEASE.log` |

## 限制（如实）

- 删除动作本机**未真跑**（现场零删除）：只验到「清单→确认→POST」链路的两端（清单实测、`/api/delete` 既有接口与既有测试）；真实点一次「删本机/删两侧」删掉哪份、板端 409 忙碌文案，NOT_RUN。要验的话建议先删本轮已知重名副本之一（R7 记录里的 142730/111738），我会先出清单。
- 数据库模块只看会话（`captures/remote` 层），不含 `data/leveled`、`data/registration`、`data/downloads`（用户选择的最小范围）。
- 页内没有「同步/导入/改名」按钮（保留在会话回放面板），避免两套入口行为分叉。
- 板端 sha256 不做（要下载才能算）：清单里板端只给登记行（state/帧数/字节）。
- 首页分栏只改渲染，`APPS` 索引不变（`APPS[0]` 仍是会话回放，联合录制 `?sid` 自动载入依赖它，有测试钉住）。
- 真机浏览器点击（WebView2 里实际点卡片/点清单一遍）NOT_RUN；独立复审 NOT_RUN。
