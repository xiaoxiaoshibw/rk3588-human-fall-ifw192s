"""Create reviewable reports from measured JSON. Exclusive writes, no result rewriting."""
import difflib
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).parent
ROOT = OUT.parents[3]
def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))
def put(name, text):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as f:
        f.write(text + '\n')
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

pts = read('01_absorbed_points.json')
attr = read('03_confirmation_attribution_r2.json')
shadow = read('06_shadow_results.json')
gate = read('07_gate_samples.json')
cleanup = read('05_cleanup_attribution.json')
fault = read('06_fault_regression.json')
r36 = read('05_r36_equivalence.json')
unit = json.loads((OUT / '05_registration.stdout.log').read_text(encoding='utf-8'))
accept = ROOT / 'docs/human_capture/evidence/2026-10-07_hrw03_r37_productionization/06_test_matrix.md'
bound = shadow['registration']['code_binding']
current = shadow['registration']['current_code_binding']
source = ROOT / 'pc_apps/human_replay/human_pipe_lib.js'
original = OUT / 'baseline_code/pc_apps/human_replay/human_pipe_lib.js'
put('05_metric_fix.diff', ''.join(difflib.unified_diff(original.read_text(encoding='utf-8').splitlines(True), source.read_text(encoding='utf-8').splitlines(True), fromfile='baseline/human_pipe_lib.js', tofile='current/human_pipe_lib.js')))
bindings = {'input_files': read('00_snapshot_inputs.json'), 'artifact_id': pts['registration_artifact_id'],
            'artifact_code': bound, 'current_code': current, 'acceptance': {'path': str(accept), 'version': 'v1', 'sha256': sha(accept)},
            'frozen_params': {'PIPE': 'all unchanged (synthetic equality + three-line diff)', 'gate': gate['params']},
            'tools_sha': {p.name: sha(p) for p in OUT.iterdir() if p.suffix in ('.js', '.py', '.html') and p.name != '09_viewer_manifest.js'},
            'runtime': 'Node v24.14.0; Python wrappers with -B -W error'}
put('09_input_source_sha.json', json.dumps(bindings, ensure_ascii=False, indent=2))

byframe = {}
for p in pts['points']:
    f = byframe.setdefault(p['frame'], {'crop': 0, 'reference': 0})
    f['crop' if p['mechanism'] == 'WORKSPACE_CROP' else 'reference'] += 1
table = '\n'.join(f"| {f} | {v['crop']} | {v['reference']} | {v['crop']+v['reference']} |" for f, v in byframe.items())
pointrows = []
for p in pts['points']:
    xyz = ', '.join(f'{v:.9f}' for v in p['source_xyz'])
    hit = p['reference_match']
    pointrows.append(f"| f{p['frame']}/p{p['original_point_index']} | {p['frame_seq']} | {xyz} | {p['registered_xyz'][2]:.9f} | {p['mechanism']} | {p['P_path']['track']} | {p['nearest_reference_voxel']['distance']:.6f} | UNKNOWN |")
