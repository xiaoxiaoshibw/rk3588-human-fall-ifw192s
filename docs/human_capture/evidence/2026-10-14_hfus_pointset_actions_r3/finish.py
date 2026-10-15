"""One final research report from measured outputs, with failures and unknowns retained."""
import sys,json,collections
from pathlib import Path
import numpy as np
root=Path('D:/Code/ldiar');here=root/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(here))
from actions import read,sha,dump
e=Path(__file__).resolve().parent;out=here/'action_research_r3'
comparison=read(e/'EXPERIMENT_COMPARISON.json');old=read(root/'docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r2/EXPERIMENT_COMPARISON.json')
hard=[('cap_20261013_082623',192),('cap_20261013_082717',140),('cap_20261013_082623',119),('cap_20261013_082623',232)]
case_rows=[];axis_audit={};failures={}
for v,rows in comparison['frames'].items():
    previous={};turns=[];flips=[];sources=collections.Counter();missing=[];new=[];target_misses=[]
    for stat in rows:
        sid=stat['sid'];fi=stat['fi'];row=read(out/v/sid/f'{fi:04d}.json');body=row['body_3d'];sk=body[0]['skeleton'] if body else {};axis=sk.get('axis')
        prior=previous.get(sid)
        if axis is not None and prior and prior['axis'] is not None and fi==prior['fi']+1:
            dot=float(np.clip(np.dot(axis,prior['axis']),-1,1));angle=float(np.degrees(np.arccos(abs(dot))))
            if dot<0:flips.append({'sid':sid,'fi':fi,'unoriented_angle_deg':angle})
            if angle>45:turns.append({'sid':sid,'fi':fi,'unoriented_angle_deg':angle})
        previous[sid]={'axis':axis,'fi':fi};sources[stat['direction_source']]+=1
        if stat['axis_missing']:missing.append({'sid':sid,'fi':fi})
        if stat['new_axis_missing']:new.append({'sid':sid,'fi':fi})
        if not body and not sid.endswith('131958'):target_misses.append({'sid':sid,'fi':fi})
        if (sid,fi) in hard:case_rows.append({'variant':v,'sid':sid,'fi':fi,**stat,'axis':axis})
    axis_audit[v]={'large_turns':turns,'sign_flips':flips,'direction_sources':dict(sources)}
    failures[v]={'new_axis_missing':new,'remaining_axis_missing':missing,'target_misses':target_misses,
        'anchor_changed_frames':[r for r in rows if r['anchor_difference_count']],
        'largest_center_shift':sorted([r for r in rows if r['center_shift_from_r1_m'] is not None],key=lambda r:r['center_shift_from_r1_m'],reverse=True)[:8]}
dump(e/'REGRESSION_DETAILS.json',{'hard_frames':case_rows,'axis':axis_audit,'failures':failures,
    'semantic_false_absorptions':'UNKNOWN','identity_drift':'UNKNOWN','provenance':'AI_INFERRED_GEOMETRY_NOT_GT'})
