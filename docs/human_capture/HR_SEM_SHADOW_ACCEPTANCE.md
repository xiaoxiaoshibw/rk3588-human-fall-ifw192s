# HR-SEM-SHADOW 唯一验收表 v1

制定：2026-10-08（Asia/Shanghai）。状态：**DRAFT_READY_FOR_DISPATCH**；本次仅制定。用户转发并明确开工后，仅作为 [HR-SEM-SHADOW](tickets/HR-SEM-SHADOW.md) 的验收表。初始状态全部NOT_RUN；不得改变W03/HR-RET-V2历史判定。

本单验证冻结语义原型，优化目标与流程完成分别判定。目标不达标必须记录FAIL/BLOCKED，不靠报告齐全改成算法PASS。

## 统一计数与标签规则

- 输入帧总数：244/271/281/195，空场285；无簇/误判/UNKNOWN帧均保留在会话统计。删除/无效源row另记，不可重复或丢失映射。
- HUMAN证据帧、旧联合判定绿/紫/灰、原track-confirmed帧、离线参照确认帧四种指标分开。
- 精确“是人”评估须有可追溯人工PERSON/STATIC_OBJECT/MIXED/UNKNOWN标签；自动ROI关联只输出代理指标。人工GT缺失时对应指标BLOCKED，不擅自填准确率、假阳性率或95%通过。
- 每会话人体识别目标分别判定，不合并平均遮住难段。正式目标：有真实人体结构证据的帧数 / 原始会话总帧数 ≥95%；HUMAN必须对应人工确认的人体所在簇/成员，而非帧中任意家具簇。全部帧需人工确认身份或经人工批准、可追溯的连续身份映射；尚未确认的帧不得算命中，也不能从分母删去。GT覆盖未闭合时整项BLOCKED，仅公开部分已标注指标；全覆盖后无簇/错误/UNKNOWN/MIXED帧均不算HUMAN命中。
- 空场目标：全部285帧的全部实际候选与结构负例 HUMAN_EVIDENCE=0；UNKNOWN允许，但分母、比例与原因公开。旧已确认静态负例的HUMAN_EVIDENCE亦应为0。GT不明的家具簇保持UNKNOWN，不能强称误报。
- 固定v1先跑；不授权门槛扫描/参数搜索。新方案若失败，报告设计与待验证项，不覆盖发现轮。

## 逐项表

