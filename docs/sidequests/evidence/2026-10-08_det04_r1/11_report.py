"""Render DET-04 tables from immutable experiment outputs; never rerun inference."""
import json
from pathlib import Path
import hashlib

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def load(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))


def table(headers, rows):
    return '\n'.join(['|'+'|'.join(headers)+'|', '|'+'|'.join(['---']*len(headers))+'|']+
                     ['|'+'|'.join(map(str,r))+'|' for r in rows])


def num(x):
    return 'null（恒定）' if x is None else f'{x:.3f}'


a=load('06_deletion_rows.json');c=load('06_comparisons.json');att=load('07_attribution.json')['rows']
dose=load('03_dose_summary.json')['groups'];neg=load('04_negative_anatomy.json')['rows'];fp=load('05_fp_anatomy.json')['rows']
short=[];allmetrics=[];negative=[];fptable=[];dose_table=[]
for r in att:
    rr=[q for q in a if q['sid']==r['sid']]
    short.append([r['sid'][-6:],num(r['base']),f"{num(r['ce_range'][0])}–{num(r['ce_range'][1])}",
                  num(r['outside_zero']),num(r['ground_kept']),f"{r['ground_delta']:+.3f}",
                  f"{rr[0]['local_frozen_pillars']} / {rr[1]['outside_ground_pillars']}"])
for sid in dict.fromkeys(r['sid'] for r in a):
    for r in [q for q in c+a if q['sid']==sid]:
        s=r['stages']['clockwise']
        allmetrics.append([sid[-6:],r.get('variant','B_workspace')[0],r['experiment'],num(r['local_anchor_max']),
                           num(r['raw_containing_max']),num(s['final_target_max']),num(r['global_raw_ped_max']),num(s['final_global_ped_max'])])
for r in dose:
    x,y=r['correlations']['cylinder_over32'],r['correlations']['upper_band_gain']
    dose_table.append([r['sid'][-6:],r['variant'][0],r['n'],f"{x['min']}–{x['max']}",num(x['pearson']),num(x['spearman']),
                       f"{y['min']}–{y['max']}",num(y['pearson']),num(y['spearman'])])
for r in neg:
    negative.append([r['variant'][0],r['index'],f"{r['head_delta']:+.6f}",r['upper_band_gain'],
                     str(r['base_winner']['anchor_id'])+'→'+str(r['zrank_winner']['anchor_id']),
                     r['most_negative_local']['anchor_id'],f"{r['most_negative_local']['delta']:+.6f}",r['local_changed']])
for r in fp:
    coords={tuple(q) for q in r['footprint_coords']}
    parts=[q for q in r['pillar_details'] if tuple(q['coord']) in coords]
    bands=lambda key:[sum(p[key][i] for p in parts) for i in range(7)]
    b,z=bands('first32_bands'),bands('zrank32_bands')
    fptable.append([r['sid'][-6:]+'/'+str(r['index']),r['anchor_id'],num(r['score']),num(r['first32_same_anchor_score']),
                    r['support_pillars'],r['footprint_pillars'],sum(p['input_count'] for p in parts),
                    f"{b[5]}→{z[5]}",f"{b[6]}→{z[6]}",','.join(f'{v:.2f}' for v in r['anchor'][:2])])

statuses={k:'PASS' for k in ['S01','A01','A02','B01','C01','F01','T01','R01','R02']}
statuses.update(E03='BLOCKED',G01='BLOCKED',L01='NOT_RUN',D01='NOT_RUN')
evidence=dict(S01='00 baseline / plan / acceptance / 18 integrity',A01='01 audit / 06 deletion / 10 independent tensor-ID checks',
              A02='06 comparisons / 07 attribution / full metric table',B01='03 dose rows/CSV/summary; 506 pairs; 0 forwards',
              C01='04 negative anatomy; 7 frames; complete local anchors; 0 forwards',F01='05 FP anatomy; 7 anchors/support NPZ; 0 forwards',
              T01='08 regression: 10 tests -B -W error exit0; 09 experiment exit0',
              R01='17 index / code diff / manifest; 18 integrity; numbered logs',R02='return append / top README / this report / options',
              E03='DET-03 resource limitation inherited; native ATen not run',G01='10: torch2.12.0+cpu CUDA false; no GPU round authorized',
              L01='No labels/physical calibration executed',D01='No device/network/driver/deploy/capture/production actions')