verify=read(e/'ALL_FRAME_VERIFICATION.json');browser=read(e/'BROWSER_R3.json');assert verify['status']==browser['status']=='PASS'
preservation=read(e/'FINAL_PRESERVATION.json');scoped=read(e/'SCOPED_PRESERVATION.json');assert scoped['status']=='PASS'
lines=['# HFUS-POINTSET-ACTIONS-02 · R3 FINAL_REPORT','',
    '已完成人体点集恢复研究、实现、全1934动作帧＋32空场HOLDOUT、6方案11796帧方案因果源重放，以及8944原页面真实Edge多视角交互。R1继续默认；R2与R3均保留实验。R3工程功能作者自验PASS，几何证据支持部分可见碎片连接和粗部位连续性；身份/完整率/家具污染率/解剖精度UNKNOWN，生产晋级BLOCKED。全树保护发现383个其他录制/配平产物消失，未解释，不报全树PASS；本轮9段源/旧输出/GT/生产范围核验PASS。SUBMITTED，非ACCEPTED。','',
    '## 输入、冻结与保护','',
    f"起始{read(e/'BASELINE_BEFORE.json')['branch']} / HEAD `{preservation['head_before']}`；全{preservation['baseline_files']}文件基线含tracked/untracked/ignored。旧R1/R2输出、core/actions/config、原录制/GT/生产/模型保持。只扩展原app.js/index.html/server.py及入口文档；8944同任务服务重启，旧其他服务/EXE未替换。三件套原字节备份*.startbytes独立匹配R2最终SHA；全树非原子扫描与实时旧服务日志单列，未宣称同一瞬间全树冻结。最终保护见FINAL_PRESERVATION、SOURCE_BINDINGS和OUTPUT_SHA_FINAL。",
    '实际技能：C:/Users/30680/.codex/skills/ponytail/SKILL.md 与 scientific-toolkit-skill/SKILL.md。Codex唯一writer，无代理、外部数据上传或新依赖。Python3.12/NumPy1.26.4/SciPy1.17.1/Node24.14.0/Microsoft Edge。原28B记录、R/T、会话配准、ROI、131958 FIT/CAL背景和54.924mm容差不变；数值配准不等于物理标定。','',
    '先读取AGENTS/HC README/HF WORKFLOW/R2报告与完整绑定。DIAGNOSTIC_STUDY覆盖38剩余轴缺测及此前4帧、四重点±3帧；DIAGNOSIS_BEFORE_EXPERIMENT先于冻结和全帧。条件只由动作诊断确定，32 HOLDOUT只作冻结后的验证，没有反调。FROZEN_EXPERIMENT与最终实验哈希相等。','',
    '## 恢复策略与消融','',
    'A：当前未选前景12cm邻接图，至少12点，10cm邻域中位≥4，线性度≥.35；最多300点、ROI≥90%、距主体P90≤.85m，28cm连接至少3个5cm体素。B：在component20上逐点剔除2tau近背景与Z<8cm新增风险，并拒绝持续未选而无过去目标支持的块。C：在component20上要求此前最多4帧/0.45s目标16cm覆盖≥50%。ABC合并，风险切除后再次验证图块连接，防止断桥孤立尾部。未选远簇和区外成员仍保存拒绝证据。','',
    '只恢复当前FG真实源行；不恢复原背景删除点、不跨帧累计身体点、不合成点。每个新增点保留raw XYZ、变换XYZ、源行、连接anchor、背景距离、图块、过去帧和纳入依据，identity=UNKNOWN、provenance=AI_INFERRED。过去坐标只是证据。固定实验的过去成员取R1可靠当前锚点；反馈实验取自身过去成员，二者分别记录。','',
    '|方案|新增成员累计|近背景新增|低于8cm新增|轴缺测|相对R1新轴缺测|>45°轴变化|最大中心偏移m|',
    '|---|---:|---:|---:|---:|---:|---:|---:|']
for v in ['baseline','component20','axis']:
    s=old['summary'][v];lines.append(f"|R1默认{'' if v=='baseline' else ' / R2 '+v}|{s['added_count']}|{s['near_background_added_count']}|{s['low_added_count']}（旧口径<4cm）|{s['axis_missing']}|见R2报告|{s['axis_large_turn']}|未单列|")
for v,s in comparison['summary'].items():
    lines.append(f"|{v}|{s['added_count']}|{s['near_background_added_count']}|{s['low_added_count']}|{s['axis_missing']}|{s['new_axis_missing']}|{len(axis_audit[v]['large_turns'])}|{s['center_shift_max_m']:.4f}|")
lines += ['',
    '累计按每帧成员计，不是独立物理点，也不是已找回人体数量。近背景是冻结距离风险proxy；B/ABC近背景新增0是排除门的直接结果，不能据此宣称纯度100%。原主体点未被重新身份筛选，原主体内家具污染仍UNKNOWN。累计粗节点数只记录在机器统计，不作准确度或主收益依据。','',
    '## 重点帧前后','', '|会话/帧|R1点/有效粗槽|R2 component20点/粗槽|R3点/粗槽|R3新增|轴来源|', '|---|---:|---:|---:|---:|---|']
for sid,fi in hard:
    b=read(here/'action_output'/sid/f'{fi:04d}.json')['body_3d'][0];r2=read(here/'action_research_r2/component20'/sid/f'{fi:04d}.json')['body_3d'][0]
    r3=read(out/'r3'/sid/f'{fi:04d}.json');o=r3['body_3d'][0];n=lambda o:sum(v['valid'] for v in o['skeleton']['nodes'].values())
    lines.append(f"|{sid[-6:]}/f{fi}|{b['point_count']}/{n(b)}|{r2['point_count']}/{n(r2)}|{o['point_count']}/{n(o)}|{r3['stats']['added_count']}|{r3['stats']['direction_source']}|")
