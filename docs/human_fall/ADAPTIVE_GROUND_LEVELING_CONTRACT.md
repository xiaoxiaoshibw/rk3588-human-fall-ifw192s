# Adaptive Ground Leveling 接口 / 状态 / 配置契约 v1（设计）

状态：PLAN_READY，IMPLEMENTATION_NOT_RUN。来源：[最终计划](ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md)、当前geometry/GL-P01/WORKFLOW与本次用户要求。该文档定义新增分支，不改旧冻结契约。经典TLS/SVD/RANSAC不宣称原创。

## 1. 数值、资格和所有权

- 单位m/rad，诊断显示deg字段带后缀。source→display列向量p_G=Rp_S+t；R=Rx(roll)Ry(pitch)、yaw/tx/ty=0，pitch=atan2(−nx,nz)、roll=asin(ny)。单位normal n_S、offset d_S，t_z=accepted observed d，不用d/nz。
- 归一化时normal和offset同除norm，翻转符号时同时取负。norm近零/非法值拒绝；符号与有provenance的anchor对齐，方向歧义拒绝，不无依据叫world up。
- physical_height_m=1.14（laser user measurement）；observed_tz_m是独立数值。任何自动算法不得覆写物理值/测量来源，不自动physical/extrinsics verified。
- 研究kind=`adaptive_ground_leveling_proposal`，算法accepted仅指通过内部显示接受门；不得冒用旧geometry_calibration/coordinate_ground kind。physical_verified/extrinsics_verified/runtime_eligible默认false。GL-I单独处理实际应用scope，score不得改资格。
- 输入owned numeric snapshot：调用者可变对象深拷贝，结果独立副本，不保留可写共享引用。纯core无ROS/文件/clock隐式读取。配置、point domain与frame版本由外层显式传入，禁止模块内各自重新筛点或采样。

## 2. 统一记录

| 记录 | 必需字段 / 类型与意义 |
|---|---|
| FrameKey | stream_instance_id、session_id、reference_epoch、ordinal/seq、source_frame、source_stamp、time_domain；字段不能混来自另一帧 |
| PointDomain | kind/schema、FrameKey、selector_id/hash、config_id/hash、units=m、canonical source_points N×3 float64、source_indices int64、region_codes、weights、point_sha/domain_id、selection_reasons、source_provenance、spatial_basis；shared domain是实际字节内容绑定，不仅用户给的名字 |
| PlaneEstimate | estimator_id/implementation_version、FrameKey/domain_id/config_id、normal_source、offset_source_m、pitch_deg/roll_deg、raw_support_mask可选、hypothesis_count/resource_complete、full_residuals/quality_ref、confidence、valid、reject_reasons |
| QualityReport | full count/finite/input-invalid count、RMS/P95/MAD、inlier_ratio(threshold_m)/support_count、per_region full stats、spatial_coverage、condition_metric、normal_plausibility、score_components、hard_gate_results、valid/reject_reasons |
| ConsensusReport | frame/domain/config绑定、pairwise[{a,b,angle_deg,offset_gap_m,pitch_gap_deg,roll_gap_deg}]、status、supporting_estimators、supporting_families、numeric_check_ok、selected_estimator、confidence_cap、reason_codes、update_candidate_allowed |
| FilterProposal | candidate(raw)、window_median、ema、rate_limited pitch/roll/observed d、dt及来源、raw_delta/accepted_delta、cohort ID与distinct count/duration、clipped/rejected标志；不是accepted |
| GroundLevelingDecision | kind/schema、state、consensus、raw/final confidence(score_kind)、FrameKey、controller_epoch、accept_revision、candidate/filter proposal refs、update_allowed、applied、fresh、last_good_age_s、freeze_latched、eligible_for_geometry、reason_codes、FinalTransform/null |
| FinalTransform | transform_id（R/t/frame/reference/config内容绑定）、from_frame=source、to_frame=ground_adaptive_display、units=m、R/t、accepted pitch/roll/observed_tz、parent domain/config/selector、accepted_frame/time、source of evidence、scope/mode、measurement_reference、physical/extrinsics/runtime flags |
| StateTransitionEvent | event_schema、event_seq/id、timestamp/time_domain、本地monotonic tick、FrameKey或null+last_frame、old/new_state、causes、current/previous transform/version、values/scores/limits、action、applied |

