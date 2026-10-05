# RK3588 人体定位、目标锁定与 WebUI 跌倒检测开发计划

当前本地新增入口：[GL-V01三会话算法验证](tickets/GL-V01_algorithm_validation.md) / [唯一验收v1](GLV01_ACCEPTANCE.md) / [回传](returns/GL-V01.md)。作者SUBMITTED/STOPPED，外部独审NOT_RUN；仅静态离线，历史数值FAIL与物理/设备边界保持。


2026-10-05 当前入口：[GL-W01本地离线工作台](tickets/GL-W01_offline_workbench.md)/[唯一验收v1](GLW01_ACCEPTANCE.md)/[使用说明](../../pc_apps/human_replay/LEVELING_README.md)。三算法离线按钮、可行度筛选、配平数据导出已作者自验，SUBMITTED/指定独审服务BLOCKED；AGL-A～I仍NOT_RUN，物理/生产资格不提升。下方10-04“仅计划”保留历史。

本轮仅计划：自适应地面配平最终路线已编制 **PLAN_READY**，[正式计划](ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md)/[模块与状态契约](ADAPTIVE_GROUND_LEVELING_CONTRACT.md)/[GL-A～GL-I工单索引](tickets/INDEX.md)。九单均未实施/NOT_RUN；H实时shadow与I人工接管须后续具体授权及证据门；当前静态方案、1.14m物理记录、P02既有结果保持，不启动CLI/设备/源码变更。

2026-10-04 当前离线P02 v2：四ROI联合配平与同一HTML三算法展示已完成作者自验；392196源点、逐区门PASS，留一区3/4 FAIL保留，物理/外推BLOCKED/P1 NO，无设备/采集/部署。入口：[唯一v2](P02_ACCEPTANCE.md)/[本轮结果](evidence/2026-10-04_p02_four_roi_r1/08_REPORT.md)。以下GL-C01等为历史阶段记录。

2026-10-04 GL-C01 **当前联合反解小点自验完成 / SUBMITTED / STOPPED**：[唯一v1](GLC01_ACCEPTANCE.md)/[收口](evidence/2026-10-04_gl_c01_r1/20_CLOSEOUT_01.md)。99帧新cohort单FIT/frame0与三个独立validation/frame33/66/98，源行冻结无Z/残差裁剪；数据估计pitch26.314310°/roll-0.612061°/tz1.323137m，validation共同FIT平面P95两区0.050762/0.057539m FAIL保留。458fall回归、5新tests作者自验通过；未指定独审，不标软件独审PASS。用户要求做完这一小点先停，本轮不派probe/独审/后续任务，不设备/采集/部署/生产。

2026-10-04 GL-B01 R1 **区域复核/诊断软件独审PASS / SUBMITTED / STOPPED**：[唯一v1](GLB01_ACCEPTANCE.md)/[收口](evidence/2026-10-04_gl_b01_r1/33_CLOSEOUT_01.md)/[独审](evidence/2026-10-04_gl_b01_r1/30_OPENCODE_VERDICT_01.md)。R01–R06/S01/Q01–Q06 PASS，无需返工；用户木地板/工作台语义和75cm参考已记录，P01剩余行集/精度/SDK BLOCKED，D01 NOT_RUN。89帧当前数据2959候选场景行保持全高度、未制造精确ground标签。联合反解下一单按新用户具体授权处理，B代码持续停写。

2026-10-04 GL-N01 R1 **当前参数名义离线配平软件独审PASS / SUBMITTED / STOPPED**：[主线计划v3](GROUND_LEVELING_NEXT_STAGE_PLAN_V3.md)/[唯一v1](GLN01_ACCEPTANCE.md)/[收口](evidence/2026-10-04_gl_n01_r1/22_CLOSEOUT_01.md)/[前后图](evidence/2026-10-04_gl_n01_r1/07_before_after_frame05_01.png)。26°/1.1m已变换全部89帧，3699085有效点源行保留；N01–N06/S01/Q01–Q06 PASS，P01独立物理BLOCKED、D01 NOT_RUN，真实浏览器NOT_RUN/BLOCKED。参数可配置、新ID与结果版本；无writer、不自动真实拟合/生产接入/设备/采集/部署。

