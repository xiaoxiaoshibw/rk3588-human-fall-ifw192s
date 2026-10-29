"""Generate descriptive reports and standard Matplotlib artifacts from actual run."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiment import read, write, HERE, EVIDENCE, sha
from temporal import POSTURES


def main(run):
    result=read(run/'RESULTS.json'); manifest=read(run/'INPUT_MANIFEST.json'); catalog=read(run/'catalog.json'); cfg=read(run/'FROZEN_CONFIG.json'); mechanisms=read(run/'MECHANISMS.json')
    def doc(name, body):
        (HERE/name).write_text(body,encoding='utf8')
    figs=run/'figures';figs.mkdir(exist_ok=False)
    allrows=[]; feature_stats={}; sf=[]
    fig,axes=plt.subplots(8,2,figsize=(14,24),constrained_layout=True)
    actions=[s for s in catalog if not s['empty']]
    for i,s in enumerate(actions):
        rows=read(run/s['sid']/'features.json');os=read(run/s['sid']/'predictions.json');allrows.extend(rows)
        t=np.array([r['time']-rows[0]['time'] for r in rows])
        for k,label,color in [('z90','z90 (m)','#aa7722'),('height','height (m)','#227c9d'),('vertical_velocity','vertical speed (m/s)','#c24658')]:
            y=[o['feature'].get(k) if o['feature'] else np.nan for o in os]
            axes[i,0].plot(t,[np.nan if v is None else v for v in y],label=label,color=color,lw=1)
        axes[i,0].set_title(s['sid']);axes[i,0].set_xlabel('device elapsed seconds');axes[i,0].legend(fontsize=7,ncol=3);axes[i,0].grid(alpha=.2)
        tilt=[o['feature']['tilt_deg'] if o['feature'] else None for o in os]
        axes[i,1].plot(t,[np.nan if v is None else v for v in tilt],label='axis tilt (degrees)',color='#7254a0')
        axes[i,1].plot(t,[r['rf']*90 if r['rf'] is not None else np.nan for r in rows],label='RF probability x 90',color='#299872')
        axes[i,1].set_xlabel('device elapsed seconds');axes[i,1].legend(fontsize=7);axes[i,1].grid(alpha=.2)
        features=[r['feature'] for r in rows if r['feature']]
        feature_stats[s['sid']]={k:dict(min=float(min(f[k] for f in features if f[k] is not None)),max=float(max(f[k] for f in features if f[k] is not None))) for k in ['height','z90','count','density']}
        sf.append('|'+s['sid']+'|'+str(len(rows))+'|'+str(result['by_session'][s['sid']]['summary']['posture']['switches'])+'|'+str(result['by_session'][s['sid']]['summary']['offline_viterbi']['switches'])+'|')
    fig.suptitle('Real fixed candidate features; action names are NOT ground truth',fontsize=15)
    fig.savefig(figs/'eight_actions.png',dpi=120);fig.savefig(figs/'eight_actions.svg');plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(14,4),constrained_layout=True)
    for ax,a,title in zip(axes,[cfg['presence_matrix'],cfg['posture']['matrix'],cfg['event']['matrix']],['Presence transition / .1 s','Posture transition / .1 s','HSMM exit transition']):
        im=ax.imshow(a,vmin=0,vmax=1,cmap='viridis');ax.set_title(title);ax.set_xlabel('next state');ax.set_ylabel('previous state');fig.colorbar(im,ax=ax)
    fig.savefig(figs/'matrices.png',dpi=160);plt.close(fig)
    write(run/'FEATURE_STATS.json',feature_stats)
    aggregate=result['aggregate']; tables='|模型|切换次数|可比转移分母|未知帧|\n|---|---:|---:|---:|\n'+''.join('|{}|{}|{}|{}|\n'.format(k,v['switches'],v['eligible_transitions'],v['unknown_frames']) for k,v in aggregate.items() if isinstance(v,dict) and 'switches' in v)
    timings='|模块|平均 ms|P50 ms|P95 ms|\n|---|---:|---:|---:|\n'+''.join('|{}|{:.4f}|{:.4f}|{:.4f}|\n'.format(k,v['mean'],v['p50'],v['p95']) for k,v in result['timing_ms'].items() if v)
    doc('README.md', '''# HFUS-MARKOV-EXPERIMENT-01

独立离线侧链，Codex唯一代码writer；复用E0 G0背景/聚类/关联/成员、原RF提取器和Three.js渲染依赖。未改生产/模型/数据/GT，无训练或板端操作。技能：ponytail `C:/Users/30680/.codex/skills/ponytail/SKILL.md`，scientific-toolkit-skill及matplotlib；论文子代理paper-lookup，复核子代理只读。

本地入口：http://127.0.0.1:8947/ 。从仓库根执行：

```powershell
python -B -W error sidequests/human_fusion_lab_next/temporal_markov_r01/server.py --port 8947
```

也可双击 start_demo.bat，终端保持运行。选择会话，播放/暂停、上一/下一帧或拖时间轴；重置从当前帧开始重算，起点之前显示未计算。启停HMM/HSMM控制显示；参数改变会重算实验结果，恢复按钮回到冻结结果。灰点为完整原始帧经原E0变换后的显示抽样，青点为候选，不是全量点数。分歧导航不是已确认误检/漏检。人工复核以真实审核人追加到本轮证据human_reviews，不写冻结GT、不自动解除训练门。

实际复现命令见证据 COMMANDS.md。首次完整提取消耗磁盘读取；核心推理只需stdlib+NumPy，PC特征图另用Matplotlib，RF严格复用原Node模块。运行输出目录必须全新，防止覆盖证据。当前结果run_r3明确复用run_r2特征字节，重新推理；r1失败、r2旧输出保留。

数据通路：原meta/points SHA → E0 INDEX绑定corrected坐标/selected成员/identity → 当前RF批推理与几何 → 各轨迹独立滤波/MC/HMM/HSMM → 固定AB账本 → 同帧Demo/特征图。无需ROS/设备/网络。
''')
    doc('DATA_AUDIT.md', '# 数据审计\n\nmaster / c9c4ee421cb0c8a3e4590b8f5730828b093c759a；脏工作树完整记录BASELINE_STATUS.txt，相关tracked/untracked源SHA见BASELINE.json。只读复用上一轮E0 G0，1934动作+90独立空场，非未见泛化集。18原meta/points重核，6072份JSON/NPZ逐文件对旧INDEX验证。R2完整提取，R3特征字节复用和新时序结果分开记录。\n\n原始字段根据实际meta.point_layout及human_replay_lib既有契约，只消费XYZ@0/4/8和intensity@12，小端float32、stride28。其余字节不解释。offset/count全连续、总长匹配、时间严格单调。时间是设备未锚定秒，不把bag walltime作设备时间。中位9.64655Hz，dt约0.103665s，速度使用每轨迹真实相邻dt；空场只取mod3=2留帧，因此实际观察间隔约0.311s。\n\n当前labels目录0文件；LABEL_MANIFEST重读：282核心和66第二人未审核，trusted_K=0。九源human_annotations=0；动作名不是标签。E1正式训练仍未解除，未训练、未调参选胜者。所有P/R/F1、混淆矩阵、Macro F1、真实事件P/R与延迟均BLOCKED/UNKNOWN。\n\n人体点集稳定性只能描述：1934帧都有候选，90空场无候选，几何轴歧义2帧；候选纯度/完整性与关联置信度未知，不把selected_count稳定当真人证据。旧action_output包含历史来源和RF占位0，本轮不拿占位作基线；输入来自可SHA核对的最新E0。原131958背景原源缺失是历史边界，本轮消费E0已冻结数值产物，不宣称重新验证其物理标定或原场景。\n\n输入全索引：run_r3/INPUT_MANIFEST.json、FEATURE_REUSE.json；保留来源meta/points、每帧源seq/offset/count、候选成员SHA、轨迹ID。各会话既有dev/final角色原样保留，但全体早已开发暴露；本轮纯规则机制研究，不作泛化验证或使用最终集选择阈值。\n')
    doc('FEATURE_REPORT.md', '# 特征分析\n\n![八动作](../../../docs/human_capture/evidence/2026-10-15_hfus_markov_r01/run_r3/figures/eight_actions.png)\n\n图件实际路径：docs/human_capture/evidence/2026-10-15_hfus_markov_r01/run_r3/figures/eight_actions.png及SVG。\n\n高度/宽/深为2–98%分位跨度；最高最低是极值；质心是均值；volume为分位盒体积；density=点数/体积（近退化体积下限1e-6m³）；tilt为最大PCA轴与z的锐角，特征值接近时null；eigen_ratio为最大特征值/总值；low_fraction为z<0.6m比例。\n\n垂速/水平速度/高度变化率/角速度分别由当前与上次有效测量差分除真实dt（m/s、deg/s）；缺失立即断差分，不能跨遮挡补速度。stable_frames是原型最大发射类连续帧数；missing_age_s为距最近测量秒。RF用真实强度及既有51维提取器；candidate_valid仅几何存在，completeness和association_confidence=null，因为无校准值。逐帧可增量计算；空间几何只依赖当前点，不依赖骨架。\n\n可观察到高度与低位变化，但坐下/蹲下观测区间重叠，HMM的两个语义状态在此数据上不可独立验证。RF在这1934个已预筛候选上全为阳性，动态范围不足以研究真实闪烁；这也暴露先选候选再评RF的选择偏差。倾角反映可见点主轴，不保证身体轴；近退化/遮挡应UNKNOWN。特征是否真正有语义判别力需要逐帧人工标签，当前UNKNOWN；不以文件名给类别后做可分性准确率。范围数值见FEATURE_STATS.json。\n')
    doc('MODEL_DESIGN.md', '''# 模型与边界

冻结参数在run_r3/FROZEN_CONFIG.json，规则初始化、未拟合，冻结后不根据最终数据选择配置。

EMA以α=1-exp(-dt/τ)更新RF；投票为过去0.5秒有效观测；滞回0.65/0.4，RF阈值0.55；短保持0.4秒输出hold_prediction，缺失时baseline/ema/vote/hysteresis为null。MC用RF阈值先离散成PRESENT/MISSING/UNKNOWN再结合转移先验；连续特征观测分类器与转移矩阵分工明确，不声称MC能直接从点云识别姿态。

HMM：π为初始分布，A每0.1秒转移；实际dt用A^floor(dt/.1)乘(I*(1-f)+A*f)插值，非拟合连续生成矩阵。姿态发射使用z90与高度的高斯原型，快速运动提升TRANSITION似然，轴歧义/稀少点提高UNKNOWN。坐/蹲均是规则假设，不是学习得到的语义。Forward αt∝(αt-1 A(dt))⊙b(xt)，每步归一，似然有下限；缺失采用高UNKNOWN发射，不将无点当0高度。presence HMM另用RF连续似然。

Viterbi在log-domain执行δt(j)=log bj+max_i(δt-1(i)+log Aij)，回溯仅用于离线。逐sid+track的连续时间段分别解码，绝不跨reset；在线输出经前缀测试，不消费未来。离线可能增加而非减少切换。

HSMM用状态-起始时刻cohort后验；Weibull S_s(a)=exp(-(a/scale_s)^shape_s)，每步生存比S(a+dt)/S(a)，退出质量乘零对角exit矩阵后产生新cohort。秒持续时间用真实timestamp；最大持续30秒强制退出；每间隔细分≤0.02秒以允许多次renewal，右端点近似仍有误差，不宣称精确连续解。后验零质量明确拒绝。时间有限窗口内状态cohort开销受时长与帧率影响；不外推为板端内存结论。

事件HMM使用完全相同事件发射，几何分布平均驻留匹配Weibull均值，形成持续时间对照。HSMM状态NORMAL/POSSIBLE_FALL/POST_FALL/RECOVERY/UNKNOWN为假设。事件候选另需近期可靠高位、≥0.3m下降、≥0.5m/s、低位持续≥0.6秒和概率门；初始低位/慢降/缺失不能触发。主动快速躺下仍可能候选，不能确认跌倒。POST_FALL仅模型状态名字，无真实跌倒含义。

sid/track分隔缓存；时间倒退、>1秒间隔或显式reset清历史；缺失清下降armed和差分。上游复用同ID代表不同人且未通知的情况无法自动识别，此处ID串扰真实效果UNKNOWN。数学参数、转移图见config与figures/matrices.png。
''')
    doc('EXPERIMENT_RESULTS.md', '# 实际实验结果\n\n本报告的E1–E6仅对应本工单实验编号，不是HFUS-LEARN E1正式训练或验收。IMPLEMENTED/TESTED不等于EVALUATED。\n\n|实验|实际运行|结论与边界|\n|---|---|---|\n|E1 闪烁|1934真实候选RF/EMA/滞回/MC/HMM全跑；另合成0.8/0.3交替|真实RF已有0切换，无增益可证；机制滤波可减少切换，不是人体效果PASS|\n|E2 遮挡|真实90空场缺失；合成同轨5帧缺失|短保持标预测，缺失发射UNKNOWN；真实遮挡标签缺失，效果BLOCKED|\n|E3 高低姿态|八动作全量高度/倾角/速度图及HMM|Forward26次、离线Viterbi30次切换，不能说更稳定即更准确；姿态GT缺失|\n|E4 下降候选|真实2024帧与快降/慢降/初始低位机制|真实0候选；机制快降1、慢降0、初始低0；主动快躺可误触发，真实P/R UNKNOWN|\n|E5 家具反证|90真实空场0簇/0所选；合成持续0.95误判|端到端空场0保持；条件家具误判在滤波后持续，时序不纠正身份；真实家具误判持续时间BLOCKED，不省略负结果|\n|E6 多人/ID|两条交错ID同输入独立运行对照|机制污染0，重置/前缀/交错Viterbi测试通过；真实多人与ID切换GT不足，效果BLOCKED|\n\n'+tables+'\n姿态/MC/HMM含缺失转移，RF可比转移只含观测且不跨ID，分母不可偷换。未知90，弱观测2；家具误检次数/持续时间、人体P/R/F1、姿态混淆矩阵/Macro F1、真实event P/R、真实P50/P95响应延迟均BLOCKED/UNKNOWN。\n\n'+timings+'\nRF特征+推理平均{:.4f}ms/P95 {:.4f}ms；完整时序平均包含所有并行对照，不是某一个待部署模型。PC墙时，排除原预处理/IO；Viterbi每帧摊销为吞吐、不是实时延迟；simple filter各自独立耗时NOT_RUN。\n\n合成阶跃响应（不是实际人体检测延迟）：{}。原始机器可读输出RESULTS.json、MECHANISMS.json及逐会话predictions.json。\n'.format(result['rf_ms']['mean'],result['rf_ms']['p95'],mechanisms['synthetic_step_response_s']))
    doc('ABLATION_REPORT.md', '# 消融与敏感性\n\n'+tables+'\n全部方法使用同一G0候选、同一上游ID/时间、无训练与重关联，固定规则参数。RF与几何门不是端到端全场召回评估。HMM/HSMM不修改候选或点成员。简单平滑、MC、presence HMM真实切换均0，无最佳模型证据；姿态Forward26/Viterbi30不是语义评分。\n\n预登记EMA τ=0.15/0.3/0.6秒全跑，每组真实检测切换均0；不选最优阈值。HSMM与event HMM同发射，真实均NORMAL/UNKNOWN，当前数据未激发可比较事件；持续时间机制差异由Weibull对几何分布和秒子步测试解释。未进行HSMM阈值搜优或学习。\n\n合成阶跃RF0.1→0.9：EMA0.2秒、投票0.3秒、HMM presence0.1秒、滞回0秒；是假设输入响应，不给真实P50/P95。更平滑可延长家具误判与增加延迟，不能仅按切换数挑赢家。\n')
    doc('FAILURE_CASES.md', '''# 失败与限制

1. R1提取把E0 uint8 selected当bool契约检查，失败退出；已显式验证0/1后转bool，原日志保留，R2提取成功。
2. 真实候选RF全阳性，E1闪烁目标不被数据激发。选择偏差来自G0几何预筛，不能推出全场人体检测完美。
3. 真实HSMM零候选：既可能门过严，也可能无符合条件动作；无审核事件边界不能算漏检或召回。快主动躺下机制同样触发，不可分真实跌倒。
4. 家具持续RF误判机制一直保留，高自转移更易固化错误。真实空场0簇意味着家具条件反证无实际正输出，相关误检持续评估BLOCKED。
5. 人体候选完整性、坐/蹲语义、多人真实身份未知。测到主轴不是身体姿态真值，2帧歧义保留未知。
6. 独立只读审查捕获交错Viterbi分段、统计分母、HSMM零质量/大dt近似、非法feature，以及Demo异步点云/复核绑定问题；均修复并复验。HSMM子步仍是有界近似，不宣称精确连续算法。
7. Demo是独立离线实验页，复用既有数据和Three依赖；未接管原console应用或打包EXE。HMM/HSMM开关控制实验显示，不改变冻结输出；无标签时导航仅指分歧/缺失/候选而非已确认FP/FN。
8. 1934帧候选未真实遮挡，90空场不是人体遮挡正例；多人/遮挡机制测试不能替代现场效果。
''')
    doc('FINAL_REPORT.md', '''# 最终结论 · SUBMITTED

IMPLEMENTED：实际几何/动态特征、原RF重新推理、EMA/投票/滞回/保持、MC、presence/posture/event HMM、Forward/Viterbi、显式秒持续HSMM、候选事件及可运行本地A/B Demo。TESTED：2024帧真实固定输入全量推理、敏感性和机制反例、单元/HTTP/浏览器检查，证据分列。EVALUATED：仅描述性稳定性/计算开销；语义效果没有独立GT支持。UNKNOWN：人体/姿态/跌倒准确率与真实延迟。BLOCKED：人工标签门及正式E1学习。设备/部署NOT_RUN。

1. **现有数据能否支持时序识别？** 能运行几何时序机制；不支持当前监督语义训练及可信效果验收。设备时间有效约9.65Hz，候选可用；K=0、事件GT缺失。
2. **HMM是否改善人体稳定性？** 未证实。1934真实候选原RF已0切换，平滑和HMM仍0。合成闪烁改善仅机制证据，不能转为实际效果结论。
3. **HSMM能否区分低位与跌倒？** 初始低/慢降机制可抑制，快降候选能触发；真实0候选，主动快速躺下仍无法区分，实际能力UNKNOWN。
4. **哪些获独立GT证明？** 本轮没有任何人体、姿态或事件效果改善获得独立GT证明；测试通过只证明行为。
5. **哪个最好、开销多少？** 没有语义最佳模型。当前优先保留原基线；HMM小于HSMM计算成本但效果未知。精确均值/P95与合成延迟见实验报告，不能把离线Viterbi当在线。
6. **值得继续训练吗？** 先补可信人工标签和困难负例，再做session隔离的有界小HMM/HSMM比较；当前不值得扩大无标签训练或引入复杂网络。小TCN/GRU可未来同特征对照，不在本轮实施。
7. **最缺标注？** 先完成282核心+66第二人；逐轨迹人体存在/非人体、可见性与真实ID，站/坐/蹲/躺/过渡开始结束；快速主动躺、坐、蹲、弯腰、家具持久误判、短遮挡及ID切换；独立真实跌倒正例和可审核事件边界。不要用动作名补标签。
8. **RK3588条件？** 核心stdlib+NumPy且源码Python3.8语法兼容，具备移植前提；未在Python3.8/NumPy1.17或RK运行。PC原RF复用Node，未交付其板端替代；全流水线板端耗时/内存/部署均NOT_RUN。

不晋级生产、不改变E1/HR09门、不重签GT。本轮唯一验收M01–M12见证据ACCEPTANCE_V1.md；逐项结果RESULTS.md。性能和稳定性数字不能推断人体识别效果改善。
''')
    print('reports and figures generated',run)


if __name__=='__main__':
    main(EVIDENCE/'run_r3')
