总控制台 · 八段动作人体与倒地姿态回放 · 2026-10-14

【2026-10-15 合并说明】两个总控制台已合并为单一 dist\Console.exe，桌面只保留“总控制台.lnk”（指向它）；
本文件与 dist\LiDAR_Console_Pointset.zip 作为点集专版历史发布物保留，以下为当时说明。

当前本机桌面“总控制台”指向 dist/Console_Pointset.exe。
旧Console.exe和正在运行的旧窗口保留；关闭旧窗口后重新双击桌面快捷方式，可看到新入口。
“骨架与倒地检测”启动 pointset/r01 原页面；默认八段动作、只显示中央目标，原九会话可切换。

本机开发发布包依赖 D:/Code/ldiar 的 pointset/r01/action_output 和原九会话output。
ZIP是本机EXE/源码备份，不含原始录制或完整离线数据，不是独立移动版数据包。
仅后台读取既有离线产物；不启动板端采集，不打开确认跌倒。

框体/骨架均由当前源点构建。骨架是粗部位中心，部分躺地帧轴歧义时显示缺测。
倒地姿态候选不等于真实失衡跌倒；初始躺地不会伪造先前站立或跌倒事件。
报告：docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r1/FINAL_REPORT.md
回放：http://127.0.0.1:8944/（独立测试服务），控制台实际服务为自己的动态端口。