| ID | 要求 | 检查与证据 | PASS条件 / FAIL或BLOCKED情形 | 初始状态 |
|---|---|---|---|---|
| SEM-01 | 版本与输入基线 | branch/HEAD、dirty、tracked+untracked SHA；源meta/bin、TLS/配准诊断、参数、代码SHA | 绑定齐全且运行前后无意外漂移；禁止按mtime换输入 | NOT_RUN |
| SEM-02 | 冻结原型可复用 | v1阈值含w_min=.06；函数原文与适配器差异、24次抽样/12空场簇帧对账 | 冻结数学/参数不变，既有抽样结果一致；有差异先FAIL工具 | NOT_RUN |
| SEM-03 | 全帧与同成员整簇 | 逐帧/逐簇索引，frame ordinal/seq/stamp、source row、成员守恒自检 | 五段全部帧处理；旧新消费同一真实簇全点集；无簇帧及小簇不遗漏 | NOT_RUN |
| SEM-04 | 三值、结构、无点纪律 | schema/原因码、60–199/200–399/≥400分档；无点/遮挡/冲突检查 | HUMAN/OBJECT/UNKNOWN输出完整；低支撑不补头/关节；无效源row不提供正结构证据，影响独立披露 | NOT_RUN |
| SEM-05 | 中央普通静立识别 | 114205全帧REF影子，旧/新分布、人工GT覆盖及全帧代理指标 | 按统一规则HUMAN≥95%总帧；GT身份覆盖未闭合→BLOCKED，闭合后达不到→FAIL；不可当正式V2结果 | NOT_RUN |
| SEM-06 | 右桌前识别/粘连 | 114254全帧REF影子，整簇与家具混入、人工GT | 同SEM-05；MIXED不强判真人；诊断不掩盖gate WARN | NOT_RUN |
| SEM-07 | 左隔板旁识别 | 114340全帧离线V2，语义、上游删除与人工GT | 按统一规则HUMAN≥95%总帧；原区域91.9%不直接当真人保留率；GT未闭合→BLOCKED | NOT_RUN |
| SEM-08 | 举左手识别与头部边界 | 114422全帧离线V2，ARM/HEAD/LEGS/TORSO与原因 | 按统一规则HUMAN≥95%总帧；HEAD未检出如实invalid；不能为了票数伪造头；GT未闭合→BLOCKED | NOT_RUN |
| SEM-09 | 新空场负例 | 114819全部285帧：V2残留 + 未删背景的工作空间全部结构候选，公开两个分母 | 两口径HUMAN=0；非零→FAIL；UNKNOWN/小簇不能略去 | NOT_RUN |
| SEM-10 | 旧负例与对抗覆盖 | WD01、箱子、格栅、远场已有静态标签/归属；索引与实际覆盖 | 已确认静态样本HUMAN=0；未覆盖资产NOT_RUN，GT不足BLOCKED；墙家具巨簇不能代表全部对抗物 | NOT_RUN |
| SEM-11 | 逐实际帧3/5审计 | 原Tracker与独立参照票逐帧表；同帧多簇、断帧、轨道拆合与身份不明案例 | 参照每身份每帧≤1票、最近5实际帧含缺失、≥3票+原min_age；无法关联→UNKNOWN/BLOCKED；原Tracker缺陷完整披露，生产零修改 | NOT_RUN |
| SEM-12 | 隔板旁边缘/GT可审阅 | 原185点线索、原5帧cleanup各1点 + 本轮全帧发现清单；查看入口与sidecar | 会话/帧/row可定位且可人工填标签；不得预造source:human；工具完成可PASS，点身份另列BLOCKED | NOT_RUN |
| SEM-13 | 三组证据与指标不偷换 | 人体受益、静态负例、UNKNOWN/粘连/泄漏代价；每段分开表 | 分母明确、不以ROI代理冒充GT，不剔掉难帧，不以确认票冒充语义正确；完整记录成功/失败 | NOT_RUN |
| SEM-14 | 确定性与必要回归 | 同输入两遍结果digest；适配器自检；用到的既有相关JS套件；命令/exit记录 | 输出digest一致且自检/相关回归exit0；不为文档改动编造测试，既有总数不替代SEM行 | NOT_RUN |
| SEM-15 | 保护资产与边界 | 原生产/捕获/旧证据/阈值SHA；目录新增与return前缀 | 只新增本轮离线工具/证据与本单return；不签artifact、不启旗标、不改Tracker/聚类/保留/配准/Fall、不启ML/部署采集 | NOT_RUN |
| SEM-16 | 可复审交付与停止 | 回传模板、逐ID自验、日志/GT缺口/下一步接入设计 | 执行者实读ponytail并写路径；报告SUBMITTED等状态，未自封ACCEPTED；设计后停写，无自动后续工单 | NOT_RUN |

## 本单之外

| 项目 | 本单状态与原因 |
|---|---|
| registration算法/对应集/调度/gate更改 | NOT_RUN；需独立工单与设计评审 |
| artifact签发/重签/安装、loader VALID/生产旗标 | NOT_RUN；不在本单范围，质量PASS不可当VALID |
| T01/T02/I01生产补丁、Tracker/Fall逻辑变更 | NOT_RUN；本单只记录关联/无效点风险 |
| 多人物、弯腰/坐蹲/卧、真实跌倒、关节精度 | NOT_RUN/BLOCKED；现有静立数据不支持这些结论 |
| 板端/物理/部署/采集/网络/驱动/ML | NOT_RUN；本单是PC侧离线试验 |
| 独立复审与生产切换 | NOT_RUN；本单执行者只提交可审查证据与设计 |

执行时在**新的本轮证据/return**逐ID记录PASS/FAIL/NOT_RUN/BLOCKED及原因，不覆盖本表初始状态或历史验收。若需修改验收标准，先提出修订理由与新版本，不能为通过自行下调95%/修改分母。