lines += ['',
    'f192的219点碎片：线性度.909、28cm连接63点/37体素、过去4帧原目标12cm覆盖95.9–97.3%，支持可见端部连接假设。区外166点残余约99%持续未选，目标支持0、近背景约74%，保持拒绝；不是家具GT。R3会拒绝其中近背景/稀疏/区外成员，完整纯人体是否提高仍UNKNOWN。邻帧源证据与实际浏览器上下文均已查看。','',
    'f140碎片过去原目标覆盖约99–100%，同时近背景约35%；因此恢复有支持的当前表面与剔除风险点分别处理。ABC点集方案的全局PCA退化仍按失败记录；R3局部主体轴用于当前点划分，不把它改名为“全局PCA已修复”。f119/f232靠近1.8特征比门，原R2少数孤立点触发退化；图块策略拒绝这类点，具体结果见表。','',
    '## 剩余38帧与粗部位','',
    'R2轴剩余38帧分布082906=8、082829=4、082717=16、082623=10。全局轴比多数约1.1–1.8，局部上半高度子空间常有4–10的特征比，提示密集躯干/低位横向表面使全局方差竞争；遮挡/身体身份原因仍UNKNOWN。比较中央80%子空间、上半高度子空间和均匀体素子空间，要求局部比≥2.5、全目标沿轴方差≥最大方差80%、与当前主轴差≤35°；不满足仍缺测。没有盲目降低原全局1.8门。','',
    'R3先用恢复目标的当前可靠轴；原当前主体满足原门且占目标≥85%时，允许主体局部轴作为当前子空间方向。否则仅允许原R1可靠历史≤.5s、换目标/失锁/时间倒退/gap清除，fallback不刷新寿命，再尝试上述当前局部子空间。所有粗槽都是当前目标源点均值，13槽定义保持、predicted_nodes=[]；轴来源与过去fi/年龄可见，不回填不可见解剖节点。','']
remaining=failures['r3']['remaining_axis_missing'];resolved=set((r['sid'],r['fi']) for r in read(e/'DIAGNOSTIC_STUDY.json')['remaining_axis_missing'])-set((r['sid'],r['fi']) for r in remaining)
lines += [f"R3在R2剩余38帧中获得当前点支持方向的帧数为{len(resolved)}，全1934动作仍轴缺测{len(remaining)}帧。方向符号翻转{len(axis_audit['r3']['sign_flips'])}次，>45°无向变化{len(axis_audit['r3']['large_turns'])}次；这些是连续性风险，不是解剖方向误差。剩余缺测与所有新退化/大转角逐帧列在REGRESSION_DETAILS。",'',
    '## 固定锚点与独立反馈闭环','',
    'r3_graph/background/temporal/combined/r3固定每帧R1原因果锚点，隔离恢复与轴因素。r3_feedback每帧重新聚类，choose仅消费上一已恢复目标median XY，恢复成员也反馈过去证据，不直接用R1本帧选择；独立创建Posture/AxisHistory/Past。原R1源码和生产tracker不改。', '']
