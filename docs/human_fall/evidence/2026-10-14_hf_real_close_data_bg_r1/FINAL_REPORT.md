# HF-REAL 第一批闭环修复交付 · 2026-10-14

**完成授权范围内的开发、运行、证据与独审；三工单停在SUBMITTED/REVIEWED_WITH_FINDINGS。r04没有全表收口，v2没有正式启用，当前不能进入统一核心/离线页面集成实施。** 失败与缺人工GT/缺原数据分别保留。

## 当前版本与交付

目标D:/Code/ldiar，master @ c21c443b0befe559e08283edb0efc2af02dcc6b8，首尾HEAD未变。读取目标AGENTS、WORKFLOW、capture README、20261013计划、RETURN_TEMPLATE、ponytail。当前pointset r01作者登记Codex，已有完整报告/2605帧产物SUBMITTED；实时仅运行原pointset server，没有pointset运行器写入。它的未提交源码/证据与README外部差异保留。本轮没有pointset r02或real_fall r05，也没有模型/训练。

45d53b8已包含r04源码、前景、tracking、process及两图，但未包含最终报告与return。逐字节版本见CURRENT_VERSION_MANIFEST，旧证据保持只读。全树基线22438个regular files，含ignored/untracked，不含.git和symlink，0读取错误；首尾保护检查另见PRESERVATION_CHECK（不能把主动授权补丁称为零漂移）。Windows Python3.12.10 / NumPy1.26.4 / Node24.14.0 / Edge。不是板端性能或物理结论。

**实际入口有版本分叉**：本轮真实浏览器加载r04 server.py→旧r04 process.json；当前pc_apps/console/console_gui.py第51行仍指向 **r02**。未改控制台/EXE/ZIP，未伪称桌面入口已切到r04，ST01完整入口与ST08打包子项未闭合。原r04 server的“.50m torso-radius”误文案已改为实际“.55m种子圈外启动残留风险”。

交付文件：唯一补充ACCEPTANCE_V1、UNIFIED_INPUT_MANIFEST、CURRENT_VERSION_MANIFEST、metrics.json、逐帧JSONL、REVIEW_QUEUE、三张新对比图、真实浏览器截图/日志、TEST_RUNS、INDEPENDENT_REVIEW、三个工单回传及HF-REAL-04当前回传。所有新证据使用此新run ID，不写旧报告。

复现命令完整列在CURRENT_VERSION_MANIFEST；输出必须使用新空目录（工具wx/x拒绝覆盖旧证据）。rebuild会在captures/leveled生成全新UUID的派生结果，不修改原raw。算法/输入hash与配置均落盘。用户禁止生产行为、confirmed、部署、采集、训练、commit/push；本轮遵守。

## 三项任务状态

| 工单 | 已实现/已运行 | 自验/独审 | 未通过项 |
|---|---|---|---|
| HF-CLOSE-01 | 当前版本审计、逐ID检查、源行/节点/事件/浏览器、报告和入口记录 | 软件检查已自验；非writer独审已执行，有发现 | r04全表未收口；console实际r02；家具/人体/关节GT不足 |
| HF-DATA-01 | 9会话2605帧绑定审计、关联4段输入、索引/时间链、最小审阅队列和原页修复 | 8会话BOUND部分标注；读写漂移拒绝及真实浏览器PASS | S9 INVALID_BINDING；S8 ROI物理坐标待人工核对；人工审核未完成 |
| HF-BG-01 | 164+523帧同源隔离诊断、32+101空场留帧、真实配平/registration重算 | 重算与门控软件PASS；有界实验已独审 | 新registration REJECTED；v2静立/近地FAIL；家具身份BLOCKED；正式完整等价P A/B BLOCKED |

## r04实际修复与未收口

