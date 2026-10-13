"""Verified 09B/09C CLI route reused; exact read-only whitelist and actual export."""
import json
import os
import shlex
import subprocess
from prepare import E,R,load,save,sha

SHELL='D:/APPS/Git/bin/bash.exe'
def cli(label,command,env=None):
    argv=[SHELL,'-c',command]
    with (E/(label+'.stdout')).open('xb') as out,(E/(label+'.stderr')).open('xb') as err:
        process=subprocess.run(argv,cwd=E,env=env,stdout=out,stderr=err)
    save(label+'_command.json',dict(argv=argv,cwd=str(E),exit_code=process.returncode))
    return process.returncode

for label,command in [('cli_version','opencode --version'),('cli_help','opencode run --help'),
                       ('cli_models','opencode models opencode-go')]:
    code=cli(label,command)
    if code:
        save('opencode_failure.json',dict(status='AUDIT_BLOCKED',stage=label,exit_code=code))
        raise SystemExit(code)
assert 'opencode-go/deepseek-v4.1-flash' in (E/'cli_models.stdout').read_text(encoding='utf8')
allowed=[E/name for name in ['PONYTAIL_SKILL.md','00_SCOPE_AND_ACCEPTANCE.md','00_EXPERIMENT_PLAN.md',
    '00_input_catalog.json','00_baseline.json','00_prepare_attempt1.md','00_prepare_02.stderr','00_prepare_03.stdout',
    '01_root_cause.md','01_reproduction.json','01_channel_diagnostics.json','01_gate_cross_checks.json',
    '02_shadow_ab_results.json','03_regression_results.txt','03_regression_command.json',
    '03_search_performance.json','03_search_paired.json','04_source_summary.json',
    '04_audit_numeric_bundle.json','04_audit_summary.json','README.md']]
allowed += list(E.glob('*.py'))
allowed += [p for root in [E/'candidate',E/'frozen',E/'baseline'] for p in root.rglob('*.py')]
allowed += [p for p in (E/'inputs').rglob('*.json')]
read={'*':'deny'}
for path in allowed:
    for value in [str(path),path.as_posix(),str(path.relative_to(R)),path.relative_to(R).as_posix(),
                  str(path.relative_to(E)),path.relative_to(E).as_posix()]:read[value]='allow'
permission={'*':'deny','read':read,'external_directory':'deny'}
config={'permission':permission,'agent':{'cl210audit':dict(description='CL2-10 causal-diagnosis read-only audit',
    mode='primary',permission=permission,
    prompt='Read-only audit. No shell, writing, task, network or other tool actions. Do not claim numerical/SHA executions.')},
    'mcp':{},'plugin':[]}
save('opencode_readonly_config.json',config)
env=os.environ.copy();env['OPENCODE_CONFIG_CONTENT']=json.dumps(config);env['OPENCODE_DISABLE_AUTOUPDATE']='true'
assert cli('cli_effective_agent','opencode debug agent cl210audit --pure',env)==0
agent=load(E/'cli_effective_agent.stdout')
assert agent['tools']['read'] and not any(value for key,value in agent['tools'].items() if key!='read')
save('opencode_permissions.json',dict(tools=agent['tools'],allowed=[str(p) for p in allowed],
     scope='Only exact file read. All other agent actions denied. CLI normal model requests and DB/log writes are runtime.'))
prompt='''你是 CL2-10 独立只读审计员，实际指定模型 opencode-go/deepseek-v4.1-flash。
先读 PONYTAIL_SKILL.md、00_SCOPE_AND_ACCEPTANCE.md、00_EXPERIMENT_PLAN.md，然后 diagnostics.py/cross_checks.py、01_root_cause.md、04_audit_summary.json 和实际源/证据。
本轮目标是121647真实TLS失败因果调查。作者目前结论BLOCKED：数值失配可复现，但物理原因UNKNOWN、无CL2-10算法修复。candidate/只保存复用的冻结09C，不是假称新的修复。
主动检查并反驳：因果推论是否过强？对局部平面反事实是否偷偷改成一个新的TLS有效性定义？D-ROI-EQUAL是否隐藏144失败/其他ROI恶化？FIT/固定holdout与跨样本是否泄漏、是否仅针对某SID/帧号硬编码？所有点/困难ROI是否保留？是否放宽50mm/RMS/支持/几何/数值一致门？仅刚体坐标不变性是否被冒称真实外参正确？正常同ROI编号是否被混当同一空间？ring/位置混杂是否如实报告？是否应编码修复还是保持BLOCKED？
核查46项回归、11段原TLS有效性和标量复算、原始七数组行绑定、paired性能对照和09C源码SHA。不要重复09C性能开发/07～09A整套审计；仅本轮继承基线和因果归因边界。
请逐T100–T111/TLS01/E01/D01给中文报告，列具体逻辑FAIL、证据不足与非阻塞建议；未亲自执行数值/SHA一律UNKNOWN，不以UNKNOWN当逻辑FAIL，也不虚构执行。CL2-10总体应依据用户八条件，只在全部满足才PASS，不因测试数而PASS。明确评价是否已具备修复/后续开发资格。
最终return/manifest在独审后写入，04_source_summary是前置 guard，不假称final seal已完成。结束写 AUDIT_COMPLETE。
只用read filePath访问以下绝对路径：
'''+ '\n'.join(p.as_posix() for p in allowed)
(E/'opencode_prompt.txt').write_text(prompt,encoding='utf8')
code=cli('04_opencode_raw','opencode run --pure --agent cl210audit --format json --model opencode-go/deepseek-v4.1-flash '+shlex.quote(prompt),env)
events=[]
for line in (E/'04_opencode_raw.stdout').read_text(encoding='utf8',errors='replace').splitlines():
    try:events.append(json.loads(line))
    except json.JSONDecodeError:pass
report='\n\n'.join(x.get('part',{}).get('text','') for x in events if x.get('type')=='text')
(E/'04_independent_review.md').write_text(report,encoding='utf8')
sessions=sorted({x['sessionID'] for x in events if x.get('sessionID')})
save('opencode_completion.json',dict(exit_code=code,marker='AUDIT_COMPLETE' in report,session_ids=sessions,
     tool_events=[x['part'] for x in events if x.get('type')=='tool_use']))
if len(sessions)==1:
    ex=cli('opencode_session_export','opencode export '+shlex.quote(sessions[0]),env)
    infos=[x['info'] for x in load(E/'opencode_session_export.stdout')['messages'] if x.get('info',{}).get('role')=='assistant']
    save('opencode_actual_model.json',dict(models=sorted({m.get('providerID','')+'/'+m.get('modelID','') for m in infos}),
      session=sessions[0],last_finish=infos[-1].get('finish'),exit_code=code,export_exit_code=ex,
      CLI_version=(E/'cli_version.stdout').read_text().strip()))
print('AUDIT_EXIT',code,'REPORT_CHARS',len(report),flush=True)
