# GL-01 R2 独立复审 REWORK / 2026-10-01

R1 CLI因API HTTP400中断exit1，尚无回传；最小指定模型探针MODEL_PROBE_OK/exit0，故可同工单session ses_f091fc094ffejMiiPuJRmuRoFU续接。不得换模型或新建重复实现会话。

现有本地/板231测试通过不足以验收。Codex独立codex_boundaries.py实跑6方法、9失败；原失败10_*保留，不改弱测试。修复下列问题，再跑同脚本和全回归/板端隔离兼容，补returns/GL-01.md。

1. 缺fit_frame_group/各validation frame_group仍可status=valid；region_id重复仍可valid。缺失/错误类型/重复/重叠元数据须明确invalid或ValueError；不能把空元数据作为独立验证。至少3区域，逐区检查，不允许相同区域冒充3区域。所有源索引一维严格整数（混入bool会被NumPy提升，须在转换前拒绝）。
2. _unit_vector/_height_interval仅检查纯bool dtype，混合[True,0.,1.]被转换接受；混合bool及字符串/非法类型须逐项拒绝，并检查单位轴约定而非静默造先验。seed负数、max_candidates>3、hard_cap>2000、eigenratio>1当前接受，违反冻结参数范围；修严格上下限/相互关系。不得静默min截断不足预算，min_inliers/区域最小值也不能低于获审协议。
3. max_candidates=1可把等支持的floor/desk竞争变成valid，独立反例已失败。候选截断/去重不能隐去歧义：保留有界的竞争证据或明确截断时拒绝/待确认；仅把K设小不得假成功。raw refine前截断也需有适当拒绝标志，不能称被丢弃的候选已被排除。
4. validate_constrained_ground接受声明valid但validation_regions=[{'passed':False}]的损坏产物。至少校验settings/up_axis/高度区间、region_id/group/数量/indices互斥、逐区RMS/p95/support门槛与passed一致、候选/预算上限；旧validate_ground_plane路径行为保持。CLI build_geometry_calibration只校旧字段不足以保护新constrained_ground，写出前调用新的严格验证。
5. holdout cap算法max(minpoints,cap//regions)可在区域很多时超过10000或每区预算不足却处理成功；在cap不足以为所有区域提供>=20点时明确失败。实际采样和原样本索引/点数分清；对已声明的不足区不能跳过后仍叫完整通过。
6. CLI --fit-region与--fit-indices同时提供目前忽略后者，必须互斥。ROI/分组JSON应记录SHA和内容元数据，确保产物可复现。现load_points_from_bag返回过滤后汇总数组且不保留seq/原点索引，不能把global decoded index冒称原bag source index/真实帧组；本单仅批准合成原型，可以明确拒绝constrained --bag并列真实来源适配BLOCKED，不以人为字符串组名冒称真实分组验证。旧bag路径保留。
7. 检查缺地面测试是否因fit/val重叠提前失败，必须有真正不重叠无地面样本和预期reason；“normal None”不能证明跑到无地面分支。15_manifest.json的ground.py hash键误变L_group_leak，修诊断生成器的变量复用并保留R1失败原文件另存R2产物。

范围仍ground/标定CLI/独立配置/相关测试/本单证据，geometry.yaml/default.yaml/UI/runtime/tracking等冻结。R1/API失败/板端首次缺sibling环境失败保留，R2证据独立写，不覆盖旧版本。实际源码SHA、命令、inner/outer退出码清楚；物理BLOCKED，雷达向下看为最新事实（角度未知），1.1m不作为夹具真值。不自行GL02。
