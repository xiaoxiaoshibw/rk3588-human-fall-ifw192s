"""Actual read-only independent CLI review; process-local exact file permissions."""
import json
import os
import shlex
import subprocess
import sys
from prepare import E,R,B,load,save

SHELL='D:/APPS/Git/bin/bash.exe'

def cli(label, command, env=None):
    argv=[SHELL,'-c',command]
    with (E/(label+'.stdout')).open('xb') as out,(E/(label+'.stderr')).open('xb') as err:
        process=subprocess.run(argv,cwd=E,env=env,stdout=out,stderr=err)
    save(label+'_command.json',dict(argv=argv,cwd=str(E),exit_code=process.returncode))
    return process.returncode

if len(sys.argv)>1 and sys.argv[1]=='preflight':
    for label,command in [('cli_version','opencode --version'),('cli_help','opencode run --help'),
                          ('cli_models','opencode models opencode-go')]:
        code=cli(label + (sys.argv[2] if len(sys.argv)>2 else ''),command)
        print(label,code,flush=True)
        if code:raise SystemExit(code)
    suffix=sys.argv[2] if len(sys.argv)>2 else ''
    assert 'opencode-go/deepseek-v4.1-flash' in (E/('cli_models'+suffix+'.stdout')).read_text(encoding='utf8')
    raise SystemExit(0)

allowed=[E/n for n in ['PONYTAIL_SKILL.md','00_SCOPE_AND_ACCEPTANCE.md','02_fix.patch',
    '03_profile_03.json','04_benchmark.json','05_regression_03_command.json','05_regression_03.stderr',
    '06_session121647.json','06_session_final_binding.json','candidate_version.json','source_summary.json','07_AUTHOR_ANALYSIS.md',
    'test_selector.py','test_equivalence.py','benchmark.py','session_probe.py','prepare.py','run_checks.py']]
allowed += [p for root in [E/'baseline',E/'candidate',E/'frozen'] for p in root.rglob('*.py')]
allowed += [B/'FINAL_REPORT.md',B/'02_fix.patch']
read={'*':'deny'}
for path in allowed:
    names={str(path),path.as_posix(),str(path.relative_to(R)),path.relative_to(R).as_posix()}
    if path.is_relative_to(E):names.update({str(path.relative_to(E)),path.relative_to(E).as_posix()})
    for name in names:read[name]='allow'
permission={'*':'deny','read':read,'external_directory':'deny'}
cfg={'permission':permission,'agent':{'cl209caudit':{
    'description':'CL2-09C exact optimization read-only audit','mode':'primary','permission':permission,
    'prompt':'Read only. No shell/write/task/network tools. Inspect evidence; do not claim running numeric or SHA checks.'}},
    'mcp':{},'plugin':[]}
save('opencode_readonly_config.json',cfg)
env=os.environ.copy();env['OPENCODE_CONFIG_CONTENT']=json.dumps(cfg);env['OPENCODE_DISABLE_AUTOUPDATE']='true'
assert cli('cli_effective_agent','opencode debug agent cl209caudit --pure',env)==0
agent=load(E/'cli_effective_agent.stdout')
assert agent['tools']['read'] and not any(v for k,v in agent['tools'].items() if k!='read')
save('opencode_permissions.json',dict(tools=agent['tools'],files=[str(p) for p in allowed],
     scope='Only read. Exact Git-project-relative and absolute allowlist. CLI own DB/log writes are normal runtime.'))
prompt='''你是 CL2-09C 独立只读审计员，指定模型 opencode-go/deepseek-v4.1-flash。先读取 PONYTAIL_SKILL.md 和 00_SCOPE_AND_ACCEPTANCE.md。
仅审计 09B 冻结基线后的等价性能优化；不重复 CL2-07～09A 审计、不接生产、不改门控。
重点读取 baseline/floor_sheet.py、candidate/floor_sheet.py、02_fix.patch、test_equivalence.py、benchmark.py 和证据。
检查：预计算整数差的 hypot 是否完全保持浮点结果；嵌套循环的部分最小间距剪枝是否必然安全；winner_sep 随循环更新会否删掉更优或改变稳定并列；共线和重复行为是否保持；原成功和拒绝完整 dict 是否相同；无 cap 是否仍可能最坏 O(n4)；剖析分项边界/开销披露是否诚实；基准是否真正无 mock 且同输入同环境；35 原回归和新差分完整性；121647 门控和 BLOCKED。
按 C01–C09/E01/D01 逐项给中文报告。你没有执行数值或 SHA，作者执行证据和自身只读审查明确区分，未亲自复算标 UNKNOWN，不把 UNKNOWN 当逻辑 FAIL。主动找具体反例、代码行和最小范围内修复。有真实 FAIL 则保留，不降低验收。
最终 manifest/return 在审计后追加；source_summary 是前置完整性，不假称最终 seal 已闭合。结束写 AUDIT_COMPLETE。
用 read filePath 读取以下绝对路径：
'''+ '\n'.join(p.as_posix() for p in allowed)
(E/'opencode_prompt.txt').write_text(prompt,encoding='utf8')
code=cli('08_opencode_raw','opencode run --pure --agent cl209caudit --format json --model opencode-go/deepseek-v4.1-flash '+shlex.quote(prompt),env)
events=[]
for line in (E/'08_opencode_raw.stdout').read_text(encoding='utf8',errors='replace').splitlines():
    try:events.append(json.loads(line))
    except json.JSONDecodeError:pass
report='\n\n'.join(x.get('part',{}).get('text','') for x in events if x.get('type')=='text')
(E/'08_OPENCODE_REVIEW.md').write_text(report,encoding='utf8')
sessions=sorted({x['sessionID'] for x in events if x.get('sessionID')})
save('opencode_completion.json',dict(exit_code=code,marker='AUDIT_COMPLETE' in report,session_ids=sessions,
     tool_events=[x['part'] for x in events if x.get('type')=='tool_use']))
if len(sessions)==1:
    exit_code=cli('opencode_session_export','opencode export '+shlex.quote(sessions[0]),env)
    exported=load(E/'opencode_session_export.stdout')
    infos=[x['info'] for x in exported['messages'] if x.get('info',{}).get('role')=='assistant']
    save('opencode_actual_model.json',dict(models=sorted({x.get('providerID','')+'/'+x.get('modelID','') for x in infos}),
         session=sessions[0],last_finish=infos[-1].get('finish'),export_exit_code=exit_code,
         CLI_version=(E/'cli_version_02.stdout').read_text().strip(),exit_code=code))
print('OPENCODE_EXIT',code,'REPORT_CHARS',len(report),flush=True)