| 原ID | 实现/运行/当前自验 | 独审与剩余 |
|---|---|---|
| ST01 | 当前SHA/原数据/前景/source rows/直接r04加载已核验 | 完整入口FAIL：console源码仍r02；仅manifest绑定process，未改正式loader |
| ST02 | f0–4圈外稳定前景补背景已实现/已运行 | 圈外人体身份BLOCKED；前五帧为离线warmup，f0–3含启动未来信息，不称全164因果 |
| ST03 | 164/164目标候选观测；全源行XYZ最大误差9.41e-7m；97空场0锁定/0事件 | 实测事实PASS；空场self-reference限制；不是人体真实召回或低位纯度PASS |
| ST04 | raw xyz与display_xyz/灰色历史节点分开；1981/2132当前valid槽，37/2132显示保留槽 | 核心软件独审PASS；这不是1981个解剖准确关节；轴仍可短借历史 |
| ST05 | f72 /7.46027s唯一verified:false prototype；confirmed_enabled=false | seek/reset/暂停真实浏览器不增加固定事件；事件/跌倒身份未人工确认 |
| ST06 | 原r02/r04节点/跳变/轴/事件对照已运行 | 多数改善，TOP_REGION显示P95 **0.123399→0.130764m** 反而恶化，改善全称FAIL |
| ST07 | 时间驱动、复用、缓存、显示插值已实现，真实播放检查 | 本机requestAnimationFrame约144Hz（仅回调/渲染节奏，不是观测频率或板端性能）；原测量仍约10Hz |
| ST08 | 源行、低点、重复/逆序源时间、重复源行、长gap、非法API、真浏览器、HF06相关回归PASS | console实际EXE/ZIP启动/重建NOT_RUN；不能自行把整项PASS |
| ST09 | 只读独审完成且有发现；身份/关节GT与泛化BLOCKED、设备/物理NOT_RUN | 未ACCEPTED；r03 RS04争议未关闭 |

弱轴帧：f47当前1599目标点，12当前节点+1显示保留；f109当前1436点/12节点；f118当前1940点/13节点。三帧方向借用有界历史参考；有效节点的全部support_rows都属于当帧target源行，预测显示不计新增物理点。

家具是否误删人体仍不能判为安全：r04相对r02旧target总计少了 **12965** 源点成员，f10少144、f72少19（TARGET_COUNTERFACTUAL）。旧target和助手人区都是proxy，不能把少掉的点全部称家具或人体。r03 404/404落视觉人区只证明ROI重合；“重叠0”的旧报告句与其正文矛盾在新独审附记纠正，旧报告不覆盖。**RS04原FAIL不关闭。**

## 哪些可以评分

八个已有会话S1、S3-near、S3-far、S4、S5、S6、S7、S8，其meta/points SHA、标签SHA与session ID绑定核验成立，源行范围/重复/时戳检查完成；只有它们明确标注的帧和点可以算局部覆盖/保留。S1没有人体分母。人工标注含传播关联，非独立新人物/新场景真值。UNKNOWN仍UNKNOWN；所有完整点精度、身体部位精度、解剖关节精度为null/BLOCKED，不报“纯人体精度PASS”。

S9的GT_V1和V2只有64个a组成的points hash、没有meta hash；实际points为7d978a67…、meta为60ddb3d5…。已核对两个版本、对象帧/索引字段及现有来源。没有可信原始绑定恢复依据；不改SHA、不强绑、不评分。新录制不当作原S9恢复。

S8小ROI候选 **0/523帧**。示例已有人体参照入ROI比例0–0.28%，不是“全场无人”。原polygon/REF_RT不变，保持小ROI/全场两路，需人核会话布局/坐标；不得把截图ROI无声扩大。

缺源检索只在captures、gt_store、radar_capture_data命名根做了一次有界搜索：215623、215643、233658均无原points.bin→DATA_BLOCKED。另223757只有points.bin缺meta.json，不能构造原registration。215540实际源可读，原配平存在，但其233658参考缺失、姿态/场景不能与131958互用，本轮同源跨背景评分BLOCKED。093958继续DATA_BAD/地面不可观测，不降门接入。

既有“最佳簇覆盖”是GT选择的上界，已分开计算原页RF默认和PointNet选簇。例：S6 RF实际覆盖 **20658/27268=75.76%**，最佳簇 **26739/27268=98.06%**；S8 RF **57010/57045=99.939%**，PointNet **44083/57045=77.278%**。这些是已有部分标签和已开发会话上的覆盖，不是泛化准确率。页面现显示当前所选簇与GT上界，避免挑簇后自证。

## 背景A/B：结论与合法限制

复用extract_foreground、build_reference_map、extract_foreground_fused；同一输入/源行/REF_RT/ROI/XYZ聚类配置与评分器，未发明第四套融合规则。三路均在独立进程使用显式共同诊断workspace z≥-0.25m，保留近地失败可见；生产z≥0.1m配置未变。配平、薄地面身份/剔除（NOT_RUN）、人体身份（PARTIAL或UNKNOWN）分开记录。