put('02_absorbed_points_analysis.md', f'''# 31 点逐点审计结果

**删除机制已闭合；人体语义仍 BLOCKED_BY_GT。** 不是“31 点都被 reference 吃掉”。30 点是 registration 后越过既有 workspace 下界 0.10m，1 点是在 workspace 内被 reference matcher 命中。

原 clean 窗口 31 点逐位复现；全部 source z<0.3。7 帧 / 7 个 frame-cluster / 一个 P candidate track id=1 涉及29点；另外2点在 P cleanup 后已不属于输出候选。其中 f63/p10660 为 crop，f63/p12476 为 reference。候选归属不等同真人 GT，29 点不可自动叫人脚，也不可叫地面。

| frame index（从0） | workspace crop | reference | 合计 |
|---|---:|---:|---:|
{table}

0.3–0.6、>0.6 带损失均0。clean cohort 包括10帧，实际有损失的是 f63/65/85/90/99/123/146；其他 f80/92/95 未损失。

## 删除为何发生

30点 source z≈0.10002–0.12051m，变换后低于0.10；实际过滤顺序先裁剪后 reference/online，部分点虽同时有潜在 reference 命中，也不能把第一原因改成 reference。当前 transform 原样保存于06，未改 leveling 或工作空间。只查代码不能判断这次高度变化是正确地面消除还是脚腿有效结构损失。

唯一 reference 点 f63/p12476：source=(0.899293125,0.152073830,0.290433317)，registered z=0.279997349；原邻域遍历第一个 reference 命中距0.110394m，全图最近入图 voxel 形心距0.064961m。registered-online 也命中0.111808m；无 registration 查询 reference 亦命中0.088915m。因此这是实际注册路径上的 reference 删除，不能声称 registration 新制造该匹配。该点已被 P cleanup 删除，仍保留在预注册 cleanup 前安全 cohort 中，不自行从31总数扣掉。

参考图有 obs（observed帧数）、occ、pts/jit/confidence，无 strong/supported tier 字段；obs 就是 reference 命中帧支撑。online 记录则有 hits/tier。01 JSON 保留第一命中及全局最近 voxel、两种 online 命中、未注册 reference 反事实、逐点身份与路径状态。

## 每个具体点

坐标单位m，source=绑定 job 的 leveled_session；S z 为 float32 的注册值。原 point index 为帧内 index，另在01保存 session全局 index、28B stride字节offset和时间戳。匹配前景四元组与 raw point identity；归属断言逐簇 n 相等，未发现重复身份/漏计。

| frame/point | ROS seq | source x,y,z | S z | 第一删除机制 | P candidate track | 最近 reference centroid(m) | 人工语义 |
|---|---:|---|---:|---|---|---:|---|
{chr(10).join(pointrows)}

**语义数量：FOOT_SHOE=0（已标注）、LOWER_LEG=0、GROUND_RESIDUE=0、MIXED=0、错配=0、UNKNOWN=31。零表示未获得标签，不是证明不存在该类。**

人工入口：[09_point_review.html](09_point_review.html)。需同时看 f63上下文和连续相邻帧；用逐点标注区分鞋/脚、下腿、地面、混合、错配、无法判断。viewer 不自动填 ground、不写 captures。JSON/HTML 仅做诊断；人工看到外形不自动产生精确点级 GT。
''')

