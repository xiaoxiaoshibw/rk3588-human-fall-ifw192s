# 下一阶段地面配平算法设计与采用门 / v1

新增最终阶段设计：[自适应配平正式计划](ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md) / [接口契约](ADAPTIVE_GROUND_LEVELING_CONTRACT.md)。本轮仅规划GL-A～GL-I，经典TLS/SVD/RANSAC不作为原创；重点是quality、家族相关性/consensus、temporal/state/age与安全回退。原I06及下文研究/失败不改、不自动重新投入旧方向，生产范围不扩大。

2026-10-04 当前入口覆盖：用户已授权按现有26°下俯/1.1m重新设计并开发。见[主线计划v3](GROUND_LEVELING_NEXT_STAGE_PLAN_V3.md)/[当前GL-N01唯一表](GLN01_ACCEPTANCE.md)。下方v2/v1设计正文作为历史保留；GL-E01/E02/I06实际软件已完成，不再按“未实施”重做。当前先完成可见名义安装变换，独立物理精度另列，不阻本地开发。

2026-10-04。**DRAFT_READY：设计与联网核查已完成，本轮未实现新算法/试验/部署。** 本文补充[阶段计划](GROUND_LEVELING_NEXT_STAGE_PLAN.md)，算法研究首单为[GL-I06](GLI06_ACCEPTANCE.md)，执行提示[AI_PROMPT_GLI06_CODEX_R1.md](AI_PROMPT_GLI06_CODEX_R1.md)。现场证据GL-E02可同步准备，两个工单不并行写源码。新增研究代码只写新evidence run_root，已审ground/calibration/配置/运行路径保持。

## 1. 算法定位：静态标定、固定变换、在线监测分开

静态标定估计可信地面法向n和偏移d；地面局部坐标只需这两个量与明确的水平参考轴约定。完整世界yaw/地图位置/IMU外参不是额外必需参数，但未测部分不能标verified。标定通过后固定R/t，在线逐帧应用同一变换，并监测可信区域残差与可观测性。不能让在线RANSAC不断改坐标轴来“消掉”机器人/背景变化，也不能把近地人体点一律当成地面删除。

原始点云→有效source/证据资格→独立FIT采样→有约束假设生成→精炼与全FIT支持→完整竞争检查→独立空间/帧验证→物理核对→版本化n/d与R/t→在线固定变换/失效监测。研究在前六环可并行推进；实际标定产物放行必须等输入与物理关卡。

## 2. 复用的基线与当前真实困难

目前`core/ground.py`已具备切平面网格均衡采样(542–568)、固定seed/预算RANSAC与三点分离/面积/方向/高度门(701–763)、TLS协方差特征分解与全FIT重算支持(769–799)、竞争/截断保守拒绝(829–855)、独立区域质量门(866–905)。这些是现有能力，不作为下一阶段“重新开发RANSAC”的工作量。

GL-I05保留了每个合格假设的精炼/拒绝/精确签名合并/未处理账本，ALL/NEAR/BEST_ONLY不同域，链/late/tie与预算缺口有独立oracle。GL-E01确认了原bag/XYZ来源，因此不再把实际几何差异归咎于本地翻X或缺原件。

仍需判别：先验表达与地面身份是否正确；少量随机三点产生的法向/偏移是否在精炼后仍不稳定；现有代表保留/预算使哪些结果保守未决；同一高噪地面与实际多个平面如何在证据层区分。`ground_degenerate`可能汇总抽样退化和先验拒绝，不能据名字直接增采样；“见证NEAR存在distinct”也不是“物理上有两个地面”的证明。

## 3. 拟采用的最小算法路线

