# CONSOLE-GROUP-DB-01 唯一验收表 v1（2026-10-15）

范围：总控制台首页分栏归类 + 新「会话数据库」模块（会话总表、清单、分级删除）。
仅判本轮 PC 侧（console.html/README + human_replay 清单接口 + 新页）；真机点击、真实删除
动作、派生数据目录、独立复审各自单列。

| ID | 判据 | 结果 | 证据 |
|---|---|---|---|
| CG-01 | 首页卡片按 `GROUPS` 分栏渲染；每张卡都有合法 group，卡片不丢不重，栏序 = GROUPS，无「其他」栏 | **PASS** | `console_html.test.js` 新用例；`FROZEN_PROBE.json` 壳页含 GROUPS/分栏 CSS/数据管理 |
| CG-02 | 分栏不改应用索引契约：`APPS[0]` 仍是会话回放（联合录制 `?sid` 自动载入依赖），本地应用仍不带 `fail` | **PASS** | `console_html.test.js`（新用例 + 既有 APPS[0..3] 用例） |
| CG-03 | 新「会话数据库」入口存在、group=数据管理、指向**本实例**回放服务 `/sessions_db.html` | **PASS** | `console_html.test.js` 新用例；冻结壳页含 `sessions_db.html` |
| CG-04 | `GET /api/manifest?sid=` 返回本机逐文件 `name/bytes/sha256` + 板端登记行；sid 白名单越界 → 400；只读不删 | **PASS** | `sessions_test.py::ManifestTest` 2 用例；`DB_PROBE.json`（真数据 sha256 与独立计算一致） |
| CG-05 | 删除链路保持仓库纪律：先清单 → 弹窗写明 sid/文件数/字节/sha256 → 人工确认 → `POST /api/delete`（既有接口未改） | **PASS（实现与清单端实测；真实删除未跑）** | `sessions_db.html` 代码 + `DB_PROBE.json` |
| CG-06 | 回归：`console_html` 19 / `console_test` 7 / `sessions` 7 / `joint_capture` 10 / `fetch_lib` 13 全 exit 0 | **PASS** | `TESTS_*.log` |
| CG-07 | 重打 + 重启：冻结 `Console.exe`/`LiDAR_Console.zip`；zip 内源码副本与树逐文件同哈希；冻结壳页/回放服务行为可见（分栏、数据库页、清单接口） | **PASS** | `FROZEN_PROBE.json`、`FILE_SHAS.json`、`PYINSTALLER.log`、`MAKE_RELEASE.log` |
| CG-08 | 真机浏览器里实际点卡片进入数据库页、点清单、点一次删除 | **NOT_RUN**（需人工点；现场零删除） | — |
| CG-09 | 派生数据（`data/leveled`、`data/registration`、`data/downloads`）纳入总表与删除 | **NOT_RUN**（用户选择最小范围，未做） | — |
| CG-10 | 独立复审 | **NOT_RUN** | — |

判定：CG-01～CG-07 PASS，CG-08～CG-10 NOT_RUN；**SUBMITTED，未 ACCEPTED**。
本轮零删除（`captures/`/`data/` 一个文件未动）；未改板端/`fetch.py`/`joint_capture.*`/模型/GT，
未 commit/push/部署/采集。
