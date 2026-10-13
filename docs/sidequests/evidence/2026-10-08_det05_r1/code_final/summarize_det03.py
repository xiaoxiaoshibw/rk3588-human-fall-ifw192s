"""Summarize every predeclared paired experiment, including negative results."""
import csv
import json
from pathlib import Path
import shutil

import numpy as np
from experiment import sha

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parents[1]/'docs/sidequests/evidence/2026-10-08_det03_r1'


def mdtable(headers,rows):
    return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|']+['|'+'|'.join(map(str,r))+'|' for r in rows])


def main():
    rep=json.loads((ROOT/'artifacts/det03_representative_r2/rows.json').read_text(encoding='utf-8'))
    allrows=json.loads((ROOT/'artifacts/det03_all_r1/rows.json').read_text(encoding='utf-8'))
    attr=json.loads((ROOT/'artifacts/det03_attribution_r1/result.json').read_text(encoding='utf-8'))['rows']
    neg=json.loads((ROOT/'artifacts/det03_negative_controls_r1/rows.json').read_text(encoding='utf-8'))
    assert len(allrows)==1012
    pairs=[];summary=[]
    for sid in sorted({r['sid'] for r in allrows}):
        for variant in ['B_workspace','E_cleanup']:
            group=[r for r in allrows if r['sid']==sid and r['variant']==variant]
            baseline={r['index']:r for r in group if r['experiment']=='base'}
            sampled={r['index']:r for r in group if r['experiment']=='zrank'}
            assert baseline.keys()==sampled.keys()
            a=[baseline[i] for i in sorted(baseline)];b=[sampled[i] for i in sorted(baseline)]
            head0=np.array([r['local_anchor_max'] for r in a]);head1=np.array([r['local_anchor_max'] for r in b])
            final0=np.array([r['stages']['clockwise']['final_target_max'] for r in a]);final1=np.array([r['stages']['clockwise']['final_target_max'] for r in b])
            for x,y in zip(a,b):
                assert x['input_sha256']==y['input_sha256'] and x['adapted_sha256']==y['adapted_sha256'] and x['ids_sha256']==y['ids_sha256']
                assert x['voxels']==y['voxels']
                pairs.append(dict(sid=sid,index=x['index'],variant=variant,input_sha256=x['input_sha256'],
                    base_head=x['local_anchor_max'],zrank_head=y['local_anchor_max'],head_delta=y['local_anchor_max']-x['local_anchor_max'],
                    base_raw_containing=x['raw_containing_max'],zrank_raw_containing=y['raw_containing_max'],
                    base_final=x['stages']['clockwise']['final_target_max'],zrank_final=y['stages']['clockwise']['final_target_max'],
                    base_global=x['stages']['clockwise']['final_global_ped_max'],zrank_global=y['stages']['clockwise']['final_global_ped_max'],
                    base_top=x['after']['top'],zrank_top=y['after']['top']))
            summary.append(dict(sid=sid,variant=variant,frames=len(a),head_median_base=float(np.median(head0)),head_median_zrank=float(np.median(head1)),
                paired_head_delta_median=float(np.median(head1-head0)),head_increased=int((head1>head0+1e-6).sum()),head_decreased=int((head1<head0-1e-6).sum()),
                final_median_base=float(np.median(final0)),final_median_zrank=float(np.median(final1)),
                paired_final_delta_median=float(np.median(final1-final0)),final_increased=int((final1>final0+1e-6).sum()),final_decreased=int((final1<final0-1e-6).sum()),
                location_ge05_base=int((final0>=.5).sum()),location_ge05_zrank=int((final1>=.5).sum()),
                final_max_base=float(final0.max()),final_max_zrank=float(final1.max()),
                global_ped_median_base=float(np.median([r['stages']['clockwise']['final_global_ped_max'] for r in a])),
                global_ped_median_zrank=float(np.median([r['stages']['clockwise']['final_global_ped_max'] for r in b])),
                global_ped_max_base=max(r['stages']['clockwise']['final_global_ped_max'] for r in a),
                global_ped_max_zrank=max(r['stages']['clockwise']['final_global_ped_max'] for r in b),
                absence_head_low=sum(r['stages']['clockwise']['final_target_max']==0 and r['raw_containing_max']<=.1 for r in a),
                absence_topk=sum(r['stages']['clockwise']['final_target_max']==0 and r['raw_containing_max']>.1 and r['raw_containing_gt01']==r['target_top100_removed'] for r in a),
                absence_nms=sum(r['stages']['clockwise']['final_target_max']==0 and r['raw_containing_gt01']>r['target_top100_removed'] and r['stages']['clockwise']['target_nms_removed']>0 for r in a),
                absence_max50=sum(r['stages']['clockwise']['final_target_max']==0 and r['stages']['clockwise']['target_max50_removed']>0 for r in a)))
    # Report regeneration is allowed only inside this new round; no historical evidence writes.
    with (OUT/'16_same_frame_pairs.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(pairs[0]));w.writeheader();w.writerows(pairs)
    changes=dict(nms_target_score_changed=sum(abs(r['stages']['legacy']['final_target_max']-r['stages']['clockwise']['final_target_max'])>1e-7 for r in allrows),
                 containment_target_score_changed=sum(abs(r['old_ccw_final_target']-r['stages']['legacy']['final_target_max'])>1e-7 for r in allrows),
                 note='These counts include baseline and sampling inputs; NMS effect uses identical heads and corrected containment on both sides')
    result=dict(pairs=len(pairs),summary=summary,postprocess_changes=changes,representatives=rep,attribution=attr,negative_controls=neg,
                score_scope='All scores diagnostics for approximate session seeds, no exact Precision/Recall or body labels',
                inference_count=74+1012+24+74+8)
    (OUT/'15_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for stage in ['det03_representative_r1','det03_representative_r2','det03_all_r1','det03_attribution_r1','det03_negative_controls_r1']:
        src=ROOT/'artifacts'/stage
        for name in ['config.json','rows.json','rows.jsonl','result.json']:
            if (src/name).exists():shutil.copyfile(src/name,OUT/(stage+'_'+name))
    sampling_table=mdtable(['会话','输入','帧','头中位 原→覆盖','配对Δ中位','头升/降','位置最终分中位 原→覆盖','≥0.5位置帧 原→覆盖'],
        [[s['sid'][-6:],s['variant'][0],s['frames'],f"{s['head_median_base']:.3f}→{s['head_median_zrank']:.3f}",f"{s['paired_head_delta_median']:+.3f}",
          f"{s['head_increased']}/{s['head_decreased']}",f"{s['final_median_base']:.3f}→{s['final_median_zrank']:.3f}",f"{s['location_ge05_base']}→{s['location_ge05_zrank']}"] for s in summary])
    global_table=mdtable(['会话','输入','位置最高 原→覆盖','全场行人最高 原→覆盖','逐帧全场最高分中位 原→覆盖'],
        [[s['sid'][-6:],s['variant'][0],f"{s['final_max_base']:.3f}→{s['final_max_zrank']:.3f}",f"{s['global_ped_max_base']:.3f}→{s['global_ped_max_zrank']:.3f}",f"{s['global_ped_median_base']:.3f}→{s['global_ped_median_zrank']:.3f}"] for s in summary])
    attr_table=[]
    for sid in sorted({r['sid'] for r in attr}):
        for v in ['B_workspace','E_cleanup']:
            g={r['experiment']:r for r in attr if r['sid']==sid and r['variant']==v}
            attr_table.append([sid[-6:],v[0],*[f"{g[n]['local_anchor_max']:.3f}" for n in ['base','local_only','outside_only']]])
    context=[];params=[];coverage=[]
    for sid in sorted({r['sid'] for r in rep if 'sid' in r}):
        get=lambda v,n:next(r for r in rep if r.get('sid')==sid and r.get('variant')==v and r.get('experiment')==n)
        context.append([sid[-6:],*[f"{get(v,n)['local_anchor_max']:.3f}" for v,n in [('A_full','base'),('B_workspace','base'),('C_reference','base'),('C_reference','context_pillars'),('E_cleanup','base'),('E_cleanup','context_pillars')]]])
        for v in ['B_workspace','E_cleanup']:
            params.append([sid[-6:],v[0],*[f"{get(v,n)['local_anchor_max']:.3f}" for n in ['base','int65535','intzero','z_anchor','z_ground']]])
            a,b=get(v,'base'),get(v,'zrank');coverage.append([sid[-6:],v[0],a['before']['count'],f"{a['after']['count']}→{b['after']['count']}",
              f"{a['after']['head_proxy']}→{b['after']['head_proxy']}",f"{a['after']['raised_hands_proxy']}→{b['after']['raised_hands_proxy']}",
              f"{a['after']['top']:.3f}→{b['after']['top']:.3f}"])
    stages=mdtable(['会话','输入','无最终框且头低于门','全被top100排除','NMS造成无位置框','max50造成无位置框'],
        [[s['sid'][-6:],s['variant'][0],s['absence_head_low'],s['absence_topk'],s['absence_nms'],s['absence_max50']] for s in summary])
    negatives=mdtable(['控制','取样','定位头','最终位置分','全场行人分','全类分'],
        [[r['tag'],r['sampling'],f"{r['local_anchor_max']:.3f}",f"{r['stages']['clockwise']['final_target_max']:.3f}",
          f"{r['stages']['clockwise']['final_global_ped_max']:.3f}",f"{r['stages']['clockwise']['final_global_any_max']:.3f}"] for r in neg])
    text=f'''# DET-03：PointPillars 真人低分的离线可证伪排查

2026-10-08；SUBMITTED，作者自验，未ACCEPTED。唯一[验收表v1](../../DET03_ACCEPTANCE.md)，[先行计划](../../DET03_PLAN.md)。实验工作树为 `C:/Users/30680/.codex/worktrees/human-detector-models/ldiar`，分支codex/human-detector-models，HEAD cfbb80c57508be1a0435fdb92260f698dc763934。唯一writer Codex。技能实际使用路径 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`。原主线暂停；设备/采集/部署/物理/接管均NOT_RUN。

## 结论与证据边界

**已证实两个相关但不同的问题：** CPU NMS和位置包含判定的yaw方向与固定上游相反，已经在本实验适配器修正；先到32点的选点策略则在同帧、同上限的因果实验中压低了多个会话的分类响应。二者不可混为一个根因：NMS/框判定不能改变分类头，修正yaw也没有让原E分支突然得到高分。

**上下文删除也有因果支持。** 固定圆柱内原始点及相交柱的完整输入后，删除外部场景仍导致四个代表帧头响应下降。它解释了本权重前景化后比分支B低分，不能称“背景删除没有生效”。圆柱与相交柱包含家具，尚无精确人体标签。

**单一主因尚未确定。** 215643的B覆盖采样有负收益，E仍存在低分帧；输入强度、z基准未物理标定；近距密集俯视IFW192S与KITTI权重训练域差异是合理残余解释，尚无域适配的独立因果实验。没有证明“只要增加柱点数”或“只要清干净背景”即可成功。

明确负例：无人模板17/35/53帧的全场行人最高分在覆盖采样后从约0.21–0.25升至0.50–0.52，产生较高分假阳性。含人位置增分不能当作整体检测改善，更不能据此接管生产。

## 实现核查和正控制

- 07_input_audit：五会话307帧均用独立`struct.unpack_from('<4f', offset=i*28)`与原decoder逐值比较；零XYZ在刚体平移前过滤，global source rows逐值匹配；1265组A/B/C/D/E输入与各自TLS prepared[ids]逐值相同；原强度/current坐标未被reference坐标或临时ID污染。
- R/t形状与正交性校验复用；逐组验证fixedICP ref→current与保存current→ref互逆。215607三法高度差3.69cm冲突保留，仅离线TLS诊断；四组配准仍WARN，软件逆矩阵检查PASS不代表正式注册/物理gate PASS。
- 上游类号0/1/2=Pedestrian/Cyclist/Car；anchor/decoder是xyz底中心+wlh+KITTI ry。零delta保持底中心和尺寸；encoder坐标batch,x,y,z，源码明确将x/y换成柱心偏移再拼9D特征，conv实际输入与独立公式逐值一致；checkpoint全部keys/values一致，缺key严格加载负例被拒绝。
- 05_voxel_kernel_r2：固定上游C++ dynamic/hard kernel原算法正文，用host accessor/allocation shim编译；KITTI+四代表帧×A/B/C/E+边界共18例，voxels/coordinates/counts全部逐值一致。这是原kernel正文的执行对照，**并非原始ATen扩展或GPU的完整运行等价**；本机无MSVC/CUDA、PyTorch为2.12.0+cpu，实际GPU逐值等价BLOCKED。
- 01/12_upstream_host：直接将固定CUDA文件的Point/overlap/IoU正文去device限定后编译到CPU。偏移45°细框IoU=0.699557，旧NMS保留两框，上游与修正后均保留一框。80框合成与222组代表帧实际候选集合的NMS保留结果一致（09）。GPU浮点/边界/tie行为仍未完整验证。
- KITTI 000134原输入不做本传感器归一化/配平，行人最终全场最高0.774、全类0.964。这是网络正控制，不是GPU等价或KITTI测评AP。74组修正前后cls/reg/dir原始头逐值完全相同，见19_fix_head_identity.json。

修复只涉及sidequest `cpu_pointpillars.py`的顺时针NMS及与上游一致的CPU分数排序、`audit_truth.py`的顺时针包含判定、`plot_static.py`的BEV投影；补充45°回归。旧adapter与本轮首次实验代码在code_before_fix保存，历史证据与图不回填。绘图消费者已检查；side-view的x投影跨度取绝对值不受yaw方向改变影响。

## 每柱32点：同帧配对，而非各自挑峰值

维持0.16×0.16×4、每柱32、checkpoint、0.1门、top100、NMS0.01、max50、强度/1023、z−1.73。仅把先到32改为**stable z排序后等序位取32，含两端，等高按源顺序**。这是高度排序分位覆盖，并非连续高度等距或增加容量。柱集合、柱计数与原始点集不变；选择的是原始点，没有插值/补点/保护圈。先固定中间帧32/33/33/28验证覆盖，再预注册全253帧B/E对照，1012次前向、506对同帧输入；采样组与基线输入/ID SHA逐项相同。

{sampling_table}

头=anchor中心距近似种子≤0.55m的Pedestrian原始分类分。最终位置分=顺时针解码框包含该XY种子；0表示没有超过0.1的最终位置框。≥0.5列只是分数/位置统计，**不是识别成功、Recall或Precision**。配对差从同一帧计算；连续帧相关，不当独立样本做显著性推断。

全场分数单列，避免把家具位置高分当真人分：

{global_table}

代表帧区域高度代理（圆柱含家具，不是手/头/腿点标签）：

{mdtable(['会话','输入','输入圆柱点','选入点 原→覆盖','1.5–1.8m 原→覆盖','≥1.8m 原→覆盖','选入顶高 原→覆盖'],coverage)}

215623举手代表帧的选入顶端1.828→2.010m，恢复的是实际源点；不是新增/手工补人体。原始完整轮廓不等于编码器输入完整。柱内原点数/选入计数/选入XYZI/源ID保存在每帧*_pillars.npz，完整7高度带计数在逐帧rows。

为避免把外围场景采样变化全算给人体，补充冻结实验：

{mdtable(['会话','输入','原头','仅相交柱覆盖','仅外围柱覆盖'],attr_table)}

前三组B仅改局部相交柱已显著提高分数，外围改动不能复现这些增益；215643局部改动下降。**这支持局部柱选点是前三组低分的一个原因，不支持普遍充分原因，也不证明具体“手部”是唯一关键特征。** frozen_pillars_equal逐值断言保留；冻结实验实际编码高度带另存actual_encoded_height_bands，早期通用after字段只是未冻结选点诊断，不用于冻结实验结论。

## 场景上下文：保留局部输入后的删除实验

{mdtable(['会话','A头','B头','C头','C外部+固定B柱','E头','E外部+固定B柱'],context)}

context_points用B的圆柱内全点+C/E圆柱外点，保持B原顺序并逐值断言圆柱点和ID完全相同；context_pillars再冻结所有与圆柱相交的B体素及计数，13–22柱逐值一致。此时B→C/E仍下降，原因不能仅归于那0.3%的圆柱点删除或人体局部柱截断。外围卷积上下文/几何与权重响应有直接因果关系，但上下文含家具、背景和地面裁剪差异，不能扩大成对所有前景模型的结论。

A→B同时包含既有denoise/范围与z裁剪，不称纯背景收益。C是独立233658空场模板；E额外含离线配准和cleanup，配准WARN保留。未改模板、背景阈值或为真人加保护区域。

## 强度与z：有限、有来源的单因素检验

SDK Point.intensity是uint16，经publisher原样转ROS float32；源有效点示例P50=708、P99=977、max=978。上游KITTI read_points直接读取float32 XYZI，训练增强不包含本项目/1023；训练会shuffle点，本场景原始顺序更易产生扫描顺序偏置。当前数据不足以确定传感器强度与KITTI reflectivity的物理对应。

预先声明/65535源于uint16表示范围，置零是强度消融；都不冒充标定。z−0.6来自行人anchor底，z0是地面原点消融；不是把机器人光学窗口约1.1m当坐标原点标定。每次只变强度或z，未将采样/阈值一并变动：

{mdtable(['会话','输入','基线头','I/65535','I=0','z−0.6','z0'],params)}

替代强度在B四代表帧均降分；E有个别小升但仍低，不支持简单除数替换可修复。z−0.6/0使模型z<1m范围截掉定位邻域高点，分别84–255和594–1025点；因此退化既可能是绝对特征基准也可能是范围裁剪。不能用这些负例证明−1.73是正确安装高度；独立物理高度/响应标定NOT_RUN。没有大量扫描后只报最好值。

## 后处理完整去向

保存head cls/reg/dir、逐相关anchor的三类原始分数、完整候选rank、top100、anchor/decoded bottom-wlh-yaw、每类NMS suppressor、max50、最终框；代表帧保存全头，全帧保存所有局部anchor、所有解码覆盖种子的框及top100的原始三类分数与回归量。每次trace必须逐框逐分复现当时正常模型输出；代码修正后74代表前向复验，头响应保持。

原first32 B/E无最终位置框的原因记账（各阶段追踪，不从“无框”倒推）：

{stages}

{changes['nms_target_score_changed']} /1012次输入的同头“旧NMS→修正NMS”位置最高分改变；{changes['containment_target_score_changed']} /1012次输入的“旧包含方向→正确包含方向”位置最高分改变。两项独立计数，分类头完全未变。局部anchor高而解码框不包含种子的案例可在trace中定位为位置偏移；这仍是近似种子诊断，未做真实框IoU判定。E低分多数在候选门前出现，不能主要归咎top100/NMS。

## 正负控制与失败记录

{negatives}

233658用户确认无人。17/35/53帧只用于本模板留帧负控制，不能当独立场景误报率；KITTI行人全场高分不是本场景真人Recall。

05首次编译的DLL依赖加载失败（exit1）原日志保留；05_r2改静态链接后通过。它是诊断构建问题，不是PointPillars低分原因。03旧7检查、11修复后8检查、04背景/逆向自检均exit0。原DET-02失败记录未改。

20首次BEV消费者核对因上游process.py的旧docstring包含非法反斜杠escape而在-W error下解析失败；20b仅省略该函数docstring、执行原函数算法后，与修正绘图斜框角点吻合。失败日志保留，未过滤警告或改上游源。

## 最小修复与尚需验证

1. 已修实验适配器的yaw和包含判定，补斜框测试；适用于固定zhulf0804 commit/checkpoint，不泛化为所有框yaw规范。不会改善原始分类头。
2. 以opt-in离线覆盖采样替代先到32，不提高容量或降低阈值。前三组有同帧及局部冻结因果支持；第四组负例和空场分数限制说明尚不能启用为生产识别人方案。
3. 本KITTI权重保留B/整场对照，不默认送仅前景。已经证实外围删点影响分数，但尚未决定最合适裁剪/背景形式。
4. 最有区分力的下一项是**在精确逐点人体/邻近家具标注上，固定外围编码，只改变纯人体柱的高度覆盖**；同时用独立无人/不同人/位置/姿态数据评估假阳性。若残余仍低，再单独做已标定强度/坐标的上游GPU等价正控制和同传感器权重适配实验。现在四会话同一人且站位很近，不能判断泛化。

无精确框/点GT，Precision/Recall及准确率NOT_RUN；没有改score门、补框或借保护区域制造成功。CenterPoint依赖环境BLOCKED，未给出它的成绩。设备/物理/生产均不以CPU检查代替。

## 验收与完整记录

| ID | 作者自验 | 依据 |
|---|---|---|
| E01 | PASS | 00基线、先行计划/表、新目录；原树复核见18 |
| E02 | PASS（发现后实验修复） | 07输入307帧/1265组、encoder/strict/逆矩阵、11斜框 |
| E03 | BLOCKED（原包运行等价）；源码/host kernel/KITTI子检查PASS | 18体素例、80框/222候选；原ATen扩展无MSVC，实际GPU见G01 |
| E04 | PASS（执行及因果范围） | 506同帧配对、24冻结前向；第四组负例保留 |
| E05 | PASS（实验执行），物理定义未闭合 | 有来源有限单因素、32个替代输入，无参数择优 |
| E06 | PASS（代表帧） | 全点/相交柱逐值冻结，外部删除仍降分 |
| E07 | PASS（执行追踪） | 所有前向最终输出逐值复现，排序/解码/NMS来源 |
| E08 | PASS | 15摘要/16CSV/逐帧JSON/原始日志/17索引/18完整性/回传 |
| G01 | BLOCKED | 无CUDA，原生ATen CPU扩展也缺MSVC；host shim不冒充GPU等价 |
| L01 | NOT_RUN | 没有精确GT或物理标定 |
| D01 | NOT_RUN | 没有设备/采集/部署/生产接管 |

实际1192次PointPillars CPU前向（含修正复验），数目只是执行记录。大数组在artifacts/det03_*新目录；17_artifact_index.json逐文件SHA绑定。日志01/02/03/04/05/06/07/10/11/12/13/14保存全部失败与成功。命令和代码SHA见17_run_manifest.json；消费资产/主树对照见18_integrity.json。现行代码快照与修复前代码都保留，不commit/push。

最终完整性：原树master/HEAD未变；5169个基线文件中观察到3个外部文档/日志变化（human_capture README、new_sessions_person_probe README及structure_probe.log），本轮未写入或回滚它们，不能声称整个原树字节全未变。五源会话、模型、原冻结代码与旧实验消费资产共3211项SHA全部不变。详细前后SHA见18；本轮写入清单仅实验树sidequest与DET-03文档/证据。
'''
    (OUT/'README.md').write_text(text,encoding='utf-8')
    print(json.dumps(dict(pairs=len(pairs),postprocess_changes=changes,summary=summary),indent=2))


if __name__=='__main__':main()
