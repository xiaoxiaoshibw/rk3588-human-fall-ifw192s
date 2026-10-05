# 下一阶段计划审查 / 2026-10-03

审查角色：Codex；只读辅助分别审生产消息链和GL05设备/物理/发布计划。**审查结论：方向可采纳，但不能直接启动GL05。当前先完成GL04浏览器收口，并准备生产接入的独立软件范围；设备验收须在输入、判据与具体授权齐备后执行。** 本文仅计划审查，不创建活动工单、不派OpenCode、不改生产代码、不连接板端、不采集/部署。

当前依据为WORKFLOW/DISPATCH最新入口、GL04_ACCEPTANCE v1与R7正式复审。GROUND_LEVELING_PLAN早期表仍写GL03 R4/GL04 WAIT_DEPENDENCY，属于旧状态，不当成当前事实。GL05 ticket目前仅WAIT_DEPENDENCY，没有现行GL05验收表；部署文档所列20261001版本/PID为历史记录，未做本轮板端核对。

## 1. 必须修正的计划缺口

| 审查项 | 当前事实 | 计划裁决 |
|---|---|---|
| GL04前置 | V01–03/V05–09 PASS；V04/C12/M03实际DPR-only NOT_RUN | 先补同页真实DPR变化，不能用属性伪造/跨导航的1与1.2替代；无代码FAIL，不为形式派R8 |
| 正式源码 | preview获审门未闭合，正式页Q/E/帮助有外部改动 | 获审后由唯一OpenCode按特性集并入当前正式源码，逐段合并、不整文件覆盖；同步源码不等于发布 |
| V10消息投影 | build_snapshot已经拿到validated ground_derived，却只发GDID/摘要 | 需要另审core写入范围与additive消息契约，不能把设备验收变成临场补代码 |
| 支持区来源 | artifact只有valid_region_ground_local bounds；自动source_valid_region_corners为trusted=false | 不把AABB伪装实际支持polygon/已核验地面；R/t可先独立闭合，support缺口如实保留 |
| 生产标定选择 | human_fall_prod.yaml calibration/ground/background路径均null | 软件发布字段能力不等于活动节点有真实变换；真实artifact与配置选择留待设备阶段授权 |
| 真实标定输入 | constrained --bag明确拒绝真实输入，原点索引/帧组尚未适配 | 先完成可追溯数值输入适配，否则GL05“从真实场景生成标定”无法执行 |
| 物理/性能判据 | GL00 physical_thresholds全部BLOCKED；无新的设备性能门槛 | 在验证数据测量前冻结，不能把合成误差或历史性能数字搬成现场标准 |
| release行为 | deploy release会重指current与正式页；只复制py/yaml、页面，不自动复制标定JSON | 候选包准备和实际切换分开；确认标定JSON冻结/哈希/回滚路径，不声称现脚本已保证完整标定回滚 |
| 停启顺序 | start按当前release路径校验旧PID，release先换链接后旧节点仍在会产生路径不匹配 | 发布计划先核旧PID并stop本功能旧进程，再release/start；失败恢复已核旧版本，不重启driver |
| 测量标签/耗时 | profile硬写ground=unavailable；现process统计不是独立转换/序列化成本 | 记录实际mode/cal/config/version；无专用测量入口就只报告整链差值，不命名为“转换耗时” |

证据位置：GL05 ticket任务2/3/5/6；GL00 R4 CODEX_REVIEW及26_parameter_plan.json；calibrate_sensors.py:224–228；calibration.py:557–591/695–718/793–891；lidar_candidates.py:470–511/593–596/612–671；human_fall_prod.yaml:38–40；deploy_human_fall.sh:98–140/160–161。

## 2. 推荐阶段顺序与放行门

### A. GL04浏览器收口（沿现行v1，不改代码判据）

在能改变实际DPR的浏览器环境中，固定同页面、同fixture/frame/cal/GDID和camera，记录变化前后实际devicePixelRatio、CSS视口、renderer与overlay backing尺寸、2D框投影及原选择ID。source/ground两模式分别验证，保留现有min(DPR,2)规则，不临时设新的DPR数值门槛。必要的浏览器缩放/显示环境操作与脚本改数值分开；无法实做仍NOT_RUN。