**A不是生产现行P的完整等价运行**：现行build_static_map全录制背景使用未来帧并永久吸收动作，占据行为与本次因果要求冲突。因此A明确使用原P函数+仅过去最多10帧临时图；不称改好了生产P。B仅空场FIT冻结；C使用既有v2函数+同一临时在线上下文，标DIAGNOSTIC_ONLY。所有正式loader仍仅VALID可供融合，未改规则。全生产P精确A/B、独立审核空场/物理场景一致性均BLOCKED，不通过看测试集调门“解决”。

S1/131958按frame mod3 FIT/CALIBRATION/HOLDOUT，HOLDOUT不建图、不调阈值，C参考半径仍现有0.12m。HF094333→131958用历史0.9477静态区域重合与临时变换，仅隔离诊断；新的严格registration拒绝已经公开。S8→175227公共REF_RT也是待物理核验假设。

| S8部分审核点指标 | A原P函数/因果临时上下文 | B冻结参考 | C现有v2诊断 |
|---|---:|---:|---:|
| 人体前景保留 | 1324/57045=2.321% | **55347/57045=97.024%** | **54069/57045=94.783%** |
| 最大XYZ簇内人体覆盖 | 1096/57045 | 55331/57045 | 54063/57045 |
| 已标近地z<0.1m点保留 | 26/1163=2.236% | **180/1163=15.477%** | **4/1163=0.344%** |
| 所选簇未标身份 | 48912/50008=97.808% | **490193/545524=89.858%** | **477846/531909=89.836%** |
| 所选簇已标非人 | 0/50008 | 0/545524 | 0/531909 |

人点分母来自53个部分已标人体对象帧；所选点/UNKNOWN分母来自全523帧，两个分母域不同并已显式区分。S8缺完整非人身份标注，**0已标非人不代表0家具污染**。B/C相对A保留更多未标身份点，不能把这些都称家具，也不能当人体。原≥95%门不变，C静立FAIL；近地点不是完整“躺下不动”GT，但明确揭示近地保护失败。低姿态和家具污染无法判通过。

HF094333全部人体GT分母0，仅旧target proxy：A保留116422/373746，B373737/373746，C373624/373746。不是审核人点保留率。B/C全场前景分别1229545/765692点，比A264779增加；是否家具接管、多人合并与真实碎裂还需人工身份。逐帧结果对此标UNKNOWN，不捏造部位数字。

空场新独立帧留出：131958 FIT33/CAL32/HOLDOUT32，175227 FIT102/CAL101/HOLDOUT101；现有孤立诊断XY链各0候选/0确认轨迹观测/0事件发射，独审独立复算相同。这是同一录制交错帧的有限验证，不是跨录制/物理独立或长期每小时误报达标；亦不代表HF06 confirmed打开。原self-reference“最严空场”逻辑相反：参考更窄会保留更多点，自身参考只是泄漏下界。

## Artifact三个gate

| Artifact | 输入/参考/代码绑定 | 几何gate / loader实际状态 | W03人体资格 |
|---|---|---|---|
| 原223757→203349 | 缺223757原meta，参考图/方法漂移 | **STALE** | BLOCKED |
| 原215540/215623/215643→233658（三个） | 原参考缺失；后两者原源也缺；方法漂移 | **STALE** | BLOCKED |
| 新094333→131958 d5327a5f… | 新source/ref SHA、真实新配平、refmap、当前代码绑定成立 | **REJECTED** | BLOCKED，无审核身份GT |

新artifact不是重签：run_job重新冻结域、TLS/SVD/RANSAC、全帧export，随后原registration.js writeJob重跑fixedICP、细静态、normal、split-half ICP和现行gate。新配平job为04e9b3db32a143ccaf7c48945952a7a7 / 61cb6976b0f8479394641850d9a7c6ca（数值配平推荐TLS；不等于物理地面身份已核验）。

