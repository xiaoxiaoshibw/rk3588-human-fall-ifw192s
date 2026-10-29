## 2026-10-15 / LOCAL-INDOOR-LIDAR-01 阶段一 R1提交及集中返工收口

### 本轮信息

- 执行者：Codex唯一源码writer；OpenCode仅指定`opencode-go/deepseek-v4.1-flash`、plan只读。状态 **SUBMITTED；人体损失定位/候选改进/训练资格BLOCKED**，非ACCEPTED。
- 唯一验收：[ACCEPTANCE_V1.md](../evidence/2026-10-15_local_indoor_lidar_phase1_r1/ACCEPTANCE_V1.md)，SHA见ENVIRONMENT_FINAL.json；正式[FINAL_REPORT](../evidence/2026-10-15_local_indoor_lidar_phase1_r1/FINAL_REPORT.md)包含六问结论。该表仅为本新工单，不与公开实验或HFUS E0/E1混用。
- 起始master/HEAD `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`，dirty，原status与103项相关tracked+untracked源码/配置/权重/冻结资产SHA在BASELINE_BEFORE.json；最终103项零变化，10新源码SHA匹配DELIVERY_V4，HEAD不变。其他并行差异保持；不声称整库冻结。
- 实际读取技能：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`、`C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md`；浏览器按`C:/Users/30680/.codex/plugins/cache/openai-bundled/computer-use/26.1007.71326/skills/computer-use/SKILL.md`及guidance/confirmations，使用其推荐Browser Use（CUA）验证。
- 仅写新`sidequests/local_indoor_lidar_phase1/`、新证据`docs/human_capture/evidence/2026-10-15_local_indoor_lidar_phase1_r1/`及本return。没有覆盖旧生产/默认R1/learn/r01/权重/EXE/历史证据；data/captures只读，无reset/checkout/clean/commit/push、训练/随机模型预测、下载/解压、采集/部署/驱动网络变更、HR09/E1。

### 集中诊断与根因覆盖

实现前[00_DIAG.md](../evidence/2026-10-15_local_indoor_lidar_phase1_r1/00_DIAG.md)已列startup/reload/同ID漂移/新sid/frame/快切/坏输入/缺源/失败恢复/审核UNKNOWN/重复与组门操作矩阵，映射L01–L08。

|ID/问题|根因与受影响入口/状态|最小实现与保留|
|---|---|---|
|L02 输入与旧权重|旧README示例16B，实际28B；本地强度不能继承公开全0；原train.py会顶层训练|28B只读stride、XYZ/名义R/T与原注册；强度12实值核验；不import旧train.py，不伪特征兼容|
|L05 候选损失不可审计|旧R1聚类后ROI/因果选择单目标可能隐藏未选簇；缺逐点人体GT|复用原core.cluster/actions.choose，记录所有簇/源成员/终止原因，不修改数值算法或默认|
|L03 人工与建议|历史reviewed/human不能替代本轮，用户明确确认的是一帧候选语义|真实聊天确认绑定sid/frame/source/member SHA；1帧7判断，C2 HUMAN_PRESENT，六NONHUMAN；完整/遮挡/漏标UNKNOWN，AI建议独立|
|L07 生命周期|快切/失败易留旧预测、旧人工草稿或队列不匹配|latest generation+abort、先清空再请求、草稿清空、当前队列同步、源/结果SHA拒绝漂移|
|L01/L03/L07审后四项LOW|创建快照0与实时审核数混淆；聊天null与表单bool不一致；静态源中途漂移；断连异常|动态1帧/7记录；统一null=UNKNOWN；静态SHA/runtime签名；只吞标准断连。原快照/失败日志保留|

### 实际变更与运行入口

新10文件：`prototype.py`（冻结R1追踪/预检）、`server.py`（只读源/三栏API/append-only人审）、`verify.py`（全量独立复算）、`index.html/app.js/state.js`（同帧三栏/生命周期）、`test_prototype.py/state.test.js`（隔离软件检查）、`start_demo.bat/README.md`（入口/限制）。最终精确SHA在DELIVERY_V4.json，不在此复制第二套清单。数值prototype.py首算后未变；原RUN_MANIFEST.code内旧UI仅历史prepare快照，当前UI独立版本绑定，未重签旧数值。

双击[独立启动脚本](../../../sidequests/local_indoor_lidar_phase1/start_demo.bat)，或仓库根执行`python -B -W error sidequests/local_indoor_lidar_phase1/server.py`，打印空闲端口URL。本次准确运行URL **http://127.0.0.1:63383/**，当前页留在cap_20261013_083254/f0/C2，全点49136/49136。[用法](../../../sidequests/local_indoor_lidar_phase1/README.md)。Three.js本地复用，无CDN，无旧console/EXE改动。

### 逐条验收

|ID / 入口或转换|层级|实际检查 / 结果|证据|
|---|---|---|---|
|L01 范围/输入/保护|offline software|PASS；九段用户当前明确授权，103旧资产零变化，10新源冻结，4线程/资源未超限|BASELINE_BEFORE、PRESERVATION_AND_RESOURCE_FINAL、DELIVERY_V4、RUN_MANIFEST|
|L02 原点/坐标/背景|offline+fixture|PASS（名义坐标，非物理标定）；18源SHA、28B/源行守恒、全候选成员及bbox复核，缺源/非法/漂移拒绝|RUN_MANIFEST、REPRODUCTION_FINAL、HTTP_AND_LIFECYCLE_R1、SOFTWARE_REWORK_R1|
|L03 人工标签资格|real human|BLOCKED；固定24帧队列只完成1帧，7候选意见；逐点GT/完整性/漏标分母0，不能由AI补成GT|human_reviews/、LABEL_QUALIFICATION_CURRENT、REVIEW_QUEUE、AI_GEOMETRY_SUGGESTIONS|
|L04 独立组/重复/冻结划分|offline|BLOCKED；2024帧精确SHA无重复组；24帧近重复276对/15待核验；可信独立组0，train/val/test空|baseline_r1/DUPLICATES、RUN_MANIFEST.split|
|L05 原候选链|offline real data|BLOCKED整体（几何完整运行PASS）；2024帧/99329595点次/11840候选次；独立全量复算及旧R1兼容2024/2024；无人体损失分母|FRAME_LEDGER、INDEX、逐帧JSON/NPZ、REPRODUCTION_R1/R2/FINAL及资源日志|
|L06 改进公平对照|offline|BLOCKED；未确认首因/独立留出，不调测试参数；改进配置0，不宣称几何或人体改善|FINAL_REPORT六问、RESOURCE summary|
|L07 真实三栏/状态/复现|software+real browser|PASS；全点、切帧sid、播放暂停、快切最新、显隐/相机、队列疑点跳转、RF BLOCKED清空/恢复、UI/runtime漂移门|BROWSER_VALIDATION_R2、BROWSER_REWORK_R1_CHECK、BROWSER_FINAL_R4.jpg、STATE_TESTS、HTTP_AND_LIFECYCLE|
|L08 报告/审查/资格报告|read-only review|PASS（交付范围）；R1四LOW集中返工后R2 READONLY_NO_NEW_DEFECT；实际模型export及完整brief读取/权限轨迹核对；训练资格仍BLOCKED|FINAL_REPORT、OPENCODE_REVIEW_R1/R2、REVIEW_RESOLUTION_R1、OPENCODE_AUDIT_FINAL、本return|

### 实际命令、退出码与资源

- `python -B -W error .../prototype.py prepare`：exit0，18原始SHA核对；`.../prototype.py replay`：exit0，完整2024，原始BASELINE_RUN.log。该首算executor保留旧整包SHA门，不冒称当前复跑入口。
- 当前复算：`python -B -W error sidequests/local_indoor_lidar_phase1/verify.py <新的结果.json>`；最终REPRODUCTION_FINAL_RESOURCE记录完整原始command/exit0/218.781s/峰值631771136B，全部2024原行/候选/旧R1选点一致；前两次结果保留。
- `python -B -W error -m unittest discover -s sidequests/local_indoor_lidar_phase1 -p test_prototype.py`：最终7项exit0（SOFTWARE_REWORK_R1.log）；初次错误导入旧server的失败日志保留，仅测试路径修正。隔离fixture不进人审/指标。
- `node .../state.test.js`与`node --check .../app.js`：exit0；12项真实HTTP/fixture契约检查PASS，实际浏览器广覆盖和最终V4快切/审核/全点核对PASS。测试总数不替代上述验收。
- 初算峰值630411264B；最终复算631771136B；服务另观测RSS174714880B、peak_wset194015232B，非整机合计峰值。8GiB目标/12GiB停止均未触发，新增预算远小于512MiB，最终清单在DELIVERY_FINAL_AUDIT。CPU分阶段P50/P95、分会话wall与全部排除在RESOURCE_AND_GEOMETRY_SUMMARY/FRAME_LEDGER；Windows process_time存在15.625ms量化，不把0ms当零成本。

### 未闭合与限制

1. 已有两类人工候选存在性意见1含人/6非人，但完整纯度/逐点GT/全帧漏标尚未确认；不能报告人体召回、切碎/家具混合率、空场FP或独立识别准确率。L03/L05语义BLOCKED。
2. 可信独立组0、无独立test；近重复筛查仅24队列，不冒充全2024近重复穷尽。L04 BLOCKED。
3. 原背景cap131958原源缺失，只复用冻结artifact，原FIT/CAL无法重验；新221808仅沿原91/91/90边界，未把名称当负类。不补采、不重建历史。
4. 本轮候选数值改动0、配置搜索0，改的是可看可追踪可审核。下一步先审核剩余23帧与组来源，确定首因后再决定有界候选修复；训练需要另行固定目标/特征/结构/seed/阈值/资源与明确授权。本轮不自动训练。
5. 设备/物理/板端/部署NOT_RUN，非本地软件结果可替代；不推进HR09或HFUS E1。

### 交给Codex全表复核

指定CLI路径实查和≤55秒probe实际8.875秒/exit0/无工具；R1/R2实际session导出providerID=opencode-go、id=deepseek-v4.1-flash、agent=plan。R1 READONLY_REVISE→集中返工→R2 READONLY_NO_NEW_DEFECT，session `ses_ec00b4e4efferBdm4Jls7Z9ryj`，exit0/340.36秒；源码停写后只读审查。完整brief读取覆盖1到末行，原始jsonl、exit、读取记录、model export与权限配置/实际工具记录均存证。session export未提供permissions字段，如实以运行配置与tool轨迹分列，不补造字段。OpenCode为AI源码/记录审查，不是独立实验或人工标签；Codex另外实际复算/保护/浏览器核验如上。

当前交付SUBMITTED，整体目标未ACCEPTED；可以继续人工审核和有证据的诊断，不包含下一阶段训练授权。