| 模块 | 设计与为什么 | 研究/放行约束 |
|---|---|---|
| 输入与采样 | 用获审FIT单frame做既有空间均衡采样，固定source/rows/seed/settings/digest；方向/高度约束在假设进入有效竞争前生效 | 不靠源Z窄带或最大点数平面定义地面；已审0.05/8变体仅显式选择，不改默认 |
| 假设资格 | 保留三点最小分离、三角形面积、法向/高度范围与支持门，显式记录每次拒绝；真实up/height未核时只WHAT_IF | 缺物理参数不是可以由PCA补的空位；先验不符先查表达方向，不翻符号凑成功 |
| 精炼主路线 | 保留一次TLS基线；若有精炼偏差证据，比较统一作用于每个合格seed的有界2/3轮“在同一均衡sampled cloud重选内点→TLS→全FIT重算支持” | 轮数比较不改变精炼域；全FIT直接精炼另variant。每轮查方向/高度/有效点数/退化，记录n/d/成员/支持；资源与不收敛原因分开 |
| 鲁棒尾部处理 | 只有已证混杂尾部使普通TLS有偏时，再比较Huber型加权TLS/IRLS；使用FIT残差尺度诊断，不使用validation来调参数 | 迭代/权重/尺度估计先定版；零尺度回退、有效支持不足拒绝；不能自适应放大距离门让困难数据通过 |
| 候选评分 | 现有全FIT支持数主指标不变；新增截断平方残差和空间覆盖作为诊断/排序对照，避免同支持数下只看一次随机结果 | 评分在相同完整FIT域计算，不只看内点；小J/第一名不删除合格见证，不替代NEAR全部两两检查 |
| 竞争完整性 | 先比较冻结fitter与GL-I05全合格假设精炼路线；精确签名去重保持关系，多重性在trace保存；分别输出ALL/NEAR/BEST_ONLY | 不用best-only、相似传递、移动代表洗掉链两端。原有10°/0.05m/.8判据不悄改；新定义必须另版本审查 |
| 空间诊断 | 按既定source空间cell/区域看局部平面、支持分布、未截断残差/覆盖，定位墙/桌/阶/反射或单平面不适用 | 初期只诊断，不把局部分区自动标签当独立地面身份，也不跨帧pool FIT |
| 多帧稳定/在线状态 | 离线各帧可分别拟合作对照，报告n/d分布和固定标定对后续帧残差；在线仍冻结一份R/t | 缺可见地面、持续异常或标定版本改变走unknown/失效，不能以前帧模型给无观测帧背书 |

截断平方诊断量采用`J=mean(min(r_i², τ²))`，r_i为同一完整FIT的有符号正交残差；τ沿本实验冻结设置。它提供“支持数相同但误差不同”的信息，并非物理概率或完整搜索证明。保留支持数/P95/RMS/覆盖/NEAR关系各项，不堆成不可解释的综合分数。

`best_support=max(所有合格精炼见证的support_count)`，NEAR仍是support≥0.8×该值，保留所有最高支持ties。J只辅助诊断或同支持排序，不能把低支持但低J的平面改称best来改变NEAR域。

每variant预先固定K=1/2/3的算法轮数。K轮执行完是处理完成，不等于总LO资源耗尽；若成员尚不稳定，保存末轮/最后有效见证及`refinement_nonconverged`，作为额外质量不确定性保持unresolved（不是丢弃seed后closed）。两周期/振荡单列；后轮越过先验或退化不能静默退回前轮“成功”。总LO预算使尚有seed/轮未执行，则明确unprocessed/resource gap，也必须unresolved。两类不同计数/原因不得混为一种预算错误。

局部优化借鉴LO-RANSAC思想，但不照搬“只优化best-so-far、提前停止”的完整策略：本项目已见序列契约要求所有合格假设有处理事件，额外LO预算也必须记账。任何研究closed仍仅指有限已见序列，不能直接写`ground.status=valid`。

## 4. 为什么选这些路线：一手资料与取舍

