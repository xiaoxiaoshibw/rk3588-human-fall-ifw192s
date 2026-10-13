# 工单 HR-SEM-SHADOW：静立/举臂语义判定，全帧整簇离线验证

- 版本：v1；制定日期：2026-10-08（Asia/Shanghai）。
- 状态：**DRAFT_READY_FOR_DISPATCH**。本聊天用户只要求制定工单；本次不启动算法实施。用户将本文连同开工指令转发给执行 Codex 后，才执行下述离线范围；不把文档登记当作生产授权。
- 执行者：用户指定的 Codex；一个 writer。无需调用 OpenCode、改模型或派出子代理；如需独立复审，另行安排。
- 本单唯一验收表：[HR_SEM_SHADOW_ACCEPTANCE.md v1](../HR_SEM_SHADOW_ACCEPTANCE.md)。不复制语义草案 H01–H08 为第二张现行表，不替换 W03 的 T37/T38 或 HR-RET-V2 的 V2 表。
- 范围：冻结 S-A+ v1 的真实整簇、全帧离线旁路与判定/确认审计；形成生产接入设计。**本单不切换生产算法，也不自动调参数。**

## 1. 目标与已知问题

新数据证明“前景点保留”与“认成人”是两个环节：114422 举左手在 v2 离线区域统计中保留100%，但0/195帧带确认轨道；旧证据规则主要把它判为 SOLID_UNIFORM。114340隔板旁有230/281帧确认轨道，区域保留91.92%；参考删除点集中在家具侧边缘，身份未标注，不能直接称为人体丢失8%。

已有 S-A+ v1 冻结原型在四段新人体各抽三帧、原区域/参考保留区域的24次相关判定中均输出 HUMAN_EVIDENCE；新空场12个簇帧样本（约4个分量×3帧）0 HUMAN。它仍缺真实整簇、全序列、粘连/遮挡与稳定确认验证；举臂 HEAD 未检出。

本单要回答：**真实候选簇全点集上，结构证据能否改善静立/举手判定，且不把家具判成人？** 验证结果支持后续优化与接入决策；没有人工GT的结果只作诊断。

## 2. 开工前必读

