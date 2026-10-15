import json
import subprocess
import urllib.request
from pathlib import Path
import sys

H=Path('D:/Code/ldiar/sidequests/human_fusion_lab_next/pointset/r01');sys.path.insert(0,str(H))
from research_actions import E, RESULT, OUT, ROOT, read, dump, sha

diag=read(E/'DIAGNOSIS.json');observations=[]
for c in diag['cases']:
    if c['roles'][0]=='AXIS_OR_NEIGHBOR':continue
    sid,fi=c['sid'],c['fi'];d=read(RESULT/sid/f'{fi:04d}.json');base=read(OUT/sid/f'{fi:04d}.json')
    low_external=[f for f in d['fragments'] if f['roi_fraction']==0 and f['z_quantiles_m'][-1]<.4]
    suspected=[f for f in d['fragments'] if sid=='cap_20261013_082623' and fi==192 and f['cluster']==5]
    observations.append({'sid':sid,'fi':fi,'source_sha256':d['source_sha256'],'source_frame':d['source_frame'],
        'provenance':'AI_INFERRED','reviewer_type':'ASSISTANT','is_independent_gt':False,'used_for_training':False,
        'central_candidate_source_indices':base['selection']['selected_source_indices'],'central_identity':'AI_INFERRED_POSSIBLE_PERSON_NOT_GT',
        'risks':{'background_overdeletion':{'status':'UNKNOWN_IDENTITY_NEAR_DELETION_RISK','source_indices':d['near_removed_source_indices']},
                 'body_fragmentation':{'status':'AI_INFERRED_POSSIBLE_BODY_FRAGMENT' if suspected else 'UNKNOWN','source_indices':[i for f in suspected for i in f['source_indices']]},
                 'furniture_contact':{'status':'AI_INFERRED_POSSIBLE_EXTERNAL_STATIC_RESIDUAL' if low_external else 'UNKNOWN',
                                     'source_indices':[i for f in low_external for i in f['source_indices']],'target_contamination_rate':None},
                 'wrong_cluster':'UNKNOWN_IDENTITY_GT_UNAVAILABLE','occlusion':'UNKNOWN_CAUSE_SINGLE_VIEW',
                 'body_axis_ambiguity':d['body_axis_ambiguity']},
        'visual_evidence':str(E/'figures'/f'{sid}_{fi:04d}.png'),
        'note':'Explicit assistant observations, never HUMAN_REVIEW; no accuracy calculation from these candidates.'})
dump(E/'AI_REVIEW_OBSERVATIONS.json',{'schema_version':'assistant-observation/1','observations':observations,'identity_gt':False})

entry='''## 2026-10-14 HFUS-POINTSET-ACTIONS-01 R2 点集诊断/局部恢复/因果体轴（当前唯一入口）

用户授权继续本机离线研发，先检查人体完整性/背景混入，再做局部恢复与骨架。Codex唯一writer，实际读取ponytail、scientific-toolkit-skill；原pointset/r01页面，默认R1保持，新增action_research_r2五种实验对照。全1934+32帧重现、6方案11796帧源成员/当前节点支撑核验；轴实验缺测79→38，局部恢复有119/140/232新困难，均不晋级默认。人体完整率/家具污染率/解剖精度UNKNOWN；AI观察单独记录非人工GT，无训练/采集/部署/confirmed/Git写。实际Edge原页/控制台iframe与原EXE启动通过，原EXE/快捷方式不替换。当前[唯一v2]({acceptance})/[报告]({report})/[交付]({index})，SUBMITTED非ACCEPTED，独审/设备/物理NOT_RUN。旧v1/原数据/GT/模型/core/输出与历史证据只读保留。下方均历史，不扩本轮范围。

'''
base='evidence/2026-10-14_hfus_pointset_actions_r2/'
for relative,prefix in [('docs/human_capture/README.md',base),('docs/human_fall/WORKFLOW.md','../human_capture/'+base)]:
    p=ROOT/relative;old=p.read_text(encoding='utf8')
    p.write_text(entry.format(acceptance=prefix+'ACCEPTANCE_V2.md',report=prefix+'FINAL_REPORT.md',index=prefix+'CURRENT_DELIVERY_INDEX.md')+old,encoding='utf8')
