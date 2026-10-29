# HFUS-TCMS-02-REALDEV-01 回传

## 2026-10-17 r1 / Codex / 实施中

- 当前唯一验收：docs/human_fall/evidence/2026-10-17_hfus_tcms_02_realdev_r1/ACCEPTANCE_V1.md，v1。
- 策略：算法/表示变化/效果 RESEARCH；严格源/规模/回放 ENGINEERING。不是 CONSOLIDATION。
- 实际已读 ponytail：C:/Users/30680/.codex/skills/ponytail/SKILL.md；scientific-toolkit-skill：C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。
- 唯一writer Codex；两助手只读审查。起始branch/HEAD/status及13484个非忽略tracked/untracked条目见 BASELINE_GIT.json / BASELINE_FILES.jsonl（6,110,522,253字节；data/junction排除，链接不跟随）。
- 状态 SUBMITTED（实施中），不是ACCEPTED；设备/物理 NOT_RUN，真实身份/地面/C/D效果 BLOCKED。
- 集中根因：旧全量建图/双重地图账/整段JSON/成品图回填不适用真实规模；新流式稀疏表示明确RESEARCH语义变化，原始行完整记账。
- probe_r1：RSS ctypes HANDLE声明错误，exit1，失败及首帧输出保留；新目录重跑，不覆盖。


## 2026-10-17 r1 / Codex / 首轮交付最终记录

### 本轮信息

- 工单HFUS-TCMS-02-REALDEV-01；状态SUBMITTED，未宣布ACCEPTED。本机源码writer仅Codex，助手和OpenCode均只读。
- 当前唯一验收v1：../evidence/2026-10-17_hfus_tcms_02_realdev_r1/ACCEPTANCE_V1.md；SHA256：a1eda3bdeb2739450fb0310e276870ee53d446fd0dce84fe6133dae52f421b0d。
- 策略保持RESEARCH（表示/候选/效果）+ENGINEERING（读取/规模/回放）。ponytail实际已读路径C:/Users/30680/.codex/skills/ponytail/SKILL.md；scientific-toolkit-skill实际路径C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。
- 起始master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a；原工作树故意dirty，13484个非忽略文件/6,110,522,253字节基线，包含未跟踪源码。无git写，范围外内容差异0。
- 用户补充场景/雷达与以前一致且全静止，并明确“借助视觉帮我判断就行”。USER_UPDATE_V1逐字记录；AI_VISUAL_REVIEW human_confirmation=false，未伪造人工确认/GT。

### 集中诊断与实际变更

| ID | 根因/受影响入口 | 实际修复或诊断 | 保留行为 |
|---|---|---|---|
| RD01/02/10 | 原逐点对象与map×current账不适合真实规模；不透明尾及来源容易遗漏 | contracts严格28B/用途/SHA；pipeline有限体素及全来源CSR；run流式全行账和逐帧索引 | XYZ-only，全部原始分母、无效行与UNKNOWN保持；体素表示属RESEARCH |
| RD03/04 | 成品图回填早帧/无布局事实会伪造M0资格；旧地面不自动适配新段 | 实际布局证据；建图/核验/fi271生效；历史TLS仅次级标志，新段残差原门FAIL | 不回填旧输出，不切未资格地面，不输出强free/强occlusion |
| RD05/06 | 未核朝向硬门、接触生长/多候选关联及低姿丢响应 | main事前登记移除RAW轴0.8m门；实际视觉委托版证据绑定；0成员TTL/LOST与mixed状态保留 | f439起LOST、尾段零候选FAIL；AI不是HUMAN/GT |
| RD07/08 | 无标签和关闭因子不能伪造效果分数 | 两方案/旧B2B3全780；288帧两因子消融；DIAGNOSTIC四键，LABELLED/D/未知用途拒绝 | 正式评分与三关闭因子BLOCKED；未运行原无界全780 |
| RD09/10 | 显示采样/缓存可能阻断实际源行或隐藏原字节漂移 | server逐帧28B SHA、全行/全部支持分页；app图层/跳秒/播放/查询；真实浏览器与冻结审查 | localhost只读；预测无当前成员，source尾16B不解释 |

| 文件/目录 | 用途与用户原差异区分 | 提交SHA |
|---|---|---|
| sidequests/hfus_tcms_02/realdev/r01/contracts.py、pipeline.py、run.py | 全部本轮新增隔离工程/研究实现 | CODE_FREEZE_R1.json逐文件 |
| 同目录continue_confirmed.py、server.py、app.js、index.html | 版本绑定诊断续接与本机源行回放 | CODE_FREEZE_R1.json逐文件 |
| 同目录tests/、README.md | 25旧断言IO适配+17新契约、浏览器/HTTP验证与复现 | CODE_FREEZE_R1.json逐文件 |
| 本轮evidence根、returns文件，WORKFLOW前插/REVIEW_LOG追加 | 新证据与当前入口，原历史字节保留；旧源码未写 | DELIVERY_SHA_FINAL.json及DOCUMENT_APPEND_CHECK_R1.json |

### 逐条验收（自验与真实效果分列）