cats = ['STATIC_REMOVAL_EXPECTED','CLUSTER_TOPOLOGY_CHANGE','TRACK_ID_REASSIGNMENT','HUMAN_CANDIDATE_GAIN','HUMAN_CANDIDATE_LOSS','REFERENCE_ABSORPTION','CLEANUP_SIDE_EFFECT','UNKNOWN']
cat_table = '\n'.join('| '+cat+' | '+' | '.join(str(attr['categories'].get(k+'|'+cat,0)) for k in ['new_green','new_purple','disappeared'])+' |' for cat in cats)
nonstatic = [v for v in attr['rows'] if v['attribution_category'] != 'STATIC_REMOVAL_EXPECTED']
needed_frames = sorted({v['frame'] for v in nonstatic})
put('04_confirmation_attribution.md', f'''# Confirmation 变化归因（当前为 r2）

现行逐行证据：[03_confirmation_attribution_r2.json](03_confirmation_attribution_r2.json)，257 行；首次 [03_confirmation_attribution.json](03_confirmation_attribution.json) 保留为 superseded。初次诊断把7个参考删除占主导的行因同时有1–4点 cleanup 标成 CLEANUP_SIDE_EFFECT；r2纠正为 REFERENCE_ABSORPTION，并补两分支逐帧 track 历史/票。首次 refinement 断言误填267而实际257，退出1日志保留；修正计数断言后 exit0，不改任何实验输入/管线。

严格复现 R38 原行集合：new green 61、new purple 70、disappeared confirmed track 行126、missed events0。green=track_confirmed；原 harness purple=joint==CONFIRMED_HUMAN，**并非 UI 的紫色 HUMAN_CANDIDATE**。这些是逐 frame-cluster 行，可重叠，不是人数。

| primary attribution | 新 green | 新 purple（原命名） | 消失 confirmation |
|---|---:|---:|---:|
{cat_table}

green 总行数 P132→S67，净-65；purple P152→S85，净-67。新增与消失不等于净delta，也不等于 FP/FN。

## 家具和人体候选分别发生了什么

102个消失行的 P cluster 位于已登记 WD01 静态区域，且有 reference 删除支撑，可解释为 STATIC_REMOVAL_EXPECTED（区域金标，不伪造每点标签）。其余24消失行是 reference absorption8、candidate loss6、topology4、track history6；其真实人/物/混合语义未验证。

新增 green 的39个 candidate gain 记录几何门/证据变化；20个 track-history 行记录跨独立 Tracker 的id与确认票变化；2个 topology 行由原始点交集支持。新增 purple：58 candidate gain、11 topology、1 history。**静态残留变少同时改变了非 WD01 候选拓扑与时序，不能仅称“家具清掉了，真人无损”。**

例 f65/P0→S0：两侧 instantaneous joint 均 NON_HUMAN，但 P votes=2/5、S=3/5，故 S track_confirmed=true；不是本帧新确认了一个已知人。f146：共享3293点，仅损失3点，但 P votes=3、S=2，confirmation 消失主要是历史差异，不能叫人体点云消失。id数值不可跨分支互认。

## Topology 与 cleanup 要分开

跨 P/S 输出可分类簇（raw候选先≥3 XY cells，再n≥60）的原始点 overlap graph：884→230 frame-cluster，总计 split10、merge2、disappeared662、appeared0。split是一个P集合与多个S集合分享原始点；不是独立 GT 人体分裂数量，662大多是背景簇移除但不能全自动贴静态语义。

split帧：f46/53/55/56/61/152/153/159/160/164；merge帧：f102/151。f55 P0共享1977点到S0、354点到S1；需要人/物/混合标签来区分去粘连和人体 fragmentation。边、点数比例、形心和几何保留于06 topology.frames。

**cleanup自身实际 split=0/merge=0**，通过同XY key集合对照核实；然而过滤后簇数 delta 并非全0：P69帧减少89簇，S128帧减少230簇，原component整体移除或缩至固定3格候选门以下。对应 `05_cleanup_attribution.json`，它不是 source→registered 的10次跨分支split。旧 T38-06/S7 的严格 delta==0 与无新增确认门仍 FAIL，未偷换为“delta≤0 即 PASS”。

## 缺少的 GT

机械 primary category 已覆盖全部257行，category UNKNOWN=0；但非静态区域的155行真实身份/混合与人体连续性仍 UNKNOWN，这是关键 GT UNKNOWN。需要标这些行的 P/S cluster 是人/物/混合，并标真人 track 是否 preserved/fragmented/lost；P ids={{1,20}}、S ids={{3,4,5}}，缺簇时为null。优先24个非 WD01消失行和10个split帧。完整帧列表：

`{','.join(map(str,needed_frames))}`

缺标签时不能声称“无系统性真人破坏”。与31点标签一起从 viewer 导出 `source:"human"` 格式；绑定原session SHA、leveling job、artifact id，始终保留 UNKNOWN 选项。
''')