s=comparison['summary']['r3_feedback'];f=failures['r3_feedback'];lines += [f"独立反馈锚点不同帧{len(f['anchor_changed_frames'])}，锚点成员差累计{s['anchor_difference_count']}，关联ID中断{s['association_interruption']}，动作目标缺失{len(f['target_misses'])}；对R1中心偏移p95={s['center_shift_p95_m']:.4f}m / max={s['center_shift_max_m']:.4f}m。中心偏移不是身份漂移准确率，身份GT缺失仍UNKNOWN。32空场目标{s['empty_targets']}、新增{s['empty_added']}；这是本场边界回归，不能推广为其他场景误检率。事件={json.dumps(s['events'],ensure_ascii=False)}，confirmed始终false。",'',
    '## 失败、代价与结论边界','',
    'A能恢复连接图块，但没有背景/时序筛选时会保留风险点；B/C单因素继续吸收一些孤立邻点，可能新造轴歧义。C的过去目标一致性无法独自排除主体附近背景；人体长时间躺地也会稳定，所以不能以稳定性直接判负。ABC会拒绝贴地身体边缘和稀疏端部，可能损失完整性；保留拒绝源行供后续身份核查。R3可能为不同当前子空间选择不同方向，必须同时报告方向跳变，不能用节点增加掩盖。错误碎片吸收/真实身份漂移/人体完整率/家具污染率和解剖精度均UNKNOWN。','',
    '实现过程保留的工程问题：三件套备份重建时index.html的CRLF曾导致哈希不符，恢复原换行后与R2最终SHA精确匹配；初次补丁同文件重复目标被工具拒绝，无写入，随后合并修正。原输出未覆盖。若有浏览器/校验失败重试，原日志和失败截图另存，见RUN_FAILURES记录。','',
    '## 页面、验证与复现','',
    f"原页面 http://127.0.0.1:8944/，默认R1；实验菜单保留R2和6个R3方案。勾选同帧对照显示R1/R2/当前目标，视角同步；橙恢复、紫拒绝、红近背景风险、绿线连接，白体轴、粉粗槽。四重点一键跳转，点击当前点查询源行与纳入依据，完整JSON导出。实际headed Edge交互查看{len(browser['cases'])}个困难/剩余缺测/邻帧的正视、俯视、三维，测试全部会话、真实空场、切换、拖动、导航、播放暂停、源点击、导出、非法输入和legacy。截图为真实渲染记录，AI视觉观察单列，未写GT。",
    '全11796帧方案独立原始mask/背景距离重算，当前帧后的原数据行在验证重放中不可访问；恢复、过去引用、feedback关联和轴因果重放与输出一致，所有有效节点支撑属于当前目标且坐标等于当前源点均值。没有背景越权恢复、未来点泄漏或预测骨架点。15项pointset、7项console Python、12项console JS与JS语法检查通过；测试总数不是语义验收。','',
    '从仓库根目录：`python -B -W error sidequests/human_fusion_lab_next/pointset/r01/experiment_r3.py`，要求独占不存在的新输出目录，已有交付禁止覆盖；`verify_r3.py`验证同一已生成输出；`server.py --port 8944`仅localhost；`check_r3_browser.py`复现实际浏览器，证据目录也独占，不覆盖历史。重新实验须新版本输出/证据绑定，先冻结，不能直接删除旧结果重跑。','',
    '|验收ID|状态|证据|','|---|---|---|',
    '|R301|保护范围PASS；全树FAIL/归因BLOCKED|BASELINE_BEFORE / FINAL_PRESERVATION / SCOPED_PRESERVATION；383外部路径缺失|',
    '|R302|PASS（几何研究）|DIAGNOSTIC_STUDY / DIAGNOSIS_BEFORE_EXPERIMENT；身份UNKNOWN|',
    '|R303|PASS（实验实现）|冻结配置 / EXPERIMENT_COMPARISON / 全量逐点纳入与拒绝|',
    '|R304|PASS（当前源支撑）；解剖UNKNOWN|ALL_FRAME_VERIFICATION / REGRESSION_DETAILS|',
    '|R305|PASS|6×1966因果前缀重放 / 当前raw XYZ与节点均值核验|',
    '|R306|PASS（闭环实验）；身份漂移UNKNOWN|独立r3_feedback / 中心偏移 / 新歧义与转角同时记录|',
    '|R307|PASS|BROWSER_R3 / browser多视角 / 视觉检查记录|',
    '|R308|PASS（交付）|当前报告 / returns / 当前入口|','',
    '最终分类：**R3工程功能PASS；几何证据支持可见点图连接与部分当前方向可观测性；AI_INFERRED仅实验身份假设；身份/解剖精度UNKNOWN；生产晋级BLOCKED。** 全树保护R301未整体PASS：383个其他captures文件在基线后消失（remote36、leveled347），原因UNKNOWN，未擅自恢复或掩盖；本轮9段源与旧输出/生产/GT范围保持。独审/设备/物理NOT_RUN。未训练新模型、未改旧GT/本轮录制/生产算法、未采集/部署/提交推送、未开放confirmed跌倒。']