accept=table(['ID','作者自验','证据'],[[k,v,evidence[k]] for k,v in statuses.items()])
text=f'''# DET-04：同扫描背景删除对照与机制归因

2026-10-08；SUBMITTED，作者自验，未 ACCEPTED。唯一 [验收v1](../../DET04_ACCEPTANCE.md) / [预注册计划](../../DET04_PLAN.md)。独立 sidequest；唯一 writer Codex；工作树 `C:/Users/30680/.codex/worktrees/human-detector-models/ldiar`，分支 `codex/human-detector-models`，HEAD `cfbb80c57508be1a0435fdb92260f698dc763934`。ponytail full 实际路径 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`（本会话未暴露独立 skill API，按文件规则加载）。

## 结论与证据边界

同扫描 counts 删除对照产生会话分歧：前三个固定 B 帧只保留圆柱相交柱后，local 分数从 0.056/0.233/0.303 升到 0.348/0.483/0.476；第四组从 0.356 降到 0.133。**背景是否存在本身不能统一解释低分，具体保留的外围结构会改变分类响应。** 加回预注册的近地面整柱使前三组下降 0.167/0.245/0.171；第四组下降 0.016，未越过预注册 0.02 效应阈值。这支持本固定地面带整柱上下文的因果贡献，不证明所有地面都抑制行人，也不是实际检测质量改善。

输入审计确认 DET-03 `context_cloud` 始终从 B 的同扫描点值/顺序中按 C/E ID 做选择。16 个存档 input/ID SHA 完全复现，**未注入外来 XYZI**。空场模板和配准 WARN 参与的是删除决策。故本轮不能将较高的 outside_zero 分数归因于“外来点内容污染”；更具体的解释候选是不同删除形状、地面与剩余外围结构。此解释边界已写在结果产生前的计划里；历史 DET-03 证据不回填，其 yaw 修复/分类头不变/采样有贡献但非充分原因等起点保持。

506 对描述性分析中，1.5–1.8m 增益与 head_delta 没有跨会话同向关系；215643 B 的 Pearson/Spearman 为 −0.556/−0.606。7 个负帧均有上带覆盖增益，存在具体 anchor 的负响应，不能称“这些帧没有恢复覆盖”。空场三留帧均在同一 anchor158179（XY≈3.68,−0.48m）出现 0.501–0.515 行人响应，footprint 上带/最高带覆盖也增加；高度覆盖对非人体结构同样可提升响应。单一主因仍未确定，不报准确率、P/R、误报率或可用性。

## H-A：冻结 B 输入，只删除同扫描外围柱

固定 32/33/33/28 帧、first32、0.55m/[0.05,2.30]m 原圆柱相交键。地面带 [-0.15,0.30]m 含端点，要求柱内全部原有效点在带内；只保留整柱，不在柱内二次改采样。基线总柱 795/791/796/879，相交柱22/21/17/13，额外近地面柱33/36/36/36。

完整 canonical voxel/坐标/源 ID 表不变，删除柱 counts=0。上游编码器有 counts 除法，实际前向仅送非零柱，因此删除位置 scatter 为零；保留位置 canvas 与原 B 逐值相等，没有 BN 伪零柱或 NaN。10 独立复核重新构造源 ID/global rows/voxel/counts，并核对有限 heads；本轮仅 8 次新网络前向。

{table(['会话','B local','C/E context-pillar区间','outside_zero','ground_kept','地面Δ','局部柱 / 额外地面柱'],short)}

预注册判定未被结果后改动：outside_zero 四组均不在 B±0.02，也均不在 C/E context-pillar 区间±0.02。215540 的原B与C/E差本就不足0.04，不能用其基线作二分归因。前三组为反向增强，第四组为中间且更接近C/E（距上界0.027，**仍不称CE-like**）。ground_kept 在215607/215623数值接近 B，但不是与高分 outside_zero 的最佳组合；所有变体同等保留。没有证明外来内容主导或背景存在性主导。

完整分列：local=种子0.55m anchor原始最高，containing=解码包含种子最高，final=最终位置框最高，global raw/final=全场行人最高。0表示该阶段没有符合项，不是人体GT的miss标签。已有对照复用修正yaw后的DET-03代表artifact：

{table(['会话','输入','实验','local','containing','final位置','global raw','global final'],allmetrics)}

## H-B：零新前向的剂量—响应

原 all_r1 rows 的506组同帧B/E配对，逐帧保存before/first32/zrank七高度带与输入SHA。主剂量为圆柱内点>32柱数；另列“相交整柱input_counts>32”。这批数据两口径逐帧相同，但仍分列存档，不能一般化合并。旧pillar张量逐值复核，只有重新分组/选点，没有网络前向。

{table(['会话','输入','n','圆柱>32范围','Pearson','Spearman','上带增益范围','Pearson','Spearman'],dose_table)}

215540两输入的柱数恒为7，相关为null，不能将缺变异解释为无效应。其余柱数与分差相关较弱或随输入不同；上带增益相关有正有负。本表仅会话内部连续帧的描述，无p值/显著性/独立样本宣称，也不证明某高度帯的纯人体机制。

## H-C：215643全部负收益帧

{table(['输入','帧','local Δ','上带增益','赢家anchor','最负local anchor','该anchor Δ','变化local数'],negative)}

7帧上带增益均为+7到+13，七带仍全部有记录。按预注册规则全部属于“代理覆盖改善但具体 anchor 负响应”，不是覆盖未改善。多数赢家仍是原anchor；B28从158154迁到159450，原赢家/其他local响应下降，故只看新峰值会掩盖同一anchor退化。B28最负local158156下降0.07587，强于其最高分下降0.01633。

04包含逐柱原点数/圆柱点数/first32与zrank的完整选入z/七带/prepared ID/raw global row、完整local变化集合、共同存档candidate变化及top100进出。原all trace并未保存全场每个anchor；未存全场集合不伪称完整。变化集合定位模型响应，不证明人体部位因果，且全场覆盖采样仍可能改变外围上下文；本轮不增加消融或人工标注。

## H-D：空场FP与真人anchor支撑并列

支撑是网络结构允许的潜在感受野占用柱（最深路径147×147 lattice，已按branch卷积/stride/转置卷积反推），不是saliency或关键柱因果标签。另列decoded footprint内的柱中心。支撑包括大量外围场景，空场1602/1592/1593柱，对比B裁剪后真人795/791/796/879柱；不把这一区别当作因果分数来源。真实人体种子位置没有精确点GT。

{table(['会话/帧','anchor','zrank分','同anchor first分','结构支撑柱','footprint柱','footprint源点','footprint1.5–1.8','footprint≥1.8','anchor XY'],fptable)}

三空场峰值固定在同一anchor158179、其解码中心约(3.63,−0.49)m，footprint源点约1050，源z顶约1.90m。first32最高带没有选入点，zrank选入10/11/11点；1.5–1.8m从7/4/6升至29/26/28。因此“恢复高点后高分”在明确无人结构上也成立，是必须保留的判别力负例。不能凭这些点称椅子/墙/人体部位，也不能推出某柱具有因果支撑作用。05及support NPZ提供各柱计数、源prepared/raw global IDs和完整选点z分布；只用233658一个无人模板的三留帧，不报误报率。

## 逐ID作者自验

{accept}

## 下一步三选一（均需新的用户明确授权）

(a) **建议优先：人体点GT标注轮。** 先给四固定代表帧与7负帧做prepared/raw row绑定的人体、邻近家具、混合/不确定点标签（未标点不默认背景）；冻结帧集、坐标变换与框/位置GT版本。只在全部点均为人体的纯人体柱内切换first32/覆盖，混合柱及所有外围柱逐值冻结，不再全场改变选点。逐帧报告GT位置分、最近竞争位分与二者边距、GT匹配anchor相对排名及框空间匹配；GT规则与竞争位最小分隔先声明，不能用全场最高/跨帧中位冒充识别指标。现有同一人/近站位仅诊断；独立人/场景泛化与新增数据另行授权。本轮仅设计，未标注。

(b) **已标定强度/z与同传感器权重适配轮。** 用户授权后先绑定可追溯物理/辐射标定，再固定输入定义比较同传感器权重；训练/数据/标注均另定范围，不临时试除数或z偏移择优。本轮不启动标定/训练或dormant ML。

(c) **GPU/原生ATen等价轮。** 用户授权兼容环境/GPU资源后，固定commit/checkpoint/现有输入，逐值比较体素、特征、cls/reg/dir及后处理；解开E03/G01资源阻塞。该轮先解决实现等价，不承诺解决识别泛化。

## 文件与执行记录

00当前基线包含原树5190项、实验树10606项（跟踪/未跟踪/忽略）；旧3211消费资产口径未变。01同类artifact与context来源审计；02预运行config；03剂量rows/CSV/summary；04负帧完整解剖；05FP完整解剖；06新删除rows/jsonl及旧对照；07条件归因；08回归（10tests exit0）；09唯一实验（8网络前向 exit0）；10独立张量/源ID检查（0网络前向 exit0）；11报告生成；17代码diff/快照/manifest/逐文件SHA索引；18收尾完整性与消费资产变化；22验收范围。大数组在新忽略目录 `sidequests/human_detectors/artifacts/det04_r1/`。

00b保留读schema时的KeyError:0（索引为dict而非list，exit1，非模型失败）；首次skill读取受PowerShell profile缺oh-my-posh/PSReadLine影响，技能正文已读取，其后命令均login=false。08/09/10均通过，不删失败。旧DET-03运行/证据未修改，主树本轮只读，完整变化按18/22实录。SHA/index文件不自引用自身；最终封口索引显式列排除项。执行PASS不等于识别可用。
'''
with (HERE/'README.md').open('x',encoding='utf-8') as f:f.write(text)
with (HERE.parents[1]/'DET04_ACCEPTANCE.md').open('a',encoding='utf-8') as f:
    f.write('\n\n## R1 最终作者自验（2026-10-08，SUBMITTED）\n\n'+accept+'\n\n完整性详见18/22；执行PASS不等于识别可用。\n')
