
## 2026-10-15 HFUS-LEARN-DEV-03 / E0 收尾提交

### 本轮信息

- 工单：HFUS-LEARN-DEV-03；Codex单writer；状态 **SUBMITTED，学习目标BLOCKED**，非ACCEPTED。
- 唯一验收：docs/human_capture/evidence/2026-10-15_hfus_learn_stage_plan_r1/ACCEPTANCE_V3.md，v3，SHA687c3d833f6d92adb5b5ac27911c663f324bc6a8920c2ac8024d7a32139ec7af。E0授权来源：用户将附件实际派发为请求，后续明确“收尾”；PLAN_PASS仅先决条件，提示词样例本身不提供授权。USER_DISPATCH.txt/AUTHORITIES.json保留派发文本，E1=NOT_GRANTED。
- 起点master/c21c443b0befe559e08283edb0efc2af02dcc6b8，dirty，2255源/config/model首尾SHA，9项变化0缺失；6个其他文件并行修改保留，不归本工单。无commit/push/reset/clean。
- 实际读取技能：C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。浏览器读取computer-use技能，使用CUA浏览器。
- 原始证据：docs/human_capture/evidence/2026-10-15_hfus_learn_dev_r1（失败/半截/profiles）与r2（当前完整数值/交付）。

### 集中诊断与根因覆盖

|缺陷|根因/消费者|修复及保留|
|---|---|---|
|D1|Windows数值INDEX反斜杠与路由POSIX键不符|写入统一POSIX，HTTPfixture+全量新目录；旧失败保留|
|D2|人工修订质量/第二审核/覆盖门不足|按源行revision/SHA/理由、独立审核/覆盖/每sid支持门；缺审UNKNOWN，未造人工标签|
|D3|profile数值前无源SHA边界|实源漂移拒绝，12旧探针只按AST兼容继承，不增第13次；整个state_dict含buffer不变|
|D4/D5|完整EXE未闭合与计数易混|新候选另名，scoped与full启动分开；所有计数从实际输出，0学习更新|
|UI2|深链接载入f195但任务仍f0|最新成功请求匹配sid/fi；失败/NOT_RUN清空；回归+真实浏览器；旧CURRENT/JS留档|

### 实际变更

新sidequests/human_fusion_lab_next/learn/r01模块：输入/标签/投影契约、无更新资源图、独立几何重放、时序接口、审计、同应用扩展路由与标注页面。pc_apps/console仅本工单可选模块加载/learn_run/--check-learn、学习卡和对应断言；并行归档/相机/其他工作保留。新候选EXE不替换旧EXE/快捷方式；候选壳布局早于并行归档版本，不能等同当前整套源码。旧pointset/r01 server/app/index字节SHA不变，R1根默认保持。

精确源码SHA：本轮DELIVERY_SOURCE_SHA_FINAL、FINAL_CONSOLE_SHA、RUN_MANIFEST.source_sha256；新页UI2由CURRENT/SOURCE_ENTRY_SERVER_UI2绑定；RUN_MANIFEST.ui_source_sha256仅prepare快照，数值首算/复算不因无关UI而重签。旧DELIVERY_SOURCE_SHA已过期测试文件条目保留，最终清单与勘误REVIEW_R3_RESOLUTION明确替代。审后不改生产代码。8096字段本身是常量，实际2024×4流计数及运行逐帧比较另外支持，未用常量证明执行。

### 逐条验收

