"""Actual same-session read-only follow-up for documentary/numeric scope findings."""
import json
import os
import shlex
import subprocess
from prepare import E,R,load,save

cfg=load(E/'opencode_readonly_config.json')
extra=[E/name for name in ['04_cohort_integrity.json','04_review_response.json','01_weighted_numeric_check.json',
    'weighted_numeric_check.py','close_review_findings.py','opencode_actual_model_02.json',
    'opencode_completion_02.json','04_opencode_raw_02_command.json','cli_version.stdout',
    'cli_effective_agent.stdout','opencode_permissions.json','inputs/cohort/03_normal_comparison.json',
    'inputs/cohort/01_leveling_index.json']]
for path in extra:
    for value in [str(path),path.as_posix(),str(path.relative_to(R)),path.relative_to(R).as_posix(),
                  str(path.relative_to(E)),path.relative_to(E).as_posix()]:
        cfg['permission']['read'][value]='allow';cfg['agent']['cl210audit']['permission']['read'][value]='allow'
save('opencode_readonly_config_03.json',cfg)
env=os.environ.copy();env['OPENCODE_CONFIG_CONTENT']=json.dumps(cfg);env['OPENCODE_DISABLE_AUTOUPDATE']='true'
session=load(E/'opencode_actual_model_02.json')['session']
prompt=f'''保持只读、同模型、同会话，补审动作项。证据根 {E.as_posix()}。
请重新read 01_root_cause.md 末尾的“数值一致门表述收窄补记”和“独审动作项关闭补记”，以及 04_cohort_integrity.json、inputs/cohort/03_normal_comparison.json、inputs/cohort/01_leveling_index.json、01_weighted_numeric_check.json、04_review_response.json。这些新增文件已在exact read白名单。
T108全集现按原CL2-07正常人体比较cohort闭合：原10 valid集合=原CLUSTER11人体作业中的valid集合=本轮10，目标外11集合相同，旧binding SHA复算后复制。模板/其他captures本就不在预注册cohort，不按新结果剔除；没有扩大宣称全部任意capture。
ROI明确algorithm_candidate、ground_confirmed=false；报告selector=dd1b58 frozen，本轮TLS诊断不调用selector，d0b3e3只用于09C搜索回归，核心quality/TLS代码相同。
另需主动核查作者收窄的数值门措辞：目标帧等权对raw SVD角差约0.000032°、offset差7.10e-7m，确实PASS数值容差，但72 P95仍FAIL；ROI等权数值门FAIL且144 P95 FAIL。“非raw算法身份”不能推断每个实验必超容差，此前过宽文字以追加补记纠正，原AB数据未变。
T110实际CLI/model/有效权限/exit记录已开放，可read opencode_actual_model_02.json、04_opencode_raw_02_command.json、cli_effective_agent.stdout 和 opencode_permissions.json；不需自证/伪称你执行SHA。最终return/manifest仍在补审后封存。
请针对新增证据给补审报告：是否关闭T100措辞和T108集合缺口？数值门区分是否准确？有无未解决逻辑FAIL？总体是否保持BLOCKED、无修复资格？保留原意见/UNKNOWN，不降低标准。最后AUDIT_COMPLETE。
'''
(E/'opencode_prompt_03.txt').write_text(prompt,encoding='utf8')
argv=['D:/APPS/Git/bin/bash.exe','-c','opencode run --pure --agent cl210audit --format json --model opencode-go/deepseek-v4.1-flash --session '+shlex.quote(session)+' '+shlex.quote(prompt)]
with (E/'04_opencode_raw_03.stdout').open('xb') as out,(E/'04_opencode_raw_03.stderr').open('xb') as err:
    p=subprocess.run(argv,cwd=E,env=env,stdout=out,stderr=err)
save('04_opencode_raw_03_command.json',dict(argv=argv,cwd=str(E),exit_code=p.returncode,configuration='opencode_readonly_config_03.json'))
events=[]
for line in (E/'04_opencode_raw_03.stdout').read_text(encoding='utf8',errors='replace').splitlines():
    try:events.append(json.loads(line))
    except json.JSONDecodeError:pass
report='\n\n'.join(x.get('part',{}).get('text','') for x in events if x.get('type')=='text')
(E/'04_independent_review_03.md').write_text(report,encoding='utf8')
save('opencode_completion_03.json',dict(exit_code=p.returncode,marker='AUDIT_COMPLETE' in report,session=session,
    tool_events=[x['part'] for x in events if x.get('type')=='tool_use']))
export_argv=['D:/APPS/Git/bin/bash.exe','-c','opencode export '+shlex.quote(session)]
with (E/'opencode_session_export_03.stdout').open('xb') as out,(E/'opencode_session_export_03.stderr').open('xb') as err:
    ex=subprocess.run(export_argv,cwd=E,env=env,stdout=out,stderr=err)
save('opencode_session_export_03_command.json',dict(argv=export_argv,cwd=str(E),exit_code=ex.returncode))
infos=[x['info'] for x in load(E/'opencode_session_export_03.stdout')['messages'] if x.get('info',{}).get('role')=='assistant']
save('opencode_actual_model_03.json',dict(models=sorted({m.get('providerID','')+'/'+m.get('modelID','') for m in infos}),
    session=session,last_finish=infos[-1].get('finish'),exit_code=p.returncode,export_exit_code=ex.returncode,
    CLI_version=(E/'cli_version.stdout').read_text().strip()))
print('SUPPLEMENT_AUDIT_EXIT',p.returncode,'REPORT_CHARS',len(report),flush=True)