(e/'FINAL_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
dump(e/'ACCEPTANCE_FINAL.json',{'status':'SUBMITTED_NOT_ACCEPTED','engineering':'PASS','geometry':'EVIDENCE_SUPPORTED_WITH_RECORDED_REGRESSIONS',
    'identity':'UNKNOWN','anatomical_accuracy':'UNKNOWN','production_promotion':'BLOCKED','independent_review':'NOT_RUN','device':'NOT_RUN','physical':'NOT_RUN',
    'ids':{'R301':'SCOPED_PASS_GLOBAL_FAIL_ATTRIBUTION_BLOCKED',**{f'R30{k}':'PASS_SELF_CHECK' for k in range(2,9)}},'default':'R1','full_tree_preservation':'FAIL_UNEXPLAINED_MISSING'})
for path in [root/'docs/human_capture/README.md',root/'docs/human_fall/WORKFLOW.md']:
    text=path.read_text(encoding='utf8');text=text.replace('当前IN_PROGRESS。','当前SUBMITTED，R3功能自验完成；全树保护R301因383非本轮capture文件缺失未整体通过，非ACCEPTED。',1)
    link='evidence/2026-10-14_hfus_pointset_actions_r3/FINAL_REPORT.md' if 'human_capture' in str(path) else '../human_capture/evidence/2026-10-14_hfus_pointset_actions_r3/FINAL_REPORT.md'
    text=text.replace('下方历史条目保留，不扩当前范围。',f'[FINAL_REPORT]({link})。下方历史条目保留，不扩当前范围。',1);path.write_text(text,encoding='utf8')
readme=here/'README.md';text=readme.read_text(encoding='utf8')
readme.write_text('# 2026-10-14 R3 当前人体点集与粗部位实验\n\n原8944页面，R1保持默认，R2保留。R3增加图连接/背景排除/因果时序消融、组合点集与当前局部体轴、独立tracker反馈。全1934+32帧×6方案源点与因果前缀重放PASS；身份/解剖精度UNKNOWN、生产晋级BLOCKED。实验入口experiment_r3.py、verify_r3.py、check_r3_browser.py；输出action_research_r3，存在时拒绝覆盖。见[FINAL_REPORT](../../../../docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r3/FINAL_REPORT.md)。\n\n'+text,encoding='utf8')
(root/'docs/human_capture/returns/HFUS-POINTSET-ACTIONS-02.md').write_text('# HFUS-POINTSET-ACTIONS-02 R3 return\n\nCodex唯一writer；实际加载C:/Users/30680/.codex/skills/ponytail/SKILL.md、scientific-toolkit-skill/SKILL.md。原8944同页，R1默认、R2保留。完成6方案×1966帧当前源点/因果重放及真实Edge多视角；固定锚点与独立tracker反馈分别统计。工程PASS，几何证据支持但回归和代价保留；身份/解剖UNKNOWN，晋级BLOCKED、SUBMITTED非ACCEPTED。独审/设备/物理NOT_RUN，无训练/采集/部署/提交推送/confirmed。\n\n[唯一v1](../evidence/2026-10-14_hfus_pointset_actions_r3/ACCEPTANCE_V1.md) · [FINAL_REPORT](../evidence/2026-10-14_hfus_pointset_actions_r3/FINAL_REPORT.md) · [全帧核验](../evidence/2026-10-14_hfus_pointset_actions_r3/ALL_FRAME_VERIFICATION.json)。\n',encoding='utf8')
# Refresh authorized final-file hashes after final entry text; frozen algorithms never change.
authorized={'sidequests/human_fusion_lab_next/pointset/r01/'+n for n in ['app.js','index.html','server.py','README.md']};authorized.update(['docs/human_capture/README.md','docs/human_fall/WORKFLOW.md'])
baseline=read(e/'BASELINE_BEFORE.json');oldchanged={r['path'].replace('\\','/'):r for r in preservation['changed']}
for name in authorized:
    key=next(k for k in baseline['files'] if k.replace('\\','/')==name);record=baseline['files'][key];value=sha(root/name)
    if value!=record['sha256']:oldchanged[name]={'path':key,'before':record['sha256'],'after':value,'authorized':True,'runtime_log':False}
preservation['changed']=list(oldchanged.values());preservation['unchanged_files']=preservation['baseline_files']-len(preservation['changed'])-len(preservation['missing'])-len(preservation['errors']);preservation['final_authorized_files_refreshed']=True
(e/'FINAL_PRESERVATION.json').write_text(json.dumps(preservation,ensure_ascii=False,indent=2),encoding='utf8')
(e/'OUTPUT_SHA_FINAL.json').write_text(json.dumps({str(p.relative_to(root)):sha(p) for p in out.rglob('*') if p.is_file()}),encoding='utf8')
dump(e/'SOURCE_SHA_FINAL.json',{str(p.relative_to(root)):sha(p) for p in here.iterdir() if p.is_file() and p.suffix in ['.py','.js','.html','.json','.yaml']})
print('FINAL',comparison['summary']['r3'],'feedback',comparison['summary']['r3_feedback'],flush=True)