新几何数值：source static8452/target13330/correspondence3817；inlier **0.451609**，仍低于现行PASS .50；fit P50 **0.029691m**（warn）、P90 **0.105731m**（reject，原max .08/.10）；holdout P50 **0.024671m**（warn，原PASS .02）。原因RESIDUAL_HIGH/HOLDOUT_MISMATCH/SPARSE_CORRESPONDENCE。**当前registration VALID=0，DEGRADED=0，STALE=4，REJECTED=1**；历史DEGRADED不能写成当前状态。默认关与请求开时全部fusionKeys都不放行。

首次重算leveling因export要求basis字段缺失而失败，留下5fae8107b72943aa865901b9c069aace不完整派生目录（无manifest，不可加载）；在runner补真实basis后新UUID重算，不补写旧失败目录。旧223757重算因缺meta退出1。失败都保留，见RUN_LOG。

## 实际修复/检查/人工最小清单

本轮修复原审阅页：深链跳会话/帧、PROPOSED队列、oracle/runtime区分；保存端重hash实际source；保存回调固定提交时sid/frame/request/indices/part，仅页面绑定未变才涂色；读取端复用同一契约拒绝错误SHA/对象scope/PROPOSED/坏索引。来源漂移或读取错误清空旧对象/部位色，不显示前会话标签。AI未提交任何HUMAN_REVIEW，测试没有保存标签。

独审发现读取漏洞后做了一次定向返工，3契约与真实浏览器复验PASS。最终4契约（增加重复/逆序时间与截断源检查）、原6pointset、原20HF06，pipe38、registration23、replay45和panel全部退出0；日志逐命令。覆盖错误绑定、重复/空/布尔索引、低/无/坏输入、弱轴过期、显示不改raw、非法HTTP、seek/reset/pause。设备/物理/console打包NOT_RUN。时间跳变的完整播放状态机反例仍未独立涵盖，不能把弱轴超时测试代替完整事件时间跳变资格。

人工仍需：W03 **31个POINT**（7帧）与**155条COMPARISON_ROW**（97帧）分别审；九会话静立、遮挡、转身、家具粘连代表窗（REVIEW_QUEUE）；S8布局/小ROI坐标核对；S9可信来源恢复或新人工重审；HF094333全部164帧事件区间，优先0/4/10/18/20/40/47/71/72/73/108/109/118/130/163的成员、近地身体、可见部位/UNKNOWN。无需把所有未标点先判背景。队列工具已完成不等于人工审核完成。

**下一阶段条件：评估器与输入契约可复用，但算法资格和统一核心/页面集成实施门未达到。** 无VALID、C静立/近地失败、身份/家具GT未完备、console仍旧版本；当前停止本轮，不扩展新融合规则、不调低门、不启动HF-INTEGRATE-01、生产/confirmed/训练/板端。

## 后续开源参考（官方页面2026-10-14核对；未本地安装/验证）

| 路线 | 问题/输入域区别 | 依赖/许可/边界 |
|---|---|---|
| [PointNet++](https://github.com/charlesq34/pointnet2) | 点集层级分类/分割；通用物体/场景训练域不能直接当稀疏室内人体结果 | 原TensorFlow/CUDA自定义算子，MIT；本轮不训练 |
| [Human3D](https://github.com/human-3d/Human3D) | 多人实例与部位场景分割；合成/EgoBody与IFW稀疏激光域不同 | CUDA11.3/PyTorch/MinkowskiEngine等；所查看仓库未见独立LICENSE，数据/上游许可须另核；不引入 |
| [LiveHPS](https://github.com/4DVLab/LiveHPS) | 单LiDAR连续帧姿态/形状，SMPL输出；须验证时间因果和本地坐标 | 预训练/PyTorch/SMPL，代码MIT，SMPL/数据另有使用条件；公开演示非本地GT |
| [Patchwork++](https://github.com/url-kaist/patchwork-plusplus) | 3D激光地面分割；有限室内FOV/无可见地面的域须重验 | C++/Eigen/CMake、Python绑定pybind11；BSD-2-Clause；地面分割不等于人体识别/物理配平 |


最终保护核验：22438文件中22429保持，8项本轮授权源码/入口补丁，1项外部仍在运行pointset原服务的SERVER_STDERR.txt日志增长（已记录，不回滚）；0缺失/0读取错误，生产与原raw/GT/模型无漂移，HEAD未变。旧证据仅由本writer保持只读，不宣称外部运行日志全树静止。最后补队列链接保持当前服务origin，避免跳回旧8941；真实浏览器browser_final_verified复验PASS，旧失败日志保留。
