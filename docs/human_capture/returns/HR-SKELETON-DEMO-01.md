# HR-SKELETON-DEMO-01 追加回传

## 2026-10-12 / R1 / Codex唯一writer / SUBMITTED

用户明确“现在能不能实现一下骨架标定给我看看”。当前唯一验收 [v2](../evidence/2026-10-12_hr_skeleton_demo_01_r1/ACCEPTANCE_V2.md)，v1失败和源保留；[完整交付与逐ID](../evidence/2026-10-12_hr_skeleton_demo_01_r1/FINAL_REPORT.md)。不跨入旧SKO验收或跌倒新单。

已打开真实点云粗骨架 http://127.0.0.1:8927/ ，隔离源 sidequests/human_fusion_lab_next/skeleton_demo/r02/；启动server_v3.py/start_demo_v3.bat。默认明确使用已有人工人体点集，机器候选模式保留。五指定真人参照帧各五区域节点，下部未分离UNKNOWN、顶部头/手未确认、手臂/肘/腕未估计；不是自动完整人体骨架，也未完成人工解剖节点标定。

SD01–SD06作者自验PASS（数学/工程/浏览器有明确限定）；SD07真人精度与标定BLOCKED、跌倒/设备/部署NOT_RUN。不自行ACCEPTED；没有外部独审。4检查exit0/-B -W error、Python3.8/JS语法通过，独立struct/标量/中位数七场raw核查误差0m、四非法API 400、真实浏览器及错误SHA停止检查；数量不替代验收。

近距自动793点混簇候选五带全部UNKNOWN保留；此前range max顺序错位由新UI v3修正，旧页/日志不改；误名旋转截图和native裁切截图明确排除，用fresh真实画布操作截图替代。工具与真人自动效果分开。

起始master / 026e06303f60ed1bbe4ddc4d037836db68da6d27。before15879/end15911 tracked/untracked/ignored全SHA、非原子/.git排除；无范围外变化/新增/缺失/errors/drift。仅新隔离代码/本证据、本return和README当前登记；结束后新增自有记录另存SHA。原生产/输入/GT/模型未改，无Git写/部署采集/板端/驱动网络/ML/代理。临时8925/8926/8928自有测试服务已停；8927留给用户查看。

ponytail实际读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md。后续若要求自动准确骨架，需先解决候选混簇并取得真实节点参照；本次不自动扩展新模型或生产接入。