here_readme=H/'README.md'
here_readme.write_text('''# 2026-10-14 R2 当前诊断与实验

继续使用 http://127.0.0.1:8944/ 原页面。默认R1；上方实验方案切换/五层同帧对照/诊断帧导航。四种局部恢复与有界历史轴均未晋级默认；当前节点仍粗部位中心，人体完整率/污染率/解剖精度UNKNOWN。

新输出action_research_r2；原action_output/output/core/配置/模型保持。[R2报告](../../../../docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r2/FINAL_REPORT.md)。`research_actions.py diagnose`、`experiment_actions.py`均独占输出，存在时拒绝覆盖；不要直接重跑历史目录。核验`verify_research_actions.py`；单测仍`python -B -W error -m unittest discover -s . -p "test_*.py"`。当前R2完整核验已完成，日志见报告索引。以下R1与原九会话保留作历史。

'''+here_readme.read_text(encoding='utf8'),encoding='utf8')
return_path=ROOT/'docs/human_capture/returns/HFUS-POINTSET-ACTIONS-01.md'
with return_path.open('a',encoding='utf8') as f:
    f.write('''

## 2026-10-14 R2 · Codex当前点集诊断与局部实验回传

- 当前唯一验收：evidence/2026-10-14_hfus_pointset_actions_r2/ACCEPTANCE_V2.md；SHA见ACCEPTANCE_FINAL.json。
- 状态SUBMITTED，非ACCEPTED。实际技能C:/Users/30680/.codex/skills/ponytail/SKILL.md与scientific-toolkit-skill/SKILL.md；单writer，无代理/模型训练。
- 起始master / c21c443b0befe559e08283edb0efc2af02dcc6b8，24627文件全树SHA、既存dirty保留；范围与提交源码SHA见FINAL_PRESERVATION/SOURCE_SHA_FINAL。无Git写。
- 根因：最大簇可能只保留主体；贴地删除与端部碎裂独立于PCA轴缺测。082623/f192未选219点簇AI_INFERRED疑似端部，非GT；主簇内部污染及误删身份UNKNOWN。
- 实现：原r01页五层/源点点击/基线与五种单因素实验；新research/experiment/verify模块、新冻结研究配置；core与历史输出只读。全1934+32帧重现与6方案11796帧当前源成员/节点均值独立核验PASS。
- 实验：point12新增434、point20新增4863且新增2歧义；component20新增5917，f192局部214成员/8节点，但新增3旧解3；low20新增4921含58近地近背景点。拒绝局部恢复晋级，轴实验79→38缺测、无成员变化，仍缺方向身份精度，实验保留。记录每个新增依据、所有失败与新困难。
- R201–R208逐ID自验见ACCEPTANCE_FINAL；局部恢复/方向精度/身份污染不冒称PASS。pointset11、console Python7/JS12、真实Edge九会话/全部79歧义+新困难/三视角/缺测/播放暂停/事件/导出/非法输入/iframePASS。gap页面fixture为SYNTHETIC，因果重置单测PASS。
- 实际Console_Pointset.exe --check-startup ok=true，动态加载同一r01；默认保持R1，所以EXE/快捷方式/旧版本保留，无打包替换。页面选择baseline即算法回滚；旧UI三件套保留快照。
- 设备/物理/独审NOT_RUN；人体完整率、家具污染率、解剖/方向精度UNKNOWN。confirmed恒false，不采集部署HR-09训练提交推送。
- 未闭合：38轴歧义、局部恢复新119/140/232困难、f192身份未证明、靠近目标背景删除是否身体未知。下一步从这些源绑定窗口研究稳定背景接触排除与当前可见端部，不扩大ROI、不补造点。
- 实际命令、返回码、源码与输出SHA、浏览器图片、首尾保全及失败证据均在R2报告/当前索引；本机自验非独立复审。
''')
statuses={f'R20{i}':{'status':'PASS','kind':'LOCAL_SELF_CHECK_NOT_INDEPENDENT_ACCEPTANCE'} for i in range(1,9)}
dump(E/'ACCEPTANCE_FINAL.json',{'status':'SUBMITTED','ids':statuses,'acceptance_sha256':sha(E/'ACCEPTANCE_V2.md'),
     'fragment_default_adoption':'FAIL_NO_IDENTITY_EVIDENCE_AND_REGRESSIONS','axis_default_adoption':'NOT_ADOPTED_DIRECTION_ACCURACY_UNKNOWN',
     'human_precision':'UNKNOWN','furniture_contamination_rate':'UNKNOWN','anatomical_accuracy':'UNKNOWN',
     'independent_review':'NOT_RUN','device':'NOT_RUN','physical':'NOT_RUN','new_default':False})
with urllib.request.urlopen('http://127.0.0.1:8944/api/version') as response: version=json.load(response)
dump(E/'VERSION_CHECK_AFTER.json',{'page':version,'exe_sha256':sha(ROOT/'pc_apps/console/dist/Console_Pointset.exe'),
     'exe_unchanged':sha(ROOT/'pc_apps/console/dist/Console_Pointset.exe')==read(E/'VERSION_CHECK_BEFORE.json')['files'][str(ROOT/'pc_apps/console/dist/Console_Pointset.exe')]['sha256'],
     'actual_startup':read(E/'FROZEN_STARTUP_R2.json')['ok'],'default':'R1_BASELINE'})
dump(E/'SOURCE_SHA_FINAL.json',{str(p.relative_to(ROOT)):sha(p) for p in list(H.glob('*.py'))+list(H.glob('*.js'))+list(H.glob('*.html'))+list(H.glob('*.yaml'))+[H/'config_research_r2.json']})
print('Records written',len(observations),'AI observations; no human GT',flush=True)
