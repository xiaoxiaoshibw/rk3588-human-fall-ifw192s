## 2026-10-15 / 计划包交付 R1（开发尚未执行）

- 状态：SUBMITTED（计划范围），非实验完成/非ACCEPTED。用户要求完整开发计划、AI阶段提示词、开发后OpenCode审查及下一阶段规划。
- 当前索引：`docs/human_capture/evidence/2026-10-15_hfus_indoor_ai_plan_r1/CURRENT.md`。
- 当前完整计划/唯一拟实施验收：同目录 `DEVELOPMENT_PLAN_V2.md`、`ACCEPTANCE_V2.md`（A01–A16）；`AI_STAGE_PROMPTS_V2.md`可整段派发或逐阶段派发。`OPERATION_MATRIX_V2.md`补操作组合，不另造判据。
- 读取AGENTS、HC README、HF WORKFLOW、E0最新return/r2 RESULTS/FINAL_REPORT、当前learn模型/runner/server及旧RF/PointNet权重与训练/推理契约。当前环境包元数据已查；实际训练环境CPU导入门留给实施S0，不宣称已完成训练验证。
- 起点master/`c9c4ee421cb0c8a3e4590b8f5730828b093c759a`，dirty；相关tracked+untracked文件33项SHA在CURRENT_BASELINE_R1.json；PRESERVATION_R1.json观察范围内零变化、HEAD不变。数据ZIP/member SHA复用本工单实际检测清单，不重复遍历大数据。用户并行工作保留。
- 技能实际读取路径（同会话）：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`、`C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md`。

### 设计与判据

S0真实状态核验→S1点云GT首屏→S2基线/可信监督与分组→S3 CPU新RF/PointNet有效训练→S4全量指标/错误Demo→S5 OpenCode只读审查/集中返工复验→S6依据审后真实证据制定下一计划/验收/提示词。

明确旋转UNKNOWN/GT不完备/独立采集组不明时的阻塞及可继续路径；旧RF缺有效强度/IFW坐标契约BLOCKED；旧shadow单列域迁移诊断；新RF/PointNet同候选同监督同划分、三seed、主seed43。不得从框造逐点GT或把UNKNOWN作负类。无空场则空场FP不可评。累计CPU训练≤2h、4线程、新增输出≤512MiB、不整包解压/不新增下载，不写生产或设备。

### 计划审查与修正

- 原helper硬编码旧CLI路径，probe启动失败WinError2；未改旧helper，失败输出保留。
- 当前CLI实查为`C:/Users/30680/AppData/Roaming/npm/node_modules/@opencode/cli/bin/opencode.exe`。新调用使用`run --standalone --agent plan`、snapshot=false、进程内只读权限；不改全局配置/DB/模型。实际调用代码review_runner.py/v2保留。
- R1：指定opencode-go/deepseek-v4.1-flash，exit0，session `ses_ec138e29fffeeTxpE01m9cKVvT`；session导出核对实际模型，工具仅read/glob/grep，完整brief及ponytail读取可观测。结论PLAN_REVISE，11项文档缺陷。原意见OPENCODE_PLAN_REVIEW_R1.md/jsonl与OPENCODE_PLAN_VERIFICATION_R1.json保留。
- 集中修正见REVIEW_RESOLUTION_R1.md，V2保留V1历史。R2启动前冻结PLAN_PACKAGE_SHA_R2.json。开发后的审查是未来S5，本次计划审查不能冒称开发审查。

### 实施验收与未运行

A01–A16全部为拟实施条目，本轮仍NOT_RUN；数据既有预检及计划审查不能使开发验收PASS。未新增训练、预测/指标、Demo或实际下一阶段实验结论。设备/物理/部署NOT_RUN；HFUS E1及本地逐点GT门保留。下一阶段目前只提供条件模板NEXT_STAGE_RULES_V2.md，真实下一计划必须在实施与审后根据证据生成，不自动执行下一阶段。

### R2计划审查收口

OpenCode复审R2 exit0，session `ses_ec1329bd4ffezwBkVgYRNCO2fn`，结论PLAN_PASS、无P0/P1；实际模型与只读工具、brief/技能读取、V2整包SHA稳定性见OPENCODE_PLAN_VERIFICATION_R2.json。保留四项P3：按来源/最终冻结split分母分表、track逐成员SHA、辅助指标/下阶段触发继承旋转硬门、IoU平局规则；已在IMPLEMENTATION_ADDENDUM_V1.md明确，实施必须一起读取。未改V2审查输入，不称为开发通过或算法有效。当前计划包提交状态SUBMITTED。


## 2026-10-15 HFUS-INDOOR-AI-TEST-01 开发R1 / SUBMITTED待开发后只读审查

### 本轮信息

Codex唯一实验源码writer；分支master，HEAD c9c4ee421cb0c8a3e4590b8f5730828b093c759a，dirty及并行控制台/回放差异保留。仅独立sidequest、新证据与追加本return。无设备/物理/部署/采集/驱动网络/Git写，无HR09/HFUS E1。状态SUBMITTED，算法目标BLOCKED，非ACCEPTED。

技能实际读取路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md；浏览器按C:/Users/30680/.codex/plugins/cache/openai-bundled/computer-use/26.1007.71326/skills/computer-use/SKILL.md及其guidance/confirmations，使用其推荐Browser Use能力。

### 集中诊断与实际变更

见本轮00_DIAG.md操作矩阵。adapter/prepare保留ZIP成员源行、原始标签tokens与UNKNOWN；evaluate安全复用原cluster+HDBSCAN，不import旧train.py；独立server/三栏页面、SHA/同ID漂移/乱序/非法输入/模型BLOCKED清屏；publish新run绑定父payload，不复制大型账本；verify独立重算；report依据真实分母生成八问与A01–A16记录。旧数据/权重/EXE/默认R1/learn源码均未由本工单修改。

r2 HDBSCAN FutureWarning失败与r3明文账本预算预停保留；r4全量完成；r5审前页面发现case选择器残留，UI_REWORK_R1记录集中修复，r6当前封存。新证据不覆盖旧失败。

### 逐条验收与实际成果

# HFUS-INDOOR-AI-TEST-01 实际结果 / review_candidate_r2

状态：SUBMITTED；算法目标BLOCKED，非ACCEPTED。唯一判据是原ACCEPTANCE_V2.md；此文件只记结果，不另立验收。

|ID|状态|证据与边界|
|---|---|---|
|A01|PASS|独立目录与新证据、旧资产SHA核验；未训练/设备/Git写|
|A02|PASS|186对逐ZIP/member SHA、float32×4/有限值/标签检查；不复制点云|
|A03|BLOCKED|526框旋转/末列未解决，完备UNKNOWN，人审0；显示明确AABB代理|
|A04|BLOCKED|0个可信独立采集组；保守单组，test0，未伪造随机split|
|A05|PASS|原cluster参数+HDBSCAN全186帧实际运行，源行/AABB保留；未分类几何候选|
|A06|PASS|旧RF/G0/shadow契约审计；具体缺依赖见MODEL_APPLICABILITY，不伪兼容推理|
|A07|BLOCKED|可信正/负0/0，所有候选UNKNOWN；旋转/完备门不绕过|
|A08|BLOCKED|新RF/PointNet无两类监督，神经启动0/steps0/训练秒0，无随机权重产物|
|A09|BLOCKED|几何独立进程重算见REPRODUCTION.json；学习权重重载无有效输入，BLOCKED|
|A10|BLOCKED|全部186帧有处理/排除账本；固定test0/可评GT0，主指标NA，不把代理当主表|
|A11|BLOCKED|CPU分阶段时延已测；可信覆盖/碎片、新RF/PointNet公平三seed不可评价|
|A12|PASS|实际浏览器同帧三栏、真实原点/代理框/实际候选；NOT_RUN/BLOCKED空预测。仅viewer软件，不是人检效果|
|A13|BLOCKED|全372帧×模型审阅案例可查；可信成功/失败无GT依据，0，不冒充10成功/10失败|
|A14|PASS|Python -B -W error、JS generation/实际HTTP/浏览器转换；源SHA/非法请求/缺预测拒绝|
|A15|NOT_RUN|开发后指定OpenCode只读审查；AI审代码记录，非人审或独立数值实验|
|A16|NOT_RUN|八问和实际瓶颈；下一阶段只规划，审查不可用则待审草案|


唯一验收V2 SHA：830f71bb76999d5a861d59c27b09d67fe736c694372a5a3071c75f62e33b8ec0。

实际det106帧/293框，track80帧/233框；186帧×2几何流=372行、224611个候选。旋转RESOLVED0、完备CONFIRMED0、人审0、可信独立采集组0；train/val/test0，全部仅诊断；正负可信监督0/0，全部候选UNKNOWN，神经启动0/steps0。主IoU/P/R/F1及可信覆盖/碎片、家具/逐点/空场指标不可评价，不把代理当GT。

复现命令：python -B -W error sidequests/hfus_indoor_ai_test/verify_run.py r6_20261015 <新的输出路径>。本次独立重算4个真实frame/model组合完全一致，读取224611候选行；97冻结资产SHA无差异。新产物约430.24MiB<512MiB，基线Windows peak_wset427552768B。

回归：python -B -W error -m unittest discover -s sidequests/hfus_indoor_ai_test -p test_indoor.py（10项exit0，TESTS_R5.log）；node sidequests/hfus_indoor_ai_test/demo/state.test.js（exit0）；node --check demo/app.js exit0。真实浏览器S1十样本、S2旋转缩放/全点/播放/快切/失败清屏，FINAL_R6_BROWSER与FINAL_R6_DEMO_TOP绑定当前run。

### 交给只读复审

当前源码停写，SOURCE_FREEZE_R2.json为最终15源文件SHA；run manifest 6a52ac9a4d69881259bfa90e4383a99cf0641d8c847d32b961a6ce3e97ffad91；split/config/payload/member/model适用性均可查。OpenCode指定模型probe6.078秒PROBE_OK/exit0，实际session export证实opencode-go/deepseek-v4.1-flash；正式开发后审查待进行，不能把probe算审查PASS。A15/A16状态将在新追加段落记录，不改此历史提交。

当前Demo：http://127.0.0.1:54850/indoor-ai/r6_20261015/ 。重启双击sidequests/hfus_indoor_ai_test/demo/start_demo.bat（默认固定r6、自动空闲端口），或python -B -W error sidequests/hfus_indoor_ai_test/demo/server.py --run r6_20261015。

审查输入：sidequests/hfus_indoor_ai_test/reports/review_candidate_r2/FINAL_REPORT.md与RESULTS.md；runs/r6_20261015/manifest/split/quality_ledger/training_status/metrics/case_index；数值父runs/r4_20261015/per_frame.jsonl、candidate_members.jsonl.gz、predictions.json；docs/human_capture/evidence/2026-10-15_hfus_indoor_ai_dev_r1_20261015/全部本轮证据。checkpoint不存在因为训练门BLOCKED；没有缺失权重伪装成运行。

下一阶段只在审查后依真实阻塞制定计划，不执行。


## 2026-10-15 开发R2审后收口 / SUBMITTED（算法目标BLOCKED）

### 本轮信息

HFUS-INDOOR-AI-TEST-01；Codex单源码writer，OpenCode仅只读。当前r7_20261015；唯一A01–A16 V2不改，SHA见最终RESULTS.json；master/HEAD c9c4ee421cb0c8a3e4590b8f5730828b093c759a及其他并行差异保留。状态SUBMITTED，不ACCEPTED。设备/物理/部署/采集NOT_RUN，学习/统计结论BLOCKED。

ponytail实际路径C:/Users/30680/.codex/skills/ponytail/SKILL.md；scientific-toolkit-skill与computer-use路径沿用本return开发R1实际读取记录。

### 集中诊断、返工与实际变更

r1/00_DIAG映射完整操作矩阵；r1/UI_REWORK_R1修共享load的case选择残留，r2/REVIEW_RESOLUTION接受P3-1并归一化verify_run保护路径，新增Windows/POSIX回归并把r2新证据纳入字节预算。P3-2按唯一补充R-4 `(-IoU,candidate_id,gt_id)`保留稳定字符串ID口径，并加回归；OpenCode R2确认符合原表。未改任何候选/几何阈值/真实分母；数值父run始终r4，source_rows账本无损保留。旧失败r2/r3、旧展示r5/r6和前审证据不覆盖。

实际更改/最终SHA见r2/SOURCE_FREEZE.json（15个实验源文件）；r7 manifest与父payload/config/split/member绑定可查。11项Python -B -W error exit0；JS generation及真实浏览器回归继承未改的实际源码版本；当前FINAL_BROWSER.json / FINAL_DEMO_TOP.jpg为r7。独立进程4个真实frame/model重新计算完全相同，224611候选行全可读。

保护检查为95项旧冻结资产SHA无差异，原97含2本工单新源码，修复后归一化排除新源码、另由SOURCE_FREEZE绑定，不减少旧资产保护。无原数据/模型/EXE/旧生产/旧证据覆盖。无Git写、训练/下载/HR09/E1/设备采集部署。

### 逐条验收

# HFUS-INDOOR-AI-TEST-01 实际结果 / post_review_final_r1

状态：SUBMITTED；算法目标BLOCKED，非ACCEPTED。唯一判据是原ACCEPTANCE_V2.md；此文件只记结果，不另立验收。

|ID|状态|证据与边界|
|---|---|---|
|A01|PASS|独立目录与新证据、旧资产SHA核验；未训练/设备/Git写|
|A02|PASS|186对逐ZIP/member SHA、float32×4/有限值/标签检查；不复制点云|
|A03|BLOCKED|526框旋转/末列未解决，完备UNKNOWN，人审0；显示明确AABB代理|
|A04|BLOCKED|0个可信独立采集组；保守单组，test0，未伪造随机split|
|A05|PASS|原cluster参数+HDBSCAN全186帧实际运行，源行/AABB保留；未分类几何候选|
|A06|PASS|旧RF/G0/shadow契约审计；具体缺依赖见MODEL_APPLICABILITY，不伪兼容推理|
|A07|BLOCKED|可信正/负0/0，所有候选UNKNOWN；旋转/完备门不绕过|
|A08|BLOCKED|新RF/PointNet无两类监督，神经启动0/steps0/训练秒0，无随机权重产物|
|A09|BLOCKED|几何独立进程重算见REPRODUCTION.json；学习权重重载无有效输入，BLOCKED|
|A10|BLOCKED|全部186帧有处理/排除账本；固定test0/可评GT0，主指标NA，不把代理当主表|
|A11|BLOCKED|CPU分阶段时延已测；可信覆盖/碎片、新RF/PointNet公平三seed不可评价|
|A12|PASS|实际浏览器同帧三栏、真实原点/代理框/实际候选；NOT_RUN/BLOCKED空预测。仅viewer软件，不是人检效果|
|A13|BLOCKED|全372帧×模型审阅案例可查；可信成功/失败无GT依据，0，不冒充10成功/10失败|
|A14|PASS|Python -B -W error、JS generation/实际HTTP/浏览器转换；源SHA/非法请求/缺预测拒绝|
|A15|PASS|开发后指定OpenCode只读审查；AI审代码记录，非人审或独立数值实验|
|A16|PASS|八问和实际瓶颈；下一阶段只规划，审查不可用则待审草案|


### 实测与限制

186帧/526待核验框、372帧×模型记录、224611未分类候选。旋转RESOLVED0、exhaustive CONFIRMED0、人审0、可信独立组0；train/val/test0；可信监督P/N0/0，新RF/PointNet启动0/steps0，L3D/L2D/LFUSION未训练。主IoU/定位/P/R/F1、可信覆盖碎片、公平三seed、家具/空场/逐点指标均不可评价。没有“AI已识别人”或“家具误检改善”结论。

候选CPU P50/P95ms：det B0 915.02/1207.26、HDBSCAN5049.35/6570.22；track B0 802.95/987.69、HDBSCAN4542.52/5171.98。诊断口径含全部失败/空候选，前5全局帧预热除外，不是独立test或板端FPS。峰值427552768B，新字节最终以DELIVERY_BINDING.json为准，包含全部失败run/r1+r2证据，预算512MiB。

### 实际OpenCode审查

R1 209.125秒exit0 READONLY_NO_NEW_DEFECT、两P3已集中复核；R2 379.406秒exit0 READONLY_NO_NEW_DEFECT，无新软件缺陷。实际session ses_ec0fe44d1ffeQPYwoZcW4ZFmOe；session export证实opencode-go/deepseek-v4.1-flash；完整brief读至sentinel，实际工具仅glob/grep/read；snapshot=false，edit/bash/task deny，不改全局/DB/auth。见r2/REVIEW_AUDIT_VERIFICATION.json、原始jsonl、status、session export和复审md。AI源码/记录审查，非独立数值实验、非人工GT。

### 当前可看入口与后续

- [最终报告](../../../sidequests/hfus_indoor_ai_test/reports/post_review_final_r1/FINAL_REPORT.md) / [逐条结果](../../../sidequests/hfus_indoor_ai_test/reports/post_review_final_r1/RESULTS.md)。
- [当前run](../../../sidequests/hfus_indoor_ai_test/runs/r7_20261015/manifest.json)，父r4保留，原始成员SHA/指标/案例全可查；新权重不存在因为训练门BLOCKED。
- [启动脚本](../../../sidequests/hfus_indoor_ai_test/demo/start_demo.bat)，默认固定r7，自动空闲端口；当前准确URL http://127.0.0.1:51034/indoor-ai/r7_20261015/ 。命令python -B -W error sidequests/hfus_indoor_ai_test/demo/server.py --run r7_20261015。
- [审后下一阶段计划](../../../sidequests/hfus_indoor_ai_test/reports/next_stage_20261015_r1/NEXT_STAGE_PLAN_V2.md) / [唯一拟验收V2](../../../sidequests/hfus_indoor_ai_test/reports/next_stage_20261015_r1/ACCEPTANCE_V2.md) / [开发提示词V2](../../../sidequests/hfus_indoor_ai_test/reports/next_stage_20261015_r1/AI_DEVELOPMENT_PROMPT_V2.md)。状态DRAFT_READY_FOR_DISPATCH，ND01–ND08全部NOT_RUN。首要瓶颈是数据定义/真实人工审核与录制组映射，先解决来源和标注，不继续训练或优先补采。只制定，未自动执行/派工/解锁下一阶段。

以上新r2记录为当前收口；上方r5/r6 URL与待审段均为保留历史。