**放行条件：V04/C12/M03有真实证据并经Codex独审，无新FAIL。** 之后更新GL04软件结论。V10/D01仍单独分层，不能由DPR通过推出生产端到端/物理已通过。

正式源码同步随后单独执行：先核获审版本与当前formal SHA、确认原合并裁决链路（未找到原询问卡时按用户既有第4步复述确认），OpenCode最小逐段合并，保留Q/E/帮助及其余外部变动；只对改动部分补原断言/消费者检查，未变部分复用R7回归，不无由重跑326/7/12+2。本地同步与板端部署分开。

### B. 生产消息接入软件准备（需另行明确core范围授权）

建议独立的生产消息集成工单，暂不编号/激活。DPR环境准备与本单只读设计可以并行；在GL04当前冻结范围内不偷改core，也不以新单名绕过跨关授权。

最小方案：在build_snapshot现有_validated_ground_derived结果处，投影`coordinate.ground`作为唯一权威块；沿既有浏览器支持的`kind=coordinate_ground`、schema=1、from/to、units=m、calibration_id、geometry_schema_version、GDID、显式R/t。顶层candidate_snapshot schema1与旧source/reference字段不改；不再发两个冲突alias，不重新求平面、不把unknown补成identity、不提升任何物理flags。

复用GL02严格artifact校验/deepcopy与GL03产生frame/parent绑定。node_runtime现有build_snapshot调用及ROS projection可自然保留新增块，先验证实际透传再决定是否需要改；不要先新增节点/热更新框架/库。建议最小授权：lidar_candidates.py、一个集中producer→ROS→JS回归、工单/验收/契约additive说明；node_runtime或预览标签仅在调用链证明需要时纳入。当前无需动ground数学、frozen config、driver、正式页或部署脚本。

**支持区域分两层决定：** 推荐先发布R/t能力、支持字段为空并附明确reason；此时V10的支持来源仍BLOCKED，不能标完整端到端PASS。若后来批准可信ROI边界，必须trusted=true+evidence、明示“ROI边界/包络，不是实际内点轮廓或已验证全区”，只发有限polyline，并检查现UI是否保留来源标签。若要求actual support polygon，则另明确标定工具/validator/轮廓持久化的范围与真实来源。默认AABB/trusted=false绝不直接画成支持面。

派工前唯一验收表/完整矩阵至少覆盖：startup full/ground-only/none；同内容、同ID异内容、新ID、caller原地改；parent/frame/cal/schema/GDID错误；非法R/t/单位/物理flags；unselected/locked/prediction/lost与pending/ready×source/ground；stale/断连/monitor失效恢复；缺支持/自动bounds/有证据ROI；有限JSON/预算/源索引与旧字段兼容。证据必须从**实际build_snapshot输出**经project_snapshot_for_ros进现JS parser，不能手工synthetic snapshot代替生产函数。

新增字段按最小whitelist发，避免整artifact/几千支持点每帧重复膨胀。优先常量R/t与有限4/5顶点边界；若真实support点集合，沿≤3000预算保留原计数/采样索引，量化serialized bytes及CPU/时间，不能因前端预算就推断板端无成本。

### C. 真实输入适配与现场协议冻结（授权范围与B区分）

先以现有、已获允许读取的数据做离线输入适配设计；新设备采集另需边界授权。保留每个真实点的frame_seq、原point_index、stamp/frame/units和过滤映射，拟合/验证索引及帧组不交叉，不把跨帧pool冒成完整单帧。适配器必须复用冻结解码语义，不能只删constrained --bag的拒绝分支。先通过真实数值输入格式/manifest来源审查，再允许生成候选标定。

至少确认一个拟合地面区和三个有空间分布的独立验证区域，预先固定ROI/帧组、源索引与覆盖条件；每区域独立评价未截断残差，不按待验证平面残差先筛点，不用总体平均掩盖某区失败。单平面/室内水平性、独立up_axis/源轴证据、分段误差与稳定窗口均需定义。

当前已知：雷达向下看、具体角度未知；机器人总高1.4m已提供；约1.1m只是窗口离地，点云原点偏移/误差未核。现场高度参考应选可在点云中确实指认的测量表面/点簇；若机器人顶面未被雷达看见，不能拿cloud bbox最高点硬比整机1.4m，更不重复要求用户重报已有数值。保留d约1.29–1.32m与窗口高度的差，禁止用1.1m硬修d；约26度截图粗估也不是安装实测。

