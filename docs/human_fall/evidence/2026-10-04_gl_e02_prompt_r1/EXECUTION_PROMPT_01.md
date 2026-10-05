现在执行 GL-E02 R1：有效 source 轴向、独立地面身份和现场证据包补齐。

工作目录 D:\Code\ldiar。你是本单唯一实现 writer；持续完成可审查提交，缺现场测量不阻本地证据工具开发。不要把本提示里的下一阶段目标自动扩展成拟合、设备操作或部署。

一、先读权威文件和最新实际记录
1. docs/human_fall/WORKFLOW.md 当前版本。
2. docs/human_fall/GLE02_ACCEPTANCE.md（唯一验收 v1，使用 E01–E06/S01/P01/D01/Q01–Q07）。
3. GROUND_LEVELING_NEXT_STAGE_PLAN.md、GROUND_LEVELING_ALGORITHM_DESIGN.md。
4. evidence/2026-10-04_mainline_evidence_r1/17_CLOSEOUT.md 及已核来源 sidecar。
5. evidence/2026-10-04_gl_i06_r1/41_CLOSEOUT_01.md、轴向诊断 REPORT.md，以及 evidence/2026-10-04_gl_axis_plan_review_r1/PLAN_REVIEW_01.md。旧入口仍写GL-I06未执行时，以实际收口为准；不追改历史。
6. 实际 load_adapted、select_group_region/gate_selection、_draft_region、ground.region_indices 及当前配置/producer，沿实际输入到消费者核查。
7. 实际读取 ponytail SKILL.md，并在回传记录实际路径。

二、纳入用户已提供的真实现场照片
稳定照片路径：docs/human_fall/evidence/2026-10-04_gl_e02_prompt_r1/scene_reference_01.png。
确认与SHA记录：同目录 PHOTO_EVIDENCE_01.json。
用户明确确认：“这是现场真实图，拍摄角度也是对的。”实际查看照片，承认场景真实性和参考视向已由用户确认，不反复询问这两点。

照片中的连续木地板用于地面身份核查；左右工作台、桌腿、右侧桌下箱体/板材、前景植物和设备属于障碍或遮挡线索。横跨地面的条状物/接缝附近先单列，不凭照片断定有无高度差。先提出同一侧连续、清晰可见木地板上的前/中/侧三个空间候选区域供源行对应核查；这是空间计划，不是已完成的三个validation。

分层记录：
- 场景照片真实、参考视向正确：user_confirmed。
- 照片中木地板及障碍的视觉语义：已观察，可作为人工地面核查依据。
- 照片拍摄时间、它与10月2日录制/安装/run/config的绑定：未提供的保持unknown。
- 照片像素→点云源行、相机→有效LiDAR source矩阵、精确安装角、source系world-up、点云原点高度：尚待独立证据，不能由“视向正确”自动填值。
不能用文件mtime当拍摄时间，不能凭透视图量绝对高度，不把26°粗估或拟合offset≈1.33m当实测。约1.1m是光学窗口位置，不是已核点云原点高度。

三、实现范围与写前诊断
建立实际 branch/HEAD、工作树及全部相关tracked/untracked SHA，包括未跟踪源码、原输入、照片、SDK/config与旧证据依赖；保留用户差异和Windows catkin表示。
在新的 evidence/<实际日期>_gl_e02_r1/ 先写00_diag：逐行映射唯一表及Q01–Q07到实际函数、输入身份、处理顺序和输出资格；日期按Asia/Shanghai，已有文件禁止覆盖。
最多三个新代码文件：core/ground_evidence.py、scripts/prepare_ground_evidence.py、tests/test_ground_evidence_input.py，可减少，不增加新服务/账号/缓存/外部依赖。纯算法部分保持stdlib+NumPy、Python3.8兼容。
旧ground数学、默认/冻结配置、driver、webui、HR、原bag/bin/NPZ、批准draft和历史证据只读；不reset/checkout/clean/commit/push，不连接板端、启停服务、改网络或设备配置，不采集或部署。

