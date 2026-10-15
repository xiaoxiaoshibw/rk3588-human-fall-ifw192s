# HFUS-LEARN-DEV-03 开发AI提示词 v2

本文件供用户下一轮向执行AI派发。**生成/审查本提示词不启动开发、训练、下载、HR09或部署。** 文件中的授权说明/样例不算真实授权；下一轮执行必须读取用户实际附加指令。

---

你是D:/Code/ldiar项目的开发AI，指定的唯一算法/实验/共享服务writer。落实已审大阶段计划，交付真实离线实现、可信标注工具与证据、学习/几何全量对照和原页面，不再交一次只有推荐/148帧试验的报告。允许失败、NO_ELIGIBLE_MODEL/NO_END_TO_END_WINNER；不造收益，不自行ACCEPTED或默认晋级。

## 1. 开工必读与唯一要求

按序读仓库AGENTS.md、docs/human_fall/WORKFLOW.md当前顶部、docs/human_capture/README.md当前顶部；再读实际路径C:/Users/30680/.codex/skills/ponytail/SKILL.md与scientific-toolkit-skill/SKILL.md，记录实际路径；本环境不同则找到真实技能，不假报。

完整读取本提示词同目录：

- DEVELOPMENT_PLAN_V2.md（全部10工作包和固定指标/预算）；
- ACCEPTANCE_V2.md（L01–L18唯一拟实施基线）；
- PLAN_REVIEW.md（最终只读审查及修订指针；未审完/需修改不得假称已审通过）；
- DATA_PREFLIGHT_V2.json、EXPERIMENT_SPLIT_V2.json、ANNOTATION_QUEUE_V2.json、EXPERIMENT_BUDGET_V2.json。

再读docs/human_capture/evidence/2026-10-15_hfus_next_dev_r1及2026-10-15_hfus_deep_routes_r1的FINAL_REPORT、RESULTS、manifest、审查/返工；追sidequests/human_fusion_lab_next/pointset/r01实际core/actions/next_contract/server/app、deep_routes/r01四脚本、原console入口和所有消费者。历史条目不扩大授权；旧N/Q要求和原报告不改。本单新建实施证据目录，不能写回计划/研究证据。

## 2. 明确权限，不把提示词当授权

用户实际派发本任务后，在已授权本机离线范围做E0软件工作。**训练E1须用户另附明确的sidequest轻量训练授权**，包括计划36作业、累计30h墙钟、2线程/4GiB/80GiB边界，并满足可信标签门。授权说明仅写在本文件而用户未实际追加的，不能开训；不能用“调研/都尝试/大阶段”推导出训练/下载许可。ML/仍须另有“开工HR-09”，本工单不激活。

缺E1或人工标签时，一次列清缺口并继续标注工具/表示/模型接口/合成契约/基线全量/页面/性能/复现等不依赖工作；相应训练/模型效果BLOCKED，不停在口头计划，不伪造学习目标完成。不要反复逐帧问确认；人工待办集中批量提交，但不能未经授权给他人发消息/上传点云。

不安装全局环境或GPU依赖、不下载运行大模型/公开大数据；新依赖/下载须另有明确许可、版本/SHA/字节/许可/目标路径清单。现有CPU PyTorch可运行的轻量路线优先。物理、板端、驱动网络、采集部署、真实跌倒实验NOT_RUN；不接管无关real_fall/其他主线。

data/和captures联接只读，不删除/清理/移动/重命名/写标签/写metadata或git add；GT、模型、配置、历史输出保留。无commit/push/reset/checkout/clean。只有当前指定writer改源；可交只读审查，不能多AI各改算法来规避单writer。只重启确认归本单管理的PID，记录端口/代码版本，不按端口杀进程，不停用户console/其他服务。默认R1不变，不新建重复应用。

## 3. 先建立能审查的输入和矩阵

按Asia/Shanghai实际日期建docs/human_capture/evidence/<date>_hfus_learn_dev_r<N>/，已有则递增。保存branch/HEAD、完整dirty状态、全部影响tracked/untracked源与模型/配置前SHA，保留用户并行差异。

重新实测八动作1934帧、新空场272帧的18原SHA/28B/offset/count/设备时间；旧/新background、历史变换/注册SHA；旧131958原字节/CAL缺失明确BLOCKED，旧32只缓存XYZ。不得沿用本计划预检PASS当本轮实测。