数值严格拒bool/string伪数值、NaN/inf、形状错误、反射/非正交R、不支持schema、frame/units/版本错配、重复/越界源行。invalid估计的normal/offset/角可null；confidence=0、valid=false、有明确原因，不用零角identity补齐。诊断候选与应用transform字段分开。

分阶段实现时额外记录numerical_valid和quality_status。GL-A只有数值适配器时可numerical_valid=true，但quality_status=NOT_EVALUATED、confidence=0、valid=false、reason=GL_QUALITY_NOT_EVALUATED；GL-B完成质量检查后才可valid=true。不能因为后续模块尚未实现而提前伪造高confidence/应用资格。

PointDomain允许每帧域内容变化且domain_id随之变化；静态compatibility key是stream/reference/selector/config/units/frame/weights策略。不能把每帧新point_sha当重标定epoch，也不能跨不同配置共享历史。source session切换默认打断连续性，除非有明确同stream兼容映射及原时间gap证明；A/B/C不能凭顺序当连续相邻帧。

## 3. Estimator接口与same-point-set

规划pure接口：`estimate_tls(domain, config)`、`estimate_svd(domain, config)`、`estimate_ransac(domain, config)` → PlaneEstimate。同owned points/weights/domain/config；不各自range gate/cap/ROI重选。TLS covariance-eigh与centeredSVD应给相同正交LS答案（在数值容差内）。RANSAC允许内部三点抽样/支持mask，但返回结果质量对**共同全域**算，不让TLS/SVD改吃其inliers。

三薄适配器分别放estimators/tls.py、svd.py、ransac.py，共享记录在contracts.py，调度在独立runner；数值核心可复用冻结模块，不为文件拆分重构旧production。新框架quality/consensus/temporal/controller/transform与适配器分开，避免一个文件或函数承担全部算法。

第一版明确沿用raw RANSAC；如以后要精修，必须记录estimator_variant、实际fit成员/weights、统一比较域与版本，不能混入旧表。一次frame截止时慢结果标GL_RESOURCE_LIMIT，不把上帧残留结果凑三算法。

Geometric pre-filter先处理单位/finite/zero/range/公共sensor artifact，选择策略和所有删除计数入domain。第一版使用版本化四区selector与已有ground hints；独立test/holdout的行域不能由待验plane残差选择。目标/箱子排除策略若加入必须有独立来源与统一domain；不让当前估计的好看程度决定自己的验证集。

自动角度估计的前提是存在可识别的地面候选域；不承诺在任意未知场景自动识别物理地面。初始化角搜索按max_pitch/max_roll的source-frame域，不把当前26°±旧fitter15°先验当作新自适应算法绝对边界。当前四区在名义显示系定义，对新安装不能默默照搬：使用已版本化的可信source indices/区域，或有独立ground hints的有界candidate模式；地面身份/coverage未闭合时HOLD/继续ACQUIRING，不靠换ROI self-fit自证。大安装重置需新selector epoch，10/26/45°合成角度测试须先给独立已知地面域，不能把旧26°rectangle误当通用ROI。

## 4. Quality与confidence

统一inlier_ratio=全共同域中|n·p+d|≤inlier_threshold的比例；TLS/SVD也输出这个support量，不伪称其运行了RANSAC。RANSAC内部hypothesis support另有字段，两个分母公开。RMS/P95/MAD使用未裁剪全域与各必需ROI；不能以inlier残差替代full residual。

condition_metric取centered covariance eigenvalues λ1≤λ2≤λ3，保存λ2/λ3（二维展开，检测线）、λ1/λ2（厚度/planarity），或SVD平方得到相同指标。点数/占据格/切平面跨度/每区支持/最大单格占比一起检查；λ2≈0的线状或极窄域，即使RMS≈0也invalid。

coverage使用固定版本的source tangent basis（来自明确seed/reference），在分米/米单位网格计算；不能用camera pixels或原sourceXY默认当水平世界坐标。若改变basis，版本变化并重新核profile。四区有效支持不足所需数、仅一条带、多面竞争无法证地面，hard reject。

