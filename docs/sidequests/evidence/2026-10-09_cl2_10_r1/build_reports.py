"""Source-grounded diagnosis report, compact audit bundle and raw regression summary."""
import numpy as np
from prepare import E,load,save,sha,C

ab=load(E/'02_shadow_ab_results.json');rep=load(E/'01_reproduction.json');catalog=load(E/'00_input_catalog.json')
target=ab['target'];case=ab['sessions'][target];original=rep['sessions'][target]
rows=case['baseline']['holdouts'];base=rows[0]['regions']['2'];scalar=original['independent_scalar_holdouts'][0]['regions']['2']
frames=rep['target_frames'];gx=[f['regions']['2']['geometry']['gradient_x_m_per_m'] for f in frames]
corrs=[f['regions']['2']['geometry']['corr_x'] for f in frames]
fit_table='| ROI | FIT 点数 | FIT 份额 | tangent 展布 m | local-to-common 夹角 ° |\n|---|---:|---:|---|---:|\n'
for i,g in original['geometry_fit'].items():
    fit_table+=f"| {i} | {g['count']} | {g['fit_share']*100:.3f}% | {g['tangent_extents_m']} | {case['variants']['C_LOCAL_PLANES']['planes'][i]['angle_to_common_deg']:.4f} |\n"
hold_table='| 第72帧 ROI | 点数 | signed mean mm | signed median mm | RMS mm | P95 mm | P99 mm | max abs mm |\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
for i,s in rows[0]['regions'].items():
    hold_table+=f"| {i} | {s['count']} | {s['signed_mean_m']*1000:.4f} | {s['median_signed_m']*1000:.4f} | {s['rms_m']*1000:.4f} | {s['p95_m']*1000:.4f} | {s['p99_m']*1000:.4f} | {s['max_abs_m']*1000:.4f} |\n"
ab_table='| 固定 ROI2 / P95 mm | ordinal72 | ordinal144 | ordinal217 | 资格 |\n|---|---:|---:|---:|---|\n'
ab_table+='| 原 TLS | '+' | '.join(f"{h['regions']['2']['p95_m']*1000:.6f}" for h in rows)+' | 原失败保持 |\n'
for key,label in [('D_ROI_EQUAL','ROI 等总权重'),('D_FRAME_EQUAL','帧等总权重'),('C_LOCAL_PLANES','四局部平面')]:
    ab_table+=f'| {label} | '+' | '.join(f"{h['regions']['2']['p95_m']*1000:.6f}" for h in case['variants'][key]['holdouts'])+' | 仅诊断，不可放行 |\n'
delta_table='| 第72帧 ROI | 原 P95 mm | ROI 等权 P95 mm | 原 RMS mm | ROI 等权 RMS mm |\n|---|---:|---:|---:|---:|\n'
for i,s in rows[0]['regions'].items():
    alt=case['variants']['D_ROI_EQUAL']['holdouts'][0]['regions'][i]
    delta_table+=f"| {i} | {s['p95_m']*1000:.4f} | {alt['p95_m']*1000:.4f} | {s['rms_m']*1000:.4f} | {alt['rms_m']*1000:.4f} |\n"