在00_diag.md逐项映射计划§9操作矩阵到真实函数/调用者/消费者、来源、检查→计算→写入顺序和失败行为；先复现原约1m粗槽跳、缺轴、径向/轴深度排序反例及方向变化探针。固定RUN_MANIFEST/授权原文、完整sid分组、输入U、标注schema、全部候选与预算后继续做，例行工程决策自行解决。

## 4. 本阶段必须一起落实的工作

1. **源与标签闭环**：U为所有有限非零且原range在0.2–15m的当前源点，未先过ROI/高度/背景。输出raw/nominal/注册补偿各坐标版本。同应用版本闸门视图提供点/像素源行联动、建议/人工审核/UNKNOWN/实例与可见性、撤销/修订审计；474队列项（282人工核心、192非金标建议）按冻结队列生成，不将建议冒充GT。
2. **可信门**：282核心（每sid24动作帧+90空场）真实人工审核；每动作sid至少12核心帧≥25可信人体点并有可信非人体点；冻结66帧独立第二人工复核（≥20%）与K/U质量门，分歧UNKNOWN。未知不作负例、旧winner/ROI/13槽不作人体/关节GT；实例、关节、事件证据各有门，不能一次放行全部损失。
3. **扫描适配**：仅用91FIT定模板，冻结两工作分辨率/边界/坐标，r和轴depth各自遮挡排序，mask/多层K2/溢出CSR/裁外保留；3D保持全U。原28B未核实字段不臆解强度/环号。全1934+90量化碰撞/空洞/裁外/多深度与源守恒，不把补洞当测量。
4. **真实逐点学习**：E1与对应标签门通过后，按计划做L3D、L2D、LFUSION三族；共同语义头与最多4个场景instance query/点mask，不要求先完美XYZ聚类。query不是物理ID，歧义UNKNOWN；无可信完整实例标注不强训no-object/实例损失。旧二分类器只能冻结控制，不当新分割头。
5. **有界选择/训练**：开发960只在4个完整sid内4折；24筛选作业、9最终seed作业、3训练消融，共36/≤30h；固定2配置/3阈值、seed19/43/97，主权重seed43。全部fit失败/截停/预算日志保留；不借974调阈值/朝向/模板/seed/架构。授权/标签门不满足时不得以随机权重运行冒充学到语义。
6. **结构与因果**：13槽测量、网络关节推断、显示平滑分列；关节GT不足明确BLOCKED。各方案全会话从头关联，处理query重排/分裂合并/遮挡/弱观测/多解/换身份/回退/超时。时序最多过去8帧/1s，前缀检查；事件资格来自近期可靠非低测量，初始躺地与快/慢下降分开，受控躺下不是跌倒TP。
7. **全量对照**：G0固定为旧冻结B，R1/A为附加历史控制、G1 HDBSCAN、3族3seed、3训练消融和推理压力开关，全部1934动作+90新空场冻结回放；成员/语义/实例/姿态/事件/拒识逐点逐帧绑定源/时间/版本。共享common节省空间，不复用旧winner证明新算法。未训/未适配模型如实NOT_RUN，E0基线仍完整交。
8. **固定评估**：按计划§8定义U/K/X、每sid宏IoU/recall/背景FP/覆盖/未知、零分母NA、K外预测；GT人体上的预测未知计FN，背景未知不算TN。按冻结排序/非退化/2pp提升门选择一次主族，974只验冻结候选，失败不反选其他族。候选缺测/轴缺测分母、所有端点/共同可算转移/最差帧全部列出，不再用排除1m反例后的集合覆盖全窗口问题。语义只能报实际已审核范围。
9. **原页与console**：原server/app同sid/fi切换全方案/源XYZ/多层深度/人工GT/预测/失败/UNKNOWN/缺源；查询原28B与源行，成员增删颜色、完整模型/代码/权重版本。跳帧只读取冻结结果，不临时续算tracker；R1和历史仍可用。源码/实际browser/总EXE分别验证，打包后置另名，不能“网页好=旧EXE已更新”。
10. **性能与闭环**：每会话/源动作/距离/可见性、seed差异、CPU阶段/端到端P50/P95及真实峰值内存/最差20反例。非平凡修复用会暴露原错的回归；Python -B -W error及真实受影响JS/console套件。当前源码/主权重必须真实新目录跑1934+90并核数值/成员差异，不拿check-only当完整复现。入口/依赖/权重/归档源码/输出SHA可追，执行期和当前源码分列。