归一化q(x)：lower-is-better用clamp((reject−x)/(reject−soft_good),0,1)，higher-is-better用clamp((x−hard_min)/(soft_full−hard_min),0,1)；阈值严格有序、分母非零。全域和最差必需区域共同约束，不能总体平均掩盖局部FAIL。

confidence_geo=Σw_jq_j，仅hard gates都过时可非零。C_consensus_factor=1/≤.7/0按GOOD/DEGRADED/BAD；C_temporal由cohort std/range与对上次接受变化给出，跳变/坏dt为0。final confidence=min(支持簇各有效成员geo score)×consensus_factor×q_temporal，并按相关性cap；字段`confidence`永远解释为启发式指数，禁止写“真实正确概率92%”。bootstrap时prior_available=false，q_temporal来自pending连续cohort而非伪previous identity。

所有soft/hard参数同样入配置，包括soft_good_rms_m、soft_good_p95_m、soft_full_support_ratio、soft_full_points、soft_full_occupied_cells、soft_full_lambda2_lambda3、max_single_cell_share、min_tangent_extents_m、normal_margin评分与cohort_std_good/reject。初始soft参考可用.01m/.02m/.95/2000点/20格/.10；跨度/单格share/normal-margin/cohort误差门在GL-B/D预注册profile，未完整合法profile不能运行，生产前必须F/H批准。

## 5. 仲裁图与相关性

normalize/flip符号后才算pairwise；点域/weight/frame不同→GL_POINT_DOMAIN_MISMATCH，不能算好一致性。pairwise既保存角和d，也存pitch/roll差；asin/atan2使用已校验n，禁止默认角sign自行变换。

GOOD：3valid，TLS/SVD数值自检OK，全部pair满足good门，geometry/逐区门均过。DEGRADED：最大一致簇size2或3仅过degraded门；BAD：无size2簇/簇冲突/非传递链无唯一选择/硬门失败。选簇以valid、cross-family、min质量、固定tie-break为明确顺序，不自动更换阈值。

TLS/SVD同属LS家族；TLS/SVD-only支持可以输出DEGRADED，但update_candidate_allowed=false。RANSAC-valid分歧时保留鲁棒冲突原因，不能二票压一票。跨家族RANSAC+一个LS可输出DEGRADED候选，初始profile仍不bootstrap，且degraded_updates_enabled=false。后续F证明必要收益才启用已有STABLE上的有限慢更新，不改此相关性规则。

## 6. 时间状态与接受事务

controller持有state、compatibility_epoch、pending窗口/cohort、EMA state、last_good（最近实际应用的已验证显示模型）、accept_revision、last_valid_input_time、manual_freeze_latched。所有改变经单一`process_bundle`/`on_tick`事务，无估计器单独写状态。

cohort接受需要distinct FrameKeys、递增stamp、连续性gap≤配置、同static compatibility key、window内normal/offset稳定及score/consensus门。重复帧不计数、不刷新age，记GL_DUPLICATE_FRAME并清pending；ACQUIRING保持未接受，已有accepted的STABLE/DEGRADED/RECOVERING转HOLD。错序/坏timestamp/gap也重置pending。dt来自受审同流source stamps；独立monotonic tick只用于无帧timeout与age，不能混入角rate的source dt。

INIT无accepted；ACQUIRING累积；STABLE正常门控更新；DEGRADED仅合格跨家族且profile允许才慢更新；HOLD不改accepted；RECOVERING第N−1帧前不更新。ACQUIRING/RECOVERING同时满足frame数与min_duration。HOLD age>max_hold_age：numeric可显示，但fresh=false/eligible_for_geometry=false，传给geometry消费者的有效模型为空/失效，不假装仍可靠。

last_good是最近真正应用的通过门的transform，包括经批准的DEGRADED慢更新，保证HOLD保持当前画面逐位不变。诊断可记录上一次CONSENSUS_GOOD，但不能在HOLD把应用值回退到它造成跳变。bad/REJECTED帧不更新任何EMA/last_good/accept_revision；窗口只存validated候选。

raw跳变达到5°候选门或offset突变达到门→HOLD；rate limiter不把它变成慢慢可用的更新。≤pending_rebase_max的小持久变化走新cohort恢复门，确认后再限幅，支持机械微移；更大/语义改变需manual reinit。max轴步长+组合角/rate共同限制，不按名义FPS偷算dt。d与角共同平滑并复查新的固定accepted plane质量，失败整笔拒绝。

