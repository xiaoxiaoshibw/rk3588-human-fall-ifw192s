# HF-CONSOLE-02 骨架与倒地回放入口

本轮只增加真实录制 r04 回放入口；保留控制台现有 pointset/r01 八段动作演示。真实跌倒仍是未确认的原型告警。

| ID | 验收要求 | 状态 |
|---|---|---|
| C02-01 | 复用同HEAD完整树快照并记录当前控制台 overlay SHA；保存覆盖前源码、规格、两份EXE与ZIP | PASS |
| C02-02 | 控制台分别启动 pointset/r01 与 real_fall/r04 的本机回放服务，端口动态分配；缺少 r04 数据时不影响现有入口 | PASS |
| C02-03 | 首页保留原“骨架与倒地检测”pointset入口，新增“真人倒地回放”入口；两入口指向各自数据 | PASS |
| C02-04 | r04直接验证164帧、frame72候选、13个当前点支撑槽、固定单个未确认prototype事件，空场0目标/0事件 | PASS |
| C02-05 | Headless Edge 打开实际控制台壳页和两个服务；新入口画面/帧72/两视图与旧入口均可用 | PASS |
| C02-06 | 源码及 Console.exe / 快捷方式目标 Console_Pointset.exe 均通过无GUI启动检查；ZIP与两EXE内嵌壳页绑定一致 | PASS |
| C02-07 | 独立复审 NOT_RUN；人体/家具/关节GT与泛化 BLOCKED；设备/物理 NOT_RUN | NOT_RUN / BLOCKED |

禁止项：不更改原始录制、GT、模型、生产算法、服务端部署与快捷方式目标；不提交或推送。显示平滑不参与倒地判定。
