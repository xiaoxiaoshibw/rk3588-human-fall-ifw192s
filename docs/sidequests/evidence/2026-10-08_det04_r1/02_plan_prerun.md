# DET-04 同扫描背景删除与机制归因预注册（v1，2026-10-08）

用户本轮指令为唯一授权。独立 sidequest；Codex 为唯一 writer。工作树 `C:/Users/30680/.codex/worktrees/human-detector-models/ldiar`，分支 `codex/human-detector-models`，HEAD `cfbb80c57508be1a0435fdb92260f698dc763934`。主树 `D:/Code/ldiar` 只读；不启动 HF/GL/HC/HR/ML，不 commit/push/reset/checkout/clean、部署、采集、标注或修改上游/权重/历史证据。

唯一验收：[DET04_ACCEPTANCE.md v1](DET04_ACCEPTANCE.md)。新证据 `evidence/2026-10-08_det04_r1/`；回传 append `returns/DET-04.md`。先完成指定资料全文阅读及 00_baseline，再写本计划/验收表，再实现，再执行。baseline 包含当前 DET-03 未提交文件、Git 跟踪/未跟踪/忽略文件 SHA；消费资产继续使用 DET-03 的原 3211 条路径，当前 SHA 全部匹配。ponytail full 实际读取 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`；当前工具目录没有独立 skill API，按文件技能加载规则读取。

## 实施前 artifact 审计与解释限制

先审计 det03_representative_r2、det03_all_r1、det03_attribution_r1、det03_negative_controls_r1 的 config/rows/trace/pillars。baseline/context_points/context_pillars、所有剂量/负帧/空场前向复用，禁止重跑。同扫描 outside_zero 两变体目前没有对应 artifact；只有这 8 次新前向允许执行。

源码 `context_cloud` 是用 C/E 外围源 ID 决策选取 **B 的点值**，输出仍来自 B，同序；不是把空场 C/E 的 XYZI 注入 B。必须逐帧用存档 input/ID SHA 验证此事实。C/E 中空场模板/配准参与删除决策，WARN 仍保留。用户提出的“高分保持则外来内容主导”作为待检验条件保留，但若输入审计确认没有外来点值，不能把高分保持归因于外来点值污染，应报告删除形状/地面/残余上下文差异；此解释边界先于本轮结果声明，不改 DET-03 分类头/采样/yaw 既有起点。

## H-A：同扫描背景删除

固定 215540/215607/215623/215643 的 32/33/33/28 帧，B_workspace、first32（不结合 z_rank32）。冻结键完全复用 DET-03：半径 0.55m，配平 z 在 [0.05,2.30]m 圆柱内实际 B 点所触及的 voxel 键；不是新几何保护圈。冻结这些柱完整 32×4 张量、坐标、counts 及源 ID。

1. outside_zero：其余柱 counts 置零。
2. outside_zero_ground_kept：同上，额外保留圆柱外 **柱内全部有效点配平 z 在 [-0.15,0.30]m（含端点）** 的整柱，first32/完整柱输入不变。判定使用冻结 TLS prepared 当前扫描坐标，model z=-1.73 仅用于原模型输入。整柱条件防止把带有墙/家具高点的混合柱当纯近地面柱。范围先声明、只运行一次、不调阈值。

counts=0 的完整审计表保存；上游 encoder 有除 counts，零柱不得送入，否则会 NaN。前向仅发送非零柱，让被删位置的 scatter 为严格零。独立计算原 B encoder canvas，逐值断言保留柱编码相同、删除位置严格零；不改 encoder 算法、权重或门。此实现等价于空柱不存在，不把带 BN 偏置的“零特征柱”冒充背景删除。

local=种子 0.55m 邻域原始 anchor 分；containing=解码框包含种子的原始分；final=最终位置框分；global raw/final 行人最大分别列出。已有 B/C/E base、context_points、context_pillars 同表。额外报告保留/删除/地面柱数和输入/局部编码 SHA。

预声明数值归因：以 local 为主、containing/final 为辅助；距 B ≤0.02 称 B-like，距 C/E context_pillars 闭区间 ≤0.02 称 C/E-like；若同时满足报告不可分。B 与 C/E 本身差 ≤0.04 时不作二分因果结论。其他结果为中间/更低/反向，不强塞假说。ground_kept 与 outside_zero 差绝对值 >0.02 单列地面上下文效应。分会话判断，不投票宣布普适主因。高分保持削弱“背景存在性充分解释”；C/E-like 支持背景存在性但不排除删除结构；地面分歧支持本带整柱的上下文贡献。8 次全部保留。

## H-B：剂量—响应，零新前向

读取 det03_all_r1_rows.jsonl 的全部 506 配对；head_delta=zrank local−base local。逐会话×B/E 分层，报告 n、范围、Pearson、平均秩 Spearman 描述性相关；不计算 p 值/置信区间，不把连续帧当独立样本。

主剂量：原输入圆柱内点按原模型体素分组，圆柱内 >32 点的柱数；另列圆柱相交整柱 input_counts>32（两口径不能混用）和存档选入 1.5–1.8m 高度带的点数增益。每帧输入 SHA、7 带 before/base/zrank 均保留；重建柱计数仅 CPU 预处理，不网络前向。恒定变量相关为 null 并记原因。负相关/弱相关/恒定同样交付；相关不是人体特征的因果证明。

## H-C：负收益帧解剖，零新前向

按 local head_delta<0 选择 215643：B=3,28；E=7,11,12,17,37，严格核对 2/5。使用现有 trace/pillars，重建相同 first32/z_rank32 选点并逐值比对已有局部柱 tensor/counts。逐柱原点数/圆柱点数、选点 7 带、z 值、源 prepared ID 与原始 global row ID 保存。已有 trace 的完整 local anchor 集合逐 anchor 输出基线/覆盖分、delta、赢家迁移、decode 包含/候选集合变化；全场未存 anchor 不伪称完整变化集合。

覆盖判定：带占用数/1.5–1.8m/顶高全部无增加才称“代理覆盖未改善”；有改善却 head 下降称“覆盖改善仍在具体 anchor 负响应”，列赢家及最负 anchor。代理不等于人体 GT，也不能证明具体生理解剖原因；不执行新消融。

## H-D：空场 FP anchor 解剖，零新前向

empty_17/35/53 z_rank32 全场 raw 行人最大 anchor，从完整存档头校验 ID/分；与四固定真人帧 B zrank 的 local 赢家并列。记录 anchor/decoded/分/最终去向，源 prepared/global row ID、整柱计数、full 与选入 z 带、first32 对照。

“支撑柱”预定义为代码计算图允许的结构感受野占用柱：backbone 三层 block 的卷积/stride 与 neck 非重叠转置卷积反推输入 lattice 区间（最深路径147×147柱，头位置取每4格向下整除）；另列 decoded footprint 内柱。该集合是潜在输入支持，不是 saliency/因果重要性。用全部 B/empty 柱重新体素化但不前向。空场没有人体 GT，只称已确认无人模板的行人响应；单模板留帧，不报误报率。

## 固定条件、失败与收尾

所有实验同原0.16×0.16×4、32点、模型范围/权重、强度/1023、z−1.73、score0.1/top100/NMS0.01/max50；没有最优组合。python -B -W error 运行现有 test_experiment.py，并加删除/冻结/边界/非法 counts 的必要回归。完整失败日志与新 artifacts 不覆盖。rows/config/code diff/index/逐文件 SHA；18 完整性检查以本轮基线为准，历史 DET-03 忽略数组也冻结；新增读取资产单列绑定。

执行 PASS 不等于识别可用；状态 SUBMITTED、不自行 ACCEPTED。E03/G01 仍 BLOCKED，L01/D01 NOT_RUN。收尾给三项需用户分别授权的建议：(a) 人体点 GT 后外围固定、仅纯人体柱覆盖，指标含人位/最近竞争位边距与 GT 相对排名；(b) 已标定强度/z、同传感器权重适配；(c) GPU/原生 ATen 等价。可写 (a) 设计，不执行标注。