joint=load(E/'01_gate_cross_checks.json')[target]['joint_geometry']
channel=load(E/'01_channel_diagnostics.json')['2']
target_record=next(r for r in catalog['sessions'] if r['sid']==target)
import os
raw_size=os.path.getsize(target_record['raw']['points.bin'])
root=f'''# CL2-10 根因调查 / 2026-10-09 Asia/Shanghai

**结果 BLOCKED：数学拒绝机制可复现，真实物理成因未唯一识别；没有最小算法修复候选。** 当前数据缺原现场表面身份/几何 GT 和本地原 bag，不能证明点云结构由真地面、测距偏差或内部混合表面中的哪一种造成。

## 文件、格式与 STEP0 交接

目标 {target}，218 帧、10,708,741 原记录，points.bin {raw_size} bytes。XYZ 为 little-endian float32 / 28B stride，intensity offset12、ring uint16 offset16；metadata 是 JSON，FIT/holdout 来源域是七数组 NPZ。使用 NumPy/stdlib 只读解码；源 SHA/文件位置在 00_input_catalog.json / 00_baseline.json。

08/09A/09B/09C 实际报告、补丁、测试记录及原 CLUSTER-01/09C return 已读取；manifest 85/97/164/126 项逐 SHA 通过。main master/347a5bf… 和已有 dirty 差异只是上下文。执行用本轮复制的 09C SHA d0b3e31395543e495cb2bcc8307c90baaabc48dd6f5bca780039e052744c7b55，主树生产 selector 仍是 92d2ed…；**未集成 09B/09C**。

既有 CL2-10 单独规划文件未找到，09C 的历史记录禁止自动开启集成；本次用户明确赋予 CL2-10“残差归因”新范围，不改旧记录、也不执行此前建议的运行链路集成。

准备失败均保留：第一次正常域不在 cl208audit overlay，停止复制后在原历史作业找到且匹配原 manifest domain_sha256；第二次沙箱阻止外部 worktree 的 Git cwd；第三次 GIT_OPTIONAL_LOCKS=0 只读状态/文件 SHA 冻结成功。没有用不同数据掩盖失败或覆盖先前副本。

## 原失败与统计口径

四 ROI 是历史名义 display 半开 XY 盒；名义26°/0°只用于原行选择和法向方向锚点，历史1.14m只是未验证参考，不参与 TLS 平面估计，不当点云原点高度 GT。实际 TLS 源法向为 {case['baseline']['normal_source']}、offset={case['baseline']['offset_source_m']:.15f}m。单位法向 signed residual=source_xyz·normal+offset，P95 为绝对残差的原线性插值分位。

原 FIT=136942 点，固定留出72/144/217不进任何实验拟合。全部11段的七数组从原 bin 精确重建，源行/FIT/留出互斥；原 finite/nonzero 排除规则保持，未加 Z/强度/通道过滤或更换 ROI。三个留出共1915点。

{fit_table}
{hold_table}

第72帧 ROI2 有 {base['count']} 点，5cm 内284点，16个尾点（正7/负9）。RMS={base['rms_m']*1000:.6f}mm≤30mm、支持率={base['support_ratio']:.10f}≥0.8，但 P95={base['p95_m']*1000:.9f}mm>50mm。独立标量点积/排序得到 rank {scalar['rank_zero_based']}，邻值 {scalar['lower']*1000:.9f}/{scalar['upper']*1000:.9f}mm；低端邻值本身已超限，非浮点擦线误判。

固定原门重算拒绝原因为 GL_HOLDOUT_QUALITY，与原报告完全相同。全 FIT/其他ROI通过不能覆盖留出逐区失败。七超限帧仍为72/107/112/126/127/139/171；后六个为描述性诊断，不改原三个留出或增加新的验收条件。原有效导出仍没有生成。

## A/B/C/D/E 假设与证据等级

| 假设 | 本轮证据 | 裁定与未识别部分 |
|---|---|---|
| A ROI 几何/分布 | 联合 lambda2/lambda3={joint['lambda2_lambda3']:.9f}、展布 {joint['tangent_extents_m']}m，原0.01/0.1m退化门不触；ROI2 占FIT46.705% | 全域退化/点数不足不是这次触发原因。原点集非均衡、区域身份与局部形状仍影响共同解；未通过换区避开问题。 |
| B 姿态/坐标 | 固定行域配套旋转±1°/平移[.1,-.2,.3]后距离差≤8.9e-16m；源码 R[2]=unit normal、正交和 signed-distance 关系一致 | 数学刚体坐标表示不能消掉固定点集的非共面结构。未验证真实安装姿态/外参；不以该控制排除 ROI 选择对应或真实物理误差。 |
| C 局部模型失配 | ROI2 FIT 局部法向差15.3384°，FIT-only 局部平面预测固定留出，三个 P95降到38.30/36.49/36.35mm，所有原点保留 | **确认共同平面模型与测量局部几何不匹配的数值贡献。** 四局部平面不是一个刚体TLS变换；无法确认此局部形状是真表面还是传感器/混合回波造成。 |
| D 密度/噪声/尾部 | ROI等总权重将72降到49.77mm，却把144升到51.16mm；帧等权72仍50.292mm；ROI2共{len(channel['ring_groups'])}个ring、所有点所在5cm格均有多ring | 密度改变会重新分配残差，未消除全部留出失败。frame数量权重不是有效修复。ring/XY/入射/表面混杂，不能仅凭相关性认定某通道故障；没有删尾点。 |
| E TLS/统计实现 | 独立 centered SVD 最大 FIT 距离差 {case['independent_SVD_max_FIT_residual_difference_m']:.3g}m，三个留出12区独立标量RMS/P95复算一致；11段原门重现 | 当前域未发现 TLS 求解、单位化、P95口径或拒绝链错误。不能把这项数值审计扩大为原bag解码/现场真值证明。 |

证据分层：E1=原始行绑定+独立计算的直接数值证据（强）；E2=预注册单变量算法/坐标反事实（强于关联，但只证明计算机制和给定模型下的贡献）；E3=独立真实几何/点身份/设备干预证据（本轮缺失）。真实物理根因仍 UNKNOWN，不将 E2 投影或重权重叫作真实几何修正。

全218帧 ROI2 X梯度复现范围 {min(gx):.6f}–{max(gx):.6f}m/m，中位{float(np.median(gx)):.6f}；corrX范围{min(corrs):.6f}–{max(corrs):.6f}。残差正负与空间关系及每帧四ROI完整 mean/median/P95/P99/max/几何在01_reproduction.json。持续结构支持局部模型贡献，**不能以梯度存在推断唯一原因或充分性**。09A 的正常同盒反例仍有效，本轮正常会话使用各自原ROI，不能把同一ROI编号当同一地面位置。

## 单变量对照与失败假设

{ab_table}
{delta_table}

ROI等权不只发生 P95 转移：第72帧 ROI2 RMS27.418→27.708mm、ROI3 RMS11.066→13.120mm；全FIT RMS22.383→22.541mm。原等权 TLS 已最小化同一点集的全域平方正交误差，改变 covariance 权重不能称为整体真实几何改善。两个正权重实验的每个FIT点权重均>0，所有评价点仍等权、数量保持；但算法目标变化，不满足当前 raw TLS/SVD 数值一致契约，故不作为新有效TLS候选。

局部平面确实降低原单位点面距离，但被测模型是四个平面而非原单平面，不能拼成一组 R,t 去替代验收或拿到“TLS PASS”。此结果只定位失配机制，不修原数据、GT或评价门。刚体控制、SVD替换和frame等权未带来有效改善，失败假设明确留存。无按目标SID/帧号的修复路径、无根据P95调权重搜索。

## 回归、跨样本与当前停止点

全部10段既有 TLS-valid 会话从各自原bin/domain/ROI复现原TLS所有门与标量留出统计，仍valid；114754仍valid但NO_RECOMMENDATION，不把TLS有效当三方法推荐。固定策略对全部11段的实验结果在02_shadow_ab_results.json，FIT与holdout从未混合。这些是不同capture、但可能同一现场；历史验收已读，非盲测，也不能证明物理误差已泛化修正。

46项-W error通过：35项09B冻结回归、6项09C差分、5项诊断机制检查。无新算法修复，故“修复后泛化”NOT_RUN。09C搜索源码逐SHA未改、关键100格输出与原oracle精确一致；单次时延比旧中位数高，正在以当前同进程原09C源码做配对对照，最终数值单独记录，不直接宣称异常算法退化或板端准入。

本轮 T107 修复资格 BLOCKED：缺少区分真表面/测量偏差的外部证据，也没有一个符合原单平面与门控契约、能在全部固定留出改善且机制成立的候选。没有修改算法入口、输出有效TLS或编造修复diff。candidate/仅存放复用的09C冻结源码，不代表CL2-10新候选。

## 最小下一步设计（未执行）

优先复用09A预注册的原现场五点独立身份/相对高度核验；先确认原场景与对应关系，ROI2外独立基准对齐，不能用目标五点拟合对齐吸收梯度。原 bag 若取得，可先独立重解码并逐源行/坐标/字段核对，以区分提取链与原测量数据。当前 meta 只记录板端 /mnt/captures/captures_remote/*.bag 和 SHA，本地目标只有meta/bin，没有可复解码bag或独立GT；不擅自连板、重采或修改高度参数。

若证实真表面非共面，应讨论单平面模型适用边界并保留原拒绝，不将曲面硬压为平面；若独立平坦GT证伪真几何解释，再用独立标定数据建立可检验测量修正。任何候选必须预固定训练/独立验收域、所有点/困难ROI保留、原门不变，不用这段已知验收数据调参数。本轮只交付设计，未实施。

生产接入、有效 TLS 解锁、B2/B3、采集/设备仍未授权；后续离线补证可规划，算法修复开发条件尚未具备。
'''
(E/'01_root_cause.md').write_text(root,encoding='utf8')
compact={}
for sid,r in ab['sessions'].items():
    compact[sid]=dict(original_TLS_valid=r['original_TLS_valid'],original_recommended=r['original_recommended'],
       baseline=r['baseline'],variants=r['variants'],rigid_coordinate_controls=r['rigid_coordinate_controls'],
       independent_SVD_max_FIT_residual_difference_m=r['independent_SVD_max_FIT_residual_difference_m'])