2026-10-04 GL-E02 R1 **软件独审PASS / SUBMITTED / STOPPED**：[唯一v1](GLE02_ACCEPTANCE.md)/[收口](evidence/2026-10-04_gl_e02_r1/41_CLOSEOUT_01.md)/[Go Flash独审](evidence/2026-10-04_gl_e02_r1/36_OPENCODE_VERDICT_02.md)。E01–E06/S01/Q01–Q07 PASS，P01独立物理复核BLOCKED，D01 NOT_RUN。用户最新1.1m/约26°下俯作为名义安装参数已记录；照片确认与刚拍陈述保留。无writer/无需返工，不自动拟合/采集/生产接入/部署。

2026-10-04 下一阶段计划已准备（DRAFT_READY，未启动）：[阶段计划v2](GROUND_LEVELING_NEXT_STAGE_PLAN.md)/[算法设计](GROUND_LEVELING_ALGORITHM_DESIGN.md)/[首代码研究单GL-I06](GLI06_ACCEPTANCE.md)/[执行提示](AI_PROMPT_GLI06_CODEX_R1.md)。算法shadow与GL-E02现场证据并行准备，源码写入串行；当前GL-E01来源链PASS及物理/DPR未闭合状态保持。

2026-10-04 主线GL-E01 R1 **来源链独审PASS / STOPPED**：[唯一v1](GLE01_ACCEPTANCE.md)/[收口](evidence/2026-10-04_mainline_evidence_r1/17_CLOSEOUT.md)/[指定独审](evidence/2026-10-04_mainline_evidence_r1/opencode_review_01/00_review.md)。原bag实际SHA、89frames/4372400points、26B→28B全部bytes/XYZ/meta/NPZ匹配，A01–A05/S01/Q01–Q06与B01来源链PASS；B02物理BLOCKED，D01 NOT_RUN，D02 DPR环境BLOCKED。旧NPZ/旧GL-I05记录不回填，GL-I05软件PASS保持；不新采集/部署/driver/network变化。当前主线转录制外参/ROI身份与实际DPR，详情见收口。

2026-10-04 当前主线GL-E01 **SUBMITTED待独审**：[唯一v1](GLE01_ACCEPTANCE.md)/[取证范围](evidence/2026-10-04_mainline_evidence_r1/00_SCOPE_AND_DIAG.md)。既有原bag已只读找到，实际SHA与声明一致，原26B独立重建canonical28B与本地bin/NPZ全量匹配；仅来源链自验，不是物理标定。Codex已停写，fresh probe后Go Flash/defaultDB复核。GL-I05软件PASS保持；外参/ROI身份仍BLOCKED，GL04真实DPR当前API不可控；不新采集/部署/网络/driver变化。

2026-10-04 GL-I05 R2 **软件独审PASS / STOPPED**：[唯一v1](GLI05_ACCEPTANCE.md)/[收口](evidence/2026-10-04_gl_i05_r2/31_CLOSEOUT.md)/[最终指定二审](evidence/2026-10-04_gl_i05_r2/opencode_second_review_02/00_review.md)。C01–C06/E01–E02/S01/Q01–Q10 PASS；B01/B02 BLOCKED、D01/D02 NOT_RUN，整单未ACCEPTED。无writer、无新软件FAIL，仅离线研究/源点证据工具；生产/输入/旧证据冻结，GL04/GL05设备边界保持。原算法二审检查器覆盖偏差已保留全版本并新编号不可变复验，未掩盖历史。

2026-10-04 GL-I05 R2 **SUBMITTED待指定独立二审**：[唯一v1](GLI05_ACCEPTANCE.md)/[提交](evidence/2026-10-04_gl_i05_r2/research_01/11_submission_manifest.json)/[R1复盘](evidence/2026-10-04_gl_i05_r1/09_CLOSEOUT.md)。Codex研究writer已停写；38case自验同序列匹配、17研究自检通过；fresh probe后Go Flash/defaultDB只读二审。B01/B02 BLOCKED，D01/D02 NOT_RUN，未ACCEPTED。

