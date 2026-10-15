# HF-CONSOLE-02 回传

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HF-CONSOLE-02 / r1 / Codex / 2026-10-14。
- 验收表：`docs/human_fall/evidence/2026-10-14_hf_console_02_r1/ACCEPTANCE_V1.md`，v1；最终 SHA 见 `FINAL_SHA.json`。
- branch / HEAD：`master` / `c21c443b0befe559e08283edb0efc2af02dcc6b8`。未提交或推送。
- 技能：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。
- 前态：同HEAD完整全树SHA快照22,438项来自 `2026-10-14_hf_real_close_data_bg_r1/BASELINE_BEFORE.json`；本轮控制台及r04前态SHA叠加记录于 `PRE_EDIT_STATE.json`。当前桌面快捷方式为 `D:/Code/ldiar/pc_apps/console/dist/Console_Pointset.exe`，工作目录 `D:/Code/ldiar/pc_apps/console/dist`，未改快捷方式。

## 诊断与实现

直接浏览器视觉证据显示稀疏点云下的几何轴不稳定、转场槽缺测和背景粘连；旧页面帧节奏约9.6Hz，旧剖析中帧读取/JSON处理P95约58ms、整次更新P95约130ms、绘制约2ms。主要缺口是观测频率、背景/人体身份不确定和几何时序，不是GPU绘制，也没有证据表明现在应先训练ML模型。

沿用现有 r04 修复页：背景开头0–4帧离线warmup、弱轴限时参考、逐帧测量与短时显示保持分离、复用WebGL对象、测量时钟播放、相邻帧预取、部位支撑按需加载。f10旧/新目标点1352/1208，部位槽9/12；f47/f109/f118有效槽0/0/0→12/12/13。END_A有效帧88→136，状态切换32→17，位置跳变P95 .759m→.132m。TOP_REGION显示P95 .123m→.131m恶化，END_B有效帧155→120下降；删除点身份未知，解剖准确率无GT。

控制台现在保留 pointset/r01“骨架与倒地检测”卡片，并新增“真人倒地回放”卡片，各起自己的本机动态端口服务。README、两个PyInstaller规格和发布脚本同步；修复构建规格对已缺失 `console_icon.png` 的依赖，改用仓库已有 `console_icon.ico`，未恢复或改写原删除文件。`Console.exe` 与桌面快捷方式实际目标 `Console_Pointset.exe` 均已重建，ZIP含两者。

## 验收状态

| ID | 结果 | 证据 |
|---|---|---|
| C02-01 | PASS | 同HEAD全树基线与当前文件overlay、覆盖前源码/spec/EXE/ZIP备份：`PRE_EDIT_STATE.json`、`POINTSET_PREBUILD_STATE.json`、`originals/` |
| C02-02 | PASS | 源码启动与快捷方式目标冻结EXE均以独立动态端口启动pointset/r01和real_fall/r04：`SOURCE_STARTUP.json`、`POINTSET_FROZEN_STARTUP.json` |
| C02-03 | PASS | 两入口各自加载服务，浏览器首页及iframe截图：`BROWSER_CHECK_FINAL.json`、`CONSOLE_HOME_FINAL.png`、`CONSOLE_REAL_FALL_FINAL.png` |
| C02-04 | PASS | r04 164帧、f72单事件且 `verified:false`、13有效粗部位槽；131958空场97帧不观测/0事件 |
| C02-05 | PASS | headless Microsoft Edge 实际壳页、两个iframe入口及f72告警画面交互通过 |
| C02-06 | PASS | 两EXE启动检查；CArchive内HTML匹配源码；ZIP完整性、双EXE、spec、README匹配通过：`PACKAGED_VERIFICATION_FINAL.json` |
| C02-07 | NOT_RUN / BLOCKED | 本工单独立复审NOT_RUN；人体/家具/关节GT与跨场景泛化BLOCKED；设备/物理NOT_RUN |

## 未闭合

- f72事件是单次未验证prototype，confirmed保持关闭；空场参考存在自参考限制。
- r04 TOP_REGION显示平滑指标回退、END_B支持减少及目标点减少均保留；没有人工标签可判断删点是否伤及人体。
- 13槽是点支撑粗区域，不是解剖骨架。单元测试套件和native WebView2窗口本轮未运行；Edge headless与冻结无GUI启动检查不能替代设备/物理验证。
- 未采集、未部署、未训练/切换模型、未修改原录制/GT/生产算法、未提交或推送。

状态：SUBMITTED，不自报 ACCEPTED。
