# HR-02 本地会话优先 / R1 回传

2026-10-05，Codex 唯一 writer，状态 SUBMITTED。唯一验收表 [HR02_OFFLINE_ACCEPTANCE.md v1](../HR02_OFFLINE_ACCEPTANCE.md)。已读 ponytail：C:/Users/30680/.codex/skills/ponytail/SKILL.md。本单为 PC HR-02 修复，不改 HF/GL 当前工单或物理结论；无独立外部复审，不报 ACCEPTED。

根因、操作矩阵见 [03_diag.md](../evidence/2026-10-05_hr02_offline_r1/03_diag.md)。基线 master/3fc1338fc306444959433a41bdeaeefd705f58ec，dirty tree 与源 SHA/原数据在 00/01/02；本轮新增差异独立保留在 12_this_turn.diff，未恢复用户既有改动。

实际改动：human_replay_lib.py 新增不访问板端的 scope=local 分支；panel.js 先本地再板端、GET 6 秒超时与刷新版本门；console_gui.py 仓内 exe 寻找仓根捕获目录，独立移动版按 exe 目录读取；sessions_test.py、panel.test.js 和 console_test.py 覆盖相关入口。config.py、replay.js 本轮未变；未改算法、driver、webui、板端、原数据或旧证据。

| ID | 层级 | 结果与证据 |
|---|---|---|
| O1 | synthetic + 实际本地 HTTP/browser | PASS；sessions_test 禁止 board 调用；panel.test 延迟远端仍显示本地；新版实际列出 9 个会话。07_packaged_http.json、08_browser_state.txt/PNG |
| O2 | synthetic + 实际本地 browser | PASS；超时、board_error 下仍点击本地 loader；实际新版浏览器板端离线/录制禁用，cap_20261004_202456 就绪688ms，播放HUD帧33/91 seq1766006，暂停帧31/91 seq1766004，已载入。08 |
| O3 | synthetic | PASS；恢复同 SID 合并无重复，选中保持；连续刷新旧响应不覆盖；panel.test.js、sessions_test.py |
| O4 | synthetic + 实际 exe | PASS；源码路径/仓内冻结路径/独立移动路径、端口占用测试；exe 从 TEMP 启动仍扫描仓根9会话，meta/bin HTTP字节与源相同、panel.js与打包字节相同；桌面快捷方式目标已更新且复读一致。07/09 |
| O5 | offline | PASS；02/10 所有原 meta/bin 的 SHA256、长度、mtime 完全相同；01/11 中 config.py/replay.js 保持。12 区分本轮与用户旧差异 |
| O6 | local | PASS；下列相关检查全部完成，退出0；tests0/tests1/05 |
| D1 | device | NOT_RUN；没有断开/恢复真实设备，也不以软件mock代替设备结果 |

执行命令：

- node --check pc_apps/human_replay/panel.js；node pc_apps/human_replay/panel.test.js；node pc_apps/human_replay/human_replay_lib.test.js（45既有检查），均exit0。
- python -B -W error -m unittest discover -s pc_apps/human_replay -p sessions_test.py -v（1）；-s pc_apps/console -p console_test.py -v（4）；-s pc_apps/human_replay -p fetch_lib_test.py -v（6），均exit0。
- python -B -W error -m unittest discover -s pc_apps/human_replay -p leveling_test.py -v（4）；同目录 leveling_auto_test.py（5），均exit0。只运行既有回归，不改变算法结论。
- 内存将panel.test的源读取替换成本轮panel.js.before，exit1，明确检出原入口仍是 /api/sessions 而非 /api/sessions?scope=local；原文件未回写。见13_regression_before.txt。

打包：python -m PyInstaller --noconfirm --distpath dist/hr02_offline --workpath build/hr02_offline Console.spec（pc_apps/console 下）。初次编译会话未保留最终exit码，不伪造；完成的exe实际启动及HTTP字节检查通过。exe SHA256 472e15109f4bf1be0a53133645ddee5e732598ca62a973f627a2cbb8241743d7。保留旧exe，桌面总控制台.lnk指向 dist/hr02_offline/Console.exe，原lnk备份在09。

浏览器初次访问时旧8901服务已退出，连接拒绝；Chrome连接工具不可用。启动本轮exe后，IAB实际操作成功，不将前次工具错误当源码失败。临时mock服务已停止；新版exe服务保留供用户查看。

最终源SHA见11。本轮结果为作者自验/修复提交，没有独立审查、设备/真实物理验收、采集或部署。