gap=gate['gap']
put('07_gate_diagnosis.md', f'''# Registration gate 冻结复核

结论：原 `reg_gate_v1` 仍 **WARN / DEGRADED / SPARSE_CORRESPONDENCE**。49.652981% 确为不足；接近边界不构成PASS或放宽门理由。当前生产 loader 另为 **STALE / REFMAP_DRIFT / METHOD_STALE**，原因是统计修复改变全文件SHA；保持SAFE，未重绑定或写旧artifact。

## 精确分子/分母

- source strong fineStatic(0.06m)：11,959；target occ≥0.9 fineStatic：17,053，其中15,537有有效normal。
- 最终固定0.08m球门：9,897有效对应（82.754% source）；1,684无target、378最近target normal无效；合计2,062 source没有用于求解的pair。
- 60% trim：floor(9897×0.60)=5,938；另外3,959个有效pair仅因固定残差trim剔除。
- gate ratio=5938/11959={gap['ratio_percent']:.9f}%，并非 raw match ratio。50%需 ceil(11959×0.5)=5,980，即多42个keep；相同60% trim需≥9,967 raw pairs，比现在多70。
- 缺口={gap['gap_percentage_points']:.9f} percentage point；不是42点修改就能构造PASS，必须来自既定协议的真实对应支撑。

## 成因分解与可证边界

| 面 | 证据 | 判断 |
|---|---|---|
| correspondence coverage | 1684球门外、378无有效normal，60%trim以后49.653% | 直接可复现的有限支撑不足，是精确gate根因 |
| reference coverage | 2062无效pair中813距occ≥0.5 coarse centroid<0.12m；410连0.30m内coarse支持也没有 | 入图层/normal/fine采样支撑不等价；未观察物理表面不能假定存在 |
| 动态污染 | source来自strong长期占用；无每点动态GT | UNKNOWN，strong不证明静态，更不证明人体不存在 |
| occlusion | 无跨会话射线/可见性GT | UNKNOWN；不能用稀疏对应直接断言遮挡 |
| FOV | source仅sector2–5有支持；sector5 2337source/1137raw/505keep，明显弱于sector2 1869/1845/1259 | 测得空间不均匀，实际FOV/遮挡/场景变化归因UNKNOWN |
| leveling/registration residual | fit p50=14.522mm/p90=57.301mm；holdout p50=11.088mm；condition≈104.272 | 已有pair上残差良好，但条件化残差不能证明未配对点安全；不换解 |
| voxel discretization | frozen coarse/fine bins、51个最近fine距离处于79–81mm附近 | 有边界点；不能证明它们全由量化造成或能补70pair，未改变网格做干预 |
| sample support | fine source n min1/median118/p90=622/max1250003；11,959 samples空间/时间相关 | 数量实测；不能假设iid或编造CI证明统计等价 |

无效pair中1695在0.30m内有fine近邻，367没有；这些桶可能交叠，不能相加当互斥物理根因。原始11959样本、状态、近邻距离、normal、trim身份保留于 `07_gate_samples.json`。

判定：**这是接近门的真实协议支撑不足；现有单pair数据不能把它裁决成无害统计边界。** 即使数值距离门小，预注册50%保持。matcher/ICP/normal半径/trim/PIPE/leveling/R/t均未修改，gate脚本只做固定解诊断；R3.6回归另按原数学复算，不用于替换解。

artifact id=`{pts['registration_artifact_id']}`。transform/旧code binding/当前code binding见06.registration；matrix、method文件SHA未变。注册/参考图数据digest未变，但全文件builder身份变化使旧loader如实STale。
''')

tests = [('新 metric/attribution 单测','05_metrics','PASS'),('新增 attribution r2 回归','05_attribution','PASS'),
         ('human_pipe_lib.test.js','05_pipe','PASS'),('human_replay_lib.test.js','05_replay','PASS'),
         ('registration artifact/load 单元回归','05_registration','PASS'),('原R3.6 equivalence/digest 回归','05_r36','PASS'),
         ('故障/当前STALE全帧SAFE回归','06_faults','PASS'),('gate固定解诊断','07_gate','PASS'),
         ('完整165帧shadow + 第二跑','06_shadow_after','FAIL')]