2026-10-04 GL-I05 R2 **同项返工实施中**：R1指定Go Flash/defaultDB独审REWORK，[R1收口](evidence/2026-10-04_gl_i05_r1/09_CLOSEOUT.md)/[二审](evidence/2026-10-04_gl_i05_r1/opencode_second_review_01/00_review.md)/[唯一验收v1](GLI05_ACCEPTANCE.md)。Codex唯一研究writer，旧提交停写；只新evidence/2026-10-04_gl_i05_r2/research_01，生产/数据/旧证据冻结。完成自验停写后fresh probe再指定二审；B01/B02 BLOCKED、D01/D02 NOT_RUN，未ACCEPTED。

2026-10-04 GL-I05 R1 **已SUBMITTED待独立二审**：[唯一验收v1](GLI05_ACCEPTANCE.md)/[回传](returns/GL-I05.md)/[提交manifest](evidence/2026-10-03_gl_i05_r1/research_01/11_submission_manifest.json)/[逐帧复核页](evidence/2026-10-03_gl_i05_r1/research_01/source_review.html)。Claude顶替Codex为唯一研究writer已停写（2026-10-04用户恢复Codex编排）；32 case全oracle_match/closure_safe、生产423/423测试OK、零src修改；B01/B02 BLOCKED、D01/D02 NOT_RUN，整单未ACCEPTED。Codex接回后先一次≤1min Go Flash/defaultDB probe，再按[二审模板](AI_PROMPT_GLI05_OPENCODE_SECOND_REVIEW_R1.md)只读独立二审收口。

2026-10-03当前入口：[GL-I04 v1](GLI04_ACCEPTANCE.md)/[收口](evidence/2026-10-03_gl_i04_r1/32_CLOSEOUT.md)/[指定OpenCode二审](evidence/2026-10-03_gl_i04_r1/opencode_second_review_01/00_review.md)。Codex三新文件停写后独立二审：L01–L06/R01–R06/S01/Q01–Q10 PASS，无源码返工；B01/B02 BLOCKED、D01/D02 NOT_RUN，整单未ACCEPTED。离线诊断可用，搜索原型保留研究、不接运行时；无活动writer，冻结算法/批准输入保持，GL04DPR/正式及GL05设备边界不变。下方准备/GL-I03入口均为历史。

2026-10-03 当前入口：[GL-I03 v1](GLI03_ACCEPTANCE.md)/[本轮收口](evidence/2026-10-03_gl_i03_r1/32_CLOSEOUT.md)/[OpenCode二审](evidence/2026-10-03_gl_i03_r1/opencode_second_review_01/00_review.md)。Codex已开发三文件，软件二审PASS/不返工；真实candidate仍BLOCKED、整单未ACCEPTED。研究对照否定“只需增采样/修符号/清搜索标志”三种简单解法，89帧同box偏差稳定，下一步先核source坐标与ROI身份一致性，再设计搜索完整性实验。角色Codex主开发/OpenCode二审，无活动writer；GL04DPR/正式与GL05设备边界保持。下方服务/未实施状态均历史。

2026-10-03 20:13最新状态：[GL-I03本次恢复门](evidence/2026-10-03_gl_i03_r1/15_RESUME_BLOCKED.md)仍BLOCKED，新probe55.047秒启动超时/exit1，无生产writer或主线源码改动。[唯一v1](GLI03_ACCEPTANCE.md)/[待派提示](AI_PROMPT_GLI03_OPENCODE_R1_RESUME.md)。真实candidate先验一致性、GL04DPR与GL05设备边界保持；不换modelDBauth。下方旧状态保留历史。

2026-10-03接回收口最新入口：[GL-I03 v1](GLI03_ACCEPTANCE.md)/[独立报告](evidence/2026-10-03_gl_i03_r1/codex_review_01/CODEX_REVIEW.md)/[服务BLOCKED](evidence/2026-10-03_gl_i03_r1/CODEX_BLOCKED.md)/[恢复提示](AI_PROMPT_GLI03_OPENCODE_R1_RESUME.md)。GL-I03未实施、无活动writer；新probe55.078秒超时/exit1严格停派，Codex唯一编排角色保持。仅既有默认/冻结范围核查通过，显式变体NOT_RUN、真实candidate另BLOCKED。GL-I01/I02档案不变，GL04DPR NOT_RUN/正式不合并；GL05设备/部署/采集/网络/HR未授权。下方19:25/旧活动状态保留历史。