1. 仓库根 `AGENTS.md`，以及 `docs/human_capture/README.md`；不得沿 HF/GL 流程启动人体捕获支线工作。
2. 本工单及唯一验收表，记录两者 SHA；实读本机 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`，返回实际路径。路径失效时先查本机 skill catalog，不编造“已读取”。
3. `docs/human_capture/HUMAN_SEMANTIC_CLASSIFICATION_DRAFT.md`、`HUMAN_RECOGNITION_REVIEW_AND_PLAN.md`。
4. `evidence/2026-10-08_human_semantic_sa_r2/{README.md,semantic_sa_review.js,review_results.json}`：v1 阈值含 `w_min=0.06`，早期r1没有此项，不可混用。
5. `evidence/2026-10-08_new_static_sessions_r1/{README.md,leveling_results.json,registration_results.json,retention_results.json,region_audit.json,integrity.json}`。
6. `evidence/2026-10-08_semantic_new_holdout_r1/{README.md,results.json,frozen_probe.js}`。
7. `evidence/2026-10-07_hrw03_r40_research_r1/07_research_and_minimal_plan_r2.md` 与 `evidence/2026-10-08_patches_p1p2p3/README.md`：了解同帧多簇复用track、断帧票不老化、无效XYZ变换问题；**本单只审计，不落地这些生产补丁**。

上述均相对于 `docs/human_capture/`。开始前核对当前树与实际文件，不信旧文档中的“inc2待做/板端不可达”等历史状态。读取相关核心函数与调用者，禁止只从旧报告复制结论。

## 3. 固定输入与坐标口径

工作区：`D:/Code/ldiar`。原始会话位于 `captures/remote/`，只读。空场参考：`cap_20261008_114819`，285帧。

| 会话 | 帧数 | 离线配平 job（上一轮 evidence/leveling 下） | 配准质量 | 本单语义输入分支 |
|---|---:|---|---|---|
| cap_20261008_114205 中央静立 | 244 | 80a4bd6fe3a4476fa099b053d74de8be | WARN，49.38% | REF影子诊断；不得运行正式V2 |
| cap_20261008_114254 右桌前 | 271 | abe747de448a4974ad9e7a6e1c70bac4 | WARN，49.51% | REF影子诊断；不得运行正式V2 |
| cap_20261008_114340 左隔板旁 | 281 | 9d389dc38cb84343b66f97db2198dbbb | PASS，52.85% | V2函数层离线试验 |
| cap_20261008_114422 中央举左手 | 195 | 24a7ba629d904f63af03ecdaadb9a9ec | PASS，50.88% | V2函数层离线试验 |
| cap_20261008_114819 空场 | 285 | 6e87c6e4146f48ba84e24c801820e5e1 | 自参考，不是跨会话PASS证明 | identity-reference V2残留 + 原始工作空间结构负例 |

配平 job 的真实目录是 `docs/human_capture/evidence/2026-10-08_new_static_sessions_r1/leveling/<job>/`，**不是** `captures/leveled/`。配准矩阵来自该轮 `registration_results.json` / 每段 `*_registration_diagnostic.json`；这些仅为诊断数据，未创建loader artifact。使用前核对会话meta/bin、TLS变换、report/manifest与代码绑定。

固定沿用上一轮配平/配准/去噪/前景/cleanup/聚类。不得重估ICP挑优解或按mtime换配平job。新pair尚无VALID artifact；质量PASS允许本单离线函数试验，不授权绕过 `fusionKeys` 生产状态门。

## 4. 允许的修改与不变量

允许在新证据轮中新增最少的纯函数语义适配器、全帧harness、必要自检、结果表与审阅页面；写入本单return。语义适配器可提取冻结函数为可调用模块，但必须保留数学/参数，记录原文件与提取函数SHA，并与既有抽样结果对账。

只读：`pc_apps/human_replay/`生产代码、`src/`、`webui/`、console可执行文件、`captures/`、既有证据；不得创建生产调用点或隐藏旗标。冻结 `0.65/0.85`、参考occ≥0.5、匹配0.12m、体素0.15/0.12、工作空间0.10–2.50、Tracker3/5、0.75m、lost_max=8、EMA0.35及Fall逻辑。S-A+ v1参数亦先冻结。

不得启动ML/W04–W09、采集、板端连接、部署、网络/驱动修改、artifact签发/重签/安装、生产旗标、commit/push/reset/checkout/clean。不得复制旧worker身份或自动换成OpenCode执行。

## 5. 执行顺序

### A. 建立可复现基线

- 建立新的 `evidence/<执行日期>_hrsemshadow_r<N>/`（日期按Asia/Shanghai，旧轮只读）；记录branch/HEAD、完整 tracked+untracked SHA、dirty差异。忽略的本单输入与冻结资产另外绑定SHA；本轮持续写入的输出不作为旧资产误报。
- 建立本单命令/退出码日志，Python使用 `-B -W error`，Windows可加 `-X utf8`；Node记录版本。复用已有依赖，避免为harness新增框架。
- 在相同输入重现上一轮ROI诊断与冻结抽样；工具对账不符，先修harness，不能通过调参数掩盖。
- 检查原始无效XYZ及变换后的虚点来源，保留原始row映射并单列影响；不得把placeholder当结构证据，也不得把本单输入审计当生产I01补丁已落地。

### B. 全帧真实整簇并存对照

- 每个会话跑全部原始帧，不仅首/中/末；分支按§3固定。旧规则与语义规则必须消费**同一帧、同一cleanup后的簇成员**。
- 对全部实际候选簇（沿原聚类门，至少原human_n_min=60点）提取全成员点；不要先用旧“是人”硬门过滤语义输入，不以手工圆柱裁出“干净人体”替代真实簇。
- v1低于400点输出UNKNOWN/POINTS_LOW；60–199、200–399、≥400各档全部计数，不悄悄丢弃小簇。
- 每簇输出原始frame ordinal/seq/stamp、簇成员源row ID、质心/范围/点数、旧label/joint/证据、三值semantic、HEAD/TORSO/LEGS/ARM等结构标志及数值原因。
- 对前景保留后的真实候选簇评估分类；同时披露上游已删点/无簇帧。不得靠新语义给已删点补人体，或把未成簇帧从会话总帧分母中删掉。

### C. 正负例、GT与按帧确认审计

- 正例是四段用户确认全程静立/举手的会话，但**存在真人不等于每个簇都是PERSON**。圆柱重叠只能辅助索引；记录 `PROVISIONAL`，不可写 `source:"human"` 冒充人工GT。
- 所有空场帧均可作为无人场景负例，分别扫描V2残留簇与未删背景的工作空间结构簇。旧WD01家具、箱子、格栅、远场负例复用已有标签/归属证据；看不清、人与物混合记MIXED/UNKNOWN。
- 交付可供人工复核的sidecar与查看入口：错误/UNKNOWN、合簇/拆簇、异常票、隔板旁边缘与cleanup删除点优先；每项有会话/帧/成员row定位。现有185点和5帧各1点记录只作排查线索，不预填真人/家具结论。
- 单独计算离线3/5参照票：每个候选身份、每个实际帧至多一票；窗口严格按最近5个实际帧，缺失帧占窗口，至少3票且达到原min_age。关联不确定则UNKNOWN/BLOCKED，不靠最近质心强行确定真人身份。
- 同时保留原Tracker输出，对照记录碰撞复用、缺失帧、轨道拆合。参照票是实验审计，不写回生产Tracker，不修改确认/Fall判据。

### D. 形成优化结论与接入设计后停写

- 按每会话、每簇及每帧报告HUMAN/OBJECT/UNKNOWN，旧新规则差异、上游保留、粗候选、瞬时联合判定、原track-confirmed与离线参照确认；这些概念分别计数。
- 两遍同输入应得到相同结果digest（剔除时间戳/路径等运行元数据），保存真实日志和失败。
- 冻结v1未达目标：保留FAIL/BLOCKED，提交基于训练/校准资料的最小修订设计与数据划分，**本单不自动试阈值或修改聚类/背景/Tracker**。新会话已经被抽样观察过，不能称为全盲独立测试集。
- 如v1表现良好，提交可审查的生产接入设计（接口、三值票源、默认关与回退、GT/独立复审依赖、源码触点），但不实施调用点。
- 若人工GT不足，继续完成适配器、全帧对照、空场负例、审阅数据、票审计与报告；对应人体验收标BLOCKED并写明所需标签，不能把整个任务停成“等用户标注”。

## 6. 交付与停止条件

交付：最少可运行脚本/语义适配器及必要自检；输入源码/参数SHA与固定输入清单；全帧逐簇JSONL/CSV或等价索引；baseline/新规则对照摘要；原track与按帧参照票；人工审阅sidecar与入口；例图/关键帧；唯一表逐ID自验；源码/输入/旧证据完整性；下一步设计。

返回追加 `docs/human_capture/returns/HR-SEM-SHADOW.md`，遵循 `docs/human_fall/RETURN_TEMPLATE.md` 的字段，不据此进入HF/GL流程；状态SUBMITTED或REWORK_REQUIRED/BLOCKED分项，不自行宣告ACCEPTED。最后停止在“证据与设计可复审”，不继续生产接入、配准治理或下一个工单。

停止红线：输入SHA不一致、坐标/成员映射不可验证、基线工具对账不符、需要修改生产冻结项才继续、需要伪造GT。先保留故障证据与定位；能独立完成的范围继续，依赖项具体标BLOCKED。
