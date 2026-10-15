"""Finalize only planning/review records; never launch implementation or training."""
import hashlib
import json
import subprocess
from datetime import datetime,timezone,timedelta
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=E.parents[3]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def write(p,d):
    with p.open('x',encoding='utf-8') as stream:json.dump(d,stream,ensure_ascii=False,indent=2)
def append(p,s):
    with p.open('a',encoding='utf-8') as stream:stream.write('\n\n'+s+'\n')
assert not (E/'FINAL_PACKAGE.json').exists()
decision=(E/'OPENCODE_REVIEW_R3.md').read_text(encoding='utf-8')
assert '# 最终结论：**PLAN_PASS**' in decision
baseline=read(E/'PLAN_BASELINE.json')
for relative,digest in baseline['source_sha256'].items():assert sha(ROOT/relative)==digest,relative
core=['DEVELOPMENT_PLAN_V3.md','ACCEPTANCE_V3.md','AI_DEVELOPMENT_PROMPT_V3.md','DATA_PREFLIGHT_V2.json','EXPERIMENT_SPLIT_V2.json',
      'ANNOTATION_QUEUE_V2.json','EXPERIMENT_BUDGET_V2.json','OUTPUT_BUDGET_V2.json','FOLD_SAMPLE_COUNTS.json','EXPERIMENT_STREAMS.json',
      'NONBLOCKING_DISPATCH_AMENDMENTS.json','VERSION_LOG.md']
bindings={n:sha(E/n) for n in core}
current={'item':'HFUS-LEARN-PLAN-03','proposed_development_item':'HFUS-LEARN-DEV-03','work_item_status':'SUBMITTED','review_decision':'PLAN_PASS',
         'plan':'DEVELOPMENT_PLAN_V3.md','acceptance':'ACCEPTANCE_V3.md','development_prompt':'AI_DEVELOPMENT_PROMPT_V3.md',
         'effective_revision':'V3 dispatch editorial r1; R3 explicitly permits two nonblocking tightening changes',
         'sha256':bindings,'review':'OPENCODE_REVIEW_R3.md','review_sha256':sha(E/'OPENCODE_REVIEW_R3.md'),
         'review_model':'opencode-go/deepseek-v4.1-flash','review_session':'ses_ec24f08afffe9TTaza6EiWWMIB','implementation':'NOT_RUN',
         'training_authorization':'NOT_GRANTED_BY_THIS_PLAN','training':'NOT_RUN','HR09':'NOT_ACTIVATED','deployment':'NOT_RUN'}
write(E/'CURRENT_PLAN.json',current)
table='\n'.join('|'+n+'|`'+h+'`|' for n,h in bindings.items())
append(E/'PLAN_REVIEW.md',f'''## 最终现行结论与派发指针（2026-10-15）

**PLAN_PASS，工单SUBMITTED；非ACCEPTED、非E1授权。** 本段替代顶部草案PENDING指针。V1 PLAN_REVISE→V2 PLAN_PASS→V3最终PLAN_PASS的原始OpenCode日志/md全部保留；正式精确派发指针[CURRENT_PLAN](CURRENT_PLAN.json)。

最终计划[DEVELOPMENT_PLAN_V3](DEVELOPMENT_PLAN_V3.md)，唯一拟实施验收[ACCEPTANCE_V3](ACCEPTANCE_V3.md)，可直接交执行AI的[AI_DEVELOPMENT_PROMPT_V3](AI_DEVELOPMENT_PROMPT_V3.md)。配套JSON名称虽含V2，属于V3明确引用的同一冻结契约，不是另一组并列要求。

审查者：单独OpenCode plan只读进程，opencode-go/deepseek-v4.1-flash，session ses_ec24f08afffe9TTaza6EiWWMIB，edit/bash deny、snapshot=false；未训练/安装/下载/读取原点大文件。CLI实际3轮exit0不等于内容全PASS：R1内容PLAN_REVISE，R2/R3内容PLAN_PASS。见OPENCODE_REVIEW_R1/R2/R3.md。

R3允许派发前并入的两项非阻断文字收紧已落实，原审字节保留V3_PRE_DISPATCH_SNAPSHOT，前后SHA见NONBLOCKING_DISPATCH_AMENDMENTS；不改族/门限/作业预算/权限。最终文件必须按下表核，而不是只看文件名/PLAN_PASS字样。

|现行文件|最终SHA256|
|---|---|
{table}

最终审查原文SHA：`{sha(E/'OPENCODE_REVIEW_R3.md')}`。当前开发L01–L18均NOT_RUN，18源计划预检与预算检查不替代实施；需未来用户实际派发才做E0，E1还需另外明确训练授权及可信标签门。ML/仍未激活HR09，无设备/采集/部署或默认晋级。
''')
write(E/'COMMAND_RESULTS.json',{'basis':'Actual tool process results recorded after completion; plan only',
 'results':[{'command':'plan raw18 SHA/28B/offset/device-time recheck and manifests','exit_code':0},
 {'command':'check_plan.py -B -W error','exit_code':0,'log':'PLAN_CHECK.log'},
 {'command':'V2 draft generation helper first','exit_code':1,'reason':'default GBK decoding JSON; repaired explicit UTF8; all planned artifacts then completed'},
 {'command':'check_plan_v2.py -B -W error','exit_code':0,'logs':['PLAN_CHECK_V2.log','PLAN_CHECK_FINAL.log']},
 {'command':'OpenCode readonly R1','session':7715,'exit_code':0,'content_decision':'PLAN_REVISE'},
 {'command':'OpenCode readonly R2','session':93611,'exit_code':0,'content_decision':'PLAN_PASS'},
 {'command':'OpenCode readonly R3','session':60048,'exit_code':0,'content_decision':'PLAN_PASS'}],
 'implementation_training_download_install_capture_deploy':'NOT_RUN'})