## 5. 完成判据与一次集中回传

严格按L01–L18逐项PASS/FAIL/NOT_RUN/BLOCKED，测试数量/模型数量不是完成。缺真实GT不阻止软件/几何/页面交付，但不能宣布语义/关节/学习已完成。允许NO_ELIGIBLE_MODEL/NO_END_TO_END_WINNER，有收益/无收益都交；本单不晋级默认。

交RUN_MANIFEST、AUTHORITIES、DATA_PREFLIGHT、LABEL_MANIFEST与人工审核/覆盖、扫描模板/源CSR审计、完整36作业矩阵与实际状态/日志、MODEL_CARDS与权重/代码/许可、全1934+90逐点/逐帧/因果结果、COMPARE_SUMMARY/分母/性能/最差反例、原页深链与真实browser证据、当前源新目录全量复现、前后SHA与实际命令/退出码、RESULTS与FINAL_REPORT及完整产物索引。不覆盖计划验收/旧报告/失败，不自填进程exit0。

算法writer停止源写后交OpenCode只读全表审核，集中修范围内缺陷并留失败/版本；读不到或无法独审NOT_RUN，不称作者自验为独审。按docs/human_fall/RETURN_TEMPLATE.md追加docs/human_capture/returns/HFUS-LEARN-DEV-03.md和REVIEW_LOG，HF/HC入口仅追加实际本轮范围与证据，不覆盖历史。

最后只交SUBMITTED或有证据BLOCKED的一页结论：哪些变好/退化、冻结候选/NO_WINNER、当前原页面与模型/代码版本、语义/关节/授权/设备缺口。不让用户拼接多轮回传，不自动接下一单。


## v2不可省略的开工/实施闸门

先核PLAN_REVIEW最后明确结论必须是PLAN_PASS，且明确指向DEVELOPMENT_PLAN_V2/ACCEPTANCE_V2/本提示词及配套JSON的SHA。若仍PENDING/PLAN_REVISE/指针不一致，不按未审计划开算法工，集中报告需修订；不得把文件存在或作者自验当OpenCode已通过。即使PLAN_PASS也只证明计划可执行，不是E1授权/开发验收。

计划v2闭环细则是本提示词的一部分，必须完整实施：

- 474是282人工核心+192建议；第二人工审核66帧名单固定，不能将AI建议或未知点自动升级金标。开发监督集只取4dev的96核心，筛选每fold72训练/24验证，final每epoch96；未标帧不当监督负样本。OOF、FINAL_DEV4、COMPARE_974_LABEL96、EMPTY90角色分别装载/打分，不能把训练拟合成绩称比较结果。
- E0必须先做≤12个无参数更新资源profile（随机权重只测shape/吞吐/峰值；可合成loss反传但无optimizer.step、参数SHA相等）。按真实P95/内存先于验证成绩冻结全族共同分辨率与E_screen10–40/E_final15–40、batch1；不满足128x512及预算则资源BLOCKED，不静默减要求/加预算/装GPU。详读OUTPUT_BUDGET_V2，稀疏二进制/共享common，禁止密集图/128D全点embedding重复落盘，估算约73.72GiB不是实测。
- 原r01已绑定的server/app/index字节优先保持；新增同应用版本模块/路由与原console入口，不另起重复demo。必要共享入口重构先有完整旧源归档、旧run冻结资源/新路由隔离方案与消费者证据，不能直接修改历史绑定后重签；旧默认与旧运行EXE状态分开。
- 实例query/结构/关节软件接口与损失开关必交；实例监督看未来真实人工实例证据，关节GT当前缺失故真实关节评分BLOCKED、未提供模型推理NOT_RUN。接口测试不当学习效果；没有有效主族则3训练消融NOT_RUN，36是上限，不凑数，不称学习阶段完整完成。
- 固定G0为旧冻结B，不得看哪一基线弱就切G0。共同转移评分不覆盖所有端点/最差帧；974只检验一次冻结主族/seed43，不换族不挑seed。审查时需同时交OOF的96验证预测和最终比较96+90，不能拿同一全dev模型自评282。

主语义集合S_sem、实例划分、可靠当前S_event的阈值/缺测区分与4fold齐全门严格执行计划v2细则F，不能拿关节显示、未关联语义点或缺fold的平均分代替主指标。
