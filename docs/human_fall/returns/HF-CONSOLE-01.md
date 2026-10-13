# HF-CONSOLE-01 回传

## 2026-10-13 R1 / Codex唯一writer / SUBMITTED

用户将“集成WEBUI”具体指向桌面总控制台.lnk，目标pc_apps/console/dist/Console.exe。已新增“骨架与倒地检测”入口、控制台内嵌原全过程；同进程随机端口自动起回放，无外部Python/旧8931依赖；实际目标EXE与ZIP重建，不修改快捷方式。

[唯一v1](../evidence/2026-10-13_hf_console_01_r1/ACCEPTANCE_V1.md)/[完整报告](../evidence/2026-10-13_hf_console_01_r1/FINAL_REPORT.md)。CI01–CI05作者自验PASS；CI06范围PASS、识别精度BLOCKED、独审/设备物理部署NOT_RUN。未ACCEPTED。

JS11/Python6全部过；实际headless Edge首页→iframe两WebGL画布/REAL-01/f72告警/返回状态保留/空场未锁定，console errors空。PyInstaller真实exit0、make_release exit0；打包HTML逐字节与源相符、launcher compiled存在。实际EXE从TEMP隐藏运行--check-startup exit0，自行启动62912、读f72告警/13槽并匹配两输入SHA；退出后两个端口关闭。不是原生窗口手工点击验收。

基线master/026e06303f60ed1bbe4ddc4d037836db68da6d27，19317全树SHA非原子/errors0；变更前originals备份与SHA，不把长扫描后的before副本当改前源码。IMPLEMENTATION_DIFF/FINAL_SHA见证据。未改原算法/回放产物/GT/模型/输入/板端/driver/网络，无Git写。此入口依赖本工作区既有数据，未装成通用实时识别能力。

ponytail C:/Users/30680/.codex/skills/ponytail/SKILL.md。用户重新打开桌面总控制台即可使用新卡片，旧已开实例需重开才加载新EXE。
