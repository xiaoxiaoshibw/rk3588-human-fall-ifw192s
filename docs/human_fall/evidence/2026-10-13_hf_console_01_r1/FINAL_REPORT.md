# HF-CONSOLE-01 R1 总控制台入口集成 / SUBMITTED

2026-10-13，用户明确指向桌面C:/Users/30680/Desktop/总控制台.lnk。实际目标D:/Code/ldiar/pc_apps/console/dist/Console.exe，Arguments空、WorkingDirectory为dist。未改快捷方式；已更新它实际指向的EXE及LiDAR_Console.zip。Codex唯一writer，ponytail实际C:/Users/30680/.codex/skills/ponytail/SKILL.md。

首页新增“骨架与倒地检测”，iframe显示原真人锁定/骨架/倒地检测过程。控制台从当前仓库定位r02及已生成证据，runpy导入后在同进程独立loopback随机端口启动回放，URL传入fall_port，随控制台进程退出。无需另跑8931或外部Python终端。原会话回放/GT/板端/摄像头等入口不变。

当前是此工作区已有两个会话的离线原型，不是任意会话实时人体/骨架算法。移动EXE到没有工作区/数据的电脑时该卡片显示未就绪，其他入口仍可使用；未额外把原始真人点云打进ZIP。原完整纯人体FAIL/解剖骨架BLOCKED等识别限制保持，不因集成升级成绩。

## 验收v1

| ID | 状态 | 证据与边界 |
|---|---|---|
| CI01 | PASS | 实际COM读取快捷方式目标；master/026e06303f60ed1bbe4ddc4d037836db68da6d27；全树19317 SHA/errors0非原子；originals与ORIGINALS_SHA是实际变更前源码/EXE/ZIP备份，before目录是长扫描后副本不可当源码变更前证据 |
| CI02 | PASS | console新增卡片/动态iframe；11 JS回归全部过；missing port明确未就绪；真正浏览器首页与内嵌告警/空场截图 |
| CI03 | PASS | 源启动fall56139；实际EXE在TEMP工作目录启动fall62912/独立端口，读取原数据；进程结束8901/62912均真实不可连接。原8931临时服务未被接管，不作为新入口依赖 |
| CI04 | PASS | console JS11/Python6回归exit0；真实Edge控制台卡片→iframe告警REAL-01、两WebGL画布/节点/告警保持；返回后f72保留，空场无锁定，console errors[] |
| CI05 | PASS | PyInstaller实际exit0，BUILD.log；EXE191301537bytes、SHA cca76928cdea2189633cdc2b8d9387d2b61fbe5d9682f7bd81e9d6be6dfed1d5；抽取嵌入HTML与现源逐字节一致、compiled launcher存在；真实frozen --check-startup exit0并读取f72告警/13槽。ZIP make_release exit0/约148.5MB，最新SHA见FINAL_SHA |
| CI06 | PASS（范围） / BLOCKED / NOT_RUN | 原r02算法/回放产物/输入载入SHA保持；原模型GT未改；算法精度BLOCKED保持，独审/设备/物理/板端部署NOT_RUN。不ACCEPTED |

## 实际验证与范围

`node console_html.test.js`：11 passed/0 failed；`python -B -W error console_test.py`：6 OK。源码`console_gui.py --check-startup <SOURCE_STARTUP.json>` exit0。

`python -m PyInstaller --noconfirm Console.spec` exit0；未改spec，沿用既有datas/依赖；发布包尺寸变化随当前人检目录已存文件，不将增长全归本次数十行入口代码。`python -B make_release.py` exit0；只目标EXE/ZIP更新，原文件实际备份在originals。

从TEMP以隐藏窗口启动实际EXE --check-startup，退出码0，FROZEN_STARTUP.json：164真人/97空场、f72/alert_active true/13骨架槽，正确当前仓库输入SHA和动态shell URL。是frozen服务/数据入口实测，不冒称原生WebView2窗口截图。真实headless Edge已验证相同控制台HTML与实际iframe服务，BROWSER_CHECK/CONSOLE_HOME/CONSOLE_EMBEDDED_ALARM。发布EXE内嵌HTML逐字节匹配源；GUI原生窗口手工点击未另测试。

初次只读rg查询误把PowerShell的-ErrorAction给rg导致exit1，随后直接Get-Content读ini，没有改配置；属于诊断命令失败。现有console_passthrough.ini指向本仓human_replay，保持。没有停止用户程序、改变板端/网络/driver、Git写或修改原识别算法/GT/原数据；旧8931/8929不动。

新入口缺数据时不尝试连接旧临时端口，不影响原回放；多控制台各自新fall端口，避免旧页面/新代码混用。本次作用范围只console_gui.py/console.html/对应tests和EXE/ZIP以及授权记录；修改前本就脏的console.html差异保留，IMPLEMENTATION_DIFF只与originals对比本轮增量。

全树扫描非原子且写入准备期间可能记录新文件，不宣称全树冻结；originals才是改前备份。结束原r02与数据等加载资产逐项SHA绑定，最后记录另FINAL_SHA。状态SUBMITTED，不自行ACCEPTED。
