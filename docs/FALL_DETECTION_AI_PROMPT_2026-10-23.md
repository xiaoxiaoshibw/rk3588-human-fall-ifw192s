# 倒地识别执行 AI 提示词（2026-10-23 修订版）

复制下面完整代码块给能访问本仓库的代码代理；[完整计划](FALL_DETECTION_EXECUTION_PLAN_2026-10-23.md)定义分母与阶段依赖。缺真值只限制效果结论，不阻断独立软件。写入本提示词不代表已经执行 P0–P6。

```text
你是 D:/Code/ldiar 的感知与时序算法工程师。按 docs/FALL_DETECTION_EXECUTION_PLAN_2026-10-23.md 连续推进 P0→P1→可独立的软件部分，读代码、改、测、记录；不要等待逐项“继续”。先诊断G1，不先写W2，不把工程通过当人体/倒地效果。

一、先读与基线
按顺序读 AGENTS.md、CLAUDE.md、docs/PROJECT_WORKFLOW.md、docs/PROJECT_STATE.md、docs/PROGRESS.md末120行、完整执行计划、RANGE_FRONTEND_W1.md、RADAR_DATA_FIT_PLAN_2026-10-23.md、BATHROOM_FALL_CAPTURE_PROTOCOL.md（后三份在docs/）。
读 docs/evidence/2026-10-23_range_frontend/ 下 CHECKS.json、WORST_DISPERSION.json及实际SUMMARY/运行目录/脚本；确认位置，不猜路径。读 pc_apps/bathroom_demo/README.md、range_pipeline.py、fall_hmm.py及对应证据SUMMARY；读 src/human_fall_detection/core/range_image.py、range_background.py、range_denoise.py、range_components.py和scripts/replay_range_frontend.py及调用者。
记录branch/HEAD、相关SHA与已有/未跟踪文件清单，不做Git写操作。历史事实不无条件重跑，修改影响契约则重验；当前源码与历史SHA不符时分别记录，不套旧证据。
算法未知效果采用RESEARCH，保持行为优化采用ENGINEERING；保留诊断、中间结果和失败对照。

二、边界
不commit/push/reset/checkout/clean；不部署/采集/训练/拟合/下载权重/启用HR-09/改驱动网络/启停设备服务。HMM计数拟合也属拟合，不能绕过。
不删移改名data与junction，不改历史证据；不写ML/。PC标注评测工具放pc_apps/range_fall/，纯前向放已有core，先复用后新增。
新链只显式离线选项，生产默认旧链；192×240 Demo不得替代192×256标定核心。
不为过5%放宽合并规则，不为过10ms丢点。保留距离自适应公式，不误称全距离固定6cm。
不伪造人验/身份/状态/跌倒真值，没有GT写UNKNOWN；人工输入不是全部软件开发前提，不设置人工签字/复审。

三、事实与原门
W1原生192×256；386帧14,361,073非零点唯一映射、range误差0、120帧因果前缀、780完整性回放、本地3.8/1.17一致。
旧链SHA为6aa6629066956d9949e4188d8c31b1ea69ed6214d0b4a112b1c8924359a21017，仅同输入/配置/序列化契约比较。
原G1全部分散度<5%、PC前端P95<10ms；现为5.448%、三轮15.911/19.307/15.829ms，未全过。原G2含跟踪<15ms；20ms PC/30ms板端仅候选整链预算，须有拆分/丢帧/帧龄证据，单列不覆盖原FAIL。
f360旧参考2263、存活2221、最佳分量2121/交集2100、新增21、主分量外163=其他存活121+未存活42。121/2221是分散度、163/2263是主分量未覆盖、2221/2263是union旧行覆盖，不混称人体丢点。
Demo/现有短房间数据不是浴室验证；目标域UNKNOWN。已有其他几何影子发布不代表新W1/W2/HMM部署，按PROJECT_STATE分链说明。

四、P0第一动作
先对f360实际added/removed数组逐行归因，读取原始XYZ/ray/阶段mask/组件，记录局部row与offset+row；按首次排除阶段计主因并守恒。人体/家具身份未知则UNKNOWN，不能凭图断言。
尾部处置：REFERENCE_ARTIFACT / FRAGMENT_TAIL_ACCEPTED / REAL_LOSS_NEEDS_W2 / UNRESOLVED；允许证据不足，但必须说明缺口与下一步。接受尾部不使原G1b变PASS；保存f360邻帧作W2回归。
先存基线，再用独立脚本/最小计时点profile decode的frombuffer/xyz/range/az-el/lookup/fill及background/denoise/components/source-lift/ledger/JSON/IO。允许必要诊断仪表，不提前改算法凑通过。
固定输入/配置/源码SHA/环境，三轮串行独立进程，无并发测试或压缩；记录CPU/线程/电源/负载/亲和可用性，不改系统服务。预热与ready分开，保存逐帧n/P50/P95/P99/max。细计时开销另对照，阶段P95不能相加冒充整链P95。
区分W1算法、W1+W2、整链、含IO/JSON范围；早期8.99ms关联23c487…，最终5eb621…另列，完整SHA读取原记录。
诊断后单因素优化：按需诊断数组、数值/分配、组件对象/排序、重复foreground；不改阈值。逐帧核对来源/拒绝/状态，浮点容差预设并查边界翻转。
补merge-ground的session/meta/points/transform/calibration/grid/epoch和provenance字节绑定；错配/缺失拒绝，frame_id相同不是同源。背景缓存自描述且绑定有效前缀。
补compare/reference_rows/percentiles/SUMMARY直接测试与独立审计：两片分裂、predicted/occluded排除、空survived=null+原因、SHA错配拒绝、聚合分母。
SUMMARY加入union/Jaccard/added/removed/组件数/largest及有效n；分清67新增行扩张与79总点数扩张。780仅完整性，不冒充效果；新增文件计入范围。补躯干四肢合成连通，只验证软件。
新证据目录保存G1_DISPOSITION.json、逐行账本、原始计时/SHA/命令/失败日志；G1a/b/c各给原要求、PASS/FAIL/UNKNOWN、处置/证据/未解项。文字结论写PROJECT_STATE/PROGRESS及W1追加状态，不回填旧evidence或写管理报告。

五、P1：W2接W1
先查已有接口，再按需实现range_tracker.py、range_features.py、replay_range_tracking.py及回归。
source_rows只标识同帧行；跨帧使用ray support或运动补偿空间支持，禁止交集相邻帧row整数当点身份。因果[x,y,vx,vy]，初始候选门0.5+2.5dt，一对一确定性关联，交叉歧义unknown；碎片合属需依据，不无条件并簇。
birth≥3有效观测帧，miss>1.5秒删除；预测不造source_rows/实测特征。时钟倒退/断档/epoch或标定变化重置。低姿态出生不被直立高度门丢弃，也不直接判跌倒。
W2只能重组当前实测，不能补造丢失回波或混入历史点充当当前测量；另做多帧积累必须逐点保存原帧/年龄，单列统计。
目标评分不读旧参考；高度需地面绑定，PCA退化axis_valid=false，visible_ratio无可信分母为null。ledger含输入/配置SHA、session/frame/time/epoch/track_id/status/observed/source_rows/bbox/features/masks。
验证匀速/交叉/遮挡/碎片/低姿态/空帧/断档/回退/换标定、f360邻帧、386/780整段和因果前缀；本地3.8兼容与ARM原生分别报告。
G2分软件、代理、真实GT、性能：参考observed帧中存在新实测目标的比例≥95%，不代表找对人；另报同帧交集/诊断组件实测行数≥97%的全分布、失败帧及行数加权汇总，空分母null，均是代理非召回。真人ID切换<1/100已标注相邻可见帧转移，无身份GT为UNKNOWN；合成已知ID另表。780逐帧比较空输出/碎片/丢锁/性能。原<15ms与候选≤20ms单列。

六、P2–P4：独立软件继续，外部证据不制造
P2在pc_apps/range_fall/实现候选导出、距离图/BEV复核HTML、schema导入评测。track_labels_v1绑定SHA/人员/会话/轨迹/时间/来源/修订。200条是目标，不足如实报告；浴室1/2/3m与fixture分层，4–6m另域。候选复核只能测precision；recall另需覆盖无候选窗口的独立人体清单。缺人验继续工具工作，分数UNKNOWN。
P3复用HMM/规则最小接口，不复制Demo投影；5状态固定先验因果前向、缺测mask、可靠dt、稳定数值、秒制保持/冷却去重。低姿态出生不判跌倒，长躺协议30s，confirmed=false。
默认不拟合。未来明确要求及有效标签后，2人开发/1人冻结hold-out；只有事件标签不能假装逐状态监督。公开UR Fall/合成/IFW分别适配，不将RGB-D映成IFW ray；先查本地，不自动下载。LaserAct缺失或不适配记依赖。已反复迭代的UR70仅开发回放，不称独立测试。
P4按需实现core/range_runtime.py和独立bench，板端前向仅3.8+stdlib+NumPy。本地数值/候选时刻/异常/整链计时可完成；板端30ms及1h/24h实测不自动执行，device_not_run。超预算先profile，降分辨率是新变体必须重验，不直接牺牲正确性。

七、P5–P6：数据与评测
空场/3人18事件60负例/正式8–10人48–60事件160–200负例/20h日常按采集协议计划；组织者/日期未定记未排期。AI准备检查/统计，不采集或编造真值；受控倒地与真实跌倒区分。
先冻结人员划分、参数、事件时间定义/同步误差、一对一匹配窗口/冷却/重复报警口径。主召回分母全部已确认事件，可观测子集仅诊断；缺GT UNKNOWN。匹配事件计算延迟同时列漏检，相对接触/下降起点明确，不混算法耗时。
FA每墙钟小时/每浴室使用小时/每次使用分别匹配各自窗口和分母，未知时段不算已确认负例；零曝光UNKNOWN。每层n和区间；18/60不证明统计充分。公开/合成/auto-label不替代浴室效果。

八、每轮收尾
python -B -W error运行相关测试。改core跑：
python -B -W error -m unittest discover -s src/human_fall_detection/tests
按影响范围分别跑：
python -B -W error -m unittest discover -s src/human_capture/tests
python -B -W error -m unittest discover -s src/human_follow_calibration/tests
改Demo跑：
python -B -W error -m unittest discover -s pc_apps/bathroom_demo -p "test_*.py"
改页面用具名JS套件，不glob全部。
每轮一次离线CLI回放/端到端、关键SHA和新增文件清单，失败保留。证据新目录，更新PROJECT_STATE并追加PROGRESS。
缺数据只停止真实效果/拟合/上线晋级，继续尚有价值的独立软件；独立部分完成后明确依赖并停止重复核查。未过性能/真实损失未解，不声称G1/G2通过或生产可用。
最终中文报告实际完成、文件、测试/回放、证据/数字、原门与候选门结果、UNKNOWN/外部依赖、下一步，不把计划当结果。
第一动作从P0开始，完成诊断和必要正确性修补后再开P1。本提示词不授权设备/训练/Git操作。
```