提交事务：输入绑定与schema→quality→consensus→candidate cohort→filter/rate→properR/固定域残差→资格/safety→生成完整R/t/IDs→原子替换last_good+revision→日志。输出/caller随后改动不污染内部；任务超时晚到的旧bundle不提交。坏reload原配置不变；合法新配置/ROI/reference rebase清cohort/旧资格，manual freeze不被自动清。

manual disable/freeze在所有状态立即生效；freeze显式unfreeze仍需RECOVERING，不可一帧变STABLE。旧GroundMonitor latch不属于这个controller，单次新GOOD不能“治愈”旧标定失效。

rollback是独立受控命令：校验获审的固定release/profile与source绑定后原子回退、停止adaptive接受、清pending；不是对原始PCAP/测量的回滚。失败保留原完整应用状态或安全disable，输出GL_ROLLBACK_FAILED，不能半切换；任何未满足启用门的命令输出GL_ACTIVATION_REJECTED并保留原因，不改raw/calibration/driver。

## 7. FinalTransform与消费者

规划`solve_display_transform(accepted_plane)`/`apply_display_transform(points, model)`；复用properR/inverse/strict numeric。R/t、accepted frame、parent domain/config/selector/measurement_reference须完整同版本。producer R/n/d/pose互相不一致即拒绝。

API区分：`transform_available`（数值可渲染）、`fresh`、`update_allowed`、`eligible_for_geometry`、`physical_verified`、`runtime_eligible`；它们不等价。初始离线/shadow输出后两资格false，不挤入GL-P01旧消息kind或旧calibration字段。

每次接受有transform_id/accept_revision；reference_epoch用于影响既有缓存/基线的重定基准。GL-I必须处理旧消费者的版本绑定与失效/重投影，点/实际点AABB/投影/选择状态同frame+transform ID。不自动拿ground transform变化当目标移动；锁定/站姿采集期间首版冻结接受更新。正式geometry接管另需物理/作用范围/消费者门，不因显示输出成功开放。

## 8. 并行、性能和故障

规划EstimationRunner发三独立任务，共享只读owned PointDomain，最多3worker、1inflight batch、1pending最新帧；frame全部结果或deadline形成一个bundle。共享state只在controller线程更新。不能混帧，不能在deadline后补改已发布帧。future.cancel不保证停止已运行NumPy，未回收任务时不无限提交新任务。

默认无在线性能保证，GL-H目标机比较串行/并行、BLAS线程、memory及pipeline额外延迟。任何resource incomplete必须显式invalid/GL_RESOURCE_LIMIT，队列满/drop/gap日志会影响连续性计数。调度不能改三算法点域；需要共同point cap时先新profile/source indices/seed/统计验证，不自动改P02冻结数据。

fault priority：schema/domain/time/epoch错误→地面语义/几何退化→估计器invalid/数值冲突→共识→跳变/速率→age/手工控制/资源。一个primary_reason+全部reason_codes，state转换和accept/discard/reset都有精确事件。GL_RATE_LIMIT action=LIMITED_STEP和GL_ANGLE_JUMP action=REJECTED可区分。

## 9. 配置与授权

配置只在YAML/JSON新命名空间，first implementation不改冻结default/geometry/perception/human_fall_prod。schema_version/profile_id/SHA/approval/evidence_ref必需。出厂候选DRAFT/offline_only/runtime_enabled=false，缺完整参数或合法profile→拒绝运行；已批准active profile不能被未审DRAFT覆盖。

alias max_delta_angle_per_second/max_angle_rate_deg_s若同时存在必须相等，只给一项规范化入immutable配置记录；程序内仅一个有效值。所有阈值/weights/budgets的units显式。max_hold_age>0，max_gap>0，window奇数≥3，acquire/recover≥window，min_duration>0；min≤soft_full、good≤degraded、alpha∈(0,1]。frame_budget_ms=null允许离线规划，禁止shadow/active启用。

planned feature不授予运行/采集/部署权限。GL-H与GL-I必须分别有后续明确授权与真实证据；新配置/格式需遵循原WF独立审查，不覆盖旧histories。未知保持unknown、缺实测NOT_RUN/BLOCKED，不为完成计划改状态。
