# HFUS-NEXT-DEV-01 回传记录

## 2026-10-15 本轮信息

- 工单 / 轮次 / 执行者：HFUS-NEXT-DEV-01 / r1 / 当前Codex单writer；仅本机离线。
- 状态：SUBMITTED，非ACCEPTED；没有默认晋级。设备/物理/部署NOT_RUN。
- 唯一验收：[ACCEPTANCE_V2.md](../evidence/2026-10-14_hfus_next_development_plan_r1/ACCEPTANCE_V2.md)，SHA `573ba864c9cc88acd7257c75cb9eae6e58df7657168d4686bbe453d272bc8d9c`。
- 起始branch/HEAD：master / `c21c443b0befe559e08283edb0efc2af02dcc6b8`；完整dirty状态、tracked/untracked源SHA和并行用户差异见[FINAL_SHA](../evidence/2026-10-15_hfus_next_dev_r1/FINAL_SHA.json)、BASELINE_BEFORE.json与GIT_STATUS_BEFORE/AFTER.txt。原R1核心/配置保持，控制台并行变更不归本轮写入。
- 实际读取技能：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`；`C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md`。
- 独立只读审查：OpenCode `opencode-go/deepseek-v4.1-flash`、plan agent，session `ses_ec47eafe3ffe5WigA5EjxxrVC4`；禁止edit/bash，snapshot=false。R1原文、返工及最终R2另存，不以作者自验冒称独审。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 入口/消费者/转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
|N01/N02|加载前缺严格schema及版本闭环|原输入→运行→冻结输出→server/source查询|next_dev.py、next_contract.py|旧输出/首次失败不覆盖；当前与执行源码分列|
|N04/N05|真实桥接/断边与背景变更不能混因子|A/B/B_tau及C/D独立状态|next_dev.py条件图/逐点账本|固定ROI/eps/补偿，不删地下点、不伪造人体GT|
|N06/N07|轴历史和低姿态资格需限时；仅站立过窄；hold时刻不能代替下降时刻|选择→轴→事件→弱关联|next_temporal.py、event_next_r2.py|初版0事件保留；新r2另版，原参数/点成员不改|
|N09|原renderer假定旧字段；成员差异曾显示占位0|冻结frame→原app/同帧对照/原字节/缺源|server.py、app.js、index.html|R1默认/历史可用；UNKNOWN/NA明确|
|N10|计时口径与执行SHA需独立可查|全量验证/新进程性能/独审|verify_next_dev.py、profile_next_dev.py|首次追踪验证停止/原日志保留，不当性能结果|

完整操作矩阵、调用者及顺序见[00_diag](../evidence/2026-10-15_hfus_next_dev_r1/00_diag.md)；[返工记录](../evidence/2026-10-15_hfus_next_dev_r1/REWORK_LOG.md)、[契约版本记录](../evidence/2026-10-15_hfus_next_dev_r1/CONTRACT_VERSION_R2.md)保留失败。验收表不改。

## 实际变更

| 文件（均在sidequests/human_fusion_lab_next/pointset/r01） | 用途 | 与原差异区分 / SHA |
|---|---|---|
|next_dev.py、next_contract.py|全量因子、条件图、源契约和冻结读取|本轮新增；CURRENT_DELIVERY→DELIVERY_BINDING_R5记录每文件SHA|
|next_temporal.py、event_next_r2.py|轴/近期非低下降/弱观测单因素|本轮新增；初版与r2输出分开|
|verify_next_dev.py、profile_next_dev.py、test_next_dev.py、replay_frozen_next.py|原字节/因果/守恒、分层性能、回归、归档复现|本轮新增；FINAL_SHA及执行源码归档|
|server.py、app.js、index.html|复用原页/原server展示与查询|仅本轮必要兼容；改前SHA/用户差异快照保留|

完整源版本与复现见[REPRODUCTION](../evidence/2026-10-15_hfus_next_dev_r1/REPRODUCTION.md)。无数据写入、Git写、训练、采集、部署、驱动或网络改动；没有另建demo/覆盖EXE。

## 逐条验收

逐项状态及证据以本轮[RESULTS.md](../evidence/2026-10-15_hfus_next_dev_r1/RESULTS.md)最新追加表为准；不是工单ACCEPTED。

|ID|范围/证据|本机自验状态|
|---|---|---|
|N01|18原文件、1934动作/272新空场、CAL重算；DATA_PREFLIGHT_R2/NEW_CAL_REPRODUCTION|PASS；旧原空场/CAL BLOCKED|
|N02|manifest/代码/背景/源/绑定、坏schema拒绝；冻结与复现入口|PASS|
|N03|A/B/B_tau全1934+90；逐点账本；旧32缓存单列|PASS|
|N04|2024实测补偿、合成退化/越界/残差恶化回退|PASS；反射证据BLOCKED|
|N05|3候选一次960选定、974内部比较、对称/成员守恒|PASS执行契约；3候选非退化FAIL，NO_GEOMETRIC_WINNER|
|N06|16192独立状态端点、2024未来拒绝、900短前缀|PASS；不冒称所有前缀O(n²)重启|
|N07|轴/槽、事件源证据及负例分层|PASS已覆盖；缺类/快降实测NOT_RUN，非真实跌倒TP|
|N08|U/K/X/未知/范围外/NA|BLOCKED语义与关节GT；K=0|
|N09|原页同帧/源字节/缺源/UNKNOWN与源码console入口|BLOCKED总体EXE一致性；源码/实际browser PASS；EXE启动real_fall FAIL，新功能NOT_RUN|
|N10|CPU/内存/会话/姿态/距离/反例与只读复审|性能已实测；最终独审状态见RESULTS最新追加表|
|N11|独立泛化/板端/物理/部署/默认晋级|NOT_RUN，本阶段不开展|

真实命令/进程退出码见[COMMAND_EXECUTION_RECORD](../evidence/2026-10-15_hfus_next_dev_r1/COMMAND_EXECUTION_RECORD.md)：Python受影响37检查退出0（-B -W error）；console JS15/Python7退出0；原app解析及实际browser通过；EXE启动退出1；全量验证/各组性能退出0。测试数量不是完成判据。

## 未闭合与限制

- 新空场90留出残余110492→11240（-89.83%），但动作前景点+69.27%；不能据此声称人体召回变好。C/D槽跳变退化，全部条件图不晋级。
- 事件r2得到2个受控慢躺下降几何候选；初始躺地/空场0，不计真实跌倒TP。轴/弱关联当前没有收益；最差082623/f195槽跳约1m保留。
- N08完整语义/关节GT缺失；N01旧131958原字节/CAL缺失；N04截图/可信平面缺失；N07缺覆盖负例/真实跌倒；N09现有EXE整体启动real_fall失败、新NEXT功能未验证。完整解除条件分别为补合法独立证据/另单授权范围，不伪造缓存原源。
- N11板端NumPy1.17实际运行、板端性能、部署、物理、独立泛化均NOT_RUN；长期会话不足不报误报/小时。

## 交给独立复审

- [FINAL_REPORT](../evidence/2026-10-15_hfus_next_dev_r1/FINAL_REPORT.md)、[RESULTS](../evidence/2026-10-15_hfus_next_dev_r1/RESULTS.md)、[当前绑定](../evidence/2026-10-15_hfus_next_dev_r1/CURRENT_DELIVERY.json)、[浏览器证据](../evidence/2026-10-15_hfus_next_dev_r1/BROWSER_EVIDENCE.md)。
- 当前原页面：http://127.0.0.1:60152/?dataset=actions&sid=cap_20261013_082623&fi=195&variant=next_A，PID972/端口60152/代码版本见SERVER_START_972.json，属于本工单；用户其他服务未停。
- R1/R2独审与前后源SHA均留本轮证据；下一步仅验收或处理明确范围内缺陷，不自动接管下一单、不默认晋级。


## 最终收口追加

N10作者自验PASS，独立AI R2全表/R3定向复审与逐项响应已保留于本轮证据；未独立重跑原字节/浏览器/性能。N06增加事件r2全2024帧、180短前缀、2024未来拒绝，均同源新状态；N07两慢降是同数据后验几何结果。N02当前源run及归档--out第二次全量重算NOT_RUN，SOURCE_ROLE_INDEX分列执行与审查快照；N03/N10派生脚本已实际退出0。N08/N09仍BLOCKED，N11 NOT_RUN。所有ID以RESULTS最后追加表为准，最终状态SUBMITTED。