2026-10-03 19:25当前入口：[GL-I03 R1](AI_PROMPT_GLI03_OPENCODE_R1.md)/[唯一v1验收表](GLI03_ACCEPTANCE.md)/[本轮证据](evidence/2026-10-03_gl_i03_r1/)，Codex正式接回唯一编排/派工/独审/收口；OpenCode Go Flash/defaultDB仍单writer。GL-I01/I02已审分层不变；真实变体preflight1193→ground_degenerate，candidate BLOCKED，先诊断/设计门。GL04DPR NOT_RUN/正式不合并、GL05设备/部署/采集/网络/HR未授权。下文旧活动状态仅历史。

当前按[WORKFLOW.md](WORKFLOW.md) v2及用户本轮交接授权，唯一生效编排/独立复审/状态收口者为 Codex。范围内自动派 OpenCode CLI `opencode-go/deepseek-v4.1-flash` 已恢复，生产代码单写入者仍 OpenCode。GL02软件PASS不变；GL03 R7 G01/G02/G03/G04/G05/G07/G08 软件PASS，G06真实分离BLOCKED，O01统计PASS/真实身份BLOCKED，D01设备NOT_RUN/现场BLOCKED。当前无活动实现写入者、无新FAIL、无需R8；整单未标ACCEPTED，GL04须另获用户授权。[R7独立复审](evidence/2026-10-02_gl03_r7/codex_review_01/CODEX_REVIEW.md)、[验收v1](GL03_ACCEPTANCE.md)。

2026-10-02本轮交接：Claude Code 17:54按CLAUDE_STANDBY顶替后现交回Codex；此后唯一生效编排者是Codex，登记见CLI_RECOVERY。

2026-10-03最新事实：GL-04 R5独审REWORK、R6派工≤1分钟probe超时/exit1（见[CODEX_BLOCKED](evidence/2026-10-03_gl04_r6/CODEX_BLOCKED.md)），无活动生产写入者。按用户本轮"Codex 已恢复"通报，Claude Code **不顶替**编排/复审/状态收口，仍由Codex负责；服务恢复后由Codex先≤1分钟无工具probe，然后按[R6工单](AI_PROMPT_GL04_OPENCODE_R6.md)/[设计矩阵](evidence/2026-10-03_gl04_r6/PLAN_REVIEW.md)派工。

以下旧R4/R3及手动派工状态均为历史，由顶部R7结果/自动派工授权覆盖。

当前执行入口：[WORKFLOW.md](WORKFLOW.md) v2，用户手动派指定OpenCode，Codex独立复审。GL02软件PASS；GL03 R4软件REWORK（G03/G04/G05）、O01统计PASS/真实身份BLOCKED、设备NOT_RUN。当前[R4复审](evidence/2026-10-02_gl03_r4/codex_review_01/CODEX_REVIEW.md)、[设计再审查](evidence/2026-10-02_gl03_r4/codex_review_01/PLAN_REVIEW.md)、[手动R5](AI_PROMPT_GL03_OPENCODE_R5.md)。GL04未放行，不自动启动实现或板端操作。

下文开发计划和历轮记录保留历史背景；旧自动OpenCode派工和旧阶段状态受当前入口覆盖，不作为新操作授权。

更新：2026-10-01。HF-00/01已验收并冻结；点云几何候选、锁定/基线、时序判定、ROS和网页首版已实现并通过软件复审。真实跌倒准确性仍待物理标定、人工标签与受控验证。

