# HC-JOINT-LOCAL-01 R3 界面文案对齐验收 v1

用户指出总控制台联合录制卡片与页面文案是旧直写本机口径（"数据直接保存到本机"），与现行实际行为（板端先录制、停止后拉回本机）不符，要求修正。
范围：pc_apps/console 文案与注释、本工单证据/回传。不改行为/接口/板端/数据，不重打 EXE（需要时另行授权），不提交推送。
唯一 writer 本轮为主控；技能 C:/Users/30680/.claude/skills/ponytail/SKILL.md。独审 NOT_RUN。

| ID | 要求 |
|---|---|
| JT07 | console.html 联合录制卡片 desc 与 README.txt 入口行改为"板端先存/结束后拉回本机"口径 |
| JT08 | joint_capture.html 删除现行代码不会产生的 completed_with_gaps 状态与提示（死文案) |
| JT09 | README.txt 联合录制段按现行行为重写（会话目录、输出文件、时长/磁盘限制、拉回重试） |
| JT10 | joint_capture.py/test.py 过时注释同步；三套现有测试回归通过并留日志 |

行为语义、拉回触发方式、EXE 重建、浏览器/设备验证不在本轮范围（NOT_RUN）。
