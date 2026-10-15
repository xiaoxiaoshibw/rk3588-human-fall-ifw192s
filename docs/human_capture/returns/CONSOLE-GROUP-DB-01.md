# CONSOLE-GROUP-DB-01 回传

- 用户授权（2026-10-15 直派）：总控制台模块收纳归类 + 新增数据库模块支持删除。两处决定经用户选择：数据库 = 会话库总表 + 分级删除；归类 = 分栏分组标题。
- [唯一验收 v1](../evidence/2026-10-15_hc_console_groups_db_r1/ACCEPTANCE_V1.md)、[根因/改动/验证/限制](../evidence/2026-10-15_hc_console_groups_db_r1/README.md)。SUBMITTED 未 ACCEPTED，独审 NOT_RUN。
- 改动（PC 侧 5 文件 + 2 新文件）：`console.html` APPS 加 `group` + `GROUPS` 分栏渲染 + 「会话数据库」卡片（`APPS[0]` 仍是会话回放，联合录制 `?sid` 契约不变）；`human_replay_lib.py` 新增只读 `GET /api/manifest`（本机逐文件 name+bytes+sha256 + 板端登记行，sid 白名单）；新页 `sessions_db.html`（总表 + 总览 + 清单/删本机/删板端/删两侧）；`sessions_test.py` +2 清单用例；`console_html.test.js` +2 分栏用例；`README.txt` 入口清单改分栏版。
- 删除纪律沿用 2026-10-14 要求：先清单（文件数/字节/sha256）→ 弹窗写明 → 人工确认 → 才 `POST /api/delete`（既有接口未改），弹窗另提示确认该会话没有在录制/拉回。
- 自验：`console_html` **19**、`console_test` **7**、`sessions` **7**（+2）、`joint_capture` **10**、`fetch_lib` **13** 全 exit 0；真数据 + 真板只读端到端：`sessions_db.html` 200、`/api/manifest?sid=cap_20261015_142730` 出 meta.json 35,345B + points.bin 237,644,764B 且 **sha256 与独立计算逐位一致**、文件仍在（`DB_PROBE.json`）。
- 重打与重启：`Console.exe` 193,819,286B / `33D53CF5…`（备份 `dist/Console.exe.bak-20261015_before_groupsdb`）、`LiDAR_Console.zip` 151,051,879B / `E2D0BD89…`；zip 内源码副本与树逐文件同哈希；重启后冻结壳页 15,434B 含 GROUPS/分栏 CSS/数据库卡片/数据管理栏，冻结 :8901 数据库页 200 且清单接口可用（`FROZEN_PROBE.json`）。
- NOT_RUN/限制：真机浏览器点击与**真实删除动作**未跑（现场零删除——`captures/`/`data/` 一个字节未动）；只做会话层（不含 `data/leveled|registration|downloads`）；板端 sha256 不算（要下载）；页内不放同步/改名（留在回放面板）；独立复审 NOT_RUN。未改板端/`fetch.py`/`joint_capture.*`/模型/GT，无 commit/push/部署/采集。
- 技能：`C:/Users/30680/.config/opencode/skills/ponytail`（skill 工具加载，full）——复用既有 `/api/sessions` 与 `/api/delete`、零新依赖、只新增一个只读清单接口与一个静态页。

## R2 首页「归档」区（2026-10-15，同一直派续）

- 用户续派「现在用不到的算法可以归档」。口径：**首页层面的收纳**——7 项研究/算法页（算法验证 / 人体识别 / 人检锁定 / 骨架与倒地检测 / 真人倒地回放 / 小目标跟踪 / 逐源标注与学习对照）加 `archived` 标记，收进启动页最下面「归档」区，**默认折叠**、点标题展开/收起；页面/URL/代码/exe 内嵌副本一个不少，零删除。
- [唯一 R2 v1](../evidence/2026-10-15_hc_console_groups_db_r2/ACCEPTANCE_V1.md)、[证据与限制](../evidence/2026-10-15_hc_console_groups_db_r2/README.md)。
- 改动 3 文件：`console.html`（`archived` 标记 + 拆 `make_card()` + `.group.archived`/`gtoggle` 折叠容器 + CSS）、`console_html.test.js`（分栏用例改口径 + 新增归档用例：默认折叠/展开收起/卡片不丢/在用入口不得归档/归档卡仍可进页）、`README.txt`（入口清单按可见+归档重写）。`APPS` 索引/URL/`?sid` 自动载入/`?hash` 深链不变。
- 自验：`console_html` **20**、`console_test` 7、`joint_capture` 10、`sessions` 7 全 exit 0；重打 `Console.exe` 193,818,509B/`6C9C65E4…`（备份 `.bak-20261015_before_archive`）、`LiDAR_Console.zip` 151,052,851B/`25ACD3EC…` 并重启，冻结壳页 17,290B 含归档区（`archived:true`×7），数据库页与清单接口未回归（`FROZEN_PROBE.json`/`DB_PROBE.json`/`FILE_SHAS.json`）。
- NOT_RUN：真机点归档标题；「真归档」（把页面/源码移出 exe 与仓库，需改 `Console.spec`/`make_release.py` 清单）本轮未做；独审 NOT_RUN。归档默认集合是我的判断（都在用链 = 录制→回放→标注→数据管理之外），要调整就是增删一处 `archived:true` 并重打。
- 技能：`C:/Users/30680/.config/opencode/skills/ponytail`（skill 工具加载，full；一行标记 + 一个折叠容器，零新依赖）。