test_table='\n'.join(f"| {title} | {state} | {read(name+'.run.json')['exit_code']} | `{name}.stdout.log` / `.stderr.log` / `.run.json` |" for title,name,state in tests)
idrows=unit + shadow['rows'] + fault
idrows.append({'id':'T38-01','result':'PASS'})
assert len({v['id'] for v in idrows}) == len(idrows)
acceptance_table='\n'.join(f"| {v['id']} | {v['result']} | "+ ('05_registration.stdout.log' if v in unit else '05_r36_equivalence.json' if v['id']=='T38-01' else '06_fault_regression.json' if v in fault else '06_shadow_results.json')+' |' for v in idrows)
put('08_final_closeout.md', f'''# HR-W03 最终收口提交（2026-10-07）

## 1. W03 最终状态

**REWORK_REQUIRED**；writer自验 SUBMITTED，未 ACCEPTED。GT子问题 BLOCKED。gate未过、31点语义UNKNOWN、非WD01真人连续性UNKNOWN与严格共同门FAIL，不能仅把整单叫“缺GT”；即使补GT也不能绕过gate。W03保留，W04–W09/registration R3.9 production未启动。

## 2. 31 个点是什么

30 workspace crop + 1 reference match；语义UNKNOWN31，无人工已验 ground/脚/腿标签。29点在P输出候选track1，2点原已被P cleanup移除。7帧 f63/65/85/90/99/123/146、7个frame-cluster、1个candidate track；z<0.3=31，0.3–0.6=0，>0.6=0。逐点31行见02/01，截图/点云外观不代替GT。

## 3. Confirmation 为什么变化

new green61：gain39/history20/topology2；new purple70：gain58/history1/topology11；disappeared126：WD01静态期望102/reference8/history6/candidate-loss6/topology4。净green -65（132→67），净purple -67（152→85），event-loss0。不能称FP/FN。

既清掉静态家具，也改变非WD01候选的点成员、几何门、拓扑和时序；非静态155行的真实人/物/混合与真人track连续性仍UNKNOWN。P/S overlap split10/merge2，不等同真人fragmentation GT。cleanup自身split/merge0；计数delta减少并非分裂，严格delta==0仍FAIL。

现行归因文件为 `03_confirmation_attribution_r2.json`，首次03保留为superseded；r2修正过度归因cleanup和时序票解释。所有257行带frame/track/形心/点数/高宽深半径/upcos/证据/标签/删除机制/历史与原因。

## 4. Registration gate

冻结 ratio=5938/11959=49.652981%<50%；9897raw×60%trim→5938keep，差42keep/70raw。1684缺球门对应、378normal不足，reference覆盖与空间分布不均匀可测；动态/遮挡/FOV/量化具体因果仍UNKNOWN。接近门不证明无害边界，未放宽/调参/换解。

历史绑定sandbox loader DEGRADED；统计修复后当前loader STALE（METHOD_STALE/REFMAP_DRIFT），全帧SAFE=P已验证。未修改旧artifact；原R/t和输入不变。身份和源码SHA见09_input_source_sha/06.registration。

## 5. 修复内容

生产唯一修改 `pc_apps/human_replay/human_pipe_lib.js` 三个表达式：delta 用数组length相减，before/after显示字段返回length。BUG-R39-M01先复现/登记，随后修改；diff=`05_metric_fix.diff`。PIPE/cleanup/聚类/分类/Tracker/Fall/registration/leveling算法不改。新工具全部在本轮evidence目录：逐点/归因/shadow/gate/统计回归、复用Three.js/OrbitControls的viewer、GT校验、记录/SHA工具。

所有165帧P/S **非诊断字段逐位相同**（对R38）；cleanup点云及人形/track/events没有因统计修复改变。诊断数值有限，fg与candidate分区守恒通过。P/S behavior digest分别 `{shadow['P']['behavior_digest']}` / `{shadow['S']['behavior_digest']}`。完整JSON digest随诊断schema正常变化，不把变化隐藏。

旧R3.6原代码sandbox完整digest复现 `{r36['historical']['digest']}`；当前源码执行原script的19项/全部algorithm-result projection、CSV SHA均相等。其完整digest变成 `{r36['after_metric_fix']['digest']}`，因为包括PL SHA；这不是逐点算法漂移，且没改写旧结果。

## 6. 回归及验收

| 检查 | 状态 | 实际exit | 真实记录 |
|---|---|---:|---|
{test_table}

完整shadow的exit1是预注册T38-05/06失败，不是运行崩溃。新 metric5项、r2 attribution5项、旧pipe35项、replay45项通过；registration逐ID见下，不以单测数宣布收口。

唯一验收表：R3.7 `06_test_matrix.md` v1，SHA `{sha(accept)}`。所有状态是本机作者自验。

| ID | 状态 | 当前证据 |
|---|---|---|
{acceptance_table}
| T39-01–08 | NOT_RUN | registration生产未授权 |
| HP02 真人弯腰 | BLOCKED | 缺真人数据，合成不替代 |
| 设备/物理/部署/采集 | NOT_RUN | 本轮未授权 |
| W04–W09 | NOT_RUN | 本轮明确禁止 |

S1/2/3/5/6 PASS，S4/7 FAIL。T38-06可有限信赖，但值并非全0，且new confirmation门未过；不把修复NaN冒称共同门PASS。

## 7. 当前人体识别能力

已验证：冻结pair/165帧本机离线背景残留 WD01 93423→1754（98.1225%），WD02 159247→24508（84.6101%）；artifact绑定失效安全回退；统计修复输出等价/确定性与机械删除归因。

尚未验证：31点实际语义、155个非静态变化行真人身份和连续性、HP02真人弯腰、正式20–60s空场及跨距离/多人/遮挡、设备实时/物理外参、实际姿态/骨架/跌倒性能。

不能声称：人体识别准确率/Precision/Recall/F1、真人无损/无系统性track破坏、姿态精度、跌倒误报率/检测延迟。98.1%/84.6%仅是指定背景窗口残留改善。

## 8. 是否可以进入 W04

**不可以。** gate未过；31点语义可能包含脚腿；非WD01拓扑/候选损失的真人GT尚未闭合；原共同门FAIL。下一步仅人工GT与既定gate支撑/契约设计审查，不能顺手调matcher或继续骨架。

## 人工如何闭合 GT

打开 `09_point_review.html`（153帧分文件加载；原坐标未抽稀/舍入）；初始UNKNOWN，分别看P、S和损失点，查看逐行JSON。优先标31点的7帧、24个非WD01消失行、10split/2merge帧；其余非静态155行的完整帧清单见04。需标签：FOOT_SHOE/LOWER_LEG/GROUND_RESIDUE/HUMAN_GROUND_MIXED/REGISTRATION_REFERENCE_MISMATCH/UNKNOWN，以及cluster PERSON/STATIC_OBJECT/MIXED/UNKNOWN、连续性PRESERVED/FRAGMENTED/LOST/STATIC_NOT_HUMAN/UNKNOWN。导出必须填写标注人，写派生文件；不写原session。source="human"只有人工导出的标签，不把当前诊断改成human。

完成后先运行（输出必须新文件）：

```powershell
node docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/review_gt.js <人工导出.json> <新的GT复核结果.json>
```

GT脚本校验点id、frame/seq/track、来源SHA与leveling/artifact绑定；GT不能自行放行gate。需要再次跑全链时建立新evidence轮，将工具和baseline_code复制到新轮，`closeout_shadow.js --phase=after` 重新复现；当前固定结果均独占写入（wx），不能覆盖本轮。真实GT完成前不继续调算法。

## 证据与纪律

00_baseline含5466个原文件（含untracked/ignored可读输入及symlink身份）、branch/HEAD/dirty状态；收尾09_scope_check报告授权三行和文档增量。各run.json保存运行参数、真实exit与stdout/stderr；输入/sourceSHA见09_input_source_sha。历史结果、首次失败、原始captures均保留。未commit/push/reset/checkout/clean/部署/采集。ponytail实读 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`，full。仅writer自验，独立复审NOT_RUN。
''')

put('09_gt_pending.json', json.dumps({'state':'BLOCKED_BY_GT','point_ids':[p['id'] for p in pts['points']],
    'point_frames':sorted(byframe), 'confirmation_rows':[{'id':v['id'],'frame':v['frame'],'P_track_id':v['P_track_id'],'S_track_id':v['S_track_id']} for v in nonstatic],
    'confirmation_frames':needed_frames,'priority':'31 points, 24 non-WD01 disappearances, 10 split frames, 2 merge frames',
    'format':'review_gt.js / 09_point_review.js export; source human only after manual review'}, ensure_ascii=False, indent=2))
print(json.dumps({'reports':['02','04','07','08'], 'state':'REWORK_REQUIRED','source_sha':sha(source)}))
