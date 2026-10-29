# HFUS-TCMS-02-PLAN 回传

## 2026-10-16 r1 本轮信息

- 用户本轮要求：逐句审查10秒背景冻结、遮挡、同向运动、聚类人体、骨架与时序预判；联网/GitHub参考，多轮设计；本轮仅规划。
- 执行者：Codex主作者；audit_reuse、visibility_research、pose_temporal_review三只读助手。无算法writer、CLI开发、训练或设备任务。
- 状态SUBMITTED；新实现/设备/物理NOT_RUN，人体/骨架/真实跌倒/提前预警效果BLOCKED，非ACCEPTED。
- 当前唯一验收：[TP01–TP08 v1](../evidence/2026-10-16_hfus_tcms_02_plan_r1/ACCEPTANCE_V1.md)，SHA256 `97c0a2ef10d708dea58d7b3a3253802c3c9818a8f12ab9153d93de51ea8e416f`。
- 起始master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a；相关tracked/untracked源SHA及用户差异见BASELINE。全非忽略树13009路径另存TREE_SNAPSHOT，明确为规划文档完成后快照，不伪报起始全树冻结。
- 已读技能：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`、`C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md`及`references/scientific-skills/paper-lookup/SKILL.md`；Crossref/arXiv参考端点已读。无新依赖/权重/数据下载。

## 集中诊断与根因覆盖

当前B3以固定块/双窗/±1格解释非刚体人体，早窗缺支撑直接不评分，用户指定运动会话响应弱。新方案用冻结表面与可见性解释找种子，再扩展当前可见成员，避免同向硬门。没有命中并不证明遮挡，前景不直接human，粗部位不改名真关节，HMM不自动获得提前预警。

只读复核提出并修正：遮挡背景无当前源行，需分当前点账本/背景surface_id账本；近背景与历史free种子来源不能混成一个后景遮挡推断；角域歧义优先；原点/首可见回波未核实时严格free分支禁用。初稿保留PLAN_DRAFT_01，当前PLAN已修正，定向再审问题闭合。

## 实际变更

本轮只新增本工单evidence、此回传，追加WORKFLOW/REVIEW_LOG。文档包括PLAN、RESEARCH、REPO_AUDIT、DESIGN_REVIEW、唯一验收、数据库原JSON/XML/失败、基线及完整性清单。原算法/GT/模型/源数据/旧证据无改动。

## 逐条验收

| ID | 类型 | 结果 | 证据 |
|---|---|---|---|
| TP01 | planning | PASS | PLAN十项逐句分析，明确空场/人体、新物体/人、同向与非刚体、术语与预判 |
| TP02 | readonly | PASS | REPO_AUDIT、当前TCMS源与冻结结果，未声称新可见性已实现 |
| TP03 | research | PASS | RESEARCH主来源及许可/传感器/前提；Crossref两成功一TLS超时，arXiv原XML成功；访问失败保留 |
| TP04 | planning | PASS | 地图/当前观测分离、两账本、UNKNOWN/失效/能力开关与恢复 |
| TP05 | planning | PASS | 因果架构、源行和地图片ID、帧级降级、最小CPU路线 |
| TP06 | planning | PASS | V0–V5、明日建议协议/反例、分层指标/人工完整性/会话隔离/STOP–GO；非采集授权 |
| TP07 | design review | PASS | 三轮审查、三只读分工、对抗反馈与定向闭合记录；非软件/性能独立验收 |
| TP08 | readonly | PASS | FINAL_CHECK scoped_source_changes为空；当前规划新增和后续记录追加分列，新算法/设备NOT_RUN，效果BLOCKED |

## 未闭合与限制

- V0–V5新实现均未执行，实施需后续实际工单授权。
- 实际传感器/回波与源原点规则、覆盖质量、同场冻结数据、地面高度与动态人体/家具人工GT仍需核实。
- 受控躺下会话证实人体运动，可作前端/卧姿实验，不能算意外跌倒或预警TP。
- 不把外部M-detector/Dynablox/LidPose性能推到本项目；不承诺现成模型/骨架/板端实时。

## 交给独立实施前复核

当前[PLAN](../evidence/2026-10-16_hfus_tcms_02_plan_r1/PLAN.md)，配RESEARCH、REPO_AUDIT、DESIGN_REVIEW、唯一验收及DELIVERY_SHA。建议下一工单仅V0–V2：同场背景冻结→遮挡/重现解释→种子聚类→停止保持；不要一次串完整骨架/HMM宣布成功。


## 2026-10-16 追加：录制与地面支撑目标设计

按用户继续设计录什么/去背景/地面/潜在目标区域，新增[补充方案](../evidence/2026-10-16_hfus_tcms_02_plan_r1/CAPTURE_GROUND_DESIGN_R1.md)，对应原TP02/TP04/TP05/TP06规划深化，未改唯一v1判据。建议同固定布局空场30–60秒、单人连续动作约2–3分钟、遮挡/移动家具反例约1–2分钟，参数冻结后另留出会话；未启动采集。地面RANSAC/受约束拟合+SVD/资格/有效范围、地面上方搜索空间、冻结静态表面、当前新目标与停止/卧地续接两路、低姿/近地保护和分层验收已明确。单平面不外推台阶，不把最大平面当真实地面，不以脚接触地面或离地高度硬切掉躺地人体；未命中和未观测仍UNKNOWN。主线ground/calibration只读核查，不启用GL里程碑或改默认。新增补充独立SHA见CAPTURE_GROUND_BINDING_R1；旧DELIVERY_SHA和旧方案保留。新算法/地面实测/设备/录制NOT_RUN、效果BLOCKED；本补充作者设计，未独立软件验收。技能沿用ponytail/scientific-toolkit；无数据/GT/模型/生产写，无训练部署/Git写。


## 2026-10-17 追加：地面与静态表面联合提取方案分析

- 用户要求“分析一下如何”；仅增量设计/源码只读分析，开始于10月16日，跨日收口，未启动开发或录制。沿用TP01–TP08唯一v1，SHA256 `97c0a2ef10d708dea58d7b3a3253802c3c9818a8f12ab9153d93de51ea8e416f`，不改验收版本或历史判定。状态SUBMITTED，非ACCEPTED。
- 证据：[分析](../evidence/2026-10-16_hfus_tcms_02_analysis_r1/ANALYSIS.md)、[两路只读意见](../evidence/2026-10-16_hfus_tcms_02_analysis_r1/READONLY_REVIEWS.md)、BASELINE/FINAL_CHECK。起始master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a，全非忽略tracked/untracked 13014文件SHA留存；原始dirty树保持，外部并行差异另列。
- 核查结论：总体路线成立；原方案多数边界已写清，实施还需落实冲突点先标记而非先硬删、发现/续接双路、接触家具的有界生长、局部地图冲突、实测停止与缺测预测分列。普通ground入口仍先选最大支持平面，build_snapshot仍先删背景；可复用组件但不能原样串联宣称新逻辑已完成。
- 数据建议仅补强长站/长卧、短时完全遮挡、家具移位后操作者离开，以及留出会话初始化/计分规则；人审确认分割跟踪与全自动人体识别分层。没有新数据/GT写入。
- 本轮增量自验：TP02/TP04/TP05/TP06/TP08 PASS；TP01/TP03/TP07整项重新验收NOT_RUN，原记录保留。本轮有定向作者仓库与Patchwork++摘要核查，M-detector Nature全文访问失败；不冒充完整文献再审或三轮软件独审。新实现/设备/物理/地面实测/采集/部署NOT_RUN，人体语义/分割/事件效果BLOCKED。
- 实际命令：文档/源码读取与定向搜索exit0；基线脚本python -B -W error exit0；结束完整性核对另存FINAL_CHECK。不运行算法、测试、训练或服务；仅分析文档及追加流程记录。
- 技能实际路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`，主作者和design_risks/reuse_audit均已读。两助手只读，主作者为唯一文档写入者，无生产writer。
- 未闭合：双路逻辑和数据效果尚未实施/验证，人工标签和当前物理地面证据不足；不自动派发下一单。范围内源码/配置/旧方案SHA及既有记录原前缀核对见FINAL_CHECK。无Git写/模型切换/驱动网络或设备动作。