当前交付：软件首版与可回退ROS1部署PASS，211两端回归、44独立Python边界和18网页纯检查通过。真实网页显示抽样流约8–9Hz、丢帧0、无缓冲溢出，算法保持完整原始点云。打开[正式页面](http://192.168.3.125:8090/human_fall/index.html)点连接；详见[最终复审](returns/HF-10.md)、[部署说明](deployment.md)和[恢复入口](AUTONOMOUS_RUN.md)。真实地面/背景、IMU与人体标签仍未验收，融合和confirmed禁用。

参考资料已整理到 [项目文献目录](../../文档/跌倒检测文献/README.md)：PointNet++正文与补充材料、ST-GCN正文及用户提供的实验方案原文；Lai 2026 PDF待补。阅读索引注明来源、核验结果和本项目适用边界。

交付目标：**RK3588运行人体样候选、位置/站姿基线、跟踪与跌倒算法；现有WebUI人工选择后自动更新目标框、位置和状态。** 详见[WebUI说明](WEBUI_SCOPE.md)与[部署说明](deployment.md)。软件、合成联调和真人验收分别记录。

## 1. 现状与首版目标

已核对：点云、IMU 发布代码在 `src/inno_lidar_ros/src/source/publish_manager.cpp`；静止目标标定和形状筛选在 `src/human_follow_calibration/scripts/`。2026-09-30 已 SSH 验证 RK3588 / Ubuntu 20.04 / Noetic 容器；点云约 9.65 Hz，六轴 IMU 短时接收约 227 Hz，姿态四元数全零不可用。用户确认没有相机。首版使用已验证的一个 PointCloud2 输入、设备状态与辅助 IMU，不创建图像/CameraInfo 输入，也不把“双目雷达”自行解释为两台独立设备。内部光学形态和精确型号可后续补资料。详见 [硬件盘点](hardware_inventory.md) 与 [IMU 核验](IMU_VERIFICATION.md)。

SDK 的 `imu_types.hpp` 把时间戳注释为纳秒，发布端按秒解释；这是待查矛盾，不能仅凭注释就改单位。当前发布端只复制角速度/加速度，未填姿态与协方差语义。现有目标筛选有最低高度和最大宽深限制，倒地人体可能被过滤。静态背景也可能扣除接近地面的身体点。现有 JSON 的距离残差比较可见表面与脚中心，不能当作尺度修正或相机外参。

首版假设：固定安装、平整室内场地，在 WebUI 人工框选确认一个目标，允许多人进入但有歧义就失去锁定。这里“识别”指人体样目标定位和同一目标连续跟踪，不涉及姓名、人脸或生物身份。页面显示坐标系明确的 XYZ/距离及包围框，可请求板端采集站姿基线；安装/地面几何标定与目标选择分开，框选像素不替代物理外参。遮挡后自动重识别、移动机器人上的跌倒检测留待后续数据支持。

## 2. 三类标定与传感器职责

1. **几何标定**：LiDAR 到固定场地/底盘的安装变换、地面法向与高度、有效时的 IMU 到 LiDAR 安装旋转。内部雷达 CSV 属厂商点云标定，不等于外部安装标定。
2. **时间标定**：确认每路时间戳单位、起点、采样时刻、偏移与漂移。原始时间戳必须保留，跨域转换经过验证后再同步。
3. **目标基线**：人工选人的站姿高度、躯干尺度、距离与初始位置；记录可用性。身体可见面与脚中心不是同一测量对象。

LiDAR 提供目标位置、地面相对高度、几何形状与连续变化。设备 IMU 在单位/轴向/偏置与安装关系核验后用于设备运动和静止重力参考，不测量人体冲击，也不能单独证明设备没有平移。未完成 IMU 验收时只记录其原始测量，几何基线按独立质量门槛评测。设备移动或地面残差异常时暂停静态背景方案，要求重新初始化。

## 3. 实现路线

在已创建的 ROS1 包 `src/human_fall_detection/` 中实现 RK3588 算法，复用现有点云解析，不改旧标定 JSON/话题或已冻结 health/manifest 的语义。纯计算与 ROS 回调分开，使用板上 Python 3.8.10、unittest + NumPy 1.17.4；首版不安装 OpenCV/姿态模型/RKNN。网页沿用板端现有 Three.js＋foxglove_bridge，把实时源码纳入本地 `webui/` 后改造；浏览器只做选择与渲染。

数据流程：
```text
点云 + 设备状态 + 辅助 IMU（有效性单独核验）
  -> 时间与几何有效性检查
  -> 姿态无关的点云候选 + 地面/背景关系
  -> 同场景三维位置与形状连续性关联
  -> WebUI 人工框选 -> 板端确认 track_id / 采集站姿基线，连续跟踪
  -> 地面高度、躯干方向、下降过程、持续低姿态
  -> 板端时序状态机 -> 状态 + 跌倒事件 + 证据
  -> WebUI 同源帧自动框 / XYZ与距离 / 标定状态 / 跌倒提示
```

锁定按时间、三维位置预测和距离门限做简单关联；多人交叉、合并、无法确定匹配时返回 ambiguous/lost，禁止自动换人。首版是人工确认的人体样点云目标，不是通用人体语义识别或姓名识别。track_id 是会话内目标编号，不等于身份。

跌倒检测不能用单帧“低于阈值”。先保留下降过程证据，再结合接近地面的低姿态与持续时间。蹲、坐、弯腰、捡物、主动躺下、遮挡必须作为困难负例。没有下降历史但启动时发现低姿态，输出 low_posture_unclassified；缺帧时输出 unknown。慢速滑落另作待验证情形，不能用快速下降规则声称全部覆盖。

低姿态特征来自点云高度分位数、几何主轴、距地面关系、水平范围与下降历史；主轴可能退化或翻转，须标无效，不能宣称获取人体骨架。零点/无效回波、家具合并、近地面背景扣除和遮挡是重点难例。仅几何无法保证区分主动躺下与跌倒，必须把误报与漏报边界写进评测。

## 4. 阶段与开发代码

| 阶段 | 工单 | 需要写的主要代码 | 通过条件 |
|---|---|---|---|
| A 数据可信 | HF-00～02 | 探测/采集工具、接口契约、时间归一与数据健康 | 点云/IMU 出流与字段证据明确；单位/同步按需求核验 |
| B 标定与候选 | HF-03～04 | 安装/地面标定、背景与候选包围盒/源帧快照 | 坐标可验证，站立与倒地均可成为候选 |
| C 锁定与事件 | HF-05～07 | 选择/基线回执、跟踪、时序状态机、ROS 输出 | 不换人、不把丢失当跌倒，状态与事件独立 |
| D 网页联调 | HF-11 | 现有 WebUI 框选、自动框、位置与跌倒显示 | 板端确认选择，框/点云对齐，断流显示未知 |
| E 实测与交付 | HF-08～10 | 页面与算法评测、两端性能、部署与审查 | RK3588＋浏览器联调可复现，审查通过 |

计划投入参考：数据/环境 2～4 工作日；标定/候选 4～7 日；锁定/事件 4～7 日；采集/评测/部署 5～10 日。属条件估计，设备接口、数据量和人工标注可能改变工期。按关卡推进，不能仅按日期宣称完成。

## 5. AI 工单分工与递交顺序

- **Luna**：HF-00 静态盘点、逐项数据清单；HF-08 固定验收规则后的测试样本、批量回放、结果表和证据索引。不得决定关键算法或为了通过而改断言。
- **OpenCode DeepSeek v4.1 Flash**：HF-01～07、09、11 的实现、测试、板上和网页联调。用户指定工单后由 Codex 通过 CLI 递交；按用户的 OpenCode 配置选择。
- **当前 Codex**：确定范围/契约，按 [CLI 工单闭环](CODEX_OPENCODE_WORKFLOW.md) 派工、跟进并直接读取回传，执行 HF-10 独立复核，续接范围内返工；输出通过、返工或待真机验证，不自动开始未授权工单。

Luna 已做静态盘点，OpenCode 已回传 HF-00 与 HF-01，两单均通过相应范围验收。HF-01 第2轮已修复 R1–R7，health/manifest 与共同规则冻结，state/event 仍为草案。HF-02 第3轮软件复审 PASS，R1–R5 全闭合，设备核验 BLOCKED。具体见 `REVIEW_LOG.md` 与 [冻结契约](CONTRACT.md)。下一步需补设备证据，现有软件无需重复派工；Codex 已接管直接读取回传/独立复审及必要CLI返工的流程，不启动 HF-03。

递交时先提交 `DISPATCH.md`、`WEBUI_SCOPE.md` 和对应工单。顺序：00 → 01 → 02 → 03 → 04 → 05 → 06 → 07 → 11 → 08 → 09 → 10。HF-00/01 已验收；HF-11 可以在 04/05 接口明确后分步准备，整体验收等待 07。HF-02/03 核验物理未知量，后续新增交互接口另行审查冻结。同一工作树一次只让一个 AI 写代码。

## 6. 验证数据与验收指标

采集点云、原始 IMU、设备状态、健康输出、配置/安装标定与独立人工标签。没有 TF 时在版本化标定文件明确坐标变换，不等待不存在的 CameraInfo/图像。PCAP 是否包含所需 IMU 与元数据必须实查；已有 captures 可用于点云回归，不能冒充跌倒标注集。测试集按人员、日期/场次划分，避免连续帧泄漏。

建议首轮至少 20 段有保护措施的模拟跌倒、100 段困难负例，加不少于 2 小时常规活动；具体实施由现场条件决定。不要为了采样要求真实无保护跌倒。标注事件起止、遮挡/可见性和目标身份编号，AI 可生成表格但最终标签需人工核对。

报告事件级召回率/精确率、误报次数/小时、漏报类型、报警延迟、锁定身份切换与有效观测时长。测量端到端延迟 p50/p95、输入/有效输出频率、CPU/内存/NPU 使用与温度。延迟计时须用可信映射或单机单调时钟。第一阶段先实测再冻结门槛；这些不是已有成绩。质量门槛由 Codex 与用户结合使用场景确认后写入契约，禁止执行者事后降低。

最终验收包含真实 WebUI：人工框选/板端回执、坐标与自动框随人更新、站姿基线成功/失败、跌倒/困难负例/未知状态、视角变化、旧快照/丢流/重连。分别记录 RK3588 算法处理率与浏览器显示帧率/延迟，页面流畅不能替代算法性能证据；用对应板端日志和网页录屏证明结果一致。

## 7. 官方参考

- [ROS1 Imu 消息定义](https://github.com/ros/common_msgs/blob/noetic-devel/sensor_msgs/msg/Imu.msg)：加速度 m/s²、角速度 rad/s；没有姿态估计应以协方差首元素 -1 声明。
- 原计划中的双目相机标定/视觉模型任务已撤出当前路线；未来增加相机须另开范围与验收，不沿用本次六轴 IMU 结论推断相机能力。

## GL-02 Claude R4 Codex独立复审 / 2026-10-01

R3原五方法5/5、R2七方法7/7、静态6/6、fall 271/271、follow 2/2、两个webui各18/18均由Codex独立实跑通过。新增reload/已有pending三方法3失败exit1：空或相同配套reload沿用旧版本却丢input.sha256/evidence/note等完整产物字段；已accepted基线请求在随后monitor持续不可用超过10秒时仍pending且无终态回执。软件REWORK，GL-03不放行；设备兼容NOT_RUN、真实物理BLOCKED。详[evidence/2026-10-01_gl02_r4/CODEX_REVIEW.md](evidence/2026-10-01_gl02_r4/CODEX_REVIEW.md)与57_*。手动下一步[AI_PROMPT_GL02_CLAUDE_R5.md](AI_PROMPT_GL02_CLAUDE_R5.md)；只修这两项，不自动派工。生产源码/原测试/driver差异/Windows软链接表示保留，未部署/采集/commit/push/reset。

2026-10-05 GL-V01 R2（地面身份纠错）已 SUBMITTED / NOT ACCEPTED。算法改为 `floor_detector.py` 从 FIT 点云自动发现最低近水平连通面并做完整高度障碍门，手选四 ROI 仅作独立对照；三个指定录制三估计器/留帧门 PASS，202456 自动↔手选参考差 1.586310° / 0.005015 m。详见 [唯一 v2](GLV01_ACCEPTANCE.md)、[提交 15](evidence/2026-10-05_gl_v01_r2/15_SUBMISSION.md)、[Luka 收口附记](evidence/2026-10-05_gl_v01_r2/21_closeout_luka.md)。GL-A～GL-I 在线/生产接管仍 NOT_RUN。
