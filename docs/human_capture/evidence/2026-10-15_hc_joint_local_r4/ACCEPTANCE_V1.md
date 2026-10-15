# HC-JOINT-LOCAL-01 R4 唯一验收 v1（2026-10-15）

范围：拉回完成 → 自动打开会话回放载入该会话 + 内嵌契约探针 + 双 EXE/ZIP 重打。
判定基准：上表 PASS 仅代表本机离线自验与冻结产物检查；设备实录/端到端与浏览器人工操作 **NOT_RUN**，独审 **NOT_RUN**。

| ID | 验收点 | 结果 | 依据 |
|---|---|---|---|
| JA01 | 联合页仅在"刚进入 completed"时发一次消息；仅内嵌控制台时发送；sid=本地目录名且过白名单 | PASS | `joint_capture.html` 审读 + 合同用例 |
| JA02 | 壳页收到合法消息 → 打开「会话回放」并带 `?sid=` 载入；已开过回放强制重载 | PASS | `TESTS_console_html.log` 新用例 1 |
| JA03 | 非法来源 origin / 非法 type / 非法 sid 一律忽略（不改 iframe、不切视图） | PASS | `TESTS_console_html.log` 新用例 2 |
| JA04 | 回放页消费 `?sid=` 自动载入；无 `?sid` 入口不受影响 | PASS | 合同用例 3 + 探针 `replay_page` |
| JA05 | 文案与行为一致（console 卡片 / README / 联合页页脚） | PASS | 对读 + `ROUND4_DIFF.patch` |
| JA06 | 回归：console 15/4/7、human_replay node 45/1/11/38/7、python 18 全绿 | PASS | `TESTS_*.log` 六份 |
| JA07 | 冻结 EXE 内嵌契约：`--check-joint-capture` exit 0 且 `page_version` 3/3 true | PASS | `JOINT_PROBE_FROZEN.json` |
| JA08 | 冻结 EXE `--check-startup`：replay/fall 起；real fall 缺 `cap_20261013_094333`/`131958` 未起（既有，源码复现） | BLOCKED（环境，既有） | `STARTUP_PROBE_*.json` |
| JA09 | 真实录制一段 → 拉回完成自动跳转回放（板端在线实机） | NOT_RUN | 未动板端/未采集；用户可自测重打版 |
| JA10 | 独立窗口打开联合页时不得误跳（无 parent 场景） | PASS | 条件分支 + 审读（无浏览器操作） |

未闭合/限制：自定义保存目录场景自动载入会失败（回放状态栏可见）；"弹出"= 控制台内切换（非新窗口）；未 commit/push；独审未做。
