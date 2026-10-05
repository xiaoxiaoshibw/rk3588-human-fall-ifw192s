# GL-I05 R1主研究/开发AI提示词

工作目录：D:/Code/ldiar。任务：[GLI05_TASK.md](GLI05_TASK.md)。唯一判据：[GLI05_ACCEPTANCE.md](GLI05_ACCEPTANCE.md) v1。本提示在2026-10-03准备，当前未实施/未派发；用户明确让你按本提示执行时，直接开展下面的离线研究，不为例行设计再次确认。不把GL-I05误作GL-05设备阶段。

## 角色和执行方式

你负责研究、判断、代码实现和实验计划修订，默认Codex为唯一研究writer。理解目标并使用ponytail最小实现，先完整读C:/Users/30680/.codex/skills/ponytail/SKILL.md并记实际路径。研究代码也实行单writer；本单不改任何生产src。完成可审自验提交并停止研究/测试写入后，交OpenCode CLI `opencode-go/deepseek-v4.1-flash` / default DB独立二审。二审不是你的自验，不用服务阻塞本地开发。二审派前一次≤1min无工具probe，失败如实BLOCKED、不切model/DB/auth/权限/全局配置。必要返工先明确交接，不能两个writer并行。

不要照旧步骤硬推进：提出能被反例推翻的假设，先做最小判别实验，再归纳和调整。没有速度收益可以是诚实成果；任何竞争误闭合/预算误升级/永远拒正例是FAIL，先集中修复。真实calibration成功不是本单完成条件。

## 先完整读取

1. docs/human_fall/WORKFLOW.md当前覆盖和流程正文；GLI05_TASK.md、GLI05_ACCEPTANCE.md v1、RETURN_TEMPLATE.md。
2. GL-I04 evidence/2026-10-03_gl_i04_r1/32_CLOSEOUT.md、33_SCOPE_CLARIFICATION.md、19_PLAN_REVISION_AND_DECISION.md、22_final_research_summary.json和opencode_second_review_01/00_review.md。
3. 本单默认evidence/2026-10-03_gl_i05_r1/00_PLAN_REVIEW.md、01_plan_manifest.json、02_existing_trace_audit.json。该审计只重算旧trace，没有新原型结果。
4. 实际core/capture_input.py的load_adapted/gate_selection/源成员映射、core/ground.py冻结sampling/qualification/refine/competition/validation、core/ground_diagnostics.py的replay/refine/observe以及GL-I04研究原型/experiment。沿实际调用链读，不注入全部历轮CLI或无关仓库。

## 开始时建立基线

核live branch/HEAD和完整tracked+untracked/SHA，当前锚点master/cbd0be1c86a1051a9a5800dfb7263f842896e1e6，只作比对，不reset。检查本单无另一个writer。01_plan_manifest给出写计划时相关SHA，执行时重新验证，合法共享树变化分类保留，不把old_tree_changes=[]写成无新增文件。

保护GL-I04三生产文件及研究/报告、所有旧core/config/tests/GL-I03三文件、批准capture/NPZ/draft、driver/HR/pc_apps/UI和历史证据。实际输入仍为GL-I02/08_real/real_candidate.adapted.npz和GL-I02/codex_review_01/work/filled_real_draft.json；不重新prepare原数据。approved up=[0.438371,0,0.898794]、height=[1.2,1.7]和原四box保持。negative-X和数据法向仅WHAT_IF，不替换批准值。

默认run_root=docs/human_fall/evidence/2026-10-03_gl_i05_r1；若跨日，建当天独立目录并记录root、保留准备证据。现有planning产物只读，新证据独占新文件/子目录，不覆盖。所有实现只在本单research_01/及本单集中tests，无生产新路径/接入点。

## 写前诊断与实验

先写简短00_diag.md，将唯一表C/E/S与Q01–Q10映射到实际函数、赋值/资格顺序、caller/版本/预算pending→terminal行为，说明ROS热reload/GL02锁定生命周期不适用；文件身份、缓存和候选末态组合不能裁剪。明确研究契约新增终态与旧GL-I04/冻结ground资格不是同一种结论。

**先oracle与原因归因，后新原型，最后成本优化。** TASK研究契约为依据，不从当前实现抄预期：

- ALL是所有已见精炼见证两两关系；NEAR是`.8*best_support`以上全部见证池的两两关系，包括所有best ties；BEST_ONLY仅对照，不能用于闭合。32旧trace中8条best-only漏判，high_noise_seed7池内33 distinct对而top-to-near为0。中间best/相似链不能被洗成通过。
- 区分seen_pairwise_closed、seen_dominant_pool_closed和unresolved，显式判别域/finite-sequence-only/physical=false。弱distinct即便有完整dominant证明也不能称全候选唯一。near-pool有distinct或任何未处理/预算/证明缺口都未决；不靠最终候选剩1清旗。
- 建独立小型oracle（只测试/证据可保存全部同序列见证），所有合格raw有处理事件和计数。新原型自身候选/证明/trace存储有界，不能回读全trace偷偷当无限候选缓存。0/4/8°全相似集合的首锚/全部排列可揭示包络假拒；0/6/12°/middle-best/late competitor必须保守，输出可核查实际见证。
- 比较冻结baseline、已审GL-I04与新prototype，source/selector/settings/seed/已见抽样序列一致，保存sequence SHA。冻结fit的实际status/validation独立于oracle/后算指标；早退后不能假称native validation发生。