四、按此优先级补齐证据
A. 复用GL-E01来源链，校验实际文件SHA、source/frame/单位、recording window与源成员，不重复整个来源研究，不回填旧NPZ字段。
B. 沿SDK输出→publisher→bag→adapter确认有效source坐标，区分机壳朝向、SDK是否已施加R/t、实际消息坐标。查已有本地厂商资料/headers/config/run归档；当前配置或较晚日志不能证明旧录制。缺证据时列明确缺口，不自动翻X。
C. 独立记录up/安装方向及不确定度、点云原点定义和高度；只需地面局部配平参数，不把完整地图yaw、相机外参或IMU融合变成额外前置。未知项不由PCA补。
D. 用照片+独立场景身份与原始点云地标对应确认地面源行。若无标定相机外参，可采用有记录的人工场景/3D地标核查；不得把未经标定的像素自动转换为源行。
E. FIT只用单source frame；三个validation frame_group必须相互不同且不同于FIT，空间分布另列。照片里的三块区域不能冒充三个源帧。绑定原pooled/source row、frame ordinal/seq、source SHA、选择版本、确认人/时间及依据。

现有草稿解析→selector→fitter全链已支持显式indices；优先复用，不先改“非轴对齐ROI协议”。新点集合需独立确认并保存新ID/文件；不能按正在受验的FIT平面残差带选验证点、只点拟合着色好看的点，或删失败点再声称独立验证。区域混杂与地面不平等解释保持分开，不强行指定地面身份。

如果确需用户补资料，只集中询问仍缺的：照片与旧录制的时间/安装一致性，实际source/SDK变换绑定，独立角度/up与原点测量，场景地标到源行确认。先完成不依赖回复的软件工作；不能猜答。旧录制无法绑定时，写出未来受控标定录制所需材料清单，取得具体授权后另执行，不在本单启动采集。

五、吸收诊断复核，不沿错误方向实现
- 同原ROI、默认0.20/4，正X sampled80；负X WHAT_IF sampled140且转validation_failed。up会改变切平面采样网格；别先认定必须扩大ROI。
- AABB不必然混入非地面点；真实轴向和独立标签不足才是待核证据。
- 质心附近候选接近不足以证明同一物理面；不要改distinct_offset到0.15，或删竞争/预算未决。
- 平面稳定不证明传感器静止；拟合n/d不是物理up/原点高度。
- 本单不fit、不研究新比较口径、不重启K2/K3或IRLS扫参。照片能补场景证据，不直接赋ground.valid/candidate资格。

六、产物与集中验证
只输出pending_evidence_packet、measurement_record（含known/unknown及来源）、photo/source/ROI evidence_index、待审选择draft、轴向与地面身份缺口表。无资料仍允许结构合法的pending正例；不保存runtime calibration/ground_derived，不自动设置physical/extrinsics verified或ground.status=valid。
至少覆盖：缺/坏/schema/NaN/单位；同路径或ID异内容/caller修改；source/window/run/config错绑定；from/to逆向；光学窗口和原点混用；照片真实但无旧录制绑定；已知照片场景但源行未映射；ROI alias/重复/越界/跨组/同FIT组；已有out/保护目录；非法模型残差筛holdout；齐全但未审不能晋级物理资格。
软件E项与物理P01分开。照片确认作为已完成的证据子项计入，不抹成“什么资料都没有”；未补齐的物理链仍P01 BLOCKED，不能以字段齐全或E软件PASS闭合。当前89帧已曝光，只作开发/工程诊断，不冒称未见最终物理holdout。

七、提交停写和指定只读独审
逐E01–E06/S01/P01/D01/Q01–Q07报告PASS/FAIL/NOT_RUN/BLOCKED，不以测试总数代替。记录原命令/退出码、软件/物理缺口、首尾SHA、scope、相关回归与全部产物。
关闭日志后生成完整manifest，按RETURN_TEMPLATE追加returns/GL-E02.md，状态仅SUBMITTED/BLOCKED，然后停止代码写入。
独审前一次≤1min无工具probe，再交opencode-go/deepseek-v4.1-flash/defaultDB实际只读独审；失败不改model/DB/auth/权限，不伪报独审。
检查源码/输出/报告每次修订必须新编号，禁止同名Edit。已有冻结检查应只读执行到新编号输出目录，最终模型判定可直接保存在CLI流，避免GL-I06独审同名覆盖的历史流程错误。
本单完成后停止，不自动进入P2拟合、GL05设备验证、正式网页合并、采集或部署。