| ID | software | synthetic | real-development | 核心证据 | independent/device/physical |
|---|---|---|---|---|
| RD01 | PASS | PASS | PASS：单源/用途/源SHA | BASELINE_* / SOURCE_PREFLIGHT / PRESERVATION_SUMMARY_R1 | BLOCKED / NOT_RUN / NOT_RUN |
| RD02 | PASS | PASS | PASS：全量工程记账 | INDEPENDENT_FULL_LEDGER_CHECK / PERFORMANCE / INDEX | BLOCKED / NOT_RUN / NOT_RUN |
| RD03 | PASS | PASS | PASS：有限M0因果资格；BLOCKED：地面独立空间/物理资格；旧地面新段残差FAIL | QUALIFICATION / ground_audit_r1/AUDIT | BLOCKED / NOT_RUN / NOT_RUN |
| RD04 | PASS | PASS | BLOCKED：C/可见性物理证据；两账已跑 | map/ / compact ledgers / capabilities=false | BLOCKED / NOT_RUN / NOT_RUN |
| RD05 | PASS | PASS | FAIL：尾段零候选，未实现可靠低姿保持 | f750/760/770/779；固定失败案例 | BLOCKED / NOT_RUN / NOT_RUN |
| RD06 | PASS | PASS | FAIL：AI续接f439 LOST；BLOCKED：人工身份/GT | AI_CONTINUATION_DIAGNOSTIC / AI_VISUAL_REVIEW_F430_V2 | BLOCKED / NOT_RUN / NOT_RUN |
| RD07 | PASS | PASS | BLOCKED：地面/实际人工身份因子及正式效果 | 全780两方案/B2B3；288帧补充消融；ORIGINAL_BOUNDED_REFERENCE | BLOCKED / NOT_RUN / NOT_RUN |
| RD08 | PASS | PASS | BLOCKED：无标签，所有效果指标null | EVALUATION / protocol gate tests / actual diagnostic outputs | BLOCKED / NOT_RUN / NOT_RUN |
| RD09 | PASS | NOT_RUN | PASS：真实回放/源行查询/失败展示 | BROWSER_FINAL_SUMMARY / replay_contract_final_STATUS | BLOCKED / NOT_RUN / NOT_RUN |
| RD10 | PASS | PASS | PASS：工程记录与AI只读审查；效果边界未解除 | CODE_FREEZE_R1 / OPENCODE_R1 / PRESERVATION_FINAL_R2 | BLOCKED / NOT_RUN / NOT_RUN |


上表证据均在../evidence/2026-10-17_hfus_tcms_02_realdev_r1/；完整真实报告[REPORT](../evidence/2026-10-17_hfus_tcms_02_realdev_r1/REPORT.md)。实际命令argv、退出码和失败见COMMANDS_FINAL_INDEX.json及各*_STATUS.json，输入与执行源码/依赖见full_r5/ENVIRONMENT.json、EXECUTED_SOURCE与OUTPUT_INDEX。

实际执行：python -B -W error -m unittest discover -s sidequests/hfus_tcms_02/realdev/r01/tests -p test_*.py，42项exit0；node --check app.js与真实HTTP replay.test.js exit0。另一个审计脚本核对真实原始780帧×2方案共1560份行账PASS（仍是同一开发数据，非独立效果实验）；288帧补充消融exit0；原有界4帧合成参考exit0。全段full_r5 exit0/371.131s，RSS峰值1,237,409,792B、封索引前输出681,107,707B，预算内。AI条件续接r2 exit0/129.988s，全部780帧只读原源；退出0代表工程完成，续接效果仍FAIL。

### 未闭合与限制

实际视觉判f430主簇为行走者，2628当前成员含15生长点，mixed/ambiguous保留；仅f430/f432实测，f431和f433–438预测0成员，f439（45.508558s）LOST。f770/f779零候选，尾部躺下目标未满足。旧地面TLS新段P95约.0583m/RMS约.0974m超过.05/.03原门；物理高度/额外空间独立验证缺失。精确可见/躺下时点与人体逐点GT未知。完整会话development_seen/dev-tainted；C家具负控、独立D、实际人工身份及正式LABELLED评分BLOCKED，设备/物理NOT_RUN，无泛化结论。

原失败probe_r1、tests_r1/r4、numeric外层GBK读取错误、AI_r1的JPEG/PNG签名拒绝均保留；旧full_r1–r4/协议/截图/请求无覆盖或删除。消融有效窗口以ABLATION_SCOPE_V2.windows_s为准，新[38,43)与原[43,47)并为[38,47)，不是全段消融。

### 只读复审与当前交付

OpenCode实际CLI v2.0.29，opencode-go/deepseek-v4.1-flash，standalone/plan，仅read/glob/grep/list，exit0/305.290s，READONLY_NO_NEW_DEFECT。原始请求/JSONL/stderr/状态/提取意见完整保留。未独立执行算法、读points.bin或重算SHA；不是人工确认或效果验收。审后源码及提交证据SHA全部复核一致；最终文档是审后追加，不伪称已由该审查读到。

回放：[两方案](http://127.0.0.1:60427/?fi=430)；[AI审核后续接](http://127.0.0.1:60894/?fi=430)；[LOST](http://127.0.0.1:60894/?fi=439)；[尾帧失败](http://127.0.0.1:60427/?fi=779)。FINAL_HEALTH_R1记录最终可用性。保持SUBMITTED，不自动启动下一里程碑；后续优先多候选关联歧义、尾段缺候选与地面残差原因。