至少执行唯一表Q的全部场景：清洁/低噪/高噪、weak distinct/close/two-plane、三seed×原和置换、重复、support ratio边界/tie、晚到更强best和第二平面、candidate/refine/trace/iteration/证明预算不足、cache可选证明与版本/caller变化、四box每frame和source层身份。记录oracle差异、误闭合、额外未决、处理/资源峰值和实际成本；不得预设35mm噪声必须闭合或真实WHAT_IF应通过。

## 成本优化是待证假设

先分阶段profile，不承诺加速。相同sample-inlier成员的精炼复用需验证完整数学依赖与字节身份。优先单次run局部有界cache，避免持久缓存/新框架；每run固定source/fit/sample/up/height/settings/源码上下文，相同mask还须精确核对成员，不能仅哈希或近似normal命中。不同mask、hash碰撞、caller修改、source/settings/up/height/实现变化要反例。cache满可以回退未缓存精炼，不能吞合格项；refine/trace/处理预算耗尽依旧unresolved。不能为cache命中率改采样、原qualification、10°/.05m/.8门。

若证明不成立或收益不足，保留未缓存正确原型并明确不采用cache，删除未验证缓存路径。oracle只算同已见序列，不证明未见假设不存在。记录sampling/raw/refine/decision/serialization、cache hit/miss/refine_calls、工作存储峰值与多次重复；全fit包括holdout、搜索不包括时不能冒称公平端到端加速。此为本机成本，目标板性能NOT_RUN。

## 物理证据分支

复用GL-I04诊断成果制作可逐frame/box定位的最小离线空间产物（自包含HTML或等价图集）。全统计仍所有原选中点；显示抽样须显式source索引/规则/数量。source XYZ/研究法向残差/WHAT_IF参考plane分别标注。empty、显示预算、source row/ordinal/seq、alias/跨组和非法输入都验证。产物不接生产webui，不自动提交新ROI或记录“地面已验证”。

只定界检查GL-I04之后新增或明确漏检的既有本地录制资料，一次给出窗口/提取时刻/config身份/from-to/SDK变换/文件SHA及缺失表；无新资料沿用旧缺口，不重复全历史、不连接板端/网络、不部署/重采集。recording extrinsic/world-up表达/区域地面身份未知保持unknown；历史六零、frame名、FIT法向、约1.1m光学窗口高度均不能代替点云原点/录制证据。不得按FIT残差筛validation制造通过。

## 提交、二审与决策

按C01–C06/E01–E02/S01/B01–B02/D01–D02及Q逐行自验：手算/已知反例→兄弟状态与版本→回归→实际输入→首尾范围/SHA。必要软件未跑NOT_RUN；B类缺证据BLOCKED不阻软件研究；D类未执行NOT_RUN。原生产suite仍适用，最小新tests只本单研究目录，Python3.8 AST/stdlib+NumPy兼容，不冒称板端验证。

提交本轮11_submission_manifest.json，包括全部相关新研究代码/tests、被冻结source/config/input、所有报告/设置/序列/原始日志及完整首尾基线引用。**先关闭stdout/log，再计算其SHA；manifest自身与正在写的日志不纳入自哈希集合。** 版本/源内容变化需新证据，不能复用旧PASS。按RETURN_TEMPLATE在returns/GL-I05.md追加SUBMITTED/BLOCKED，记实际writer/技能路径/每ID层级/命令exit/SHA/失败与计划修订。然后停止实现/测试写入。

提供具体run_root、manifest和独立检查目标，按AI_PROMPT_GLI05_OPENCODE_SECOND_REVIEW_R1.md执行指定Go Flash/defaultDB probe和只读二审。OpenCode只用native skill(name=ponytail)，不得读/扫描/哈希外部Codex技能目录来比对；所有审查尝试用新编号文件，保留自身失败脚本/输出。记录真实CLI session/model/defaultDB/exit/finish，原始命令输出必须有真实文件入口，缺日志不能虚构文件名。服务失败不让自己冒充独审。

最终按唯一验收ID收口、更新当前指针；给出采用/不采用/需补实验的研究结论、适用边界与下一个最小判别实验。源码/生产路径/ground资格保持冻结，任何新接入或物理先验/ROI改变仅提出具体提案。本单不自动启动后续工单、GL-05设备、GL04DPR/正式页或部署。
