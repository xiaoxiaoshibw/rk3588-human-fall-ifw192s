# CONSOLE-GROUP-DB-01 R2 唯一验收表 v1（2026-10-15）

范围：首页「归档」区——把现在用不到的研究/算法页收进折叠区（渲染层，不动代码/页面/数据）。
口径与限制见 [README](README.md)。

| ID | 判据 | 结果 | 证据 |
|---|---|---|---|
| AR-01 | `archived` 标记的条目只在归档区渲染，可见分栏不含它们；可见栏 = 有可见卡片的组，栏序同 GROUPS | **PASS** | `TESTS_console_html.log`（分栏用例新口径） |
| AR-02 | 归档区是首页最后一栏（`group archived`），卡片数 = `archived` 标记数，且**默认折叠**；点标题展开、再点收起（`hidden` 翻转 + 文案跟随） | **PASS** | `TESTS_console_html.log`（归档用例） |
| AR-03 | 卡片不丢：可见 + 归档 = `APPS.length`；在用入口（USB 摄像头、USB＋雷达联合录制、会话回放、GT 标注、会话数据库）不被归档 | **PASS** | 同上 |
| AR-04 | 归档不改契约：`APPS` 索引/URL 不变（`APPS[0]` 仍是会话回放，联合录制 `?sid` 自动载入不受影响）；归档卡点击仍进对应页 | **PASS** | 同上 + 既有 APPS[0..3] 用例 |
| AR-05 | 回归：`console_html` 20 / `console_test` 7 / `joint_capture` 10 / `sessions` 7 全 exit 0 | **PASS** | `TESTS_*.log` |
| AR-06 | 重打 + 重启：冻结壳页含归档区（`group archived`+`gtoggle`，`archived:true` ×7）；zip 内源码副本与树逐文件同哈希；数据库页与清单接口未回归 | **PASS** | `FROZEN_PROBE.json`、`FILE_SHAS.json`、`DB_PROBE.json` |
| AR-07 | 真机浏览器点击归档标题展开/收起 | **NOT_RUN**（Node 替身已判 hidden/回调；需人工点） | — |
| AR-08 | 真归档（把页面/源码移出 exe 与仓库目录） | **NOT_RUN**（本轮口径为首页收纳；用户如要另议） | — |
| AR-09 | 独立复审 | **NOT_RUN** | — |

判定：AR-01～AR-06 PASS，AR-07～AR-09 NOT_RUN；**SUBMITTED，未 ACCEPTED**。
本轮零删除、零数据写入（`captures/`/`data/` 未动）；未改板端/`fetch.py`/`joint_capture.*`/模型/GT，
未 commit/push/部署/采集。