ret=ROOT/'docs/human_capture/returns/HFUS-LEARN-PLAN-03.md'
rows='\n'.join(f'|L{i:02d}|拟实施条目见唯一ACCEPTANCE_V3|NOT_RUN（本轮仅计划，非开发实测）|' for i in range(1,19))
append(ret,f'''# HFUS-LEARN-PLAN-03 2026-10-15 回传

## 本轮信息

- 用户要求制定更大阶段计划、可派发开发AI提示词并给OpenCode审查。本轮仅计划/数据预检/审查；状态SUBMITTED，非ACCEPTED，无开发/训练/下载/HR09/部署。
- 拟实施工单HFUS-LEARN-DEV-03，唯一[ACCEPTANCE_V3](../evidence/{E.name}/ACCEPTANCE_V3.md)，SHA {bindings['ACCEPTANCE_V3.md']}；旧N/Q表不变。
- 当前主作者Codex；独立OpenCode opencode-go/deepseek-v4.1-flash plan / ses_ec24f08afffe9TTaza6EiWWMIB只读审查，实际三轮exit0，内容R1 PLAN_REVISE→R2/R3 PLAN_PASS。
- 起始branch/HEAD：{baseline['branch']} / {baseline['HEAD']}，完整dirty状态GIT_STATUS_BEFORE/FINAL，影响源码与模型/配置SHA见PLAN_BASELINE；本轮原源前后相等，用户差异不改。
- 实际读取技能C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。原论文/官方实现仅查设计与依赖边界，无模型运行。

## 集中诊断与根因覆盖

V1 D1混淆OOF/全开发拟合/最终语义评估，D2训练样本/吞吐/空间预算不具体；D3旧绑定字节与同应用扩展、D4派发闸门、D5人工/建议量、D6实例/关节条件、D7预检范围均集中修复。V3落实低危必读项/逐fold计数/12-4-3流映射以及state_dict/适用性收紧；原审/初稿/审前字节都保留，详见VERSION_LOG和PLAN_REVIEW，不用CLI exit0冒充审查PASS。

## 实际变更

仅本轮docs/human_capture/evidence/{E.name}/计划/验收/提示词/JSON/审查及记录；HF/HC入口与REVIEW_LOG追加，当前回传追加。没有修改算法/生产/模型/原数据或服务，没有Git写；CURRENT_PLAN绑定最终全部权威文件SHA，完整索引另存。

## 逐条验收

计划预检18原SHA/28B/offset/设备时间实际PASS；预算与队列脚本exit0。学习/标注/页面/模型实现仍未开工，不能沿用计划预检或计划审查PASS作为开发验收。

|拟实施ID|要求来源|当前实施状态|
|---|---|---|
{rows}

## 未闭合与限制

下一阶段10包：474队列项=282人工核心+192建议，66第二人工；三族前端/场景实例/结构接口/因果时序，36作业上限30h（E1须未来用户另授权、真实标签门），80GiB输出/资源探针，全1934+90与原页/复现。OOF开发96与最终比较96+空90严格分表，所有既有数据已开发使用，不称未见泛化。关节/身份/人工门不足相应BLOCKED，不以接口可用冒充性能；未来E0仍须尽做不依赖项，不自动HR09/采集/部署。

## 交给后续执行/复审

正式可派发文件[AI_DEVELOPMENT_PROMPT_V3](../evidence/{E.name}/AI_DEVELOPMENT_PROMPT_V3.md)，主[DEVELOPMENT_PLAN_V3](../evidence/{E.name}/DEVELOPMENT_PLAN_V3.md)与[最终审查/精确指针](../evidence/{E.name}/PLAN_REVIEW.md)/CURRENT_PLAN.json。最终PLAN_PASS仅为计划可实施，本轮不启动下一单；须用户实际派发，训练另有明确授权证据。
''')
title='## 2026-10-15 HFUS-LEARN-PLAN-03 学习前端大阶段计划（仅计划，SUBMITTED）\n\n'
for relative,prefix in [('docs/human_fall/WORKFLOW.md','../human_capture/'),('docs/human_capture/README.md','')]:
 path=ROOT/relative
 with (E/('ENTRY_BEFORE_'+path.name)).open('xb') as stream:stream.write(path.read_bytes())
 entry=title+f'用户要求制定下一大阶段及AI开发提示词并交OpenCode审查。本轮仅计划/18源预检/只读审查，无开发训练。当前[计划V3]({prefix}evidence/{E.name}/DEVELOPMENT_PLAN_V3.md)/[唯一拟实施L01–L18验收V3]({prefix}evidence/{E.name}/ACCEPTANCE_V3.md)/[开发提示词V3]({prefix}evidence/{E.name}/AI_DEVELOPMENT_PROMPT_V3.md)/[最终审查与SHA]({prefix}evidence/{E.name}/PLAN_REVIEW.md)/[回传]({prefix}returns/HFUS-LEARN-PLAN-03.md)。OpenCode R1 PLAN_REVISE→R2/V3最终PLAN_PASS，非ACCEPTED/非训练授权。10工作包含474队列项（282人工+192建议）、三族学习/场景实例/结构与因果时序、36作业上限30h/资源门、全1934+90对照与同应用版本页面。OOF与最终比较分表，旧N/Q/默认R1/GT/模型/数据/用户差异保留；未来须用户实际派发才做E0，E1须另外明确有界训练授权和可信标签门，不自动ML/HR09/下载安装/设备采集部署/Git写。本条不接管其他主线。\n\n'
 path.write_text(entry+path.read_text(encoding='utf-8-sig'),encoding='utf-8')