readme=REPO/'sidequests/human_detectors/README.md'
original=readme.read_text(encoding='utf-8')
entry='最新（2026-10-08）：[DET-04同扫描背景删除与机制归因](../../docs/sidequests/evidence/2026-10-08_det04_r1/README.md)，[预注册计划](../../docs/sidequests/DET04_PLAN.md)/[唯一验收v1](../../docs/sidequests/DET04_ACCEPTANCE.md)。8次新前向：前三固定帧相交柱独留增分、加回预声明近地面柱降分，第四帧独留降分；背景存在性不能统一解释。审计旧context为B同扫描点按C/E源ID选取，无外来XYZI注入。506对描述相关、7负帧均覆盖改善却anchor负响应、三空场同anchor≥0.5全部保留；单一主因/识别可用性未定。SUBMITTED，未ACCEPTED，主线继续暂停。\n\n'
heading,body=original.split('\n',1)
readme.write_text(heading+'\n\n'+entry+body.lstrip('\n'),encoding='utf-8')
acc=HERE.parents[1]/'DET04_ACCEPTANCE.md'
ret=HERE.parents[1]/'returns/DET-04.md'
return_text=f'''\n\n## DET-04 R1 — 2026-10-08 / Codex / SUBMITTED

- 唯一验收：docs/sidequests/DET04_ACCEPTANCE.md v1，提交SHA `{hashlib.sha256(acc.read_bytes()).hexdigest()}`；先行计划/当前baseline→实现→实验。
- 唯一writer Codex；实际本机Python3.12.10/PyTorch2.12.0+cpu，原固定PointPillars checkpoint；分支codex/human-detector-models，起始/结束HEAD cfbb80c57508be1a0435fdb92260f698dc763934；主树只读，无部署/采集/标注/提交/推送。
- ponytail full 实际读取路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。无独立skill API，按文件加载规则读取；未委派writer。

### 集中诊断与根因边界

只保留B同扫描圆柱相交柱，前三组local 0.056/0.233/0.303→0.348/0.483/0.476，第四0.356→0.133；加回固定[-0.15,0.30]m全部点整柱，前三下降0.167/0.245/0.171。冻结柱完整tensor/counts/源ID、retained encoder canvas逐值一致、deleted scatter为零。零counts直接进入上游encoder会除零；本实现保留完整审计零counts表，前向只发送非零柱，未改上游或权重。

既有context_cloud输出逐值为B点按C/E源ID删选，16输入/ID SHA重现；没有外来点值注入，故不能用本轮高分归因外来XYZI。外围结构与地面上下文有因果支持，统一主因仍未定。506对描述相关不作显著性；7负帧上带均增加、具体local anchor下降；empty17/35/53均同anchor158179约0.50–0.51，footprint高度覆盖提升也提高无人响应，不报误报率/P/R或识别可用。

### 实际变更

新 sidequests/human_detectors/det04.py；test_experiment.py新增冻结/删除/地面边界与感受野回归；README顶部同步。DET04计划/验收表、本轮新证据与新忽略artifacts/回传；DET-03未提交文件已纳入baseline，历史证据未回填。代码diff/源码SHA见17，完整消费资产变化及工作树变化见18/22。

### 逐ID自验

{accept}

### 验证、消费资产与未闭合

python -B -W error现有test_experiment.py 10tests exit0；唯一实验09 exit0，8新网络前向；H-B/C/D与独立复核0新网络前向。00b读schema失败保留，不是实验失败。原3211消费资产和DET-03忽略产物按当前baseline复核，差异清单见18；本轮新增消费既有DET-03 rows/config/trace/pillars和本轮代码/计划/config，绑定00/17，未改源会话/上游/权重/变换。

E03/G01仍BLOCKED；L01/D01 NOT_RUN；人体/家具GT、物理标定与泛化未闭合。执行PASS不等于识别可用，未自行ACCEPTED。

下一步三选一均需用户另行明确授权：优先(a)人体点GT后外围固定、纯人体柱覆盖，指标含GT人位/最近竞争位边距与GT相对排名；(b)已标定强度/z与同传感器权重适配；(c)GPU/原生ATen等价。完整(a)设计草案见报告，本轮未执行标注。

复审入口：[完整报告](../evidence/2026-10-08_det04_r1/README.md)，[唯一验收v1](../DET04_ACCEPTANCE.md)，编号日志/17diff+SHA/18完整性/22范围。当前状态SUBMITTED，等待独立复审或用户选下一轮。
'''
with ret.open('a',encoding='utf-8') as f:f.write(return_text)
print('Report / acceptance final self-check / top README / return append complete; no inference')
