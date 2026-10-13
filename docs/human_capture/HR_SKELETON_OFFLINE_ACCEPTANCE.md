# HR-SKELETON-OFFLINE 唯一验收表 v1

2026-10-08（Asia/Shanghai）；状态 **DRAFT_READY_FOR_DISPATCH**，本轮只制定。生效范围：用户明确授权 [本工单](tickets/HR-SKELETON-OFFLINE.md) 的独立PC离线原型后。全部初始NOT_RUN；不能放行正式W04/W05、恢复旧HR-07或改变SEM/W03/RET-V2状态。

统一纪律：100个计划原始帧/最多120分支行分开；未审、无簇、低支撑、错误和UNKNOWN保留清单。人工PERSON和节点可见性/支撑区域必须有实际reviewer、来源/成员SHA；ROI、机器ID、骨架形状不作为人体GT。节点当前valid必须有真实当帧支撑，raw与filtered分开；缺点UNKNOWN/null。区域参考误差不是独立解剖关节精度。明确真实正例防止全拒绝制造通过。

| ID | 检查与证据 | PASS条件 / FAIL或BLOCKED | 初始 |
|---|---|---|---|
| SKO-01 | branch/HEAD、dirty、全部tracked/untracked+忽略冻结输入/旧evidence SHA | 基线完整、独占新轮、记录当前授权和工具/运行版本；意外漂移FAIL | NOT_RUN |
| SKO-02 | raw meta/bin、TLS/诊断矩阵、R1权威完整成员、R2工具与交付SHA | 不信候选内部SHA；从raw独立重建，身份/来源/摘要全部对应；不可核验BLOCKED/被篡改FAIL | NOT_RUN |
| SKO-03 | 预登记窗口/开发验证用途、全帧清单、无簇和未审 | 按计划固定100唯一帧/120分支行；不按输出挑成功帧，不称盲测；丢分母FAIL | NOT_RUN |
| SKO-04 | PERSON/STATIC_OBJECT/MIXED/UNKNOWN、人ID/连续性、实际人工reviewer | 真人输入满足B的最小GT；其余帧未审仍BLOCKED，非PERSON不得自动获得有效人体骨架；GT缺失BLOCKED | NOT_RUN |
| SKO-05 | 节点支撑定义、schema/参数v1、开发与验证隔离 | 算法前冻结定义/理由/评分含义，开发参数冻结后验证；验证集调参或无点规则变更凑结果FAIL | NOT_RUN |
| SKO-06 | 局部坐标/正逆变换、单位、Z语义 | 首版纯XY平移、Z不改、全有效成员保留，数值逆变换最大误差≤1e-5m；混坐标或假称外参核验FAIL | NOT_RUN |
| SKO-07 | frame/source/global row、normalized映射、node支撑row | 一一映射、有效node支撑属当帧完整人体成员，可独立重算；换成员旧SHA、交换SHA、重命名ID、删成员/重复ID、伪权威均拒绝并定位 | NOT_RUN |
| SKO-08 | 空/无效XYZ/低支撑/STATIC/MIXED/UNKNOWN | 各入口清楚拒绝或UNKNOWN，零/非有限源row不变有效结构；不能重聚类、裁ROI或改背景凑人体；违规FAIL | NOT_RUN |
| SKO-09 | 真实合法躯干正例、非法/缺失对照 | 至少一个真实人工确认可见躯干区域的正例产出有真实支撑节点，同时负例拒绝；全拒绝FAIL，缺真实GT BLOCKED；不代表全身精度达标 | NOT_RUN |
| SKO-10 | 举手HEAD/ARM歧义、缺头/可见头标签、逐帧原因 | 不把最高点/手固定当头，不按身高补头；缺支撑null，漏掉已标可见头计漏检并披露；真人对应未标BLOCKED | NOT_RUN |
| SKO-11 | PCA退化/正负轴、单腿/双腿与人体左右 | 轴/朝向不明UNKNOWN；只在真实支撑分离时产A/B，未确认左右不乱命名；坐蹲/卧等未覆盖不推断通过 | NOT_RUN |
| SKO-12 | actual stamp、缺帧/重复/倒退/seek/换身份或坐标版本 | 独立时序状态、实际dt、所有生命周期reset实测；原human Tracker/Fall不改，当前缺点不被历史滤波补有效 | NOT_RUN |
| SKO-13 | 审阅入口、support显示、raw/filtered、导出sidecar一致 | 显示/成员/支撑/身份/参数/票据来源一致，非法导出拒绝；实际浏览器未跑单列BLOCKED，不用headless冒充UI | NOT_RUN |
| SKO-14 | 逐节点GT覆盖/valid/UNKNOWN/区域误差/跳变与代价 | 真实分母、失败与缺口完整；无节点GT对应指标BLOCKED，不伪造正确率/关节精度/人体召回；仅报告可行性 | NOT_RUN |
| SKO-15 | 固定验证/难例/空场，两口径/分母与身份资格 | 不把背景或未授权机器候选直接当PERSON；空场0有效PERSON骨架；隔板/举手失败真实保留，不凭躯干成功宣布头/完整四肢通过 | NOT_RUN |
| SKO-16 | 独立raw/support/逆变换、可核正负预期与两遍digest | 不单用被测validator的PASS自证；同固定输入/参数两遍结果digest一致，独立核成员/观测/显示 | NOT_RUN |
| SKO-17 | 必要相关JS/Python回归、旧资产/新范围/return前缀 | 实际命令/exit/日志与SHA齐全；Python -B -W error；只跑受影响/复用入口的必要回归；旧资产无变化、return仅追加 | NOT_RUN |
| SKO-18 | 分项报告、可审查交付、ponytail路径、停止/生产边界 | SUBMITTED及逐ID结果，未自封ACCEPTED；工具/GT/节点性能/设备分开；完整报告后停止，无自动下一阶段 | NOT_RUN |

说明：SKO-09是最小阳性能力检查，不是95%人体识别或骨架准确率门。SKO-14要求可信报告；数值性能资格没有因报告完整而获得PASS。实施返回另外列逐节点“已验证可行/失败/GT阻断/未覆盖”，保留HEAD与躯干差异。若需要正式精度目标，先冻结独立GT/评估口径并另行审查版本，不回改本轮门或历史。

本单之外：W03冻结/正式自动人体资格、WD02规则裁定、生产W04/W05、W06姿态/W07跌倒、完整四肢/COCO17、精确关节、弯腰坐蹲卧/多人真实资格、采集/板端/物理/部署/网络驱动/ML、artifact签装/生产旗标均NOT_RUN/BLOCKED，须各自正式条件与授权。新表不成为这些项目的替代验收表。