**物理门槛尚未成立。** .03m RMS/.05m P95、2度/.03m是合成软件协议；GL02的.1m是监测触发正例，均不能自动成为GL05现场精度。先确定测量方式、可见性、误差预算/不确定度，再在验证数据采样前冻结现场判据。性能也先固定同数据/配置/输入节奏、统计窗口及可接受退化规则，不能现在编造p95<某值或≥10Hz。

### D. GL05隔离设备验收与候选版本（需具体现场/连接权限）

GL01～04必要软件门槛、B/C对应前置齐备后，创建唯一GL05_ACCEPTANCE v1与操作矩阵。按实际核对的RK3588/容器/ROS/Python/NumPy、driver/page/node/config/calibration/hash建立新基线，不拿部署文档的旧PID/版本当当前值。

隔离执行/构建与活动服务分开，避开会改vendor manifest的顶层build脚本。候选真实artifact及配置选择显式记录，不能把synthetic路径写生产。做真实离线逐区地面/高度/稳定失效、同数据旧新板端性能与真实浏览器source/ground/俯瞰/选择/源版本失效；baseline pending/ready与旧事件/ACK保留。confirmed与IMU融合继续关闭，semantic unknown不改；大框因果/分离/人体准确性另外分列。

性能记录process p50/p95、有效处理Hz、输入Hz、窗口drop增量及累计基线、RSS/CPU/温度与序列化/发布成本；浏览器FPS单列。跨时钟不能相减造端到端延迟。若无独立转换测量入口，只写整链差值。修正/替代profile硬编码mode标签需明确脚本范围，记录真实cal/schema/GDID/config版本。

### E. 具体版本获审后发布（最后门）

先形成可审查候选bundle/网页/config/真实calibration/manifest与已验证rollback目标。当前release只复制*.py/*.yaml及页面，calibration JSON的版本冻结和完整回滚仍需具体方案/必要脚本范围授权；不能默认“代码回滚=标定回滚”。候选包可在本地/隔离stage准备，**不执行release作为准备动作**。

发布动作必须在具体版本、目标、备份/回滚与权限可核后执行。当前脚本应按实际PID/旧release核对→stop本功能旧节点/observer→release→start→核加载位置、页面/配置/标定hash/健康；release会重指链接，start按新current路径不能直接安全匹配仍运行的旧路径PID。失败恢复已核旧版本，只动本功能，不重启driver/bridge、不改网络、自启、旧首页，不删除历史release/原数据。发布后独审与回滚证据齐备才给发布层PASS。

## 3. GL05验收表建立前的检查清单（不是活动验收表）

| 分类 | 必须交付的可观察证据 | 当前执行准备 |
|---|---|---|
| 软件/浏览器前置 | GL04 V04真实DPR、获审源码同步，原功能/用户改动与SHA | NOT_RUN |
| 生产消费闭环 | 实际producer→ROS projection→JS，同帧/版本/R/t/实际BBox/支持来源与选择ID | BLOCKED |
| 真实输入来源 | 完整原帧/点索引/单位/frame/manifest；fit/validation无泄漏 | BLOCKED |
| 地面身份/覆盖 | 人工确认拟合区与≥3独立区域、预先ROI与索引 | BLOCKED |
| 物理数值/高度 | 每区域未截断残差、支持/稳定、可指认尺量目标及不确定度、冻结判据 | BLOCKED |
| 板端性能 | 可重现同数据/节奏窗口、drop增量、处理/序列化/资源、真实mode标签 | BLOCKED（判据未冻结） |
| 环境/候选版本 | 实际环境/运行bundle与page/config/artifact对应、无driver变化 | NOT_RUN |
| 发布/回滚 | 具体新/旧版本与完整code+page+calibration可回退、真实PID/路径/指针 | NOT_RUN |

本次仅完成审查文件。当前授权仍为GL04范围内编排/复审；新core集成/真实适配/设备连接/采集/配置启用/部署必须按具体范围获得新授权。下一步建议先批准B的软件范围与C的离线适配范围，同时补A的DPR环境；正式同步、GL05设备执行和最终发布各守其前置，不把“审计划”当实施/发布授权。