save('04_audit_numeric_bundle.json',dict(sessions=compact,target_frames_summary=dict(
    count=len(frames),failure_ordinals=[f['ordinal'] for f in frames if f['regions']['2']['p95_m']>.05],
    gradient_x_min=min(gx),gradient_x_max=max(gx),gradient_x_median=float(np.median(gx))),
    target_scalar_checks=original['independent_scalar_holdouts'],target_geometry=original['geometry_fit'],
    target_frame72_metrics=rows[0],target_channel=channel,
    source_bindings=load(E/'00_input_catalog.json'),original_gate_cross_checks=load(E/'01_gate_cross_checks.json')))
text='CL2-10 regression evidence (not completion by totals)\n\n'
text+=(E/'03_regression.stderr').read_text(encoding='utf8')
text+='\nOriginal 11-session TLS gate results:\n'
text+='\n'.join(f"{sid}: valid={r['valid']} reasons={r['reject_reasons']} scalar_holdouts={r['fixed_scalar_holdout_metrics_match']}" for sid,r in load(E/'01_gate_cross_checks.json').items())
text+='\n\nNo CL2-10 algorithm repair candidate; candidate/ bytes are frozen CL2-09C. Original P95=.05/RMS=.03 gates unchanged.\n'
text+='Key search single-call records:\n'+(E/'03_search_performance.json').read_text(encoding='utf8')
(E/'03_regression_results.txt').write_text(text,encoding='utf8')
print('AUTHOR_REPORT_AND_AUDIT_BUNDLE_READY')
