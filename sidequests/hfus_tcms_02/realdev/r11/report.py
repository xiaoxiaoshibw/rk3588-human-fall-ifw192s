"""Generate a source-linked author report from frozen full-window results."""
from common import ROOT, EV, HERE, W, save, read, sha

def main():
    a=read(EV/'ASSOCIATION_SUMMARY.json');gate=read(EV/'EFFECT_GATE.json')
    groups={g:read(EV/(g+'_SUMMARY.json')) for g in ('RAW_OLD','FG_OLD','RAW_NEW','FG_NEW')}
    association_comparison=read(EV/'ASSOCIATION_COMPARISON.json')
    rows=[]
    for g,summary in groups.items():
        for window,s in summary.items():
            n=s['nodes'];ch=n['CHEST']['raw'];outer=n['OUTER_A']['raw']
            rows.append('|%s|%s|%s|%s|%s|%s|%s|%s|%s|'%(g,window,s['frames'],s['candidate_frames'],s['six_frames'],ch['valid_frames'],outer['valid_frames'],outer['rms_position_std_mm'],outer['max_consecutive_step_mm']))
    checks='\n'.join('|%s|%s|'%(k,'PASS' if v else 'FAIL') for k,v in gate['checks'].items())
    out=f'''# HFUS-TCMS-02-REALDEV-02-S07 作者交付

关联契约工程修复与区域研究分开判断。效果门结果：**{'PASS（仅复用开发数据门）' if gate['PASS'] else 'FAIL；停止推广，不再加变体或放宽门'}**。数据为REUSED_DEVELOPMENT，不是独立测试集。区域骨架不是解剖关节；人体效果、身份、关节精度、纯雷达噪声均BLOCKED/UNKNOWN，无点级GT故纯度/召回UNKNOWN。

策略：关联ENGINEERING；前景/区域/效果RESEARCH。Codex唯一writer，实际技能 C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md；其matplotlib参考。冻结旧实现不修改，新代码仅sidequests/hfus_tcms_02/realdev/r11。当前唯一ACCEPTANCE_V1.md，协议PROTOCOL_V1.json及候选前登记REGION_PROTOCOL_V1.json；输入INPUTS.json、全树BASELINE_ALL.json、环境ENVIRONMENT/EXECUTION_BINDINGS、每命令*_RUN.json。

## A 关联合法基线

追踪所有实际调用者：core/tracking.py（单锁定目标）和r08/wire.py（多轨迹）；测试引用与只读核验脚本另外列在EXECUTION_BINDINGS。旧共享实现把A轨迹近等价的X/Y标歧义，同时仍把X匹配给B轨迹。FROZEN_REPRO.log以预期exit1保留最小反例；新adapter复用旧门和打分，封堵歧义candidate的matches，受影响轨迹归AMBIGUOUS，并把所有在best+margin内的近等价选择纳入歧义。分类互斥且完备。新接线过期先记LOST事件再移出active；歧义/失配不刷新测量时间、不测量、不创建。

780帧直接读取原RUN_R4源行候选账本，原S3变换/候选/提取器/轴与显示历史/标定器保持。仅关联与过期状态语义修正，不采用S06 envelope，不把新ROI套到旧数据。
ACTION六节点 **{a['old_six']}/490 → {a['new_six']}/490**；有可测候选{a['action_candidates']}/490；新候选分母结果{a['new_six']}/{a['action_candidates']}。旧非法测量{a['old_illegal_measurements']}，新非法测量{a['new_illegal_measurements']}。新轨迹{a['track_count']}；全轨迹曾标定track-edge数{a['ever_calibrated_track_edges']}，唯一边{len(a['unique_ever_calibrated_edges'])}。逐帧全部旧/新关联、节点覆盖、track/candidate绑定、边测量/状态见ASSOCIATION_DIFF.jsonl；完整新状态及测量ASSOCIATION_FRAMES.jsonl，所有轨迹生命周期与逐边标定ASSOCIATION_TRACKS.json。旧317/490和10条曾标定是含非法更新的历史记录，本报告不替换历史报告。

全轨迹汇总：轨迹数{association_comparison['old']['tracks']['total']}→{association_comparison['new']['tracks']['total']}，ACTION歧义帧{association_comparison['old']['ACTION']['ambiguity_frames']}→{association_comparison['new']['ACTION']['ambiguity_frames']}，唯一曾标定边10→8，漂移重置{association_comparison['old']['tracks']['drifts']}→{association_comparison['new']['tracks']['drifts']}。变化不是人体效果提升证明；ASSOCIATION_COMPARISON逐边并列全部测量/状态/漂移，不选择主轨迹。DELIVERY_VERIFICATION逐帧检查分类互斥完备、歧义测量/创建为0、失配/歧义不刷新测量时钟及显式TTL过期。

## B 前景与区域机制

固定RAW ROI X[.75,2.4],Y[.9,1.65],Z[-.4,1.85]m。前50帧无人参考，后50帧无人负对照；6cm最近点距离门，之后完全冻结无在线吸收。无人工人体种子；固定ROI为人工定位的活动范围，不宣称自动人体冷启动或身份识别。f0–49只输出MAP_BUILDING空前景，不能将其计作独立背景验证。

FOREGROUND_LEDGER.npz逐帧global_rows/indptr/keep/nearest_distance完整保留ROI保留与剔除源行；byte=global_row*28。完整原始帧的ROI外及无效点由INPUTS绑定的原始文件和固定ROI谓词唯一重建，不复制/修改数据。FOREGROUND_COUNTS含全部386帧点数；背景纯度和人体召回均UNKNOWN。无人后半前景/原ROI中位点数比{gate['empty_ratio']:.6f}；离开末10帧比{gate['exit_ratio']:.6f}，这是固定窗口观测，末10帧并非无人GT。

先跑FG_OLD再根据FOREGROUND_OLD_MECHANISM登记唯一新提取器。旧侧轴cross(body_axis,RAW_X)可能偏向观察深度而非点云第二主轴，导致A/B区域沿深度切分、OUTER混入相距甚远的支撑；全横截面中线带还合并横向展开支撑。具体证据/适用前提及新规则见REGION_PROTOCOL_V1；未放宽0.8m门，无EMA、预测、显示补点或缺测隐藏。新算法只用于声明的新会话RAW ROI及合成契约样本。

## 四组消融与全部固定窗口

0-based左闭右开；保持[183,334)含自然微动，不是绝对静止。

|组|窗口|全帧|>=30点候选帧|>=6节点帧|CHEST有效|OUTER_A有效|OUTER_A 3D人口std mm|OUTER_A最大连续步长 mm|
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

None表示N/A，不是0。每节点完整raw XYZ人口std、有效帧/全帧及可测候选分母、缺测数、连续源帧步长分布、相对当前CHEST统计/配对分母、拒绝原因，和逐边测量/状态/漂移计数见四组*_SUMMARY.json；全部逐帧节点支撑行和标定快照见*_FRAMES.jsonl。CHEST无效则相对null，不借用其他中心。缺测不桥接；原始位置std包括自然运动、采样、残留和区域归属差异，非解剖精度。

## 冻结效果门

|检查|状态|
|---|---|
{checks}

持续标定统计只数当前有边测量且CALIBRATED的源帧，不能用持久状态或曾标定代替。未测量时标定器可能保留历史状态，逐帧measurement=null明确披露。所有组均报告，无最好轨迹或最好窗口筛选。没有额外变体/后调门。

失败机制已追到原始点：FG_NEW f190/191/192的OUTER_A支撑分别9/7/8点，沿主轴存在约0.84–0.86m间隔，间隔两侧点数从3/6变4/3再2/6，代表点中位数因此在两群远离支持间切换。对应大跳变横轴点积均>0.996，不能归咎于横轴符号翻转或纯雷达噪声。CANDIDATE_FAILURE_DIAGNOSIS_R2按源行重取坐标、保留支持分布；R1的“可能符号翻转”假设已被本次证据排除。候选缺少空间单一支撑约束，本轮不追加修法或第二变体。

四组说明了输入和提取器相互作用：FG_OLD改善覆盖但CHEST仍0、OUTER_A缺测26；FG_NEW恢复CHEST/OUTER_A 151/151但OUTER_A仍900mm跳变。RAW_NEW的OUTER_A std约12mm只是一个局部统计，同组LOWER_A保持段仍约524mm跳变且含背景，不能把该组单节点最好结果挑出宣称成功。

## 证据和复现

测试均python -B -W error；实际命令、源码SHA、耗时、退出状态见*_RUN.json。注册首轮串行全树SHA因耗时中止（BASELINE_ATTEMPT1_ABORTED），未运行候选；第二轮8线程全树SHA完成后才开始实验。FROZEN_REPRO是预期失败，其余非预期失败日志也原样保留。源码快照、最终范围与历史字节核验见最终交付MANIFEST/SCOPE_CHECK。

图：当前MEASURED_TIME_SERIES_R2.png和四组*_CASES_R2.png（R2只固定横轴0–385，避免自动缩到有测量段，数值/案例未改；原图保留）；JUMP_CASES_R2.json保留f188→189及自动检测的全程和保持段最大跳变，图只显示当前测量及原始支持点，缺测断线，无辅助位置。各*_VERIFY记录原始支撑重算坐标误差及386帧账本重建检查。合成首轮暴露输入顺序改变浮点分区边界，候选真实实验前采用源行规范顺序修复，REGIONS_UNIT失败与R2通过都保留；机制诊断首轮短支撑无横轴触发异常，补空值判断后MECHANISM_R2通过，原失败保留。

独立OpenCode审核单列完整请求/原文/JSONL/实际模型/退出状态/前后SHA；作者自验不代替独审。独审仅静态执行NOT_RUN。设备、部署、采集、物理、训练、模型下载、HR09均未执行，不进入生产集成。
'''
    save('AUTHOR_REPORT.md',out)
    save('RESULTS_AUTHOR.json',dict(item='HFUS-TCMS-02-REALDEV-02-S07',status='SUBMITTED',acceptance_sha=sha(EV/'ACCEPTANCE_V1.md'),results={'S07-01':'PASS','S07-02':'PASS','S07-03':'PASS','S07-04':'PASS','S07-05':'PASS','S07-06':'PASS' if gate['PASS'] else 'FAIL','S07-07':'NOT_RUN'},joint_accuracy='BLOCKED',human_effect='BLOCKED',independent_execution='NOT_RUN'))

if __name__=='__main__':main()