2026-10-04重新核查了一手资料。PCL约束平面接口在模型资格中限制法向与用户轴的夹角；该轴仍须有本项目来源，API不提供重力真值。[PCL官方约束平面](https://pointclouds.org/documentation/classpcl_1_1_sample_consensus_model_perpendicular_plane.html)

LO+论文讨论局部优化、截断平方评分和精炼点数上限，并明确局部优化存在时间/质量取舍。这里借鉴模块和实验设计，不把其图像几何结果当IFW192S性能。[BMVC官方全文：Fixing the Locally Optimized RANSAC](https://www.bmva-archive.org.uk/bmvc/2012/BMVC/paper095/paper095.pdf)

PCL正式提供RANSAC、MSAC、MLESAC、PROSAC等估计器。首选基线+TLS局部优化+MSAC型诊断量；MLESAC需要额外噪声概率模型，PROSAC需要可信排序，目前没有证据证明是本项目首要瓶颈，暂不引入。[PCL sample_consensus](https://pointclouds.org/documentation/group__sample__consensus.html)，[MSAC官方类说明](https://pointclouds.org/documentation/classpcl_1_1_m_estimator_sample_consensus.html)

Patchwork++提供区域与多层地面处理、时序回补、反射噪声模块。用作单平面前提失败时的分区诊断/备选来源；其SemanticKITTI实验和传感器参数不是本项目结论。对下视IFW192S的FOV/高度/坐标/强度与近地人体保留须重新验证，先不引入整套C++/Python库或自动时序回补。[原论文](https://arxiv.org/abs/2207.11919v2)，[作者实现与参数说明](https://github.com/url-kaist/patchwork-plusplus/blob/master/USAGE.md)

这些文献支持“候选方法值得比较”，最终采用与不采用由本项目预先固定的实验决定。原LO/PROSAC作者PDF在本次web open失败；已读BMVC LO+全文、PCL官方说明和Patchwork++摘要/作者资料，未冒称全部原论文全文复现。arXiv API两篇原始返回保存在planning evidence/01_arxiv_raw.xml，数据库/版本索引另存。

## 5. 并行算法研究：GL-I06，物理缺失不阻离线诊断

只在新run_root执行。先R0“关卡拒绝账本+同raw序列竞争shadow”，后R1“一次TLS vs 2/3轮有界TLS”，最后才按根因需要R2“鲁棒权重/评分/局部区域诊断”。每轮单因素，独立variant_id，单writer，不把方法名拼成大架构。

两类对照明确：R0保持同source/selector/settings/seed/sampled rows/raw sequence，可证明处理完整性与旧拒绝来源；R1/R2允许精炼参数改变，冻结初始raw假设序列，记录新旧精炼差异，不假称最终W完全相同。每种W分别由独立oracle判关系，用已知合成GT另评估法向/偏移误差，oracle不代表地面真值。

预先固定实验矩阵：clean/8mm/35mm噪声；墙多于地面、平行桌面与地面、阶/双平面；非均匀密度/距离分布、缺点/共线/窄带；0/4/8°全相似正例、0/6/12°非传递相似链、中间best、ties与.8边界；晚强best/晚distinct；成员振荡/两周期/后轮越先验；candidate/refine/LO/trace/迭代预算0/边界/耗尽；至少3seed与顺序置换；同内容复跑与source/settings/caller变化。真实89frames/四box只同协议分析/WHAT_IF，不挑成功seed、不删困难帧、不按新残差筛validation。

独立验证使用FIT之外的**至少三个不同frame_group**（每组再说明空间分布），各组相互不同且不等于FIT。同帧划三块不能满足现有constrained接口；空间/时间独立性两项都记录。真实数据缺地面身份时报告观察误差与限制；已有源索引/框不能代替人工/现场标签。

方法选择样本与最终验收holdout分开：当前已观察89帧用于开发诊断，不能再称“从未使用的最终物理holdout”。最终方案/参数冻结后，用预先封存且未参与选择的样本或后续获准取得的独立数据验收。若看过holdout失败后改方法，记录该轮曝光并用新的独立证据复验；没有条件时保留泛化/物理未验证，不让同一holdout变成调参集。

记录：每stage拒绝计数与事件；完整支持/未截断RMS/P95与最差区域；已知GT n/d误差；NEAR关系与误闭合/额外未决；法向/d跨seed和frame稳定性；sampling/raw/refine/LO/decision/serialization成本、至少3重复、独立内存峰值。桌面算法统计与RK3588实际新增耗时分列，不能混为在线速率。

## 6. 算法采用门与停止条件

必须同时满足：独立同序列关系oracle无误闭合；所有预算/未知保持；单平面/弱distinct正例可闭合；独立区域最差误差与多seed稳定性无已知退化；至少一项预登记主要指标有可重复收益；成本与内存有界且透明。若需改变竞争域/阈值/评分放行语义，先开新契约版本与反例审查，不在旧表下偷偷扩大PASS。

没有收益可“保留基线、不采用”；算法有效但物理资料缺失可“研究采用、物理BLOCKED”；基线/新方法均在独立区域失败，优先报告单平面前提/身份/测量问题。出现真正竞争，不强行造唯一地面。获审算法研究最多推荐新的candidate-only软件接入单，不能直接部署或启用physical flags。

条件分支可正常收口：R0未发现精炼偏差时，记录“条件门核查PASS；2/3轮实验NOT_RUN（门未触发）；保留基线”，由独审确认该条件不适用，不为涂全表PASS额外实施。IRLS同理。必要无条件检查未跑仍不能PASS。

## 7. 遇到困难时的联网闭环

每次先保存最小反例与违反ID，再以具体根因检索官方源码/文档和原论文；记录URL、访问日期、版本/commit、适用前提与失败访问。提出1–2个候选解释或方法，与冻结基线做同输入对照，结果写采用/否定/需补实验。资料中的数据集成绩/默认高度/距离阈值不移植成本项目门槛；联网不能替代缺失的现场测量。只有新的失败证据/范围变化才再查或再测，不为形式重复整套研究。