append(ROOT/'docs/human_fall/REVIEW_LOG.md',f'## 2026-10-15 HFUS-LEARN-PLAN-03 OpenCode计划审核\n\n用户明确要求OpenCode审查。独立只读plan进程，opencode-go/deepseek-v4.1-flash，session ses_ec24f08afffe9TTaza6EiWWMIB，edit/bash deny、snapshot=false；原始[R1](../human_capture/evidence/{E.name}/OPENCODE_REVIEW_R1.md)/[R2](../human_capture/evidence/{E.name}/OPENCODE_REVIEW_R2.md)/[R3](../human_capture/evidence/{E.name}/OPENCODE_REVIEW_R3.md)与[最终SHA/指针](../human_capture/evidence/{E.name}/PLAN_REVIEW.md)保留。R1 PLAN_REVISE（评估角色/资源预算等D1–D7）→V2 PLAN_PASS→V3最终PLAN_PASS；两项非阻断派发文字按R3允许收紧，审前字节/前后SHA留档。仅计划可执行性审查，不是E1许可/开发ACCEPTED，不曾训练/下载/安装/采集部署，最终工单SUBMITTED；L01–L18实施全NOT_RUN。')
(E/'GIT_STATUS_FINAL.txt').write_bytes(subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=ROOT))
files={str(p.relative_to(E)).replace('\\','/'):sha(p) for p in E.rglob('*') if p.is_file() and p.name not in ['ARTIFACT_INDEX.json','FINAL_PACKAGE.json']}
write(E/'ARTIFACT_INDEX.json',{'schema':'hfus-learn-plan-index/1','files':files})
write(E/'FINAL_PACKAGE.json',{'status':'SUBMITTED','review_decision':'PLAN_PASS','time_asia_shanghai':datetime.now(timezone(timedelta(hours=8))).isoformat(),
 'current_plan_sha256':sha(E/'CURRENT_PLAN.json'),'plan_review_sha256':sha(E/'PLAN_REVIEW.md'),'artifact_index_sha256':sha(E/'ARTIFACT_INDEX.json'),
 'return_sha256':sha(ret),'previous_sources_unchanged':True,'implementation_training_download_install_deployment':'NOT_RUN'})
print('SUBMITTED: V3 plan/prompt/acceptance final SHA bound; OpenCode PLAN_PASS; no implementation/training',flush=True)