|ID|范围|结果|证据/命令|
|---|---|---|---|
|L01|offline/synthetic software；设备NOT_RUN|PASS|E0 only; USER_DISPATCH/AUTHORITIES; single writer; no training/download/HR09/device/commit. ponytail loaded.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L02|offline/synthetic software；设备NOT_RUN|PASS|DATA_PREFLIGHT and FINAL_PRESERVATION:18 original sources,28B/time/count,background/R-T,numeric dependencies rehashed; old131958 original/CAL BLOCKED,32 cache schemas checked separately.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L03|offline/synthetic software；设备NOT_RUN|BLOCKED|Tool/474 queue PASS;282 primary+66 independent second human reviews remain0;K=0. Geometry192 proposals never GT.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L04|offline/synthetic software；设备NOT_RUN|PASS|Software contract only:U/K/X,UNKNOWN not negative,revision reason/SHA,independent reviewer and quality/coverage gates; actual semantic/instance/joint/event labels absent and BLOCKED.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L05|offline/synthetic software；设备NOT_RUN|PASS|91FIT empirical angular template; radial/axial128x512+256x1024,K2+all-members CSR; full2024 conserved. Not physical calibration.128 overflow maximum18023 despite median0;256 overflow maximum0.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L06|offline/synthetic software；设备NOT_RUN|BLOCKED|No E1/trusted labels. L3D/L2D/LFUSION graphs/interfaces/probes only;0 optimizer steps; no main weight.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L07|offline/synthetic software；设备NOT_RUN|BLOCKED|4-query exclusive assignment/empty loss/masks synthetic interfaces PASS; real instance supervision/training absent; query index not identity.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L08|offline/synthetic software；设备NOT_RUN|BLOCKED|72/24/96 split,4sid folds,36 jobs,thresholds/seeds frozen;12 inherited no-update profiles with all state_dict/buffer SHA invariant; AST compatibility recorded,not rerun.256x1024,E11/33 resource bound only. Current E0 output35.12GiB<80; future complete learning matrix storage not qualified. No training/OOF/model selection.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L09|offline/synthetic software；设备NOT_RUN|BLOCKED|Old measured13 slots separate from joint adapter. Adapter/real joint scoring NOT_RUN; GT/license/version gate absent;no MPJPE/PCK.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L10|offline/synthetic software；设备NOT_RUN|BLOCKED|4 geometry streams independently replayed2024,synthetic query/reset association cases PASS; actual learned query identity/occlusion evaluation NOT_RUN.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L11|offline/synthetic software；设备NOT_RUN|BLOCKED|CausalGRU<=8frames/1s synthetic interface/prefix/reset tested; full geometry event ledger uses old frozen2s detector,not learned8frame result; no real fall TP/generalization claim.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L12|offline/synthetic software；设备NOT_RUN|PASS|E0 state accounting:4 geometry streams x2024 fresh twice.36 learning jobs BLOCKED,12 learning/3 inference-pressure streams NOT_RUN. Full geometry row/member/event/source ledger saved; learned ledger unavailable.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L13|offline/synthetic software；设备NOT_RUN|BLOCKED|OOF96 versus final96+empty90 score tables below:K0,X=all U,NA semantics,zero selected model. Geometry all endpoints/worst20 and common1757 transitions available; no semantic winner or974 selection.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L14|offline/synthetic software；设备NOT_RUN|PASS|Software scope:original console module imports versioned route; old root/app/index hashes identical,R1 default. UI/manifest/index SHA gates,raw28B,multilayer/label/UNKNOWN/missing source/failed/NOT_RUN covered by HTTP+browser+tests; no human labels fabricated. Deep-link queue sync fixed UI2.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L15|offline/synthetic software；设备NOT_RUN|BLOCKED|Geometry PC stage/e2e CPU P50/P95+peak/by-session/distance/worst20 PASS; activity source metadata only. Human visibility GT/learned seed spread unavailable. Shared preprocessing,both-grid archiveIO included; separate warm-cache read benchmark is not inference/board FPS.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L16|offline/synthetic software；设备NOT_RUN|BLOCKED|Software boundary/synthetic regression PASS and actual geometry fresh recompute PASS82984 arrays/8096 JSON rows,zero mismatches. Actual learned main-weight reproduction unavailable; cannot PASS entire requirement.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L17|offline/synthetic software；设备NOT_RUN|FAIL|Browser E0/JS17 console cases/Python7 scoped checks PASS. Separate named candidate built exit0;source and candidate --check-learn UI2 exit0. Both full --check-startup exit1:real fall replay did not start. Interactive desktop EXE NOT_RUN; original EXE untouched.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|
|L18|offline/synthetic software；设备NOT_RUN|PASS|Software submission record only:manifest/source/output bindings,OpenCode R3 read-only full-table review exit0 READONLY_NO_NEW_DEFECT;formal return/entry appended. Not stage ACCEPTED; E1/GT/fullconsole remain BLOCKED/FAIL.（实际命令见本轮COMMAND_RESULTS/TEST_RESULTS/UI2_COMMAND_RESULTS/FINAL_CONSOLE_SHA）|

### 实测与未闭合

18原始源重核，1934动作+90空场，4几何流primary/reproduction各完整新算2024；82984数组、8096JSON逐帧零差异，非复制旧winner。G0兼容旧B2024/2024，G1各自分母槽跳P95 .16359m高于G0 .13613m，无轴112对76，不晋级。共同1757转移/全部端点/最差20见摘要。K0、282核心/66第二人工未做；36学习作业BLOCKED、15学习/压力流NOT_RUN，关节GT/主权重/语义OOF与最终比较NA。

新软件Python7、最初consoleJS17/Python7、旧契约13与UI2节点回归通过；并行布局后的当前consoleJS最终21/21 exit0，快照分开。源码/候选--check-learn UI2 exit0；完整--check-startup均exit1 real fall replay did not start，交互桌面EXE NOT_RUN，不能宣称完整软件PASS。

数据/采集/设备/驱动/部署/物理/泛化NOT_RUN；旧131958原源/CAL BLOCKED。没有训练/下载/HR09。当前证据约35.12GiB小于80，未来完整学习矩阵存储未合格。CPU口径含共享预处理与存档IO；暖缓存读取另表，不作为板端模型FPS。

### 交给Codex独立复审

R1 READONLY_REVISE→R2 READONLY_NO_NEW_DEFECT→最终R3 READONLY_NO_NEW_DEFECT；请求opencode-go/deepseek-v4.1-flash plan，只读edit/bash/task deny，snapshot=false。R3 session ses_ec14efee9ffetp6snOLcBAEK3L，exit0；仅源码/记录审查，非独立数值实验或人工审核。原意见、集中返工、命令/退出码均保留。

当前交付见r2/FINAL_REPORT.md、RESULTS.md、DELIVERY_BINDING.json。下一步仅等待用户/验收方审查；本工单不能自动推进E1、默认晋级或下一工单。
